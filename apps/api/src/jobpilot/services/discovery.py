"""Discovery runs: fetch a followed board, filter by preferences, store new postings through the
shared job pipeline, and record observations and source health.

Idempotent: postings are keyed by (source, provider posting id) and by the pipeline's URL and
description checks, so repeating a run never creates duplicates. Logs carry counts only.
"""

import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from jobpilot.core.config import Settings
from jobpilot.db.models import Job, JobSource, SourceRun
from jobpilot.services.applications import set_status
from jobpilot.services.extraction.openai_extractor import OpenAIExtractor
from jobpilot.services.jobs import NewJob, ingest_job, stored_requirements
from jobpilot.services.matching import job_facts, title_similarity
from jobpilot.services.preferences import JobPreferences, check_hard_filters, contains_word
from jobpilot.services.sources.base import FeedFormatError, NormalizedPosting
from jobpilot.services.sources.fetcher import FeedFetcher, FetchError
from jobpilot.services.sources.providers import ADAPTERS

logger = logging.getLogger(__name__)

TITLE_MATCH_THRESHOLD = 0.5  # Share of a target title's words that must appear in the posting title
MAX_BACKOFF = timedelta(hours=24)
RATE_LIMIT_RETRY = timedelta(minutes=15)


@dataclass(frozen=True)
class Prefilter:
    passed: bool
    reason: str | None = None


def prefilter(posting: NormalizedPosting, company: str, preferences: JobPreferences) -> Prefilter:
    """Cheap checks before storing anything: exclusions and target titles."""
    if any(company.lower() == c.lower() for c in preferences.excluded_companies):
        return Prefilter(False, "excluded company")
    text = f"{posting.title}\n{posting.description}"
    if any(contains_word(text, k) for k in preferences.exclude_keywords):
        return Prefilter(False, "excluded keyword")
    targets = preferences.target_titles
    if targets and max(title_similarity(t, posting.title) for t in targets) < TITLE_MATCH_THRESHOLD:
        return Prefilter(False, "title does not match your targets")
    return Prefilter(True)


def requests_in_last_hour(session: Session, now: datetime) -> int:
    return session.scalar(select(func.coalesce(func.sum(SourceRun.attempts), 0))
                          .where(SourceRun.started_at >= now - timedelta(hours=1)))


def run_source(session: Session, source: JobSource, *, fetcher: FeedFetcher, settings: Settings,
               preferences: JobPreferences, ai: OpenAIExtractor | None, trigger: str,
               now: datetime | None = None) -> SourceRun:
    """Run discovery for one source. Commits its own work. Never raises for feed problems."""
    now = now or datetime.now(UTC)
    run = SourceRun(source_id=source.id, trigger=trigger, status="running", attempts=0,
                    fetched=0, new_jobs=0, seen_again=0, filtered_out=0, archived=0, closed=0)
    session.add(run)
    source.last_run_at = now

    if requests_in_last_hour(session, now) >= settings.discovery_max_requests_per_hour:
        run.status, run.error_code = "skipped", "local_rate_limit"
        run.error_message = "Skipped: the hourly request limit for job feeds was reached."
        source.next_run_at = now + RATE_LIMIT_RETRY
        return _finish(session, run, source)

    adapter = ADAPTERS[source.provider]
    try:
        result = fetcher.fetch_json(adapter.feed_url(source.board), adapter.host)
        run.attempts, run.http_status = result.attempts, result.http_status
        postings = adapter.parse(result.payload)
    except FetchError as error:
        run.attempts, run.http_status = error.attempts, error.http_status
        return _fail(session, run, source, error.code, str(error), now)
    except FeedFormatError:
        return _fail(session, run, source, "invalid_format", "The job feed had an unexpected format.", now)

    run.fetched = len(postings)
    complete = len(postings) <= settings.discovery_max_postings_per_source
    postings = postings[: settings.discovery_max_postings_per_source]
    extractor = ai if settings.discovery_use_ai else None
    known = {
        job.source_external_id: job
        for job in session.scalars(select(Job).where(Job.source_id == source.id))
    }

    for posting in postings:
        job = known.get(posting.external_id)
        if job is not None:  # Seen before: record the observation only.
            job.last_seen_at, job.closed_at = now, None
            run.seen_again += 1
            continue
        if not prefilter(posting, source.company_name, preferences).passed:
            run.filtered_out += 1
            continue
        _store(session, source, posting, preferences, extractor, now, run, known)

    if complete:  # Only a full feed can tell us a posting is gone.
        listed = {p.external_id for p in postings}
        gone = [external_id for external_id, job in known.items()
                if external_id not in listed and job.closed_at is None]
        if gone:
            session.execute(update(Job).where(Job.source_id == source.id, Job.source_external_id.in_(gone))
                            .values(closed_at=now))
        run.closed = len(gone)

    run.status = "success"
    source.status, source.consecutive_failures = "healthy", 0
    source.last_success_at = now
    source.last_error_code = source.last_error_message = None
    source.next_run_at = now + timedelta(minutes=source.interval_minutes)
    if not complete:
        run.error_message = f"Only the first {settings.discovery_max_postings_per_source} postings were read."
    return _finish(session, run, source)


def _store(session: Session, source: JobSource, posting: NormalizedPosting, preferences: JobPreferences,
           extractor: OpenAIExtractor | None, now: datetime, run: SourceRun, known: dict) -> None:
    new = NewJob(
        description=posting.description, url=posting.url, title=posting.title, company=source.company_name,
        application_status="discovered",
        structured={**posting.structured, "title": posting.title, "company": source.company_name},
        source_fields={"source_id": source.id, "source_external_id": posting.external_id,
                       "posted_at": posting.posted_at, "first_seen_at": now, "last_seen_at": now},
    )
    job, duplicate = ingest_job(session, new, extractor)
    known[posting.external_id] = job
    if duplicate:  # Already saved (e.g. pasted in by the user): start tracking its observations.
        if job.source_id is None:
            job.source_id, job.source_external_id = source.id, posting.external_id
            job.first_seen_at = job.first_seen_at or now
        job.last_seen_at, job.closed_at = now, None
        run.seen_again += 1
        return
    run.new_jobs += 1
    failures = [f for f in check_hard_filters(preferences, job_facts(stored_requirements(job), job.description))
                if f.status == "fail"]
    if failures:
        set_status(session, job, "archived", note="Filtered out: " + " ".join(f.reason for f in failures))
        run.archived += 1


def _fail(session: Session, run: SourceRun, source: JobSource, code: str, message: str,
          now: datetime) -> SourceRun:
    run.status, run.error_code, run.error_message = "failed", code, message[:200]
    source.consecutive_failures += 1
    source.status = "failing" if source.consecutive_failures >= 3 else "degraded"
    source.last_error_code, source.last_error_message = code, message[:200]
    backoff = timedelta(minutes=source.interval_minutes) * 2 ** min(source.consecutive_failures - 1, 6)
    source.next_run_at = now + min(backoff, MAX_BACKOFF)
    return _finish(session, run, source)


def _finish(session: Session, run: SourceRun, source: JobSource) -> SourceRun:
    run.finished_at = datetime.now(UTC)
    session.commit()
    logger.info(
        "discovery run source=%s provider=%s status=%s attempts=%d fetched=%d new=%d seen_again=%d "
        "filtered=%d archived=%d closed=%d error=%s",
        source.id, source.provider, run.status, run.attempts, run.fetched, run.new_jobs, run.seen_again,
        run.filtered_out, run.archived, run.closed, run.error_code,
    )
    return run

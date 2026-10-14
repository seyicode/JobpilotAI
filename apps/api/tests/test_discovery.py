"""Discovery runs against fictional feeds. No real network requests are made."""

import copy
import logging
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from feed_samples import GREENHOUSE
from sqlalchemy import select

from jobpilot.api.routes.sources import get_feed_fetcher
from jobpilot.core.config import Settings
from jobpilot.db.models import Job, JobSource, SourceRun
from jobpilot.services.discovery import prefilter, run_source
from jobpilot.services.preferences import JobPreferences
from jobpilot.services.sources.base import NormalizedPosting
from jobpilot.services.sources.fetcher import FeedFetcher

T0 = datetime(2026, 10, 14, 9, 0, tzinfo=UTC)
SETTINGS = Settings(discovery_retry_base_delay_seconds=0, discovery_max_retries=0)


class Feed:
    """Serves queued responses; records how many requests were made."""

    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls = 0

    def __call__(self, request):
        self.calls += 1
        item = self.responses.pop(0)
        return item if isinstance(item, httpx.Response) else httpx.Response(200, json=item)


def fetcher(feed: Feed, settings: Settings = SETTINGS) -> FeedFetcher:
    return FeedFetcher(settings, transport=httpx.MockTransport(feed), sleep=lambda _: None)


@pytest.fixture
def session(session_factory):
    with session_factory() as session:
        yield session


@pytest.fixture
def source(session):
    source = JobSource(provider="greenhouse", board="examplecorp", company_name="Example Corp", enabled=True,
                       interval_minutes=360, status="new", consecutive_failures=0)
    session.add(source)
    session.commit()
    return source


NO_PREFERENCES = JobPreferences()


def run(session, source, feed, preferences=NO_PREFERENCES, now=T0, settings=SETTINGS):
    return run_source(session, source, fetcher=fetcher(feed, settings), settings=settings,
                      preferences=preferences, ai=None, trigger="scheduled", now=now)


def jobs(session):
    return {j.source_external_id: j for j in session.scalars(select(Job))}


def test_new_postings_go_through_the_shared_pipeline(session, source):
    result = run(session, source, Feed(GREENHOUSE))
    assert (result.status, result.fetched, result.new_jobs, result.filtered_out) == ("success", 2, 2, 0)
    job = jobs(session)["4012345"]
    assert (job.application_status, job.company, job.title) == ("discovered", "Example Corp", "Senior Backend Engineer")
    assert job.source_url == "https://boards.greenhouse.io/examplecorp/jobs/4012345"
    assert (job.first_seen_at, job.last_seen_at, job.closed_at) == (T0, T0, None)
    assert job.posted_at.year == 2026
    assert job.extraction_method == "rules"  # AI is never used for discovery unless enabled
    requirements = job.requirements
    assert requirements["work_arrangement"] == "remote"  # from the feed's structured data
    assert requirements["salary"] == {"min": 80000, "max": 95000, "currency": "GBP", "period": "year"}
    assert set(requirements["required_skills"]) >= {"Python", "PostgreSQL"}  # from text extraction
    assert (source.status, source.last_success_at, source.next_run_at) == ("healthy", T0, T0 + timedelta(hours=6))


def test_runs_are_idempotent_and_track_observations(session, source):
    run(session, source, Feed(GREENHOUSE))
    later = T0 + timedelta(hours=6)
    again = run(session, source, Feed(GREENHOUSE), now=later)
    assert (again.new_jobs, again.seen_again, again.closed) == (0, 2, 0)
    assert len(jobs(session)) == 2
    assert jobs(session)["4012345"].first_seen_at == T0
    assert jobs(session)["4012345"].last_seen_at == later


def test_postings_that_disappear_are_closed_and_can_reopen(session, source):
    run(session, source, Feed(GREENHOUSE))
    shorter = copy.deepcopy(GREENHOUSE)
    shorter["jobs"] = shorter["jobs"][:1]
    result = run(session, source, Feed(shorter), now=T0 + timedelta(hours=6))
    assert result.closed == 1
    assert jobs(session)["4012346"].closed_at == T0 + timedelta(hours=6)
    run(session, source, Feed(GREENHOUSE), now=T0 + timedelta(hours=12))
    assert jobs(session)["4012346"].closed_at is None


def test_truncated_feeds_never_close_postings(session, source):
    run(session, source, Feed(GREENHOUSE))
    limited = Settings(discovery_max_postings_per_source=1, discovery_retry_base_delay_seconds=0)
    result = run(session, source, Feed(GREENHOUSE), now=T0 + timedelta(hours=6), settings=limited)
    assert result.closed == 0 and "Only the first 1 postings" in result.error_message


def test_preferences_filter_and_archive(session, source):
    preferences = JobPreferences(target_titles=["Backend Engineer"], work_arrangements=["onsite"],
                                 hard_filters=["work_arrangement"])
    result = run(session, source, Feed(GREENHOUSE), preferences=preferences)
    assert (result.new_jobs, result.filtered_out, result.archived) == (1, 1, 1)
    job = jobs(session)["4012345"]  # remote, but you want on-site only
    assert job.application_status == "archived"
    assert "4012346" not in jobs(session)  # "Office Manager" is not a target title


@pytest.mark.parametrize(("preferences", "reason"), [
    (JobPreferences(excluded_companies=["example corp"]), "excluded company"),
    (JobPreferences(exclude_keywords=["payments"]), "excluded keyword"),
    (JobPreferences(target_titles=["Designer"]), "title does not match your targets"),
])
def test_prefilter(preferences, reason):
    posting = NormalizedPosting(external_id="1", title="Backend Engineer", description="We do payments.",
                                url="https://x")
    assert prefilter(posting, "Example Corp", preferences).reason == reason
    assert prefilter(posting, "Other", JobPreferences(target_titles=["backend engineer"])).passed


def test_existing_pasted_job_is_linked_not_duplicated(db_client, session_factory):
    db_client.post("/jobs", json={"description": "Pasted earlier. " * 10,
                                  "source_url": "https://boards.greenhouse.io/examplecorp/jobs/4012345"})
    with session_factory() as session:
        source = JobSource(provider="greenhouse", board="examplecorp", company_name="Example Corp", enabled=True,
                           interval_minutes=360, status="new", consecutive_failures=0)
        session.add(source)
        session.commit()
        result = run(session, source, Feed(GREENHOUSE))
        assert (result.new_jobs, result.seen_again) == (1, 1)
        pasted = jobs(session)["4012345"]
        assert pasted.application_status == "shortlisted" and pasted.source_id == source.id


def test_failures_back_off_and_mark_health(session, source):
    for attempt in range(1, 4):
        result = run(session, source, Feed(httpx.Response(503)), now=T0)
        assert (result.status, result.error_code) == ("failed", "http_503")
    assert (source.status, source.consecutive_failures) == ("failing", 3)
    assert source.next_run_at == T0 + timedelta(hours=24)  # 6h x 4, capped at 24h
    assert source.last_error_message == "The job feed returned an error (503)."
    run(session, source, Feed(GREENHOUSE), now=T0 + timedelta(days=1))
    assert (source.status, source.consecutive_failures, source.last_error_code) == ("healthy", 0, None)


def test_bad_feed_shapes_fail_cleanly(session, source):
    result = run(session, source, Feed({"unexpected": True}))
    assert (result.status, result.error_code, source.status) == ("failed", "invalid_format", "degraded")


def test_hourly_request_limit_skips_without_fetching(session, source):
    feed = Feed()
    limited = Settings(discovery_max_requests_per_hour=1)
    session.add(SourceRun(source_id=source.id, trigger="manual", status="success", attempts=1,
                          started_at=T0 - timedelta(minutes=5), fetched=0, new_jobs=0, seen_again=0,
                          filtered_out=0, archived=0, closed=0))
    session.commit()
    result = run(session, source, feed, settings=limited)
    assert (result.status, result.error_code, feed.calls) == ("skipped", "local_rate_limit", 0)
    assert source.consecutive_failures == 0 and source.next_run_at == T0 + timedelta(minutes=15)


def test_logs_have_counts_not_content(session, source, caplog):
    caplog.set_level(logging.DEBUG)
    run(session, source, Feed(GREENHOUSE))
    assert "discovery run" in caplog.text and "new=2" in caplog.text
    for secret in ("Senior Backend Engineer", "payments", "examplecorp", "greenhouse.io"):
        assert secret not in caplog.text


# API


def test_source_management(db_client):
    providers = db_client.get("/sources/providers").json()
    assert [p["provider"] for p in providers] == ["greenhouse", "lever", "ashby"]
    created = db_client.post("/sources", json={"provider": "lever", "board": " examplelabs ",
                                               "company_name": " Example  Labs "})
    assert created.status_code == 201
    body = created.json()
    assert (body["board"], body["company_name"], body["interval_minutes"], body["status"]) == (
        "examplelabs", "Example Labs", 360, "new")
    assert db_client.post("/sources", json={"provider": "lever", "board": "examplelabs",
                                            "company_name": "Again"}).status_code == 409
    assert db_client.post("/sources", json={"provider": "lever", "board": "../x",
                                            "company_name": "Bad"}).status_code == 422
    assert db_client.post("/sources", json={"provider": "indeed", "board": "x",
                                            "company_name": "Bad"}).status_code == 422
    too_fast = db_client.patch(f"/sources/{body['id']}", json={"interval_minutes": 5})
    assert too_fast.status_code == 422
    paused = db_client.patch(f"/sources/{body['id']}", json={"enabled": False, "interval_minutes": 120}).json()
    assert (paused["enabled"], paused["interval_minutes"]) == (False, 120)
    assert db_client.delete(f"/sources/{body['id']}").status_code == 204


def test_run_now_with_cooldown_and_history(db_client):
    source = db_client.post("/sources", json={"provider": "greenhouse", "board": "examplecorp",
                                              "company_name": "Example Corp"}).json()
    feed = Feed(GREENHOUSE)
    db_client.app.dependency_overrides[get_feed_fetcher] = lambda: fetcher(feed)
    first = db_client.post(f"/sources/{source['id']}/run")
    assert first.status_code == 200 and first.json()["new_jobs"] == 2
    again = db_client.post(f"/sources/{source['id']}/run")
    assert again.status_code == 429 and int(again.headers["retry-after"]) > 0
    assert feed.calls == 1
    runs = db_client.get(f"/sources/{source['id']}/runs").json()
    assert [(r["trigger"], r["status"], r["fetched"]) for r in runs] == [("manual", "success", 2)]
    listed = db_client.get("/jobs").json()
    assert {j["application_status"] for j in listed} == {"discovered"}

    db_client.delete(f"/sources/{source['id']}")
    assert len(db_client.get("/jobs").json()) == 2  # jobs are kept when unfollowing

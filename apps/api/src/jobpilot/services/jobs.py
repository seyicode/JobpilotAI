"""The one job pipeline, shared by pasted jobs and discovered jobs:
deduplicate -> extract requirements -> (optionally) apply structured overrides -> store.
Matching is computed on request from what is stored here.
"""

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime

from pydantic import ValidationError
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from jobpilot.db.models import Experience, Job, Skill
from jobpilot.services.extraction import ExtractionOutcome, extract_requirements
from jobpilot.services.extraction.openai_extractor import OpenAIExtractor
from jobpilot.services.extraction.schema import JobRequirements
from jobpilot.services.job_ingestion import canonical_url, description_fingerprint
from jobpilot.services.matching import MatchResult, VerifiedProfile, match_job
from jobpilot.services.preferences import JobPreferences

logger = logging.getLogger(__name__)


@dataclass
class NewJob:
    """A job to store. `url` must already be validated by the caller."""

    description: str
    url: str | None = None
    title: str | None = None
    company: str | None = None
    application_status: str = "shortlisted"
    # Facts a structured source reported directly (location, salary, ...). They take priority
    # over text extraction because they come from the employer's own data, not from parsing.
    structured: dict = field(default_factory=dict)
    source_fields: dict = field(default_factory=dict)  # Origin columns for discovered jobs


def find_duplicate(session: Session, fingerprint: str, url: str | None) -> Job | None:
    condition = Job.description_hash == fingerprint
    if url:
        condition = or_(condition, Job.canonical_url == url)
    return session.scalars(select(Job).where(condition).limit(1)).first()


def ingest_job(session: Session, new: NewJob, ai: OpenAIExtractor | None) -> tuple[Job, bool]:
    """Store a job unless it is a duplicate. Returns (job, duplicate). The caller commits.

    Duplicate checks happen before extraction, so duplicates never cost an AI request."""
    url = canonical_url(new.url) if new.url else None
    fingerprint = description_fingerprint(new.description)
    existing = find_duplicate(session, fingerprint, url)
    if existing is not None:
        return existing, True

    job = Job(
        title=new.title, company=new.company, source_url=new.url, canonical_url=url,
        description=new.description, description_hash=fingerprint,
        application_status=new.application_status, **new.source_fields,
    )
    apply_extraction(job, extract_for_job(session, job, ai), structured=new.structured)
    savepoint = session.begin_nested()
    session.add(job)
    try:
        savepoint.commit()
    except IntegrityError:  # Stored by a concurrent request; use that one.
        savepoint.rollback()
        existing = find_duplicate(session, fingerprint, url)
        if existing is None:
            raise
        return existing, True
    logger.info("job created id=%s chars=%d has_url=%s extraction=%s",
                job.id, len(job.description), bool(url), job.extraction_method)
    return job, False


def extract_for_job(session: Session, job: Job, ai: OpenAIExtractor | None) -> ExtractionOutcome:
    library_skills = list(session.scalars(select(Skill.name)))
    return extract_requirements(
        session, job.description, title=job.title, company=job.company,
        extra_skills=library_skills, ai=ai,
    )


def apply_extraction(job: Job, outcome: ExtractionOutcome, structured: dict | None = None) -> None:
    requirements = outcome.requirements
    note = outcome.note
    if structured:
        requirements = merge_structured(requirements, structured)
        note = f"{note} Location, arrangement, type and pay from the job feed were used where given."
    job.requirements = requirements.model_dump()
    job.extraction_method = outcome.method
    job.extraction_note = note[:200] if note else None
    job.extracted_at = datetime.now(UTC)
    job.title = requirements.title or job.title
    job.company = requirements.company or job.company


def merge_structured(requirements: JobRequirements, structured: dict) -> JobRequirements:
    """Overlay non-empty structured fields on extracted requirements, then re-validate."""
    data = requirements.model_dump()
    for key, value in structured.items():
        if key == "salary" and isinstance(value, dict):
            if any(v is not None for v in value.values()):
                data["salary"] = value
        elif value not in (None, "", []):
            data[key] = value
    try:
        return JobRequirements.model_validate(data)
    except ValidationError:
        logger.warning("structured job data failed validation; using extracted requirements")
        return requirements


def stored_requirements(job: Job) -> JobRequirements:
    """Requirements as saved, or all-unknown if extraction never ran or the data is unreadable."""
    try:
        return JobRequirements.model_validate(job.requirements or {})
    except ValidationError:
        return JobRequirements()


def load_profile(session: Session) -> VerifiedProfile:
    skills = list(session.scalars(select(Skill)))
    experiences = list(session.scalars(select(Experience)))

    def as_dict(e: Experience) -> dict:
        return {"kind": e.kind, "title": e.title, "organization": e.organization,
                "start_date": e.start_date, "end_date": e.end_date, "is_current": e.is_current,
                "highlights": e.highlights}

    return VerifiedProfile(
        verified_skills=[s.name for s in skills if s.verified],
        verified_experiences=[as_dict(e) for e in experiences if e.verified],
        draft_skills=[s.name for s in skills if not s.verified],
        draft_experiences=[as_dict(e) for e in experiences if not e.verified],
    )


def match_for_job(job: Job, preferences: JobPreferences, profile: VerifiedProfile,
                  weights: dict[str, float]) -> MatchResult:
    return match_job(stored_requirements(job), job.description, preferences, profile, weights=weights)

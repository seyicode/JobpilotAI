import logging
import re
import uuid
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field, ValidationError, field_validator
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from jobpilot.api.routes.preferences import load_preferences
from jobpilot.core.config import Settings, get_settings
from jobpilot.db.models import Experience, Job, Skill
from jobpilot.db.session import get_session
from jobpilot.services.extraction import ExtractionOutcome, extract_requirements
from jobpilot.services.extraction.openai_extractor import OpenAIExtractor
from jobpilot.services.extraction.schema import JobRequirements
from jobpilot.services.job_ingestion import InvalidJobUrl, canonical_url, description_fingerprint
from jobpilot.services.matching import MatchResult, VerifiedProfile, match_job

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/jobs", tags=["jobs"])

SessionDep = Annotated[Session, Depends(get_session)]


def get_ai_extractor(settings: Annotated[Settings, Depends(get_settings)]) -> OpenAIExtractor | None:
    return OpenAIExtractor(settings) if settings.ai_configured else None


AIDep = Annotated[OpenAIExtractor | None, Depends(get_ai_extractor)]
OptionalName = Annotated[str | None, Field(default=None, max_length=200)]


class JobCreate(BaseModel):
    description: str = Field(min_length=50, max_length=50_000)
    source_url: Annotated[str | None, Field(default=None, max_length=2000)]
    title: OptionalName
    company: OptionalName

    @field_validator("title", "company", "source_url", mode="before")
    @classmethod
    def blank_to_none(cls, value: object) -> object:
        if isinstance(value, str):
            return re.sub(r"\s+", " ", value).strip() or None
        return value

    @field_validator("description", mode="before")
    @classmethod
    def strip_description(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value


class JobSummary(BaseModel):
    id: uuid.UUID
    title: str | None
    company: str | None
    source_url: str | None
    extraction_method: str | None
    created_at: datetime


class JobListItem(JobSummary):
    match_score: int | None
    match_coverage: int
    eligible: bool


class JobDetail(JobSummary):
    description: str
    requirements: dict | None
    extraction_note: str | None
    extracted_at: datetime | None


class JobCreateResult(BaseModel):
    job: JobDetail
    duplicate: bool


@router.post("", response_model=JobCreateResult, status_code=status.HTTP_201_CREATED)
def create_job(
    payload: JobCreate, session: SessionDep, ai: AIDep, response: Response
) -> JobCreateResult:
    """Store a pasted job. A duplicate returns the existing job with 200 and duplicate=true."""
    try:
        url = canonical_url(payload.source_url) if payload.source_url else None
    except InvalidJobUrl as error:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(error)) from None
    fingerprint = description_fingerprint(payload.description)

    existing = _find_duplicate(session, fingerprint, url)
    if existing is None:
        job = Job(
            title=payload.title, company=payload.company, source_url=payload.source_url,
            canonical_url=url, description=payload.description, description_hash=fingerprint,
        )
        _apply_extraction(job, _extract(session, job, ai))
        session.add(job)
        try:
            session.commit()
        except IntegrityError:  # Another request stored the same job first.
            session.rollback()
            existing = _find_duplicate(session, fingerprint, url)
            if existing is None:
                raise
        else:
            logger.info(
                "job created id=%s chars=%d has_url=%s extraction=%s",
                job.id, len(job.description), bool(url), job.extraction_method,
            )
            return JobCreateResult(job=JobDetail.model_validate(job, from_attributes=True), duplicate=False)

    response.status_code = status.HTTP_200_OK
    logger.info("job duplicate id=%s", existing.id)
    return JobCreateResult(job=JobDetail.model_validate(existing, from_attributes=True), duplicate=True)


@router.get("", response_model=list[JobListItem])
def list_jobs(session: SessionDep, settings: Annotated[Settings, Depends(get_settings)]) -> list[JobListItem]:
    """Newest first, each with its current match score (recomputed; nothing is cached)."""
    jobs = session.scalars(select(Job).order_by(Job.created_at.desc()))
    preferences, profile = load_preferences(session), load_profile(session)
    items = []
    for job in jobs:
        result = _match(job, preferences, profile, settings)
        items.append(JobListItem(
            **JobSummary.model_validate(job, from_attributes=True).model_dump(),
            match_score=result.score, match_coverage=result.coverage, eligible=result.eligible,
        ))
    return items


@router.get("/{job_id}", response_model=JobDetail)
def get_job(job_id: uuid.UUID, session: SessionDep) -> Job:
    return get_job_or_404(session, job_id)


@router.get("/{job_id}/match", response_model=MatchResult)
def get_match(
    job_id: uuid.UUID, session: SessionDep, settings: Annotated[Settings, Depends(get_settings)]
) -> MatchResult:
    """Deterministic match against your preferences and verified library, with reasons."""
    job = get_job_or_404(session, job_id)
    return _match(job, load_preferences(session), load_profile(session), settings)


@router.delete("/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_job(job_id: uuid.UUID, session: SessionDep) -> Response:
    session.delete(get_job_or_404(session, job_id))
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{job_id}/extract", response_model=JobDetail)
def reextract_job(job_id: uuid.UUID, session: SessionDep, ai: AIDep) -> Job:
    """Run extraction again, replacing any earlier or manually corrected requirements."""
    job = get_job_or_404(session, job_id)
    _apply_extraction(job, _extract(session, job, ai))
    session.commit()
    return job


@router.put("/{job_id}/requirements", response_model=JobDetail)
def correct_requirements(job_id: uuid.UUID, payload: JobRequirements, session: SessionDep) -> Job:
    """Save the user's corrections to the extracted requirements."""
    job = get_job_or_404(session, job_id)
    _apply_extraction(job, ExtractionOutcome(payload, "manual", "Corrected by you."))
    session.commit()
    return job


def get_job_or_404(session: Session, job_id: uuid.UUID) -> Job:
    job = session.get(Job, job_id)
    if job is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Job not found.")
    return job


def _find_duplicate(session: Session, fingerprint: str, url: str | None) -> Job | None:
    condition = Job.description_hash == fingerprint
    if url:
        condition = or_(condition, Job.canonical_url == url)
    return session.scalars(select(Job).where(condition).limit(1)).first()


def _extract(session: Session, job: Job, ai: OpenAIExtractor | None) -> ExtractionOutcome:
    library_skills = list(session.scalars(select(Skill.name)))
    return extract_requirements(
        session, job.description, title=job.title, company=job.company,
        extra_skills=library_skills, ai=ai,
    )


def _apply_extraction(job: Job, outcome: ExtractionOutcome) -> None:
    requirements = outcome.requirements
    job.requirements = requirements.model_dump()
    job.extraction_method = outcome.method
    job.extraction_note = outcome.note
    job.extracted_at = datetime.now(UTC)
    job.title = requirements.title or job.title
    job.company = requirements.company or job.company


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


def _match(job: Job, preferences, profile: VerifiedProfile, settings: Settings) -> MatchResult:
    return match_job(stored_requirements(job), job.description, preferences, profile,
                     weights=settings.match_weights)

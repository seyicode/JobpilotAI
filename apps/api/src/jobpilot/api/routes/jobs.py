import logging
import re
import uuid
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from jobpilot.api.routes.preferences import load_preferences
from jobpilot.core.config import Settings, get_settings
from jobpilot.db.models import Job, JobStatusEvent
from jobpilot.db.session import get_session
from jobpilot.services.applications import ApplicationStatus, set_status
from jobpilot.services.extraction import ExtractionOutcome
from jobpilot.services.extraction.openai_extractor import OpenAIExtractor
from jobpilot.services.extraction.schema import JobRequirements
from jobpilot.services.job_ingestion import InvalidJobUrl
from jobpilot.services.jobs import (
    NewJob,
    apply_extraction,
    extract_for_job,
    ingest_job,
    load_profile,
    match_for_job,
)
from jobpilot.services.matching import MatchResult

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/jobs", tags=["jobs"])

SessionDep = Annotated[Session, Depends(get_session)]
SettingsDep = Annotated[Settings, Depends(get_settings)]


def get_ai_extractor(settings: SettingsDep) -> OpenAIExtractor | None:
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
    application_status: ApplicationStatus
    status_changed_at: datetime | None
    seen_at: datetime | None
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
    notes: str | None


class JobCreateResult(BaseModel):
    job: JobDetail
    duplicate: bool


class ApplicationUpdate(BaseModel):
    """Manual application tracking. Omitted fields are unchanged."""

    status: ApplicationStatus | None = None
    notes: Annotated[str | None, Field(default=None, max_length=5000)]
    seen: bool | None = None
    status_note: Annotated[str | None, Field(default=None, max_length=500)]


class StatusEventOut(BaseModel):
    from_status: str | None
    to_status: str
    note: str | None
    created_at: datetime


@router.post("", response_model=JobCreateResult, status_code=status.HTTP_201_CREATED)
def create_job(payload: JobCreate, session: SessionDep, ai: AIDep, response: Response) -> JobCreateResult:
    """Store a pasted job. A duplicate returns the existing job with 200 and duplicate=true."""
    new = NewJob(description=payload.description, url=payload.source_url,
                 title=payload.title, company=payload.company)
    try:
        job, duplicate = ingest_job(session, new, ai)
    except InvalidJobUrl as error:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(error)) from None
    session.commit()
    if duplicate:
        response.status_code = status.HTTP_200_OK
        logger.info("job duplicate id=%s", job.id)
    return JobCreateResult(job=JobDetail.model_validate(job, from_attributes=True), duplicate=duplicate)


@router.get("", response_model=list[JobListItem])
def list_jobs(session: SessionDep, settings: SettingsDep) -> list[JobListItem]:
    """Newest first, each with its current match score (recomputed; nothing is cached)."""
    jobs = session.scalars(select(Job).order_by(Job.created_at.desc()))
    preferences, profile = load_preferences(session), load_profile(session)
    items = []
    for job in jobs:
        result = match_for_job(job, preferences, profile, settings.match_weights)
        items.append(JobListItem(
            **JobSummary.model_validate(job, from_attributes=True).model_dump(),
            match_score=result.score, match_coverage=result.coverage, eligible=result.eligible,
        ))
    return items


@router.get("/{job_id}", response_model=JobDetail)
def get_job(job_id: uuid.UUID, session: SessionDep) -> Job:
    return get_job_or_404(session, job_id)


@router.get("/{job_id}/match", response_model=MatchResult)
def get_match(job_id: uuid.UUID, session: SessionDep, settings: SettingsDep) -> MatchResult:
    """Deterministic match against your preferences and verified library, with reasons."""
    job = get_job_or_404(session, job_id)
    return match_for_job(job, load_preferences(session), load_profile(session), settings.match_weights)


@router.patch("/{job_id}/application", response_model=JobDetail)
def update_application(job_id: uuid.UUID, payload: ApplicationUpdate, session: SessionDep) -> Job:
    """Update status, private notes, or mark as seen. Status changes are recorded in the history."""
    job = get_job_or_404(session, job_id)
    changes = payload.model_dump(exclude_unset=True)
    if changes.get("status"):
        set_status(session, job, changes["status"], note=payload.status_note)
    if "notes" in changes:
        job.notes = (payload.notes or "").strip() or None
    if payload.seen is not None:
        job.seen_at = datetime.now(UTC) if payload.seen else None
    session.commit()
    logger.info("application updated job=%s status=%s", job.id, job.application_status)
    return job


@router.get("/{job_id}/application/history", response_model=list[StatusEventOut])
def application_history(job_id: uuid.UUID, session: SessionDep) -> list[JobStatusEvent]:
    get_job_or_404(session, job_id)
    return list(session.scalars(select(JobStatusEvent).where(JobStatusEvent.job_id == job_id)
                                .order_by(JobStatusEvent.created_at)))


@router.delete("/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_job(job_id: uuid.UUID, session: SessionDep) -> Response:
    session.delete(get_job_or_404(session, job_id))
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{job_id}/extract", response_model=JobDetail)
def reextract_job(job_id: uuid.UUID, session: SessionDep, ai: AIDep) -> Job:
    """Run extraction again, replacing any earlier or manually corrected requirements."""
    job = get_job_or_404(session, job_id)
    apply_extraction(job, extract_for_job(session, job, ai))
    session.commit()
    return job


@router.put("/{job_id}/requirements", response_model=JobDetail)
def correct_requirements(job_id: uuid.UUID, payload: JobRequirements, session: SessionDep) -> Job:
    """Save the user's corrections to the extracted requirements."""
    job = get_job_or_404(session, job_id)
    apply_extraction(job, ExtractionOutcome(payload, "manual", "Corrected by you."))
    session.commit()
    return job


def get_job_or_404(session: Session, job_id: uuid.UUID) -> Job:
    job = session.get(Job, job_id)
    if job is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Job not found.")
    return job

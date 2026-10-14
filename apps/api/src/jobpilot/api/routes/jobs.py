import logging
import re
import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from jobpilot.db.models import Job
from jobpilot.db.session import get_session
from jobpilot.services.job_ingestion import InvalidJobUrl, canonical_url, description_fingerprint

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/jobs", tags=["jobs"])

SessionDep = Annotated[Session, Depends(get_session)]
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


class JobDetail(JobSummary):
    description: str
    requirements: dict | None
    extraction_note: str | None
    extracted_at: datetime | None


class JobCreateResult(BaseModel):
    job: JobDetail
    duplicate: bool


@router.post("", response_model=JobCreateResult, status_code=status.HTTP_201_CREATED)
def create_job(payload: JobCreate, session: SessionDep, response: Response) -> JobCreateResult:
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
        session.add(job)
        try:
            session.commit()
        except IntegrityError:  # Another request stored the same job first.
            session.rollback()
            existing = _find_duplicate(session, fingerprint, url)
            if existing is None:
                raise
        else:
            logger.info("job created id=%s chars=%d has_url=%s", job.id, len(job.description), bool(url))
            return JobCreateResult(job=JobDetail.model_validate(job, from_attributes=True), duplicate=False)

    response.status_code = status.HTTP_200_OK
    logger.info("job duplicate id=%s", existing.id)
    return JobCreateResult(job=JobDetail.model_validate(existing, from_attributes=True), duplicate=True)


@router.get("", response_model=list[JobSummary])
def list_jobs(session: SessionDep) -> list[Job]:
    return list(session.scalars(select(Job).order_by(Job.created_at.desc())))


@router.get("/{job_id}", response_model=JobDetail)
def get_job(job_id: uuid.UUID, session: SessionDep) -> Job:
    return get_job_or_404(session, job_id)


@router.delete("/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_job(job_id: uuid.UUID, session: SessionDep) -> Response:
    session.delete(get_job_or_404(session, job_id))
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


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

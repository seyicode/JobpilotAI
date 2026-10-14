"""Tailored resume versions per job: generate, edit, approve, copy, delete.

Resume text is never logged; logs carry ids, versions, methods, and counts only.
"""

import logging
import uuid
from datetime import UTC, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from jobpilot.api.routes.jobs import (
    get_job_or_404,
    load_profile,
    match_for_job,
    stored_requirements,
)
from jobpilot.api.routes.preferences import load_preferences
from jobpilot.api.routes.profile import load_profile_details
from jobpilot.core.config import Settings, get_settings
from jobpilot.db.models import Experience, Job, Skill, TailoredResume
from jobpilot.db.session import get_session
from jobpilot.services.resumes.assembly import assemble_resume
from jobpilot.services.resumes.review import EditRejected, apply_edit, library_conflicts
from jobpilot.services.resumes.schema import ResumeContent

logger = logging.getLogger(__name__)
router = APIRouter(tags=["tailored resumes"])

SessionDep = Annotated[Session, Depends(get_session)]
SettingsDep = Annotated[Settings, Depends(get_settings)]


class ResumeWarning(BaseModel):
    location: str
    message: str


class VersionSummary(BaseModel):
    id: uuid.UUID
    job_id: uuid.UUID
    version: int
    status: Literal["draft", "approved"]
    generation_method: str
    edited: bool
    based_on_version: int | None
    warning_count: int
    note: str | None
    created_at: datetime
    updated_at: datetime
    approved_at: datetime | None


class VersionDetail(VersionSummary):
    content: ResumeContent
    warnings: list[ResumeWarning]


class GenerateRequest(BaseModel):
    method: Literal["deterministic"] = "deterministic"


class ApproveRequest(BaseModel):
    acknowledge_warnings: bool = False


@router.post("/jobs/{job_id}/resumes", response_model=VersionDetail, status_code=status.HTTP_201_CREATED)
def generate(job_id: uuid.UUID, session: SessionDep, settings: SettingsDep,
             payload: GenerateRequest | None = None) -> VersionDetail:
    """Create a new draft version tailored to the job from your verified library."""
    job = get_job_or_404(session, job_id)
    content = _assemble(session, job, settings)
    record = _new_version(session, job.id, content, method="deterministic", based_on=None,
                          note="Selected and ordered from your verified library. No text was rewritten.")
    logger.info(
        "tailored resume generated job=%s version=%d method=deterministic entries=%d bullets=%d",
        job.id, record.version, sum(len(s.entries) for s in content.sections),
        sum(1 for _ in content.bullets()),
    )
    return _detail(record)


@router.get("/jobs/{job_id}/resumes", response_model=list[VersionSummary])
def list_versions(job_id: uuid.UUID, session: SessionDep) -> list[VersionSummary]:
    get_job_or_404(session, job_id)
    records = session.scalars(select(TailoredResume).where(TailoredResume.job_id == job_id)
                              .order_by(TailoredResume.version.desc()))
    return [_summary(r) for r in records]


@router.get("/tailored-resumes/{resume_id}", response_model=VersionDetail)
def get_version(resume_id: uuid.UUID, session: SessionDep) -> VersionDetail:
    return _detail(_get_or_404(session, resume_id))


@router.put("/tailored-resumes/{resume_id}", response_model=VersionDetail)
def edit_version(resume_id: uuid.UUID, payload: ResumeContent, session: SessionDep) -> VersionDetail:
    """Save edits to a draft. Titles, organisations, and dates always come from the library."""
    record = _get_or_404(session, resume_id)
    _require_draft(record)
    library, skills = _verified_library(session)
    try:
        content, issues = apply_edit(payload, ResumeContent.model_validate(record.content), library,
                                     skills, load_profile_details(session).summary)
    except EditRejected as error:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(error)) from None
    record.content = content.model_dump(mode="json")
    record.warnings = [{"location": i.location, "message": i.message} for i in issues]
    record.edited = True
    session.commit()
    logger.info("tailored resume edited id=%s version=%d warnings=%d", record.id, record.version, len(issues))
    return _detail(record)


@router.post("/tailored-resumes/{resume_id}/approve", response_model=VersionDetail)
def approve_version(resume_id: uuid.UUID, session: SessionDep,
                    payload: ApproveRequest | None = None) -> VersionDetail:
    """Lock a draft after review. Warnings must be acknowledged; library changes block approval."""
    record = _get_or_404(session, resume_id)
    _require_draft(record)
    acknowledged = payload.acknowledge_warnings if payload else False
    if record.warnings and not acknowledged:
        raise HTTPException(status.HTTP_409_CONFLICT,
                            "This version has warnings. Review them, then confirm to approve.")
    library, skills = _verified_library(session)
    conflicts = library_conflicts(ResumeContent.model_validate(record.content), library, skills)
    if conflicts:
        raise HTTPException(status.HTTP_409_CONFLICT,
                            " ".join(conflicts) + " Edit this version or generate a new one.")
    record.status = "approved"
    record.approved_at = datetime.now(UTC)
    session.commit()
    logger.info("tailored resume approved id=%s version=%d", record.id, record.version)
    return _detail(record)


@router.post("/tailored-resumes/{resume_id}/copy", response_model=VersionDetail,
             status_code=status.HTTP_201_CREATED)
def copy_version(resume_id: uuid.UUID, session: SessionDep) -> VersionDetail:
    """Start a new draft from any version (approved versions cannot be edited)."""
    source = _get_or_404(session, resume_id)
    record = _new_version(session, source.job_id, ResumeContent.model_validate(source.content),
                          method=source.generation_method, based_on=source.version,
                          note=f"Copied from version {source.version}.", edited=source.edited,
                          warnings=source.warnings)
    return _detail(record)


@router.delete("/tailored-resumes/{resume_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_version(resume_id: uuid.UUID, session: SessionDep) -> Response:
    """Delete a draft. Approved versions are kept as history."""
    record = _get_or_404(session, resume_id)
    _require_draft(record)
    session.delete(record)
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# Helpers


def verified_experiences(session: Session) -> list[dict]:
    rows = session.scalars(select(Experience).where(Experience.verified.is_(True)))
    return [{"id": e.id, "kind": e.kind, "title": e.title, "organization": e.organization,
             "location": e.location, "start_date": e.start_date, "end_date": e.end_date,
             "is_current": e.is_current, "highlights": list(e.highlights or [])} for e in rows]


def verified_skill_names(session: Session) -> list[str]:
    return list(session.scalars(select(Skill.name).where(Skill.verified.is_(True))))


def _verified_library(session: Session) -> tuple[dict[uuid.UUID, dict], list[str]]:
    return {e["id"]: e for e in verified_experiences(session)}, verified_skill_names(session)


def _assemble(session: Session, job: Job, settings: Settings) -> ResumeContent:
    match = match_for_job(job, load_preferences(session), load_profile(session), settings)
    return assemble_resume(stored_requirements(job), match, load_profile_details(session),
                           verified_experiences(session), verified_skill_names(session))


def _new_version(session: Session, job_id: uuid.UUID, content: ResumeContent, *, method: str,
                 based_on: int | None, note: str, edited: bool = False,
                 warnings: list[dict] | None = None) -> TailoredResume:
    latest = session.scalar(select(func.max(TailoredResume.version)).where(TailoredResume.job_id == job_id))
    record = TailoredResume(
        job_id=job_id, version=(latest or 0) + 1, status="draft", generation_method=method,
        edited=edited, based_on_version=based_on, content=content.model_dump(mode="json"),
        warnings=list(warnings or []), note=note,
    )
    session.add(record)
    session.commit()
    return record


def _get_or_404(session: Session, resume_id: uuid.UUID) -> TailoredResume:
    record = session.get(TailoredResume, resume_id)
    if record is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Resume version not found.")
    return record


def _require_draft(record: TailoredResume) -> None:
    if record.status != "draft":
        raise HTTPException(status.HTTP_409_CONFLICT,
                            "Approved versions cannot be changed. Make a copy to edit.")


def _summary(record: TailoredResume) -> VersionSummary:
    return VersionSummary(
        id=record.id, job_id=record.job_id, version=record.version, status=record.status,
        generation_method=record.generation_method, edited=record.edited,
        based_on_version=record.based_on_version, warning_count=len(record.warnings or []),
        note=record.note, created_at=record.created_at, updated_at=record.updated_at,
        approved_at=record.approved_at,
    )


def _detail(record: TailoredResume) -> VersionDetail:
    return VersionDetail(**_summary(record).model_dump(),
                         content=ResumeContent.model_validate(record.content),
                         warnings=[ResumeWarning(**w) for w in record.warnings or []])

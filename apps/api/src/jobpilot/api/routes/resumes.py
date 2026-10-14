import logging
import re
import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, UploadFile, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from jobpilot.core.config import Settings, get_settings
from jobpilot.db.models import Resume
from jobpilot.db.session import get_session
from jobpilot.services.resume_parser import ResumeParseError, parse_resume

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/resumes", tags=["resumes"])

SessionDep = Annotated[Session, Depends(get_session)]


class SectionOut(BaseModel):
    key: str
    heading: str
    content: str


class ResumeSummary(BaseModel):
    id: uuid.UUID
    filename: str
    file_type: str
    size_bytes: int
    created_at: datetime


class ResumeDetail(ResumeSummary):
    text: str
    sections: list[SectionOut]


@router.post("", response_model=ResumeDetail, status_code=status.HTTP_201_CREATED)
async def upload_resume(
    file: UploadFile,
    session: SessionDep,
    settings: Annotated[Settings, Depends(get_settings)],
) -> Resume:
    data = await file.read(settings.max_resume_bytes + 1)
    if not data:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "The uploaded file is empty.")
    if len(data) > settings.max_resume_bytes:
        limit_mb = settings.max_resume_bytes // (1024 * 1024)
        raise HTTPException(
            status.HTTP_413_CONTENT_TOO_LARGE, f"Resumes must be {limit_mb} MB or smaller."
        )
    filename = _clean_filename(file.filename)
    try:
        file_type, text, sections = parse_resume(filename, data)
    except ResumeParseError as error:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(error)) from None
    resume = Resume(
        filename=filename, file_type=file_type, size_bytes=len(data), text=text, sections=sections
    )
    session.add(resume)
    session.commit()
    # Log metadata only; never resume contents or filenames, which can contain names.
    logger.info(
        "resume uploaded id=%s type=%s bytes=%d sections=%d",
        resume.id, file_type, len(data), len(sections),
    )
    return resume


@router.get("", response_model=list[ResumeSummary])
def list_resumes(session: SessionDep) -> list[Resume]:
    return list(session.scalars(select(Resume).order_by(Resume.created_at.desc())))


@router.get("/{resume_id}", response_model=ResumeDetail)
def get_resume(resume_id: uuid.UUID, session: SessionDep) -> Resume:
    return _get_or_404(session, resume_id)


@router.delete("/{resume_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_resume(resume_id: uuid.UUID, session: SessionDep) -> Response:
    session.delete(_get_or_404(session, resume_id))
    session.commit()
    logger.info("resume deleted id=%s", resume_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _get_or_404(session: Session, resume_id: uuid.UUID) -> Resume:
    resume = session.get(Resume, resume_id)
    if resume is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Resume not found.")
    return resume


def _clean_filename(filename: str | None) -> str:
    name = re.split(r"[\\/]", filename or "")[-1]
    name = re.sub(r"[\x00-\x1f\x7f]", "", name).strip()
    return name[:255] or "resume"

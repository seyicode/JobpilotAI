"""Verified experience and skills library.

Imported and edited entries are unverified until the user confirms them. Editing the content
of a verified entry makes it unverified again unless the same request re-verifies it.
"""

import logging
import re
import uuid
from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field, ValidationError, field_validator, model_validator
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from jobpilot.db.models import Experience, Resume, Skill
from jobpilot.db.session import get_session
from jobpilot.services.library_import import drafts_from_sections

logger = logging.getLogger(__name__)
router = APIRouter(tags=["library"])

SessionDep = Annotated[Session, Depends(get_session)]
Kind = Literal["job", "education", "project", "certification", "volunteering", "other"]
DATE_PATTERN = r"^\d{4}(-(0[1-9]|1[0-2]))?$"
OptionalText = Annotated[str | None, Field(default=None, max_length=200)]


class ExperienceFields(BaseModel):
    kind: Kind
    title: str = Field(min_length=1, max_length=200)
    organization: OptionalText
    location: OptionalText
    start_date: Annotated[str | None, Field(default=None, pattern=DATE_PATTERN)]
    end_date: Annotated[str | None, Field(default=None, pattern=DATE_PATTERN)]
    is_current: bool = False
    highlights: list[Annotated[str, Field(min_length=1, max_length=500)]] = Field(
        default_factory=list, max_length=30
    )

    @field_validator("title", "organization", "location", mode="before")
    @classmethod
    def strip_text(cls, value: str | None) -> str | None:
        if isinstance(value, str):
            return re.sub(r"\s+", " ", value).strip() or None
        return value

    @field_validator("highlights", mode="before")
    @classmethod
    def strip_highlights(cls, value: list) -> list:
        if not isinstance(value, list):
            return value
        return [h.strip() for h in value if not isinstance(h, str) or h.strip()]

    @model_validator(mode="after")
    def check_dates(self) -> "ExperienceFields":
        if self.is_current and self.end_date:
            raise ValueError("A current entry cannot have an end date.")
        if self.start_date and self.end_date:
            start = self.start_date if len(self.start_date) == 7 else self.start_date + "-01"
            end = self.end_date if len(self.end_date) == 7 else self.end_date + "-12"
            if end < start:
                raise ValueError("The end date must not be before the start date.")
        return self


class ExperienceCreate(ExperienceFields):
    verified: bool = False


class ExperienceUpdate(BaseModel):
    """Partial update; omitted fields are unchanged."""

    kind: Kind | None = None
    title: str | None = None
    organization: str | None = None
    location: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    is_current: bool | None = None
    highlights: list[str] | None = None
    verified: bool | None = None


class ExperienceOut(ExperienceFields):
    id: uuid.UUID
    verified: bool
    source_resume_id: uuid.UUID | None
    created_at: datetime
    updated_at: datetime


class SkillCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    verified: bool = False

    @field_validator("name", mode="before")
    @classmethod
    def strip_name(cls, value: str) -> str:
        return re.sub(r"\s+", " ", value).strip() if isinstance(value, str) else value


class SkillUpdate(BaseModel):
    name: str | None = None
    verified: bool | None = None


class SkillOut(BaseModel):
    id: uuid.UUID
    name: str
    verified: bool
    source_resume_id: uuid.UUID | None
    created_at: datetime


class ImportResult(BaseModel):
    experiences_created: int
    skills_created: int
    skipped: int


# Experiences


@router.get("/experiences", response_model=list[ExperienceOut])
def list_experiences(session: SessionDep, verified: bool | None = None) -> list[Experience]:
    query = select(Experience).order_by(
        Experience.is_current.desc(),
        Experience.start_date.desc().nulls_last(),
        Experience.created_at,
    )
    if verified is not None:
        query = query.where(Experience.verified == verified)
    return list(session.scalars(query))


@router.post("/experiences", response_model=ExperienceOut, status_code=status.HTTP_201_CREATED)
def create_experience(payload: ExperienceCreate, session: SessionDep) -> Experience:
    experience = Experience(**payload.model_dump())
    session.add(experience)
    session.commit()
    return experience


@router.patch("/experiences/{experience_id}", response_model=ExperienceOut)
def update_experience(
    experience_id: uuid.UUID, payload: ExperienceUpdate, session: SessionDep
) -> Experience:
    experience = _get_or_404(session, Experience, experience_id, "Experience")
    changes = payload.model_dump(exclude_unset=True)
    verified = changes.pop("verified", None)
    if any(changes.get(name, ...) is None for name in ("kind", "title", "is_current", "highlights")):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Required fields cannot be empty.")
    current = ExperienceFields.model_validate(experience, from_attributes=True).model_dump()
    try:
        merged = ExperienceFields.model_validate(current | changes).model_dump()
    except ValidationError as error:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, _first_error(error)) from None
    content_changed = merged != current
    for name, value in merged.items():
        setattr(experience, name, value)
    if verified is not None:
        experience.verified = verified
    elif content_changed:
        experience.verified = False
    session.commit()
    return experience


@router.delete("/experiences/{experience_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_experience(experience_id: uuid.UUID, session: SessionDep) -> Response:
    session.delete(_get_or_404(session, Experience, experience_id, "Experience"))
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# Skills


@router.get("/skills", response_model=list[SkillOut])
def list_skills(session: SessionDep, verified: bool | None = None) -> list[Skill]:
    query = select(Skill).order_by(func.lower(Skill.name))
    if verified is not None:
        query = query.where(Skill.verified == verified)
    return list(session.scalars(query))


@router.post("/skills", response_model=SkillOut, status_code=status.HTTP_201_CREATED)
def create_skill(payload: SkillCreate, session: SessionDep) -> Skill:
    _ensure_unique_skill(session, payload.name)
    skill = Skill(**payload.model_dump())
    session.add(skill)
    session.commit()
    return skill


@router.patch("/skills/{skill_id}", response_model=SkillOut)
def update_skill(skill_id: uuid.UUID, payload: SkillUpdate, session: SessionDep) -> Skill:
    skill = _get_or_404(session, Skill, skill_id, "Skill")
    changes = payload.model_dump(exclude_unset=True)
    verified = changes.pop("verified", None)
    if "name" in changes:
        try:
            name = SkillCreate(name=changes["name"]).name
        except ValidationError as error:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, _first_error(error)) from None
        if name != skill.name:
            if name.lower() != skill.name.lower():
                _ensure_unique_skill(session, name)
            skill.name = name
            skill.verified = False
    if verified is not None:
        skill.verified = verified
    session.commit()
    return skill


@router.delete("/skills/{skill_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_skill(skill_id: uuid.UUID, session: SessionDep) -> Response:
    session.delete(_get_or_404(session, Skill, skill_id, "Skill"))
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# Import


@router.post("/resumes/{resume_id}/import", response_model=ImportResult)
def import_resume(resume_id: uuid.UUID, session: SessionDep) -> ImportResult:
    """Create unverified drafts from a parsed resume, skipping entries already in the library."""
    resume = _get_or_404(session, Resume, resume_id, "Resume")
    drafts, skill_names = drafts_from_sections(resume.sections)

    existing_experiences = {
        (e.kind, e.title.lower(), (e.organization or "").lower())
        for e in session.scalars(select(Experience))
    }
    existing_skills = {name.lower() for name in session.scalars(select(Skill.name))}
    created_experiences = created_skills = skipped = 0
    for draft in drafts:
        key = (draft.kind, draft.title.lower(), (draft.organization or "").lower())
        if key in existing_experiences:
            skipped += 1
            continue
        try:
            fields = ExperienceFields.model_validate(vars(draft)).model_dump()
        except ValidationError:
            # Keep the text but drop dates the heuristics got wrong.
            fields = ExperienceFields.model_validate(
                vars(draft) | {"start_date": None, "end_date": None, "is_current": False}
            ).model_dump()
        session.add(Experience(**fields, source_resume_id=resume.id))
        existing_experiences.add(key)
        created_experiences += 1
    for name in skill_names:
        if name.lower() in existing_skills:
            skipped += 1
            continue
        session.add(Skill(name=name, source_resume_id=resume.id))
        existing_skills.add(name.lower())
        created_skills += 1
    session.commit()
    logger.info(
        "resume imported id=%s experiences=%d skills=%d skipped=%d",
        resume.id, created_experiences, created_skills, skipped,
    )
    return ImportResult(
        experiences_created=created_experiences, skills_created=created_skills, skipped=skipped
    )


def _get_or_404(session: Session, model: type, item_id: uuid.UUID, label: str):
    item = session.get(model, item_id)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"{label} not found.")
    return item


def _ensure_unique_skill(session: Session, name: str) -> None:
    if session.scalar(select(Skill.id).where(func.lower(Skill.name) == name.lower())):
        raise HTTPException(status.HTTP_409_CONFLICT, f"“{name}” is already in your skills.")


def _first_error(error: ValidationError) -> str:
    message = error.errors()[0]["msg"]
    return message.removeprefix("Value error, ")

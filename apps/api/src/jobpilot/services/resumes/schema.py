"""The user's profile (contact details and summary) and the structure of a tailored resume.

A tailored resume is stored as data, never as a file. Every entry points at the library entry
it came from, and every bullet keeps the original wording it was derived from, so a reviewer can
always compare the two. Titles, organisations, and dates are copied from the library.
"""

import re
import uuid
from typing import Annotated, Literal

from pydantic import BaseModel, Field, field_validator

Kind = Literal["job", "education", "project", "certification", "volunteering", "other"]
OptionalText = Annotated[str | None, Field(default=None, max_length=200)]

SECTION_ORDER: list[tuple[Kind, str]] = [
    ("job", "Experience"),
    ("project", "Projects"),
    ("education", "Education"),
    ("certification", "Certifications"),
    ("volunteering", "Volunteering"),
    ("other", "Other"),
]


def _clean(value: object) -> object:
    if isinstance(value, str):
        return re.sub(r"\s+", " ", value).strip() or None
    return value


class UserProfile(BaseModel):
    """Contact details and a summary, written by the user. Used for resume headers."""

    full_name: Annotated[str | None, Field(default=None, max_length=100)]
    headline: Annotated[str | None, Field(default=None, max_length=150)]
    email: Annotated[str | None, Field(default=None, max_length=254, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")]
    phone: Annotated[str | None, Field(default=None, max_length=40, pattern=r"^[\d+() .\-]{5,40}$")]
    location: Annotated[str | None, Field(default=None, max_length=100)]
    links: list[Annotated[str, Field(max_length=300, pattern=r"^https?://\S+$")]] = Field(
        default_factory=list, max_length=5
    )
    summary: Annotated[str | None, Field(default=None, max_length=1200)]

    @field_validator("full_name", "headline", "email", "phone", "location", mode="before")
    @classmethod
    def clean_text(cls, value: object) -> object:
        return _clean(value)

    @field_validator("summary", mode="before")
    @classmethod
    def clean_summary(cls, value: object) -> object:
        if isinstance(value, str):
            return re.sub(r"[ \t]+", " ", value).strip() or None
        return value

    @field_validator("links", mode="before")
    @classmethod
    def clean_links(cls, value: object) -> object:
        if isinstance(value, list):
            return list(dict.fromkeys(v.strip() for v in value if isinstance(v, str) and v.strip()))
        return value


class ResumeHeader(BaseModel):
    name: str | None = None
    headline: str | None = None
    email: str | None = None
    phone: str | None = None
    location: str | None = None
    links: list[str] = Field(default_factory=list)


class ResumeBullet(BaseModel):
    text: Annotated[str, Field(min_length=1, max_length=500)]
    source_text: str  # The verified highlight this bullet came from
    changed_by: Literal["none", "ai", "user"] = "none"
    reason: str | None = None  # Why it was selected, or why an AI rewrite was rejected

    @field_validator("text", mode="before")
    @classmethod
    def clean(cls, value: object) -> object:
        if isinstance(value, str):
            return _clean(value) or ""  # Blank fails min_length with a clear error
        return value


class ResumeEntry(BaseModel):
    source_id: uuid.UUID  # Library experience id
    kind: Kind
    title: str
    organization: str | None = None
    location: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    is_current: bool = False
    bullets: list[ResumeBullet] = Field(default_factory=list, max_length=30)
    reason: str | None = None


class ResumeSection(BaseModel):
    kind: Kind
    heading: str
    entries: list[ResumeEntry] = Field(default_factory=list)


class ResumeContent(BaseModel):
    header: ResumeHeader = Field(default_factory=ResumeHeader)
    summary: Annotated[str | None, Field(default=None, max_length=1200)]
    skills: list[Annotated[str, Field(min_length=1, max_length=100)]] = Field(
        default_factory=list, max_length=60
    )
    sections: list[ResumeSection] = Field(default_factory=list)

    def bullets(self):
        """Every (entry, bullet) pair in reading order."""
        for section in self.sections:
            for entry in section.entries:
                for bullet in entry.bullets:
                    yield entry, bullet

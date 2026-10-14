import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Resume(Base):
    """Text extracted from an uploaded resume. The original file is not stored."""

    __tablename__ = "resumes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    filename: Mapped[str] = mapped_column(String(255))
    file_type: Mapped[str] = mapped_column(String(10))
    size_bytes: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text)
    sections: Mapped[list[dict]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )


class Experience(Base):
    """A job, education, project, or similar entry the user can verify.

    Only verified entries may be used for resume tailoring.
    """

    __tablename__ = "experiences"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    kind: Mapped[str] = mapped_column(String(20))
    title: Mapped[str] = mapped_column(String(200))
    organization: Mapped[str | None] = mapped_column(String(200))
    location: Mapped[str | None] = mapped_column(String(200))
    start_date: Mapped[str | None] = mapped_column(String(7))
    end_date: Mapped[str | None] = mapped_column(String(7))
    is_current: Mapped[bool] = mapped_column(Boolean, default=False)
    highlights: Mapped[list[str]] = mapped_column(JSONB, default=list)
    verified: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    source_resume_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("resumes.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Skill(Base):
    """A skill name, unique case-insensitively. Only verified skills may be used for tailoring."""

    __tablename__ = "skills"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(100))
    verified: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    source_resume_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("resumes.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


Index("uq_skills_name_lower", func.lower(Skill.name), unique=True)


class PreferencesRecord(Base):
    """The user's job preferences, validated by services.preferences.JobPreferences.

    Single-user for now: one row with id 1.
    """

    __tablename__ = "job_preferences"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    data: Mapped[dict] = mapped_column(JSONB)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class JobSource(Base):
    """A company job board the user follows (one provider + board name)."""

    __tablename__ = "job_sources"
    __table_args__ = (UniqueConstraint("provider", "board", name="uq_job_sources_provider_board"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    provider: Mapped[str] = mapped_column(String(20))
    board: Mapped[str] = mapped_column(String(100))
    company_name: Mapped[str] = mapped_column(String(200))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    interval_minutes: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), default="new")  # new|healthy|degraded|failing
    consecutive_failures: Mapped[int] = mapped_column(Integer, default=0)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    next_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    last_error_code: Mapped[str | None] = mapped_column(String(40))
    last_error_message: Mapped[str | None] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SourceRun(Base):
    """One fetch of a source's feed. Counts only; no job content."""

    __tablename__ = "source_runs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("job_sources.id", ondelete="CASCADE"), index=True)
    trigger: Mapped[str] = mapped_column(String(20))  # manual | scheduled
    status: Mapped[str] = mapped_column(String(20))  # running | success | failed | skipped
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.clock_timestamp(), index=True
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    http_status: Mapped[int | None] = mapped_column(Integer)
    fetched: Mapped[int] = mapped_column(Integer, default=0)
    new_jobs: Mapped[int] = mapped_column(Integer, default=0)
    seen_again: Mapped[int] = mapped_column(Integer, default=0)
    filtered_out: Mapped[int] = mapped_column(Integer, default=0)
    archived: Mapped[int] = mapped_column(Integer, default=0)
    closed: Mapped[int] = mapped_column(Integer, default=0)
    error_code: Mapped[str | None] = mapped_column(String(40))
    error_message: Mapped[str | None] = mapped_column(String(200))


class Job(Base):
    """A job posting the user pasted in. The original description is stored unchanged."""

    __tablename__ = "jobs"
    __table_args__ = (
        Index("uq_jobs_source_posting", "source_id", "source_external_id", unique=True,
              postgresql_where=text("source_external_id IS NOT NULL")),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title: Mapped[str | None] = mapped_column(String(200))
    company: Mapped[str | None] = mapped_column(String(200))
    source_url: Mapped[str | None] = mapped_column(String(2000))
    canonical_url: Mapped[str | None] = mapped_column(String(2000), unique=True)
    description: Mapped[str] = mapped_column(Text)
    description_hash: Mapped[str] = mapped_column(String(64), unique=True)
    requirements: Mapped[dict | None] = mapped_column(JSONB)
    extraction_method: Mapped[str | None] = mapped_column(String(20))
    extraction_note: Mapped[str | None] = mapped_column(String(200))
    extracted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Application tracking, updated by the user (see services.applications).
    application_status: Mapped[str] = mapped_column(String(20), default="shortlisted", index=True)
    status_changed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    notes: Mapped[str | None] = mapped_column(Text)
    seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Discovery: where the posting came from and when it was observed in its feed.
    source_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("job_sources.id", ondelete="SET NULL"), index=True
    )
    source_external_id: Mapped[str | None] = mapped_column(String(200))
    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    first_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )


class AIUsage(Base):
    """One request to an AI provider, for spending limits. Never stores prompt or output text."""

    __tablename__ = "ai_usage"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    purpose: Mapped[str] = mapped_column(String(50))
    model: Mapped[str] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(30))
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cost_usd: Mapped[Decimal | None] = mapped_column(Numeric(12, 6))
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    # clock_timestamp(), not now(): retries in one transaction get distinct, ordered times.
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.clock_timestamp(), index=True
    )


class AICacheEntry(Base):
    """A validated AI result keyed by a hash of the prompt version, model, and input."""

    __tablename__ = "ai_cache"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    purpose: Mapped[str] = mapped_column(String(50))
    model: Mapped[str] = mapped_column(String(100))
    result: Mapped[dict] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ProfileRecord(Base):
    """The user's contact details and summary, validated by services.resumes.schema.UserProfile.

    Single-user for now: one row with id 1.
    """

    __tablename__ = "profile"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    data: Mapped[dict] = mapped_column(JSONB)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class TailoredResume(Base):
    """One version of a resume tailored to a job. Approved versions are read-only."""

    __tablename__ = "tailored_resumes"
    __table_args__ = (UniqueConstraint("job_id", "version", name="uq_tailored_resumes_job_version"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"), index=True)
    version: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), default="draft")  # draft | approved
    generation_method: Mapped[str] = mapped_column(String(20))  # deterministic | ai
    edited: Mapped[bool] = mapped_column(Boolean, default=False)
    based_on_version: Mapped[int | None] = mapped_column(Integer)
    content: Mapped[dict] = mapped_column(JSONB)
    warnings: Mapped[list[dict]] = mapped_column(JSONB, default=list)
    note: Mapped[str | None] = mapped_column(String(300))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class JobStatusEvent(Base):
    """One application status change, for the job's history."""

    __tablename__ = "job_status_events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"), index=True)
    from_status: Mapped[str | None] = mapped_column(String(20))
    to_status: Mapped[str] = mapped_column(String(20))
    note: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.clock_timestamp()
    )

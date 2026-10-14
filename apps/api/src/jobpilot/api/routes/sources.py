"""Followed company job boards: add, configure, run, and inspect health and run history."""

import logging
import re
import uuid
from datetime import UTC, datetime, timedelta
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from jobpilot.api.routes.jobs import AIDep
from jobpilot.api.routes.preferences import load_preferences
from jobpilot.core.config import Settings, get_settings
from jobpilot.db.models import JobSource, SourceRun
from jobpilot.db.session import get_session
from jobpilot.services.discovery import run_source
from jobpilot.services.sources.base import InvalidBoard, validate_board
from jobpilot.services.sources.fetcher import FeedFetcher
from jobpilot.services.sources.providers import ADAPTERS

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/sources", tags=["sources"])

SessionDep = Annotated[Session, Depends(get_session)]
SettingsDep = Annotated[Settings, Depends(get_settings)]
Provider = Literal["greenhouse", "lever", "ashby"]


def get_feed_fetcher(settings: SettingsDep) -> FeedFetcher:
    return FeedFetcher(settings)


FetcherDep = Annotated[FeedFetcher, Depends(get_feed_fetcher)]


class ProviderOut(BaseModel):
    provider: str
    label: str
    docs_url: str
    board_hint: str


class SourceCreate(BaseModel):
    provider: Provider
    board: Annotated[str, Field(min_length=1, max_length=100)]
    company_name: Annotated[str, Field(min_length=1, max_length=200)]
    interval_minutes: int | None = None
    enabled: bool = True

    @field_validator("company_name", mode="before")
    @classmethod
    def clean(cls, value: object) -> object:
        return re.sub(r"\s+", " ", value).strip() if isinstance(value, str) else value


class SourceUpdate(BaseModel):
    company_name: Annotated[str | None, Field(default=None, min_length=1, max_length=200)]
    interval_minutes: int | None = None
    enabled: bool | None = None


class SourceOut(BaseModel):
    id: uuid.UUID
    provider: Provider
    board: str
    company_name: str
    enabled: bool
    interval_minutes: int
    status: Literal["new", "healthy", "degraded", "failing"]
    consecutive_failures: int
    last_run_at: datetime | None
    last_success_at: datetime | None
    next_run_at: datetime | None
    last_error_code: str | None
    last_error_message: str | None
    created_at: datetime


class RunOut(BaseModel):
    id: uuid.UUID
    trigger: str
    status: str
    started_at: datetime
    finished_at: datetime | None
    attempts: int
    http_status: int | None
    fetched: int
    new_jobs: int
    seen_again: int
    filtered_out: int
    archived: int
    closed: int
    error_code: str | None
    error_message: str | None


BOARD_HINTS = {
    "greenhouse": "The name in boards.greenhouse.io/<board>",
    "lever": "The name in jobs.lever.co/<board>",
    "ashby": "The name in jobs.ashbyhq.com/<board>",
}


@router.get("/providers", response_model=list[ProviderOut])
def list_providers() -> list[ProviderOut]:
    return [ProviderOut(provider=a.provider, label=a.label, docs_url=a.docs_url, board_hint=BOARD_HINTS[a.provider])
            for a in ADAPTERS.values()]


@router.get("", response_model=list[SourceOut])
def list_sources(session: SessionDep) -> list[JobSource]:
    return list(session.scalars(select(JobSource).order_by(JobSource.company_name)))


@router.post("", response_model=SourceOut, status_code=status.HTTP_201_CREATED)
def create_source(payload: SourceCreate, session: SessionDep, settings: SettingsDep) -> JobSource:
    try:
        board = validate_board(payload.board)
    except InvalidBoard as error:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(error)) from None
    interval = _interval(payload.interval_minutes or settings.discovery_default_interval_minutes, settings)
    source = JobSource(provider=payload.provider, board=board, company_name=payload.company_name,
                       enabled=payload.enabled, interval_minutes=interval, status="new",
                       consecutive_failures=0, next_run_at=datetime.now(UTC))
    session.add(source)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "You already follow that job board.") from None
    logger.info("source created id=%s provider=%s", source.id, source.provider)
    return source


@router.patch("/{source_id}", response_model=SourceOut)
def update_source(source_id: uuid.UUID, payload: SourceUpdate, session: SessionDep,
                  settings: SettingsDep) -> JobSource:
    source = _get_or_404(session, source_id)
    changes = payload.model_dump(exclude_unset=True)
    if changes.get("company_name"):
        source.company_name = re.sub(r"\s+", " ", changes["company_name"]).strip()
    if changes.get("interval_minutes") is not None:
        source.interval_minutes = _interval(changes["interval_minutes"], settings)
    if changes.get("enabled") is not None:
        source.enabled = changes["enabled"]
        if source.enabled and source.next_run_at is None:
            source.next_run_at = datetime.now(UTC)
    session.commit()
    return source


@router.delete("/{source_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_source(source_id: uuid.UUID, session: SessionDep) -> Response:
    """Stop following a board. Jobs already found are kept."""
    session.delete(_get_or_404(session, source_id))
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{source_id}/run", response_model=RunOut)
def run_now(source_id: uuid.UUID, session: SessionDep, settings: SettingsDep, fetcher: FetcherDep,
            ai: AIDep) -> SourceRun:
    """Fetch this board now. Limited to once per cooldown period per board."""
    source = _get_or_404(session, source_id)
    now = datetime.now(UTC)
    cooldown = timedelta(minutes=settings.discovery_manual_cooldown_minutes)
    if source.last_run_at and now - source.last_run_at < cooldown:
        wait = int((source.last_run_at + cooldown - now).total_seconds()) + 1
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS,
                            f"This board was checked recently. Try again in {max(1, wait // 60)} minute(s).",
                            headers={"Retry-After": str(wait)})
    return run_source(session, source, fetcher=fetcher, settings=settings,
                      preferences=load_preferences(session), ai=ai, trigger="manual", now=now)


@router.get("/{source_id}/runs", response_model=list[RunOut])
def list_runs(source_id: uuid.UUID, session: SessionDep,
              limit: Annotated[int, Query(ge=1, le=100)] = 20) -> list[SourceRun]:
    _get_or_404(session, source_id)
    return list(session.scalars(select(SourceRun).where(SourceRun.source_id == source_id)
                                .order_by(SourceRun.started_at.desc()).limit(limit)))


def _interval(minutes: int, settings: Settings) -> int:
    if minutes < settings.discovery_min_interval_minutes:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT,
                            f"Boards can be checked at most every {settings.discovery_min_interval_minutes} minutes.")
    return min(minutes, 7 * 24 * 60)


def _get_or_404(session: Session, source_id: uuid.UUID) -> JobSource:
    source = session.get(JobSource, source_id)
    if source is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Source not found.")
    return source

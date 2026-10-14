"""Application tracker endpoints, shaped for both the web app and a future mobile app.

All list responses are JSON objects ({items, next_cursor, total}) so fields can be added without
breaking clients. Nothing here applies for jobs; statuses are set by the user.
"""

import logging
from datetime import UTC, date, datetime, time, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from jobpilot.api.routes.preferences import load_preferences
from jobpilot.core.config import Settings, get_settings
from jobpilot.db.models import Job, JobSource, TailoredResume
from jobpilot.db.session import get_session
from jobpilot.services.applications import STATUSES, ApplicationStatus
from jobpilot.services.jobs import load_profile, match_for_job, stored_requirements
from jobpilot.services.tracker import (
    SortKey,
    TrackerFilters,
    TrackerRow,
    View,
    apply_filters,
    decode_cursor,
    encode_cursor,
    sort_rows,
    to_csv,
    view_statuses,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/applications", tags=["applications"])

SessionDep = Annotated[Session, Depends(get_session)]
SettingsDep = Annotated[Settings, Depends(get_settings)]
MAX_EXPORT_ROWS = 5_000


class TrackerPage(BaseModel):
    items: list[TrackerRow]
    next_cursor: str | None
    total: int


class TrackerSummary(BaseModel):
    new: int
    by_status: dict[str, int]


def tracker_filters(
    view: View = "all",
    status_: Annotated[list[ApplicationStatus] | None, Query(alias="status")] = None,
    min_score: Annotated[int | None, Query(ge=0, le=100)] = None,
    eligible_only: bool = False,
    found_from: date | None = None,
    found_to: date | None = None,
    company: Annotated[str | None, Query(max_length=200)] = None,
    q: Annotated[str | None, Query(max_length=200)] = None,
    min_salary: Annotated[int | None, Query(ge=0, le=100_000_000)] = None,
    salary_currency: Annotated[str | None, Query(pattern=r"^[A-Za-z]{3}$")] = None,
    include_unknown_salary: bool = True,
    sort: SortKey = "score",
    order: Annotated[str, Query(pattern="^(asc|desc)$")] = "desc",
) -> TrackerFilters:
    return TrackerFilters(
        view=view, statuses=tuple(status_ or ()), min_score=min_score, eligible_only=eligible_only,
        found_from=found_from, found_to=found_to, company=(company or "").strip() or None,
        search=(q or "").strip() or None, min_salary=min_salary,
        salary_currency=salary_currency.upper() if salary_currency else None,
        include_unknown_salary=include_unknown_salary, sort=sort, descending=order == "desc",
    )


FiltersDep = Annotated[TrackerFilters, Depends(tracker_filters)]


@router.get("", response_model=TrackerPage)
def list_applications(filters: FiltersDep, session: SessionDep, settings: SettingsDep,
                      limit: Annotated[int, Query(ge=1, le=200)] = 50, cursor: str | None = None) -> TrackerPage:
    """Jobs with their match and status, filtered and sorted. Pass next_cursor to get more."""
    try:
        offset = decode_cursor(cursor, filters) if cursor else 0
    except ValueError:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT,
                            "That page cursor is invalid or belongs to different filters.") from None
    rows = tracker_rows(session, settings, filters)
    page = rows[offset: offset + limit]
    more = offset + limit < len(rows)
    return TrackerPage(items=page, total=len(rows),
                       next_cursor=encode_cursor(offset + limit, filters) if more else None)


@router.get("/summary", response_model=TrackerSummary)
def summary(session: SessionDep) -> TrackerSummary:
    """Counts for tabs and badges."""
    counts = dict(session.execute(select(Job.application_status, func.count()).group_by(Job.application_status)).all())
    new = session.scalar(select(func.count()).select_from(Job).where(
        Job.application_status == "discovered", Job.seen_at.is_(None), Job.closed_at.is_(None)))
    return TrackerSummary(new=new, by_status={s: counts.get(s, 0) for s in STATUSES})


@router.get("/export.csv")
def export_csv(filters: FiltersDep, session: SessionDep, settings: SettingsDep) -> Response:
    """The same rows as the list, as CSV. Spreadsheet formulas are neutralised; notes are excluded."""
    rows = tracker_rows(session, settings, filters)[:MAX_EXPORT_ROWS]
    logger.info("applications exported rows=%d", len(rows))
    filename = f"jobpilot-applications-{datetime.now(UTC).date().isoformat()}.csv"
    return Response(content="﻿" + to_csv(rows), media_type="text/csv; charset=utf-8", headers={
        "Content-Disposition": f'attachment; filename="{filename}"',
        "Cache-Control": "no-store, private",
        "X-Content-Type-Options": "nosniff",
    })


def tracker_rows(session: Session, settings: Settings, f: TrackerFilters) -> list[TrackerRow]:
    query = select(Job, JobSource.provider).outerjoin(JobSource, Job.source_id == JobSource.id)
    statuses = f.statuses or view_statuses(f.view)
    if statuses is None:
        query = query.where(Job.application_status != "archived")
    else:
        query = query.where(Job.application_status.in_(statuses))
    found = func.coalesce(Job.first_seen_at, Job.created_at)
    if f.found_from:
        query = query.where(found >= datetime.combine(f.found_from, time.min, UTC))
    if f.found_to:
        query = query.where(found < datetime.combine(f.found_to + timedelta(days=1), time.min, UTC))
    if f.company:
        query = query.where(Job.company.ilike(f"%{_escape_like(f.company)}%", escape="\\"))
    if f.search:
        term = f"%{_escape_like(f.search)}%"
        query = query.where(or_(Job.title.ilike(term, escape="\\"), Job.company.ilike(term, escape="\\")))

    results = session.execute(query).all()
    resume_states = _resume_states(session, [job.id for job, _ in results])
    preferences, profile = load_preferences(session), load_profile(session)
    rows = []
    for job, provider in results:
        match = match_for_job(job, preferences, profile, settings.match_weights)
        requirements = stored_requirements(job)
        rows.append(TrackerRow(
            id=str(job.id), title=job.title, company=job.company, application_status=job.application_status,
            match_score=match.score, match_coverage=match.coverage, eligible=match.eligible,
            location=requirements.location, work_arrangement=requirements.work_arrangement,
            salary_min=requirements.salary.min, salary_max=requirements.salary.max,
            salary_currency=requirements.salary.currency, salary_period=requirements.salary.period,
            found_at=job.first_seen_at or job.created_at, posted_at=job.posted_at, last_seen_at=job.last_seen_at,
            closed=job.closed_at is not None,
            is_new=job.application_status == "discovered" and job.seen_at is None and job.closed_at is None,
            source_provider=provider, source_url=job.source_url,
            resume_status=resume_states.get(job.id, "none"), status_changed_at=job.status_changed_at,
        ))
    return sort_rows(apply_filters(rows, f), f.sort, f.descending)


def _resume_states(session: Session, job_ids: list) -> dict:
    if not job_ids:
        return {}
    approved = func.bool_or(TailoredResume.status == "approved")
    rows = session.execute(select(TailoredResume.job_id, approved)
                           .where(TailoredResume.job_id.in_(job_ids)).group_by(TailoredResume.job_id)).all()
    return {job_id: "approved" if any_approved else "draft" for job_id, any_approved in rows}


def _escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")

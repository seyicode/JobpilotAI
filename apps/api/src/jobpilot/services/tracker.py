"""Application tracker: one row per job with its match, for lists, filters, and CSV export.

Scores are computed on request by the matching engine, so score filters and sorting run in
Python after the database filters. Pagination uses an opaque offset cursor bound to the filters.
"""

import base64
import csv
import hashlib
import io
import json
from dataclasses import asdict, dataclass
from datetime import date, datetime
from typing import Literal

from jobpilot.services.applications import IN_PROGRESS, SAVED
from jobpilot.services.preferences import ANNUAL_MULTIPLIER

View = Literal["new", "saved", "in_progress", "all", "archived"]
SortKey = Literal["score", "found", "company", "salary", "status_changed"]


@dataclass
class TrackerRow:
    id: str
    title: str | None
    company: str | None
    application_status: str
    match_score: int | None
    match_coverage: int
    eligible: bool
    location: str | None
    work_arrangement: str | None
    salary_min: int | None
    salary_max: int | None
    salary_currency: str | None
    salary_period: str | None
    found_at: datetime
    posted_at: datetime | None
    last_seen_at: datetime | None
    closed: bool
    is_new: bool
    source_provider: str | None
    source_url: str | None
    resume_status: Literal["none", "draft", "approved"]
    status_changed_at: datetime | None


@dataclass(frozen=True)
class TrackerFilters:
    view: View = "all"
    statuses: tuple[str, ...] = ()
    min_score: int | None = None
    eligible_only: bool = False
    found_from: date | None = None
    found_to: date | None = None
    company: str | None = None
    search: str | None = None
    min_salary: int | None = None
    salary_currency: str | None = None
    include_unknown_salary: bool = True
    sort: SortKey = "score"
    descending: bool = True

    def fingerprint(self) -> str:
        raw = json.dumps(asdict(self), default=str, sort_keys=True)
        return hashlib.sha256(raw.encode()).hexdigest()[:16]


def view_statuses(view: View) -> tuple[str, ...] | None:
    """Statuses a view covers; None means "all except archived"."""
    return {"new": ("discovered",), "saved": SAVED, "in_progress": IN_PROGRESS,
            "archived": ("archived",), "all": None}[view]


def annual_salary(row: TrackerRow) -> int | None:
    amount = row.salary_max if row.salary_max is not None else row.salary_min
    if amount is None or row.salary_period is None:
        return None
    return amount * ANNUAL_MULTIPLIER[row.salary_period]


def apply_filters(rows: list[TrackerRow], f: TrackerFilters) -> list[TrackerRow]:
    """Filters that need the computed match or normalised salary."""
    result = []
    for row in rows:
        if f.view == "new" and not row.is_new:
            continue
        if f.min_score is not None and (row.match_score is None or row.match_score < f.min_score):
            continue
        if f.eligible_only and not row.eligible:
            continue
        if f.min_salary is not None:
            annual = annual_salary(row)
            # Another currency can't be compared, so it counts as unknown, as in must-match filters.
            comparable = (annual is not None and row.salary_currency is not None
                          and (not f.salary_currency or row.salary_currency == f.salary_currency))
            if not comparable:
                if not f.include_unknown_salary:
                    continue
            elif annual < f.min_salary:
                continue
        result.append(row)
    return result


def sort_rows(rows: list[TrackerRow], key: SortKey, descending: bool) -> list[TrackerRow]:
    """Missing values always sort last, whatever the direction."""
    def value(row: TrackerRow):
        return {
            "score": row.match_score,
            "found": row.found_at,
            "company": (row.company or "").lower() or None,
            "salary": annual_salary(row),
            "status_changed": row.status_changed_at,
        }[key]

    present = [r for r in rows if value(r) is not None]
    missing = [r for r in rows if value(r) is None]
    present.sort(key=lambda r: (value(r), r.found_at, r.id), reverse=descending)
    return present + sorted(missing, key=lambda r: (r.found_at, r.id), reverse=True)


def encode_cursor(offset: int, filters: TrackerFilters) -> str:
    raw = json.dumps({"o": offset, "f": filters.fingerprint()}).encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def decode_cursor(cursor: str, filters: TrackerFilters) -> int:
    """Raises ValueError for a malformed cursor or one made with different filters."""
    padded = cursor + "=" * (-len(cursor) % 4)
    data = json.loads(base64.urlsafe_b64decode(padded.encode()))
    if not isinstance(data, dict) or data.get("f") != filters.fingerprint():
        raise ValueError("cursor does not match these filters")
    offset = data.get("o")
    if not isinstance(offset, int) or offset < 0:
        raise ValueError("bad cursor offset")
    return offset


CSV_COLUMNS = [
    ("Title", "title"), ("Company", "company"), ("Status", "application_status"),
    ("Match score", "match_score"), ("Score coverage %", "match_coverage"), ("Passes must-match", "eligible"),
    ("Location", "location"), ("Work arrangement", "work_arrangement"),
    ("Salary min", "salary_min"), ("Salary max", "salary_max"), ("Currency", "salary_currency"),
    ("Pay period", "salary_period"), ("Found", "found_at"), ("Posted", "posted_at"),
    ("Last seen", "last_seen_at"), ("No longer listed", "closed"), ("Source", "source_provider"),
    ("Link", "source_url"), ("Resume", "resume_status"),
]
_FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


def csv_cell(value: object) -> str:
    """Stringify, neutralising spreadsheet formulas (CSV injection)."""
    if value is None:
        return ""
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, datetime):
        return value.isoformat(timespec="minutes")
    text = str(value)
    return "'" + text if text.startswith(_FORMULA_PREFIXES) else text


def to_csv(rows: list[TrackerRow]) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow([header for header, _ in CSV_COLUMNS])
    for row in rows:
        writer.writerow([csv_cell(getattr(row, attr)) for _, attr in CSV_COLUMNS])
    return buffer.getvalue()

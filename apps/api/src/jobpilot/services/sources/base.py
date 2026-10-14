"""Shared types for job-source adapters.

An adapter knows one provider's public job-board feed: which host it lives on, how to build the
feed URL for a board, and how to turn the feed's JSON into NormalizedPostings. Adapters never
fetch anything themselves (the fetcher does), never scrape web pages, and never visit job URLs.
"""

import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Protocol

BOARD_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,99}$")


class InvalidBoard(ValueError):
    """The board name is not allowed. Safe to show users."""


class FeedFormatError(ValueError):
    """The feed's JSON did not have the expected shape."""


@dataclass
class NormalizedPosting:
    external_id: str  # The provider's id for the posting, unique within the provider
    title: str
    description: str  # Plain text, converted from HTML where needed
    url: str  # The public posting page, kept as the job's source link
    location: str | None = None
    company: str | None = None
    posted_at: datetime | None = None
    # Facts the provider states directly; these override text extraction.
    structured: dict = field(default_factory=dict)


class SourceAdapter(Protocol):
    provider: str
    label: str
    host: str
    docs_url: str

    def feed_url(self, board: str) -> str: ...

    def parse(self, payload: object) -> list[NormalizedPosting]: ...


def validate_board(board: str) -> str:
    board = board.strip()
    if not BOARD_PATTERN.fullmatch(board) or ".." in board:
        raise InvalidBoard("Board names may contain only letters, numbers, dots, hyphens and underscores.")
    return board


def text(value: object, limit: int = 200) -> str | None:
    if isinstance(value, str):
        value = re.sub(r"\s+", " ", value).strip()
        return value[:limit] or None
    return None


def parse_datetime(value: object) -> datetime | None:
    """ISO 8601 strings or Unix epoch milliseconds."""
    try:
        if isinstance(value, int | float) and not isinstance(value, bool):
            return datetime.fromtimestamp(value / 1000, tz=UTC)
        if isinstance(value, str) and value:
            parsed = datetime.fromisoformat(value)
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
    except (ValueError, OverflowError, OSError):
        return None
    return None


def arrangement_from_text(*values: str | None) -> str | None:
    joined = " ".join(v for v in values if v).lower()
    if "hybrid" in joined:
        return "hybrid"
    if "remote" in joined:
        return "remote"
    return None


def employment_type(value: object) -> str | None:
    key = re.sub(r"[^a-z]", "", value.lower()) if isinstance(value, str) else ""
    return {
        "fulltime": "full_time", "permanent": "full_time", "parttime": "part_time",
        "contract": "contract", "contractor": "contract", "freelance": "contract",
        "intern": "internship", "internship": "internship", "temporary": "temporary", "temp": "temporary",
    }.get(key)


def salary(minimum: object, maximum: object, currency: object, period: str | None) -> dict | None:
    def number(v: object) -> int | None:
        return int(v) if isinstance(v, int | float) and not isinstance(v, bool) and v >= 0 else None

    low, high = number(minimum), number(maximum)
    code = currency.strip().upper() if isinstance(currency, str) and re.fullmatch(r"\s*[A-Za-z]{3}\s*", currency) else None
    if low is None and high is None:
        return None
    return {"min": low, "max": high, "currency": code, "period": period}

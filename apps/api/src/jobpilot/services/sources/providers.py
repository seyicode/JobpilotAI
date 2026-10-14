"""Adapters for public company job-board feeds.

Each provider publishes these endpoints specifically so job boards can be read programmatically,
without authentication. Fields are read defensively: anything missing becomes unknown.
"""

from urllib.parse import quote

from jobpilot.services.sources.base import (
    FeedFormatError,
    NormalizedPosting,
    SourceAdapter,
    arrangement_from_text,
    employment_type,
    parse_datetime,
    salary,
    text,
)
from jobpilot.services.sources.html_text import html_to_text


def _list(payload: object, key: str | None) -> list:
    if key is None:
        items = payload
    else:
        items = payload.get(key) if isinstance(payload, dict) else None
    if not isinstance(items, list):
        raise FeedFormatError(f"Expected a list of jobs{f' under {key!r}' if key else ''}.")
    return [item for item in items if isinstance(item, dict)]


def _posting(external_id: object, title: object, description: str, url: object, **extra) -> NormalizedPosting | None:
    if not isinstance(external_id, str | int) or not isinstance(url, str) or not url.startswith("https://"):
        return None
    clean_title = text(title)
    if not clean_title or not description.strip():
        return None
    structured = {k: v for k, v in (extra.pop("structured", {}) or {}).items() if v not in (None, "", [])}
    return NormalizedPosting(external_id=str(external_id), title=clean_title, description=description.strip(),
                             url=url, structured=structured, **extra)


class Greenhouse:
    provider = "greenhouse"
    label = "Greenhouse"
    host = "boards-api.greenhouse.io"
    docs_url = "https://developers.greenhouse.io/job-board.html"

    def feed_url(self, board: str) -> str:
        return f"https://{self.host}/v1/boards/{quote(board, safe='')}/jobs?content=true&pay_transparency=true"

    def parse(self, payload: object) -> list[NormalizedPosting]:
        postings = []
        for job in _list(payload, "jobs"):
            location = text((job.get("location") or {}).get("name") if isinstance(job.get("location"), dict) else None)
            pay = next((r for r in job.get("pay_input_ranges") or [] if isinstance(r, dict)), None)
            pay_range = None
            if pay:
                cents = [pay.get("min_cents"), pay.get("max_cents")]
                low, high = (c // 100 if isinstance(c, int) else None for c in cents)
                pay_range = salary(low, high, pay.get("currency_type"), "year")
            posting = _posting(
                job.get("id"), job.get("title"),
                html_to_text(job.get("content") or "", escaped=True), job.get("absolute_url"),
                location=location, posted_at=parse_datetime(job.get("first_published") or job.get("updated_at")),
                structured={"location": location, "work_arrangement": arrangement_from_text(location),
                            "salary": pay_range},
            )
            if posting:
                postings.append(posting)
        return postings


LEVER_INTERVALS = {"per-year-salary": "year", "per-month-salary": "month", "per-hour-wage": "hour"}
LEVER_WORKPLACE = {"remote": "remote", "hybrid": "hybrid", "onsite": "onsite", "on-site": "onsite"}


class Lever:
    provider = "lever"
    label = "Lever"
    host = "api.lever.co"
    docs_url = "https://github.com/lever/postings-api"

    def feed_url(self, board: str) -> str:
        return f"https://{self.host}/v0/postings/{quote(board, safe='')}?mode=json"

    def parse(self, payload: object) -> list[NormalizedPosting]:
        postings = []
        for job in _list(payload, None):
            categories = job.get("categories") if isinstance(job.get("categories"), dict) else {}
            parts = [job.get("descriptionPlain") or html_to_text(job.get("description") or "")]
            for section in job.get("lists") or []:
                if isinstance(section, dict):
                    parts.append(f"{text(section.get('text')) or ''}\n{html_to_text(section.get('content') or '')}")
            parts.append(job.get("additionalPlain") or html_to_text(job.get("additional") or ""))
            location = text(categories.get("location"))
            range_ = job.get("salaryRange") if isinstance(job.get("salaryRange"), dict) else {}
            workplace = job.get("workplaceType")
            posting = _posting(
                job.get("id"), job.get("text"), "\n\n".join(p for p in parts if p), job.get("hostedUrl"),
                location=location, posted_at=parse_datetime(job.get("createdAt")),
                structured={
                    "location": location,
                    "work_arrangement": LEVER_WORKPLACE.get(workplace) if isinstance(workplace, str) else None,
                    "employment_type": employment_type(categories.get("commitment")),
                    "salary": salary(range_.get("min"), range_.get("max"), range_.get("currency"),
                                     LEVER_INTERVALS.get(range_.get("interval"))) if range_ else None,
                },
            )
            if posting:
                postings.append(posting)
        return postings


ASHBY_WORKPLACE = {"remote": "remote", "hybrid": "hybrid", "onsite": "onsite"}
ASHBY_INTERVALS = {"1 YEAR": "year", "1 MONTH": "month", "1 HOUR": "hour"}


class Ashby:
    provider = "ashby"
    label = "Ashby"
    host = "api.ashbyhq.com"
    docs_url = "https://developers.ashbyhq.com/docs/public-job-posting-api"

    def feed_url(self, board: str) -> str:
        return f"https://{self.host}/posting-api/job-board/{quote(board, safe='')}?includeCompensation=true"

    def parse(self, payload: object) -> list[NormalizedPosting]:
        postings = []
        for job in _list(payload, "jobs"):
            if job.get("isListed") is False:
                continue
            location = text(job.get("location"))
            workplace = job.get("workplaceType")
            arrangement = ASHBY_WORKPLACE.get(workplace.lower()) if isinstance(workplace, str) else None
            if arrangement is None and job.get("isRemote") is True:
                arrangement = "remote"
            description = job.get("descriptionPlain") or html_to_text(job.get("descriptionHtml") or "")
            posting = _posting(
                job.get("id"), job.get("title"), description, job.get("jobUrl"),
                location=location, posted_at=parse_datetime(job.get("publishedAt")),
                structured={"location": location, "work_arrangement": arrangement,
                            "employment_type": employment_type(job.get("employmentType")),
                            "salary": _ashby_salary(job.get("compensation"))},
            )
            if posting:
                postings.append(posting)
        return postings


def _ashby_salary(compensation: object) -> dict | None:
    if not isinstance(compensation, dict):
        return None
    for component in compensation.get("summaryComponents") or []:
        if isinstance(component, dict) and component.get("compensationType") == "Salary":
            return salary(component.get("minValue"), component.get("maxValue"), component.get("currencyCode"),
                          ASHBY_INTERVALS.get(component.get("interval")))
    return None


ADAPTERS: dict[str, SourceAdapter] = {a.provider: a for a in (Greenhouse(), Lever(), Ashby())}

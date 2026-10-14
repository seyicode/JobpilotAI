"""Job preferences and explainable hard filters.

Hard filters only fail on a known conflict. When a job is missing the information needed
to decide (for example, no salary listed), the result is "unknown" and the job passes.
"""

import re
from dataclasses import dataclass
from typing import Annotated, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

WorkArrangement = Literal["remote", "hybrid", "onsite"]
EmploymentType = Literal["full_time", "part_time", "contract", "internship", "temporary"]
Seniority = Literal["intern", "entry", "mid", "senior", "lead", "manager", "director", "executive"]
SalaryPeriod = Literal["year", "month", "hour"]
HardFilter = Literal["work_arrangement", "location", "employment_type", "seniority", "min_salary"]

ANNUAL_MULTIPLIER = {"year": 1, "month": 12, "hour": 2080}  # 40 hours x 52 weeks
Term = Annotated[str, Field(min_length=1, max_length=100)]


def _terms(max_items: int = 20):
    return Field(default_factory=list, max_length=max_items)


class JobPreferences(BaseModel):
    target_titles: list[Term] = _terms()
    seniority_levels: list[Seniority] = _terms()
    locations: list[Term] = _terms()
    willing_to_relocate: bool = False
    work_arrangements: list[WorkArrangement] = _terms()
    employment_types: list[EmploymentType] = _terms()
    min_salary: Annotated[int | None, Field(default=None, ge=0, le=100_000_000)]
    salary_currency: Annotated[str, Field(pattern=r"^[A-Z]{3}$")] = "USD"
    salary_period: SalaryPeriod = "year"
    include_keywords: list[Term] = _terms(50)
    exclude_keywords: list[Term] = _terms(50)
    excluded_companies: list[Term] = _terms(100)
    hard_filters: list[HardFilter] = Field(default_factory=lambda: ["work_arrangement"])

    @field_validator(
        "target_titles", "locations", "include_keywords", "exclude_keywords", "excluded_companies",
        mode="before",
    )
    @classmethod
    def clean_terms(cls, value: object) -> object:
        """Trim, collapse whitespace, drop blanks, and dedupe case-insensitively."""
        if not isinstance(value, list):
            return value
        seen, cleaned = set(), []
        for item in value:
            if isinstance(item, str):
                item = re.sub(r"\s+", " ", item).strip()
                if not item or item.lower() in seen:
                    continue
                seen.add(item.lower())
            cleaned.append(item)
        return cleaned

    @field_validator(
        "seniority_levels", "work_arrangements", "employment_types", "hard_filters", mode="after"
    )
    @classmethod
    def dedupe(cls, value: list) -> list:
        return list(dict.fromkeys(value))

    @field_validator("salary_currency", mode="before")
    @classmethod
    def upper_currency(cls, value: object) -> object:
        return value.strip().upper() if isinstance(value, str) else value

    @model_validator(mode="after")
    def keyword_conflicts(self) -> "JobPreferences":
        overlap = {k.lower() for k in self.include_keywords} & {
            k.lower() for k in self.exclude_keywords
        }
        if overlap:
            raise ValueError(f"Keywords cannot be both included and excluded: {', '.join(sorted(overlap))}.")
        return self


@dataclass(frozen=True)
class JobFacts:
    """What is known about a job posting. None means unknown."""

    title: str
    company: str | None = None
    location: str | None = None
    description: str = ""
    work_arrangement: WorkArrangement | None = None
    employment_type: EmploymentType | None = None
    seniority: Seniority | None = None
    salary_max: int | None = None
    salary_currency: str | None = None
    salary_period: SalaryPeriod | None = None


@dataclass(frozen=True)
class FilterResult:
    filter: str
    status: Literal["pass", "fail", "unknown"]
    reason: str


def check_hard_filters(preferences: JobPreferences, job: JobFacts) -> list[FilterResult]:
    """Evaluate always-on exclusions plus the user's chosen hard filters, with reasons."""
    results = [_excluded_company(preferences, job), _excluded_keywords(preferences, job)]
    checks = {
        "work_arrangement": _work_arrangement,
        "location": _location,
        "employment_type": _employment_type,
        "seniority": _seniority,
        "min_salary": _min_salary,
    }
    results += [checks[name](preferences, job) for name in preferences.hard_filters]
    return [result for result in results if result is not None]


def passes_hard_filters(results: list[FilterResult]) -> bool:
    return all(result.status != "fail" for result in results)


def _excluded_company(p: JobPreferences, job: JobFacts) -> FilterResult | None:
    if not p.excluded_companies:
        return None
    if not job.company:
        return FilterResult("excluded_companies", "unknown", "The company is not listed.")
    company = job.company.lower()
    for excluded in p.excluded_companies:
        if excluded.lower() == company:
            return FilterResult("excluded_companies", "fail", f"{job.company} is on your excluded list.")
    return FilterResult("excluded_companies", "pass", f"{job.company} is not on your excluded list.")


def _excluded_keywords(p: JobPreferences, job: JobFacts) -> FilterResult | None:
    if not p.exclude_keywords:
        return None
    text = f"{job.title}\n{job.description}"
    found = [k for k in p.exclude_keywords if _contains_word(text, k)]
    if found:
        return FilterResult("exclude_keywords", "fail", f"Mentions excluded keywords: {', '.join(found)}.")
    return FilterResult("exclude_keywords", "pass", "No excluded keywords found.")


def _work_arrangement(p: JobPreferences, job: JobFacts) -> FilterResult | None:
    if not p.work_arrangements:
        return None
    if job.work_arrangement is None:
        return FilterResult("work_arrangement", "unknown", "The posting does not say remote, hybrid, or on-site.")
    status = "pass" if job.work_arrangement in p.work_arrangements else "fail"
    wanted = ", ".join(p.work_arrangements)
    return FilterResult("work_arrangement", status, f"Job is {job.work_arrangement}; you want {wanted}.")


def _location(p: JobPreferences, job: JobFacts) -> FilterResult | None:
    if not p.locations:
        return None
    if job.work_arrangement == "remote":
        return FilterResult("location", "pass", "Job is remote, so location does not apply.")
    if not job.location:
        return FilterResult("location", "unknown", "The job location is not listed.")
    matched = next((loc for loc in p.locations if loc.lower() in job.location.lower()), None)
    if matched:
        return FilterResult("location", "pass", f"{job.location} matches {matched}.")
    if p.willing_to_relocate:
        return FilterResult("location", "pass", f"{job.location} is outside your locations, but you are willing to relocate.")
    return FilterResult("location", "fail", f"{job.location} is not in your locations.")


def _employment_type(p: JobPreferences, job: JobFacts) -> FilterResult | None:
    if not p.employment_types:
        return None
    if job.employment_type is None:
        return FilterResult("employment_type", "unknown", "The employment type is not listed.")
    status = "pass" if job.employment_type in p.employment_types else "fail"
    label = job.employment_type.replace("_", "-")
    return FilterResult("employment_type", status, f"Job is {label}.")


def _seniority(p: JobPreferences, job: JobFacts) -> FilterResult | None:
    if not p.seniority_levels:
        return None
    if job.seniority is None:
        return FilterResult("seniority", "unknown", "The seniority level is not clear.")
    status = "pass" if job.seniority in p.seniority_levels else "fail"
    return FilterResult("seniority", status, f"Job is {job.seniority} level.")


def _min_salary(p: JobPreferences, job: JobFacts) -> FilterResult | None:
    if p.min_salary is None:
        return None
    if job.salary_max is None or job.salary_period is None:
        return FilterResult("min_salary", "unknown", "No salary is listed.")
    if (job.salary_currency or "").upper() != p.salary_currency:
        return FilterResult(
            "min_salary", "unknown",
            f"Salary is in {job.salary_currency or 'an unknown currency'}, not {p.salary_currency}.",
        )
    job_annual = job.salary_max * ANNUAL_MULTIPLIER[job.salary_period]
    wanted_annual = p.min_salary * ANNUAL_MULTIPLIER[p.salary_period]
    status = "pass" if job_annual >= wanted_annual else "fail"
    comparison = "meets" if status == "pass" else "is below"
    return FilterResult(
        "min_salary", status,
        f"Top of range {comparison} your minimum (about {job_annual:,} vs {wanted_annual:,} {p.salary_currency} a year).",
    )


def _contains_word(text: str, keyword: str) -> bool:
    return re.search(rf"(?<!\w){re.escape(keyword)}(?!\w)", text, re.IGNORECASE) is not None

"""Structured job requirements. None or an empty list means unknown, never 'not required'."""

import re
from typing import Annotated

from pydantic import BaseModel, Field, field_validator, model_validator

from jobpilot.services.preferences import EmploymentType, SalaryPeriod, Seniority, WorkArrangement
from jobpilot.services.skills import dedupe_skills, skill_key

ShortText = Annotated[str, Field(min_length=1, max_length=100)]


class Salary(BaseModel):
    min: Annotated[int | None, Field(default=None, ge=0, le=100_000_000)]
    max: Annotated[int | None, Field(default=None, ge=0, le=100_000_000)]
    currency: Annotated[str | None, Field(default=None, pattern=r"^[A-Z]{3}$")]
    period: SalaryPeriod | None = None

    @field_validator("currency", mode="before")
    @classmethod
    def upper(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip().upper() or None
        return value

    @model_validator(mode="after")
    def ordered(self) -> "Salary":
        if self.min is not None and self.max is not None and self.min > self.max:
            self.min, self.max = self.max, self.min
        return self


class JobRequirements(BaseModel):
    title: Annotated[str | None, Field(default=None, max_length=200)]
    company: Annotated[str | None, Field(default=None, max_length=200)]
    required_skills: list[ShortText] = Field(default_factory=list, max_length=50)
    preferred_skills: list[ShortText] = Field(default_factory=list, max_length=50)
    seniority: Seniority | None = None
    location: Annotated[str | None, Field(default=None, max_length=200)]
    work_arrangement: WorkArrangement | None = None
    employment_type: EmploymentType | None = None
    salary: Salary = Field(default_factory=Salary)
    years_experience_min: Annotated[int | None, Field(default=None, ge=0, le=50)]
    qualifications: list[Annotated[str, Field(min_length=1, max_length=300)]] = Field(
        default_factory=list, max_length=30
    )

    @field_validator("title", "company", "location", mode="before")
    @classmethod
    def clean_text(cls, value: object) -> object:
        if isinstance(value, str):
            return re.sub(r"\s+", " ", value).strip() or None
        return value

    @field_validator("required_skills", "preferred_skills", "qualifications", mode="before")
    @classmethod
    def clean_list(cls, value: object) -> object:
        if not isinstance(value, list):
            return value
        return [re.sub(r"\s+", " ", v).strip() if isinstance(v, str) else v for v in value
                if not isinstance(v, str) or v.strip()]

    @model_validator(mode="after")
    def dedupe(self) -> "JobRequirements":
        self.required_skills = dedupe_skills(self.required_skills)
        required = {skill_key(s) for s in self.required_skills}
        self.preferred_skills = [
            s for s in dedupe_skills(self.preferred_skills) if skill_key(s) not in required
        ]
        self.qualifications = list(dict.fromkeys(self.qualifications))
        return self

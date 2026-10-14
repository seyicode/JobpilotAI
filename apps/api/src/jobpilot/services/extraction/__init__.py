"""Job requirement extraction: rules-based for now; an AI extractor is tried first when configured."""

from dataclasses import dataclass

from jobpilot.services.extraction.rules import extract_with_rules
from jobpilot.services.extraction.schema import JobRequirements


@dataclass(frozen=True)
class ExtractionOutcome:
    requirements: JobRequirements
    method: str  # "openai", "rules", or "manual"
    note: str | None = None  # Why a fallback happened; safe to show users


def extract_requirements(
    description: str, *, title: str | None, company: str | None, extra_skills: list[str]
) -> ExtractionOutcome:
    requirements = extract_with_rules(
        description, title=title, company=company, extra_skills=extra_skills
    )
    return ExtractionOutcome(requirements, "rules", "Extracted with local rules.")

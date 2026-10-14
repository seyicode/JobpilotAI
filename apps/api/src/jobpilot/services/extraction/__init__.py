"""Job requirement extraction: OpenAI when configured, with local rules as the fallback."""

import logging
from dataclasses import dataclass

from sqlalchemy.orm import Session

from jobpilot.services.extraction.openai_extractor import AIUnavailable, OpenAIExtractor
from jobpilot.services.extraction.rules import extract_with_rules
from jobpilot.services.extraction.schema import JobRequirements

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ExtractionOutcome:
    requirements: JobRequirements
    method: str  # "openai", "rules", or "manual"
    note: str | None = None  # What happened, including why a fallback was used; safe to show users


def extract_requirements(
    session: Session,
    description: str,
    *,
    title: str | None,
    company: str | None,
    extra_skills: list[str],
    ai: OpenAIExtractor | None,
) -> ExtractionOutcome:
    """Try AI first when available; on any problem, use local rules and say why."""
    if ai is None:
        fallback_reason = "AI extraction is not configured."
    else:
        try:
            requirements, note = ai.extract(session, description)
        except AIUnavailable as error:
            fallback_reason = str(error)
            logger.info("ai extraction fell back to rules reason=%s", fallback_reason)
        else:
            hints = {k: v for k, v in (("title", title), ("company", company)) if v}
            return ExtractionOutcome(requirements.model_copy(update=hints), "openai", note)

    requirements = extract_with_rules(description, title=title, company=company, extra_skills=extra_skills)
    return ExtractionOutcome(requirements, "rules", f"{fallback_reason} Used local rules instead.")

"""Deterministic tailored-resume assembly. No AI, no network, same inputs -> same resume.

Only verified library entries and skills are used. Text is selected and ordered, never
rewritten: every bullet starts as the exact verified highlight. Each choice records a reason.
"""

from dataclasses import dataclass

from jobpilot.services.extraction.schema import JobRequirements
from jobpilot.services.matching import MatchResult, skill_patterns
from jobpilot.services.resumes.schema import (
    SECTION_ORDER,
    ResumeBullet,
    ResumeContent,
    ResumeEntry,
    ResumeHeader,
    ResumeSection,
    UserProfile,
)
from jobpilot.services.skills import skill_key

BULLETS_RECENT = 5  # For the most recent jobs
BULLETS_OLDER = 3
BULLETS_UNRELATED = 2  # Older jobs that mention none of the job's skills
RECENT_JOBS = 2
MAX_PROJECTS = 3
MAX_SKILLS = 30
ALWAYS_INCLUDED = {"job", "education", "certification"}


@dataclass(frozen=True)
class Term:
    name: str
    weight: int  # 2 = required skill, 1 = preferred skill
    label: str


def assemble_resume(
    requirements: JobRequirements,
    match: MatchResult,
    profile: UserProfile,
    experiences: list[dict],
    skills: list[str],
) -> ResumeContent:
    """`experiences` and `skills` must already be filtered to verified items."""
    terms = [Term(s, 2, "required") for s in requirements.required_skills]
    terms += [Term(s, 1, "preferred") for s in requirements.preferred_skills]
    patterns = {t.name: skill_patterns(t.name) for t in terms}
    evidence_quotes = {e.quote for e in match.evidence if e.quote}

    def mentions(text: str) -> list[Term]:
        return [t for t in terms if any(p.search(text) for p in patterns[t.name])]

    sections = []
    for kind, heading in SECTION_ORDER:
        candidates = [e for e in experiences if e["kind"] == kind]
        entries = _entries_for(kind, candidates, mentions, evidence_quotes)
        if entries:
            sections.append(ResumeSection(kind=kind, heading=heading, entries=entries))

    return ResumeContent(
        header=ResumeHeader(
            name=profile.full_name, headline=profile.headline, email=profile.email,
            phone=profile.phone, location=profile.location, links=profile.links,
        ),
        summary=profile.summary,
        skills=order_skills(skills, requirements),
        sections=sections,
    )


def _entries_for(kind, candidates, mentions, evidence_quotes) -> list[ResumeEntry]:
    scored = []
    for experience in candidates:
        bullets = []
        for index, highlight in enumerate(experience.get("highlights") or []):
            found = mentions(highlight)
            score = sum(t.weight for t in found) + (1 if highlight in evidence_quotes else 0)
            bullets.append((score, index, highlight, found))
        title_terms = mentions(experience["title"])
        entry_terms = _unique(title_terms + [t for b in bullets for t in b[3]])
        relevance = sum(b[0] for b in bullets) + sum(t.weight for t in title_terms)
        scored.append((relevance, experience, bullets, entry_terms))

    if kind in ALWAYS_INCLUDED:
        chosen = sorted(scored, key=lambda s: _recency_key(s[1]), reverse=True)
        if kind == "certification":
            chosen.sort(key=lambda s: s[0], reverse=True)  # Stable: relevant first, then newest
    else:
        relevant = [s for s in scored if s[0] > 0]
        chosen = sorted(relevant, key=lambda s: (s[0], _recency_key(s[1])), reverse=True)
        if kind == "project":
            chosen = chosen[:MAX_PROJECTS]

    entries = []
    for position, (relevance, experience, bullets, entry_terms) in enumerate(chosen):
        limit = _bullet_limit(kind, position, relevance)
        ranked = sorted(bullets, key=lambda b: (-b[0], b[1]))[:limit]
        entries.append(ResumeEntry(
            source_id=experience["id"], kind=kind, title=experience["title"],
            organization=experience.get("organization"), location=experience.get("location"),
            start_date=experience.get("start_date"), end_date=experience.get("end_date"),
            is_current=bool(experience.get("is_current")),
            bullets=[ResumeBullet(text=text, source_text=text, reason=_bullet_reason(found))
                     for _, _, text, found in ranked],
            reason=_entry_reason(kind, entry_terms),
        ))
    return entries


def _bullet_limit(kind: str, position: int, relevance: int) -> int:
    if kind != "job":
        return BULLETS_OLDER
    if position < RECENT_JOBS:
        return BULLETS_RECENT
    return BULLETS_OLDER if relevance > 0 else BULLETS_UNRELATED


def _recency_key(experience: dict) -> tuple:
    """Current roles first, then by end date, then start date (missing dates last)."""
    end = "9999-99" if experience.get("is_current") else experience.get("end_date") or ""
    return (end, experience.get("start_date") or "")


def order_skills(skills: list[str], requirements: JobRequirements) -> list[str]:
    """Verified skills the job requires, then preferred, then the rest alphabetically."""
    by_key = {}
    for name in skills:
        by_key.setdefault(skill_key(name), name)
    ordered = []
    for wanted in requirements.required_skills + requirements.preferred_skills:
        name = by_key.pop(skill_key(wanted), None)
        if name:
            ordered.append(name)
    ordered += sorted(by_key.values(), key=str.lower)
    return ordered[:MAX_SKILLS]


def _unique(terms: list[Term]) -> list[Term]:
    seen, result = set(), []
    for term in terms:
        if term.name not in seen:
            seen.add(term.name)
            result.append(term)
    return result


def _describe(terms: list[Term]) -> str:
    parts = []
    for label in ("required", "preferred"):
        names = [t.name for t in terms if t.label == label]
        if names:
            parts.append(f"{', '.join(names)} ({label})")
    return "; ".join(parts)


def _bullet_reason(found: list[Term]) -> str:
    return f"Mentions {_describe(_unique(found))}." if found else "Kept for context."


def _entry_reason(kind: str, terms: list[Term]) -> str:
    if terms:
        return f"Relevant: mentions {_describe(terms)}."
    if kind == "job":
        return "Included to keep your work history complete."
    return f"{dict(SECTION_ORDER)[kind]} entries are always included."

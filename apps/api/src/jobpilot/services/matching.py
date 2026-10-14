"""Deterministic, explainable job matching.

Only verified skills and experience count as evidence. Draft (unverified) items appear only as
hints in gaps. A factor that cannot be judged because a detail is missing is marked unknown and
left out of the score; `coverage` says how much of the total weight was judged.
"""

import re
from dataclasses import dataclass, field
from datetime import date
from typing import Literal

from jobpilot.services.extraction.schema import JobRequirements
from jobpilot.services.preferences import (
    FilterResult,
    JobFacts,
    JobPreferences,
    check_hard_filters,
    check_soft_preferences,
    contains_word,
    passes_hard_filters,
)
from jobpilot.services.skills import ALIASES, skill_key

DEFAULT_WEIGHTS = {
    "required_skills": 35,
    "preferred_skills": 10,
    "experience_years": 15,
    "seniority": 10,
    "title": 10,
    "keywords": 10,
    "preferences": 10,
}
LABELS = {
    "required_skills": "Required skills",
    "preferred_skills": "Preferred skills",
    "experience_years": "Years of experience",
    "seniority": "Seniority",
    "title": "Job title",
    "keywords": "Keywords you want",
    "preferences": "Other preferences",
}
SENIORITY_ORDER = ["intern", "entry", "mid", "senior", "lead", "manager", "director", "executive"]
_STOPWORDS = {"and", "or", "of", "the", "a", "an", "to", "in", "for", "with", "at", "&", "-", "/"}


@dataclass(frozen=True)
class VerifiedProfile:
    """The user's library. Only `verified_*` lists count as evidence."""

    verified_skills: list[str] = field(default_factory=list)
    verified_experiences: list[dict] = field(default_factory=list)
    draft_skills: list[str] = field(default_factory=list)
    draft_experiences: list[dict] = field(default_factory=list)


@dataclass(frozen=True)
class Evidence:
    requirement: str
    kind: Literal["required_skill", "preferred_skill"]
    source: Literal["skill", "experience"]
    source_label: str
    quote: str | None = None


@dataclass(frozen=True)
class Gap:
    requirement: str
    kind: str
    hint: str | None = None


@dataclass(frozen=True)
class ScoreComponent:
    key: str
    label: str
    weight: float
    status: Literal["scored", "unknown"]
    value: float | None
    points: float | None
    detail: str


@dataclass(frozen=True)
class MatchResult:
    eligible: bool
    score: int | None
    coverage: int
    summary: str
    filters: list[FilterResult]
    preference_checks: list[FilterResult]
    components: list[ScoreComponent]
    evidence: list[Evidence]
    gaps: list[Gap]


def job_facts(requirements: JobRequirements, description: str) -> JobFacts:
    salary = requirements.salary
    return JobFacts(
        title=requirements.title or "",
        company=requirements.company,
        location=requirements.location,
        description=description,
        work_arrangement=requirements.work_arrangement,
        employment_type=requirements.employment_type,
        seniority=requirements.seniority,
        salary_max=salary.max if salary.max is not None else salary.min,
        salary_currency=salary.currency,
        salary_period=salary.period,
    )


def match_job(
    requirements: JobRequirements,
    description: str,
    preferences: JobPreferences,
    profile: VerifiedProfile,
    *,
    weights: dict[str, float] | None = None,
    today: date | None = None,
) -> MatchResult:
    weights = DEFAULT_WEIGHTS | validate_weights(weights or {})
    facts = job_facts(requirements, description)
    filters = check_hard_filters(preferences, facts)
    # Seniority has its own scoring factor, so it is not counted again here.
    soft_checks = [c for c in check_soft_preferences(preferences, facts) if c.filter != "seniority"]
    evidence: list[Evidence] = []
    gaps: list[Gap] = []

    components = [
        _skills_component("required_skills", requirements.required_skills, profile, evidence, gaps),
        _skills_component("preferred_skills", requirements.preferred_skills, profile, evidence, gaps),
        _experience_component(requirements, profile, gaps, today or date.today()),
        _seniority_component(requirements, preferences),
        _title_component(requirements, preferences),
        _keywords_component(facts, preferences),
        _preferences_component(soft_checks),
    ]
    components = [_weigh(c, weights[c.key]) for c in components]

    known = [c for c in components if c.status == "scored" and c.weight > 0]
    total_weight = sum(c.weight for c in components)
    known_weight = sum(c.weight for c in known)
    score = round(sum(c.points for c in known) / known_weight * 100) if known_weight else None
    coverage = round(known_weight / total_weight * 100) if total_weight else 0
    eligible = passes_hard_filters(filters)
    return MatchResult(
        eligible=eligible, score=score, coverage=coverage,
        summary=_summary(eligible, score, coverage, filters),
        filters=filters, preference_checks=soft_checks, components=components,
        evidence=evidence, gaps=gaps,
    )


def validate_weights(weights: dict[str, float]) -> dict[str, float]:
    unknown = set(weights) - set(DEFAULT_WEIGHTS)
    if unknown:
        raise ValueError(f"Unknown match weight(s): {', '.join(sorted(unknown))}")
    if any(w < 0 for w in weights.values()):
        raise ValueError("Match weights cannot be negative")
    return weights


def _component(key: str, value: float | None, detail: str) -> ScoreComponent:
    status = "unknown" if value is None else "scored"
    return ScoreComponent(key, LABELS[key], 0, status, value, None, detail)


def _weigh(component: ScoreComponent, weight: float) -> ScoreComponent:
    points = None if component.value is None else round(component.value * weight, 2)
    return ScoreComponent(component.key, component.label, weight, component.status,
                          component.value, points, component.detail)


def _skills_component(key: str, skills: list[str], profile: VerifiedProfile,
                      evidence: list[Evidence], gaps: list[Gap]) -> ScoreComponent:
    kind = key[:-1]  # "required_skill" / "preferred_skill"
    if not skills:
        return _component(key, None, "The posting lists none, so this was not scored.")
    matched = 0
    for skill in skills:
        found = _skill_evidence(skill, kind, profile)
        if found:
            matched += 1
            evidence.extend(found)
        else:
            gaps.append(Gap(skill, kind, _draft_hint(skill, profile)))
    return _component(key, matched / len(skills), f"{matched} of {len(skills)} backed by your verified library.")


def _skill_evidence(skill: str, kind: str, profile: VerifiedProfile) -> list[Evidence]:
    key = skill_key(skill)
    found = [Evidence(skill, kind, "skill", f"Verified skill: {name}")
             for name in profile.verified_skills if skill_key(name) == key][:1]
    for experience in profile.verified_experiences:
        quote = _mention(skill, experience)
        if quote is not None:
            found.append(Evidence(skill, kind, "experience", _experience_label(experience), quote or None))
            if len(found) >= 3:
                break
    return found


def _mention(skill: str, experience: dict) -> str | None:
    """The highlight mentioning the skill, "" if only the title does, or None."""
    patterns = skill_patterns(skill)
    for highlight in experience.get("highlights") or []:
        if any(p.search(highlight) for p in patterns):
            return highlight if len(highlight) <= 200 else highlight[:197] + "..."
    if any(p.search(experience.get("title") or "") for p in patterns):
        return ""
    return None


def skill_patterns(skill: str) -> list[re.Pattern]:
    key = skill_key(skill)
    spellings = {skill, key} | {alias for alias, target in ALIASES.items() if target == key}
    return [re.compile(rf"(?<![\w+#.]){re.escape(s)}(?![\w+#])", re.IGNORECASE) for s in spellings]


def _draft_hint(skill: str, profile: VerifiedProfile) -> str | None:
    key = skill_key(skill)
    for name in profile.draft_skills:
        if skill_key(name) == key:
            return f"“{name}” is a draft skill in your library. Verify it if it's accurate."
    for experience in profile.draft_experiences:
        if _mention(skill, experience) is not None:
            return f"Mentioned in a draft entry ({_experience_label(experience)}). Verify it to count."
    return None


def _experience_label(experience: dict) -> str:
    title, organization = experience.get("title"), experience.get("organization")
    return f"{title} at {organization}" if organization else title


def _experience_component(requirements: JobRequirements, profile: VerifiedProfile,
                          gaps: list[Gap], today: date) -> ScoreComponent:
    needed = requirements.years_experience_min
    if not needed:
        return _component("experience_years", None, "The posting gives no minimum years.")
    jobs = [e for e in profile.verified_experiences if e.get("kind") == "job"]
    years = verified_years(jobs, today)
    undated = sum(1 for e in jobs if not e.get("start_date"))
    if years < needed:
        hint = f"{undated} verified work entr{'y has' if undated == 1 else 'ies have'} no dates." if undated else None
        gaps.append(Gap(f"{needed}+ years of experience", "experience", hint))
    return _component("experience_years", min(1.0, years / needed),
                      f"About {years:g} verified years of work experience; the posting asks for {needed}+.")


def verified_years(experiences: list[dict], today: date) -> float:
    """Total years covered by dated entries, counting overlapping periods once."""
    spans = []
    for e in experiences:
        start = _month_index(e.get("start_date"), first=True)
        end = _month_index(f"{today.year}-{today.month:02d}", first=False) if e.get("is_current") \
            else _month_index(e.get("end_date"), first=False)
        if start is not None and end is not None and end >= start:
            spans.append((start, end + 1))
    months, cursor = 0, None
    for start, end in sorted(spans):
        if cursor is not None and start < cursor:
            start = cursor
        if end > start:
            months += end - start
            cursor = end
    return round(months / 12, 1)


def _month_index(value: str | None, *, first: bool) -> int | None:
    if not value:
        return None
    year, _, month = value.partition("-")
    return int(year) * 12 + (int(month) - 1 if month else (0 if first else 11))


def _seniority_component(requirements: JobRequirements, preferences: JobPreferences) -> ScoreComponent:
    job_level, wanted = requirements.seniority, preferences.seniority_levels
    if job_level is None:
        return _component("seniority", None, "The posting does not state a level.")
    if not wanted:
        return _component("seniority", None, "You have not chosen target levels.")
    if job_level in wanted:
        return _component("seniority", 1.0, f"{job_level.title()} is one of your target levels.")
    distance = min(abs(SENIORITY_ORDER.index(job_level) - SENIORITY_ORDER.index(w)) for w in wanted)
    if distance == 1:
        return _component("seniority", 0.5, f"{job_level.title()} is one step from your target levels.")
    return _component("seniority", 0.0, f"{job_level.title()} is outside your target levels.")


def _title_component(requirements: JobRequirements, preferences: JobPreferences) -> ScoreComponent:
    title = requirements.title
    if not title:
        return _component("title", None, "The posting has no clear job title.")
    if not preferences.target_titles:
        return _component("title", None, "You have not set target job titles.")
    best, best_target = 0.0, preferences.target_titles[0]
    for target in preferences.target_titles:
        value = _title_similarity(target, title)
        if value > best:
            best, best_target = value, target
    if best == 1.0:
        return _component("title", 1.0, f"Matches your target “{best_target}”.")
    if best > 0:
        return _component("title", round(best, 2), f"Partly matches your target “{best_target}”.")
    return _component("title", 0.0, "Does not match any of your target titles.")


def _title_similarity(target: str, title: str) -> float:
    if target.lower() in title.lower():
        return 1.0
    target_words, title_words = _words(target), _words(title)
    if not target_words:
        return 0.0
    return len(target_words & title_words) / len(target_words)


def _words(text: str) -> set[str]:
    return {w for w in re.findall(r"[\w+#.]+", text.lower()) if w not in _STOPWORDS}


def _keywords_component(facts: JobFacts, preferences: JobPreferences) -> ScoreComponent:
    keywords = preferences.include_keywords
    if not keywords:
        return _component("keywords", None, "You have not set keywords you'd like to see.")
    text = f"{facts.title}\n{facts.description}"
    found = [k for k in keywords if contains_word(text, k)]
    detail = f"Mentions {', '.join(found)}." if found else "Mentions none of your keywords."
    return _component("keywords", len(found) / len(keywords), detail)


def _preferences_component(checks: list[FilterResult]) -> ScoreComponent:
    known = [c for c in checks if c.status != "unknown"]
    if not known:
        return _component("preferences", None, "No other preferences could be checked.")
    passed = sum(1 for c in known if c.status == "pass")
    return _component("preferences", passed / len(known), f"{passed} of {len(known)} other preferences met.")


def _summary(eligible: bool, score: int | None, coverage: int, filters: list[FilterResult]) -> str:
    if not eligible:
        reasons = " ".join(f.reason for f in filters if f.status == "fail")
        return f"Filtered out by your must-match preferences. {reasons}"
    if score is None:
        return "Not enough information to score this job."
    return f"{score}% match, based on {coverage}% of the scoring factors. Scores are estimates, not guarantees."

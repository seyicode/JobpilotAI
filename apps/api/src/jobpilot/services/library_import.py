"""Turn parsed resume sections into unverified library drafts. Heuristic; users review everything."""

import re
from dataclasses import dataclass, field

SECTION_KINDS = {
    "experience": "job",
    "education": "education",
    "projects": "project",
    "certifications": "certification",
    "volunteering": "volunteering",
}

_BULLET = re.compile(r"^\s*(?:[•●▪◦‣∙·\-*–]|o\s)\s*")
_MONTH = r"(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\.?"
_DATE = rf"(?:{_MONTH}\s+\d{{4}}|\d{{1,2}}/\d{{4}}|\d{{4}})"
_RANGE = re.compile(
    rf"(?P<start>{_DATE})\s*(?:-|–|—|to)\s*(?P<end>{_DATE}|present|current|now)", re.IGNORECASE
)
_SINGLE = re.compile(rf"\b(?P<date>{_DATE})\b", re.IGNORECASE)
_MONTHS = ("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec")
_TITLE_SPLIT = re.compile(r"\s+at\s+|\s*[|,]\s*|\s+[–—-]\s+")


@dataclass
class ExperienceDraft:
    kind: str
    title: str
    organization: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    is_current: bool = False
    highlights: list[str] = field(default_factory=list)


def drafts_from_sections(sections: list[dict]) -> tuple[list[ExperienceDraft], list[str]]:
    experiences: list[ExperienceDraft] = []
    skills: list[str] = []
    for section in sections:
        if section["key"] == "skills":
            skills.extend(split_skills(section["content"]))
        elif section["key"] in SECTION_KINDS:
            kind = SECTION_KINDS[section["key"]]
            for block in split_entries(section["content"]):
                draft = parse_entry(kind, block)
                if draft:
                    experiences.append(draft)
    return experiences, _dedupe(skills)


def split_entries(content: str) -> list[list[str]]:
    """Split on blank lines, and where a non-bullet line follows bullet lines."""
    entries: list[list[str]] = []
    current: list[str] = []
    previous_was_bullet = False
    for line in content.splitlines():
        is_bullet = bool(_BULLET.match(line))
        if not line.strip() or (previous_was_bullet and not is_bullet):
            if current:
                entries.append(current)
            current = []
        if line.strip():
            current.append(line.strip())
        previous_was_bullet = is_bullet
    if current:
        entries.append(current)
    return entries


def parse_entry(kind: str, lines: list[str]) -> ExperienceDraft | None:
    if any(_BULLET.match(line) for line in lines):
        header = []
        for line in lines:
            if _BULLET.match(line) or len(header) == 3:
                break
            header.append(line)
    else:  # No bullets: title and organization lines, plus any date-only lines after them.
        header = lines[:2]
        while len(header) < len(lines) and _is_date_line(lines[len(header)]):
            header.append(lines[len(header)])
    highlights = [_BULLET.sub("", line).strip() for line in lines[len(header):]]

    header_text = " | ".join(header)
    draft = ExperienceDraft(kind=kind, title="", highlights=[h[:500] for h in highlights if h][:30])
    match = _RANGE.search(header_text)
    if match:
        draft.start_date = normalize_date(match["start"])
        end = match["end"].lower()
        draft.is_current = end in ("present", "current", "now")
        draft.end_date = None if draft.is_current else normalize_date(match["end"])
        header_text = header_text[: match.start()] + header_text[match.end() :]
    elif kind in ("education", "certification") and (single := _SINGLE.search(header_text)):
        draft.end_date = normalize_date(single["date"])
        header_text = header_text[: single.start()] + header_text[single.end() :]

    parts = [p.strip(" ,|()–—-") for p in _TITLE_SPLIT.split(header_text)]
    parts = [p for p in parts if p]
    if not parts:
        return None
    draft.title = parts[0][:200]
    draft.organization = parts[1][:200] if len(parts) > 1 else None
    return draft


def _is_date_line(line: str) -> bool:
    line = line.strip(" ()")
    return bool(_RANGE.fullmatch(line) or _SINGLE.fullmatch(line))


def normalize_date(value: str) -> str | None:
    """Convert 'Mar 2021', '03/2021', or '2021' to 'YYYY-MM' or 'YYYY'."""
    value = value.strip().lower()
    if match := re.fullmatch(r"(\d{1,2})/(\d{4})", value):
        month = int(match[1])
        return f"{match[2]}-{month:02d}" if 1 <= month <= 12 else match[2]
    if match := re.fullmatch(rf"({_MONTH})\s+(\d{{4}})", value):
        return f"{match[2]}-{_MONTHS.index(match[1][:3]) + 1:02d}"
    if re.fullmatch(r"\d{4}", value):
        return value
    return None


def split_skills(content: str) -> list[str]:
    skills = []
    for line in content.splitlines():
        line = _BULLET.sub("", line)
        if ":" in line:  # "Languages: Python, Go" -> drop the category label
            line = line.split(":", 1)[1]
        for token in re.split(r"[,;|•·]|\s/\s", line):
            token = token.strip(" .")
            if 0 < len(token) <= 60 and len(token.split()) <= 5:
                skills.append(token)
    return skills


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    unique = []
    for value in values:
        if value.lower() not in seen:
            seen.add(value.lower())
            unique.append(value)
    return unique

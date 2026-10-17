"""Checks that tailored resume text makes no claims beyond the verified library.

Used for both user edits (which produce warnings the user must acknowledge) and AI rewrites
(which are rejected outright). Heuristic: it catches new numbers, new skills or tools, and new
proper nouns, which are the usual ways a rewrite overstates experience.
"""

import re
from dataclasses import dataclass

from jobpilot.services.extraction.rules import ALIAS_SPELLINGS, KNOWN_SKILLS
from jobpilot.services.matching import skill_patterns
from jobpilot.services.skills import skill_key

_NUMBER = re.compile(r"(?<![\w.])[$£€]?\d+(?:[.,]\d+)*\s?(?:%|k\b|m\b|x\b)?", re.IGNORECASE)
_CAPITALISED = re.compile(r"\b[A-Z][\w&.+#-]*[A-Za-z0-9+#]\b|\b[A-Z]\b")


@dataclass(frozen=True)
class ClaimIssue:
    location: str  # Human-readable place, e.g. 'Senior Engineer at Example Corp, bullet 2'
    message: str


def numbers(text: str) -> set[str]:
    """Numbers as written, normalised: '1,200' == '1200', '40 %' == '40%'."""
    return {re.sub(r"[,\s]", "", m.group()).lower() for m in _NUMBER.finditer(text)}


def skill_terms(text: str, vocabulary: list[str]) -> set[str]:
    """Skill keys mentioned in the text (aliases resolved)."""
    found = set()
    for name in vocabulary:
        if any(p.search(text) for p in skill_patterns(name)):
            found.add(skill_key(name))
    return found


def proper_nouns(text: str) -> set[str]:
    """Capitalised words that are not simply starting a sentence."""
    found = set()
    for match in _CAPITALISED.finditer(text):
        before = text[: match.start()].rstrip()
        sentence_start = not before or before[-1] in ".!?:;•-–(\"'"
        if not sentence_start:
            found.add(match.group().rstrip(".").lower())
    return found


def vocabulary(extra: list[str]) -> list[str]:
    return list(dict.fromkeys(KNOWN_SKILLS + ALIAS_SPELLINGS + extra))


def new_claims(text: str, source: str, vocab: list[str], *, check_nouns: bool) -> list[str]:
    """Describe anything in `text` that is not supported by `source`."""
    problems = []
    added_numbers = numbers(text) - numbers(source)
    if added_numbers:
        problems.append(f"adds number(s) not in your verified entry: {', '.join(sorted(added_numbers))}")
    added_skills = skill_terms(text, vocab) - skill_terms(source, vocab)
    if added_skills:
        problems.append(f"adds skill(s) not in your verified entry: {', '.join(sorted(added_skills))}")
    if check_nouns:
        source_words = {w.strip(".").lower() for w in re.findall(r"[\w&.+#-]+", source)}
        # Skill names (including aliases such as Postgres/PostgreSQL) are judged by the skill check.
        mentioned_skills = skill_terms(text, vocab) | skill_terms(source, vocab)
        added_nouns = {n for n in proper_nouns(text)
                       if n not in source_words and skill_key(n) not in mentioned_skills}
        if added_nouns:
            problems.append(f"adds name(s) not in your verified entry: {', '.join(sorted(added_nouns))}")
    return problems

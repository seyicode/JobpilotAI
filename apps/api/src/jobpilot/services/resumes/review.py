"""Rules for editing and approving tailored resumes.

Edits may reword, reorder, or remove bullets, choose entries and skills, and change the header
and summary. They may not change titles, organisations, or dates (copied from the library), add
bullets that do not come from a verified highlight, or add unverified skills. Wording that adds
numbers, skills, or names not in the source produces warnings the user must acknowledge.
"""

import uuid

from pydantic import ValidationError

from jobpilot.services.resumes.claims import (
    ClaimIssue,
    new_claims,
    numbers,
    skill_terms,
    vocabulary,
)
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


class EditRejected(ValueError):
    """The edit breaks a rule that cannot be acknowledged away. Safe to show users."""


def entry_label(entry: ResumeEntry) -> str:
    return f"{entry.title} at {entry.organization}" if entry.organization else entry.title


def apply_edit(
    submitted: ResumeContent,
    previous: ResumeContent,
    library: dict[uuid.UUID, dict],
    verified_skills: list[str],
    profile_summary: str | None,
) -> tuple[ResumeContent, list[ClaimIssue]]:
    """Validate a user's edit. Returns the cleaned content and warnings, or raises EditRejected.

    `library` maps ids to the user's currently verified entries."""
    vocab = vocabulary(verified_skills)
    issues: list[ClaimIssue] = []

    try:
        UserProfile(full_name=submitted.header.name, headline=submitted.header.headline,
                    email=submitted.header.email, phone=submitted.header.phone,
                    location=submitted.header.location, links=submitted.header.links)
    except ValidationError as error:
        field = error.errors()[0]["loc"][0]
        raise EditRejected(f"The header's {str(field).replace('_', ' ')} is not valid.") from None

    skills = _verified_skill_names(submitted.skills, verified_skills)

    summary = submitted.summary
    if summary and summary != profile_summary:
        added = sorted(numbers(summary) - numbers(profile_summary or ""))
        if added:
            issues.append(ClaimIssue("Summary", f"Adds number(s) not in your profile summary: {', '.join(added)}"))
        verified_keys = {skill_key(s) for s in verified_skills}
        unverified = sorted(skill_terms(summary, vocab) - verified_keys)
        if unverified:
            issues.append(ClaimIssue("Summary", f"Mentions skill(s) you have not verified: {', '.join(unverified)}"))

    previous_bullets = {(e.source_id, b.source_text): b for e, b in previous.bullets()}
    previous_entries = {e.source_id: e for s in previous.sections for e in s.entries}
    entries_by_kind: dict[str, list[ResumeEntry]] = {}
    seen: set[uuid.UUID] = set()
    for section in submitted.sections:
        for entry in section.entries:
            source = library.get(entry.source_id)
            if source is None:
                raise EditRejected(
                    f"“{entry_label(entry)}” is not a verified entry in your library. "
                    "Verify it there, or remove it from this resume."
                )
            if entry.source_id in seen:
                raise EditRejected(f"“{entry_label(entry)}” appears more than once.")
            seen.add(entry.source_id)
            cleaned = _locked_entry(source, entry, previous_entries.get(entry.source_id))
            for position, bullet in enumerate(entry.bullets, start=1):
                if bullet.source_text not in (source.get("highlights") or []):
                    raise EditRejected(
                        f"A bullet in “{entry_label(cleaned)}” does not come from that entry's "
                        "verified highlights. Add it to your library first."
                    )
                earlier = previous_bullets.get((entry.source_id, bullet.source_text))
                cleaned.bullets.append(_bullet(bullet, earlier))
                if bullet.text != bullet.source_text:
                    for problem in new_claims(bullet.text, bullet.source_text, vocab, check_nouns=True):
                        issues.append(ClaimIssue(f"{entry_label(cleaned)}, bullet {position}",
                                                 problem[0].upper() + problem[1:]))
            entries_by_kind.setdefault(cleaned.kind, []).append(cleaned)

    sections = [ResumeSection(kind=kind, heading=heading, entries=entries_by_kind[kind])
                for kind, heading in SECTION_ORDER if kind in entries_by_kind]
    content = ResumeContent(header=ResumeHeader(**submitted.header.model_dump()), summary=summary,
                            skills=skills, sections=sections)
    return content, issues


def library_conflicts(content: ResumeContent, library: dict[uuid.UUID, dict],
                      verified_skills: list[str]) -> list[str]:
    """Reasons the content no longer matches the verified library (checked before approval)."""
    problems = []
    verified_keys = {skill_key(s) for s in verified_skills}
    for name in content.skills:
        if skill_key(name) not in verified_keys:
            problems.append(f"The skill “{name}” is no longer verified.")
    for section in content.sections:
        for entry in section.entries:
            source = library.get(entry.source_id)
            if source is None:
                problems.append(f"“{entry_label(entry)}” is no longer a verified entry.")
                continue
            highlights = source.get("highlights") or []
            if any(b.source_text not in highlights for b in entry.bullets):
                problems.append(f"“{entry_label(entry)}” has changed in your library since this version was made.")
    return problems


def _verified_skill_names(requested: list[str], verified: list[str]) -> list[str]:
    by_key = {skill_key(name): name for name in verified}
    result, seen = [], set()
    for name in requested:
        key = skill_key(name)
        if key not in by_key:
            raise EditRejected(f"“{name}” is not a verified skill. Verify it in your library first.")
        if key not in seen:
            seen.add(key)
            result.append(by_key[key])
    return result


def _locked_entry(source: dict, submitted: ResumeEntry, earlier: ResumeEntry | None) -> ResumeEntry:
    """Facts come from the library, whatever was submitted."""
    return ResumeEntry(
        source_id=source["id"], kind=source["kind"], title=source["title"],
        organization=source.get("organization"), location=source.get("location"),
        start_date=source.get("start_date"), end_date=source.get("end_date"),
        is_current=bool(source.get("is_current")), bullets=[],
        reason=earlier.reason if earlier else "Added by you.",
    )


def _bullet(submitted: ResumeBullet, earlier: ResumeBullet | None) -> ResumeBullet:
    if submitted.text == submitted.source_text:
        changed_by = "none"
    elif earlier is not None and earlier.text == submitted.text:
        changed_by = earlier.changed_by  # Unchanged since the AI (or user) last wrote it
    else:
        changed_by = "user"
    reason = earlier.reason if earlier else "Added by you."
    return ResumeBullet(text=submitted.text, source_text=submitted.source_text,
                        changed_by=changed_by, reason=reason)

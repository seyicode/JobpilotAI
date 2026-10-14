import pytest

from jobpilot.services.library_import import (
    drafts_from_sections,
    normalize_date,
    parse_entry,
    split_entries,
    split_skills,
)


def test_drafts_from_sections_maps_kinds_and_skills():
    sections = [
        {"key": "header", "heading": "Header", "content": "Alex Example"},
        {
            "key": "experience",
            "heading": "Experience",
            "content": "Software Engineer at Example Corp | Jan 2021 - Present\n"
            "• Built a billing service in Python\n"
            "• Cut deploy time by 40%\n"
            "Intern, Sample Labs, 2019 – 2020\n"
            "- Wrote data pipelines",
        },
        {"key": "education", "heading": "Education", "content": "BSc Computer Science\nExample University\n2018"},
        {"key": "skills", "heading": "Skills", "content": "Languages: Python, Go; SQL\nDocker | python"},
    ]
    experiences, skills = drafts_from_sections(sections)
    assert [(e.kind, e.title, e.organization) for e in experiences] == [
        ("job", "Software Engineer", "Example Corp"),
        ("job", "Intern", "Sample Labs"),
        ("education", "BSc Computer Science", "Example University"),
    ]
    current, intern, degree = experiences
    assert (current.start_date, current.end_date, current.is_current) == ("2021-01", None, True)
    assert current.highlights == ["Built a billing service in Python", "Cut deploy time by 40%"]
    assert (intern.start_date, intern.end_date, intern.highlights) == (
        "2019", "2020", ["Wrote data pipelines"],
    )
    assert (degree.start_date, degree.end_date) == (None, "2018")
    assert skills == ["Python", "Go", "SQL", "Docker"]


def test_split_entries_uses_blank_lines_and_bullet_boundaries():
    content = "A\n- one\nB\n- two\n\nC\nD"
    assert split_entries(content) == [["A", "- one"], ["B", "- two"], ["C", "D"]]


def test_entry_without_bullets_keeps_extra_lines_as_highlights():
    draft = parse_entry("project", ["Budget app", "Personal project", "Tracks spending", "Uses React"])
    assert (draft.title, draft.organization) == ("Budget app", "Personal project")
    assert draft.highlights == ["Tracks spending", "Uses React"]


def test_entry_with_only_dates_is_skipped():
    assert parse_entry("job", ["2019 - 2020"]) is None


@pytest.mark.parametrize(
    ("value", "expected"),
    [("Mar 2021", "2021-03"), ("September 2020", "2020-09"), ("03/2021", "2021-03"),
     ("13/2021", "2021"), ("2021", "2021"), ("soon", None)],
)
def test_normalize_date(value, expected):
    assert normalize_date(value) == expected


def test_split_skills_ignores_long_phrases():
    assert split_skills("Python, an extremely long sentence that is not a skill at all") == ["Python"]

import uuid
from datetime import date

from jobpilot.services.extraction.schema import JobRequirements
from jobpilot.services.matching import VerifiedProfile, match_job
from jobpilot.services.preferences import JobPreferences
from jobpilot.services.resumes.assembly import assemble_resume, order_skills
from jobpilot.services.resumes.schema import UserProfile

REQUIREMENTS = JobRequirements(
    title="Backend Engineer", required_skills=["Python", "PostgreSQL"], preferred_skills=["Docker"],
)


def entry(kind, title, highlights=(), start=None, end=None, current=False, org="Example Corp"):
    return {"id": uuid.uuid4(), "kind": kind, "title": title, "organization": org, "location": None,
            "start_date": start, "end_date": end, "is_current": current, "highlights": list(highlights)}


CURRENT = entry("job", "Senior Engineer", [
    "Ran the team offsite",
    "Built payment APIs in Python",
    "Moved reporting to Postgres and Python services",
    "Containerised services with Docker",
], start="2022-01", current=True)
PREVIOUS = entry("job", "Engineer", ["Wrote Python ETL jobs"], start="2019", end="2021", org="Sample Labs")
OLDEST = entry("job", "Support Analyst", ["Answered tickets", "Wrote runbooks", "Trained staff"],
               start="2015", end="2018", org="Help Ltd")
OLDER_RELEVANT = entry("job", "Intern", ["Fixed SQL reports", "Tested Python scripts", "Filed bugs", "Docs"],
                       start="2013", end="2014", org="Intern Co")
PROJECTS = [entry("project", f"Project {i}", [f"Python tool number {i}"], start=f"202{i}", org=None)
            for i in range(5)] + [entry("project", "Knitting site", ["HTML and CSS"], org=None)]
EDUCATION = entry("education", "BSc Computer Science", start="2010", end="2013", org="Example University")
VOLUNTEERING = entry("volunteering", "Coach", ["Coached juniors"], org="Club")

ALL = [OLDEST, CURRENT, EDUCATION, VOLUNTEERING, PREVIOUS, OLDER_RELEVANT, *PROJECTS]
PROFILE = UserProfile(full_name="Alex Example", email="alex@example.com", summary="Backend engineer.")


def build(experiences=ALL, skills=("docker", "Go", "python", "Postgres", "Excel")):
    match = match_job(REQUIREMENTS, "", JobPreferences(),
                      VerifiedProfile(verified_skills=list(skills), verified_experiences=experiences),
                      today=date(2026, 10, 14))
    return assemble_resume(REQUIREMENTS, match, PROFILE, experiences, list(skills))


def section(resume, kind):
    return next(s for s in resume.sections if s.kind == kind)


def test_header_and_summary_come_from_profile_verbatim():
    resume = build()
    assert (resume.header.name, resume.header.email) == ("Alex Example", "alex@example.com")
    assert resume.summary == "Backend engineer."


def test_section_order_and_inclusion():
    resume = build()
    assert [s.heading for s in resume.sections] == ["Experience", "Projects", "Education"]
    jobs = section(resume, "job").entries
    assert [e.title for e in jobs] == ["Senior Engineer", "Engineer", "Support Analyst", "Intern"]
    assert all(s.kind != "volunteering" for s in resume.sections)  # not relevant to this job


def test_bullets_are_verbatim_ranked_and_explained():
    current = section(build(), "job").entries[0]
    assert [b.text for b in current.bullets] == [
        "Moved reporting to Postgres and Python services",  # two required skills
        "Built payment APIs in Python",
        "Containerised services with Docker",
        "Ran the team offsite",
    ]
    assert all(b.text == b.source_text and b.changed_by == "none" for b in current.bullets)
    assert current.bullets[0].reason == "Mentions Python, PostgreSQL (required)."
    assert current.bullets[2].reason == "Mentions Docker (preferred)."
    assert current.bullets[3].reason == "Kept for context."
    assert current.reason == "Relevant: mentions Python, PostgreSQL (required); Docker (preferred)."


def test_bullet_limits_for_older_jobs():
    jobs = {e.title: e for e in section(build(), "job").entries}
    assert len(jobs["Support Analyst"].bullets) == 2  # older and unrelated
    assert jobs["Support Analyst"].reason == "Included to keep your work history complete."
    intern = jobs["Intern"]
    assert len(intern.bullets) == 3
    # "SQL" is not a requirement here (PostgreSQL is); the rest keep their original order.
    assert [b.text for b in intern.bullets] == ["Tested Python scripts", "Fixed SQL reports", "Filed bugs"]


def test_projects_are_relevant_only_and_capped():
    projects = section(build(), "project").entries
    assert len(projects) == 3
    assert "Knitting site" not in [p.title for p in projects]
    assert [p.title for p in projects] == ["Project 4", "Project 3", "Project 2"]  # newest relevant first


def test_entries_copy_library_facts_and_ids():
    resume = build()
    current = section(resume, "job").entries[0]
    assert (current.source_id, current.organization, current.start_date, current.is_current) == (
        CURRENT["id"], "Example Corp", "2022-01", True)
    education = section(resume, "education").entries[0]
    assert education.reason == "Education entries are always included."


def test_skills_are_verified_only_and_ordered_by_relevance():
    resume = build()
    assert resume.skills == ["python", "Postgres", "docker", "Excel", "Go"]
    assert order_skills([], REQUIREMENTS) == []


def test_empty_library_gives_empty_resume():
    resume = build(experiences=[], skills=())
    assert resume.sections == [] and resume.skills == []

import pytest

from jobpilot.services.extraction.rules import extract_with_rules
from jobpilot.services.extraction.schema import JobRequirements, Salary
from jobpilot.services.skills import skill_key

POSTING = """Senior Backend Engineer at Example Corp
Location: London, UK
Hybrid, full-time. £80,000 - £95,000 per year.

About the role
You'll build Python services on Postgres and Docker.

Requirements:
- 5+ years of professional software experience
- Strong SQL and REST API design
- BSc in Computer Science or equivalent experience

Nice to have:
- Kubernetes
- Terraform
- Python packaging
"""


def test_extracts_core_fields():
    r = extract_with_rules(POSTING)
    assert (r.title, r.company) == ("Senior Backend Engineer", "Example Corp")
    assert r.seniority == "senior"
    assert r.location == "London, UK"
    assert (r.work_arrangement, r.employment_type) == ("hybrid", "full_time")
    assert r.salary == Salary(min=80000, max=95000, currency="GBP", period="year")
    assert r.years_experience_min == 5
    assert "BSc in Computer Science or equivalent experience" in r.qualifications


def test_required_vs_preferred_skills():
    r = extract_with_rules(POSTING)
    # Python appears in both contexts, so it stays required; aliases use canonical names.
    assert set(r.required_skills) == {"Python", "PostgreSQL", "Docker", "SQL", "REST"}
    assert set(r.preferred_skills) == {"Kubernetes", "Terraform"}


def test_hints_override_guesses_and_library_skills_extend_vocabulary():
    r = extract_with_rules(POSTING, title="Backend Engineer II", company="Acme",
                           extra_skills=["Billing Systems"])
    assert (r.title, r.company) == ("Backend Engineer II", "Acme")
    assert r.seniority == "senior"  # "II" is not a level word; the body's "Senior" is used
    assert extract_with_rules("Billing Systems experience needed.", extra_skills=["billing systems"]).required_skills == ["billing systems"]


def test_missing_details_stay_unknown():
    r = extract_with_rules("We are a friendly team building useful software for customers worldwide.")
    assert r == JobRequirements()


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Pay: $45/hr", Salary(min=45, max=45, currency="USD", period="hour")),
        ("€4.500 - €5.200 per month", Salary(min=4500, max=5200, currency="EUR", period="month")),
        ("Salary 120k-140k USD", Salary(min=120000, max=140000, currency="USD", period="year")),
        ("CAD 95,000 annually", Salary(min=95000, max=95000, currency="CAD", period="year")),
        ("5 years of Python experience", Salary()),
    ],
)
def test_salary_formats(text, expected):
    assert extract_with_rules(text).salary == expected


@pytest.mark.parametrize(
    ("text", "arrangement"),
    [
        ("This role is fully remote.", "remote"),
        ("This is not remote; you will be on-site in Leeds.", "onsite"),
        ("Hybrid: 2 days in the office, otherwise remote.", "hybrid"),
        ("Great culture.", None),
    ],
)
def test_work_arrangement(text, arrangement):
    assert extract_with_rules(text).work_arrangement == arrangement


@pytest.mark.parametrize(
    ("title", "seniority"),
    [("Staff Engineer", "lead"), ("Junior Developer", "entry"), ("Head of Data", "director"),
     ("Engineering Manager", "manager"), ("Product Manager", None), ("Summer Intern", "intern")],
)
def test_seniority_from_title(title, seniority):
    assert extract_with_rules("Details to follow.", title=title).seniority == seniority


def test_go_is_not_matched_as_an_ordinary_word():
    assert extract_with_rules("Go build great things with us.").required_skills == []
    assert extract_with_rules("Skills: Python, Go, Rust").required_skills == ["Python", "Rust", "Go"]


def test_short_aliases_need_exact_case():
    assert extract_with_rules("We use JS daily.").required_skills == ["JavaScript"]
    assert extract_with_rules("Our js team").required_skills == []


def test_schema_dedupes_and_removes_preferred_duplicates():
    r = JobRequirements(required_skills=["Postgres", "postgresql", " Python "],
                        preferred_skills=["python", "Go"], salary={"min": 10, "max": 5, "currency": "gbp"})
    assert r.required_skills == ["Postgres", "Python"]
    assert r.preferred_skills == ["Go"]
    assert (r.salary.min, r.salary.max, r.salary.currency) == (5, 10, "GBP")
    assert skill_key("K8s") == "kubernetes"


@pytest.mark.parametrize(
    ("text", "location"),
    [
        ("Location: Manchester, UK. Hybrid, full-time. £60,000 per year.", "Manchester, UK"),
        ("Location: St. Louis, MO | Remote friendly", "St. Louis, MO"),
        ("Based in: Berlin, Germany; salary on request", "Berlin, Germany"),
        ("Remote (EU time zones) role", "EU time zones"),
    ],
)
def test_location_stops_at_other_details(text, location):
    assert extract_with_rules(text).location == location

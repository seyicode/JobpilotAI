import pytest
from pydantic import ValidationError

from jobpilot.services.preferences import (
    JobFacts,
    JobPreferences,
    check_hard_filters,
    passes_hard_filters,
)

JOB = JobFacts(
    title="Senior Backend Engineer",
    company="Example Corp",
    location="London, UK",
    description="Python services. Some on-call rotation.",
    work_arrangement="hybrid",
    employment_type="full_time",
    seniority="senior",
    salary_max=90_000,
    salary_currency="GBP",
    salary_period="year",
)


def statuses(preferences: JobPreferences, job: JobFacts = JOB) -> dict[str, str]:
    return {r.filter: r.status for r in check_hard_filters(preferences, job)}


def test_defaults_are_permissive():
    preferences = JobPreferences()
    assert preferences.hard_filters == ["work_arrangement"]
    assert check_hard_filters(preferences, JOB) == []


def test_terms_are_cleaned_and_deduped():
    preferences = JobPreferences(
        target_titles=["  Backend   Engineer ", "backend engineer", ""],
        work_arrangements=["remote", "remote"],
        salary_currency=" gbp ",
    )
    assert preferences.target_titles == ["Backend Engineer"]
    assert preferences.work_arrangements == ["remote"]
    assert preferences.salary_currency == "GBP"


@pytest.mark.parametrize(
    "data",
    [
        {"work_arrangements": ["moon"]},
        {"salary_currency": "pounds"},
        {"min_salary": -1},
        {"hard_filters": ["vibes"]},
        {"include_keywords": ["Python"], "exclude_keywords": ["python"]},
        {"target_titles": ["x" * 101]},
    ],
)
def test_invalid_preferences(data):
    with pytest.raises(ValidationError):
        JobPreferences(**data)


def test_exclusions_always_apply():
    preferences = JobPreferences(
        excluded_companies=["example corp"], exclude_keywords=["on-call"], hard_filters=[]
    )
    results = check_hard_filters(preferences, JOB)
    assert [(r.filter, r.status) for r in results] == [
        ("excluded_companies", "fail"),
        ("exclude_keywords", "fail"),
    ]
    assert results[1].reason == "Mentions excluded keywords: on-call."
    assert not passes_hard_filters(results)


def test_keywords_match_whole_words_only():
    preferences = JobPreferences(exclude_keywords=["Java"], hard_filters=[])
    assert statuses(preferences, JobFacts(title="JavaScript Engineer")) == {"exclude_keywords": "pass"}
    assert statuses(preferences, JobFacts(title="Java Engineer")) == {"exclude_keywords": "fail"}


def test_work_arrangement_and_employment_type():
    preferences = JobPreferences(
        work_arrangements=["remote"], employment_types=["contract"],
        hard_filters=["work_arrangement", "employment_type"],
    )
    assert statuses(preferences) == {"work_arrangement": "fail", "employment_type": "fail"}
    unknown = JobFacts(title="Engineer")
    assert statuses(preferences, unknown) == {"work_arrangement": "unknown", "employment_type": "unknown"}
    assert passes_hard_filters(check_hard_filters(preferences, unknown))


def test_location_rules():
    preferences = JobPreferences(locations=["Manchester"], hard_filters=["location"])
    assert statuses(preferences) == {"location": "fail"}
    assert statuses(preferences.model_copy(update={"willing_to_relocate": True})) == {"location": "pass"}
    remote = JobFacts(title="Engineer", location="Berlin", work_arrangement="remote")
    assert statuses(preferences, remote) == {"location": "pass"}
    assert statuses(JobPreferences(locations=["london"], hard_filters=["location"])) == {"location": "pass"}


def test_salary_is_compared_annually_in_the_same_currency():
    hourly = JobPreferences(min_salary=50, salary_currency="GBP", salary_period="hour", hard_filters=["min_salary"])
    result = check_hard_filters(hourly, JOB)[0]
    assert result.status == "fail"  # 90,000 < 50 x 2080 = 104,000
    assert "90,000 vs 104,000 GBP" in result.reason

    monthly = hourly.model_copy(update={"min_salary": 7000, "salary_period": "month"})
    assert statuses(monthly) == {"min_salary": "pass"}  # 90,000 >= 84,000

    usd = hourly.model_copy(update={"salary_currency": "USD"})
    assert statuses(usd) == {"min_salary": "unknown"}
    assert statuses(hourly, JobFacts(title="Engineer")) == {"min_salary": "unknown"}


def test_seniority():
    preferences = JobPreferences(seniority_levels=["mid", "senior"], hard_filters=["seniority"])
    assert statuses(preferences) == {"seniority": "pass"}
    assert statuses(preferences, JobFacts(title="Intern", seniority="intern")) == {"seniority": "fail"}


def test_unused_hard_filters_are_skipped():
    preferences = JobPreferences(hard_filters=["location", "min_salary", "seniority"])
    assert check_hard_filters(preferences, JOB) == []


# API


def test_get_returns_defaults_before_saving(db_client):
    body = db_client.get("/preferences").json()
    assert body["updated_at"] is None
    assert body["hard_filters"] == ["work_arrangement"]
    assert body["work_arrangements"] == []


def test_put_replaces_preferences(db_client):
    saved = db_client.put(
        "/preferences",
        json={"target_titles": ["Backend Engineer"], "work_arrangements": ["remote"], "min_salary": 80000},
    )
    assert saved.status_code == 200
    assert saved.json()["updated_at"] is not None

    replaced = db_client.put("/preferences", json={"locations": ["London"]}).json()
    assert replaced["locations"] == ["London"]
    assert replaced["target_titles"] == [] and replaced["min_salary"] is None
    assert db_client.get("/preferences").json() == replaced


def test_put_rejects_invalid_preferences(db_client):
    response = db_client.put("/preferences", json={"work_arrangements": ["moon"]})
    assert response.status_code == 422
    assert db_client.get("/preferences").json()["updated_at"] is None

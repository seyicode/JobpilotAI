from datetime import date

import pytest

from jobpilot.services.extraction.schema import JobRequirements
from jobpilot.services.matching import VerifiedProfile, match_job, validate_weights, verified_years
from jobpilot.services.preferences import JobPreferences

TODAY = date(2026, 10, 14)
DESCRIPTION = "Senior Backend Engineer. Python, PostgreSQL, Kubernetes. Fintech payments."
REQUIREMENTS = JobRequirements(
    title="Senior Backend Engineer", company="Example Corp",
    required_skills=["Python", "PostgreSQL", "Kubernetes"], preferred_skills=["Terraform"],
    seniority="senior", location="London", work_arrangement="hybrid", employment_type="full_time",
    salary={"min": 80000, "max": 95000, "currency": "GBP", "period": "year"},
    years_experience_min=5,
)
JOB = {"kind": "job", "title": "Software Engineer", "organization": "Example Corp",
       "start_date": "2019-01", "end_date": None, "is_current": True,
       "highlights": ["Built payment APIs in Python on Postgres"]}
PROFILE = VerifiedProfile(
    verified_skills=["python"],
    verified_experiences=[JOB],
    draft_skills=["Kubernetes"],
    draft_experiences=[{"kind": "project", "title": "Infra as code", "organization": None,
                        "highlights": ["Terraform modules"]}],
)
PREFS = JobPreferences(
    target_titles=["Backend Engineer"], seniority_levels=["senior"], work_arrangements=["hybrid", "remote"],
    include_keywords=["fintech", "crypto"], min_salary=70000, salary_currency="GBP",
    hard_filters=["work_arrangement"],
)


def components(result):
    return {c.key: c for c in result.components}


def test_full_match_breakdown():
    result = match_job(REQUIREMENTS, DESCRIPTION, PREFS, PROFILE, today=TODAY)
    c = components(result)
    assert result.eligible
    assert (c["required_skills"].value, c["required_skills"].detail) == (
        2 / 3, "2 of 3 backed by your verified library.")
    assert c["preferred_skills"].value == 0
    assert c["experience_years"].value == 1.0  # Jan 2019 to Oct 2026 is 7.8 years, capped at 5+
    assert c["experience_years"].detail.startswith("About 7.8 verified years")
    assert c["seniority"].value == 1.0
    assert c["title"].value == 1.0
    assert c["keywords"].value == 0.5
    assert c["preferences"].value == 1.0  # salary met; location/employment not set
    assert result.coverage == 100
    # 35*2/3 + 0 + 15 + 10 + 10 + 5 + 10 = 73.33 of 100
    assert result.score == 73
    assert result.summary.startswith("73% match, based on 100% of the scoring factors.")


def test_evidence_uses_only_verified_items_and_quotes_them():
    result = match_job(REQUIREMENTS, DESCRIPTION, PREFS, PROFILE, today=TODAY)
    python = [e for e in result.evidence if e.requirement == "Python"]
    assert [(e.source, e.source_label) for e in python] == [
        ("skill", "Verified skill: python"), ("experience", "Software Engineer at Example Corp")]
    assert python[1].quote == "Built payment APIs in Python on Postgres"
    postgres = [e for e in result.evidence if e.requirement == "PostgreSQL"]
    assert [e.source for e in postgres] == ["experience"]  # matched through the "postgres" alias


def test_gaps_point_to_drafts_without_counting_them():
    result = match_job(REQUIREMENTS, DESCRIPTION, PREFS, PROFILE, today=TODAY)
    gaps = {g.requirement: g for g in result.gaps}
    assert gaps["Kubernetes"].hint == "“Kubernetes” is a draft skill in your library. Verify it if it's accurate."
    assert gaps["Terraform"].hint == "Mentioned in a draft entry (Infra as code). Verify it to count."
    assert not any(e.requirement in ("Kubernetes", "Terraform") for e in result.evidence)


def test_unknown_details_are_excluded_not_penalised():
    sparse = JobRequirements(title="Engineer", required_skills=["Python"])
    result = match_job(sparse, "Engineer. Python.", JobPreferences(), PROFILE, today=TODAY)
    c = components(result)
    for key in ("preferred_skills", "experience_years", "seniority", "title", "keywords", "preferences"):
        assert c[key].status == "unknown" and c[key].points is None
    assert result.score == 100  # the only known factor is fully met
    assert result.coverage == 35
    assert result.eligible


def test_nothing_known_gives_no_score():
    result = match_job(JobRequirements(), "Text.", JobPreferences(), VerifiedProfile(), today=TODAY)
    assert (result.score, result.coverage) == (None, 0)
    assert result.summary == "Not enough information to score this job."


def test_must_match_failure_marks_ineligible_but_still_explains():
    prefs = PREFS.model_copy(update={"work_arrangements": ["remote"]})
    result = match_job(REQUIREMENTS, DESCRIPTION, prefs, PROFILE, today=TODAY)
    assert not result.eligible
    assert result.summary == "Filtered out by your must-match preferences. Job is hybrid; you want remote."
    assert result.score is not None


def test_soft_preferences_affect_score_only():
    prefs = PREFS.model_copy(update={"min_salary": 120000})
    result = match_job(REQUIREMENTS, DESCRIPTION, prefs, PROFILE, today=TODAY)
    assert result.eligible
    assert components(result)["preferences"].value == 0
    assert [c.filter for c in result.preference_checks] == ["min_salary"]


def test_seniority_one_step_away_scores_half():
    prefs = PREFS.model_copy(update={"seniority_levels": ["mid"]})
    assert components(match_job(REQUIREMENTS, DESCRIPTION, prefs, PROFILE, today=TODAY))["seniority"].value == 0.5


def test_title_partial_match():
    prefs = PREFS.model_copy(update={"target_titles": ["Platform Engineer"]})
    c = components(match_job(REQUIREMENTS, DESCRIPTION, prefs, PROFILE, today=TODAY))["title"]
    assert c.value == 0.5 and c.detail == "Partly matches your target “Platform Engineer”."


def test_experience_years_counts_overlaps_once_and_flags_undated_entries():
    jobs = [
        {"kind": "job", "start_date": "2018", "end_date": "2020", "is_current": False},
        {"kind": "job", "start_date": "2020-01", "end_date": "2020-12", "is_current": False},
        {"kind": "job", "start_date": "2024-01", "end_date": None, "is_current": True},
    ]
    assert verified_years(jobs, TODAY) == 5.8  # 2018-2020 (3y) + Jan 2024-Oct 2026 (34 months)
    undated = VerifiedProfile(verified_experiences=[{"kind": "job", "title": "Dev", "highlights": []}])
    result = match_job(REQUIREMENTS, DESCRIPTION, PREFS, undated, today=TODAY)
    gap = next(g for g in result.gaps if g.kind == "experience")
    assert (gap.requirement, gap.hint) == ("5+ years of experience", "1 verified work entry has no dates.")
    assert components(result)["experience_years"].value == 0


def test_custom_weights():
    result = match_job(REQUIREMENTS, DESCRIPTION, PREFS, PROFILE, today=TODAY,
                       weights={"keywords": 0, "preferred_skills": 0})
    assert components(result)["keywords"].weight == 0
    assert result.score == round((35 * 2 / 3 + 15 + 10 + 10 + 10) / 80 * 100)
    with pytest.raises(ValueError, match="Unknown match weight"):
        validate_weights({"vibes": 1})
    with pytest.raises(ValueError, match="negative"):
        validate_weights({"title": -1})


# API


def test_match_endpoint_and_list_scores(db_client):
    db_client.put("/preferences", json={"work_arrangements": ["remote"], "target_titles": ["Backend Engineer"]})
    db_client.post("/skills", json={"name": "Python", "verified": True})
    db_client.post("/skills", json={"name": "PostgreSQL", "verified": False})
    posting = ("Backend Engineer at Example Corp\nRemote. Requirements: Python and PostgreSQL. "
               "We build reliable services for customers.")
    job = db_client.post("/jobs", json={"description": posting}).json()["job"]

    match = db_client.get(f"/jobs/{job['id']}/match").json()
    assert match["eligible"] is True
    assert [e["requirement"] for e in match["evidence"]] == ["Python"]
    assert match["gaps"][0]["requirement"] == "PostgreSQL"
    assert "draft skill" in match["gaps"][0]["hint"]
    assert {f["filter"]: f["status"] for f in match["filters"]} == {"work_arrangement": "pass"}

    listed = db_client.get("/jobs").json()[0]
    assert (listed["match_score"], listed["eligible"]) == (match["score"], True)
    assert db_client.get("/jobs/00000000-0000-0000-0000-000000000000/match").status_code == 404


def test_match_reflects_corrections_and_filters(db_client):
    db_client.put("/preferences", json={"work_arrangements": ["remote"]})
    posting = "Data Engineer at Example Corp. Requirements: SQL and Airflow. Location: Leeds."
    job = db_client.post("/jobs", json={"description": posting}).json()["job"]
    assert db_client.get(f"/jobs/{job['id']}/match").json()["filters"][0]["status"] == "unknown"

    corrected = job["requirements"] | {"work_arrangement": "onsite"}
    db_client.put(f"/jobs/{job['id']}/requirements", json=corrected)
    match = db_client.get(f"/jobs/{job['id']}/match").json()
    assert match["eligible"] is False
    assert match["summary"].startswith("Filtered out")

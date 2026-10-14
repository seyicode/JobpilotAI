import pytest

from jobpilot.services.applications import STATUSES
from jobpilot.services.extraction.schema import JobRequirements
from jobpilot.services.jobs import NewJob, ingest_job, merge_structured

DESCRIPTION = """Backend Engineer at Example Corp
Location: Leeds. On-site, part-time. Requirements: Python and PostgreSQL.
We build payment systems for merchants across the UK."""


def test_statuses_cover_the_full_pipeline():
    assert STATUSES == ("discovered", "shortlisted", "ready_to_apply", "applied", "interviewing",
                        "offered", "rejected", "archived")


def test_pasted_jobs_start_shortlisted_and_unseen(db_client):
    job = db_client.post("/jobs", json={"description": DESCRIPTION}).json()["job"]
    assert (job["application_status"], job["status_changed_at"], job["seen_at"]) == ("shortlisted", None, None)
    assert db_client.get("/jobs").json()[0]["application_status"] == "shortlisted"


def test_status_changes_are_recorded(db_client):
    job = db_client.post("/jobs", json={"description": DESCRIPTION}).json()["job"]
    url = f"/jobs/{job['id']}/application"
    updated = db_client.patch(url, json={"status": "applied", "status_note": "Applied on their site"}).json()
    assert updated["application_status"] == "applied" and updated["status_changed_at"]
    db_client.patch(url, json={"status": "applied"})  # unchanged: no new event
    db_client.patch(url, json={"status": "interviewing"})
    history = db_client.get(f"/jobs/{job['id']}/application/history").json()
    assert [(h["from_status"], h["to_status"], h["note"]) for h in history] == [
        ("shortlisted", "applied", "Applied on their site"), ("applied", "interviewing", None)]


def test_notes_and_seen(db_client):
    job = db_client.post("/jobs", json={"description": DESCRIPTION}).json()["job"]
    url = f"/jobs/{job['id']}/application"
    body = db_client.patch(url, json={"notes": "  Recruiter: Sam  ", "seen": True}).json()
    assert body["notes"] == "Recruiter: Sam" and body["seen_at"]
    assert body["application_status"] == "shortlisted"
    body = db_client.patch(url, json={"notes": "", "seen": False}).json()
    assert body["notes"] is None and body["seen_at"] is None


def test_invalid_updates(db_client):
    job = db_client.post("/jobs", json={"description": DESCRIPTION}).json()["job"]
    assert db_client.patch(f"/jobs/{job['id']}/application", json={"status": "auto_applied"}).status_code == 422
    assert db_client.patch("/jobs/00000000-0000-0000-0000-000000000000/application", json={}).status_code == 404


def test_ingest_job_is_shared_and_idempotent(session_factory):
    with session_factory() as session:
        new = NewJob(description=DESCRIPTION, url="https://example.com/jobs/1", application_status="discovered",
                     structured={"work_arrangement": "remote", "employment_type": "full_time",
                                 "salary": {"min": 50000, "max": 60000, "currency": "GBP", "period": "year"}})
        job, duplicate = ingest_job(session, new, ai=None)
        again, duplicate_again = ingest_job(session, new, ai=None)
        session.commit()
        assert (duplicate, duplicate_again, again.id) == (False, True, job.id)
        assert job.application_status == "discovered"
        requirements = job.requirements
        # Structured feed data overrides text extraction ("On-site, part-time" in the text).
        assert (requirements["work_arrangement"], requirements["employment_type"]) == ("remote", "full_time")
        assert requirements["salary"]["max"] == 60000
        assert requirements["location"] == "Leeds"  # not in structured data, so extraction is kept
        assert job.extraction_note.endswith("from the job feed were used where given.")


@pytest.mark.parametrize(
    ("structured", "expected_location"),
    [({"location": None}, "Leeds"), ({"location": "Remote, UK"}, "Remote, UK"), ({"seniority": "wizard"}, "Leeds")],
)
def test_merge_structured_ignores_blanks_and_invalid_data(structured, expected_location):
    merged = merge_structured(JobRequirements(location="Leeds"), structured)
    assert merged.location == expected_location
    assert merged.seniority is None

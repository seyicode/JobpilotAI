import csv
import io
from datetime import UTC, datetime, timedelta

import pytest

from jobpilot.db.models import Job
from jobpilot.services.tracker import TrackerFilters, csv_cell, decode_cursor, encode_cursor


def post(client, title, company, extra="", **fields):
    description = f"{title} at {company}\nRequirements: Python. {extra} We build useful software for customers."
    job = client.post("/jobs", json={"description": description, **fields}).json()["job"]
    return job["id"]


@pytest.fixture
def tracker(db_client, session_factory):
    client = db_client
    client.put("/preferences", json={"target_titles": ["Backend Engineer"]})
    client.post("/skills", json={"name": "Python", "verified": True})
    ids = {
        "backend": post(client, "Backend Engineer", "Acme", "Salary £90,000 per year. Remote."),
        "frontend": post(client, "Frontend Developer", "Globex", "Pay $60/hr."),
        "data": post(client, "Data Analyst", "Initech"),
        "archived": post(client, "Backend Engineer II", "Umbrella"),
    }
    client.patch(f"/jobs/{ids['frontend']}/application", json={"status": "applied"})
    client.patch(f"/jobs/{ids['archived']}/application", json={"status": "archived"})
    with session_factory() as session:  # Make two of them look discovered, one a week ago.
        for key, days in (("data", 0), ("backend", 7)):
            job = session.get(Job, ids[key])
            job.application_status = "discovered"
            job.first_seen_at = datetime.now(UTC) - timedelta(days=days)
        session.commit()
    return client, ids


def titles(response):
    return [item["title"] for item in response.json()["items"]]


def test_default_view_hides_archived_and_sorts_by_score(tracker):
    client, _ = tracker
    body = client.get("/applications").json()
    assert body["total"] == 3 and body["next_cursor"] is None
    assert body["items"][0]["title"] == "Backend Engineer"  # target title and Python both match
    first = body["items"][0]
    assert (first["salary_max"], first["salary_currency"], first["work_arrangement"]) == (90000, "GBP", "remote")
    assert first["is_new"] is True and first["resume_status"] == "none"


@pytest.mark.parametrize(("query", "expected"), [
    ("view=new", {"Backend Engineer", "Data Analyst"}),
    ("view=in_progress", {"Frontend Developer"}),
    ("view=archived", {"Backend Engineer II"}),
    ("status=applied&status=discovered", {"Backend Engineer", "Data Analyst", "Frontend Developer"}),
    ("company=glob", {"Frontend Developer"}),
    ("q=analyst", {"Data Analyst"}),
    ("min_score=90", {"Backend Engineer"}),
])
def test_filters(tracker, query, expected):
    client, _ = tracker
    assert set(titles(client.get(f"/applications?{query}"))) == expected


def test_date_filter_uses_when_the_job_was_found(tracker):
    client, _ = tracker
    today = datetime.now(UTC).date()
    found = set(titles(client.get(f"/applications?found_from={today - timedelta(days=1)}")))
    assert found == {"Data Analyst", "Frontend Developer"}


def test_salary_filter_compares_annual_amounts_and_unknowns(tracker):
    client, _ = tracker
    # $60/hr is $124,800 a year; £90,000 is in another currency than USD.
    assert set(titles(client.get("/applications?min_salary=100000&salary_currency=USD"))) == {
        "Frontend Developer", "Backend Engineer", "Data Analyst"}  # unknown/other currency included
    strict = "/applications?min_salary=100000&salary_currency=USD&include_unknown_salary=false"
    assert titles(client.get(strict)) == ["Frontend Developer"]
    assert titles(client.get("/applications?min_salary=95000&salary_currency=GBP&include_unknown_salary=false")) == []


def test_sorting_puts_missing_values_last(tracker):
    client, _ = tracker
    assert titles(client.get("/applications?sort=salary&order=desc"))[:2] == ["Frontend Developer", "Backend Engineer"]
    assert titles(client.get("/applications?sort=salary&order=asc"))[:2] == ["Backend Engineer", "Frontend Developer"]
    assert titles(client.get("/applications?sort=company&order=asc")) == [
        "Backend Engineer", "Frontend Developer", "Data Analyst"]


def test_cursor_pagination(tracker):
    client, _ = tracker
    first = client.get("/applications?limit=2&sort=company&order=asc").json()
    assert len(first["items"]) == 2 and first["total"] == 3
    second = client.get(f"/applications?limit=2&sort=company&order=asc&cursor={first['next_cursor']}").json()
    assert [i["title"] for i in second["items"]] == ["Data Analyst"] and second["next_cursor"] is None
    mismatched = client.get(f"/applications?limit=2&sort=score&cursor={first['next_cursor']}")
    assert mismatched.status_code == 422
    assert client.get("/applications?cursor=garbage").status_code == 422


def test_summary_counts(tracker):
    client, ids = tracker
    summary = client.get("/applications/summary").json()
    assert summary["new"] == 2
    assert summary["by_status"]["discovered"] == 2 and summary["by_status"]["archived"] == 1
    client.patch(f"/jobs/{ids['data']}/application", json={"seen": True})
    assert client.get("/applications/summary").json()["new"] == 1


def test_resume_status_is_reported(tracker):
    client, ids = tracker
    client.post("/experiences", json={"kind": "job", "title": "Engineer", "highlights": ["Python APIs"],
                                      "verified": True})
    version = client.post(f"/jobs/{ids['backend']}/resumes").json()
    rows = {i["id"]: i for i in client.get("/applications").json()["items"]}
    assert rows[ids["backend"]]["resume_status"] == "draft"
    client.post(f"/tailored-resumes/{version['id']}/approve")
    rows = {i["id"]: i for i in client.get("/applications").json()["items"]}
    assert rows[ids["backend"]]["resume_status"] == "approved"


def test_csv_export(tracker, session_factory):
    client, ids = tracker
    with session_factory() as session:
        job = session.get(Job, ids["data"])
        job.title, job.notes = "=HYPERLINK(\"https://evil.example\")", "private note"
        session.commit()
    response = client.get("/applications/export.csv?sort=company&order=asc")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert response.headers["cache-control"] == "no-store, private"
    assert response.headers["content-disposition"].startswith('attachment; filename="jobpilot-applications-')
    rows = list(csv.reader(io.StringIO(response.text.lstrip("﻿"))))
    assert rows[0][:4] == ["Title", "Company", "Status", "Match score"]
    assert len(rows) == 4
    assert "'=HYPERLINK(\"https://evil.example\")" in [r[0] for r in rows]
    assert "private note" not in response.text


@pytest.mark.parametrize(("value", "expected"), [
    ("=1+1", "'=1+1"), ("+x", "'+x"), ("-x", "'-x"), ("@x", "'@x"), ("ok", "ok"), (None, ""), (True, "yes"), (85, "85"),
])
def test_csv_cells(value, expected):
    assert csv_cell(value) == expected


def test_cursor_round_trip():
    filters = TrackerFilters(view="new")
    assert decode_cursor(encode_cursor(50, filters), filters) == 50
    with pytest.raises(ValueError):
        decode_cursor(encode_cursor(50, filters), TrackerFilters(view="saved"))


def test_like_wildcards_are_escaped(tracker):
    client, _ = tracker
    assert titles(client.get("/applications?company=%25")) == []
    assert titles(client.get("/applications?q=_")) == []


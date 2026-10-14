import uuid

JOB = {
    "kind": "job",
    "title": "  Software   Engineer ",
    "organization": "Example Corp",
    "start_date": "2021-01",
    "is_current": True,
    "highlights": ["Built a billing service", "  "],
}

RESUME_TEXT = b"""Alex Example

Experience
Software Engineer at Example Corp | Jan 2021 - Present
- Built a billing service in Python

Skills
Python, PostgreSQL
"""


def create_job(client, **overrides):
    response = client.post("/experiences", json=JOB | overrides)
    assert response.status_code == 201, response.text
    return response.json()


def test_create_experience_defaults_to_unverified_and_cleans_text(db_client):
    body = create_job(db_client)
    assert body["verified"] is False
    assert body["title"] == "Software Engineer"
    assert body["highlights"] == ["Built a billing service"]
    assert body["location"] is None


def test_experience_date_rules(db_client):
    bad = [
        {"start_date": "2021-13"},
        {"is_current": True, "end_date": "2022"},
        {"is_current": False, "start_date": "2022-05", "end_date": "2021"},
        {"kind": "hobby"},
        {"title": ""},
    ]
    for overrides in bad:
        assert db_client.post("/experiences", json=JOB | overrides).status_code == 422
    same_year = create_job(db_client, is_current=False, start_date="2021-05", end_date="2021")
    assert same_year["end_date"] == "2021"


def test_verify_then_edit_content_unverifies(db_client):
    item = create_job(db_client)
    url = f"/experiences/{item['id']}"
    assert db_client.patch(url, json={"verified": True}).json()["verified"] is True

    unchanged = db_client.patch(url, json={"title": "Software Engineer"}).json()
    assert unchanged["verified"] is True

    edited = db_client.patch(url, json={"highlights": ["Built a billing service in Python"]}).json()
    assert edited["verified"] is False

    reverified = db_client.patch(url, json={"title": "Senior Engineer", "verified": True}).json()
    assert (reverified["title"], reverified["verified"]) == ("Senior Engineer", True)


def test_patch_validates_merged_state(db_client):
    item = create_job(db_client)
    url = f"/experiences/{item['id']}"
    response = db_client.patch(url, json={"end_date": "2023"})
    assert response.status_code == 422
    assert response.json() == {"detail": "A current entry cannot have an end date."}
    assert db_client.patch(url, json={"title": None}).status_code == 422
    assert db_client.patch(url, json={"is_current": False, "end_date": "2023"}).status_code == 200


def test_list_filter_and_delete(db_client):
    first = create_job(db_client)
    create_job(db_client, title="Other", verified=True)
    assert [e["title"] for e in db_client.get("/experiences?verified=true").json()] == ["Other"]
    assert len(db_client.get("/experiences").json()) == 2
    assert db_client.delete(f"/experiences/{first['id']}").status_code == 204
    assert db_client.delete(f"/experiences/{first['id']}").status_code == 404
    assert db_client.patch(f"/experiences/{uuid.uuid4()}", json={}).status_code == 404


def test_skills_are_unique_case_insensitively(db_client):
    python = db_client.post("/skills", json={"name": " Python "}).json()
    assert (python["name"], python["verified"]) == ("Python", False)
    duplicate = db_client.post("/skills", json={"name": "python"})
    assert duplicate.status_code == 409
    go = db_client.post("/skills", json={"name": "Go"}).json()
    assert db_client.patch(f"/skills/{go['id']}", json={"name": "PYTHON"}).status_code == 409
    assert [s["name"] for s in db_client.get("/skills").json()] == ["Go", "Python"]


def test_skill_rename_unverifies_but_case_fix_keeps_uniqueness(db_client):
    skill = db_client.post("/skills", json={"name": "postgres", "verified": True}).json()
    url = f"/skills/{skill['id']}"
    renamed = db_client.patch(url, json={"name": "Postgres"}).json()
    assert (renamed["name"], renamed["verified"]) == ("Postgres", False)
    assert db_client.patch(url, json={"verified": True}).json()["verified"] is True
    assert db_client.patch(url, json={"name": " "}).status_code == 422
    assert db_client.delete(url).status_code == 204


def test_import_creates_unverified_drafts_once(db_client):
    resume = db_client.post(
        "/resumes", files={"file": ("cv.txt", RESUME_TEXT, "text/plain")}
    ).json()
    result = db_client.post(f"/resumes/{resume['id']}/import").json()
    assert result == {"experiences_created": 1, "skills_created": 2, "skipped": 0}

    experiences = db_client.get("/experiences").json()
    assert len(experiences) == 1
    job = experiences[0]
    assert (job["title"], job["organization"], job["start_date"], job["is_current"]) == (
        "Software Engineer", "Example Corp", "2021-01", True,
    )
    assert job["verified"] is False and job["source_resume_id"] == resume["id"]
    assert all(not s["verified"] for s in db_client.get("/skills").json())

    again = db_client.post(f"/resumes/{resume['id']}/import").json()
    assert again == {"experiences_created": 0, "skills_created": 0, "skipped": 3}


def test_deleting_resume_keeps_library_entries(db_client):
    resume = db_client.post(
        "/resumes", files={"file": ("cv.txt", RESUME_TEXT, "text/plain")}
    ).json()
    db_client.post(f"/resumes/{resume['id']}/import")
    db_client.delete(f"/resumes/{resume['id']}")
    experiences = db_client.get("/experiences").json()
    assert len(experiences) == 1 and experiences[0]["source_resume_id"] is None


def test_import_unknown_resume(db_client):
    assert db_client.post(f"/resumes/{uuid.uuid4()}/import").status_code == 404

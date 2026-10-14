"""Tailored resume versions: generate, edit rules, approval, history."""

import pytest

POSTING = """Backend Engineer at Acme
Requirements: Python and PostgreSQL. Nice to have: Docker.
We build payment systems for merchants across the UK and Europe."""

HIGHLIGHTS = ["Built payment APIs in Python on Postgres", "Ran the team offsite", "Containerised services with Docker"]


@pytest.fixture
def setup(db_client):
    """A verified job entry, a draft entry, verified skills, a profile, and one job."""
    client = db_client
    client.put("/profile", json={"full_name": "Alex Example", "email": "alex@example.com",
                                 "summary": "Backend engineer with 6 years in payments."})
    job_entry = client.post("/experiences", json={
        "kind": "job", "title": "Software Engineer", "organization": "Example Corp",
        "start_date": "2020-01", "is_current": True, "highlights": HIGHLIGHTS, "verified": True,
    }).json()
    draft_entry = client.post("/experiences", json={
        "kind": "job", "title": "Unverified Role", "organization": "Draft Ltd", "highlights": ["Python work"],
    }).json()
    for name, verified in (("Python", True), ("PostgreSQL", True), ("Kubernetes", False)):
        client.post("/skills", json={"name": name, "verified": verified})
    job = client.post("/jobs", json={"description": POSTING}).json()["job"]
    return client, job, job_entry, draft_entry


def generate(client, job):
    response = client.post(f"/jobs/{job['id']}/resumes")
    assert response.status_code == 201, response.text
    return response.json()


def test_generate_uses_only_verified_items(setup):
    client, job, job_entry, _ = setup
    version = generate(client, job)
    assert (version["version"], version["status"], version["generation_method"], version["edited"]) == (
        1, "draft", "deterministic", False)
    content = version["content"]
    assert content["header"]["name"] == "Alex Example"
    assert content["summary"] == "Backend engineer with 6 years in payments."
    assert content["skills"] == ["Python", "PostgreSQL"]
    [section] = content["sections"]
    [entry] = section["entries"]
    assert entry["source_id"] == job_entry["id"]
    assert [b["text"] for b in entry["bullets"]] == [HIGHLIGHTS[0], HIGHLIGHTS[2], HIGHLIGHTS[1]]
    assert "Unverified Role" not in str(content)


def test_versions_are_numbered_per_job(setup):
    client, job, *_ = setup
    generate(client, job)
    generate(client, job)
    versions = client.get(f"/jobs/{job['id']}/resumes").json()
    assert [v["version"] for v in versions] == [2, 1]
    assert client.get("/jobs/00000000-0000-0000-0000-000000000000/resumes").status_code == 404


def edit(client, version, mutate):
    content = version["content"]
    mutate(content)
    return client.put(f"/tailored-resumes/{version['id']}", json=content)


def test_rewording_is_tracked_and_facts_stay_locked(setup):
    client, job, *_ = setup
    version = generate(client, job)

    def mutate(content):
        entry = content["sections"][0]["entries"][0]
        entry["title"] = "Chief Technology Officer"  # ignored: facts come from the library
        entry["start_date"] = "2010-01"
        entry["bullets"] = [{**entry["bullets"][0], "text": "Designed Python payment APIs on PostgreSQL"}]

    response = edit(client, version, mutate)
    assert response.status_code == 200, response.text
    body = response.json()
    entry = body["content"]["sections"][0]["entries"][0]
    assert (entry["title"], entry["start_date"]) == ("Software Engineer", "2020-01")
    assert entry["bullets"][0]["changed_by"] == "user"
    assert entry["bullets"][0]["source_text"] == HIGHLIGHTS[0]
    assert (body["edited"], body["warnings"]) == (True, [])


def test_new_claims_produce_warnings_that_block_plain_approval(setup):
    client, job, *_ = setup
    version = generate(client, job)

    def mutate(content):
        bullet = content["sections"][0]["entries"][0]["bullets"][0]
        bullet["text"] = "Built payment APIs in Python and Kubernetes, cutting costs 40%"
        content["summary"] = "Backend engineer with 9 years in payments and Kubernetes."

    body = edit(client, version, mutate).json()
    messages = [w["message"] for w in body["warnings"]]
    assert "Adds number(s) not in your profile summary: 9" in messages
    assert "Mentions skill(s) you have not verified: kubernetes" in messages
    assert any("40%" in m for m in messages) and any("kubernetes" in m for m in messages[2:])

    blocked = client.post(f"/tailored-resumes/{version['id']}/approve")
    assert blocked.status_code == 409
    approved = client.post(f"/tailored-resumes/{version['id']}/approve", json={"acknowledge_warnings": True})
    assert approved.status_code == 200 and approved.json()["status"] == "approved"


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (lambda c: c["skills"].append("Kubernetes"), "“Kubernetes” is not a verified skill"),
        (lambda c: c["sections"][0]["entries"][0]["bullets"].append(
            {"text": "Invented thing", "source_text": "Invented thing"}), "does not come from that entry"),
        (lambda c: c["sections"][0]["entries"].append(c["sections"][0]["entries"][0]), "appears more than once"),
        (lambda c: c["header"].update(email="nope"), "header's email is not valid"),
    ],
)
def test_edits_that_break_rules_are_rejected(setup, mutate, message):
    client, job, *_ = setup
    response = edit(client, generate(client, job), mutate)
    assert response.status_code == 422
    assert message in response.json()["detail"]


def test_unverified_entries_cannot_be_added(setup):
    client, job, _, draft_entry = setup
    version = generate(client, job)

    def mutate(content):
        content["sections"][0]["entries"].append({
            "source_id": draft_entry["id"], "kind": "job", "title": "Unverified Role",
            "bullets": [{"text": "Python work", "source_text": "Python work"}],
        })

    response = edit(client, version, mutate)
    assert response.status_code == 422
    assert "not a verified entry" in response.json()["detail"]


def test_skills_use_verified_spelling_and_entries_can_be_removed(setup):
    client, job, *_ = setup

    def mutate(content):
        content["skills"] = ["postgres", "python", "Python"]
        content["sections"] = []

    body = edit(client, generate(client, job), mutate).json()
    assert body["content"]["skills"] == ["PostgreSQL", "Python"]
    assert body["content"]["sections"] == []


def test_approved_versions_are_locked_and_copyable(setup):
    client, job, *_ = setup
    version = generate(client, job)
    client.post(f"/tailored-resumes/{version['id']}/approve")
    assert edit(client, version, lambda c: None).status_code == 409
    assert client.delete(f"/tailored-resumes/{version['id']}").status_code == 409

    copy = client.post(f"/tailored-resumes/{version['id']}/copy").json()
    assert (copy["version"], copy["status"], copy["based_on_version"]) == (2, "draft", 1)
    assert copy["content"] == version["content"]
    assert client.delete(f"/tailored-resumes/{copy['id']}").status_code == 204
    assert [v["version"] for v in client.get(f"/jobs/{job['id']}/resumes").json()] == [1]


def test_library_changes_block_approval(setup):
    client, job, job_entry, _ = setup
    version = generate(client, job)
    client.patch(f"/experiences/{job_entry['id']}", json={"highlights": ["Something else entirely"]})
    response = client.post(f"/tailored-resumes/{version['id']}/approve")
    assert response.status_code == 409
    assert "is no longer a verified entry" in response.json()["detail"]  # edit unverified it


def test_deleting_a_job_deletes_its_versions(setup):
    client, job, *_ = setup
    version = generate(client, job)
    client.delete(f"/jobs/{job['id']}")
    assert client.get(f"/tailored-resumes/{version['id']}").status_code == 404


def test_resume_text_is_never_logged(setup, caplog):
    client, job, *_ = setup
    caplog.set_level("DEBUG")
    version = generate(client, job)
    edit(client, version, lambda c: c["sections"][0]["entries"][0]["bullets"][0].update(text="Secret wording 99%"))
    client.post(f"/tailored-resumes/{version['id']}/approve", json={"acknowledge_warnings": True})
    for secret in ("payment APIs", "Secret wording", "Alex Example", "alex@example.com", "Example Corp"):
        assert secret not in caplog.text
    assert "tailored resume approved" in caplog.text

import uuid

import pytest

from jobpilot.services.job_ingestion import InvalidJobUrl, canonical_url, description_fingerprint

DESCRIPTION = """Senior Backend Engineer at Example Corp

We are hiring a backend engineer to build Python services on PostgreSQL.
Requirements: 5+ years of experience with Python. Remote (UK)."""


def create(client, **fields):
    return client.post("/jobs", json={"description": DESCRIPTION} | fields)


def test_fingerprint_ignores_case_whitespace_and_punctuation():
    assert description_fingerprint("Python,  PostgreSQL!\n") == description_fingerprint("python postgresql")
    assert description_fingerprint("Python") != description_fingerprint("Go")


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("HTTP://WWW.Example.com/jobs/42/?utm_source=x&b=2&a=1#apply", "https://example.com/jobs/42?a=1&b=2"),
        ("https://example.com:8443/jobs?gclid=abc", "https://example.com:8443/jobs"),
        ("https://example.com/", "https://example.com"),
    ],
)
def test_canonical_url(url, expected):
    assert canonical_url(url) == expected


@pytest.mark.parametrize("url", ["ftp://example.com/job", "javascript:alert(1)", "example.com/job"])
def test_canonical_url_rejects_non_http(url):
    with pytest.raises(InvalidJobUrl):
        canonical_url(url)


def test_create_preserves_original_description_and_url(db_client):
    response = create(db_client, source_url="https://www.example.com/jobs/42?utm_source=feed",
                      title="  Backend   Engineer ", company="")
    assert response.status_code == 201
    body = response.json()
    assert body["duplicate"] is False
    job = body["job"]
    assert job["description"] == DESCRIPTION
    assert job["source_url"] == "https://www.example.com/jobs/42?utm_source=feed"
    # A blank company hint is ignored, so the extracted company is used.
    assert (job["title"], job["company"]) == ("Backend Engineer", "Example Corp")
    assert db_client.get(f"/jobs/{job['id']}").json()["description"] == DESCRIPTION


def test_duplicate_description_returns_existing_job(db_client):
    first = create(db_client).json()["job"]
    again = create(db_client, description=DESCRIPTION.upper().replace("\n", "  \n"))
    assert again.status_code == 200
    assert again.json() == {"job": first, "duplicate": True}
    assert len(db_client.get("/jobs").json()) == 1


def test_duplicate_url_with_different_text_returns_existing_job(db_client):
    first = create(db_client, source_url="https://example.com/jobs/42").json()["job"]
    again = create(db_client, description=DESCRIPTION + " Updated.",
                   source_url="http://www.example.com/jobs/42/?utm_campaign=x")
    assert again.status_code == 200
    assert again.json()["job"]["id"] == first["id"]


def test_validation(db_client):
    assert create(db_client, description="too short").status_code == 422
    bad_url = create(db_client, source_url="ftp://example.com/job")
    assert bad_url.status_code == 422
    assert bad_url.json() == {"detail": "Job URLs must start with http:// or https://."}


def test_list_hides_description_and_delete(db_client):
    job = create(db_client).json()["job"]
    listed = db_client.get("/jobs").json()
    assert [j["id"] for j in listed] == [job["id"]]
    assert "description" not in listed[0]
    assert db_client.delete(f"/jobs/{job['id']}").status_code == 204
    assert db_client.get(f"/jobs/{job['id']}").status_code == 404
    assert db_client.delete(f"/jobs/{uuid.uuid4()}").status_code == 404


def test_create_runs_rule_extraction(db_client):
    job = create(db_client).json()["job"]
    assert job["extraction_method"] == "rules"
    assert job["extracted_at"] is not None
    requirements = job["requirements"]
    assert requirements["title"] == "Senior Backend Engineer"
    assert requirements["seniority"] == "senior"
    assert requirements["work_arrangement"] == "remote"
    assert requirements["location"] == "UK"
    assert requirements["years_experience_min"] == 5
    assert set(requirements["required_skills"]) == {"Python", "PostgreSQL"}
    assert requirements["salary"] == {"min": None, "max": None, "currency": None, "period": None}
    assert job["title"] == "Senior Backend Engineer" and job["company"] == "Example Corp"


def test_user_corrections_are_saved_as_manual(db_client):
    job = create(db_client).json()["job"]
    corrected = job["requirements"] | {"seniority": "lead", "required_skills": ["Python", "Go"]}
    response = db_client.put(f"/jobs/{job['id']}/requirements", json=corrected)
    assert response.status_code == 200
    body = response.json()
    assert body["extraction_method"] == "manual"
    assert body["requirements"]["seniority"] == "lead"
    assert body["requirements"]["required_skills"] == ["Python", "Go"]
    assert db_client.put(f"/jobs/{job['id']}/requirements", json={"seniority": "wizard"}).status_code == 422


def test_reextract_replaces_corrections(db_client):
    job = create(db_client, title="Platform Engineer").json()["job"]
    assert job["requirements"]["title"] == "Platform Engineer"
    db_client.put(f"/jobs/{job['id']}/requirements", json={"title": "Platform Engineer", "seniority": "lead"})
    again = db_client.post(f"/jobs/{job['id']}/extract").json()
    assert again["extraction_method"] == "rules"
    assert again["requirements"]["seniority"] == "senior"  # the manual "lead" is replaced
    assert again["title"] == "Platform Engineer"

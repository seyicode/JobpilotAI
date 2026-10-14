import uuid

import pytest
from pydantic import ValidationError

from jobpilot.services.resumes.schema import ResumeBullet, ResumeContent, UserProfile

PROFILE = {
    "full_name": "  Alex   Example ", "headline": "Backend engineer", "email": "alex@example.com",
    "phone": "+44 20 7946 0000", "location": "London, UK",
    "links": ["https://example.com/alex", " https://example.com/alex ", ""],
    "summary": "Backend engineer focused on reliable APIs.\n\nEight years in fintech.",
}


def test_profile_cleans_input():
    profile = UserProfile(**PROFILE)
    assert profile.full_name == "Alex Example"
    assert profile.links == ["https://example.com/alex"]
    assert profile.summary == "Backend engineer focused on reliable APIs.\n\nEight years in fintech."
    assert UserProfile(full_name="  ").full_name is None


@pytest.mark.parametrize(
    "field",
    [{"email": "not-an-email"}, {"phone": "call me"}, {"links": ["javascript:alert(1)"]},
     {"links": [f"https://example.com/{i}" for i in range(6)]}, {"summary": "x" * 1201}],
)
def test_profile_rejects_bad_values(field):
    with pytest.raises(ValidationError):
        UserProfile(**field)


def test_resume_content_round_trip_and_bullet_iteration():
    entry_id = uuid.uuid4()
    content = ResumeContent.model_validate({
        "summary": "Summary",
        "skills": ["Python"],
        "sections": [{"kind": "job", "heading": "Experience", "entries": [{
            "source_id": str(entry_id), "kind": "job", "title": "Engineer",
            "bullets": [{"text": " Built  APIs ", "source_text": "Built APIs"}],
        }]}],
    })
    [(entry, bullet)] = list(content.bullets())
    assert entry.source_id == entry_id
    assert (bullet.text, bullet.changed_by) == ("Built APIs", "none")
    with pytest.raises(ValidationError):
        ResumeBullet(text="   ", source_text="x")


def test_profile_api(db_client):
    empty = db_client.get("/profile").json()
    assert empty["updated_at"] is None and empty["full_name"] is None

    saved = db_client.put("/profile", json=PROFILE)
    assert saved.status_code == 200
    assert saved.json()["full_name"] == "Alex Example"
    assert db_client.get("/profile").json() == saved.json()
    assert db_client.put("/profile", json={"email": "nope"}).status_code == 422


def test_profile_is_never_logged(db_client, caplog):
    caplog.set_level("DEBUG")
    db_client.put("/profile", json=PROFILE)
    for secret in ("alex@example.com", "Alex Example", "7946", "fintech"):
        assert secret not in caplog.text

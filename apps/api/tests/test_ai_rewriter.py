"""AI bullet rewording. All HTTP goes to an in-memory fake; no real requests are made."""

import json
import uuid

import httpx
import pytest
from fakes import FakeOpenAI, chat_completion, make_settings
from sqlalchemy import select

from jobpilot.api.routes.tailored import get_ai_rewriter
from jobpilot.db.models import AIUsage
from jobpilot.services.ai.openai_client import AIUnavailable
from jobpilot.services.extraction.schema import JobRequirements
from jobpilot.services.resumes.ai_rewriter import AIRewriter
from jobpilot.services.resumes.schema import ResumeContent

BULLETS = [
    "Built payment APIs in Python on Postgres for 1,200 merchants",
    "Ran the team offsite",
    "Wrote runbooks for on-call",
    "Containerised services with Docker",
    "Fixed flaky tests",
    "Mentored two juniors",
]
CONTENT = ResumeContent.model_validate({
    "header": {"name": "Alex Example", "email": "alex@example.com"},
    "skills": ["Python"],
    "sections": [{"kind": "job", "heading": "Experience", "entries": [{
        "source_id": str(uuid.uuid4()), "kind": "job", "title": "Engineer", "organization": "Example Corp",
        "start_date": "2020", "is_current": True,
        "bullets": [{"text": b, "source_text": b, "reason": "Selected."} for b in BULLETS],
    }]}],
})
REQUIREMENTS = JobRequirements(title="Backend Engineer", required_skills=["Python"])
PROPOSALS = {
    "b0": "Delivered Python payment APIs on PostgreSQL serving 1,200 merchants",  # faithful
    "b1": "Organised the team offsite, boosting morale 30%",                      # new number
    "b2": "Wrote Kubernetes runbooks for on-call",                                 # new skill
    "b3": "Containerised services with Docker at Google",                         # new name
    "b4": "Fixed flaky tests " + "and much more " * 10,                            # too long
    # b5 missing
}


@pytest.fixture
def session(session_factory):
    with session_factory() as session:
        yield session


def rewriter(fake: FakeOpenAI, **settings) -> AIRewriter:
    return AIRewriter(make_settings(**settings), transport=httpx.MockTransport(fake), sleep=lambda _: None)


def reply(proposals=PROPOSALS):
    return chat_completion({"bullets": [{"id": k, "text": v} for k, v in proposals.items()]})


def test_only_safe_rewordings_are_accepted(session):
    content, note = rewriter(FakeOpenAI(reply())).rewrite(session, CONTENT, REQUIREMENTS, ["Python"])
    bullets = [b for _, b in content.bullets()]
    assert (bullets[0].text, bullets[0].changed_by) == (PROPOSALS["b0"], "ai")
    assert bullets[0].source_text == BULLETS[0]
    for index, problem in [(1, "adds number(s) not in your verified entry: 30%"),
                           (2, "adds skill(s) not in your verified entry: kubernetes"),
                           (3, "adds name(s) not in your verified entry: google"),
                           (4, "the rewording was much longer than the original"),
                           (5, "the AI did not return this bullet")]:
        assert (bullets[index].text, bullets[index].changed_by) == (BULLETS[index], "none")
        assert bullets[index].reason == f"Selected. AI rewording not used: {problem}."
    assert note == ("AI reworded 1 of 6 bullets. 5 rewordings were rejected by the fact check, "
                    "so the verified wording was kept.")
    assert [b.text for _, b in CONTENT.bullets()] == BULLETS  # input not mutated


def test_model_sees_only_bullet_text(session):
    fake = FakeOpenAI(reply())
    rewriter(fake).rewrite(session, CONTENT, REQUIREMENTS, ["Python"])
    body = json.loads(fake.requests[0].content)
    assert body["response_format"]["json_schema"]["name"] == "resume_bullets"
    user = json.loads(body["messages"][1]["content"])
    assert user["target_role"] == "Backend Engineer"
    assert [b["text"] for b in user["bullets"]] == BULLETS
    sent = fake.requests[0].content.decode()
    for private in ("Alex Example", "alex@example.com", "Example Corp", "2020"):
        assert private not in sent
    assert "Never add numbers" in body["messages"][0]["content"]


def test_results_are_cached_and_usage_is_recorded_under_its_purpose(session):
    fake = FakeOpenAI(reply())
    rewriter(fake).rewrite(session, CONTENT, REQUIREMENTS, ["Python"])
    rewriter(fake).rewrite(session, CONTENT, REQUIREMENTS, ["Python"])
    assert len(fake.requests) == 1
    assert [u.purpose for u in session.scalars(select(AIUsage))] == ["resume_rewrite"]


def test_limits_and_errors_raise(session):
    with pytest.raises(AIUnavailable, match="daily AI request limit"):
        rewriter(FakeOpenAI(), ai_daily_request_limit=0).rewrite(session, CONTENT, REQUIREMENTS, [])
    with pytest.raises(AIUnavailable, match="too long"):
        rewriter(FakeOpenAI(), ai_max_input_chars=1000).rewrite(
            session, CONTENT.model_copy(update={"sections": CONTENT.sections * 5}), REQUIREMENTS, [])
    with pytest.raises(AIUnavailable, match="no bullets"):
        rewriter(FakeOpenAI()).rewrite(session, ResumeContent(), REQUIREMENTS, [])
    with pytest.raises(AIUnavailable, match="declined to reword"):
        rewriter(FakeOpenAI(chat_completion(None, refusal="no"))).rewrite(session, CONTENT, REQUIREMENTS, [])


# API


@pytest.fixture
def job_with_library(db_client):
    client = db_client
    client.post("/experiences", json={"kind": "job", "title": "Engineer", "organization": "Example Corp",
                                      "highlights": ["Built payment APIs in Python"], "verified": True})
    description = "Backend Engineer at Acme\nRequirements: Python. We build payment systems for merchants."
    return client, client.post("/jobs", json={"description": description}).json()["job"]


def test_ai_generation_records_method_and_note(job_with_library):
    client, job = job_with_library
    fake = FakeOpenAI(reply({"b0": "Delivered payment APIs in Python"}))
    client.app.dependency_overrides[get_ai_rewriter] = lambda: rewriter(fake)
    version = client.post(f"/jobs/{job['id']}/resumes", json={"method": "ai"}).json()
    assert (version["generation_method"], version["note"]) == ("ai", "AI reworded 1 of 1 bullets.")
    bullet = version["content"]["sections"][0]["entries"][0]["bullets"][0]
    assert (bullet["text"], bullet["source_text"], bullet["changed_by"]) == (
        "Delivered payment APIs in Python", "Built payment APIs in Python", "ai")

    # Approving and exporting work the same way for AI versions.
    assert client.post(f"/tailored-resumes/{version['id']}/approve").status_code == 200


def test_ai_generation_falls_back_without_ai(job_with_library):
    client, job = job_with_library
    version = client.post(f"/jobs/{job['id']}/resumes", json={"method": "ai"}).json()
    assert version["generation_method"] == "deterministic"
    assert version["note"] == "AI rewording is not configured, so the verified wording was used unchanged."

    failing = FakeOpenAI(httpx.Response(401, json={}))
    client.app.dependency_overrides[get_ai_rewriter] = lambda: rewriter(failing)
    version = client.post(f"/jobs/{job['id']}/resumes", json={"method": "ai"}).json()
    assert version["generation_method"] == "deterministic"
    assert version["note"] == "The AI service rejected the API key. The verified wording was used unchanged."


def test_ai_status_reveals_nothing_secret(db_client):
    body = db_client.get("/ai/status").json()
    assert set(body) == {"available"}

"""Source adapters and the feed fetcher. No real network requests are made."""

from datetime import UTC, datetime

import httpx
import pytest
from feed_samples import ASHBY, GREENHOUSE, LEVER

from jobpilot.core.config import Settings
from jobpilot.services.sources.base import FeedFormatError, InvalidBoard, validate_board
from jobpilot.services.sources.fetcher import USER_AGENT, FeedFetcher, FetchError
from jobpilot.services.sources.html_text import html_to_text
from jobpilot.services.sources.providers import ADAPTERS


@pytest.mark.parametrize("board", ["examplecorp", "Example-Corp_2", "a.b"])
def test_valid_boards(board):
    assert validate_board(f" {board} ") == board


@pytest.mark.parametrize("board", ["", "../admin", "a/b", "a?b=1", "a b", "-lead", "x" * 101, "a..b",
                                   "evil.com/x", "%2e%2e"])
def test_invalid_boards(board):
    with pytest.raises(InvalidBoard):
        validate_board(board)


def test_feed_urls_stay_on_the_provider_host():
    assert ADAPTERS["greenhouse"].feed_url("examplecorp") == (
        "https://boards-api.greenhouse.io/v1/boards/examplecorp/jobs?content=true&pay_transparency=true")
    assert ADAPTERS["lever"].feed_url("examplelabs") == "https://api.lever.co/v0/postings/examplelabs?mode=json"
    assert ADAPTERS["ashby"].feed_url("exampleco") == (
        "https://api.ashbyhq.com/posting-api/job-board/exampleco?includeCompensation=true")


def test_html_to_text_drops_scripts_and_keeps_structure():
    html = "<h2>Role</h2><p>Build&nbsp;things.</p><ul><li>Python</li><li>SQL</li></ul><script>x()</script>"
    assert html_to_text(html) == "Role\n\nBuild things.\n\n- Python\n\n- SQL"
    assert html_to_text("&lt;p&gt;Hi &amp;amp; bye&lt;/p&gt;", escaped=True) == "Hi & bye"


def test_greenhouse():
    first, second = ADAPTERS["greenhouse"].parse(GREENHOUSE)
    assert (first.external_id, first.title, first.location) == ("4012345", "Senior Backend Engineer", "Remote - UK")
    assert first.url == "https://boards.greenhouse.io/examplecorp/jobs/4012345"
    assert "We build payments." in first.description and "- Python" in first.description
    assert "alert" not in first.description
    assert first.posted_at == datetime(2026, 9, 28, 13, 0, tzinfo=UTC)
    assert first.structured == {
        "location": "Remote - UK", "work_arrangement": "remote",
        "salary": {"min": 80000, "max": 95000, "currency": "GBP", "period": "year"},
    }
    assert second.structured == {"location": "London"}


def test_lever():
    first, second = ADAPTERS["lever"].parse(LEVER)
    assert (first.title, first.location) == ("Platform Engineer", "Berlin")
    assert first.description == ("Help us scale our platform.\n\nWhat you'll need\n- Kubernetes\n\n- Go"
                                 "\n\nVisa sponsorship available.")
    assert first.structured == {
        "location": "Berlin", "work_arrangement": "hybrid", "employment_type": "full_time",
        "salary": {"min": 70000, "max": 90000, "currency": "EUR", "period": "year"},
    }
    assert first.posted_at.year == 2025
    assert second.structured == {"employment_type": "contract"}  # "unspecified" workplace is unknown


def test_ashby_skips_unlisted_jobs():
    [job] = ADAPTERS["ashby"].parse(ASHBY)
    assert (job.external_id, job.title) == ("b2a1c3d4-0000-4000-8000-0000000000aa", "Data Engineer")
    assert job.structured == {
        "location": "New York", "work_arrangement": "remote", "employment_type": "full_time",
        "salary": {"min": 150000, "max": 180000, "currency": "USD", "period": "year"},
    }


@pytest.mark.parametrize(("provider", "payload"), [("greenhouse", []), ("lever", {"jobs": []}), ("ashby", "nope")])
def test_unexpected_shapes_raise(provider, payload):
    with pytest.raises(FeedFormatError):
        ADAPTERS[provider].parse(payload)


def test_missing_fields_are_tolerated():
    assert ADAPTERS["lever"].parse([{"id": "x"}, {}, "junk"]) == []
    [job] = ADAPTERS["ashby"].parse({"jobs": [{"id": 1, "title": "T", "jobUrl": "https://jobs.ashbyhq.com/a/1",
                                               "descriptionPlain": "D", "compensation": "weird"}]})
    assert job.structured == {}


# Fetcher

HOST = "api.lever.co"
URL = f"https://{HOST}/v0/postings/examplelabs?mode=json"


class Replay:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.requests: list[httpx.Request] = []

    def __call__(self, request):
        self.requests.append(request)
        item = self.responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def fetcher(replay, sleeps=None, **settings):
    values = {"discovery_retry_base_delay_seconds": 1.0} | settings
    return FeedFetcher(Settings(**values), transport=httpx.MockTransport(replay),
                       sleep=(sleeps.append if sleeps is not None else lambda _: None))


def test_fetch_success_identifies_jobpilot():
    replay = Replay(httpx.Response(200, json=LEVER))
    result = fetcher(replay).fetch_json(URL, HOST)
    assert (result.payload, result.attempts) == (LEVER, 1)
    request = replay.requests[0]
    assert request.headers["user-agent"] == USER_AGENT
    assert "cookie" not in request.headers and "authorization" not in request.headers


@pytest.mark.parametrize("url", ["http://api.lever.co/v0/postings/x", "https://evil.example/v0/postings/x",
                                 "https://api.lever.co.evil.example/x"])
def test_only_https_to_the_allowed_host(url):
    replay = Replay()
    with pytest.raises(FetchError, match="not allowed"):
        fetcher(replay).fetch_json(url, HOST)
    assert replay.requests == []


def test_retries_with_backoff_and_retry_after():
    sleeps: list[float] = []
    replay = Replay(httpx.Response(503), httpx.Response(429, headers={"retry-after": "120"}),
                    httpx.Response(200, json=[]))
    result = fetcher(replay, sleeps).fetch_json(URL, HOST)
    assert result.attempts == 3
    assert sleeps == [1.0, 30.0]  # base delay, then Retry-After capped at 30s


def test_gives_up_after_retries():
    replay = Replay(httpx.ReadTimeout("slow"), httpx.ConnectError("down"), httpx.Response(502))
    with pytest.raises(FetchError) as caught:
        fetcher(replay, discovery_max_retries=2).fetch_json(URL, HOST)
    assert (caught.value.code, caught.value.attempts) == ("http_502", 3)


@pytest.mark.parametrize(("response", "code"), [
    (httpx.Response(404), "not_found"),
    (httpx.Response(403), "forbidden"),
    (httpx.Response(302, headers={"location": "https://evil.example"}), "redirect"),
    (httpx.Response(200, content=b"<html>"), "invalid_json"),
])
def test_non_retryable_failures(response, code):
    replay = Replay(response)
    with pytest.raises(FetchError) as caught:
        fetcher(replay).fetch_json(URL, HOST)
    assert caught.value.code == code
    assert len(replay.requests) == 1


def test_oversized_responses_are_abandoned():
    replay = Replay(httpx.Response(200, content=b"[" + b"0," * 60_000 + b"0]"))
    with pytest.raises(FetchError, match="larger than the allowed size"):
        fetcher(replay, discovery_max_response_bytes=100_000).fetch_json(URL, HOST)

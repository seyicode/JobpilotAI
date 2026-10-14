"""Polite, locked-down HTTP fetching for job feeds.

- Only HTTPS requests to the adapter's own host (an allowlist); redirects are not followed.
- Timeouts, bounded retries with capped backoff on 408/429/5xx and network errors, Retry-After honoured.
- Responses larger than the configured limit are abandoned while streaming.
- Requests identify JobPilot and carry nothing about the user.
"""

import json
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from urllib.parse import urlsplit

import httpx

from jobpilot.core.config import Settings
from jobpilot.core.logs import quiet_third_party_loggers

logger = logging.getLogger(__name__)
quiet_third_party_loggers()

USER_AGENT = "JobPilot-AI/0.1 (personal job search; reads public job-board APIs)"
RETRYABLE_STATUS = {408, 429, 500, 502, 503, 504}
MAX_BACKOFF_SECONDS = 30.0


class FetchError(Exception):
    """A feed could not be fetched. `code` is stored in source health; the message is user-safe."""

    def __init__(self, code: str, message: str, http_status: int | None = None):
        super().__init__(message)
        self.code = code
        self.http_status = http_status
        self.attempts = 1


@dataclass(frozen=True)
class FetchResult:
    payload: object
    http_status: int
    attempts: int
    bytes: int


class FeedFetcher:
    def __init__(self, settings: Settings, transport: httpx.BaseTransport | None = None,
                 sleep: Callable[[float], None] = time.sleep):
        self.settings = settings
        self.transport = transport
        self.sleep = sleep

    def fetch_json(self, url: str, allowed_host: str) -> FetchResult:
        parts = urlsplit(url)
        if parts.scheme != "https" or parts.hostname != allowed_host:
            raise FetchError("blocked_url", "That feed address is not allowed.")
        s = self.settings
        timeout = httpx.Timeout(s.discovery_timeout_seconds, connect=min(5.0, s.discovery_timeout_seconds))
        headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
        error = FetchError("timeout", "The job feed did not respond in time.")
        with httpx.Client(transport=self.transport, timeout=timeout, follow_redirects=False,
                          headers=headers) as client:
            for attempt in range(1, s.discovery_max_retries + 2):
                retry_after = None
                try:
                    with client.stream("GET", url) as response:
                        if response.status_code == 200:
                            body = self._read_capped(response)
                            return FetchResult(self._json(body), 200, attempt, len(body))
                        error = _status_error(response.status_code)
                        retry_after = _retry_after(response)
                        if response.status_code not in RETRYABLE_STATUS:
                            error.attempts = attempt
                            raise error
                except FetchError as failure:  # Too large, invalid JSON, or not retryable
                    failure.attempts = attempt
                    raise
                except httpx.TimeoutException:
                    error = FetchError("timeout", "The job feed did not respond in time.")
                except httpx.TransportError:
                    error = FetchError("network_error", "The job feed could not be reached.")
                logger.info("feed fetch retryable failure host=%s attempt=%d code=%s", allowed_host, attempt, error.code)
                if attempt <= s.discovery_max_retries:
                    delay = retry_after if retry_after is not None else s.discovery_retry_base_delay_seconds * 2 ** (attempt - 1)
                    self.sleep(min(delay, MAX_BACKOFF_SECONDS))
        error.attempts = s.discovery_max_retries + 1
        raise error

    def _read_capped(self, response: httpx.Response) -> bytes:
        limit = self.settings.discovery_max_response_bytes
        chunks, size = [], 0
        for chunk in response.iter_bytes():
            size += len(chunk)
            if size > limit:
                raise FetchError("too_large", "The job feed was larger than the allowed size.")
            chunks.append(chunk)
        return b"".join(chunks)

    @staticmethod
    def _json(body: bytes) -> object:
        try:
            return json.loads(body)
        except ValueError:
            raise FetchError("invalid_json", "The job feed did not return valid JSON.") from None


def _status_error(status: int) -> FetchError:
    if status == 404:
        return FetchError("not_found", "No job board was found with that name.", status)
    if status in (401, 403):
        return FetchError("forbidden", "The job board refused access.", status)
    if status == 429:
        return FetchError("rate_limited", "The job board asked us to slow down.", status)
    if 300 <= status < 400:
        return FetchError("redirect", "The job feed tried to redirect elsewhere; not followed.", status)
    return FetchError(f"http_{status}", f"The job feed returned an error ({status}).", status)


def _retry_after(response: httpx.Response) -> float | None:
    try:
        return max(0.0, float(response.headers["retry-after"]))
    except (KeyError, ValueError):
        return None

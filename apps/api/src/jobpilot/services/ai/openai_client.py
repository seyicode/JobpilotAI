"""Shared OpenAI Chat Completions client with structured JSON output and spending controls.

Every caller (requirement extraction, resume rewriting) goes through this class, so all AI use
shares one set of limits and one usage ledger. Called from the backend only. Prompts, inputs,
outputs, and the API key are never logged or stored in the ledger.
"""

import hashlib
import json
import logging
import time
from collections.abc import Callable
from datetime import UTC, datetime
from decimal import Decimal

import httpx
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from jobpilot.core.config import Settings
from jobpilot.core.logs import quiet_third_party_loggers
from jobpilot.db.models import AICacheEntry, AIUsage

logger = logging.getLogger(__name__)
quiet_third_party_loggers()

RETRYABLE_STATUS = {408, 409, 429, 500, 502, 503, 504}
MAX_RETRY_AFTER_SECONDS = 5.0


class AIUnavailable(Exception):
    """AI could not be used. The message is safe to show users."""


class OpenAIClient:
    def __init__(
        self,
        settings: Settings,
        transport: httpx.BaseTransport | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ):
        if not settings.ai_configured:
            raise ValueError("OpenAI is not configured")
        self.settings = settings
        self.model: str = settings.openai_model  # type: ignore[assignment]
        self.transport = transport
        self.sleep = sleep

    def cache_key(self, *parts: object) -> str:
        raw = json.dumps([self.model, *parts], default=str)
        return hashlib.sha256(raw.encode()).hexdigest()

    def cached(self, session: Session, key: str, purpose: str) -> dict | None:
        entry = session.get(AICacheEntry, key)
        if entry is not None:
            logger.info("ai cache hit purpose=%s model=%s", purpose, self.model)
            return entry.result
        return None

    def store(self, session: Session, key: str, purpose: str, result: dict) -> None:
        """Cache a result the caller has validated."""
        session.merge(AICacheEntry(key=key, purpose=purpose, model=self.model, result=result))

    def complete_json(self, session: Session, *, purpose: str, system: str, user: str,
                      schema_name: str, schema: dict, refusal_message: str) -> dict:
        """Check limits, call the API with retries, record usage, and return the parsed JSON."""
        self._check_limits(session, len(system) + len(user))
        s = self.settings
        body = {
            "model": self.model,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "response_format": {
                "type": "json_schema",
                "json_schema": {"name": schema_name, "strict": True, "schema": schema},
            },
            "max_completion_tokens": s.ai_max_output_tokens,
        }
        headers = {"Authorization": f"Bearer {s.openai_api_key.get_secret_value()}"}  # type: ignore[union-attr]
        timeout = httpx.Timeout(s.ai_timeout_seconds, connect=min(5.0, s.ai_timeout_seconds))
        url = s.openai_base_url.rstrip("/") + "/chat/completions"

        reason = "The AI service did not respond in time."
        with httpx.Client(transport=self.transport, timeout=timeout) as client:
            for attempt in range(s.ai_max_retries + 1):
                started = time.monotonic()
                retry_after = None
                try:
                    response = client.post(url, json=body, headers=headers)
                except (httpx.TimeoutException, httpx.TransportError) as error:
                    timed_out = isinstance(error, httpx.TimeoutException)
                    self._record(session, purpose, "timeout" if timed_out else "network_error", started, attempt)
                    reason = ("The AI service did not respond in time." if timed_out
                              else "The AI service could not be reached.")
                else:
                    if response.status_code == 200:
                        return self._parse(session, purpose, response, started, attempt, refusal_message)
                    self._record(session, purpose, f"http_{response.status_code}", started, attempt)
                    reason = _http_reason(response.status_code)
                    if response.status_code not in RETRYABLE_STATUS:
                        raise AIUnavailable(reason)
                    retry_after = _retry_after(response)
                if attempt < s.ai_max_retries:
                    delay = retry_after if retry_after is not None else s.ai_retry_base_delay_seconds * 2**attempt
                    self.sleep(min(delay, MAX_RETRY_AFTER_SECONDS))
        raise AIUnavailable(reason)

    def _check_limits(self, session: Session, prompt_chars: int) -> None:
        s = self.settings
        now = datetime.now(UTC)
        day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        month_start = day_start.replace(day=1)
        requests_today = session.scalar(
            select(func.count()).select_from(AIUsage).where(AIUsage.created_at >= day_start)
        )
        if requests_today >= s.ai_daily_request_limit:
            raise AIUnavailable("The daily AI request limit has been reached.")

        tokens, cost = session.execute(
            select(
                func.coalesce(func.sum(AIUsage.input_tokens + AIUsage.output_tokens), 0),
                func.coalesce(func.sum(AIUsage.cost_usd), 0),
            ).where(AIUsage.created_at >= month_start)
        ).one()
        # Rough upper bound for this request: about 4 characters per token, plus full output.
        estimate_in = prompt_chars // 4 + 50
        estimate_out = s.ai_max_output_tokens
        if tokens + estimate_in + estimate_out > s.ai_monthly_token_limit:
            raise AIUnavailable("The monthly AI token limit has been reached.")
        if s.ai_monthly_budget_usd is not None:
            estimated_cost = self._cost(estimate_in, estimate_out)
            if estimated_cost is None:
                raise AIUnavailable("An AI budget is set but token prices are not configured.")
            if float(cost) + float(estimated_cost) > s.ai_monthly_budget_usd:
                raise AIUnavailable("The monthly AI budget has been reached.")

    def _cost(self, input_tokens: int, output_tokens: int) -> Decimal | None:
        s = self.settings
        if s.ai_input_cost_per_million_tokens_usd is None or s.ai_output_cost_per_million_tokens_usd is None:
            return None
        cost = (input_tokens * s.ai_input_cost_per_million_tokens_usd
                + output_tokens * s.ai_output_cost_per_million_tokens_usd) / 1_000_000
        return Decimal(str(round(cost, 6)))

    def _parse(self, session: Session, purpose: str, response: httpx.Response, started: float,
               attempt: int, refusal_message: str) -> dict:
        try:
            payload = response.json()
            usage = payload.get("usage") or {}
            message = payload["choices"][0]["message"]
        except (ValueError, KeyError, IndexError, TypeError):
            self._record(session, purpose, "invalid_output", started, attempt)
            raise AIUnavailable("The AI response could not be read.") from None
        input_tokens = int(usage.get("prompt_tokens") or 0)
        output_tokens = int(usage.get("completion_tokens") or 0)
        if message.get("refusal") or not message.get("content"):
            self._record(session, purpose, "refused", started, attempt, input_tokens, output_tokens)
            raise AIUnavailable(refusal_message)
        try:
            data = json.loads(message["content"])
        except ValueError:
            self._record(session, purpose, "invalid_output", started, attempt, input_tokens, output_tokens)
            raise AIUnavailable("The AI response could not be read.") from None
        self._record(session, purpose, "success", started, attempt, input_tokens, output_tokens)
        return data

    def _record(self, session: Session, purpose: str, status: str, started: float, attempt: int,
                input_tokens: int = 0, output_tokens: int = 0) -> None:
        latency_ms = int((time.monotonic() - started) * 1000)
        session.add(AIUsage(
            purpose=purpose, model=self.model, status=status, input_tokens=input_tokens,
            output_tokens=output_tokens, cost_usd=self._cost(input_tokens, output_tokens),
            latency_ms=latency_ms,
        ))
        session.flush()
        logger.info(
            "ai request purpose=%s model=%s status=%s attempt=%d input_tokens=%d output_tokens=%d latency_ms=%d",
            purpose, self.model, status, attempt + 1, input_tokens, output_tokens, latency_ms,
        )


def _retry_after(response: httpx.Response) -> float | None:
    try:
        return max(0.0, float(response.headers["retry-after"]))
    except (KeyError, ValueError):
        return None


def _http_reason(status_code: int) -> str:
    if status_code in (401, 403):
        return "The AI service rejected the API key."
    if status_code == 404:
        return "The configured AI model was not found."
    if status_code == 429:
        return "The AI service is rate limiting requests."
    return f"The AI service returned an error ({status_code})."

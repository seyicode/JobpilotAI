"""Test doubles for the OpenAI HTTP API. Nothing here makes network requests."""

import json

import httpx

from jobpilot.core.config import Settings


class FakeOpenAI:
    """Replays queued responses (or exceptions) and records requests."""

    def __init__(self, *responses):
        self.responses = list(responses)
        self.requests: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        item = self.responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def chat_completion(content: dict | str | None, refusal: str | None = None) -> httpx.Response:
    text = json.dumps(content) if isinstance(content, dict) else content
    return httpx.Response(200, json={
        "choices": [{"message": {"content": text, "refusal": refusal}}],
        "usage": {"prompt_tokens": 400, "completion_tokens": 100},
    })


def make_settings(**overrides) -> Settings:
    values = {
        "openai_api_key": "sk-test-secret", "openai_model": "test-model",
        "ai_retry_base_delay_seconds": 0.5,
        "ai_input_cost_per_million_tokens_usd": 1.0, "ai_output_cost_per_million_tokens_usd": 4.0,
    }
    return Settings(**(values | overrides))

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql://jobpilot:jobpilot_local_only@localhost:5432/jobpilot"
    cors_origins: list[str] = ["http://localhost:3000"]
    max_resume_bytes: int = 5 * 1024 * 1024

    # AI requirement extraction. Disabled unless both the key and the model are set.
    openai_api_key: SecretStr | None = None
    openai_model: str | None = None
    openai_base_url: str = "https://api.openai.com/v1"
    ai_timeout_seconds: float = Field(default=20, gt=0, le=120)
    ai_max_retries: int = Field(default=2, ge=0, le=5)
    ai_retry_base_delay_seconds: float = Field(default=0.5, ge=0, le=10)
    ai_max_input_chars: int = Field(default=20_000, ge=1_000, le=200_000)
    ai_max_output_tokens: int = Field(default=1_500, ge=200, le=16_000)
    # Spending controls, checked before every request.
    ai_daily_request_limit: int = Field(default=50, ge=0)
    ai_monthly_token_limit: int = Field(default=1_000_000, ge=0)
    ai_monthly_budget_usd: float | None = Field(default=None, ge=0)
    ai_input_cost_per_million_tokens_usd: float | None = Field(default=None, ge=0)
    ai_output_cost_per_million_tokens_usd: float | None = Field(default=None, ge=0)

    # Job discovery from public company job feeds (Greenhouse, Lever, Ashby).
    discovery_enabled: bool = False  # Scheduled runs; "Run now" works either way
    discovery_use_ai: bool = False  # AI extraction for discovered jobs (needs AI configured too)
    discovery_timeout_seconds: float = Field(default=15, gt=0, le=60)
    discovery_max_retries: int = Field(default=2, ge=0, le=5)
    discovery_retry_base_delay_seconds: float = Field(default=1.0, ge=0, le=30)
    discovery_max_response_bytes: int = Field(default=10_000_000, ge=100_000, le=50_000_000)
    discovery_max_postings_per_source: int = Field(default=500, ge=1, le=5_000)
    discovery_max_requests_per_hour: int = Field(default=60, ge=1, le=1_000)
    discovery_default_interval_minutes: int = Field(default=360, ge=60)
    discovery_min_interval_minutes: int = Field(default=60, ge=15)
    discovery_manual_cooldown_minutes: int = Field(default=10, ge=1)
    discovery_delay_between_sources_seconds: float = Field(default=2.0, ge=0, le=60)
    discovery_worker_tick_seconds: int = Field(default=60, ge=10, le=3600)

    # Resume export page size: A4 or LETTER.
    resume_page_size: Literal["A4", "LETTER"] = "A4"

    # Matching: override factor weights, e.g. MATCH_WEIGHTS={"required_skills": 50}.
    match_weights: dict[str, float] = Field(default_factory=dict)

    # Blank values (e.g. "AI_MONTHLY_BUDGET_USD=") mean "not set".
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", env_ignore_empty=True)

    @property
    def ai_configured(self) -> bool:
        return bool(self.openai_api_key and self.openai_api_key.get_secret_value() and self.openai_model)


@lru_cache
def get_settings() -> Settings:
    return Settings()

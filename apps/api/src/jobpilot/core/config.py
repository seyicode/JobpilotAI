from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql://jobpilot:jobpilot_local_only@localhost:5432/jobpilot"
    cors_origins: list[str] = ["http://localhost:3000"]
    max_resume_bytes: int = 5 * 1024 * 1024
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()

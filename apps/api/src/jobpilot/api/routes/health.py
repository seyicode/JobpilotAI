from typing import Annotated

import psycopg
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from jobpilot.core.config import Settings, get_settings

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: str


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    """Liveness: does not depend on external services."""
    return HealthResponse(status="ok")


@router.get("/ready", response_model=HealthResponse)
def ready(settings: Annotated[Settings, Depends(get_settings)]) -> HealthResponse:
    """Readiness: verify PostgreSQL with a bounded connection timeout."""
    try:
        with psycopg.connect(settings.database_url, connect_timeout=3) as connection:
            connection.execute("SELECT 1")
    except psycopg.Error:
        raise HTTPException(status_code=503, detail="Database unavailable") from None
    return HealthResponse(status="ok")

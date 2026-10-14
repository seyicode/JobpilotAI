"""Scheduled job discovery. Run with `python -m jobpilot.worker` (the `worker` Compose service).

Every tick, while DISCOVERY_ENABLED is true, it claims due sources one at a time and runs them,
pausing between sources. Claiming locks the row (SKIP LOCKED) and pushes next_run_at forward as a
lease, so several workers never fetch the same board at once, and a crashed run is retried later.
"""

import logging
import signal
import time
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from sqlalchemy import or_, select
from sqlalchemy.orm import Session, sessionmaker

from jobpilot.api.routes.preferences import load_preferences
from jobpilot.core.config import Settings, get_settings
from jobpilot.core.logs import quiet_third_party_loggers
from jobpilot.db.models import JobSource
from jobpilot.db.session import get_engine
from jobpilot.services.discovery import run_source
from jobpilot.services.extraction.openai_extractor import OpenAIExtractor
from jobpilot.services.sources.fetcher import FeedFetcher

logger = logging.getLogger("jobpilot.worker")


def claim_due_source(session: Session, now: datetime) -> JobSource | None:
    """Lock one due, enabled source and lease it until its next interval. Commits the claim."""
    source = session.scalars(
        select(JobSource)
        .where(JobSource.enabled.is_(True), or_(JobSource.next_run_at.is_(None), JobSource.next_run_at <= now))
        .order_by(JobSource.next_run_at.asc().nulls_first())
        .limit(1)
        .with_for_update(skip_locked=True)
    ).first()
    if source is None:
        session.rollback()
        return None
    source.next_run_at = now + timedelta(minutes=source.interval_minutes)
    session.commit()
    return source


def tick(session_factory: sessionmaker, settings: Settings, fetcher: FeedFetcher, *,
         now: Callable[[], datetime] = lambda: datetime.now(UTC),
         sleep: Callable[[float], None] = time.sleep, max_sources: int = 50) -> int:
    """Run every due source once. Returns how many ran."""
    if not settings.discovery_enabled:
        return 0
    ai = OpenAIExtractor(settings) if settings.discovery_use_ai and settings.ai_configured else None
    ran = 0
    while ran < max_sources:
        with session_factory() as session:
            source = claim_due_source(session, now())
            if source is None:
                break
            if ran:
                sleep(settings.discovery_delay_between_sources_seconds)
            preferences = load_preferences(session)
            run_source(session, source, fetcher=fetcher, settings=settings, preferences=preferences,
                       ai=ai, trigger="scheduled", now=now())
            ran += 1
    return ran


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s [%(name)s] %(message)s")
    quiet_third_party_loggers()
    settings = get_settings()
    session_factory = sessionmaker(get_engine(), expire_on_commit=False)
    fetcher = FeedFetcher(settings)
    stopping = False

    def stop(*_):
        nonlocal stopping
        stopping = True

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    logger.info("worker started scheduled_discovery=%s tick_seconds=%d",
                settings.discovery_enabled, settings.discovery_worker_tick_seconds)
    while not stopping:
        try:
            ran = tick(session_factory, settings, fetcher)
            if ran:
                logger.info("worker tick sources_run=%d", ran)
        except Exception:  # Keep the worker alive; the next tick retries.
            logger.exception("worker tick failed")
        for _ in range(settings.discovery_worker_tick_seconds):
            if stopping:
                break
            time.sleep(1)
    logger.info("worker stopped")


if __name__ == "__main__":
    main()

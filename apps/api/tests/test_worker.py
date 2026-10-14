"""Scheduled discovery worker. No real network requests are made."""

from datetime import UTC, datetime, timedelta

import httpx
import pytest
from feed_samples import ASHBY, GREENHOUSE, LEVER
from sqlalchemy import select

from jobpilot.core.config import Settings
from jobpilot.db.models import JobSource, SourceRun
from jobpilot.services.sources.fetcher import FeedFetcher
from jobpilot.worker import claim_due_source, tick

T0 = datetime(2026, 10, 14, 9, 0, tzinfo=UTC)
FEEDS = {"boards-api.greenhouse.io": GREENHOUSE, "api.lever.co": LEVER, "api.ashbyhq.com": ASHBY}


def serve(request):
    return httpx.Response(200, json=FEEDS[request.url.host])


def add(session, provider, board, next_run_at, enabled=True):
    source = JobSource(provider=provider, board=board, company_name=board.title(), enabled=enabled,
                       interval_minutes=360, status="new", consecutive_failures=0, next_run_at=next_run_at)
    session.add(source)
    session.commit()
    return source


@pytest.fixture
def factory(session_factory):
    return session_factory


def run_tick(factory, settings, sleeps=None):
    return tick(factory, settings, FeedFetcher(settings, transport=httpx.MockTransport(serve)),
                now=lambda: T0, sleep=(sleeps.append if sleeps is not None else lambda _: None))


def test_disabled_by_default(factory):
    with factory() as session:
        add(session, "greenhouse", "examplecorp", None)
    assert Settings().discovery_enabled is False
    assert run_tick(factory, Settings()) == 0


def test_runs_due_enabled_sources_with_a_pause_between(factory):
    with factory() as session:
        add(session, "greenhouse", "examplecorp", None)
        add(session, "lever", "examplelabs", T0 - timedelta(minutes=1))
        add(session, "ashby", "exampleco", T0 + timedelta(hours=1))  # not due yet
        add(session, "greenhouse", "paused", None, enabled=False)
    sleeps: list[float] = []
    assert run_tick(factory, Settings(discovery_enabled=True), sleeps) == 2
    assert sleeps == [2.0]
    with factory() as session:
        runs = session.scalars(select(SourceRun)).all()
        assert sorted((r.trigger, r.status) for r in runs) == [("scheduled", "success")] * 2
        ran = {s.board: s for s in session.scalars(select(JobSource))}
        assert ran["examplecorp"].next_run_at == T0 + timedelta(hours=6)
        assert ran["paused"].last_run_at is None
    assert run_tick(factory, Settings(discovery_enabled=True)) == 0  # nothing due any more


def test_claims_are_exclusive(factory):
    with factory() as session:
        add(session, "greenhouse", "examplecorp", None)
    with factory() as first, factory() as second:
        claimed = first.scalars(select(JobSource).with_for_update(skip_locked=True)).first()
        assert claimed is not None
        assert claim_due_source(second, T0) is None  # locked by the first session
        first.rollback()
    with factory() as session:
        source = claim_due_source(session, T0)
        assert source.next_run_at == T0 + timedelta(hours=6)  # leased
        assert claim_due_source(session, T0) is None


def test_discovery_status(db_client):
    status = db_client.get("/sources/status").json()
    assert status == {"scheduled": False, "uses_ai": False, "requests_last_hour": 0,
                      "hourly_request_limit": 60, "next_check_at": None, "sources_failing": 0}

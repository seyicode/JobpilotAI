"""Database tests use a separate <db>_test PostgreSQL database, created and migrated once."""

from collections.abc import Iterator
from pathlib import Path

import psycopg
import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from psycopg import sql
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker

from jobpilot.core.config import get_settings
from jobpilot.db.session import get_session, sqlalchemy_url
from jobpilot.main import create_app

API_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session")
def test_database_url() -> str:
    url = make_url(sqlalchemy_url(get_settings().database_url))
    test_url = url.set(database=f"{url.database}_test")
    admin = url.set(drivername="postgresql").render_as_string(hide_password=False)
    try:
        with psycopg.connect(admin, autocommit=True, connect_timeout=3) as connection:
            exists = connection.execute(
                "SELECT 1 FROM pg_database WHERE datname = %s", (test_url.database,)
            ).fetchone()
            if not exists:
                connection.execute(
                    sql.SQL("CREATE DATABASE {}").format(sql.Identifier(test_url.database))
                )
    except psycopg.OperationalError:
        pytest.skip("PostgreSQL is not available for database tests")
    rendered = test_url.render_as_string(hide_password=False)
    config = Config(str(API_ROOT / "alembic.ini"))
    config.attributes["database_url"] = rendered
    config.attributes["configure_logging"] = False
    command.upgrade(config, "head")
    return rendered


@pytest.fixture
def db_session(test_database_url: str) -> Iterator[Session]:
    engine = create_engine(test_database_url)
    with engine.begin() as connection:
        connection.execute(text("TRUNCATE resumes"))
    with sessionmaker(engine, expire_on_commit=False)() as session:
        yield session
    engine.dispose()


@pytest.fixture
def db_client(db_session: Session) -> Iterator[TestClient]:
    app = create_app()
    app.dependency_overrides[get_session] = lambda: db_session
    with TestClient(app) as client:
        yield client

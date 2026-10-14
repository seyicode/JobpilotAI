from collections.abc import Iterator
from functools import lru_cache

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from jobpilot.core.config import get_settings


def sqlalchemy_url(database_url: str) -> str:
    """Use the psycopg 3 driver for plain postgresql:// URLs."""
    if database_url.startswith("postgresql://"):
        return "postgresql+psycopg://" + database_url.removeprefix("postgresql://")
    return database_url


@lru_cache
def get_engine() -> Engine:
    url = sqlalchemy_url(get_settings().database_url)
    return create_engine(url, pool_pre_ping=True, connect_args={"connect_timeout": 3})


def get_session() -> Iterator[Session]:
    with sessionmaker(get_engine(), expire_on_commit=False)() as session:
        yield session

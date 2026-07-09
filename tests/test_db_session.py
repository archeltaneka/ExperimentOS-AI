from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

import packages.db.session as db_session
from packages.db.session import (
    create_async_session_factory,
    create_database_engine,
    get_database_url,
)


def test_database_url_comes_from_environment(monkeypatch) -> None:
    monkeypatch.setattr(db_session, "load_environment", lambda: False)
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://user:pass@localhost:5432/app")

    assert get_database_url() == "postgresql+psycopg://user:pass@localhost:5432/app"


def test_database_url_requires_environment(monkeypatch) -> None:
    monkeypatch.setattr(db_session, "load_environment", lambda: False)
    monkeypatch.delenv("DATABASE_URL", raising=False)

    try:
        get_database_url()
    except RuntimeError as exc:
        assert "DATABASE_URL" in str(exc)
    else:
        raise AssertionError("Expected get_database_url to require DATABASE_URL")


def test_create_database_engine_and_session_factory() -> None:
    engine = create_database_engine("postgresql+psycopg://user:pass@localhost:5432/app")
    session_factory = create_async_session_factory(engine)

    assert isinstance(engine, AsyncEngine)
    assert isinstance(session_factory, async_sessionmaker)

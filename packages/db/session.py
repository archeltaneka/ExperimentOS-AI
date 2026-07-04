from __future__ import annotations

import os

from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine


def get_database_url() -> str:
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL environment variable is required")
    return database_url


def create_database_engine(database_url: str | None = None) -> AsyncEngine:
    return create_async_engine(database_url or get_database_url())


def create_async_session_factory(engine: AsyncEngine) -> async_sessionmaker:
    return async_sessionmaker(engine, expire_on_commit=False)

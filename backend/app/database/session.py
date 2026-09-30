"""Database engine, session factory and initialisation helpers."""

from __future__ import annotations

import logging
import time
from typing import Iterator, Optional

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import Settings, get_settings

logger = logging.getLogger(__name__)

settings: Settings = get_settings()


def _connect_args(database_url: str) -> dict:
    """SQLite needs a tweak because TestClient talks to the app from a thread."""
    if database_url.startswith("sqlite"):
        return {"check_same_thread": False}
    return {}


engine: Engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    future=True,
    connect_args=_connect_args(settings.database_url),
)

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, future=True)


class Base(DeclarativeBase):
    """Declarative base shared by every ORM model."""


def get_db() -> Iterator[Session]:
    """FastAPI dependency that yields a request scoped session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db(
    retries: Optional[int] = None,
    delay: Optional[float] = None,
    engine_override: Optional[Engine] = None,
) -> None:
    """Create all tables, retrying while the database container is starting."""
    # Importing the models package registers every table on Base.metadata.
    from app import models  # noqa: F401  (side-effect import)

    target_engine = engine_override or engine
    attempts = settings.db_init_retries if retries is None else retries
    wait = settings.db_init_retry_delay if delay is None else delay

    last_error: Optional[Exception] = None
    for attempt in range(1, attempts + 1):
        try:
            Base.metadata.create_all(bind=target_engine)
            logger.info("Database schema is ready (attempt %s/%s)", attempt, attempts)
            return
        except Exception as exc:  # pragma: no cover - depends on live infra
            last_error = exc
            logger.warning(
                "Database not ready yet (attempt %s/%s): %s", attempt, attempts, exc
            )
            time.sleep(wait)

    raise RuntimeError(f"Unable to initialise the database: {last_error}")

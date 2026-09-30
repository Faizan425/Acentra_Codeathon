"""Pytest fixtures shared by the whole backend test-suite.

The environment is configured *before* the application modules are imported so
that the app under test always talks to a throwaway SQLite database instead of
the Docker Postgres instance. Nothing here requires Docker or LocalStack.
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

TEST_DB_FILE = BACKEND_ROOT / "tests" / "test_fraud_engine.sqlite3"

os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB_FILE.as_posix()}"
os.environ["NOTIFICATIONS_ENABLED"] = "false"
os.environ["DB_INIT_RETRIES"] = "1"
os.environ["DB_INIT_RETRY_DELAY"] = "0"
os.environ["LOG_LEVEL"] = "WARNING"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.database.session import Base, SessionLocal, engine, get_db  # noqa: E402
from app.fraud_engine.base import TransactionData  # noqa: E402
from app.services.notification_service import NotificationResult  # noqa: E402


# --------------------------------------------------------------------- helpers
def utcnow() -> datetime:
    return datetime.now(timezone.utc)



@pytest.fixture(scope="session", autouse=True)
def _prepare_database():
    """Create the schema once per session and delete the SQLite file after."""
    Base.metadata.create_all(bind=engine)
    yield
    engine.dispose()
    if TEST_DB_FILE.exists():
        TEST_DB_FILE.unlink()


@pytest.fixture(autouse=True)
def _clean_tables():
    """Start every test from an empty database."""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield


@pytest.fixture()
def db_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def client():
    """A TestClient wired to the isolated SQLite database."""
    from main import app

    def _override_get_db():
        session = SessionLocal()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture()
def make_transaction():
    """Factory producing :class:`TransactionData` snapshots for rule tests."""

    def _make(
        account_id: str = "ACC-TEST",
        amount: float = 100.0,
        timestamp: Optional[datetime] = None,
        latitude: Optional[float] = None,
        longitude: Optional[float] = None,
        location: Optional[str] = None,
        transaction_id: Optional[int] = None,
        minutes_ago: Optional[float] = None,
    ) -> TransactionData:
        if timestamp is None:
            timestamp = utcnow() - timedelta(minutes=minutes_ago or 0)
        return TransactionData(
            id=transaction_id,
            account_id=account_id,
            amount=amount,
            timestamp=timestamp,
            latitude=latitude,
            longitude=longitude,
            location=location,
        )

    return _make


class SpyNotifier:
    """Test double that records every SNS publish attempt."""

    def __init__(self, published: bool = True, error: Optional[str] = None) -> None:
        self.published = published
        self.error = error
        self.calls: List[Dict[str, Any]] = []
        self.enabled = True

    def publish_fraud_alert(self, transaction: Any, flag: Any) -> NotificationResult:
        self.calls.append({"transaction": transaction, "flag": flag})
        return NotificationResult(self.published, message_id="spy-message-id", error=self.error)

    def ensure_topic(self) -> str:
        return "arn:aws:sns:us-east-1:000000000000:fraud-alerts"

    def health(self):
        return True, "spy"


@pytest.fixture()
def spy_notifier():
    return SpyNotifier()

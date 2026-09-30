"""Reusable test helpers."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fraud_engine.interfaces import RuleContext
from fraud_engine.models import Transaction


BASE_TIME = datetime(2026, 1, 15, 12, 0, tzinfo=UTC)


def transaction(
    transaction_id: str,
    *,
    user_id: str = "user-1",
    amount: float = 100,
    timestamp: datetime = BASE_TIME,
    latitude: float = 12.9716,
    longitude: float = 77.5946,
) -> Transaction:
    return Transaction(
        transaction_id=transaction_id,
        user_id=user_id,
        amount=amount,
        currency="INR",
        timestamp=timestamp,
        latitude=latitude,
        longitude=longitude,
        merchant="Test merchant",
    )


def context(
    *,
    recent: tuple[Transaction, ...] = (),
    previous: Transaction | None = None,
    average: float | None = None,
) -> RuleContext:
    return RuleContext(
        recent_transactions=recent,
        previous_transaction=previous,
        historical_average_amount=average,
    )


def minutes_before(minutes: float) -> datetime:
    return BASE_TIME - timedelta(minutes=minutes)

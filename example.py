"""Run three local fraud assessments with the automatically discovered rules."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fraud_engine.discovery import build_discovered_engine
from fraud_engine.models import RiskAssessment, Transaction
from fraud_engine.repositories.memory import InMemoryTransactionRepository


NOW = datetime(2026, 1, 15, 12, 0, tzinfo=UTC)


def make_transaction(
    transaction_id: str,
    *,
    amount: float,
    timestamp: datetime,
    latitude: float = 12.9716,
    longitude: float = 77.5946,
) -> Transaction:
    return Transaction(
        transaction_id=transaction_id,
        user_id="demo-user",
        amount=amount,
        currency="INR",
        timestamp=timestamp,
        latitude=latitude,
        longitude=longitude,
        merchant="Demo merchant",
    )


def print_assessment(label: str, assessment: RiskAssessment) -> None:
    print(f"\n{label}")
    print(f"Risk score: {assessment.risk_score:g}")
    print(f"High risk: {assessment.high_risk}")
    if not assessment.triggered_rules:
        print("Triggered rules: none")
    for result in assessment.triggered_rules:
        print(f"- {result.rule_name}: {result.reason}")


def normal_transaction_example() -> RiskAssessment:
    repository = InMemoryTransactionRepository()
    repository.save(make_transaction("normal-history", amount=1_000, timestamp=NOW - timedelta(days=1)))
    engine = build_discovered_engine(repository)
    return engine.evaluate(make_transaction("normal-current", amount=1_100, timestamp=NOW))


def suspicious_transaction_example() -> RiskAssessment:
    repository = InMemoryTransactionRepository()
    repository.save(make_transaction("amount-history", amount=1_000, timestamp=NOW - timedelta(days=1)))
    engine = build_discovered_engine(repository)
    return engine.evaluate(make_transaction("amount-current", amount=5_000, timestamp=NOW))


def high_risk_transaction_example() -> RiskAssessment:
    repository = InMemoryTransactionRepository()
    for index in range(4):
        repository.save(
            make_transaction(
                f"rapid-history-{index}",
                amount=100,
                timestamp=NOW - timedelta(minutes=4 - index),
                latitude=40.7128,
                longitude=-74.0060,
            )
        )
    engine = build_discovered_engine(repository)
    return engine.evaluate(
        make_transaction(
            "high-risk-current",
            amount=500,
            timestamp=NOW,
            latitude=35.6762,
            longitude=139.6503,
        )
    )


if __name__ == "__main__":
    print_assessment("Normal transaction", normal_transaction_example())
    print_assessment("Suspicious transaction", suspicious_transaction_example())
    print_assessment("High-risk transaction", high_risk_transaction_example())

"""Rule 1 - Transaction velocity.

Flags an account that fires too many transactions inside a short time window.
Thresholds are injected through the constructor / settings, never hardcoded.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from app.fraud_engine.base import (
    EvaluationContext,
    FraudRule,
    RuleResult,
    TransactionData,
    ensure_aware,
)
from app.fraud_engine.registry import register_rule


@register_rule
class TransactionVelocityRule(FraudRule):
    """More than ``max_transactions`` transactions within ``window_minutes``."""

    name = "transaction_velocity"
    description = (
        "Flags accounts creating more than N transactions inside a rolling "
        "time window (N and the window are configurable)."
    )

    def __init__(
        self,
        max_transactions: int = 5,
        window_minutes: int = 10,
        score: int = 30,
    ) -> None:
        self.max_transactions = int(max_transactions)
        self.window_minutes = int(window_minutes)
        self.score = int(score)

    @classmethod
    def from_settings(cls, settings: Any) -> "TransactionVelocityRule":
        return cls(
            max_transactions=settings.velocity_max_transactions,
            window_minutes=settings.velocity_window_minutes,
            score=settings.velocity_score,
        )

    def evaluate(
        self, transaction: TransactionData, context: EvaluationContext
    ) -> RuleResult:
        moment = ensure_aware(transaction.timestamp)
        window_start = moment - timedelta(minutes=self.window_minutes)

        # The window is measured relative to the transaction being evaluated,
        # which keeps seeded demo data deterministic.
        recent = [
            entry
            for entry in context.for_account(transaction.account_id)
            if window_start <= ensure_aware(entry.timestamp) <= moment
        ]
        total = len(recent) + 1  # never forget the transaction itself

        details = {
            "transactions_in_window": total,
            "max_transactions": self.max_transactions,
            "window_minutes": self.window_minutes,
            "window_start": window_start.isoformat(),
            "transaction_timestamp": moment.isoformat(),
        }

        if total > self.max_transactions:
            return RuleResult.hit(
                rule=self.name,
                reason=(
                    f"{total} transactions within {self.window_minutes} minutes "
                    f"(limit {self.max_transactions})"
                ),
                score=self.score,
                details=details,
            )

        return RuleResult.clear(
            rule=self.name,
            reason=(
                f"{total} transactions within {self.window_minutes} minutes "
                f"(limit {self.max_transactions})"
            ),
            details=details,
        )

    def describe(self) -> dict:
        info = super().describe()
        info.update(
            {
                "max_transactions": self.max_transactions,
                "window_minutes": self.window_minutes,
                "score": self.score,
            }
        )
        return info

"""Rule 2 - Unusual transaction amount.

A deliberately *simple demonstration* rule: compare the current amount with the
account's own historical average. It is NOT a real banking fraud model - see the
README ("Fraud rules" / "Design decisions").
"""

from __future__ import annotations

from typing import Any, List

from app.fraud_engine.base import (
    EvaluationContext,
    FraudRule,
    RuleResult,
    TransactionData,
    ensure_aware,
)
from app.fraud_engine.registry import register_rule


@register_rule
class UnusualAmountRule(FraudRule):
    """Flags amounts larger than ``multiplier`` x the historical average."""

    name = "unusual_amount"
    description = (
        "Flags a transaction whose amount exceeds a configurable multiple of "
        "the account's historical average amount (simplified demo rule)."
    )

    def __init__(
        self,
        multiplier: float = 10.0,
        min_history: int = 3,
        history_limit: int = 50,
        score: int = 30,
    ) -> None:
        self.multiplier = float(multiplier)
        self.min_history = int(min_history)
        self.history_limit = int(history_limit)
        self.score = int(score)

    @classmethod
    def from_settings(cls, settings: Any) -> "UnusualAmountRule":
        return cls(
            multiplier=settings.amount_multiplier,
            min_history=settings.amount_min_history,
            history_limit=settings.amount_history_limit,
            score=settings.amount_score,
        )

    def _history(
        self, transaction: TransactionData, context: EvaluationContext
    ) -> List[TransactionData]:
        moment = ensure_aware(transaction.timestamp)
        entries = [
            entry
            for entry in context.for_account(transaction.account_id)
            if ensure_aware(entry.timestamp) <= moment
        ]
        return entries[-self.history_limit :]

    def evaluate(
        self, transaction: TransactionData, context: EvaluationContext
    ) -> RuleResult:
        history = self._history(transaction, context)

        if len(history) < self.min_history:
            return RuleResult.clear(
                rule=self.name,
                reason=(
                    f"Only {len(history)} previous transactions for this account "
                    f"(need at least {self.min_history} to compute a baseline)"
                ),
                details={
                    "historical_average": None,
                    "current_amount": round(transaction.amount, 2),
                    "history_sample_size": len(history),
                    "min_history": self.min_history,
                    "multiplier": self.multiplier,
                },
            )

        average = sum(entry.amount for entry in history) / len(history)
        if average <= 0:
            return RuleResult.clear(
                rule=self.name,
                reason="Historical average amount is zero - nothing to compare against",
                details={
                    "historical_average": round(average, 2),
                    "current_amount": round(transaction.amount, 2),
                    "history_sample_size": len(history),
                    "multiplier": self.multiplier,
                },
            )

        ratio = transaction.amount / average
        details = {
            "historical_average": round(average, 2),
            "current_amount": round(transaction.amount, 2),
            "ratio_to_average": round(ratio, 2),
            "multiplier": self.multiplier,
            "history_sample_size": len(history),
        }

        if ratio > self.multiplier:
            return RuleResult.hit(
                rule=self.name,
                reason=(
                    f"Amount {transaction.amount:,.2f} is {ratio:.1f}x the historical "
                    f"average of {average:,.2f} (limit {self.multiplier:g}x)"
                ),
                score=self.score,
                details=details,
            )

        return RuleResult.clear(
            rule=self.name,
            reason=(
                f"Amount {transaction.amount:,.2f} is {ratio:.1f}x the historical "
                f"average of {average:,.2f} (limit {self.multiplier:g}x)"
            ),
            details=details,
        )

    def describe(self) -> dict:
        info = super().describe()
        info.update(
            {
                "multiplier": self.multiplier,
                "min_history": self.min_history,
                "score": self.score,
            }
        )
        return info

"""Transaction-velocity fraud rule."""

from __future__ import annotations

from datetime import timedelta
from math import isfinite

from ..interfaces import Rule, RuleContext
from ..models import RuleResult, Transaction
from ..registry import register_rule


@register_rule
class VelocityRule(Rule):
    """Flag a transaction when too many payments occur in a short window.

    The count includes the transaction currently being assessed plus historical
    transactions in the configured window.  The current item is not expected in
    ``RuleContext`` because the engine builds the context before saving it.
    """

    RULE_ID = "transaction_velocity"

    def __init__(
        self,
        *,
        window_minutes: float = 10,
        max_transactions: int = 5,
        score: float = 30,
    ) -> None:
        if not isinstance(window_minutes, (int, float)) or not isfinite(window_minutes):
            raise ValueError("window_minutes must be a finite number")
        if window_minutes <= 0:
            raise ValueError("window_minutes must be greater than zero")
        if not isinstance(max_transactions, int) or isinstance(max_transactions, bool):
            raise ValueError("max_transactions must be an integer")
        if max_transactions <= 0:
            raise ValueError("max_transactions must be greater than zero")
        if not isinstance(score, (int, float)) or not isfinite(score) or score < 0:
            raise ValueError("score must be a non-negative finite number")
        self._window = timedelta(minutes=window_minutes)
        self._max_transactions = max_transactions
        self._score = float(score)

    @property
    def rule_id(self) -> str:
        return self.RULE_ID

    @property
    def name(self) -> str:
        return "Transaction velocity"

    def evaluate(self, transaction: Transaction, context: RuleContext) -> RuleResult:
        window_start = transaction.timestamp - self._window
        prior_count = sum(
            1
            for item in context.recent_transactions
            if item.user_id == transaction.user_id
            and window_start <= item.timestamp < transaction.timestamp
        )
        transaction_count = prior_count + 1
        triggered = transaction_count >= self._max_transactions
        reason = (
            f"{transaction_count} transactions (including current) occurred within "
            f"the last {self._window.total_seconds() / 60:g} minutes"
        )
        if not triggered:
            reason = (
                f"Velocity normal: {transaction_count} transactions (including current) "
                f"within the last {self._window.total_seconds() / 60:g} minutes"
            )
        return RuleResult(
            rule_id=self.rule_id,
            rule_name=self.name,
            triggered=triggered,
            score=self._score if triggered else 0,
            reason=reason,
        )

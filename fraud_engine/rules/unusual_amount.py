"""Historical-average transaction-amount fraud rule."""

from __future__ import annotations

from math import isfinite

from ..interfaces import Rule, RuleContext
from ..models import RuleResult, Transaction
from ..registry import register_rule


@register_rule
class UnusualAmountRule(Rule):
    """Flag amounts that strictly exceed a configurable historical multiplier."""

    RULE_ID = "unusual_transaction_amount"

    def __init__(self, *, multiplier: float = 3.0, score: float = 25) -> None:
        if not isinstance(multiplier, (int, float)) or not isfinite(multiplier):
            raise ValueError("multiplier must be a finite number")
        if multiplier <= 0:
            raise ValueError("multiplier must be greater than zero")
        if not isinstance(score, (int, float)) or not isfinite(score) or score < 0:
            raise ValueError("score must be a non-negative finite number")
        self._multiplier = float(multiplier)
        self._score = float(score)

    @property
    def rule_id(self) -> str:
        return self.RULE_ID

    @property
    def name(self) -> str:
        return "Unusual transaction amount"

    def evaluate(self, transaction: Transaction, context: RuleContext) -> RuleResult:
        average = context.historical_average_amount
        if average is None or average <= 0:
            return RuleResult(
                rule_id=self.rule_id,
                rule_name=self.name,
                triggered=False,
                score=0,
                reason="Insufficient positive transaction history for an amount baseline",
            )
        ratio = transaction.amount / average
        triggered = transaction.amount > self._multiplier * average
        if triggered:
            reason = f"Transaction amount {ratio:.1f}x exceeds historical average"
        else:
            reason = (
                f"Transaction amount is {ratio:.1f}x historical average; "
                f"threshold is {self._multiplier:g}x"
            )
        return RuleResult(
            rule_id=self.rule_id,
            rule_name=self.name,
            triggered=triggered,
            score=self._score if triggered else 0,
            reason=reason,
        )

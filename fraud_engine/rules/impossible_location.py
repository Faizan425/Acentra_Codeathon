"""Geographical-impossibility fraud rule."""

from __future__ import annotations

from math import isfinite

from ..geo import haversine_distance_km
from ..interfaces import Rule, RuleContext
from ..models import RuleResult, Transaction
from ..registry import register_rule


@register_rule
class ImpossibleLocationRule(Rule):
    """Flag travel whose required speed exceeds a realistic configured limit."""

    RULE_ID = "impossible_geographical_location"

    def __init__(self, *, max_speed_kmh: float = 900, score: float = 45) -> None:
        if not isinstance(max_speed_kmh, (int, float)) or not isfinite(max_speed_kmh):
            raise ValueError("max_speed_kmh must be a finite number")
        if max_speed_kmh <= 0:
            raise ValueError("max_speed_kmh must be greater than zero")
        if not isinstance(score, (int, float)) or not isfinite(score) or score < 0:
            raise ValueError("score must be a non-negative finite number")
        self._max_speed_kmh = float(max_speed_kmh)
        self._score = float(score)

    @property
    def rule_id(self) -> str:
        return self.RULE_ID

    @property
    def name(self) -> str:
        return "Impossible geographical location"

    def evaluate(self, transaction: Transaction, context: RuleContext) -> RuleResult:
        previous = context.previous_transaction
        if previous is None:
            return self._not_triggered("No previous transaction is available for location comparison")
        elapsed_seconds = (transaction.timestamp - previous.timestamp).total_seconds()
        if elapsed_seconds <= 0:
            return self._not_triggered("Previous transaction is not earlier than current transaction")
        distance_km = haversine_distance_km(
            previous.latitude,
            previous.longitude,
            transaction.latitude,
            transaction.longitude,
        )
        required_speed = distance_km / (elapsed_seconds / 3_600)
        triggered = required_speed > self._max_speed_kmh
        if triggered:
            reason = (
                f"Travel requires {required_speed:.0f} km/h across {distance_km:.1f} km, "
                f"exceeding the {self._max_speed_kmh:g} km/h limit"
            )
        else:
            reason = (
                f"Travel requires {required_speed:.0f} km/h, within the "
                f"{self._max_speed_kmh:g} km/h limit"
            )
        return RuleResult(
            rule_id=self.rule_id,
            rule_name=self.name,
            triggered=triggered,
            score=self._score if triggered else 0,
            reason=reason,
        )

    def _not_triggered(self, reason: str) -> RuleResult:
        return RuleResult(
            rule_id=self.rule_id,
            rule_name=self.name,
            triggered=False,
            score=0,
            reason=reason,
        )

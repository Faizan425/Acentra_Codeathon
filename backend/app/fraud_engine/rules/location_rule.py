"""Rule 3 - Impossible geographical location ("impossible travel").

Compares the current transaction with the most recent *located* transaction of
the same account. If the implied travel speed exceeds a configurable limit (or
two distant locations are recorded at the same instant) the rule fires.
"""

from __future__ import annotations

from typing import Any, Optional

from app.fraud_engine.base import (
    EvaluationContext,
    FraudRule,
    RuleResult,
    TransactionData,
    ensure_aware,
)
from app.fraud_engine.geo import haversine_km
from app.fraud_engine.registry import register_rule


@register_rule
class ImpossibleTravelRule(FraudRule):
    """Flags physically impossible travel between consecutive transactions."""

    name = "impossible_location"
    description = (
        "Flags consecutive transactions whose implied travel speed exceeds a "
        "configurable maximum (Haversine distance / elapsed time)."
    )

    def __init__(
        self,
        max_speed_kmh: float = 1000.0,
        min_distance_km: float = 1.0,
        score: int = 40,
    ) -> None:
        self.max_speed_kmh = float(max_speed_kmh)
        self.min_distance_km = float(min_distance_km)
        self.score = int(score)

    @classmethod
    def from_settings(cls, settings: Any) -> "ImpossibleTravelRule":
        return cls(
            max_speed_kmh=settings.max_travel_speed_kmh,
            min_distance_km=settings.location_min_distance_km,
            score=settings.location_score,
        )

    # ---------------------------------------------------------------- helpers
    @staticmethod
    def _format_elapsed(elapsed_seconds: float) -> str:
        if elapsed_seconds <= 0:
            return "no time difference"
        if elapsed_seconds < 90:
            return f"{elapsed_seconds:.0f} seconds"
        minutes = elapsed_seconds / 60.0
        if minutes < 90:
            return f"{minutes:.1f} minutes"
        return f"{minutes / 60.0:.1f} hours"

    def _base_details(
        self, previous: TransactionData, transaction: TransactionData
    ) -> dict:
        return {
            "previous_location": previous.location,
            "previous_latitude": previous.latitude,
            "previous_longitude": previous.longitude,
            "previous_timestamp": ensure_aware(previous.timestamp).isoformat(),
            "current_location": transaction.location,
            "current_latitude": transaction.latitude,
            "current_longitude": transaction.longitude,
            "max_speed_kmh": self.max_speed_kmh,
            "min_distance_km": self.min_distance_km,
        }

    # -------------------------------------------------------------- execution
    def evaluate(
        self, transaction: TransactionData, context: EvaluationContext
    ) -> RuleResult:
        moment = ensure_aware(transaction.timestamp)

        if not transaction.has_coordinates():
            return RuleResult.clear(
                rule=self.name,
                reason="Transaction has no coordinates - travel cannot be evaluated",
                details={"coordinates_present": False, "max_speed_kmh": self.max_speed_kmh},
            )

        previous: Optional[TransactionData] = context.most_recent_located(
            not_after=moment, account_id=transaction.account_id
        )
        if previous is None:
            return RuleResult.clear(
                rule=self.name,
                reason="No earlier located transaction for this account to compare with",
                details={"coordinates_present": True, "max_speed_kmh": self.max_speed_kmh},
            )

        distance_km = haversine_km(
            previous.latitude, previous.longitude, transaction.latitude, transaction.longitude
        )
        elapsed_seconds = (moment - ensure_aware(previous.timestamp)).total_seconds()
        details = self._base_details(previous, transaction)
        details.update(
            {
                "distance_km": round(distance_km, 2),
                "elapsed_seconds": round(elapsed_seconds, 3),
                "elapsed_human": self._format_elapsed(elapsed_seconds),
            }
        )

        if distance_km <= self.min_distance_km:
            details["speed_kmh"] = 0.0 if elapsed_seconds > 0 else None
            return RuleResult.clear(
                rule=self.name,
                reason=(
                    f"Only {distance_km:.2f} km from the previous transaction "
                    f"(below the {self.min_distance_km:g} km noise threshold)"
                ),
                details=details,
            )

        if elapsed_seconds <= 0:
            # Same (or out of order) timestamp but far apart -> impossible.
            details["speed_kmh"] = None
            return RuleResult.hit(
                rule=self.name,
                reason=(
                    f"{distance_km:,.0f} km apart with no time difference "
                    f"({previous.location or 'previous point'} -> "
                    f"{transaction.location or 'current point'})"
                ),
                score=self.score,
                details=details,
            )

        speed_kmh = distance_km / (elapsed_seconds / 3600.0)
        details["speed_kmh"] = round(speed_kmh, 1)

        if speed_kmh > self.max_speed_kmh:
            return RuleResult.hit(
                rule=self.name,
                reason=(
                    f"Implied travel speed {speed_kmh:,.0f} km/h over "
                    f"{distance_km:,.0f} km in {self._format_elapsed(elapsed_seconds)} "
                    f"(max {self.max_speed_kmh:,.0f} km/h)"
                ),
                score=self.score,
                details=details,
            )

        return RuleResult.clear(
            rule=self.name,
            reason=(
                f"Implied travel speed {speed_kmh:,.0f} km/h is within the "
                f"{self.max_speed_kmh:,.0f} km/h limit"
            ),
            details=details,
        )

    def describe(self) -> dict:
        info = super().describe()
        info.update(
            {
                "max_speed_kmh": self.max_speed_kmh,
                "min_distance_km": self.min_distance_km,
                "score": self.score,
            }
        )
        return info


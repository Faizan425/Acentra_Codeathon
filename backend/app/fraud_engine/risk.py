"""Risk aggregation policy - turns a total score into a risk level."""

from __future__ import annotations

from dataclasses import dataclass

from app.models.status import HIGH, LOW, MEDIUM


@dataclass(frozen=True)
class RiskPolicy:
    """Configurable score -> level mapping.

    The demo thresholds (0-29 LOW, 30-59 MEDIUM, 60+ HIGH) are *illustrative*
    values for this prototype, not real banking standards.
    """

    medium_threshold: int = 30
    high_threshold: int = 60

    def level_for(self, score: int) -> str:
        if score >= self.high_threshold:
            return HIGH
        if score >= self.medium_threshold:
            return MEDIUM
        return LOW

    def to_dict(self) -> dict:
        return {
            "low": f"0-{self.medium_threshold - 1}",
            "medium": f"{self.medium_threshold}-{self.high_threshold - 1}",
            "high": f"{self.high_threshold}+",
            "medium_threshold": self.medium_threshold,
            "high_threshold": self.high_threshold,
        }

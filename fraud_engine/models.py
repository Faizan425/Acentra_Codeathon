"""Domain models shared by the fraud engine and its rules."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from math import isfinite
from typing import final


def _require_non_empty(value: str, field_name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")


@dataclass(frozen=True, slots=True)
class Transaction:
    """A validated, timezone-aware payment transaction."""

    transaction_id: str
    user_id: str
    amount: float
    currency: str
    timestamp: datetime
    latitude: float
    longitude: float
    merchant: str

    def __post_init__(self) -> None:
        for field_name in ("transaction_id", "user_id", "currency", "merchant"):
            _require_non_empty(getattr(self, field_name), field_name)
        if not isinstance(self.amount, (int, float)) or not isfinite(self.amount):
            raise ValueError("amount must be a finite number")
        if self.amount < 0:
            raise ValueError("amount cannot be negative")
        if not isinstance(self.timestamp, datetime) or self.timestamp.tzinfo is None:
            raise ValueError("timestamp must be a timezone-aware datetime")
        if self.timestamp.utcoffset() is None:
            raise ValueError("timestamp must include a UTC offset")
        validate_coordinates(self.latitude, self.longitude)


def validate_coordinates(latitude: float, longitude: float) -> None:
    """Raise ``ValueError`` when coordinates are outside their valid ranges."""

    if not isinstance(latitude, (int, float)) or not isfinite(latitude):
        raise ValueError("latitude must be a finite number")
    if not isinstance(longitude, (int, float)) or not isfinite(longitude):
        raise ValueError("longitude must be a finite number")
    if not -90 <= latitude <= 90:
        raise ValueError("latitude must be between -90 and 90")
    if not -180 <= longitude <= 180:
        raise ValueError("longitude must be between -180 and 180")


@dataclass(frozen=True, slots=True)
class RuleResult:
    """The independently computed outcome of one rule."""

    rule_id: str
    rule_name: str
    triggered: bool
    score: float
    reason: str

    def __post_init__(self) -> None:
        _require_non_empty(self.rule_id, "rule_id")
        _require_non_empty(self.rule_name, "rule_name")
        if not isinstance(self.score, (int, float)) or not isfinite(self.score):
            raise ValueError("score must be a finite number")
        if self.score < 0:
            raise ValueError("score cannot be negative")
        if not isinstance(self.reason, str):
            raise ValueError("reason must be a string")


@final
@dataclass(frozen=True, slots=True)
class RiskAssessment:
    """Aggregate assessment produced after every injected rule is evaluated."""

    transaction_id: str
    risk_score: float
    high_risk: bool
    triggered_rules: tuple[RuleResult, ...]
    evaluated_rules: tuple[RuleResult, ...]

    def __post_init__(self) -> None:
        _require_non_empty(self.transaction_id, "transaction_id")
        if not 0 <= self.risk_score <= 100:
            raise ValueError("risk_score must be between 0 and 100")

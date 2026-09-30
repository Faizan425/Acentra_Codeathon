"""Core contracts for the fraud rule engine.

This module deliberately contains **no** rule specific logic. It only defines:

* :class:`TransactionData` - a storage agnostic view of a transaction,
* :class:`RuleResult`      - the structured answer every rule must return,
* :class:`EvaluationContext` - extra information a rule may inspect (history),
* :class:`FraudRule`       - the interface every rule plugin implements.

Any developer can add a new rule by subclassing :class:`FraudRule`; the engine
itself never needs to change.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Sequence


def ensure_aware(value: Optional[datetime]) -> Optional[datetime]:
    """Return a timezone aware datetime (naive values are assumed to be UTC)."""
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


@dataclass(frozen=True)
class TransactionData:
    """Immutable snapshot of a transaction handed to every rule.

    Rules never touch the ORM model directly, which keeps them trivial to unit
    test (build a ``TransactionData`` by hand) and free of database concerns.
    """

    account_id: str
    amount: float
    timestamp: datetime
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    location: Optional[str] = None
    id: Optional[int] = None

    def has_coordinates(self) -> bool:
        return self.latitude is not None and self.longitude is not None

    @classmethod
    def from_model(cls, transaction: Any) -> "TransactionData":
        """Build a snapshot from an ORM ``Transaction`` instance."""
        return cls(
            id=getattr(transaction, "id", None),
            account_id=transaction.account_id,
            amount=float(transaction.amount),
            timestamp=ensure_aware(transaction.timestamp) or datetime.now(timezone.utc),
            latitude=transaction.latitude,
            longitude=transaction.longitude,
            location=transaction.location,
        )


@dataclass
class RuleResult:
    """Structured verdict returned by a single rule."""

    rule: str
    triggered: bool
    reason: str
    score: int = 0
    details: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def hit(
        cls,
        rule: str,
        reason: str,
        score: int,
        details: Optional[Dict[str, Any]] = None,
    ) -> "RuleResult":
        """A rule was violated and contributes ``score`` risk points."""
        return cls(rule=rule, triggered=True, reason=reason, score=score, details=details or {})

    @classmethod
    def clear(
        cls, rule: str, reason: str, details: Optional[Dict[str, Any]] = None
    ) -> "RuleResult":
        """A rule was evaluated but not violated (contributes 0 points)."""
        return cls(rule=rule, triggered=False, reason=reason, score=0, details=details or {})

    def to_dict(self) -> Dict[str, Any]:
        return {
            "rule": self.rule,
            "triggered": self.triggered,
            "reason": self.reason,
            "score": self.score if self.triggered else 0,
            "details": self.details,
        }


@dataclass
class EvaluationContext:
    """Everything a rule may look at besides the transaction under evaluation."""

    #: Previous transactions of the *same account*, ordered oldest -> newest.
    history: Sequence[TransactionData] = field(default_factory=tuple)
    evaluated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    attributes: Dict[str, Any] = field(default_factory=dict)

    def located_history(
        self, not_after: Optional[datetime] = None, account_id: Optional[str] = None
    ) -> list:
        """History entries that carry coordinates, oldest first."""
        entries = [entry for entry in self.history if entry.has_coordinates()]
        if account_id is not None:
            entries = [entry for entry in entries if entry.account_id == account_id]
        if not_after is not None:
            cutoff = ensure_aware(not_after)
            entries = [entry for entry in entries if entry.timestamp <= cutoff]
        return entries

    def most_recent_located(
        self, not_after: Optional[datetime] = None, account_id: Optional[str] = None
    ) -> Optional[TransactionData]:
        """The latest located transaction at or before ``not_after``."""
        entries = self.located_history(not_after, account_id)
        return entries[-1] if entries else None

    def for_account(self, account_id: str) -> list:
        """History entries belonging to a single account, oldest first.

        The service already loads per-account history, but rules stay defensive
        so they behave correctly no matter how they are called.
        """
        return [entry for entry in self.history if entry.account_id == account_id]


class FraudRule(ABC):
    """Common interface implemented by every fraud rule plugin.

    A rule must be *independent*: it receives the transaction plus the shared
    context and returns a :class:`RuleResult`. It must not mutate shared state
    and must not assume that any other rule ran before it.

    Subclasses usually also implement :meth:`from_settings` so the registry can
    build them from application configuration without knowing anything about
    their constructor.
    """

    #: Stable identifier stored on the fraud flag and shown in the console.
    name: str = "unnamed_rule"
    #: Short human readable summary shown in the reviewer console.
    description: str = ""

    @abstractmethod
    def evaluate(
        self, transaction: TransactionData, context: EvaluationContext
    ) -> RuleResult:
        """Evaluate one transaction and return a structured verdict."""
        raise NotImplementedError

    @classmethod
    def from_settings(cls, settings: Any) -> "FraudRule":
        """Build the rule from application settings (no-arg by default)."""
        return cls()

    def describe(self) -> Dict[str, Any]:
        return {"name": self.name, "description": self.description}

"""Abstractions that keep rules independent of storage infrastructure."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from .models import RuleResult, Transaction


@dataclass(frozen=True, slots=True)
class RuleContext:
    """Historical facts prepared by the engine before rules are evaluated.

    ``recent_transactions`` contains transactions for the current user strictly
    earlier than the transaction being assessed.  A rule applies its own time
    window, so the context remains reusable by independently added rules.
    """

    recent_transactions: tuple[Transaction, ...]
    previous_transaction: Transaction | None
    historical_average_amount: float | None


class Rule(ABC):
    """Contract for a pluggable, storage-agnostic fraud rule."""

    @property
    @abstractmethod
    def rule_id(self) -> str:
        """Stable identifier used by the registry and assessment output."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable rule name."""

    @abstractmethod
    def evaluate(self, transaction: Transaction, context: RuleContext) -> RuleResult:
        """Evaluate a transaction from supplied facts only."""

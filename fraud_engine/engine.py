"""The storage-agnostic orchestrator for injected fraud rules."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime
from math import isfinite

from .interfaces import Rule, RuleContext
from .models import RiskAssessment, Transaction
from .repositories.base import TransactionRepository


class RuleEngine:
    """Evaluate injected rules against a context assembled from a repository.

    The transaction is persisted only after all rules have seen history that
    excludes it.  This prevents a transaction from changing its own velocity or
    amount baseline while retaining it for subsequent assessments.
    """

    def __init__(
        self,
        repository: TransactionRepository,
        rules: Iterable[Rule],
        *,
        high_risk_threshold: float = 70,
    ) -> None:
        if not isinstance(high_risk_threshold, (int, float)) or not isfinite(high_risk_threshold):
            raise ValueError("high_risk_threshold must be a finite number")
        if not 0 <= high_risk_threshold <= 100:
            raise ValueError("high_risk_threshold must be between 0 and 100")
        self._repository = repository
        self._rules = tuple(rules)
        rule_ids = [rule.rule_id for rule in self._rules]
        if len(rule_ids) != len(set(rule_ids)):
            raise ValueError("Injected rules must have unique rule_id values")
        self._high_risk_threshold = float(high_risk_threshold)

    @property
    def rules(self) -> tuple[Rule, ...]:
        """The injected rules, in their deterministic evaluation order."""

        return self._rules

    def build_context(self, transaction: Transaction) -> RuleContext:
        """Build generic historical facts; no rule queries storage directly."""

        history = self._repository.get_user_transactions(transaction.user_id)
        historical_transactions = tuple(
            item for item in history if item.timestamp < transaction.timestamp
        )
        previous = self._repository.get_previous_transaction(
            transaction.user_id, transaction.timestamp
        )
        average = _historical_average(historical_transactions)
        return RuleContext(
            recent_transactions=historical_transactions,
            previous_transaction=previous,
            historical_average_amount=average,
        )

    def evaluate(self, transaction: Transaction) -> RiskAssessment:
        """Evaluate all rules and store the assessed transaction for later use."""

        context = self.build_context(transaction)
        results = tuple(rule.evaluate(transaction, context) for rule in self._rules)
        triggered = tuple(result for result in results if result.triggered)
        total_score = min(sum(result.score for result in triggered), 100.0)
        assessment = RiskAssessment(
            transaction_id=transaction.transaction_id,
            risk_score=total_score,
            high_risk=total_score >= self._high_risk_threshold,
            triggered_rules=triggered,
            evaluated_rules=results,
        )
        self._repository.save(transaction)
        return assessment


def _historical_average(transactions: tuple[Transaction, ...]) -> float | None:
    if not transactions:
        return None
    return sum(item.amount for item in transactions) / len(transactions)

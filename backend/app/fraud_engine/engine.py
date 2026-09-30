"""Rule agnostic fraud engine.

The engine knows how to *run* rules and *aggregate* their results. It contains
no per-rule thresholds and no rule specific branching - adding a rule never
requires touching this file.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence

from app.fraud_engine.base import (
    EvaluationContext,
    FraudRule,
    RuleResult,
    TransactionData,
)
from app.fraud_engine.risk import RiskPolicy

logger = logging.getLogger(__name__)


@dataclass
class EngineResult:
    """Aggregated verdict for one transaction."""

    risk_score: int
    risk_level: str
    triggered_rules: List[str] = field(default_factory=list)
    reasons: List[str] = field(default_factory=list)
    rule_details: List[Dict[str, Any]] = field(default_factory=list)
    results: List[RuleResult] = field(default_factory=list)
    evaluated_rules: List[str] = field(default_factory=list)

    @property
    def is_flagged(self) -> bool:
        """A transaction is flagged as soon as any rule contributes points."""
        return self.risk_score > 0

    def failed_rules(self) -> List[str]:
        return [result.rule for result in self.results if result.details.get("_error")]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "risk_score": self.risk_score,
            "risk_level": self.risk_level,
            "triggered_rules": list(self.triggered_rules),
            "reasons": list(self.reasons),
            "rule_details": list(self.rule_details),
        }


class FraudEngine:
    """Runs a collection of independent rules over a transaction."""

    def __init__(
        self, rules: Optional[Sequence[FraudRule]] = None, risk_policy: Optional[RiskPolicy] = None
    ) -> None:
        self._rules: List[FraudRule] = list(rules or [])
        self.risk_policy = risk_policy or RiskPolicy()

    # ------------------------------------------------------------------ setup
    @property
    def rules(self) -> tuple:
        return tuple(self._rules)

    def register(self, rule: FraudRule) -> FraudRule:
        """Add a rule at runtime (used by the plugin registry and tests)."""
        self._rules.append(rule)
        return rule

    def rule_names(self) -> List[str]:
        return [rule.name for rule in self._rules]

    def describe_rules(self) -> List[Dict[str, Any]]:
        return [rule.describe() for rule in self._rules]

    # -------------------------------------------------------------- execution
    def evaluate(
        self,
        transaction: TransactionData,
        context: Optional[EvaluationContext] = None,
    ) -> EngineResult:
        """Run every rule independently and aggregate the verdicts."""
        context = context or EvaluationContext()

        results: List[RuleResult] = []
        for rule in self._rules:
            try:
                result = rule.evaluate(transaction, context)
                if not isinstance(result, RuleResult):
                    raise TypeError(
                        f"rule '{rule.name}' returned {type(result).__name__}, "
                        "expected RuleResult"
                    )
            except Exception as exc:  # a broken plugin must not break the engine
                logger.exception("Fraud rule %s failed: %s", rule.name, exc)
                result = RuleResult.clear(
                    rule=rule.name,
                    reason=f"rule could not be evaluated: {exc.__class__.__name__}",
                    details={"_error": str(exc)},
                )
            results.append(result)

        triggered = [result for result in results if result.triggered]
        risk_score = sum(result.score for result in triggered)
        risk_level = self.risk_policy.level_for(risk_score)

        return EngineResult(
            risk_score=risk_score,
            risk_level=risk_level,
            triggered_rules=[result.rule for result in triggered],
            reasons=[result.reason for result in triggered],
            rule_details=[result.to_dict() for result in results],
            results=results,
            evaluated_rules=[rule.name for rule in self._rules],
        )

"""Tests for generic engine orchestration and risk aggregation."""

from __future__ import annotations

from conftest import transaction
from fraud_engine.engine import RuleEngine
from fraud_engine.interfaces import Rule, RuleContext
from fraud_engine.models import RuleResult, Transaction
from fraud_engine.repositories.memory import InMemoryTransactionRepository


class StaticRule(Rule):
    def __init__(self, rule_id: str, triggered: bool, score: float) -> None:
        self._rule_id = rule_id
        self._triggered = triggered
        self._score = score

    @property
    def rule_id(self) -> str:
        return self._rule_id

    @property
    def name(self) -> str:
        return self._rule_id.replace("_", " ")

    def evaluate(self, transaction: Transaction, context: RuleContext) -> RuleResult:
        return RuleResult(
            self.rule_id,
            self.name,
            self._triggered,
            self._score if self._triggered else 0,
            "static test result",
        )


def test_engine_aggregates_only_triggered_rules_and_persists_transaction() -> None:
    repository = InMemoryTransactionRepository()
    engine = RuleEngine(
        repository,
        [StaticRule("first", True, 30), StaticRule("second", False, 50), StaticRule("third", True, 25)],
    )

    assessment = engine.evaluate(transaction("current"))

    assert assessment.risk_score == 55
    assert not assessment.high_risk
    assert [result.rule_id for result in assessment.triggered_rules] == ["first", "third"]
    assert len(assessment.evaluated_rules) == 3
    assert repository.get_user_transactions("user-1")[0].transaction_id == "current"


def test_engine_caps_score_at_100() -> None:
    engine = RuleEngine(
        InMemoryTransactionRepository(),
        [StaticRule("first", True, 80), StaticRule("second", True, 80)],
    )

    assessment = engine.evaluate(transaction("current"))

    assert assessment.risk_score == 100
    assert assessment.high_risk


def test_engine_honours_configurable_high_risk_threshold() -> None:
    engine = RuleEngine(
        InMemoryTransactionRepository(), [StaticRule("only", True, 45)], high_risk_threshold=40
    )

    assert engine.evaluate(transaction("current")).high_risk

"""Tests for rule registration and extension without engine modification."""

from __future__ import annotations

from fraud_engine.discovery import load_discovered_rules
from fraud_engine.interfaces import Rule, RuleContext
from fraud_engine.models import RuleResult, Transaction
from fraud_engine.registry import register_rule, registered_rule_classes


@register_rule
class DummyTestRule(Rule):
    """A test-only rule deliberately added without touching RuleEngine."""

    @property
    def rule_id(self) -> str:
        return "dummy_test_rule"

    @property
    def name(self) -> str:
        return "Dummy test rule"

    def evaluate(self, transaction: Transaction, context: RuleContext) -> RuleResult:
        return RuleResult(self.rule_id, self.name, True, 7, "Test extension was evaluated")


def test_decorated_rule_is_registered_and_loaded_without_engine_changes() -> None:
    rules = load_discovered_rules()

    assert "dummy_test_rule" in registered_rule_classes()
    assert any(rule.rule_id == "dummy_test_rule" for rule in rules)

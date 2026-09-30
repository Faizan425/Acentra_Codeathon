"""Tests for package scanning and built-in rule discovery."""

from __future__ import annotations

import importlib
import sys

from conftest import context, minutes_before, transaction
from fraud_engine.discovery import discover_rules, load_discovered_rules
from fraud_engine.registry import registered_rule_classes


def test_builtin_rule_modules_are_discovered() -> None:
    modules = discover_rules()
    registered = registered_rule_classes()

    assert "fraud_engine.rules.velocity" in modules
    assert "fraud_engine.rules.unusual_amount" in modules
    assert "fraud_engine.rules.impossible_location" in modules
    assert {
        "transaction_velocity",
        "unusual_transaction_amount",
        "impossible_geographical_location",
    }.issubset(registered)


def test_discovery_scans_a_new_rules_package_without_code_changes(tmp_path, monkeypatch) -> None:
    package_name = "temporary_discovered_rules"
    package = tmp_path / package_name
    package.mkdir()
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "custom.py").write_text(
        "from fraud_engine.interfaces import Rule, RuleContext\n"
        "from fraud_engine.models import RuleResult, Transaction\n"
        "from fraud_engine.registry import register_rule\n"
        "@register_rule\n"
        "class TemporaryRule(Rule):\n"
        "    RULE_ID = 'temporary_discovered_rule'\n"
        "    @property\n"
        "    def rule_id(self): return self.RULE_ID\n"
        "    @property\n"
        "    def name(self): return 'Temporary rule'\n"
        "    def evaluate(self, transaction: Transaction, context: RuleContext):\n"
        "        return RuleResult(self.rule_id, self.name, False, 0, 'ok')\n",
        encoding="utf-8",
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    importlib.invalidate_caches()

    modules = discover_rules(package_name)

    assert f"{package_name}.custom" in modules
    assert "temporary_discovered_rule" in registered_rule_classes()
    sys.modules.pop(f"{package_name}.custom", None)
    sys.modules.pop(package_name, None)


def test_discovered_rules_accept_configuration() -> None:
    rules = load_discovered_rules({"transaction_velocity": {"max_transactions": 2, "score": 9}})
    velocity = next(rule for rule in rules if rule.rule_id == "transaction_velocity")

    result = velocity.evaluate(
        transaction("current"), context(recent=(transaction("prior", timestamp=minutes_before(1)),))
    )

    assert result.triggered
    assert result.score == 9

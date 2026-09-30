"""Fraud engine tests - aggregation, risk levels and rule extensibility."""

from __future__ import annotations

import inspect

from app.fraud_engine.base import EvaluationContext, FraudRule, RuleResult
from app.fraud_engine.engine import FraudEngine
from app.fraud_engine.registry import (
    build_rules,
    discover_rule_classes,
    register_rule,
    registered_rule_classes,
)
from app.fraud_engine.risk import RiskPolicy

from tests.conftest import utcnow


class StaticRule(FraudRule):
    """Test rule returning a fixed verdict."""

    def __init__(self, name: str, score: int, triggered: bool):
        self.name = name
        self.score = score
        self.triggered = triggered

    def evaluate(self, transaction, context):  # noqa: D102
        if self.triggered:
            return RuleResult.hit(
                self.name, f"{self.name} fired", self.score, {"score": self.score}
            )
        return RuleResult.clear(self.name, f"{self.name} did not fire")


class BrokenRule(FraudRule):
    name = "broken_rule"

    def evaluate(self, transaction, context):  # noqa: D102
        raise RuntimeError("boom")


def _transaction(make_transaction):
    return make_transaction(amount=100.0, timestamp=utcnow())


# ------------------------------------------------------------------ aggregation
def test_no_rule_triggers_gives_low_risk(make_transaction):
    engine = FraudEngine([StaticRule("a", 30, False), StaticRule("b", 40, False)])
    result = engine.evaluate(_transaction(make_transaction), EvaluationContext())

    assert result.risk_score == 0
    assert result.risk_level == "LOW"
    assert result.triggered_rules == []
    assert result.is_flagged is False


def test_multiple_rules_trigger_and_scores_aggregate(make_transaction):
    engine = FraudEngine([StaticRule("a", 30, True), StaticRule("b", 40, True)])
    result = engine.evaluate(_transaction(make_transaction), EvaluationContext())

    assert result.risk_score == 70
    assert result.risk_level == "HIGH"
    assert sorted(result.triggered_rules) == ["a", "b"]
    assert len(result.reasons) == 2
    assert result.is_flagged is True


def test_risk_level_boundaries():
    policy = RiskPolicy(medium_threshold=30, high_threshold=60)

    assert policy.level_for(0) == "LOW"
    assert policy.level_for(29) == "LOW"
    assert policy.level_for(30) == "MEDIUM"
    assert policy.level_for(59) == "MEDIUM"
    assert policy.level_for(60) == "HIGH"
    assert policy.level_for(100) == "HIGH"


def test_single_trigger_is_medium_risk(make_transaction):
    engine = FraudEngine([StaticRule("a", 30, True)])
    result = engine.evaluate(_transaction(make_transaction), EvaluationContext())

    assert result.risk_level == "MEDIUM"


def test_rule_details_are_preserved_for_every_rule(make_transaction):
    engine = FraudEngine([StaticRule("a", 30, True), StaticRule("b", 40, False)])
    result = engine.evaluate(_transaction(make_transaction), EvaluationContext())

    stored = {entry["rule"]: entry for entry in result.rule_details}
    assert stored["a"]["triggered"] is True
    assert stored["a"]["score"] == 30
    assert stored["b"]["triggered"] is False
    assert stored["b"]["score"] == 0


# ------------------------------------------------------------------- robustness
def test_a_broken_rule_does_not_break_the_engine(make_transaction):
    engine = FraudEngine([BrokenRule(), StaticRule("good", 30, True)])
    result = engine.evaluate(_transaction(make_transaction), EvaluationContext())

    assert result.risk_score == 30
    assert result.triggered_rules == ["good"]
    assert result.rule_details[0]["rule"] == "broken_rule"
    assert result.rule_details[0]["triggered"] is False


def test_engine_runs_every_rule_independently(make_transaction):
    calls = []

    class RecordingRule(FraudRule):
        def __init__(self, name):
            self.name = name

        def evaluate(self, transaction, context):
            calls.append(self.name)
            return RuleResult.clear(self.name, "ok")

    engine = FraudEngine([RecordingRule("first"), RecordingRule("second")])
    engine.evaluate(_transaction(make_transaction), EvaluationContext())

    assert calls == ["first", "second"]


# ---------------------------------------------------------------- extensibility
def test_engine_source_has_no_concrete_rule_logic():
    """Regression guard: the engine must stay rule agnostic."""
    from app.fraud_engine import engine as engine_module

    source = inspect.getsource(engine_module).lower()
    for forbidden in [
        "velocity",
        "unusual_amount",
        "impossible_location",
        "haversine",
        "multiplier",
        "window_minutes",
        "max_speed_kmh",
    ]:
        assert forbidden not in source, f"engine.py must not reference '{forbidden}'"


def test_new_rule_can_be_added_without_touching_the_engine(make_transaction):
    """Simulates a future developer adding ``NewDeviceRule``."""

    @register_rule
    class NewDeviceRule(FraudRule):
        name = "new_device"

        def __init__(self, score: int = 25):
            self.score = score

        def evaluate(self, transaction, context):
            return RuleResult.hit(
                self.name, "First transaction from an unknown device", self.score
            )

    engine = FraudEngine([NewDeviceRule()])
    result = engine.evaluate(_transaction(make_transaction), EvaluationContext())

    assert result.risk_score == 25
    assert result.risk_level == "LOW"  # small score contributions are possible
    assert result.triggered_rules == ["new_device"]


def test_registry_discovers_the_packaged_rules():
    classes = discover_rule_classes()
    names = {cls.name for cls in classes}

    assert {"transaction_velocity", "unusual_amount", "impossible_location"} <= names


def test_build_rules_uses_from_settings_hooks():
    settings = type(
        "FakeSettings",
        (),
        {
            "velocity_max_transactions": 3,
            "velocity_window_minutes": 2,
            "velocity_score": 30,
            "amount_multiplier": 5.0,
            "amount_min_history": 2,
            "amount_history_limit": 10,
            "amount_score": 30,
            "max_travel_speed_kmh": 900.0,
            "location_min_distance_km": 1.0,
            "location_score": 40,
        },
    )()

    rules = build_rules(settings)
    by_name = {rule.name: rule for rule in rules}

    assert by_name["transaction_velocity"].max_transactions == 3
    assert by_name["transaction_velocity"].window_minutes == 2
    assert by_name["unusual_amount"].multiplier == 5.0
    assert by_name["impossible_location"].max_speed_kmh == 900.0


def test_registered_rule_classes_are_unique():
    discover_rule_classes()
    discover_rule_classes()
    names = [cls.name for cls in registered_rule_classes()]

    assert len(names) == len(set(names))


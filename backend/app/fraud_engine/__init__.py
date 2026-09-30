"""Extensible fraud rule engine (rule agnostic core + pluggable rules)."""

from app.fraud_engine.base import (
    EvaluationContext,
    FraudRule,
    RuleResult,
    TransactionData,
    ensure_aware,
)
from app.fraud_engine.engine import EngineResult, FraudEngine
from app.fraud_engine.registry import (
    build_rules,
    discover_rule_classes,
    register_rule,
    registered_rule_classes,
    reset_registry,
)
from app.fraud_engine.risk import RiskPolicy

__all__ = [
    "EvaluationContext",
    "FraudRule",
    "RuleResult",
    "TransactionData",
    "EngineResult",
    "FraudEngine",
    "RiskPolicy",
    "register_rule",
    "registered_rule_classes",
    "discover_rule_classes",
    "build_rules",
    "reset_registry",
    "ensure_aware",
]


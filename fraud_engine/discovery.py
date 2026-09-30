"""Automatic import-based rule discovery and composition-root helpers."""

from __future__ import annotations

import importlib
import pkgutil
from collections.abc import Mapping
from typing import Any

from .engine import RuleEngine
from .interfaces import Rule
from .registry import instantiate_registered_rules
from .repositories.base import TransactionRepository


def discover_rules(package_name: str = "fraud_engine.rules") -> tuple[str, ...]:
    """Import every module within a rules package, allowing decorators to run.

    New modules added under the package are found by ``pkgutil``.  The engine is
    deliberately not involved in this process.
    """

    package = importlib.import_module(package_name)
    if not hasattr(package, "__path__"):
        raise ValueError(f"{package_name!r} is not a package")
    module_names = tuple(
        module.name
        for module in pkgutil.iter_modules(package.__path__, f"{package.__name__}.")
    )
    for module_name in module_names:
        importlib.import_module(module_name)
    return module_names


def load_discovered_rules(
    configurations: Mapping[str, Mapping[str, Any]] | None = None,
) -> tuple[Rule, ...]:
    """Discover installed rules and construct new configured instances."""

    discover_rules()
    return instantiate_registered_rules(configurations)


def build_discovered_engine(
    repository: TransactionRepository,
    *,
    rule_configurations: Mapping[str, Mapping[str, Any]] | None = None,
    high_risk_threshold: float = 70,
) -> RuleEngine:
    """Composition root for applications that want all discovered rules."""

    return RuleEngine(
        repository=repository,
        rules=load_discovered_rules(rule_configurations),
        high_risk_threshold=high_risk_threshold,
    )

"""Rule plugin registry and discovery.

Extensibility in three lines:

1. create ``app/fraud_engine/rules/my_new_rule.py``,
2. decorate the class with ``@register_rule``,
3. done - :func:`discover_rule_classes` imports every module inside the
   ``rules`` package, so the new rule is picked up automatically.

The engine and this registry never import a concrete rule class.
"""

from __future__ import annotations

import importlib
import logging
import pkgutil
from typing import Any, List, Optional, Type

from app.fraud_engine.base import FraudRule

logger = logging.getLogger(__name__)

RULES_PACKAGE = "app.fraud_engine.rules"

_REGISTERED_RULES: List[Type[FraudRule]] = []


def register_rule(rule_cls: Type[FraudRule]) -> Type[FraudRule]:
    """Class decorator that adds a rule to the plugin registry."""
    if not issubclass(rule_cls, FraudRule):
        raise TypeError(f"{rule_cls!r} must subclass FraudRule")
    if rule_cls not in _REGISTERED_RULES:
        _REGISTERED_RULES.append(rule_cls)
        logger.debug("Registered fraud rule plugin: %s", rule_cls.__name__)
    return rule_cls


def registered_rule_classes() -> List[Type[FraudRule]]:
    """All rule classes registered so far (in registration order)."""
    return list(_REGISTERED_RULES)


def reset_registry() -> None:
    """Clear the registry - used by tests to prove registration is dynamic."""
    _REGISTERED_RULES.clear()


def discover_rule_classes(package_name: str = RULES_PACKAGE) -> List[Type[FraudRule]]:
    """Import every module in the rules package and return registered classes."""
    package = importlib.import_module(package_name)
    package_path = getattr(package, "__path__", None)
    if package_path:
        for module_info in pkgutil.iter_modules(package_path):
            if module_info.name.startswith("_"):
                continue
            importlib.import_module(f"{package_name}.{module_info.name}")
    return registered_rule_classes()


def build_rules(
    settings: Any, package_name: str = RULES_PACKAGE
) -> List[FraudRule]:
    """Instantiate every discovered rule using its own ``from_settings`` hook."""
    rules: List[FraudRule] = []
    for rule_cls in discover_rule_classes(package_name):
        try:
            rules.append(rule_cls.from_settings(settings))
        except Exception:  # pragma: no cover - misconfigured plugin
            logger.exception("Could not build rule plugin %s", rule_cls.__name__)
    return rules

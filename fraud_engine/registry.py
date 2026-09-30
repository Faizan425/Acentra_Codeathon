"""Registration and construction of independently pluggable rule classes."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .interfaces import Rule


RULE_REGISTRY: dict[str, type[Rule]] = {}


def _class_rule_id(rule_class: type[Rule]) -> str:
    """Get a stable rule id without retaining a globally created instance."""

    rule_id = getattr(rule_class, "RULE_ID", None)
    if rule_id is None:
        # Supporting this fallback keeps the public Rule contract sufficient for
        # simple third-party rules whose no-argument constructor is available.
        rule_id = rule_class().rule_id
    if not isinstance(rule_id, str) or not rule_id.strip():
        raise ValueError("A registered rule must expose a non-empty rule_id")
    return rule_id


def register_rule(rule_class: type[Rule]) -> type[Rule]:
    """Decorator that registers a concrete ``Rule`` class by stable id."""

    if not isinstance(rule_class, type) or not issubclass(rule_class, Rule):
        raise TypeError("Only Rule subclasses can be registered")
    rule_id = _class_rule_id(rule_class)
    existing = RULE_REGISTRY.get(rule_id)
    if existing is not None and existing is not rule_class:
        raise ValueError(f"A rule is already registered with id {rule_id!r}")
    RULE_REGISTRY[rule_id] = rule_class
    return rule_class


def registered_rule_classes() -> dict[str, type[Rule]]:
    """Return a copy so callers cannot mutate the global registry accidentally."""

    return dict(RULE_REGISTRY)


def instantiate_registered_rules(
    configurations: Mapping[str, Mapping[str, Any]] | None = None,
) -> tuple[Rule, ...]:
    """Create fresh configured rule instances from the registered classes."""

    configurations = configurations or {}
    unknown_ids = set(configurations) - set(RULE_REGISTRY)
    if unknown_ids:
        names = ", ".join(sorted(unknown_ids))
        raise ValueError(f"Configuration supplied for unknown rule id(s): {names}")
    return tuple(
        rule_class(**dict(configurations.get(rule_id, {})))
        for rule_id, rule_class in RULE_REGISTRY.items()
    )

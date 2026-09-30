"""FastAPI dependency providers.

Keeping the engine and the notifier behind ``Depends`` makes them trivially
replaceable in tests (``app.dependency_overrides``) and guarantees a single
engine instance per process.
"""

from __future__ import annotations

from functools import lru_cache

from app.config import Settings, get_settings
from app.fraud_engine.engine import FraudEngine
from app.fraud_engine.registry import build_rules
from app.fraud_engine.risk import RiskPolicy
from app.services.notification_service import FraudNotificationService


@lru_cache(maxsize=1)
def get_fraud_engine() -> FraudEngine:
    """Build the engine from every discovered rule plugin."""
    settings: Settings = get_settings()
    policy = RiskPolicy(
        medium_threshold=settings.medium_risk_threshold,
        high_threshold=settings.high_risk_threshold,
    )
    return FraudEngine(rules=build_rules(settings), risk_policy=policy)


@lru_cache(maxsize=1)
def get_notification_service() -> FraudNotificationService:
    return FraudNotificationService(get_settings())

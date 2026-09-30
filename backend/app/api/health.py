"""Health check endpoint."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.dependencies import get_fraud_engine, get_notification_service
from app.fraud_engine.engine import FraudEngine
from app.schemas.stats import HealthResponse
from app.services.notification_service import FraudNotificationService

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/health", response_model=HealthResponse, tags=["system"])
def health_check(
    db: Session = Depends(get_db),
    engine: FraudEngine = Depends(get_fraud_engine),
    notifier: FraudNotificationService = Depends(get_notification_service),
) -> HealthResponse:
    """Reports the state of the database and the LocalStack SNS connection."""
    database_state = "up"
    try:
        db.execute(text("SELECT 1"))
    except Exception as exc:  # pragma: no cover - depends on live infra
        logger.warning("Health check: database unavailable: %s", exc)
        database_state = "down"

    notifications_ok, notification_detail = notifier.health()

    overall = "healthy" if database_state == "up" else "degraded"
    return HealthResponse(
        status=overall,
        database=database_state,
        notifications="up" if notifications_ok else "down",
        notification_detail=notification_detail,
        rules=engine.rule_names(),
    )

"""Dashboard statistics and engine introspection endpoints."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.dependencies import get_fraud_engine
from app.fraud_engine.engine import FraudEngine
from app.models.fraud_flag import FraudFlag
from app.models.status import (
    CLEARED,
    CONFIRMED_FRAUD,
    HIGH,
    MEDIUM,
    PENDING_REVIEW,
    REVIEWED,
)
from app.models.transaction import Transaction
from app.schemas.stats import DashboardSummary, EngineInfoResponse

logger = logging.getLogger(__name__)

router = APIRouter()


def _flag_count(db: Session, **filters) -> int:
    query = db.query(func.count(FraudFlag.id))
    for column, value in filters.items():
        query = query.filter(getattr(FraudFlag, column) == value)
    return int(query.scalar() or 0)


@router.get(
    "/summary",
    response_model=DashboardSummary,
    summary="Dashboard counters for the reviewer console",
)
def dashboard_summary(db: Session = Depends(get_db)) -> DashboardSummary:
    try:
        total_transactions = int(db.query(func.count(Transaction.id)).scalar() or 0)
        flagged_transactions = int(db.query(func.count(FraudFlag.id)).scalar() or 0)
        flagged_amount = float(db.query(func.coalesce(func.sum(Transaction.amount), 0))
                               .join(FraudFlag, FraudFlag.transaction_id == Transaction.id)
                               .scalar() or 0)

        return DashboardSummary(
            total_transactions=total_transactions,
            flagged_transactions=flagged_transactions,
            high_risk_transactions=_flag_count(db, risk_level=HIGH),
            medium_risk_transactions=_flag_count(db, risk_level=MEDIUM),
            pending_reviews=_flag_count(db, status=PENDING_REVIEW),
            reviewed_transactions=_flag_count(db, status=REVIEWED),
            cleared_transactions=_flag_count(db, status=CLEARED),
            confirmed_fraud=_flag_count(db, status=CONFIRMED_FRAUD),
            total_flagged_amount=round(flagged_amount, 2),
        )
    except SQLAlchemyError as exc:
        logger.exception("Database error while building the dashboard summary: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database is unavailable, please retry shortly",
        ) from exc


@router.get(
    "/engine",
    response_model=EngineInfoResponse,
    summary="List the active rule plugins and the risk policy",
)
def engine_info(engine: FraudEngine = Depends(get_fraud_engine)) -> EngineInfoResponse:
    rules = []
    for rule in engine.rules:
        described = rule.describe()
        configuration = {key: value for key, value in described.items() if key not in {"name", "description"}}
        rules.append(
            {
                "name": described.get("name", rule.name),
                "description": described.get("description", ""),
                "configuration": configuration,
            }
        )
    return EngineInfoResponse(rules=rules, risk_policy=engine.risk_policy.to_dict())

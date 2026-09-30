"""Fraud flag endpoints - the reviewer console talks to these."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, joinedload

from app.database.session import get_db
from app.dependencies import get_fraud_engine
from app.fraud_engine.engine import FraudEngine
from app.models.fraud_flag import FraudFlag
from app.models.status import (
    ALLOWED_TRANSITIONS,
    CLEARED,
    PENDING_REVIEW,
    can_transition,
    is_valid_review_status,
)
from app.models.transaction import Transaction
from app.schemas.fraud_flag import (
    ClearRequest,
    FraudFlagDetail,
    FraudFlagListResponse,
    FraudFlagRead,
    ReviewRequest,
    ReviewResponse,
)
from app.schemas.transaction import TransactionRead

logger = logging.getLogger(__name__)

router = APIRouter()


# --------------------------------------------------------------------- helpers
def _get_flag_or_404(db: Session, flag_id: int) -> FraudFlag:
    flag = (
        db.query(FraudFlag)
        .options(joinedload(FraudFlag.transaction))
        .filter(FraudFlag.id == flag_id)
        .one_or_none()
    )
    if flag is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Fraud flag {flag_id} was not found",
        )
    return flag


def _change_status(db: Session, flag: FraudFlag, target: str, reviewer: Optional[str]) -> FraudFlag:
    """Validate and apply a review status transition, then persist it."""
    if not is_valid_review_status(target):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"'{target}' is not a valid review status. "
                f"Allowed values: {sorted(ALLOWED_TRANSITIONS)}"
            ),
        )

    if not can_transition(flag.status, target):
        allowed = sorted(ALLOWED_TRANSITIONS.get(flag.status, frozenset()))
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Cannot move fraud flag {flag.id} from {flag.status} to {target}. "
                f"Allowed transitions: {allowed}"
            ),
        )

    flag.status = target
    if target == PENDING_REVIEW:
        flag.reviewed_at = None
        flag.reviewed_by = None
    else:
        flag.reviewed_at = datetime.now(timezone.utc)
        flag.reviewed_by = reviewer or flag.reviewed_by or "console-reviewer"

    try:
        db.add(flag)
        db.commit()
        db.refresh(flag)
    except SQLAlchemyError as exc:
        db.rollback()
        logger.exception("Could not update fraud flag %s: %s", flag.id, exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database is unavailable, please retry shortly",
        ) from exc

    return flag


# ------------------------------------------------------------------- endpoints
@router.get(
    "",
    response_model=FraudFlagListResponse,
    summary="List flagged transactions for the reviewer console",
)
def list_fraud_flags(
    db: Session = Depends(get_db),
    status_filter: Optional[str] = Query(
        default=None, alias="status", description="PENDING_REVIEW | REVIEWED | CLEARED | CONFIRMED_FRAUD"
    ),
    risk_level: Optional[str] = Query(default=None, description="LOW | MEDIUM | HIGH"),
    account_id: Optional[str] = Query(default=None, max_length=64),
    min_score: Optional[int] = Query(default=None, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> FraudFlagListResponse:
    try:
        query = db.query(FraudFlag).options(joinedload(FraudFlag.transaction))

        if status_filter:
            query = query.filter(FraudFlag.status == status_filter)
        if risk_level:
            query = query.filter(FraudFlag.risk_level == risk_level)
        if min_score is not None:
            query = query.filter(FraudFlag.risk_score >= min_score)
        if account_id:
            query = query.join(Transaction).filter(Transaction.account_id == account_id)

        total = query.count()
        rows = (
            query.order_by(FraudFlag.risk_score.desc(), FraudFlag.created_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )
    except SQLAlchemyError as exc:
        logger.exception("Database error while listing fraud flags: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database is unavailable, please retry shortly",
        ) from exc

    return FraudFlagListResponse(
        total=total,
        limit=limit,
        offset=offset,
        items=[FraudFlagRead.model_validate(row) for row in rows],
    )


@router.get(
    "/{flag_id}",
    response_model=FraudFlagDetail,
    summary="Full fraud flag detail incl. per-rule explanation and history",
)
def get_fraud_flag(
    flag_id: int,
    db: Session = Depends(get_db),
    engine: FraudEngine = Depends(get_fraud_engine),
) -> FraudFlagDetail:
    flag = _get_flag_or_404(db, flag_id)

    history: List[TransactionRead] = []
    if flag.transaction is not None:
        rows = (
            db.query(Transaction)
            .filter(
                Transaction.account_id == flag.transaction.account_id,
                Transaction.id != flag.transaction.id,
            )
            .order_by(Transaction.timestamp.desc(), Transaction.id.desc())
            .limit(10)
            .all()
        )
        history = [TransactionRead.model_validate(row) for row in rows]

    payload: Dict[str, Any] = {
        "id": flag.id,
        "transaction_id": flag.transaction_id,
        "risk_score": flag.risk_score,
        "risk_level": flag.risk_level,
        "triggered_rules": list(flag.triggered_rules or []),
        "reasons": list(flag.reasons or []),
        "rule_details": list(flag.rule_details or []),
        "status": flag.status,
        "reviewed_at": flag.reviewed_at,
        "reviewed_by": flag.reviewed_by,
        "alert_published": bool(flag.alert_published),
        "alert_error": flag.alert_error,
        "created_at": flag.created_at,
        "transaction": (
            TransactionRead.model_validate(flag.transaction) if flag.transaction else None
        ),
        "history": history,
        "risk_policy": engine.risk_policy.to_dict(),
        "allowed_transitions": sorted(ALLOWED_TRANSITIONS.get(flag.status, frozenset())),
    }
    return FraudFlagDetail.model_validate(payload)


@router.patch(
    "/{flag_id}/review",
    response_model=ReviewResponse,
    summary="Mark a flagged transaction as reviewed (or confirmed fraud)",
)
def review_fraud_flag(
    flag_id: int,
    payload: ReviewRequest,
    db: Session = Depends(get_db),
) -> ReviewResponse:
    flag = _get_flag_or_404(db, flag_id)
    previous = flag.status
    flag = _change_status(db, flag, payload.status, payload.reviewer)
    return ReviewResponse(
        flag=FraudFlagRead.model_validate(flag),
        previous_status=previous,
        message=f"Fraud flag {flag.id} moved from {previous} to {flag.status}",
    )


@router.patch(
    "/{flag_id}/clear",
    response_model=ReviewResponse,
    summary="Clear a flagged transaction (reviewer decided it is legitimate)",
)
def clear_fraud_flag(
    flag_id: int,
    payload: Optional[ClearRequest] = None,
    db: Session = Depends(get_db),
) -> ReviewResponse:
    flag = _get_flag_or_404(db, flag_id)
    previous = flag.status
    reviewer = payload.reviewer if payload else None
    flag = _change_status(db, flag, CLEARED, reviewer)
    return ReviewResponse(
        flag=FraudFlagRead.model_validate(flag),
        previous_status=previous,
        message=f"Fraud flag {flag.id} cleared (was {previous})",
    )

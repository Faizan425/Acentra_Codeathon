"""Transaction endpoints."""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.dependencies import get_fraud_engine, get_notification_service
from app.fraud_engine.engine import FraudEngine
from app.models.fraud_flag import FraudFlag
from app.models.transaction import Transaction
from app.schemas.transaction import (
    TransactionCreate,
    TransactionCreatedResponse,
    TransactionListResponse,
    TransactionRead,
)
from app.services.fraud_service import create_transaction
from app.services.notification_service import FraudNotificationService

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post(
    "",
    response_model=TransactionCreatedResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a transaction and evaluate it against every fraud rule",
)
def create_new_transaction(
    payload: TransactionCreate,
    db: Session = Depends(get_db),
    engine: FraudEngine = Depends(get_fraud_engine),
    notifier: FraudNotificationService = Depends(get_notification_service),
) -> TransactionCreatedResponse:
    try:
        transaction, result, flag = create_transaction(
            db,
            account_id=payload.account_id,
            amount=payload.amount,
            timestamp=payload.timestamp,
            latitude=payload.latitude,
            longitude=payload.longitude,
            location=payload.location,
            engine=engine,
            notifier=notifier,
        )
    except SQLAlchemyError as exc:
        db.rollback()
        logger.exception("Database error while creating transaction: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database is unavailable, please retry shortly",
        ) from exc

    return TransactionCreatedResponse(
        transaction=TransactionRead.model_validate(transaction),
        evaluation=result.to_dict(),
        fraud_flag=flag.to_dict(include_transaction=False) if flag else None,
        alert_published=bool(flag.alert_published) if flag else False,
        alert_error=flag.alert_error if flag else None,
    )


@router.get(
    "",
    response_model=TransactionListResponse,
    summary="List transactions (optionally only the flagged ones)",
)
def list_transactions(
    db: Session = Depends(get_db),
    account_id: Optional[str] = Query(default=None, max_length=64),
    flagged: Optional[bool] = Query(
        default=None, description="true = only flagged, false = only unflagged"
    ),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> TransactionListResponse:
    try:
        query = db.query(Transaction)
        if account_id:
            query = query.filter(Transaction.account_id == account_id)
        if flagged is True:
            query = query.join(FraudFlag, FraudFlag.transaction_id == Transaction.id)
        elif flagged is False:
            query = query.outerjoin(FraudFlag, FraudFlag.transaction_id == Transaction.id).filter(
                FraudFlag.id.is_(None)
            )

        total = query.count()
        rows = (
            query.order_by(Transaction.timestamp.desc(), Transaction.id.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )
    except SQLAlchemyError as exc:
        logger.exception("Database error while listing transactions: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database is unavailable, please retry shortly",
        ) from exc

    return TransactionListResponse(
        total=total,
        limit=limit,
        offset=offset,
        items=[TransactionRead.model_validate(row) for row in rows],
    )


@router.get(
    "/{transaction_id}",
    response_model=TransactionRead,
    summary="Fetch a single transaction",
)
def get_transaction(transaction_id: int, db: Session = Depends(get_db)) -> TransactionRead:
    transaction = db.get(Transaction, transaction_id)
    if transaction is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Transaction {transaction_id} was not found",
        )
    return TransactionRead.model_validate(transaction)

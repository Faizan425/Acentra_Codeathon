"""Business logic: evaluate a transaction and persist the outcome.

This is the only place that knows how to glue the ORM, the rule engine and the
notification service together. The API layer stays thin because of it.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import List, Optional, Sequence, Tuple

from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.fraud_engine.base import EvaluationContext, TransactionData, ensure_aware
from app.fraud_engine.engine import EngineResult, FraudEngine
from app.models.fraud_flag import FraudFlag
from app.models.status import HIGH, PENDING_REVIEW
from app.models.transaction import Transaction
from app.services.notification_service import FraudNotificationService

logger = logging.getLogger(__name__)


def load_account_history(
    db: Session, account_id: str, moment: datetime, limit: int
) -> List[Transaction]:
    """Previous transactions of an account at (or before) ``moment``.

    Returned oldest -> newest because that is how rules reason about time.
    """
    rows = (
        db.query(Transaction)
        .filter(Transaction.account_id == account_id, Transaction.timestamp <= moment)
        .order_by(Transaction.timestamp.desc(), Transaction.id.desc())
        .limit(limit)
        .all()
    )
    return list(reversed(rows))


def history_snapshot(db: Session, account_id: str, moment: datetime, limit: int) -> List[TransactionData]:
    return [
        TransactionData.from_model(row)
        for row in load_account_history(db, account_id, moment, limit)
    ]


def create_transaction(
    db: Session,
    *,
    account_id: str,
    amount: float,
    timestamp: Optional[datetime] = None,
    latitude: Optional[float] = None,
    longitude: Optional[float] = None,
    location: Optional[str] = None,
    engine: FraudEngine,
    notifier: Optional[FraudNotificationService] = None,
    settings: Optional[Settings] = None,
) -> Tuple[Transaction, EngineResult, Optional[FraudFlag]]:
    """Persist a transaction, run the rule engine and store a fraud flag.

    Order of operations (matters for reliability):

    1. load the account history *before* inserting the new row,
    2. insert the transaction and flush to obtain its id,
    3. evaluate the rules,
    4. persist the fraud flag when any rule contributed risk,
    5. notify through SNS for HIGH risk - a failure here never rolls back 2-4.
    """
    config = settings or get_settings()
    moment = ensure_aware(timestamp) or datetime.now(timezone.utc)

    history = history_snapshot(db, account_id, moment, config.history_lookup_limit)

    transaction = Transaction(
        account_id=account_id,
        amount=amount,
        timestamp=moment,
        latitude=latitude,
        longitude=longitude,
        location=location,
    )
    db.add(transaction)
    db.flush()  # assign the primary key without committing

    context = EvaluationContext(history=history, evaluated_at=moment)
    result = engine.evaluate(TransactionData.from_model(transaction), context)

    flag: Optional[FraudFlag] = None
    if result.is_flagged:
        flag = FraudFlag(
            transaction_id=transaction.id,
            risk_score=result.risk_score,
            risk_level=result.risk_level,
            triggered_rules=result.triggered_rules,
            reasons=result.reasons,
            rule_details=result.rule_details,
            status=PENDING_REVIEW,
            alert_published=False,
        )
        db.add(flag)

    db.commit()
    db.refresh(transaction)
    if flag is not None:
        db.refresh(flag)

    # ------------------------------------------------------- high risk alert
    if flag is not None and result.risk_level == HIGH:
        service = notifier or FraudNotificationService(config)
        outcome = service.publish_fraud_alert(transaction, flag)
        flag.alert_published = outcome.published
        flag.alert_error = outcome.error
        try:
            db.commit()
            db.refresh(flag)
        except Exception as exc:  # pragma: no cover - defensive
            db.rollback()
            logger.error("Could not persist notification outcome: %s", exc)

    return transaction, result, flag

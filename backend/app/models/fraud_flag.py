"""FraudFlag ORM model - the persisted outcome of a rule-engine evaluation."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from app.database.session import Base

#: Use JSONB on PostgreSQL (indexable, efficient) and plain JSON elsewhere
#: (e.g. the SQLite database used by the test-suite).
JSONType = JSON().with_variant(JSONB, "postgresql")


class FraudFlag(Base):
    """A risk verdict produced by the fraud engine for one transaction."""

    __tablename__ = "fraud_flags"

    id = Column(Integer, primary_key=True, autoincrement=True)
    transaction_id = Column(
        Integer,
        ForeignKey("transactions.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    risk_score = Column(Integer, nullable=False, default=0)
    risk_level = Column(String(16), nullable=False, index=True)
    triggered_rules = Column(JSONType, nullable=False, default=list)
    reasons = Column(JSONType, nullable=False, default=list)
    rule_details = Column(JSONType, nullable=False, default=list)

    status = Column(String(24), nullable=False, default="PENDING_REVIEW", index=True)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    reviewed_by = Column(String(128), nullable=True)

    # Result of the LocalStack/SNS notification attempt (never hides the flag).
    alert_published = Column(Boolean, nullable=False, default=False)
    alert_error = Column(Text, nullable=True)

    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    transaction = relationship("Transaction", back_populates="fraud_flag")

    def to_dict(self, include_transaction: bool = True) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "id": self.id,
            "transaction_id": self.transaction_id,
            "risk_score": self.risk_score,
            "risk_level": self.risk_level,
            "triggered_rules": list(self.triggered_rules or []),
            "reasons": list(self.reasons or []),
            "rule_details": list(self.rule_details or []),
            "status": self.status,
            "reviewed_at": self.reviewed_at.isoformat() if self.reviewed_at else None,
            "reviewed_by": self.reviewed_by,
            "alert_published": bool(self.alert_published),
            "alert_error": self.alert_error,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
        if include_transaction and self.transaction is not None:
            payload["transaction"] = self.transaction.to_dict()
        return payload

    def __repr__(self) -> str:  # pragma: no cover - debugging helper
        return (
            f"<FraudFlag id={self.id} transaction={self.transaction_id} "
            f"score={self.risk_score} level={self.risk_level} status={self.status}>"
        )

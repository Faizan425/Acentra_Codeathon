"""Transaction ORM model."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from sqlalchemy import Column, DateTime, Float, Index, Integer, Numeric, String
from sqlalchemy.orm import relationship

from app.database.session import Base


class Transaction(Base):
    """A single monetary movement performed by an account."""

    __tablename__ = "transactions"
    __table_args__ = (
        Index("ix_transactions_account_timestamp", "account_id", "timestamp"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    account_id = Column(String(64), nullable=False, index=True)
    # Numeric is the "sensible" PostgreSQL type for money.
    amount = Column(Numeric(14, 2), nullable=False)
    timestamp = Column(DateTime(timezone=True), nullable=False, index=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    location = Column(String(128), nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    fraud_flag = relationship(
        "FraudFlag",
        back_populates="transaction",
        uselist=False,
        cascade="all, delete-orphan",
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "account_id": self.account_id,
            "amount": float(self.amount) if self.amount is not None else None,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "location": self.location,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self) -> str:  # pragma: no cover - debugging helper
        return f"<Transaction id={self.id} account={self.account_id} amount={self.amount}>"

"""Pydantic schemas for transactions.

All API input is validated here: amounts must be positive, coordinates must be
inside their valid ranges and must be supplied as a pair. The frontend can never
inject a risk score - scores are always computed on the backend.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


class TransactionCreate(BaseModel):
    """Payload accepted by ``POST /api/transactions``."""

    model_config = ConfigDict(extra="forbid")

    account_id: str = Field(min_length=1, max_length=64, examples=["ACC-1001"])
    amount: float = Field(gt=0, le=1_000_000_000, examples=[500.0])
    timestamp: Optional[datetime] = Field(
        default=None, description="ISO-8601 timestamp; defaults to 'now' in UTC"
    )
    latitude: Optional[float] = Field(default=None, ge=-90, le=90, examples=[13.0827])
    longitude: Optional[float] = Field(default=None, ge=-180, le=180, examples=[80.2707])
    location: Optional[str] = Field(default=None, max_length=128, examples=["Chennai, IN"])

    @model_validator(mode="after")
    def _coordinates_come_in_pairs(self) -> "TransactionCreate":
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("latitude and longitude must be provided together")
        return self


class TransactionRead(BaseModel):
    """A transaction as returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    account_id: str
    amount: float
    timestamp: datetime
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    location: Optional[str] = None
    created_at: Optional[datetime] = None


class TransactionListResponse(BaseModel):
    total: int
    limit: int
    offset: int
    items: List[TransactionRead]


class TransactionCreatedResponse(BaseModel):
    """Result of creating a transaction: the row plus its risk verdict."""

    transaction: TransactionRead
    evaluation: Dict[str, Any]
    fraud_flag: Optional[Dict[str, Any]] = None
    alert_published: bool = False
    alert_error: Optional[str] = None

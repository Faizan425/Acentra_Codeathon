"""Pydantic schemas for fraud flags and reviewer actions."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.transaction import TransactionRead


class RuleDetailRead(BaseModel):
    """One rule's verdict as stored on the fraud flag."""

    rule: str
    triggered: bool
    reason: str
    score: int = 0
    details: Dict[str, Any] = Field(default_factory=dict)


class FraudFlagRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    transaction_id: int
    risk_score: int
    risk_level: str
    triggered_rules: List[str] = Field(default_factory=list)
    reasons: List[str] = Field(default_factory=list)
    rule_details: List[Dict[str, Any]] = Field(default_factory=list)
    status: str
    reviewed_at: Optional[datetime] = None
    reviewed_by: Optional[str] = None
    alert_published: bool = False
    alert_error: Optional[str] = None
    created_at: Optional[datetime] = None
    transaction: Optional[TransactionRead] = None


class FraudFlagDetail(FraudFlagRead):
    """Flag plus the historical context a reviewer needs to make a decision."""

    history: List[TransactionRead] = Field(default_factory=list)
    risk_policy: Dict[str, Any] = Field(default_factory=dict)
    allowed_transitions: List[str] = Field(default_factory=list)


class FraudFlagListResponse(BaseModel):
    total: int
    limit: int
    offset: int
    items: List[FraudFlagRead]


class ReviewRequest(BaseModel):
    """Body of ``PATCH /api/fraud-flags/{id}/review``."""

    model_config = ConfigDict(extra="forbid")

    status: str = Field(default="REVIEWED", examples=["REVIEWED"])
    reviewer: Optional[str] = Field(default=None, max_length=128, examples=["alice"])


class ClearRequest(BaseModel):
    """Body of ``PATCH /api/fraud-flags/{id}/clear``."""

    model_config = ConfigDict(extra="forbid")

    reviewer: Optional[str] = Field(default=None, max_length=128, examples=["alice"])


class ReviewResponse(BaseModel):
    flag: FraudFlagRead
    previous_status: str
    message: str

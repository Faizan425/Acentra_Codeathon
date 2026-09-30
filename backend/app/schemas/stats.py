"""Dashboard / health response schemas."""

from __future__ import annotations

from typing import Any, Dict, List

from pydantic import BaseModel, Field


class DashboardSummary(BaseModel):
    """Counters rendered by the reviewer console dashboard."""

    total_transactions: int = 0
    flagged_transactions: int = 0
    high_risk_transactions: int = 0
    medium_risk_transactions: int = 0
    pending_reviews: int = 0
    reviewed_transactions: int = 0
    cleared_transactions: int = 0
    confirmed_fraud: int = 0
    total_flagged_amount: float = 0.0


class RuleInfo(BaseModel):
    name: str
    description: str = ""
    configuration: Dict[str, Any] = Field(default_factory=dict)


class EngineInfoResponse(BaseModel):
    """Describes the active rule plugins and the risk policy."""

    rules: List[RuleInfo] = Field(default_factory=list)
    risk_policy: Dict[str, Any] = Field(default_factory=dict)


class HealthResponse(BaseModel):
    status: str
    database: str
    notifications: str
    notification_detail: str = ""
    rules: List[str] = Field(default_factory=list)
    version: str = "1.0.0"

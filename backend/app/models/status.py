"""Review statuses, risk levels and the allowed status transitions.

Kept as plain string constants on purpose: they are stored verbatim in the
database, are easy to read in ``psql``/the JSON API and avoid enum/DB mapping
surprises for a hackathon-sized prototype.
"""

from __future__ import annotations

from typing import Dict, FrozenSet

# --------------------------------------------------------------------- status
PENDING_REVIEW = "PENDING_REVIEW"
REVIEWED = "REVIEWED"
CLEARED = "CLEARED"
CONFIRMED_FRAUD = "CONFIRMED_FRAUD"

ALL_REVIEW_STATUSES: FrozenSet[str] = frozenset(
    {PENDING_REVIEW, REVIEWED, CLEARED, CONFIRMED_FRAUD}
)

#: Which statuses a fraud flag may move to from its current status.
#:
#: Policy: a reviewer can always *decide* a pending flag, and can escalate a
#: ``REVIEWED`` flag to a stronger decision. A final decision (``CLEARED`` /
#: ``CONFIRMED_FRAUD``) must be reopened to ``PENDING_REVIEW`` before another
#: decision can be recorded - this keeps the review trail honest and makes the
#: transition validation visible in the API.
ALLOWED_TRANSITIONS: Dict[str, FrozenSet[str]] = {
    PENDING_REVIEW: frozenset({REVIEWED, CLEARED, CONFIRMED_FRAUD}),
    REVIEWED: frozenset({CLEARED, CONFIRMED_FRAUD, PENDING_REVIEW}),
    CLEARED: frozenset({PENDING_REVIEW}),
    CONFIRMED_FRAUD: frozenset({PENDING_REVIEW}),
}

# ---------------------------------------------------------------- risk levels
LOW = "LOW"
MEDIUM = "MEDIUM"
HIGH = "HIGH"

ALL_RISK_LEVELS: FrozenSet[str] = frozenset({LOW, MEDIUM, HIGH})


def is_valid_review_status(status: str) -> bool:
    return status in ALL_REVIEW_STATUSES


def can_transition(current: str, target: str) -> bool:
    """Return True when ``current -> target`` is an allowed status change."""
    if current == target:
        return True
    return target in ALLOWED_TRANSITIONS.get(current, frozenset())

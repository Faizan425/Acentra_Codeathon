"""Repository interface required by context-building infrastructure."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime

from ..models import Transaction


class TransactionRepository(ABC):
    """Storage boundary. Rules never receive or query this abstraction."""

    @abstractmethod
    def save(self, transaction: Transaction) -> None:
        """Store a transaction."""

    @abstractmethod
    def get_user_transactions(self, user_id: str) -> tuple[Transaction, ...]:
        """Return all transactions for one user in timestamp order."""

    @abstractmethod
    def get_recent_transactions(
        self, user_id: str, since: datetime
    ) -> tuple[Transaction, ...]:
        """Return a user's transactions on or after ``since``."""

    @abstractmethod
    def get_previous_transaction(
        self, user_id: str, before: datetime
    ) -> Transaction | None:
        """Return the latest transaction strictly before ``before``."""

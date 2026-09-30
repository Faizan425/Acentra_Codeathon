"""Simple in-memory repository suitable for local development and tests."""

from __future__ import annotations

from datetime import datetime

from ..models import Transaction
from .base import TransactionRepository


class InMemoryTransactionRepository(TransactionRepository):
    """Store transactions in ordinary dictionaries and return immutable views."""

    def __init__(self) -> None:
        self._transactions_by_user: dict[str, list[Transaction]] = {}
        self._transaction_ids: set[str] = set()

    def save(self, transaction: Transaction) -> None:
        if transaction.transaction_id in self._transaction_ids:
            raise ValueError(f"Transaction id already exists: {transaction.transaction_id!r}")
        transactions = self._transactions_by_user.setdefault(transaction.user_id, [])
        transactions.append(transaction)
        transactions.sort(key=lambda item: item.timestamp)
        self._transaction_ids.add(transaction.transaction_id)

    def get_user_transactions(self, user_id: str) -> tuple[Transaction, ...]:
        return tuple(self._transactions_by_user.get(user_id, ()))

    def get_recent_transactions(
        self, user_id: str, since: datetime
    ) -> tuple[Transaction, ...]:
        if since.tzinfo is None or since.utcoffset() is None:
            raise ValueError("since must be a timezone-aware datetime")
        return tuple(
            transaction
            for transaction in self.get_user_transactions(user_id)
            if transaction.timestamp >= since
        )

    def get_previous_transaction(
        self, user_id: str, before: datetime
    ) -> Transaction | None:
        if before.tzinfo is None or before.utcoffset() is None:
            raise ValueError("before must be a timezone-aware datetime")
        eligible = (
            transaction
            for transaction in self.get_user_transactions(user_id)
            if transaction.timestamp < before
        )
        return max(eligible, key=lambda item: item.timestamp, default=None)

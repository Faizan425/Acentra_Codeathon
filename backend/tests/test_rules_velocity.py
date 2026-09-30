"""Velocity rule tests: below / exactly at / above the configured threshold."""

from __future__ import annotations

from datetime import timedelta

from app.fraud_engine.base import EvaluationContext
from app.fraud_engine.rules.velocity_rule import TransactionVelocityRule

from tests.conftest import utcnow


def _context(history):
    return EvaluationContext(history=history)


def test_below_threshold_does_not_trigger(make_transaction):
    rule = TransactionVelocityRule(max_transactions=5, window_minutes=10, score=30)
    base = utcnow()
    # 3 previous transactions + the current one = 4 total (< 5)
    history = [
        make_transaction(amount=10, timestamp=base - timedelta(minutes=3 - i))
        for i in range(3)
    ]
    current = make_transaction(amount=10, timestamp=base)

    result = rule.evaluate(current, _context(history))

    assert result.triggered is False
    assert result.score == 0
    assert result.details["transactions_in_window"] == 4


def test_exactly_at_threshold_does_not_trigger(make_transaction):
    rule = TransactionVelocityRule(max_transactions=5, window_minutes=10, score=30)
    base = utcnow()
    # 4 previous + current = 5 total, which is still allowed.
    history = [
        make_transaction(amount=10, timestamp=base - timedelta(minutes=4 - i))
        for i in range(4)
    ]
    current = make_transaction(amount=10, timestamp=base)

    result = rule.evaluate(current, _context(history))

    assert result.triggered is False
    assert result.details["transactions_in_window"] == 5


def test_above_threshold_triggers_with_score(make_transaction):
    rule = TransactionVelocityRule(max_transactions=5, window_minutes=10, score=30)
    base = utcnow()
    # 5 previous + current = 6 total -> over the limit.
    history = [
        make_transaction(amount=10, timestamp=base - timedelta(minutes=5 - i))
        for i in range(5)
    ]
    current = make_transaction(amount=10, timestamp=base)

    result = rule.evaluate(current, _context(history))

    assert result.triggered is True
    assert result.rule == "transaction_velocity"
    assert result.score == 30
    assert "6 transactions within 10 minutes" in result.reason


def test_transactions_outside_the_window_are_ignored(make_transaction):
    rule = TransactionVelocityRule(max_transactions=2, window_minutes=10, score=30)
    base = utcnow()
    history = [
        make_transaction(amount=10, timestamp=base - timedelta(minutes=30)),
        make_transaction(amount=10, timestamp=base - timedelta(minutes=20)),
        make_transaction(amount=10, timestamp=base - timedelta(minutes=15)),
    ]
    current = make_transaction(amount=10, timestamp=base)

    result = rule.evaluate(current, _context(history))

    assert result.triggered is False
    assert result.details["transactions_in_window"] == 1


def test_other_accounts_are_not_counted(make_transaction):
    rule = TransactionVelocityRule(max_transactions=2, window_minutes=10, score=30)
    base = utcnow()
    history = [
        make_transaction(account_id="OTHER-ACCOUNT", timestamp=base - timedelta(minutes=1)),
        make_transaction(account_id="OTHER-ACCOUNT", timestamp=base - timedelta(minutes=2)),
    ]
    current = make_transaction(account_id="ACC-TEST", timestamp=base)

    result = rule.evaluate(current, _context(history))

    assert result.triggered is False


def test_thresholds_come_from_constructor_not_hardcoded(make_transaction):
    rule = TransactionVelocityRule(max_transactions=1, window_minutes=1, score=99)
    base = utcnow()
    history = [make_transaction(timestamp=base - timedelta(seconds=30))]
    current = make_transaction(timestamp=base)

    result = rule.evaluate(current, _context(history))

    assert result.triggered is True
    assert result.score == 99


def test_from_settings_reads_application_configuration():
    class FakeSettings:
        velocity_max_transactions = 7
        velocity_window_minutes = 3
        velocity_score = 11

    rule = TransactionVelocityRule.from_settings(FakeSettings())

    assert rule.max_transactions == 7
    assert rule.window_minutes == 3
    assert rule.score == 11

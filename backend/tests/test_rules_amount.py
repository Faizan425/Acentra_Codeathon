"""Amount rule tests: normal amount, unusual amount and edge cases."""

from __future__ import annotations

from datetime import timedelta

from app.fraud_engine.base import EvaluationContext
from app.fraud_engine.rules.amount_rule import UnusualAmountRule

from tests.conftest import utcnow


def _context(history):
    return EvaluationContext(history=history)


def _baseline(make_transaction, base, amount=500.0, count=4):
    return [
        make_transaction(amount=amount, timestamp=base - timedelta(days=count - i))
        for i in range(count)
    ]


def test_normal_amount_does_not_trigger(make_transaction):
    rule = UnusualAmountRule(multiplier=10.0, min_history=3, score=30)
    base = utcnow()
    history = _baseline(make_transaction, base, amount=500.0, count=4)
    current = make_transaction(amount=520.0, timestamp=base)

    result = rule.evaluate(current, _context(history))

    assert result.triggered is False
    assert result.score == 0
    assert result.details["historical_average"] == 500.0
    assert result.details["ratio_to_average"] == 1.04


def test_unusual_amount_triggers(make_transaction):
    rule = UnusualAmountRule(multiplier=10.0, min_history=3, score=30)
    base = utcnow()
    history = _baseline(make_transaction, base, amount=500.0, count=4)
    current = make_transaction(amount=50_000.0, timestamp=base)

    result = rule.evaluate(current, _context(history))

    assert result.triggered is True
    assert result.rule == "unusual_amount"
    assert result.score == 30
    assert result.details["ratio_to_average"] == 100.0
    assert "historical average" in result.reason


def test_not_enough_history_does_not_trigger(make_transaction):
    rule = UnusualAmountRule(multiplier=2.0, min_history=3, score=30)
    base = utcnow()
    history = _baseline(make_transaction, base, amount=100.0, count=2)
    current = make_transaction(amount=100_000.0, timestamp=base)

    result = rule.evaluate(current, _context(history))

    assert result.triggered is False
    assert result.details["history_sample_size"] == 2


def test_exactly_at_the_multiplier_does_not_trigger(make_transaction):
    """The rule fires only when the amount *exceeds* the multiplier."""
    rule = UnusualAmountRule(multiplier=10.0, min_history=3, score=30)
    base = utcnow()
    history = _baseline(make_transaction, base, amount=100.0, count=4)
    current = make_transaction(amount=1000.0, timestamp=base)

    result = rule.evaluate(current, _context(history))

    assert result.details["ratio_to_average"] == 10.0
    assert result.triggered is False


def test_zero_average_is_handled_without_error(make_transaction):
    rule = UnusualAmountRule(multiplier=2.0, min_history=2, score=30)
    base = utcnow()
    history = _baseline(make_transaction, base, amount=0.0, count=3)
    current = make_transaction(amount=100.0, timestamp=base)

    result = rule.evaluate(current, _context(history))

    assert result.triggered is False
    assert "zero" in result.reason.lower()


def test_future_transactions_are_not_used_as_baseline(make_transaction):
    rule = UnusualAmountRule(multiplier=2.0, min_history=1, score=30)
    base = utcnow()
    history = [
        make_transaction(amount=100.0, timestamp=base + timedelta(days=1)),
        make_transaction(amount=100.0, timestamp=base + timedelta(days=2)),
    ]
    current = make_transaction(amount=1000.0, timestamp=base)

    result = rule.evaluate(current, _context(history))

    assert result.triggered is False
    assert result.details["history_sample_size"] == 0

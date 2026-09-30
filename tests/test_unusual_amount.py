"""Unit tests for unusual transaction amounts."""

from __future__ import annotations

from conftest import context, transaction
from fraud_engine.rules.unusual_amount import UnusualAmountRule


def test_normal_amount_does_not_trigger() -> None:
    result = UnusualAmountRule().evaluate(transaction("current", amount=299), context(average=100))

    assert not result.triggered
    assert result.score == 0


def test_amount_at_threshold_does_not_trigger() -> None:
    result = UnusualAmountRule().evaluate(transaction("current", amount=300), context(average=100))

    assert not result.triggered


def test_clearly_unusual_amount_triggers() -> None:
    result = UnusualAmountRule().evaluate(transaction("current", amount=800), context(average=200))

    assert result.triggered
    assert result.score == 25
    assert "4.0x" in result.reason


def test_insufficient_history_does_not_trigger() -> None:
    result = UnusualAmountRule().evaluate(transaction("current", amount=10_000), context())

    assert not result.triggered
    assert "Insufficient" in result.reason


def test_zero_historical_average_does_not_trigger() -> None:
    result = UnusualAmountRule().evaluate(transaction("current", amount=10_000), context(average=0))

    assert not result.triggered


def test_amount_multiplier_and_score_are_configurable() -> None:
    result = UnusualAmountRule(multiplier=1.5, score=11).evaluate(
        transaction("current", amount=151), context(average=100)
    )

    assert result.triggered
    assert result.score == 11

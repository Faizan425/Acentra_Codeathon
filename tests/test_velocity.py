"""Unit tests for transaction velocity."""

from __future__ import annotations

from conftest import context, minutes_before, transaction
from fraud_engine.rules.velocity import VelocityRule


def test_velocity_below_threshold() -> None:
    current = transaction("current")
    history = tuple(transaction(f"history-{index}", timestamp=minutes_before(index + 1)) for index in range(3))

    result = VelocityRule().evaluate(current, context(recent=history))

    assert not result.triggered
    assert result.score == 0


def test_velocity_triggers_exactly_at_threshold() -> None:
    current = transaction("current")
    history = tuple(transaction(f"history-{index}", timestamp=minutes_before(index + 1)) for index in range(4))

    result = VelocityRule().evaluate(current, context(recent=history))

    assert result.triggered
    assert result.score == 30
    assert "5 transactions" in result.reason


def test_velocity_triggers_above_threshold() -> None:
    current = transaction("current")
    history = tuple(transaction(f"history-{index}", timestamp=minutes_before(index + 1)) for index in range(6))

    assert VelocityRule().evaluate(current, context(recent=history)).triggered


def test_velocity_ignores_transactions_outside_window() -> None:
    current = transaction("current")
    history = tuple(transaction(f"history-{index}", timestamp=minutes_before(11 + index)) for index in range(6))

    assert not VelocityRule().evaluate(current, context(recent=history)).triggered


def test_velocity_ignores_another_users_transactions() -> None:
    current = transaction("current")
    history = tuple(
        transaction(f"other-{index}", user_id="other-user", timestamp=minutes_before(index + 1))
        for index in range(6)
    )

    assert not VelocityRule().evaluate(current, context(recent=history)).triggered


def test_velocity_configuration_changes_threshold_and_score() -> None:
    current = transaction("current")
    history = (transaction("history", timestamp=minutes_before(1)),)

    result = VelocityRule(max_transactions=2, score=9).evaluate(current, context(recent=history))

    assert result.triggered
    assert result.score == 9

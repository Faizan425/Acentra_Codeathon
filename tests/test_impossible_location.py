"""Unit tests for impossible geographical travel."""

from __future__ import annotations

from datetime import timedelta

import pytest

from conftest import BASE_TIME, context, transaction
from fraud_engine.geo import haversine_distance_km
from fraud_engine.rules.impossible_location import ImpossibleLocationRule


def test_normal_travel_does_not_trigger() -> None:
    previous = transaction("previous", timestamp=BASE_TIME - timedelta(hours=2))
    current = transaction("current", latitude=12.9816, longitude=77.6046)

    result = ImpossibleLocationRule().evaluate(current, context(previous=previous))

    assert not result.triggered
    assert result.score == 0


def test_impossible_travel_triggers() -> None:
    previous = transaction(
        "previous", timestamp=BASE_TIME - timedelta(hours=1), latitude=40.7128, longitude=-74.006
    )
    current = transaction("current", latitude=35.6762, longitude=139.6503)

    result = ImpossibleLocationRule().evaluate(current, context(previous=previous))

    assert result.triggered
    assert result.score == 45
    assert "exceeding" in result.reason


def test_no_previous_transaction_does_not_trigger() -> None:
    result = ImpossibleLocationRule().evaluate(transaction("current"), context())

    assert not result.triggered
    assert "No previous" in result.reason


def test_same_timestamp_does_not_trigger() -> None:
    previous = transaction("previous", latitude=40.7128, longitude=-74.006)
    current = transaction("current", latitude=35.6762, longitude=139.6503)

    result = ImpossibleLocationRule().evaluate(current, context(previous=previous))

    assert not result.triggered
    assert "not earlier" in result.reason


def test_invalid_coordinates_fail_clearly() -> None:
    with pytest.raises(ValueError, match="latitude"):
        transaction("invalid", latitude=91)
    with pytest.raises(ValueError, match="longitude"):
        haversine_distance_km(0, 0, 0, 181)


def test_maximum_speed_and_score_are_configurable() -> None:
    previous = transaction("previous", timestamp=BASE_TIME - timedelta(hours=1))
    current = transaction("current", latitude=13.9716, longitude=77.5946)

    result = ImpossibleLocationRule(max_speed_kmh=50, score=16).evaluate(
        current, context(previous=previous)
    )

    assert result.triggered
    assert result.score == 16

"""Impossible travel rule tests, including zero / very small time deltas."""

from __future__ import annotations

from datetime import timedelta

from app.fraud_engine.base import EvaluationContext
from app.fraud_engine.rules.location_rule import ImpossibleTravelRule

from tests.conftest import utcnow

CHENNAI = (13.0827, 80.2707)
LONDON = (51.5074, -0.1278)
BENGALURU = (12.9716, 77.5946)


def _context(history):
    return EvaluationContext(history=history)


def test_normal_travel_does_not_trigger(make_transaction):
    rule = ImpossibleTravelRule(max_speed_kmh=1000.0)
    base = utcnow()
    history = [
        make_transaction(
            timestamp=base - timedelta(hours=8),
            latitude=CHENNAI[0],
            longitude=CHENNAI[1],
            location="Chennai, IN",
        )
    ]
    current = make_transaction(
        timestamp=base, latitude=BENGALURU[0], longitude=BENGALURU[1], location="Bengaluru, IN"
    )

    result = rule.evaluate(current, _context(history))

    assert result.triggered is False
    assert 250 < result.details["distance_km"] < 350
    assert result.details["speed_kmh"] < 100


def test_impossible_travel_triggers(make_transaction):
    rule = ImpossibleTravelRule(max_speed_kmh=1000.0, score=40)
    base = utcnow()
    history = [
        make_transaction(
            timestamp=base - timedelta(minutes=5),
            latitude=CHENNAI[0],
            longitude=CHENNAI[1],
            location="Chennai, IN",
        )
    ]
    current = make_transaction(
        timestamp=base, latitude=LONDON[0], longitude=LONDON[1], location="London, UK"
    )

    result = rule.evaluate(current, _context(history))

    assert result.triggered is True
    assert result.rule == "impossible_location"
    assert result.score == 40
    assert result.details["distance_km"] > 7000
    assert result.details["elapsed_seconds"] == 300
    assert result.details["speed_kmh"] > 1000
    assert "Implied travel speed" in result.reason


def test_fast_but_plausible_flight_does_not_trigger(make_transaction):
    """London -> New York (~5570 km) in 7.5 h is a realistic flight."""
    rule = ImpossibleTravelRule(max_speed_kmh=1000.0)
    base = utcnow()
    history = [
        make_transaction(
            timestamp=base - timedelta(hours=7, minutes=30),
            latitude=LONDON[0],
            longitude=LONDON[1],
            location="London, UK",
        )
    ]
    current = make_transaction(
        timestamp=base, latitude=40.7128, longitude=-74.0060, location="New York, US"
    )

    result = rule.evaluate(current, _context(history))

    assert result.triggered is False
    assert result.details["speed_kmh"] < 1000


def test_missing_coordinates_does_not_trigger(make_transaction):
    rule = ImpossibleTravelRule()
    base = utcnow()
    history = [
        make_transaction(
            timestamp=base - timedelta(minutes=1),
            latitude=CHENNAI[0],
            longitude=CHENNAI[1],
        )
    ]
    current = make_transaction(timestamp=base, latitude=None, longitude=None)

    result = rule.evaluate(current, _context(history))

    assert result.triggered is False
    assert "no coordinates" in result.reason.lower()


def test_no_previous_located_transaction_does_not_trigger(make_transaction):
    rule = ImpossibleTravelRule()
    base = utcnow()
    current = make_transaction(timestamp=base, latitude=CHENNAI[0], longitude=CHENNAI[1])

    result = rule.evaluate(current, _context([]))

    assert result.triggered is False
    assert "no earlier located transaction" in result.reason.lower()


def test_same_instant_different_continents_triggers(make_transaction):
    """Zero time difference + large distance must not divide by zero."""
    rule = ImpossibleTravelRule(min_distance_km=1.0)
    base = utcnow()
    history = [
        make_transaction(
            timestamp=base, latitude=CHENNAI[0], longitude=CHENNAI[1], location="Chennai"
        )
    ]
    current = make_transaction(
        timestamp=base, latitude=LONDON[0], longitude=LONDON[1], location="London"
    )

    result = rule.evaluate(current, _context(history))

    assert result.triggered is True
    assert result.details["elapsed_seconds"] == 0
    assert result.details["speed_kmh"] is None
    assert "no time difference" in result.reason


def test_tiny_time_delta_with_tiny_distance_is_noise(make_transaction):
    """GPS jitter: 200 m apart in 1 second must stay below the noise threshold."""
    rule = ImpossibleTravelRule(max_speed_kmh=1000.0, min_distance_km=1.0)
    base = utcnow()
    history = [
        make_transaction(
            timestamp=base - timedelta(seconds=1), latitude=13.0827, longitude=80.2707
        )
    ]
    current = make_transaction(timestamp=base, latitude=13.0845, longitude=80.2707)

    result = rule.evaluate(current, _context(history))

    assert result.triggered is False
    assert result.details["distance_km"] < 1.0


def test_small_time_delta_large_distance_triggers(make_transaction):
    """1 minute Chennai -> London is physically impossible."""
    rule = ImpossibleTravelRule(max_speed_kmh=1000.0)
    base = utcnow()
    history = [
        make_transaction(
            timestamp=base - timedelta(minutes=1), latitude=CHENNAI[0], longitude=CHENNAI[1]
        )
    ]
    current = make_transaction(timestamp=base, latitude=LONDON[0], longitude=LONDON[1])

    result = rule.evaluate(current, _context(history))

    assert result.triggered is True
    assert result.details["elapsed_seconds"] == 60
    assert result.details["speed_kmh"] > 100_000


def test_configurable_max_speed_is_respected(make_transaction):
    """~290 km in 10 minutes = 1700 km/h -> impossible for a 200 km/h policy."""
    rule = ImpossibleTravelRule(max_speed_kmh=200.0)
    base = utcnow()
    history = [
        make_transaction(
            timestamp=base - timedelta(minutes=10), latitude=BENGALURU[0], longitude=BENGALURU[1]
        )
    ]
    current = make_transaction(timestamp=base, latitude=CHENNAI[0], longitude=CHENNAI[1])

    result = rule.evaluate(current, _context(history))

    assert result.triggered is True
    assert result.details["max_speed_kmh"] == 200.0


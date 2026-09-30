"""Haversine helper tests."""

from __future__ import annotations

import pytest

from app.fraud_engine.geo import haversine_km, safe_speed_kmh

CHENNAI = (13.0827, 80.2707)
LONDON = (51.5074, -0.1278)


def test_distance_to_same_point_is_zero():
    assert haversine_km(*CHENNAI, *CHENNAI) == pytest.approx(0.0, abs=1e-9)


def test_known_distance_chennai_to_london():
    distance = haversine_km(*CHENNAI, *LONDON)
    # Reference great circle distance is ~8,200 km.
    assert 8000 < distance < 8400


def test_short_distance_is_accurate():
    # Chennai -> Bengaluru is roughly 290 km.
    distance = haversine_km(*CHENNAI, 12.9716, 77.5946)
    assert 250 < distance < 320


def test_invalid_coordinates_are_rejected():
    with pytest.raises(ValueError):
        haversine_km(120.0, 80.0, 13.0, 80.0)
    with pytest.raises(ValueError):
        haversine_km(13.0, 200.0, 13.0, 80.0)


def test_speed_is_infinite_for_zero_elapsed_time():
    assert safe_speed_kmh(100.0, 0.0) == float("inf")


def test_speed_calculation():
    assert safe_speed_kmh(300.0, 1.0) == pytest.approx(300.0)

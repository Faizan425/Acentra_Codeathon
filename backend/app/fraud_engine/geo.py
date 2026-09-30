"""Geospatial helpers used by geography aware fraud rules."""

from __future__ import annotations

import math

EARTH_RADIUS_KM = 6371.0088


def haversine_km(
    lat1: float, lon1: float, lat2: float, lon2: float
) -> float:
    """Great-circle distance between two coordinates, in kilometres.

    The Haversine formula is accurate enough for the "impossible travel" demo
    (sub 0.5% error) and needs no external dependency.

    Raises:
        ValueError: if any coordinate is outside its valid range.
    """
    if not (-90.0 <= lat1 <= 90.0 and -90.0 <= lat2 <= 90.0):
        raise ValueError("latitude must be between -90 and 90 degrees")
    if not (-180.0 <= lon1 <= 180.0 and -180.0 <= lon2 <= 180.0):
        raise ValueError("longitude must be between -180 and 180 degrees")

    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (
        math.sin(delta_phi / 2.0) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2
    )
    return 2.0 * EARTH_RADIUS_KM * math.asin(math.sqrt(a))


def safe_speed_kmh(distance_km: float, elapsed_hours: float) -> float:
    """Speed in km/h, returning ``math.inf`` for a zero/negative time span."""
    if elapsed_hours <= 0:
        return math.inf
    return distance_km / elapsed_hours

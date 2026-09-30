"""Small reusable geographical calculations used by location-related rules."""

from __future__ import annotations

from math import asin, cos, radians, sin, sqrt

from .models import validate_coordinates

EARTH_RADIUS_KM = 6_371.0088


def haversine_distance_km(
    latitude_a: float,
    longitude_a: float,
    latitude_b: float,
    longitude_b: float,
) -> float:
    """Calculate great-circle distance between valid coordinates in kilometres."""

    validate_coordinates(latitude_a, longitude_a)
    validate_coordinates(latitude_b, longitude_b)
    latitude_delta = radians(latitude_b - latitude_a)
    longitude_delta = radians(longitude_b - longitude_a)
    formula = sin(latitude_delta / 2) ** 2 + (
        cos(radians(latitude_a))
        * cos(radians(latitude_b))
        * sin(longitude_delta / 2) ** 2
    )
    return 2 * EARTH_RADIUS_KM * asin(sqrt(formula))

"""Minimal distance-based dispatch logic.

Swap haversine_distance for a real routing engine (OSRM / Google Maps / OR-Tools)
once you need road-accurate ETAs instead of straight-line distance.
"""
import math


def haversine_distance(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Returns distance in kilometers between two lat/lng points."""
    R = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lng2 - lng1)

    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def find_nearest_available_driver(drivers: list, delivery_lat: float, delivery_lng: float):
    """drivers: list of Driver ORM objects with current_lat/current_lng and is_available."""
    candidates = [d for d in drivers if d.is_available and d.current_lat is not None]
    if not candidates:
        return None
    return min(
        candidates,
        key=lambda d: haversine_distance(d.current_lat, d.current_lng, delivery_lat, delivery_lng),
    )

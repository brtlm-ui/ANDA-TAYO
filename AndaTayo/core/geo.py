"""
Distance helpers for "nearby" search - no GeoDjango / PostGIS needed.

- haversine_km(): plain Python, used when saving a spot (distance from WMSU).
- annotate_distance(): adds a `distance_km` column computed by the DATABASE with the same
  Haversine formula, so we can filter (within X km) and sort (nearest first) in one query.
  Works on MySQL/MariaDB and on SQLite (Django provides the math functions for both).
- bounding_box(): a cheap latitude/longitude pre-filter applied before the exact distance,
  so the database only does the trig math for spots that are roughly close.
"""
import math

from django.db.models import ExpressionWrapper, F, FloatField, Value
from django.db.models.functions import ASin, Cos, Least, Power, Radians, Sin, Sqrt

EARTH_RADIUS_KM = 6371.0088

# Western Mindanao State University, main campus (approximate - adjust if needed).
WMSU_COORDS = (6.9128, 122.0631)

# Default map view: Zamboanga City
DEFAULT_CENTER = (6.9214, 122.0790)


def haversine_km(lat1, lng1, lat2, lng2):
    """Great-circle distance between two points, in kilometres."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlmb / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(min(1.0, math.sqrt(a)))


def bounding_box(lat, lng, radius_km):
    """(min_lat, max_lat, min_lng, max_lng) of a square that contains the search circle."""
    dlat = math.degrees(radius_km / EARTH_RADIUS_KM)
    dlng = math.degrees(radius_km / (EARTH_RADIUS_KM * max(math.cos(math.radians(lat)), 1e-6)))
    return lat - dlat, lat + dlat, lng - dlng, lng + dlng


def annotate_distance(queryset, lat, lng, lat_field='latitude', lng_field='longitude'):
    """Add `distance_km` (Haversine, computed in SQL) to every row of the queryset."""
    lat_r = math.radians(lat)
    dlat = Radians(F(lat_field)) - Value(lat_r)
    dlng = Radians(F(lng_field)) - Value(math.radians(lng))
    a = (
        Power(Sin(dlat / 2), 2)
        + Cos(Value(lat_r)) * Cos(Radians(F(lat_field))) * Power(Sin(dlng / 2), 2)
    )
    # Least(..., 1) protects ASin from tiny floating-point overshoots above 1.0
    distance = Value(2 * EARTH_RADIUS_KM) * ASin(Least(Sqrt(a), Value(1.0)))
    return queryset.annotate(distance_km=ExpressionWrapper(distance, output_field=FloatField()))


def within_radius(queryset, lat, lng, radius_km):
    """Spots within `radius_km` of (lat, lng), with `distance_km`, nearest first."""
    min_lat, max_lat, min_lng, max_lng = bounding_box(lat, lng, radius_km)
    qs = queryset.filter(
        latitude__gte=min_lat, latitude__lte=max_lat,
        longitude__gte=min_lng, longitude__lte=max_lng,
    )
    return annotate_distance(qs, lat, lng).filter(distance_km__lte=radius_km).order_by('distance_km')

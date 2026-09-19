"""Geography: haversine distance, city -> lat/lng cache. Owner: Nischal.

STUB (Phase 0): resolve() returns the place unchanged; distance is a fixed guess when coords are
missing. Real cache + Nominatim lookup lands in Phase 1.
"""
import math

from app.models import Place

STATUS = "stub"


def resolve(place: Place) -> tuple[Place, list[str]]:
    return place, []


def distance_miles(a: Place, b: Place) -> float:
    if None in (a.lat, a.lng, b.lat, b.lng):
        return 250.0
    r = 3958.8
    p1, p2 = math.radians(a.lat), math.radians(b.lat)
    dp, dl = p2 - p1, math.radians(b.lng - a.lng)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(h)) * 1.2

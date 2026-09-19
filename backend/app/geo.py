"""Geography: road-mile estimates and city -> lat/lng lookup. Owner: Nischal.

- `haversine_miles`, `distance_miles`, `drive_hours` are pure math.
- `resolve()` is the ONLY function here that does I/O: it reads/writes the `data/cities.json` cache and,
  on a miss, asks Nominatim (OpenStreetMap). The network call lives in `_fetch`, which tests replace,
  so the test suite never touches the network.
"""
from __future__ import annotations

import json
import math
import re
import time
from pathlib import Path

import httpx

from app.models import Place

STATUS = "live"

EARTH_RADIUS_MI = 3958.8
ROAD_CIRCUITY = 1.2          # straight line -> road miles (estimate; say so in the pitch)
AVG_SPEED_MPH = 50.0
CACHE_PATH = Path(__file__).resolve().parents[1] / "data" / "cities.json"
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "LoadCheck/0.1 (VTHacks 14 student project)"
_HAS_STATE = re.compile(r",\s*[A-Za-z]{2}\s*$")
_last_request = 0.0


# ---- pure math ----

def haversine_miles(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lng2 - lng1)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * EARTH_RADIUS_MI * math.asin(math.sqrt(h))


def distance_miles(a: Place, b: Place) -> float:
    """Estimated road miles: straight-line distance x 1.2. Both places must already be resolved."""
    for p in (a, b):
        if p.lat is None or p.lng is None:
            raise ValueError(f"No coordinates for '{p.city}'; resolve it first (check the city and state)")
    return haversine_miles(a.lat, a.lng, b.lat, b.lng) * ROAD_CIRCUITY


def drive_hours(miles: float) -> float:
    return miles / AVG_SPEED_MPH


# ---- lookup (the only I/O) ----

def _key(city: str) -> str:
    return " ".join(city.split()).lower()


def _load_cache() -> dict[str, dict]:
    if not CACHE_PATH.exists():
        return {}
    return {_key(k): v for k, v in json.loads(CACHE_PATH.read_text()).items()}


def _save_to_cache(city: str, lat: float, lng: float) -> None:
    raw = json.loads(CACHE_PATH.read_text()) if CACHE_PATH.exists() else {}
    raw[city] = {"lat": lat, "lng": lng}
    CACHE_PATH.write_text(json.dumps(dict(sorted(raw.items())), indent=2) + "\n")


def _fetch(query: str) -> tuple[float, float] | None:
    """One Nominatim lookup: max 1 request/second, 5 s timeout. Returns None on any failure."""
    global _last_request
    wait = 1.0 - (time.monotonic() - _last_request)
    if wait > 0:
        time.sleep(wait)
    _last_request = time.monotonic()
    try:
        r = httpx.get(
            NOMINATIM_URL,
            params={"q": f"{query}, USA", "format": "json", "limit": 1},
            headers={"User-Agent": USER_AGENT},
            timeout=5.0,
        )
        r.raise_for_status()
        hits = r.json()
        return (float(hits[0]["lat"]), float(hits[0]["lon"])) if hits else None
    except (httpx.HTTPError, ValueError, KeyError, IndexError):
        return None


def resolve(place: Place) -> tuple[Place, list[str]]:
    """Fill in lat/lng for a place. Never guesses: returns a warning instead."""
    if place.lat is not None and place.lng is not None:
        return place, []
    city = " ".join(place.city.split())
    if not _HAS_STATE.search(city):
        return place, [f"State missing for {city or 'a place'}; add it as 'City, ST'"]

    hit = _load_cache().get(_key(city))
    if hit:
        return place.model_copy(update={"lat": hit["lat"], "lng": hit["lng"]}), []

    found = _fetch(city)
    if found is None:
        return place, [f"Couldn't find {city} on the map; check the spelling"]
    lat, lng = found
    _save_to_cache(city, lat, lng)
    return place.model_copy(update={"lat": lat, "lng": lng}), []

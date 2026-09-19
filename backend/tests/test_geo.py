"""geo.py: distance math, cache, Nominatim fallback (faked), warnings. Never touches the network."""
import json

import pytest

from app import geo
from app.models import Place


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    """Every test gets its own cache file and a fetcher that fails loudly if called unexpectedly."""
    cache = tmp_path / "cities.json"
    cache.write_text(json.dumps({"Richmond, VA": {"lat": 37.5407, "lng": -77.436}}))
    monkeypatch.setattr(geo, "CACHE_PATH", cache)
    monkeypatch.setattr(geo, "_fetch", lambda q: pytest.fail(f"unexpected network lookup: {q}"))
    return cache


def test_distance_is_haversine_times_1_2():
    ric = Place(city="Richmond, VA", lat=37.5407, lng=-77.436)
    clt = Place(city="Charlotte, NC", lat=35.2271, lng=-80.8431)
    straight = geo.haversine_miles(ric.lat, ric.lng, clt.lat, clt.lng)
    assert geo.haversine_miles(36.0, -80.0, 37.0, -80.0) == pytest.approx(69.09, abs=0.01)  # 1 deg latitude
    assert straight == pytest.approx(248, rel=0.02)          # Richmond -> Charlotte great-circle
    assert geo.distance_miles(ric, clt) == pytest.approx(straight * 1.2)


def test_distance_to_self_is_zero():
    p = Place(city="Roanoke, VA", lat=37.271, lng=-79.9414)
    assert geo.distance_miles(p, p) == 0


def test_distance_without_coords_raises():
    with pytest.raises(ValueError, match="No coordinates for 'Nowhere, VA'"):
        geo.distance_miles(Place(city="Nowhere, VA"), Place(city="Richmond, VA", lat=1, lng=1))


def test_drive_hours_at_50_mph():
    assert geo.drive_hours(550) == 11


def test_resolve_keeps_existing_coords():
    p = Place(city="Anywhere, VA", lat=1.0, lng=2.0)
    assert geo.resolve(p) == (p, [])


def test_resolve_cache_hit_is_case_and_space_insensitive():
    place, warnings = geo.resolve(Place(city="  richmond,   va "))
    assert (place.lat, place.lng) == (37.5407, -77.436) and warnings == []


def test_resolve_miss_fetches_and_writes_back(isolated, monkeypatch):
    calls = []
    monkeypatch.setattr(geo, "_fetch", lambda q: calls.append(q) or (36.1, -80.2))
    place, warnings = geo.resolve(Place(city="Winston-Salem, NC"))
    assert (place.lat, place.lng) == (36.1, -80.2) and warnings == []
    assert json.loads(isolated.read_text())["Winston-Salem, NC"] == {"lat": 36.1, "lng": -80.2}
    geo.resolve(Place(city="Winston-Salem, NC"))   # second time comes from the cache
    assert calls == ["Winston-Salem, NC"]


def test_resolve_missing_state_warns_and_does_not_guess():
    place, warnings = geo.resolve(Place(city="Springfield"))
    assert place.lat is None and warnings == ["State missing for Springfield; add it as 'City, ST'"]


def test_resolve_lookup_failure_warns(monkeypatch):
    monkeypatch.setattr(geo, "_fetch", lambda q: None)
    place, warnings = geo.resolve(Place(city="Atlantis, ZZ"))
    assert place.lat is None and "Couldn't find Atlantis, ZZ" in warnings[0]


def test_every_seed_city_is_prewarmed():
    """The real cities.json must cover every city on the simulated board (demo runs offline)."""
    real = json.loads((geo.Path(__file__).resolve().parents[1] / "data" / "cities.json").read_text())
    board = json.loads((geo.Path(__file__).resolve().parents[1] / "data" / "seed_loads.json").read_text())
    cities = {l[k]["city"] for l in board["loads"] for k in ("origin", "destination")}
    assert cities <= set(real)

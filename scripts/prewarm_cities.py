"""Look up cities now and store them in backend/data/cities.json, so the demo works with Wi-Fi off.

  python scripts/prewarm_cities.py "Blacksburg, VA" "Columbus, GA"
Uses geo.resolve (cache first, then Nominatim at 1 request/second). Commit cities.json afterwards.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.geo import resolve  # noqa: E402
from app.models import Place  # noqa: E402


def main(cities: list[str]) -> int:
    if not cities:
        print(__doc__)
        return 2
    failed = 0
    for city in cities:
        place, warnings = resolve(Place(city=city))
        if place.lat is None:
            failed += 1
            print(f"MISS  {city}: {'; '.join(warnings)}")
        else:
            print(f"OK    {city}: {place.lat:.4f}, {place.lng:.4f}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

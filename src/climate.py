"""Hardiness zone lookup from latitude/longitude."""
import json
import os

_ZONES_FILE = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "data", "hardiness_zones.json"
)
_zones_data = None


def _load_zones():
    global _zones_data
    if _zones_data is None:
        with open(_ZONES_FILE, encoding="utf-8") as f:
            _zones_data = json.load(f)["zones"]
    return _zones_data


def get_hardiness_zone(lat, lng):
    """Return approximate hardiness zone for a lat/lng coordinate.

    More specific entries (smaller area) are checked first to allow
    city-level overrides of regional zones.
    """
    zones = _load_zones()

    # Sort by area (smallest first) so specific entries win
    def area(z):
        return (z["lat_max"] - z["lat_min"]) * (z["lng_max"] - z["lng_min"])

    sorted_zones = sorted(zones, key=area)

    for z in sorted_zones:
        if (z["lat_min"] <= lat <= z["lat_max"] and
                z["lng_min"] <= lng <= z["lng_max"]):
            return z["zone"]

    # Default fallback — rough estimate based on latitude
    if lat >= 58:
        return 0
    elif lat >= 55:
        return 1
    elif lat >= 52:
        return 2
    elif lat >= 50:
        return 3
    elif lat >= 48:
        return 4
    else:
        return 5


def centroid(coords):
    """Calculate centroid of a list of [lng, lat] coordinate pairs."""
    if not coords:
        return None, None
    lats = [c[1] for c in coords]
    lngs = [c[0] for c in coords]
    return sum(lats) / len(lats), sum(lngs) / len(lngs)

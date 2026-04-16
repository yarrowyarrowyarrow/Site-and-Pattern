"""
climate.py — Hardiness zone lookup from latitude/longitude.

Uses data/hardiness_zones.json (a set of bounding-box regions for Western
Canada).  Falls back to simple latitude bands when no region matches.
"""

import json
import os
from functools import lru_cache
from typing import Optional

from src.paths import resource_path

_DATA_FILE = resource_path(os.path.join("data", "hardiness_zones.json"))


@lru_cache(maxsize=1)
def _load_zones() -> dict:
    """Load and cache the zone JSON file."""
    try:
        with open(_DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"regions": [], "fallback_latitude_bands": []}


def get_zone(lat: float, lng: float) -> Optional[int]:
    """
    Return the approximate USDA/Canadian hardiness zone for (lat, lng),
    or None if outside the covered area.

    Strategy:
    1. Check every bounding-box region in the JSON; collect all matches.
    2. Return the zone from the smallest matching region (most specific).
    3. If no region matches, fall back to latitude-band lookup.
    """
    if lat is None or lng is None:
        return None

    data = _load_zones()

    # ── Region lookup ──────────────────────────────────────────────────────
    best_zone: Optional[int] = None
    best_area: Optional[float] = None

    for region in data.get("regions", []):
        if (region["lat_min"] <= lat <= region["lat_max"] and
                region["lng_min"] <= lng <= region["lng_max"]):
            area = (
                (region["lat_max"] - region["lat_min"]) *
                (region["lng_max"] - region["lng_min"])
            )
            if best_area is None or area < best_area:
                best_area = area
                best_zone = region["zone"]

    if best_zone is not None:
        return best_zone

    # ── Latitude-band fallback ─────────────────────────────────────────────
    for band in data.get("fallback_latitude_bands", []):
        if band["lat_min"] <= lat < band["lat_max"]:
            return band["zone"]

    # Outside all known ranges
    return None


def zone_label(zone: Optional[int]) -> str:
    """Return a display string like 'Zone 3' or 'Zone: unknown'."""
    if zone is None:
        return "Zone: unknown"
    return f"Zone {zone}"


def zone_description(zone: Optional[int]) -> str:
    """Human-readable description of a zone for the status bar tooltip."""
    _desc = {
        1: "Zone 1 — extreme cold (< -45 °C winters)",
        2: "Zone 2 — very cold (-45 to -40 °C winters)",
        3: "Zone 3 — cold (-40 to -34 °C winters) — Edmonton area",
        4: "Zone 4 — moderate-cold (-34 to -29 °C winters) — Calgary area",
        5: "Zone 5 — mild-cold (-29 to -23 °C winters) — Lethbridge area",
        6: "Zone 6 — mild (-23 to -18 °C winters)",
        7: "Zone 7 — temperate (-18 to -12 °C winters)",
        8: "Zone 8 — warm-temperate (-12 to -7 °C winters) — Vancouver",
        9: "Zone 9 — warm (-7 to -1 °C winters) — Victoria",
    }
    return _desc.get(zone, zone_label(zone))

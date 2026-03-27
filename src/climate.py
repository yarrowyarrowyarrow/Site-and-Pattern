"""
climate.py — Hardiness zone lookup from latitude/longitude (Step 3 implementation).

For Step 1 this provides a simple lookup stub based on rough latitude bands
for Western Canada.  A proper zone-polygon dataset will be added in Step 3.
"""

import json
import os


def get_zone(lat: float, lng: float) -> int | None:
    """
    Return an approximate USDA/Canadian hardiness zone (integer) for the
    given coordinates, or None if outside the covered area.

    Rough latitude bands for Western Canada / Alberta:
        lat >= 60          → Zone 1
        57 <= lat < 60     → Zone 2
        54 <= lat < 57     → Zone 3  (northern Alberta, Edmonton ~53.5)
        51 <= lat < 54     → Zone 3b / 4a
        49 <= lat < 51     → Zone 4b / 5a  (southern Alberta, Calgary ~51)
        lat < 49           → Zone 5+
    """
    if lat is None or lng is None:
        return None

    # Outside Canada / not a useful range for this app
    if not (-140 <= lng <= -52 and 41 <= lat <= 83):
        return None

    if lat >= 60:
        return 1
    elif lat >= 57:
        return 2
    elif lat >= 54:
        return 3
    elif lat >= 51:
        return 4
    elif lat >= 49:
        return 5
    else:
        return 6


def zone_label(zone: int | None) -> str:
    """Return a display string like 'Zone 3' or 'Zone unknown'."""
    if zone is None:
        return "Zone unknown"
    return f"Zone {zone}"

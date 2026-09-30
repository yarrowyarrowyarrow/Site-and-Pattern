"""
placement_footprint.py — what a community will cover, for the map to draw under
the cursor before the click (F191, V2.99).

Until V2.99 an armed map showed nothing where the pointer was, though a community
is "~3 m across". ``html/map/08-footprint.js`` now draws a ghost that follows the
cursor; for a single plant it has all it needs in the plant payload, but for a
community it needs each member's place and size, which live here, Python-side.

The offsets are the members' own ``offset_x`` (metres east of the centre) and
``offset_y`` (metres north), exactly as ``MapEventRouter._on_polyculture_click``
places them, so the ghost is where the plants land. Sizes are the catalogue's:
``spacing_meters`` and ``mature_canopy_m``, the two rings the pattern preview
already draws. The ring round the whole community reaches the far edge of the
farthest canopy, which is what the ground will look like; the natural radius the
Community spacing starts from is centre to centre, and a different question.

Qt-free: the plant lookup is passed in, and defaults to the catalogue's.
"""

from __future__ import annotations

import math


def community_footprint(polyculture: dict, lookup=None) -> dict:
    """``{"name", "radius_m", "members": [[east_m, north_m, spacing_m, canopy_m], ...]}``.

    ``lookup(plant_id)`` returns the catalogue row, or ``None``; a member it
    cannot find keeps its place and gets a 1 m spacing, the map's own default,
    so a thin catalogue shrinks the ghost rather than dropping a plant from it.
    """
    if lookup is None:
        from src.db.plants import get_plant as lookup    # noqa: PLC0415
    members, reach = [], 0.0
    for m in (polyculture or {}).get("members") or []:
        east = float(m.get("offset_x") or 0.0)
        north = float(m.get("offset_y") or 0.0)
        try:
            row = lookup(m.get("plant_id")) or {}
        except Exception:                                 # noqa: BLE001
            row = {}
        spacing = float(row.get("spacing_meters") or 1.0)
        canopy = float(row.get("mature_canopy_m") or spacing * 1.5)
        members.append([round(east, 3), round(north, 3),
                        round(spacing, 3), round(canopy, 3)])
        reach = max(reach, math.hypot(east, north) + max(canopy, spacing) / 2)
    return {
        "name": (polyculture or {}).get("name") or "",
        "radius_m": round(reach, 3),
        "members": members,
    }

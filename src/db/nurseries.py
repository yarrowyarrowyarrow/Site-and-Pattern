"""
nurseries.py — Query API for the native-plant nursery directory (schema v44,
V2.18, Saskatchewan expansion).

Design principle P8 (repair/conversion is first-class) and the adoption funnel's
ACT/OUTPUT stage — a design only becomes habitat once the plants are actually
bought and put in the ground, so "where do I get these near me?" is a first-class
question. The directory is seeded from ``data/nurseries_master.json`` and sorted
by rough distance from the property pin.

Honesty (P9): coordinates are community-level approximations and the directory is
a compiled starting point, not a live feed — see the disclaimer in the JSON. The
UI surfaces that caveat.
"""

from __future__ import annotations

import math
import sqlite3
from typing import Optional

from src.db.plants import get_connection


# The native channels — always worth showing for a habitat design regardless of a
# given plant's assigned retail tier.
_NATIVE_CHANNELS = ("native_specialist", "seed_or_plug")

# Map a plant's availability_class to the supplier channels that could carry it.
_AVAILABILITY_TO_SELLS = {
    "native_specialist": ("native_specialist", "seed_or_plug"),
    "seed_or_plug":      ("seed_or_plug", "native_specialist"),
    "garden_centre":     ("garden_centre", "native_specialist", "seed_or_plug"),
    "big_box":           ("big_box", "garden_centre", "native_specialist"),
    "rare":              ("native_specialist", "seed_or_plug"),
}


def _row_to_dict(row: sqlite3.Row) -> dict:
    return dict(row) if row is not None else {}


def _haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Great-circle distance in km — fine for sorting suppliers by rough
    proximity to a property pin."""
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lng2 - lng1)
    a = (math.sin(dp / 2) ** 2
         + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2)
    return r * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def all_nurseries() -> list[dict]:
    """Every nursery/seed house/society in the directory."""
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM nurseries ORDER BY province, city, name"
        ).fetchall()
        return [_row_to_dict(r) for r in rows]
    finally:
        conn.close()


def nurseries_near(lat: float, lng: float, limit: int = 6, *,
                   province: Optional[str] = None,
                   sells: Optional[list] = None) -> list[dict]:
    """Return the ``limit`` nearest suppliers to ``(lat, lng)``, each with a
    ``distance_km`` field, nearest first.

    ``province`` restricts to one province code (e.g. "SK"). ``sells`` restricts
    to a set of supplier channels (see ``_AVAILABILITY_TO_SELLS``). Mail-order
    suppliers (``ships = 1``) are always eligible regardless of distance — they
    just sort by their nominal location — so a Regina pin still surfaces the SK
    seed houses that ship province-wide."""
    if lat is None or lng is None:
        return []
    conn = get_connection()
    try:
        clauses, params = [], []
        if province:
            clauses.append("province = ?")
            params.append(province)
        if sells:
            sells = [s for s in sells if s]
            if sells:
                clauses.append("sells IN (%s)" % ",".join("?" for _ in sells))
                params += list(sells)
        sql = "SELECT * FROM nurseries"
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        rows = conn.execute(sql, params).fetchall()
    finally:
        conn.close()

    out = []
    for r in rows:
        d = _row_to_dict(r)
        if d.get("lat") is None or d.get("lng") is None:
            continue
        d["distance_km"] = round(_haversine_km(lat, lng, d["lat"], d["lng"]), 1)
        out.append(d)
    out.sort(key=lambda d: d["distance_km"])
    return out[:max(1, int(limit))]


def nurseries_for_availability(availability_class: str, lat: float, lng: float,
                               limit: int = 6) -> list[dict]:
    """Nearest suppliers that could stock a plant of the given
    ``availability_class`` — the channel-aware convenience wrapper around
    :func:`nurseries_near`."""
    channels = _AVAILABILITY_TO_SELLS.get(
        availability_class or "", _NATIVE_CHANNELS)
    return nurseries_near(lat, lng, limit=limit, sells=list(channels))


# How near a bricks-and-mortar supplier counts as "local" rather than "ships".
_LOCAL_KM = 60.0


def access_label(n: dict) -> str:
    """A human, non-distance-shaming way to describe how to reach a supplier —
    societies lead with their sales/education, distant mail-order suppliers with
    'ships to you' rather than a discouraging 200 km figure (P9, and the user's
    explicit ask)."""
    city = n.get("city", "")
    kind = n.get("kind", "")
    if kind == "society":
        return "native plant sales & education · province-wide"
    if kind == "designer":
        return f"native landscape design · {city}" if city else "native landscape design"
    d = n.get("distance_km")
    dtxt = f"{d:g} km" if isinstance(d, (int, float)) else ""
    if isinstance(d, (int, float)) and d > _LOCAL_KM and n.get("ships"):
        return f"ships to you · {city}" if city else "ships to you"
    return " · ".join(x for x in (city, dtxt) if x)


def native_sources_near(lat: float, lng: float, limit: int = 6) -> list[dict]:
    """Curated 'where to buy natives' list for the site panel.

    Every entry is a native-plant seller or society (general garden centres and
    landscape designers are not surfaced). The nearest native-plant society is
    pinned first — for a Regina or Lumsden pin, where the closest native nursery
    is a couple hundred km away, the honest and useful answer is "the NPSS runs
    native plant sales & education province-wide, and these seed houses ship to
    you", not "nearest garden centre 200 km". Remaining slots are the nearest
    native suppliers by distance (so Saskatoon and North Battleford pins surface
    their local growers), each carrying an ``access`` label from
    :func:`access_label`."""
    rows = nurseries_near(lat, lng, limit=10_000)
    if not rows:
        return []
    societies = [n for n in rows if n.get("kind") == "society"]
    suppliers = [n for n in rows
                 if n.get("kind") in ("native_nursery", "seed_house")]

    picked: list[dict] = []
    if societies:
        picked.append(societies[0])   # nearest society, pinned as the anchor
    picked += suppliers[: max(0, int(limit) - len(picked))]
    for n in picked:
        n["access"] = access_label(n)
    return picked

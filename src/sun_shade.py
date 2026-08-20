"""
sun_shade.py — the sun and the shade it casts, as one question (V2.38).

Design principle P5 — see docs/DESIGN_PHILOSOPHY.md (perception is
constructed, not received: make the invisible ecology visible).

The app had two answers to "where does the light fall?" and they lived on
different tabs. Analysis → Sun Path drew the arc, and asked for a button press
*and* a map click before it would draw anything. Site → Features & Shade cast
the shadows, on its own date combo and its own clock. Both were reading
``solar.sun_position`` for the same instant; nothing joined them, so seeing the
sun move and seeing the shadow move were two separate acts of setup.

This module holds the part of that merge with no Qt in it: the date
vocabulary, the daylight window a clock may scrub through, and the caster
inventory. Kept Qt-free so the rules are testable on a bare container — the
suite skips ~156 widget tests without libEGL, and a rule that only runs where
Qt runs is a rule that stops running.

What lives here is deliberately small. The *maths* stays in ``src/solar.py``
and ``src/shade.py``, which both predate this and are shared with the 3D scene
and the fork. This is vocabulary and clamping, not astronomy.
"""

from __future__ import annotations

from datetime import date

# "Today" is a real choice — the sun is where it is today, and that is the
# question most people arrive with. It cannot be a fixed (month, day) because a
# session can outlive midnight, so it is a sentinel resolved on read.
TODAY = "today"

# The clock's fallback span, used before a site location is known (and if the
# solar calculation refuses). Wide enough to contain any prairie summer day.
DEFAULT_WINDOW = (5 * 60, 21 * 60)

# Deciduous crowns are bare here; ``shade._LEAF_OFF_MONTHS`` is the authority
# and this reads it rather than restating it.


def date_choices() -> list[tuple[str, object]]:
    """``(label, data)`` for the one date combo the merged surface shows.

    The six ``solar.KEY_DATES`` in the order that module lists them, then
    Today. Data is ``(month, day)`` for a key date and :data:`TODAY` for today,
    so a caller never has to parse the label back into a date.
    """
    from src.solar import KEY_DATES
    out: list[tuple[str, object]] = [
        (label, (d.month, d.day)) for label, d in KEY_DATES.items()
    ]
    out.append(("Today", TODAY))
    return out


def resolve_date(data, today: date | None = None) -> date:
    """Turn a combo's stored data back into a real date.

    Key dates carry ``solar.KEY_DATES``' own year, so the sun position is
    computed for a real day rather than an invented one; ``TODAY`` resolves to
    the day the user is standing in.
    """
    now = today or date.today()
    if data == TODAY or data is None:
        return now
    month, day = data
    from src.solar import KEY_DATES
    year = next((d.year for d in KEY_DATES.values()), now.year)
    try:
        return date(year, int(month), int(day))
    except ValueError:                       # e.g. Feb 29 in a non-leap year
        return now


def nearest_key_date_index(today: date | None = None) -> int:
    """Index into :func:`date_choices` of the key date closest to today.

    By circular day-of-year distance, so opening the panel in July shows July
    sun rather than whatever happens to be listed first. Note this returns a
    *key date*, never the Today entry: the key dates are the ones worth
    comparing against each other, and Today is one click away.
    """
    from src.solar import KEY_DATES
    doy_today = (today or date.today()).timetuple().tm_yday
    best_i, best_d = 0, 400
    for i, d in enumerate(KEY_DATES.values()):
        doy = d.timetuple().tm_yday
        dist = min(abs(doy - doy_today), 365 - abs(doy - doy_today))
        if dist < best_d:
            best_i, best_d = i, dist
    return best_i


def daylight_window(lat, lng, d: date) -> tuple[int, int]:
    """``(lo, hi)`` minutes since midnight the clock may scrub through.

    Sunrise to a touch past sunset for this site on this date. A slider that
    lets you ask an impossible question has to answer it with nothing, so the
    range is the real daylight and not a generic 5-to-9.

    Falls back to :data:`DEFAULT_WINDOW` when the site has no location yet, or
    when the day never properly rises or sets (the far north in December, where
    the honest answer is "this is not a normal day" rather than a bad number).
    """
    if lat is None or lng is None:
        return DEFAULT_WINDOW
    try:
        from src.solar import sunrise_sunset
        sr, ss = sunrise_sunset(float(lat), float(lng), d)
        lo = max(0, int(sr * 60))
        hi = min(24 * 60 - 1, int(ss * 60) + 15)
    except Exception:                        # noqa: BLE001 — see docstring
        return DEFAULT_WINDOW
    if hi <= lo:
        return DEFAULT_WINDOW
    return lo, hi


def clamp_to_window(minutes: int, window: tuple[int, int]) -> int:
    """Keep a clock reading inside its date's daylight."""
    lo, hi = window
    return max(lo, min(hi, int(minutes)))


def clock(minutes: int) -> str:
    """``HH:MM`` for minutes since midnight."""
    m = max(0, int(minutes))
    return f"{m // 60:02d}:{m % 60:02d}"


def is_leaf_off(month) -> bool:
    """True when deciduous crowns are bare in this month, so the UI can say so.

    The lighter shadows a leaf-off date produces read as a bug unless something
    explains them (P9 — the model's honesty is only useful if it is legible).
    """
    if month is None:
        return False
    from src.shade import _LEAF_OFF_MONTHS
    return int(month) in _LEAF_OFF_MONTHS


# ── What is actually casting the shade ───────────────────────────────────────

def caster_counts(project_dict: dict | None) -> tuple[int, int]:
    """``(buildings, trees)`` among the project's existing features.

    Pure feature scan, no DB. Placed design trees join the shade automatically
    and are not counted here — this line answers "did my import land?", not
    "what is in my design?".
    """
    trees = buildings = 0
    for f in (project_dict or {}).get("features") or []:
        props = f.get("properties") or {}
        et = props.get("element_type")
        if et == "existing_tree":
            trees += 1
        elif et == "existing_building":
            buildings += 1
        elif (et == "canopy_footprint"
              or (et == "custom_shape" and props.get("cast_shade"))):
            if props.get("caster_kind") == "tree":
                trees += 1
            else:
                buildings += 1
    return buildings, trees


def caster_summary(buildings: int, trees: int,
                   where: str = "the Site tab") -> tuple[str, bool]:
    """``(line, have_any)`` for the inventory shown before the shade is drawn.

    Told *before* the click, because a shade map cast by nothing looks the same
    as a shade map cast by a site with no shade.
    """
    if not buildings and not trees:
        return (f"No existing features yet — import or draw them on "
                f"{where} so the shade is real.", False)
    return (f"Casting shade: {buildings} building"
            f"{'s' if buildings != 1 else ''} · {trees} tree"
            f"{'s' if trees != 1 else ''} (+ your placed plants, "
            "automatically).", True)


# ── Where the arc goes when nobody has said ──────────────────────────────────

def default_anchor(project_dict: dict | None,
                   site_config: dict | None) -> tuple[float, float] | None:
    """Where to centre the sun arc without asking: the boundary's centroid,
    else the site pin.

    Placing the anchor used to be a *prerequisite* — press a button, then find
    and click the right bit of map — which is a lot of ceremony for a feature
    whose answer is almost always "the middle of my yard". The click stays
    available for the case where it matters (a specific bed, a neighbour's
    tree); it is no longer the toll gate.
    """
    boundary = _first_boundary(project_dict)
    if boundary:
        n = len(boundary)
        return (sum(p[0] for p in boundary) / n, sum(p[1] for p in boundary) / n)
    sc = site_config or {}
    lat, lng = sc.get("latitude"), sc.get("longitude")
    if lat is None or lng is None:
        return None
    try:
        return float(lat), float(lng)
    except (TypeError, ValueError):
        return None


def _first_boundary(project_dict: dict | None) -> list[tuple[float, float]]:
    """The first drawn boundary ring as ``[(lat, lng), …]``, or ``[]``.

    Reads the GeoJSON directly (lng, lat order) rather than going through
    ``project.project_to_map_data`` so this module stays importable without the
    map layer — the same reason the rest of the file has no Qt in it.
    """
    for f in (project_dict or {}).get("features") or []:
        props = f.get("properties") or {}
        if props.get("element_type") != "property_boundary":
            continue
        geom = f.get("geometry") or {}
        if geom.get("type") != "Polygon":
            continue
        rings = geom.get("coordinates") or []
        if not rings:
            continue
        ring = [(float(pt[1]), float(pt[0])) for pt in rings[0]
                if isinstance(pt, (list, tuple)) and len(pt) >= 2]
        # A GeoJSON ring repeats its first point to close; averaging with the
        # duplicate pulls the centroid toward that corner.
        if len(ring) > 2 and ring[0] == ring[-1]:
            ring = ring[:-1]
        if len(ring) >= 3:
            return ring
    return []

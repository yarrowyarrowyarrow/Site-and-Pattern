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

def is_existing_caster(props: dict) -> bool:
    """Is a feature with these properties something already on the site that
    casts shade: a tree or building marked, drawn, scanned or imported. Placed
    plants are not: they join the shade automatically."""
    et = props.get("element_type")
    return (et in ("existing_tree", "existing_building", "canopy_footprint")
            or (et == "custom_shape" and bool(props.get("cast_shade"))))


def is_tree(props: dict) -> bool:
    return (props.get("element_type") == "existing_tree"
            or props.get("caster_kind") == "tree")


def shade_is_off(props: dict) -> bool:
    """Unticked in Sun & Shade › Existing features (V3.37): kept in the
    design, but casting no shade (``shade.SHADE_OFF``)."""
    from src.shade import SHADE_OFF
    return bool(props.get(SHADE_OFF))


def caster_counts(project_dict: dict | None) -> tuple[int, int]:
    """``(buildings, trees)`` among the project's existing features that cast
    shade: one switched off in Sun & Shade is not counted (V3.37).

    Pure feature scan, no DB. Placed design trees join the shade automatically
    and are not counted here — this line answers "did my import land?", not
    "what is in my design?".
    """
    trees = buildings = 0
    for f in (project_dict or {}).get("features") or []:
        props = f.get("properties") or {}
        if not is_existing_caster(props) or shade_is_off(props):
            continue
        if is_tree(props):
            trees += 1
        else:
            buildings += 1
    return buildings, trees


def switched_off(project_dict: dict | None) -> int:
    """How many existing features are switched off in Sun & Shade."""
    return sum(1 for f in (project_dict or {}).get("features") or []
               if is_existing_caster(f.get("properties") or {})
               and shade_is_off(f.get("properties") or {}))


def caster_summary(buildings: int, trees: int,
                   where: str = "the Site tab",
                   off: int = 0, off_where: str = "in Sun & Shade"
                   ) -> tuple[str, bool]:
    """``(line, have_any)`` for the inventory shown before the shade is drawn.

    Told *before* the click, because a shade map cast by nothing looks the same
    as a shade map cast by a site with no shade. ``off`` is how many were
    switched off in Sun & Shade (``off_where``: "below" on that page), said so
    a smaller count is not a mystery.
    """
    note = (f" {off} switched off {off_where}." if off else "")
    if not buildings and not trees:
        if off:
            return (f"Nothing is casting shade:{note}", False)
        return (f"No existing features yet — import or draw them on "
                f"{where} so the shade is real.", False)
    return (f"Casting shade: {buildings} building"
            f"{'s' if buildings != 1 else ''} · {trees} tree"
            f"{'s' if trees != 1 else ''} (+ your placed plants, "
            f"automatically).{note}", True)


# ── The list Sun & Shade › Existing features shows (V3.37) ───────────────────

def describe_feature(feature: dict) -> str:
    """A row's first words: "Tree (canopy height) · crown 6 m · 11 m tall".
    Shared with the scan's review list (``features_scan_flow``)."""
    props = feature.get("properties") or {}
    tree = is_tree(props)
    label = props.get("label") or ("Tree" if tree else "Building")
    height = float(props.get("height_m") or 0)
    bits = [label]
    if tree:
        bits.append(f"crown {2 * float(props.get('canopy_radius_m') or 0):.0f} m")
    if height:
        bits.append(f"{height:.0f} m tall")
    return " · ".join(bits)


def feature_centre(feature: dict):
    """``(lat, lng)`` of a point, or the centroid of a polygon; or ``None``."""
    geom = feature.get("geometry") or {}
    coords = geom.get("coordinates") or []
    if geom.get("type") == "Point" and len(coords) >= 2:
        return float(coords[1]), float(coords[0])
    if geom.get("type") == "Polygon" and coords and coords[0]:
        from src.osm_features import ring_centroid
        return ring_centroid(coords[0])
    return None


_COMPASS = ("north", "north-east", "east", "south-east", "south",
            "south-west", "west", "north-west")


def _offset_m(point, middle) -> tuple[float, float]:
    """``(north, east)`` metres from ``middle`` to ``point``, the cosLat way
    (``src/projection.py``'s default, centimetres at yard scale)."""
    import math
    from src.projection import M_PER_DEG_LAT
    return ((point[0] - middle[0]) * M_PER_DEG_LAT,
            (point[1] - middle[1]) * M_PER_DEG_LAT
            * math.cos(math.radians(middle[0])))


def where_from(point, middle) -> str:
    """"12 m north-west": from the yard's middle to ``point``, both
    ``(lat, lng)``; "in the middle" within 2 m; "" when either is unknown.
    Rows that would otherwise read alike (four "Tree (detected)") differ by
    where they are, which is how a person tells them apart."""
    if not point or not middle:
        return ""
    import math
    north, east = _offset_m(point, middle)
    dist = math.hypot(north, east)
    if dist < 2.0:
        return "in the middle"
    bearing = math.degrees(math.atan2(east, north)) % 360
    return f"{dist:.0f} m {_COMPASS[int((bearing + 22.5) // 45) % 8]}"


def caster_rows(project_dict: dict | None,
                site_config: dict | None = None) -> list[dict]:
    """One row per existing feature that can cast shade, for the list:
    ``{"index", "text", "where", "on", "centre"}``, where ``index`` is the
    feature's place in ``features``. Buildings first, then trees, each nearest
    the yard's middle first."""
    feats = (project_dict or {}).get("features") or []
    middle = default_anchor(project_dict, site_config)
    rows = []
    for i, f in enumerate(feats):
        props = f.get("properties") or {}
        if not is_existing_caster(props):
            continue
        centre = feature_centre(f)
        where = where_from(centre, middle)
        text = describe_feature(f) + (f" · {where}" if where else "")
        rows.append({"index": i, "text": text, "where": where,
                     "on": not shade_is_off(props), "centre": centre,
                     "_order": (is_tree(props), _distance(centre, middle))})
    rows.sort(key=lambda r: r.pop("_order"))
    return rows


def _distance(point, middle) -> float:
    if not point or not middle:
        return float("inf")
    import math
    return math.hypot(*_offset_m(point, middle))


def set_shade(project_dict: dict, indexes, on: bool) -> int:
    """Switch the shade of the features at ``indexes`` on or off (V3.37).
    Returns how many changed. Pure: mutates the project in place; the caller
    wraps it in one undo step. On is the default, so it is written by
    removing the key: a design that never switched anything off is the file
    it always was."""
    from src.shade import SHADE_OFF
    feats = (project_dict or {}).get("features") or []
    changed = 0
    for i in indexes:
        if not 0 <= i < len(feats):
            continue
        props = feats[i].setdefault("properties", {})
        if not is_existing_caster(props) or shade_is_off(props) == (not on):
            continue
        if on:
            props.pop(SHADE_OFF, None)
        else:
            props[SHADE_OFF] = True
        changed += 1
    return changed


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

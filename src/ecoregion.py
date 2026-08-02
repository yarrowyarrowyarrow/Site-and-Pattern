"""
ecoregion.py — which ecoregions a point falls in, and the vocabulary of them.

Design principle P2 — see docs/DESIGN_PHILOSOPHY.md (the best designs disappear
into their context: the context has a name, and it is not the province you are
in).

Replaces the "pick your ecoregion from a dropdown" guesswork with automatic
detection from the property's lat/lng. The plant filter becomes a verification
(with the right answer pre-selected) rather than a question — most people do not
know whether their address falls in Aspen Parkland or Boreal Mixedwood.

Two things changed in V2.38, both from user feedback.

**A site can be in more than one.** ``lookup_ecoregion`` returned the *first*
matching polygon and stopped. A property near a boundary — which is where a lot
of the interesting planting is — belongs to both, and saying so is more useful
than picking one. :func:`lookup_ecoregions` returns them all; the singular name
is kept as a shim for callers that genuinely want one.

**Two axes were sharing one.** ``aspen_parkland``, ``mixedgrass_prairie``,
``moist_mixedgrass``, ``fescue_foothills``, ``boreal_mixedwood`` and
``subalpine_montane`` are *geographic* ecoregions — regions on a map, hundreds
of kilometres across. ``riparian`` and ``wet_meadow`` are *site-scale moisture
niches*: a streamside metre exists inside any of the six. This module's own
docstring used to admit they were "per-feature rather than per-region at the
provincial scale" and keep them "manual-only in the dropdown" — which is a note
saying the vocabulary has two kinds of thing in it. They are separated here:
the geographic list comes from the polygons, the moisture list is a constant.

**The geographic vocabulary is the shipped polygon file**, not a hard-coded
list beside it. *"I'd prefer it breakdown into the individual ecoregions it
exists in so when I add BC and other areas of turtle island we simply add more
ecoregions"* — that only works if adding a region means adding a polygon and
nothing else. ``scripts/prepare_ecoregions.py`` writes the file;
``data/ecoregions_canada.geojson`` is then the single source of truth for what
geographic ecoregions exist, what they are called, and where they are.

Implementation notes:

  * **Pure Python, no shapely / pyproj.** For point-in-polygon, ray casting
    (~15 lines, in ``src/geometry.py``) is just as correct as shapely, has zero
    install footprint, and avoids the PyInstaller bundling risk those native
    libraries carry on Windows. Polygon *overlay* work belongs in the dev-time
    prep script, which may use shapely freely.

  * **Lat/lng comparison, no projection.** Ecoregion boundaries at provincial
    scale are coarse enough that WGS84→projected distortion does not move a
    city across a boundary.

  * **The shipped polygons are still rectangular approximations** of the major
    prairie ecoregions (V1.36) — five vertices each. Replacing them with real
    CEC Level III boundaries is a download-once dev step (see the script), and
    until that lands a lookup near a boundary is a rough answer, which is why
    the site panel reports it as detection rather than fact (P9).
"""

import json
from functools import lru_cache
from typing import Optional

from src.resources import resource_path


_DATA_FILE = resource_path("data", "ecoregions_canada.geojson")


@lru_cache(maxsize=1)
def _load_features() -> list[dict]:
    """Load and cache the GeoJSON FeatureCollection. Returns an empty
    list (rather than raising) if the file is missing or malformed —
    callers degrade gracefully to "ecoregion unknown" rather than
    crashing the site panel."""
    try:
        with open(_DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return []
    if not isinstance(data, dict):
        return []
    features = data.get("features")
    if not isinstance(features, list):
        return []
    return features


def _point_in_ring(lat: float, lng: float, ring: list[list[float]]) -> bool:
    """Back-compat shim — the implementation now lives in ``src.geometry``
    (extracted in V1.48 so the design generator can reuse it for boundary
    clipping). Kept here so existing imports of ``ecoregion._point_in_ring``
    keep working."""
    from src.geometry import point_in_ring
    return point_in_ring(lat, lng, ring)


def _point_in_polygon(lat: float, lng: float, polygon: list[list[list[float]]]) -> bool:
    """Back-compat shim for ``src.geometry.point_in_polygon`` (see above)."""
    from src.geometry import point_in_polygon
    return point_in_polygon(lat, lng, polygon)


def lookup_ecoregions(lat: float, lng: float) -> list[str]:
    """Every geographic ecoregion key whose polygon contains (lat, lng).

    In file order, de-duplicated — a region may be drawn as several polygons
    (the prairie set ships one per province-side lobe) and being in two lobes
    of the same region is still being in one region.

    Empty when the point falls outside every shipped polygon, which is the
    honest answer for a site the data does not cover yet, and is what the
    caller should say rather than guessing the nearest.
    """
    if lat is None or lng is None:
        return []
    found: list[str] = []
    for feature in _load_features():
        geom = feature.get("geometry") or {}
        if geom.get("type") != "Polygon":
            continue
        coords = geom.get("coordinates")
        if not coords:
            continue
        key = (feature.get("properties") or {}).get("key")
        if not key or key in found:
            continue
        if _point_in_polygon(lat, lng, coords):
            found.append(key)
    return found


def lookup_ecoregion(lat: float, lng: float) -> Optional[str]:
    """The first matching ecoregion key, or ``None``.

    Kept for callers that genuinely want a single answer (the site panel's
    one-line readout). Anything choosing *plants* should use
    :func:`lookup_ecoregions` — a boundary site's second region is exactly the
    one whose species list you were missing.
    """
    keys = lookup_ecoregions(lat, lng)
    return keys[0] if keys else None


# ── The vocabulary ──────────────────────────────────────────────────────────
#
# Name and place are kept APART. Packed into one label they elided mid-word in
# the filter dropdown — "Moist Mixed Gras...ina (Saskatoon)" — so neither the
# ecoregion nor the geography survived; the two-line item painter in
# `filter_widgets` puts the name first and whole, the place under it.

# Site-scale moisture niches. Not places — conditions that occur inside any
# geographic ecoregion — so they are not in the polygon file and never will be.
MOISTURE_NICHES: list[tuple[str, str, str]] = [
    # (key, name, where it is)
    ("riparian",   "Riparian",           "streamside"),
    ("wet_meadow", "Wet Meadow / Marsh", "wet ground"),
]

# The geographic vocabulary of last resort. Used only when the polygon file is
# missing or unreadable — a frozen build with a broken resource path should
# still offer a working filter rather than an empty one. Kept in step with the
# shipped file by ``tests/test_ecoregion.py``.
_FALLBACK_GEOGRAPHIC: list[tuple[str, str, str]] = [
    ("aspen_parkland",     "Aspen Parkland",           "central AB / SK"),
    ("mixedgrass_prairie", "Mixedgrass Prairie",       "south AB / SK"),
    ("moist_mixedgrass",   "Moist Mixed Grassland",    "Regina / Saskatoon"),
    ("fescue_foothills",   "Fescue / Foothills",       "SW Alberta"),
    ("boreal_mixedwood",   "Boreal Mixedwood / Plain", "north AB / SK"),
    ("subalpine_montane",  "Subalpine / Montane",      "the mountains"),
]


def _split_label(label: str) -> tuple[str, str]:
    """``"Aspen Parkland (central AB)"`` → ``("Aspen Parkland", "central AB")``.

    Transitional: features written before V2.38 carry one packed ``label``
    instead of separate ``name`` / ``where``. Splitting on the *last* bracket
    keeps names that contain their own brackets intact.
    """
    label = (label or "").strip()
    if label.endswith(")") and "(" in label:
        head, _, tail = label.rpartition("(")
        return head.strip(), tail[:-1].strip()
    return label, ""


@lru_cache(maxsize=1)
def geographic_ecoregions() -> tuple[tuple[str, str, str], ...]:
    """``(key, name, where)`` per geographic ecoregion, in display order.

    Read from the shipped polygons, so adding a region to the file adds it to
    every dropdown, the validator's accepted vocabulary and the seeding script
    at once. De-duplicated by key: several polygons may share one region, and
    the *first* one's name wins (later lobes name their own province-side).

    Order is each feature's ``sort`` property when present, else file order.
    """
    rows: list[tuple[int, int, tuple[str, str, str]]] = []
    seen: set[str] = set()
    for i, feature in enumerate(_load_features()):
        props = feature.get("properties") or {}
        key = props.get("key")
        if not key or key in seen:
            continue
        seen.add(key)
        name = (props.get("name") or "").strip()
        where = (props.get("where") or "").strip()
        if not name:
            name, packed_where = _split_label(props.get("label") or key)
            where = where or packed_where
        try:
            sort = int(props.get("sort", i))
        except (TypeError, ValueError):
            sort = i
        rows.append((sort, i, (key, name or key, where)))
    if not rows:
        return tuple(_FALLBACK_GEOGRAPHIC)
    rows.sort(key=lambda r: (r[0], r[1]))
    return tuple(row[2] for row in rows)


def ecoregions() -> list[tuple[str, str, str]]:
    """The whole filter vocabulary: geographic regions, then moisture niches.

    One list because one dropdown asks the question, but the two halves are
    different kinds of claim and :func:`is_moisture_niche` tells them apart.
    """
    return list(geographic_ecoregions()) + list(MOISTURE_NICHES)


def ecoregion_keys() -> list[str]:
    """The canonical keys, in display order — the validator's vocabulary."""
    return [key for key, _name, _where in ecoregions()]


def geographic_keys() -> list[str]:
    """Just the regions on the map (no moisture niches)."""
    return [key for key, _name, _where in geographic_ecoregions()]


def is_moisture_niche(key: str) -> bool:
    """True for ``riparian`` / ``wet_meadow`` — a condition, not a place.

    A site *detection* may never return one of these: no lat/lng puts you in
    "wet ground". They are only ever chosen by hand, or asserted per species.
    """
    return any(k == key for k, _n, _w in MOISTURE_NICHES)


def ecoregion_display(key: str) -> tuple[str, str]:
    """``(name, where)`` for a key — the two lines the filter list draws."""
    for k, name, where in ecoregions():
        if k == key:
            return name, where
    return key, ""


def label_for_key(key: Optional[str]) -> str:
    """The human-readable one-line label for a key, or ``'—'`` when unknown."""
    if not key:
        return "—"
    name, where = ecoregion_display(key)
    if name == key and not where:
        return key
    return f"{name} ({where})" if where else name


# Module-level snapshot for callers that build constants at import time
# (``plant_panel`` does). Everything else should call :func:`ecoregions`, which
# stays correct if the caches are cleared.
ECOREGIONS: list[tuple[str, str, str]] = ecoregions()

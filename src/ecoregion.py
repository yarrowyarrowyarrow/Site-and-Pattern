"""
ecoregion.py — Point-in-polygon lookup of Alberta ecoregions (V1.36).

Replaces the "pick your ecoregion from a 7-option dropdown" guesswork
with automatic detection from the property's lat/lng. The plant filter
combo at ``plant_panel._AB_ECOREGION_CHOICES`` becomes a verification
(with the right answer pre-selected) rather than a question — most
users don't actually know whether their address falls in Aspen
Parkland or Boreal Mixedwood.

Polygon data lives in ``data/ecoregions_canada.geojson`` as a standard
GeoJSON FeatureCollection. Each feature's ``properties.key`` matches a
canonical ecoregion key in ``plant_panel._AB_ECOREGION_CHOICES`` (the
list this module's output drives).

Implementation notes:

  * **Pure Python, no shapely / pyproj.** The original step-4 plan
    proposed introducing shapely + pyproj here as groundwork for future
    spatial features (soil intersect, watershed). For a single
    point-in-polygon lookup, ray casting (~15 lines) is just as
    correct, has zero install footprint, and avoids the PyInstaller
    bundling risk those native-dep libraries carry on Windows.
    The shapely adoption can happen later when a feature genuinely
    needs polygon overlay / union ops.

  * **Lat/lng comparison, no projection.** Ecoregion boundaries at
    the scale of Alberta are coarse enough that the WGS84
    -> projected distortion doesn't move a city across a boundary.
    Future features that need accurate areas (e.g. "show me the
    fraction of my property that falls in Region X") will need
    projection; that's the moment to add pyproj, not this one.

  * **Starter polygon set.** The shipped polygons are rectangular
    approximations of Alberta's five major terrestrial ecoregions
    (boreal mixedwood, aspen parkland, mixedgrass prairie, fescue
    foothills, subalpine montane). The two minor regions in the
    plant filter (``riparian``, ``wet_meadow``) are per-feature
    rather than per-region at the provincial scale — they stay
    manual-only in the dropdown. ``scripts/prepare_ecoregions.py``
    is the documented path to upgrade to fidelity polygons from
    the CEC Level III Ecoregions shapefile.
"""

import json
import os
from functools import lru_cache
from typing import Optional


_DATA_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data", "ecoregions_canada.geojson",
)


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


def lookup_ecoregion(lat: float, lng: float) -> Optional[str]:
    """Return the canonical ``ab_ecoregion`` key for (lat, lng), or
    ``None`` if the point falls outside every shipped ecoregion polygon.

    Returns the first matching feature when polygons overlap — the
    shipped polygon set is intentionally non-overlapping, so order
    doesn't matter in practice, but feature order in the GeoJSON is
    the tiebreaker if a future revision introduces overlap."""
    if lat is None or lng is None:
        return None
    for feature in _load_features():
        geom = feature.get("geometry") or {}
        if geom.get("type") != "Polygon":
            continue
        coords = geom.get("coordinates")
        if not coords:
            continue
        if _point_in_polygon(lat, lng, coords):
            return feature.get("properties", {}).get("key")
    return None


def label_for_key(key: Optional[str]) -> str:
    """Return the human-readable label for an ecoregion key, or '—'
    when the key is unknown. Reads the GeoJSON properties.label so the
    UI string stays in sync with the shipped data file."""
    if not key:
        return "—"
    for feature in _load_features():
        props = feature.get("properties") or {}
        if props.get("key") == key:
            return props.get("label") or key
    return key

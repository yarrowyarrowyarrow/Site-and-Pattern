"""
osm_features.py — Import existing trees & buildings from OpenStreetMap (V1.51).

So the design generator's shade model and keep-out zones can account for what's
already on the property without the user marking everything by hand. Buildings
are well-mapped in towns; individual trees less so — hence this pairs with the
manual marking from V1.49 as a fallback for whatever OSM misses.

Mirrors the ``src/property_data.py`` fetchers exactly: stdlib ``urllib`` only,
short timeout, and **degrade gracefully** — every fetch returns ``[]`` / ``None``
on any failure so the UI shows "none found" rather than crashing. (This whole
module is therefore untestable against the live API in CI; tests parse captured
Overpass JSON fixtures, the same way ``test_property_data`` does.)

Data → project features:
  * building way  → ``existing_building`` (centroid, footprint radius, height
    from ``height`` or ``building:levels`` × 3 m).
  * ``natural=tree`` node → ``existing_tree`` (point, canopy radius from
    ``diameter_crown`` when present, else a default).

Public API:
  * ``fetch_buildings(bbox) -> list[dict]``
  * ``fetch_trees(bbox) -> list[dict]``
  * ``fetch_existing_features(bbox) -> dict`` (both, one Overpass call)
Each returned item: ``{"kind": "tree"|"building", "lat", "lng", "height_m",
"radius_m"}`` — ready for ``design_api.add_existing_tree/building``.
"""

from __future__ import annotations

import json
import math
import urllib.parse
import urllib.request
from typing import Optional

_TIMEOUT = 25.0
_USER_AGENT = "PermaDesign/1.0 (https://github.com/yarrowyarrowyarrow/permadesign)"
# Public Overpass instance; the app degrades gracefully if it's unreachable.
_OVERPASS_URL = "https://overpass-api.de/api/interpreter"

_DEFAULT_TREE_HEIGHT_M = 7.0
_DEFAULT_TREE_RADIUS_M = 3.0
_DEFAULT_BUILDING_HEIGHT_M = 5.0
_STOREY_HEIGHT_M = 3.0


def _bbox_str(bbox: dict) -> str:
    """Overpass wants ``south,west,north,east``."""
    return f"{bbox['south']},{bbox['west']},{bbox['north']},{bbox['east']}"


def _query(bbox: dict, include_trees: bool, include_buildings: bool) -> str:
    parts = []
    b = _bbox_str(bbox)
    if include_buildings:
        parts.append(f'way["building"]({b});')
    if include_trees:
        parts.append(f'node["natural"="tree"]({b});')
    return f"[out:json][timeout:25];({''.join(parts)});out geom;"


def _post_overpass(query: str) -> Optional[dict]:
    """POST an Overpass QL query, return parsed JSON or None on any failure."""
    try:
        data = b"data=" + urllib.parse.quote(query).encode("utf-8")
        req = urllib.request.Request(
            _OVERPASS_URL, data=data,
            headers={"User-Agent": _USER_AGENT,
                     "Content-Type": "application/x-www-form-urlencoded"})
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception:  # noqa: BLE001 — any failure degrades to "no data"
        return None


def _parse_height(tags: dict, default: float) -> float:
    """Building/tree height from OSM tags: explicit ``height`` (metres) wins,
    else ``building:levels`` × storey height, else the default."""
    h = tags.get("height")
    if h:
        try:
            return max(0.5, float(str(h).split()[0]))   # "12 m" → 12
        except (ValueError, IndexError):
            pass
    levels = tags.get("building:levels")
    if levels:
        try:
            return max(0.5, float(levels) * _STOREY_HEIGHT_M)
        except ValueError:
            pass
    return default


def _ring_centroid_radius(geometry: list) -> Optional[tuple]:
    """Centroid (lat, lng) and an enclosing radius (m) for an Overpass ``geom``
    way (list of ``{"lat","lon"}``). ``None`` for a degenerate ring."""
    pts = [(g["lat"], g["lon"]) for g in geometry
           if "lat" in g and "lon" in g]
    if len(pts) < 3:
        return None
    clat = sum(p[0] for p in pts) / len(pts)
    clng = sum(p[1] for p in pts) / len(pts)
    cos_lat = math.cos(clat * math.pi / 180) or 1e-9
    # Footprint "radius" = max vertex distance from centroid (covers the
    # building for keep-out / a coarse shadow caster).
    radius = 0.0
    for la, ln in pts:
        dx = (ln - clng) * 111320.0 * cos_lat
        dy = (la - clat) * 111320.0
        radius = max(radius, math.hypot(dx, dy))
    return (clat, clng, max(1.0, radius))


def parse_elements(data: Optional[dict]) -> list[dict]:
    """Turn an Overpass JSON response into existing-feature dicts. Pure and
    fixture-testable (no network)."""
    out: list[dict] = []
    for el in (data or {}).get("elements", []) or []:
        tags = el.get("tags", {}) or {}
        etype = el.get("type")
        if etype == "node" and tags.get("natural") == "tree":
            lat, lng = el.get("lat"), el.get("lon")
            if lat is None or lng is None:
                continue
            crown = tags.get("diameter_crown")
            radius = _DEFAULT_TREE_RADIUS_M
            if crown:
                try:
                    radius = max(0.5, float(str(crown).split()[0]) / 2.0)
                except (ValueError, IndexError):
                    pass
            out.append({"kind": "tree", "lat": float(lat), "lng": float(lng),
                        "height_m": _parse_height(tags, _DEFAULT_TREE_HEIGHT_M),
                        "radius_m": radius})
        elif etype == "way" and tags.get("building"):
            cr = _ring_centroid_radius(el.get("geometry", []) or [])
            if cr is None:
                continue
            clat, clng, radius = cr
            out.append({"kind": "building", "lat": clat, "lng": clng,
                        "height_m": _parse_height(
                            tags, _DEFAULT_BUILDING_HEIGHT_M),
                        "radius_m": radius})
    return out


def fetch_existing_features(bbox: dict, *, trees: bool = True,
                            buildings: bool = True) -> dict:
    """Fetch existing trees and/or buildings in ``bbox`` from OSM. Returns
    ``{"trees": [...], "buildings": [...]}`` (empty lists on any failure)."""
    if not (trees or buildings):
        return {"trees": [], "buildings": []}
    data = _post_overpass(_query(bbox, trees, buildings))
    feats = parse_elements(data)
    return {
        "trees": [f for f in feats if f["kind"] == "tree"],
        "buildings": [f for f in feats if f["kind"] == "building"],
    }


def fetch_buildings(bbox: dict) -> list[dict]:
    return fetch_existing_features(bbox, trees=False, buildings=True)["buildings"]


def fetch_trees(bbox: dict) -> list[dict]:
    return fetch_existing_features(bbox, trees=True, buildings=False)["trees"]


def _too_close(lat, lng, existing, min_m=2.0) -> bool:
    """True when an (lat,lng) is within ``min_m`` of an already-present feature
    point — used to dedupe OSM imports against hand-marked features."""
    cos_lat = math.cos(lat * math.pi / 180) or 1e-9
    for elat, elng in existing:
        dx = (lng - elng) * 111320.0 * cos_lat
        dy = (lat - elat) * 111320.0
        if dx * dx + dy * dy < min_m * min_m:
            return True
    return False


def add_features_to_project(features: list[dict], project_dict: dict) -> int:
    """Append OSM-derived existing trees/buildings to a project's feature list
    (the V1.49 ``existing_tree`` / ``existing_building`` shapes), skipping any
    that duplicate a feature already present. Returns the number added. Pure
    (mutates the dict in place); the GUI calls this on the main thread after the
    off-thread fetch."""
    feats = project_dict.setdefault("features", [])
    existing_pts = []
    for f in feats:
        et = (f.get("properties") or {}).get("element_type")
        if et in ("existing_tree", "existing_building"):
            c = (f.get("geometry") or {}).get("coordinates") or []
            if len(c) >= 2:
                existing_pts.append((c[1], c[0]))
    added = 0
    for item in features or []:
        lat, lng = item.get("lat"), item.get("lng")
        if lat is None or lng is None or _too_close(lat, lng, existing_pts):
            continue
        etype = ("existing_tree" if item.get("kind") == "tree"
                 else "existing_building")
        feats.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [lng, lat]},
            "properties": {
                "element_type": etype,
                "height_m": float(item.get("height_m") or (
                    _DEFAULT_TREE_HEIGHT_M if etype == "existing_tree"
                    else _DEFAULT_BUILDING_HEIGHT_M)),
                "canopy_radius_m": float(item.get("radius_m") or (
                    _DEFAULT_TREE_RADIUS_M if etype == "existing_tree"
                    else 4.0)),
                "label": ("Tree (OSM)" if etype == "existing_tree"
                          else "Building (OSM)"),
                "struct_id": etype,
                "source": "osm",
            },
        })
        existing_pts.append((lat, lng))
        added += 1
    return added

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
# Primary + fallback mirror. The public primary rate-limits per-IP hard —
# two imports within seconds routinely get a 429 — so a failed attempt
# retries once (after a pause) and then tries the mirror before giving up.
_OVERPASS_URLS = [
    _OVERPASS_URL,
    "https://overpass.kumi.systems/api/interpreter",
]
_RETRY_PAUSE_S = 2.0

_DEFAULT_TREE_HEIGHT_M = 7.0
_DEFAULT_TREE_RADIUS_M = 3.0
_DEFAULT_BUILDING_HEIGHT_M = 5.0
_STOREY_HEIGHT_M = 3.0


def _bbox_str(bbox: dict) -> str:
    """Overpass wants ``south,west,north,east``."""
    return f"{bbox['south']},{bbox['west']},{bbox['north']},{bbox['east']}"


def _query(bbox: dict, include_trees: bool, include_buildings: bool) -> str:
    # Both ways AND relations: large complexes (apartment blocks with
    # courtyards) are often mapped as multipolygon relations, which a
    # way-only query never returns (V2.13).
    parts = []
    b = _bbox_str(bbox)
    if include_buildings:
        parts.append(f'way["building"]({b});')
        parts.append(f'relation["building"]({b});')
    if include_trees:
        parts.append(f'node["natural"="tree"]({b});')
    return f"[out:json][timeout:25];({''.join(parts)});out geom;"


def _post_overpass(query: str, url: str = _OVERPASS_URL) -> Optional[dict]:
    """POST an Overpass QL query to one endpoint; parsed JSON or None."""
    try:
        data = b"data=" + urllib.parse.quote(query).encode("utf-8")
        req = urllib.request.Request(
            url, data=data,
            headers={"User-Agent": _USER_AGENT,
                     "Content-Type": "application/x-www-form-urlencoded"})
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception:  # noqa: BLE001 — the caller retries / falls back
        return None


def _fetch_overpass(query: str, *, _post=None, _sleep=None) -> Optional[dict]:
    """Fetch with retry + mirror fallback: primary → (pause) primary again →
    mirror. Returns parsed JSON, or None only when every attempt failed —
    which callers must report as *failure*, never as an empty result.
    ``_post``/``_sleep`` are injectable for tests."""
    import time
    post = _post or _post_overpass
    sleep = _sleep or time.sleep
    attempts = [_OVERPASS_URLS[0], _OVERPASS_URLS[0]] + _OVERPASS_URLS[1:]
    for i, url in enumerate(attempts):
        if i > 0:
            sleep(_RETRY_PAUSE_S)   # etiquette: back off before hammering again
        data = post(query, url)
        if data is not None:
            return data
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


def _ring_lnglat(geometry: list) -> Optional[list]:
    """Cleaned, **closed** ring of ``[lng, lat]`` pairs (GeoJSON order) from an
    Overpass ``geom`` way (a list of ``{"lat","lon"}``). ``None`` for a
    degenerate ring (fewer than 3 distinct vertices). The ring is what lets the
    shapely shadow path cast the building's true footprint."""
    pts = [[float(g["lon"]), float(g["lat"])] for g in geometry
           if "lat" in g and "lon" in g]
    # Distinct vertices, ignoring a closing duplicate.
    core = pts[:-1] if len(pts) > 1 and pts[0] == pts[-1] else pts
    if len(core) < 3:
        return None
    ring = list(core)
    ring.append(ring[0])            # close the ring
    return ring


def ring_centroid(ring_lnglat: list) -> Optional[tuple]:
    """``(lat, lng)`` centroid of a ring of ``[lng, lat]`` pairs, or ``None``
    for a degenerate ring (<3 distinct vertices)."""
    pts = [(p[1], p[0]) for p in (ring_lnglat or []) if len(p) >= 2]
    if len(pts) > 1 and pts[0] == pts[-1]:
        pts = pts[:-1]              # drop closing duplicate
    if len(pts) < 3:
        return None
    clat = sum(p[0] for p in pts) / len(pts)
    clng = sum(p[1] for p in pts) / len(pts)
    return (clat, clng)


def ring_radius_m(ring_lnglat: list, center: Optional[tuple] = None) -> float:
    """Enclosing radius in metres: the max distance from ``center`` (``(lat,
    lng)``; defaults to the ring centroid) to any vertex of ``ring_lnglat`` (a
    ring of ``[lng, lat]`` pairs). ``0.0`` for an empty ring.

    Shared by the OSM import, the drawn-shape, and the footprint-edit paths so
    they all size a footprint's ``canopy_radius_m`` identically — covering the
    structure for keep-out and the circle fallback."""
    pts = [(p[1], p[0]) for p in (ring_lnglat or []) if len(p) >= 2]
    if not pts:
        return 0.0
    if center is None:
        # Drop a closing-duplicate vertex so it doesn't skew the centroid
        # (mirrors ring_centroid); the max scan below still covers every vertex.
        core = pts[:-1] if len(pts) > 1 and pts[0] == pts[-1] else pts
        clat = sum(p[0] for p in core) / len(core)
        clng = sum(p[1] for p in core) / len(core)
    else:
        clat, clng = center
    cos_lat = math.cos(clat * math.pi / 180) or 1e-9
    radius = 0.0
    for la, ln in pts:
        dx = (ln - clng) * 111320.0 * cos_lat
        dy = (la - clat) * 111320.0
        radius = max(radius, math.hypot(dx, dy))
    return radius


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
            ring = _ring_lnglat(el.get("geometry", []) or [])
            if ring is None:
                continue
            c = ring_centroid(ring)
            if c is None:
                continue
            clat, clng = c
            out.append({"kind": "building", "lat": clat, "lng": clng,
                        "height_m": _parse_height(
                            tags, _DEFAULT_BUILDING_HEIGHT_M),
                        "radius_m": max(1.0, ring_radius_m(ring, (clat, clng))),
                        "footprint": ring})
        elif etype == "relation" and tags.get("building"):
            # Multipolygon building (V2.13): each *closed* outer-role member
            # ring becomes a footprint (tags/height come from the relation).
            # Outers split across several unclosed way fragments would need
            # arc-stitching — skipped rather than force-closed into garbage.
            for m in el.get("members", []) or []:
                if m.get("type") != "way" or m.get("role") not in ("outer", ""):
                    continue
                geometry = m.get("geometry", []) or []
                if (len(geometry) < 4
                        or geometry[0].get("lat") != geometry[-1].get("lat")
                        or geometry[0].get("lon") != geometry[-1].get("lon")):
                    continue                     # unclosed fragment — skip
                ring = _ring_lnglat(geometry)
                if ring is None:
                    continue
                c = ring_centroid(ring)
                if c is None:
                    continue
                clat, clng = c
                out.append({"kind": "building", "lat": clat, "lng": clng,
                            "height_m": _parse_height(
                                tags, _DEFAULT_BUILDING_HEIGHT_M),
                            "radius_m": max(1.0, ring_radius_m(
                                ring, (clat, clng))),
                            "footprint": ring})
    return out


def fetch_existing_features(bbox: dict, *, trees: bool = True,
                            buildings: bool = True) -> Optional[dict]:
    """Fetch existing trees and/or buildings in ``bbox`` from OSM. Returns
    ``{"trees": [...], "buildings": [...]}``, or **None when the network
    fetch failed** (timeout / rate-limit / server busy, after retry + mirror).
    A None must be reported as a failure — for years a failed request was
    silently rendered as "Found 0 buildings", which is a lie (V2.13)."""
    if not (trees or buildings):
        return {"trees": [], "buildings": []}
    data = _fetch_overpass(_query(bbox, trees, buildings))
    if data is None:
        return None
    feats = parse_elements(data)
    return {
        "trees": [f for f in feats if f["kind"] == "tree"],
        "buildings": [f for f in feats if f["kind"] == "building"],
    }


def fetch_buildings(bbox: dict) -> list[dict]:
    """Buildings only; keeps the legacy []-on-failure contract for the bulk
    downloader (which has its own retry/progress handling)."""
    res = fetch_existing_features(bbox, trees=False, buildings=True)
    return res["buildings"] if res else []


def fetch_trees(bbox: dict) -> list[dict]:
    res = fetch_existing_features(bbox, trees=True, buildings=False)
    return res["trees"] if res else []


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


def _osm_building_feature(item: dict) -> Optional[dict]:
    """Build a shade-casting ``canopy_footprint`` Polygon feature from an OSM
    building dict carrying a ``footprint`` ring. Mirrors
    ``footprint_extract.add_extracted_footprints`` so the building renders as a
    true outline AND casts a true-shape shadow, while ``canopy_radius_m`` + a
    stored centroid keep the keep-out (``src/exclusion.py``) and circle fallback
    working. ``None`` when the footprint is missing/degenerate (caller then
    falls back to a Point ``existing_building``).

    The ``shape_id`` is a fresh uuid so it can never collide with an existing or
    re-imported footprint (a count/time-based scheme could repeat after a
    building is deleted, or for two imports in the same millisecond)."""
    import uuid
    footprint = item.get("footprint")
    if not footprint or len(footprint) < 4:
        return None
    coords = [[float(p[0]), float(p[1])] for p in footprint]
    if coords[0] != coords[-1]:
        coords.append(coords[0])            # close the ring
    return {
        "type": "Feature",
        "geometry": {"type": "Polygon", "coordinates": [coords]},
        "properties": {
            "element_type": "canopy_footprint",
            "shape_id": f"shape_osm_{uuid.uuid4().hex[:12]}",
            "label": "Building (OSM)",
            "shape_type": "Building (OSM)",
            "fill_color": "#8d6e63",
            "stroke_color": "#5d4037",
            "fill_opacity": 0.3,
            "dash_array": "",
            "height_m": float(item.get("height_m") or _DEFAULT_BUILDING_HEIGHT_M),
            "cast_shade": True,
            # Centroid + radius let keepout_circles / the circle fallback treat
            # the polygon like the old point building without re-deriving them.
            "canopy_radius_m": float(item.get("radius_m") or 4.0),
            "lat": float(item["lat"]), "lng": float(item["lng"]),
            "source": "osm",
        },
    }


def add_features_to_project(features: list[dict], project_dict: dict) -> int:
    """Append OSM-derived existing trees/buildings to a project's feature list,
    skipping any that duplicate a feature already present. Returns the number
    added. Pure (mutates the dict in place); the GUI calls this on the main
    thread after the off-thread fetch.

    Trees become ``existing_tree`` Points (canopy circle). Buildings with a true
    footprint become shade-casting ``canopy_footprint`` Polygons (V1.58) so they
    render as real outlines and cast true-shape shadows; a building without a
    usable ring falls back to the legacy ``existing_building`` Point."""
    feats = project_dict.setdefault("features", [])
    existing_pts = []
    for f in feats:
        props = f.get("properties") or {}
        et = props.get("element_type")
        geom = f.get("geometry") or {}
        if et in ("existing_tree", "existing_building"):
            c = geom.get("coordinates") or []
            if len(c) >= 2:
                existing_pts.append((c[1], c[0]))
        elif et == "canopy_footprint" and props.get("source") == "osm":
            la, ln = props.get("lat"), props.get("lng")
            if la is None or ln is None:
                ring = (geom.get("coordinates") or [None])[0]
                cc = ring_centroid(ring) if ring else None
                la, ln = cc if cc else (None, None)
            if la is not None and ln is not None:
                existing_pts.append((la, ln))
    added = 0
    for item in features or []:
        lat, lng = item.get("lat"), item.get("lng")
        # ``dedupe_m`` lets a source scale the duplicate radius with the
        # feature it detected (tree_detect: a crown centred inside an
        # already-known crown is the same tree). Default stays 2 m.
        if lat is None or lng is None or _too_close(
                lat, lng, existing_pts,
                min_m=float(item.get("dedupe_m") or 2.0)):
            continue
        if item.get("kind") == "building":
            feat = _osm_building_feature(item)
            if feat is not None:
                feats.append(feat)
                existing_pts.append((lat, lng))
                added += 1
                continue
        # Tree, or a building with no usable footprint → legacy Point feature.
        # Items may override label/source (e.g. tree_detect's imagery-derived
        # trees, V2.26) and declare foliage; absent keys keep OSM semantics.
        etype = ("existing_tree" if item.get("kind") == "tree"
                 else "existing_building")
        props = {
            "element_type": etype,
            "height_m": float(item.get("height_m") or (
                _DEFAULT_TREE_HEIGHT_M if etype == "existing_tree"
                else _DEFAULT_BUILDING_HEIGHT_M)),
            "canopy_radius_m": float(item.get("radius_m") or (
                _DEFAULT_TREE_RADIUS_M if etype == "existing_tree"
                else 4.0)),
            "label": item.get("label") or (
                "Tree (OSM)" if etype == "existing_tree"
                else "Building (OSM)"),
            "struct_id": etype,
            "source": item.get("source") or "osm",
        }
        if etype == "existing_tree" and item.get("foliage"):
            props["tree_foliage"] = item["foliage"]
        feats.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [lng, lat]},
            "properties": props,
        })
        existing_pts.append((lat, lng))
        added += 1
    return added


# ── Qt worker thread (optional; mirrors shade.ShadeWorker) ───────────────────
# Defined only when PyQt6 is importable so the pure fetch above stays usable
# headless. The GUI runs fetch_existing_features off the UI thread because it
# does a network Overpass query.
try:
    from PyQt6.QtCore import QObject, pyqtSignal
    _HAVE_QT = True
except ImportError:
    _HAVE_QT = False

if _HAVE_QT:
    class OSMWorker(QObject):
        """Fetch existing OSM features for a bbox off the UI thread.

            worker = OSMWorker(bbox)
            worker.ready.connect(on_ready)   # emits the fetch result, or None
        """

        ready = pyqtSignal(object)
        finished = pyqtSignal()

        def __init__(self, bbox, parent=None):
            super().__init__(parent)
            self._bbox = bbox

        def run(self):
            try:
                res = fetch_existing_features(self._bbox)
            except Exception:  # noqa: BLE001 — never crash the worker thread
                res = None
            self.ready.emit(res)
            self.finished.emit()


def pad_bbox(bbox: dict, metres: float) -> dict:
    """Grow a bbox by ``metres`` on every side. Load-bearing for the import
    (V2.13): Overpass returns a building way only when at least one of its
    *corner nodes* falls inside the box, so a boundary drawn tight over a big
    building can contain the building but none of its corners — the margin
    catches them (the full footprint comes back via ``out geom`` regardless)."""
    clat = (bbox["south"] + bbox["north"]) / 2.0
    dlat = metres / 111320.0
    dlng = metres / (111320.0 * max(1e-9, math.cos(clat * math.pi / 180)))
    return {"south": bbox["south"] - dlat, "north": bbox["north"] + dlat,
            "west": bbox["west"] - dlng, "east": bbox["east"] + dlng}


def bbox_with_area_note(boundary, site_config: dict,
                        radius_m: float = 60.0, pad_m: float = 30.0):
    """``(bbox, note)``: the search bbox plus a human description of what area
    it covers, so the import status can say exactly what was searched.
    Boundary path = the polygon's bounding box grown by ``pad_m``; fallback =
    a square of half-extent ``radius_m`` around the property pin. ``(None,
    "")`` when neither exists. Pure geometry, shared by the OSM + footprint
    import flows."""
    if boundary and len(boundary) >= 3:
        lats = [p[0] for p in boundary]
        lngs = [p[1] for p in boundary]
        raw = {"north": max(lats), "south": min(lats),
               "east": max(lngs), "west": min(lngs)}
        return (pad_bbox(raw, pad_m) if pad_m > 0 else raw,
                f"your boundary + {pad_m:.0f} m margin")
    lat, lng = site_config.get("latitude"), site_config.get("longitude")
    if lat is None or lng is None:
        return None, ""
    cos_lat = math.cos(lat * math.pi / 180) or 1e-9
    dlat = radius_m / 111320.0
    dlng = radius_m / (111320.0 * cos_lat)
    return ({"north": lat + dlat, "south": lat - dlat,
             "east": lng + dlng, "west": lng - dlng},
            f"≈{radius_m:.0f} m around the pin — draw a property boundary "
            "to control the area")


def bbox_from_boundary_or_pin(boundary, site_config: dict,
                              radius_m: float = 60.0):
    """Back-compat wrapper over :func:`bbox_with_area_note` (bbox only)."""
    return bbox_with_area_note(boundary, site_config, radius_m=radius_m)[0]


# ── Boundary-precise filtering (V2.13) ───────────────────────────────────────
# The Overpass query has to be a bbox, but the user drew a *polygon* — and a
# padded bbox happily scoops up the neighbours' whole block corner. These
# pure-Python helpers (no shapely; it's an optional dependency) clip the
# results back to the drawn boundary plus a user-controlled neighbour margin.

def _point_in_polygon(lat: float, lng: float, poly: list) -> bool:
    """Ray-cast point-in-polygon; ``poly`` = [(lat, lng), …] (open or closed)."""
    n = len(poly)
    if n < 3:
        return False
    inside = False
    j = n - 1
    for i in range(n):
        yi, xi = poly[i][0], poly[i][1]
        yj, xj = poly[j][0], poly[j][1]
        if (yi > lat) != (yj > lat):
            x_cross = xj + (lat - yj) / (yi - yj) * (xi - xj)
            if lng < x_cross:
                inside = not inside
        j = i
    return inside


def _dist_to_polygon_m(lat: float, lng: float, poly: list) -> float:
    """Min distance (metres, equirectangular) from a point to the polygon's
    edges. Zero-ish for points on the boundary; combine with
    :func:`_point_in_polygon` for interior points."""
    if not poly:
        return float("inf")
    cos_lat = math.cos(lat * math.pi / 180) or 1e-9

    def _xy(p):
        return ((p[1] - lng) * 111320.0 * cos_lat, (p[0] - lat) * 111320.0)

    best = float("inf")
    n = len(poly)
    for i in range(n):
        ax, ay = _xy(poly[i])
        bx, by = _xy(poly[(i + 1) % n])
        dx, dy = bx - ax, by - ay
        seg2 = dx * dx + dy * dy
        t = 0.0 if seg2 <= 1e-12 else max(
            0.0, min(1.0, -(ax * dx + ay * dy) / seg2))
        px, py = ax + t * dx, ay + t * dy
        best = min(best, math.hypot(px, py))
    return best


def _feature_near_boundary(item: dict, boundary: list, margin_m: float) -> bool:
    """True when the feature touches the boundary polygon or comes within
    ``margin_m`` of it: centroid or any footprint vertex inside / near."""
    pts = [(item.get("lat"), item.get("lng"))]
    for p in item.get("footprint") or []:
        pts.append((p[1], p[0]))                 # footprint is [lng, lat]
    for la, ln in pts:
        if la is None or ln is None:
            continue
        if _point_in_polygon(la, ln, boundary):
            return True
        if margin_m > 0 and _dist_to_polygon_m(la, ln, boundary) <= margin_m:
            return True
    return False


def filter_to_boundary(feats: list, boundary, margin_m: float = 30.0):
    """Split fetched features into (kept, n_inside, n_neighbours) against the
    drawn boundary polygon: inside = centroid inside; neighbour = within
    ``margin_m`` of the edge (their shade still falls on the site). With no
    usable boundary everything is kept (bbox semantics, the pin fallback)."""
    if not boundary or len(boundary) < 3:
        return list(feats or []), len(feats or []), 0
    kept, n_inside, n_neigh = [], 0, 0
    for item in feats or []:
        la, ln = item.get("lat"), item.get("lng")
        centroid_inside = (la is not None and ln is not None
                           and _point_in_polygon(la, ln, boundary))
        if centroid_inside:
            kept.append(item)
            n_inside += 1
        elif _feature_near_boundary(item, boundary, margin_m):
            kept.append(item)
            n_neigh += 1
    return kept, n_inside, n_neigh


def import_osm_result(res: Optional[dict], project_dict: dict, *,
                      boundary=None, margin_m: float = 30.0,
                      area_note: str = "") -> dict:
    """Filter a fetch result to the boundary, add to the project, and compose
    the status message — the whole import tail in one pure, testable call
    (the map controller sits at its line ceiling). Returns
    ``{"added": int, "kept": int, "found": int, "message": str}``;
    ``res=None`` (network failure) produces added=0 and the honest message."""
    if res is None:
        return {"added": 0, "kept": 0, "found": 0,
                "message": ("OpenStreetMap didn't answer (busy or offline) — "
                            "nothing was imported. Wait ~30 s and try again.")}
    feats = list(res.get("buildings", [])) + list(res.get("trees", []))
    kept, n_inside, n_neigh = filter_to_boundary(feats, boundary, margin_m)
    added = add_features_to_project(kept, project_dict)
    msg = f"Found {len(feats)} nearby; "
    if boundary and len(boundary) >= 3:
        msg += (f"kept {len(kept)} ({n_inside} inside your boundary + "
                f"{n_neigh} neighbour{'s' if n_neigh != 1 else ''} within "
                f"{margin_m:.0f} m); ")
    elif area_note:
        msg += f"searched {area_note}; "
    msg += f"added {added} new."
    if added or len(kept):
        msg += (" Click an imported outline and press Delete to drop any "
                "you don't want.")
    elif not feats:
        msg += (" OSM knows no buildings/trees here — anything missing can "
                "be drawn by hand below.")
    return {"added": added, "kept": len(kept), "found": len(feats),
            "message": msg}

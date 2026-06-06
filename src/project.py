"""
project.py — Save/load PermaDesign projects as GeoJSON (Step 4 implementation).

For Step 1 this provides a minimal stub with the data structures defined,
but no file I/O yet.  The full implementation comes in Step 4.
"""

import json
import os
from datetime import datetime, timezone
from typing import Optional


def _utc_now_iso() -> str:
    """Naive-UTC ISO timestamp, matching the legacy datetime.utcnow()
    output exactly while avoiding its Python 3.12+ deprecation warning."""
    return datetime.now(timezone.utc).replace(tzinfo=None).isoformat()

# 1.7 (V1.48): added the `existing_tree` / `existing_building` feature types
# (user-marked shade casters). Additive — older readers ignore unknown
# element_types in project_to_map_data, so projects stay forward/backward
# compatible.
SCHEMA_VERSION = "1.7"


def new_placement_group_id() -> str:
    """Generate a fresh unique placement group identifier.

    Plants placed by the same gesture (Single click, Row, Grid, Circle, Polyculture)
    share a group id so they can be selected/deleted as one unit.
    """
    import uuid
    return "pg_" + uuid.uuid4().hex[:10]


def community_id_for(center_lat, center_lng):
    """Stable per-instance key for a placed community, derived from its
    anchor centre. Members of the same community instance share this key so
    the map can isolate one community within a row/grid of communities (which
    all share a single placement_group_id). Returns ``None`` for plants that
    have no community centre.
    """
    if center_lat is None or center_lng is None:
        return None
    return f"{round(float(center_lat), 6)}_{round(float(center_lng), 6)}"


def new_project(name: str = "Untitled Design") -> dict:
    """Return a fresh empty project dict."""
    return {
        "type": "FeatureCollection",
        "properties": {
            "schema_version": SCHEMA_VERSION,
            "project_name": name,
            "created": _utc_now_iso(),
            "hardiness_zone": None,
            "notes": "",
            "site_config": {
                "latitude": None,
                "longitude": None,
                "area_m2": None,
                "hardiness_zone": None,
                "soil_type": None,
                "sun_exposure": None,
                "wind_exposure": None,
                "priorities": [],
            }
        },
        "features": []
    }


def save_project(project: dict, path: str) -> None:
    """Write project dict to a .perma.geojson file."""
    with open(path, "w", encoding="utf-8") as f:
        json.dump(project, f, indent=2)


def load_project(path: str) -> dict:
    """Read and return a project dict from a .perma.geojson file."""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def feature_to_shape(feature: dict) -> Optional[dict]:
    """Convert one ``custom_shape`` / ``canopy_footprint`` Polygon feature to the
    map-widget shape dict (``loadShape`` input), or ``None`` if it isn't a usable
    polygon. Shared by ``project_to_map_data`` and the footprint-import path so
    both build the shape dict identically (id + height round-trip)."""
    geom = feature.get("geometry", {})
    if geom.get("type") != "Polygon":
        return None
    coords = geom.get("coordinates") or []
    if not coords:
        return None
    props = feature.get("properties", {})
    points = [[pt[1], pt[0]] for pt in coords[0]]   # (lng,lat) → (lat,lng)
    if len(points) > 1 and points[0] == points[-1]:
        points = points[:-1]                        # drop closing duplicate
    if len(points) < 3:
        return None
    # canopy_footprint carries a height (it casts shade); plain shapes default
    # to 0. `or 0.0` coalesces a demoted shape's explicit None height.
    return {
        "points": points,
        "shape_id": props.get("shape_id"),
        "shape_type": props.get("shape_type", "Custom"),
        "label": props.get("label", ""),
        "fill_color": props.get("fill_color", "#4caf50"),
        "stroke_color": props.get("stroke_color", "#2e7d32"),
        "fill_opacity": props.get("fill_opacity", 0.25),
        "dash_array": props.get("dash_array", ""),
        "height_m": props.get("height_m") or 0.0,
    }


def update_shape_geometry(project: dict, shape_id: str,
                          points_latlng: list) -> bool:
    """Rewrite a ``custom_shape`` / ``canopy_footprint`` feature's polygon to a
    new outline after a map vertex-drag edit. ``points_latlng`` is the open ring
    the map sends (a list of ``[lat, lng]`` vertices). Re-sizes the footprint's
    ``canopy_radius_m`` from the new ring, and refreshes the stored centroid for
    OSM buildings, so keep-out (``src/exclusion.py``) and the circle fallback
    stay in step with the edited shape. Returns True when a matching shape was
    updated. Pure — mutates ``project`` in place (Qt-free, unit-testable)."""
    if not points_latlng or len(points_latlng) < 3:
        return False
    from src.osm_features import ring_radius_m, ring_centroid
    ring = [[pt[1], pt[0]] for pt in points_latlng]    # [lat,lng] → [lng,lat]
    ring.append(ring[0])                               # close the ring
    for f in project.get("features", []):
        props = f.get("properties", {}) or {}
        if props.get("shape_id") != shape_id:
            continue
        geom = f.setdefault("geometry", {})
        geom["type"] = "Polygon"
        geom["coordinates"] = [ring]
        if (props.get("cast_shade")
                or props.get("element_type") == "canopy_footprint"):
            props["canopy_radius_m"] = max(0.5, ring_radius_m(ring))
            if props.get("source") == "osm":
                c = ring_centroid(ring)
                if c:
                    props["lat"], props["lng"] = c
        return True
    return False


def project_to_map_data(project: dict) -> dict:
    """
    Extract map elements from the project for loading into the map widget.
    Returns dict with boundaries (list), plants, structures, hedgerows, shapes.
    """
    result = {
        "boundaries": [],   # list of {id, points, color, showLengths, showArea}
        "boundary": None,   # kept for backward compat — first boundary's points
        "plants": [],
        "structures": [],
        "hedgerows": [],
        "shapes": [],
        "contours": [],
        "auto_contours": [],   # auto-generated contour features (MultiLineString)
        "slope_overlay": None, # cached slope-overlay metadata (PNG regenerated on demand)
    }
    for feature in project.get("features", []):
        props = feature.get("properties", {})
        geom  = feature.get("geometry", {})
        etype = props.get("element_type")

        if etype == "property_boundary" and geom.get("type") == "Polygon":
            ring = geom["coordinates"][0]
            pts = [[pt[1], pt[0]] for pt in ring]
            bd = {
                "id":          props.get("boundary_id", f"b_loaded_{len(result['boundaries'])}"),
                "points":      pts,
                "color":       props.get("color", "green"),
                "showLengths": props.get("show_lengths", True),
                "showArea":    props.get("show_area", True),
            }
            result["boundaries"].append(bd)
            if result["boundary"] is None:
                result["boundary"] = pts   # backward compat

        elif etype == "plant" and geom.get("type") == "Point":
            lng, lat = geom["coordinates"]
            # Backward compat: legacy projects have no placement_group_id —
            # assign a fresh unique one so each pre-existing plant becomes a
            # singleton group. This keeps the group abstraction uniform and
            # lets group-delete operate consistently.
            group_id = props.get("placement_group_id") or new_placement_group_id()
            result["plants"].append({
                "plant_id":    props.get("plant_id", 0),
                "common_name": props.get("common_name", "Unknown"),
                "lat": lat,
                "lng": lng,
                "placement_group_id": group_id,
                "polyculture_name": props.get("polyculture_name", ""),
                "polyculture_center_lat": props.get("polyculture_center_lat"),
                "polyculture_center_lng": props.get("polyculture_center_lng"),
            })

        elif etype in ("existing_tree", "existing_building") \
                and geom.get("type") == "Point":
            # V1.49: user-marked existing trees/buildings. Reconstruct a
            # structure-style def so they render through the same map path
            # (loadStructure) on reload.
            lng, lat = geom["coordinates"]
            from src.db.structures import existing_feature_def
            sid = ("existing_tree" if etype == "existing_tree"
                   else "existing_building")
            size_m = props.get("size_m")
            if not size_m:
                size_m = float(props.get("canopy_radius_m", 3.0)) * 2.0
            sd = existing_feature_def(sid, size_m=size_m,
                                      height_m=props.get("height_m") or 6.0)
            sd["name"] = props.get("label", sd["name"])
            result["structures"].append({
                "lat": lat, "lng": lng, "struct_def": sd,
            })

        elif etype == "structure" and geom.get("type") == "Point":
            lng, lat = geom["coordinates"]
            result["structures"].append({
                "lat": lat,
                "lng": lng,
                "struct_def": props.get("struct_def", {}),
            })

        elif etype == "hedgerow" and geom.get("type") == "LineString":
            points = [[pt[1], pt[0]] for pt in geom["coordinates"]]
            result["hedgerows"].append({
                "points": points,
                "style": props.get("style", "hedge"),
                "color": props.get("color", "#4caf50"),
                "width_m": props.get("width_m", 1.5),
                "spacing_m": props.get("spacing_m", 1.0),
                "species": props.get("species", ""),
            })

        elif (etype in ("custom_shape", "canopy_footprint")
              and geom.get("type") == "Polygon"):
            sh = feature_to_shape(feature)
            if sh:
                result["shapes"].append(sh)

        elif etype == "contour_line" and geom.get("type") == "LineString":
            points = [[pt[1], pt[0]] for pt in geom["coordinates"]]
            result["contours"].append({
                "points": points,
                "elevation_m": props.get("elevation_m", 0),
                "color": props.get("color", "#795548"),
            })

        elif etype == "auto_contour":
            segments_lnglat = []
            if geom.get("type") == "MultiLineString":
                segments_lnglat = geom.get("coordinates") or []
            elif geom.get("type") == "LineString":
                segments_lnglat = [geom.get("coordinates") or []]
            segments = [
                [[pt[1], pt[0]] for pt in seg]
                for seg in segments_lnglat if len(seg) >= 2
            ]
            if segments:
                result["auto_contours"].append({
                    "elevation_m": props.get("elevation_m", 0),
                    "color":       props.get("color", "#5d4037"),
                    "segments":    segments,
                })

        elif etype == "slope_overlay":
            result["slope_overlay"] = {
                "bbox":         props.get("bbox") or {},
                "stats":        props.get("stats") or {},
                "interval_m":   props.get("interval_m"),
                "resolution_m": props.get("resolution_m"),
                "source":       props.get("source", ""),
            }

    return result

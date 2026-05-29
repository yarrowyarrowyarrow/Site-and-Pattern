"""
project.py — Save/load PermaDesign projects as GeoJSON (Step 4 implementation).

For Step 1 this provides a minimal stub with the data structures defined,
but no file I/O yet.  The full implementation comes in Step 4.
"""

import json
import os
from datetime import datetime, timezone


def _utc_now_iso() -> str:
    """Naive-UTC ISO timestamp, matching the legacy datetime.utcnow()
    output exactly while avoiding its Python 3.12+ deprecation warning."""
    return datetime.now(timezone.utc).replace(tzinfo=None).isoformat()

SCHEMA_VERSION = "1.6"


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

        elif etype == "custom_shape" and geom.get("type") == "Polygon":
            ring = geom["coordinates"][0]
            points = [[pt[1], pt[0]] for pt in ring]
            # Remove closing duplicate if present
            if len(points) > 1 and points[0] == points[-1]:
                points = points[:-1]
            result["shapes"].append({
                "points": points,
                "shape_type": props.get("shape_type", "Custom"),
                "label": props.get("label", ""),
                "fill_color": props.get("fill_color", "#4caf50"),
                "stroke_color": props.get("stroke_color", "#2e7d32"),
                "fill_opacity": props.get("fill_opacity", 0.25),
                "dash_array": props.get("dash_array", ""),
            })

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

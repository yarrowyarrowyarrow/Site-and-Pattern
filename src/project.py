"""
project.py — Save/load PermaDesign projects as GeoJSON (Step 4 implementation).

For Step 1 this provides a minimal stub with the data structures defined,
but no file I/O yet.  The full implementation comes in Step 4.
"""

import json
import os
from datetime import datetime

SCHEMA_VERSION = "1.5"


def new_project(name: str = "Untitled Design") -> dict:
    """Return a fresh empty project dict."""
    return {
        "type": "FeatureCollection",
        "properties": {
            "schema_version": SCHEMA_VERSION,
            "project_name": name,
            "created": datetime.utcnow().isoformat(),
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
    Returns dict with boundary, plants, zone_center, structures, hedgerows, shapes.
    """
    result = {
        "boundary": None,
        "plants": [],
        "zone_center": None,
        "structures": [],
        "hedgerows": [],
        "shapes": [],
        "contours": [],
    }
    for feature in project.get("features", []):
        props = feature.get("properties", {})
        geom  = feature.get("geometry", {})
        etype = props.get("element_type")

        if etype == "property_boundary" and geom.get("type") == "Polygon":
            ring = geom["coordinates"][0]
            result["boundary"] = [[pt[1], pt[0]] for pt in ring]

        elif etype == "plant" and geom.get("type") == "Point":
            lng, lat = geom["coordinates"]
            result["plants"].append({
                "plant_id":    props.get("plant_id", 0),
                "common_name": props.get("common_name", "Unknown"),
                "lat": lat,
                "lng": lng
            })

        elif etype == "zone_center" and geom.get("type") == "Point":
            lng, lat = geom["coordinates"]
            result["zone_center"] = (lat, lng)

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

    return result

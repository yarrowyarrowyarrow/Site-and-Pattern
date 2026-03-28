"""
project.py — Save/load PermaDesign projects as GeoJSON (Step 4 implementation).

For Step 1 this provides a minimal stub with the data structures defined,
but no file I/O yet.  The full implementation comes in Step 4.
"""

import json
import os
from datetime import datetime


def new_project(name: str = "Untitled Design") -> dict:
    """Return a fresh empty project dict."""
    return {
        "type": "FeatureCollection",
        "properties": {
            "project_name": name,
            "created": datetime.utcnow().isoformat(),
            "hardiness_zone": None,
            "notes": ""
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
    Returns {'boundary': [...], 'plants': [...], 'zone_center': (lat, lng) or None}
    """
    result = {"boundary": None, "plants": [], "zone_center": None}
    for feature in project.get("features", []):
        props = feature.get("properties", {})
        geom  = feature.get("geometry", {})
        etype = props.get("element_type")

        if etype == "property_boundary" and geom.get("type") == "Polygon":
            # GeoJSON uses [lng, lat]; Leaflet wants [lat, lng]
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

    return result

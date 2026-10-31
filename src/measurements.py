"""
measurements.py — a measurement drawn on the map is part of the design (F215,
V3.11).

Until V3.11 a measurement lived only in the map page (``html/map/04-tools.js``):
Python never heard of one, so undo, which works on ``project["features"]``,
could not take it back, and Ctrl+Z straight after measuring undid whatever came
before it. The selection box could not catch one, nothing saved it, and nothing
cleared it, so the last design's measurements stayed on the map through New,
Open and every undo.

Now each is a feature, like a map note: a two-point ``LineString`` in GeoJSON's
``[lng, lat]`` order with ``element_type: "measurement"`` and the page's own
``measurement_id``. Its length is not stored: the page works it out from the
two points, the same way every time, so a stored copy could only disagree.

Qt-free, so the handlers that call it (``src/controllers/map_events.py``) and
the loader (``src/project.py``) are testable without a display.
"""

from __future__ import annotations

ELEMENT_TYPE = "measurement"


def _points(coords) -> list:
    """``[[lat, lng], [lat, lng]]`` as floats, or ``[]`` when not two points."""
    try:
        pts = [[float(p[0]), float(p[1])] for p in coords or []]
    except (TypeError, ValueError, IndexError):
        return []
    return pts if len(pts) == 2 else []


def measurement_feature(measure_id: str, coords) -> dict | None:
    """The feature for a measurement between two ``[lat, lng]`` points, or
    ``None`` when there are not two usable points."""
    pts = _points(coords)
    if not measure_id or not pts:
        return None
    return {
        "type": "Feature",
        "geometry": {"type": "LineString",
                     "coordinates": [[lng, lat] for lat, lng in pts]},
        "properties": {"element_type": ELEMENT_TYPE,
                       "measurement_id": str(measure_id)},
    }


def is_measurement(feature: dict) -> bool:
    return ((feature or {}).get("properties") or {}).get(
        "element_type") == ELEMENT_TYPE


def add_measurement(project: dict, measure_id: str, coords) -> bool:
    """Append one measurement; ``False`` (and nothing added) for bad input or
    an id the design already holds, so a page that says it twice adds one."""
    feat = measurement_feature(measure_id, coords)
    if feat is None:
        return False
    feats = project.setdefault("features", [])
    if any(is_measurement(f) and f["properties"].get("measurement_id")
           == feat["properties"]["measurement_id"] for f in feats):
        return False
    feats.append(feat)
    return True


def remove_measurements(project: dict, ids) -> int:
    """Remove the measurements with these ids; how many went."""
    wanted = {str(i) for i in ids or []}
    feats = project.get("features") or []
    kept = [f for f in feats
            if not (is_measurement(f)
                    and f["properties"].get("measurement_id") in wanted)]
    removed = len(feats) - len(kept)
    if removed:
        project["features"] = kept
    return removed


def to_map_data(feature: dict) -> dict | None:
    """``{"id", "points": [[lat, lng], [lat, lng]]}`` for the map's
    ``loadMeasurement``, or ``None`` for a feature that is not a usable one."""
    if not is_measurement(feature):
        return None
    geom = feature.get("geometry") or {}
    if geom.get("type") != "LineString":
        return None
    coords = geom.get("coordinates") or []
    pts = _points([[c[1], c[0]] for c in coords if len(c) >= 2])
    mid = feature["properties"].get("measurement_id")
    if not pts or not mid:
        return None
    return {"id": str(mid), "points": pts}

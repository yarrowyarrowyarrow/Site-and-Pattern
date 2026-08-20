"""
tests/test_map_features.py — Unit tests for map annotation features added in
the map-annotations branch: multi-boundary and zoom math.

Run with:
    python -m pytest tests/test_map_features.py -v
"""

import sys
import os
import math
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import src.project as project_io

# ─────────────────────────────────────────────────────────────────────────────
# Helpers mirroring the JS geometry functions so we can test round-trips
# ─────────────────────────────────────────────────────────────────────────────

def haversine_m(a, b):
    """Haversine distance in metres between two [lat, lng] points."""
    R = 6_371_000
    d_lat = math.radians(b[0] - a[0])
    d_lng = math.radians(b[1] - a[1])
    lat1 = math.radians(a[0])
    lat2 = math.radians(b[0])
    x = (math.sin(d_lat / 2) ** 2
         + math.cos(lat1) * math.cos(lat2) * math.sin(d_lng / 2) ** 2)
    return R * 2 * math.atan2(math.sqrt(x), math.sqrt(1 - x))


def shoelace_area_m2(points):
    """Approximate polygon area via projected Shoelace formula."""
    n = len(points)
    if n < 3:
        return 0.0
    R = 6_371_000
    lat0 = sum(p[0] for p in points) / n
    lng0 = sum(p[1] for p in points) / n
    cos_lat = math.cos(math.radians(lat0))
    proj = [
        ((p[0] - lat0) * math.pi / 180 * R,
         (p[1] - lng0) * math.pi / 180 * R * cos_lat)
        for p in points
    ]
    area = 0.0
    for i in range(n):
        j = (i + 1) % n
        area += proj[i][1] * proj[j][0]
        area -= proj[j][1] * proj[i][0]
    return abs(area) / 2


# ─────────────────────────────────────────────────────────────────────────────
# Boundary geometry tests
# ─────────────────────────────────────────────────────────────────────────────

# A simple 100m × 100m square centred near Edmonton
# Half-offset = 50m so each edge spans 100m
_CENTRE_LAT = 53.5461
_CENTRE_LNG = -113.4938
_HALF_DEG_LAT = 50 / 111_320
_HALF_DEG_LNG = 50 / (111_320 * math.cos(math.radians(_CENTRE_LAT)))

SQUARE_POINTS = [
    [_CENTRE_LAT - _HALF_DEG_LAT, _CENTRE_LNG - _HALF_DEG_LNG],
    [_CENTRE_LAT - _HALF_DEG_LAT, _CENTRE_LNG + _HALF_DEG_LNG],
    [_CENTRE_LAT + _HALF_DEG_LAT, _CENTRE_LNG + _HALF_DEG_LNG],
    [_CENTRE_LAT + _HALF_DEG_LAT, _CENTRE_LNG - _HALF_DEG_LNG],
]


def test_boundary_edge_lengths():
    """Each edge of the square should be ~100 m."""
    n = len(SQUARE_POINTS)
    for i in range(n):
        d = haversine_m(SQUARE_POINTS[i], SQUARE_POINTS[(i + 1) % n])
        assert 95 < d < 105, f"Edge {i} length {d:.1f} m not near 100 m"


def test_boundary_area():
    """Area of the square should be ~10 000 m²."""
    area = shoelace_area_m2(SQUARE_POINTS)
    assert 9_000 < area < 11_000, f"Area {area:.0f} m² not near 10 000 m²"


def test_translated_boundary_area_unchanged():
    """Translating all vertices should not change the area."""
    orig_area = shoelace_area_m2(SQUARE_POINTS)
    shifted = [[p[0] + 0.01, p[1] + 0.01] for p in SQUARE_POINTS]
    shifted_area = shoelace_area_m2(shifted)
    assert abs(orig_area - shifted_area) / orig_area < 0.01


def test_scaled_boundary_area():
    """Scaling by 2× from the centroid should give 4× area."""
    lat0 = sum(p[0] for p in SQUARE_POINTS) / len(SQUARE_POINTS)
    lng0 = sum(p[1] for p in SQUARE_POINTS) / len(SQUARE_POINTS)
    scaled = [
        [lat0 + (p[0] - lat0) * 2, lng0 + (p[1] - lng0) * 2]
        for p in SQUARE_POINTS
    ]
    orig_area   = shoelace_area_m2(SQUARE_POINTS)
    scaled_area = shoelace_area_m2(scaled)
    ratio = scaled_area / orig_area
    assert 3.8 < ratio < 4.2, f"Scale-2× area ratio {ratio:.3f} not near 4.0"


# ─────────────────────────────────────────────────────────────────────────────
# Multi-boundary project serialization round-trip
# ─────────────────────────────────────────────────────────────────────────────

def _make_project_with_boundaries(boundary_list):
    """Build a project dict containing the given boundaries."""
    proj = project_io.new_project("Test")
    for bd in boundary_list:
        pts = bd["points"]
        ring = [[p[1], p[0]] for p in pts] + [[pts[0][1], pts[0][0]]]
        proj["features"].append({
            "type": "Feature",
            "geometry": {"type": "Polygon", "coordinates": [ring]},
            "properties": {
                "element_type": "property_boundary",
                "boundary_id": bd["id"],
                "color": bd.get("color", "green"),
                "show_lengths": bd.get("show_lengths", True),
                "show_area": bd.get("show_area", True),
            }
        })
    return proj


def test_multi_boundary_round_trip_count():
    """project_to_map_data returns the same number of boundaries as stored."""
    boundaries = [
        {"id": "b1", "points": SQUARE_POINTS, "color": "red"},
        {"id": "b2", "points": [[p[0] + 0.05, p[1] + 0.05] for p in SQUARE_POINTS],
         "color": "blue"},
    ]
    proj = _make_project_with_boundaries(boundaries)
    data = project_io.project_to_map_data(proj)
    assert len(data["boundaries"]) == 2, (
        f"Expected 2 boundaries, got {len(data['boundaries'])}"
    )


def test_multi_boundary_round_trip_colors():
    """Per-boundary colors are preserved through serialize → deserialize."""
    boundaries = [
        {"id": "b1", "points": SQUARE_POINTS, "color": "magenta"},
        {"id": "b2", "points": [[p[0] + 0.05, p[1]] for p in SQUARE_POINTS],
         "color": "orange"},
    ]
    proj = _make_project_with_boundaries(boundaries)
    data = project_io.project_to_map_data(proj)
    colors = {bd["id"]: bd["color"] for bd in data["boundaries"]}
    assert colors["b1"] == "magenta"
    assert colors["b2"] == "orange"


def test_multi_boundary_round_trip_label_toggles():
    """show_lengths / show_area toggles are preserved."""
    boundaries = [
        {"id": "b1", "points": SQUARE_POINTS, "color": "green",
         "show_lengths": False, "show_area": True},
    ]
    proj = _make_project_with_boundaries(boundaries)
    data = project_io.project_to_map_data(proj)
    bd = data["boundaries"][0]
    assert bd["showLengths"] is False
    assert bd["showArea"] is True


def test_legacy_boundary_backward_compat():
    """Old projects with no boundary_id/color still load."""
    proj = project_io.new_project("Legacy")
    pts = SQUARE_POINTS
    ring = [[p[1], p[0]] for p in pts] + [[pts[0][1], pts[0][0]]]
    proj["features"].append({
        "type": "Feature",
        "geometry": {"type": "Polygon", "coordinates": [ring]},
        "properties": {"element_type": "property_boundary"},  # no id or color
    })
    data = project_io.project_to_map_data(proj)
    assert len(data["boundaries"]) == 1
    bd = data["boundaries"][0]
    assert bd["color"] == "green"       # default
    assert bd["showLengths"] is True    # default
    assert bd["showArea"] is True       # default


def test_multi_boundary_json_roundtrip(tmp_path):
    """Save and reload a project with multiple boundaries."""
    import tempfile, os
    boundaries = [
        {"id": f"b{i}", "points": [[p[0] + i * 0.01, p[1]] for p in SQUARE_POINTS],
         "color": c}
        for i, c in enumerate(["green", "red", "blue"])
    ]
    proj = _make_project_with_boundaries(boundaries)
    path = str(tmp_path / "test.perma.geojson")
    project_io.save_project(proj, path)
    loaded = project_io.load_project(path)
    data = project_io.project_to_map_data(loaded)
    assert len(data["boundaries"]) == 3
    loaded_colors = {bd["id"]: bd["color"] for bd in data["boundaries"]}
    assert loaded_colors == {"b0": "green", "b1": "red", "b2": "blue"}


# ─────────────────────────────────────────────────────────────────────────────
# Zoom step math
# ─────────────────────────────────────────────────────────────────────────────

def _scale_factor(zoom_delta: float) -> float:
    """Convert Leaflet zoomDelta to scale multiplier per scroll tick."""
    return 2 ** zoom_delta


def test_zoom_fine_approx_1_1x():
    """Fine sensitivity (zoomDelta=0.15) ≈ 1.1× per tick."""
    scale = _scale_factor(0.15)
    assert 1.09 < scale < 1.12, f"Fine zoom scale {scale:.4f} not near 1.1×"


def test_zoom_normal_approx_1_26x():
    """Normal sensitivity (zoomDelta=0.33) ≈ 1.26× per tick."""
    scale = _scale_factor(0.33)
    assert 1.24 < scale < 1.28, f"Normal zoom scale {scale:.4f} not near 1.26×"


def test_zoom_fast_approx_1_5x():
    """Fast sensitivity (zoomDelta=0.58) ≈ 1.49× per tick."""
    scale = _scale_factor(0.58)
    assert 1.47 < scale < 1.52, f"Fast zoom scale {scale:.4f} not near 1.5×"


def test_zoom_coarse_approx_2x():
    """Coarse sensitivity (zoomDelta=1.0) = exactly 2× per tick."""
    scale = _scale_factor(1.0)
    assert abs(scale - 2.0) < 1e-9, f"Coarse zoom scale {scale:.4f} not 2×"


# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import inspect
    import pathlib
    import tempfile

    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    passed = failed = 0
    for fn in tests:
        try:
            params = inspect.signature(fn).parameters
            if "tmp_path" in params:
                # Mimic pytest's tmp_path fixture: a fresh pathlib.Path per test.
                with tempfile.TemporaryDirectory() as td:
                    fn(pathlib.Path(td))
            else:
                fn()
            print(f"  PASS  {fn.__name__}")
            passed += 1
        except AssertionError as e:
            print(f"  FAIL  {fn.__name__}: {e}")
            failed += 1
        except Exception as e:
            print(f"  ERROR {fn.__name__}: {e}")
            failed += 1
    print(f"\n{passed} passed, {failed} failed of {passed + failed}.")
    sys.exit(0 if failed == 0 else 1)

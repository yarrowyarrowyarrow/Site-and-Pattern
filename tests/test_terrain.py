"""
tests/test_terrain.py — Unit tests for the auto-terrain generator.

Covers the pure-Python helpers (no PyQt6, no network):
  * bbox sizing / validation
  * grid sampling layout
  * marching squares on synthetic ramps and cones
  * slope grid central differences
  * slope-to-RGBA palette binning
  * minimal PNG encoder
  * edmonton field detection (mocked HTTP)
  * generate_terrain orchestration with monkeypatched fetchers
"""

import io
import math
import os
import struct
import sys
import zlib

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import src.terrain as t


# Simple bbox covering ~110 m × 65 m at lat 53.5 (Edmonton-ish).
BBOX = {"south": 53.5, "north": 53.501, "west": -113.5, "east": -113.499}


# ── bbox / projection ───────────────────────────────────────────────────────

def test_metres_per_deg_at_equator_and_pole():
    mlat_eq, mlng_eq = t.metres_per_deg(0.0)
    assert math.isclose(mlat_eq, 111320.0, rel_tol=1e-9)
    assert math.isclose(mlng_eq, 111320.0, rel_tol=1e-9)
    mlat_p, mlng_p = t.metres_per_deg(89.999)
    assert mlat_p > 0 and mlng_p > 0   # safe at the pole (no div-by-zero)


def test_bbox_size_m_reasonable():
    w, h = t.bbox_size_m(BBOX)
    # 0.001° lat ≈ 111.3 m, 0.001° lng at lat 53.5 ≈ 66 m
    assert 110 < h < 113
    assert 65 < w < 67


def test_bbox_in_edmonton():
    assert t.bbox_in_edmonton(BBOX) is True
    far = {"south": 49.0, "north": 49.001, "west": -123.0, "east": -122.999}
    assert t.bbox_in_edmonton(far) is False


def test_grid_dims_min_two():
    cols, rows = t.grid_dims(BBOX, 10.0)
    assert cols >= 2 and rows >= 2
    cols2, rows2 = t.grid_dims(BBOX, 5.0)
    # Halving resolution roughly doubles cells along each axis
    assert cols2 >= cols and rows2 >= rows


def test_validate_bbox_rejects_too_large():
    big = {"south": 53.0, "north": 53.1, "west": -113.5, "east": -113.40}
    err = t.validate_bbox(big, 10.0)
    assert err is not None and "too large" in err.lower()


def test_validate_bbox_too_dense_suggests_resolution():
    # 1 km × 0.6 km at 5 m → 200 × 120 = 24 k cells, well over 5 k cap.
    big = {"south": 53.45, "north": 53.4555, "west": -113.55, "east": -113.535}
    err = t.validate_bbox(big, 5.0)
    assert err is not None
    assert "Slope grid" in err   # validation should suggest a coarser grid


def test_validate_bbox_rejects_too_dense():
    err = t.validate_bbox(BBOX, 1.0)   # < MIN_RESOLUTION_M
    assert err is not None


def test_validate_bbox_accepts_residential():
    # ~110×65 m at 10 m grid = ~12×7 cells — comfortable.
    assert t.validate_bbox(BBOX, 10.0) is None


# ── grid sampling ───────────────────────────────────────────────────────────

def test_grid_points_corner_alignment():
    pts = t._grid_points(BBOX, cols=3, rows=3)
    assert len(pts) == 9
    # Top-left = (north, west)
    assert math.isclose(pts[0][0], BBOX["north"], abs_tol=1e-9)
    assert math.isclose(pts[0][1], BBOX["west"],  abs_tol=1e-9)
    # Bottom-right = (south, east)
    assert math.isclose(pts[-1][0], BBOX["south"], abs_tol=1e-9)
    assert math.isclose(pts[-1][1], BBOX["east"],  abs_tol=1e-9)


# ── marching squares ────────────────────────────────────────────────────────

def _ramp_grid(rows: int, cols: int) -> list[list[float]]:
    """Elevation = row + col → diagonal ramp."""
    return [[float(r + c) for c in range(cols)] for r in range(rows)]


def test_marching_squares_diagonal_ramp_segment_count():
    grid = _ramp_grid(5, 5)
    out = t.marching_squares(grid, [3.0, 5.0], BBOX)
    assert len(out) == 2
    # Level 3 crosses the band r+c ∈ {1, 2}; level 5 crosses r+c ∈ {3, 4}.
    by_level = {r["elevation_m"]: r["segments"] for r in out}
    assert len(by_level[3.0]) == 5
    assert len(by_level[5.0]) == 7


def test_marching_squares_skips_uniform_grid():
    grid = [[5.0] * 4 for _ in range(4)]
    out = t.marching_squares(grid, [3.0, 5.0], BBOX)
    # Level 3.0 lies entirely below; level 5.0 sits exactly at corners
    # (≥ test → idx=15 → no segment). Both levels emit nothing.
    for level_result in out:
        assert level_result["segments"] == []


def test_marching_squares_segments_inside_bbox():
    grid = _ramp_grid(5, 5)
    out = t.marching_squares(grid, [3.0], BBOX)
    for seg in out[0]["segments"]:
        for lat, lng in seg:
            assert BBOX["south"] - 1e-9 <= lat <= BBOX["north"] + 1e-9
            assert BBOX["west"]  - 1e-9 <= lng <= BBOX["east"]  + 1e-9


def test_marching_squares_handles_empty_input():
    assert t.marching_squares([], [1.0], BBOX) == []
    assert t.marching_squares([[1.0]], [], BBOX) == []


# ── slope grid ──────────────────────────────────────────────────────────────

def test_slope_grid_flat_is_zero():
    elev = {
        "grid": [[100.0] * 4 for _ in range(4)],
        "cols": 4, "rows": 4, "bbox": BBOX, "resolution_m": 25,
    }
    s = t.compute_slope_grid(elev)
    for row in s:
        for v in row:
            assert v < 1e-6


def test_slope_grid_pure_ns_drop():
    # 1 m drop per row → slope = 1m / dy, where dy = height_m / (rows-1)
    rows, cols = 5, 5
    grid = [[float(r) for _ in range(cols)] for r in range(rows)]
    elev = {"grid": grid, "cols": cols, "rows": rows,
            "bbox": BBOX, "resolution_m": 25}
    s = t.compute_slope_grid(elev)
    width_m, height_m = t.bbox_size_m(BBOX)
    expected = (1.0 / (height_m / (rows - 1))) * 100.0
    # Centre of grid: central differences over 2 rows = exact gradient.
    assert math.isclose(s[2][2], expected, rel_tol=0.02)


# ── slope ramp / PNG ────────────────────────────────────────────────────────

def test_slope_to_rgba_bin_boundaries():
    flat   = t._slope_to_rgba(0.5)
    gentle = t._slope_to_rgba(3.0)
    steep  = t._slope_to_rgba(50.0)
    assert flat   != gentle
    assert gentle != steep
    # Flat = the first ramp entry's RGBA
    assert flat == t._SLOPE_RAMP[0][1]
    # >33% picks the last (hazardous) bin
    assert steep == t._SLOPE_RAMP[-1][1]


def test_slope_ramp_rgba_dimensions():
    grid = [[0.0, 5.0, 50.0], [1.0, 12.0, 25.0]]
    rgba, w, h = t.slope_ramp_rgba(grid)
    assert (w, h) == (3, 2)
    assert len(rgba) == 3 * 2 * 4
    # Top-left pixel = flat colour
    assert tuple(rgba[0:4]) == t._SLOPE_RAMP[0][1]


def test_encode_png_rgba_round_trip_with_zlib():
    # 2×2 RGBA: (R, G, B, A)
    rgba = bytes([
        255, 0,   0,   255,
        0,   255, 0,   255,
        0,   0,   255, 255,
        255, 255, 0,   128,
    ])
    png = t.encode_png_rgba(rgba, 2, 2)
    # PNG signature
    assert png[:8] == b"\x89PNG\r\n\x1a\n"
    # IHDR chunk follows the signature: length(4) + "IHDR" + data(13) + crc(4)
    assert png[12:16] == b"IHDR"
    width  = struct.unpack(">I", png[16:20])[0]
    height = struct.unpack(">I", png[20:24])[0]
    assert (width, height) == (2, 2)
    # IDAT decompresses back to the filtered scanlines (filter=0 + raw row).
    idat_start = png.find(b"IDAT")
    assert idat_start > 0
    length = struct.unpack(">I", png[idat_start - 4:idat_start])[0]
    compressed = png[idat_start + 4:idat_start + 4 + length]
    decompressed = zlib.decompress(compressed)
    # Each scanline = filter byte (0) + 4 bytes/pixel × 2 pixels
    assert decompressed[0]  == 0
    assert decompressed[9]  == 0
    assert decompressed[1:5]   == bytes([255, 0, 0, 255])
    assert decompressed[10:14] == bytes([0, 0, 255, 255])


# ── _coerce_float / _flatten_geojson_lines ──────────────────────────────────

def test_coerce_float():
    assert t._coerce_float("3.5") == 3.5
    assert t._coerce_float(7) == 7.0
    assert t._coerce_float(None) is None
    assert t._coerce_float("abc") is None


def test_flatten_geojson_lines_linestring():
    geom = {"type": "LineString", "coordinates": [[1, 2], [3, 4]]}
    assert list(t._flatten_geojson_lines(geom)) == [[[1, 2], [3, 4]]]


def test_flatten_geojson_lines_multi():
    geom = {"type": "MultiLineString",
            "coordinates": [[[1, 2], [3, 4]], [[5, 6], [7, 8]]]}
    out = list(t._flatten_geojson_lines(geom))
    assert len(out) == 2 and out[0] == [[1, 2], [3, 4]]


def test_flatten_geojson_lines_other_types_yield_nothing():
    assert list(t._flatten_geojson_lines({"type": "Point", "coordinates": [1, 2]})) == []


# ── orchestration with mocked I/O ───────────────────────────────────────────

def test_generate_terrain_uses_edmonton_when_available(monkeypatch=None):
    """Edmonton bbox should pull the vector contour dataset."""
    real_edm  = t.fetch_edmonton_contours
    real_om   = t.fetch_openmeteo_grid
    fake_grid = {
        "grid": _ramp_grid(5, 5), "cols": 5, "rows": 5,
        "bbox": BBOX, "resolution_m": 25,
        "source": "Open-Meteo / Copernicus DEM 30m",
    }

    def fake_edm(bbox, interval_m=0.5):
        return [
            {"coords": [[BBOX["south"], BBOX["west"]],
                        [BBOX["north"], BBOX["east"]]],
             "elevation_m": 100.0},
            {"coords": [[BBOX["south"], BBOX["east"]],
                        [BBOX["north"], BBOX["west"]]],
             "elevation_m": 100.5},
        ]

    t.fetch_edmonton_contours = fake_edm
    t.fetch_openmeteo_grid    = lambda *a, **kw: fake_grid
    try:
        result = t.generate_terrain(BBOX, {
            "interval_m": 0.5, "resolution_m": 10.0,
            "want_contours": True, "want_slope_overlay": True,
        })
    finally:
        t.fetch_edmonton_contours = real_edm
        t.fetch_openmeteo_grid    = real_om

    assert result["ok"]
    assert "Edmonton" in result["source"]
    assert len(result["contours"]) == 2
    assert result["slope_png_bytes"][:8] == b"\x89PNG\r\n\x1a\n"
    assert result["slope_bbox"] == BBOX
    assert "max_slope_pct" in result["stats"]


def test_generate_terrain_falls_back_to_openmeteo_outside_edmonton():
    far = {"south": 49.0, "north": 49.0009, "west": -123.0, "east": -122.9994}
    fake_grid = {
        "grid": _ramp_grid(5, 5), "cols": 5, "rows": 5,
        "bbox": far, "resolution_m": 25,
        "source": "Open-Meteo / Copernicus DEM 30m",
    }
    real_edm = t.fetch_edmonton_contours
    real_om  = t.fetch_openmeteo_grid

    edm_called = {"n": 0}
    def fake_edm(*a, **kw):
        edm_called["n"] += 1
        return None

    t.fetch_edmonton_contours = fake_edm
    t.fetch_openmeteo_grid    = lambda *a, **kw: fake_grid
    try:
        result = t.generate_terrain(far, {
            "interval_m": 1.0, "resolution_m": 15.0,
            "want_contours": True, "want_slope_overlay": True,
        })
    finally:
        t.fetch_edmonton_contours = real_edm
        t.fetch_openmeteo_grid    = real_om

    assert result["ok"]
    # Edmonton fetch shouldn't be tried for a Vancouver bbox
    assert edm_called["n"] == 0
    assert "Open-Meteo" in result["source"]
    # Generated contours via marching squares
    assert len(result["contours"]) > 0


def test_generate_terrain_reports_validation_error():
    big = {"south": 53.0, "north": 53.05, "west": -113.5, "east": -113.45}
    out = t.generate_terrain(big, {"interval_m": 0.5, "resolution_m": 10.0})
    assert out["ok"] is False
    assert out["error"] is not None


def test_generate_terrain_handles_no_network():
    real_edm = t.fetch_edmonton_contours
    real_om  = t.fetch_openmeteo_grid
    t.fetch_edmonton_contours = lambda *a, **kw: None
    t.fetch_openmeteo_grid    = lambda *a, **kw: None
    try:
        out = t.generate_terrain(BBOX, {
            "interval_m": 0.5, "resolution_m": 10.0,
            "want_contours": True, "want_slope_overlay": True,
        })
    finally:
        t.fetch_edmonton_contours = real_edm
        t.fetch_openmeteo_grid    = real_om
    assert out["ok"] is False
    # Warnings list should be populated so the UI can explain what failed.
    assert any("unreachable" in w.lower() for w in (out.get("warnings") or []))


def test_generate_terrain_partial_success_keeps_edmonton_contours():
    """Edmonton contours succeeded but Open-Meteo grid failed → still ok."""
    real_edm = t.fetch_edmonton_contours
    real_om  = t.fetch_openmeteo_grid
    t.fetch_edmonton_contours = lambda *a, **kw: [
        {"coords": [[BBOX["south"], BBOX["west"]],
                    [BBOX["north"], BBOX["east"]]],
         "elevation_m": 670.0},
    ]
    t.fetch_openmeteo_grid = lambda *a, **kw: None
    try:
        out = t.generate_terrain(BBOX, {
            "interval_m": 0.5, "resolution_m": 10.0,
            "want_contours": True, "want_slope_overlay": True,
        })
    finally:
        t.fetch_edmonton_contours = real_edm
        t.fetch_openmeteo_grid    = real_om
    assert out["ok"] is True
    assert len(out["contours"]) == 1
    assert out["slope_png_bytes"] is None
    assert any("unreachable" in w.lower() for w in (out.get("warnings") or []))


def test_generate_terrain_empty_edmonton_falls_back_to_openmeteo_contours():
    """Edmonton dataset reachable but no features in bbox → fallback marches."""
    real_edm = t.fetch_edmonton_contours
    real_om  = t.fetch_openmeteo_grid
    fake_grid = {
        "grid": _ramp_grid(5, 5), "cols": 5, "rows": 5,
        "bbox": BBOX, "resolution_m": 25,
        "source": "Open-Meteo / Copernicus DEM 30m",
    }
    t.fetch_edmonton_contours = lambda *a, **kw: []      # reachable, empty
    t.fetch_openmeteo_grid    = lambda *a, **kw: fake_grid
    try:
        out = t.generate_terrain(BBOX, {
            "interval_m": 1.0, "resolution_m": 25.0,
            "want_contours": True, "want_slope_overlay": False,
        })
    finally:
        t.fetch_edmonton_contours = real_edm
        t.fetch_openmeteo_grid    = real_om
    assert out["ok"] is True
    assert len(out["contours"]) > 0
    assert "Open-Meteo" in out["source"]


# ── Despike filter ──────────────────────────────────────────────────────────

def test_despike_replaces_single_cell_spike():
    """A 100 m sentinel jutting out of a flat plateau should get clipped."""
    grid = [
        [100.0, 100.0, 100.0, 100.0, 100.0],
        [100.0, 100.0, 100.0, 100.0, 100.0],
        [100.0, 100.0, 9999.0, 100.0, 100.0],   # the spike
        [100.0, 100.0, 100.0, 100.0, 100.0],
        [100.0, 100.0, 100.0, 100.0, 100.0],
    ]
    out = t._despike(grid, threshold_m=10.0)
    assert out[2][2] == 100.0
    # Untouched cells stay untouched
    assert out[0][0] == 100.0


def test_despike_preserves_real_terrain():
    """A gradual ramp must pass through unchanged."""
    grid = [[float(r + c) for c in range(5)] for r in range(5)]
    out = t._despike(grid, threshold_m=10.0)
    for r in range(5):
        for c in range(5):
            assert out[r][c] == grid[r][c]


def test_despike_keeps_real_cliff():
    """A genuine cliff (5 m drop, below threshold) is kept, not smoothed."""
    grid = [
        [100.0, 100.0, 100.0, 100.0, 100.0],
        [100.0, 100.0, 100.0, 100.0, 100.0],
        [100.0, 100.0,  95.0,  95.0,  95.0],
        [100.0, 100.0,  95.0,  95.0,  95.0],
        [100.0, 100.0,  95.0,  95.0,  95.0],
    ]
    out = t._despike(grid, threshold_m=10.0)
    # The cliff cells should stay close to 95 (could be 95 or 100 since
    # interior cliff cells have 5 neighbours at 95 and 3 at 100, median = 95).
    assert abs(out[3][2] - 95.0) < 1e-6


# ── HTTP retry helper ───────────────────────────────────────────────────────

def test_http_get_json_retry_succeeds_on_third_try():
    real = t._http_get_json
    calls = {"n": 0}

    def flaky(url, timeout=10.0):
        calls["n"] += 1
        return {"ok": 1} if calls["n"] >= 3 else None

    t._http_get_json = flaky
    real_sleep = t.time.sleep
    t.time.sleep = lambda _s: None      # don't actually sleep in tests
    try:
        out = t._http_get_json_retry("https://example.invalid/x", attempts=3)
    finally:
        t._http_get_json = real
        t.time.sleep = real_sleep
    assert out == {"ok": 1}
    assert calls["n"] == 3


def test_http_get_json_retry_gives_up_after_attempts():
    real = t._http_get_json
    t._http_get_json = lambda *a, **kw: None
    real_sleep = t.time.sleep
    t.time.sleep = lambda _s: None
    try:
        out = t._http_get_json_retry("https://example.invalid/y", attempts=2)
    finally:
        t._http_get_json = real
        t.time.sleep = real_sleep
    assert out is None


# ── _http_get_json error path ───────────────────────────────────────────────

def test_http_get_json_returns_none_on_error():
    import urllib.request as ur
    real = ur.urlopen
    ur.urlopen = lambda *a, **kw: (_ for _ in ()).throw(OSError("offline"))
    try:
        assert t._http_get_json("https://example.invalid/missing") is None
    finally:
        ur.urlopen = real


# ── Entry point ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    passed = failed = 0
    for fn in tests:
        try:
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

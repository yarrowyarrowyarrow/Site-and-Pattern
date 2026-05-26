"""
tests/test_property_data.py — Unit tests for the auto-fill property data
helpers. All network entry points are monkeypatched so these tests run
fully offline.
"""

import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import src.property_data as pd


# ── usda_zone_from_min_c ────────────────────────────────────────────────────

def test_usda_zone_breakpoints():
    # zone 3 starts at -40 °F → -40 °C is exactly that boundary
    assert pd.usda_zone_from_min_c(-40.0) == 3
    # -23 °C ≈ -9.4 °F → zone 6 ([-10, 0) °F)
    assert pd.usda_zone_from_min_c(-23.0) == 6
    # 5 °C = 41 °F → zone 11 ([40, 50) °F)
    assert pd.usda_zone_from_min_c(5.0) == 11


def test_usda_zone_clamped():
    assert pd.usda_zone_from_min_c(-100.0) == 1
    assert pd.usda_zone_from_min_c(50.0) == 13


# ── _texture_class ──────────────────────────────────────────────────────────

def test_texture_class_clay():
    assert pd._texture_class(20, 30, 50) == "Clay"


def test_texture_class_sandy_loam():
    assert pd._texture_class(70, 20, 10) == "Sandy loam"


def test_texture_class_silt_loam():
    assert pd._texture_class(20, 60, 20) == "Silt loam"


def test_texture_class_loam():
    # ~40 / 40 / 20 falls in the loam region
    assert pd._texture_class(40, 40, 20) == "Loam"


def test_texture_class_handles_none():
    assert pd._texture_class(None, 50, 20) is None


# ── _compass_label ──────────────────────────────────────────────────────────

def test_compass_label_cardinal():
    assert pd._compass_label(0)   == "N"
    assert pd._compass_label(90)  == "E"
    assert pd._compass_label(180) == "S"
    assert pd._compass_label(270) == "W"


def test_compass_label_intercardinal():
    assert pd._compass_label(45)  == "NE"
    assert pd._compass_label(135) == "SE"


# ── _slope_sample_points ────────────────────────────────────────────────────

def test_sample_points_centred():
    pts = pd._slope_sample_points(53.5, -113.5, 60.0)
    assert len(pts) == 5
    assert pts[0] == (53.5, -113.5)
    # N is north of centre, S south
    assert pts[1][0] > pts[0][0]
    assert pts[3][0] < pts[0][0]
    # E is east of centre, W west
    assert pts[2][1] > pts[0][1]
    assert pts[4][1] < pts[0][1]


# ── _parse_elevation ────────────────────────────────────────────────────────

def test_parse_elevation_flat():
    out = pd._parse_elevation([100.0, 100.0, 100.0, 100.0, 100.0], sample_m=60.0)
    assert out["elevation_m"] == 100.0
    assert out["slope_pct"] < 0.05
    assert out["aspect"] == "Flat"
    assert out["aspect_deg"] is None


def test_parse_elevation_south_facing():
    # North=110, South=100 → slope drops to the south (aspect ≈ 180°)
    out = pd._parse_elevation([105.0, 110.0, 105.0, 100.0, 105.0], sample_m=60.0)
    assert out["slope_pct"] > 0
    assert out["aspect"] == "S"


def test_parse_elevation_west_facing():
    # East higher than west → slope drops to the west (aspect ≈ 270°)
    out = pd._parse_elevation([105.0, 105.0, 110.0, 105.0, 100.0], sample_m=60.0)
    assert out["slope_pct"] > 0
    assert out["aspect"] == "W"


def test_parse_elevation_handles_missing():
    assert pd._parse_elevation([None, 1, 2, 3, 4], sample_m=60.0) is None
    assert pd._parse_elevation([], sample_m=60.0) is None


def test_parse_elevation_slope_magnitude():
    # 10 m drop over 120 m baseline → 10/120 ≈ 8.33 %
    out = pd._parse_elevation([100, 105, 100, 95, 100], sample_m=60.0)
    expected_pct = (10.0 / 120.0) * 100.0
    assert math.isclose(out["slope_pct"], expected_pct, rel_tol=0.01)


# ── _parse_rainfall ─────────────────────────────────────────────────────────

def test_parse_rainfall_two_years():
    data = {
        "daily": {
            "time":              ["2020-01-15", "2020-07-15", "2021-07-15"],
            "precipitation_sum": [10.0,         50.0,         60.0],
        }
    }
    out = pd._parse_rainfall(data)
    assert out is not None
    # Two distinct years observed → divide totals by 2.
    assert out["years_used"] == 2
    assert out["annual_mm"] == 60.0           # (10 + 50 + 60) / 2
    # July monthly mean = (50 + 60) / 2 = 55
    assert out["monthly_mm"][6] == 55.0
    # January monthly mean = 10 / 2 = 5
    assert out["monthly_mm"][0] == 5.0
    assert out["source"].startswith("Open-Meteo")


def test_parse_rainfall_skips_nones():
    data = {
        "daily": {
            "time":              ["2020-01-01", "2020-02-01"],
            "precipitation_sum": [None,         12.0],
        }
    }
    out = pd._parse_rainfall(data)
    assert out["annual_mm"] == 12.0


def test_parse_rainfall_empty():
    assert pd._parse_rainfall({"daily": {"time": [], "precipitation_sum": []}}) is None


# ── _parse_soilgrids ────────────────────────────────────────────────────────

def _sg_layer(name, values_per_depth):
    return {
        "name": name,
        "depths": [
            {"label": label, "values": {"mean": v}}
            for label, v in values_per_depth
        ],
    }


def test_parse_soilgrids_minimal():
    data = {"properties": {"layers": [
        _sg_layer("phh2o", [("0-5cm", 65), ("5-15cm", 68)]),
        _sg_layer("sand",  [("0-5cm", 400)]),
        _sg_layer("silt",  [("0-5cm", 350)]),
        _sg_layer("clay",  [("0-5cm", 250)]),
    ]}}
    out = pd._parse_soilgrids(data)
    assert out is not None
    summary = out["summary"]
    # phh2o is stored ×10 → 65/10 = 6.5
    assert summary["ph_top"] == 6.5
    # sand/silt/clay g/kg with d_factor 10 → percentages
    assert summary["sand_pct_top"] == 40.0
    assert summary["silt_pct_top"] == 35.0
    assert summary["clay_pct_top"] == 25.0
    assert summary["texture_class"] == "Loam"
    # Deepest reported = 15 cm because phh2o has both depths
    assert summary["max_reported_depth_cm"] == 15
    assert out["source"].startswith("SoilGrids")


def test_parse_soilgrids_handles_missing_means():
    data = {"properties": {"layers": [
        {"name": "phh2o", "depths": [{"label": "0-5cm", "values": {}}]}
    ]}}
    assert pd._parse_soilgrids(data) is None


def test_parse_soilgrids_empty():
    assert pd._parse_soilgrids({"properties": {"layers": []}}) is None


# ── _parse_hardiness_fallback ───────────────────────────────────────────────

def test_parse_hardiness_fallback_min_per_year():
    data = {"daily": {
        "time":              ["2020-01-15", "2020-07-15", "2021-01-10"],
        "temperature_2m_min": [-30.0,        10.0,         -25.0],
    }}
    out = pd._parse_hardiness_fallback(data)
    assert out is not None
    # Annual minima: 2020=-30, 2021=-25 → average = -27.5
    assert math.isclose(out["avg_extreme_min_c"], -27.5, rel_tol=1e-3)
    # USDA zone for -27.5 °C ≈ -17.5 °F → zone 5 ([-20, -10) °F)
    assert out["zone"] == 5


def test_parse_hardiness_fallback_empty():
    assert pd._parse_hardiness_fallback({"daily": {"time": [], "temperature_2m_min": []}}) is None


# ── HTTP layer (monkeypatched) ──────────────────────────────────────────────

def test_http_get_json_handles_error(monkeypatch=None):
    """No-network: simulate failure and assert None is returned."""
    def boom(url, headers=None, timeout=None):
        raise OSError("offline")
    # Patch urlopen to raise.
    import urllib.request as ur
    real = ur.urlopen
    ur.urlopen = boom
    try:
        assert pd._http_get_json("https://example.invalid/none") is None
    finally:
        ur.urlopen = real


def test_fetch_hardiness_uses_local_zone(monkeypatch=None):
    """Edmonton lookup should hit the bundled NRCan dataset, no network."""
    # Force the network fallback to fail so we know the local path returned.
    real = pd._http_get_json
    pd._http_get_json = lambda url, timeout=8.0: None
    try:
        out = pd.fetch_hardiness(53.5461, -113.4938)
    finally:
        pd._http_get_json = real
    assert out is not None
    assert out["zone"] == 3
    assert "NRCan" in out["source"]


# ── _parse_elevation: water-adjacent degradation (V1.37) ────────────────────
#
# Pins on the North Saskatchewan River used to break the at-pin
# elevation/slope/aspect row because the Copernicus DEM returns null
# over water and the original code required all 5 samples to be
# non-null. V1.37 changes the contract: as long as the centre sample
# is present, return what we can.

import src.property_data as pd


def test_parse_elevation_all_samples_present():
    """Original happy path — flat ground, no slope."""
    out = pd._parse_elevation([100.0, 100.0, 100.0, 100.0, 100.0], sample_m=30.0)
    assert out is not None
    assert out["elevation_m"] == 100.0
    assert out["slope_pct"] == 0.0


def test_parse_elevation_north_facing_slope():
    # Higher in the south, lower in the north → downhill faces N.
    out = pd._parse_elevation([100.0, 99.0, 100.0, 101.0, 100.0], sample_m=30.0)
    assert out is not None
    assert out["aspect"] == "N"


def test_parse_elevation_centre_only():
    """Pin on a river — only the centre cell has a value, the four
    cardinal neighbours are over water and come back null. We should
    return elevation but no slope/aspect, with a source note."""
    out = pd._parse_elevation([663.5, None, None, None, None], sample_m=30.0)
    assert out is not None
    assert out["elevation_m"] == 663.5
    assert out["slope_pct"] is None
    assert out["aspect"] == "—"
    assert "over water" in out["source"]


def test_parse_elevation_one_axis_available():
    """N+S present, E+W null — we use the N+S gradient only."""
    out = pd._parse_elevation([100.0, 99.0, None, 101.0, None], sample_m=30.0)
    assert out is not None
    assert out["slope_pct"] is not None
    assert out["aspect"] == "N"
    assert "partial" in out["source"]


def test_parse_elevation_centre_null_returns_none():
    """No useful info → None, as before."""
    out = pd._parse_elevation([None, 100.0, 100.0, 100.0, 100.0], sample_m=30.0)
    assert out is None


def test_parse_elevation_empty_returns_none():
    assert pd._parse_elevation([], sample_m=30.0) is None


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

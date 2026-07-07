"""
tests/test_climate.py — Basic tests for the climate/hardiness zone lookup.

Run with:
    python -m pytest tests/
    -- or --
    python tests/test_climate.py
"""

import sys
import os

# Add project root to path so imports work without install
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.climate import get_zone, zone_label, zone_description


# ── Helpers ───────────────────────────────────────────────────────────────────

def _check(lat, lng, expected_zone, label=""):
    result = get_zone(lat, lng)
    assert result == expected_zone, (
        f"{label or f'({lat}, {lng})'}: expected Zone {expected_zone}, got Zone {result}"
    )


# ── Zone lookup tests ─────────────────────────────────────────────────────────

def test_edmonton():
    """Edmonton, AB should be Zone 3."""
    _check(53.5461, -113.4938, 3, "Edmonton")


def test_calgary():
    """Calgary, AB should be Zone 4."""
    _check(51.0447, -114.0719, 4, "Calgary")


def test_lethbridge():
    """Lethbridge, AB should be Zone 5."""
    _check(49.6956, -112.8451, 5, "Lethbridge")


def test_medicine_hat():
    """Medicine Hat, AB should be Zone 5."""
    _check(50.0417, -110.6770, 5, "Medicine Hat")


def test_red_deer():
    """Red Deer, AB should be Zone 3."""
    _check(52.2681, -113.8112, 3, "Red Deer")


def test_grande_prairie():
    """Grande Prairie, AB should be Zone 3."""
    _check(55.1707, -118.7884, 3, "Grande Prairie")


def test_fort_mcmurray():
    """Fort McMurray, AB should be Zone 2."""
    _check(56.7265, -111.3803, 2, "Fort McMurray")


def test_vancouver():
    """Vancouver, BC should be Zone 8."""
    _check(49.2827, -123.1207, 8, "Vancouver")


def test_victoria():
    """Victoria, BC should be Zone 9."""
    _check(48.4284, -123.3656, 9, "Victoria")


def test_kelowna():
    """Kelowna, BC (Okanagan) should be Zone 6."""
    _check(49.8880, -119.4960, 6, "Kelowna")


def test_regina():
    """Regina, SK should be Zone 3."""
    _check(50.4452, -104.6189, 3, "Regina")


def test_saskatoon():
    """Saskatoon, SK should be Zone 3."""
    _check(52.1332, -106.6700, 3, "Saskatoon")


def test_north_battleford():
    """North Battleford, SK should be Zone 3 (dedicated box added V2.14;
    without it the broad 'Northern Saskatchewan' box would report Zone 2)."""
    _check(52.7575, -108.2861, 3, "North Battleford")


def test_lumsden():
    """Lumsden, SK (Qu'Appelle valley near Regina) should be Zone 3."""
    _check(50.6500, -104.8700, 3, "Lumsden")


def test_winnipeg():
    """Winnipeg, MB should be Zone 4."""
    _check(49.8951, -97.1384, 4, "Winnipeg")


def test_outside_coverage_returns_none_or_int():
    """Points outside Western Canada return None or a fallback int, never crash."""
    result = get_zone(0.0, 0.0)           # middle of Atlantic Ocean
    assert result is None or isinstance(result, int)


def test_none_inputs():
    """None lat/lng should return None."""
    assert get_zone(None, None) is None


# ── zone_label tests ──────────────────────────────────────────────────────────

def test_zone_label_known():
    assert zone_label(3) == "Zone 3"
    assert zone_label(5) == "Zone 5"


def test_zone_label_none():
    assert "unknown" in zone_label(None).lower()


# ── zone_description tests ────────────────────────────────────────────────────

def test_zone_description_contains_zone():
    desc = zone_description(3)
    assert "3" in desc
    assert "Edmonton" in desc   # our description mentions Edmonton for Zone 3


def test_zone_description_none():
    desc = zone_description(None)
    assert desc  # should not be empty


# ── GDD + frost window (V1.35) ────────────────────────────────────────────────

from src.climate import (
    compute_gdd,
    frost_window,
    get_climate_summary,
    get_winter_summary,
    doy_to_date_label,
)


def _synth_year(year: int, day_mean_c: float, day_amplitude_c: float = 5.0,
                start: int = 1, end: int = 365) -> list[dict]:
    """Build a year of synthetic daily temperature rows with a constant
    mean and a fixed min/max amplitude."""
    from datetime import date, timedelta
    rows = []
    d0 = date(year, 1, 1)
    for doy in range(start, end + 1):
        d = d0 + timedelta(days=doy - 1)
        rows.append({
            "date": d.isoformat(),
            "tmin": day_mean_c - day_amplitude_c,
            "tmax": day_mean_c + day_amplitude_c,
        })
    return rows


def test_compute_gdd_zero_below_base():
    """All days at -10 °C → no growing-degree days."""
    rows = _synth_year(2024, day_mean_c=-10.0)
    assert compute_gdd(rows, base=5.0) == 0.0


def test_compute_gdd_simple_warm_year():
    """365 days at mean 20 °C, base 5 → 365 * 15 = 5475."""
    rows = _synth_year(2024, day_mean_c=20.0)
    gdd = compute_gdd(rows, base=5.0)
    assert abs(gdd - 5475.0) < 0.5


def test_compute_gdd_averages_across_years():
    """5 identical years → mean GDD = one-year GDD."""
    rows = []
    for y in range(2019, 2024):
        rows.extend(_synth_year(y, day_mean_c=15.0))
    gdd = compute_gdd(rows, base=5.0)
    # 365 days * 10 (15-5) = 3650, averaged across 5 years = 3650
    assert abs(gdd - 3650.0) < 0.5


def test_compute_gdd_empty_returns_zero():
    assert compute_gdd([], base=5.0) == 0.0


def test_compute_gdd_handles_none_temps():
    """A row with tmin/tmax=None should be skipped, not crash."""
    rows = [
        {"date": "2024-06-01", "tmin": 10.0, "tmax": 20.0},
        {"date": "2024-06-02", "tmin": None, "tmax": None},
        {"date": "2024-06-03", "tmin": 10.0, "tmax": 20.0},
    ]
    # Mean = 15 each valid day. Base 5. (15-5)*2 = 20. One year → 20.
    assert abs(compute_gdd(rows, base=5.0) - 20.0) < 0.5


def test_frost_window_finds_correct_dates():
    """Synthetic year with explicit frost events on known DOYs."""
    rows = [
        {"date": "2024-04-15", "tmin": -3.0, "tmax": 5.0},   # spring frost
        {"date": "2024-05-10", "tmin": -1.0, "tmax": 8.0},   # later spring frost
        {"date": "2024-07-15", "tmin": 8.0,  "tmax": 22.0},  # warm middle
        {"date": "2024-09-25", "tmin": -2.0, "tmax": 6.0},   # first fall frost
        {"date": "2024-10-20", "tmin": -5.0, "tmax": 2.0},   # later fall frost
    ]
    fw = frost_window(rows)
    from datetime import date
    expected_last_spring = date(2024, 5, 10).timetuple().tm_yday
    expected_first_fall = date(2024, 9, 25).timetuple().tm_yday
    assert fw["last_spring_frost_doy"] == expected_last_spring
    assert fw["first_fall_frost_doy"] == expected_first_fall
    assert fw["frost_free_days"] == expected_first_fall - expected_last_spring
    assert fw["years_used"] == 1


def test_frost_window_averages_across_years():
    rows = []
    # Two years with last-spring DOY 100 and 110 → mean 105.
    rows.append({"date": "2022-04-10", "tmin": -1.0, "tmax": 5.0})  # doy 100
    rows.append({"date": "2023-04-20", "tmin": -1.0, "tmax": 5.0})  # doy 110
    # Two years with first-fall DOY 270 and 280 → mean 275.
    rows.append({"date": "2022-09-27", "tmin": -1.0, "tmax": 5.0})  # doy 270
    rows.append({"date": "2023-10-07", "tmin": -1.0, "tmax": 5.0})  # doy 280
    fw = frost_window(rows)
    assert fw["last_spring_frost_doy"] == 105
    assert fw["first_fall_frost_doy"] == 275
    assert fw["frost_free_days"] == 170
    assert fw["years_used"] == 2


def test_frost_window_no_frost_returns_nones():
    """Subtropical / coastal location — never freezes."""
    rows = _synth_year(2024, day_mean_c=18.0)
    fw = frost_window(rows)
    assert fw["last_spring_frost_doy"] is None
    assert fw["first_fall_frost_doy"] is None
    assert fw["frost_free_days"] is None


def test_get_climate_summary_with_mock_fetcher():
    """End-to-end: a mock fetcher returns synthetic rows, summary
    computes GDD/frost from them and returns the expected shape."""
    rows = _synth_year(2024, day_mean_c=15.0)
    summary = get_climate_summary(
        53.5, -113.5, use_cache=False, _fetcher=lambda lat, lng: rows
    )
    assert summary is not None
    assert "gdd5_mean" in summary
    assert summary["gdd5_mean"] > 0
    assert "last_spring_frost_doy" in summary
    assert summary["source"] == "Open-Meteo / ERA5-Land"
    assert summary["cached"] is False


def test_get_climate_summary_handles_fetch_failure():
    """If the fetcher returns None, summary returns None."""
    summary = get_climate_summary(
        53.5, -113.5, use_cache=False, _fetcher=lambda lat, lng: None
    )
    assert summary is None


def _synth_winter_rows():
    """A cold, snowy Nov–Mar plus a warm summer (so the snow model builds a
    real pack only in winter)."""
    from datetime import date, timedelta
    rows = []
    d, end = date(2021, 11, 1), date(2022, 3, 31)
    while d <= end:
        rows.append({"date": d.isoformat(), "tmin": -18.0, "tmax": -8.0,
                     "precip": 3.0})
        d += timedelta(days=1)
    return rows


def test_get_winter_summary_with_mock_fetcher():
    summary = get_winter_summary(
        53.5, -113.5, _fetcher=lambda lat, lng: _synth_winter_rows())
    assert summary is not None
    assert summary["snow_cover_days"] > 100
    assert summary["reliability"] == "reliable"
    assert "modelled" in summary["source"]


def test_get_winter_summary_handles_fetch_failure():
    assert get_winter_summary(53.5, -113.5, _fetcher=lambda lat, lng: None) is None


def test_doy_to_date_label():
    """DOY 1 = Jan 1, DOY 60 = Feb 29 (leap)/Mar 1, etc."""
    assert doy_to_date_label(1) in ("Jan 1", "Jan 01")
    assert "Jul" in doy_to_date_label(196)
    assert doy_to_date_label(None) == "—"


# ── Entry point ───────────────────────────────────────────────────────────────

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

    print(f"\n{passed} passed, {failed} failed out of {passed + failed} tests.")
    sys.exit(0 if failed == 0 else 1)

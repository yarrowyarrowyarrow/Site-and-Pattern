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

"""
tests/test_map3d_js.py

V1.56 — JS builders that drive the embedded map3d 3D view's sun (and the
shadows it casts) from src/solar.py. Pure string/JSON building + the existing
solar math; no Qt, no network.
"""

import os
import sys
import unittest
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import src.map3d_js as m3  # noqa: E402

# Edmonton — the project's reference location (src/solar.py).
_LAT, _LNG = 53.5461, -113.4938


class TestSetSun(unittest.TestCase):
    def test_emits_guarded_hook_call(self):
        js = m3.set_sun(180.0, 45.0)
        self.assertIn("window.permaSetSun && window.permaSetSun(", js)
        self.assertIn("180.0", js)
        self.assertIn("45.0", js)
        self.assertTrue(js.strip().endswith(");"))

    def test_values_are_json_encoded_numbers(self):
        # ints coerce to floats; no raw string interpolation that could inject.
        js = m3.set_sun(90, 30)
        self.assertIn("90.0", js)
        self.assertIn("30.0", js)


class TestSetSunFor(unittest.TestCase):
    def test_daytime_returns_hook_js(self):
        # Summer-solstice noon at Edmonton → sun well above the horizon.
        js = m3.set_sun_for(_LAT, _LNG, datetime(2025, 6, 21, 12, 0))
        self.assertIsNotNone(js)
        self.assertIn("window.permaSetSun", js)

    def test_night_returns_none(self):
        # 1 AM local → sun below the horizon → nothing to draw.
        self.assertIsNone(
            m3.set_sun_for(_LAT, _LNG, datetime(2025, 6, 21, 1, 0)))

    def test_matches_solar_sun_position(self):
        # The emitted azimuth/altitude are exactly solar.sun_position's, so the
        # 3D sun and the 2D shade engine agree by construction.
        from datetime import timedelta
        from src.solar import sun_position
        when = datetime(2025, 6, 21, 15, 0)
        sun = sun_position(_LAT, _LNG, when + timedelta(hours=-_LNG / 15.0))
        js = m3.set_sun_for(_LAT, _LNG, when)
        self.assertIn(str(float(sun.azimuth)), js)
        self.assertIn(str(float(sun.altitude)), js)


if __name__ == "__main__":
    unittest.main()

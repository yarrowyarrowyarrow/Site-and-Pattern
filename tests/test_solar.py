"""
tests/test_solar.py

Numeric-correctness tests for src/solar.py against known astronomy.
Pure maths — no DB, no Qt. These pin the sun-position / sunrise-sunset
/ shadow formulas so a refactor can't silently shift the Analysis tab's
sun-path overlay.

Reference facts used as oracles (all at Edmonton, lat 53.5461):
  • At local solar noon the sun is due south (azimuth ≈ 180°) and its
    altitude ≈ 90 − |lat − declination|.
  • Summer-solstice declination ≈ +23.45°, winter ≈ −23.45°, equinox ≈ 0.
  • At an equinox the day is ~12 h everywhere, so sunrise+sunset ≈ 24
    and they straddle solar noon symmetrically.
  • A 45° sun casts a shadow equal to the object's height (factor 1.0).
"""

import math
import os
import sys
import unittest
from datetime import date, datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.solar import (  # noqa: E402
    SunPosition,
    sun_position,
    sun_path_for_date,
    sunrise_sunset,
    shadow_azimuth,
    shadow_length_factor,
    EDMONTON_LAT,
    EDMONTON_LNG,
    KEY_DATES,
)

_LAT = EDMONTON_LAT
_LNG = EDMONTON_LNG


def _solar_noon_utc(lng: float, d: date) -> datetime:
    """UTC datetime closest to local solar noon for a longitude.

    solar_time = utc + lng/15 + eot/60; solar noon is solar_time == 12,
    so utc ≈ 12 − lng/15 (ignoring the few-minute EoT term, which we
    absorb by searching a small window in the tests that need exactness).
    """
    utc_hour = 12 - lng / 15.0
    utc_hour %= 24
    h = int(utc_hour)
    m = int((utc_hour - h) * 60)
    return datetime(d.year, d.month, d.day, h, m)


class TestSunPositionNoon(unittest.TestCase):
    """At solar noon the sun is near due south with a predictable altitude."""

    def _noon_altitude(self, d: date) -> SunPosition:
        # Scan a ±40 min window around computed solar noon and take the
        # highest sun — that's solar noon regardless of the EoT offset.
        base = _solar_noon_utc(_LNG, d)
        best = None
        for dm in range(-40, 41, 2):
            dt = datetime(base.year, base.month, base.day, base.hour,
                          base.minute) + _timedelta(minutes=dm)
            pos = sun_position(_LAT, _LNG, dt)
            if best is None or pos.altitude > best.altitude:
                best = pos
        return best

    def test_summer_solstice_noon_altitude(self):
        # Max altitude ≈ 90 − (lat − 23.45) = 90 − 30.10 = 59.9°
        pos = self._noon_altitude(KEY_DATES["Summer Solstice"])
        expected = 90 - (_LAT - 23.45)
        self.assertAlmostEqual(pos.altitude, expected, delta=1.0)

    def test_winter_solstice_noon_altitude(self):
        # Max altitude ≈ 90 − (lat + 23.45) = 90 − 76.996 = 13.0°
        pos = self._noon_altitude(KEY_DATES["Winter Solstice"])
        expected = 90 - (_LAT + 23.45)
        self.assertAlmostEqual(pos.altitude, expected, delta=1.0)

    def test_noon_sun_is_due_south(self):
        pos = self._noon_altitude(KEY_DATES["Summer Solstice"])
        # Northern hemisphere: noon sun bears ~180° (due south).
        self.assertAlmostEqual(pos.azimuth, 180.0, delta=3.0)

    def test_summer_higher_than_winter(self):
        summer = self._noon_altitude(KEY_DATES["Summer Solstice"]).altitude
        winter = self._noon_altitude(KEY_DATES["Winter Solstice"]).altitude
        self.assertGreater(summer, winter)


class TestSunriseSunset(unittest.TestCase):

    def test_equinox_is_about_twelve_hours(self):
        sr, ss = sunrise_sunset(_LAT, _LNG, KEY_DATES["Spring Equinox"])
        # Day length ≈ 12 h at an equinox (within ~15 min of geometric).
        self.assertAlmostEqual(ss - sr, 12.0, delta=0.3)

    def test_equinox_symmetric_about_noon(self):
        sr, ss = sunrise_sunset(_LAT, _LNG, KEY_DATES["Fall Equinox"])
        self.assertAlmostEqual((sr + ss) / 2.0, 12.0, delta=0.1)

    def test_summer_longer_than_winter(self):
        sr_s, ss_s = sunrise_sunset(_LAT, _LNG, KEY_DATES["Summer Solstice"])
        sr_w, ss_w = sunrise_sunset(_LAT, _LNG, KEY_DATES["Winter Solstice"])
        self.assertGreater(ss_s - sr_s, ss_w - sr_w)

    def test_summer_day_length_plausible(self):
        # Edmonton gets ~17 h of daylight at the summer solstice.
        sr, ss = sunrise_sunset(_LAT, _LNG, KEY_DATES["Summer Solstice"])
        self.assertGreater(ss - sr, 16.0)
        self.assertLess(ss - sr, 18.0)


class TestSunPathForDate(unittest.TestCase):

    def test_only_above_horizon(self):
        path = sun_path_for_date(_LAT, _LNG, KEY_DATES["Summer Solstice"])
        self.assertTrue(path)
        for pos in path:
            self.assertGreater(pos.altitude, -2)

    def test_summer_has_more_daylight_samples(self):
        n_summer = len(sun_path_for_date(_LAT, _LNG, KEY_DATES["Summer Solstice"]))
        n_winter = len(sun_path_for_date(_LAT, _LNG, KEY_DATES["Winter Solstice"]))
        self.assertGreater(n_summer, n_winter)

    def test_step_count_respected(self):
        # Polar-ish high step count shouldn't error and stays bounded.
        path = sun_path_for_date(_LAT, _LNG, KEY_DATES["Spring Equinox"], steps=24)
        self.assertLessEqual(len(path), 24)


class TestShadowGeometry(unittest.TestCase):

    def test_shadow_azimuth_opposite_sun(self):
        self.assertEqual(shadow_azimuth(180.0), 0.0)
        self.assertEqual(shadow_azimuth(90.0), 270.0)
        self.assertEqual(shadow_azimuth(0.0), 180.0)
        self.assertEqual(shadow_azimuth(350.0), 170.0)

    def test_shadow_length_at_45_deg(self):
        # tan(45°) = 1 → shadow length equals object height.
        self.assertAlmostEqual(shadow_length_factor(45.0), 1.0, places=6)

    def test_shadow_length_low_sun_is_long(self):
        # Low sun → long shadow (factor > 1); high sun → short (< 1).
        self.assertGreater(shadow_length_factor(10.0), 1.0)
        self.assertLess(shadow_length_factor(80.0), 1.0)

    def test_shadow_length_below_horizon_infinite(self):
        self.assertEqual(shadow_length_factor(0.0), float("inf"))
        self.assertEqual(shadow_length_factor(-5.0), float("inf"))


class TestEveningAzimuthDirection(unittest.TestCase):
    """Regression: late-afternoon/evening shadows used to mirror to the morning
    direction. The shade paths convert a local-solar hour to UTC by adding
    -lng/15 (~+7.6 h in Alberta), so an evening time crosses midnight UTC and
    pushed solar_time negative — which dropped the afternoon azimuth correction
    in sun_position. Wrapping solar_time to [0,24) fixes it."""

    def _utc_for_local(self, local_hour: float, d: date) -> datetime:
        # Mirror shade_grid_at / shadow_polygons_payload: utc = local - lng/15.
        from datetime import timedelta
        return (datetime(d.year, d.month, d.day, 0, 0)
                + timedelta(hours=local_hour - _LNG / 15.0))

    def test_late_afternoon_sun_bears_west(self):
        d = KEY_DATES["Summer Solstice"]
        for local_hour in (17, 18, 19):
            pos = sun_position(_LAT, _LNG, self._utc_for_local(local_hour, d))
            self.assertGreater(pos.altitude, 0.0,
                               f"sun should be up at {local_hour}:00")
            self.assertTrue(180.0 < pos.azimuth < 360.0,
                            f"PM sun should bear west at {local_hour}:00 "
                            f"(got azimuth={pos.azimuth:.1f}°)")

    def test_morning_sun_bears_east(self):
        d = KEY_DATES["Summer Solstice"]
        pos = sun_position(_LAT, _LNG, self._utc_for_local(8, d))
        self.assertTrue(0.0 < pos.azimuth < 180.0,
                        f"AM sun should bear east (got azimuth={pos.azimuth:.1f}°)")


# Local import kept out of module top to keep the oracle helper readable.
from datetime import timedelta as _timedelta  # noqa: E402


if __name__ == "__main__":
    unittest.main()

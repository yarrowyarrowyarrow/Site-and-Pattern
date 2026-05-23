"""
solar.py — Solar position calculations for sun path overlay.

Uses simplified astronomical formulas (no external deps) to compute
sun altitude and azimuth for any lat/lng/datetime. Accurate to ~1°
which is sufficient for native habitat design visualization.

Reference: NOAA Solar Calculator methodology (simplified).
"""

from __future__ import annotations

import math
from datetime import datetime, date, timedelta
from typing import NamedTuple


class SunPosition(NamedTuple):
    """Sun position at a given moment."""
    altitude: float   # degrees above horizon (negative = below)
    azimuth: float    # degrees clockwise from north (0=N, 90=E, 180=S, 270=W)
    hour: float       # decimal hour (local solar time)


def sun_position(lat: float, lng: float, dt: datetime) -> SunPosition:
    """
    Compute sun altitude and azimuth for a given location and UTC datetime.

    Parameters
    ----------
    lat, lng : float
        Location in decimal degrees.
    dt : datetime
        UTC datetime.

    Returns
    -------
    SunPosition with altitude (degrees), azimuth (degrees from N), hour.
    """
    # Day of year
    n = dt.timetuple().tm_yday

    # Solar declination (Spencer, 1971)
    B = math.radians((360 / 365) * (n - 81))
    declination = math.radians(
        23.45 * math.sin(B)
    )

    # Equation of time (minutes)
    eot = 9.87 * math.sin(2 * B) - 7.53 * math.cos(B) - 1.5 * math.sin(B)

    # Local solar time
    utc_hours = dt.hour + dt.minute / 60 + dt.second / 3600
    # Time correction for longitude (4 min per degree from standard meridian)
    # Using lng directly as offset from UTC (simplified)
    solar_time = utc_hours + lng / 15 + eot / 60

    # Hour angle (degrees, 15° per hour from solar noon)
    hour_angle = math.radians((solar_time - 12) * 15)

    lat_rad = math.radians(lat)

    # Altitude
    sin_alt = (math.sin(lat_rad) * math.sin(declination) +
               math.cos(lat_rad) * math.cos(declination) * math.cos(hour_angle))
    sin_alt = max(-1.0, min(1.0, sin_alt))
    altitude = math.degrees(math.asin(sin_alt))

    # Azimuth
    cos_az = ((math.sin(declination) - math.sin(lat_rad) * sin_alt) /
              (math.cos(lat_rad) * math.cos(math.radians(altitude)) + 1e-10))
    cos_az = max(-1.0, min(1.0, cos_az))
    azimuth = math.degrees(math.acos(cos_az))

    if hour_angle > 0:
        azimuth = 360 - azimuth

    return SunPosition(altitude=altitude, azimuth=azimuth, hour=solar_time % 24)


def sun_path_for_date(lat: float, lng: float, d: date,
                      steps: int = 48) -> list[SunPosition]:
    """
    Compute sun positions throughout a day at evenly-spaced intervals.
    Returns only positions where sun is above the horizon.
    """
    positions = []
    for i in range(steps):
        frac = i / steps
        utc_hour = frac * 24
        h = int(utc_hour) % 24  # defensive clamp: prevent hour=24 crash
        m = int((utc_hour % 1) * 60)
        dt = datetime(d.year, d.month, d.day, h, m)
        pos = sun_position(lat, lng, dt)
        if pos.altitude > -2:  # include just below horizon for arc drawing
            positions.append(pos)
    return positions


def sunrise_sunset(lat: float, lng: float, d: date) -> tuple[float, float]:
    """
    Approximate sunrise and sunset times as decimal hours (local solar time).
    Returns (sunrise_hour, sunset_hour).
    """
    n = d.timetuple().tm_yday
    B = math.radians((360 / 365) * (n - 81))
    declination = 23.45 * math.sin(B)

    lat_rad = math.radians(lat)
    dec_rad = math.radians(declination)

    cos_ha = -math.tan(lat_rad) * math.tan(dec_rad)
    cos_ha = max(-1.0, min(1.0, cos_ha))
    ha = math.degrees(math.acos(cos_ha))

    sunrise = 12 - ha / 15
    sunset = 12 + ha / 15
    return (sunrise, sunset)


def shadow_azimuth(sun_az: float) -> float:
    """Shadow direction is opposite the sun azimuth."""
    return (sun_az + 180) % 360


def shadow_length_factor(sun_alt: float) -> float:
    """
    Ratio of shadow length to object height.
    shadow_length = object_height * shadow_length_factor
    """
    if sun_alt <= 0:
        return float('inf')
    return 1.0 / math.tan(math.radians(sun_alt))


# ── Edmonton-specific presets ────────────────────────────────────────────────

EDMONTON_LAT = 53.5461
EDMONTON_LNG = -113.4938

# Key dates for native habitat design — solstices, equinoxes, frost-free window
KEY_DATES = {
    "Summer Solstice": date(2025, 6, 21),
    "Winter Solstice": date(2025, 12, 21),
    "Spring Equinox": date(2025, 3, 20),
    "Fall Equinox": date(2025, 9, 22),
    "Last Frost (~May 7)": date(2025, 5, 7),
    "First Frost (~Sep 23)": date(2025, 9, 23),
}

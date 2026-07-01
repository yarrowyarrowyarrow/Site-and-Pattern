"""
climate.py — Hardiness zone lookup + growing-degree-day stats.

Two responsibilities:

  * **Hardiness zone** (legacy): bounding-box lookup against
    ``data/hardiness_zones.json``. Tells the user how cold the winters
    get at the property location.

  * **Growing-degree days + frost window** (V1.35): historical-temperature
    aggregates from the Open-Meteo Historical Weather endpoint. Tells
    the user how much *summer warmth* accumulates — the missing other
    half of the climate picture. Two locations can share a hardiness
    zone but differ in GDD by 30%+, which is the difference between
    "apricots ripen here" and "apricots survive but never fruit".

The GDD/frost code follows the existing rainfall-fetch pattern in
``src/property_data.py`` (same vendor, same archive endpoint, same
graceful-degradation pattern). Results are cached in the
``climate_cache`` table (schema v14) keyed on the lat/lng quantized to
0.01° so repeated pin-set events near the same spot don't re-fetch.
"""

import json
import math
import os
from datetime import date
from functools import lru_cache
from typing import Optional

from src.http_utils import http_get_json
from src.resources import resource_path

_DATA_FILE = resource_path("data", "hardiness_zones.json")


@lru_cache(maxsize=1)
def _load_zones() -> dict:
    """Load and cache the zone JSON file."""
    try:
        with open(_DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"regions": [], "fallback_latitude_bands": []}


def get_zone(lat: float, lng: float) -> Optional[int]:
    """
    Return the approximate USDA/Canadian hardiness zone for (lat, lng),
    or None if outside the covered area.

    Strategy:
    1. Check every bounding-box region in the JSON; collect all matches.
    2. Return the zone from the smallest matching region (most specific).
    3. If no region matches, fall back to latitude-band lookup.
    """
    if lat is None or lng is None:
        return None

    data = _load_zones()

    # ── Region lookup ──────────────────────────────────────────────────────
    best_zone: Optional[int] = None
    best_area: Optional[float] = None

    for region in data.get("regions", []):
        if (region["lat_min"] <= lat <= region["lat_max"] and
                region["lng_min"] <= lng <= region["lng_max"]):
            area = (
                (region["lat_max"] - region["lat_min"]) *
                (region["lng_max"] - region["lng_min"])
            )
            if best_area is None or area < best_area:
                best_area = area
                best_zone = region["zone"]

    if best_zone is not None:
        return best_zone

    # ── Latitude-band fallback ─────────────────────────────────────────────
    for band in data.get("fallback_latitude_bands", []):
        if band["lat_min"] <= lat < band["lat_max"]:
            return band["zone"]

    # Outside all known ranges
    return None


def zone_label(zone: Optional[int]) -> str:
    """Return a display string like 'Zone 3' or 'Zone: unknown'."""
    if zone is None:
        return "Zone: unknown"
    return f"Zone {zone}"


def zone_description(zone: Optional[int]) -> str:
    """Human-readable description of a zone for the status bar tooltip."""
    _desc = {
        1: "Zone 1 — extreme cold (< -45 °C winters)",
        2: "Zone 2 — very cold (-45 to -40 °C winters)",
        3: "Zone 3 — cold (-40 to -34 °C winters) — Edmonton area",
        4: "Zone 4 — moderate-cold (-34 to -29 °C winters) — Calgary area",
        5: "Zone 5 — mild-cold (-29 to -23 °C winters) — Lethbridge area",
        6: "Zone 6 — mild (-23 to -18 °C winters)",
        7: "Zone 7 — temperate (-18 to -12 °C winters)",
        8: "Zone 8 — warm-temperate (-12 to -7 °C winters) — Vancouver",
        9: "Zone 9 — warm (-7 to -1 °C winters) — Victoria",
    }
    return _desc.get(zone, zone_label(zone))


# ── Growing-degree days + frost window (V1.35, schema v14) ──────────────────
#
# GDD₅ (growing-degree days, base 5°C) is the standard climate metric for
# whether a plant has enough cumulative warmth to flower, set fruit, and
# reach maturity in a given location. Computed as the sum of
# max(0, daily_mean_temp - 5°C) across the growing season. Two locations
# can share a hardiness zone but differ in GDD₅ by 30%+ — Lethbridge
# accumulates ~1700 per year, Fort McMurray ~1300, both nominally Zone 3.
#
# Frost window is the average last-spring-frost day and first-fall-frost
# day across the historical record. The difference is the average
# frost-free-day count, which is what most planting calendars actually
# care about.


def compute_gdd(daily_rows: list[dict], base: float = 5.0) -> float:
    """Compute total growing-degree days from a list of daily-temperature
    rows. Each row is ``{"date": "YYYY-MM-DD", "tmin": float, "tmax":
    float}`` or similar with both temps in °C. Returns 0.0 on empty
    input. Returns the *mean per year* if rows span multiple years
    (callers usually want the annual mean, not the multi-year total).
    """
    if not daily_rows:
        return 0.0
    total = 0.0
    years: set[int] = set()
    for row in daily_rows:
        tmin = row.get("tmin")
        tmax = row.get("tmax")
        if tmin is None or tmax is None:
            continue
        # Daily mean approximation — standard for GDD when only daily
        # min/max are available (vs hourly).
        tmean = (float(tmin) + float(tmax)) / 2.0
        if tmean > base:
            total += (tmean - base)
        date_str = row.get("date") or ""
        if len(date_str) >= 4:
            try:
                years.add(int(date_str[:4]))
            except ValueError:
                pass
    n_years = len(years) or 1
    return round(total / n_years, 1)


def frost_window(daily_rows: list[dict]) -> dict:
    """Compute average last-spring-frost and first-fall-frost across all
    years in ``daily_rows``. "Frost" is tmin ≤ 0 °C. Returns:

        {
          "last_spring_frost_doy": int | None,   # avg day-of-year in Jan-Jun
          "first_fall_frost_doy":  int | None,   # avg day-of-year in Jul-Dec
          "frost_free_days":       int | None,
          "years_used":            int,
        }

    Returns Nones for the frost-day fields when no frost events were
    found (e.g. coastal subtropical locations) or when input is empty.
    """
    by_year: dict[int, list[dict]] = {}
    for row in daily_rows:
        date_str = row.get("date") or ""
        if len(date_str) < 4:
            continue
        try:
            year = int(date_str[:4])
        except ValueError:
            continue
        by_year.setdefault(year, []).append(row)

    last_spring_doys: list[int] = []
    first_fall_doys: list[int] = []
    for year, rows in by_year.items():
        last_spring: Optional[int] = None
        first_fall: Optional[int] = None
        for row in rows:
            tmin = row.get("tmin")
            if tmin is None or float(tmin) > 0:
                continue
            try:
                d = date.fromisoformat(row["date"])
            except (KeyError, ValueError):
                continue
            doy = d.timetuple().tm_yday
            if d.month <= 6:
                # First half of year — track the LAST frost we see.
                if last_spring is None or doy > last_spring:
                    last_spring = doy
            else:
                # Second half — track the FIRST frost we see.
                if first_fall is None or doy < first_fall:
                    first_fall = doy
        if last_spring is not None:
            last_spring_doys.append(last_spring)
        if first_fall is not None:
            first_fall_doys.append(first_fall)

    last_avg  = round(sum(last_spring_doys) / len(last_spring_doys)) \
        if last_spring_doys else None
    first_avg = round(sum(first_fall_doys) / len(first_fall_doys)) \
        if first_fall_doys else None
    free_days: Optional[int] = None
    if last_avg is not None and first_avg is not None:
        free_days = first_avg - last_avg
    return {
        "last_spring_frost_doy": last_avg,
        "first_fall_frost_doy":  first_avg,
        "frost_free_days":       free_days,
        "years_used":            len(by_year),
    }


def _http_get_json(url: str, timeout: float = 20.0) -> Optional[dict]:
    """Module-local alias for :func:`src.http_utils.http_get_json`, kept so
    tests can monkeypatch ``climate._http_get_json``."""
    return http_get_json(url, timeout=timeout)


def fetch_historical_temps(
    lat: float, lng: float, years: int = 3,
) -> Optional[list[dict]]:
    """Fetch the last ``years`` complete calendar years of daily min/max
    temperature for (lat, lng) from Open-Meteo Historical Weather
    (ERA5-Land). Returns a list of ``{date, tmin, tmax}`` dicts in
    chronological order, or ``None`` on any failure.

    Default ``years=3`` since V1.37 — the GDD + frost-window stats
    are stable across 3+ year windows in continental climates, and
    the smaller payload halves the on-pin-drop fetch time vs. the
    original 5-year window. Caller can pass a larger ``years`` for
    higher-resolution averaging when latency doesn't matter.

    Same vendor / endpoint / timeout policy as
    ``property_data.fetch_rainfall`` — keeping the network surface
    uniform across the codebase."""
    today = date.today()
    end_d = date(today.year - 1, 12, 31)
    start = date(end_d.year - years + 1, 1, 1)
    url = (
        "https://archive-api.open-meteo.com/v1/archive?"
        f"latitude={lat:.4f}&longitude={lng:.4f}"
        f"&start_date={start.isoformat()}&end_date={end_d.isoformat()}"
        "&daily=temperature_2m_min,temperature_2m_max&timezone=UTC"
    )
    data = _http_get_json(url)
    if not data or "daily" not in data:
        return None
    daily = data["daily"]
    times  = daily.get("time")          or []
    tmins  = daily.get("temperature_2m_min") or []
    tmaxs  = daily.get("temperature_2m_max") or []
    if not times or len(times) != len(tmins) or len(times) != len(tmaxs):
        return None
    return [
        {"date": t, "tmin": tmin, "tmax": tmax}
        for t, tmin, tmax in zip(times, tmins, tmaxs)
        if tmin is not None and tmax is not None
    ]


def get_climate_summary(
    lat: float, lng: float,
    *,
    use_cache: bool = True,
    _fetcher=fetch_historical_temps,
) -> Optional[dict]:
    """Return a climate-summary dict for (lat, lng), or ``None`` if the
    fetch fails and nothing is cached. Shape:

        {
          "gdd5_mean":             float,
          "last_spring_frost_doy": int,
          "first_fall_frost_doy":  int,
          "frost_free_days":       int,
          "years_used":            int,
          "source":                str,
          "cached":                bool,   # True if served from DB cache
        }

    On a cache miss, fetches from Open-Meteo, derives the stats, stores
    them, and returns ``cached=False``. The ``_fetcher`` parameter
    exists for tests (mock the network call without monkey-patching the
    module attribute)."""
    if use_cache:
        try:
            from src.db.plants import get_cached_climate
            cached = get_cached_climate(lat, lng)
        except Exception:
            cached = None
        if cached:
            cached["cached"] = True
            return cached

    rows = _fetcher(lat, lng)
    if not rows:
        return None

    summary = {
        "gdd5_mean": compute_gdd(rows, base=5.0),
        "source":    "Open-Meteo / ERA5-Land",
        "cached":    False,
    }
    summary.update(frost_window(rows))

    if use_cache:
        try:
            from src.db.plants import store_cached_climate
            store_cached_climate(lat, lng, summary)
        except Exception:
            pass            # cache failure shouldn't block the result
    return summary


def fetch_daily_temp_precip(
    lat: float, lng: float, years: int = 5,
) -> Optional[list[dict]]:
    """Fetch the last ``years`` complete calendar years of daily min/max
    temperature **and** precipitation for (lat, lng) from Open-Meteo (ERA5-Land).
    Returns ``[{date, tmin, tmax, precip}]`` chronologically, or ``None``.

    Same vendor/endpoint as :func:`fetch_historical_temps`; precipitation is
    included so the snow model (:mod:`src.snow`) can build a snowpack alongside
    the freeze–thaw counts. Default ``years=5`` for stable winter averages."""
    today = date.today()
    end_d = date(today.year - 1, 12, 31)
    start = date(end_d.year - years + 1, 1, 1)
    url = (
        "https://archive-api.open-meteo.com/v1/archive?"
        f"latitude={lat:.4f}&longitude={lng:.4f}"
        f"&start_date={start.isoformat()}&end_date={end_d.isoformat()}"
        "&daily=temperature_2m_min,temperature_2m_max,precipitation_sum"
        "&models=era5_land&timezone=UTC"
    )
    data = _http_get_json(url, timeout=20.0)
    if not data or "daily" not in data:
        return None
    daily = data["daily"]
    times  = daily.get("time")               or []
    tmins  = daily.get("temperature_2m_min") or []
    tmaxs  = daily.get("temperature_2m_max") or []
    precs  = daily.get("precipitation_sum")  or []
    if not times or len(times) != len(tmins) or len(times) != len(tmaxs):
        return None
    out: list[dict] = []
    for i, t in enumerate(times):
        if tmins[i] is None or tmaxs[i] is None:
            continue
        out.append({
            "date":   t,
            "tmin":   tmins[i],
            "tmax":   tmaxs[i],
            "precip": precs[i] if i < len(precs) and precs[i] is not None else 0.0,
        })
    return out


def get_winter_summary(
    lat: float, lng: float, *, _fetcher=fetch_daily_temp_precip,
) -> Optional[dict]:
    """Winter snow-cover + survival metrics for (lat, lng) — the *insulation*
    half of the snow story. Fetches daily temp+precip and runs the snow model in
    :mod:`src.snow`. Returns the metrics dict (with a ``source``), or ``None``.

    Not DB-cached (unlike :func:`get_climate_summary`): the result rides in the
    project's ``site_config`` so it persists with the design and is always
    computed fresh on a new pin-drop. ``_fetcher`` is injectable for tests."""
    rows = _fetcher(lat, lng)
    if not rows:
        return None
    from src import snow
    metrics = snow.winter_metrics(rows)
    if metrics:
        metrics["source"] = "Open-Meteo / ERA5-Land (modelled snowpack)"
    return metrics


def doy_to_date_label(doy: Optional[int], year: int = 2025) -> str:
    """Format a day-of-year as 'Jun 15' for UI display. Uses a non-leap
    reference year by default — the difference vs leap years is at most
    one day."""
    if doy is None:
        return "—"
    try:
        d = date.fromordinal(date(year, 1, 1).toordinal() + int(doy) - 1)
    except (ValueError, OverflowError):
        return "—"
    return d.strftime("%b %-d") if os.name != "nt" else d.strftime("%b %d").lstrip("0")

"""
wind.py — seasonal wind rose + live current wind from Open-Meteo (V1.67).

Wind used to be a single user-picked arrow. This adds real data, free and with
no API key, from the same vendor/endpoint family as ``src/climate.py``:

  * :func:`fetch_historical_wind` — multi-year **hourly** wind speed + direction
    from the Open-Meteo archive (ERA5). Hourly is required to build a rose.
  * :func:`compute_wind_rose` — pure aggregation into a 16-compass-direction ×
    speed-bin frequency rose, for the whole year and each season, plus the
    prevailing direction, calm fraction, and mean/max speed.
  * :func:`get_wind_summary` — DB-cached (``wind_cache``) like the climate
    summary, so after one fetch the rose is available offline. ``_fetcher`` is
    injectable for tests.
  * :func:`fetch_current_wind` — the "now" reading from the forecast endpoint
    (online-only; small banner alongside the historical rose).
  * :func:`wind_rose_geometry` — pure rose→wedges for the UI to paint (keeps the
    drawing layer dumb and the maths unit-testable).

Direction convention matches the app and Open-Meteo: degrees the wind blows
**from**, 0 = N, 90 = E, 180 = S, 270 = W. Speeds are km/h (Open-Meteo default).
Qt-free, network-graceful (every fetch returns ``None`` on failure).
"""

from __future__ import annotations

import json
import math
import urllib.error
import urllib.request
from datetime import date
from typing import Optional

_ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
_FORECAST_URL = "https://api.open-meteo.com/v1/forecast"

_DIRS_16 = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
            "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]

# Speed bins in km/h with display labels (last bin is open-ended).
_SPEED_EDGES = [5.0, 12.0, 20.0, 30.0]            # → 5 bins
_SPEED_LABELS = ["Calm/Light", "Light", "Moderate", "Strong", "Very strong"]
# Below this the direction is meaningless — counted as "calm".
_CALM_KMH = 2.0

# Map a mean km/h to the analysis panel's 4 category words.
_CATEGORY_EDGES = [(8.0, "Light"), (18.0, "Moderate"),
                   (30.0, "Strong"), (1e9, "Very Strong")]


def dir_index(deg: float) -> int:
    """16-point compass index (0 = N) for a bearing in degrees."""
    return int(((deg % 360) + 11.25) // 22.5) % 16


def dir_label(deg: float) -> str:
    return _DIRS_16[dir_index(deg)]


def speed_category(kmh: Optional[float]) -> str:
    """Mean speed → the existing UI's Light/Moderate/Strong/Very Strong word."""
    if kmh is None:
        return "Moderate"
    for edge, label in _CATEGORY_EDGES:
        if kmh < edge:
            return label
    return "Very Strong"


def _speed_bin(kmh: float) -> int:
    for i, edge in enumerate(_SPEED_EDGES):
        if kmh < edge:
            return i
    return len(_SPEED_EDGES)        # last (open-ended) bin


def _http_get_json(url: str, timeout: float = 20.0) -> Optional[dict]:
    """Minimal stdlib JSON GET (mirrors climate._http_get_json). None on any
    network/parse failure — caller renders 'unavailable' rather than crashing."""
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, urllib.error.HTTPError,
            json.JSONDecodeError, TimeoutError, OSError):
        return None


def fetch_historical_wind(lat: float, lng: float,
                          years: int = 2) -> Optional[list]:
    """Last ``years`` complete calendar years of **hourly** wind speed +
    direction for (lat, lng) from Open-Meteo archive (ERA5). Returns a list of
    ``{"month": int, "speed": km/h, "dir_deg": deg-from}`` dicts, or ``None``.

    ``years=2`` keeps the hourly payload modest (~17k rows) while a rose is
    stable across 2+ years in continental climates."""
    today = date.today()
    end_d = date(today.year - 1, 12, 31)
    start = date(end_d.year - years + 1, 1, 1)
    url = (
        f"{_ARCHIVE_URL}?latitude={lat:.4f}&longitude={lng:.4f}"
        f"&start_date={start.isoformat()}&end_date={end_d.isoformat()}"
        "&hourly=wind_speed_10m,wind_direction_10m&timezone=UTC"
    )
    data = _http_get_json(url)
    if not data or "hourly" not in data:
        return None
    h = data["hourly"]
    times = h.get("time") or []
    speeds = h.get("wind_speed_10m") or []
    dirs = h.get("wind_direction_10m") or []
    if not times or len(times) != len(speeds) or len(times) != len(dirs):
        return None
    rows = []
    for t, s, d in zip(times, speeds, dirs):
        if s is None or d is None:
            continue
        # t is "YYYY-MM-DDTHH:MM"; month drives the seasonal split.
        try:
            month = int(t[5:7])
        except (ValueError, IndexError):
            continue
        rows.append({"month": month, "speed": float(s), "dir_deg": float(d)})
    return rows or None


# Meteorological seasons (Northern Hemisphere).
_SEASON_OF = {12: "winter", 1: "winter", 2: "winter",
              3: "spring", 4: "spring", 5: "spring",
              6: "summer", 7: "summer", 8: "summer",
              9: "fall", 10: "fall", 11: "fall"}


def _rose_block(rows: list) -> dict:
    """Aggregate a list of {speed, dir_deg} into one rose block."""
    n = len(rows)
    if n == 0:
        return {"n": 0, "calm_pct": 0.0, "mean_speed": 0.0, "max_speed": 0.0,
                "prevailing_deg": None, "prevailing_label": None,
                "matrix": [[0.0] * (len(_SPEED_EDGES) + 1) for _ in range(16)]}
    n_bins = len(_SPEED_EDGES) + 1
    matrix = [[0 for _ in range(n_bins)] for _ in range(16)]
    calm = 0
    speed_sum = 0.0
    speed_max = 0.0
    dir_counts = [0] * 16
    for r in rows:
        sp = r["speed"]
        speed_sum += sp
        speed_max = max(speed_max, sp)
        if sp < _CALM_KMH:
            calm += 1
            continue
        di = dir_index(r["dir_deg"])
        matrix[di][_speed_bin(sp)] += 1
        dir_counts[di] += 1
    prevailing_i = max(range(16), key=lambda i: dir_counts[i]) \
        if any(dir_counts) else None
    pct = [[round(100.0 * c / n, 3) for c in row] for row in matrix]
    return {
        "n": n,
        "calm_pct": round(100.0 * calm / n, 2),
        "mean_speed": round(speed_sum / n, 1),
        "max_speed": round(speed_max, 1),
        "prevailing_deg": (prevailing_i * 22.5) if prevailing_i is not None
                          else None,
        "prevailing_label": _DIRS_16[prevailing_i] if prevailing_i is not None
                            else None,
        "matrix": pct,          # 16 dirs × n_bins, percent of block total
    }


def compute_wind_rose(rows: list) -> dict:
    """Pure aggregation of hourly rows into annual + seasonal rose blocks.

    Returns ``{"annual": block, "seasons": {spring/summer/fall/winter: block},
    "speed_labels": [...], "source": str}`` where each block is
    :func:`_rose_block` output. The annual block's ``prevailing_label`` is what
    drives the overlay and the windbreak suggestion."""
    by_season: dict[str, list] = {"spring": [], "summer": [],
                                  "fall": [], "winter": []}
    for r in rows or []:
        by_season[_SEASON_OF.get(r.get("month", 0), "summer")].append(r)
    return {
        "annual": _rose_block(rows or []),
        "seasons": {s: _rose_block(rs) for s, rs in by_season.items()},
        "speed_labels": list(_SPEED_LABELS),
        "source": "Open-Meteo / ERA5",
    }


def get_wind_summary(lat: float, lng: float, *, use_cache: bool = True,
                     _fetcher=fetch_historical_wind) -> Optional[dict]:
    """Return the wind rose for (lat, lng), cached in ``wind_cache``. On a miss,
    fetch hourly history, compute the rose, store, and return it (with
    ``cached=False``). ``None`` only when the fetch fails and nothing is cached.
    ``_fetcher`` is injectable for tests."""
    if use_cache:
        try:
            from src.db.plants import get_cached_wind
            cached = get_cached_wind(lat, lng)
        except Exception:  # noqa: BLE001
            cached = None
        if cached:
            cached["cached"] = True
            return cached

    rows = _fetcher(lat, lng)
    if not rows:
        return None
    rose = compute_wind_rose(rows)
    rose["cached"] = False
    if use_cache:
        try:
            from src.db.plants import store_cached_wind
            store_cached_wind(lat, lng, rose)
        except Exception:  # noqa: BLE001 — cache failure shouldn't block result
            pass
    return rose


def fetch_current_wind(lat: float, lng: float) -> Optional[dict]:
    """Live 'now' wind (online-only) from the Open-Meteo forecast endpoint.
    Returns ``{"speed", "dir_deg", "dir_label", "gusts"}`` (km/h) or ``None``."""
    url = (
        f"{_FORECAST_URL}?latitude={lat:.4f}&longitude={lng:.4f}"
        "&current=wind_speed_10m,wind_direction_10m,wind_gusts_10m"
        "&timezone=auto"
    )
    data = _http_get_json(url, timeout=12.0)
    cur = (data or {}).get("current") or {}
    speed = cur.get("wind_speed_10m")
    deg = cur.get("wind_direction_10m")
    if speed is None or deg is None:
        return None
    return {
        "speed": round(float(speed), 1),
        "dir_deg": float(deg),
        "dir_label": dir_label(float(deg)),
        "gusts": (round(float(cur["wind_gusts_10m"]), 1)
                  if cur.get("wind_gusts_10m") is not None else None),
    }


_AXIS_NAMES = ["N–S", "NE–SW", "E–W", "NW–SE"]


def _axis_label(axis_deg: float) -> str:
    """Nearest of the 4 windbreak axes for an axis bearing in [0, 180)."""
    return _AXIS_NAMES[int((axis_deg + 22.5) // 45) % 4]


def windbreak_advice(rose: Optional[dict], *, exposed_kmh: float = 18.0):
    """Design hint from a rose: which way to run a windbreak (perpendicular to
    the prevailing wind) and whether the site is exposed. Returns
    ``{"orientation_axis_deg", "orientation_label", "exposed", "mean_speed",
    "text"}`` or ``None`` when there's no prevailing direction."""
    a = (rose or {}).get("annual") or {}
    deg = a.get("prevailing_deg")
    label = a.get("prevailing_label")
    if deg is None:
        return None
    mean = float(a.get("mean_speed") or 0.0)
    axis = (deg + 90.0) % 180.0          # barrier runs across the wind
    axis_label = _axis_label(axis)
    exposed = mean >= exposed_kmh
    text = (f"Prevailing wind from {label} (~{mean:.0f} km/h). "
            f"Run a windbreak/hedgerow {axis_label} (across the wind)")
    text += (". Exposed site — shelter wind-sensitive plants such as fruit "
             "trees and broadleaf evergreens." if exposed else ".")
    return {"orientation_axis_deg": axis, "orientation_label": axis_label,
            "exposed": exposed, "mean_speed": mean, "text": text}


def wind_rose_geometry(block: dict, *, max_radius: float = 1.0) -> list:
    """Turn one rose block into stacked wedges for the UI to paint.

    Returns a list of ``{"dir_index", "start_deg", "end_deg", "r0", "r1",
    "band", "pct"}`` — one wedge per (direction, speed band) with non-zero
    frequency, radius scaled so the busiest direction reaches ``max_radius``.
    ``start_deg``/``end_deg`` are compass bearings (0 = N, clockwise) centred on
    each direction; the painter maps bearing→screen angle."""
    matrix = block.get("matrix") or []
    if not matrix:
        return []
    dir_totals = [sum(row) for row in matrix]
    peak = max(dir_totals) if dir_totals else 0.0
    if peak <= 0:
        return []
    scale = max_radius / peak
    wedges = []
    for i, row in enumerate(matrix):
        center = i * 22.5
        r0 = 0.0
        for band, pct in enumerate(row):
            if pct <= 0:
                continue
            r1 = r0 + pct * scale
            wedges.append({
                "dir_index": i,
                "start_deg": center - 11.25,
                "end_deg": center + 11.25,
                "r0": r0, "r1": r1,
                "band": band, "pct": pct,
            })
            r0 = r1
    return wedges

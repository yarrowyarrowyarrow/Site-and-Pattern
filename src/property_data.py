"""
property_data.py — Auto-fill site data for a property pin.

Pulls four datasets for a (lat, lng):

  * rainfall   — Open-Meteo / ERA5-Land daily precipitation, averaged
                 into annual + monthly means.
  * soil       — SoilGrids v2.0 (ISRIC): pH, sand/silt/clay %, depth.
  * elevation  — Copernicus DEM 30m via Open-Meteo's elevation endpoint;
                 slope (% and degrees) and aspect computed by sampling
                 four neighbours at a configurable offset.
  * hardiness  — Local NRCan-derived dataset (data/hardiness_zones.json)
                 with a fallback that derives a USDA zone from the average
                 annual extreme minimum temperature in ERA5-Land.

All network calls use stdlib only and degrade gracefully when offline:
fetchers return ``None`` on any error so the UI can show "unavailable"
rather than crashing.
"""

from __future__ import annotations

import json
import math
import os
import urllib.parse
import urllib.request
from datetime import date, timedelta
from typing import Optional

from src.climate import get_zone


_TIMEOUT = 8.0
_USER_AGENT = "PermaDesign/1.0 (https://github.com/yarrowyarrowyarrow/permadesign)"


def _http_get_json(url: str, timeout: float = _TIMEOUT) -> Optional[dict]:
    """GET a URL, return parsed JSON, or None on any failure."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception:
        return None


# ── Rainfall ────────────────────────────────────────────────────────────────

def fetch_rainfall(lat: float, lng: float, years: int = 10) -> Optional[dict]:
    """
    Annual + monthly mean precipitation (mm) from ERA5-Land via Open-Meteo.

    Returns ``{"annual_mm", "monthly_mm" (12), "years_used", "source"}``
    or ``None`` if the request fails.
    """
    today = date.today()
    end_d = date(today.year - 1, 12, 31)
    start = date(end_d.year - years + 1, 1, 1)
    url = (
        "https://archive-api.open-meteo.com/v1/archive?"
        f"latitude={lat:.4f}&longitude={lng:.4f}"
        f"&start_date={start.isoformat()}&end_date={end_d.isoformat()}"
        "&daily=precipitation_sum&timezone=UTC"
    )
    data = _http_get_json(url)
    if not data or "daily" not in data:
        return None
    return _parse_rainfall(data)


def _parse_rainfall(data: dict) -> Optional[dict]:
    times = data["daily"].get("time") or []
    sums  = data["daily"].get("precipitation_sum") or []
    if not times or len(times) != len(sums):
        return None
    monthly = [0.0] * 12
    annuals: dict[int, float] = {}
    for t, p in zip(times, sums):
        if p is None:
            continue
        year  = int(t[:4])
        month = int(t[5:7])
        annuals[year] = annuals.get(year, 0.0) + p
        monthly[month - 1] += p
    n_years = len(annuals) or 1
    monthly_mean = [round(monthly[i] / n_years, 1) for i in range(12)]
    annual_mean  = round(sum(annuals.values()) / n_years, 1)
    return {
        "annual_mm":   annual_mean,
        "monthly_mm":  monthly_mean,
        "years_used":  n_years,
        "source":      "Open-Meteo / ERA5-Land",
    }


# ── Soil ────────────────────────────────────────────────────────────────────

def fetch_soil(lat: float, lng: float) -> Optional[dict]:
    """
    Soil pH, sand/silt/clay %, and reported depth.

    Tries SoilGrids v2.0 (ISRIC) first; if the live API is unavailable
    or returns no usable data, falls back to a curated Alberta regional
    approximation bundled with the app (see
    ``data/soil_fallback_alberta.json``). The returned dict's
    ``source`` field always reflects which path was used so the UI can
    label the data appropriately.

    Top-layer values are surfaced in ``summary``; per-depth values are
    kept in ``properties`` for callers that want the full profile.
    """
    qs = urllib.parse.urlencode([
        ("lat", f"{lat:.4f}"),
        ("lon", f"{lng:.4f}"),
        ("property", "phh2o"),
        ("property", "sand"),
        ("property", "silt"),
        ("property", "clay"),
        ("depth", "0-5cm"),
        ("depth", "5-15cm"),
        ("depth", "15-30cm"),
        ("depth", "30-60cm"),
        ("depth", "60-100cm"),
        ("value", "mean"),
    ], doseq=True)
    url = f"https://rest.isric.org/soilgrids/v2.0/properties/query?{qs}"
    data = _http_get_json(url)
    parsed = _parse_soilgrids(data) if data else None
    if parsed is not None:
        return parsed
    # Fallback: nearest Alberta regional profile.
    return _alberta_soil_fallback(lat, lng)


def _alberta_soil_fallback(lat: float, lng: float) -> Optional[dict]:
    """Return the closest bundled Alberta regional soil profile, or None.

    The result is shaped like ``_parse_soilgrids`` output (same
    ``summary`` keys, plus a single synthetic ``properties`` block) so
    the UI can render it without a special case. ``source`` makes the
    approximation explicit so users don't mistake it for a measured
    point estimate.
    """
    import json as _json
    import math as _math

    here = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(here)
    path = os.path.join(project_root, "data", "soil_fallback_alberta.json")
    try:
        with open(path, "r", encoding="utf-8") as f:
            entries = _json.load(f)
    except (OSError, ValueError):
        return None
    if not isinstance(entries, list) or not entries:
        return None

    def _dist2(p, q):
        # Squared great-circle approximation in degrees — fine for
        # picking the nearest centroid out of a half-dozen candidates.
        dlat = p[0] - q[0]
        dlng = (p[1] - q[1]) * _math.cos(_math.radians((p[0] + q[0]) / 2))
        return dlat * dlat + dlng * dlng

    best = min(entries, key=lambda e: _dist2((lat, lng), tuple(e.get("centroid") or (0, 0))))
    ph    = best.get("ph_top")
    sand  = best.get("sand_pct_top")
    silt  = best.get("silt_pct_top")
    clay  = best.get("clay_pct_top")
    depth = best.get("max_reported_depth_cm")

    by_prop = {}
    if ph   is not None: by_prop["phh2o"] = [{"label": "0-30cm (regional)", "value": ph}]
    if sand is not None: by_prop["sand"]  = [{"label": "0-30cm (regional)", "value": sand}]
    if silt is not None: by_prop["silt"]  = [{"label": "0-30cm (regional)", "value": silt}]
    if clay is not None: by_prop["clay"]  = [{"label": "0-30cm (regional)", "value": clay}]

    return {
        "properties": by_prop,
        "summary": {
            "ph_top":               ph,
            "sand_pct_top":         sand,
            "silt_pct_top":         silt,
            "clay_pct_top":         clay,
            "texture_class":        best.get("texture_class") or _texture_class(sand, silt, clay),
            "max_reported_depth_cm": depth,
        },
        "source": (
            f"Regional approximation — {best.get('region', 'Alberta')} "
            f"(SoilGrids v2.0 unavailable; bundled AB soil atlas)"
        ),
        "fallback": True,
        "fallback_notes": best.get("notes", ""),
    }


# SoilGrids stores values as int * d_factor. For phh2o (pH) and sand/silt/clay
# (g/kg as 0.1 % units), d_factor is 10.
_SG_FACTORS = {"phh2o": 10.0, "sand": 10.0, "silt": 10.0, "clay": 10.0}


def _parse_soilgrids(data: dict) -> Optional[dict]:
    layers = data.get("properties", {}).get("layers", [])
    if not layers:
        return None
    by_prop: dict[str, list[dict]] = {}
    for layer in layers:
        name = layer.get("name")
        f    = _SG_FACTORS.get(name, 1.0)
        depths = []
        for d in layer.get("depths", []):
            mean = (d.get("values") or {}).get("mean")
            if mean is None:
                continue
            depths.append({"label": d.get("label"), "value": round(mean / f, 2)})
        if depths:
            by_prop[name] = depths
    if not by_prop:
        return None

    def _top(prop: str) -> Optional[float]:
        rows = by_prop.get(prop) or []
        return rows[0]["value"] if rows else None

    sand, silt, clay = _top("sand"), _top("silt"), _top("clay")
    return {
        "properties": by_prop,
        "summary": {
            "ph_top":               _top("phh2o"),
            "sand_pct_top":         sand,
            "silt_pct_top":         silt,
            "clay_pct_top":         clay,
            "texture_class":        _texture_class(sand, silt, clay),
            "max_reported_depth_cm": _max_reported_depth(by_prop),
        },
        "source": "SoilGrids v2.0 (ISRIC)",
    }


def _max_reported_depth(by_prop: dict) -> Optional[int]:
    """Deepest bottom-cm across any reported depth label."""
    deepest = 0
    for depths in by_prop.values():
        for d in depths:
            label = d.get("label") or ""
            try:
                bottom = int(label.split("-")[-1].replace("cm", ""))
            except (ValueError, AttributeError):
                continue
            if bottom > deepest:
                deepest = bottom
    return deepest or None


def _texture_class(sand, silt, clay) -> Optional[str]:
    """USDA soil-texture class from sand/silt/clay percentages.

    Implements the standard USDA texture triangle. Values outside 0-100 or
    not summing close to 100 still produce a best-effort classification.
    """
    if None in (sand, silt, clay):
        return None
    s, si, c = float(sand), float(silt), float(clay)

    if c >= 40:
        if si >= 40:               return "Silty clay"
        if s >= 45:                return "Sandy clay"
        return "Clay"
    if c >= 27:
        if s <= 20:                return "Silty clay loam"
        if s <= 45:                return "Clay loam"
        return "Sandy clay loam"
    if c >= 20 and s > 45 and si < 28:
        return "Sandy clay loam"
    if si >= 80 and c < 12:        return "Silt"
    if si >= 50 and c < 27:        return "Silt loam"
    if s >= 85 and (si + 1.5 * c) < 15: return "Sand"
    if s >= 70 and (si + 2.0 * c) < 30: return "Loamy sand"
    if 43 <= s <= 85 and c < 20:   return "Sandy loam"
    return "Loam"


# ── Elevation / slope / aspect ──────────────────────────────────────────────

def fetch_elevation(lat: float, lng: float, sample_m: float = 60.0) -> Optional[dict]:
    """
    Elevation, slope, and aspect from Copernicus DEM 30m via Open-Meteo.

    The DEM is sampled at the centre and at four neighbours offset by
    ``sample_m`` metres (N/E/S/W). dz/dx and dz/dy are derived by central
    differences, so slope is the local gradient magnitude over the
    sampling window — a reasonable parcel-scale estimate.
    """
    points = _slope_sample_points(lat, lng, sample_m)
    lats = ",".join(f"{p[0]:.6f}" for p in points)
    lngs = ",".join(f"{p[1]:.6f}" for p in points)
    url  = f"https://api.open-meteo.com/v1/elevation?latitude={lats}&longitude={lngs}"
    data = _http_get_json(url)
    if not data or "elevation" not in data:
        return None
    return _parse_elevation(data["elevation"], sample_m)


def _slope_sample_points(lat: float, lng: float, m: float):
    """[centre, N, E, S, W] in degrees, offset by ``m`` metres."""
    dlat = m / 111320.0
    cos_lat = math.cos(math.radians(lat))
    if abs(cos_lat) < 1e-9:
        cos_lat = 1e-9
    dlng = m / (111320.0 * cos_lat)
    return [
        (lat,        lng),
        (lat + dlat, lng),
        (lat,        lng + dlng),
        (lat - dlat, lng),
        (lat,        lng - dlng),
    ]


def _parse_elevation(elev: list, sample_m: float) -> Optional[dict]:
    if not elev or len(elev) < 5 or any(v is None for v in elev[:5]):
        return None
    centre, n, e, s, w = elev[:5]
    dz_dx = (e - w) / (2.0 * sample_m)   # +x = east
    dz_dy = (n - s) / (2.0 * sample_m)   # +y = north
    grad   = math.hypot(dz_dx, dz_dy)
    slope_pct = round(grad * 100.0, 2)
    slope_deg = round(math.degrees(math.atan(grad)), 2)

    if slope_pct < 0.05:
        aspect_deg, aspect = None, "Flat"
    else:
        # Downhill direction: azimuth (deg from N, clockwise) of -gradient.
        ang = math.degrees(math.atan2(-dz_dx, -dz_dy))
        ang = (ang + 360.0) % 360.0
        aspect_deg = round(ang, 1)
        aspect     = _compass_label(ang)

    return {
        "elevation_m": round(centre, 1),
        "slope_pct":   slope_pct,
        "slope_deg":   slope_deg,
        "aspect_deg":  aspect_deg,
        "aspect":      aspect,
        "sample_m":    sample_m,
        "source":      "Copernicus DEM 30m (via Open-Meteo)",
    }


def _compass_label(deg: float) -> str:
    dirs = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
    return dirs[int((deg + 22.5) // 45) % 8]


# ── Hardiness zone ──────────────────────────────────────────────────────────

def fetch_hardiness(lat: float, lng: float) -> Optional[dict]:
    """
    Hardiness zone for the property.

    First consults the local NRCan-derived dataset
    (``data/hardiness_zones.json``).  If that returns None — i.e. the
    point is outside the bundled regions — falls back to deriving a USDA
    zone from the average annual extreme minimum temperature in ERA5-Land.
    """
    z = get_zone(lat, lng)
    if z is not None:
        return {
            "zone":   z,
            "source": "NRCan plant hardiness zones (local)",
        }

    today = date.today()
    end_d = date(today.year - 1, 12, 31)
    start = date(end_d.year - 9, 1, 1)
    url = (
        "https://archive-api.open-meteo.com/v1/archive?"
        f"latitude={lat:.4f}&longitude={lng:.4f}"
        f"&start_date={start.isoformat()}&end_date={end_d.isoformat()}"
        "&daily=temperature_2m_min&timezone=UTC"
    )
    data = _http_get_json(url)
    if not data or "daily" not in data:
        return None
    return _parse_hardiness_fallback(data)


def _parse_hardiness_fallback(data: dict) -> Optional[dict]:
    times = data["daily"].get("time") or []
    mins  = data["daily"].get("temperature_2m_min") or []
    annual_mins: dict[int, float] = {}
    for t, m in zip(times, mins):
        if m is None:
            continue
        year = int(t[:4])
        cur = annual_mins.get(year)
        if cur is None or m < cur:
            annual_mins[year] = m
    if not annual_mins:
        return None
    avg_min_c = sum(annual_mins.values()) / len(annual_mins)
    return {
        "zone":             usda_zone_from_min_c(avg_min_c),
        "avg_extreme_min_c": round(avg_min_c, 1),
        "source":           "Open-Meteo / ERA5-Land (extreme-min fallback)",
    }


def usda_zone_from_min_c(min_c: float) -> int:
    """USDA hardiness zone (1-13) from average annual extreme-min °C.

    USDA bands are 10 °F wide: zone 1 = [-60, -50) °F, zone 2 = [-50, -40),
    …, zone 13 = [60, 70). Boundary temperatures fall into the warmer zone.
    """
    f = min_c * 9.0 / 5.0 + 32.0
    z = int((f + 60.0) // 10.0) + 1
    return max(1, min(13, z))


# ── Geocoding (Alberta, OSM Nominatim) ──────────────────────────────────────

_AB_VIEWBOX = "-120.0,48.95,-109.95,60.05"   # lng_min, lat_min, lng_max, lat_max


def geocode_alberta(query: str, limit: int = 6,
                    *, near: "tuple[float, float] | None" = None,
                    radius_km: float = 50.0) -> list[dict]:
    """Forward-geocode an address or place name, restricted to Alberta.

    Returns a list of ``{"label", "lat", "lng"}`` dicts, or ``[]`` on
    failure / no match. Uses OSM Nominatim.

    Results are re-ranked client-side so that hits whose street-number
    starts with a numeric token in the query (e.g. typing "4916" should
    surface 4916-something as the first result) sort ahead of generic
    matches that just happen to mention the digits anywhere in the
    display name.

    When ``near=(lat, lng)`` is supplied, the search is biased toward
    that point: the Nominatim viewbox shrinks to a ~``radius_km``-wide
    box around it instead of all of Alberta, and ``lat``/``lon`` query
    params are forwarded so Nominatim's own ranking weights local
    matches more heavily. This is what lets a short numeric query like
    "4916" surface real houses near where the user is looking instead
    of random province-wide hits.
    """
    import re

    q = (query or "").strip()
    if not q:
        return []

    # Direct "lat, lng" entry shortcut.
    m = re.match(r"^\s*(-?\d+(?:\.\d+)?)[,\s]+(-?\d+(?:\.\d+)?)\s*$", q)
    if m:
        try:
            lat, lng = float(m.group(1)), float(m.group(2))
            if -90 <= lat <= 90 and -180 <= lng <= 180:
                return [{
                    "label": f"{lat:.5f}, {lng:.5f}",
                    "lat": lat, "lng": lng,
                }]
        except ValueError:
            pass

    # Ask Nominatim for a few extra candidates so the client-side
    # re-ranking has something to work with even when the top raw match
    # is a generic placename.
    fetch_limit = max(int(limit), 10)
    extra_params: dict[str, str] = {}
    if near is not None:
        try:
            blat = float(near[0])
            blng = float(near[1])
            # ~111 km per latitude degree; AB longitude shrinks by ~cos(lat).
            dlat = max(0.05, float(radius_km) / 111.0)
            dlng = dlat / max(0.2, math.cos(math.radians(blat)))
            viewbox = (
                f"{blng - dlng:.5f},{blat - dlat:.5f},"
                f"{blng + dlng:.5f},{blat + dlat:.5f}"
            )
            extra_params["lat"] = f"{blat:.5f}"
            extra_params["lon"] = f"{blng:.5f}"
        except (TypeError, ValueError):
            viewbox = _AB_VIEWBOX
    else:
        viewbox = _AB_VIEWBOX

    params = urllib.parse.urlencode({
        "format": "json",
        "limit":  str(fetch_limit),
        "addressdetails": "1",
        "countrycodes": "ca",
        "viewbox": viewbox,
        "bounded": "1",
        "dedupe": "1",
        "q": q,
        **extra_params,
    })
    url = "https://nominatim.openstreetmap.org/search?" + params
    data = _http_get_json(url)
    if not isinstance(data, list):
        return []

    numeric_tokens = re.findall(r"\d+", q)
    word_tokens = [w.lower() for w in re.findall(r"[A-Za-z]{2,}", q)]
    q_lower = q.lower()

    out: list[tuple[int, int, dict]] = []  # (-score, original_idx, hit)
    for idx, it in enumerate(data):
        addr = it.get("address") or {}
        # Defence in depth: drop anything outside Alberta.
        if addr.get("state") != "Alberta" and addr.get("ISO3166-2-lvl4") != "CA-AB":
            continue
        try:
            lat = float(it["lat"])
            lng = float(it["lon"])
        except (KeyError, ValueError, TypeError):
            continue

        display_name = it.get("display_name") or q
        house_number = (addr.get("house_number") or "").strip()
        display_lower = display_name.lower()

        score = 0
        # Strongest signal: house number begins with a numeric token from
        # the query. Equality outranks startswith.
        for tok in numeric_tokens:
            if house_number == tok:
                score += 200
            elif house_number.startswith(tok):
                score += 120
            elif tok in house_number:
                score += 40
            if tok in display_lower:
                score += 15
        # Word-token coverage in the display name (street name etc.).
        for w in word_tokens:
            if w in display_lower:
                score += 10
        # Whole-query substring hit on display name is also informative.
        if q_lower and q_lower in display_lower:
            score += 25
        # Mild boost for exact match on Nominatim's own importance ranking.
        try:
            score += int(float(it.get("importance") or 0) * 5)
        except (TypeError, ValueError):
            pass

        out.append((-score, idx, {
            "label": display_name,
            "lat": lat,
            "lng": lng,
            "house_number": house_number,
        }))

    out.sort()
    ranked = [hit for _, _, hit in out]
    return ranked[:max(1, int(limit))]


def reverse_geocode(lat: float, lng: float) -> Optional[str]:
    """Reverse-geocode a coordinate to a human-readable address.

    Returns Nominatim's ``display_name`` string, or ``None`` if the
    lookup fails. Used by the Site panel to fill in the actual address
    when the user drops a pin manually.
    """
    try:
        params = urllib.parse.urlencode({
            "format": "json",
            "lat": f"{float(lat):.6f}",
            "lon": f"{float(lng):.6f}",
            "zoom": "18",
            "addressdetails": "1",
        })
    except (TypeError, ValueError):
        return None
    url = "https://nominatim.openstreetmap.org/reverse?" + params
    data = _http_get_json(url)
    if not isinstance(data, dict):
        return None
    label = data.get("display_name")
    if isinstance(label, str) and label.strip():
        return label.strip()
    return None


# ── Aggregator ──────────────────────────────────────────────────────────────

def fetch_all(lat: float, lng: float) -> dict:
    """Fetch all four datasets sequentially. Caller may want a thread."""
    return {
        "lat":       lat,
        "lng":       lng,
        "rainfall":  fetch_rainfall(lat, lng),
        "soil":      fetch_soil(lat, lng),
        "elevation": fetch_elevation(lat, lng),
        "hardiness": fetch_hardiness(lat, lng),
    }

"""
property_data.py — Auto-fill site data for a property pin.

Pulls four datasets for a (lat, lng):

  * rainfall   — Environment Canada 1981–2010 climate normal (bundled,
                 gauge-based) for prairie pins, falling back to Open-Meteo
                 ERA5-Land reanalysis outside the bundled coverage.
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
import urllib.parse
import urllib.request
from datetime import date, timedelta
from typing import Optional

from src.climate import get_zone
from src.http_utils import http_get_json
from src.projection import M_PER_DEG_LAT
from src.resources import resource_path


_TIMEOUT = 8.0


def _http_get_json(url: str, timeout: float = _TIMEOUT) -> Optional[dict]:
    """Module-local alias for :func:`src.http_utils.http_get_json`, kept so
    tests can monkeypatch ``property_data._http_get_json``."""
    return http_get_json(url, timeout=timeout)


# ── Rainfall ────────────────────────────────────────────────────────────────

# Distance (km) within which a bundled Environment Canada climate normal is
# treated as authoritative for a pin. ~150 km comfortably covers settled
# Alberta and the Edmonton–Red Deer–Calgary corridor; beyond it we fall back
# to live ERA5-Land rather than snapping to a distant station.
_NORMAL_MAX_KM = 150.0
# Within this radius the pin is effectively "in" the station's locality, so
# the source line names the normal without a "nearest station" caveat.
_NORMAL_LOCAL_KM = 60.0


def fetch_rainfall(lat: float, lng: float, years: int = 10) -> Optional[dict]:
    """
    Annual + monthly mean precipitation (mm) for a pin.

    Primary source is the bundled Environment Canada 1981–2010 climate
    normal (``data/rainfall_fallback_alberta.json``): gauge-based ground
    truth, a genuine *climate normal* (matching the panel header), and
    fully offline. Open-Meteo's ERA5-Land reanalysis is only used as a
    secondary source for pins outside the bundled prairie coverage — it
    is known to over-predict precipitation over land and averages over a
    coarse grid box, so it is labelled honestly rather than presented as a
    climate normal.

    Returns ``{"annual_mm", "monthly_mm" (12), "years_used", "source"}``
    or ``None`` if every source fails.
    """
    # 1. Primary — bundled EC climate normal when the pin is in coverage.
    normal = _climate_normal_rainfall(lat, lng, max_km=_NORMAL_MAX_KM)
    if normal is not None:
        return normal

    # 2. Secondary — live ERA5-Land reanalysis for out-of-coverage pins.
    #    Request the 9 km ERA5-Land model explicitly (the archive default is
    #    the coarser ~25 km ERA5) and let the API derive local day
    #    boundaries so daily totals are not split across the UTC midnight.
    today = date.today()
    end_d = date(today.year - 1, 12, 31)
    start = date(end_d.year - years + 1, 1, 1)
    url = (
        "https://archive-api.open-meteo.com/v1/archive?"
        f"latitude={lat:.4f}&longitude={lng:.4f}"
        f"&start_date={start.isoformat()}&end_date={end_d.isoformat()}"
        # rain_sum alongside the total gives a *measured* rain/snow split: snow
        # water-equivalent = precipitation_sum − rain_sum. precipitation_sum
        # stays the headline total (liquid-water equivalent).
        "&daily=precipitation_sum,rain_sum&models=era5_land&timezone=auto"
    )
    # The archive API ships ~10 years of daily data per call; the
    # default 8 s timeout is borderline on slower connections, so give
    # this endpoint more breathing room before declaring failure.
    data = _http_get_json(url, timeout=20.0)
    parsed = _parse_rainfall(data) if data and "daily" in data else None
    if parsed is not None:
        # A multi-year reanalysis mean is not a climate normal — say so.
        parsed["source"] = "Open-Meteo ERA5-Land (10-yr reanalysis mean)"
        return parsed

    # 3. Last resort — nearest EC normal regardless of distance, so an
    #    offline session out of coverage still shows an approximation.
    return _climate_normal_rainfall(lat, lng, max_km=None)


def _dist2(p, q) -> float:
    """Squared cosLat-corrected angular distance (deg²) between two
    (lat, lng) points — cheap nearest-neighbour metric, no projection."""
    dlat = p[0] - q[0]
    dlng = (p[1] - q[1]) * math.cos(math.radians((p[0] + q[0]) / 2))
    return dlat * dlat + dlng * dlng


def _climate_normal_rainfall(
    lat: float, lng: float, max_km: Optional[float] = None
) -> Optional[dict]:
    """Return the nearest bundled Environment Canada climate-normal rainfall.

    Picks the closest of the bundled station centroids. When ``max_km`` is
    set and the nearest station is farther than that, the pin is considered
    outside coverage and ``None`` is returned so the caller can fall back to
    live data. Mirrors the soil-fallback pattern so the UI renders it with
    no special case.
    """
    import json as _json

    path = resource_path("data", "rainfall_fallback_alberta.json")
    try:
        with open(path, "r", encoding="utf-8") as f:
            entries = _json.load(f)
    except (OSError, ValueError):
        return None
    if not isinstance(entries, list) or not entries:
        return None

    best = min(
        entries,
        key=lambda e: _dist2((lat, lng), tuple(e.get("centroid") or (0, 0))),
    )
    # deg → km via the latitude scale (~111 km per degree).
    dist_km = math.sqrt(_dist2((lat, lng), tuple(best.get("centroid") or (0, 0)))) * 111.0
    if max_km is not None and dist_km > max_km:
        return None

    monthly = best.get("monthly_mm") or []
    if len(monthly) != 12:
        return None
    region = best.get("region", "nearest station")
    source = f"Environment Canada 1981–2010 normal — {region}"
    if dist_km > _NORMAL_LOCAL_KM:
        source += " (nearest station)"
    result = {
        "annual_mm":   round(float(best.get("annual_mm") or sum(monthly)), 1),
        "monthly_mm":  [round(float(m), 1) for m in monthly],
        "years_used":  30,
        "source":      source,
    }
    # The bundled normal carries total precipitation only — add an honest,
    # clearly-flagged rain/snow split from the prairie snow-fraction climatology.
    from src import precip_split
    return precip_split.add_estimated_split(result)


def _parse_rainfall(data: dict) -> Optional[dict]:
    daily = data["daily"]
    times = daily.get("time") or []
    sums  = daily.get("precipitation_sum") or []
    if not times or len(times) != len(sums):
        return None
    # Optional measured rain series (rain_sum, mm). When present and aligned it
    # gives a real split (snow water-equivalent = total − rain); otherwise we
    # fall back to the estimated prairie-climatology split below.
    rains = daily.get("rain_sum") or []
    have_split = len(rains) == len(times)

    monthly = [0.0] * 12
    monthly_rain = [0.0] * 12
    annuals: dict[int, float] = {}
    for i, (t, p) in enumerate(zip(times, sums)):
        if p is None:
            continue
        year  = int(t[:4])
        month = int(t[5:7])
        annuals[year] = annuals.get(year, 0.0) + p
        monthly[month - 1] += p
        if have_split:
            r = rains[i]
            monthly_rain[month - 1] += r if r is not None else 0.0
    n_years = len(annuals) or 1
    monthly_mean = [round(monthly[i] / n_years, 1) for i in range(12)]
    annual_mean  = round(sum(annuals.values()) / n_years, 1)
    result = {
        "annual_mm":   annual_mean,
        "monthly_mm":  monthly_mean,
        "years_used":  n_years,
        "source":      "Open-Meteo / ERA5-Land",
    }

    from src import precip_split
    if have_split:
        rain_mean = [round(monthly_rain[i] / n_years, 1) for i in range(12)]
        # Snow water-equivalent = total − rain (clamped ≥ 0), so rain + snow
        # always reconcile to the precipitation total.
        snow_mm = [max(0.0, round(monthly_mean[i] - rain_mean[i], 1))
                   for i in range(12)]
        return precip_split.add_measured_split(
            result, rain_mean, snow_mm,
            source="Open-Meteo ERA5-Land (measured rain/snow)")
    # No measured series — estimate the split from the prairie climatology.
    return precip_split.add_estimated_split(result)


# ── Soil ────────────────────────────────────────────────────────────────────

def fetch_soil(lat: float, lng: float) -> Optional[dict]:
    """
    Soil pH, sand/silt/clay %, and reported depth.

    Source order: the offline **Gridded Soil Landscapes of Canada** pack when
    downloaded (real per-location data, no network — see ``src/soil_grid.py``),
    then SoilGrids v2.0 (ISRIC) as an opportunistic online bonus, then a curated
    Alberta regional approximation bundled with the app (see
    ``data/soil_fallback_alberta.json``). The returned dict's ``source`` field
    always reflects which path was used so the UI can label it appropriately.

    Top-layer values are surfaced in ``summary``; per-depth values are
    kept in ``properties`` for callers that want the full profile.
    """
    # 1. Offline pack (Gridded SLC) — instant, real, no network.
    try:
        from src.soil_grid import sample_soil
        local = sample_soil(lat, lng)
    except Exception:  # noqa: BLE001 — pack/rasterio issues → try the next source
        local = None
    if local is not None:
        return local

    # 2. SoilGrids v2.0 (online; ISRIC has paused the service, so often skipped).
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

    path = resource_path("data", "soil_fallback_alberta.json")
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
    api_result = None
    if data and "elevation" in data:
        api_result = _parse_elevation(data["elevation"], sample_m)
    if api_result is not None and api_result.get("slope_pct") is not None:
        # Full success from Open-Meteo — no need to consult the
        # offline pack.
        return api_result

    # V1.37: when Open-Meteo gives us no centre (returns None or null at
    # centre) or only a centre with no slope, try the local Edmonton
    # 0.5 m LiDAR pack. It's higher-resolution AND fills in
    # river-valley pins where the Copernicus DEM has nulls.
    try:
        from src.terrain import lookup_point_elevation_edmonton
        offline = lookup_point_elevation_edmonton(lat, lng, sample_m=sample_m)
    except Exception:
        offline = None
    if offline is not None and offline.get("slope_pct") is not None:
        return offline
    # Fall back to whatever the API gave us (even if it's centre-only)
    # so the user still sees an elevation reading in the at-pin row.
    return api_result if api_result is not None else offline


def _slope_sample_points(lat: float, lng: float, m: float):
    """[centre, N, E, S, W] in degrees, offset by ``m`` metres."""
    dlat = m / M_PER_DEG_LAT
    cos_lat = math.cos(math.radians(lat))
    if abs(cos_lat) < 1e-9:
        cos_lat = 1e-9
    dlng = m / (M_PER_DEG_LAT * cos_lat)
    return [
        (lat,        lng),
        (lat + dlat, lng),
        (lat,        lng + dlng),
        (lat - dlat, lng),
        (lat,        lng - dlng),
    ]


def _parse_elevation(elev: list, sample_m: float) -> Optional[dict]:
    """V1.37: degrades gracefully when some of the 5 sample points are
    null. Pins on water (where the DEM has no value) used to fail the
    whole readout — now we return whatever we can:

      * Centre null → return None (no useful info).
      * Centre present, all 4 neighbours null → return elevation only;
        slope/aspect show as "—" instead of breaking the row.
      * Centre present, some neighbours null → use only the axes
        where both neighbours are present (e.g. N+S but not E+W).

    The "at-pin" elevation source is Copernicus DEM 30 m, which omits
    water surfaces; the river-pin case the user hit in V1.36 testing
    was the canonical failure mode."""
    if not elev or len(elev) < 1 or elev[0] is None:
        return None
    centre = elev[0]
    # Pad to 5 samples so the unpacking below is safe regardless of
    # how many neighbours the DEM returned.
    padded = list(elev[:5]) + [None] * max(0, 5 - len(elev[:5]))
    _, n, e, s, w = padded

    have_ns = n is not None and s is not None
    have_ew = e is not None and w is not None
    dz_dy = (n - s) / (2.0 * sample_m) if have_ns else 0.0   # +y = north
    dz_dx = (e - w) / (2.0 * sample_m) if have_ew else 0.0   # +x = east

    if not have_ns and not have_ew:
        # Centre only — no gradient available.
        return {
            "elevation_m": round(centre, 1),
            "slope_pct":   None,
            "slope_deg":   None,
            "aspect_deg":  None,
            "aspect":      "—",
            "sample_m":    sample_m,
            "source":      "Copernicus DEM 30m (via Open-Meteo, "
                           "neighbours over water — slope unavailable)",
        }

    grad      = math.hypot(dz_dx, dz_dy)
    slope_pct = round(grad * 100.0, 2)
    slope_deg = round(math.degrees(math.atan(grad)), 2)

    if slope_pct < 0.05:
        aspect_deg, aspect = None, "Flat"
    else:
        ang = math.degrees(math.atan2(-dz_dx, -dz_dy))
        ang = (ang + 360.0) % 360.0
        aspect_deg = round(ang, 1)
        aspect     = _compass_label(ang)

    src_note = ""
    if not (have_ns and have_ew):
        src_note = " (partial — only one axis sampled, neighbours over water)"
    return {
        "elevation_m": round(centre, 1),
        "slope_pct":   slope_pct,
        "slope_deg":   slope_deg,
        "aspect_deg":  aspect_deg,
        "aspect":      aspect,
        "sample_m":    sample_m,
        "source":      "Copernicus DEM 30m (via Open-Meteo)" + src_note,
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


# ── Climate (V1.35) ─────────────────────────────────────────────────────────

def fetch_climate(lat: float, lng: float) -> Optional[dict]:
    """Thin shim around ``src.climate.get_climate_summary`` so the site
    panel's existing ``_SiteFetchWorker`` pattern can pick it up the
    same way as rainfall / soil / elevation / hardiness. Returns the
    climate-summary dict or ``None``."""
    from src.climate import get_climate_summary
    return get_climate_summary(lat, lng)


# ── Ecoregion (V1.36) ───────────────────────────────────────────────────────

def fetch_ecoregion(lat: float, lng: float) -> Optional[dict]:
    """Look up the AB ecoregion for (lat, lng) via point-in-polygon.
    Returns ``{"key": "aspen_parkland", "label": "Aspen Parkland (central AB)",
    "source": "..."}`` or ``None`` if the point falls outside every
    shipped polygon.

    Synchronous and local (no network) — runs instantly. Plugged into
    the site panel's existing worker-step list for shape-uniformity
    with the other fetchers, not because it needs the background thread."""
    from src.ecoregion import lookup_ecoregion, label_for_key
    key = lookup_ecoregion(lat, lng)
    if not key:
        return None
    return {
        "key":    key,
        "label":  label_for_key(key),
        "source": "ecoregions_canada.geojson (auto)",
    }


# ── Aggregator ──────────────────────────────────────────────────────────────

def fetch_all(lat: float, lng: float) -> dict:
    """Fetch all six datasets sequentially. Caller may want a thread."""
    return {
        "lat":       lat,
        "lng":       lng,
        "rainfall":  fetch_rainfall(lat, lng),
        "soil":      fetch_soil(lat, lng),
        "elevation": fetch_elevation(lat, lng),
        "hardiness": fetch_hardiness(lat, lng),
        "climate":   fetch_climate(lat, lng),
        "ecoregion": fetch_ecoregion(lat, lng),
    }

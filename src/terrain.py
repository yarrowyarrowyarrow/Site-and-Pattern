"""
terrain.py — Auto-generate slope contour lines and slope-ramp overlays.

Two data paths, picked per location:

    Edmonton (urban LiDAR)
        Contour Lines LL - WGS84 — the underlying *tabular dataset*,
        Socrata id n6cj-24tp, 0.5 m interval. Pre-baked vector
        contours in lat/lng so they map cleanly to Leaflet; we just
        clip + filter by interval. The IDs that show up in the
        Edmonton portal's URL bar (4hu9-9vq3, 2aq6-x42w) are *map
        views* — visualisations whose .geojson endpoint always
        returns one stub feature with `geometry:null` and
        `properties:{}`. Use the catalog API
        (`/api/catalog/v1?only=dataset&q=contour`) to discover the
        actual data-bearing assets if Edmonton ever republishes.
        https://data.edmonton.ca/dataset/Contour-Lines-LL-WGS84/n6cj-24tp

    Anywhere else
        Open-Meteo elevation API (Copernicus DEM 30 m), sampled on a regular
        grid; contours generated via marching squares.

The slope-ramp overlay is always derived from a regular elevation grid (a
fresh Open-Meteo sample, even inside Edmonton), rendered to RGBA bytes that
the main thread wraps in a QImage / PNG for a Leaflet ImageOverlay.

All network calls use stdlib only and degrade gracefully — fetchers return
``None`` on any error so the UI can show "unavailable" rather than crashing.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import struct
import time
import urllib.parse
import urllib.request
import zlib
from typing import Iterable, Optional

from src.http_utils import http_get_json

# PyQt6 is optional at import time so the pure-Python helpers (and tests)
# can run in any environment. The TerrainWorker class is only defined when
# Qt is available.
try:
    from PyQt6.QtCore import QObject, pyqtSignal
    _HAVE_QT = True
except ImportError:
    _HAVE_QT = False


# ── Constants ───────────────────────────────────────────────────────────────

_TIMEOUT = 10.0

# Edmonton "Contour Lines 3TM" (0.5 m interval)
_EDM_DATASET_ID = "n6cj-24tp"   # "Contour Lines LL - WGS84" — the underlying dataset
                                # (sibling map view at 2aq6-x42w returns empty rows)
_EDM_RESOURCE = f"https://data.edmonton.ca/resource/{_EDM_DATASET_ID}.geojson"
_EDM_PAGE_SIZE = 1000
_EDM_MAX_FEATURES = 5000

# Open-Meteo accepts up to 100 coords per request.
_OPEN_METEO_BATCH = 100
_OPEN_METEO_INTERVAL = 0.30  # seconds between batches; the API throttles
                              # bursts under ~3-4 req/s on the free tier
_OPEN_METEO_RETRY_ATTEMPTS = 4

# Hard caps so a sloppy bbox can't lock the app up.
_MAX_GRID_CELLS = 10000      # ≤ 100 batched Open-Meteo requests; ~1 km at 10 m grid
_MIN_RESOLUTION_M = 5.0
_MAX_BBOX_M = 4000.0         # 4 km on a side — fits a sub-neighbourhood

# Elevation samples differing from their 3×3 neighbours' median by more
# than this are treated as DEM sentinel/canopy-bleed artifacts and replaced
# with the local median. 10 m of vertical noise on a 10 m horizontal grid
# would already imply 100 % slope, so anything beyond is almost always
# bogus over urban Alberta terrain.
_DESPIKE_THRESHOLD_M = 10.0

# Chaikin corner-cutting iterations applied to stitched contour polylines.
# Two iterations are enough to produce visibly organic curves without
# noticeably distorting the contour position.
_CHAIKIN_ITERATIONS = 2

# Edmonton bbox (loose) — used to pick the local data source.
_EDM_BBOX = (53.39, 53.71, -113.71, -113.27)  # (south, north, west, east)

# Slope ramp bins (% slope) → RGBA. Habitat-design friendly: green flat,
# yellow/orange gentle, red steep, magenta hazardous.
_SLOPE_RAMP = (
    (2.0,   (102, 187, 106, 140)),   # < 2%   flat → mid green
    (5.0,   (174, 213, 129, 140)),   # 2–5%   gentle → light green
    (10.0,  (255, 235, 59,  150)),   # 5–10%  moderate → yellow
    (20.0,  (255, 152, 0,   170)),   # 10–20% strong → orange
    (33.0,  (244, 67,  54,  185)),   # 20–33% steep → red
    (1e9,   (170, 0,   140, 200)),   # > 33%  hazardous → magenta
)


# ── HTTP helper ─────────────────────────────────────────────────────────────

def _http_get_json(url: str, timeout: float = _TIMEOUT) -> Optional[dict]:
    """Module-local alias for :func:`src.http_utils.http_get_json`, kept so
    tests can monkeypatch ``terrain._http_get_json``."""
    return http_get_json(url, timeout=timeout)


def _http_get_json_retry(url: str, attempts: int = _OPEN_METEO_RETRY_ATTEMPTS,
                         timeout: float = _TIMEOUT) -> Optional[dict]:
    """
    Like ``_http_get_json`` but retries transient failures with exponential
    backoff (0.5 s, 1.0 s, 2.0 s, …). Open-Meteo occasionally drops a
    request under load; without retry, one 500/timeout in a 100-batch grid
    sample fails a meaningful fraction of cells.
    """
    delay = 0.5
    for i in range(attempts):
        result = _http_get_json(url, timeout=timeout)
        if result is not None:
            return result
        if i < attempts - 1:
            time.sleep(delay)
            delay *= 2.0
    return None


# ── Bbox / projection helpers ───────────────────────────────────────────────

def metres_per_deg(lat: float) -> tuple[float, float]:
    """Approx (m_per_deg_lat, m_per_deg_lng) at this latitude.

    Delegates to src.projection (Chunk 8) so the cosLat ↔ UTM choice is
    made in one place. The default backend is coslat, which returns the
    exact legacy tuple, so terrain/bbox maths is unchanged unless a
    project opts into UTM.
    """
    from src.projection import metres_per_deg as _mpd
    return _mpd(lat)


def bbox_size_m(bbox: dict) -> tuple[float, float]:
    """Return (width_m, height_m) for a bbox dict {south, north, west, east}."""
    mid_lat = 0.5 * (bbox["south"] + bbox["north"])
    mlat, mlng = metres_per_deg(mid_lat)
    height = abs(bbox["north"] - bbox["south"]) * mlat
    width  = abs(bbox["east"]  - bbox["west"])  * mlng
    return width, height


def bbox_in_edmonton(bbox: dict) -> bool:
    """True if the bbox centre falls within the Edmonton municipal envelope."""
    s, n, w, e = _EDM_BBOX
    cy = 0.5 * (bbox["south"] + bbox["north"])
    cx = 0.5 * (bbox["west"]  + bbox["east"])
    return s <= cy <= n and w <= cx <= e


def grid_dims(bbox: dict, resolution_m: float) -> tuple[int, int]:
    """Number of cells (cols, rows) for the bbox at this ground resolution."""
    width_m, height_m = bbox_size_m(bbox)
    cols = max(2, int(round(width_m  / resolution_m)) + 1)
    rows = max(2, int(round(height_m / resolution_m)) + 1)
    return cols, rows


def validate_bbox(bbox: dict, resolution_m: float) -> Optional[str]:
    """Return an error string if the bbox would be too costly, else None."""
    width_m, height_m = bbox_size_m(bbox)
    if width_m <= 0 or height_m <= 0:
        return "Empty area — drag a rectangle on the map."
    if max(width_m, height_m) > _MAX_BBOX_M:
        return (
            f"Area too large ({max(width_m, height_m):.0f} m on a side). "
            f"Zoom in or draw a smaller rectangle (max {_MAX_BBOX_M:.0f} m)."
        )
    if resolution_m < _MIN_RESOLUTION_M:
        return f"Resolution must be ≥ {_MIN_RESOLUTION_M:.0f} m."
    cols, rows = grid_dims(bbox, resolution_m)
    if cols * rows > _MAX_GRID_CELLS:
        # Suggest a resolution that just fits, so the user knows what to do.
        suggested = max(_MIN_RESOLUTION_M,
                        math.ceil(resolution_m * math.sqrt(
                            (cols * rows) / _MAX_GRID_CELLS)))
        return (
            f"Grid too dense ({cols}×{rows} = {cols*rows} samples; "
            f"max {_MAX_GRID_CELLS}). Try Slope grid ≥ {suggested:.0f} m, "
            f"or pick a smaller rectangle."
        )
    return None


# ── Disk cache ──────────────────────────────────────────────────────────────

def _cache_root() -> str:
    # Under the shared per-user data folder (V1.69-renamed PermaDesign →
    # Site & Pattern, with one-time migration) so this cache moves with the rest.
    from src import user_paths
    path = os.path.join(user_paths.user_data_dir(), "cache", "terrain")
    os.makedirs(path, exist_ok=True)
    return path


def _cache_key(*parts) -> str:
    raw = "|".join(repr(p) for p in parts).encode("utf-8")
    return hashlib.sha1(raw).hexdigest()[:16]


def _cache_path(key: str, ext: str) -> str:
    return os.path.join(_cache_root(), f"{key}.{ext}")


def _cache_load_json(key: str) -> Optional[dict]:
    p = _cache_path(key, "json")
    if not os.path.exists(p):
        return None
    try:
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _cache_save_json(key: str, data: dict) -> None:
    p = _cache_path(key, "json")
    try:
        with open(p, "w", encoding="utf-8") as f:
            json.dump(data, f)
    except Exception:
        pass


# ── Edmonton vector contour fetch ───────────────────────────────────────────

# ── Offline at-point elevation lookup (V1.37) ───────────────────────────────
#
# When Open-Meteo's elevation endpoint is unreachable or returns null
# at the property pin (e.g. river-valley pins where the Copernicus DEM
# has gaps over water), fall back to the City of Edmonton's downloaded
# 0.5 m LiDAR contours. This is local-only data, so it's both faster
# (no network) and more accurate (0.5 m vs 30 m resolution) — when the
# user has the offline pack.
#
# Result shape matches ``property_data._parse_elevation`` so the site
# panel slot doesn't need to special-case it.

def lookup_point_elevation_edmonton(
    lat: float, lng: float, sample_m: float = 60.0,
) -> Optional[dict]:
    """Interpolate point elevation from the offline Edmonton LiDAR
    contour dataset. Returns the same dict shape as
    ``property_data._parse_elevation`` (elevation + slope + aspect) so
    the site panel slot doesn't need to special-case it. Returns
    ``None`` when offline data isn't present or the point falls
    outside Edmonton's coverage."""
    try:
        from src.terrain_store import TerrainStore as _TerrainStore
        ts = _TerrainStore()
        if not ts.has_edmonton_data():
            return None
    except Exception:
        return None

    # Edmonton coverage envelope — fail fast on points clearly outside.
    if not (53.30 <= lat <= 53.75 and -113.75 <= lng <= -113.20):
        return None

    # Pull contours in a small bbox around the pin — ~200 m radius is
    # ample for IDW with the 0.5 m contour interval.
    radius_m = max(200.0, 4.0 * sample_m)
    mlat, mlng = metres_per_deg(lat)
    dlat = radius_m / mlat
    dlng = radius_m / mlng
    bbox = {
        "south": lat - dlat, "north": lat + dlat,
        "west":  lng - dlng, "east":  lng + dlng,
    }
    try:
        contours = ts.get_edmonton_contours(bbox, interval_m=0.5)
    except Exception:
        return None
    if not contours:
        return None

    # Flatten to (lat, lng, elev) vertex list.
    verts: list[tuple[float, float, float]] = []
    for feat in contours:
        elev = feat.get("elevation_m")
        if elev is None:
            continue
        for coord in feat.get("coords") or []:
            if len(coord) < 2:
                continue
            verts.append((coord[0], coord[1], float(elev)))
    if not verts:
        return None

    # IDW the centre + 4 cardinal neighbours, then derive slope/aspect
    # exactly like the Open-Meteo path so the result is interchangeable.
    def _idw(plat: float, plng: float) -> Optional[float]:
        sum_w = sum_we = 0.0
        # Tight floor on d² so a sample exactly on a vertex doesn't
        # blow up; ~0.25 m² matches the contour-vertex spacing.
        for vlat, vlng, ve in verts:
            dlat_m = (vlat - plat) * mlat
            dlng_m = (vlng - plng) * mlng
            d2 = max(dlat_m * dlat_m + dlng_m * dlng_m, 0.25)
            w = 1.0 / d2
            sum_w += w
            sum_we += w * ve
        return sum_we / sum_w if sum_w > 0 else None

    centre = _idw(lat, lng)
    if centre is None:
        return None

    # Sample N/E/S/W at sample_m offsets — same convention as
    # property_data._slope_sample_points.
    nlat = lat + sample_m / mlat
    slat = lat - sample_m / mlat
    elng = lng + sample_m / mlng
    wlng = lng - sample_m / mlng
    n = _idw(nlat, lng)
    s = _idw(slat, lng)
    e = _idw(lat,  elng)
    w = _idw(lat,  wlng)

    # All four neighbours come from the same contour cloud, so unlike
    # the Open-Meteo path none of them will be None individually —
    # but guard anyway.
    if n is None or s is None or e is None or w is None:
        return {
            "elevation_m": round(centre, 1),
            "slope_pct":   None, "slope_deg": None,
            "aspect_deg":  None, "aspect":   "—",
            "sample_m":    sample_m,
            "source":      "City of Edmonton — 0.5 m LiDAR (offline IDW, centre only)",
        }

    dz_dx = (e - w) / (2.0 * sample_m)
    dz_dy = (n - s) / (2.0 * sample_m)
    grad = math.hypot(dz_dx, dz_dy)
    slope_pct = round(grad * 100.0, 2)
    slope_deg = round(math.degrees(math.atan(grad)), 2)
    if slope_pct < 0.05:
        aspect_deg, aspect = None, "Flat"
    else:
        ang = (math.degrees(math.atan2(-dz_dx, -dz_dy)) + 360.0) % 360.0
        aspect_deg = round(ang, 1)
        # Reuse the compass_label helper via local import to avoid a
        # circular dependency (property_data already imports terrain).
        from src.property_data import _compass_label as _compass
        aspect = _compass(ang)
    return {
        "elevation_m": round(centre, 1),
        "slope_pct":   slope_pct,
        "slope_deg":   slope_deg,
        "aspect_deg":  aspect_deg,
        "aspect":      aspect,
        "sample_m":    sample_m,
        "source":      "City of Edmonton — 0.5 m LiDAR (offline IDW)",
    }


def fetch_edmonton_contours(bbox: dict, interval_m: float = 0.5) -> Optional[list[dict]]:
    """
    Fetch Edmonton 0.5 m contour lines intersecting ``bbox``.

    Returns a list of ``{coords: [[lat, lng], ...], elevation_m: float}`` —
    or ``None`` if the dataset can't be reached (caller falls back to
    Open-Meteo). Lines are filtered to multiples of ``interval_m`` so the
    user can request sparser overlays without redownloading.

    Uses Socrata's $where=intersects(...) on the geometry column. The
    elevation column name is detected by introspecting one feature, so the
    code keeps working if the City renames a field.
    """
    # Fast path: full offline dataset downloaded by user
    try:
        from src.terrain_store import TerrainStore as _TerrainStore
        _ts = _TerrainStore()
        if _ts.has_edmonton_data():
            return _ts.get_edmonton_contours(bbox, interval_m)
    except Exception:
        pass

    cache_key = _cache_key("edm", bbox, interval_m)
    cached = _cache_load_json(cache_key)
    if cached is not None:
        return cached.get("features") or []

    elev_field, geom_field = _edm_detect_fields()
    if not elev_field or not geom_field:
        return None

    # Socrata GeoJSON intersects() takes a polygon literal (lng lat pairs).
    s, n, w, e = bbox["south"], bbox["north"], bbox["west"], bbox["east"]
    poly_wkt = (
        f"'POLYGON(({w} {s}, {e} {s}, {e} {n}, {w} {n}, {w} {s}))'"
    )
    where = f"intersects({geom_field}, {poly_wkt})"
    select = f"{geom_field},{elev_field}"

    out: list[dict] = []
    offset = 0
    while True:
        qs = urllib.parse.urlencode({
            "$select": select,
            "$where":  where,
            "$limit":  _EDM_PAGE_SIZE,
            "$offset": offset,
        })
        page = _http_get_json(f"{_EDM_RESOURCE}?{qs}")
        if not page or "features" not in page:
            return None
        feats = page["features"]
        if not feats:
            break
        for f in feats:
            elev = _coerce_float((f.get("properties") or {}).get(elev_field))
            if elev is None:
                continue
            if interval_m > 0 and abs(round(elev / interval_m) * interval_m - elev) > 0.01:
                continue
            for line in _flatten_geojson_lines(f.get("geometry") or {}):
                # Socrata GeoJSON gives [lng, lat] tuples. Convert to [lat, lng].
                coords = [[c[1], c[0]] for c in line if len(c) >= 2]
                if len(coords) >= 2:
                    out.append({"coords": coords, "elevation_m": round(elev, 2)})
        if len(feats) < _EDM_PAGE_SIZE or len(out) >= _EDM_MAX_FEATURES:
            break
        offset += _EDM_PAGE_SIZE

    _cache_save_json(cache_key, {"features": out})
    return out


_EDM_ELEV_HINTS = (
    "elev", "elevation_m", "elev_m", "contour", "height", "value",
    "z_value", "_z", "altitude", "dem",
)
_EDM_GEOM_TYPES = ("multiline", "line", "geometry", "point", "polygon")


def _edm_detect_fields() -> tuple[Optional[str], Optional[str]]:
    """Return (elevation_field, geometry_field) for the dataset.

    Detection runs in three layers, fastest-first:

      1. Cache hit → use it.
      2. Socrata "view metadata" (`/api/views/<id>.json`) — authoritative
         column list with explicit data types. We pick the first column
         whose type is a known geometry type, plus a numeric column whose
         field name matches an elevation hint (or any numeric column as
         a last resort). This is the robust path: it doesn't depend on
         the .geojson endpoint returning a non-empty sample, which is
         what was throwing the "Could not detect field names" error in
         practice when the API briefly returned an empty page.
      3. Row-sniffing on `?$limit=1` (the legacy heuristic) — kept as a
         final fallback for the case where the metadata endpoint is
         blocked / proxied / behind auth.
    """
    cache_key = _cache_key("edm_fields_v5")  # bumped: dataset ID 2aq6-x42w (map view) → n6cj-24tp (dataset)
    cached = _cache_load_json(cache_key)
    if cached and cached.get("elev") and cached.get("geom"):
        return cached.get("elev"), cached.get("geom")

    elev_field, geom_field = _edm_detect_via_metadata()
    if not elev_field or not geom_field:
        elev_field2, geom_field2 = _edm_detect_via_sample()
        elev_field = elev_field or elev_field2
        geom_field = geom_field or geom_field2

    if elev_field and geom_field:
        _cache_save_json(cache_key, {"elev": elev_field, "geom": geom_field})
    return elev_field, geom_field


def _edm_detect_via_metadata() -> tuple[Optional[str], Optional[str]]:
    """Use the Socrata views API to pick fields by declared data type."""
    meta_url = f"https://data.edmonton.ca/api/views/{_EDM_DATASET_ID}.json"
    meta = _http_get_json(meta_url, timeout=_TIMEOUT)
    if not isinstance(meta, dict):
        return None, None
    cols = meta.get("columns") or []
    if not isinstance(cols, list):
        return None, None

    geom_field: Optional[str] = None
    elev_candidates: list[tuple[int, str]] = []  # (priority, field)

    for col in cols:
        fname = (col.get("fieldName") or "").strip()
        dtype = (col.get("dataTypeName") or "").strip().lower()
        if not fname:
            continue
        if geom_field is None and dtype in _EDM_GEOM_TYPES:
            geom_field = fname
            continue
        if dtype == "number":
            fl = fname.lower()
            for prio, hint in enumerate(_EDM_ELEV_HINTS):
                if hint in fl:
                    elev_candidates.append((prio, fname))
                    break
            else:
                # Generic numeric column → very low priority fallback.
                elev_candidates.append((len(_EDM_ELEV_HINTS) + 1, fname))

    elev_candidates.sort(key=lambda t: t[0])
    elev_field = elev_candidates[0][1] if elev_candidates else None
    return elev_field, geom_field


def _edm_detect_via_sample() -> tuple[Optional[str], Optional[str]]:
    """Legacy fallback: sniff a single feature off the .geojson endpoint."""
    sample = _http_get_json(f"{_EDM_RESOURCE}?$limit=1", timeout=_TIMEOUT)
    if not sample or "features" not in sample or not sample["features"]:
        return None, None
    props = (sample["features"][0].get("properties") or {})
    # Socrata's spatial column has been "the_geom" for years on this
    # dataset; the metadata path above is what we trust to disagree.
    geom_field = "the_geom"
    elev_field: Optional[str] = None
    for k, v in props.items():
        if any(h in k.lower() for h in _EDM_ELEV_HINTS):
            if _coerce_float(v) is not None:
                elev_field = k
                break
    if elev_field is None:
        for k, v in props.items():
            if _coerce_float(v) is not None:
                elev_field = k
                break
    return elev_field, geom_field


def _coerce_float(v) -> Optional[float]:
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _flatten_geojson_lines(geom: dict) -> Iterable[list]:
    """Yield each LineString's coordinate list from a (Multi)LineString geom."""
    t = geom.get("type")
    cs = geom.get("coordinates") or []
    if t == "LineString":
        yield cs
    elif t == "MultiLineString":
        for line in cs:
            yield line


# ── Open-Meteo grid sampling ────────────────────────────────────────────────

def fetch_openmeteo_grid(bbox: dict, resolution_m: float) -> Optional[dict]:
    """
    Sample the Copernicus DEM 30 m on a regular grid covering ``bbox``.

    Returns ``{grid: [[float, ...], ...], cols, rows, bbox, missing_pct}``
    with the grid laid out **north-to-south, west-to-east** (row 0 = north
    edge), or ``None`` if too many samples couldn't be obtained. A handful
    of dropped batches are tolerated — missing cells are median-imputed
    from the neighbours we did get, then the whole grid is despiked to
    suppress single-cell DEM artifacts.
    """
    cache_key = _cache_key("om_v3", bbox, resolution_m)

    # Fast path: SQLite store (survives cache-dir wipes)
    _srtm_store = None
    try:
        from src.terrain_store import TerrainStore as _TerrainStore
        _srtm_store = _TerrainStore()
        hit = _srtm_store.get_srtm_grid(cache_key)
        if hit is not None:
            return hit
    except Exception:
        _srtm_store = None

    cached = _cache_load_json(cache_key)
    if cached is not None:
        return cached

    cols, rows = grid_dims(bbox, resolution_m)
    points = _grid_points(bbox, cols, rows)

    elevations: list[Optional[float]] = []
    failed_batches = 0
    n_batches = 0
    for batch_start in range(0, len(points), _OPEN_METEO_BATCH):
        n_batches += 1
        batch = points[batch_start:batch_start + _OPEN_METEO_BATCH]
        lats = ",".join(f"{p[0]:.6f}" for p in batch)
        lngs = ",".join(f"{p[1]:.6f}" for p in batch)
        url = f"https://api.open-meteo.com/v1/elevation?latitude={lats}&longitude={lngs}"
        data = _http_get_json_retry(url)
        if not data or "elevation" not in data:
            # Don't fail the whole grid for one bad batch — fill with None
            # and median-impute below. Only give up if most batches drop.
            elevations.extend([None] * len(batch))
            failed_batches += 1
        else:
            elevations.extend(data["elevation"])
        if batch_start + _OPEN_METEO_BATCH < len(points):
            time.sleep(_OPEN_METEO_INTERVAL)

    if len(elevations) != cols * rows:
        return None

    valid = [v for v in elevations if v is not None]
    # Bail only if effectively no data came back. A single dropped batch
    # in 25 (= 4 % missing) is still a usable grid.
    if not valid or len(valid) < 0.5 * len(elevations):
        return None

    median = sorted(valid)[len(valid) // 2]
    elevations = [float(v) if v is not None else float(median) for v in elevations]
    missing_pct = round(100.0 * (1.0 - len(valid) / len(elevations)), 1)

    grid = [
        [elevations[r * cols + c] for c in range(cols)]
        for r in range(rows)
    ]
    grid = _despike(grid, _DESPIKE_THRESHOLD_M)
    # Gentle Gaussian blur tames cell-scale noise so marching squares
    # produces gradual, organic contour lines rather than the staircase
    # patterns you get from a raw 30 m DEM sampled on a 10 m grid.
    grid = _gaussian_smooth_3x3(grid)

    out = {"grid": grid, "cols": cols, "rows": rows, "bbox": bbox,
           "resolution_m": resolution_m,
           "missing_pct": missing_pct,
           "failed_batches": failed_batches,
           "n_batches": n_batches,
           "source": "Open-Meteo / Copernicus DEM 30m"}
    _cache_save_json(cache_key, out)
    try:
        if _srtm_store is not None:
            _srtm_store.store_srtm_grid(cache_key, out)
    except Exception:
        pass
    return out


def _despike(grid: list[list[float]],
             threshold_m: float) -> list[list[float]]:
    """
    Replace cells that differ from their 8-neighbour median by more than
    ``threshold_m``. Conservative: real terrain features (gradual slopes,
    natural cliffs up to a few metres per cell) pass through unchanged.

    Catches the DEM sentinel values and building-canopy spikes that
    otherwise produce visually-implausible 200%+ slopes on flat
    residential blocks.
    """
    if not grid or not grid[0]:
        return grid
    rows = len(grid)
    cols = len(grid[0])
    out = [row[:] for row in grid]
    for r in range(rows):
        for c in range(cols):
            window = []
            for dr in (-1, 0, 1):
                for dc in (-1, 0, 1):
                    if dr == 0 and dc == 0:
                        continue
                    rr, cc = r + dr, c + dc
                    if 0 <= rr < rows and 0 <= cc < cols:
                        window.append(grid[rr][cc])
            if len(window) < 4:
                continue        # corners/edges with too few neighbours
            window.sort()
            local_median = window[len(window) // 2]
            if abs(grid[r][c] - local_median) > threshold_m:
                out[r][c] = local_median
    return out


_GAUSSIAN_KERNEL_3X3 = ((1, 2, 1), (2, 4, 2), (1, 2, 1))


def _gaussian_smooth_3x3(grid: list[list[float]]) -> list[list[float]]:
    """
    3×3 Gaussian blur with the canonical [1 2 1; 2 4 2; 1 2 1] / 16 kernel.
    Edge cells use the available subset (effectively reflect-by-omission)
    so the bbox boundary doesn't get pulled toward zero.
    """
    if not grid or not grid[0]:
        return grid
    rows = len(grid)
    cols = len(grid[0])
    out = [row[:] for row in grid]
    for r in range(rows):
        for c in range(cols):
            total = 0.0
            weight_sum = 0
            for dr in (-1, 0, 1):
                for dc in (-1, 0, 1):
                    rr, cc = r + dr, c + dc
                    if 0 <= rr < rows and 0 <= cc < cols:
                        w = _GAUSSIAN_KERNEL_3X3[dr + 1][dc + 1]
                        total += grid[rr][cc] * w
                        weight_sum += w
            if weight_sum:
                out[r][c] = total / weight_sum
    return out


def _grid_points(bbox: dict, cols: int, rows: int) -> list[tuple[float, float]]:
    """Row-major (north-to-south × west-to-east) grid of (lat, lng)."""
    pts = []
    for r in range(rows):
        # Row 0 sits on the *north* edge.
        t = r / max(1, rows - 1)
        lat = bbox["north"] - t * (bbox["north"] - bbox["south"])
        for c in range(cols):
            u = c / max(1, cols - 1)
            lng = bbox["west"] + u * (bbox["east"] - bbox["west"])
            pts.append((lat, lng))
    return pts


# ── Marching squares (isoline generation) ───────────────────────────────────

def marching_squares(grid: list[list[float]], levels: list[float],
                     bbox: dict) -> list[dict]:
    """
    Extract iso-elevation polylines from a regular grid.

    For each level we walk every grid cell, classify the four corners as
    above/below the level, and emit zero, one, or two short line segments
    via the standard 16-case lookup. Segments are returned unstitched —
    fast to render in Leaflet, simple to test.
    """
    if not grid or not grid[0] or not levels:
        return []
    rows = len(grid)
    cols = len(grid[0])

    def lat_at(r: float) -> float:
        t = r / max(1, rows - 1)
        return bbox["north"] - t * (bbox["north"] - bbox["south"])

    def lng_at(c: float) -> float:
        u = c / max(1, cols - 1)
        return bbox["west"] + u * (bbox["east"] - bbox["west"])

    out: list[dict] = []
    for level in levels:
        segments: list[list[list[float]]] = []
        for r in range(rows - 1):
            for c in range(cols - 1):
                tl = grid[r][c]
                tr = grid[r][c + 1]
                br = grid[r + 1][c + 1]
                bl = grid[r + 1][c]

                idx = (
                    (8 if tl >= level else 0) |
                    (4 if tr >= level else 0) |
                    (2 if br >= level else 0) |
                    (1 if bl >= level else 0)
                )
                if idx == 0 or idx == 15:
                    continue

                # Edge midpoint locations in (row_frac, col_frac).
                #   T = top edge    (between TL, TR)
                #   R = right edge  (between TR, BR)
                #   B = bottom edge (between BR, BL)
                #   L = left edge   (between BL, TL)
                def interp(a: float, b: float) -> float:
                    if abs(b - a) < 1e-12:
                        return 0.5
                    return (level - a) / (b - a)

                T = (r, c + interp(tl, tr))
                R = (r + interp(tr, br), c + 1)
                B = (r + 1, c + interp(bl, br))
                L = (r + interp(tl, bl), c)

                pairs = _MS_CASES.get(idx, ())
                for a, b in pairs:
                    pa = {"T": T, "R": R, "B": B, "L": L}[a]
                    pb = {"T": T, "R": R, "B": B, "L": L}[b]
                    seg = [
                        [lat_at(pa[0]), lng_at(pa[1])],
                        [lat_at(pb[0]), lng_at(pb[1])],
                    ]
                    segments.append(seg)

        if segments:
            # Stitch cell-aligned 2-point segments into continuous polylines
            # (so a contour that crosses 30 cells becomes 1 line, not 30
            # disconnected ones). Then apply Chaikin corner-cutting for the
            # organic curves the user expects from a real contour map.
            stitched = _stitch_segments(segments)
            smoothed = [_chaikin(line, _CHAIKIN_ITERATIONS) for line in stitched]
            out.append({"elevation_m": round(level, 2),
                        "segments": smoothed})
    return out


def _stitch_segments(segments: list[list[list[float]]]) -> list[list[list[float]]]:
    """
    Join 2-point segments whose endpoints coincide into longer polylines.

    Marching squares emits one or two short segments per grid cell; adjacent
    cells share edge crossings so neighbouring segments meet exactly at a
    common point. Walking the start→end / end→start chains turns the bag
    of segments into the polylines a human would draw.
    """
    if not segments:
        return []

    def key(p):
        # Endpoints from a single grid agree to floating-point exactness,
        # but we round defensively in case of identical-up-to-the-last-bit.
        return (round(p[0], 9), round(p[1], 9))

    by_start: dict = {}
    by_end:   dict = {}
    for i, seg in enumerate(segments):
        by_start.setdefault(key(seg[0]),  []).append(i)
        by_end.setdefault(  key(seg[-1]), []).append(i)

    used = [False] * len(segments)
    polylines: list[list[list[float]]] = []

    for i, seg in enumerate(segments):
        if used[i]:
            continue
        used[i] = True
        line = [list(seg[0]), list(seg[-1])]

        # Extend forward: seg ending at our tail.
        while True:
            k = key(line[-1])
            nxt = next((j for j in by_start.get(k, []) if not used[j]), None)
            if nxt is None:
                break
            used[nxt] = True
            line.append(list(segments[nxt][-1]))

        # Extend backward: seg starting at our head.
        while True:
            k = key(line[0])
            nxt = next((j for j in by_end.get(k, []) if not used[j]), None)
            if nxt is None:
                break
            used[nxt] = True
            line.insert(0, list(segments[nxt][0]))

        polylines.append(line)
    return polylines


def _chaikin(line: list[list[float]], iterations: int) -> list[list[float]]:
    """
    Chaikin corner-cutting: each iteration replaces every interior point
    with two points 1/4 and 3/4 of the way along its neighbouring edges,
    yielding smoother polylines that converge to a B-spline. Endpoints of
    open lines are preserved; closed loops are detected by start==end and
    treated as a closed curve so the seam doesn't develop a corner.
    """
    if iterations <= 0 or not line or len(line) < 3:
        return line

    pts = [list(p) for p in line]
    closed = (
        len(pts) >= 3
        and abs(pts[0][0] - pts[-1][0]) < 1e-9
        and abs(pts[0][1] - pts[-1][1]) < 1e-9
    )

    for _ in range(iterations):
        if closed:
            new = []
            for i in range(len(pts) - 1):
                a = pts[i]
                b = pts[i + 1]
                q = [a[0] + 0.25 * (b[0] - a[0]), a[1] + 0.25 * (b[1] - a[1])]
                r = [a[0] + 0.75 * (b[0] - a[0]), a[1] + 0.75 * (b[1] - a[1])]
                new.append(q)
                new.append(r)
            new.append(new[0])   # re-close
            pts = new
        else:
            new = [pts[0]]
            for i in range(len(pts) - 1):
                a = pts[i]
                b = pts[i + 1]
                q = [a[0] + 0.25 * (b[0] - a[0]), a[1] + 0.25 * (b[1] - a[1])]
                r = [a[0] + 0.75 * (b[0] - a[0]), a[1] + 0.75 * (b[1] - a[1])]
                new.append(q)
                new.append(r)
            new.append(pts[-1])
            pts = new

    return pts


# Standard marching-squares case table. Bits: TL=8, TR=4, BR=2, BL=1.
# Saddle cases (5, 10) are split arbitrarily — fine for visual contours.
_MS_CASES = {
    1:  (("L", "B"),),
    2:  (("B", "R"),),
    3:  (("L", "R"),),
    4:  (("T", "R"),),
    5:  (("L", "T"), ("B", "R")),
    6:  (("T", "B"),),
    7:  (("L", "T"),),
    8:  (("L", "T"),),
    9:  (("T", "B"),),
    10: (("L", "B"), ("T", "R")),
    11: (("T", "R"),),
    12: (("L", "R"),),
    13: (("B", "R"),),
    14: (("L", "B"),),
}


# ── Slope grid (central differences) ────────────────────────────────────────

def _grid_from_contours(contours: list[dict], bbox: dict,
                         resolution_m: float) -> Optional[dict]:
    """Interpolate Edmonton LiDAR contour vertices onto a regular elevation
    grid for the existing compute_slope_grid pipeline.

    Avoids the Open-Meteo round-trip + 30 m grid downsample when the user
    already has the much finer LiDAR data cached locally. Inverse-distance
    weighted blend over vertices in the cell's 3x3 bucket neighbourhood —
    contours at 0.5 m sampling are dense enough that this gives a smooth
    field at typical 5-15 m output resolution. Returns None when contours
    are too sparse to interpolate (caller falls back to Open-Meteo).
    """
    verts: list[tuple[float, float, float]] = []
    for c in contours:
        e = c.get("elevation_m")
        if e is None:
            continue
        # generate_terrain reshapes raw {coords} into {segments: [coords]} —
        # accept either shape so callers can pass either form.
        if "segments" in c:
            for seg in c["segments"]:
                for ll in seg:
                    if len(ll) >= 2:
                        verts.append((ll[0], ll[1], e))
        else:
            for ll in c.get("coords", []):
                if len(ll) >= 2:
                    verts.append((ll[0], ll[1], e))
    if len(verts) < 100:
        return None

    # Cap output dimensions so a city-scale bbox can't explode the work.
    MAX_DIM = 512
    cols, rows = grid_dims(bbox, resolution_m)
    if cols > MAX_DIM or rows > MAX_DIM:
        width_m, height_m = bbox_size_m(bbox)
        new_res = max(width_m / (MAX_DIM - 1), height_m / (MAX_DIM - 1))
        cols, rows = grid_dims(bbox, new_res)

    width_m, height_m = bbox_size_m(bbox)
    dx_m = width_m  / max(1, cols - 1)
    dy_m = height_m / max(1, rows - 1)
    bucket_m = max(dx_m, dy_m) * 4.0  # vertices ~within a 4-cell radius

    mid_lat = 0.5 * (bbox["south"] + bbox["north"])
    m_per_deg_lat, m_per_deg_lng = metres_per_deg(mid_lat)
    deg_per_m_lat = 1.0 / m_per_deg_lat
    deg_per_m_lng = 1.0 / m_per_deg_lng
    buck_lat = bucket_m * deg_per_m_lat
    buck_lng = bucket_m * deg_per_m_lng

    south, north = bbox["south"], bbox["north"]
    west,  east  = bbox["west"],  bbox["east"]

    buckets: dict[tuple[int, int], list[tuple[float, float, float]]] = {}
    for vlat, vlng, ve in verts:
        bi = int((vlat - south) / buck_lat)
        bj = int((vlng - west)  / buck_lng)
        buckets.setdefault((bi, bj), []).append((vlat, vlng, ve))

    fallback_mean = sum(v[2] for v in verts) / len(verts)
    grid = [[fallback_mean] * cols for _ in range(rows)]

    for r in range(rows):
        lat = north - (north - south) * r / max(1, rows - 1)
        bi = int((lat - south) / buck_lat)
        for c in range(cols):
            lng = west + (east - west) * c / max(1, cols - 1)
            bj = int((lng - west) / buck_lng)

            sum_w = 0.0
            sum_we = 0.0
            for dbi in (-1, 0, 1):
                for dbj in (-1, 0, 1):
                    bv = buckets.get((bi + dbi, bj + dbj))
                    if not bv:
                        continue
                    for vlat, vlng, ve in bv:
                        dlat_m = (vlat - lat) * m_per_deg_lat
                        dlng_m = (vlng - lng) * m_per_deg_lng
                        # Floor d² so a cell landing on a vertex doesn't
                        # blow up the weight — half the contour-vertex
                        # spacing (~0.25 m²) is small enough to dominate
                        # but finite.
                        d2 = max(dlat_m * dlat_m + dlng_m * dlng_m, 0.25)
                        w = 1.0 / d2
                        sum_w += w
                        sum_we += w * ve
            if sum_w > 0:
                grid[r][c] = sum_we / sum_w

    return {
        "grid": grid,
        "rows": rows,
        "cols": cols,
        "bbox": bbox,
        "source": "City of Edmonton LiDAR contours",
        "missing_pct": 0.0,
    }


def compute_slope_grid(elev: dict) -> list[list[float]]:
    """
    Slope (%) at each cell of an elevation grid (forward/back diffs at
    the edges, centred elsewhere). The slope is the magnitude of the
    horizontal gradient, in *percent rise over run*.
    """
    grid = elev["grid"]
    rows = elev["rows"]
    cols = elev["cols"]
    bbox = elev["bbox"]
    width_m, height_m = bbox_size_m(bbox)
    dx = width_m  / max(1, cols - 1)
    dy = height_m / max(1, rows - 1)

    out = [[0.0] * cols for _ in range(rows)]
    for r in range(rows):
        rN = max(0, r - 1)
        rS = min(rows - 1, r + 1)
        span_y = (rS - rN) * dy
        if span_y == 0:
            span_y = dy
        for c in range(cols):
            cW = max(0, c - 1)
            cE = min(cols - 1, c + 1)
            span_x = (cE - cW) * dx
            if span_x == 0:
                span_x = dx
            dz_dx = (grid[r][cE] - grid[r][cW]) / span_x
            dz_dy = (grid[rN][c] - grid[rS][c]) / span_y
            out[r][c] = round(math.hypot(dz_dx, dz_dy) * 100.0, 3)
    return out


# ── Aspect (compass direction the slope faces) ──────────────────────────────
#
# Aspect is the second microclimate driver after slope. A south-facing
# slope in Alberta gets 30–40% more growing-season solar energy than a
# north-facing one at the same address — functionally a hardiness zone
# warmer. The single-point aspect at the property pin is already
# computed in property_data.py:_parse_elevation; these helpers extend
# the same formula to the full grid so the slope-analysis job can
# report a dominant aspect for the chosen area.
#
# Convention: aspect is reported as a compass bearing in [0, 360) where
# 0/360 = N, 90 = E, 180 = S, 270 = W. A flat cell (slope < threshold)
# has no meaningful aspect and is excluded from the dominant-aspect
# tally rather than being assigned an arbitrary direction.

_ASPECT_COMPASS_8 = ("N", "NE", "E", "SE", "S", "SW", "W", "NW")


def compute_aspect_grid(elev: dict) -> list[list[float]]:
    """
    Aspect (compass degrees from north, clockwise) at each cell of an
    elevation grid. Uses the same gradient sampling as
    ``compute_slope_grid`` so the two grids align cell-for-cell. Flat
    cells (zero gradient) return ``-1.0`` as a sentinel; callers should
    filter on the matching slope grid rather than reading this value.
    """
    grid = elev["grid"]
    rows = elev["rows"]
    cols = elev["cols"]
    bbox = elev["bbox"]
    width_m, height_m = bbox_size_m(bbox)
    dx = width_m  / max(1, cols - 1)
    dy = height_m / max(1, rows - 1)

    out = [[0.0] * cols for _ in range(rows)]
    for r in range(rows):
        rN = max(0, r - 1)
        rS = min(rows - 1, r + 1)
        span_y = (rS - rN) * dy
        if span_y == 0:
            span_y = dy
        for c in range(cols):
            cW = max(0, c - 1)
            cE = min(cols - 1, c + 1)
            span_x = (cE - cW) * dx
            if span_x == 0:
                span_x = dx
            dz_dx = (grid[r][cE] - grid[r][cW]) / span_x
            dz_dy = (grid[rN][c] - grid[rS][c]) / span_y
            if dz_dx == 0 and dz_dy == 0:
                out[r][c] = -1.0
                continue
            # Downhill direction as compass bearing from north, clockwise.
            # Matches property_data._parse_elevation so the area readout
            # is consistent with the single-point readout.
            deg = math.degrees(math.atan2(-dz_dx, -dz_dy)) % 360.0
            out[r][c] = round(deg, 2)
    return out


def classify_aspect_8way(degrees: float) -> str:
    """
    Bucket a compass bearing into one of N/NE/E/SE/S/SW/W/NW. Returns
    ``"Flat"`` for the ``-1.0`` sentinel produced by
    ``compute_aspect_grid`` on zero-gradient cells.

    Buckets are 45° wide and centred on each cardinal/inter-cardinal
    direction (N spans 337.5–22.5, NE spans 22.5–67.5, etc.) — the
    standard convention used in QGIS, ArcGIS, and most ecology tooling.
    """
    if degrees < 0:
        return "Flat"
    # Shift so bucket 0 (N) is centred on 0°, then divide by 45°.
    idx = int(((degrees + 22.5) % 360.0) // 45.0)
    return _ASPECT_COMPASS_8[idx]


def dominant_aspect_for_grid(
    aspect_grid: list[list[float]],
    slope_grid: list[list[float]],
    slope_threshold_pct: float = 2.0,
) -> dict:
    """
    Compute the dominant compass aspect across an aspect grid, weighted
    by the matching slope grid so flat terrain doesn't dilute the answer.

    Returns ``{"dominant": "S", "share": 0.42, "counts": {...},
    "sampled_cells": N, "flat_cells": M}`` — ``share`` is the dominant
    bucket's fraction of sampled (non-flat) cells. Returns
    ``{"dominant": None, ...}`` when fewer than 4 cells meet the
    threshold (too small to be meaningful).
    """
    counts: dict[str, int] = {b: 0 for b in _ASPECT_COMPASS_8}
    sampled = 0
    flat = 0
    for r, row in enumerate(aspect_grid):
        for c, deg in enumerate(row):
            if deg < 0 or slope_grid[r][c] < slope_threshold_pct:
                flat += 1
                continue
            counts[classify_aspect_8way(deg)] += 1
            sampled += 1
    if sampled < 4:
        return {
            "dominant": None,
            "share": 0.0,
            "counts": counts,
            "sampled_cells": sampled,
            "flat_cells": flat,
        }
    dominant = max(counts, key=lambda k: counts[k])
    return {
        "dominant": dominant,
        "share": round(counts[dominant] / sampled, 3),
        "counts": counts,
        "sampled_cells": sampled,
        "flat_cells": flat,
    }


# ── Slope ramp PNG ──────────────────────────────────────────────────────────

def slope_ramp_rgba(slope_grid: list[list[float]]) -> tuple[bytes, int, int]:
    """
    Convert a slope grid (% rise/run) to row-major top-to-bottom RGBA bytes.
    """
    h = len(slope_grid)
    w = len(slope_grid[0]) if h else 0
    out = bytearray(w * h * 4)
    for y, row in enumerate(slope_grid):
        for x, slope in enumerate(row):
            r, g, b, a = _slope_to_rgba(slope)
            i = (y * w + x) * 4
            out[i] = r
            out[i + 1] = g
            out[i + 2] = b
            out[i + 3] = a
    return bytes(out), w, h


def _slope_to_rgba(slope_pct: float) -> tuple[int, int, int, int]:
    for upper, rgba in _SLOPE_RAMP:
        if slope_pct < upper:
            return rgba
    return _SLOPE_RAMP[-1][1]


def encode_png_rgba(rgba: bytes, width: int, height: int) -> bytes:
    """
    Minimal PNG encoder for 8-bit RGBA. Produces IHDR + one IDAT + IEND
    so we don't need PIL or QImage in the worker thread. Filter byte 0
    (None) prepended to each scanline; zlib over the whole stream.
    """
    if width * height * 4 != len(rgba):
        raise ValueError("rgba buffer size doesn't match width*height*4")

    def chunk(tag: bytes, data: bytes) -> bytes:
        return (struct.pack(">I", len(data)) + tag + data
                + struct.pack(">I", zlib.crc32(tag + data) & 0xffffffff))

    sig = b"\x89PNG\r\n\x1a\n"
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)  # RGBA, no interlace

    raw = bytearray()
    stride = width * 4
    for y in range(height):
        raw.append(0)  # filter: None
        raw.extend(rgba[y * stride:(y + 1) * stride])
    idat = zlib.compress(bytes(raw), 9)

    return sig + chunk(b"IHDR", ihdr) + chunk(b"IDAT", idat) + chunk(b"IEND", b"")


# ── High-level orchestration ────────────────────────────────────────────────

def generate_terrain(bbox: dict, options: dict) -> dict:
    """
    Top-level entry called by TerrainWorker. Returns:

        {
          "ok": bool,
          "error": str | None,
          "source": str,          # human-readable provenance
          "contours": [           # list of {elevation_m, segments: [[[lat,lng],...]]}
              ...
          ],
          "slope_png_bytes": bytes | None,   # raw PNG, base64 in JS layer
          "slope_bbox": {south, north, west, east} | None,
          "stats": {min_elev, max_elev, max_slope_pct, ...},
        }

    ``options``: ``interval_m`` (default 0.5 in Edmonton, 1.0 elsewhere),
    ``resolution_m`` (default 5 in Edmonton, 15 elsewhere), ``want_contours``,
    ``want_slope_overlay``, ``force_source`` ("auto" | "edmonton" | "openmeteo").
    """
    err = validate_bbox(bbox, options.get("resolution_m") or _MIN_RESOLUTION_M)
    if err:
        return {"ok": False, "error": err, "contours": [], "slope_png_bytes": None}

    force = options.get("force_source", "auto")
    use_edm = (force == "edmonton") or (force == "auto" and bbox_in_edmonton(bbox))
    interval_m = float(options.get("interval_m") or (0.5 if use_edm else 1.0))
    resolution_m = float(options.get("resolution_m") or (5.0 if use_edm else 15.0))
    want_contours = options.get("want_contours", True)
    want_slope = options.get("want_slope_overlay", True)

    contours: list[dict] = []
    source = ""
    stats: dict = {}
    warnings: list[str] = []

    if want_contours and use_edm:
        edm = fetch_edmonton_contours(bbox, interval_m=interval_m)
        if edm is None:
            # Network/dataset error — fall through to Open-Meteo unless the
            # user explicitly forced the Edmonton path.
            if force == "edmonton":
                warnings.append("Edmonton contour dataset unreachable.")
        elif not edm:
            # Reached the dataset but nothing intersects the bbox — areas
            # outside city limits, river/ravine pockets without LiDAR,
            # etc. Fall back to Open-Meteo for marching-squares contours.
            pass
        else:
            contours = [
                {"elevation_m": f["elevation_m"],
                 "segments":   [f["coords"]]}
                for f in edm
            ]
            source = "City of Edmonton — Contour Lines 3TM (0.5 m LiDAR)"
            elevs = [c["elevation_m"] for c in contours]
            stats["min_elev"] = min(elevs)
            stats["max_elev"] = max(elevs)

    # The slope ramp always needs a regular elevation grid. Fallback
    # contours also need it when Edmonton didn't supply any.
    elev = None
    need_grid = want_slope or (want_contours and not contours)
    if need_grid:
        # Prefer the local LiDAR contours when available — much faster
        # than the Open-Meteo round-trip and finer than its 30 m grid.
        slope_contours = contours
        if use_edm and not slope_contours:
            # Slope was requested but contour output wasn't — still try the
            # local Edmonton fetch so the IDW path can run.
            edm = fetch_edmonton_contours(bbox, interval_m=interval_m)
            if edm:
                slope_contours = [
                    {"elevation_m": f["elevation_m"],
                     "segments":   [f["coords"]]}
                    for f in edm
                ]
        if slope_contours and use_edm:
            elev = _grid_from_contours(slope_contours, bbox, resolution_m)
            if elev is not None and not source:
                source = "City of Edmonton — LiDAR contours (IDW grid)"
        if elev is None:
            elev = fetch_openmeteo_grid(bbox, resolution_m)
            if elev is None:
                warnings.append(
                    "Open-Meteo elevation unreachable — try again, or pick a "
                    "smaller area."
                )
            else:
                missing = elev.get("missing_pct") or 0.0
                if missing > 5.0:
                    warnings.append(
                        f"{missing:.0f}% of elevation samples were dropped "
                        f"and median-imputed; results in those cells are "
                        f"approximate."
                    )

    if want_contours and not contours and elev is not None:
        levels = _levels_for_grid(elev["grid"], interval_m)
        contours = marching_squares(elev["grid"], levels, bbox)
        if not source:
            source = elev["source"]

    slope_png: Optional[bytes] = None
    if want_slope and elev is not None:
        slope_grid = compute_slope_grid(elev)
        rgba, w, h = slope_ramp_rgba(slope_grid)
        slope_png = encode_png_rgba(rgba, w, h)
        flat = [s for row in slope_grid for s in row]
        if flat:
            stats["max_slope_pct"] = round(max(flat), 2)
        # Aspect rides along on the same DEM — same gradient sample as
        # the slope grid, so it's effectively free. Surfaced via
        # `stats["dominant_aspect"]` in the area status readout.
        aspect_grid = compute_aspect_grid(elev)
        asp = dominant_aspect_for_grid(aspect_grid, slope_grid)
        if asp["dominant"]:
            stats["dominant_aspect"] = asp["dominant"]
            stats["dominant_aspect_share"] = asp["share"]
            stats["mean_slope_pct"] = round(sum(flat) / len(flat), 2)

    # Partial success counts: render whatever we have, surface warnings
    # in the panel. Only return error if every layer the user asked for
    # came up empty.
    asked_for_anything = want_contours or want_slope
    got_anything = bool(contours) or slope_png is not None
    if asked_for_anything and not got_anything:
        if warnings:
            err = " ".join(warnings)
        else:
            err = "Could not fetch elevation data. Check your internet connection."
        return {
            "ok": False, "error": err,
            "contours": [], "slope_png_bytes": None,
            "warnings": warnings,
        }

    return {
        "ok": True,
        "error": None,
        "source": source or "Unknown",
        "contours": contours,
        "slope_png_bytes": slope_png,
        "slope_bbox": bbox if slope_png else None,
        "stats": stats,
        "warnings": warnings,
        "interval_m": interval_m,
        "resolution_m": resolution_m,
    }


def _levels_for_grid(grid: list[list[float]], interval_m: float) -> list[float]:
    flat = [v for row in grid for v in row]
    if not flat:
        return []
    lo = math.floor(min(flat) / interval_m) * interval_m
    hi = math.ceil(max(flat)  / interval_m) * interval_m
    n = int(round((hi - lo) / interval_m)) + 1
    if n <= 0 or n > 200:        # absurd levels guard
        return []
    return [round(lo + i * interval_m, 4) for i in range(n)]


# ── Qt worker thread ────────────────────────────────────────────────────────

if _HAVE_QT:
    class TerrainWorker(QObject):
        """
        Run terrain generation off the UI thread.

            worker = TerrainWorker(bbox, options)
            worker.moveToThread(thread)
            worker.ready.connect(on_terrain_ready)
            worker.failed.connect(on_terrain_error)
            thread.started.connect(worker.run)
            thread.start()
        """

        ready    = pyqtSignal(dict)        # generate_terrain() result
        failed   = pyqtSignal(str)         # error message
        finished = pyqtSignal()

        def __init__(self, bbox: dict, options: dict, parent=None):
            super().__init__(parent)
            self._bbox = bbox
            self._options = options

        def run(self):
            try:
                result = generate_terrain(self._bbox, self._options)
            except Exception as exc:
                self.failed.emit(f"Terrain generation failed: {exc}")
                self.finished.emit()
                return
            if not result.get("ok"):
                self.failed.emit(result.get("error") or "Unknown error")
            else:
                self.ready.emit(result)
            self.finished.emit()

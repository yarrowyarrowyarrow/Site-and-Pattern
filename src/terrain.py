"""
terrain.py — Auto-generate slope contour lines and slope-ramp overlays.

Two data paths, picked per location:

    Edmonton (urban LiDAR)
        Contour Lines 3TM dataset (Socrata 4hu9-9vq3, 0.5 m interval).
        Pre-baked vector contours; we just clip + filter by interval.
        https://data.edmonton.ca/Elevation-Model/Contour-Lines-3TM/4hu9-9vq3

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
_USER_AGENT = "PermaDesign/1.0 (https://github.com/yarrowyarrowyarrow/permadesign)"

# Edmonton "Contour Lines 3TM" (0.5 m interval)
_EDM_DATASET_ID = "4hu9-9vq3"
_EDM_RESOURCE = f"https://data.edmonton.ca/resource/{_EDM_DATASET_ID}.geojson"
_EDM_PAGE_SIZE = 1000
_EDM_MAX_FEATURES = 5000

# Open-Meteo accepts up to 100 coords per request.
_OPEN_METEO_BATCH = 100
_OPEN_METEO_INTERVAL = 0.15  # seconds between batches, polite pacing

# Hard caps so a sloppy bbox can't lock the app up.
_MAX_GRID_CELLS = 2500       # 50 × 50 — ≤ 25 batched Open-Meteo requests
_MIN_RESOLUTION_M = 5.0
_MAX_BBOX_M = 2000.0         # 2 km on a side, keeps urban use cases comfortable

# Edmonton bbox (loose) — used to pick the local data source.
_EDM_BBOX = (53.39, 53.71, -113.71, -113.27)  # (south, north, west, east)

# Slope ramp bins (% slope) → RGBA. Permaculture-friendly: green flat,
# yellow/orange gentle, red steep, magenta hazardous.
_SLOPE_RAMP = (
    (2.0,   (102, 187, 106, 140)),   # < 2%   flat → mid green
    (5.0,   (174, 213, 129, 140)),   # 2–5%   gentle → light green
    (10.0,  (255, 235, 59,  150)),   # 5–10%  moderate → yellow
    (20.0,  (255, 152, 0,   170)),   # 10–20% strong → orange
    (33.0,  (244, 67,  54,  185)),   # 20–33% steep → red
    (1e9,   (170, 0,   140, 200)),   # > 33%  hazardous → magenta
)


# ── HTTP helper (mirrors property_data._http_get_json) ──────────────────────

def _http_get_json(url: str, timeout: float = _TIMEOUT) -> Optional[dict]:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception:
        return None


def _http_get_json_retry(url: str, attempts: int = 3,
                         timeout: float = _TIMEOUT) -> Optional[dict]:
    """
    Like ``_http_get_json`` but retries transient failures with exponential
    backoff (0.5 s, 1.0 s, 2.0 s, …). Open-Meteo occasionally drops a
    request under load; without retry, one 500/timeout in a 25-batch grid
    sample fails the whole generation.
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
    """Approx (m_per_deg_lat, m_per_deg_lng) at this latitude."""
    cos_lat = math.cos(math.radians(lat))
    if abs(cos_lat) < 1e-9:
        cos_lat = 1e-9
    return 111320.0, 111320.0 * cos_lat


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
        return (
            f"Grid too dense ({cols}×{rows} = {cols*rows} samples). "
            f"Increase resolution or pick a smaller area."
        )
    return None


# ── Disk cache ──────────────────────────────────────────────────────────────

def _cache_root() -> str:
    base = os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share")
    path = os.path.join(base, "PermaDesign", "cache", "terrain")
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


def _edm_detect_fields() -> tuple[Optional[str], Optional[str]]:
    """Return (elevation_field, geometry_field) for the dataset, by sniffing."""
    cache_key = _cache_key("edm_fields_v2")
    cached = _cache_load_json(cache_key)
    if cached:
        return cached.get("elev"), cached.get("geom")

    sample = _http_get_json(f"{_EDM_RESOURCE}?$limit=1")
    if not sample or "features" not in sample or not sample["features"]:
        return None, None
    feat = sample["features"][0]
    props = feat.get("properties") or {}

    # GeoJSON spec — geometry sits at "geometry"; the *underlying* Socrata
    # geometry column is whatever they named it. The .geojson endpoint
    # always serialises geometry under "geometry" but $select needs the
    # source column. Their default for spatial datasets is "the_geom"; if
    # missing we fall back to "*" for $select (won't include geom but lets
    # us still get properties) — though intersects() always needs the
    # column name. In practice the column has been "the_geom" for years.
    geom_field = "the_geom"

    elev_field = None
    for k, v in props.items():
        kl = k.lower()
        if any(t in kl for t in ("elev", "contour", "height", "z_value", "_z", "elevation_m")):
            if _coerce_float(v) is not None:
                elev_field = k
                break
    if elev_field is None:
        # Last-ditch: any numeric property.
        for k, v in props.items():
            if _coerce_float(v) is not None:
                elev_field = k
                break

    _cache_save_json(cache_key, {"elev": elev_field, "geom": geom_field})
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

    Returns ``{grid: [[float, ...], ...], cols, rows, bbox}`` with the grid
    laid out **north-to-south, west-to-east** (row 0 = north edge), or
    ``None`` on failure.
    """
    cache_key = _cache_key("om", bbox, resolution_m)
    cached = _cache_load_json(cache_key)
    if cached is not None:
        return cached

    cols, rows = grid_dims(bbox, resolution_m)
    points = _grid_points(bbox, cols, rows)

    elevations: list[Optional[float]] = []
    for batch_start in range(0, len(points), _OPEN_METEO_BATCH):
        batch = points[batch_start:batch_start + _OPEN_METEO_BATCH]
        lats = ",".join(f"{p[0]:.6f}" for p in batch)
        lngs = ",".join(f"{p[1]:.6f}" for p in batch)
        url = f"https://api.open-meteo.com/v1/elevation?latitude={lats}&longitude={lngs}"
        data = _http_get_json_retry(url)
        if not data or "elevation" not in data:
            return None
        elevations.extend(data["elevation"])
        if batch_start + _OPEN_METEO_BATCH < len(points):
            time.sleep(_OPEN_METEO_INTERVAL)

    if len(elevations) != cols * rows:
        return None
    if any(v is None for v in elevations):
        return None

    grid = [
        [float(elevations[r * cols + c]) for c in range(cols)]
        for r in range(rows)
    ]
    out = {"grid": grid, "cols": cols, "rows": rows, "bbox": bbox,
           "resolution_m": resolution_m, "source": "Open-Meteo / Copernicus DEM 30m"}
    _cache_save_json(cache_key, out)
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
            out.append({"elevation_m": round(level, 2),
                        "segments": segments})
    return out


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
        elev = fetch_openmeteo_grid(bbox, resolution_m)
        if elev is None:
            if want_slope:
                warnings.append("Slope ramp unavailable (Open-Meteo unreachable).")
            if want_contours and not contours:
                warnings.append("Contour fallback unavailable (Open-Meteo unreachable).")

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
        Run terrain generation off the UI thread. Mirrors the pattern in
        ``src/api/permapeople.py``.

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

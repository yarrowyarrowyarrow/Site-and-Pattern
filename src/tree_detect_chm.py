"""
tree_detect_chm.py — Individual-tree detection from a canopy-height map (V2.26).

Design principle P8 (repair starts from an honest inventory) and P9 (measured
values with a stated error, never false precision) — see docs/DESIGN_PHILOSOPHY.md.

The RGB-from-basemap detector (``src/tree_detect.py``) fought a losing battle:
the Esri basemap carries no near-infrared band (so "green" is a weak proxy for
vegetation) and serves inconsistent captures (date, sun angle, resolution), so
every field run surfaced a new false-positive mode. The whole industry avoids
this by working from **tree height**, not colour — the standard method is
*local-maxima on a Canopy Height Model (CHM)*: scan a window whose size grows
with height across a height raster; the tallest cell in each window is a
treetop, and the window scales because tall trees have wider crowns.

The blocker was always "you need LiDAR to get a CHM". No longer: **Meta + WRI
publish a free global 1 m canopy-height map** (``dataforgood-fb-data`` on AWS,
anonymous access, height-in-metres GeoTIFF tiles, mean abs error ≈ 2.8 m). This
module fetches the tile covering the property, reads the window over the drawn
boundary, and runs variable-window local-maxima on real heights — so a tree's
position, crown size and **height** are all measured, not inferred from pixels
or shadows. Location-independent; no per-photo tuning.

Architecture reuse:
  * The GeoTIFF read mirrors ``footprint_ndsm.read_ndsm_geotiff`` / the soil
    pack — ``rasterio`` (+ ``pyproj``) when present, graceful ``None`` otherwise.
    A canopy-height map *is* an nDSM restricted to vegetation.
  * Detected trees are emitted in the exact item shape ``tree_detect``/
    ``osm_features.add_features_to_project`` consume, so boundary clipping,
    dedupe and project insertion are reused unchanged.

Honesty contract (P9): heights are measured from the map and carry its ≈3 m
error; crown *radius* is a stated allometric estimate from height (the map
gives height well, per-crown width less so); foliage is left unknown (no
spectral data in a height map) = year-round shade, the app's honest default; a
failed/absent fetch returns ``None`` — reported as "couldn't get height data",
never as "no trees".

Public API:
  * ``detect_treetops(chm, gt, to_lnglat, *, min_height_m, …) -> list``  (pure)
  * ``detect_trees_chm(bbox, *, min_height_m, _reader=…) -> dict | None``
  * ``import_chm_result(res, project_dict, *, boundary, margin_m, area_note)``
"""

from __future__ import annotations

import math
import os
from typing import Callable, Optional

try:
    import numpy as np
    _HAVE_NUMPY = True
except ImportError:  # pragma: no cover
    _HAVE_NUMPY = False

# Meta/WRI High-Resolution Canopy Height (v1, global, 1 m). Anonymous S3 over
# HTTPS — no credentials. Tiles are quadkey-named GeoTIFFs; tiles.geojson maps
# quadkey → footprint polygon.
_CHM_BASE = ("https://dataforgood-fb-data.s3.amazonaws.com/"
             "forests/v1/alsgedi_global_v6_float")
_CHM_TILE_URL = _CHM_BASE + "/chm/{quadkey}.tif"
_CHM_INDEX_URL = _CHM_BASE + "/tiles.geojson"
_USER_AGENT = "PermaDesign/1.0 (https://github.com/yarrowyarrowyarrow/permadesign)"

# Detection tuning (all stated estimates; heights themselves are measured).
_MIN_TREE_HEIGHT_M = 3.0     # below this = shrub/hedge, not a shade-casting tree
# Open-grown crown radius ≈ base + slope × height (a mid-range allometry between
# narrow conifers and broad broadleaf). Clamped to yard-tree reality.
_CROWN_BASE_M = 1.4
_CROWN_SLOPE = 0.16
_CROWN_MIN_M, _CROWN_MAX_M = 0.9, 10.0
_MIN_SEP_M = 2.0             # two distinct treetops are at least this far apart
_SUPPRESS_FACTOR = 0.8       # crowns closer than this × radius are one tree
_HEIGHT_MAX_M = 40.0         # sanity clamp (a bad nodata cell can't be a 300 m tree)
_CHM_MAE_M = 2.8             # published mean absolute error, surfaced honestly


# ── Geo helpers (shared convention with footprint_ndsm) ──────────────────────

def _pixel_to_xy(col: float, row: float, gt: tuple) -> tuple:
    c, a, b, f, d, e = gt
    return (c + a * col + b * row, f + d * col + e * row)


def _ground_m(lat1, lng1, lat2, lng2) -> float:
    """Ground distance in metres (cosLat metric — see src/projection.py)."""
    cos_lat = math.cos(math.radians((lat1 + lat2) / 2)) or 1e-9
    dx = (lng2 - lng1) * 111320.0 * cos_lat
    dy = (lat2 - lat1) * 111320.0
    return math.hypot(dx, dy)


def _crown_radius_m(h: float) -> float:
    return max(_CROWN_MIN_M, min(_CROWN_MAX_M, _CROWN_BASE_M + _CROWN_SLOPE * h))


# ── Variable-window local-maxima detection (the algorithm) ───────────────────

def _box_blur3(arr):
    """3×3 mean, edge-replicated — damps single-pixel CHM noise so it doesn't
    seed spurious treetops, without eroding real crown peaks."""
    p = np.pad(arr, 1, mode="edge")
    acc = np.zeros_like(arr)
    for dr in (0, 1, 2):
        for dc in (0, 1, 2):
            acc += p[dr:dr + arr.shape[0], dc:dc + arr.shape[1]]
    return acc / 9.0


def _local_max3(arr):
    """Boolean mask: pixels ≥ all 8 neighbours (edge-replicated). Prefilters the
    greedy pass down to genuine peaks so an all-forest window stays fast."""
    p = np.pad(arr, 1, mode="edge")
    m = np.ones_like(arr, dtype=bool)
    for dr in (0, 1, 2):
        for dc in (0, 1, 2):
            if dr == 1 and dc == 1:
                continue
            m &= arr >= p[dr:dr + arr.shape[0], dc:dc + arr.shape[1]]
    return m


def detect_treetops(chm, gt: tuple, to_lnglat: Callable, *,
                    min_height_m: float = _MIN_TREE_HEIGHT_M,
                    pixel_size_m: Optional[float] = None,
                    smooth: bool = True) -> list:
    """Detect individual treetops in a canopy-height array by variable-window
    local-maxima. Pure (numpy only) and fully testable on synthetic rasters.

    ``chm`` — 2D height-above-ground in metres (NaN/negative = ground).
    ``gt`` — pixel(col,row)→world affine (footprint_ndsm convention).
    ``to_lnglat(x, y) -> (lng, lat)`` — world→WGS-84.

    Returns a list of item dicts in the shared detector shape (``kind``,
    ``lat``/``lng``, ``height_m`` measured, ``radius_m`` estimated, ``foliage``
    None, ``source`` "canopy-height", ``detect_confidence``, ``dedupe_m``)."""
    if not _HAVE_NUMPY:
        return []
    arr = np.asarray(chm, dtype="float64")
    if arr.ndim != 2 or arr.size == 0:
        return []
    arr = np.where(np.isfinite(arr), arr, 0.0)
    arr = np.where(arr < 0.0, 0.0, arr)
    if pixel_size_m is None:
        pixel_size_m = math.sqrt(abs(gt[1]) * abs(gt[5])) or 1.0

    work = _box_blur3(arr) if smooth else arr
    cand = _local_max3(work) & (work >= float(min_height_m))
    ys, xs = np.where(cand)
    if ys.size == 0:
        return []
    heights = work[ys, xs]
    order = np.argsort(heights)[::-1]      # tallest first (non-max suppression)

    min_sep_px = _MIN_SEP_M / pixel_size_m
    accepted = []          # (row, col, crown_radius_px)
    tops = []
    for idx in order:
        r, c = int(ys[idx]), int(xs[idx])
        h = float(arr[r, c])               # report the true (unblurred) peak
        if h > _HEIGHT_MAX_M:
            continue
        crown_r_m = _crown_radius_m(h)
        crown_r_px = crown_r_m / pixel_size_m
        supp = max(min_sep_px, _SUPPRESS_FACTOR * crown_r_px)
        nearest = None
        skip = False
        for (ar, ac, arad) in accepted:
            d = math.hypot(c - ac, r - ar)
            if d < supp or d < _SUPPRESS_FACTOR * arad:
                skip = True
                break
            if nearest is None or d < nearest:
                nearest = d
        if skip:
            continue
        # A tree hemmed in by taller neighbours reads narrower — cap the crown
        # at half the gap to the nearest already-accepted (taller) top.
        if nearest is not None:
            crown_r_m = max(_CROWN_MIN_M,
                            min(crown_r_m, 0.5 * nearest * pixel_size_m))
        accepted.append((r, c, crown_r_m / pixel_size_m))
        x, y = _pixel_to_xy(c + 0.5, r + 0.5, gt)
        lng, lat = to_lnglat(x, y)
        tops.append({
            "kind": "tree",
            "lat": float(lat), "lng": float(lng),
            "height_m": round(h, 1),
            "radius_m": round(crown_r_m, 1),
            "label": "Tree (detected)",
            "source": "canopy-height",
            "foliage": None,      # no spectral data in a height map
            "detect_confidence": "high (canopy-height map)",
            "dedupe_m": max(2.0, 0.8 * crown_r_m),
        })
    return tops


# ── Tile lookup + windowed GeoTIFF read (needs rasterio; graceful None) ───────

def _quadkey_tile_url(quadkey: str) -> str:
    return _CHM_TILE_URL.format(quadkey=quadkey)


def _index_cache_path() -> str:
    from src import user_paths
    d = os.path.join(str(user_paths.user_data_dir()), "canopy")
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, "tiles.geojson")


def _load_tile_index(_fetch: Optional[Callable] = None) -> Optional[dict]:
    """The Meta tiles.geojson (quadkey → footprint), cached once under the user
    data dir. ``_fetch`` is injectable for tests. ``None`` on any failure."""
    import json
    path = _index_cache_path()
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        except Exception:  # noqa: BLE001 — refetch below
            pass
    fetch = _fetch or _http_get_bytes
    raw = fetch(_CHM_INDEX_URL)
    if not raw:
        return None
    try:
        data = json.loads(raw.decode("utf-8"))
    except Exception:  # noqa: BLE001
        return None
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f)
    except OSError:
        pass
    return data


def _http_get_bytes(url: str, timeout: float = 30.0) -> Optional[bytes]:
    import urllib.request
    try:
        req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read()
    except Exception:  # noqa: BLE001 — offline-graceful
        return None


def _feature_bbox(geom: dict) -> Optional[tuple]:
    """(west, south, east, north) of a GeoJSON Polygon/MultiPolygon ring set."""
    coords = geom.get("coordinates")
    if not coords:
        return None
    xs, ys = [], []

    def _walk(c):
        if not c:
            return
        if isinstance(c[0], (int, float)):
            xs.append(c[0])
            ys.append(c[1])
        else:
            for cc in c:
                _walk(cc)
    _walk(coords)
    if not xs:
        return None
    return (min(xs), min(ys), max(xs), max(ys))


def quadkeys_for_bbox(bbox: dict, index: dict) -> list:
    """Quadkeys of tiles whose footprint bbox intersects ``bbox``. Property-
    scale queries fall inside one tile (occasionally two at a seam)."""
    out = []
    for feat in (index or {}).get("features", []) or []:
        props = feat.get("properties") or {}
        qk = (props.get("quadkey") or props.get("QuadKey")
              or props.get("tile") or props.get("id"))
        fb = _feature_bbox(feat.get("geometry") or {})
        if qk is None or fb is None:
            continue
        w, s, e, n = fb
        if not (e < bbox["west"] or w > bbox["east"]
                or n < bbox["south"] or s > bbox["north"]):
            out.append(str(qk))
    return out


def _read_window_vsicurl(url: str, bbox: dict):
    """Windowed read of the CHM tile at ``url`` over ``bbox`` via rasterio's
    /vsicurl (range requests — fetches only the needed window, not the whole
    tile). Returns ``(chm_array, gt, to_lnglat)`` or ``None``. Mirrors
    ``footprint_ndsm.read_ndsm_geotiff``'s dependency handling."""
    try:
        import rasterio
        from rasterio.windows import from_bounds
    except ImportError:
        return None
    try:
        with rasterio.open("/vsicurl/" + url) as ds:
            west, south = bbox["west"], bbox["south"]
            east, north = bbox["east"], bbox["north"]
            crs = ds.crs
            to_lnglat = (lambda x, y: (x, y))
            if crs is not None and (crs.to_epsg() or 0) != 4326:
                from rasterio.warp import transform_bounds
                from pyproj import Transformer
                west, south, east, north = transform_bounds(
                    4326, crs, west, south, east, north)
                tr = Transformer.from_crs(crs, 4326, always_xy=True)
                to_lnglat = (lambda x, y: tr.transform(x, y))
            win = from_bounds(west, south, east, north, ds.transform)
            arr = ds.read(1, window=win, boundless=True,
                          fill_value=float("nan"))
            wt = ds.window_transform(win)
            gt = (wt.c, wt.a, wt.b, wt.f, wt.d, wt.e)
            return arr, gt, to_lnglat
    except Exception:  # noqa: BLE001 — network / GDAL / coverage all degrade
        return None


def _default_reader(bbox: dict):
    """Fetch + windowed-read the Meta CHM for ``bbox``. ``None`` when there's no
    rasterio, no network, or no coverage — the caller then falls back."""
    index = _load_tile_index()
    if not index:
        return None
    for qk in quadkeys_for_bbox(bbox, index):
        res = _read_window_vsicurl(_quadkey_tile_url(qk), bbox)
        if res is not None and _HAVE_NUMPY and np.asarray(res[0]).size:
            return res
    return None


def _pixel_size_from(gt: tuple, to_lnglat: Callable) -> float:
    """Ground metres per pixel, derived through ``to_lnglat`` so it's correct
    whatever the tile CRS (Web-Mercator metres at lat 53 are ~1.7× ground —
    reading pixel size off the transform units would size every crown wrong)."""
    x0, y0 = _pixel_to_xy(0.5, 0.5, gt)
    x1, y1 = _pixel_to_xy(1.5, 0.5, gt)
    lng0, lat0 = to_lnglat(x0, y0)
    lng1, lat1 = to_lnglat(x1, y1)
    d = _ground_m(lat0, lng0, lat1, lng1)
    return d if d > 1e-6 else 1.0


def detect_trees_chm(bbox: dict, *, min_height_m: float = _MIN_TREE_HEIGHT_M,
                     _reader: Optional[Callable] = None) -> Optional[dict]:
    """Detect trees over ``bbox`` from the canopy-height map. ``_reader(bbox) ->
    (chm_array, gt, to_lnglat) | None`` is injectable (real: Meta CHM via
    rasterio; tests: synthetic). Returns ``None`` when no height data could be
    read (caller falls back / reports honestly); otherwise::

        {"trees": [...], "m_per_px": float, "source": "canopy-height",
         "mae_m": 2.8, "min_height_m": float}
    """
    reader = _reader or _default_reader
    res = reader(bbox)
    if res is None:
        return None
    chm, gt, to_lnglat = res
    pixel_size_m = _pixel_size_from(gt, to_lnglat)
    tops = detect_treetops(chm, gt, to_lnglat, min_height_m=min_height_m,
                           pixel_size_m=pixel_size_m)
    trees = [t for t in tops
             if bbox["south"] <= t["lat"] <= bbox["north"]
             and bbox["west"] <= t["lng"] <= bbox["east"]]
    return {"trees": trees, "m_per_px": round(pixel_size_m, 2),
            "source": "canopy-height", "mae_m": _CHM_MAE_M,
            "min_height_m": min_height_m}


# ── Import tail (reuses the OSM/RGB filter + insert; CHM-specific message) ────

def import_chm_result(res: Optional[dict], project_dict: dict, *,
                      boundary=None, margin_m: float = 30.0,
                      area_note: str = "") -> dict:
    """Filter CHM-detected trees to the boundary, add them, and compose an
    honest status message. No satellite-alignment offset is applied: CHM
    positions are the map's own WGS-84 georeference (true coords), not a read
    off the displayed basemap. ``res=None`` means no height data was available.

    Returns ``{"added", "kept", "found", "message"}``."""
    from src.osm_features import add_features_to_project, filter_to_boundary
    if res is None:
        return {"added": 0, "kept": 0, "found": 0, "message": ""}
    items = list(res.get("trees") or [])
    kept, n_inside, n_neigh = filter_to_boundary(items, boundary, margin_m)
    added = add_features_to_project(kept, project_dict)
    msg = (f"Read the 1 m canopy-height map; found {len(items)} tree"
           f"{'s' if len(items) != 1 else ''} taller than "
           f"{res.get('min_height_m', _MIN_TREE_HEIGHT_M):.0f} m")
    if boundary and len(boundary) >= 3:
        msg += (f"; kept {len(kept)} ({n_inside} inside your boundary + "
                f"{n_neigh} neighbour{'s' if n_neigh != 1 else ''} within "
                f"{margin_m:.0f} m)")
    elif area_note:
        msg += f" ({area_note})"
    msg += f"; added {added} new."
    if added:
        msg += (f" Heights are measured from the map (±≈{res.get('mae_m', _CHM_MAE_M):.0f} m); "
                "crown sizes are estimated from height. Foliage is unknown "
                "(a height map has no colour), so all are treated as "
                "year-round shade. Click a tree and press Delete to remove "
                "any you don't want.")
    elif not items:
        msg += (" The canopy-height map shows nothing above that height here "
                "— lower the height threshold, or mark trees by hand below.")
    return {"added": added, "kept": len(kept), "found": len(items),
            "message": msg}

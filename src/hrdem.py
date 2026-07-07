"""
hrdem.py — NRCan HRDEM (High Resolution Digital Elevation Model) elevation
source for Saskatchewan and the rest of Canada (V2.17).

Design principle P5 — make invisible ecology visible: Edmonton-parity yard-scale
relief, terrain shadows and canopy heights depend on fine elevation data. Alberta
gets it from the City of Edmonton 0.5 m LiDAR contour pack; this module is the
national equivalent, so Regina / Lumsden / Saskatoon / Battleford (and anywhere
NRCan has flown LiDAR) get true 1–2 m relief instead of the coarse 30 m Copernicus
fallback.

HOW IT WORKS
    * Query the NRCan Datacube **STAC** API for HRDEM LiDAR / mosaic items that
      intersect the project bbox, and pick the DTM (bare-earth) and DSM (surface)
      **Cloud-Optimized GeoTIFF** assets (Lambert Conformal Conic).
    * **Windowed-read** the COGs over HTTP (``/vsicurl/``) with rasterio, sampling
      a regular grid — reusing the exact rasterio + pyproj pattern already proven
      in ``src/soil_grid.py`` (reproject 4326 → raster CRS, sample points).
    * Return the **same grid dict shape** as ``terrain.fetch_openmeteo_grid`` so it
      drops straight into ``terrain.generate_terrain`` (contours, slope, hydrology,
      3-D scene). ``nDSM = DSM − DTM`` yields object heights for canopy / building
      footprints — richer than Edmonton's contour-only data.

HONEST DEGRADATION (P9)
    Everything here is best-effort and **fail-safe**: no rasterio/pyproj, no
    network, no HRDEM coverage for the bbox, or any parse error → every function
    returns ``None`` and the caller falls back to the 30 m Copernicus DEM, which
    is labelled as such. HRDEM covers much of the *settled* prairie; rural gaps
    are expected and handled by the fallback, never a crash.

TESTABILITY
    The STAC HTTP fetch and the COG point-sampler are **injectable seams**
    (``fetcher`` / ``sampler`` kwargs), so the coverage logic and grid assembly
    are unit-tested with canned STAC JSON and a fake sampler — no network and no
    rasterio required. The real rasterio path is exercised against a synthetic COG
    where rasterio is installed.

NOTE: the live STAC/asset wiring is coded to NRCan's published HRDEM contract
(collections ``hrdem-lidar`` / ``hrdem-mosaic``; DTM/DSM COG assets). It is
defensive about collection ids and asset key spellings and degrades safely, so if
the live schema differs slightly it simply falls back to Copernicus until tuned.
"""

from __future__ import annotations

import urllib.parse
from typing import Callable, Optional

from src.http_utils import http_get_json
from src.terrain import (
    _cache_key,
    _despike,
    _DESPIKE_THRESHOLD_M,
    _grid_points,
    grid_dims,
)

# NRCan Datacube STAC — HRDEM collections (LiDAR projects + seamless mosaic).
STAC_API = "https://datacube.services.geo.ca/stac/api"
_COLLECTIONS = ("hrdem-lidar", "hrdem-mosaic")
# Asset keys we accept for the bare-earth (DTM) and surface (DSM) rasters —
# NRCan has used a few spellings across product generations; be tolerant.
_DTM_KEYS = ("dtm", "dem", "hrdem-dtm", "dtm-1m", "dtm_1m")
_DSM_KEYS = ("dsm", "hrdem-dsm", "dsm-1m", "dsm_1m")

_TIMEOUT = 25.0
# HRDEM LiDAR resolves yard scale, so use a fine sampling grid (like Edmonton's
# 5 m IDW grid) rather than the 15 m used for the coarse Copernicus DEM.
DEFAULT_RESOLUTION_M = 5.0


# ── HTTP seam (monkeypatchable in tests) ─────────────────────────────────────

def _http_get_json(url: str, timeout: float = _TIMEOUT) -> Optional[dict]:
    """Module-local alias so tests can monkeypatch ``hrdem._http_get_json``."""
    return http_get_json(url, timeout=timeout)


# ── STAC search + asset selection (pure JSON; no heavy deps) ──────────────────

def _stac_search(bbox: dict, *, fetcher: Optional[Callable] = None) -> list[dict]:
    """Return HRDEM STAC items intersecting ``bbox`` (may be empty). Fail-safe:
    any error → ``[]``. ``fetcher(url) -> dict`` is injectable for tests."""
    get = fetcher or _http_get_json
    bbox_param = f"{bbox['west']},{bbox['south']},{bbox['east']},{bbox['north']}"
    items: list[dict] = []
    for collection in _COLLECTIONS:
        qs = urllib.parse.urlencode({
            "collections": collection,
            "bbox": bbox_param,
            "limit": "10",
        })
        try:
            data = get(f"{STAC_API}/search?{qs}")
        except Exception:  # noqa: BLE001 — any fetch failure → skip this collection
            data = None
        if isinstance(data, dict):
            feats = data.get("features")
            if isinstance(feats, list):
                items.extend(f for f in feats if isinstance(f, dict))
    return items


def _asset_href(item: dict, keys: tuple[str, ...]) -> Optional[str]:
    """Pull the first matching COG href from a STAC item's assets, tolerant of
    asset-key spelling and of the key living in the asset's ``roles``."""
    assets = item.get("assets")
    if not isinstance(assets, dict):
        return None
    lowered = {k.lower(): v for k, v in assets.items() if isinstance(v, dict)}
    # 1. direct key match
    for want in keys:
        a = lowered.get(want)
        if a and a.get("href"):
            return a["href"]
    # 2. key contains one of the wanted tokens, or roles/title mention it
    for k, a in lowered.items():
        href = a.get("href")
        if not href:
            continue
        blob = (k + " " + " ".join(a.get("roles", []) or [])
                + " " + str(a.get("title", ""))).lower()
        if any(want in blob for want in keys):
            return href
    return None


def _pick_cog(items: list[dict], keys: tuple[str, ...]) -> Optional[str]:
    """Choose the DTM (or DSM) COG href from candidate STAC items. Prefers the
    seamless mosaic item when present, else the first item that has the asset."""
    ordered = sorted(
        items,
        key=lambda it: 0 if "mosaic" in str(it.get("collection", "")).lower() else 1,
    )
    for it in ordered:
        href = _asset_href(it, keys)
        if href:
            return href
    return None


def has_coverage(bbox: dict, *, fetcher: Optional[Callable] = None) -> bool:
    """True if NRCan HRDEM has a DTM covering ``bbox``. Fail-safe → False."""
    try:
        return _pick_cog(_stac_search(bbox, fetcher=fetcher), _DTM_KEYS) is not None
    except Exception:  # noqa: BLE001
        return False


# ── COG point sampler (lazy rasterio + pyproj — the soil_grid pattern) ────────

def _rasterio_sampler(cog_url: str) -> Optional[Callable]:
    """Return ``sample(points) -> list[Optional[float]]`` reading ``cog_url`` over
    ``/vsicurl/``, or ``None`` if rasterio is unavailable / the COG won't open.

    Opens the dataset once and reuses it for every point (GDAL block-caches the
    HTTP range reads), reprojecting 4326 → the raster CRS via pyproj — the same
    approach as ``soil_grid._sample_one``."""
    try:
        import rasterio  # noqa: F401
    except ImportError:
        return None
    try:
        vsi = cog_url if cog_url.startswith("/vsicurl/") else f"/vsicurl/{cog_url}"
        ds = rasterio.open(vsi)
    except Exception:  # noqa: BLE001 — unreachable / not a raster
        return None

    crs = ds.crs
    transformer = None
    if crs is not None and (crs.to_epsg() or 0) != 4326:
        try:
            from pyproj import Transformer
            transformer = Transformer.from_crs(4326, crs, always_xy=True)
        except Exception:  # noqa: BLE001
            ds.close()
            return None
    nodata = ds.nodata

    def sample(points: list[tuple[float, float]]) -> list[Optional[float]]:
        # points are (lat, lng); rasterio wants (x, y) = (lng, lat) in raster CRS.
        coords = []
        for lat, lng in points:
            x, y = (transformer.transform(lng, lat) if transformer else (lng, lat))
            coords.append((x, y))
        out: list[Optional[float]] = []
        for val in ds.sample(coords):
            v = val[0]
            try:
                fv = float(v)
            except (TypeError, ValueError):
                out.append(None)
                continue
            if nodata is not None and fv == float(nodata):
                out.append(None)
            elif fv < -1e6 or fv > 1e6:   # GDAL sentinel
                out.append(None)
            else:
                out.append(fv)
        return out

    return sample


# ── Grid assembly (pure Python; testable with an injected sampler) ────────────

def _build_grid(bbox: dict, resolution_m: float,
                sampler: Callable, source: str) -> Optional[dict]:
    """Sample a regular north-to-south grid with ``sampler`` and return the
    ``fetch_openmeteo_grid``-shaped dict, or ``None`` if too little data."""
    cols, rows = grid_dims(bbox, resolution_m)
    points = _grid_points(bbox, cols, rows)
    try:
        elevations = list(sampler(points))
    except Exception:  # noqa: BLE001 — a mid-read failure → let the caller fall back
        return None
    if len(elevations) != cols * rows:
        return None

    valid = [v for v in elevations if v is not None]
    if not valid or len(valid) < 0.5 * len(elevations):
        return None
    median = sorted(valid)[len(valid) // 2]
    elevations = [float(v) if v is not None else float(median) for v in elevations]
    missing_pct = round(100.0 * (1.0 - len(valid) / len(elevations)), 1)

    grid = [[elevations[r * cols + c] for c in range(cols)] for r in range(rows)]
    # Despike nodata/edge artifacts. No Gaussian blur: HRDEM is already fine and
    # we want to preserve the yard-scale detail that motivates using it.
    grid = _despike(grid, _DESPIKE_THRESHOLD_M)

    return {
        "grid": grid, "cols": cols, "rows": rows, "bbox": bbox,
        "resolution_m": resolution_m, "missing_pct": missing_pct,
        "source": source,
    }


def fetch_hrdem_grid(bbox: dict, resolution_m: float = DEFAULT_RESOLUTION_M, *,
                     fetcher: Optional[Callable] = None,
                     sampler: Optional[Callable] = None) -> Optional[dict]:
    """Return an HRDEM bare-earth (DTM) elevation grid for ``bbox`` — same shape
    as ``terrain.fetch_openmeteo_grid`` — or ``None`` to fall back to Copernicus.

    ``fetcher`` overrides the STAC HTTP call, ``sampler`` overrides the COG point
    sampler; both exist so the logic is testable without network or rasterio."""
    cache_key = _cache_key("hrdem_dtm_v1", bbox, resolution_m)

    store = None
    try:
        from src.terrain_store import TerrainStore
        store = TerrainStore()
        hit = store.get_srtm_grid(cache_key)   # generic keyed grid cache (reused)
        if hit is not None:
            return hit
    except Exception:  # noqa: BLE001
        store = None

    samp = sampler
    if samp is None:
        cog = _pick_cog(_stac_search(bbox, fetcher=fetcher), _DTM_KEYS)
        if not cog:
            return None
        samp = _rasterio_sampler(cog)
        if samp is None:
            return None

    out = _build_grid(bbox, resolution_m, samp, "NRCan HRDEM (1 m LiDAR, DTM)")
    if out is None:
        return None
    try:
        if store is not None:
            store.store_srtm_grid(cache_key, out)
    except Exception:  # noqa: BLE001
        pass
    return out


def fetch_hrdem_ndsm(bbox: dict, resolution_m: float = DEFAULT_RESOLUTION_M, *,
                     fetcher: Optional[Callable] = None,
                     dtm_sampler: Optional[Callable] = None,
                     dsm_sampler: Optional[Callable] = None) -> Optional[dict]:
    """Return an nDSM (normalized DSM = DSM − DTM) object-height grid for ``bbox``
    — heights of trees, buildings, hedges above bare earth — or ``None``.

    Feeds the canopy / building-footprint pipeline (``footprint_ndsm.py``): a
    positive-height blob is a tree or structure that casts shade. Same grid dict
    shape; ``source`` notes it is an nDSM."""
    items = None
    dsamp = dsm_sampler
    tsamp = dtm_sampler
    if dsamp is None or tsamp is None:
        items = _stac_search(bbox, fetcher=fetcher)
        if dsamp is None:
            dsm_cog = _pick_cog(items, _DSM_KEYS)
            dsamp = _rasterio_sampler(dsm_cog) if dsm_cog else None
        if tsamp is None:
            dtm_cog = _pick_cog(items, _DTM_KEYS)
            tsamp = _rasterio_sampler(dtm_cog) if dtm_cog else None
    if dsamp is None or tsamp is None:
        return None

    dsm = _build_grid(bbox, resolution_m, dsamp, "hrdem-dsm")
    dtm = _build_grid(bbox, resolution_m, tsamp, "hrdem-dtm")
    if dsm is None or dtm is None or dsm["cols"] != dtm["cols"] \
            or dsm["rows"] != dtm["rows"]:
        return None

    ndsm = [
        [max(0.0, dsm["grid"][r][c] - dtm["grid"][r][c])
         for c in range(dsm["cols"])]
        for r in range(dsm["rows"])
    ]
    return {
        "grid": ndsm, "cols": dsm["cols"], "rows": dsm["rows"], "bbox": bbox,
        "resolution_m": resolution_m,
        "source": "NRCan HRDEM nDSM (DSM − DTM object heights)",
    }

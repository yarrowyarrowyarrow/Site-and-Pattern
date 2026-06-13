"""
soil_grid.py — offline soil sampling from the Gridded Soil Landscapes of
Canada (V1.67).

ISRIC's SoilGrids REST API is paused, so the live `fetch_soil` always fell back
to a coarse 6-region Alberta guess. This adds a *download-once, then offline*
path: the **Gridded Soil Landscapes of Canada** GeoTIFFs (sand/silt/clay/pH by
depth, GlobalSoilMap standard, covering the agricultural prairies) are fetched
once into a local pack (see ``src/soil_downloader.py``) and sampled here by
lat/lng with `rasterio` + `pyproj` — the same optional deps and reprojection
path ``src/footprint_ndsm.py`` already uses.

:func:`sample_soil` returns the **same dict shape as
``property_data._parse_soilgrids``** (``summary`` + ``properties`` + ``source``)
so the display, cache, and the new plant-matching wiring need no special case.
Returns ``None`` when there's no pack, the point is outside coverage, or
``rasterio``/``pyproj`` aren't installed — callers then fall through to SoilGrids
or the regional approximation.
"""

from __future__ import annotations

import os
import sys
from typing import Optional

# Attribute → filename keywords (robust to the source's exact GeoTIFF names).
_ATTR_KEYWORDS = {
    "ph": ("ph",),
    "sand": ("sand",),
    "silt": ("silt",),
    "clay": ("clay",),
}
# Prefer a topsoil-depth raster when several depths are present.
_TOPSOIL_HINTS = ("0-5", "0_5", "0to5", "0-30", "0_30", "sd1", "_05_", "topsoil")


def soil_pack_dir() -> str:
    """Directory holding the downloaded soil GeoTIFFs (sibling of the DB)."""
    if os.name == "nt":
        base = os.environ.get("APPDATA", os.path.expanduser("~"))
    elif sys.platform == "darwin":
        base = os.path.join(os.path.expanduser("~"),
                            "Library", "Application Support")
    else:
        base = os.environ.get("XDG_DATA_HOME",
                              os.path.join(os.path.expanduser("~"),
                                           ".local", "share"))
    d = os.path.join(base, "PermaDesign", "soil")
    os.makedirs(d, exist_ok=True)
    return d


def _tifs(pack_dir: str) -> list:
    try:
        return [f for f in os.listdir(pack_dir)
                if f.lower().endswith((".tif", ".tiff"))]
    except OSError:
        return []


def has_soil_pack(pack_dir: Optional[str] = None) -> bool:
    """True when at least one soil GeoTIFF is present in the pack."""
    return bool(_tifs(pack_dir or soil_pack_dir()))


def _find_attr_tif(pack_dir: str, attr: str) -> Optional[str]:
    kws = _ATTR_KEYWORDS[attr]
    matches = [f for f in _tifs(pack_dir)
               if any(k in f.lower() for k in kws)]
    if not matches:
        return None
    top = [f for f in matches if any(h in f.lower() for h in _TOPSOIL_HINTS)]
    return os.path.join(pack_dir, sorted(top or matches)[0])


def _normalize(attr: str, v: float) -> float:
    """Coerce a raster value into display units (% for texture, pH units),
    tolerating the common g/kg or ×10 encodings used by gridded soil products."""
    v = float(v)
    if attr in ("sand", "silt", "clay"):
        if v > 100.0:           # g/kg or ×10 → percent
            v = v / 10.0
        return round(v, 1)
    # pH
    if v > 14.0:                # pH×10
        v = v / 10.0
    return round(v, 2)


def _sample_one(path: str, lat: float, lng: float) -> Optional[float]:
    try:
        import rasterio
    except ImportError:
        return None
    try:
        with rasterio.open(path) as ds:
            x, y = lng, lat
            crs = ds.crs
            if crs is not None and (crs.to_epsg() or 0) != 4326:
                from pyproj import Transformer
                tr = Transformer.from_crs(4326, crs, always_xy=True)
                x, y = tr.transform(lng, lat)
            val = next(ds.sample([(x, y)]))[0]
            if val is None:
                return None
            fval = float(val)
            nodata = ds.nodata
            if nodata is not None and fval == float(nodata):
                return None
            # GeoTIFF nodata often surfaces as a huge sentinel.
            if fval < -1e6 or fval > 1e6:
                return None
            return fval
    except Exception:  # noqa: BLE001 — any read failure → "no value here"
        return None


def sample_soil(lat: float, lng: float,
                pack_dir: Optional[str] = None) -> Optional[dict]:
    """Sample the local soil pack at (lat, lng). Returns a dict shaped like
    ``property_data._parse_soilgrids`` output, or ``None`` when no pack /
    outside coverage / rasterio unavailable."""
    pack = pack_dir or soil_pack_dir()
    if not has_soil_pack(pack):
        return None
    vals: dict[str, Optional[float]] = {}
    for attr in ("ph", "sand", "silt", "clay"):
        tif = _find_attr_tif(pack, attr)
        raw = _sample_one(tif, lat, lng) if tif else None
        vals[attr] = _normalize(attr, raw) if raw is not None else None
    # Need at least pH or a full texture triple to be useful.
    if vals["ph"] is None and None in (vals["sand"], vals["silt"], vals["clay"]):
        return None

    from src.property_data import _texture_class
    sand, silt, clay = vals["sand"], vals["silt"], vals["clay"]
    by_prop = {}
    for attr, key in (("ph", "phh2o"), ("sand", "sand"),
                      ("silt", "silt"), ("clay", "clay")):
        if vals[attr] is not None:
            by_prop[key] = [{"label": "0-30cm (SLC)", "value": vals[attr]}]
    return {
        "properties": by_prop,
        "summary": {
            "ph_top": vals["ph"],
            "sand_pct_top": sand,
            "silt_pct_top": silt,
            "clay_pct_top": clay,
            "texture_class": _texture_class(sand, silt, clay),
            "max_reported_depth_cm": 30,
        },
        "source": "Gridded Soil Landscapes of Canada (offline pack)",
    }

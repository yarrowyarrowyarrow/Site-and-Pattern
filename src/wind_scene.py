"""
src/wind_scene.py — the site's real wind, as the 3D scene consumes it (V2.33, F68).

Design principles P5 (make invisible ecology visible) and P11 (the body and the
site know things the screen does not) — see docs/DESIGN_PHILOSOPHY.md.

The app has known which way the wind blows on a given site since V1.67: a
seasonal wind rose from Open-Meteo, DB-cached so it works offline
(:mod:`src.wind`), and since V1.68 a porosity-aware shelter geometry for the
plants already in the design (:mod:`src.wind_shadow`). None of it reached the
3D preview. The viewer swayed — generically, at a fixed amplitude, in a
hard-coded diagonal direction, with every plant in the yard moving the same
amount whether it stood in the open or behind a spruce windbreak.

So the windbreak analysis was a band on a 2D map, and the one place a person
would actually *believe* it — watching the grass behind the shelterbelt move
less than the grass in front of it — showed nothing. This module is the join.

    wind_block(project, month=…, year=…, bounds=…) -> dict | None

Qt-free and network-optional: the wind rose comes from the DB cache when it is
there, from the project's own persisted `site_config` when it is not, and the
whole block is simply absent when neither is (the viewer then keeps its
generic sway, which is the honest degradation).

The SHELTER GRID is the piece worth explaining. `wind_shadow.merged_shelter`
returns lee polygons in lat/lng; a vertex shader cannot test point-in-polygon.
So the polygons are rasterised here — Python-side, where the geometry already
lives — into a small coverage grid over the scene's own bounds, which the
viewer uploads as one shared texture and samples by world position. One
uniform, no per-instance attribute, and it works identically for the baked and
the procedural plant paths.
"""

from __future__ import annotations

from typing import Optional

# Grid resolution over the scene bounds. A yard is tens of metres and a shelter
# band is metres wide, so this is roughly a 0.5–1 m cell — finer than the eye
# can distinguish in swaying foliage, and 4 KB of texture.
SHELTER_COLS = 64
SHELTER_ROWS = 64

# How much of its sway a plant keeps in the deepest shelter. Not zero: a
# windbreak reduces wind speed, it does not stop it, and drawing dead-still
# plants behind a hedge would be the same false precision in the other
# direction (P9). 50% porosity gives ~50-70% reduction at 5H downwind in the
# literature; the strongest band lands near the low end of that.
_BAND_KEEP = {"strong": 0.35, "moderate": 0.60, "weak": 0.82}

_SEASON_OF = {12: "winter", 1: "winter", 2: "winter",
              3: "spring", 4: "spring", 5: "spring",
              6: "summer", 7: "summer", 8: "summer",
              9: "fall", 10: "fall", 11: "fall"}


def season_for_month(month: int) -> str:
    """Meteorological season for a scene month — the granularity the wind rose
    actually holds (src.wind computes four seasonal blocks, no finer)."""
    return _SEASON_OF.get(int(month or 0), "summer")


def _site_latlng(project: dict):
    sc = ((project or {}).get("properties") or {}).get("site_config") or {}
    lat, lng = sc.get("latitude"), sc.get("longitude")
    try:
        return (float(lat), float(lng)) if lat is not None and lng is not None \
            else (None, None)
    except (TypeError, ValueError):
        return (None, None)


def _rose_for(project: dict, month: int, get_rose=None):
    """(from_deg, mean_kmh, approximate) for the scene's season, or Nones.

    Prefers the SEASONAL block — the app has computed and cached four of them
    since V1.67 and read exactly one of them anywhere (snow microsites). A
    prairie yard's winter wind is not its July wind, and the 3D view is the
    surface where that difference is legible.
    """
    sc = ((project or {}).get("properties") or {}).get("site_config") or {}
    lat, lng = _site_latlng(project)
    rose = None
    if lat is not None:
        try:
            if get_rose is None:
                from src.wind import get_wind_summary as get_rose_default
                get_rose = get_rose_default
            rose = get_rose(lat, lng)
        except Exception:                             # noqa: BLE001
            rose = None                               # offline / no cache yet
    if rose:
        block = (rose.get("seasons") or {}).get(season_for_month(month)) \
            or rose.get("annual") or {}
        deg = block.get("prevailing_deg")
        if deg is not None:
            return (float(deg), float(block.get("mean_speed") or 0.0),
                    bool(rose.get("approximate")))
    # The annual figure wind_flow.fetch_wind_for_site already persisted onto
    # the project — no DB, no network, and correct as far as it goes.
    deg = sc.get("wind_prevailing_deg")
    if deg is None:
        return (None, None, None)
    try:
        return (float(deg), float(sc.get("wind_mean_kmh") or 0.0), True)
    except (TypeError, ValueError):
        return (None, None, None)


def _shelter_grid(project, from_deg, year, bounds, origin, get_plant=None):
    """Rasterise the merged lee bands into a 0–255 coverage grid, or None."""
    try:
        from shapely.geometry import Point, Polygon        # noqa: PLC0415
        from src.wind_shadow import casters_from_project, merged_shelter
    except Exception:                                      # noqa: BLE001
        return None
    casters = casters_from_project(project, year=year, get_plant=get_plant)
    if not casters:
        return None
    merged = merged_shelter(casters, from_deg)
    bands = merged.get("bands") or []
    if not bands:
        return None
    # merged_shelter hands back lat/lng rings (it feeds a Leaflet overlay);
    # the scene is local metres about `origin`, so project them back.
    shapes = []
    for band in bands:
        keep = _BAND_KEEP.get(band.get("strength"), 0.8)
        for ring in band.get("rings") or []:
            pts = [origin.to_xy(lng, lat) for lat, lng in ring]
            if len(pts) >= 3:
                poly = Polygon(pts)
                if poly.is_valid and not poly.is_empty:
                    shapes.append((poly, keep))
    if not shapes:
        return None
    x0, y0 = bounds["min_x"], bounds["min_y"]
    dx = (bounds["max_x"] - x0) / SHELTER_COLS
    dy = (bounds["max_y"] - y0) / SHELTER_ROWS
    cells = []
    for r in range(SHELTER_ROWS):
        cy = y0 + (r + 0.5) * dy
        for c in range(SHELTER_COLS):
            pt = Point(x0 + (c + 0.5) * dx, cy)
            keep = 1.0
            for poly, k in shapes:
                if k < keep and poly.contains(pt):
                    keep = k
            cells.append(int(round(keep * 255)))
    return {"cols": SHELTER_COLS, "rows": SHELTER_ROWS,
            "min_x": round(x0, 2), "min_y": round(y0, 2),
            "max_x": round(bounds["max_x"], 2),
            "max_y": round(bounds["max_y"], 2),
            "keep": cells}


def wind_block(project: dict, *, month: int = 7, year: int = 0,
               bounds: Optional[dict] = None, origin=None,
               get_plant=None, get_rose=None) -> Optional[dict]:
    """The scene's ``wind`` block, or None when the site's wind is unknown.

    ``origin`` is the scene's projector (``src.projection.Projector``) so the
    shelter grid lands in the same local metres as the plants.
    """
    from_deg, mean_kmh, approximate = _rose_for(project, month, get_rose)
    if from_deg is None:
        return None
    block = {
        # Degrees the wind blows FROM, 0 = north — src.wind's convention, kept
        # so nobody has to remember which end of the arrow this is.
        "from_deg": round(float(from_deg), 1),
        "mean_kmh": round(float(mean_kmh or 0.0), 1),
        "season": season_for_month(month),
        # True when this came from the bundled regional approximation or from
        # the project's stored annual figure rather than from a fetched
        # seasonal rose. The viewer does not draw differently; it is here so a
        # caption can say so rather than implying a measurement (P9).
        "approximate": bool(approximate),
    }
    if bounds and origin is not None:
        grid = _shelter_grid(project, from_deg, year, bounds, origin, get_plant)
        if grid:
            block["shelter"] = grid
    return block

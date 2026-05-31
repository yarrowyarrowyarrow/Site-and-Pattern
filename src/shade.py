"""
shade.py — Cast-shade estimation for the design grid (V1.48).

Estimates which patches of ground are shaded a meaningful fraction of the day,
so the generator can put shade-tolerant plants where it is actually shady —
under existing trees, north of buildings, beneath the design's own canopy.

Casters are:
  * existing on-site trees / buildings the user marked (project features
    ``existing_tree`` / ``existing_building``),
  * the design's own trees & shrubs (mature height + canopy), and
  * already-placed plants/structures.

The model is deliberately simple and **Qt-free**, reusing ``src/solar.py``:
for a handful of representative dates/times we get the sun's altitude/azimuth,
project each caster's shadow as a circle of the caster's canopy radius displaced
down-sun by ``height / tan(altitude)``, and accumulate, per grid cell, the
fraction of sampled daylight moments it lies in shadow. Cells over a threshold
are "shaded". Accurate enough to steer planting; not a ray-traced shadow study.
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta
from typing import Optional

# Representative sampling — solstices + equinox capture the seasonal envelope;
# a few daylight hours capture the east→west sweep without a heavy loop.
_SAMPLE_MONTHS_DAYS = [(3, 20), (6, 21), (9, 22)]
_SAMPLE_HOURS_LOCAL = [9, 12, 15]          # mid-morning, noon, mid-afternoon
_MIN_SUN_ALT = 5.0                          # below this the sun casts no useful
                                            # shadow (and 1/tan blows up)
_MAX_SHADOW_M = 60.0                        # clamp absurd low-sun shadows


def _caster(lat: float, lng: float, height_m: float, radius_m: float) -> dict:
    return {"lat": lat, "lng": lng, "height_m": max(0.0, float(height_m)),
            "radius_m": max(0.5, float(radius_m))}


def casters_from_project(project_dict: dict) -> list[dict]:
    """Collect shade casters from a project FeatureCollection: marked existing
    trees/buildings plus already-placed plants/structures with a known height.
    Plant heights come from the catalogue (mature_height_meters / canopy)."""
    casters: list[dict] = []
    feats = (project_dict or {}).get("features") or []

    # Lazy plant lookup so this module stays import-light / DB-optional.
    def _plant_dims(pid):
        try:
            from src.db.plants import get_plant
            row = get_plant(pid) or {}
            h = row.get("mature_height_meters") or row.get("mature_height_m")
            cw = row.get("mature_canopy_m") or row.get("spacing_meters")
            return (float(h) if h else 0.0, float(cw) / 2 if cw else 0.5)
        except Exception:  # noqa: BLE001
            return (0.0, 0.5)

    for f in feats:
        props = f.get("properties", {}) or {}
        et = props.get("element_type")
        geom = f.get("geometry", {}) or {}
        coords = geom.get("coordinates")
        if not coords:
            continue
        # Point geometry → (lng, lat); polygon → use first vertex as a proxy.
        if geom.get("type") == "Point":
            lng, lat = coords[0], coords[1]
        else:
            try:
                ring = coords[0]
                lng = sum(p[0] for p in ring) / len(ring)
                lat = sum(p[1] for p in ring) / len(ring)
            except Exception:  # noqa: BLE001
                continue
        if et == "existing_tree":
            casters.append(_caster(lat, lng, props.get("height_m", 6.0),
                                   props.get("canopy_radius_m", 3.0)))
        elif et == "existing_building":
            casters.append(_caster(lat, lng, props.get("height_m", 5.0),
                                   props.get("canopy_radius_m", 4.0)))
        elif et == "plant":
            pid = props.get("plant_id")
            h, r = _plant_dims(pid)
            if h >= 2.0:                      # only trees/large shrubs matter
                casters.append(_caster(lat, lng, h, r))
    return casters


def _accumulate_shade(out, casters, sun, lat, lng, rows, cols, bbox) -> bool:
    """Add one sun-moment's shadow footprint into ``out`` (in place). Returns
    True when the sun was high enough to cast (so the caller can count valid
    samples). Shared by the season-averaged and single-instant entry points."""
    from src.solar import shadow_azimuth, shadow_length_factor
    if sun.altitude < _MIN_SUN_ALT:
        return False
    cos_lat = math.cos(lat * math.pi / 180) or 1e-9
    shadow_dir = math.radians(shadow_azimuth(sun.azimuth))
    length_factor = shadow_length_factor(sun.altitude)

    def _cell_ll(r, c):
        t = r / max(1, rows - 1)
        u = c / max(1, cols - 1)
        return (bbox["north"] - t * (bbox["north"] - bbox["south"]),
                bbox["west"] + u * (bbox["east"] - bbox["west"]))

    for cv in casters:
        shadow_len = min(cv["height_m"] * length_factor, _MAX_SHADOW_M)
        # Shadow centre: caster displaced down-sun. Azimuth is degrees clockwise
        # from north → north component = cos, east component = sin.
        s_lat = cv["lat"] + (shadow_len * math.cos(shadow_dir)) / 111320.0
        s_lng = cv["lng"] + (shadow_len * math.sin(shadow_dir)) / (111320.0 * cos_lat)
        rad_lat = cv["radius_m"] / 111320.0
        rad_lng = cv["radius_m"] / (111320.0 * cos_lat)
        for r in range(rows):
            for c in range(cols):
                clat, clng = _cell_ll(r, c)
                ndx = (clng - s_lng) / rad_lng if rad_lng else 0.0
                ndy = (clat - s_lat) / rad_lat if rad_lat else 0.0
                if ndx * ndx + ndy * ndy <= 1.0:
                    out[r][c] += 1.0
    return True


def shade_grid(casters: list[dict], elev: dict,
               lat: Optional[float] = None,
               lng: Optional[float] = None,
               dates: Optional[list] = None,
               hours: Optional[list] = None) -> list[list[float]]:
    """``[[fraction]]`` grid (same shape as ``elev['grid']``): per cell, the
    fraction of sampled daylight moments it is shaded by any caster.

    ``dates`` is a list of ``(month, day)`` and ``hours`` a list of local solar
    hours; both default to the season/day-spread sample (equinox + solstices ×
    morning/noon/afternoon) — the season-averaged shade used for placement.
    ``lat``/``lng`` default to the grid-bbox centre."""
    grid = elev.get("grid") or []
    rows = elev.get("rows", len(grid))
    cols = elev.get("cols", len(grid[0]) if grid else 0)
    out = [[0.0] * cols for _ in range(rows)]
    if not casters or rows == 0 or cols == 0:
        return out

    bbox = elev["bbox"]
    if lat is None:
        lat = (bbox["north"] + bbox["south"]) / 2.0
    if lng is None:
        lng = (bbox["east"] + bbox["west"]) / 2.0

    dates = dates or _SAMPLE_MONTHS_DAYS
    hours = hours or _SAMPLE_HOURS_LOCAL

    from src.solar import sun_position
    samples = 0
    for mo, day in dates:
        for hr in hours:
            # solar.sun_position expects UTC and adds lng/15 back to recover
            # local solar time, so convert the local sample hour to UTC first
            # (utc = local - lng/15). Without this, noon would read as dawn.
            dt = datetime(2025, mo, day) + timedelta(hours=hr - lng / 15.0)
            if _accumulate_shade(out, casters, sun_position(lat, lng, dt),
                                 lat, lng, rows, cols, bbox):
                samples += 1

    if samples:
        for r in range(rows):
            for c in range(cols):
                out[r][c] = min(1.0, out[r][c] / samples)
    return out


def shade_grid_at(casters: list[dict], elev: dict, when: datetime,
                  lat: Optional[float] = None,
                  lng: Optional[float] = None) -> list[list[float]]:
    """Binary shade grid for a single instant ``when`` (a naive *local* solar
    datetime): 1.0 where shaded, 0.0 where lit. Used by the time-of-day overlay
    slider so the user can watch shadows sweep across the day/season."""
    grid = elev.get("grid") or []
    rows = elev.get("rows", len(grid))
    cols = elev.get("cols", len(grid[0]) if grid else 0)
    out = [[0.0] * cols for _ in range(rows)]
    if not casters or rows == 0 or cols == 0:
        return out
    bbox = elev["bbox"]
    if lat is None:
        lat = (bbox["north"] + bbox["south"]) / 2.0
    if lng is None:
        lng = (bbox["east"] + bbox["west"]) / 2.0
    from src.solar import sun_position
    dt_utc = when + timedelta(hours=-lng / 15.0)
    _accumulate_shade(out, casters, sun_position(lat, lng, dt_utc),
                      lat, lng, rows, cols, bbox)
    return out


def shade_grid_for_design(project_dict: dict, elev: dict,
                          extra_casters: Optional[list] = None,
                          when: Optional[datetime] = None
                          ) -> list[list[float]]:
    """Convenience wrapper: gather casters from the project (existing + placed)
    plus any ``extra_casters`` and compute the shade grid over ``elev``. With
    ``when`` set, returns the single-instant grid; otherwise the season-average."""
    casters = casters_from_project(project_dict)
    if extra_casters:
        casters = casters + list(extra_casters)
    if when is not None:
        return shade_grid_at(casters, elev, when)
    return shade_grid(casters, elev)


# Shade colour ramp: translucent indigo that deepens with shade fraction.
# (upper-bound fraction, (r, g, b, a)) — first bucket whose bound exceeds the
# value wins. Fully-lit cells are transparent so only shade shows.
_SHADE_RAMP = [
    (0.15, (0, 0, 0, 0)),         # essentially lit → transparent
    (0.40, (63, 81, 181, 60)),   # light shade
    (0.70, (48, 63, 159, 110)),  # moderate
    (1.01, (26, 35, 126, 160)),  # deep shade
]


def _shade_to_rgba(frac: float) -> tuple[int, int, int, int]:
    for upper, rgba in _SHADE_RAMP:
        if frac < upper:
            return rgba
    return _SHADE_RAMP[-1][1]


def shade_ramp_rgba(shade_grid_vals: list[list[float]]) -> tuple[bytes, int, int]:
    """Convert a shade fraction grid to row-major RGBA bytes (mirrors
    ``terrain.slope_ramp_rgba``), ready for ``terrain.encode_png_rgba`` and the
    map's image overlay."""
    h = len(shade_grid_vals)
    w = len(shade_grid_vals[0]) if h else 0
    out = bytearray(w * h * 4)
    for y, row in enumerate(shade_grid_vals):
        for x, frac in enumerate(row):
            r, g, b, a = _shade_to_rgba(frac)
            i = (y * w + x) * 4
            out[i] = r
            out[i + 1] = g
            out[i + 2] = b
            out[i + 3] = a
    return bytes(out), w, h


def shade_overlay_payload(project_dict: dict, boundary, site_config,
                          when: Optional[datetime] = None) -> Optional[dict]:
    """Qt-free orchestration for the shade map overlay (called by the GUI's
    ShadeWorker off-thread). Builds the elevation grid for the site, computes
    the shade grid (single-instant when ``when`` is given, else season-average),
    encodes it to a PNG data URL, and returns ``{"data_url", "bbox"}`` for
    ``map_widget.draw_shade_overlay``. ``None`` when no grid/casters are
    available (caller shows "no shade to display")."""
    try:
        from src import zoning, terrain
        elev = zoning.site_elevation_grid(boundary, site_config)
        if not elev:
            return None
        grid = shade_grid_for_design(project_dict, elev, when=when)
        # All-zero (no casters / nothing shaded) → nothing to draw.
        if not any(v > 0 for row in grid for v in row):
            return None
        rgba, w, h = shade_ramp_rgba(grid)
        png = terrain.encode_png_rgba(rgba, w, h)
        import base64
        data_url = "data:image/png;base64," + base64.b64encode(png).decode("ascii")
        b = elev["bbox"]
        return {"data_url": data_url,
                "bbox": {"south": b["south"], "north": b["north"],
                         "west": b["west"], "east": b["east"]}}
    except Exception:  # noqa: BLE001 — overlay is best-effort
        return None


# ── Qt worker thread (optional; mirrors terrain.TerrainWorker) ───────────────
# Defined only when PyQt6 is importable, so the pure compute above stays usable
# (and testable) without Qt. The GUI runs shade_overlay_payload off the UI
# thread because it can trigger a network elevation fetch.
try:
    from PyQt6.QtCore import QObject, pyqtSignal
    _HAVE_QT = True
except ImportError:
    _HAVE_QT = False

if _HAVE_QT:
    class ShadeWorker(QObject):
        """Compute the shade overlay payload off the UI thread.

            worker = ShadeWorker(project_dict, boundary, site_config, when)
            worker.moveToThread(thread); worker.ready.connect(on_ready)
            thread.started.connect(worker.run); thread.start()
        """

        ready = pyqtSignal(object)   # payload dict, or None
        finished = pyqtSignal()

        def __init__(self, project_dict, boundary, site_config, when=None,
                     parent=None):
            super().__init__(parent)
            self._project = project_dict
            self._boundary = boundary
            self._site_config = site_config
            self._when = when

        def run(self):
            try:
                payload = shade_overlay_payload(
                    self._project, self._boundary, self._site_config, self._when)
            except Exception:  # noqa: BLE001 — never crash the worker thread
                payload = None
            self.ready.emit(payload)
            self.finished.emit()

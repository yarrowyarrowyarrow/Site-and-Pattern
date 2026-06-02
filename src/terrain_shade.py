"""
terrain_shade.py — DEM horizon ray-march for terrain self-shadowing (V1.55).

The footprint shade model in ``src/shade.py`` projects building / tree
*footprints* down-sun on a flat plane. It is blind to **terrain relief**: a
ridge to the south-west that blocks the low afternoon sun, or a valley floor a
hillside keeps in shadow for half the day. This module supplies that missing
piece — the classic DEM cast-shadow ("hill-shadow" / horizon) test over the
elevation grid PermaDesign already fetches (``src/terrain.py``).

For one sun moment (azimuth + altitude from ``src/solar.py``) we, for every
grid cell, march along the ground **toward the sun** and ask whether any upwind
cell rises above the sun's altitude angle. If so, that cell is in terrain
shadow for that moment. ``src/shade.py`` unions this per-moment mask with the
footprint shadows before accumulating the season-average fraction, so terrain
shadows flow through to the planting-zone tags and placement scoring with no
change to those consumers.

numpy accelerates the march when present; a pure-Python fallback keeps the
feature working on the zero-extra-deps install (just slower — the grids are
capped at 10 000 cells and we sample ~9 sun moments, off the UI thread). The
grid is laid out **north-to-south, west-to-east** (row 0 = north), matching
``terrain.fetch_openmeteo_grid`` / ``zoning.cell_latlng``.
"""

from __future__ import annotations

import math
from typing import Optional

try:
    import numpy as _np
    _HAVE_NUMPY = True
except ImportError:  # pragma: no cover - numpy is an optional accelerator
    _np = None
    _HAVE_NUMPY = False

# Grids spanning less vertical relief than this can't cast a meaningful terrain
# shadow; flat sites skip the march entirely, leaving shade.py's footprint-only
# result bit-for-bit unchanged.
_MIN_RELIEF_M = 0.5
# Sun lower than this casts no useful shadow in shade.py either (1/tan blows up).
_MIN_SUN_ALT = 5.0


def has_relief(elev: dict, min_relief_m: float = _MIN_RELIEF_M) -> bool:
    """True when the elevation grid spans at least ``min_relief_m`` of vertical
    relief — i.e. a terrain shadow is even possible. A cheap min/max scan so
    callers (``shade.shade_grid``) can skip the march on flat sites."""
    grid = (elev or {}).get("grid") or []
    lo = hi = None
    for row in grid:
        for v in row:
            if lo is None or v < lo:
                lo = v
            if hi is None or v > hi:
                hi = v
    return lo is not None and (hi - lo) >= min_relief_m


def terrain_shadow_mask(elev: dict, azimuth_deg: float,
                        altitude_deg: float) -> Optional[list[list[float]]]:
    """Per-cell terrain-shadow mask for one sun moment.

    Returns a ``[[0.0/1.0]]`` grid the same shape as ``elev['grid']`` (1.0 = the
    cell is shadowed by upwind terrain), or ``None`` when there is no grid, no
    relief, or the sun is too low to be meaningful. Row 0 is the north edge.

    ``azimuth_deg`` is degrees clockwise from north (matching
    ``solar.sun_position``); ``altitude_deg`` is the sun's height above the
    horizon in degrees.
    """
    grid = (elev or {}).get("grid") or []
    rows = elev.get("rows", len(grid))
    cols = elev.get("cols", len(grid[0]) if grid else 0)
    if rows < 2 or cols < 2 or altitude_deg <= _MIN_SUN_ALT:
        return None
    if not has_relief(elev):
        return None

    from src import terrain
    width_m, height_m = terrain.bbox_size_m(elev["bbox"])
    dx = width_m / max(1, cols - 1)     # ground metres between columns (E-W)
    dy = height_m / max(1, rows - 1)    # ground metres between rows (N-S)
    if dx <= 0 or dy <= 0:
        return None

    az = math.radians(azimuth_deg)
    # March one cell (the finer spacing) per step so we never skip a cell in the
    # denser direction. Toward the sun: its bearing has north component cos(az)
    # and east component sin(az). Row grows southward, so a northward step
    # DECREASES the row index.
    step_m = min(dx, dy)
    dr = -math.cos(az) * step_m / dy    # row delta per step
    dc = math.sin(az) * step_m / dx     # col delta per step
    tan_alt = math.tan(math.radians(altitude_deg))

    if _HAVE_NUMPY:
        return _mask_numpy(grid, rows, cols, dr, dc, step_m, tan_alt)
    return _mask_python(grid, rows, cols, dr, dc, step_m, tan_alt)


def _max_steps(rows: int, cols: int, dr: float, dc: float) -> int:
    """Steps until the ray is guaranteed off the grid from any cell — bounds the
    march for the vectorised path, which can't break early per-cell."""
    span = 1
    if abs(dr) > 1e-12:
        span = max(span, int((rows - 1) / abs(dr)) + 1)
    if abs(dc) > 1e-12:
        span = max(span, int((cols - 1) / abs(dc)) + 1)
    return span


def _mask_numpy(grid, rows, cols, dr, dc, step_m, tan_alt):
    """Vectorised march: at each step k, gather the elevation k cells toward the
    sun and OR-in any cell whose angle to it exceeds the sun altitude."""
    Z = _np.asarray(grid, dtype=float)
    r_idx = _np.arange(rows)[:, None]
    c_idx = _np.arange(cols)[None, :]
    shadowed = _np.zeros((rows, cols), dtype=bool)
    for k in range(1, _max_steps(rows, cols, dr, dc) + 1):
        rr = _np.round(r_idx + k * dr).astype(_np.intp)
        cc = _np.round(c_idx + k * dc).astype(_np.intp)
        valid = (rr >= 0) & (rr < rows) & (cc >= 0) & (cc < cols)
        zk = Z[_np.clip(rr, 0, rows - 1), _np.clip(cc, 0, cols - 1)]
        # Elevation angle to the sample exceeds the sun altitude ⇒ blocked.
        shadowed |= valid & ((zk - Z) > tan_alt * (k * step_m))
    return shadowed.astype(float).tolist()


def _mask_python(grid, rows, cols, dr, dc, step_m, tan_alt):
    """Pure-Python fallback — same result as ``_mask_numpy`` (identical rounding
    and blocked test), with a per-cell early break on the first blocker / once
    the ray walks off the grid toward the sun."""
    out = [[0.0] * cols for _ in range(rows)]
    for r in range(rows):
        grow = grid[r]
        for c in range(cols):
            z0 = grow[c]
            k = 1
            while True:
                rr = int(round(r + k * dr))
                cc = int(round(c + k * dc))
                if rr < 0 or rr >= rows or cc < 0 or cc >= cols:
                    break               # walked off the grid toward the sun
                if (grid[rr][cc] - z0) > tan_alt * (k * step_m):
                    out[r][c] = 1.0
                    break               # first blocker is enough
                k += 1
    return out

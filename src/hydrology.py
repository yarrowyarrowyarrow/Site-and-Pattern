"""
hydrology.py — Where the water actually goes: D8 flow routing + accumulation.

Design principle P5 (perception is constructed — make invisible ecology
visible) — see docs/DESIGN_PHILOSOPHY.md. Rain is invisible on a flat map;
this module turns the site's elevation grid into the two things a designer
can act on (P8 — repair): where runoff *concentrates* (swale / rain-garden
sites, erosion risk) and where it *ponds* (moisture-loving beds, or a
drainage problem). Honesty note (P9): the result is only as fine as the DEM —
Edmonton's 0.5 m LiDAR contours resolve yard-scale flow; the 30 m Copernicus
DEM elsewhere shows broad drainage patterns, not the swale by your fence.

Pure Python, Qt-free, no network. Consumes the same elevation-grid dict the
slope ramp uses (``{"grid", "rows", "cols", "bbox"}``, row 0 = north edge,
col 0 = west edge — see terrain.py) and mirrors its cell-spacing derivation
so the water raster aligns cell-for-cell with the slope raster.

Method: priority-flood depression filling (Barnes et al. 2014, the epsilon
variant so filled flats still drain), then D8 steepest-descent receivers on
the filled surface, then a single high→low accumulation pass. O(n log n) in
grid cells; the grids here are ≤ 10,000 cells (terrain._MAX_GRID_CELLS).
"""

from __future__ import annotations

import heapq
import math
from typing import Optional

from src.terrain import bbox_size_m, encode_png_rgba

# A cell counts as "ponding" when the fill pass had to raise it by more than
# this depth (metres). Below it, treat as DEM noise rather than a basin.
PONDING_MIN_DEPTH_M = 0.05

# Tiny gradient imposed across filled flats so they drain to their spill
# point instead of stalling the D8 pass (Barnes' epsilon variant).
_FILL_EPS = 1e-6

# 8-neighbour offsets (dr, dc): N, NE, E, SE, S, SW, W, NW in grid terms
# (row 0 = north, so dr=-1 means north).
_D8 = [(-1, 0), (-1, 1), (0, 1), (1, 1), (1, 0), (1, -1), (0, -1), (-1, -1)]


def _cell_size_m(elev: dict) -> tuple[float, float]:
    """(dx, dy) metres per cell — the exact derivation compute_slope_grid
    uses, so all terrain rasters stay aligned."""
    width_m, height_m = bbox_size_m(elev["bbox"])
    dx = width_m / max(1, elev["cols"] - 1)
    dy = height_m / max(1, elev["rows"] - 1)
    return dx, dy


def fill_depressions(elev: dict) -> tuple[list[list[float]], list[list[float]]]:
    """Priority-flood the grid from its border inward.

    Returns ``(filled, depth)``: the depression-filled surface (with the
    epsilon gradient across flats) and the per-cell fill depth in metres
    (``filled - original``, ≥ 0). Cells the flood raised are closed basins —
    where water would pond before spilling.
    """
    grid = elev["grid"]
    rows, cols = elev["rows"], elev["cols"]
    filled = [[0.0] * cols for _ in range(rows)]
    visited = [[False] * cols for _ in range(rows)]
    heap: list = []

    for r in range(rows):
        for c in range(cols):
            if r in (0, rows - 1) or c in (0, cols - 1):
                visited[r][c] = True
                filled[r][c] = float(grid[r][c])
                heapq.heappush(heap, (filled[r][c], r, c))

    while heap:
        z, r, c = heapq.heappop(heap)
        for dr, dc in _D8:
            nr, nc = r + dr, c + dc
            if nr < 0 or nr >= rows or nc < 0 or nc >= cols:
                continue
            if visited[nr][nc]:
                continue
            visited[nr][nc] = True
            filled[nr][nc] = max(float(grid[nr][nc]), z + _FILL_EPS)
            heapq.heappush(heap, (filled[nr][nc], nr, nc))

    depth = [[max(0.0, filled[r][c] - float(grid[r][c])) for c in range(cols)]
             for r in range(rows)]
    return filled, depth


def d8_receivers(filled: list[list[float]], rows: int, cols: int,
                 dx: float, dy: float) -> list[list[Optional[tuple]]]:
    """Steepest-descent neighbour per cell on the filled surface.

    ``None`` where no neighbour is lower — after the epsilon fill that only
    happens on border cells, which drain off-grid.
    """
    diag = math.hypot(dx, dy)
    dist = {(-1, 0): dy, (1, 0): dy, (0, 1): dx, (0, -1): dx,
            (-1, 1): diag, (1, 1): diag, (1, -1): diag, (-1, -1): diag}
    out: list[list[Optional[tuple]]] = [[None] * cols for _ in range(rows)]
    for r in range(rows):
        for c in range(cols):
            best = 0.0
            best_rc = None
            z = filled[r][c]
            for dr, dc in _D8:
                nr, nc = r + dr, c + dc
                if nr < 0 or nr >= rows or nc < 0 or nc >= cols:
                    continue
                drop = (z - filled[nr][nc]) / dist[(dr, dc)]
                if drop > best:
                    best = drop
                    best_rc = (nr, nc)
            out[r][c] = best_rc
    return out


def flow_accumulation(elev: dict) -> dict:
    """The public entry point: route the grid's rain downhill.

    Returns::

        {"accum":     [[m² of upstream area draining through each cell]],
         "receivers": [[(r, c) | None]],
         "ponding":   [[bool]]  (fill depth > PONDING_MIN_DEPTH_M),
         "cell_area_m2": float,
         "n_ponding": int}
    """
    rows, cols = elev["rows"], elev["cols"]
    dx, dy = _cell_size_m(elev)
    cell_area = dx * dy

    filled, depth = fill_depressions(elev)
    receivers = d8_receivers(filled, rows, cols, dx, dy)

    accum = [[cell_area] * cols for _ in range(rows)]
    order = sorted(((filled[r][c], r, c)
                    for r in range(rows) for c in range(cols)),
                   reverse=True)
    for _z, r, c in order:
        rec = receivers[r][c]
        if rec is not None:
            accum[rec[0]][rec[1]] += accum[r][c]

    ponding = [[depth[r][c] > PONDING_MIN_DEPTH_M for c in range(cols)]
               for r in range(rows)]
    return {
        "accum": accum,
        "receivers": receivers,
        "ponding": ponding,
        "cell_area_m2": cell_area,
        "n_ponding": sum(1 for row in ponding for v in row if v),
    }


# ── Rendering: translucent blue accumulation raster ─────────────────────────
# Log-scaled: accumulation spans orders of magnitude, and the interesting
# structure (channels vs sheets) lives in the ratios. Cells with fewer than
# _MIN_UPSTREAM_CELLS upstream stay transparent so ridges don't tint.

_MIN_UPSTREAM_CELLS = 3.0

# (t upper bound in [0,1], RGBA) — light wash → channel blue; first match wins.
_WATER_RAMP = [
    (0.35, (100, 181, 246, 60)),
    (0.70, (33, 150, 243, 105)),
    (1.01, (13, 71, 161, 150)),
]
_PONDING_RGBA = (0, 137, 123, 160)     # teal — closed basin / ponding


def water_ramp_rgba(accum: list[list[float]], ponding: list[list[bool]],
                    cell_area_m2: float) -> tuple[bytes, int, int]:
    """Row-major RGBA bytes for the accumulation raster (mirrors
    terrain.slope_ramp_rgba's contract; feed to terrain.encode_png_rgba)."""
    h = len(accum)
    w = len(accum[0]) if h else 0
    floor = _MIN_UPSTREAM_CELLS * cell_area_m2
    max_a = max((v for row in accum for v in row), default=0.0)
    log_span = math.log(max_a / floor) if max_a > floor else 1.0
    out = bytearray(w * h * 4)
    for y, row in enumerate(accum):
        for x, a in enumerate(row):
            if ponding[y][x]:
                rgba = _PONDING_RGBA
            elif a <= floor or log_span <= 0:
                rgba = (0, 0, 0, 0)
            else:
                t = min(1.0, math.log(a / floor) / log_span)
                for upper, cand in _WATER_RAMP:
                    if t < upper:
                        rgba = cand
                        break
                else:
                    rgba = _WATER_RAMP[-1][1]
            i = (y * w + x) * 4
            out[i], out[i + 1], out[i + 2], out[i + 3] = rgba
    return bytes(out), w, h


def water_png(elev: dict, flow: dict) -> bytes:
    """Accumulation raster as PNG bytes, ready for the map image overlay."""
    rgba, w, h = water_ramp_rgba(flow["accum"], flow["ponding"],
                                 flow["cell_area_m2"])
    return encode_png_rgba(rgba, w, h)


# ── Rendering: sparse downhill arrows ────────────────────────────────────────

def flow_arrows(elev: dict, flow: dict, cap: int = 120) -> list[dict]:
    """A sparse lattice of downhill arrows for the map: at most ``cap``
    entries ``{"lat", "lng", "bearing", "strength"}`` (bearing = compass
    degrees the water moves toward; strength 0–1, log-scaled accumulation).
    Cells with little upstream area are skipped so ridges stay clean."""
    rows, cols = elev["rows"], elev["cols"]
    bbox = elev["bbox"]
    dx, dy = _cell_size_m(elev)
    accum, receivers = flow["accum"], flow["receivers"]
    cell_area = flow["cell_area_m2"]
    floor = _MIN_UPSTREAM_CELLS * cell_area
    max_a = max((v for row in accum for v in row), default=0.0)
    log_span = math.log(max_a / floor) if max_a > floor else 1.0

    stride = max(1, int(math.ceil(math.sqrt((rows * cols) / max(1, cap)))))
    lat_span = bbox["north"] - bbox["south"]
    lng_span = bbox["east"] - bbox["west"]

    out: list[dict] = []
    for r in range(stride // 2, rows, stride):
        for c in range(stride // 2, cols, stride):
            a = accum[r][c]
            rec = receivers[r][c]
            if rec is None or a <= floor or log_span <= 0:
                continue
            east_m = (rec[1] - c) * dx
            north_m = (r - rec[0]) * dy          # +row = south, so invert
            bearing = math.degrees(math.atan2(east_m, north_m)) % 360.0
            t = min(1.0, math.log(a / floor) / log_span)
            out.append({
                "lat": bbox["north"] - (r / max(1, rows - 1)) * lat_span,
                "lng": bbox["west"] + (c / max(1, cols - 1)) * lng_span,
                "bearing": round(bearing, 1),
                "strength": round(t, 3),
            })
            if len(out) >= cap:
                return out
    return out

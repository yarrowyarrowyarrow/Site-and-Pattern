"""
layout.py — Plant-group layout patterns for the design generator (V1.50).

Pure-Python ports of the row / grid / circle / scatter math that lived only
JS-side in ``html/map.html`` (``_rowPositions``, ``_gridPositions``,
``_circlePositions`` / ``_hexPackedDisc``, ``_hexBurstPositions``). The
interactive map computes those from two user clicks; the generator instead
places a group of ``count`` plants *centred on a point* it chose inside the
boundary, so these helpers take ``(center_lat, center_lng, count, spacing_m)``
and return ``[(lat, lng), …]``.

Qt-free, no deps. Metre→degree uses the same local cos-lat projection as the
rest of the app (``/111320`` lat, ``/(111320·cosLat)`` lng) so positions line up
with ``llm_design`` placement and ``geometry.point_in_polygon`` clipping.

The patterns the LLM can request (see ``llm_design._SYSTEM_PROMPT``):

  * ``row``     — a straight line, good for hedges and bed edges.
  * ``grid``    — a rectangular block (mass planting / formal block).
  * ``circle``  — a hex-packed disc (a feature specimen or herb circle).
  * ``scatter`` — a natural-looking jittered cluster (accents).
  * ``drift``   — an elongated, flowing patch of one species, the Rainer/West
                  "designed plant communities" / Oudolf look (design principle P2:
                  the best designs look like they grew there). The naturalistic
                  default for grasses and forbs.

All are deterministic (``scatter`` / ``drift`` use a seeded RNG) so a given group
lays out the same way every run — important for tests and reproducibility.

Design principle P2 (the best designs disappear into their context) — see
docs/DESIGN_PHILOSOPHY.md.
"""

from __future__ import annotations

import math
import random

_M_PER_DEG = 111320.0

# Canonical pattern names. ``LAYOUTS`` is the validated set the spec accepts.
ROW = "row"
GRID = "grid"
CIRCLE = "circle"
SCATTER = "scatter"
DRIFT = "drift"
LAYOUTS = frozenset({ROW, GRID, CIRCLE, SCATTER, DRIFT})


def _cos_lat(lat: float) -> float:
    return math.cos(lat * math.pi / 180) or 1e-9


def _offset(center_lat: float, center_lng: float,
            dx_m: float, dy_m: float) -> tuple[float, float]:
    """Translate a metre offset (east = +dx, north = +dy) from a centre to
    (lat, lng) using the local cos-lat projection."""
    return (center_lat + dy_m / _M_PER_DEG,
            center_lng + dx_m / (_M_PER_DEG * _cos_lat(center_lat)))


def row_positions(center_lat: float, center_lng: float, count: int,
                  spacing_m: float, *, bearing_deg: float = 90.0
                  ) -> list[tuple[float, float]]:
    """``count`` points on a straight line through the centre at ``spacing_m``
    centre-to-centre. ``bearing_deg`` is the line direction (90 = E–W, the
    default; 0 = N–S). The row is centred on ``(center_lat, center_lng)``."""
    count = max(1, int(count))
    if count == 1:
        return [(center_lat, center_lng)]
    rad = math.radians(bearing_deg)
    ux, uy = math.sin(rad), math.cos(rad)   # bearing 0 = north (+y)
    half = (count - 1) / 2.0
    out = []
    for i in range(count):
        d = (i - half) * spacing_m
        out.append(_offset(center_lat, center_lng, ux * d, uy * d))
    return out


def grid_positions(center_lat: float, center_lng: float, count: int,
                   spacing_m: float, *, stagger: bool = True,
                   aspect: float = 1.0) -> list[tuple[float, float]]:
    """``count`` points on a rectangular grid centred on the point. Columns are
    derived to keep the block roughly ``aspect`` (width/height) shaped; when
    ``stagger`` every other row shifts half a column for a hex-ish pack. Returns
    exactly ``count`` points (row-major), so the caller gets what it asked for."""
    count = max(1, int(count))
    cols = max(1, int(round(math.sqrt(count * max(aspect, 0.1)))))
    rows = max(1, math.ceil(count / cols))
    # Centre the block: offsets span [-(n-1)/2 … +(n-1)/2] * spacing.
    half_c = (cols - 1) / 2.0
    half_r = (rows - 1) / 2.0
    out: list[tuple[float, float]] = []
    for r in range(rows):
        row_off = (spacing_m / 2.0) if (stagger and r % 2) else 0.0
        for c in range(cols):
            if len(out) >= count:
                break
            dx = (c - half_c) * spacing_m + row_off
            dy = (half_r - r) * spacing_m   # row 0 at the top (north)
            out.append(_offset(center_lat, center_lng, dx, dy))
    return out


def _hex_packed_disc(center_lat: float, center_lng: float, radius_m: float,
                     spacing_m: float) -> list[tuple[float, float]]:
    """Honeycomb hex-pack inside a disc (port of JS ``_hexPackedDisc``). Centre
    point first, then rings; every interior point has six neighbours at
    ``spacing_m``."""
    s = max(spacing_m, 0.01)
    row_spacing = s * math.sqrt(3) / 2.0
    max_row = math.ceil(radius_m / row_spacing) + 1
    max_col = math.ceil(radius_m / s) + 1
    r2 = radius_m * radius_m + 1e-3
    out: list[tuple[float, float]] = [(center_lat, center_lng)]
    for ri in range(-max_row, max_row + 1):
        y = ri * row_spacing
        row_off = (s / 2.0) if (ri & 1) else 0.0
        for ci in range(-max_col, max_col + 1):
            x = ci * s + row_off
            if x * x + y * y <= r2:
                if abs(x) < 1e-6 and abs(y) < 1e-6:
                    continue   # centre already emitted
                out.append(_offset(center_lat, center_lng, x, y))
    return out


def circle_positions(center_lat: float, center_lng: float, count: int,
                     spacing_m: float, *, fill: bool = True
                     ) -> list[tuple[float, float]]:
    """``count`` points arranged as a disc (``fill=True``, hex-packed, centre
    first) or a single perimeter ring (``fill=False``). The radius is sized to
    hold ``count`` points at ``spacing_m`` so groups don't overlap their
    neighbours."""
    count = max(1, int(count))
    if count == 1:
        return [(center_lat, center_lng)]
    if fill:
        # Area ≈ count · s²  → radius ≈ s·sqrt(count/π); grow a touch, then trim
        # to exactly count, closest-to-centre first (matches the JS cap).
        radius_m = max(spacing_m, spacing_m * math.sqrt(count / math.pi) * 1.15)
        disc = _hex_packed_disc(center_lat, center_lng, radius_m, spacing_m)
        if len(disc) > count:
            cl = _cos_lat(center_lat)

            def _d2(p):
                dx = (p[1] - center_lng) * _M_PER_DEG * cl
                dy = (p[0] - center_lat) * _M_PER_DEG
                return dx * dx + dy * dy
            disc.sort(key=_d2)
            disc = disc[:count]
        return disc
    # Perimeter ring sized so neighbours sit ~spacing_m apart.
    radius_m = max(spacing_m, (count * spacing_m) / (2 * math.pi))
    out = []
    for k in range(count):
        theta = 2 * math.pi * k / count
        out.append(_offset(center_lat, center_lng,
                            radius_m * math.sin(theta),
                            radius_m * math.cos(theta)))
    return out


def scatter_positions(center_lat: float, center_lng: float, count: int,
                      spacing_m: float, *, seed: int = 0
                      ) -> list[tuple[float, float]]:
    """``count`` naturalistic points: a jittered hex-pack disc so plants look
    informally clustered rather than gridded, while keeping a rough minimum
    separation. Deterministic for a given ``seed``."""
    count = max(1, int(count))
    if count == 1:
        return [(center_lat, center_lng)]
    rng = random.Random(seed)
    # Start from a slightly oversized disc, jitter each point up to ±35% of the
    # spacing, then take the requested count.
    base = circle_positions(center_lat, center_lng, int(count * 1.4) + 1,
                            spacing_m, fill=True)
    out = []
    j = spacing_m * 0.35
    for (lat, lng) in base[:count]:
        dx = rng.uniform(-j, j)
        dy = rng.uniform(-j, j)
        out.append(_offset(lat, lng, dx, dy))
    return out


def drift_positions(center_lat: float, center_lng: float, count: int,
                    spacing_m: float, *, seed: int = 0,
                    bearing_deg: float | None = None,
                    aspect: float = 2.6) -> list[tuple[float, float]]:
    """``count`` points in an elongated, organic *drift* — the Rainer/West
    "designed plant communities" / Oudolf look: a flowing, overlapping patch of
    one species that reads as if it seeded itself, rather than a grid or an even
    scatter. Points hex-pack inside an ellipse whose long axis runs along
    ``bearing_deg`` (seeded-random when ``None``), elongated by ``aspect``
    (long/short), then get a light jitter. Deterministic for a given ``seed``."""
    count = max(1, int(count))
    if count == 1:
        return [(center_lat, center_lng)]
    rng = random.Random(seed)
    if bearing_deg is None:
        bearing_deg = rng.uniform(0.0, 180.0)
    aspect = max(1.0, float(aspect))
    s = max(spacing_m, 0.01)
    # Ellipse sized to hold ~count points: area π·a·b ≈ count·s², a/b = aspect.
    # Oversize a touch so the hex-pack yields at least `count` before trimming.
    a = max(s, s * math.sqrt(count * aspect / math.pi)) * 1.12
    b = a / aspect
    row_spacing = s * math.sqrt(3) / 2.0
    max_row = math.ceil(a / row_spacing) + 1
    max_col = math.ceil(a / s) + 1
    local: list[tuple[float, float]] = []
    for ri in range(-max_row, max_row + 1):
        y = ri * row_spacing
        row_off = (s / 2.0) if (ri & 1) else 0.0
        for ci in range(-max_col, max_col + 1):
            x = ci * s + row_off
            if (x * x) / (a * a) + (y * y) / (b * b) <= 1.0 + 1e-9:
                local.append((x, y))
    # Keep the `count` points closest to the centre (a filled drift, not a ring).
    local.sort(key=lambda p: p[0] * p[0] + p[1] * p[1])
    local = local[:count]
    rad = math.radians(bearing_deg)
    sin_r, cos_r = math.sin(rad), math.cos(rad)
    j = s * 0.30
    out: list[tuple[float, float]] = []
    for (x, y) in local:
        jx = x + rng.uniform(-j, j)
        jy = y + rng.uniform(-j, j)
        # Rotate so the major axis (local x) runs along the bearing (0° = north):
        # east = x·sinθ + y·cosθ, north = x·cosθ − y·sinθ.
        east = jx * sin_r + jy * cos_r
        north = jx * cos_r - jy * sin_r
        out.append(_offset(center_lat, center_lng, east, north))
    return out


def positions_for_layout(layout: str, center_lat: float, center_lng: float,
                         count: int, spacing_m: float
                         ) -> list[tuple[float, float]]:
    """Dispatch to the requested pattern. Unknown / empty ``layout`` falls back
    to ``scatter`` (the safe, natural default)."""
    layout = (layout or "").lower().strip()
    if layout == ROW:
        return row_positions(center_lat, center_lng, count, spacing_m)
    if layout == GRID:
        return grid_positions(center_lat, center_lng, count, spacing_m)
    if layout == CIRCLE:
        return circle_positions(center_lat, center_lng, count, spacing_m)
    if layout == DRIFT:
        return drift_positions(center_lat, center_lng, count, spacing_m)
    return scatter_positions(center_lat, center_lng, count, spacing_m)


def default_layout_for(plant_type: str) -> str:
    """Deterministic pattern when the LLM doesn't specify one — by habit:
    trees space out on a grid, shrubs cluster in circles, grasses/forbs lay out
    as naturalistic drifts, edges/groundcover run in rows."""
    pt = (plant_type or "").lower()
    if pt == "tree":
        return GRID
    if pt == "shrub":
        return CIRCLE
    if pt in ("grass", "sedge", "rush", "herb", "root", "fern"):
        return DRIFT
    if pt in ("groundcover", "vine"):
        return ROW
    return DRIFT

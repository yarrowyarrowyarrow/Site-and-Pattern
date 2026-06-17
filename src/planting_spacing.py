"""
src/planting_spacing.py — layer/type-aware, spread-aware planting spacing (F22 / F35).

A naturalistic planting is not one even grid: trees are spaced widest, then
shrubs, then perennials, with groundcover knitting the ground tightest — and
self-spreading species (F35, ``spread_habit``) are spaced wider still because
they fill the gaps over time. This Qt-free engine is shared by:

  * the community builder's "Auto-arrange by layer" (:func:`arrange_concentric`), and
  * Fill Area matrix planting per type (:func:`layered_fill_plan`).

Design principle P2 (the best designs disappear into their context) — see
docs/DESIGN_PHILOSOPHY.md.
"""

from __future__ import annotations

import math
import random

# Spacing multiplier by plant_type, relative to the ground/base unit (1.0).
TYPE_FACTOR: dict[str, float] = {
    "groundcover": 1.0,
    "grass": 1.3, "sedge": 1.3, "rush": 1.3, "fern": 1.3,
    "herb": 1.8, "root": 1.8,
    "vine": 2.5,
    "shrub": 4.0,
    "tree": 10.0,
}
_FALLBACK_FACTOR = 1.5

# F35: self-spreaders fill in over time, so they're planted sparser.
SPREAD_FACTOR: dict[str, float] = {
    "": 1.0, "clumping": 1.0,
    "slow_spreader": 1.3,
    "self_seeding": 1.6,
    "aggressive_rhizomatous": 2.0,
}

# Vegetation-layer buckets, tallest → ground (the placement order).
LAYER_ORDER = ("canopy", "shrub", "perennial", "ground")

# plant_type → bucket.
_TYPE_LAYER = {
    "tree": "canopy",
    "shrub": "shrub", "vine": "shrub",
    "herb": "perennial", "root": "perennial", "grass": "perennial",
    "sedge": "perennial", "rush": "perennial", "fern": "perennial",
    "groundcover": "ground",
}
# community-member vegetation `layer` value → bucket.
_VEGLAYER_BUCKET = {
    "overstory": "canopy", "understory": "shrub", "shrub_layer": "shrub",
    "groundcover": "ground", "herbaceous": "perennial", "vine": "perennial",
    "root": "perennial",
}
# Minimum sensible spacing per bucket — guarantees tree > shrub > perennial >
# ground ordering even when a record carries no/placeholder spacing.
LAYER_MIN_SPACING = {"canopy": 3.0, "shrub": 1.2, "perennial": 0.5, "ground": 0.3}


def _type(rec) -> str:
    return (rec.get("plant_type") or "").strip().lower()


def layer_of(plant_type: str) -> str:
    """Vegetation-layer bucket for a plant_type (canopy/shrub/perennial/ground)."""
    return _TYPE_LAYER.get((plant_type or "").strip().lower(), "perennial")


def bucket_for_member(m) -> str:
    """Bucket for a community member: its assigned vegetation ``layer`` wins
    (the user set it), else fall back to its plant_type."""
    veg = (m.get("layer") or "").strip().lower()
    if veg in _VEGLAYER_BUCKET:
        return _VEGLAYER_BUCKET[veg]
    return layer_of(m.get("plant_type") or "")


def spread_factor(rec) -> float:
    return SPREAD_FACTOR.get((rec.get("spread_habit") or "").strip().lower(), 1.0)


def plant_spacing(rec, base_m: float) -> float:
    """Centre-to-centre spacing (m) for one plant given the ground/base spacing:
    ``base × per-type factor × spread factor``, floored to the plant's own mature
    canopy so it never overlaps itself. ``rec`` is a dict with ``plant_type`` and
    optionally ``spread_habit`` / ``mature_canopy_m``."""
    base = max(0.05, float(base_m or 1.0))
    s = base * TYPE_FACTOR.get(_type(rec), _FALLBACK_FACTOR) * spread_factor(rec)
    canopy = rec.get("mature_canopy_m")
    if canopy:
        s = max(s, float(canopy))
    return round(s, 3)


# ── Community auto-arrange (concentric by layer) ─────────────────────────────

def _member_spacing(m) -> float:
    bucket = bucket_for_member(m)
    return max(float(m.get("spacing_m") or 0.0), LAYER_MIN_SPACING.get(bucket, 0.5))


def _canopy_offsets(n: int, sp: float):
    """Trees: 1 → centred; n → a ring, equidistant from the centre and each
    other. Returns ``([(x, y), …], outer_radius)``."""
    if n <= 0:
        return [], 0.0
    if n == 1:
        return [(0.0, 0.0)], sp / 2.0
    r = max(sp / 2.0, sp / (2.0 * math.sin(math.pi / n)))
    offs = [(r * math.cos(2 * math.pi * k / n), r * math.sin(2 * math.pi * k / n))
            for k in range(n)]
    return offs, r


def _ring_offsets(n: int, sp: float, base_r: float):
    """``n`` points on concentric rings from ``base_r`` outward, ~``sp`` apart
    along each ring and between rings. Returns ``([(x, y), …], outer_radius)``."""
    out: list = []
    placed = 0
    r = max(base_r, sp)
    ring = 0
    while placed < n:
        cap = max(1, int((2 * math.pi * r) // sp))
        cnt = min(cap, n - placed)
        ang0 = (math.pi / cnt) if (ring % 2) else 0.0   # stagger alternate rings
        for k in range(cnt):
            ang = 2 * math.pi * k / cnt + ang0
            out.append((r * math.cos(ang), r * math.sin(ang)))
        placed += cnt
        r += sp
        ring += 1
    return out, r - sp


def arrange_concentric(members, max_radius_m: float | None = None):
    """Lay community ``members`` out by layer: tree(s) centred, shrubs ringed
    around them, perennials in the next band, groundcover filling the outer band.
    Returns ``(members_with_offsets, radius_m)`` — ``radius_m`` is how far out the
    arrangement reaches, so the builder can grow the canvas to fit.

    ``max_radius_m`` caps how far the arrangement spreads outward: when the
    natural layout reaches past it, every offset is scaled in proportionally so
    the whole community fits within the cap (the layer rings are preserved, just
    drawn tighter). ``None`` leaves the natural radius untouched."""
    members = [dict(m) for m in members]
    buckets: dict[str, list] = {b: [] for b in LAYER_ORDER}
    for m in members:
        buckets[bucket_for_member(m)].append(m)

    out: list = []
    r_cursor = 0.0
    for layer in LAYER_ORDER:
        items = buckets[layer]
        if not items:
            continue
        sp = max((_member_spacing(m) for m in items), default=1.0)
        if layer == "canopy":
            offs, outer = _canopy_offsets(len(items), sp)
        else:
            offs, outer = _ring_offsets(len(items), sp, r_cursor + sp)
        for m, (x, y) in zip(items, offs):
            m["offset_x"] = round(x, 2)
            m["offset_y"] = round(y, 2)
            out.append(m)
        r_cursor = max(r_cursor, outer)

    if max_radius_m and r_cursor > max_radius_m > 0:
        scale = max_radius_m / r_cursor
        for m in out:
            m["offset_x"] = round(m["offset_x"] * scale, 2)
            m["offset_y"] = round(m["offset_y"] * scale, 2)
        r_cursor = max_radius_m
    return out, round(r_cursor, 2)


# ── Layered fill (per-type spacing over a polygon) ───────────────────────────

def _dist_m(lat1, lng1, lat2, lng2) -> float:
    dlat = (lat2 - lat1) * 111320.0
    dlng = (lng2 - lng1) * 111320.0 * math.cos(math.radians((lat1 + lat2) / 2.0))
    return math.hypot(dlat, dlng)


def layered_fill_plan(ring, typed_members, base_m: float, rng=None,
                      jitter: float = 0.6) -> list:
    """Fill a polygon ``ring`` (``[lng, lat]`` pairs) layer by layer, each at its
    own spacing: trees sparse, shrubs medium, perennials denser, groundcover
    knitting the rest (matrix). Taller plants reserve their footprint so shorter
    layers don't sit on top of them; groundcover still knits up close.

    ``typed_members`` are dicts with ``plant_id``, ``plant_type`` (and optionally
    ``spread_habit``, ``mature_canopy_m``, ``weight``, ``layer_bucket``).
    Returns ``[(plant_id, lat, lng), …]``."""
    from src import area_fill
    if not ring or not typed_members:
        return []
    rng = rng or random.Random(0)

    by_layer: dict[str, list] = {b: [] for b in LAYER_ORDER}
    for tm in typed_members:
        bucket = tm.get("layer_bucket") or layer_of(tm.get("plant_type"))
        by_layer.get(bucket, by_layer["perennial"]).append(tm)

    records: list = []
    placed_taller: list = []   # (lat, lng, reserve_m) of already-placed taller plants
    for layer in LAYER_ORDER:
        items = by_layer[layer]
        if not items:
            continue
        sp = max(plant_spacing(tm, base_m) for tm in items)
        pts = area_fill.fill_points(ring, sp, jitter, rng)
        if placed_taller and pts:
            # Ground knits right up to taller stems (small clearance); taller
            # layers keep clear of each taller plant's reserved footprint.
            kept = []
            for plat, plng in pts:
                ok = True
                for tlat, tlng, reserve in placed_taller:
                    clr = 0.4 if layer == "ground" else reserve
                    if _dist_m(plat, plng, tlat, tlng) < clr:
                        ok = False
                        break
                if ok:
                    kept.append((plat, plng))
            pts = kept
        if not pts:
            continue
        specs = [(tm["plant_id"], float(tm.get("weight") or 1.0)) for tm in items]
        assigned = area_fill.assign_members(pts, specs)
        records.extend(assigned)
        if layer != "ground":
            reserve = sp * 0.5
            placed_taller.extend((lat, lng, reserve) for _pid, lat, lng in assigned)
    return records

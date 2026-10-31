"""
reference_layout.py — how a wild community sits on the ground (V3.39, F255).

Design principle P1 (living systems self-organize — encode generative rules,
not fixed layouts) — see docs/DESIGN_PHILOSOPHY.md.

Until V3.39 the walks scattered every plant uniformly at random over a 20 m
square: the grove was a few trees standing apart in a lawn of wildflowers, and
a prairie crocus stood under the spruce as often as in the sun. A community
grows the way its plants spread, and these are the rules here:

- **Trees in clumps.** An aspen clone's stems come up a couple of metres apart
  from one root; spruce and pine stand in a group. The first clump sits north
  of the centre, so its shade falls away from the open ground, and the others
  join it east and west, so a walk faces a grove or a forest edge across the
  open.
- **Shrubs in thickets** of two or three, around the grove's edge: just
  outside the crowns, or just inside them for a shrub of the shade.
- **Wildflowers in drifts** of three to five, single plants and pairs for the
  ones that are not the community's leads.
- **Grasses as the matrix between**, in patches of one species each.
- **Light decides who stands where.** A plant that needs full sun is never
  under a crown; a plant of the shade goes under one (bunchberry under the
  spruce), or beside a shrub where there are no trees.

The walker starts where the scene's origin is, the plants' centroid
(``scene_contract._scene_origin``, ``walkSpawn`` in
``html/scene3d/08-modes.js``). So the layout is centred on its own centroid, and
no tree or shrub stands within :data:`CLEARING_M` of it: a grove in the north
pulls the centroid north, so the clearing is moved after it until the two
agree.

Pure geometry over plain dicts, in metres east and north of the walk's centre;
:mod:`src.reference_ecosystem` decides what grows and turns the result into a
project.
"""

from __future__ import annotations

import math
import random
from typing import Optional

#: The share of a layer's plants that are its lead species; the other species
#: of its genera fill the rest as single plants and pairs.
LEAD_SHARE = 0.7
#: No tree or shrub within this many metres of the centre, where the walker
#: starts.
CLEARING_M = 3.0
#: A crown's width when the catalogue gives no width and no spacing.
_LAYER_CROWN_M = {"canopy": 7.0, "shrub": 2.0, "forb": 0.4, "grass": 0.4}
#: The sunflower's angle, which packs a clump's stems evenly from its middle.
_GOLDEN = math.pi * (3.0 - math.sqrt(5.0))
#: Group sizes: (lead species, the rest).
_THICKET = ((2, 3), (1, 2))
_DRIFT = ((3, 5), (1, 2))
_PATCH = ((4, 6), (1, 3))


def crown_m(row: dict, layer: str = "") -> float:
    """A plant's mature crown width in metres, as the scene draws it:
    ``mature_canopy_m``, else 1.5 times its spacing (the rule ``db.plants``
    fills the column with), else the layer's usual width."""
    for key, factor in (("mature_canopy_m", 1.0), ("spacing_m", 1.5)):
        try:
            value = float(row.get(key) or 0)
        except (TypeError, ValueError):
            value = 0.0
        if value > 0:
            return value * factor
    return _LAYER_CROWN_M.get(layer, 0.5)


def sun_of(row: dict) -> str:
    """``"sun"`` for a plant that needs full sun, ``"shade"`` for one of the
    shade, ``"any"`` for one that takes either or says nothing."""
    need = (row.get("sun_requirement") or "").lower()
    if not need:
        return "any"
    if "full_sun" not in need:
        return "shade"
    if "shade" not in need:
        return "sun"
    return "any"


def stem_gap(row: dict) -> float:
    """How far apart a clump's stems stand: under half the crown, 2 to 4 m,
    and closer for a poplar or aspen, whose stems are one clone's suckers."""
    gap = min(4.0, max(2.0, crown_m(row, "canopy") * 0.45))
    genus = (row.get("scientific_name") or "").split(" ")[0].lower()
    return gap * 0.7 if genus == "populus" else gap


class Ground:
    """What has been planted so far, and where the light falls."""

    def __init__(self, size_m: float, clear_at: tuple = (0.0, 0.0)):
        self.half = max(4.0, float(size_m) / 2.0)
        self.clear_at = (float(clear_at[0]), float(clear_at[1]))
        self.trees: list[tuple] = []      # (x, y, crown radius)
        self.shrubs: list[tuple] = []     # (x, y, crown radius)
        self.herbs: list[tuple] = []      # (x, y)

    def cover(self, x: float, y: float) -> float:
        """Distance to the nearest tree over that tree's crown radius: under
        1 is under a crown. Large where there are no trees."""
        best = 9.0
        for tx, ty, r in self.trees:
            best = min(best, math.hypot(x - tx, y - ty) / max(r, 0.1))
        return best

    def suits(self, x: float, y: float, sun: str) -> bool:
        cover = self.cover(x, y)
        if sun == "sun":
            return cover >= 1.0
        if sun == "shade":
            return cover <= 0.9 if self.trees else True
        return cover >= 0.6

    def in_shrub(self, x: float, y: float, share: float = 0.85) -> bool:
        return any(math.hypot(x - sx, y - sy) < r * share
                   for sx, sy, r in self.shrubs)

    def near_trunk(self, x: float, y: float, within: float) -> bool:
        return any(math.hypot(x - tx, y - ty) < within
                   for tx, ty, _r in self.trees)

    def clamp(self, x: float, y: float, margin: float) -> tuple:
        lim = max(0.0, self.half - margin)
        return max(-lim, min(lim, x)), max(-lim, min(lim, y))

    def in_clearing(self, x: float, y: float, extra: float = 0.0) -> bool:
        return math.hypot(x - self.clear_at[0],
                          y - self.clear_at[1]) < CLEARING_M + extra

    def out_of_clearing(self, x: float, y: float) -> tuple:
        cx, cy = self.clear_at
        dx, dy = x - cx, y - cy
        d = math.hypot(dx, dy)
        if d >= CLEARING_M:
            return x, y
        if d < 1e-6:
            return cx, cy + CLEARING_M
        return cx + dx * CLEARING_M / d, cy + dy * CLEARING_M / d

    def random_point(self, rng: random.Random, margin: float) -> tuple:
        lim = max(0.1, self.half - margin)
        return rng.uniform(-lim, lim), rng.uniform(-lim, lim)


def _split(count: int, n_leads: int, n_fill: int) -> tuple:
    """How many of a layer's plants are its leads and how many the rest."""
    if not n_leads:
        return 0, (count if n_fill else 0)
    if not n_fill:
        return count, 0
    lead = int(round(count * LEAD_SHARE))
    return lead, count - lead


def _sequence(rng, leads, fill, count, sizes) -> list[tuple]:
    """``(row, group size)`` in planting order. The leads' share is divided
    evenly among them, so every lead is planted, each share in groups of the
    lead size, the leads taking turns; then the rest, a small group of each in
    turn, until the layer's count is met."""
    n_lead, n_fill = _split(count, len(leads), len(fill))
    (lo, hi), (flo, fhi) = sizes
    per_lead = []
    for i, row in enumerate(leads):
        share = n_lead // len(leads) + (1 if i < n_lead % len(leads) else 0)
        groups = []
        while share > 0:
            size = share if share <= hi else min(share - lo, rng.randint(lo, hi))
            size = max(1, size)
            groups.append((row, size))
            share -= size
        per_lead.append(groups)
    out = []
    for turn in range(max((len(g) for g in per_lead), default=0)):
        out.extend(g[turn] for g in per_lead if turn < len(g))
    left, i = n_fill, 0
    while left > 0 and fill:
        size = min(left, rng.randint(flo, fhi))
        out.append((fill[i % len(fill)], size))
        left -= size
        i += 1
    return out


def _spot(ground: Ground, rng: random.Random, *, sun: str, margin: float,
          spread_from: list, woody: bool, target: Optional[float] = None,
          tries: int = 90) -> tuple:
    """The best of ``tries`` random points for a group's middle: one the light
    suits, clear of trunks and thickets, away from the other groups."""
    best, best_score = (0.0, 0.0), -math.inf
    for _ in range(tries):
        x, y = ground.random_point(rng, margin)
        score = rng.random() * 0.4
        if woody and ground.in_clearing(x, y, margin):
            score -= 100.0
        if target is not None:
            score -= 3.0 * abs(min(ground.cover(x, y), 3.0) - target)
        elif not ground.suits(x, y, sun):
            score -= 50.0
        if ground.near_trunk(x, y, 1.2 if woody else 0.8):
            score -= 20.0
        if ground.in_shrub(x, y, 1.0 if woody else 0.9):
            score -= 10.0
        if sun == "shade" and not ground.trees and ground.shrubs and not woody:
            score -= 0.3 * min(math.hypot(x - sx, y - sy)
                               for sx, sy, _r in ground.shrubs)
        if spread_from:
            score += 0.6 * min(6.0, min(math.hypot(x - gx, y - gy)
                                        for gx, gy in spread_from))
        if score > best_score:
            best, best_score = (x, y), score
    return best


def _clumps(ground, rng, leads, fill, count) -> list[tuple]:
    """The trees: each lead species a clump of its stems, the first north of
    the centre, the others joining it east and west in turn; any stems the
    leads do not fill go to the genera's other trees, one to three a clump."""
    groups = [(row, max(1, int(stems))) for row, stems in leads]
    left = count - sum(s for _r, s in groups)
    i = 0
    while left > 0 and (fill or groups):
        if fill:
            size = min(left, rng.randint(1, 3))
            groups.append((fill[i % len(fill)], size))
        else:
            row, stems = groups[i % len(groups)]
            groups[i % len(groups)] = (row, stems + 1)
            size = 1
        left -= size
        i += 1
    placed, clumps, side = [], [], 1
    for row, stems in groups:
        gap = stem_gap(row)
        unit = gap / 1.77
        radius = unit * math.sqrt(stems)
        if not clumps:
            cx, cy = ground.clear_at[0], ground.clear_at[1] + ground.half * 0.45
        else:
            ref = max(clumps, key=lambda c: c[0] * side)
            angle = (0.0 if side > 0 else math.pi) + rng.uniform(-0.5, 0.5)
            dist = ref[2] + radius + gap * 0.6
            cx, cy = (ref[0] + dist * math.cos(angle),
                      ref[1] + dist * math.sin(angle))
            side = -side
        cx, cy = ground.clamp(cx, cy, radius + 1.0)
        clumps.append((cx, cy, radius))
        crown = crown_m(row, "canopy") / 2.0
        for k in range(stems):
            r = unit * math.sqrt(k + 0.5)
            t = k * _GOLDEN + rng.uniform(-0.35, 0.35)
            x = cx + r * math.cos(t) + rng.uniform(-0.15, 0.15) * gap
            y = cy + r * math.sin(t) + rng.uniform(-0.15, 0.15) * gap
            x, y = ground.clamp(*ground.out_of_clearing(x, y), 1.0)
            ground.trees.append((x, y, crown))
            placed.append((row, x, y))
    return placed


def _thickets(ground, rng, leads, fill, count) -> list[tuple]:
    """The shrubs, two or three of a species together, where the grove meets
    the open (inside its edge for a shrub of the shade), or spread over the
    open where there are no trees."""
    placed, centres = [], []
    for row, size in _sequence(rng, leads, fill, count, _THICKET):
        crown = crown_m(row, "shrub")
        sun = sun_of(row)
        target = (0.7 if sun == "shade" else 1.2) if ground.trees else None
        cx, cy = _spot(ground, rng, sun=sun, margin=crown / 2 + 0.5,
                       spread_from=centres, woody=True, target=target)
        centres.append((cx, cy))
        step = min(2.6, max(0.8, crown * 0.7))
        turn = rng.uniform(0, 2 * math.pi)
        for k in range(size):
            if k == 0:
                x, y = cx, cy
            else:
                t = turn + (k - 1) * 2 * math.pi / max(1, size - 1)
                x = cx + step * math.cos(t) * rng.uniform(0.85, 1.15)
                y = cy + step * math.sin(t) * rng.uniform(0.85, 1.15)
            x, y = ground.clamp(*ground.out_of_clearing(x, y), crown / 2)
            ground.shrubs.append((x, y, crown / 2))
            placed.append((row, x, y))
    return placed


def _drifts(ground, rng, leads, fill, count) -> list[tuple]:
    """The wildflowers: a drift of three to five of a lead species along a
    line, singles and pairs of the rest, each where the light suits it."""
    placed, centres = [], []
    for row, size in _sequence(rng, leads, fill, count, _DRIFT):
        sun = sun_of(row)
        cx, cy = _spot(ground, rng, sun=sun, margin=0.6,
                       spread_from=centres, woody=False)
        centres.append((cx, cy))
        step = min(0.8, max(0.35, crown_m(row, "forb") * 1.3))
        axis = rng.uniform(0, math.pi)
        for k in range(size):
            along = (k - (size - 1) / 2.0) * step
            for _attempt in range(6):
                side = rng.uniform(-0.3, 0.3) * step
                x = cx + along * math.cos(axis) - side * math.sin(axis)
                y = cy + along * math.sin(axis) + side * math.cos(axis)
                x, y = ground.clamp(x, y, 0.3)
                if ground.suits(x, y, sun) and not ground.in_shrub(x, y):
                    break
                along *= 0.6
            ground.herbs.append((x, y))
            placed.append((row, x, y))
    return placed


def _matrix(ground, rng, leads, fill, count) -> list[tuple]:
    """The grasses: patches of four to six of a lead species, ones to threes
    of the rest, each patch where its light suits it and away from the
    others, its plants spread evenly inside it, so the ground between the
    drifts and thickets fills with grass."""
    placed, centres = [], []
    for row, size in _sequence(rng, leads, fill, count, _PATCH):
        sun = sun_of(row)
        cx, cy = _spot(ground, rng, sun=sun, margin=0.6,
                       spread_from=centres, woody=False)
        centres.append((cx, cy))
        reach = 0.8 + 0.3 * size
        for _k in range(size):
            best, best_score = (cx, cy), -math.inf
            for _try in range(14):
                t = rng.uniform(0, 2 * math.pi)
                r = reach * math.sqrt(rng.random())
                x, y = ground.clamp(cx + r * math.cos(t),
                                    cy + r * math.sin(t), 0.3)
                score = min(1.5, min((math.hypot(x - hx, y - hy)
                                      for hx, hy in ground.herbs),
                                     default=1.5))
                if (not ground.suits(x, y, sun) or ground.in_shrub(x, y)
                        or ground.near_trunk(x, y, 0.6)):
                    score -= 50.0
                if score > best_score:
                    best, best_score = (x, y), score
            ground.herbs.append(best)
            placed.append((row, best[0], best[1]))
    return placed


_FORMS = {"clump": _clumps, "edge": _thickets, "drift": _drifts,
          "matrix": _matrix}
_DEFAULT_FORM = {"canopy": "clump", "shrub": "edge", "forb": "drift",
                 "grass": "matrix"}


def _lay_out_once(layers: list, size_m: float, seed: int,
                  clear_at: tuple) -> list:
    ground = Ground(size_m, clear_at)
    out = []
    for index, spec in enumerate(layers):
        layer = spec.get("layer") or ""
        form = spec.get("form") or _DEFAULT_FORM.get(layer, "drift")
        place = _FORMS.get(form, _drifts)
        count = int(spec.get("count") or 0)
        leads = list(spec.get("leads") or [])
        fill = list(spec.get("fill") or [])
        if count <= 0 or not (leads or fill):
            continue
        rng = random.Random(seed * 101 + index)
        if place is not _clumps:
            leads = [row for row, _stems in leads]
        out.extend(place(ground, rng, leads, fill, count))
    return out


def _centroid(placed: list) -> tuple:
    if not placed:
        return 0.0, 0.0
    return (sum(x for _r, x, _y in placed) / len(placed),
            sum(y for _r, _x, y in placed) / len(placed))


def lay_out(layers: list[dict], *, size_m: float, seed: int = 7) -> list:
    """Where every plant of a community stands.

    ``layers`` is, in planting order (trees first: everything else reads the
    light under them), ``{"layer", "form", "count", "leads", "fill"}`` with
    ``leads`` a list of ``(row, stems)`` and ``fill`` a list of rows. Returns
    ``[(row, east_m, north_m)]`` with the plants' centroid at the origin,
    where the walker starts, and the clearing round it. The same input always
    gives the same layout."""
    clear = (0.0, 0.0)
    best, best_miss = [], math.inf
    for _round in range(5):
        placed = _lay_out_once(layers, size_m, seed, clear)
        cx, cy = _centroid(placed)
        miss = math.hypot(cx - clear[0], cy - clear[1])
        if miss < best_miss:
            best, best_miss = placed, miss
        if miss < 0.2:
            break
        clear = (cx, cy)
    cx, cy = _centroid(best)
    return [(row, x - cx, y - cy) for row, x, y in best]

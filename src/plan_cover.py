"""
plan_cover.py — Plan My Yard fills to a cover, not to a count (PY-4, V3.28;
docs/homeowner/07-plan-my-yard.md §4.6).

Design principle P9 — see docs/DESIGN_PHILOSOPHY.md.

The generator's density setting changed how many plants it placed and not how
much of the bed they covered (31%, 32%, 34% at sparse, balanced and full on a
15 x 10 m yard), and restricting the ground to a drawn bed collapsed a plan to
four or five plants. After the main pass, the critic and the top-ups, this
adds plants until the planted area's mature cover, measured exactly as the
overview measures it (``yard_overview.cover``), reaches the target the person
chose: **70%** for *Fill it now*, **40%** for *Over two or three summers* (O3,
Y3); the advanced densities aim for 25%, 45% and 70%.

What it adds: the design's own low and middle plants and the best-ranked dry
plants of its pool, the widest first (since V3.29; most numerous first before,
which filled with 22 cm violets), so a fill reads as more of the same; each at
the open spot
``OpenGround`` finds for it. It stops at the target, at the plant ceiling, or
when the next plants find no open ground, and says which.

Qt-free.
"""

from __future__ import annotations

from typing import Callable, Optional

#: The cover a plan aims for, by the answer given (O3, Y3; §4.7).
COVER_TARGETS = {"now": 0.70, "summers": 0.40,
                 "sparse": 0.25, "balanced": 0.45, "full": 0.70}
#: What the fill adds: the herbaceous layers only (V3.29: widest first, a fill
#: that could take shrubs filled a yard with 4.5 m chokecherries), and nothing
#: that needs standing water.
FILLER_TYPES = ("wildflower", "herb", "grass", "sedge", "rush", "fern",
                "groundcover")
#: How many kinds take turns in the fill.
FILLER_KINDS = 4
#: A plant spreading less than this once grown fills too little ground to
#: fill with while bigger ones are on offer (V3.29: 64 violets, 22 cm each,
#: added 2 m² to a 150 m² yard and sent a plan to the plant ceiling).
MIN_SPREAD_M = 0.4
#: How far down the ranked pool the fill looks for a filler, so it fills
#: with good plants and not with the widest anywhere in the catalogue.
POOL_FILLERS = 12
#: A spot that adds less new cover than this share of the plant's own spread
#: is not open ground: three in a row and the fill stops.
MIN_GAIN = 0.10
_MISSES = 4

STOP_TARGET, STOP_LIMIT, STOP_FULL = "target", "limit", "full"

#: What the dialog's estimate assumes of a plan's plants, measured on the
#: probe yard (``scripts/probe_plan_my_yard.py``, V3.28): a plant's grown
#: spread covers about 0.7 m² and costs about $9-$19.
TYPICAL_CANOPY_M2 = 0.7
TYPICAL_PRICE = (9.0, 19.0)


def target_for(density: str = "", cover: Optional[float] = None) -> float:
    """The cover a plan aims for: ``cover`` when given, else the density's."""
    if cover is not None:
        return max(0.0, min(0.95, float(cover)))
    return COVER_TARGETS.get((density or "balanced").lower(), 0.45)


def estimate(area_m2: float, target: float) -> dict:
    """``{"plants", "low", "high"}``: about how many plants a plan for
    ``area_m2`` at ``target`` cover places and what they cost, before the plan
    is made (07 §4.3), so the dialog can say *about*.

    Plants overlap as they grow, so cover rises as ``1 - exp(-n a / A)``, not
    in proportion to the count: ``n = -ln(1 - target) A / a``. On the probe
    yard it says about 260 and 110 where the plans placed 248 and 92; in one
    18 m² bed about 30 and 13 where they placed 20 to 74 and 11 to 34, by
    the plants they chose. Rounded (P9)."""
    import math
    if area_m2 <= 0 or target <= 0:
        return {"plants": 0, "low": 0, "high": 0}
    n = -math.log(1.0 - min(target, 0.95)) * area_m2 / TYPICAL_CANOPY_M2
    n = max(1, _round(n))
    lo, hi = TYPICAL_PRICE
    return {"plants": n, "low": _round(n * lo, money=True),
            "high": _round(n * hi, money=True)}


def _round(x: float, money: bool = False) -> int:
    """To 1 under 20, 5 under 100, 10 under 1,000, else 50 (money: 10, 50,
    100)."""
    steps = ((100, 10), (1000, 50), (float("inf"), 100)) if money else \
        ((20, 1), (100, 5), (1000, 10), (float("inf"), 50))
    for top, step in steps:
        if x < top:
            return int(round(x / step) * step)
    return int(x)


def fillers(project, pool: list, get_plant: Callable) -> list:
    """The rows the fill takes turns with: the design's own fillable plants,
    most numerous first, then the pool's, up to :data:`FILLER_KINDS`."""
    from src.zoning import needs_standing_water
    counts: dict = {}
    for p in project.placed_plants:
        counts[p.get("plant_id")] = counts.get(p.get("plant_id"), 0) + 1
    out, seen = [], set()

    def take(row):
        if (not row or row.get("id") in seen
                or (row.get("plant_type") or "") not in FILLER_TYPES
                or needs_standing_water(row)):
            return
        seen.add(row["id"])
        out.append(row)

    for pid, _n in sorted(counts.items(), key=lambda kv: -kv[1]):
        take(get_plant(pid))
    for row in pool[:POOL_FILLERS]:
        take(row)
    # The widest first (V3.29): the same cover in fewer plants, and a
    # variant's fill no longer runs into the plant ceiling on small ones.
    from src.yard_overview import canopy_m
    wide = sorted((r for r in out if canopy_m(r) >= MIN_SPREAD_M),
                  key=lambda r: -canopy_m(r))
    return (wide if len(wide) >= 2 else out)[:FILLER_KINDS]


def fill_to_cover(project, existing_features, ground, pool: list, target: float,
                  *, limit: int, get_plant: Optional[Callable] = None,
                  refuse: Optional[Callable] = None) -> dict:
    """Add plants to ``project`` until its cover reaches ``target``.

    ``ground`` is the design's ``OpenGround``; ``pool`` the ranked catalogue
    rows the plan chose from; ``refuse(lat, lng, row)`` turns a spot down (a
    front yard's street band, for a plant too tall for it). Returns
    ``{"added", "cover", "stopped"}``."""
    from shapely.geometry import Point
    from src import yard_overview
    if get_plant is None:
        from src.db.plants import get_plant                   # noqa: PLC0415
    whole = {"features": list(project.as_dict().get("features") or [])
             + list(existing_features or [])}
    proj, area = yard_overview.local_area(whole)
    if area is None or area.area <= 0:
        return {"added": 0, "cover": 0.0, "stopped": STOP_FULL}
    total = area.area
    covered = yard_overview._discs(proj, whole, get_plant)
    covered = covered.intersection(area) if covered is not None else None

    def share():
        return (covered.area / total) if covered is not None else 0.0

    rows = fillers(project, pool, get_plant)
    added, misses, turn = 0, 0, 0
    stopped = STOP_FULL
    while rows:
        if share() >= target:
            stopped = STOP_TARGET
            break
        if len(project.placed_plants) >= limit:
            stopped = STOP_LIMIT
            break
        row = rows[turn % len(rows)]
        turn += 1
        lat, lng = ground.spot_for(row)
        x, y = proj.to_xy(lat, lng)
        disc = Point(x, y).buffer(yard_overview.canopy_m(row) / 2.0, 24)
        new = disc.intersection(area)
        gain = (new.difference(covered).area if covered is not None
                else new.area)
        if gain < MIN_GAIN * disc.area or (refuse and refuse(lat, lng, row)):
            misses += 1
            if misses >= _MISSES * len(rows):
                break
            continue
        misses = 0
        project.place_plant(row["id"], lat, lng, quantity=1)
        covered = new if covered is None else covered.union(new)
        added += 1
    return {"added": added, "cover": share(), "stopped": stopped}

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

What it adds: the design's own low and middle plants, most numerous first
(the matrix of the plan, so a fill reads as more of the same rather than as new
kinds), else the best-ranked dry plants of its pool; each at the open spot
``OpenGround`` finds for it. It stops at the target, at the plant ceiling, or
when the next plants find no open ground, and says which.

Qt-free.
"""

from __future__ import annotations

from typing import Callable, Optional

#: The cover a plan aims for, by the answer given (O3, Y3; §4.7).
COVER_TARGETS = {"now": 0.70, "summers": 0.40,
                 "sparse": 0.25, "balanced": 0.45, "full": 0.70}
#: What the fill adds: not trees (too big to fill a gap), not vines (they need
#: a host), and nothing that needs standing water.
_NOT_FILLERS = ("tree", "vine", "aquatic")
#: How many kinds take turns in the fill.
FILLER_KINDS = 4
#: A spot that adds less new cover than this share of the plant's own spread
#: is not open ground: three in a row and the fill stops.
MIN_GAIN = 0.10
_MISSES = 4

STOP_TARGET, STOP_LIMIT, STOP_FULL = "target", "limit", "full"


def target_for(density: str = "", cover: Optional[float] = None) -> float:
    """The cover a plan aims for: ``cover`` when given, else the density's."""
    if cover is not None:
        return max(0.0, min(0.95, float(cover)))
    return COVER_TARGETS.get((density or "balanced").lower(), 0.45)


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
                or (row.get("plant_type") or "") in _NOT_FILLERS
                or needs_standing_water(row)):
            return
        seen.add(row["id"])
        out.append(row)

    for pid, _n in sorted(counts.items(), key=lambda kv: -kv[1]):
        take(get_plant(pid))
    for row in pool:
        take(row)
    return out[:FILLER_KINDS]


def fill_to_cover(project, existing_features, ground, pool: list, target: float,
                  *, limit: int, get_plant: Optional[Callable] = None) -> dict:
    """Add plants to ``project`` until its cover reaches ``target``.

    ``ground`` is the design's ``OpenGround``; ``pool`` the ranked catalogue
    rows the plan chose from. Returns ``{"added", "cover", "stopped"}``."""
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
        if gain < MIN_GAIN * disc.area:
            misses += 1
            if misses >= _MISSES * len(rows):
                break
            continue
        misses = 0
        project.place_plant(row["id"], lat, lng, quantity=1)
        covered = new if covered is None else covered.union(new)
        added += 1
    return {"added": added, "cover": share(), "stopped": stopped}

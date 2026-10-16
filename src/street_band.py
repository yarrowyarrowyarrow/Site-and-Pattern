"""
street_band.py — a front yard's street edge (PY-7, V3.29; docs/homeowner/07
§4.3, decision Y2).

Design principle P13 — see docs/DESIGN_PHILOSOPHY.md.

A front yard is read from the sidewalk, and a planting there survives when it
looks meant (Nassauer's cues to care, :mod:`src.cues_to_care`). Plan My Yard's
*Front yard* answer keeps the band one metre deep along the street side for
plants that stay 60 cm or shorter and stay where they are put, planted as
repeated drifts of one or two showy low plants; everything taller stands
behind it.

The street side is the person's answer, else the measured one, else south
(:func:`side_for`, which ``frontage`` also reads). The band is the planting
ground within :data:`DEPTH_M` of the outline's street-most extent along that
bearing: exact for a rectangular lot, and for any lot the strip a passer-by
sees first.

Qt-free; needs shapely for the band (none without it).
"""

from __future__ import annotations

from typing import Callable, Optional

DEPTH_M = 1.0
MAX_HEIGHT_M = 0.6
#: Spacing of the band's drifts, and how many of one plant make a drift.
SPACING_M = 0.45
DRIFT = 3
_SPREADERS = ("aggressive_rhizomatous", "self_seeding")
_NOT_IN_BAND = ("tree", "vine", "aquatic")

#: The eight compass words and their bearings.
SIDES = {"north": 0.0, "north-east": 45.0, "east": 90.0, "south-east": 135.0,
         "south": 180.0, "south-west": 225.0, "west": 270.0,
         "north-west": 315.0}


def side_for(site_config: Optional[dict], project: Optional[dict] = None
             ) -> str:
    """The street side: the person's answer (``site_config["street_side"]``),
    else the one measured from the project's roads, else south."""
    told = ((site_config or {}).get("street_side") or "").strip().lower()
    if told in SIDES:
        return told
    from src import frontage
    try:
        return frontage.frontage_for_project(project or {}).side
    except Exception:                                      # noqa: BLE001
        return frontage.ASSUMED.side


def fits(row: dict) -> bool:
    """Whether a plant may stand in the street band: 60 cm or shorter once
    grown (a recorded height; none recorded does not fit) and not recorded
    as spreading."""
    if (row.get("plant_type") or "").lower() in _NOT_IN_BAND:
        return False
    if (row.get("spread_habit") or "") in _SPREADERS:
        return False
    try:
        h = float(row.get("mature_height_meters") or 0)
    except (TypeError, ValueError):
        return False
    return 0 < h <= MAX_HEIGHT_M


class Band:
    """The band for an outline (``[[lat, lng], …]``) and a street side."""

    def __init__(self, boundary, side: str = "south",
                 depth_m: float = DEPTH_M):
        import math
        from shapely.geometry import Polygon
        from src.projection import Projector
        self.side = side if side in SIDES else "south"
        pts = [(float(p[0]), float(p[1])) for p in boundary or []]
        self.proj = Projector.for_positions(pts) if len(pts) >= 3 else None
        self.poly = None
        if self.proj is None:
            return
        ring = Polygon([self.proj.to_xy(la, ln) for la, ln in pts])
        ring = ring if ring.is_valid else ring.buffer(0)
        b = math.radians(SIDES[self.side])
        self.ux, self.uy = math.sin(b), math.cos(b)    # toward the street
        far = max(x * self.ux + y * self.uy
                  for x, y in ring.exterior.coords)
        # The half-plane toward the street from ``far - depth_m``, as a big
        # quadrilateral in the bearing's own axes.
        size = 4 * max(ring.bounds[2] - ring.bounds[0],
                       ring.bounds[3] - ring.bounds[1], 10.0)
        vx, vy = self.uy, -self.ux

        def at(s_, d_):
            return (s_ * vx + d_ * self.ux, s_ * vy + d_ * self.uy)
        strip = Polygon([at(-size, far - depth_m), at(size, far - depth_m),
                         at(size, far + size), at(-size, far + size)])
        self.poly = ring.intersection(strip)

    def contains(self, lat: float, lng: float) -> bool:
        if self.poly is None or self.poly.is_empty:
            return False
        from shapely.geometry import Point
        return self.poly.contains(Point(*self.proj.to_xy(lat, lng)))

    def seats(self, spacing_m: float = SPACING_M) -> list:
        """``[(lat, lng)]`` along the band's middle, ``spacing_m`` apart, in
        order along the street."""
        if self.poly is None or self.poly.is_empty:
            return []
        from shapely.geometry import Point
        # Walk the band's long axis: perpendicular to the bearing.
        vx, vy = self.uy, -self.ux
        xs = [x * vx + y * vy for x, y in _coords(self.poly)]
        ds = [x * self.ux + y * self.uy for x, y in _coords(self.poly)]
        if not xs:
            return []
        mid = (max(ds) + min(ds)) / 2.0
        out = []
        t = min(xs) + spacing_m / 2.0
        while t <= max(xs):
            x, y = t * vx + mid * self.ux, t * vy + mid * self.uy
            if self.poly.contains(Point(x, y)):
                out.append(self.proj.to_latlng(x, y))
            t += spacing_m
        return out


    def toward_street(self, lat: float, lng: float) -> float:
        """How far toward the street, in metres along the bearing."""
        x, y = self.proj.to_xy(lat, lng)
        return x * self.ux + y * self.uy


#: Tall enough to screen what is behind it from the sidewalk.
TALL_M = 1.2


def grade(project, band: Band, get_plant: Callable) -> int:
    """Taller plants step back (PY-7): each tall plant in the street half
    trades places with a short plant in the back half, the tallest nearest
    the street first, so a passer-by sees the whole planting. A plant a vine
    was seated beside stays, so the vine keeps its host. Returns the swaps."""
    from src.project_store import ProjectStore
    if band.proj is None:
        return 0
    store = ProjectStore(project.as_dict())
    placed = [p for p in store.placed_plants if p.get("feature_id")]
    if len(placed) < 2:
        return 0
    d = {p["feature_id"]: band.toward_street(p["lat"], p["lng"])
         for p in placed}
    lo, hi = min(d.values()), max(d.values())
    if hi - lo < 2.0:
        return 0
    mid = (lo + hi) / 2.0
    rows = {p["feature_id"]: get_plant(p["plant_id"]) or {} for p in placed}

    def height(p):
        try:
            return float(rows[p["feature_id"]].get("mature_height_meters")
                         or 0)
        except (TypeError, ValueError):
            return 0.0
    vines = [p for p in placed
             if (rows[p["feature_id"]].get("plant_type") or "") == "vine"]

    def holds_vine(p):
        return any(store_dist(band, p, v) < 1.0 for v in vines)
    tall = sorted((p for p in placed if height(p) >= TALL_M
                   and d[p["feature_id"]] > mid and not holds_vine(p)),
                  key=lambda p: -d[p["feature_id"]])
    short = sorted((p for p in placed if 0 < height(p) <= MAX_HEIGHT_M
                    and d[p["feature_id"]] < mid),
                   key=lambda p: d[p["feature_id"]])
    swaps = 0
    for t, s_ in zip(tall, short):
        (tl, tg), (sl, sg) = (t["lat"], t["lng"]), (s_["lat"], s_["lng"])
        store.move_plant(t["plant_id"], tl, tg, sl, sg,
                         feature_id=t["feature_id"])
        store.move_plant(s_["plant_id"], sl, sg, tl, tg,
                         feature_id=s_["feature_id"])
        swaps += 1
    return swaps


def store_dist(band: Band, a: dict, b: dict) -> float:
    ax, ay = band.proj.to_xy(a["lat"], a["lng"])
    bx, by = band.proj.to_xy(b["lat"], b["lng"])
    return ((ax - bx) ** 2 + (ay - by) ** 2) ** 0.5


def _coords(geom) -> list:
    if hasattr(geom, "geoms"):
        return [c for g in geom.geoms for c in _coords(g)]
    if hasattr(geom, "exterior"):
        return list(geom.exterior.coords)
    return []


def plant_band(project, band: Band, pool: list, *,
               get_plant: Callable, keep: Callable = lambda la, ln: True
               ) -> dict:
    """Clear the band of plants that do not fit, then plant it with repeated
    drifts of the pool's first one or two showy plants that do (``keep``
    says whether a seat is open ground). Returns ``{"removed", "added",
    "names"}``."""
    from src.project_store import ProjectStore
    if band.poly is None or band.poly.is_empty:
        return {"removed": 0, "added": 0, "names": []}
    store = ProjectStore(project.as_dict())
    out = [(p["plant_id"], p["lat"], p["lng"]) for p in store.placed_plants
           if band.contains(p["lat"], p["lng"])
           and not fits(get_plant(p["plant_id"]) or {})]
    store.remove_plants_batch(out)
    low = _showy_first([r for r in pool if fits(r)])[:2]
    added = 0
    if low:
        for i, (lat, lng) in enumerate(band.seats()):
            if not keep(lat, lng):
                continue
            row = low[(i // DRIFT) % len(low)]
            project.place_plant(row["id"], lat, lng, quantity=1)
            added += 1
    return {"removed": len(out), "added": added,
            "names": [r.get("common_name") or "" for r in low]}


def _showy_first(rows: list) -> list:
    from src.flower_colour import WIND_POLLINATED_TYPES
    return ([r for r in rows if (r.get("plant_type") or "").lower()
             not in WIND_POLLINATED_TYPES]
            + [r for r in rows if (r.get("plant_type") or "").lower()
               in WIND_POLLINATED_TYPES])

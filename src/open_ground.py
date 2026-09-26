"""Where the design review plants what it adds: in open ground (F183, V2.91).

Design principle P2 — see docs/DESIGN_PHILOSOPHY.md

After the main pass has laid out a design, three follow-up steps can add plants:
the critic's repairs (:func:`src.design_critic.apply_repairs`), the goal top-up
and the wildlife top-up (:mod:`src.llm_design`). Until V2.91 each put every plant
it added on the boundary's first 6 m grid cell, its north-west corner, so in a
test design a willow, a buckbean and a sunflower stood on one point.

:class:`OpenGround` finds a spot for one plant at a time, from the plants
actually in the ground. The main pass's positioner is usually spent by then
(measured: no free anchor cell at all on a 12 x 18 m yard at full density), and
it never knew about the vines F181 seats.

* **Where a plant may go at all:** inside the boundary, clear of keep-out (the
  design's own pond or rain garden included, which the main pass places after
  its plants), and inside the drawn restoration zones when there are any. The
  main pass's rules.
* **Free ground first.** Free means every placed plant is at least half their
  two spacings away: the spacing the main pass lays its drifts at.
* **Among free spots, the ground that suits the plant** (the main pass's own
  cell score) when the terrain is known, and then the spot nearest the planting,
  so an addition joins the design instead of standing alone in a far corner.
* **With no free spot, the least crowded one.**
* **A vine at the foot of a tree or shrub** when one has room (F181's seats).

Ties go to the candidate grid's row-major order, so a design always comes out
the same way.
"""

from __future__ import annotations

import math
from typing import Callable, Optional

from src.projection import Projector

#: The candidate grid is this fine, coarsened on a large lot so that one search
#: never weighs more than ``MAX_CANDIDATES`` spots.
STEP_M = 0.5
MAX_CANDIDATES = 2500
#: With no boundary, how far past the planted ground the search reaches (a
#: plant's own spacing when that is more).
MARGIN_M = 3.0
#: Room is counted up to this many times what a plant needs: four spacings from
#: anything, one spot is as far from the planting as another.
RATIO_CAP = 4.0
#: Among free spots: how well the ground suits the plant, then how near it is.
W_FIT = 0.75
W_NEAR = 0.25


class OpenGround:
    """The open ground in a design, asked for one plant at a time.

    ``project`` is read on every call, so each addition sees the ones before
    it. ``keepout`` and ``fills`` are the main pass's (``src.exclusion``
    circles and rings), ``cell_env_map`` its scored anchor cells, and
    ``spacing_of(plant_id)`` its centre-to-centre spacing.
    """

    def __init__(self, project, boundary=None, center=None, *,
                 keepout=None, fills=None, cell_env_map=None,
                 spacing_of: Optional[Callable[[int], float]] = None):
        from src.exclusion import keepout_circles
        self._project = project
        self._poly = _polygon(boundary)
        self._keepout = (list(keepout or [])
                         + keepout_circles(project.as_dict()))
        self._fills = [r for r in (fills or []) if r and len(r) >= 3]
        self._env = dict(cell_env_map or {})
        self._spacing_of = spacing_of or _generator_spacing
        self._rows: dict = {}
        self._spacings: dict = {}
        ring = self._poly[0] if self._poly else []
        if ring:
            origin = (sum(p[1] for p in ring) / len(ring),
                      sum(p[0] for p in ring) / len(ring))
        else:
            origin = tuple(center) if center else (0.0, 0.0)
        self._center = tuple(center) if center else origin
        self._proj = Projector(origin[0], origin[1])
        self._base: Optional[list] = None
        self._env_cells: Optional[dict] = None
        self._env_step = 0.0

    # ── The question ────────────────────────────────────────────────────────

    def spot_for(self, row: dict) -> tuple[float, float]:
        """Where to plant one of ``row`` (a catalogue row, with its ``id``)."""
        placed = [(p["lat"], p["lng"], p.get("plant_id"))
                  for p in self._project.placed_plants]
        if (row.get("plant_type") or "").lower() == "vine":
            seat = self._seat_vine(placed)
            if seat is not None:
                return seat
        own = self._spacing(row.get("id"))
        cands = self._clear(self._grid(placed, own), own)
        if not cands:
            return self._center
        near = self._neighbours(placed, own)
        plant = dict(row, _uses=_uses_of(row))
        best, best_key = cands[0], None
        for la, ln in cands:
            x, y = self._proj.to_xy(la, ln)
            room = _room(x, y, *near)
            fit = self._fit(plant, x, y)
            if room >= 1.0:
                key = (1, W_FIT * fit + W_NEAR / min(room, RATIO_CAP))
            else:
                key = (0, room + 1e-3 * fit)
            if best_key is None or key > best_key:
                best, best_key = (la, ln), key
        return best

    # ── Candidates ──────────────────────────────────────────────────────────

    def _grid(self, placed, own: float) -> list:
        """Spots a plant could be put at before keep-out: the boundary's grid
        (computed once), or with no boundary the planted ground plus a margin."""
        if self._poly:
            if self._base is None:
                self._base = self._in_fills(self._grid_over(
                    self._poly_xy_bbox(), _area_xy(self._ring_xy())))
            return self._base
        pts = [self._proj.to_xy(la, ln) for la, ln, _ in placed]
        pts.append(self._proj.to_xy(*self._center))
        m = max(MARGIN_M, own)
        bbox = (min(p[0] for p in pts) - m, min(p[1] for p in pts) - m,
                max(p[0] for p in pts) + m, max(p[1] for p in pts) + m)
        return self._in_fills(self._grid_over(
            bbox, (bbox[2] - bbox[0]) * (bbox[3] - bbox[1])))

    def _grid_over(self, bbox, area_m2: float) -> list:
        """Row-major from the north-west, like the main pass's grid."""
        xmin, ymin, xmax, ymax = bbox
        step = max(STEP_M, math.sqrt(max(area_m2, 0.0) / MAX_CANDIDATES))
        out = []
        y = ymax - step / 2.0
        while y > ymin:
            x = xmin + step / 2.0
            while x < xmax:
                la, ln = self._proj.to_latlng(x, y)
                if self._inside(la, ln):
                    out.append((la, ln))
                x += step
            y -= step
        return out

    def _in_fills(self, cands: list) -> list:
        """Inside the drawn restoration zones when any spot is, as the main
        pass steers its anchors (never down to nothing)."""
        if not self._fills:
            return cands
        from src.geometry import point_in_ring
        inside = [c for c in cands
                  if any(point_in_ring(c[0], c[1], r) for r in self._fills)]
        return inside or cands

    def _clear(self, cands: list, own: float) -> list:
        """Clear of keep-out by half the plant's spread, else by its centre,
        else (keep-out over everything) whatever there is."""
        if not self._keepout:
            return cands
        from src.exclusion import is_clear
        for margin in (own / 2.0, 0.0):
            ok = [c for c in cands
                  if is_clear(c[0], c[1], self._keepout, margin)]
            if ok:
                return ok
        return cands

    def _inside(self, lat: float, lng: float) -> bool:
        if not self._poly:
            return True
        from src.geometry import point_in_polygon
        return point_in_polygon(lat, lng, self._poly)

    def _ring_xy(self) -> list:
        return [self._proj.to_xy(p[1], p[0]) for p in self._poly[0]]

    def _poly_xy_bbox(self) -> tuple:
        xy = self._ring_xy()
        return (min(p[0] for p in xy), min(p[1] for p in xy),
                max(p[0] for p in xy), max(p[1] for p in xy))

    # ── Room and fit ────────────────────────────────────────────────────────

    def _neighbours(self, placed, own: float) -> tuple:
        """The placed plants bucketed on a grid one largest-need wide, each
        with the room it and this plant need between them."""
        pts = [(self._proj.to_xy(la, ln), (own + self._spacing(pid)) / 2.0)
               for la, ln, pid in placed]
        cell = max([need for _, need in pts] + [0.25])
        buckets: dict = {}
        for (x, y), need in pts:
            key = (math.floor(x / cell), math.floor(y / cell))
            buckets.setdefault(key, []).append((x, y, need))
        return buckets, cell

    def _fit(self, plant: dict, x: float, y: float) -> float:
        """The main pass's ecological cell score at the nearest scored anchor
        cell, or a neutral 0.5 when the terrain is unknown."""
        if not self._env:
            return 0.5
        env = self._env_near(x, y)
        if env is None:
            return 0.5
        from src.placement_score import score_cell_for_plant
        return score_cell_for_plant(plant, env)

    def _env_near(self, x: float, y: float):
        if self._env_cells is None:
            xy = {c: self._proj.to_xy(c[0], c[1]) for c in self._env}
            pts = list(xy.values())
            gap = min((math.hypot(a[0] - b[0], a[1] - b[1])
                       for b in pts[1:] for a in pts[:1]), default=6.0)
            self._env_step = max(gap, 0.5)
            self._env_cells = {}
            for c, (cx, cy) in xy.items():
                key = (math.floor(cx / self._env_step),
                       math.floor(cy / self._env_step))
                self._env_cells.setdefault(key, []).append((cx, cy, c))
        s = self._env_step
        ix, iy = math.floor(x / s), math.floor(y / s)
        best, best_d = None, float("inf")
        for bx in range(ix - 1, ix + 2):
            for by in range(iy - 1, iy + 2):
                for cx, cy, c in self._env_cells.get((bx, by), ()):
                    d = math.hypot(cx - x, cy - y)
                    if d < best_d:
                        best, best_d = c, d
        return self._env.get(best) if best is not None else None

    # ── Vines ───────────────────────────────────────────────────────────────

    def _seat_vine(self, placed) -> Optional[tuple[float, float]]:
        """F181's seat at a tree or shrub's foot, counting the vines already
        on each host, or None when no host has room."""
        from src.exclusion import is_clear
        from src.vine_habit import holds_vines
        from src.vine_seating import VineSeats, crown_m_of
        seats = VineSeats(lambda la, ln: (self._inside(la, ln)
                                          and is_clear(la, ln, self._keepout)))
        vines = []
        for la, ln, pid in placed:
            row = self._row(pid)
            kind = (row.get("plant_type") or "").lower()
            if holds_vines(row):
                seats.add_host(la, ln, kind, crown_m_of(row))
            elif kind == "vine":
                vines.append((la, ln))
        if not seats.hosts:
            return None
        for la, ln in vines:
            seats.note_vine(la, ln)
        return seats.seat([(la, ln) for la, ln, _ in placed])

    # ── Catalogue lookups, once per species ─────────────────────────────────

    def _row(self, plant_id) -> dict:
        if plant_id not in self._rows:
            try:
                from src.db.plants import get_plant
                self._rows[plant_id] = get_plant(plant_id) or {}
            except Exception:  # noqa: BLE001 — a lookup must not break a design
                self._rows[plant_id] = {}
        return self._rows[plant_id]

    def _spacing(self, plant_id) -> float:
        if plant_id not in self._spacings:
            try:
                self._spacings[plant_id] = max(0.25,
                                               float(self._spacing_of(plant_id)))
            except Exception:  # noqa: BLE001
                self._spacings[plant_id] = 1.0
        return self._spacings[plant_id]


def _room(x: float, y: float, buckets: dict, cell: float) -> float:
    """How many times over the nearest placed plant leaves this spot the room
    the two of them need; ``RATIO_CAP`` when nothing is that near.

    Searched ring by ring out from the spot's bucket: once rings ``0..r`` are
    done, anything left is at least ``r`` cells away, and no pair needs more
    than a cell, so a best of ``r`` or less cannot be beaten."""
    if not buckets:
        return RATIO_CAP
    ix, iy = math.floor(x / cell), math.floor(y / cell)
    best = RATIO_CAP
    r = 0
    while True:
        for bx in range(ix - r, ix + r + 1):
            for by in range(iy - r, iy + r + 1):
                if max(abs(bx - ix), abs(by - iy)) != r:
                    continue
                for px, py, need in buckets.get((bx, by), ()):
                    q = math.hypot(px - x, py - y) / need
                    if q < best:
                        best = q
        if best <= r:
            return best
        r += 1


def _polygon(boundary) -> Optional[list]:
    """A ``(lat, lng)`` boundary as a GeoJSON polygon, or None."""
    pts = [p for p in (boundary or [])
           if isinstance(p, (list, tuple)) and len(p) >= 2]
    if len(pts) < 3:
        return None
    ring = [[float(p[1]), float(p[0])] for p in pts]
    if ring[0] != ring[-1]:
        ring.append(ring[0])
    return [ring]


def _area_xy(ring: list) -> float:
    n = len(ring)
    twice = sum(ring[i][0] * ring[(i + 1) % n][1]
                - ring[(i + 1) % n][0] * ring[i][1] for i in range(n))
    return abs(twice) / 2.0


def _uses_of(row: dict) -> set:
    """The use tags the cell score reads (``_uses``), from the row."""
    if isinstance(row.get("_uses"), (set, frozenset)):
        return set(row["_uses"])
    return {u.strip() for u in (row.get("permaculture_uses") or "").split(",")
            if u.strip()}


def _generator_spacing(plant_id) -> float:
    """The main pass's spacing, so "room" means the same thing to both."""
    from src.llm_design import _plant_spacing_m
    return _plant_spacing_m(plant_id)

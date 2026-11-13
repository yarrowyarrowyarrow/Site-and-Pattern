"""
src/scene_views.py — what the 3D camera frames, and where to stand (V3.43).

Design principle P13 (a native planting has to be loved to survive) and P5
(perception is constructed: the first picture decides what the design is taken
to be) — see docs/DESIGN_PHILOSOPHY.md.

Until V3.43 every camera in the 3D preview was placed from the scene's
``bounds``, and ``bounds`` has a floor of ±25 m so an empty design still gets a
stage. Measured on the worked example, an 11 x 8 m yard was about 1% of the
opening picture. The "sidewalk" view the before/after page and the presentation
still use stood 22 m outside a 15 x 37 m lot with a boulevard tree's trunk in the
middle of the frame, and Walk the garden started at the centre of the stage,
which on most lots is inside the house.

Two answers, decided once here and sent with the scene so the viewer, the stills
and the walker cannot disagree (the V2.88 lesson):

* :func:`focus_box` is the design's own extent: its outline, its placed plants
  and its structures, padded. The orbit, Reset view and the flyover frame it.
* :func:`street_view` is where a neighbour stands: just outside the edge that
  faces the street (:mod:`src.frontage`: the person's answer, else the side
  measured from the roads, else south), stepped sideways until no trunk stands in
  front of the lens, looking at the planting on that side of the yard.
* :func:`house_view` (V3.44) is where the person stands most days: at the wall
  of their own house, looking out at the planting. Only when a building stands
  inside the outline; the app does not guess where a house might be (P9).

Qt-free, DB-free, plain arithmetic in scene metres (+x east, +y north).
"""

from __future__ import annotations

import math
from typing import Optional

#: Metres added round the design's extent.
FOCUS_PAD_M = 2.0
#: The smallest extent framed, so one plant is not looked at from 40 cm.
FOCUS_MIN_SPAN_M = 8.0

#: How far outside the street edge the neighbour stands: a sidewalk's distance.
STREET_STANDOFF_M = 4.0
#: Sideways steps tried, in order, when something stands in front of the lens.
_SIDE_STEPS_M = (0.0, 1.5, -1.5, 3.0, -3.0, 4.5, -4.5, 6.0, -6.0)
#: ... and then nearer the edge (in front of a boulevard tree) or further back
#: from it, when no sideways step is clear.
_BACK_STEPS_M = (0.0, -2.0, -3.0, 3.0, 6.0)
#: A trunk nearer the eye than this is in the way wherever one looks.
_EYE_CLEAR_M = 1.2
#: Only what stands in the first part of the sight line is "in front of the
#: lens"; a tree beside the planting is part of the picture.
_NEAR_SHARE = 0.6
#: A shrub this tall hides the view like a tree does.
_TALL_SHRUB_M = 2.0
#: What stands between the sidewalk and the yard (a boulevard tree) has to be
#: out of the picture altogether, not just off the centre line: 2 m from the
#: lens a 14 m elm's trunk filled an eighth of the frame from 1.4 m to one side.
#: The tangent of a little more than half the picture's width (the camera sees
#: about 37 degrees either side at the window's shape).
_OUT_OF_FRAME = 0.8

#: From the house: how far outside the wall the person stands (a doorstep),
#: how near a corner they may stand, and the least distance looked across (a
#: plant against the wall would otherwise be looked straight down on).
HOUSE_STEP_M = 0.8
_CORNER_CLEAR_M = 0.6
HOUSE_LOOK_MIN_M = 4.0
#: A plant that grows this tall, this near the eye, is in the way: the first
#: build stood the person in a foundation bed with grasses against the lens.
_CROWD_HEIGHT_M = 1.0
_CROWD_NEAR_M = 1.5


def _placed(plant: dict) -> bool:
    """A plant the person or the plan put there: not a tree that was already
    standing, and not a seedling that came up on its own in a later year (a
    recruit would move the view from one year's picture to the next)."""
    return plant.get("plant_id") is not None and not plant.get("recruit")


def focus_box(boundary: Optional[list], plants: list, structures: list, *,
              pad: float = FOCUS_PAD_M,
              min_span: float = FOCUS_MIN_SPAN_M) -> Optional[dict]:
    """``{min_x, min_y, max_x, max_y}`` round the design itself, or ``None``
    when it has no outline, no placed plant and no structure (the viewer then
    frames ``bounds`` as it always did).

    Existing trees and buildings do not widen it: a neighbour's house two lots
    over is in the scene and is not what the design is.
    """
    xs: list = []
    ys: list = []
    for pt in boundary or []:
        xs.append(float(pt[0]))
        ys.append(float(pt[1]))
    for p in plants or []:
        if _placed(p):
            xs.append(float(p["x"]))
            ys.append(float(p["y"]))
    for s in structures or []:
        xs.append(float(s["x"]))
        ys.append(float(s["y"]))
    if not xs:
        return None
    lo_x, hi_x = min(xs) - pad, max(xs) + pad
    lo_y, hi_y = min(ys) - pad, max(ys) + pad
    if hi_x - lo_x < min_span:
        mid = (lo_x + hi_x) / 2.0
        lo_x, hi_x = mid - min_span / 2.0, mid + min_span / 2.0
    if hi_y - lo_y < min_span:
        mid = (lo_y + hi_y) / 2.0
        lo_y, hi_y = mid - min_span / 2.0, mid + min_span / 2.0
    return {"min_x": round(lo_x, 2), "min_y": round(lo_y, 2),
            "max_x": round(hi_x, 2), "max_y": round(hi_y, 2)}


def street_bearing(project: dict) -> tuple:
    """``(bearing, known)``: degrees clockwise from north, from the yard toward
    its street, and whether that was told or measured rather than assumed."""
    from src.frontage import ASSUMED, frontage_for_project
    try:
        f = frontage_for_project(project or {})
    except Exception:                                      # noqa: BLE001
        f = ASSUMED
    return float(f.bearing), bool(f.measured or f.told)


def _in_ring(x: float, y: float, ring: list) -> bool:
    inside = False
    n = len(ring)
    for i in range(n):
        x0, y0 = ring[i]
        x1, y1 = ring[(i + 1) % n]
        if (y0 > y) != (y1 > y) and x < (x1 - x0) * (y - y0) / (y1 - y0) + x0:
            inside = not inside
    return inside


def _segments_cross(a, b, c, d) -> bool:
    def side(p, q, r):
        return (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])
    return (side(a, b, c) * side(a, b, d) < 0
            and side(c, d, a) * side(c, d, b) < 0)


def _clearance(eye, look, trunks, buildings, outside: float) -> float:
    """How clear the view from ``eye`` toward ``look`` is: the smallest gap
    between the first part of the sight line and a trunk. Less than zero when
    something is in the way: -2 with the eye inside a building, -1 when the
    line passes through one. A trunk within ``outside`` metres along the line
    stands before the yard begins and must be out of the frame."""
    ex, ey = eye
    dx, dy = look[0] - ex, look[1] - ey
    length = math.hypot(dx, dy) or 1.0
    near = (ex + dx * _NEAR_SHARE, ey + dy * _NEAR_SHARE)
    if any(_in_ring(ex, ey, ring) for ring in buildings):
        return -2.0
    for ring in buildings:
        for i in range(len(ring)):
            if _segments_cross(eye, near, ring[i], ring[(i + 1) % len(ring)]):
                return -1.0
    best = 99.0
    for tx, ty, radius in trunks:
        at_eye = math.hypot(tx - ex, ty - ey) - radius
        if at_eye < _EYE_CLEAR_M:
            best = min(best, at_eye - _EYE_CLEAR_M)
            continue
        along = ((tx - ex) * dx + (ty - ey) * dy) / length
        if along <= 0 or along > length * _NEAR_SHARE:
            continue
        across = abs((tx - ex) * dy - (ty - ey) * dx) / length
        if along <= outside:
            best = min(best, across - radius - along * _OUT_OF_FRAME)
        else:
            best = min(best, across - radius - 0.5)
    return best


def _trunks(plants: list) -> list:
    """``[(x, y, radius)]`` for what hides a view like a tree does: every tree,
    and a shrub by its grown height (so the answer is the same every year)."""
    out = []
    for p in plants or []:
        kind = p.get("plant_type")
        height = float(p.get("mature_height_m") or p.get("height_m") or 0)
        if kind == "tree" or (kind == "shrub" and height >= _TALL_SHRUB_M):
            # Half the drawn trunk's width, near enough: a big tree's is wide.
            out.append((float(p["x"]), float(p["y"]),
                        max(0.2, 0.05 * height)))
    return out


def _walls(buildings: list) -> list:
    """The rings of what is a building: a drawn tree crown is not a wall."""
    return [[(float(q[0]), float(q[1])) for q in (bld.get("ring") or [])]
            for bld in buildings or []
            if bld.get("kind") != "canopy" and len(bld.get("ring") or []) >= 3]


def street_view(boundary: Optional[list], plants: list, buildings: list,
                bearing: float, *,
                standoff: float = STREET_STANDOFF_M) -> Optional[dict]:
    """Where a neighbour stands and what they look at: ``{eye: [x, y],
    look: [x, y], bearing}`` in scene metres, or ``None`` without an outline.

    The eye is ``standoff`` metres outside the outline's street edge, level
    with the planting on the street side of the yard, moved sideways along the
    frontage until no trunk stands in the first part of the sight line.

    **The same answer in every year.** The before/after page renders this view
    at three years and "a viewpoint change between two images reads as a
    difference in the design" (:mod:`src.before_after`). So it is worked out
    from the design as planted, never from what stands this year: every placed
    plant counts toward what is looked at whether or not shade has taken it,
    and a shrub is in the way by its grown height, not this year's.
    """
    if not boundary or len(boundary) < 3:
        return None
    ring = [(float(p[0]), float(p[1])) for p in boundary]
    cx = sum(p[0] for p in ring) / len(ring)
    cy = sum(p[1] for p in ring) / len(ring)
    b = math.radians(bearing)
    d = (math.sin(b), math.cos(b))            # toward the street
    n = (math.cos(b), -math.sin(b))           # along the frontage

    def to_ts(x, y):
        return ((x - cx) * d[0] + (y - cy) * d[1],
                (x - cx) * n[0] + (y - cy) * n[1])

    ts = [to_ts(x, y) for x, y in ring]
    t_edge = max(t for t, _ in ts)
    front = [s for t, s in ts if t >= t_edge - 1.5]
    if len(front) < 2:                        # a corner faces the street
        front = [s for _, s in ts]
    s_lo, s_hi = min(front), max(front)

    placed = [p for p in plants or [] if _placed(p)]
    street_half = [p for p in placed if to_ts(p["x"], p["y"])[0] > 0]
    subject = street_half or placed
    if subject:
        lx = sum(p["x"] for p in subject) / len(subject)
        ly = sum(p["y"] for p in subject) / len(subject)
    else:
        lx, ly = cx, cy
    look = (lx, ly)
    s_look = to_ts(lx, ly)[1]

    trunks = _trunks(plants)
    rings = _walls(buildings)

    centre_s = min(max(s_look, s_lo + 0.5), s_hi - 0.5) if s_hi - s_lo > 1 \
        else (s_lo + s_hi) / 2.0
    best = None
    for back in _BACK_STEPS_M:
        for step in _SIDE_STEPS_M:
            s = min(max(centre_s + step, s_lo - 1.0), s_hi + 1.0)
            t = t_edge + standoff + back
            eye = (cx + d[0] * t + n[0] * s, cy + d[1] * t + n[1] * s)
            gap = _clearance(eye, look, trunks, rings, standoff + back + 1.0)
            if best is None or gap > best[0]:
                best = (gap, eye)
            if gap >= 0:
                break
        if best[0] >= 0:
            break
    eye = best[1]
    view = {"eye": [round(eye[0], 2), round(eye[1], 2)],
            "look": [round(look[0], 2), round(look[1], 2)],
            "bearing": round(float(bearing) % 360.0, 1)}
    if best[0] <= -1.0 or (placed and not street_half):
        # The planting is not on the street's side of things: a building
        # stands between it and every spot tried, or all of it is in the half
        # of the yard away from the street (a back-yard plan). This is still
        # where a neighbour stands; :func:`opening_view` does not open on it.
        view["behind"] = True
    return view


def opening_view(views: Optional[dict]) -> str:
    """Which named view a window opens on (V3.44; the owner's D5 is the
    street): ``"street"`` when the planting can be seen from there,
    ``"house"`` when it is behind the house or all at the back and there is a
    house to look from, else ``"whole"`` (the whole yard, which is never
    wrong: an empty design, a walk through a wild community)."""
    views = views or {}
    street = views.get("street")
    if street and not street.get("behind"):
        return "street"
    if views.get("house"):
        return "house"
    return "whole"


# ── from the house (V3.44) ───────────────────────────────────────────────────

def _area(ring: list) -> float:
    total = 0.0
    for i in range(len(ring)):
        x0, y0 = ring[i]
        x1, y1 = ring[(i + 1) % len(ring)]
        total += x0 * y1 - x1 * y0
    return abs(total) / 2.0


def _centroid(ring: list) -> tuple:
    return (sum(p[0] for p in ring) / len(ring),
            sum(p[1] for p in ring) / len(ring))


def house_ring(boundary: Optional[list], buildings: list,
               pin: Optional[tuple] = None) -> Optional[list]:
    """The house, as ``[(x, y), ...]``, or ``None``: the largest building
    standing inside the yard's outline (its middle inside it); with no
    outline, the building the yard's pin stands on.

    A neighbour's house is in the scene and is not this yard's. A yard
    outlined without its house, or a pin set down on the lawn, has none here,
    and the view is not offered: nothing says which building it would be."""
    walls = _walls(buildings)
    if boundary and len(boundary) >= 3:
        outline = [(float(p[0]), float(p[1])) for p in boundary]
        inside = [ring for ring in walls
                  if _in_ring(*_centroid(ring), outline)]
        return max(inside, key=_area) if inside else None
    if pin is not None:
        under = [ring for ring in walls
                 if _in_ring(float(pin[0]), float(pin[1]), ring)]
        return max(under, key=_area) if under else None
    return None


def extent_ring(focus: Optional[dict]) -> Optional[list]:
    """The design's own extent (:func:`focus_box`) as a ring, to stand in for
    the outline of a yard that has none drawn: the simple app's usual design
    is a pin and a bed (V3.28: "a bed with no outline is enough")."""
    if not focus:
        return None
    return [[focus["min_x"], focus["min_y"]], [focus["max_x"], focus["min_y"]],
            [focus["max_x"], focus["max_y"]], [focus["min_x"], focus["max_y"]]]


def _to_segment(px: float, py: float, a: tuple, b: tuple) -> tuple:
    """``(distance, along)`` from a point to the segment ``a``-``b``: how far,
    and how many metres from ``a`` the nearest point on it is."""
    dx, dy = b[0] - a[0], b[1] - a[1]
    length = math.hypot(dx, dy)
    if length < 1e-9:
        return math.hypot(px - a[0], py - a[1]), 0.0
    along = ((px - a[0]) * dx + (py - a[1]) * dy) / length
    along = min(max(along, 0.0), length)
    qx, qy = a[0] + dx * along / length, a[1] + dy * along / length
    return math.hypot(px - qx, py - qy), along


def house_view(boundary: Optional[list], plants: list,
               buildings: list, pin: Optional[tuple] = None,
               extent: Optional[list] = None) -> Optional[dict]:
    """Where the person stands at their own house and what they look at:
    ``{eye: [x, y], look: [x, y]}`` in scene metres, or ``None`` when there
    is no house (:func:`house_ring`; ``pin`` is the yard's pin, for a yard
    with no outline, and ``extent`` what to look at when nothing is planted).

    The wall is the one most of the planting is nearest to (a front bed is
    seen from the front of the house, a back bed from the back). The person
    stands a step outside it, at the spot on that wall closest to that
    planting, moved along the wall until no trunk and no other building is in
    the way and nothing that grows tall is within arm's reach (a path or a
    doorstep, where there is one), looking across at the planting.

    **The same answer in every year**, for the reason :func:`street_view`
    gives: it is worked out from the design as planted.
    """
    house = house_ring(boundary, buildings, pin)
    if house is None:
        return None
    hx, hy = _centroid(house)
    placed = [(float(p["x"]), float(p["y"])) for p in plants or []
              if _placed(p)]
    # With nothing planted the yard itself is the subject: its corners.
    subject = placed or [(float(p[0]), float(p[1]))
                         for p in (boundary or extent or [])]
    if not subject:
        return None

    n = len(house)
    groups: dict = {}
    for px, py in subject:
        best = min(range(n), key=lambda i: _to_segment(
            px, py, house[i], house[(i + 1) % n])[0])
        groups.setdefault(best, []).append((px, py))

    def length(i):
        a, b = house[i], house[(i + 1) % n]
        return math.hypot(b[0] - a[0], b[1] - a[1])

    wall = max(groups, key=lambda i: (len(groups[i]), length(i), -i))
    seen = groups[wall]
    lx = sum(p[0] for p in seen) / len(seen)
    ly = sum(p[1] for p in seen) / len(seen)

    a, b = house[wall], house[(wall + 1) % n]
    span = length(wall)
    ux, uy = (b[0] - a[0]) / span, (b[1] - a[1]) / span       # along the wall
    nx, ny = uy, -ux                                           # across it
    mid = (a[0] + ux * span / 2.0, a[1] + uy * span / 2.0)
    if (mid[0] - hx) * nx + (mid[1] - hy) * ny < 0:            # point outward
        nx, ny = -nx, -ny
    _dist, along = _to_segment(lx, ly, a, b)
    margin = min(_CORNER_CLEAR_M, span / 2.0)
    trunks = _trunks(plants)
    rings = _walls(buildings)
    # By grown height, so the answer is the same in every year.
    tall = [(float(p["x"]), float(p["y"])) for p in plants or []
            if _placed(p) and float(p.get("mature_height_m")
                                    or p.get("height_m") or 0) >= _CROWD_HEIGHT_M]

    def look_from(eye):
        dx, dy = lx - eye[0], ly - eye[1]
        dist = math.hypot(dx, dy)
        if dist >= HOUSE_LOOK_MIN_M:
            return (lx, ly)
        if dist < 0.5:                       # planted against the wall
            dx, dy, dist = nx, ny, 1.0
        return (eye[0] + dx / dist * HOUSE_LOOK_MIN_M,
                eye[1] + dy / dist * HOUSE_LOOK_MIN_M)

    best = None
    for step in _SIDE_STEPS_M:
        s = min(max(along + step, margin), span - margin)
        eye = (a[0] + ux * s + nx * HOUSE_STEP_M,
               a[1] + uy * s + ny * HOUSE_STEP_M)
        look = look_from(eye)
        gap = _clearance(eye, look, trunks, rings, 0.0)
        crowd = sum(1 for x, y in tall
                    if math.hypot(x - eye[0], y - eye[1]) < _CROWD_NEAR_M)
        # A clear sight line first, then the fewest tall plants at the eye.
        rank = (gap >= 0, -crowd, gap)
        if best is None or rank > best[0]:
            best = (rank, eye, look)
        if gap >= 0 and not crowd:
            break
    _rank, eye, look = best
    return {"eye": [round(eye[0], 2), round(eye[1], 2)],
            "look": [round(look[0], 2), round(look[1], 2)]}

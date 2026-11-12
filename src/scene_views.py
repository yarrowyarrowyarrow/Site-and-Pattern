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

    trunks = []
    for p in plants or []:
        kind = p.get("plant_type")
        height = float(p.get("mature_height_m") or p.get("height_m") or 0)
        if kind == "tree" or (kind == "shrub" and height >= _TALL_SHRUB_M):
            # Half the drawn trunk's width, near enough: a big tree's is wide.
            trunks.append((float(p["x"]), float(p["y"]),
                           max(0.2, 0.05 * height)))
    rings = [[(float(q[0]), float(q[1])) for q in (bld.get("ring") or [])]
             for bld in buildings or []
             if bld.get("kind") != "canopy" and len(bld.get("ring") or []) >= 3]

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
    return {"eye": [round(eye[0], 2), round(eye[1], 2)],
            "look": [round(look[0], 2), round(look[1], 2)],
            "bearing": round(float(bearing) % 360.0, 1)}

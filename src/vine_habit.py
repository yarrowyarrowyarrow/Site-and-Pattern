"""
vine_habit.py — what a vine holds onto (V2.89, F179).

Design principle P10 — see docs/DESIGN_PHILOSOPHY.md. A vine is the plainest
case of a plant defined by its neighbour: its recorded height is how far it
CLIMBS, not how tall it stands. Until V2.89 the 3D scene drew all six catalogue
vines as free-standing leafy columns that height tall, so a 6 m Wild Clematis
was a 6 m green pillar in the open.

The owner's rule (V2.89): *"Vines should climb adjacent plant but only if it is
a tree or shrub."* So a vine climbs the tree or shrub beside it; with neither
beside it, it has nothing to climb and lies on the ground. Since V2.93 a shrub
whose habit is a rosette (soapweed yucca: sword leaves from the ground, no
crown) is not a host either: "only if" is a limit, and nobody plants a clematis
to climb a yucca. The generator's seating asks the same question
(:func:`holds_vines`), so it never seats a vine at one.

"Beside" means the two footprints touch: the gap between the vine's root and the
host's crown edge is no more than the vine's own spread radius, plus
``TOUCH_SLACK_M``. The nearest crown edge wins, then the lower index, so one
design always draws the same way.

This is decided ONCE, while ``scene_contract.build_scene`` assembles the scene,
and written into the vine's record as a ``drawn`` block. The viewer draws from it
(``html/scene3d/22-vines.js``) and ``scene_wildlife`` perches animals on it, so
the two cannot disagree about where the vine is. That is the V2.88 lesson: the
flowers and the body each worked out a groundcover's height for themselves, and
the flowers floated.

Qt-free and DB-free.
"""

from __future__ import annotations

import math
from typing import Optional

#: The owner's rule: what a vine may climb.
CLIMBABLE = ("tree", "shrub")
#: A woody habit with no crown to climb (V2.93): the yucca's rosette.
NOT_A_CROWN = ("rosette",)

#: A vine with nothing to climb lies on the ground, no taller than this.
SPRAWL_HEIGHT_M = 0.30

#: Two footprints "touch" within this much of each other.
TOUCH_SLACK_M = 0.10

#: A host fainter than this is not there yet: the viewer's own line for whether
#: a plant is present enough to flower (html/scene3d/05-flowers.js).
PRESENT_OPACITY = 0.25

#: Where on the host's crown the climbing foliage centres, as a fraction of the
#: crown radius out from the trunk towards the vine. Only the animals read it;
#: the viewer fits the leaves to the host's real geometry.
_FOLIAGE_OUT = 0.75


def _num(value, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def is_vine(plant: dict) -> bool:
    return (plant.get("plant_type") or "") == "vine"


def holds_vines(plant: dict) -> bool:
    """Whether this kind of plant can hold a vine up at all: a tree or shrub
    with a crown. A scene plant and a catalogue row both answer it."""
    return ((plant.get("plant_type") or "") in CLIMBABLE
            and (plant.get("branching") or "").lower() not in NOT_A_CROWN)


def can_hold(plant: dict) -> bool:
    """A tree or shrub with a crown that is standing in this year's scene."""
    if not holds_vines(plant):
        return False
    if plant.get("health_state") == "dead":
        return False
    return _num(plant.get("opacity"), 1.0) >= PRESENT_OPACITY


def host_for(vine: dict, plants: list) -> Optional[int]:
    """Index into ``plants`` of the tree or shrub ``vine`` climbs, or None."""
    vx, vy = _num(vine.get("x"), 0.0), _num(vine.get("y"), 0.0)
    reach = max(0.0, _num(vine.get("canopy_m"), 0.0)) / 2.0 + TOUCH_SLACK_M
    best, best_gap = None, None
    for i, host in enumerate(plants):
        if host is vine or not can_hold(host):
            continue
        radius = max(0.0, _num(host.get("canopy_m"), 0.0)) / 2.0
        gap = math.hypot(_num(host.get("x"), 0.0) - vx,
                         _num(host.get("y"), 0.0) - vy) - radius
        if gap > reach:
            continue
        if best_gap is None or gap < best_gap - 1e-9:
            best, best_gap = i, gap
    return best


def drawn_block(vine: dict, host: Optional[dict] = None,
                index: Optional[int] = None) -> dict:
    """How ``vine`` is drawn: climbing ``host`` (at ``index`` in the scene's
    plants), or sprawling on the ground when there is none."""
    vx, vy = _num(vine.get("x"), 0.0), _num(vine.get("y"), 0.0)
    length = max(0.1, _num(vine.get("height_m"), 0.5))       # grown this year
    spread = max(0.2, _num(vine.get("canopy_m"), 0.5))
    if host is None:
        return {"habit": "sprawling", "x": round(vx, 2), "y": round(vy, 2),
                "height_m": round(min(length, SPRAWL_HEIGHT_M), 3),
                "canopy_m": round(spread, 3)}
    hx, hy = _num(host.get("x"), 0.0), _num(host.get("y"), 0.0)
    h_height = max(0.2, _num(host.get("height_m"), 1.0))
    h_canopy = max(0.2, _num(host.get("canopy_m"), 1.0))
    dx, dy = vx - hx, vy - hy
    dist = math.hypot(dx, dy)
    # Planted against the trunk, it still has to climb one side of it.
    ux, uy = (dx / dist, dy / dist) if dist > 1e-6 else (1.0, 0.0)
    out = h_canopy / 2.0 * _FOLIAGE_OUT
    return {
        "habit": "climbing",
        "x": round(hx + ux * out, 2), "y": round(hy + uy * out, 2),
        # As far as the vine reaches, and no further than the host goes.
        "height_m": round(min(length, h_height), 3),
        "canopy_m": round(min(h_canopy, max(0.6, spread)), 3),
        "support": {
            "index": index,
            "name": host.get("common_name") or "",
            "plant_type": host.get("plant_type") or "",
            "x": round(hx, 2), "y": round(hy, 2),
            "height_m": round(h_height, 3), "canopy_m": round(h_canopy, 3),
            # From the host's trunk towards the vine's root, in scene metres
            # (x east, y north): the side of the crown the vine covers.
            "toward": [round(ux, 4), round(uy, 4)],
        },
    }


def apply_vine_habits(plants: list) -> None:
    """Give every vine in a scene's ``plants`` its ``drawn`` block, in place."""
    for vine in plants:
        if is_vine(vine):
            i = host_for(vine, plants)
            vine["drawn"] = drawn_block(
                vine, plants[i] if i is not None else None, i)


def drawn_frame(plant: dict) -> dict:
    """``plant`` as it is DRAWN. For a vine with a ``drawn`` block, a shallow
    copy whose position, height and width are the drawn foliage's; anything
    else is returned unchanged."""
    d = plant.get("drawn")
    if not d:
        return plant
    framed = dict(plant)
    framed.update(x=d["x"], y=d["y"], height_m=d["height_m"],
                  canopy_m=d["canopy_m"])
    return framed

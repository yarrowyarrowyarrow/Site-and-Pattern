"""How a succulent or cactus is drawn: which body, and how big (F177, V2.93).

Design principle P5 — see docs/DESIGN_PHILOSOPHY.md

Until V2.93 the catalogue's cacti and fleshy plants borrowed other plants'
bodies. The prickly pears were the groundcover mat's star of narrow blades (a
cactus's leaves are scales, and ``scale`` is a narrow outline), the ball cactus
and roseroot were the herb mat drawn in 5 mm and 3 cm leaves, and the yucca was
a leafy bush with its flowers inside it. Each now gets one of these, from what
the catalogue records of its habit:

* ``pads`` — flat jointed stems in chains, a first tier leaning low off the
  ground and more standing on their rims (``growth_form: pads``: the prickly
  pears);
* ``ball`` — one or a few spiny globes (``growth_form: globose``: the ball
  cactus);
* ``swords`` — rosettes of stiff narrow leaves from the ground, each sending up
  a flower stalk (a shrub recorded ``branching: rosette`` with narrow leaves:
  soapweed yucca);
* ``fleshy`` — upright stems crowded with fleshy leaves, the flowers on top
  (``growth_form: succulent``: roseroot); on a groundcover, the same stems over
  a mat of short leafy shoots (the stonecrop, ``mat`` in the block).

**Decided once, here** (called from ``scene_contract.build_scene``), as a
``drawn`` block the viewer draws (``html/scene3d/24-succulents.js``) and
``scene_wildlife`` perches on, as the vines (V2.89) and the pond (V2.90) are.
The block says how tall the body is drawn (to the top of the flowers, V2.88's
rule), the ground it covers, and the counts the viewer builds to: how many
balls, rosettes, flower stalks or stems. Where a count is recorded it is used
(``flowering_stems``); where it is not, the choice is said in the function that
makes it.
"""

from __future__ import annotations

from typing import Optional

BODIES = ("pads", "ball", "swords", "fleshy")

#: Leaf outlines that make a woody rosette a yucca's swords.
_NARROW_LEAVES = ("linear", "strap", "needle", "awl")

#: A ball cactus's tallest globe as a share of the recorded height; the
#: flowers at its crown make up the rest.
BALL_OF_HEIGHT = 0.85
#: How wide a globe is for its height: globose to ovoid.
BALL_WIDTH = 0.85
#: Globes at maturity. Floras give "solitary or clustered"; one is drawn at
#: planting and this many once grown, a drawing choice.
BALLS_MATURE = 5

#: Roseroot's stems stand within this share of the height from the centre, on a
#: crown too thick to call a single point.
FLESHY_SPREAD = 0.5


def _grown(plant: dict) -> float:
    """How far grown the plant is, as the flower layer reads it (15-florets.js):
    ``scale_factor`` clamped to 0.25..1."""
    sf = plant.get("scale_factor")
    return max(0.25, min(1.0, 1.0 if sf is None else float(sf)))


def _stems(plant: dict) -> int:
    """Flowering stems at this age: the recorded count scaled by growth, the
    number the flower layer draws inflorescences for (15-florets.js)."""
    fs = plant.get("flowering_stems") or 0
    return max(1, round(_grown(plant) * float(fs))) if fs else 1


def body_for(plant: dict) -> Optional[str]:
    """Which succulent body ``plant`` is drawn with, or None when it is not
    one of these."""
    form = (plant.get("growth_form") or "").lower()
    ptype = (plant.get("plant_type") or "").lower()
    if form == "pads":
        return "pads"
    if form == "globose":
        return "ball"
    if (ptype == "shrub" and (plant.get("branching") or "").lower() == "rosette"
            and (plant.get("leaf_shape") or "").lower() in _NARROW_LEAVES):
        return "swords"
    if form == "succulent":
        return "fleshy"
    return None


def _season(plant: dict) -> list:
    """The months a yucca's flower stalk stands: from its first bloom month to
    the end of its fruit, so the capsules have something to hang on. Empty when
    no bloom is recorded (P9: nothing recorded draws nothing)."""
    bs, be = plant.get("bloom_start") or 0, plant.get("bloom_end") or 0
    if not bs:
        return []
    return [bs, max(be or bs, plant.get("fruit_end") or 0)]


def drawn_block(plant: dict, body: str) -> dict:
    """The ``drawn`` block for one succulent."""
    h = float(plant.get("height_m") or 0.0)
    canopy = float(plant.get("canopy_m") or 0.0)
    block = {"body": body, "x": plant.get("x"), "y": plant.get("y"),
             "height_m": round(h, 3), "canopy_m": round(canopy, 3)}
    if body == "ball":
        # One globe at planting, BALLS_MATURE once grown; the cluster is only
        # as wide as its globes, well inside the ground spaced for it.
        n = 1 + round((BALLS_MATURE - 1) * (_grown(plant) - 0.25) / 0.75)
        ball = BALL_OF_HEIGHT * h
        across = BALL_WIDTH * ball * (1.0 if n == 1 else 1.0 + 0.9 * (n ** 0.5))
        block.update(stems=n, ball_m=round(ball, 3),
                     canopy_m=round(min(canopy or across, across), 3))
    elif body == "swords":
        # One rosette per flowering stem: a yucca's stalk rises from the
        # middle of a rosette, and the rosette flowers again another year.
        n = _stems(plant)
        leaf = float(plant.get("leaf_size_cm") or 40.0) / 100.0 * _grown(plant)
        block.update(stems=n, stalks=n, leaf_m=round(leaf, 3),
                     stalk_months=_season(plant))
    elif body == "fleshy":
        n = _stems(plant)
        if (plant.get("plant_type") or "").lower() == "groundcover":
            # A stonecrop's flowering stems stand over a mat of short leafy
            # shoots that covers the ground it was spaced for, and die after
            # seeding while the mat stays: they stand in the yucca stalk's
            # season.
            block.update(stems=n, mat=True, stalk_months=_season(plant))
        else:
            across = 2.0 * FLESHY_SPREAD * h + 2.0 * float(
                plant.get("leaf_size_cm") or 2.0) / 100.0
            block.update(stems=n,
                         canopy_m=round(min(canopy or across, across), 3))
    return block


def apply_succulent_habits(plants: list) -> None:
    """Write each succulent's ``drawn`` block, in place. A plant that already
    has one (a vine or a wetland plant) is left alone."""
    for p in plants:
        if p.get("drawn"):
            continue
        body = body_for(p)
        if body is not None:
            p["drawn"] = drawn_block(p, body)

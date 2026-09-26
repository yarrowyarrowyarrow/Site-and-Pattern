"""How a wetland plant is drawn: which body, and where the water is (F175, V2.90).

Design principle P5 — see docs/DESIGN_PHILOSOPHY.md

Until V2.90 seventeen aquatics shared one reed tuft. A pond-lily, a submerged
pondweed and an arrowhead are three different bodies, and the one that matters
most to how a pond reads, the floating leaf, was drawn standing up in the air.
Each wetland plant now gets one of these, from what the catalogue records of its
habit (``growth_form``) and its leaves:

* ``floating`` — leaves lying on the water (pond-lily, floating marsh-marigold,
  duckweed);
* ``submerged`` — lives under the water, and only its flowers and shoot tips
  reach the surface (waterweed, milfoil, pondweed, bladderwort);
* ``broadleaf`` — an emergent whose broad leaves stand on stalks (arrowheads,
  water-plantain, calla, buckbean);
* ``whorled`` — an emergent whose stems are clothed in whorls of narrow leaves
  (mare's-tail), drawn by the horsetail builder (14-layers.js) because the two
  are the same shape at this scale;
* ``reed`` — narrow-leaved emergents and tussocks (cattail, bulrush, bur-reed),
  the tuft they always had;
* ``herb`` — an aquatic whose body is a herb's (Water Parsnip is an erect leafy
  umbellifer), drawn by the herb layer.

**Decided once, here** (called from ``scene_contract.build_scene``), as a
``drawn`` block the viewer draws and ``scene_wildlife`` perches on, the V2.88
lesson of the floating flowers for the third time.

**The water.** A scene has water only where a design has a pond structure,
which ``struct_pond.glb`` draws as an opaque sheet ``WATER_SURFACE_M`` above the
ground, an axis-aligned ellipse. A floating or submerged plant inside it is
drawn at that surface; anywhere else at ground level, where a pond-lily in a dry
bed is still visibly a pond-lily. For those two bodies the recorded height is
the stem's length under water, as a vine's is its length (V2.89), not how tall
the plant stands: a floating plant is drawn at most ``FLOATING_ABOVE_M`` above
the surface and a submerged one at most ``SUBMERGED_ABOVE_M``.
"""

from __future__ import annotations

from typing import Optional

#: struct_pond.glb's water: an opaque sheet this far above the ground under the
#: pond, an ellipse with these semi-axes as fractions of the pond's size (2.44 m
#: by 1.798 m at its authored 6 m). tests/test_pond_habit.py reads the model file
#: and keeps the three numbers equal to it.
WATER_SURFACE_M = 0.10
POND_WATER_RX = 2.44 / 6.0
POND_WATER_RY = 1.798 / 6.0

#: Above the water surface: a floating plant's flowers, a submerged one's stalks.
FLOATING_ABOVE_M = 0.05
SUBMERGED_ABOVE_M = 0.10

BODIES = ("floating", "submerged", "broadleaf", "whorled", "reed", "herb")

#: Leaf shapes that make an emergent a reed rather than a broad-leaved plant.
_NARROW_LEAVES = ("", "linear", "awl", "needle", "scale")
#: Grasses, sedges and rushes are drawn as graminoids whatever water they stand
#: in, and horsetails (``jointed``) by their own builder (V2.89).
_GRAMINOIDS = ("grass", "sedge", "rush")
#: Herb habits an aquatic may record, drawn by the herb layer.
_HERB_FORMS = ("erect", "clump", "rosette", "ferny", "mat", "cushion")


def body_for(plant: dict) -> Optional[str]:
    """Which wetland body ``plant`` is drawn with, or None when it is not one of
    the pond's to draw."""
    ptype = (plant.get("plant_type") or "").lower()
    form = (plant.get("growth_form") or "").lower()
    if form == "jointed" or ptype in _GRAMINOIDS:
        return None
    if form in ("floating", "submerged"):
        return form
    if form == "emergent":
        if (plant.get("leaf_arrangement") or "").lower() == "whorled":
            return "whorled"
        if (plant.get("leaf_shape") or "").lower() not in _NARROW_LEAVES:
            return "broadleaf"
        return "reed" if ptype == "aquatic" else None
    if ptype != "aquatic":
        return None
    return "herb" if form in _HERB_FORMS else "reed"


def water_at(x: float, y: float, structures) -> float:
    """Height of the water surface above the ground at scene point ``(x, y)``:
    ``WATER_SURFACE_M`` inside a pond's water, else 0."""
    for s in structures or []:
        if s.get("struct_id") != "pond":
            continue
        size = float(s.get("size_m") or 0.0)
        rx, ry = POND_WATER_RX * size, POND_WATER_RY * size
        if rx <= 0 or ry <= 0:
            continue
        dx = (x - float(s.get("x") or 0.0)) / rx
        dy = (y - float(s.get("y") or 0.0)) / ry
        if dx * dx + dy * dy <= 1.0:
            return WATER_SURFACE_M
    return 0.0


def drawn_block(plant: dict, body: str, structures) -> dict:
    """The ``drawn`` block for one wetland plant."""
    h = float(plant.get("height_m") or 0.0)
    water = 0.0
    if body in ("floating", "submerged"):
        water = water_at(float(plant.get("x") or 0.0),
                         float(plant.get("y") or 0.0), structures)
        above = FLOATING_ABOVE_M if body == "floating" else SUBMERGED_ABOVE_M
        h = water + min(h, above)
    return {"body": body, "water_m": round(water, 3),
            "x": plant.get("x"), "y": plant.get("y"),
            "height_m": round(h, 3),
            "canopy_m": plant.get("canopy_m")}


def apply_pond_habits(plants: list, structures=None) -> None:
    """Write each wetland plant's ``drawn`` block, in place. A plant that
    already has one (a vine, V2.89) is left alone."""
    for p in plants:
        if p.get("drawn"):
            continue
        body = body_for(p)
        if body is not None:
            p["drawn"] = drawn_block(p, body, structures)

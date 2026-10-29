"""
walk_cards.py — what a click in the walk opens (F255, V3.38–V3.39).

Design principle P3 — see docs/DESIGN_PHILOSOPHY.md (relationships matter
more than components: the card is the plant's edges, made readable).

The owner, in Learn › Walk a wild landscape: *"I'd like to be able to click a
plant and read its drop down … this is this plant, here is what it does, here
are creatures it supports … if I click on an animal … it tells a little bit
about that animal, especially the plants it relies on, both on the design and
not yet on the design. Relationality is key."* The walk's hint has said
"left-click a plant to learn about it" since V2.43, and until V3.38 the click
found nothing to show: only the design's 3D preview sent the cards.

:func:`build` is the card data for both windows (``src.scene_dossier``, with
each animal's plants that are not in the scene yet), so the two cards cannot
differ; :func:`push` is the walk's, which offers its own planting list as the
plants *Plant one* can put on the trowel, and :func:`on_plant_chosen` is what
that button does. The cards themselves are drawn by ``html/scene3d/25-cards.js``.
"""

from __future__ import annotations

#: The walks are Alberta's natural communities: the plants an animal would
#: use that are not in the walk yet are the ones native to Alberta.
WALK_PROVINCE = "AB"


def build(scene: dict, *, plantable=(), province: str = "") -> dict:
    """The cards for everything in ``scene``: the dossier with each animal's
    plants beyond the scene (``what_it_feeds.animal_plans``). An empty dict on
    failure: no card is a smaller fault than a broken window."""
    try:
        from src.scene_dossier import build_dossier
        from src.what_it_feeds import animal_plans
        return build_dossier(scene, animal_plans=animal_plans,
                             plantable=tuple(plantable), province=province)
    except Exception:      # noqa: BLE001
        return {}


def push(win, scene: dict) -> None:
    """Send ``win.viewer`` the cards for everything in ``scene``.

    Called with every scene the walk pushes, so a card left open follows the
    year and the plants under it.
    """
    plantable = [p["plant_id"] for p in getattr(win, "_palette", []) or []
                 if p.get("plant_id") is not None]
    win.viewer.set_dossier(build(scene, plantable=plantable,
                                 province=WALK_PROVINCE))


def on_plant_chosen(win, plant_id: int) -> None:
    """*Plant one* on an animal's card: put that plant on the trowel, so the
    next click on the ground plants it. Only the walk's own plants are offered
    (``plantable``), so it is always in the planting list."""
    combo = getattr(win, "_species", None)
    if combo is None:
        return
    for i in range(combo.count()):
        item = combo.itemData(i)
        if isinstance(item, dict) and item.get("plant_id") == int(plant_id):
            combo.setCurrentIndex(i)
            win._plant_btn.setChecked(True)
            win._set_mode("plant")
            win._say.setText(f"Click the ground to plant "
                             f"{item.get('common_name') or 'it'}.")
            return

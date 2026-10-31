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


def plantable(win) -> set:
    """What *Plant one* may put on the walk's trowel: its planting list, and
    any plant that suits the community (``reference_ecosystem.plantable_ids``).
    The first build offered the planting list alone, and every plant on it was
    already in the walk, so no animal's card ever showed the button."""
    ids = {p["plant_id"] for p in getattr(win, "_palette", []) or []
           if p.get("plant_id") is not None}
    community = getattr(win, "_community", "")
    if community:
        # The same for every push in one community: kept on the window, not
        # worked out again on every plant and pull.
        cached = getattr(win, "_plantable_for", None)
        if not cached or cached[0] != community:
            try:
                from src.reference_ecosystem import plantable_ids
                cached = (community, frozenset(plantable_ids(community)))
            except Exception:      # noqa: BLE001
                cached = (community, frozenset())
            win._plantable_for = cached
        ids |= cached[1]
    return ids


def push(win, scene: dict) -> None:
    """Send ``win.viewer`` the cards for everything in ``scene``.

    Called with every scene the walk pushes, so a card left open follows the
    year and the plants under it.
    """
    win.viewer.set_dossier(build(scene, plantable=sorted(plantable(win)),
                                 province=WALK_PROVINCE))


#: The planting list's word for a plant's kind (the glossary's), for a plant
#: *Plant one* adds to it.
_KIND = {"tree": "tree", "shrub": "shrub", "grass": "grass", "sedge": "grass",
         "graminoid": "grass"}


def on_plant_chosen(win, plant_id: int, *,
                    get_plant=None) -> None:
    """*Plant one* on an animal's card: put that plant on the trowel, so the
    next click on the ground plants it. A plant not on the planting list yet
    is added to it first; one the walk does not offer changes nothing."""
    combo = getattr(win, "_species", None)
    if combo is None:
        return
    pid = int(plant_id)
    index = next((i for i in range(combo.count())
                  if isinstance(combo.itemData(i), dict)
                  and combo.itemData(i).get("plant_id") == pid), -1)
    if index < 0:
        if pid not in plantable(win):
            return
        if get_plant is None:
            from src.db.plants import get_plant
        row = get_plant(pid) or {}
        if not row:
            return
        item = {"plant_id": pid,
                "common_name": row.get("common_name") or "plant",
                "scientific_name": row.get("scientific_name") or "",
                "layer": ""}
        kind = _KIND.get((row.get("plant_type") or "").lower(), "wildflower")
        combo.addItem(f"{item['common_name']}  ·  {kind}", item)
        index = combo.count() - 1
    combo.setCurrentIndex(index)
    item = combo.itemData(index)
    win._plant_btn.setChecked(True)
    win._set_mode("plant")
    win._say.setText(f"Click the ground to plant "
                     f"{item.get('common_name') or 'it'}.")

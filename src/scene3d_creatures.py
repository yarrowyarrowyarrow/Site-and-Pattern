"""
scene3d_creatures.py — which pollinator the 3D window's tools are about
(V3.44, F261; split out of ``scene3d_window.py``, which has a line ceiling).

Design principle P5 (make the invisible ecology visible) — see
docs/DESIGN_PHILOSOPHY.md.

The window's *Fly as…*, *Tour the year* and *Show its plants* all read one
list of native bees, butterflies and moths. Until V3.44 the window opened on
the list's first row: *Agapostemon femoratus*, first by genus, known only by
its Latin name, whether or not the design held a plant it uses. *Show its
plants* then lit nothing, on most designs.

:func:`default_row` picks the animal the tools start on: one with an English
name (``yard_overview_items.english_name``, WD-7) that the records have
feeding on the most plants **standing in this design**; else the first with an
English name. The person's own choice is never replaced.

Qt-free; the window puts :func:`rows` in its list.
"""

from __future__ import annotations

from typing import Iterable, Optional


def rows() -> list:
    """``[(label, creature | None), ...]`` in list order: bees genus by genus
    under a heading each, then butterflies and moths. A heading's creature is
    ``None``; a creature is ``{taxon, fid, kind, name}``."""
    out: list = []
    try:
        from src.bee_habitat import list_target_bees
        bees = list_target_bees()
    except Exception:      # noqa: BLE001 — a data fault must not stop the window
        bees = []
    genus = None
    for b in bees:
        if b["genus"] != genus:
            genus = b["genus"]
            out.append((f"── {genus} ──", None))
        label = (f"    {b['common_name']} (any {b['genus']})" if b["is_group"]
                 else f"    {b['common_name']}")
        out.append((label, {"taxon": "bee", "fid": b["id"], "kind": "bee",
                            "name": b["common_name"],
                            "scientific_name": b.get("scientific_name", "")}))
    try:
        from src.lep_habitat import list_target_lepidoptera
        leps = list_target_lepidoptera()
    except Exception:      # noqa: BLE001
        leps = []
    if leps:
        out.append(("── Butterflies & Moths ──", None))
        for lp in leps:
            # A skipper flies like a butterfly for the avatar's purposes.
            kind = "moth" if lp["kind"] == "moth" else "butterfly"
            icon = "🦋" if kind == "butterfly" else "🌙"
            out.append((f"    {icon} {lp['common_name']}",
                        {"taxon": "lep", "fid": lp["id"], "kind": kind,
                         "name": lp["common_name"],
                         "scientific_name": lp.get("scientific_name", "")}))
    return out


def _english(creature: dict) -> bool:
    from src.yard_overview_items import english_name
    return bool(english_name({"name": creature.get("name", ""),
                              "scientific_name":
                                  creature.get("scientific_name", "")}))


def default_row(listed: list, plant_ids: Iterable[int], *,
                fed=None) -> Optional[int]:
    """The index in ``listed`` (:func:`rows`) the tools should start on, or
    ``None`` for an empty list.

    ``fed`` is injectable for tests: ``plant_ids -> [{fauna_id, food}, ...]``
    with the animal on the most plants first
    (``what_it_feeds.animals_fed``)."""
    by_fid = {c["fid"]: i for i, (_label, c) in enumerate(listed)
              if c is not None and _english(c)}
    ids = [int(p) for p in plant_ids or [] if p is not None]
    if ids and by_fid:
        try:
            if fed is None:
                from src.what_it_feeds import animals_fed as fed
            for animal in fed(ids):
                if animal.get("food") and animal.get("fauna_id") in by_fid:
                    return by_fid[animal["fauna_id"]]
        except Exception:      # noqa: BLE001 — fall back to the first named
            pass
    if by_fid:
        return min(by_fid.values())
    return next((i for i, (_l, c) in enumerate(listed) if c is not None),
                None)


def plant_ids_for(creature: dict) -> list:
    """The plants the creature is recorded on: a bee's flowers, or a
    butterfly's or moth's flowers and its caterpillar's food plants."""
    fid = creature["fid"]
    try:
        if creature["taxon"] == "bee":
            from src.bee_habitat import target_plant_ids_for_bee
            return target_plant_ids_for_bee(fid)
        from src.lep_habitat import (nectar_plant_ids_for_lep,
                                     larval_host_ids_for_lep)
        return sorted(set(nectar_plant_ids_for_lep(fid))
                      | set(larval_host_ids_for_lep(fid)))
    except Exception:      # noqa: BLE001
        return []

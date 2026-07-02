"""
creature_community.py — "Design a community for a creature": assemble a plant
community tailored to one native bee, butterfly or moth from the fauna data
spine (F37). This is the backing generator for the plant-community panel's
"For a creature…" option (V2.12).

Given a fauna id it gathers the plants that species actually needs — adult
nectar/pollen plants and, for butterflies/moths, the larval host plants its
caterpillars feed on — buckets them by vegetation layer, caps the set to a
plantable size, and lays them out in concentric rings (canopy at the centre,
nectar herbs on the outer ring). The result is a ready-to-save community.

Design principle P3 / P10 (the plant↔animal edge is the unit of value), P8
(habitat is built *for* a species, across its life stages), P5 (start from what
the design already supports), and P9 (honest: non-feeding moths get a
host-plant-only community, never invented nectar). Qt-free — the panel wraps it.
See docs/DESIGN_PHILOSOPHY.md.
"""

from __future__ import annotations

import math
from typing import Callable, Optional

from src.db import fauna as _fauna


# plant_type → vegetation layer (the polyculture layer vocabulary).
_TYPE_LAYER = {
    "tree": "overstory",
    "shrub": "shrub_layer",
    "vine": "vine",
    "groundcover": "groundcover",
    "grass": "herbaceous", "sedge": "herbaceous", "rush": "herbaceous",
    "herb": "herbaceous", "wildflower": "herbaceous", "fern": "herbaceous",
    "aquatic": "herbaceous",
}

# Layout: base ring radius (m) + how many of that layer to keep. Ordered from
# the centre outward so the tallest plants anchor the middle.
_LAYER_PLAN = [
    ("overstory",   0.0, 2),
    ("understory",  2.5, 2),
    ("shrub_layer", 3.5, 3),
    ("vine",        1.4, 1),
    ("herbaceous",  5.5, 6),
    ("groundcover", 6.8, 2),
]
_LAYER_RADIUS = {layer: r for layer, r, _ in _LAYER_PLAN}
_LAYER_ORDER = [layer for layer, _, _ in _LAYER_PLAN]


def _layer_for(plant: dict) -> str:
    layer = _TYPE_LAYER.get(plant.get("plant_type"), "herbaceous")
    # A small tree drops to the understory ring so it doesn't crowd the centre.
    if layer == "overstory" and (plant.get("mature_height_meters") or 99) < 6:
        layer = "understory"
    return layer


def _gather(fauna_id: int):
    """Return (taxon, name, nectar_ids, host_ids) for the creature, or None."""
    row = _fauna.get_fauna(fauna_id)
    if not row:
        return None
    taxon = row.get("taxon")
    name = row.get("common_name") or "this creature"
    nectar_ids: list[int] = []
    host_ids: list[int] = []
    if taxon == "bee":
        from src.bee_habitat import floral_matches_for_bee
        seen = set()
        for m in floral_matches_for_bee(fauna_id):
            if m.plant_id not in seen:
                seen.add(m.plant_id)
                nectar_ids.append(m.plant_id)
    elif taxon == "lepidoptera":
        from src.lep_habitat import (nectar_plant_ids_for_lep,
                                     larval_host_ids_for_lep)
        nectar_ids = nectar_plant_ids_for_lep(fauna_id)
        host_ids = larval_host_ids_for_lep(fauna_id)
    else:
        return None
    return taxon, name, nectar_ids, host_ids


def _community_name(taxon: str, name: str) -> str:
    if name.lower() == "monarch":
        return "Monarch Waystation"
    if taxon == "bee":
        return f"{name} Forage Garden"
    return f"{name} Garden"


def _needs_note(fauna_id: int, taxon: str, name: str) -> str:
    """A short, honest habitat note: what to leave for this creature to complete
    its life cycle (overwintering / nesting)."""
    if taxon == "lepidoptera":
        attrs = _fauna.lep_attributes_for(fauna_id)
        stage = attrs.get("overwintering_stage")
        note = {
            "egg": "It overwinters as eggs on its host plants — leave the stems standing.",
            "larva": "It overwinters as a caterpillar in the leaf litter — leave the leaves.",
            "pupa": "It overwinters as a chrysalis/cocoon on stems and litter — tidy lightly.",
            "adult": "The adult overwinters sheltered — leave brush, bark and leaf piles.",
            "migrant": "It migrates rather than overwintering here — late-season nectar fuels the trip.",
        }.get(stage, "")
        return note
    # bee
    try:
        from src.bee_habitat import nesting_guidance
        g = nesting_guidance(fauna_id)
        return g.headline + "." if g and g.headline else ""
    except Exception:      # noqa: BLE001
        return ""


def build_creature_community(fauna_id: int, *,
                             get_plant: Optional[Callable] = None,
                             max_members: int = 14) -> Optional[dict]:
    """Assemble a plant community for ``fauna_id`` (a bee, butterfly or moth).

    Returns ``{"name", "description", "fauna_id", "members": [...]}`` where each
    member is ``{plant_id, common_name, layer, functions, role, offset_x,
    offset_y, notes}`` ready for ``polycultures.replace_polyculture_members``.
    Returns ``None`` if the fauna id isn't a bee/lep or nothing in the plant DB
    supports it.
    """
    if get_plant is None:
        from src.db.plants import get_plant as _gp
        get_plant = _gp

    gathered = _gather(fauna_id)
    if gathered is None:
        return None
    taxon, name, nectar_ids, host_ids = gathered

    host_set = set(host_ids)
    # Preserve host plants preferentially (a butterfly garden without its
    # caterpillar host is only half a habitat), then nectar plants.
    ordered: list[tuple[int, str]] = []   # (plant_id, kind) kind ∈ nectar|host
    seen: set[int] = set()
    for pid in host_ids:
        if pid not in seen:
            seen.add(pid); ordered.append((pid, "host"))
    for pid in nectar_ids:
        if pid not in seen:
            seen.add(pid); ordered.append((pid, "nectar"))
    if not ordered:
        return None

    # Bucket by vegetation layer, keeping host plants first within each bucket.
    buckets: dict[str, list[dict]] = {ly: [] for ly in _LAYER_ORDER}
    for pid, kind in ordered:
        p = get_plant(pid)
        if not p:
            continue
        layer = _layer_for(p)
        buckets.setdefault(layer, [])
        buckets[layer].append({"plant_id": pid, "kind": kind, "layer": layer,
                               "common_name": p.get("common_name", "")})

    # Cap per layer (host plants already sorted first so they survive the cap),
    # then globally, keeping the layer order so structure is preserved.
    members: list[dict] = []
    for layer, _r, cap in _LAYER_PLAN:
        members.extend(buckets.get(layer, [])[:cap])
    members = members[:max_members]
    if not members:
        return None

    # Lay out concentric rings by layer; even angular spacing within each layer.
    per_layer_count: dict[str, int] = {}
    for m in members:
        per_layer_count[m["layer"]] = per_layer_count.get(m["layer"], 0) + 1
    idx_in_layer: dict[str, int] = {}
    phase = {"overstory": 0.0, "understory": 0.6, "shrub_layer": 1.1,
             "vine": 2.0, "herbaceous": 0.3, "groundcover": 1.7}
    n_nectar = n_host = 0
    for m in members:
        layer = m["layer"]
        n = per_layer_count[layer]
        i = idx_in_layer.get(layer, 0)
        idx_in_layer[layer] = i + 1
        r = _LAYER_RADIUS.get(layer, 5.0)
        if n <= 1 and r == 0.0:
            ox = oy = 0.0                       # a lone canopy tree sits centre
        else:
            if r == 0.0:
                r = 2.0                         # spread a multi-tree canopy off-origin
            ang = phase.get(layer, 0.0) + (i / max(1, n)) * math.tau
            ox = round(math.cos(ang) * r, 2)
            oy = round(math.sin(ang) * r, 2)
        is_host = m["kind"] == "host"
        m["functions"] = [] if is_host else ["pollinator"]
        m["offset_x"] = ox
        m["offset_y"] = oy
        m["notes"] = (f"Caterpillar host for the {name}" if is_host
                      else f"Nectar/pollen for the {name}")
        if is_host:
            n_host += 1
        else:
            n_nectar += 1
        m.pop("kind", None)

    # Description: what the community does + the honesty note.
    bits = []
    if n_nectar:
        bits.append(f"{n_nectar} nectar/pollen plant{'s' if n_nectar != 1 else ''} "
                    f"for the adults")
    if n_host:
        bits.append(f"{n_host} caterpillar host plant{'s' if n_host != 1 else ''} "
                    f"for its young")
    lead = " and ".join(bits) if bits else "the plants it depends on"
    note = _needs_note(fauna_id, taxon, name)
    desc = (f"A plant community tailored to the {name}: {lead}, arranged in "
            f"layers from a canopy centre out to a nectar-rich edge.")
    if note:
        desc += " " + note

    return {
        "fauna_id": fauna_id,
        "name": _community_name(taxon, name),
        "description": desc,
        "members": members,
    }

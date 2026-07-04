"""
chickadee_scenario.py — "feed a chickadee brood" provisioning scenario (F47).

Tallamy's single most quotable number: **one clutch of chickadees needs
6,000–9,000 caterpillars** to fledge (Tallamy & Shropshire 2009). This module
turns the user's design into that story — it tallies the caterpillar-producing
capacity of the placed larval-host plants and weighs it against a brood's need,
then delivers a pass / partway / short verdict and names the keystone plants
doing the work.

It extends the app's embodiment family from "be a bee / fly as a butterfly" to
"provision a bird": the food web is otherwise invisible, and a hungry brood
makes it concrete without inventing precision.

Design principle P3 (relationships matter more than components — a bird is fed
by an edge, plant→caterpillar→nestling, not by a plant), P6 (make ecological
value legible — translate "hosts N moth species" into "raises a brood"), and P9
(uncertainty is a feature — the capacity is an honest **range**, never a single
fake number). See docs/DESIGN_PHILOSOPHY.md.

Qt-free and dependency-injectable: the panel, the scripting API and the tests
share one definition. It reads the same larval-host edges the Habitat Score
does — no new data.
"""

from __future__ import annotations

from typing import Callable, Optional

# A chickadee (Poecile atricapillus) brood's caterpillar demand — Tallamy &
# Shropshire (2009). Kept as an honest range; we never collapse it to one value.
BROOD_NEED_LOW = 6000
BROOD_NEED_HIGH = 9000

# Rough per-mature-plant caterpillar yield PER larval-host lepidopteran species
# it carries. A deliberately coarse biomass proxy (P9): a productive keystone
# host carrying ~a dozen moth species lands in the low-thousands, so a few such
# plants can provision a brood — matching Tallamy's "a couple of native keystone
# trees" rule of thumb. Presented only as a low–high band, never a point value.
CATS_PER_HOST_SPECIES_LOW = 150
CATS_PER_HOST_SPECIES_HIGH = 400

# Named keystone starting points to suggest when a design falls short. These are
# the classic prairie/parkland caterpillar factories, not Indigenous plant-use
# knowledge (Principle 12) — purely the larval-host relationship.
_KEYSTONE_SUGGESTIONS = "willow, aspen, native cherry, goldenrod, or aster"


def _distinct_counts(placed_plants: list[dict]) -> dict[int, int]:
    """``{plant_id: n_instances}`` over the placed-plant list."""
    counts: dict[int, int] = {}
    for p in placed_plants or []:
        pid = p.get("plant_id")
        if pid is not None:
            counts[pid] = counts.get(pid, 0) + 1
    return counts


def _name_for(placed_plants: list[dict], plant_id: int,
              get_plant: Optional[Callable]) -> str:
    for p in placed_plants or []:
        if p.get("plant_id") == plant_id and p.get("common_name"):
            return p["common_name"]
    if get_plant is None:
        from src.db.plants import get_plant as _gp
        get_plant = _gp
    row = get_plant(plant_id) or {}
    return row.get("common_name") or f"plant {plant_id}"


def chickadee_provision(placed_plants: list[dict], *,
                        get_keystone: Optional[Callable] = None,
                        supported_leps: Optional[Callable] = None,
                        get_plant: Optional[Callable] = None) -> dict:
    """Estimate whether ``placed_plants`` could provision a chickadee brood.

    Returns a JSON-friendly dict:

      * ``caterpillars_low`` / ``caterpillars_high`` — the design's estimated
        seasonal caterpillar capacity, as a range;
      * ``brood_need_low`` / ``brood_need_high`` — 6,000 / 9,000;
      * ``broods_low`` / ``broods_high`` — how many broods that capacity covers
        (conservative / optimistic);
      * ``n_host_species`` — distinct larval-host lepidoptera the design carries;
      * ``host_plants`` — the caterpillar factories, richest keystone first, each
        ``{plant_id, common_name, count, keystone_rank, caterpillars_low/high}``;
      * ``status`` — ``'none' | 'short' | 'partway' | 'clears'``;
      * ``verdict`` — a plain-language story.

    All data access is injectable for tests; defaults read the DB.
    """
    if get_keystone is None:
        from src.db.fauna import keystone_rank_lepidoptera as get_keystone
    if supported_leps is None:
        from src.db.fauna import lepidoptera_supported_by_plants as supported_leps

    counts = _distinct_counts(placed_plants)
    host_plants: list[dict] = []
    cap_low = cap_high = 0
    for pid, n in counts.items():
        rank = int(get_keystone(pid) or 0)
        if rank <= 0:
            continue
        plow = n * rank * CATS_PER_HOST_SPECIES_LOW
        phigh = n * rank * CATS_PER_HOST_SPECIES_HIGH
        cap_low += plow
        cap_high += phigh
        host_plants.append({
            "plant_id": pid,
            "common_name": _name_for(placed_plants, pid, get_plant),
            "count": n,
            "keystone_rank": rank,
            "caterpillars_low": plow,
            "caterpillars_high": phigh,
        })
    # Richest caterpillar factories first (rank × count), then by name.
    host_plants.sort(key=lambda h: (-(h["keystone_rank"] * h["count"]),
                                    h["common_name"].lower()))

    n_host_species = len(supported_leps(list(counts.keys())))

    status = _status(cap_low, cap_high)
    broods_low = round(cap_low / BROOD_NEED_HIGH, 2)   # conservative
    broods_high = round(cap_high / BROOD_NEED_LOW, 2)  # optimistic

    return {
        "caterpillars_low": cap_low,
        "caterpillars_high": cap_high,
        "brood_need_low": BROOD_NEED_LOW,
        "brood_need_high": BROOD_NEED_HIGH,
        "broods_low": broods_low,
        "broods_high": broods_high,
        "n_host_species": n_host_species,
        "host_plants": host_plants,
        "status": status,
        "verdict": _verdict(status, cap_low, cap_high, host_plants),
    }


def _status(cap_low: int, cap_high: int) -> str:
    if cap_high <= 0:
        return "none"
    if cap_low >= BROOD_NEED_LOW:      # conservative estimate meets the minimum
        return "clears"
    if cap_high >= BROOD_NEED_LOW:     # optimistic estimate reaches the minimum
        return "partway"
    return "short"


def _top_names(host_plants: list[dict], k: int = 3) -> str:
    names = [h["common_name"] for h in host_plants[:k]]
    if not names:
        return ""
    if len(names) == 1:
        return names[0]
    return ", ".join(names[:-1]) + " and " + names[-1]


def _fmt_range(lo: int, hi: int) -> str:
    return f"~{lo:,}–{hi:,}"


def _verdict(status: str, cap_low: int, cap_high: int,
             host_plants: list[dict]) -> str:
    need = f"{BROOD_NEED_LOW:,}–{BROOD_NEED_HIGH:,}"
    cap = _fmt_range(cap_low, cap_high)
    tops = _top_names(host_plants)
    if status == "none":
        return (f"A chickadee brood needs {need} caterpillars to fledge — and "
                f"this design grows no larval-host plants, so a brood would go "
                f"hungry. Start with keystone hosts: {_KEYSTONE_SUGGESTIONS}.")
    if status == "clears":
        return (f"🐦 This design could raise a chickadee brood. Its "
                f"{len(host_plants)} caterpillar-host plant"
                f"{'s' if len(host_plants) != 1 else ''} could produce {cap} "
                f"caterpillars a season — a brood needs {need}. The keystone "
                f"workhorses: {tops}.")
    if status == "partway":
        return (f"Partway there: {cap} caterpillars against the {need} a brood "
                f"needs. {tops} carr{'y' if _ends_plural(tops) else 'ies'} what "
                f"there is — add more keystone hosts ({_KEYSTONE_SUGGESTIONS}) "
                f"to close the gap.")
    return (f"A chickadee brood would go hungry here: only {cap} caterpillars "
            f"against the {need} needed. {tops} carr"
            f"{'y' if _ends_plural(tops) else 'ies'} the load — add keystone "
            f"hosts ({_KEYSTONE_SUGGESTIONS}) to build real capacity.")


def _ends_plural(tops: str) -> bool:
    """True when the subject phrase is plural (contains 'and' or a comma)."""
    return (" and " in tops) or ("," in tops)

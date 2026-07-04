"""
plant_impact.py — "pull-a-plant" impact simulator (F46).

The app teaches by *showing* what a design provides. This module lets the user
learn the other way: by **breaking it**. Pick a placed plant and preview what
removing it would cost — the wildlife species that lose all their support,
whether the Tallamy food-web chain snaps, and the Habitat Value Score delta.

Design principle P3 (relationships matter more than components — a plant's worth
is the edges it carries, and pulling it makes those edges visible), P10 (design
for relationships, not objects), and P5 (start from what the design already
has). Honest about redundancy (P9): if another copy of the species remains,
nothing is lost, and the result says so — teaching that duplication is
resilience. See docs/DESIGN_PHILOSOPHY.md.

Qt-free: it recomputes :func:`src.habitat_score.compute_habitat_score` with and
without the plant and diffs :func:`src.db.fauna.fauna_supported_by_plants`, so
the panel, the scripting API and the tests share one definition of "what this
plant is worth here". No new data — it reads the same edges the score does.
"""

from __future__ import annotations

from typing import Callable, Optional

from src.habitat_score import compute_habitat_score

_TAXA = ("lepidoptera", "bird", "bee", "other_insect", "mammal")
_TAXON_LABEL = {
    "lepidoptera": "butterflies & moths", "bird": "birds", "bee": "bees",
    "other_insect": "other insects", "mammal": "mammals",
}
_TAXON_LABEL_SING = {
    "lepidoptera": "butterfly/moth", "bird": "bird", "bee": "bee",
    "other_insect": "other insect", "mammal": "mammal",
}


def _taxon_phrase(taxon: str, n: int) -> str:
    return f"{n} {(_TAXON_LABEL if n != 1 else _TAXON_LABEL_SING)[taxon]}"


def _distinct_ids(plants: list[dict]) -> list[int]:
    return list({p["plant_id"] for p in plants if p.get("plant_id") is not None})


def _fauna_sets(plant_ids: list[int]) -> dict[str, set]:
    from src.db.fauna import fauna_supported_by_plants
    return {t: fauna_supported_by_plants(plant_ids, taxon=t) for t in _TAXA}


def _fauna_names(fids: set) -> list[str]:
    if not fids:
        return []
    from src.db.fauna import get_fauna
    names = []
    for fid in fids:
        row = get_fauna(fid)
        if row and row.get("common_name"):
            names.append(row["common_name"])
    return sorted(names, key=str.lower)


def pull_plant_impact(placed_plants: list[dict],
                      structures: Optional[list[dict]],
                      plant_id: int, *,
                      get_plant: Optional[Callable] = None) -> Optional[dict]:
    """Preview the cost of removing **one** occurrence of ``plant_id``.

    Removes a single placed instance (so the result honestly reflects any
    redundant copies that remain), recomputes the habitat score, and diffs the
    supported-fauna sets. Returns a JSON-friendly dict (see module docstring for
    the shape), or ``None`` if ``plant_id`` isn't placed.
    """
    structures = structures or []
    idx = next((i for i, p in enumerate(placed_plants)
                if p.get("plant_id") == plant_id), None)
    if idx is None:
        return None

    kept = placed_plants[:idx] + placed_plants[idx + 1:]
    remaining_copies = sum(1 for p in kept if p.get("plant_id") == plant_id)

    before = compute_habitat_score(placed_plants, structures)
    after = compute_habitat_score(kept, structures)

    score_before = before.total if before else 0
    score_after = after.total if after else 0
    fw_before = (before.food_web.get("status") if before else "empty") or "empty"
    fw_after = (after.food_web.get("status") if after else "empty") or "empty"
    cat_before = before.food_web.get("n_caterpillars", 0) if before else 0
    cat_after = after.food_web.get("n_caterpillars", 0) if after else 0

    # Species the DESIGN loses (supported before, gone after) — the plant's true
    # keystone weight *here*. Empty when a redundant copy remains.
    before_sets = _fauna_sets(_distinct_ids(placed_plants))
    after_sets = _fauna_sets(_distinct_ids(kept))
    lost_by_taxon: dict[str, list[str]] = {}
    n_lost = 0
    for t in _TAXA:
        lost = before_sets[t] - after_sets[t]
        if lost:
            names = _fauna_names(lost)
            lost_by_taxon[t] = names
            n_lost += len(lost)

    # This plant's own reach (how many species it supports at all) — context
    # that stays meaningful even when redundancy means nothing is lost.
    from src.db.fauna import fauna_for_plant
    reach = {r["id"] for r in fauna_for_plant(plant_id)}

    name = _plant_name(placed_plants[idx], plant_id, get_plant)
    chain_snaps = (fw_before == "complete" and fw_after != "complete")

    return {
        "plant_id": plant_id,
        "common_name": name,
        "remaining_copies": remaining_copies,
        "score_before": score_before,
        "score_after": score_after,
        "score_delta": score_after - score_before,
        "species_supported": len(reach),
        "species_lost": n_lost,
        "species_lost_by_taxon": lost_by_taxon,
        "food_web_before": fw_before,
        "food_web_after": fw_after,
        "chain_snaps": chain_snaps,
        "caterpillars_before": cat_before,
        "caterpillars_after": cat_after,
        "verdict": _verdict(name, n_lost, lost_by_taxon, remaining_copies,
                            chain_snaps, score_after - score_before, len(reach)),
    }


def _plant_name(placed: dict, plant_id: int,
                get_plant: Optional[Callable]) -> str:
    if placed.get("common_name"):
        return placed["common_name"]
    if get_plant is None:
        from src.db.plants import get_plant as _gp
        get_plant = _gp
    row = get_plant(plant_id) or {}
    return row.get("common_name") or "this plant"


def _verdict(name: str, n_lost: int, lost_by_taxon: dict,
             remaining_copies: int, chain_snaps: bool,
             delta: int, reach: int) -> str:
    """Plain-language, honest summary of pulling the plant."""
    if remaining_copies > 0 and n_lost == 0:
        return (f"Pulling one {name} costs nothing here — "
                f"{remaining_copies} more still feed the same species. "
                f"That redundancy is resilience.")
    if n_lost == 0:
        if reach:
            return (f"{name} feeds {reach} species, but every one is also "
                    f"supported by another plant — so removing it loses none. "
                    f"Redundancy is resilience.")
        return (f"No documented wildlife depends on {name} in this design, so "
                f"removing it costs no supported species (Score {_fmt(delta)}).")
    parts = ", ".join(_taxon_phrase(t, len(v))
                      for t, v in lost_by_taxon.items())
    lead = (f"Remove {name} and this design loses {n_lost} wildlife "
            f"species — {parts}.")
    if chain_snaps:
        lead += (" The food-web chain snaps: without it the caterpillars-to-"
                 "birds link no longer closes.")
    lead += f" Habitat Score {_fmt(delta)}."
    return lead


def _fmt(delta: int) -> str:
    if delta > 0:
        return f"+{delta}"
    if delta < 0:
        return f"{delta}"
    return "unchanged"

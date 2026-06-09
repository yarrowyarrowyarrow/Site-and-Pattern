"""
src/sourcing.py — cost / sourcing helpers for generated designs (V1.45).

Plant prices in PermaDesign are deliberately modelled as a **range** per single
nursery plant, not an exact figure: Alberta retail prices vary by nursery,
region and year. A plant carries an explicit ``price_low_cad`` / ``price_high_cad``
when we have one; otherwise a per-``plant_type`` default (below) is used so a
design can always be costed. Everything here is an *estimate* and is surfaced
in the UI with that disclaimer.

This module is the single source of truth for the default ranges — the seeding
script (``scripts/apply_sourcing_data.py``) imports them so the seeded data and
the runtime fallback never drift. Kept Qt-free so the CLI, engine and tests can
all use it.
"""

from __future__ import annotations

# Default retail price range (CAD) for ONE nursery plant, by ``plant_type``.
# Research-backed (Alberta native nurseries + garden centres, 2025–26):
#   herbaceous plug/pot ~$8–16 · vine ~$15–35 · shrub ~$25–50 · tree ~$45–120 ·
#   bulb/tuber ~$5–12. See the plan / apply_sourcing_data.py header for sources.
TYPE_PRICE_DEFAULTS: dict[str, tuple[float, float]] = {
    "herb":        (8.0, 16.0),
    "groundcover": (8.0, 16.0),
    "grass":       (8.0, 16.0),
    "sedge":       (8.0, 16.0),
    "rush":        (8.0, 16.0),
    "fern":        (8.0, 16.0),
    "aquatic":     (8.0, 16.0),
    "vine":        (15.0, 35.0),
    "shrub":       (25.0, 50.0),
    "tree":        (45.0, 120.0),
    "root":        (5.0, 12.0),
}
_FALLBACK_RANGE = (8.0, 16.0)  # unknown plant_type → herb-like


def plant_price_range(plant: dict) -> tuple[float, float]:
    """Return ``(low, high)`` CAD for one plant, preferring its explicit price
    columns and falling back to the ``plant_type`` default."""
    lo = plant.get("price_low_cad")
    hi = plant.get("price_high_cad")
    if lo is not None and hi is not None and (lo or hi):
        lo, hi = float(lo), float(hi)
        return (min(lo, hi), max(lo, hi))
    ptype = (plant.get("plant_type") or "").strip().lower()
    return TYPE_PRICE_DEFAULTS.get(ptype, _FALLBACK_RANGE)


def _as_pairs(items) -> list[tuple]:
    """Normalise ``items`` (placed-plant dicts OR ``(plant_id, qty)`` tuples)
    into ``(plant_id, qty)`` pairs."""
    pairs: list[tuple] = []
    for it in items or []:
        if isinstance(it, dict):
            pairs.append((it.get("plant_id") or it.get("id"),
                          int(it.get("quantity") or 1)))
        else:
            # (plant_id, qty) or (plant_id, qty, layout) — V1.50 added a layout
            # element; only the first two matter for costing.
            pid, qty = it[0], it[1]
            pairs.append((pid, int(qty or 1)))
    return pairs


def estimate_cost(items, get_plant=None) -> tuple[float, float]:
    """Total estimated ``(low, high)`` CAD across ``items`` × quantity.

    ``items`` may be placed-plant dicts (``plant_id``/``quantity``) or
    ``(plant_id, qty)`` tuples. ``get_plant`` is injectable for tests; it
    defaults to the real catalogue lookup."""
    if get_plant is None:
        from src.db.plants import get_plant as _gp
        get_plant = _gp
    total_lo = total_hi = 0.0
    cache: dict = {}
    for pid, qty in _as_pairs(items):
        if pid is None:
            continue
        rec = cache.get(pid)
        if rec is None:
            rec = get_plant(pid) or {}
            cache[pid] = rec
        lo, hi = plant_price_range(rec)
        total_lo += lo * qty
        total_hi += hi * qty
    return (round(total_lo, 2), round(total_hi, 2))


def polyculture_cost(poly_ids, get_polyculture=None,
                     get_plant=None) -> tuple[float, float]:
    """Estimated ``(low, high)`` CAD to plant the given communities — the sum of
    their member plants. Used to budget the (atomic) communities before trimming
    individual plants."""
    if get_polyculture is None:
        from src.db.polycultures import get_polyculture_by_id as get_polyculture
    low = high = 0.0
    for pid in poly_ids or []:
        pc = get_polyculture(pid) or {}
        lo, hi = estimate_cost(pc.get("members", []), get_plant=get_plant)
        low += lo
        high += hi
    return (round(low, 2), round(high, 2))


def trim_to_budget(items, budget, get_plant=None) -> tuple[list, int]:
    """Drop the most expensive items until the design's *midpoint* estimate
    fits ``budget``, keeping at least one. Returns ``(kept_items, n_dropped)``.

    Enforcing the budget at selection time (before placement) avoids needing a
    project-removal API. ``items`` are ``(plant_id, qty)`` tuples or placed-plant
    dicts; the return preserves the input element type/order of the kept items."""
    if not budget or budget <= 0:
        return (list(items or []), 0)
    if get_plant is None:
        from src.db.plants import get_plant as _gp
        get_plant = _gp

    items = list(items or [])
    pairs = _as_pairs(items)
    cache: dict = {}

    def midpoint(pid, qty) -> float:
        rec = cache.get(pid)
        if rec is None:
            rec = (get_plant(pid) or {}) if pid is not None else {}
            cache[pid] = rec
        lo, hi = plant_price_range(rec)
        return (lo + hi) / 2.0 * qty

    # Index items by descending unit midpoint so we drop the priciest first.
    order = sorted(range(len(items)),
                   key=lambda i: midpoint(*pairs[i]), reverse=True)
    drop: set[int] = set()
    total = sum(midpoint(*p) for p in pairs)
    for i in order:
        if total <= budget or len(items) - len(drop) <= 1:
            break
        drop.add(i)
        total -= midpoint(*pairs[i])

    kept = [it for idx, it in enumerate(items) if idx not in drop]
    return (kept, len(drop))


def format_cost(low: float, high: float) -> str:
    """Compact ``$low–$high`` (whole-dollar) for UI/CLI display."""
    return f"${low:,.0f}–${high:,.0f}"


# ── Whole-design costing (C1) ────────────────────────────────────────────────
#
# A design is more than its plants: structures (ponds, fences, raised beds…)
# carry an install cost, and new beds need mulch. These let the app price the
# *whole* design, not just the plant order — same estimate-with-a-disclaimer
# spirit as the plant ranges above. Kept Qt-free and dependency-injectable.

# Bulk landscape mulch, delivered (CAD per cubic metre). Coarse Alberta estimate;
# arborist chips can be free, bagged retail is dearer — this brackets the middle.
MULCH_PRICE_PER_M3: tuple[float, float] = (35.0, 75.0)
DEFAULT_MULCH_DEPTH_CM: float = 7.5  # a typical establishment mulch depth


def structure_cost(structures, get_structure=None) -> tuple[float, float]:
    """Total estimated ``(low, high)`` CAD install cost across placed structures.

    ``structures`` may be structure-definition dicts (as stored on a placed
    feature's ``struct_def``) or bare structure ids. A structure with no
    ``install_cost_cad`` contributes 0 — retained snags/brush piles and existing
    trees/buildings cost nothing to install. ``get_structure`` is injectable for
    tests; it defaults to the real catalogue lookup."""
    if get_structure is None:
        from src.db.structures import get_structure as _gs
        get_structure = _gs
    lo = hi = 0.0
    for s in structures or []:
        rec = s if isinstance(s, dict) else (get_structure(s) or {})
        ic = rec.get("install_cost_cad")
        if ic is None and rec.get("id"):   # older project: stamp from catalogue
            ic = (get_structure(rec["id"]) or {}).get("install_cost_cad")
        if ic:
            lo += float(ic[0])
            hi += float(ic[1])
    return (round(lo, 2), round(hi, 2))


def mulch_cost(area_m2, depth_cm: float = DEFAULT_MULCH_DEPTH_CM,
               price_per_m3: tuple[float, float] = MULCH_PRICE_PER_M3
               ) -> tuple[float, float]:
    """Estimated ``(low, high)`` CAD to mulch ``area_m2`` at ``depth_cm`` deep."""
    area = max(0.0, float(area_m2 or 0.0))
    volume_m3 = area * (max(0.0, float(depth_cm)) / 100.0)
    return (round(volume_m3 * price_per_m3[0], 2),
            round(volume_m3 * price_per_m3[1], 2))


def design_cost(plants, structures=None, mulch_area_m2: float = 0.0,
                get_plant=None, get_structure=None) -> dict:
    """Whole-design cost breakdown. Returns a dict of ``(low, high)`` CAD tuples
    keyed ``plants`` / ``structures`` / ``mulch`` / ``total``."""
    p = estimate_cost(plants, get_plant=get_plant)
    s = structure_cost(structures or [], get_structure=get_structure)
    m = mulch_cost(mulch_area_m2)
    total = (round(p[0] + s[0] + m[0], 2), round(p[1] + s[1] + m[1], 2))
    return {"plants": p, "structures": s, "mulch": m, "total": total}

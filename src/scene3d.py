"""
src/scene3d.py — shared placement/timeline state for the 2D map and a future
3D viewport (D1 foundation).

Both views need the same answer to "how big, and how present, is each placed
plant at year N?". This pure, Qt-free, DB-free module is the single source of
truth for that:

  * ``growth_scale_factor`` — the fraction of mature size at a year, matching the
    2D timeline exactly (the 2D controller calls this so the two can never drift);
  * ``plant_3d_state`` — a per-plant record a 3D scene can consume directly
    (lat/lng + height_m/canopy_m scaled to the year + scale_factor +
    presence_opacity from succession);
  * ``placed_plants_3d_state`` — the same for a whole design at a year.

Growth params and successional role come from the plant record + ``src.succession``.
"""

from __future__ import annotations

import math

from src.succession import successional_role, presence_factor, years_to_maturity


def growth_scale_factor(year: int, ytm: int, curve: str) -> float:
    """Fraction (clamped 0.1–1.0) of mature size at ``year`` for a plant whose
    years-to-maturity is ``ytm`` and growth curve is ``curve``.

    Matches the 2D growth timeline exactly: full size at year 0 (the mature-design
    reference) and at/after maturity; in between, ``fast_early`` = √ratio,
    ``slow_start`` = ratio^1.5, everything else linear."""
    ytm = max(1, int(ytm or 1))
    if year <= 0 or year >= ytm:
        factor = 1.0
    else:
        ratio = year / ytm
        if curve == "fast_early":
            factor = math.sqrt(ratio)
        elif curve == "slow_start":
            factor = ratio ** 1.5
        else:                       # steady / unknown
            factor = ratio
    return max(0.1, min(1.0, factor))


def spread_scale_factor(year: int, spread_habit: str, ytm: int) -> float:
    """Horizontal-footprint expansion (≥1.0) of a self-spreading plant at ``year``.

    Where :func:`growth_scale_factor` scales a plant toward its mature size,
    spread is the *colony* widening over time (F35): clonal / rhizomatous / self-
    seeding species creep outward and fill the gaps they were planted into. The
    asymptote is the planting engine's ``SPREAD_FACTOR`` (so a species spaced 2×
    wide because it's aggressive ends up filling that 2× footprint here), reached
    linearly by maturity and held after. Clumpers / unassessed stay at 1.0."""
    from src.planting_spacing import SPREAD_FACTOR
    final = SPREAD_FACTOR.get((spread_habit or "").strip().lower(), 1.0)
    if final <= 1.0 or year <= 0:
        return 1.0
    ytm = max(1, int(ytm or 1))
    ratio = min(1.0, year / ytm)
    return 1.0 + (final - 1.0) * ratio


def spread_aggressiveness(spread_habit: str) -> float:
    """How aggressively a habit colonises, as a 0–1 rate independent of year.

    Derived from the planting engine's ``SPREAD_FACTOR`` asymptote
    (``final − 1``): 0.0 clumping/unassessed, 0.3 slow_spreader, 0.6
    self_seeding, 1.0 aggressive_rhizomatous. The 3D viewer multiplies this by
    the timeline year to keep a colony creeping outward continuously, rather
    than freezing once ``spread_scale_factor`` plateaus at maturity."""
    from src.planting_spacing import SPREAD_FACTOR
    final = SPREAD_FACTOR.get((spread_habit or "").strip().lower(), 1.0)
    return max(0.0, final - 1.0)


# Fallback mature dimensions (metres) when a record lacks them — keeps a 3D
# scene sane for sparsely-populated rows.
_DEFAULT_HEIGHT_M = {"tree": 8.0, "shrub": 2.0, "herb": 0.5,
                     "groundcover": 0.2, "vine": 2.0, "root": 0.4}
_DEFAULT_CANOPY_M = {"tree": 5.0, "shrub": 1.5, "herb": 0.4,
                     "groundcover": 0.5, "vine": 1.0, "root": 0.3}


def plant_3d_state(plant: dict, lat: float, lng: float, year: int) -> dict:
    """Per-plant 3D state at ``year``: position + scaled height/canopy + the
    growth scale factor + the succession presence opacity."""
    ptype = (plant.get("plant_type") or "").lower()
    ytm = years_to_maturity(plant)
    curve = plant.get("growth_curve") or "steady"
    role = successional_role(plant)
    factor = growth_scale_factor(year, ytm, curve)
    # Woody plants (trees & shrubs) don't scatter a visible clonal colony in the
    # scene: a "spreading" tree or shrub reads as the yard filling with
    # duplicates, which isn't how a canopy grows or how the user wants it drawn.
    # Only herbaceous layers colonise the ground here. (Clonal-shrub *spacing*
    # still widens via planting_spacing.spread_factor — this gate is the scene's
    # visual colony only.)
    woody = ptype in ("tree", "shrub")
    spread = (1.0 if woody
              else spread_scale_factor(year, plant.get("spread_habit") or "", ytm))
    rate = 0.0 if woody else spread_aggressiveness(plant.get("spread_habit") or "")
    mature_h = plant.get("mature_height_meters") or _DEFAULT_HEIGHT_M.get(ptype, 0.5)
    mature_c = plant.get("mature_canopy_m") or _DEFAULT_CANOPY_M.get(ptype, 0.4)
    return {
        "lat": lat,
        "lng": lng,
        "plant_type": ptype,
        "foliage_type": (plant.get("deciduous_evergreen") or "herbaceous").lower(),
        "scale_factor": round(factor, 4),
        "spread_factor": round(spread, 4),
        # Year-independent aggressiveness (0 none … 1 aggressive) so the 3D
        # viewer can grow a colony continuously over the timeline rather than
        # plateauing with spread_factor at maturity.
        "spread_rate": round(rate, 4),
        # Growth scales the whole plant; spread additionally widens the ground
        # footprint (canopy) as the colony fills in — height is unaffected.
        "height_m": round(float(mature_h) * factor, 3),
        "canopy_m": round(float(mature_c) * factor * spread, 3),
        "presence_opacity": round(presence_factor(role, year, ytm), 3),
    }


def placed_plants_3d_state(placed_plants, year: int, get_plant=None) -> list:
    """3D state for every placed plant at ``year``. Each input dict needs
    ``plant_id`` / ``lat`` / ``lng``; ``get_plant`` is injectable for tests.
    Returns a list of records (each the ``plant_3d_state`` dict + ``plant_id``)."""
    if get_plant is None:
        from src.db.plants import get_plant as _gp
        get_plant = _gp
    cache: dict = {}
    out: list = []
    for p in placed_plants or []:
        pid = p.get("plant_id")
        if pid is None or p.get("lat") is None or p.get("lng") is None:
            continue
        rec = cache.get(pid)
        if rec is None:
            rec = get_plant(pid) or {}
            cache[pid] = rec
        st = plant_3d_state(rec, p["lat"], p["lng"], year)
        st["plant_id"] = pid
        out.append(st)
    return out

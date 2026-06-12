"""
src/succession.py — ecological-succession helpers for the growth timeline (N5).

Pure, Qt-free and DB-free so the timeline panel, the map controller and the
tests all share one definition of:

  * restoration **stages** along the timeline (pioneer → forb-grass → shrub →
    climax) and the slider label for a given year;
  * a plant's **successional role** (pioneer / mid / climax), read from the
    ``permaculture_uses`` blob (``early_successional`` / ``climax`` tags) with a
    maturity heuristic so long-lived canopy species read as climax even when
    untagged — the feature works on today's data, and an explicit ``climax`` tag
    (added later by the dataset workflow) is honoured the moment it appears;
  * the **presence factor** (0..1 opacity) that fades pioneers *out* and climax
    species *in* as the design matures;
  * the dynamic **time horizon** — the slider extends to the longest
    ``years_to_maturity`` in the design so slow trees actually reach full size.
"""

from __future__ import annotations

# Slider horizon clamps: never shorter than this, never longer than this.
TIMELINE_FLOOR_YEARS = 20
TIMELINE_CAP_YEARS = 60

# Plant-type → fallback years-to-maturity when a record doesn't carry one
# (kept in step with the controller's own default so estimates don't drift).
_DEFAULT_YTM = {"tree": 15, "shrub": 5, "herb": 2, "groundcover": 1,
                "vine": 2, "root": 2}


def years_to_maturity(plant: dict) -> int:
    """A plant's years-to-maturity, falling back to a per-type default."""
    ytm = plant.get("years_to_maturity")
    if ytm:
        return int(ytm)
    return _DEFAULT_YTM.get((plant.get("plant_type") or "").lower(), 2)


def restoration_stage(year: int) -> str:
    """Restoration stage name for a timeline year."""
    if year <= 0:
        return "Planting"
    if year <= 2:
        return "Pioneer forbs"
    if year <= 4:
        return "Forb–grass matrix"
    if year <= 9:
        return "Shrubs establishing"
    return "Climax / canopy"


def year_label(year: int) -> str:
    """Slider read-out: the year plus its restoration stage."""
    if year <= 0:
        return "Year 0 (Planting)"
    return f"Year {year} · {restoration_stage(year)}"


def successional_role(plant: dict) -> str:
    """Return ``'pioneer'`` / ``'climax'`` / ``'mid'`` for a plant record.

    Reads the ``permaculture_uses`` comma-blob first (``early_successional`` /
    ``pioneer`` → pioneer, ``climax`` → climax). Untagged long-lived woody
    species fall back to climax via a maturity heuristic so the timeline does
    something sensible on today's (mostly untagged) data."""
    uses = (plant.get("permaculture_uses") or "").lower()
    tags = {t.strip() for t in uses.split(",") if t.strip()}
    if "early_successional" in tags or "pioneer" in tags:
        return "pioneer"
    if "climax" in tags:
        return "climax"
    ptype = (plant.get("plant_type") or "").lower()
    if ptype == "tree" and years_to_maturity(plant) >= 15:
        return "climax"
    return "mid"


def presence_factor(role: str, year: int, ytm: int) -> float:
    """Opacity 0..1 expressing how *present* a species is at ``year``.

    ``pioneer`` species hold full presence through their early window then fade
    to a faint remnant; ``climax`` species start faint and rise toward full by
    maturity; ``mid`` (and everything at year 0, the mature-design reference)
    stay fully present. Never returns 0 — faded plants stay dimly visible."""
    if year <= 0:
        return 1.0
    if role == "pioneer":
        # Pioneers hold while establishing, then fade as later layers close in.
        # The fade is scaled to the species' own lifecycle: short-lived forbs
        # fade within a few years; long-lived pioneer trees (lodgepole, aspen)
        # persist for decades rather than vanishing at full canopy size.
        m = max(1, int(ytm or 2))
        hold = max(4, 2 * m)   # full presence through ~2× maturity
        tail = max(8, 4 * m)   # faded to a remnant by ~4× maturity
        if year <= hold:
            return 1.0
        if year >= tail:
            return 0.2
        return 1.0 - 0.8 * (year - hold) / (tail - hold)
    if role == "climax":
        m = max(1, int(ytm or 15))
        return max(0.2, min(1.0, year / m))
    return 1.0


def timeline_max_years(plants, get_plant=None,
                       floor: int = TIMELINE_FLOOR_YEARS,
                       cap: int = TIMELINE_CAP_YEARS) -> int:
    """Longest ``years_to_maturity`` among the placed ``plants``, clamped to
    ``[floor, cap]`` — so the slider reaches the slowest tree's maturity without
    running off to absurd lengths. ``plants`` are placed-plant dicts (carrying
    ``plant_id``) or bare ids; ``get_plant`` is injectable for tests."""
    if get_plant is None:
        from src.db.plants import get_plant as _gp
        get_plant = _gp
    longest = 0
    cache: dict = {}
    for p in plants or []:
        pid = p.get("plant_id") if isinstance(p, dict) else p
        if pid is None:
            continue
        rec = cache.get(pid)
        if rec is None:
            rec = get_plant(pid) or {}
            cache[pid] = rec
        longest = max(longest, years_to_maturity(rec))
    return max(floor, min(cap, longest or floor))

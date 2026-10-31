"""
forage_calendar.py — whole-design bloom succession + pollinator forage-gap
analysis (V2.13).

The Habitat Value Score already rewards *bloom continuity* as one hidden
sub-score; this module makes it **legible** (Design principle P6 — make
ecological value legible) and **honest** (P9 — name the gaps, never paper over
them). Given the plants placed in a design it answers one question a pollinator
gardener actually cares about: *is there always something in bloom?*

For each of the twelve months it counts how many of the design's plants are in
flower, flags the growing-season months with **no** forage as gaps, and returns
a per-plant succession (sorted by first bloom) so the relay from spring to fall
is visible. Qt-free: the analysis panel draws it, tests exercise it directly.

Bloom windows are parsed with the same ``parse_month_range`` the score uses.
**The two disagree about grasses, on purpose (V2.91):** a grass, sedge or rush
is not forage here, while the score's bloom continuity still counts its bloom
period, pending the owner's decision on the headline (F184). See
docs/DESIGN_PHILOSOPHY.md.
"""

from __future__ import annotations

from typing import Optional

from src.habitat_score import GROWING_SEASON_MONTHS, parse_month_range

_MONTH_ABBR = ["", "Jan", "Feb", "Mar", "Apr", "May", "Jun",
               "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
_MONTH_FULL = ["", "January", "February", "March", "April", "May", "June",
               "July", "August", "September", "October", "November", "December"]

_FALLBACK_FLOWER = "#e6a5d0"     # a soft bloom colour when none is recorded

#: Wind-pollinated habits: they flower, but not for bees.
WIND_POLLINATED_TYPES = frozenset({"grass", "sedge", "rush"})


def is_pollinator_forage(p: dict) -> bool:
    """Does this plant feed pollinators when it flowers? Yes if it flowers at
    all (a recorded bloom period, or a flower form other than 'none'), unless
    it is a grass, sedge or rush.

    **Those never count, bloom period or not (V2.91, F182; the owner's rule).**
    All 78 in the catalogue record a bloom period, and this used to accept any
    bloom period before it looked at anything else, so a meadow's grasses
    filled May to September with forage no bee can use. Four wind-pollinated
    wetland plants filed ``aquatic`` (cattail, bur-reed, a bulrush and a sedge)
    still count: the catalogue records no pollination mode to tell them by.
    Design › Food's month by month reads this too."""
    if (p.get("plant_type") or "").strip().lower() in WIND_POLLINATED_TYPES:
        return False
    if (p.get("bloom_period") or "").strip():
        return True
    ff = (p.get("flower_form") or "none").strip().lower()
    return ff not in ("", "none")


def _bloom_months(p: dict) -> list[int]:
    """Months this plant is in bloom. A flowering plant with no recorded window
    falls back to a broad summer relay (Jun–Sep) rather than vanishing — the
    same generous default the 3D flower layer uses (honest but not silent)."""
    months = parse_month_range(p.get("bloom_period") or "")
    if months:
        return months
    return [6, 7, 8, 9] if is_pollinator_forage(p) else []


def build_forage_calendar(plants: Optional[list[dict]]) -> dict:
    """Return the whole-design forage calendar.

    ``plants`` are placed-plant dicts (as the analysis panel already holds),
    each with ``common_name`` and a ``bloom_period`` / ``flower_form`` /
    ``flower_color``. Result::

        {
          "months": [ {month, name, abbr, count, is_growing, is_gap}, ... ]  # 12
          "gap_months": [int, ...],        # growing-season months with 0 forage
          "covered_growing": int,          # growing months with >=1 forage plant
          "growing_total": int,            # size of the growing season (7)
          "coverage": float,               # covered / total   (0..1)
          "peak_month": int,               # month with the most plants in bloom
          "flowering_plants": int,         # plants that contribute forage
          "succession": [ {name, color, months:[bool*12], first, last}, ... ],
          "note": str,                     # honest plain-language summary
        }
    """
    flowering = [p for p in (plants or []) if is_pollinator_forage(p)]
    growing = sorted(GROWING_SEASON_MONTHS)

    counts = [0] * 13                       # 1-indexed month -> plant count
    succession: list[dict] = []
    for p in flowering:
        months = _bloom_months(p)
        if not months:
            continue
        flags = [False] * 12
        for m in months:
            if 1 <= m <= 12:
                counts[m] += 1
                flags[m - 1] = True
        if not any(flags):
            continue
        present = [i + 1 for i, f in enumerate(flags) if f]
        succession.append({
            "name": p.get("common_name") or p.get("scientific_name") or "plant",
            "color": (p.get("flower_color") or "").strip() or _FALLBACK_FLOWER,
            "months": flags,
            "first": min(present),
            "last": max(present),
        })

    months_out = []
    for m in range(1, 13):
        is_growing = m in GROWING_SEASON_MONTHS
        months_out.append({
            "month": m,
            "name": _MONTH_FULL[m],
            "abbr": _MONTH_ABBR[m],
            "count": counts[m],
            "is_growing": is_growing,
            "is_gap": is_growing and counts[m] == 0 and bool(flowering),
        })

    gap_months = [m for m in growing if counts[m] == 0]
    covered = sum(1 for m in growing if counts[m] > 0)
    peak = max(range(1, 13), key=lambda m: counts[m]) if any(counts[1:]) else 0
    # Succession: earliest bloomers first so the spring→fall relay reads top-down.
    succession.sort(key=lambda s: (s["first"], s["last"], s["name"].lower()))

    return {
        "months": months_out,
        "gap_months": gap_months,
        "covered_growing": covered,
        "growing_total": len(growing),
        "coverage": (covered / len(growing)) if growing else 0.0,
        "peak_month": peak,
        "flowering_plants": len(succession),
        "succession": succession,
        "note": _note(len(succession), gap_months, covered, len(growing)),
    }


def _note(n_flowering: int, gap_months: list[int], covered: int,
          total: int) -> str:
    """Plain-language, honest summary (P9)."""
    if n_flowering == 0:
        return ("No flowering plants are placed yet — add nectar and pollen "
                "plants across the season to feed pollinators.")
    if not gap_months:
        return (f"Something is in bloom in every growing-season month "
                f"(Apr–Oct) — a continuous nectar relay for pollinators.")
    gap_names = ", ".join(_MONTH_FULL[m] for m in gap_months)
    return (f"Forage covers {covered} of {total} growing-season months. "
            f"Bloom gap{'s' if len(gap_months) != 1 else ''}: {gap_names} — "
            f"add something that flowers then so pollinators aren't left hungry.")


def gap_filling_suggestions(plants: Optional[list[dict]],
                            candidate_plants: Optional[list[dict]],
                            limit: int = 8) -> list[dict]:
    """Native ``candidate_plants`` that flower in the design's bloom gaps and
    aren't already placed — the "add these" list. Each result carries the gap
    months it fills. Empty when there are no gaps or no candidates.

    ``candidate_plants`` is typically the full native plant list; only flowering,
    Alberta-native candidates that hit a gap month are returned, best-fit first
    (most gap months covered)."""
    cal = build_forage_calendar(plants)
    gaps = set(cal["gap_months"])
    if not gaps or not candidate_plants:
        return []
    placed_names = {(p.get("common_name") or "").lower() for p in (plants or [])}
    out: list[dict] = []
    for c in candidate_plants:
        if (c.get("common_name") or "").lower() in placed_names:
            continue
        if not is_pollinator_forage(c):
            continue
        fills = sorted(gaps.intersection(_bloom_months(c)))
        if not fills:
            continue
        out.append({
            "common_name": c.get("common_name", ""),
            "scientific_name": c.get("scientific_name", ""),
            "bloom_period": c.get("bloom_period", ""),
            "flower_color": (c.get("flower_color") or "").strip() or _FALLBACK_FLOWER,
            "fills": fills,
        })
    out.sort(key=lambda r: (-len(r["fills"]), r["common_name"].lower()))
    return out[:max(0, limit)]

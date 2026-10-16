"""
plant_directory_bloom.py — what is flowering this week (F90/F44).

Design principle P11 — see docs/DESIGN_PHILOSOPHY.md (the body and the site
know things the screen does not: the point of this line is to get somebody to
go and look).

Split out of :mod:`src.plant_directory` in V2.80, when the architecture guard
fired at 610 lines against 600. The seam was already named in that module's own
docstring, which lists this as its own bullet: the rest of the file answers
*tell me about this species*, and these three answer *what should I go outside
and see right now*, for the start screen.

Re-exported from `plant_directory` so every existing caller keeps working.
"""

from __future__ import annotations

import datetime
from typing import Callable, Optional

def in_bloom_now(*, month: Optional[int] = None,
                 ecoregion: str = "",
                 search_fn: Optional[Callable] = None) -> dict:
    """Species in bloom this month, for the start screen's footer.

    ``{"month": n, "month_name": str, "count": n, "ecoregion": key,
    "where": str, "plants": [...]}``.

    The existing :mod:`src.phenology` answers this for *your design* — it takes
    placed plants. This is the catalogue-wide question, which nothing asked
    before there was a screen you see without opening a design.

    **``where`` is honest about scope.** With no known ecoregion it says so
    rather than implying the count is local; a number that looks regional and
    is not would be exactly the false precision P9 forbids.
    """
    if search_fn is None:
        from src.db.plants import search_plants as search_fn   # noqa: PLC0415
    month = int(month or datetime.date.today().month)
    criteria = {"bloom_months": [str(month)]}
    if ecoregion:
        criteria["ecoregion"] = ecoregion
    # Imported inside the function: `plant_directory` imports this module
    # at the top to re-export the three names below, so a module-level
    # import back would be a cycle.
    from src.plant_directory import _safely, search  # noqa: PLC0415
    rows = _safely(lambda: search(criteria, search_fn=search_fn), [])

    where = ""
    if ecoregion:
        from src.ecoregion import ecoregion_display            # noqa: PLC0415
        name, _ = ecoregion_display(ecoregion)
        where = f"in {name}" if name else ""
    return {"month": month, "month_name": _MONTH_NAMES[month - 1],
            "count": len(rows), "ecoregion": ecoregion, "where": where,
            "plants": rows}


def bloom_line(summary: dict) -> str:
    """The footer link, in as few words as it can be said in.

    Names its scope either way. "41 species flowering now" reads as a claim
    about *here*, and without a known ecoregion it would not be one (P9), so
    the catalogue-wide case says so rather than staying silent.
    """
    count = int(summary.get("count") or 0)
    if not count:
        return ""
    scope = summary.get("where") or "catalogue-wide"
    return f"{count} species flowering now, {scope}"


#: Not what "in flower" calls to mind: wind-pollinated grasses and their kin,
#: whose bloom is the absence of a showy flower (src/flower_colour.py), and
#: pond plants, which most yards have nowhere to grow.
_NOT_SHOWY = frozenset({"grass", "sedge", "rush", "aquatic"})


def flowering_around(*, month: Optional[int] = None, place: str = "edmonton",
                     search_fn: Optional[Callable] = None) -> dict:
    """The plants native around ``place`` (the reviewed Edmonton list, F220)
    in flower this month, for the start screen's last line (the owner, V3.23).

    ``{"month_name": str, "place": str, "names": [common names]}``: showy
    plants only (``_NOT_SHOWY``, ``zoning.needs_standing_water``), the ones
    garden centres sell first (``sourcing.ease``), then by name, so the two
    named are ones a person could see in a yard and buy. Never raises: a front
    door must not fail to open over a line."""
    month = int(month or datetime.date.today().month)
    out = {"month_name": _MONTH_NAMES[month - 1],
           "place": place.replace("_", " ").title(), "names": []}
    try:
        if search_fn is None:
            from src.db.plants import search_plants as search_fn  # noqa: PLC0415
        from src.sourcing import ease                               # noqa: PLC0415
        from src.zoning import needs_standing_water                 # noqa: PLC0415
        rows = search_fn(bloom_months=[str(month)], native_near=place)
        rows = [r for r in rows
                if (r.get("plant_type") or "").lower() not in _NOT_SHOWY
                and not needs_standing_water(r) and r.get("common_name")]
        rows.sort(key=lambda r: (-ease(r), r["common_name"]))
        out["names"] = [r["common_name"] for r in rows]
    except Exception:                                        # noqa: BLE001
        pass
    return out


def flowering_line(summary: dict, shown: int = 2) -> str:
    """"In flower around Edmonton in July: Wild Bergamot, Harebell and 40
    more." ``""`` when nothing is: a month with no flowers says nothing rather
    than "0 plants" (P9: it does not claim to have looked at a yard)."""
    names = list(summary.get("names") or [])
    if not names:
        return ""
    head = (f"In flower around {summary.get('place') or 'Edmonton'} in "
            f"{summary.get('month_name', '')}: ")
    if len(names) <= shown + 1:
        said = (names[0] if len(names) == 1
                else ", ".join(names[:-1]) + " and " + names[-1])
    else:
        said = f"{', '.join(names[:shown])} and {len(names) - shown} more"
    return head + said + "."


def catalogue_size(count_fn: Optional[Callable] = None) -> int:
    """How many species the catalogue holds, for the start screen's directory
    row. Never raises: a front door must not fail to open over a count."""
    if count_fn is not None:
        return int(count_fn())
    try:
        from src.db.plants import get_connection             # noqa: PLC0415
        conn = get_connection()
        try:
            return int(conn.execute("SELECT COUNT(*) FROM plants").fetchone()[0])
        finally:
            conn.close()
    except Exception:                                        # noqa: BLE001
        return 0


_MONTH_NAMES = ("January", "February", "March", "April", "May", "June", "July",
                "August", "September", "October", "November", "December")

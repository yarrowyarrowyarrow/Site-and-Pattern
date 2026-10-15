"""
water_budget.py — how much water a design needs, and the rule a person can
follow (V3.20, OV-7).

Design principle P9 — see docs/DESIGN_PHILOSOPHY.md.

Moved out of the Water page (``planning_panel``), which had three faults the
first review found:

  * **Rows missing (R4).** The table listed six fixed types, so wildflowers,
    grasses and sedges were in the total with no row: the generated bed's
    twelve wildflowers were invisible.
  * **A seasonal surplus (R38).** It weighed the season's demand against the
    season's rain and called the difference a surplus. A new planting dies in
    a two-week dry spell whatever the season's total, so the page now gives the
    care calendar's rule as a weekly quantity: a deep soak in any week without
    a good rain.
  * **Edmonton's rainfall, wherever the pin.** Rainfall now comes from the
    site's own normals when they have been fetched, labelled with their source,
    and only otherwise from Edmonton's, labelled so.

The numbers are estimates per plant type and water need, the same constants
the page always used; the supply side stays as information.
"""

from __future__ import annotations

from typing import Optional

from src.plant_conditions import condition_tokens

#: Edmonton's approximate monthly rainfall, mm: the fallback when the site's
#: own normals have not been fetched.
EDMONTON_MONTHLY_RAINFALL_MM = (15, 10, 15, 25, 45, 75, 90, 65, 40, 20, 15, 12)

#: Litres a week through the growing season, by plant type, before the
#: water-need multiplier. A type not listed uses :data:`DEFAULT_L_WEEK`.
PLANT_WATER_NEEDS_L_WEEK = {
    "tree": 40.0, "shrub": 15.0, "herb": 8.0, "groundcover": 3.0,
    "vine": 12.0, "root": 6.0,
}
DEFAULT_L_WEEK = 8.0

WATER_MULTIPLIER = {"low": 0.5, "medium": 1.0, "high": 1.5}

#: Year 1 waters everything in; from year 3 established natives are nearly
#: rain-fed and cultivars keep their full demand.
Y1_MULT = 1.5
Y3_MULT_NATIVE = 0.2
Y3_MULT_CULTIVATED = 1.0

#: May to September, the weeks the demand is spread over.
GROWING_WEEKS = 22

#: A good rain, the calendar's deep soak (``maintenance_calendar``, Year 1).
GOOD_RAIN = "15–20 mm"


def _plant_litres(plant: dict) -> tuple:
    """``(year 1, year 3+)`` seasonal litres for one placed plant."""
    ptype = (plant.get("plant_type") or "herb")
    tokens = condition_tokens(plant.get("water_needs"))
    need = tokens[0] if tokens else "medium"
    weekly = (PLANT_WATER_NEEDS_L_WEEK.get(ptype, DEFAULT_L_WEEK)
              * WATER_MULTIPLIER.get(need, 1.0))
    season = weekly * GROWING_WEEKS
    native = bool(plant.get("native_to_alberta"))
    return (season * Y1_MULT,
            season * (Y3_MULT_NATIVE if native else Y3_MULT_CULTIVATED))


def demand_by_type(plants) -> dict:
    """``{plant type: {"count", "native", "y1", "y3"}}`` in seasonal litres,
    a row for every type present, in the plant key's order
    (``member_colors.TYPE_COLORS``), then any other type by name."""
    rows: dict = {}
    for p in plants or []:
        y1, y3 = _plant_litres(p)
        slot = rows.setdefault(p.get("plant_type") or "herb",
                               {"count": 0, "native": 0, "y1": 0.0, "y3": 0.0})
        slot["count"] += 1
        slot["native"] += 1 if p.get("native_to_alberta") else 0
        slot["y1"] += y1
        slot["y3"] += y3
    from src.member_colors import TYPE_COLORS
    order = ([t for t in TYPE_COLORS if t in rows]
             + sorted(t for t in rows if t not in TYPE_COLORS))
    return {t: rows[t] for t in order}


def first_summer_weekly_litres(plants) -> float:
    """Litres a week in the first summer: the year-1 demand over the
    growing weeks."""
    return sum(_plant_litres(p)[0] for p in plants or []) / GROWING_WEEKS


def rainfall(site_config: Optional[dict]) -> tuple:
    """``(monthly mm × 12, where it is from)``: the site's own normals when
    fetched (``site_config["rainfall"]["monthly_mm"]``), else Edmonton's."""
    rain = ((site_config or {}).get("rainfall") or {})
    months = rain.get("monthly_mm") or []
    if len(months) == 12:
        try:
            values = tuple(float(m) for m in months)
        except (TypeError, ValueError):
            values = ()
        if values:
            source = (rain.get("source") or "").strip()
            return values, (f"this site's normals ({source})" if source
                            else "this site's normals")
    return EDMONTON_MONTHLY_RAINFALL_MM, "Edmonton normal"


def weekly_rule(plants) -> str:
    """The sentence the page and the overview give instead of a surplus."""
    litres = first_summer_weekly_litres(plants)
    if litres <= 0:
        return ""
    return (f"First summer: about {_round_litres(litres)} L a week in any "
            f"week without a good rain ({GOOD_RAIN}). From year 3: only in a "
            f"drought.")


def _round_litres(litres: float) -> str:
    """To 10 L, or 5 under 100, with a thousands comma: an estimate, said as
    one (P9)."""
    step = 5 if litres < 100 else 10
    return f"{max(step, int(round(litres / step)) * step):,}"

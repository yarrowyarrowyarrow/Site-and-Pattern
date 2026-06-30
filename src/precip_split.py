"""
src/precip_split.py — separate precipitation by *when its water is available*.

Design principle P9 (uncertainty is a feature — communicate honestly, not false
precision) and P11 (the body and the site know things the screen does not) —
see docs/DESIGN_PHILOSOPHY.md.

Precipitation is always measured as **liquid-water equivalent** (mm of water);
standard climate normals (ECCC included) already report snow that way, so the
annual/monthly total is correct as-is — it is *not* an over-estimate, and we do
no snow-depth conversion (fresh-snow depth per mm of water ranges ~4:1 to 20:1,
so a "cm of snow" figure would be false precision).

What the total hides is *timing*. The same millimetre waters a landscape very
differently depending on when and how it arrives:

  * **Rain** infiltrates immediately — and rain that falls in the **growing
    season (Apr–Oct)** is the water a planting can actually use while it is
    active.
  * **Snow** is delayed-release: it sits until spring, then melts in a pulse —
    and much of that pulse can run off frozen or sloped ground rather than
    recharging the soil.

So this module splits the total into rain vs snow (both as water-equivalent, so
``rain + snow == total`` by construction — no inflation) and reports the
growing-season rain and the delayed snowmelt water as the two figures that
actually matter for siting. Two ways to get the split:

  * **Measured** — Open-Meteo archive reports ``rain_sum`` directly, so snow
    water-equivalent = ``precipitation_sum − rain_sum``.
  * **Estimated** — the bundled Environment Canada normal carries total
    precipitation only, so we apply a documented prairie snow-fraction
    climatology (flagged as an estimate).

Qt-free and DB-free so the fetch layer, the panel and the tests share it.
"""

from __future__ import annotations

from typing import Optional

# Fraction of each month's precipitation that typically falls as snow
# (water-equivalent) in the settled Canadian prairies / central Alberta
# (Köppen Dfb, hardiness zone 3–4): a transparent regional climatology used only
# when a source can't measure rain vs snow itself. Deep winter ~all snow, summer
# ~all rain, shoulder months mixed. Order is Jan … Dec.
PRAIRIE_SNOW_FRACTION = [
    1.00, 1.00, 0.90, 0.45, 0.08, 0.00,
    0.00, 0.00, 0.05, 0.35, 0.90, 1.00,
]

# Growing-season months (Apr–Oct) — the window when rain actually waters a
# planting (matches habitat_score.GROWING_SEASON_MONTHS).
GROWING_MONTHS = tuple(range(4, 11))


def _f(x) -> float:
    try:
        return float(x)
    except (TypeError, ValueError):
        return 0.0


def partition(total_mm: list, snow_fraction: list) -> dict:
    """Split a 12-month precipitation total into rain and snow (both mm, water-
    equivalent) using a per-month ``snow_fraction`` (0..1). By construction
    ``rain_mm[i] + snow_mm[i] == total_mm[i]`` (rounded)."""
    rain: list[float] = []
    snow: list[float] = []
    for t, frac in zip(total_mm, snow_fraction):
        t = max(0.0, _f(t))
        frac = max(0.0, min(1.0, _f(frac)))
        s = t * frac
        snow.append(round(s, 1))
        rain.append(round(t - s, 1))
    return {"rain_mm": rain, "snow_mm": snow}


def annual_total(monthly: list) -> float:
    return round(sum(_f(m) for m in monthly), 1)


def growing_season_total(monthly: list, months=GROWING_MONTHS) -> float:
    """Sum of ``monthly`` over the growing-season months (Apr–Oct by default)."""
    if not monthly:
        return 0.0
    return round(sum(_f(monthly[m - 1]) for m in months
                     if 1 <= m <= len(monthly)), 1)


def _attach(rainfall: dict, rain_mm: list, snow_mm: list, source: str) -> dict:
    """Write the split + timing fields onto a (copied) rainfall dict and return
    it. All water amounts are liquid-water equivalent (mm)."""
    out = dict(rainfall)
    out["monthly_rain_mm"] = [round(_f(x), 1) for x in rain_mm]
    out["monthly_snow_mm"] = [round(_f(x), 1) for x in snow_mm]
    out["annual_rain_mm"] = annual_total(rain_mm)
    out["annual_snow_mm"] = annual_total(snow_mm)        # delayed spring-melt water
    out["growing_season_rain_mm"] = growing_season_total(rain_mm)  # available now
    out["snow_split_source"] = source
    return out


def add_estimated_split(rainfall: Optional[dict],
                        snow_fraction: list = PRAIRIE_SNOW_FRACTION,
                        source: str = "estimated (prairie snow-fraction climatology)"
                        ) -> Optional[dict]:
    """Return ``rainfall`` enriched with an *estimated* rain/snow split derived
    from ``monthly_mm`` × ``snow_fraction``. Returns the input unchanged when it
    has no usable 12-month total."""
    if not rainfall:
        return rainfall
    total = rainfall.get("monthly_mm")
    if not total or len(total) != 12:
        return rainfall
    part = partition(total, snow_fraction)
    return _attach(rainfall, part["rain_mm"], part["snow_mm"], source)


def add_measured_split(rainfall: Optional[dict], rain_mm: list, snow_mm: list,
                       source: str = "Open-Meteo measured rain/snow"
                       ) -> Optional[dict]:
    """Return ``rainfall`` enriched with a *measured* split (rain mm + snow
    water-equivalent mm, 12-month each). Returns the input unchanged on a length
    mismatch."""
    if not rainfall:
        return rainfall
    if not (len(rain_mm) == len(snow_mm) == 12):
        return rainfall
    return _attach(rainfall, rain_mm, snow_mm, source)

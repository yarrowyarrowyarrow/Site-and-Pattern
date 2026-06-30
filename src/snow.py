"""
src/snow.py — winter snow cover & survival metrics (the *insulation* function).

Design principle P9 (uncertainty is a feature — ranges and "design for the bad
year", not false precision) and P11 (the body and the site know things the
screen does not) — see docs/DESIGN_PHILOSOPHY.md.

Snow's value to a planting is only partly the water it carries; the other half is
**insulation**. A reliable snowpack decouples crown/root temperature from the air
— plants whose buds sit *below* the snowline can survive winters their air-
temperature hardiness zone says they shouldn't. But that protection is fragile in
Alberta's variable winters: chinook / midwinter-thaw events strip the blanket at
the worst moment, rain-on-snow + refreeze causes ice encasement, and repeated
freeze–thaw heaves new plantings. And snow reliability is *declining* — so the
honest design rule is never to *bank* a marginal plant on snow, and to recommend
mulch (the controllable substitute) where cover is thin.

This module models those realities from daily temperature + precipitation (the
same archive series the climate fetch uses), as honest estimates:

  * a simple temperature-index **snowpack** (precip falls as snow below 0 °C,
    melts via degree-days above it) → **insulating-cover days** per winter;
  * **freeze–thaw cycles** (days crossing 0 °C) — heaving / ice risk;
  * **midwinter thaw days** (above-freezing days in Dec–Feb) — chinook exposure;
  * **rain-on-snow days** — ice-encasement risk;

and turns them into a reliability label + plain-language, height-aware survival
notes. Qt-free and DB-free so the fetch layer, the panel and the tests share it.
"""

from __future__ import annotations

from datetime import date
from typing import Optional

# Snowpack model parameters (temperature-index; deliberately simple + documented).
SNOW_TEMP_C = 0.0           # precip falls as snow when the daily mean ≤ this
MELT_FACTOR_MM_PER_DEG = 2.5  # SWE melted per degree-day above SNOW_TEMP_C
# Snow water-equivalent (mm) above which the pack meaningfully insulates crowns
# (≈15 cm of settled snow at ~10:1) — the threshold for an "insulating-cover day".
INSULATING_SWE_MM = 15.0

# Winter window for freeze–thaw counting (the months a planting is dormant and
# vulnerable to heaving / ice), and the deep-winter window where losing snow
# cover matters most (chinook season).
_FREEZE_THAW_MONTHS = (11, 12, 1, 2, 3)
_MIDWINTER_MONTHS = (12, 1, 2)


def _mean(rows_vals) -> Optional[float]:
    vals = [v for v in rows_vals if v is not None]
    return sum(vals) / len(vals) if vals else None


def _snow_season(d: date) -> int:
    """Snow-season key so a winter isn't split across the calendar year: the
    season starting in July of year Y covers Jul Y … Jun Y+1, keyed by Y."""
    return d.year if d.month >= 7 else d.year - 1


def _parse_rows(daily_rows) -> list[dict]:
    """Normalise + sort rows to ``[{date: date, tmin, tmax, precip}]``."""
    out: list[dict] = []
    for r in daily_rows or []:
        ds = r.get("date") or ""
        try:
            d = date.fromisoformat(ds)
        except (TypeError, ValueError):
            continue
        tmin = r.get("tmin")
        tmax = r.get("tmax")
        if tmin is None or tmax is None:
            continue
        out.append({
            "date": d,
            "tmin": float(tmin),
            "tmax": float(tmax),
            "precip": float(r.get("precip") or 0.0),
        })
    out.sort(key=lambda r: r["date"])
    return out


def winter_metrics(daily_rows) -> Optional[dict]:
    """Average winter snow-cover + stress metrics across the years in
    ``daily_rows`` (``[{date, tmin, tmax, precip}]``). Returns ``None`` on empty
    input. Shape:

        {
          "snow_cover_days":    float,   # avg days/yr with insulating pack
          "freeze_thaw_cycles": float,   # avg cross-0°C days/yr (Nov–Mar)
          "midwinter_thaw_days":float,   # avg above-freezing days/yr (Dec–Feb)
          "rain_on_snow_days":  float,   # avg rain-on-existing-snowpack days/yr
          "reliability":        str,     # reliable | variable | unreliable
          "years_used":         int,
        }
    """
    rows = _parse_rows(daily_rows)
    if not rows:
        return None

    by_season: dict[int, dict] = {}
    pack = 0.0  # snow water-equivalent (mm), carried day to day
    prev_season: Optional[int] = None
    for r in rows:
        season = _snow_season(r["date"])
        if season != prev_season:
            pack = 0.0  # reset the pack at the start of each snow season
            prev_season = season
        acc = by_season.setdefault(season, {
            "cover": 0, "ft": 0, "thaw": 0, "ros": 0})

        tmean = (r["tmin"] + r["tmax"]) / 2.0
        p = r["precip"]
        # Snowpack update: accumulate when cold, melt via degree-days when warm.
        had_pack = pack >= INSULATING_SWE_MM
        if tmean <= SNOW_TEMP_C:
            pack += p
        else:
            # Rain (warm + wet) on an existing insulating pack → melt + refreeze
            # → ice-encasement risk. Checked before applying the day's melt.
            if p >= 1.0 and had_pack:
                acc["ros"] += 1
            pack = max(0.0, pack - MELT_FACTOR_MM_PER_DEG * (tmean - SNOW_TEMP_C))

        if pack >= INSULATING_SWE_MM:
            acc["cover"] += 1
        m = r["date"].month
        if m in _FREEZE_THAW_MONTHS and r["tmax"] > 0.0 and r["tmin"] < 0.0:
            acc["ft"] += 1
        if m in _MIDWINTER_MONTHS and r["tmax"] > 0.0:
            acc["thaw"] += 1

    seasons = list(by_season.values())
    metrics = {
        "snow_cover_days":     round(_mean([s["cover"] for s in seasons]) or 0.0, 1),
        "freeze_thaw_cycles":  round(_mean([s["ft"] for s in seasons]) or 0.0, 1),
        "midwinter_thaw_days": round(_mean([s["thaw"] for s in seasons]) or 0.0, 1),
        "rain_on_snow_days":   round(_mean([s["ros"] for s in seasons]) or 0.0, 1),
        "years_used":          len(seasons),
    }
    metrics["reliability"] = reliability_label(metrics["snow_cover_days"],
                                               metrics["midwinter_thaw_days"])
    return metrics


def reliability_label(snow_cover_days: float, midwinter_thaw_days: float) -> str:
    """Classify snow-cover reliability from insulating-cover days, downgraded
    when frequent midwinter thaws keep stripping the pack."""
    if snow_cover_days >= 90 and midwinter_thaw_days <= 12:
        return "reliable"
    if snow_cover_days >= 45:
        return "variable"
    return "unreliable"


def survival_notes(metrics: Optional[dict]) -> list[str]:
    """Plain-language, height-aware survival guidance from the metrics. Always
    frames the insulation benefit as conditional (P9 — design for the thin-snow
    year) and points to mulch as the controllable substitute."""
    if not metrics:
        return []
    rel = metrics.get("reliability")
    notes: list[str] = []
    if rel == "reliable":
        notes.append(
            "Reliable snow cover — crowns and low perennials below the snowline "
            "sit roughly a hardiness zone milder than the air. Tree and tall-"
            "shrub buds above the snow get no benefit.")
        notes.append(
            "Still design for the occasional thin-snow winter; don't bank a "
            "marginal plant on snow alone.")
    elif rel == "variable":
        notes.append(
            "Variable snow cover — some winters insulate crowns, others don't. "
            "Treat snow protection as a bonus, not a guarantee; mulch crowns of "
            "marginal perennials.")
    else:
        notes.append(
            "Unreliable snow cover — assume crowns face near-air temperatures. "
            "Choose fully hardy plants and mulch for winter protection.")

    if metrics.get("midwinter_thaw_days", 0) >= 12:
        notes.append(
            "Frequent midwinter thaws (chinook-prone): expect rain-on-snow and "
            "refreeze — favour freeze–thaw-tolerant species and avoid exposed "
            "marginal evergreens.")
    if metrics.get("freeze_thaw_cycles", 0) >= 40:
        notes.append(
            "Many freeze–thaw cycles — mulch and firm in new plantings to resist "
            "frost heave.")
    return notes

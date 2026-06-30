"""
src/snow_microsite.py — where snow drifts and lingers (the *spatial* snow lever).

Design principle P3 (relationships matter — snow, wind, plants and terrain act
together), P7 (cross-domain insight) and P11 (the site knows things the screen
does not) — see docs/DESIGN_PHILOSOPHY.md.

Snow's value is mostly about whether it *stays put where the plants are*. The
single biggest control a designer has over that is the **windbreak**: snow drops
out of moving air in the lee of trees, shrubs and structures — the very same lee
a windbreak shelters. So a snow-catch zone is, geometrically, a wind-shelter zone
computed for the **prevailing winter wind**. Deeper catch = deeper insulating,
better-watered, slightly warmer microsite (good for marginal / moisture-loving
plants); open windward ground is scoured bare (colder, drier — only the toughest
plants).

This module reuses the wind-shelter geometry (:func:`src.wind_shadow.merged_shelter`)
rather than re-deriving it, relabelling the strength bands as snow-catch depth,
and supplies the plain-language interpretation. Qt-free; the merge function is
injectable for tests.
"""

from __future__ import annotations

from typing import Optional

# Wind-shelter strength band → snow-catch depth (same geometry, snow framing).
_CATCH_BY_STRENGTH = {"strong": "deep", "moderate": "moderate", "weak": "light"}


def snow_catch_payload(casters: list, winter_wind_from_deg: float,
                       *, merged_fn=None) -> dict:
    """Snow-accumulation (lee) zones for the prevailing winter wind.

    ``casters`` are wind-shadow casters (``src.wind_shadow.casters_from_project``);
    ``winter_wind_from_deg`` is the winter prevailing wind direction (degrees the
    wind blows *from*). Returns ``{"bands": [{"catch": deep|moderate|light,
    "rings": [...]}, …], "wind_from_deg": …}`` — empty bands when there are no
    casters or shapely is unavailable. ``merged_fn`` is injectable for tests."""
    if merged_fn is None:
        from src.wind_shadow import merged_shelter
        merged_fn = merged_shelter
    shelter = merged_fn(casters, winter_wind_from_deg) or {}
    bands = [
        {"catch": _CATCH_BY_STRENGTH.get(b.get("strength"), "moderate"),
         "rings": b.get("rings", [])}
        for b in shelter.get("bands", [])
    ]
    return {
        "bands": bands,
        "wind_from_deg": shelter.get("wind_from_deg", winter_wind_from_deg),
    }


def winter_prevailing_deg(wind_rose: Optional[dict]) -> Optional[float]:
    """Winter prevailing wind direction (deg FROM) from a wind-rose summary
    (:func:`src.wind.get_wind_summary`), falling back to the annual prevailing
    when the winter block has none. ``None`` when no direction is available."""
    if not wind_rose:
        return None
    seasons = wind_rose.get("seasons") or {}
    winter = seasons.get("winter") or {}
    deg = winter.get("prevailing_deg")
    if deg is None:
        deg = (wind_rose.get("annual") or {}).get("prevailing_deg")
    return float(deg) if deg is not None else None


def interpretation(winter_wind_label: Optional[str] = None) -> list[str]:
    """Plain-language guidance for reading the snow-catch overlay."""
    notes = [
        "Snow drifts into the lee of trees, shrubs and structures — the same "
        "shelter a windbreak gives. Those drifts are deeper-insulated, moister "
        "and slightly warmer: site marginal or moisture-loving plants here.",
        "Open, windward ground is scoured bare — colder and drier. Put the "
        "toughest, most exposure- and drought-hardy plants there, or add a "
        "windbreak to build a catch.",
    ]
    if winter_wind_label:
        notes.append(f"Computed for the prevailing winter wind "
                     f"(from {winter_wind_label}).")
    return notes

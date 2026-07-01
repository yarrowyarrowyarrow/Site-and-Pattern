"""
src/snow_microsite_flow.py — map-side wiring for the snow-catch overlay (Step 3).

The Qt-free maths lives in :mod:`src.snow_microsite` (and the reused
:mod:`src.wind_shadow`); this is the thin glue that gathers the inputs from
``main`` and draws the layer. Kept as free functions taking ``main`` (never new
MainWindow methods — it is at the architecture-guard method ceiling), mirroring
:mod:`src.wind_shadow_flow`.

Snow-catch = wind shelter for the prevailing **winter** wind. The winter
direction comes from the cached wind rose (so this needs the wind rose to have
been fetched once — we read the cache rather than block the UI on a fetch).

Design principle P3 / P7 / P11 — see docs/DESIGN_PHILOSOPHY.md.
"""

from __future__ import annotations

from typing import Optional


def _winter_rose(main) -> Optional[dict]:
    """The site's cached wind rose, or ``None`` when not yet fetched / no pin."""
    coords = main.site_panel.current_coords()
    if not coords:
        return None
    try:
        from src.db.plants import get_cached_wind
        return get_cached_wind(coords[0], coords[1])
    except Exception:  # noqa: BLE001
        return None


def enable(main, on: bool) -> None:
    """Toggle the snow-catch overlay. On: compute + draw + show; off: hide."""
    main._snow_catch_on = bool(on)
    if not on:
        main.map_widget.set_snow_catch_visible(False)
        return
    recompute(main)
    main.map_widget.set_snow_catch_visible(True)


def recompute(main) -> None:
    """Recompute + redraw the snow-catch zones (no-op when the overlay is off).
    Needs a wind rose (winter prevailing direction) and sheltering plants; shows
    a status hint when either is missing."""
    if not getattr(main, "_snow_catch_on", False):
        return
    from src import snow_microsite
    rose = _winter_rose(main)
    deg = snow_microsite.winter_prevailing_deg(rose)
    if deg is None:
        main.statusBar().showMessage(
            "Snow catch needs wind data — fetch the wind rose on "
            "Analysis → Wind first.", 5000)
        main.map_widget.draw_snow_catch({"bands": [], "wind_from_deg": 0})
        return
    from src.wind_shadow import casters_from_project
    try:
        casters = casters_from_project(main._project, year=0)  # mature shelter
    except Exception:  # noqa: BLE001 — never break the map on a bad caster
        casters = []
    payload = snow_microsite.snow_catch_payload(casters, deg)
    main.map_widget.draw_snow_catch(payload)
    if not payload.get("bands"):
        main.statusBar().showMessage(
            "Snow catch: place some trees or shrubs to create sheltered "
            "drifts (or add a windbreak).", 5000)


def on_plants_changed(main, *_args) -> None:
    """A plant moved/placed/removed → refresh the catch zones if the overlay is
    on (the lee geometry depends on the sheltering plants)."""
    if getattr(main, "_snow_catch_on", False):
        recompute(main)

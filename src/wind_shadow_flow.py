"""
wind_shadow_flow.py — orchestration for the live wind-shadow overlay (V1.68).

Free functions taking ``main`` (kept off MainWindow + the map-events controller,
which are both at their guard ceilings — wiring is done from app.py straight to
these). Builds shelter casters from the project, pushes them to the JS live
layer, drives the live angle, and recomputes the authoritative merged footprint
(``src/wind_shadow.merged_shelter``) on commit.

State on ``main``: ``_wind_shadow_on`` (bool), ``_wind_shadow_angle`` (deg from).
"""

from __future__ import annotations


def _angle(main) -> float:
    return float(getattr(main, "_wind_shadow_angle", 270.0))


def _casters(main) -> list:
    from src.wind_shadow import casters_from_project
    try:
        return casters_from_project(main._project, year=0)   # mature shelter
    except Exception:  # noqa: BLE001 — never break the map on a bad caster
        return []


def enable(main, on: bool) -> None:
    """Toggle the live wind-shadow layer. On: push casters + angle, show, and
    compute the merged footprint. Off: hide it."""
    main._wind_shadow_on = bool(on)
    mw = main.map_widget
    if not on:
        mw.set_wind_shadow_visible(False)
        return
    mw.set_wind_casters(_casters(main))
    mw.set_wind_angle_live(_angle(main))
    mw.set_wind_shadow_visible(True)
    recompute_merged(main)


def on_angle_live(main, deg) -> None:
    """Dial scrub: re-orient the JS ghost instantly (no Python geometry)."""
    main._wind_shadow_angle = float(deg)
    if getattr(main, "_wind_shadow_on", False):
        main.map_widget.set_wind_angle_live(float(deg))


def on_angle_commit(main, deg) -> None:
    """Dial released: recompute the authoritative merged footprint."""
    main._wind_shadow_angle = float(deg)
    if getattr(main, "_wind_shadow_on", False):
        recompute_merged(main)


def on_plants_changed(main, *_args) -> None:
    """A plant was moved/placed/removed — rebuild casters + merged (if on)."""
    if not getattr(main, "_wind_shadow_on", False):
        return
    main.map_widget.set_wind_casters(_casters(main))
    recompute_merged(main)


def recompute_merged(main) -> None:
    from src.wind_shadow import merged_shelter
    payload = merged_shelter(_casters(main), _angle(main))
    main.map_widget.draw_merged_wind_shelter(payload)

"""
shade_features_flow.py — Sun & Shade › Existing features, connected to the
design (V3.37).

Free functions taking ``main``, wired once from ``app._connect_signals`` (the
window is at its method ceiling, the map controller near its line ceiling).
The section (``src/shade_features.py``) says what the person ticked; this
writes it into the design as one undo step and asks a shade map on screen to
follow. Scan this area runs the same scan as Site › Features, and the
section's status line repeats the one there.
"""

from __future__ import annotations

from contextlib import nullcontext

from src import sun_shade


def wire(main) -> None:
    section = main.analysis_panel.shade_features
    section.shade_switched.connect(
        lambda indexes, on: switch(main, indexes, on))
    # Undo, redo or a file opened changed what casts: a shade map on screen
    # follows, as it does a tick.
    section.casting_changed.connect(
        lambda: main._map_events._refresh_shade_if_active())
    section.frame_requested.connect(lambda lat, lng: frame(main, lat, lng))
    from src import features_scan_flow
    section.scan_requested.connect(lambda: features_scan_flow.scan_area(main))
    section.by_hand_requested.connect(lambda: by_hand(main))
    main.site_panel.osm_status_changed.connect(section.set_status)


def switch(main, indexes, on: bool) -> int:
    """Switch the shade of the features at ``indexes``: one undo step, then a
    shade map on screen redrawn without (or with) them. Returns how many
    changed."""
    persistence = getattr(main, "_persistence", None)
    label = "cast shade" if on else "stop casting shade"
    cm = (persistence.checkpoint(label) if persistence is not None
          else nullcontext())
    with cm:
        changed = sun_shade.set_shade(main._project, list(indexes), on)
    if changed:
        main._mark_modified()
        main._map_events._refresh_shade_if_active()
    else:
        # Nothing moved (the design changed under the list): show it as it is.
        sc = (main._project.get("properties", {}) or {}).get("site_config")
        main.analysis_panel.shade_features.refresh(main._project, sc)
    return changed


def frame(main, lat: float, lng: float) -> None:
    """The row's feature in the middle of the map, a yard's width around it
    (the scan's review list frames its finds the same way)."""
    main.map_widget.fit_bounds(lat - 0.0004, lng - 0.0006,
                               lat + 0.0004, lng + 0.0006)


def by_hand(main) -> None:
    """Site › Features in front, where the hand tools are."""
    from src.keyboard_help import show_panel
    show_panel(main.site_panel.features_page)

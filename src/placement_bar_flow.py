"""
placement_bar_flow.py — who shows the placement bar, and when it goes (V2.98).

Free functions taking ``main``: ``app.py`` calls :func:`install` once, and the
connections it makes are lambdas into this module, so the bar costs MainWindow
no methods (their budget is guarded; see ``tests/test_architecture_guard.py``).

The bar has two sources and one rule. **It shows while the map is placing, and
says what.** A panel announces that it armed the map (``armed_changed`` /
``armedChanged``, carrying what, how and how many); the bar shows that panel's
controls under the sentence, and the *other* panel stands down, so two panels can
no longer both claim the map. **It goes the moment the map stops placing**, which
until V2.98 Python could not know about when the map stopped on its own: Esc in
the map, a finished fill. The map now reports every mode it enters
(``MapBridge.mode_changed``), and :func:`on_map_mode` follows it out of placing.

That report is what makes Esc mean the same thing on both sides. Before it, Esc
left Python's ``_current_mode`` at ``'polyculture'``, and ``_on_polyculture_click``
places on any map click in that mode: measured in the running app, one click on
empty map after Esc planted the whole community outside the yard.
"""

from __future__ import annotations

from src.placement_arming import describe

#: The map modes in which a click places plants (or corners of an area to fill).
PLACING_MODES = ("plant", "polyculture", "fill")


def install(main) -> None:
    """Build the bar over the map and wire both panels and the map to it."""
    from src.placement_bar import PlacementBar
    holder = main.map_widget.parentWidget()
    bar = PlacementBar(holder, anchor=main.map_widget)
    main.placement_bar = bar
    bar.add_page("plants", main.plant_panel.placement_controls(),
                 accessory=main.plant_panel.placement_accessory())
    bar.add_page("communities", main.polyculture_panel.placement_controls())
    bar.done_requested.connect(main._cancel_draw)
    main.plant_panel.armed_changed.connect(
        lambda info: on_armed(main, "plants", info))
    main.polyculture_panel.armedChanged.connect(
        lambda info: on_armed(main, "communities", info))
    main.map_widget.bridge.mode_changed.connect(
        lambda mode, seq: on_map_mode(main, mode, seq))


def _panels(main) -> dict:
    return {"plants": getattr(main, "plant_panel", None),
            "communities": getattr(main, "polyculture_panel", None)}


def on_armed(main, source: str, info: dict) -> None:
    """A panel armed the map, or stood down."""
    bar = getattr(main, "placement_bar", None)
    if bar is None:
        return
    if info.get("armed"):
        for other, panel in _panels(main).items():
            if other != source and panel is not None:
                try:
                    panel.set_armed(False)
                except (AttributeError, RuntimeError):
                    pass
        headline, instruction = describe(
            source, info.get("kind", "single"), info.get("what", ""),
            qty=int(info.get("qty") or 1), mix=int(info.get("mix") or 0))
        bar.show_page(source, headline, instruction)
    elif bar.source == source:
        bar.hide_bar()


def on_map_mode(main, mode: str, seq: int) -> None:
    """The map entered ``mode``. Follow it out of placing; nothing else.

    ``seq`` is the stamp of the last mode change Python had sent when the map
    made this one. Python and the map can cross: Esc pressed a moment after you
    picked a new plant reaches Python *after* Python armed the new plant, and
    acting on it would stand the fresh placement down. So a report older than
    Python's latest change is ignored; the map will report again once it has
    caught up.

    Entering a placing mode needs nothing here: Python sent it, and the panel
    that armed it has already said so.
    """
    try:
        if int(seq) < int(main.map_widget.mode_seq):
            return
    except (AttributeError, TypeError, ValueError):
        return
    if mode in PLACING_MODES:
        return
    was_placing = getattr(main, "_current_mode", "none") in PLACING_MODES
    stand_down(main)
    if mode == "none" and was_placing:
        # The map stopped placing on its own (Esc in the map, a finished fill):
        # say so everywhere Python keeps it.
        main._current_mode = "none"
        try:
            main._set_mode_label("Ready")
            main.toolbar.reset_draw_buttons()
        except (AttributeError, RuntimeError):
            pass


def stand_down(main) -> None:
    """Placing is over: the bar goes, neither panel claims the map, and the
    stashes that describe an in-flight placement are dropped.

    ``_pending_fill`` is left alone on purpose: a finished fill leaves placing
    *before* it hands over its polygon, and the polygon still needs the spec.
    """
    for panel in _panels(main).values():
        if panel is None:
            continue
        try:
            panel.set_armed(False)
        except (AttributeError, RuntimeError):
            pass
    try:
        main.plant_panel.clear_pending_polyculture()
    except (AttributeError, RuntimeError):
        pass
    main._pending_community_pattern = None
    main._pending_community_pattern_mix = None
    bar = getattr(main, "placement_bar", None)
    if bar is not None:
        try:
            bar.hide_bar()
        except RuntimeError:
            pass

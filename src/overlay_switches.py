"""
overlay_switches.py — a switch with nothing to change says what it needs
(V3.19, QF-19).

The V3.05 click pass found 29 controls that changed nothing visible when
pressed, and the first review counted the 13 of them that style an overlay
(R27): the four contour options on Slope, the two shadow options on Sun &
Shade, two wind options, and the relationship web's five filters. Each was
enabled the whole time and nothing said why a click did nothing. They are not
one case:

  * **Sun & Shade** (*Show shadow direction arrows*, *Show shadow length
    indicators*) redraw a drawn sun path at once, and do nothing without one.
  * **Wind** (*Wind direction arrows*, *Shelter zones behind windbreaks*)
    were read only by *Show Wind Overlay*: with the overlay up, a click
    changed nothing until the button was pressed again. They now redraw a
    drawn overlay at once, as the shadow options do.
  * **Habitat**'s five filters change the relationship web, which draws only
    while *Show the relationship web on the map* is ticked.

Each of those is now offered only while its overlay is on the map, and while
it is not, its tooltip (and the description a screen reader reads with its
name) says what to do first. The map widget records which overlays it has
drawn (``MapWidget.overlay_shown``, ``overlays_changed``), whatever drew or
cleared them: a button, undo, an open, the map's own right-click menu.

The four **Slope** options are not in this table on purpose. They are what
*Generate* reads (``SitePanel._on_auto_terrain_generate``): they choose what
the next slope map draws, and they act on nothing already drawn. Disabled
until a slope map existed, *Water flow*, which starts unticked, could never be
asked for on the first Generate. Their tooltips say when they apply instead.

Wired from ``MainWindow._connect_signals`` (MainWindow is at its method
ceiling).
"""

from __future__ import annotations

#: The words when an overlay is not drawn: what to do first, and what the
#: switch is for. One sentence each, as the words guide asks of a message.
SUN_FIRST = ("Press “Show sun path” first. This changes the sun path drawn "
             "on the map.")
WIND_FIRST = ("Press “Show Wind Overlay” first. This changes the wind "
              "overlay drawn on the map.")
WEB_FIRST = ("Tick “Show the relationship web on the map” first. This "
             "chooses what the web draws.")

#: A tooltip a switch had of its own, kept to give back when it is offered.
_OWN_TIP = "_overlay_switch_own_tip"


def groups(main) -> tuple:
    """``((switches, is_drawn, words when not), ...)``: each overlay's
    switches, a callable that says whether the overlay is on the map now, and
    what the switches say until it is."""
    a = main.analysis_panel
    mw = main.map_widget
    return (
        ((a._sun_shadows, a._sun_shadow_length),
         lambda: mw.overlay_shown("sun_path"), SUN_FIRST),
        ((a._wind_arrows, a._wind_shelter),
         lambda: mw.overlay_shown("wind"), WIND_FIRST),
        (tuple(a._web_layer_boxes.values()),
         lambda: a._web_toggle.isChecked(), WEB_FIRST),
    )


def offer(box, ready: bool, need: str) -> None:
    """Enable ``box`` when its overlay is drawn; otherwise disable it and say
    ``need`` in its tooltip and accessible description."""
    own = box.property(_OWN_TIP)
    if own is None:
        own = box.toolTip() or ""
        box.setProperty(_OWN_TIP, own)
    box.setEnabled(bool(ready))
    tip = own if ready else need
    box.setToolTip(tip)
    box.setAccessibleDescription(tip)


def sync(main) -> None:
    """Bring every overlay switch in line with what the map shows now."""
    for boxes, drawn, need in groups(main):
        ready = bool(drawn())
        for box in boxes:
            offer(box, ready, need)


def _redraw_wind(main) -> None:
    """A wind switch was clicked: redraw the overlay if it is up (V3.19).
    Until then the two were read only by *Show Wind Overlay*, so a click with
    the overlay drawn changed nothing until the button was pressed again."""
    if main.map_widget.overlay_shown("wind"):
        main.analysis_panel._on_show_wind()


def install(main) -> None:
    """Wire the switches to the map's overlays, and set them for now."""
    main.map_widget.overlays_changed.connect(lambda: sync(main))
    a = main.analysis_panel
    a._web_toggle.toggled.connect(lambda _on: sync(main))
    for box in (a._wind_arrows, a._wind_shelter):
        box.toggled.connect(lambda _on: _redraw_wind(main))
    sync(main)

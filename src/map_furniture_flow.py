"""
map_furniture_flow.py — the north arrow and the scale bar, as View menu
switches (F205, V3.06).

Design principle P11 — see docs/DESIGN_PHILOSOPHY.md.

The map had neither, so a picture of a design (a screenshot, or the map page
of Export PDF, which is a grab of the map as shown) could not be read for
direction or distance, and a person standing in the yard with it could not
line it up or pace it out. View → North Arrow and View → Scale Bar switch each
on and off; View → Scale Units picks Automatic, Kilometres or Metres, and a
click on the bar fixes the other unit from the one it shows. All three are
remembered between sessions.

Automatic is the default since V3.19 (QF-18, R18; the owner's answer K1,
"Automatic but able to change between the 2"): metres below 1 km and kilometres
from 1 km, where V3.06's kilometres default read "0.005 km" across a yard. No
install is moved: the unit is written only when a person picks one (the menu or
a click on the bar), so a stored unit is a choice and is kept, and an install
that never chose has nothing stored and reads Automatic.

The drawing is the map page's (``html/map/11-map-furniture.js``); this module
only keeps the settings and tells the page, now if it has loaded and again on
every load, since a reloaded page starts bare. The same page draws the line that
says the map needs an internet connection (V3.19, QF-6), which Export PDF keeps
off its map picture through :func:`offline_notice_held`.
"""

from __future__ import annotations

from contextlib import contextmanager

from PyQt6.QtCore import QSettings
from PyQt6.QtGui import QActionGroup

KEY_ARROW = "map/north_arrow"
KEY_SCALE = "map/scale_bar"
KEY_UNIT = "map/scale_units"
UNITS = ("auto", "km", "m")
_ACTIONS = {"auto": "_act_scale_auto", "km": "_act_scale_km",
            "m": "_act_scale_m"}


def _flag(value, default: bool) -> bool:
    """A QSettings boolean, which comes back as a string on some platforms."""
    if value is None:
        return default
    if isinstance(value, str):
        return value.strip().lower() in ("1", "true", "yes", "on")
    return bool(value)


def state() -> dict:
    """What the switches say: both on and Automatic until changed."""
    s = QSettings()
    unit = str(s.value(KEY_UNIT, "auto") or "auto")
    return {"north_arrow": _flag(s.value(KEY_ARROW), True),
            "scale_bar": _flag(s.value(KEY_SCALE), True),
            "unit": unit if unit in UNITS else "auto"}


def apply(main, *, force: bool = False) -> None:
    """Draw what the switches say on the map. Not before its page has loaded
    (``run_js`` does not queue, and a page that loads later is told on
    ``map_ready``, which passes ``force``)."""
    mw = main.map_widget
    if not force and not getattr(mw, "is_ready", True):
        return
    st = state()
    mw.set_north_arrow(st["north_arrow"])
    mw.set_scale_bar(st["scale_bar"], st["unit"])


@contextmanager
def offline_notice_held(main):
    """Keep the line that says the map needs a connection off the map while
    Export PDF asks where to save and grabs the map (V3.19, QF-6, from the
    review): it is the screen's, and on a printed plan it read as part of the
    plan. The save box gives the page time to draw itself without it before
    the grab; afterwards it comes back if it still applies."""
    mw = main.map_widget
    ready = bool(getattr(mw, "is_ready", False))
    if ready:
        mw.hold_offline_notice(True)
    try:
        yield
    finally:
        if ready:
            mw.hold_offline_notice(False)


def set_flag(main, key: str, on: bool) -> None:
    QSettings().setValue(key, bool(on))
    apply(main)


def set_unit(main, unit: str) -> None:
    """Automatic, kilometres or metres, from the menu or a click on the bar
    (which sends only kilometres or metres)."""
    unit = unit if unit in UNITS else "auto"
    QSettings().setValue(KEY_UNIT, unit)
    act = getattr(main, _ACTIONS[unit], None)
    if act is not None and not act.isChecked():
        act.setChecked(True)
    apply(main)


def install(main, menu) -> None:
    """Add North Arrow, Scale Bar and Scale Units to ``menu`` (View), and draw
    them once the map can: now if it has loaded, and on every load after."""
    st = state()
    arrow = menu.addAction("&North Arrow")
    arrow.setCheckable(True)
    arrow.setChecked(st["north_arrow"])
    arrow.setStatusTip("Show an arrow pointing north on the map, and in the "
                       "map picture Export PDF takes")
    scale = menu.addAction("Scale &Bar")
    scale.setCheckable(True)
    scale.setChecked(st["scale_bar"])
    scale.setStatusTip("Show a scale bar at the bottom of the map, and in the "
                       "map picture Export PDF takes")
    units = menu.addMenu("Scale &Units")
    # Behind View → Advanced tools (V3.21): its menu action, by name.
    units.menuAction().setObjectName("view_scale_units")
    group = QActionGroup(units)
    group.setExclusive(True)
    auto = units.addAction("&Automatic")
    auto.setStatusTip("Metres below 1 km, kilometres from 1 km")
    km = units.addAction("&Kilometres")
    metres = units.addAction("&Metres")
    for act in (auto, km, metres):
        act.setCheckable(True)
        group.addAction(act)
    {"auto": auto, "km": km, "m": metres}[st["unit"]].setChecked(True)
    main._act_north_arrow, main._act_scale_bar = arrow, scale
    main._act_scale_auto, main._act_scale_km, main._act_scale_m = auto, km, metres

    arrow.toggled.connect(lambda on: set_flag(main, KEY_ARROW, on))
    scale.toggled.connect(lambda on: set_flag(main, KEY_SCALE, on))
    auto.triggered.connect(lambda: set_unit(main, "auto"))
    km.triggered.connect(lambda: set_unit(main, "km"))
    metres.triggered.connect(lambda: set_unit(main, "m"))
    bridge = main.map_widget.bridge
    bridge.scale_unit_changed.connect(lambda unit: set_unit(main, unit))
    bridge.map_ready.connect(lambda: apply(main, force=True))
    if getattr(main.map_widget, "is_ready", False):
        apply(main)

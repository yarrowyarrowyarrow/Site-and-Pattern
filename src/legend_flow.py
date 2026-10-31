"""
legend_flow.py — how far down the map's legend goes, remembered (F217, V3.11).

The legend (``html/map/12-legend.js``) names only what is on the map, and two
of its sections have a switch: plants by **type** (Tree, Shrub, …) or by
**species**, numbered as the printed planting plan numbers them, and boundaries
**simple** (one line, "Boundary") or **named** (one line per colour and name,
"City park land", "Private lot"). The switches are the page's; this module
keeps what they say between sessions and tells the page, now if it has loaded
and again on every load, since a reloaded page starts bare. The pattern is
``map_furniture_flow``'s.
"""

from __future__ import annotations

KEY_PLANTS = "map/legend_plants"
KEY_BOUNDARIES = "map/legend_boundaries"
PLANTS = ("type", "species")
BOUNDARIES = ("simple", "named")


def normalise(plants, boundaries) -> tuple[str, str]:
    """The two values, each one the page knows or its default. Qt-free."""
    p = str(plants or "").strip().lower()
    b = str(boundaries or "").strip().lower()
    return (p if p in PLANTS else PLANTS[0],
            b if b in BOUNDARIES else BOUNDARIES[0])


def state() -> tuple[str, str]:
    """What the switches said last: by type and simple until changed."""
    from PyQt6.QtCore import QSettings
    s = QSettings()
    return normalise(s.value(KEY_PLANTS), s.value(KEY_BOUNDARIES))


def apply(main, *, force: bool = False) -> None:
    """Tell the page. Not before it has loaded (``run_js`` does not queue, and
    a page that loads later is told on ``map_ready``, which passes ``force``)."""
    mw = main.map_widget
    if not force and not getattr(mw, "is_ready", True):
        return
    mw.set_legend_detail(*state())


def remember(plants: str, boundaries: str) -> None:
    """A switch in the legend changed: keep it for next time."""
    from PyQt6.QtCore import QSettings
    p, b = normalise(plants, boundaries)
    s = QSettings()
    s.setValue(KEY_PLANTS, p)
    s.setValue(KEY_BOUNDARIES, b)


def install(main) -> None:
    bridge = main.map_widget.bridge
    bridge.legend_detail_changed.connect(remember)
    bridge.map_ready.connect(lambda: apply(main, force=True))
    if getattr(main.map_widget, "is_ready", False):
        apply(main)

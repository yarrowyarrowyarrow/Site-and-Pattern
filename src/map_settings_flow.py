"""
map_settings_flow.py — View › Map Settings…: the satellite token and the
scroll-wheel zoom step (V3.07).

The zoom step sat at the end of the View row until V3.07, off-screen at
1366 px, and was never remembered: every launch began at Fine. The owner moved
it here on the V3.05 surface audit, a preference rather than a tool. It is saved
now, and sent to the map each time its page loads (``run_js`` does not queue a
call, so one made before the page is up would only log an error).
"""

from __future__ import annotations

from PyQt6.QtCore import QSettings

KEY_ZOOM = "map/zoom_sensitivity"

#: ``(level, words)``, in the order the dialog lists them. The levels are the
#: map page's own (``setZoomSensitivity`` in html/map/05-features.js), whose
#: default is Fine.
ZOOM_LEVELS = (
    ("fine", "Fine (1.1× per wheel step)"),
    ("normal", "Normal (1.26×)"),
    ("fast", "Fast (1.5×)"),
    ("coarse", "Coarse (2×)"),
)
_KNOWN = tuple(level for level, _words in ZOOM_LEVELS)


def zoom_level() -> str:
    """The saved scroll-wheel step, Fine until changed."""
    level = str(QSettings().value(KEY_ZOOM, "fine") or "fine")
    return level if level in _KNOWN else "fine"


def apply(main, *, force: bool = False) -> None:
    """Send the saved step to the map, once its page has loaded (``force``
    is the page saying it has)."""
    mw = main.map_widget
    if not force and not getattr(mw, "is_ready", True):
        return
    mw.set_zoom_sensitivity(zoom_level())


def set_zoom_level(main, level: str) -> None:
    QSettings().setValue(KEY_ZOOM, level if level in _KNOWN else "fine")
    apply(main)


def install(main) -> None:
    """Send the saved step on every load of the map's page, and now if it has
    already loaded."""
    main.map_widget.bridge.map_ready.connect(lambda: apply(main, force=True))
    if getattr(main.map_widget, "is_ready", False):
        apply(main)


def open_dialog(main) -> None:
    """View › Map Settings…: the Mapbox token and the zoom step."""
    from src.preferences_dialog import MapPreferencesDialog
    from src.settings import get_mapbox_token, set_mapbox_token
    dlg = MapPreferencesDialog(current_token=get_mapbox_token() or "",
                               zoom_level=zoom_level(), parent=main)
    if dlg.exec() != MapPreferencesDialog.DialogCode.Accepted:
        return
    token = dlg.token()
    set_mapbox_token(token)
    if token:
        main.map_widget.set_mapbox_token(token)
    set_zoom_level(main, dlg.zoom_level())

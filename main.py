"""
main.py — Site & Pattern entry point.

Usage:
    python main.py
"""

import sys
import os

# Allow importing from the project root
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Wire up a CA bundle before anything can open an https connection —
# macOS Pythons and frozen builds ship no root certificates, which
# silently breaks every network feature (see src/ssl_bootstrap.py).
from src.ssl_bootstrap import ensure_ca_bundle
ensure_ca_bundle()

# File + stderr logging (V2.22) — before any Qt import so even an import-time
# failure of the GUI stack leaves a trace in <user data dir>/logs/app.log.
from src.log import init_logging
init_logging()

from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QIcon
from PyQt6.QtCore import Qt, QtMsgType, QTimer, qInstallMessageHandler

# QtWebEngine must be initialised before QApplication on some platforms
from PyQt6.QtWebEngineWidgets import QWebEngineView  # noqa: F401

from src.app import MainWindow
from src import app_mode, onboarding_flow


def _qt_message_filter(msg_type, context, message):
    # Qt 6 + Windows HiDPI + per-widget `font-size: NNpx` stylesheets
    # cause the engine to internally call QFont::setPointSize(-1) when
    # switching the font's size unit from points to pixels. The
    # warning is harmless but extremely noisy (one per styled widget
    # × many widgets in the side panels). Drop just this specific
    # line; pass everything else through to stderr unchanged.
    if msg_type == QtMsgType.QtWarningMsg and \
            "QFont::setPointSize: Point size <= 0" in (message or ""):
        return
    sys.stderr.write(f"{message}\n")
    sys.stderr.flush()


def main():
    # Filter the Qt-internal QFont stylesheet warning before the
    # QApplication starts wiring up panels and emitting it.
    qInstallMessageHandler(_qt_message_filter)

    # High-DPI support
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    # The user-facing name is "Site & Pattern" (see src/branding.py and the
    # window title), but the Qt application/organization name deliberately keeps
    # the legacy "PermaDesign" identifier: it keys QSettings (window geometry +
    # the one-time legacy-recipe migration flag), so renaming it would orphan
    # existing users' settings and risk re-running that migration.
    app.setApplicationName("PermaDesign")
    app.setApplicationVersion("1.0.0")
    app.setOrganizationName("PermaDesign")

    # One ring that follows keyboard focus in every window, the start screen
    # included (F195, V3.02): the panels' own stylesheets remove Qt's.
    # V3.05: an exception escaping a button's code is logged and reported,
    # not the end of the session (PyQt6 aborts on one otherwise).
    from src import slot_errors
    slot_errors.install()

    from src import focus_ring
    focus_ring.install(app)
    # And every control at least 24 px across, and every checkbox's box
    # visible (F195, V3.03).
    from src import indicator_style, target_size
    target_size.install(app)
    indicator_style.install(app)
    # The app's own icon on every window, the start screen's included (F232,
    # V3.17); the .exe and the Mac app carry it from the build.
    from src import app_icon
    app_icon.install(app)

    # The start screen, ahead of the map (V2.40, page in V2.41). Everything it
    # offers is read from disk — the saves folder, the design you were last in,
    # an autosave that survived a crash, what is in bloom — so it needs no
    # MainWindow, and running it first is the whole difference between a start
    # screen and a dialog laid over an app you can already see. Returns "" when
    # it is turned off or dismissed, which means "start me on the blank map".
    #
    # The window is built *behind* it, on a zero-timer that fires inside the
    # screen's own modal event loop. Constructing MainWindow is a few hundred
    # ms and starts no threads, but it kicks off the Leaflet load, which is
    # asynchronous and is the part that actually costs seconds. Without this
    # the screen would be a straight regression in perceived speed: today's
    # dialog already has the map loading behind it. Nothing is shown until a
    # door is picked.
    built: dict = {}
    QTimer.singleShot(0, lambda: built.setdefault("window", MainWindow()))
    choice = onboarding_flow.choose_start_action()

    window = built.get("window") or MainWindow()
    # V2.43 — the Learn door does not open the design app. Its surfaces are
    # standalone windows (a walkable landscape, the Field Guide, the lessons),
    # and *not showing the map and the six side tabs* is the whole of the
    # simplification the feedback asked for. The window is still built — it is
    # what the Learn windows hang their singletons off, and it makes stepping
    # into Design later instant — it is simply never shown.
    if app_mode.opens_main_window(choice):
        window.show()
    # Rows that draw a project wait for map_ready; the rest run at once.
    onboarding_flow.act_on_start_choice(window, choice)

    # Safety net: if a Learn door failed to open its window, Qt would quit the
    # moment this function returns, with nothing on screen and no error. A
    # working app on the wrong screen beats a silent exit.
    if not any(w.isVisible() for w in app.topLevelWidgets()):
        window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()

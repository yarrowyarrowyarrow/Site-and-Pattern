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
from PyQt6.QtCore import Qt, QtMsgType, qInstallMessageHandler

# QtWebEngine must be initialised before QApplication on some platforms
from PyQt6.QtWebEngineWidgets import QWebEngineView  # noqa: F401

from src.app import MainWindow
from src import onboarding_flow


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

    # The start menu, ahead of the map (V2.40). Everything it offers is read
    # from disk — the saves folder, the design you were last in, an autosave
    # that survived a crash — so it needs no MainWindow, and running it first
    # is the whole difference between a start screen and a dialog laid over an
    # app you can already see. Returns "" when it is turned off or dismissed,
    # which means "start me on the blank map".
    choice = onboarding_flow.choose_start_action()

    window = MainWindow()
    window.show()
    # Acted on once the map can render, not now — see act_on_start_choice.
    onboarding_flow.act_on_start_choice(window, choice)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()

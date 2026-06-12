"""
main.py — PermaDesign entry point.

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

from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QIcon
from PyQt6.QtCore import Qt, QtMsgType, qInstallMessageHandler

# QtWebEngine must be initialised before QApplication on some platforms
from PyQt6.QtWebEngineWidgets import QWebEngineView  # noqa: F401

from src.app import MainWindow


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
    app.setApplicationName("PermaDesign")
    app.setApplicationVersion("1.0.0")
    app.setOrganizationName("PermaDesign")

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()

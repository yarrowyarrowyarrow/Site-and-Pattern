"""
main.py — PermaDesign entry point.

Usage:
    python main.py
"""

import sys
import os

# Allow importing from the project root
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QIcon
from PyQt6.QtCore import Qt

# QtWebEngine must be initialised before QApplication on some platforms
from PyQt6.QtWebEngineWidgets import QWebEngineView  # noqa: F401

from src.app import MainWindow


def main():
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

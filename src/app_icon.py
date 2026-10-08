"""
src/app_icon.py — the app's icon on its own windows (F232, V3.17).

The .exe and the Mac app carry the icon from the build (``permadesign.spec``,
the files made by ``scripts/packaging/make_app_icon.py``). This puts the same
picture on the windows themselves: the title bar, the taskbar button and
Alt-Tab, which Qt otherwise draws blank, and on a source checkout, which has
no .exe to carry an icon at all.

Qt is imported only when the icon is built, so the sizes and paths can be
checked without it.
"""

from __future__ import annotations

from src.resources import resource_path

# Every size the build makes (make_app_icon.WINDOWS_SIZES). Qt draws the
# nearest, so a title bar gets the hand-made 16 px frame, not a shrunk 256.
SIZES = (16, 20, 24, 32, 40, 48, 64, 96, 128, 256)


def path(size: int) -> str:
    return resource_path("assets", "icon", f"app_{size}.png")


def icon():
    from PyQt6.QtCore import QSize
    from PyQt6.QtGui import QIcon
    ic = QIcon()
    for s in SIZES:
        ic.addFile(path(s), QSize(s, s))
    return ic


def install(app) -> None:
    """Every window the app opens, the start screen's included."""
    app.setWindowIcon(icon())

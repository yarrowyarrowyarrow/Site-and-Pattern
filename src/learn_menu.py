"""
learn_menu.py — the second screen, behind the Learn door (V2.43).

Design principle P13 — see docs/DESIGN_PHILOSOPHY.md.
UI conventions: docs/UI_PRINCIPLES.md (Krug), same as ``start_screen``.

Three places to go, in the order a person needs them: walk into a real wild
community and plant in it, look something up, be taught about what you just
did. Which rows exist and what they are called lives in the Qt-free
:mod:`src.app_mode`; this file is presentation only, exactly like
``start_screen`` — that separation is what lets the routing be tested without
a display.

Deliberately built from ``start_screen``'s own ``_Row`` and ``_LINK``. It is
the same screen family and a second, near-identical set of styles would drift
apart within a release or two; the V2.41 rewrite is the house style and this
inherits it rather than re-deciding it.

**The Learn doors open standalone windows.** No map, no side tabs, no site
analysis — that is the whole simplification the feedback asked for, and the
mechanism is :func:`src.app_mode.opens_main_window` returning ``False`` for
these keys. See :mod:`src.app_mode` for why the split is a door at boot rather
than the mid-session toggle V2.42 argued against.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget,
)

from src import app_mode
from src.branding import APP_NAME
from src.start_screen import _LINK, _Row
from src.ui_style import BASE_SURFACE

#: Re-exported so callers do not need to import two modules to read a choice.
BACK = app_mode.BACK


class LearnMenu(QDialog):
    """Ask what the user came to learn. ``choice()`` is one of the
    :mod:`src.app_mode` keys, or ``""`` if they closed it."""

    def __init__(self, parent: QWidget | None = None, *,
                 discovery_line: str = "", communities: int = 0,
                 sandbox: str = ""):
        super().__init__(parent)
        self.setWindowTitle(f"{APP_NAME}: Learn")
        self.setMinimumWidth(560)
        self._choice = ""
        # Carried, not inherited — this can open before any MainWindow exists,
        # so there is no parent stylesheet to take the theme from.
        self.setStyleSheet(BASE_SURFACE)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 16)
        layout.setSpacing(9)

        head = QLabel("Learn")
        head.setStyleSheet("color: #e8f5e9; font-size: 24px; "
                           "font-weight: bold;")
        layout.addWidget(head)
        # One line, and it is a promise about what happens here rather than a
        # mission statement. Krug: happy talk must die.
        sub = QLabel("Walk it, look it up, then be taught it.")
        sub.setStyleSheet("color: #8fb98f; font-size: 13px;")
        layout.addWidget(sub)
        layout.addSpacing(6)

        notes = app_mode.learn_notes(discovery_line=discovery_line,
                                     communities=communities,
                                     sandbox=sandbox)
        for i, (key, icon, title) in enumerate(app_mode.LEARN_DOORS):
            row = _Row(icon, title, notes.get(key, ""), primary=(i == 0), parent=self)
            row.clicked.connect(lambda _c=False, k=key: self._pick(k))
            layout.addWidget(row)

        layout.addSpacing(2)

        tail = QHBoxLayout()
        back = QPushButton("← Back")
        back.setCursor(Qt.CursorShape.PointingHandCursor)
        back.setFlat(True)
        back.setStyleSheet(_LINK)
        back.setToolTip("Return to the start screen.")
        back.clicked.connect(lambda: self._pick(BACK))
        tail.addWidget(back)
        tail.addStretch()
        layout.addLayout(tail)

    # ── Result ──────────────────────────────────────────────────────────────

    def _pick(self, key: str):
        self._choice = key
        self.accept()

    def choice(self) -> str:
        return self._choice


# ── The lessons window ───────────────────────────────────────────────────────

class LearnStudioWindow(QWidget):
    """Lessons, Field Study and Present, as a window of their own.

    ``LearnPanel`` is a self-contained ``QWidget`` that takes its design
    through two provider callables and knows nothing about ``MainWindow`` — so
    Learn mode can host it directly rather than opening the whole app to reach
    one side tab. Nothing about the panel changes; it is simply given a
    different project to talk about.

    The project it talks about is **the sandbox**: the reference landscape the
    user has been planting in. That is the V2.43 move that made this cheap —
    ``lesson_track``, ``docent`` and ``field_study`` all already took
    ``placed_plants`` as a plain argument, so none of them needed a line
    changed to be about a fen instead of a front yard.
    """

    def __init__(self, plants: list | None = None, title: str = ""):
        super().__init__(None)          # top-level window
        name = f"{APP_NAME}: Lessons"
        self.setWindowTitle(f"{name} — {title}" if title else name)
        self.resize(560, 760)
        self.setStyleSheet(BASE_SURFACE)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)

        from src.learn_panel import LearnPanel
        self.panel = LearnPanel(self)
        lay.addWidget(self.panel)
        self.set_plants(plants or [])

    def set_plants(self, plants: list) -> None:
        """Point the lessons at a landscape. Never raises: an empty or
        unreadable sandbox should leave the lessons talking about the
        catalogue, which is what they do with no plants."""
        try:
            self.panel.set_placed_plants(list(plants or []))
            self.panel.set_structures([])
        except Exception:                                  # noqa: BLE001
            pass

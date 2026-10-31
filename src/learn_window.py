"""
learn_window.py — the Lessons and the Quizzes, each a window of its own
(V2.43 as ``learn_menu.py``; split by page V3.42).

Design principle P13 — see docs/DESIGN_PHILOSOPHY.md.

The start screen's Learn column opens them (V3.42, the owner: "Lessons and
quizzes should each be a separate line item under learn"), so each window
shows one page with its own title and no tab bar. Until V3.42 this module also
held ``LearnMenu``, the second screen the Learn doors sat behind; the doors are
on the start screen now and the menu is gone, which is why the module was
renamed. The routing is in the Qt-free :mod:`src.app_mode`.
"""

from __future__ import annotations

from PyQt6.QtWidgets import QVBoxLayout, QWidget

from src.app_mode import LESSONS, QUIZZES
from src.branding import APP_NAME
from src.ui_style import BASE_SURFACE

#: The window's word for each page, as the start screen names the door.
TITLES = {LESSONS: "Lessons", QUIZZES: "Quizzes"}


class LearnStudioWindow(QWidget):
    """The Lessons or the Quizzes, as a window of their own. Present left it in
    V3.38 (F258): it narrated a lawn conversion over a wild community.

    ``LearnPanel`` is a self-contained ``QWidget`` that takes its design
    through two provider callables and knows nothing about ``MainWindow`` — so
    a Learn window can host it directly rather than opening the whole app to
    reach one side tab. Nothing about the panel changes; it is simply given a
    different project to talk about, and shows one of its pages (``page``,
    :data:`~src.app_mode.LESSONS` or :data:`~src.app_mode.QUIZZES`).

    The project it talks about is **the sandbox**: the reference landscape the
    user has been planting in. That is the V2.43 move that made this cheap —
    ``lesson_track``, ``docent`` and ``field_study`` all already took
    ``placed_plants`` as a plain argument, so none of them needed a line
    changed to be about a fen instead of a front yard.
    """

    def __init__(self, plants: list | None = None, title: str = "",
                 page: str = LESSONS):
        super().__init__(None)          # top-level window
        self.page = page if page in TITLES else LESSONS
        name = f"{APP_NAME}: {TITLES[self.page]}"
        self.setWindowTitle(f"{name} — {title}" if title else name)
        self.resize(560, 760)
        self.setStyleSheet(BASE_SURFACE)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)

        from src.learn_panel import LearnPanel
        self.panel = LearnPanel(self, present=False)
        lay.addWidget(self.panel)
        # The lessons' first landscape is the walk planted in, not "your
        # design" (V3.41).
        self.panel._lesson_track.set_here_label(
            f"The walk you planted in: {title}" if title
            else "The walk you planted in")
        from src.quiz_topics import WALKED
        self.panel._field_study.set_landscape_words(WALKED)
        # One page, chosen at the door: no tab bar to switch to the other.
        tabs = self.panel._tabs
        shown = (self.panel._lesson_track if self.page == LESSONS
                 else self.panel._field_study)
        for i in range(tabs.count()):
            if tabs.widget(i).isAncestorOf(shown):
                tabs.setCurrentIndex(i)
        tabs.tabBar().hide()
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

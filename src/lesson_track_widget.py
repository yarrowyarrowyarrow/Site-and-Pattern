"""
lesson_track_widget.py — the Lessons page (F53; three lessons since V3.41, F88).

A self-contained QWidget that shows ``src.lessons``' three lessons a page at a
time: the page's text, a *Look at it* pointer into the app, what the page
means for **a landscape the reader chooses** (the one this window is about, a
walk, or a saved design), its sources, and Back / Next. All the words are in
the Qt-free ``lessons`` module; this only renders and tracks the page.

Until V3.41 it showed ``src.lesson_track``'s four one-paragraph steps
"against your design", which in the Learn window meant the walk's sandbox and
read to the owner as unclear.

Design principle P5 (a guided sequence builds the model) and P7 — see
docs/DESIGN_PHILOSOPHY.md.
"""

from __future__ import annotations

import html
import json
from typing import Callable, Optional

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QComboBox, QFormLayout, QHBoxLayout, QLabel, QPushButton, QVBoxLayout,
    QWidget,
)

#: How many saved designs the chooser offers, newest first.
SAVED_SHOWN = 8


class LessonTrackWidget(QWidget):
    """The lessons. ``plants_provider`` / ``structures_provider`` return the
    landscape this window is about (the open design, or the walk planted in),
    the chooser's first entry; :meth:`set_here_label` names it."""

    def __init__(self, plants_provider: Optional[Callable] = None,
                 structures_provider: Optional[Callable] = None, parent=None):
        super().__init__(parent)
        self._plants_provider = plants_provider
        self._structures_provider = structures_provider
        self._steps: list[dict] = []
        self._i = 0
        self._lands: dict = {}
        self._build()

    def _build(self):
        from src import lessons
        lay = QVBoxLayout(self)
        lay.setContentsMargins(6, 6, 6, 6)
        lay.setSpacing(8)

        intro = QLabel(
            "Three short lessons. Each page ends with what it means for a "
            "landscape you choose: a walk, or one of your designs.")
        intro.setWordWrap(True)
        intro.setStyleSheet("color: #90a4ae; font-size: 12px;")
        lay.addWidget(intro)

        form = QFormLayout()
        form.setContentsMargins(0, 0, 0, 0)
        self._lesson_box = QComboBox()
        self._lesson_box.setAccessibleName("Lesson")
        for key, title, _pages in lessons.LESSONS:
            self._lesson_box.addItem(title, key)
        form.addRow("Lesson", self._lesson_box)
        self._about = QComboBox()
        self._about.setAccessibleName("About which landscape")
        self._fill_about()
        form.addRow("About", self._about)
        lay.addLayout(form)

        self._dots = QLabel("")
        self._dots.setTextFormat(Qt.TextFormat.RichText)
        self._dots.setStyleSheet("font-size: 13px;")
        lay.addWidget(self._dots)

        self._title = QLabel("")
        self._title.setWordWrap(True)
        self._title.setStyleSheet(
            "color: #a5d6a7; font-size: 15px; font-weight: bold; padding: 2px 0;")
        lay.addWidget(self._title)

        self._lesson = QLabel("")
        self._lesson.setWordWrap(True)
        self._lesson.setTextFormat(Qt.TextFormat.RichText)
        self._lesson.setStyleSheet("color: #d7e8d0; font-size: 13px; padding: 2px 0;")
        lay.addWidget(self._lesson)

        self._look = QLabel("")
        self._look.setWordWrap(True)
        self._look.setTextFormat(Qt.TextFormat.RichText)
        self._look.setStyleSheet("color: #9ccc9c; font-size: 12px;")
        lay.addWidget(self._look)

        self._readout = QLabel("")
        self._readout.setWordWrap(True)
        self._readout.setTextFormat(Qt.TextFormat.RichText)
        self._readout.setStyleSheet(
            "font-size: 12px; padding: 8px; background: #1a2a1a; "
            "border: 1px solid #2e4a2e; border-radius: 4px;")
        lay.addWidget(self._readout)

        self._sources = QLabel("")
        self._sources.setWordWrap(True)
        self._sources.setStyleSheet("color: #8fa68a; font-size: 12px;")
        lay.addWidget(self._sources)

        nav = QHBoxLayout()
        self._back = QPushButton("← Back")
        self._back.clicked.connect(self._prev)
        self._next = QPushButton("Next →")
        self._next.clicked.connect(self._advance)
        for b in (self._back, self._next):
            b.setStyleSheet(
                "QPushButton { background: #24352b; color: #e8f5e9; border: 1px "
                "solid #3a5a44; border-radius: 4px; padding: 6px 12px; }"
                "QPushButton:disabled { color: #5f7d6a; }")
        nav.addWidget(self._back)
        nav.addStretch()
        nav.addWidget(self._next)
        lay.addLayout(nav)

        lay.addStretch()
        self._lesson_box.currentIndexChanged.connect(self._on_lesson)
        self._about.currentIndexChanged.connect(lambda _i: self._show())
        self._load_lesson()

    def _fill_about(self):
        """The landscapes a lesson can talk about: this window's, each walk,
        then the newest saved designs."""
        self._about.addItem("This design", ("here", ""))
        try:
            from src.reference_ecosystem import REFERENCE_COMMUNITIES
            for key, spec in REFERENCE_COMMUNITIES.items():
                self._about.addItem(f"The walk: {spec['name']}", ("walk", key))
        except Exception:      # noqa: BLE001
            pass
        try:
            from src import saves
            for entry in saves.your_designs()[:SAVED_SHOWN]:
                name = entry.get("name") or entry.get("filename") or "a design"
                self._about.addItem(f"Saved: {name}", ("saved", entry["path"]))
        except Exception:      # noqa: BLE001
            pass

    def set_here_label(self, words: str):
        """Name the first landscape ("The walk you planted in")."""
        self._about.setItemText(0, words)

    # ── flow ────────────────────────────────────────────────────────────────

    def refresh(self):
        """The landscape this window is about changed: read it again, keeping
        the lesson and the page."""
        self._lands.pop(0, None)
        if self._steps:
            self._show()

    def _on_lesson(self, _index: int):
        self._i = 0
        self._load_lesson()

    def _load_lesson(self):
        from src import lessons
        try:
            self._steps = lessons.lesson(self._lesson_box.currentData())["pages"]
        except Exception:      # noqa: BLE001
            self._steps = []
        if not self._steps:
            self._title.setText("Lessons unavailable.")
            for label in (self._lesson, self._look, self._readout,
                          self._sources, self._dots):
                label.setText("")
            self._back.setEnabled(False)
            self._next.setEnabled(False)
            return
        self._i = min(self._i, len(self._steps) - 1)
        self._show()

    def _call(self, provider):
        if provider is None:
            return None
        try:
            return provider()
        except Exception:      # noqa: BLE001
            return None

    def _land(self) -> dict:
        """The chosen landscape, read once per choice."""
        from src import lessons
        index = self._about.currentIndex()
        if index in self._lands:
            return self._lands[index]
        kind, value = self._about.currentData() or ("here", "")
        land: dict = {}
        try:
            if kind == "here":
                land = lessons.landscape(
                    self._call(self._plants_provider) or [],
                    structures=self._call(self._structures_provider) or [])
            elif kind == "walk":
                from src.reference_edit import open_sandbox
                land = lessons.from_project(open_sandbox(value))
            else:
                with open(value, "r", encoding="utf-8") as fh:
                    land = lessons.from_project(json.load(fh))
        except Exception:      # noqa: BLE001 — a readout is a nicety
            land = {}
        self._lands[index] = land
        return land

    def _show(self):
        if not self._steps:
            return
        from src import lessons
        page = self._steps[self._i]
        self._title.setText(f"{self._i + 1}. {page['title']}")
        self._lesson.setText("".join(f"<p>{html.escape(t)}</p>"
                                     for t in page["text"]))
        self._look.setText(f"<b>Look at it:</b> {html.escape(page['look'])}")
        said = lessons.readout(page["readout"], self._land()) \
            if page["readout"] else ""
        self._readout.setVisible(bool(said))
        self._readout.setText(
            f"<b style='color:#a5d6a7'>{html.escape(self._about.currentText())}"
            f"</b><br><span style='color:#dcedc8'>{html.escape(said)}</span>")
        cites = page.get("sources") or ()
        self._sources.setVisible(bool(cites))
        self._sources.setText("From: " + "; ".join(cites))
        self._sources.setToolTip("\n".join(lessons.SOURCES.get(c, c)
                                           for c in cites))
        self._dots.setText(self._dot_row())
        self._back.setEnabled(self._i > 0)
        last = self._i + 1 >= len(self._steps)
        more = self._lesson_box.currentIndex() + 1 < self._lesson_box.count()
        # The last page of a lesson leads to the next; the very last starts
        # again (V3.38: it read Finish and could never be pressed).
        self._next.setText(("Next lesson →" if more else "Start again")
                           if last else "Next →")
        self._next.setEnabled(True)

    def _dot_row(self) -> str:
        return " ".join(
            "<span style='color:#a5d6a7'>●</span>" if j == self._i
            else "<span style='color:#5c8a68'>○</span>"
            for j in range(len(self._steps)))

    def _prev(self):
        if self._i > 0:
            self._i -= 1
            self._show()

    def _advance(self):
        if not self._steps:
            return
        if self._i + 1 < len(self._steps):
            self._i += 1
            self._show()
            return
        nxt = self._lesson_box.currentIndex() + 1
        self._lesson_box.setCurrentIndex(nxt if nxt < self._lesson_box.count()
                                         else 0)

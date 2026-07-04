"""
lesson_track_widget.py — the guided lesson-track stepper UI (F53).

A self-contained QWidget that walks the user through src.lesson_track's four
steps one at a time: the lesson paragraph, a live "your design" readout coloured
by status, and Back / Next navigation with a progress dot row. All content is in
the Qt-free ``lesson_track`` module; this only renders and tracks the step.

Design principle P5 (a guided sequence builds the model) and P7 — see
docs/DESIGN_PHILOSOPHY.md.
"""

from __future__ import annotations

from typing import Callable, Optional

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget,
)

_STATUS = {
    "good":      ("#a5d6a7", "✓ on track"),
    "attention": ("#ffcc80", "› room to grow"),
    "empty":     ("#90a4ae", "· nothing placed yet"),
}


class LessonTrackWidget(QWidget):
    """Guided lesson stepper. ``plants_provider`` / ``structures_provider``
    return the live design so each step's readout is about the user's project."""

    def __init__(self, plants_provider: Optional[Callable] = None,
                 structures_provider: Optional[Callable] = None, parent=None):
        super().__init__(parent)
        self._plants_provider = plants_provider
        self._structures_provider = structures_provider
        self._steps: list[dict] = []
        self._i = 0
        self._build()

    def _build(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(6, 6, 6, 6)
        lay.setSpacing(8)

        intro = QLabel(
            "A short course, taught against your own design: keystone plants → "
            "closing the food web → succession over time → ranges, not "
            "certainties.")
        intro.setWordWrap(True)
        intro.setStyleSheet("color: #90a4ae; font-size: 11px;")
        lay.addWidget(intro)

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
        self._lesson.setStyleSheet("color: #d7e8d0; font-size: 12px; padding: 2px 0 6px 0;")
        lay.addWidget(self._lesson)

        self._readout = QLabel("")
        self._readout.setWordWrap(True)
        self._readout.setTextFormat(Qt.TextFormat.RichText)
        self._readout.setStyleSheet(
            "font-size: 12px; padding: 8px; background: #1a2a1a; "
            "border: 1px solid #2e4a2e; border-radius: 4px;")
        lay.addWidget(self._readout)

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
        self.refresh()

    # ── flow ────────────────────────────────────────────────────────────────

    def refresh(self):
        """Recompute the track from the live design, keeping the current step."""
        plants = self._call(self._plants_provider) or []
        structures = self._call(self._structures_provider) or []
        try:
            from src.lesson_track import build_lesson_track
            self._steps = build_lesson_track(plants, structures)["steps"]
        except Exception:      # noqa: BLE001
            self._steps = []
        if not self._steps:
            self._title.setText("Lesson track unavailable.")
            self._lesson.setText("")
            self._readout.setText("")
            self._dots.setText("")
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

    def _show(self):
        step = self._steps[self._i]
        self._title.setText(f"{self._i + 1}. {step['title']}")
        self._lesson.setText(step["lesson"])
        color, tag = _STATUS.get(step["status"], _STATUS["empty"])
        self._readout.setText(
            f"<b style='color:{color}'>Your design — {tag}</b><br>"
            f"<span style='color:#dcedc8'>{step['your_design']}</span>")
        self._dots.setText(self._dot_row())
        self._back.setEnabled(self._i > 0)
        self._next.setText("Finish" if self._i + 1 >= len(self._steps) else "Next →")
        self._next.setEnabled(self._i + 1 < len(self._steps))

    def _dot_row(self) -> str:
        out = []
        for j, s in enumerate(self._steps):
            color, _ = _STATUS.get(s["status"], _STATUS["empty"])
            if j == self._i:
                out.append(f"<span style='color:{color}'>●</span>")
            else:
                out.append(f"<span style='color:#3a5a44'>○</span>")
        return " ".join(out)

    def _prev(self):
        if self._i > 0:
            self._i -= 1
            self._show()

    def _advance(self):
        if self._i + 1 < len(self._steps):
            self._i += 1
            self._show()

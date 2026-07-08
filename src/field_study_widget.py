"""
field_study_widget.py — the Field Study quiz runner UI (F48).

A small self-contained QWidget that walks the user through a
``src.field_study.generate_quiz`` set one question at a time: prompt (+ a cached
photo for identify questions), four choices, immediate right/wrong feedback with
the explanation, and a running score. All quiz logic is in the Qt-free
``field_study`` module; this only renders and tracks the flow.

Design principle P5 (retrieval practice builds the model) — see
docs/DESIGN_PHILOSOPHY.md.
"""

from __future__ import annotations

import random
from typing import Callable, Optional

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import (
    QLabel, QPushButton, QVBoxLayout, QWidget,
)

_OK = "#a5d6a7"
_BAD = "#ef9a9a"
_OPT_STYLE = (
    "QPushButton { text-align: left; padding: 8px 10px; color: #e8f5e9; "
    "background: #1a2a1a; border: 1px solid #2e4a2e; border-radius: 4px; }"
    "QPushButton:hover:enabled { background: #24352420; border-color: #4a7a4a; }"
    "QPushButton:disabled { color: #c8e6c9; }"
)


class FieldStudyWidget(QWidget):
    """Quiz runner. ``plants_provider`` returns the current placed-plant list
    (so a new quiz is design-aware); pass ``None`` for a general quiz."""

    def __init__(self, plants_provider: Optional[Callable] = None, parent=None):
        super().__init__(parent)
        self._provider = plants_provider
        self._quiz: list[dict] = []
        self._i = 0
        self._score = 0
        self._answered = False
        self._build()

    def _build(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(6, 6, 6, 6)
        lay.setSpacing(8)

        intro = QLabel(
            "Test your recall — identify plants, trace specialist relationships, "
            "and spot the gaps in your own design. Great prep for a nursery or "
            "trail visit.")
        intro.setWordWrap(True)
        intro.setStyleSheet("color: #90a4ae; font-size: 11px;")
        lay.addWidget(intro)

        self._start_btn = QPushButton("Start a quiz")
        self._start_btn.setStyleSheet(
            "QPushButton { background: #2e7d32; color: #e8f5e9; border: 1px solid "
            "#43a047; border-radius: 4px; padding: 6px; font-weight: bold; }"
            "QPushButton:hover { background: #388e3c; }")
        self._start_btn.clicked.connect(self.new_quiz)
        lay.addWidget(self._start_btn)

        self._progress = QLabel("")
        self._progress.setStyleSheet("color: #a5d6a7; font-size: 11px; font-weight: bold;")
        lay.addWidget(self._progress)

        self._photo = QLabel("")
        self._photo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._photo.setVisible(False)
        lay.addWidget(self._photo)

        self._prompt = QLabel("")
        self._prompt.setWordWrap(True)
        self._prompt.setStyleSheet("color: #e8f5e9; font-size: 13px; font-weight: bold;")
        self._prompt.setVisible(False)
        lay.addWidget(self._prompt)

        self._hint = QLabel("")
        self._hint.setWordWrap(True)
        self._hint.setStyleSheet("color: #9ccc9c; font-size: 11px; font-style: italic;")
        self._hint.setVisible(False)
        lay.addWidget(self._hint)

        self._opt_btns: list[QPushButton] = []
        for i in range(4):
            b = QPushButton("")
            b.setStyleSheet(_OPT_STYLE)
            b.clicked.connect(lambda _=False, idx=i: self._answer(idx))
            b.setVisible(False)
            lay.addWidget(b)
            self._opt_btns.append(b)

        self._explain = QLabel("")
        self._explain.setWordWrap(True)
        self._explain.setVisible(False)
        self._explain.setStyleSheet(
            "color: #dcedc8; font-size: 11px; padding: 8px; background: #1a2a1a; "
            "border: 1px solid #2e4a2e; border-radius: 4px;")
        lay.addWidget(self._explain)

        self._next_btn = QPushButton("Next →")
        self._next_btn.setVisible(False)
        self._next_btn.clicked.connect(self._next)
        lay.addWidget(self._next_btn)

        lay.addStretch()

    # ── flow ──────────────────────────────────────────────────────────────

    def new_quiz(self):
        from src.field_study import generate_quiz
        plants = None
        if self._provider is not None:
            try:
                plants = self._provider() or None
            except Exception:      # noqa: BLE001
                plants = None
        try:
            self._quiz = generate_quiz(plants, seed=random.randrange(1 << 30), n=5)
        except Exception:      # noqa: BLE001
            self._quiz = []
        self._i = 0
        self._score = 0
        self._start_btn.setText("Restart quiz")
        if not self._quiz:
            self._progress.setText("Quiz unavailable — the plant database "
                                   "couldn't be read.")
            return
        self._show()

    def _show(self):
        q = self._quiz[self._i]
        self._answered = False
        self._progress.setText(f"Question {self._i + 1} of {len(self._quiz)}   "
                               f"·   score {self._score}")
        self._prompt.setText(q["prompt"]); self._prompt.setVisible(True)
        self._hint.setText(q.get("hint", "")); self._hint.setVisible(bool(q.get("hint")))
        self._set_photo(q.get("image_url", ""))
        for i, b in enumerate(self._opt_btns):
            if i < len(q["options"]):
                b.setText(q["options"][i])
                b.setStyleSheet(_OPT_STYLE)
                b.setEnabled(True)
                b.setVisible(True)
            else:
                b.setVisible(False)
        self._explain.setVisible(False)
        self._next_btn.setVisible(False)

    def _set_photo(self, url: str):
        pm = None
        if url:
            try:
                from src.image_cache import get_cached_image
                path = get_cached_image(url)
                if path:
                    pm = QPixmap(path)
            except Exception:      # noqa: BLE001
                pm = None
        if pm and not pm.isNull():
            self._photo.setPixmap(pm.scaledToHeight(
                150, Qt.TransformationMode.SmoothTransformation))
            self._photo.setVisible(True)
        else:
            self._photo.setVisible(False)

    def _answer(self, idx: int):
        if self._answered:
            return
        self._answered = True
        q = self._quiz[self._i]
        correct = q["answer_index"]
        if idx == correct:
            self._score += 1
        for i, b in enumerate(self._opt_btns[:len(q["options"])]):
            b.setEnabled(False)
            if i == correct:
                b.setStyleSheet(_OPT_STYLE + f"QPushButton {{ color: {_OK}; "
                                "border-color: #43a047; font-weight: bold; }}")
            elif i == idx:
                b.setStyleSheet(_OPT_STYLE + f"QPushButton {{ color: {_BAD}; "
                                "border-color: #b04a4a; }}")
        verdict = "✓ Correct. " if idx == correct else "✗ Not quite. "
        self._explain.setText(verdict + q.get("explanation", ""))
        self._explain.setVisible(True)
        self._progress.setText(f"Question {self._i + 1} of {len(self._quiz)}   "
                               f"·   score {self._score}")
        self._next_btn.setText("See results" if self._i + 1 >= len(self._quiz)
                               else "Next →")
        self._next_btn.setVisible(True)

    def _next(self):
        if self._i + 1 >= len(self._quiz):
            self._finish()
            return
        self._i += 1
        self._show()

    def _finish(self):
        total = len(self._quiz)
        for b in self._opt_btns:
            b.setVisible(False)
        self._photo.setVisible(False)
        self._hint.setVisible(False)
        self._next_btn.setVisible(False)
        pct = round(100 * self._score / total) if total else 0
        self._prompt.setText(f"Quiz complete — {self._score} / {total} ({pct}%)")
        self._prompt.setVisible(True)
        msg = ("Field-ready! You know your natives and their relationships."
               if pct >= 80 else
               "Good start — replay to lock it in, then go check outside."
               if pct >= 50 else
               "Every naturalist starts here. Replay and watch the patterns click.")
        self._explain.setText(msg)
        self._explain.setVisible(True)
        self._progress.setText("")

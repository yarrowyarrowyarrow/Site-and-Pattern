"""
docent_widget.py — the docent / presentation-mode UI (F52).

A self-contained QWidget that walks the src.docent script one beat at a time as
an on-screen guided tour: a large beat title, the generated narration, and
Back / Next navigation with a beat counter — the thing you click through while
showing a neighbour, an HOA board, or a class what the design does. All the
narration is generated in the Qt-free ``docent`` module from the design's own
facts; this only presents it.

Design principle P5 (a narrated sequence teaches a viewer to *see* the ecology)
— see docs/DESIGN_PHILOSOPHY.md.
"""

from __future__ import annotations

from typing import Callable, Optional

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget,
)


class DocentWidget(QWidget):
    """On-screen guided tour. ``plants_provider`` / ``structures_provider``
    return the live design so the narration is about the user's project."""

    def __init__(self, plants_provider: Optional[Callable] = None,
                 structures_provider: Optional[Callable] = None, parent=None):
        super().__init__(parent)
        self._plants_provider = plants_provider
        self._structures_provider = structures_provider
        self._beats: list[dict] = []
        self._i = 0
        self._build()

    def _build(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(6, 6, 6, 6)
        lay.setSpacing(8)

        intro = QLabel(
            "Present your design — a short narrated tour built from its own "
            "numbers, to walk a neighbour, an HOA board, or a class through what "
            "it does.")
        intro.setWordWrap(True)
        intro.setStyleSheet("color: #90a4ae; font-size: 11px;")
        lay.addWidget(intro)

        self._subtitle = QLabel("")
        self._subtitle.setWordWrap(True)
        self._subtitle.setStyleSheet("color: #a5d6a7; font-size: 11px; font-style: italic;")
        lay.addWidget(self._subtitle)

        self._counter = QLabel("")
        self._counter.setStyleSheet("color: #90a4ae; font-size: 11px; font-weight: bold;")
        lay.addWidget(self._counter)

        self._title = QLabel("")
        self._title.setWordWrap(True)
        self._title.setStyleSheet(
            "color: #e8f5e9; font-size: 17px; font-weight: bold; padding: 4px 0;")
        lay.addWidget(self._title)

        self._narration = QLabel("")
        self._narration.setWordWrap(True)
        self._narration.setStyleSheet(
            "color: #dcedc8; font-size: 13px; line-height: 150%; padding: 10px; "
            "background: #16241a; border: 1px solid #2e4a2e; border-radius: 6px;")
        self._narration.setMinimumHeight(140)
        self._narration.setAlignment(Qt.AlignmentFlag.AlignTop)
        lay.addWidget(self._narration)

        nav = QHBoxLayout()
        self._back = QPushButton("← Back")
        self._back.clicked.connect(self._prev)
        self._next = QPushButton("Next →")
        self._next.clicked.connect(self._advance)
        for b in (self._back, self._next):
            b.setStyleSheet(
                "QPushButton { background: #2e7d32; color: #e8f5e9; border: 1px "
                "solid #43a047; border-radius: 4px; padding: 8px 16px; "
                "font-weight: bold; }"
                "QPushButton:disabled { background: #24352b; color: #5f7d6a; "
                "border-color: #3a5a44; }")
        nav.addWidget(self._back)
        nav.addStretch()
        nav.addWidget(self._next)
        lay.addLayout(nav)

        lay.addStretch()
        self.refresh()

    # ── flow ────────────────────────────────────────────────────────────────

    def refresh(self):
        """Rebuild the tour from the live design, restarting at the opening."""
        plants = self._call(self._plants_provider) or []
        structures = self._call(self._structures_provider) or []
        try:
            from src.docent import build_docent_script
            script = build_docent_script(plants, structures)
            self._beats = script["beats"]
            self._subtitle.setText(script["subtitle"])
        except Exception:      # noqa: BLE001
            self._beats = []
            self._subtitle.setText("")
        self._i = 0
        if not self._beats:
            self._title.setText("Presentation unavailable.")
            self._narration.setText("")
            self._counter.setText("")
            self._back.setEnabled(False)
            self._next.setEnabled(False)
            return
        self._show()

    def _call(self, provider):
        if provider is None:
            return None
        try:
            return provider()
        except Exception:      # noqa: BLE001
            return None

    def _show(self):
        beat = self._beats[self._i]
        self._counter.setText(f"Beat {self._i + 1} of {len(self._beats)}")
        self._title.setText(beat["title"])
        self._narration.setText(beat["narration"])
        self._back.setEnabled(self._i > 0)
        last = self._i + 1 >= len(self._beats)
        self._next.setText("Start over" if last else "Next →")
        self._next.setEnabled(True)

    def _prev(self):
        if self._i > 0:
            self._i -= 1
            self._show()

    def _advance(self):
        if self._i + 1 >= len(self._beats):
            self._i = 0          # loop back to the opening
        else:
            self._i += 1
        self._show()

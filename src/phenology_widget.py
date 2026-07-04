"""
phenology_widget.py — the "what's happening now" dashboard UI (F51).

A self-contained QWidget that renders src.phenology.build_phenology for the live
design: a headline for the selected month, a "go check outside" prompt, the
month's blooming / fruiting / waking / going-dormant / task lists, and a compact
twelve-month activity strip you can click to browse. All logic is in the Qt-free
``phenology`` module; this only renders and lets the user pick a month.

Design principle P4 (design the trajectory, not the install day) and P11 (drive
the user outside to verify) — see docs/DESIGN_PHILOSOPHY.md.
"""

from __future__ import annotations

from datetime import datetime
from typing import Callable, Optional

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QComboBox, QHBoxLayout, QLabel, QVBoxLayout, QWidget,
)

_MONTHS = ["January", "February", "March", "April", "May", "June", "July",
           "August", "September", "October", "November", "December"]


class PhenologyWidget(QWidget):
    """Design-aware phenology dashboard. ``plants_provider`` returns the current
    placed-plant list."""

    def __init__(self, plants_provider: Optional[Callable] = None, parent=None):
        super().__init__(parent)
        self._provider = plants_provider
        self._month = datetime.now().month
        self._build()

    def _build(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(6, 6, 6, 6)
        lay.setSpacing(8)

        intro = QLabel(
            "What your design is doing this month — and what to walk outside "
            "and confirm. A landscape is a trajectory, not an install day.")
        intro.setWordWrap(True)
        intro.setStyleSheet("color: #90a4ae; font-size: 11px;")
        lay.addWidget(intro)

        row = QHBoxLayout()
        row.addWidget(self._muted("Month:"))
        self._month_combo = QComboBox()
        self._month_combo.addItems(_MONTHS)
        self._month_combo.setCurrentIndex(self._month - 1)
        self._month_combo.currentIndexChanged.connect(self._on_month)
        row.addWidget(self._month_combo)
        row.addStretch()
        lay.addLayout(row)

        self._headline = QLabel("")
        self._headline.setWordWrap(True)
        self._headline.setStyleSheet(
            "color: #a5d6a7; font-size: 14px; font-weight: bold; padding: 4px 0;")
        lay.addWidget(self._headline)

        self._go_check = QLabel("")
        self._go_check.setWordWrap(True)
        self._go_check.setStyleSheet(
            "color: #ffe0b2; font-size: 12px; padding: 8px; background: #241a12; "
            "border: 1px solid #5a3a1e; border-radius: 4px;")
        self._go_check.setVisible(False)
        lay.addWidget(self._go_check)

        self._detail = QLabel("")
        self._detail.setWordWrap(True)
        self._detail.setTextFormat(Qt.TextFormat.RichText)
        self._detail.setStyleSheet(
            "color: #c8e6c9; font-size: 12px; padding: 8px; background: #1a2a1a; "
            "border: 1px solid #2e4a2e; border-radius: 4px;")
        lay.addWidget(self._detail)

        strip_label = QLabel("The year at a glance")
        strip_label.setStyleSheet(
            "color: #a5d6a7; font-size: 11px; font-weight: bold; padding: 6px 0 2px 0;")
        lay.addWidget(strip_label)

        self._strip = QLabel("")
        self._strip.setTextFormat(Qt.TextFormat.RichText)
        self._strip.setWordWrap(True)
        self._strip.setStyleSheet("font-family: 'Consolas','Courier New',monospace; "
                                  "font-size: 11px; color: #cfe3f0;")
        lay.addWidget(self._strip)

        lay.addStretch()
        self.refresh()

    def _muted(self, text: str) -> QLabel:
        lab = QLabel(text)
        lab.setStyleSheet("color: #90a4ae; font-size: 11px;")
        return lab

    def _on_month(self, idx: int):
        self._month = idx + 1
        self.refresh()

    def refresh(self):
        """Recompute and render for the selected month from the live design."""
        plants = None
        if self._provider is not None:
            try:
                plants = self._provider() or []
            except Exception:      # noqa: BLE001
                plants = []
        try:
            from src.phenology import build_phenology
            data = build_phenology(plants, month=self._month)
        except Exception:      # noqa: BLE001
            self._headline.setText("Phenology unavailable.")
            self._go_check.setVisible(False)
            self._detail.setText("")
            self._strip.setText("")
            return
        now = data["now"]
        self._headline.setText(now["headline"])
        if now["go_check"]:
            self._go_check.setText("🥾 " + now["go_check"])
            self._go_check.setVisible(True)
        else:
            self._go_check.setVisible(False)
        self._detail.setText(self._detail_html(now))
        self._strip.setText(self._strip_html(data["months"], self._month))

    def _detail_html(self, now: dict) -> str:
        rows = [
            ("In bloom", now["blooming"], "#e6a5d0"),
            ("Fruiting", now["fruiting"], "#ef9a9a"),
            ("Breaking dormancy", now["waking"], "#a5d6a7"),
            ("Going dormant", now["dormant"], "#bcaaa4"),
        ]
        parts = []
        for label, names, color in rows:
            if names:
                shown = ", ".join(names[:8]) + ("…" if len(names) > 8 else "")
                parts.append(f"<b style='color:{color}'>{label}:</b> {shown}")
        if now["tasks"]:
            tasks = "; ".join(f"{t['verb']} {t['name']}" for t in now["tasks"][:8])
            parts.append(f"<b style='color:#ffcc80'>To do:</b> {tasks}")
        if not parts:
            return "<i style='color:#90a4ae'>Nothing predicted to change this month.</i>"
        return "<br>".join(parts)

    def _strip_html(self, months: list, current: int) -> str:
        cells = []
        for slot in months:
            n = slot["n_active"]
            block = "·" if n == 0 else ("▪" if n < 3 else "▮")
            color = "#cfe3f0" if slot["month"] == current else "#5f7d8c"
            weight = "bold" if slot["month"] == current else "normal"
            cells.append(f"<span style='color:{color}; font-weight:{weight}'>"
                         f"{slot['abbr']} {block}</span>")
        return " &nbsp; ".join(cells)

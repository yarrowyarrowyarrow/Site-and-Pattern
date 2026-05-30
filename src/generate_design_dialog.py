"""
generate_design_dialog.py — the "Generate Design" dialog.

Lets the user tick design goals (the checkboxes come straight from
:data:`src.design_goals.GOALS`), optionally add a free-text brief, and choose
whether to build offline (no AI). The controller reads the selections back and
runs generation on a background thread. Structure mirrors
:mod:`src.preferences_dialog`.
"""

from __future__ import annotations

from PyQt6.QtWidgets import (
    QCheckBox, QDialog, QDialogButtonBox, QGroupBox, QLabel,
    QPlainTextEdit, QVBoxLayout, QWidget,
)

from src.design_goals import GOALS


class GenerateDesignDialog(QDialog):
    """Collect goals + brief + offline flag for a one-click design."""

    def __init__(self, *, has_boundary: bool, has_pin: bool,
                 preselected: list | None = None,
                 parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("Generate Design")
        self.setMinimumWidth(460)
        preselected = set(preselected or [])

        layout = QVBoxLayout(self)

        intro = QLabel(
            "<b>Generate a starting design</b><br>"
            "Pick the goals that matter to you. A local AI picks fitting "
            "native plants and communities; if no AI is reachable, a "
            "rule-based fallback runs instead. You can fine-tune everything "
            "afterwards by dragging or deleting."
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)

        goals_box = QGroupBox("Design goals")
        goals_layout = QVBoxLayout(goals_box)
        self._checks: dict[str, QCheckBox] = {}
        for g in GOALS:
            label = g.label if g.backed \
                else f"{g.label}  (guidance only — needs data)"
            cb = QCheckBox(label)
            cb.setChecked(g.key in preselected)
            if not g.backed:
                cb.setToolTip(
                    "There's no plant data backing this goal yet, so it's "
                    "passed to the AI as guidance and can't be guaranteed."
                )
            elif g.caveat:
                cb.setToolTip(g.caveat)
            goals_layout.addWidget(cb)
            self._checks[g.key] = cb
        layout.addWidget(goals_box)

        layout.addWidget(QLabel("Extra details (optional):"))
        self._brief = QPlainTextEdit()
        self._brief.setPlaceholderText(
            "e.g. a low-water front yard with shade under the spruce"
        )
        self._brief.setFixedHeight(70)
        layout.addWidget(self._brief)

        self._offline_check = QCheckBox("Build without AI (offline)")
        self._offline_check.setToolTip(
            "Skip the local AI model and build deterministically from your "
            "goals and the seeded plant communities."
        )
        layout.addWidget(self._offline_check)

        if has_boundary:
            note = "Plants will be placed inside your drawn boundary."
        elif has_pin:
            note = ("No boundary drawn — plants will be placed around your "
                    "property pin.")
        else:
            note = "⚠ Draw a boundary or drop a property pin first."
        placement = QLabel(note)
        placement.setWordWrap(True)
        placement.setStyleSheet("color: #90a4ae;")
        layout.addWidget(placement)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel
        )
        ok_button = buttons.button(QDialogButtonBox.StandardButton.Ok)
        ok_button.setText("Generate")
        # Placed geometry needs an anchor — disable OK without one.
        ok_button.setEnabled(has_boundary or has_pin)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def selected_goals(self) -> list:
        return [key for key, cb in self._checks.items() if cb.isChecked()]

    def brief(self) -> str:
        return self._brief.toPlainText().strip()

    def offline(self) -> bool:
        return self._offline_check.isChecked()

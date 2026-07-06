"""
generate_design_dialog.py — the "Generate Design" dialog.

Lets the user tick design goals (the checkboxes come straight from
:data:`src.design_goals.GOALS`), optionally add a free-text brief, and choose
whether to build offline (no AI). The controller reads the selections back and
runs generation on a background thread. Structure mirrors
:mod:`src.preferences_dialog`.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QDialogButtonBox, QGroupBox, QHBoxLayout,
    QLabel, QListWidget, QListWidgetItem, QPlainTextEdit, QSpinBox,
    QVBoxLayout, QWidget,
)

from src.design_goals import GOALS


class GenerateDesignDialog(QDialog):
    """Collect goals + brief + offline flag for a one-click design."""

    def __init__(self, *, has_boundary: bool, has_pin: bool,
                 preselected: list | None = None,
                 fauna_options: list | None = None,
                 parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("Generate Design")
        self.setMinimumWidth(460)
        preselected = set(preselected or [])
        self._fauna_list: QListWidget | None = None  # set below if options given

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

        # ── Optional: design for specific wildlife ──────────────────────────
        # The controller passes fauna_options (so the dialog stays DB-free):
        # a list of {"id", "common_name", "taxon", "icon"} dicts.
        if fauna_options:
            fauna_box = QGroupBox("Design for wildlife (optional)")
            fauna_layout = QVBoxLayout(fauna_box)
            hint = QLabel("Tick species to ensure the design includes plants "
                          "that feed or host them.")
            hint.setWordWrap(True)
            fauna_layout.addWidget(hint)
            self._fauna_list = QListWidget()
            self._fauna_list.setMaximumHeight(140)
            _taxon_label = {"lepidoptera": "butterfly/moth", "bird": "bird",
                            "bee": "bee", "other_insect": "insect",
                            "mammal": "mammal"}
            for f in fauna_options:
                fid = f.get("id")
                if fid is None:
                    continue
                icon = f.get("icon") or ""
                taxon = _taxon_label.get(f.get("taxon", ""), f.get("taxon", ""))
                label = f"{icon} {f.get('common_name', '?')}".strip()
                if taxon:
                    label += f"  ({taxon})"
                item = QListWidgetItem(label)
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                item.setCheckState(Qt.CheckState.Unchecked)
                item.setData(Qt.ItemDataRole.UserRole, int(fid))
                self._fauna_list.addItem(item)
            fauna_layout.addWidget(self._fauna_list)
            layout.addWidget(fauna_box)

        layout.addWidget(QLabel("Extra details (optional):"))
        self._brief = QPlainTextEdit()
        self._brief.setPlaceholderText(
            "e.g. a low-water front yard with shade under the spruce"
        )
        self._brief.setFixedHeight(70)
        layout.addWidget(self._brief)

        budget_row = QHBoxLayout()
        budget_row.addWidget(QLabel("Budget (optional):"))
        self._budget = QSpinBox()
        self._budget.setRange(0, 100000)
        self._budget.setSingleStep(25)
        self._budget.setPrefix("$ ")
        self._budget.setSpecialValueText("no limit")  # shown at value 0
        self._budget.setToolTip(
            "Approximate total plant budget in CAD. The priciest plants are "
            "trimmed to fit, and an estimated cost is shown afterwards. Prices "
            "are estimates (ranges), not quotes."
        )
        budget_row.addWidget(self._budget)
        budget_row.addStretch(1)
        layout.addLayout(budget_row)

        density_row = QHBoxLayout()
        density_row.addWidget(QLabel("Planting density:"))
        self._density_combo = QComboBox()
        # data = the value generate_design expects; label = user-facing.
        for label, val in (("Sparse", "sparse"), ("Balanced", "balanced"),
                           ("Full", "full")):
            self._density_combo.addItem(label, val)
        self._density_combo.setCurrentIndex(1)   # Balanced
        self._density_combo.setToolTip(
            "How much of the boundary to fill: Sparse leaves room, Full packs "
            "the space at healthy spacing."
        )
        density_row.addWidget(self._density_combo)
        density_row.addStretch(1)
        layout.addLayout(density_row)

        self._match_site_check = QCheckBox("Match to site conditions && terrain")
        self._match_site_check.setChecked(True)
        self._match_site_check.setToolTip(
            "Place moisture-loving plants in low/wet ground, drought-tolerant "
            "plants on dry slopes, and shade plants in shade — using the "
            "terrain around your pin/boundary and any existing trees or "
            "buildings you've marked. Needs elevation data (online); falls back "
            "to whole-property matching if unavailable."
        )
        layout.addWidget(self._match_site_check)

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

    def match_site(self) -> bool:
        """Whether to derive wet/dry/shaded micro-zones from the terrain and
        place plants/structures accordingly (V1.48)."""
        return self._match_site_check.isChecked()

    def density(self) -> str:
        """Planting density: 'sparse' | 'balanced' | 'full' (V1.50)."""
        return self._density_combo.currentData() or "balanced"

    def selected_goals(self) -> list:
        return [key for key, cb in self._checks.items() if cb.isChecked()]

    def selected_fauna(self) -> list:
        """Fauna ids the user ticked (empty if none / no picker shown)."""
        if self._fauna_list is None:
            return []
        out = []
        for i in range(self._fauna_list.count()):
            item = self._fauna_list.item(i)
            if item.checkState() == Qt.CheckState.Checked:
                out.append(item.data(Qt.ItemDataRole.UserRole))
        return out

    def brief(self) -> str:
        return self._brief.toPlainText().strip()

    def offline(self) -> bool:
        return self._offline_check.isChecked()

    def budget(self) -> float | None:
        """Total plant budget in CAD, or ``None`` for no limit (value 0)."""
        v = self._budget.value()
        return float(v) if v > 0 else None

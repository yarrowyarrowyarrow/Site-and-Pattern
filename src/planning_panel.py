"""
planning_panel.py — Side-panel tab for planning and analysis features.

Contains inner tabs:
  P2:  Maintenance / labour estimator
  P3a: Wildlife forage calendar (pollinator nectar + bird food by month)
  P3b: Human forage calendar (edible plants by harvest window)
  P6:  Water budget calculator
  V4:  Design notes / journal
"""

from __future__ import annotations

from datetime import datetime

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTabWidget, QTextEdit, QFrame, QScrollArea, QFormLayout,
    QDoubleSpinBox, QSpinBox, QGroupBox, QGridLayout,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
    QTreeWidget, QTreeWidgetItem,
    QSlider,
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtGui import QColor, QFont


# ── Maintenance hours estimates for plant types ──────────────────────────────

_PLANT_MAINTENANCE_HOURS: dict[str, float] = {
    "tree":        3.0,   # pruning, watering establishment
    "shrub":       2.5,   # pruning, mulching
    "herb":        1.5,   # dividing, weeding
    "groundcover": 0.5,   # minimal once established
    "vine":        3.0,   # training, pruning
    "root":        1.0,   # harvest, replant
}

# Month names
_MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
           "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

# Edmonton climate data (approximate)
_EDMONTON_MONTHLY_RAINFALL_MM = [
    15, 10, 15, 25, 45, 75, 90, 65, 40, 20, 15, 12
]
_EDMONTON_ANNUAL_RAINFALL_MM = sum(_EDMONTON_MONTHLY_RAINFALL_MM)

# Water needs per plant type (litres/week during growing season)
_PLANT_WATER_NEEDS_L_WEEK: dict[str, float] = {
    "tree":        40.0,
    "shrub":       15.0,
    "herb":        8.0,
    "groundcover": 3.0,
    "vine":        12.0,
    "root":        6.0,
}

_WATER_MULTIPLIER: dict[str, float] = {
    "low":    0.5,
    "medium": 1.0,
    "high":   1.5,
}


class PlanningPanel(QWidget):
    """Panel housing maintenance estimator, wildlife/human forage calendars, water budget, and notes."""

    # V4 signal: notes changed
    notes_changed = pyqtSignal(str)

    # Timeline signal: year slider changed
    timeline_year_changed = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._placed_plants: list[dict] = []
        self._structures: list[dict] = []
        self._project_notes: str = ""
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(0)

        self._tabs = QTabWidget()
        self._tabs.setStyleSheet("QTabBar::tab { padding: 4px 8px; }")

        self._build_maintenance_tab()
        self._build_wildlife_forage_tab()
        self._build_human_forage_tab()
        self._build_water_tab()
        self._build_timeline_tab()
        self._build_notes_tab()

        layout.addWidget(self._tabs)

    # ═════════════════════════════════════════════════════════════════════════
    #  P2 — Maintenance / Labour Estimator
    # ═════════════════════════════════════════════════════════════════════════

    def _build_maintenance_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(6)

        info = QLabel(
            "Establishment vs. stewardship effort. Year 1\n"
            "front-loads watering-in, weeding, and mulching;\n"
            "established native plantings settle into a much\n"
            "lower maintenance floor by Year 3+."
        )
        info.setWordWrap(True)
        info.setStyleSheet("color: #90a4ae; font-size: 11px;")
        layout.addWidget(info)

        # Available hours input
        hours_row = QHBoxLayout()
        hours_row.addWidget(QLabel("Your available hrs/week:"))
        self._avail_hours = QDoubleSpinBox()
        self._avail_hours.setRange(0, 100)
        self._avail_hours.setValue(10)
        self._avail_hours.setSingleStep(1)
        hours_row.addWidget(self._avail_hours)
        layout.addLayout(hours_row)

        btn = QPushButton("Calculate Establishment Effort")
        btn.setStyleSheet(
            "QPushButton { background: #2e7d32; color: #e8f5e9; border: 1px solid #43a047; "
            "border-radius: 4px; padding: 6px; font-weight: bold; }"
            "QPushButton:hover { background: #388e3c; }"
        )
        btn.clicked.connect(self._calc_maintenance)
        layout.addWidget(btn)

        # Results
        self._maint_results = QLabel("")
        self._maint_results.setWordWrap(True)
        self._maint_results.setStyleSheet(
            "color: #c8e6c9; font-size: 12px; padding: 8px; "
            "background: #1a2a1a; border: 1px solid #2e4a2e; border-radius: 4px; "
            "font-family: 'Consolas', 'Courier New', monospace;"
        )
        self._maint_results.setMinimumHeight(180)
        self._maint_results.setAlignment(Qt.AlignmentFlag.AlignTop)
        layout.addWidget(self._maint_results, 1)

        layout.addStretch()
        self._tabs.addTab(tab, "Effort")

    # Year-1 establishment + Year-3+ stewardship multipliers, applied to the
    # per-plant-type base hours. Native plantings ramp down dramatically once
    # established (deep roots, locally-adapted, weather-resilient); cultivated
    # / non-native plants stay closer to a steady annual cost.
    _Y1_MULT_NATIVE      = 2.0
    _Y1_MULT_CULTIVATED  = 1.5
    _Y3_MULT_NATIVE      = 0.3
    _Y3_MULT_CULTIVATED  = 1.0

    def _calc_maintenance(self):
        if not self._placed_plants and not self._structures:
            self._maint_results.setText("No plants or structures placed yet.")
            return

        # Per-type per-establishment-phase totals
        type_totals: dict[str, dict[str, float]] = {}
        for p in self._placed_plants:
            ptype  = p.get("plant_type", "herb")
            native = bool(p.get("native_to_alberta"))
            base   = _PLANT_MAINTENANCE_HOURS.get(ptype, 1.5)
            y1_mult = self._Y1_MULT_NATIVE if native else self._Y1_MULT_CULTIVATED
            y3_mult = self._Y3_MULT_NATIVE if native else self._Y3_MULT_CULTIVATED
            slot = type_totals.setdefault(
                ptype, {"count": 0, "native": 0, "y1": 0.0, "y3": 0.0}
            )
            slot["count"]   += 1
            slot["native"]  += 1 if native else 0
            slot["y1"]      += base * y1_mult
            slot["y3"]      += base * y3_mult

        plant_y1 = sum(s["y1"] for s in type_totals.values())
        plant_y3 = sum(s["y3"] for s in type_totals.values())

        # Structures: existing maintenance_hours_year is steady-state, applies to
        # both Y1 and Y3+. (Initial install cost varies wildly and is one-time —
        # explicitly excluded from the recurring estimate.)
        total_struct = 0.0
        struct_lines = []
        for s in self._structures:
            hrs = s.get("maintenance_hours_year", 0)
            if hrs:
                total_struct += hrs
                struct_lines.append(f"  {s.get('name', '?')}: {hrs} hrs")

        total_y1 = plant_y1 + total_struct
        total_y3 = plant_y3 + total_struct
        avail    = self._avail_hours.value() * 52

        # Build result text
        lines = [
            "ESTABLISHMENT EFFORT  vs.  STEWARDSHIP",
            "=" * 42,
            f"                       Year 1     Year 3+",
            "",
        ]
        if type_totals:
            lines.append("Plants (by type):")
            for ptype in ["tree", "shrub", "herb", "groundcover", "vine", "root"]:
                if ptype not in type_totals:
                    continue
                slot = type_totals[ptype]
                nat = slot["native"]
                cnt = slot["count"]
                lines.append(
                    f"  {ptype.title()+'s':12s} {cnt:2d}  ({nat}/native)  "
                    f"{slot['y1']:6.0f}   {slot['y3']:6.0f}"
                )
            lines.append(
                f"  {'Subtotal':12s}                "
                f"{plant_y1:6.0f}   {plant_y3:6.0f}"
            )
            lines.append("")

        if struct_lines:
            lines.append(f"Structures (steady-state, applies to both years):")
            lines.extend(struct_lines)
            lines.append(
                f"  {'Subtotal':12s}                "
                f"{total_struct:6.0f}   {total_struct:6.0f}"
            )
            lines.append(
                "  (Installation labour is one-time and not included)"
            )
            lines.append("")

        lines.append("=" * 42)
        lines.append(
            f"  {'TOTAL':12s}                "
            f"{total_y1:6.0f}   {total_y3:6.0f}  hrs/year"
        )
        lines.append(
            f"  {'per week':12s}                "
            f"{total_y1/52:6.1f}   {total_y3/52:6.1f}  hrs/week"
        )
        lines.append(
            f"  Your capacity: {avail:.0f} hrs/year "
            f"({self._avail_hours.value():.0f} hrs/week)"
        )
        lines.append("")

        # Capacity feedback: compare Year 1 (the hard year) to capacity
        if total_y1 <= avail:
            pct = (total_y1 / avail * 100) if avail > 0 else 0
            lines.append(f"✓ Year 1 within capacity ({pct:.0f}% utilized).")
        else:
            over = total_y1 - avail
            lines.append(f"⚠ Year 1 over capacity by {over:.0f} hrs.")
            lines.append(
                f"  Stagger planting across seasons or reduce by "
                f"{over/52:.1f} hrs/week."
            )

        # Highlight the establishment payoff
        if plant_y1 > 0 and plant_y3 < plant_y1:
            drop = (1 - plant_y3 / plant_y1) * 100
            lines.append(
                f"✓ Stewardship effort drops {drop:.0f}% from Y1 → Y3+ "
                "as natives establish."
            )

        self._maint_results.setText("\n".join(lines))

    # ═════════════════════════════════════════════════════════════════════════
    #  P3a — Wildlife Forage Calendar (pollinator nectar + bird food)
    # ═════════════════════════════════════════════════════════════════════════

    _TREE_STYLE = (
        "QTreeWidget { background: #1a2a1a; border: 1px solid #2e4a2e; "
        "color: #c8e6c9; }"
        "QTreeWidget::item { padding: 2px 4px; }"
        "QTreeWidget::item:has-children { color: #a5d6a7; }"
        "QHeaderView::section { background: #1e2e1e; color: #a5d6a7; "
        "border: 1px solid #2e4a2e; padding: 4px; }"
    )

    def _build_wildlife_forage_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(6)

        info = QLabel(
            "When pollinators feed (blooms) and when birds\n"
            "feed (berries/seeds). Expand a month to see the\n"
            "individual plants providing forage. Apr–Oct months\n"
            "with no bloom source are flagged as nectar gaps."
        )
        info.setWordWrap(True)
        info.setStyleSheet("color: #90a4ae; font-size: 11px;")
        layout.addWidget(info)

        btn_row = QHBoxLayout()
        btn = QPushButton("Show Wildlife Forage")
        btn.setStyleSheet(
            "QPushButton { background: #6a1b9a; color: #f3e5f5; border: 1px solid #8e24aa; "
            "border-radius: 4px; padding: 6px; font-weight: bold; }"
            "QPushButton:hover { background: #8e24aa; }"
        )
        btn.clicked.connect(self._calc_wildlife_forage)
        btn_row.addWidget(btn, 1)

        btn_expand = QPushButton("Expand all")
        btn_expand.setStyleSheet(
            "QPushButton { background: #37474f; color: #b0bec5; border: 1px solid #546e7a; "
            "border-radius: 4px; padding: 6px; }"
            "QPushButton:hover { background: #455a64; }"
        )
        btn_expand.clicked.connect(lambda: self._wildlife_tree.expandAll())
        btn_row.addWidget(btn_expand)

        btn_collapse = QPushButton("Collapse all")
        btn_collapse.setStyleSheet(
            "QPushButton { background: #37474f; color: #b0bec5; border: 1px solid #546e7a; "
            "border-radius: 4px; padding: 6px; }"
            "QPushButton:hover { background: #455a64; }"
        )
        btn_collapse.clicked.connect(lambda: self._wildlife_tree.collapseAll())
        btn_row.addWidget(btn_collapse)
        layout.addLayout(btn_row)

        self._wildlife_gap_label = QLabel("")
        self._wildlife_gap_label.setWordWrap(True)
        self._wildlife_gap_label.setStyleSheet("color: #ef9a9a; font-size: 11px; padding: 2px;")
        layout.addWidget(self._wildlife_gap_label)

        self._wildlife_tree = QTreeWidget()
        self._wildlife_tree.setColumnCount(2)
        self._wildlife_tree.setHeaderLabels(["When", "Forage"])
        self._wildlife_tree.setStyleSheet(self._TREE_STYLE)
        self._wildlife_tree.header().setSectionResizeMode(
            0, QHeaderView.ResizeMode.ResizeToContents
        )
        self._wildlife_tree.header().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch
        )
        self._wildlife_tree.setRootIsDecorated(True)
        layout.addWidget(self._wildlife_tree, 1)

        self._tabs.addTab(tab, "Wildlife Forage")

    def _calc_wildlife_forage(self):
        self._wildlife_tree.clear()

        if not self._placed_plants:
            self._wildlife_gap_label.setText("")
            placeholder = QTreeWidgetItem(["—", "No plants placed yet"])
            self._wildlife_tree.addTopLevelItem(placeholder)
            return

        try:
            from src.db.plants import get_connection
        except Exception:
            return

        plant_ids = list({p["plant_id"] for p in self._placed_plants})
        bloom_by_month: dict[int, list[str]] = {m: [] for m in range(1, 13)}
        berry_by_month: dict[int, list[str]] = {m: [] for m in range(1, 13)}

        conn = get_connection()
        try:
            for pid in plant_ids:
                row = conn.execute(
                    "SELECT common_name, bloom_period, fruit_period "
                    "FROM plants WHERE id = ?",
                    (pid,)
                ).fetchone()
                if not row:
                    continue
                name = row["common_name"]
                if row["bloom_period"]:
                    for m in self._parse_month_range(row["bloom_period"]):
                        if name not in bloom_by_month[m]:
                            bloom_by_month[m].append(name)
                if row["fruit_period"]:
                    for m in self._parse_month_range(row["fruit_period"]):
                        if name not in berry_by_month[m]:
                            berry_by_month[m].append(name)
        finally:
            conn.close()

        # Build tree: Month → [Pollinator Blooms, Bird Food] → plant names
        growing = set(range(4, 11))
        gap_months = sorted(
            m for m in growing if not bloom_by_month.get(m)
        )
        bloom_color  = QColor("#ce93d8")
        berry_color  = QColor("#ffcc80")
        muted_color  = QColor("#546e7a")
        gap_color    = QColor("#ef5350")

        for i in range(12):
            month_num = i + 1
            blooms  = sorted(bloom_by_month.get(month_num, []))
            berries = sorted(berry_by_month.get(month_num, []))
            summary_bits = []
            if blooms:
                summary_bits.append(f"{len(blooms)} blooms")
            if berries:
                summary_bits.append(f"{len(berries)} fruits")
            if not summary_bits:
                if month_num in growing:
                    summary = "— nectar gap"
                else:
                    summary = "—"
            else:
                summary = " · ".join(summary_bits)

            month_item = QTreeWidgetItem([_MONTHS[i], summary])
            if not summary_bits and month_num in growing:
                month_item.setForeground(0, gap_color)
                month_item.setForeground(1, gap_color)
            elif not summary_bits:
                month_item.setForeground(0, muted_color)
                month_item.setForeground(1, muted_color)

            # Pollinator blooms sub-tree
            bloom_node = QTreeWidgetItem(
                [f"Pollinator blooms", f"({len(blooms)})"]
            )
            bloom_node.setForeground(0, bloom_color)
            if blooms:
                for n in blooms:
                    bloom_node.addChild(QTreeWidgetItem(["", n]))
            else:
                bloom_node.addChild(QTreeWidgetItem(["", "—"]))
            month_item.addChild(bloom_node)

            # Bird food sub-tree
            berry_node = QTreeWidgetItem(
                [f"Bird food", f"({len(berries)})"]
            )
            berry_node.setForeground(0, berry_color)
            if berries:
                for n in berries:
                    berry_node.addChild(QTreeWidgetItem(["", n]))
            else:
                berry_node.addChild(QTreeWidgetItem(["", "—"]))
            month_item.addChild(berry_node)

            self._wildlife_tree.addTopLevelItem(month_item)

        # Gap label
        if gap_months:
            names = ", ".join(_MONTHS[m - 1] for m in gap_months)
            self._wildlife_gap_label.setText(
                f"⚠ Nectar gaps in growing season: {names}. "
                f"Add a species blooming in these months to support pollinators."
            )
            self._wildlife_gap_label.setStyleSheet(
                "color: #ef9a9a; font-size: 11px; padding: 2px;"
            )
        else:
            self._wildlife_gap_label.setText(
                "✓ Continuous bloom across the growing season (Apr–Oct)."
            )
            self._wildlife_gap_label.setStyleSheet(
                "color: #a5d6a7; font-size: 11px; padding: 2px;"
            )

    # ═════════════════════════════════════════════════════════════════════════
    #  P3b — Human Forage Calendar (edible plants by harvest window)
    # ═════════════════════════════════════════════════════════════════════════

    def _build_human_forage_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(6)

        info = QLabel(
            "What you can harvest from your design, by month.\n"
            "Includes only plants with an edible part recorded\n"
            "in the database — berries, fruits, edible leaves /\n"
            "roots / shoots."
        )
        info.setWordWrap(True)
        info.setStyleSheet("color: #90a4ae; font-size: 11px;")
        layout.addWidget(info)

        btn_row = QHBoxLayout()
        btn = QPushButton("Show Human Forage")
        btn.setStyleSheet(
            "QPushButton { background: #e65100; color: #fff3e0; border: 1px solid #ff6d00; "
            "border-radius: 4px; padding: 6px; font-weight: bold; }"
            "QPushButton:hover { background: #ff6d00; }"
        )
        btn.clicked.connect(self._calc_human_forage)
        btn_row.addWidget(btn, 1)

        btn_expand = QPushButton("Expand all")
        btn_expand.setStyleSheet(
            "QPushButton { background: #37474f; color: #b0bec5; border: 1px solid #546e7a; "
            "border-radius: 4px; padding: 6px; }"
            "QPushButton:hover { background: #455a64; }"
        )
        btn_expand.clicked.connect(lambda: self._human_tree.expandAll())
        btn_row.addWidget(btn_expand)

        btn_collapse = QPushButton("Collapse all")
        btn_collapse.setStyleSheet(
            "QPushButton { background: #37474f; color: #b0bec5; border: 1px solid #546e7a; "
            "border-radius: 4px; padding: 6px; }"
            "QPushButton:hover { background: #455a64; }"
        )
        btn_collapse.clicked.connect(lambda: self._human_tree.collapseAll())
        btn_row.addWidget(btn_collapse)
        layout.addLayout(btn_row)

        self._human_tree = QTreeWidget()
        self._human_tree.setColumnCount(2)
        self._human_tree.setHeaderLabels(["When", "Edible plant — part"])
        self._human_tree.setStyleSheet(self._TREE_STYLE)
        self._human_tree.header().setSectionResizeMode(
            0, QHeaderView.ResizeMode.ResizeToContents
        )
        self._human_tree.header().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch
        )
        layout.addWidget(self._human_tree, 1)

        self._tabs.addTab(tab, "Human Forage")

    def _calc_human_forage(self):
        self._human_tree.clear()

        if not self._placed_plants:
            placeholder = QTreeWidgetItem(["—", "No plants placed yet"])
            self._human_tree.addTopLevelItem(placeholder)
            return

        try:
            from src.db.plants import get_connection
        except Exception:
            return

        plant_ids = list({p["plant_id"] for p in self._placed_plants})

        # entry per plant: (name, edible_parts) by month
        edible_by_month: dict[int, list[tuple[str, str]]] = {m: [] for m in range(1, 13)}

        conn = get_connection()
        try:
            for pid in plant_ids:
                row = conn.execute(
                    "SELECT common_name, edible_parts, fruit_period "
                    "FROM plants WHERE id = ?",
                    (pid,)
                ).fetchone()
                if not row:
                    continue
                edible = (row["edible_parts"] or "").strip()
                if not edible:
                    continue
                name = row["common_name"]

                # Prefer planting_calendar harvest months when present (curated),
                # else parse fruit_period (covers berries, nuts, fruit).
                cal_rows = conn.execute(
                    "SELECT month FROM planting_calendar "
                    "WHERE plant_id = ? AND status = 'harvest'",
                    (pid,)
                ).fetchall()
                months: list[int] = []
                if cal_rows:
                    months = sorted({cr["month"] for cr in cal_rows})
                elif row["fruit_period"]:
                    months = self._parse_month_range(row["fruit_period"])

                for m in months:
                    pair = (name, edible)
                    if pair not in edible_by_month[m]:
                        edible_by_month[m].append(pair)
        finally:
            conn.close()

        muted_color = QColor("#546e7a")
        warm_color  = QColor("#ffcc80")
        total_count = 0
        for i in range(12):
            month_num = i + 1
            items = sorted(edible_by_month.get(month_num, []), key=lambda x: x[0].lower())
            summary = f"{len(items)} plants" if items else "—"
            month_item = QTreeWidgetItem([_MONTHS[i], summary])
            if not items:
                month_item.setForeground(0, muted_color)
                month_item.setForeground(1, muted_color)
            else:
                month_item.setForeground(1, warm_color)
                for name, parts in items:
                    child = QTreeWidgetItem(["", f"{name} — {parts}"])
                    month_item.addChild(child)
                total_count += len(items)
            self._human_tree.addTopLevelItem(month_item)

        if total_count == 0:
            note = QTreeWidgetItem(
                ["", "None of your placed plants have edible parts recorded. "
                     "Try Saskatoon, raspberry, chokecherry, or wild strawberry."]
            )
            note.setForeground(1, muted_color)
            self._human_tree.addTopLevelItem(note)

    @staticmethod
    def _parse_month_range(text: str) -> list[int]:
        """Parse a period string like 'August-September' or 'May' into month numbers."""
        month_map = {
            "jan": 1, "january": 1, "feb": 2, "february": 2,
            "mar": 3, "march": 3, "apr": 4, "april": 4,
            "may": 5, "jun": 6, "june": 6,
            "jul": 7, "july": 7, "aug": 8, "august": 8,
            "sep": 9, "september": 9, "oct": 10, "october": 10,
            "nov": 11, "november": 11, "dec": 12, "december": 12,
        }
        text = text.lower().strip()
        parts = text.replace("–", "-").replace("—", "-").split("-")
        months = []
        for part in parts:
            part = part.strip()
            for key, num in month_map.items():
                if part.startswith(key):
                    months.append(num)
                    break
        if len(months) == 2:
            start, end = months
            if start <= end:
                return list(range(start, end + 1))
            return list(range(start, 13)) + list(range(1, end + 1))
        return months

    # ═════════════════════════════════════════════════════════════════════════
    #  P6 — Water Budget Calculator
    # ═════════════════════════════════════════════════════════════════════════

    def _build_water_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(6)

        info = QLabel(
            "Establishment water (Year 1, heavy hand-watering)\n"
            "vs. stewardship water (Year 3+, mostly natives at\n"
            "0.2× base demand). Compared against growing-season\n"
            "rainfall and catchment capacity."
        )
        info.setWordWrap(True)
        info.setStyleSheet("color: #90a4ae; font-size: 11px;")
        layout.addWidget(info)

        form = QFormLayout()
        form.setContentsMargins(0, 0, 0, 0)

        self._garden_area = QDoubleSpinBox()
        self._garden_area.setRange(1, 50000)
        self._garden_area.setValue(200)
        self._garden_area.setSuffix(" m²")
        form.addRow("Garden area:", self._garden_area)

        self._rain_barrels = QSpinBox()
        self._rain_barrels.setRange(0, 50)
        self._rain_barrels.setValue(2)
        form.addRow("Rain barrels (200L):", self._rain_barrels)

        self._roof_area = QDoubleSpinBox()
        self._roof_area.setRange(0, 1000)
        self._roof_area.setValue(80)
        self._roof_area.setSuffix(" m²")
        form.addRow("Roof catchment:", self._roof_area)

        self._has_swale = QSpinBox()
        self._has_swale.setRange(0, 20)
        self._has_swale.setValue(0)
        self._has_swale.setSuffix(" swales")
        form.addRow("Swales:", self._has_swale)

        self._has_pond = QSpinBox()
        self._has_pond.setRange(0, 10)
        self._has_pond.setValue(0)
        self._has_pond.setSuffix(" ponds")
        form.addRow("Ponds:", self._has_pond)

        layout.addLayout(form)

        btn = QPushButton("Calculate Establishment Water Budget")
        btn.setStyleSheet(
            "QPushButton { background: #0277bd; color: #e1f5fe; border: 1px solid #0288d1; "
            "border-radius: 4px; padding: 6px; font-weight: bold; }"
            "QPushButton:hover { background: #0288d1; }"
        )
        btn.clicked.connect(self._calc_water)
        layout.addWidget(btn)

        self._water_results = QLabel("")
        self._water_results.setWordWrap(True)
        self._water_results.setStyleSheet(
            "color: #c8e6c9; font-size: 12px; padding: 8px; "
            "background: #1a2a1a; border: 1px solid #2e4a2e; border-radius: 4px; "
            "font-family: 'Consolas', 'Courier New', monospace;"
        )
        self._water_results.setMinimumHeight(180)
        self._water_results.setAlignment(Qt.AlignmentFlag.AlignTop)
        layout.addWidget(self._water_results, 1)

        layout.addStretch()
        self._tabs.addTab(tab, "Water")

    # Year-1 establishment / Year-3+ stewardship water multipliers, applied
    # to the per-plant base × needs-level demand. Native plantings drop hard
    # once established (deep roots, locally-adapted); cultivars stay near
    # their full demand.
    _WATER_Y1_MULT             = 1.5   # establishment irrigation for everything
    _WATER_Y3_MULT_NATIVE      = 0.2   # established natives are nearly rain-fed
    _WATER_Y3_MULT_CULTIVATED  = 1.0   # cultivars need ongoing water

    def _calc_water(self):
        if not self._placed_plants:
            self._water_results.setText("No plants placed yet.")
            return

        # Growing season = May-Sep (5 months, ~22 weeks)
        growing_weeks = 22

        # Per-type Y1 / Y3+ demand (seasonal litres). All needed fields
        # (plant_type, water_needs, native_to_alberta) are pre-populated by
        # _sync_planning_panel in app.py, so we don't need DB lookups here.
        type_demands: dict[str, dict[str, float]] = {}
        total_y1_L = 0.0
        total_y3_L = 0.0
        for p in self._placed_plants:
            ptype       = p.get("plant_type", "herb")
            native      = bool(p.get("native_to_alberta"))
            water_needs = p.get("water_needs") or "medium"
            base = _PLANT_WATER_NEEDS_L_WEEK.get(ptype, 8.0)
            mult = _WATER_MULTIPLIER.get(water_needs, 1.0)
            weekly = base * mult
            seasonal_baseline = weekly * growing_weeks

            y1 = seasonal_baseline * self._WATER_Y1_MULT
            y3 = seasonal_baseline * (
                self._WATER_Y3_MULT_NATIVE if native
                else self._WATER_Y3_MULT_CULTIVATED
            )

            slot = type_demands.setdefault(
                ptype, {"count": 0, "native": 0, "y1": 0.0, "y3": 0.0}
            )
            slot["count"]  += 1
            slot["native"] += 1 if native else 0
            slot["y1"]     += y1
            slot["y3"]     += y3
            total_y1_L     += y1
            total_y3_L     += y3

        # Rainfall on garden area (growing season May–Sep)
        garden_m2 = self._garden_area.value()
        growing_rain_mm = sum(_EDMONTON_MONTHLY_RAINFALL_MM[4:9])
        rainfall_L = growing_rain_mm * garden_m2

        # Catchment
        roof_m2 = self._roof_area.value()
        roof_catchment_L = growing_rain_mm * roof_m2 * 0.8
        barrel_capacity_L = self._rain_barrels.value() * 200
        captured_L = min(roof_catchment_L, barrel_capacity_L)
        swale_L = self._has_swale.value() * 2000
        pond_L  = self._has_pond.value()  * 5000
        total_supply = rainfall_L + captured_L + swale_L + pond_L

        # Build result
        lines = [
            "WATER BUDGET — Growing Season May–Sep",
            "=" * 42,
            f"                          Year 1      Year 3+",
            "",
            "DEMAND (plants):",
        ]
        for ptype in ["tree", "shrub", "herb", "groundcover", "vine", "root"]:
            if ptype not in type_demands:
                continue
            slot = type_demands[ptype]
            lines.append(
                f"  {ptype.title()+'s':12s} {slot['count']:2d}  ({slot['native']}/native)  "
                f"{slot['y1']:7.0f} L  {slot['y3']:7.0f} L"
            )
        lines.append(
            f"  {'Total':12s}                "
            f"{total_y1_L:7.0f} L  {total_y3_L:7.0f} L"
        )
        lines.append(
            f"  {'(m³)':12s}                "
            f"{total_y1_L/1000:7.1f}    {total_y3_L/1000:7.1f}"
        )
        lines.append("")

        lines.append("SUPPLY (seasonal):")
        lines.append(f"  Rainfall on garden ({garden_m2:.0f} m²): {rainfall_L:7.0f} L")
        if captured_L > 0:
            lines.append(
                f"  Rain barrels ({self._rain_barrels.value()} × 200L, "
                f"roof-fed): {captured_L:7.0f} L"
            )
        if swale_L > 0:
            lines.append(f"  Swales ({self._has_swale.value()}): {swale_L:7.0f} L")
        if pond_L > 0:
            lines.append(f"  Ponds ({self._has_pond.value()}): {pond_L:7.0f} L")
        lines.append(f"  Total supply:                          {total_supply:7.0f} L")
        lines.append("")

        lines.append("=" * 42)
        bal_y1 = total_supply - total_y1_L
        bal_y3 = total_supply - total_y3_L

        def _balance_line(label: str, bal: float) -> str:
            mark = "✓" if bal >= 0 else "⚠"
            tag  = "Surplus" if bal >= 0 else "Deficit"
            v    = abs(bal)
            return f"  {mark} {label}: {tag} {v:.0f} L ({v/1000:.1f} m³)"

        lines.append(_balance_line("Year 1   ", bal_y1))
        lines.append(_balance_line("Year 3+  ", bal_y3))
        lines.append("")

        # Suggestions for the Year-1 deficit (the hard year)
        if bal_y1 < 0:
            deficit = -bal_y1
            extra_barrels = int(deficit / 200) + 1
            lines.append(f"Year 1 needs ≈ {extra_barrels} more rain barrels,")
            lines.append(f"or {deficit/growing_weeks:.0f} L/week of supplemental")
            lines.append("hand-watering during establishment.")

        # Highlight the native-rooted payoff
        if total_y1_L > 0 and total_y3_L < total_y1_L:
            drop = (1 - total_y3_L / total_y1_L) * 100
            lines.append(
                f"✓ Demand drops {drop:.0f}% from Y1 → Y3+ as natives root in."
            )

        self._water_results.setText("\n".join(lines))

    # ═════════════════════════════════════════════════════════════════════════
    #  V4 — Design Notes / Journal
    # ═════════════════════════════════════════════════════════════════════════

    def _build_notes_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(6)

        info = QLabel(
            "Record observations, soil test results,\n"
            "and design rationale for this project."
        )
        info.setWordWrap(True)
        info.setStyleSheet("color: #90a4ae; font-size: 11px;")
        layout.addWidget(info)

        # Timestamp button
        btn_row = QHBoxLayout()
        btn_ts = QPushButton("+ Add Timestamp")
        btn_ts.setStyleSheet(
            "QPushButton { background: #37474f; color: #b0bec5; border: 1px solid #546e7a; "
            "border-radius: 4px; padding: 4px 8px; }"
            "QPushButton:hover { background: #455a64; }"
        )
        btn_ts.clicked.connect(self._insert_timestamp)
        btn_row.addWidget(btn_ts)

        btn_heading = QPushButton("+ Section")
        btn_heading.setStyleSheet(
            "QPushButton { background: #37474f; color: #b0bec5; border: 1px solid #546e7a; "
            "border-radius: 4px; padding: 4px 8px; }"
            "QPushButton:hover { background: #455a64; }"
        )
        btn_heading.clicked.connect(self._insert_section)
        btn_row.addWidget(btn_heading)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        # Text editor
        self._notes_edit = QTextEdit()
        self._notes_edit.setPlaceholderText(
            "Write your design notes here...\n\n"
            "Suggestions:\n"
            "• Soil test results (pH, nutrients)\n"
            "• Drainage observations\n"
            "• Microclimate notes\n"
            "• Design rationale & goals\n"
            "• Seasonal observations\n"
            "• Plant performance notes"
        )
        self._notes_edit.setStyleSheet(
            "QTextEdit { background: #1a2a1a; color: #c8e6c9; border: 1px solid #2e4a2e; "
            "border-radius: 4px; padding: 6px; font-size: 12px; font-family: 'Consolas', 'Courier New', monospace; }"
        )
        self._notes_edit.textChanged.connect(self._on_notes_changed)
        layout.addWidget(self._notes_edit, 1)

        # Word count
        self._notes_count = QLabel("0 words")
        self._notes_count.setStyleSheet("color: #546e7a; font-size: 10px;")
        layout.addWidget(self._notes_count)

        self._tabs.addTab(tab, "Notes")

    def _insert_timestamp(self):
        ts = datetime.now().strftime("\n--- %Y-%m-%d %H:%M ---\n")
        self._notes_edit.insertPlainText(ts)

    def _insert_section(self):
        self._notes_edit.insertPlainText("\n## \n")
        cursor = self._notes_edit.textCursor()
        cursor.movePosition(cursor.MoveOperation.Left)
        self._notes_edit.setTextCursor(cursor)

    def _on_notes_changed(self):
        text = self._notes_edit.toPlainText()
        word_count = len(text.split()) if text.strip() else 0
        self._notes_count.setText(f"{word_count} words")
        self.notes_changed.emit(text)

    # ── Public API ─────────────────────────────────────────────────────────

    # ═════════════════════════════════════════════════════════════════════════
    #  P1 — Succession / Timeline Planner
    # ═════════════════════════════════════════════════════════════════════════

    def _build_timeline_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(8)

        info = QLabel(
            "Visualise how your landscape changes over time.\n"
            "Drag the slider to see plant sizes at different\n"
            "stages of maturity (species-specific growth curves)."
        )
        info.setWordWrap(True)
        info.setStyleSheet("color: #90a4ae; font-size: 11px;")
        layout.addWidget(info)

        # Year slider
        slider_row = QHBoxLayout()
        slider_row.addWidget(QLabel("Year:"))
        self._year_slider = QSlider(Qt.Orientation.Horizontal)
        self._year_slider.setRange(0, 20)
        self._year_slider.setValue(0)
        self._year_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self._year_slider.setTickInterval(1)
        self._year_slider.setPageStep(5)
        slider_row.addWidget(self._year_slider)
        self._year_label = QLabel("Year 0 (Planting)")
        self._year_label.setMinimumWidth(110)
        self._year_label.setStyleSheet("font-weight: bold; color: #a5d6a7;")
        slider_row.addWidget(self._year_label)
        layout.addLayout(slider_row)

        # Debounce timer for slider
        self._timeline_timer = QTimer()
        self._timeline_timer.setSingleShot(True)
        self._timeline_timer.setInterval(100)
        self._timeline_timer.timeout.connect(self._emit_timeline_year)

        self._year_slider.valueChanged.connect(self._on_year_slider_changed)

        # Summary display
        self._timeline_summary = QLabel("")
        self._timeline_summary.setWordWrap(True)
        self._timeline_summary.setStyleSheet("color: #b0bec5; font-size: 11px; padding: 8px;")
        layout.addWidget(self._timeline_summary)

        # Reset button
        btn_row = QHBoxLayout()
        reset_btn = QPushButton("Reset to Planting (Year 0)")
        reset_btn.clicked.connect(lambda: self._year_slider.setValue(0))
        btn_row.addWidget(reset_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        layout.addStretch()
        self._tabs.addTab(tab, "Timeline")

    def _on_year_slider_changed(self, value: int):
        labels = {0: "Year 0 (Planting)", 1: "Year 1", 3: "Year 3",
                  5: "Year 5", 10: "Year 10", 15: "Year 15", 20: "Year 20"}
        self._year_label.setText(labels.get(value, f"Year {value}"))
        self._timeline_timer.start()  # debounce

    def _emit_timeline_year(self):
        year = self._year_slider.value()
        self.timeline_year_changed.emit(year)

    def update_timeline_summary(self, summary: str):
        """Called from app.py with a text summary of the landscape at this year."""
        self._timeline_summary.setText(summary)

    def set_placed_plants(self, plants: list[dict]):
        """Update the list of placed plants (from app.py)."""
        self._placed_plants = plants

    def set_structures(self, structures: list[dict]):
        """Update the list of placed structures (from app.py)."""
        self._structures = structures

    def set_notes(self, text: str):
        """Load notes from project (called on project open)."""
        self._notes_edit.blockSignals(True)
        self._notes_edit.setPlainText(text)
        self._notes_edit.blockSignals(False)
        self._project_notes = text

    def get_notes(self) -> str:
        """Return current notes text."""
        return self._notes_edit.toPlainText()

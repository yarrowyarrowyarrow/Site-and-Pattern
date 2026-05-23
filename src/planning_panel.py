"""
planning_panel.py — Side-panel tab for planning and analysis features.

Contains inner tabs:
  P2: Maintenance / labour estimator
  P3: Bloom & Berry calendar (pollinator nectar + bird food by month)
  P6: Water budget calculator
  V4: Design notes / journal
"""

from __future__ import annotations

from datetime import datetime

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTabWidget, QTextEdit, QFrame, QScrollArea, QFormLayout,
    QDoubleSpinBox, QSpinBox, QGroupBox, QGridLayout,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
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
    """Panel housing maintenance estimator, bloom & berry calendar, water budget, and notes."""

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
        self._build_bloom_berry_tab()
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
            "Estimated annual maintenance hours for\n"
            "all placed plants and structures."
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

        btn = QPushButton("Calculate Maintenance")
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
            "background: #1a2a1a; border: 1px solid #2e4a2e; border-radius: 4px;"
        )
        self._maint_results.setMinimumHeight(120)
        self._maint_results.setAlignment(Qt.AlignmentFlag.AlignTop)
        layout.addWidget(self._maint_results, 1)

        layout.addStretch()
        self._tabs.addTab(tab, "Maintenance")

    def _calc_maintenance(self):
        from collections import Counter
        if not self._placed_plants and not self._structures:
            self._maint_results.setText("No plants or structures placed yet.")
            return

        # Plant maintenance by type
        type_counts: Counter = Counter()
        type_hours: dict[str, float] = {}
        for p in self._placed_plants:
            ptype = p.get("plant_type", "herb")
            type_counts[ptype] += 1

        total_plant_hours = 0.0
        plant_lines = []
        for ptype in ["tree", "shrub", "herb", "groundcover", "vine", "root"]:
            count = type_counts.get(ptype, 0)
            if count == 0:
                continue
            hrs = _PLANT_MAINTENANCE_HOURS.get(ptype, 1.5) * count
            total_plant_hours += hrs
            plant_lines.append(f"  {ptype.title()}s: {count} × {_PLANT_MAINTENANCE_HOURS.get(ptype, 1.5):.1f} = {hrs:.0f} hrs")

        # Structure maintenance
        total_struct_hours = 0.0
        struct_lines = []
        for s in self._structures:
            hrs = s.get("maintenance_hours_year", 0)
            if hrs:
                total_struct_hours += hrs
                struct_lines.append(f"  {s.get('name', '?')}: {hrs} hrs")

        total = total_plant_hours + total_struct_hours
        avail = self._avail_hours.value() * 52  # yearly

        # Build result text
        lines = ["ANNUAL MAINTENANCE ESTIMATE", "=" * 36, ""]
        if plant_lines:
            lines.append("Plants:")
            lines.extend(plant_lines)
            lines.append(f"  Subtotal: {total_plant_hours:.0f} hrs/year")
            lines.append("")
        if struct_lines:
            lines.append("Structures:")
            lines.extend(struct_lines)
            lines.append(f"  Subtotal: {total_struct_hours:.0f} hrs/year")
            lines.append("")

        lines.append("=" * 36)
        lines.append(f"TOTAL: {total:.0f} hrs/year ({total/52:.1f} hrs/week)")
        lines.append(f"Your capacity: {avail:.0f} hrs/year ({self._avail_hours.value():.0f} hrs/week)")
        lines.append("")

        if total <= avail:
            pct = (total / avail * 100) if avail > 0 else 0
            lines.append(f"✓ Within capacity ({pct:.0f}% utilized)")
        else:
            over = total - avail
            lines.append(f"⚠ Over capacity by {over:.0f} hrs/year!")
            lines.append(f"  Consider reducing by {over/52:.1f} hrs/week")

        self._maint_results.setText("\n".join(lines))

    # ═════════════════════════════════════════════════════════════════════════
    #  P3 — Bloom & Berry Calendar (pollinator nectar + bird food)
    # ═════════════════════════════════════════════════════════════════════════

    def _build_bloom_berry_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(6)

        info = QLabel(
            "When pollinators feed (blooms) and when birds\n"
            "feed (berries/seeds) from your placed plants.\n"
            "Months with no bloom source are flagged red —\n"
            "those are nectar gaps to fill."
        )
        info.setWordWrap(True)
        info.setStyleSheet("color: #90a4ae; font-size: 11px;")
        layout.addWidget(info)

        btn = QPushButton("Show Bloom & Berry Calendar")
        btn.setStyleSheet(
            "QPushButton { background: #6a1b9a; color: #f3e5f5; border: 1px solid #8e24aa; "
            "border-radius: 4px; padding: 6px; font-weight: bold; }"
            "QPushButton:hover { background: #8e24aa; }"
        )
        btn.clicked.connect(self._calc_bloom_berry)
        layout.addWidget(btn)

        # Gap summary
        self._bloom_gap_label = QLabel("")
        self._bloom_gap_label.setWordWrap(True)
        self._bloom_gap_label.setStyleSheet("color: #ef9a9a; font-size: 11px; padding: 2px;")
        layout.addWidget(self._bloom_gap_label)

        # Table: Month | Pollinator Blooms | Bird Food
        self._bloom_table = QTableWidget()
        self._bloom_table.setColumnCount(3)
        self._bloom_table.setHorizontalHeaderLabels(
            ["Month", "Pollinator Blooms", "Bird Food"]
        )
        self._bloom_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.ResizeToContents
        )
        self._bloom_table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch
        )
        self._bloom_table.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeMode.Stretch
        )
        self._bloom_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._bloom_table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self._bloom_table.setStyleSheet(
            "QTableWidget { background: #1a2a1a; border: 1px solid #2e4a2e; color: #c8e6c9; gridline-color: #2e4a2e; }"
            "QHeaderView::section { background: #1e2e1e; color: #a5d6a7; border: 1px solid #2e4a2e; padding: 4px; }"
        )
        self._bloom_table.setRowCount(12)
        for i, m in enumerate(_MONTHS):
            self._bloom_table.setItem(i, 0, QTableWidgetItem(m))
            self._bloom_table.setItem(i, 1, QTableWidgetItem(""))
            self._bloom_table.setItem(i, 2, QTableWidgetItem(""))
        layout.addWidget(self._bloom_table, 1)

        layout.addStretch()
        self._tabs.addTab(tab, "Bloom & Berry")

    def _calc_bloom_berry(self):
        if not self._placed_plants:
            self._bloom_gap_label.setText("")
            for i in range(12):
                self._bloom_table.setItem(i, 1, QTableWidgetItem("No plants placed"))
                self._bloom_table.setItem(i, 2, QTableWidgetItem(""))
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
                    "SELECT common_name, bloom_period, fruit_period FROM plants WHERE id = ?",
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

        # Nectar-gap detection across growing season (Apr–Oct)
        growing = list(range(4, 11))
        gap_months = [m for m in growing if not bloom_by_month.get(m)]
        if gap_months:
            names = ", ".join(_MONTHS[m - 1] for m in gap_months)
            self._bloom_gap_label.setText(
                f"⚠ Nectar gaps in growing season: {names}. "
                f"Add a species blooming in these months to support pollinators."
            )
        else:
            self._bloom_gap_label.setText(
                "✓ Continuous bloom across the growing season (Apr–Oct)."
            )
            self._bloom_gap_label.setStyleSheet(
                "color: #a5d6a7; font-size: 11px; padding: 2px;"
            )

        # Populate table
        for i in range(12):
            month_num = i + 1
            blooms = bloom_by_month.get(month_num, [])
            berries = berry_by_month.get(month_num, [])

            bloom_item = QTableWidgetItem(
                ", ".join(sorted(blooms)) if blooms else "—"
            )
            in_growing = month_num in growing
            if blooms:
                bloom_item.setForeground(QColor("#ce93d8"))
            elif in_growing:
                bloom_item.setForeground(QColor("#ef5350"))
                bloom_item.setText("— (nectar gap)")
            else:
                bloom_item.setForeground(QColor("#546e7a"))
            self._bloom_table.setItem(i, 1, bloom_item)

            berry_item = QTableWidgetItem(
                ", ".join(sorted(berries)) if berries else "—"
            )
            berry_item.setForeground(
                QColor("#ffcc80") if berries else QColor("#546e7a")
            )
            self._bloom_table.setItem(i, 2, berry_item)

        # Re-apply the gap-label style each time so a gap-free design
        # can flip back to a warning if the user later removes plants.
        if gap_months:
            self._bloom_gap_label.setStyleSheet(
                "color: #ef9a9a; font-size: 11px; padding: 2px;"
            )

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
            "Estimate total water needs of placed plants\n"
            "vs. rainfall and catchment capacity."
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

        btn = QPushButton("Calculate Water Budget")
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
            "background: #1a2a1a; border: 1px solid #2e4a2e; border-radius: 4px;"
        )
        self._water_results.setMinimumHeight(120)
        self._water_results.setAlignment(Qt.AlignmentFlag.AlignTop)
        layout.addWidget(self._water_results, 1)

        layout.addStretch()
        self._tabs.addTab(tab, "Water")

    def _calc_water(self):
        if not self._placed_plants:
            self._water_results.setText("No plants placed yet.")
            return

        # Growing season = May-Sep (5 months, ~22 weeks)
        growing_weeks = 22

        # Calculate plant water demand
        total_demand_L = 0.0
        type_demands: dict[str, tuple[int, float]] = {}  # type -> (count, litres)

        try:
            from src.db.plants import get_plant
        except Exception:
            get_plant = lambda pid: None

        for p in self._placed_plants:
            ptype = p.get("plant_type", "herb")
            plant_data = get_plant(p["plant_id"]) if "plant_id" in p else None
            water_needs = (plant_data or {}).get("water_needs", "medium")
            base = _PLANT_WATER_NEEDS_L_WEEK.get(ptype, 8.0)
            mult = _WATER_MULTIPLIER.get(water_needs, 1.0)
            weekly = base * mult
            seasonal = weekly * growing_weeks

            if ptype not in type_demands:
                type_demands[ptype] = (0, 0.0)
            cnt, tot = type_demands[ptype]
            type_demands[ptype] = (cnt + 1, tot + seasonal)
            total_demand_L += seasonal

        # Rainfall on garden area
        garden_m2 = self._garden_area.value()
        # Growing season rainfall (May-Sep)
        growing_rain_mm = sum(_EDMONTON_MONTHLY_RAINFALL_MM[4:9])  # May=4, Sep=8
        rainfall_L = growing_rain_mm * garden_m2  # 1mm on 1m² = 1L

        # Catchment: roof → barrels
        roof_m2 = self._roof_area.value()
        # Assume 80% efficiency
        roof_catchment_L = growing_rain_mm * roof_m2 * 0.8
        barrel_capacity_L = self._rain_barrels.value() * 200

        # Swale infiltration bonus (rough: each swale retains ~2000L/season)
        swale_L = self._has_swale.value() * 2000

        # Pond storage (rough: each pond ~5000L usable)
        pond_L = self._has_pond.value() * 5000

        total_supply = rainfall_L + min(roof_catchment_L, barrel_capacity_L) + swale_L + pond_L

        # Build result
        lines = ["WATER BUDGET (Growing Season: May–Sep)", "=" * 40, ""]

        lines.append("DEMAND:")
        for ptype in ["tree", "shrub", "herb", "groundcover", "vine", "root"]:
            if ptype in type_demands:
                cnt, tot = type_demands[ptype]
                lines.append(f"  {ptype.title()}s ({cnt}): {tot:.0f} L")
        lines.append(f"  Total demand: {total_demand_L:.0f} L ({total_demand_L/1000:.1f} m³)")
        lines.append("")

        lines.append("SUPPLY:")
        lines.append(f"  Rainfall on garden ({garden_m2:.0f} m²): {rainfall_L:.0f} L")
        if barrel_capacity_L > 0:
            lines.append(f"  Rain barrels ({self._rain_barrels.value()} × 200L): {min(roof_catchment_L, barrel_capacity_L):.0f} L")
        if swale_L > 0:
            lines.append(f"  Swales ({self._has_swale.value()}): ~{swale_L:.0f} L")
        if pond_L > 0:
            lines.append(f"  Ponds ({self._has_pond.value()}): ~{pond_L:.0f} L")
        lines.append(f"  Total supply: {total_supply:.0f} L ({total_supply/1000:.1f} m³)")
        lines.append("")

        lines.append("=" * 40)
        balance = total_supply - total_demand_L
        if balance >= 0:
            lines.append(f"✓ Surplus: {balance:.0f} L ({balance/1000:.1f} m³)")
            lines.append("  Water-smart design!")
        else:
            deficit = -balance
            lines.append(f"⚠ Deficit: {deficit:.0f} L ({deficit/1000:.1f} m³)")
            # How many extra barrels needed?
            if deficit > 0:
                extra_barrels = int(deficit / 200) + 1
                lines.append(f"  ≈ {extra_barrels} more rain barrels needed")
                lines.append(f"  or reduce demand by {deficit/growing_weeks:.0f} L/week")

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

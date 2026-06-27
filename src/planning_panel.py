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

from src.plant_conditions import condition_tokens


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

        from src.ui_style import inner_tab_stylesheet
        from src.fill_tab_widget import FillTabWidget
        # Six wide sub-tabs on a narrow panel — opt into shrink-to-fit so they all
        # stay visible (with elide), instead of a scroll chevron hiding "Notes".
        self._tabs = FillTabWidget(allow_shrink=True)
        self._tabs.setDocumentMode(True)
        # Show every sub-tab at once — no scroll chevron hiding "Notes". The
        # FillTabBar spreads them edge-to-edge; labels are kept short enough
        # that all six fit without eliding on a narrow side panel.
        self._tabs.tabBar().setUsesScrollButtons(False)
        self._tabs.tabBar().setExpanding(True)
        self._tabs.tabBar().setElideMode(Qt.TextElideMode.ElideRight)
        self._tabs.setStyleSheet(inner_tab_stylesheet())

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
            "Establishment vs. stewardship effort. Year 1 front-loads "
            "watering-in, weeding, and mulching; established native "
            "plantings settle into a much lower maintenance floor by Year 3+."
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
        self._maint_results.setTextFormat(Qt.TextFormat.RichText)
        self._maint_results.setStyleSheet(
            "color: #c8e6c9; font-size: 12px; padding: 8px; "
            "background: #1a2a1a; border: 1px solid #2e4a2e; border-radius: 4px;"
        )
        self._maint_results.setMinimumHeight(220)
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

        # ── Build the HTML output ───────────────────────────────────────
        rows: list[str] = []
        # Plant rows
        for ptype in ["tree", "shrub", "herb", "groundcover", "vine", "root"]:
            if ptype not in type_totals:
                continue
            slot = type_totals[ptype]
            label = ptype.title() + ("s" if not ptype.endswith("s") else "")
            native_tag = (
                f"<span style='color:#78909c;'> ({slot['native']} native)</span>"
                if slot["native"] else ""
            )
            rows.append(self._row(
                f"{label}",
                f"{slot['count']}{native_tag}",
                f"{slot['y1']:.0f} h",
                f"{slot['y3']:.0f} h",
            ))
        if type_totals:
            rows.append(self._row(
                "Plants subtotal", "",
                f"{plant_y1:.0f} h", f"{plant_y3:.0f} h",
                subtotal=True,
            ))

        if struct_lines:
            for s in self._structures:
                hrs = s.get("maintenance_hours_year", 0)
                if hrs:
                    rows.append(self._row(
                        s.get("name", "?"), "",
                        f"{hrs} h", f"{hrs} h",
                    ))
            rows.append(self._row(
                "Structures subtotal", "",
                f"{total_struct:.0f} h", f"{total_struct:.0f} h",
                subtotal=True,
            ))

        # Final TOTAL row
        rows.append(self._row(
            "TOTAL", "",
            f"{total_y1:.0f} h", f"{total_y3:.0f} h",
            total=True,
        ))
        rows.append(self._row(
            "per week", "",
            f"{total_y1/52:.1f} h", f"{total_y3/52:.1f} h",
            footnote=True,
        ))

        table_html = (
            "<table cellpadding='4' cellspacing='0' "
            "style='border-collapse:collapse; width:100%;'>"
            "<tr style='background:#1e3a1e; color:#a5d6a7;'>"
            "<th align='left'>Type</th>"
            "<th align='right'>Plants</th>"
            "<th align='right'>Year&nbsp;1</th>"
            "<th align='right'>Year&nbsp;3+</th>"
            "</tr>"
            + "".join(rows) + "</table>"
        )

        # Footer note
        cap_text = (
            f"<p style='color:#90a4ae; font-size:11px; margin:6px 0 4px 0;'>"
            f"Your capacity: <b>{self._avail_hours.value():.0f}&nbsp;h/week</b> "
            f"({avail:.0f}&nbsp;h/year). Structures show steady-state recurring "
            f"hours; one-time install labour is not included."
            f"</p>"
        )

        # Callouts
        callouts: list[str] = []
        if total_y1 <= avail:
            pct = (total_y1 / avail * 100) if avail > 0 else 0
            callouts.append(self._callout(
                "good",
                f"Year&nbsp;1 within capacity "
                f"(<b>{pct:.0f}%</b> utilized).",
            ))
        else:
            over = total_y1 - avail
            callouts.append(self._callout(
                "warn",
                f"Year&nbsp;1 over capacity by <b>{over:.0f}&nbsp;h</b>. "
                f"Stagger planting across seasons or reduce by "
                f"{over/52:.1f}&nbsp;h/week.",
            ))
        if plant_y1 > 0 and plant_y3 < plant_y1:
            drop = (1 - plant_y3 / plant_y1) * 100
            callouts.append(self._callout(
                "good",
                f"Stewardship effort drops <b>{drop:.0f}%</b> "
                f"from Y1 → Y3+ as natives establish.",
            ))

        html = (
            "<div style='font-size:12px;'>"
            + table_html
            + cap_text
            + "".join(callouts)
            + "</div>"
        )
        self._maint_results.setText(html)

    # ── HTML helpers shared by Effort + Water result tables ──────────────────
    @staticmethod
    def _row(
        label: str, count: str, y1: str, y3: str,
        *, subtotal: bool = False, total: bool = False,
        footnote: bool = False,
    ) -> str:
        """One row of the Effort / Water tables. Style flags control the
        visual emphasis: subtotal = muted highlight, total = strong highlight,
        footnote = small muted text for the per-week row."""
        if total:
            bg = "background:#1e3a1e;"
            text_style = "color:#e8f5e9; font-weight:bold;"
        elif subtotal:
            bg = "background:#172817;"
            text_style = "color:#a5d6a7; font-weight:bold;"
        elif footnote:
            bg = ""
            text_style = "color:#78909c; font-size:11px; font-style:italic;"
        else:
            bg = ""
            text_style = "color:#c8e6c9;"
        return (
            f"<tr style='{bg}'>"
            f"<td style='{text_style} padding:3px 6px;'>{label}</td>"
            f"<td align='right' style='{text_style} padding:3px 6px;'>{count}</td>"
            f"<td align='right' style='{text_style} padding:3px 6px;'>{y1}</td>"
            f"<td align='right' style='{text_style} padding:3px 6px;'>{y3}</td>"
            f"</tr>"
        )

    @staticmethod
    def _callout(kind: str, html_body: str) -> str:
        """Coloured 'aside' badge — green for good news, amber/red for warnings."""
        styles = {
            "good": ("#1e3a1e", "#66bb6a", "#c8e6c9", "✓"),
            "warn": ("#3a2a1e", "#ffb74d", "#ffe0b2", "⚠"),
            "bad":  ("#3a1e1e", "#e57373", "#ffcdd2", "⚠"),
        }
        bg, border, fg, icon = styles.get(kind, styles["good"])
        return (
            f"<div style='background:{bg}; border-left:3px solid {border}; "
            f"color:{fg}; padding:6px 10px; margin:6px 0; font-size:12px;'>"
            f"<b>{icon}</b>&nbsp; {html_body}"
            f"</div>"
        )

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
            "When pollinators feed (blooms) and when birds feed "
            "(berries/seeds). Expand a month to see the individual plants "
            "providing forage. Apr–Oct months with no bloom source are "
            "flagged as nectar gaps."
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

        self._tabs.addTab(tab, "Wildlife")

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
            "What you can harvest from your design, by month. Includes only "
            "plants with an edible part recorded in the database — berries, "
            "fruits, edible leaves / roots / shoots."
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

        self._tabs.addTab(tab, "Harvest")

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
            "Establishment water (Year 1, heavy hand-watering) vs. "
            "stewardship water (Year 3+, mostly natives at 0.2× base demand). "
            "Compared against growing-season rainfall and catchment capacity."
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
        self._water_results.setTextFormat(Qt.TextFormat.RichText)
        self._water_results.setStyleSheet(
            "color: #c8e6c9; font-size: 12px; padding: 8px; "
            "background: #1a2a1a; border: 1px solid #2e4a2e; border-radius: 4px;"
        )
        self._water_results.setMinimumHeight(240)
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
            # water_needs may list several tolerances (V1.84); the first/primary
            # value drives the irrigation estimate.
            water_tokens = condition_tokens(p.get("water_needs"))
            water_needs = water_tokens[0] if water_tokens else "medium"
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

        bal_y1 = total_supply - total_y1_L
        bal_y3 = total_supply - total_y3_L

        # ── Build the HTML output ───────────────────────────────────────
        # Demand rows (plants by type, then total)
        rows: list[str] = []
        for ptype in ["tree", "shrub", "herb", "groundcover", "vine", "root"]:
            if ptype not in type_demands:
                continue
            slot = type_demands[ptype]
            label = ptype.title() + ("s" if not ptype.endswith("s") else "")
            native_tag = (
                f"<span style='color:#78909c;'> ({slot['native']} native)</span>"
                if slot["native"] else ""
            )
            rows.append(self._row(
                f"{label}",
                f"{slot['count']}{native_tag}",
                f"{slot['y1']:.0f} L",
                f"{slot['y3']:.0f} L",
            ))
        rows.append(self._row(
            "Demand total", "",
            f"{total_y1_L:.0f} L", f"{total_y3_L:.0f} L",
            total=True,
        ))
        rows.append(self._row(
            "(m³)", "",
            f"{total_y1_L/1000:.1f}", f"{total_y3_L/1000:.1f}",
            footnote=True,
        ))

        demand_html = (
            "<table cellpadding='4' cellspacing='0' "
            "style='border-collapse:collapse; width:100%; margin-bottom:8px;'>"
            "<tr style='background:#1e3a1e; color:#a5d6a7;'>"
            "<th align='left'>Type</th>"
            "<th align='right'>Plants</th>"
            "<th align='right'>Year&nbsp;1</th>"
            "<th align='right'>Year&nbsp;3+</th>"
            "</tr>"
            + "".join(rows) + "</table>"
        )

        # Supply rows
        supply_rows: list[str] = []

        def _supply_row(label: str, val_L: float) -> str:
            return (
                "<tr>"
                f"<td style='color:#c8e6c9; padding:3px 6px;'>{label}</td>"
                f"<td align='right' style='color:#c8e6c9; padding:3px 6px;'>"
                f"{val_L:.0f} L</td>"
                "</tr>"
            )

        supply_rows.append(_supply_row(
            f"Rainfall on garden ({garden_m2:.0f} m²)", rainfall_L
        ))
        if captured_L > 0:
            supply_rows.append(_supply_row(
                f"Rain barrels ({self._rain_barrels.value()} × 200 L, roof-fed)",
                captured_L,
            ))
        if swale_L > 0:
            supply_rows.append(_supply_row(
                f"Bioswales ({self._has_swale.value()})", swale_L,
            ))
        if pond_L > 0:
            supply_rows.append(_supply_row(
                f"Ponds ({self._has_pond.value()})", pond_L,
            ))
        supply_rows.append(
            "<tr style='background:#1e3a1e; color:#e8f5e9;'>"
            "<td style='padding:3px 6px; font-weight:bold;'>Total supply</td>"
            f"<td align='right' style='padding:3px 6px; font-weight:bold;'>"
            f"{total_supply:.0f} L</td>"
            "</tr>"
        )

        supply_html = (
            "<table cellpadding='4' cellspacing='0' "
            "style='border-collapse:collapse; width:100%; margin-bottom:8px;'>"
            "<tr style='background:#1e3a1e; color:#a5d6a7;'>"
            "<th align='left' colspan='2'>Supply (seasonal)</th>"
            "</tr>"
            + "".join(supply_rows) + "</table>"
        )

        # Balance callouts (one per phase)
        def _balance_callout(label: str, bal: float) -> str:
            if bal >= 0:
                return self._callout(
                    "good",
                    f"<b>{label}</b>: surplus <b>{bal:.0f} L</b> "
                    f"({bal/1000:.1f} m³).",
                )
            v = -bal
            return self._callout(
                "bad",
                f"<b>{label}</b>: deficit <b>{v:.0f} L</b> "
                f"({v/1000:.1f} m³).",
            )

        callouts: list[str] = []
        callouts.append(_balance_callout("Year 1",   bal_y1))
        callouts.append(_balance_callout("Year 3+",  bal_y3))

        # Year-1 deficit hint (the hard year)
        if bal_y1 < 0:
            deficit = -bal_y1
            extra_barrels = int(deficit / 200) + 1
            callouts.append(self._callout(
                "warn",
                f"Year&nbsp;1 needs ≈ <b>{extra_barrels} more rain "
                f"barrels</b>, or <b>{deficit/growing_weeks:.0f} L/week</b> "
                f"of supplemental hand-watering during establishment.",
            ))

        # Highlight the native-rooted payoff
        if total_y1_L > 0 and total_y3_L < total_y1_L:
            drop = (1 - total_y3_L / total_y1_L) * 100
            callouts.append(self._callout(
                "good",
                f"Demand drops <b>{drop:.0f}%</b> from Y1 → Y3+ as "
                f"natives root in.",
            ))

        html = (
            "<div style='font-size:12px;'>"
            + demand_html
            + supply_html
            + "".join(callouts)
            + "</div>"
        )
        self._water_results.setText(html)

    # ═════════════════════════════════════════════════════════════════════════
    #  V4 — Design Notes / Journal
    # ═════════════════════════════════════════════════════════════════════════

    def _build_notes_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(6)

        info = QLabel(
            "Record observations, soil test results, and design rationale "
            "for this project."
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
            "Watch the planting move through ecological succession. Drag the "
            "slider from planting day toward maturity: pioneer forbs fill in "
            "first and fade as shrubs and climax trees take over. The slider "
            "reaches the slowest species' mature age."
        )
        info.setWordWrap(True)
        info.setStyleSheet("color: #90a4ae; font-size: 11px;")
        layout.addWidget(info)

        # Year slider — range extends to the slowest plant's maturity once a
        # design is loaded (see _update_timeline_horizon); 20 yr until then.
        slider_row = QHBoxLayout()
        slider_row.addWidget(QLabel("Year:"))
        self._year_slider = QSlider(Qt.Orientation.Horizontal)
        self._year_slider.setRange(0, 20)
        self._year_slider.setValue(0)
        self._year_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self._year_slider.setTickInterval(2)
        self._year_slider.setPageStep(5)
        slider_row.addWidget(self._year_slider)
        self._year_label = QLabel("Year 0 (Planting)")
        self._year_label.setMinimumWidth(150)
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
        from src.succession import year_label
        self._year_label.setText(year_label(value))
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
        self._update_timeline_horizon()

    def _update_timeline_horizon(self):
        """Extend the timeline slider to the slowest placed plant's maturity so
        slow trees actually reach full size (N5). Clamped 20–60 yr."""
        slider = getattr(self, "_year_slider", None)
        if slider is None:
            return
        try:
            from src.succession import timeline_max_years
            max_year = timeline_max_years(self._placed_plants)
        except Exception:
            max_year = 20
        cur = slider.value()
        slider.blockSignals(True)
        slider.setMaximum(max_year)
        slider.setTickInterval(max(1, max_year // 10))
        slider.setPageStep(max(1, max_year // 4))
        slider.blockSignals(False)
        if cur > max_year:
            slider.setValue(max_year)

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

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
    QSlider,
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtGui import QColor, QFont



# ── Maintenance hours estimates for plant types ──────────────────────────────
# The numbers now live in the Qt-free src/maintenance_calendar.py (F42), which
# needs them too; imported here under the historical name so the Effort tab and
# the year-by-year calendar can never quote different hours for the same design.

#: A plant type, as the effort table's rows name it.
_TYPE_PLURAL = {
    "tree": "Trees", "shrub": "Shrubs", "wildflower": "Wildflowers",
    "herb": "Herbs", "groundcover": "Groundcovers", "grass": "Grasses",
    "sedge": "Sedges", "rush": "Rushes", "vine": "Vines", "fern": "Ferns",
    "aquatic": "Water plants", "root": "Roots and bulbs",
}

class PlanningPanel(QWidget):
    """The pages that were the Planning tab, until V3.08 moved each where its
    question is asked: Effort and Timeline to Design › Over time, Water to
    Design › Water, Notes to Site › Notes (src/side_panel_layout.py). The
    wildlife and harvest calendars became Design › Food. This class still
    builds and runs the four pages it kept."""

    # V4 signal: notes changed
    notes_changed = pyqtSignal(str)

    # A map note (Draw → 📝 Note) was clicked in the Notes tab — frame it
    # on the map. Payload: lat, lng.
    map_note_focus_requested = pyqtSignal(float, float)

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
        # The Analysis strip's tighter padding: at 4px 10px six labels need
        # more than the panel's width and "Timeline" was cut off (V3.05).
        self._tabs.setStyleSheet(inner_tab_stylesheet()
                                 + "QTabBar::tab { padding: 4px 6px; }")

        self._build_maintenance_tab()
        # Wildlife and Harvest became Design › Food in V3.08 (src/food_page.py),
        # one calendar with people's food kept apart from the animals'.
        self._build_water_tab()
        self._build_timeline_tab()
        self._build_notes_tab()

        layout.addWidget(self._tabs)

        # V3.05: these four pages fill themselves from the design, on screen,
        # where each used to open on a Calculate button over an empty box whose
        # result then went stale with the next edit (src/live_refresh.py).
        # Since V3.08 these pages sit in the Design tab, and
        # src/side_panel_layout.py points ``_live`` at its strip.
        from src.live_refresh import LiveRefresh
        self._live = LiveRefresh(self, self._tabs, {
            self._maint_page: self._calc_maintenance,
            self._water_page: self._calc_water,
        })

    def _poke(self, *_args) -> None:
        """An input of a live page changed: refill whichever is on screen."""
        live = getattr(self, "_live", None)
        if live is not None:
            live.poke()

    # ═════════════════════════════════════════════════════════════════════════
    #  P2 — Maintenance / Labour Estimator
    # ═════════════════════════════════════════════════════════════════════════

    def _build_maintenance_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(6)

        info = QLabel(
            "Year 1 is the most work: watering in, weeding, mulching. By year "
            "3 an established native planting needs far less."
        )
        info.setWordWrap(True)
        info.setStyleSheet("color: #90a4ae; font-size: 12px;")
        layout.addWidget(info)

        # Available hours input
        hours_row = QHBoxLayout()
        hours_label = QLabel("Your available hrs/week:")
        hours_row.addWidget(hours_label)
        self._avail_hours = QDoubleSpinBox()
        hours_label.setBuddy(self._avail_hours)
        self._avail_hours.setRange(0, 100)
        self._avail_hours.setValue(10)
        self._avail_hours.setSingleStep(1)
        self._avail_hours.valueChanged.connect(self._poke)
        hours_row.addWidget(self._avail_hours)
        layout.addLayout(hours_row)

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
        self._maint_page = tab
        self._tabs.addTab(tab, "Effort")

    def _calc_maintenance(self):
        """The care calendar's hours, as the PDF prints them (V3.20, OV-6).
        This page had its own arithmetic: "Year 3+" used the year-10
        multiplier and a single figure, where the calendar gives Years 2–4 a
        band of its own and every band a ±35% range, so the example read 9 h
        here and 18–38 h in the PDF for the same years (OVF-2)."""
        if not self._placed_plants and not self._structures:
            self._maint_results.setText("No plants or structures placed yet.")
            return
        from src.maintenance_calendar import (
            GROWING_WEEKS, build_maintenance_calendar, year1_by_type,
        )
        from src.member_colors import TYPE_COLORS
        cal = build_maintenance_calendar(self._placed_plants, self._structures)
        by_type = year1_by_type(self._placed_plants)

        def hours(lo, hi):
            return f"{lo:.0f}–{hi:.0f} h"

        def weekly(lo, hi):
            return f"{lo / GROWING_WEEKS:.1f}–{hi / GROWING_WEEKS:.1f} h"

        # Year 1, by type: a row for every type in the design (V3.08), in
        # the catalogue's order.
        rows: list[str] = []
        order = ([t for t in TYPE_COLORS if t in by_type]
                 + sorted(t for t in by_type if t not in TYPE_COLORS))
        for ptype in order:
            slot = by_type[ptype]
            label = _TYPE_PLURAL.get(ptype) or str(ptype).replace("_", " ").title()
            native_tag = (
                f"<span style='color:#90a4ae;'> ({slot['native']} native)</span>"
                if slot["native"] else "")
            rows.append(self._row(label, f"{slot['count']}{native_tag}",
                                  hours(slot["low"], slot["high"]), ""))
        for item in cal.structure_detail:
            qty = f" × {item['qty']}" if item["qty"] > 1 else ""
            rows.append(self._row(f"{item['name']}{qty}", "",
                                  f"{item['hours_total']:.0f} h", ""))

        # The calendar's four bands, as ranges, and a week of the season.
        band_rows = [self._row(band.label, "",
                               hours(band.hours_low, band.hours_high),
                               weekly(band.hours_low, band.hours_high),
                               total=band.key == "establish")
                     for band in cal.bands]
        # One table, two header rows, so the columns line up.
        head = "<tr style='background:#1e3a1e; color:#a5d6a7;'>"
        table_html = (
            "<table cellpadding='4' cellspacing='0' "
            "style='border-collapse:collapse; width:100%;'>"
            + head + "<th align='left'>Year 1, by type</th>"
            "<th align='right'>Plants</th><th align='right'>A year</th>"
            "<th></th></tr>" + "".join(rows)
            + head + "<th align='left'>When</th><th></th>"
            "<th align='right'>A year</th>"
            "<th align='right'>A week, May–Sep</th></tr>"
            + "".join(band_rows) + "</table>")

        avail = self._avail_hours.value()
        cap_text = (
            f"<p style='color:#90a4ae; font-size:12px; margin:6px 0 4px 0;'>"
            f"Your time: <b>{avail:.0f}&nbsp;h a week</b> through the season. "
            f"Structures show their yearly upkeep; building them is not "
            f"included. Ranges, because the weather, the weeds and the "
            f"gardener move them more than the plant list does.</p>")

        callouts: list[str] = []
        first = cal.bands[0] if cal.bands else None
        if first is not None and first.hours_high:
            top_week = first.hours_high / GROWING_WEEKS
            if top_week <= avail:
                callouts.append(self._callout(
                    "good", f"Year&nbsp;1 fits your time: at most "
                            f"<b>{top_week:.1f}&nbsp;h</b> a week."))
            else:
                callouts.append(self._callout(
                    "warn", f"Year&nbsp;1 may need up to "
                            f"<b>{top_week:.1f}&nbsp;h</b> a week, more than "
                            f"you have. Plant in stages over two seasons, or "
                            f"start smaller."))
            last = cal.bands[-1]
            if last.hours_high < first.hours_high:
                drop = (1 - last.hours_high / first.hours_high) * 100
                callouts.append(self._callout(
                    "good", f"The work falls by about <b>{drop:.0f}%</b> "
                            f"from Year&nbsp;1 to {last.label} as the "
                            f"natives establish."))

        self._maint_results.setText(
            "<div style='font-size:12px;'>" + table_html
            + cap_text + "".join(callouts) + "</div>")

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
            text_style = "color:#90a4ae; font-size:12px; font-style:italic;"
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
    #  P6 — Water Budget Calculator
    # ═════════════════════════════════════════════════════════════════════════

    def _build_water_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(6)

        info = QLabel(
            "What the plants drink in their first summer, when everything is "
            "watered in, and from year 3, when natives need a fifth as much. "
            "A new bed is lost in a dry week, not a dry season, so the rule "
            "below is weekly."
        )
        info.setWordWrap(True)
        info.setStyleSheet("color: #90a4ae; font-size: 12px;")
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
        for box in (self._garden_area, self._rain_barrels, self._roof_area,
                    self._has_swale, self._has_pond):
            box.valueChanged.connect(self._poke)

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
        self._water_page = tab
        self._tabs.addTab(tab, "Water")

    def _calc_water(self):
        """The design's water, by ``src/water_budget.py`` (V3.20, OV-7): a row
        for every type, the site's own rainfall when fetched, and the weekly
        rule where a seasonal "surplus" was (R4, R38)."""
        if not self._placed_plants:
            self._water_results.setText("No plants placed yet.")
            return
        from src import water_budget as wb

        rows: list[str] = []
        demand = wb.demand_by_type(self._placed_plants)
        for ptype, slot in demand.items():
            label = _TYPE_PLURAL.get(ptype) or str(ptype).replace("_", " ").title()
            native_tag = (
                f"<span style='color:#90a4ae;'> ({slot['native']} native)</span>"
                if slot["native"] else "")
            rows.append(self._row(label, f"{slot['count']}{native_tag}",
                                  f"{slot['y1']:,.0f} L", f"{slot['y3']:,.0f} L"))
        total_y1 = sum(s["y1"] for s in demand.values())
        total_y3 = sum(s["y3"] for s in demand.values())
        rows.append(self._row("A season", "", f"{total_y1:,.0f} L",
                              f"{total_y3:,.0f} L", total=True))
        rows.append(self._row(
            "A week, May–Sep", "", f"{total_y1 / wb.GROWING_WEEKS:,.0f} L",
            f"{total_y3 / wb.GROWING_WEEKS:,.0f} L", footnote=True))
        demand_html = (
            "<table cellpadding='4' cellspacing='0' "
            "style='border-collapse:collapse; width:100%; margin-bottom:8px;'>"
            "<tr style='background:#1e3a1e; color:#a5d6a7;'>"
            "<th align='left'>Type</th><th align='right'>Plants</th>"
            "<th align='right'>First summer</th>"
            "<th align='right'>From year&nbsp;3</th></tr>"
            + "".join(rows) + "</table>")

        # What falls and what is caught: information, not a balance. A season
        # can total more rain than the plants use and still hold the two dry
        # weeks that kill a new planting (R38).
        months, source = wb.rainfall(getattr(self, "_site_config", None))
        season_mm = sum(months[4:9])
        garden_m2 = self._garden_area.value()
        captured = min(season_mm * self._roof_area.value() * 0.8,
                       self._rain_barrels.value() * 200)
        supply = [(f"Rain on the garden ({garden_m2:.0f} m², "
                   f"{season_mm:.0f} mm May–Sep, {source})",
                   season_mm * garden_m2)]
        if captured > 0:
            supply.append((f"Rain barrels ({self._rain_barrels.value()} × "
                           f"200 L, roof-fed)", captured))
        if self._has_swale.value():
            supply.append((f"Swales ({self._has_swale.value()})",
                           self._has_swale.value() * 2000))
        if self._has_pond.value():
            supply.append((f"Ponds ({self._has_pond.value()})",
                           self._has_pond.value() * 5000))
        supply_html = (
            "<table cellpadding='4' cellspacing='0' "
            "style='border-collapse:collapse; width:100%; margin-bottom:8px;'>"
            "<tr style='background:#1e3a1e; color:#a5d6a7;'>"
            "<th align='left' colspan='2'>What falls and what you catch, "
            "May–Sep</th></tr>"
            + "".join(
                f"<tr><td style='color:#c8e6c9; padding:3px 6px;'>{label}</td>"
                f"<td align='right' style='color:#c8e6c9; padding:3px 6px;'>"
                f"{litres:,.0f} L</td></tr>" for label, litres in supply)
            + "</table>")

        self._water_results.setText(
            "<div style='font-size:12px;'>" + demand_html + supply_html
            + self._callout("good", wb.weekly_rule(self._placed_plants))
            + "</div>")

    def set_site_config(self, site_config: dict) -> None:
        """The site's fetched data, for the Water page's rainfall (V3.20)."""
        self._site_config = dict(site_config or {})
        self._poke()

    # ═════════════════════════════════════════════════════════════════════════
    #  V4 — Design Notes / Journal
    # ═════════════════════════════════════════════════════════════════════════

    def _build_notes_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        # Below the site walk on Site › Notes since V3.08, whose page has the
        # margins already.
        layout.setContentsMargins(0, 4, 0, 0)
        layout.setSpacing(6)

        heading = QLabel("Design journal")
        heading.setStyleSheet(
            "color: #a5d6a7; font-size: 12px; font-weight: bold; "
            "padding: 4px 0 2px 0;")
        layout.addWidget(heading)

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
        self._notes_edit.setAccessibleName("Design notes")
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
        heading.setBuddy(self._notes_edit)
        # In a scrolling page, so it holds a height rather than taking one.
        self._notes_edit.setMinimumHeight(180)
        layout.addWidget(self._notes_edit, 1)

        # Word count
        self._notes_count = QLabel("0 words")
        self._notes_count.setStyleSheet("color: #90a4ae; font-size: 12px;")
        layout.addWidget(self._notes_count)

        # ── Notes pinned on the map (Draw → 📝 Note) ─────────────────────────
        # The journal above and the on-map observations are one record: every
        # map note is listed here, and clicking one frames it on the map.
        self._map_notes_header = QLabel("Notes pinned on the map")
        self._map_notes_header.setStyleSheet(
            "color: #a5d6a7; font-size: 12px; font-weight: bold; "
            "padding: 6px 0 2px 0;")
        layout.addWidget(self._map_notes_header)

        self._map_notes_hint = QLabel(
            "None yet — use Draw → 📝 Note to pin an observation to a spot "
            "on the map. It will show up here; click it to jump there.")
        self._map_notes_hint.setWordWrap(True)
        self._map_notes_hint.setStyleSheet("color: #90a4ae; font-size: 12px;")
        layout.addWidget(self._map_notes_hint)

        map_notes_box = QWidget()
        self._map_notes_list = QVBoxLayout(map_notes_box)
        self._map_notes_list.setContentsMargins(0, 0, 0, 0)
        self._map_notes_list.setSpacing(2)
        layout.addWidget(map_notes_box)

        # Site › Notes since V3.08, beside the site walk's questions.
        self._notes_page = tab
        self._tabs.addTab(tab, "Notes")

    def set_map_notes(self, notes: list[dict]):
        """Render the map-note list (``[{id, text, lat, lng}]``) in the Notes
        tab. Called from app.py's ``_sync_planning_panel`` so it tracks note
        add/remove, undo/redo, and project load."""
        lst = getattr(self, "_map_notes_list", None)
        if lst is None:
            return
        while lst.count():
            item = lst.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
        notes = notes or []
        self._map_notes_hint.setVisible(not notes)
        for n in notes:
            btn = QPushButton("📍 " + (n.get("text") or "(no text)"))
            btn.setToolTip("Show this note on the map")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet(
                "QPushButton { text-align: left; padding: 4px 8px; "
                "color: #c8e6c9; background: #1a2a1a; "
                "border: 1px solid #2e4a2e; border-radius: 4px; }"
                "QPushButton:hover { border-color: #4a7a4a; }")
            lat, lng = n.get("lat"), n.get("lng")
            if lat is not None and lng is not None:
                btn.clicked.connect(
                    lambda _=False, a=float(lat), b=float(lng):
                    self.map_note_focus_requested.emit(a, b))
            lst.addWidget(btn)

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
            "Drag from planting day to maturity: the first wildflowers fill "
            "in, then give way as shrubs and trees take over."
        )
        info.setWordWrap(True)
        info.setStyleSheet("color: #90a4ae; font-size: 12px;")
        layout.addWidget(info)

        # Year slider — range extends to the slowest plant's maturity once a
        # design is loaded (see _update_timeline_horizon); 20 yr until then.
        slider_row = QHBoxLayout()
        year_label = QLabel("Year:")
        slider_row.addWidget(year_label)
        self._year_slider = QSlider(Qt.Orientation.Horizontal)
        year_label.setBuddy(self._year_slider)
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
        self._timeline_summary.setStyleSheet("color: #b0bec5; font-size: 12px; padding: 8px;")
        layout.addWidget(self._timeline_summary)

        # Year-by-year conversion schedule (F17, P8/P4): turn the drawn lawn
        # zones + the design's plants into an ordered remove-this / plant-that,
        # when list across the restoration stages above.
        sched_label = QLabel("Phased conversion plan")
        sched_label.setStyleSheet(
            "color: #a5d6a7; font-size: 12px; font-weight: bold; "
            "padding: 6px 0 2px 0;")
        layout.addWidget(sched_label)

        self._conversion_schedule = QTextEdit()
        sched_label.setBuddy(self._conversion_schedule)
        self._conversion_schedule.setReadOnly(True)
        self._conversion_schedule.setStyleSheet(
            "QTextEdit { background: #1a2a1a; color: #c8e6c9; "
            "border: 1px solid #2e4a2e; border-radius: 4px; padding: 6px; "
            "font-size: 12px; }")
        self._conversion_schedule.setMinimumHeight(180)
        self._conversion_schedule.setPlainText(
            "Place plants (and draw lawn-conversion zones) to see a "
            "year-by-year planting & establishment schedule.")
        layout.addWidget(self._conversion_schedule)

        # Reset button
        btn_row = QHBoxLayout()
        reset_btn = QPushButton("Reset to Planting (Year 0)")
        reset_btn.clicked.connect(lambda: self._year_slider.setValue(0))
        btn_row.addWidget(reset_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        layout.addStretch()
        # Design › Over time since V3.08 (src/side_panel_layout.py).
        self._timeline_page = tab
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

    def set_conversion_schedule(self, schedule):
        """Render the year-by-year conversion schedule (F17) in the Timeline tab.
        ``schedule`` is a ``conversion_plan.ConversionSchedule`` (or None to show
        the empty-state hint). Never raises — the schedule is a planning aid."""
        widget = getattr(self, "_conversion_schedule", None)
        if widget is None:
            return
        if schedule is None:
            widget.setPlainText(
                "Place plants (and draw lawn-conversion zones) to see a "
                "year-by-year planting & establishment schedule.")
            return
        try:
            from src.conversion_plan import render_schedule_text
            widget.setPlainText(render_schedule_text(schedule))
        except Exception:  # noqa: BLE001
            pass

    def set_placed_plants(self, plants: list[dict]):
        """Update the list of placed plants (from app.py)."""
        self._placed_plants = plants
        self._update_timeline_horizon()
        self._poke()

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
        """Update the list of placed structures (from app.py). The Water page's
        barrels, ponds and swales start from what is placed (V3.05)."""
        self._structures = structures
        from src.design_inputs import water_features
        found = water_features(structures)
        for box, key in ((self._rain_barrels, "rain_barrels"),
                         (self._has_pond, "ponds"),
                         (self._has_swale, "swales")):
            box.blockSignals(True)
            box.setValue(found[key])
            box.blockSignals(False)
        self._poke()

    def set_site_area(self, area_m2: float) -> None:
        """The Water page's garden area starts from the drawn boundary (V3.05);
        with no boundary it keeps whatever it held."""
        if area_m2 and area_m2 > 0:
            self._garden_area.blockSignals(True)
            self._garden_area.setValue(round(float(area_m2), 1))
            self._garden_area.blockSignals(False)
            self._poke()

    def set_notes(self, text: str):
        """Load notes from project (called on project open)."""
        self._notes_edit.blockSignals(True)
        self._notes_edit.setPlainText(text)
        self._notes_edit.blockSignals(False)
        self._project_notes = text
        # The counter listens to edits, which the block above silences: count
        # what was loaded, or a page of notes reads "0 words" (V3.05 audit).
        self._notes_count.setText(f"{len(text.split()) if text.strip() else 0} words")

    def get_notes(self) -> str:
        """Return current notes text."""
        return self._notes_edit.toPlainText()

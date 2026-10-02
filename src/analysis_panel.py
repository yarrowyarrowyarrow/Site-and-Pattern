"""
analysis_panel.py — the Design tab's widget, and the builder of two Site pages.

Builds:
  A1: Sun Path / Shadow overlay   } Site › Sun & Shade and Site › Wind since
  A4: Wind / Windbreak effect     } V3.07 (src/side_panel_layout.py moves them)
  H1: Habitat Value Score (Tallamy-style composite scoring of native habitat quality)
  F51: This Month (phenology), the first section of Design › Over time (V3.08)
  Food: src/food_page.py, the Bees page and the Wildlife and Harvest
        calendars as one (V3.08)
The Design tab's other pages (Report card, Planted, Over time, Water) are built
by other panels and put in this strip by src/side_panel_layout.py.

(The Sector, Season and Forage tabs were retired in V2.25: sun and wind cover
the sector wedges' job, the season tile filter added no design value, and the
forage calendar is Design › Food's month by month (V3.08). The Field Study / Lessons /
Present teaching tabs moved to the top-level Learn tab — src/learn_panel.py.)
"""

from __future__ import annotations

from datetime import date

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QComboBox, QSpinBox,
    QFormLayout, QSlider, QCheckBox,
    QGroupBox, QFrame, QTextEdit, QDial, QScrollArea,
)
from PyQt6.QtCore import Qt, pyqtSignal, QThreadPool, QRunnable, QTimer
from PyQt6.QtGui import QPixmap


# One colour for the main action, the app's green, and grey for the rest
# (F209, V3.08): Sun & Shade's primary was orange, Wind's teal and blue.
from src.ui_style import BTN_PRIMARY, BTN_SECONDARY


class AnalysisPanel(QWidget):
    """Panel with analysis overlay controls (A1-A4)."""

    # A1: Sun path
    sun_path_requested = pyqtSignal(dict)   # {lat, lng, date_key, show_shadows}
    sun_path_cleared = pyqtSignal()
    sun_time_changed = pyqtSignal(int)      # minutes since midnight (V2.37 scrub)
    sun_redraw_requested = pyqtSignal(dict)  # redraw at the existing anchor

    # A1 (V2.38): the cast-shade half, moved here from SitePanel so one date
    # and one clock drive the arc and the shadows together.
    shade_requested = pyqtSignal(dict)    # {"when": (month, day, hour, minute)}
    shade_cleared   = pyqtSignal()
    shade_opacity   = pyqtSignal(float)   # 0..1, live slider
    shade_zones_requested = pyqtSignal()  # classify planting zones → tag cache
    shade_zones_visible_changed = pyqtSignal(bool)  # show/hide the zone grid

    # A4: Wind/windbreak
    wind_requested = pyqtSignal(dict)       # {direction, speed_label, show_shelter}
    wind_cleared = pyqtSignal()
    wind_data_requested = pyqtSignal()      # fetch real wind data for the site
    # Live wind-shadow overlay (V1.68).
    wind_shadow_toggled = pyqtSignal(bool)
    wind_angle_changed_live = pyqtSignal(int)   # dial scrub (JS-only redraw)
    wind_shadow_commit = pyqtSignal(int)        # dial released (Python merge)
    # Snow-catch microsites (Step 3): winter drifts in the lee of windbreaks.
    snow_catch_toggled = pyqtSignal(bool)

    # "What the bee sees" map overlay (F37 increment 3): the Bees tab asks the
    # 2D map to recolour by the selected bee's floral-resource value.
    bee_map_overlay_requested = pyqtSignal(dict)   # {"bee": name, "styles": {pid: fit}}
    bee_map_overlay_cleared = pyqtSignal()

    # F5: relationship web — a whole graph payload from
    # src.relationship_graph.build_relationship_graph, drawn by
    # html/map/07-network.js.
    relationship_overlay_requested = pyqtSignal(dict)
    relationship_overlay_cleared = pyqtSignal()

    # A cached species photo finished downloading off-thread — re-render the
    # Habitat tab's species gallery (F11 / I1). Emitted from a worker thread;
    # Qt delivers it to the GUI thread.
    galleryImageReady = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._placed_plants: list[dict] = []
        self._structures: list[dict] = []
        self._last_habitat_result = None          # for the species gallery re-render
        self._gallery_warmed: set[str] = set()    # image urls already fetched once
        self._lawn_conversion: dict | None = None  # for the F10 counterfactual
        # Sun & Shade: the site's location, so the clock can span this site's
        # real daylight before anything has been drawn.
        self._sun_lat: float | None = None
        self._sun_lng: float | None = None
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(0)

        from src.ui_style import inner_tab_stylesheet
        from src.fill_tab_widget import FillTabWidget
        # Five sub-tabs on a narrow panel — opt into shrink-to-fit (with
        # elide) so labels compress instead of the strip clipping off-screen
        # (the Planning panel uses the same trick for its six tabs).
        self._tabs = FillTabWidget(allow_shrink=True)
        self._tabs.setDocumentMode(True)
        self._tabs.tabBar().setUsesScrollButtons(False)
        self._tabs.tabBar().setExpanding(True)
        self._tabs.tabBar().setElideMode(Qt.TextElideMode.ElideRight)
        # Tighter horizontal padding than the stock sub-tab style: this strip
        # has to fit the side panel's 300px minimum on macOS too, whose system
        # font renders wider than Windows/Linux at the same 11px (same trick
        # as the top-level strip in app.py).
        self._tabs.setStyleSheet(inner_tab_stylesheet()
                                 + "QTabBar::tab { padding: 4px 6px; }")

        self._build_sun_tab()
        # Manual contour drawing moved to Site → Slope analysis (it's
        # site-scale terrain analysis and lives next to the auto-contour
        # generator there).
        self._build_wind_tab()
        self._build_habitat_tab()
        self._build_phenology_tab()
        # Field Study / Lessons / Present moved to the top-level Learn tab
        # (src/learn_panel.py, V2.25) — teaching tools, not analysis.
        self._build_food_tab()

        layout.addWidget(self._tabs)
        # V3.05: the score fills itself when its page is on screen and the
        # design changes; it had a Calculate button over an empty box, and a
        # result that went stale with the next edit (src/live_refresh.py).
        from src.live_refresh import LiveRefresh
        self._live = LiveRefresh(self, self._tabs,
                                 {self._habitat_page: self._calc_habitat_score,
                                  self._food: self._food.refresh})

    # ═════════════════════════════════════════════════════════════════════════
    #  A1 — Sun Path / Shadow
    # ═════════════════════════════════════════════════════════════════════════

    def _build_sun_tab(self):
        """Sun & Shade — one date, one clock, both answers (V2.38).

        This was two tabs. Analysis → Sun Path drew the arc from its own date
        combo, after a button press and a map click. Site → Features & Shade
        cast the shadows from a *different* date combo and a different clock,
        one tab across. They were computing the same instant from the same
        ``solar`` module and could not be made to agree without setting both.
        Now the date and the time are asked once, and the answer is the sun
        where it is and the shadow it throws.

        The existing-features *import* stayed on the Site tab: entering what is
        already on the ground is data capture, not analysis, and folding the
        two together is what made "Features & Shade" two things under one
        label.
        """
        page = QScrollArea()
        page.setWidgetResizable(True)
        page.setFrameShape(QFrame.Shape.NoFrame)
        tab = QWidget()
        page.setWidget(tab)
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(8)

        info = QLabel(
            "Pick a date and drag the clock: the sun moves, and the shadows "
            "with it."
        )
        info.setWordWrap(True)
        info.setStyleSheet("color: #90a4ae; font-size: 12px;")
        layout.addWidget(info)

        self._build_sun_when_group(layout)
        self._build_sun_arc_group(layout)
        self._build_shade_group(layout)
        self._build_shade_zones_group(layout)
        # Wired last, in one place: every one of these handlers reads controls
        # from more than one group, so connecting inside a builder would make
        # the tab's construction order load-bearing.
        self._sun_date.currentIndexChanged.connect(self._on_sun_date_changed)
        self._sun_time_slider.valueChanged.connect(self._on_sun_time_scrubbed)
        self._sun_shadows.toggled.connect(self._on_sun_option_changed)
        self._sun_shadow_length.toggled.connect(self._on_sun_option_changed)
        # Bring the clock and the leaf-off note in line with the opening date
        # without emitting a redraw for an arc nobody has drawn yet.
        self._apply_date_to_controls()

        # Results area
        self._sun_info = QLabel("")
        self._sun_info.setWordWrap(True)
        self._sun_info.setStyleSheet("color: #ffcc80; font-size: 12px; padding: 4px;")
        layout.addWidget(self._sun_info)

        layout.addStretch()
        # Hosted by the Site tab since V3.07 (src/side_panel_layout.py); built
        # and run here, so nothing about how it works moved with it.
        self._sun_page = page
        self._tabs.addTab(page, "Sun && Shade")

    def _build_sun_when_group(self, layout):
        """The single date + single clock that drive both the arc and the shade."""
        from src import sun_shade

        box = QGroupBox("When")
        box.setStyleSheet(self._GROUP_STYLE)
        v = QVBoxLayout(box)
        v.setContentsMargins(6, 6, 6, 6)
        v.setSpacing(4)

        form = QFormLayout()
        form.setContentsMargins(0, 0, 0, 0)

        self._sun_date = QComboBox()
        for label, data in sun_shade.date_choices():
            self._sun_date.addItem(label, data)
        # Open in the season the user is standing in — the Site panel's shade
        # combo already did this and the sun path did not, so the two disagreed
        # from the first frame.
        self._sun_date.setCurrentIndex(sun_shade.nearest_key_date_index())
        form.addRow("Date:", self._sun_date)

        # Time of day. This control existed before V2.37 as a three-position
        # morning/noon/evening slider that was connected to nothing and read by
        # nothing — a draggable control that did not do anything, which is worse
        # than not having one. It is now a real scrub in minutes, clamped to the
        # selected date's actual daylight, and it moves the sun, its shadow ray
        # and the cast shade together.
        self._sun_time_slider = QSlider(Qt.Orientation.Horizontal)
        self._sun_time_slider.setRange(*sun_shade.DEFAULT_WINDOW)
        self._sun_time_slider.setSingleStep(15)
        self._sun_time_slider.setPageStep(60)
        self._sun_time_slider.setValue(15 * 60)   # mid-afternoon: long, clearly
                                                  # directional shadows to start
        self._sun_time_slider.setToolTip(
            "Drag to move the sun along its arc and swing the shadows with it.\n"
            "Range is that date's sunrise to sunset.\n\n"
            "This is SUN time, not clock time: 12:00 is when the sun is "
            "highest.\nIn Alberta that lands about 1½ hours before noon on a "
            "summer clock\n(daylight saving plus the distance to the "
            "time-zone meridian).")
        self._sun_time_label = QLabel("Sun time  15:00")
        # addRow(label, field) does not link them (only addRow("text", field)
        # does), and the label carries the time too: name the slider itself.
        self._sun_time_slider.setAccessibleName("Sun time")
        form.addRow(self._sun_time_label, self._sun_time_slider)
        v.addLayout(form)

        # Two update rates, deliberately. The sun marker is JS-only over a
        # payload the map already holds, so it follows the drag at full rate.
        # The shade recompute re-runs an elevation grid plus a full polygon
        # pass on a worker thread, so it waits for the drag to settle.
        self._shade_scrub = QTimer(self)
        self._shade_scrub.setSingleShot(True)
        self._shade_scrub.setInterval(180)
        self._shade_scrub.timeout.connect(self._emit_shade_for_scrub)

        # Leaf-off honesty note (V2.13): shown for leaf-off dates so the
        # lighter shadows under tagged deciduous trees aren't read as a bug.
        self._shade_leafoff_note = QLabel(
            "🍂 Deciduous trees are shown leaf-off for this date — bare "
            "branches cast ~30% shade. Trees marked without a type still "
            "cast full shade.")
        self._shade_leafoff_note.setWordWrap(True)
        self._shade_leafoff_note.setStyleSheet("color: #90a4ae; font-size: 12px;")
        self._shade_leafoff_note.setVisible(False)
        v.addWidget(self._shade_leafoff_note)

        layout.addWidget(box)

    def _build_sun_arc_group(self, layout):
        """The sun's arc across the sky, drawn on the map."""
        box = QGroupBox("The sun's arc")
        box.setStyleSheet(self._GROUP_STYLE)
        v = QVBoxLayout(box)
        v.setContentsMargins(6, 6, 6, 6)
        v.setSpacing(4)

        form = QFormLayout()
        form.setContentsMargins(0, 0, 0, 0)

        self._sun_shadows = QCheckBox("Show shadow direction arrows")
        self._sun_shadows.setChecked(True)
        form.addRow(self._sun_shadows)

        self._sun_shadow_length = QCheckBox("Show shadow length indicators")
        self._sun_shadow_length.setChecked(False)
        form.addRow(self._sun_shadow_length)

        arc_row = QHBoxLayout()
        arc_label = QLabel("Arc radius:")
        arc_row.addWidget(arc_label)
        self._sun_arc_radius = QSpinBox()
        arc_label.setBuddy(self._sun_arc_radius)
        self._sun_arc_radius.setRange(20, 500)
        self._sun_arc_radius.setValue(80)
        self._sun_arc_radius.setSuffix(" m")
        self._sun_arc_radius.setToolTip(
            "Minimum arc radius in metres. The arc auto-sizes to ~22% of the\n"
            "viewport so it's always legible — this value sets a lower bound."
        )
        arc_row.addWidget(self._sun_arc_radius)
        arc_row.addStretch()
        form.addRow(arc_row)
        v.addLayout(form)

        btn_row = QHBoxLayout()
        # V2.38: this used to read "Place Sun Path…" and mean it — the arc
        # would not draw until you had also found and clicked the right bit of
        # map. The centre is now the boundary centroid (or the site pin) unless
        # you say otherwise, so the common case costs one click instead of two
        # plus aim.
        btn_show = QPushButton("Show sun path")
        btn_show.setToolTip(
            "Draw the sun's arc centred on your property.\n"
            "Use 'Move…' to centre it somewhere specific instead.")
        btn_show.setStyleSheet(BTN_PRIMARY)
        btn_show.clicked.connect(self._on_show_sun_path)
        btn_row.addWidget(btn_show)

        btn_move = QPushButton("Move…")
        btn_move.setToolTip(
            "Click this, then click the map to centre the arc on a "
            "particular bed or tree.")
        btn_move.setStyleSheet(BTN_SECONDARY)
        btn_move.clicked.connect(self._on_move_sun_path)
        btn_row.addWidget(btn_move)

        btn_clear = QPushButton("Clear")
        btn_clear.setStyleSheet(BTN_SECONDARY)
        btn_clear.clicked.connect(self.sun_path_cleared.emit)
        btn_row.addWidget(btn_clear)
        v.addLayout(btn_row)

        layout.addWidget(box)

    def _build_shade_group(self, layout):
        """The shade the site's trees and buildings actually cast, at that hour."""
        box = QGroupBox("Cast shade")
        box.setStyleSheet(self._GROUP_STYLE)
        box.setToolTip("Cast shade from existing trees/buildings and the "
                       "design's own canopy, at the date and time above.")
        v = QVBoxLayout(box)
        v.setContentsMargins(6, 6, 6, 6)
        v.setSpacing(4)

        # Caster inventory (V2.13): tells the user whether the shade below
        # will be real BEFORE they click — refreshed by update_caster_summary.
        self._caster_summary = QLabel("")
        self._caster_summary.setWordWrap(True)
        self._caster_summary.setStyleSheet("color: #90a4ae; font-size: 12px;")
        self.update_caster_summary(None)
        v.addWidget(self._caster_summary)

        opa_row = QHBoxLayout()
        opa_row.addWidget(QLabel("Opacity:"))
        self._shade_opacity = QSlider(Qt.Orientation.Horizontal)
        self._shade_opacity.setAccessibleName("Shade opacity")
        self._shade_opacity.setRange(0, 100)
        self._shade_opacity.setValue(50)
        self._shade_opacity.valueChanged.connect(
            lambda val: self.shade_opacity.emit(val / 100.0))
        opa_row.addWidget(self._shade_opacity)
        v.addLayout(opa_row)

        btn_row = QHBoxLayout()
        btn_show = QPushButton("Show shade")
        btn_show.setStyleSheet(
            "QPushButton { background: #37474f; color: #eceff1; "
            "border: 1px solid #607d8b; border-radius: 4px; padding: 6px; "
            "font-weight: bold; } QPushButton:hover { background: #455a64; }")
        btn_show.clicked.connect(self._on_show_shade)
        btn_row.addWidget(btn_show)
        btn_clear = QPushButton("Clear")
        btn_clear.setStyleSheet(BTN_SECONDARY)
        btn_clear.clicked.connect(self.shade_cleared.emit)
        btn_row.addWidget(btn_clear)
        v.addLayout(btn_row)

        layout.addWidget(box)

    def _build_shade_zones_group(self, layout):
        """Classify every planting spot full sun / partial / full shade."""
        box = QGroupBox("Planting zones")
        box.setStyleSheet(self._GROUP_STYLE)
        v = QVBoxLayout(box)
        v.setContentsMargins(6, 6, 6, 6)
        v.setSpacing(4)

        # Classify each planting cell from the season-average grid and cache
        # the tags (src/db/shade_zones.py) so plant matching can read them
        # without recomputing.
        btn_classify = QPushButton("Classify planting zones")
        btn_classify.setStyleSheet(BTN_SECONDARY)
        btn_classify.setToolTip(
            "Tag every spot full sun / partial shade / full shade from the "
            "season-average shade, and cache it for plant matching.")
        btn_classify.clicked.connect(self.shade_zones_requested.emit)
        v.addWidget(btn_classify)

        zrow = QHBoxLayout()
        self._zones_show_cb = QCheckBox("Show on map")
        self._zones_show_cb.setChecked(True)
        self._zones_show_cb.setToolTip(
            "Show/hide the classified planting zones on the map.")
        self._zones_show_cb.toggled.connect(self.shade_zones_visible_changed.emit)
        zrow.addWidget(self._zones_show_cb)
        legend = QLabel(
            '<span style="color:#ffd54f">■</span> Full sun&nbsp;&nbsp;'
            '<span style="color:#fb8c00">■</span> Partial&nbsp;&nbsp;'
            '<span style="color:#5c6bc0">■</span> Full shade')
        legend.setStyleSheet("font-size: 12px;")
        zrow.addWidget(legend)
        zrow.addStretch()
        v.addLayout(zrow)

        self._shade_zone_status = QLabel("")
        self._shade_zone_status.setWordWrap(True)
        self._shade_zone_status.setStyleSheet("color: #a5d6a7; font-size: 12px;")
        v.addWidget(self._shade_zone_status)

        layout.addWidget(box)

    # ── Reading the two controls ─────────────────────────────────────────────

    def _sun_config(self) -> dict:
        """The current Sun Path settings. One builder, so "place it" and
        "redraw it where it already is" cannot drift apart."""
        from src import sun_shade
        d = sun_shade.resolve_date(self._sun_date.currentData())
        return {
            "date": d.isoformat(),
            "date_label": self._sun_date.currentText(),
            "show_shadows": self._sun_shadows.isChecked(),
            "show_shadow_length": self._sun_shadow_length.isChecked(),
            "arc_radius": self._sun_arc_radius.value(),
        }

    def _shade_when(self) -> tuple[int, int, int, int]:
        """``(month, day, hour, minute)`` — the same instant the arc is drawn
        for, read from the same two controls."""
        from src import sun_shade
        d = sun_shade.resolve_date(self._sun_date.currentData())
        mins = self._sun_time_slider.value()
        return (d.month, d.day, mins // 60, mins % 60)

    def _on_show_sun_path(self):
        self.sun_path_requested.emit(self._sun_config())
        # Hand the keyboard to the clock so ←/→ sweep the day immediately.
        self._sun_time_slider.setFocus(Qt.FocusReason.OtherFocusReason)

    def _on_move_sun_path(self):
        """Re-centre the arc by clicking the map (the old default)."""
        cfg = dict(self._sun_config())
        cfg["pick_anchor"] = True
        self.sun_path_requested.emit(cfg)

    def _on_show_shade(self):
        self.shade_requested.emit({"when": self._shade_when()})
        self._sun_time_slider.setFocus(Qt.FocusReason.OtherFocusReason)

    def set_sun_info(self, text: str):
        self._sun_info.setText(text)

    # ── Time-of-day scrub (V2.37; drives the shade too since V2.38) ──────────

    def set_sun_window(self, sunrise_hour: float, sunset_hour: float):
        """Clamp the time slider to a date's real daylight, after a draw.

        You cannot drag the sun to 3 a.m. in June because there is no sun
        there, and a slider that lets you ask an impossible question has to
        answer it with nothing.
        """
        lo = int(max(0, min(23 * 60 + 59, round(sunrise_hour * 60))))
        hi = int(max(lo + 1, min(24 * 60 - 1, round(sunset_hour * 60))))
        self._apply_time_window(lo, hi)

    def _apply_time_window(self, lo: int, hi: int):
        """Set the clock's range, keeping the current reading where it can be
        kept — re-dating should not throw away the hour you were looking at."""
        cur = self._sun_time_slider.value()
        blocked = self._sun_time_slider.blockSignals(True)
        self._sun_time_slider.setRange(lo, hi)
        self._sun_time_slider.setValue(max(lo, min(hi, cur)))
        self._sun_time_slider.blockSignals(blocked)
        self._sun_time_slider.setEnabled(True)
        self._update_sun_time_label()
        # Draw the marker at the opening position so the control is visibly
        # live rather than waiting to be discovered.
        self.sun_time_changed.emit(self._sun_time_slider.value())

    def set_site_location(self, lat, lng):
        """Remember where the site is, so the clock can span its real daylight
        before anything has been drawn.

        Called from ``_mark_modified``, i.e. on every feature mutation, so it
        returns early when nothing moved — re-clamping emits, and emitting
        crosses into JS."""
        if (lat, lng) == (self._sun_lat, self._sun_lng):
            return
        self._sun_lat, self._sun_lng = lat, lng
        self._reclamp_time_to_date()
        # The Wind tab's empty state asked for a pin that was already down
        # (V3.05 audit); say what is actually missing. Since V3.07 the rose
        # comes with the pin's site data (src/wind_flow.py).
        if not getattr(self, "_wind_fetched", False):
            self.set_wind_status(
                "No wind yet: it comes with the site pin (Site Info)."
                if lat is None else "No wind for this pin yet: it arrives with "
                "the site's data, or press Refresh wind data.")

    def _reclamp_time_to_date(self):
        from src import sun_shade
        d = sun_shade.resolve_date(self._sun_date.currentData())
        lo, hi = sun_shade.daylight_window(
            getattr(self, "_sun_lat", None), getattr(self, "_sun_lng", None), d)
        self._apply_time_window(lo, hi)

    def _update_sun_time_label(self):
        from src import sun_shade
        # "Sun time", not "Time": solar.sunrise_sunset and solar.sun_position
        # both work in local *solar* time — noon is when the sun is highest —
        # and the shade worker consumes the same convention. Labelling it as
        # clock time would be a quiet ~1½-hour lie on an Alberta summer day
        # (P9: say what the model actually computes).
        self._sun_time_label.setText(
            f"Sun time  {sun_shade.clock(self._sun_time_slider.value())}")

    def _on_sun_time_scrubbed(self, minutes: int):
        self._update_sun_time_label()
        # Immediate: the receiver only moves one marker in JS over a payload it
        # already holds, so this follows the drag.
        self.sun_time_changed.emit(int(minutes))
        # Debounced: the shade recompute is a worker-thread grid pass.
        self._shade_scrub.start()

    def _emit_shade_for_scrub(self):
        """Fire the debounced shade recompute — but only if shade is on screen.

        Merging the two controls means the clock now belongs to both features,
        and a scrub meant for the arc must not conjure a shade overlay nobody
        asked for. ``only_if_active`` asks the main window, which is the one
        thing that knows: the flag lives there, survives undo/redo and project
        load, and a copy of it here would be a second truth to keep in step.
        """
        self.shade_requested.emit(
            {"when": self._shade_when(), "only_if_active": True})

    def _on_sun_option_changed(self, _checked=False):
        """An arrow/length toggle only matters to an arc already on the map."""
        self.sun_redraw_requested.emit(self._sun_config())

    def _apply_date_to_controls(self):
        """Re-clamp the clock to the selected date and show/hide the leaf-off
        note. No signals out — this is the part that is safe to run at build."""
        from src import sun_shade
        data = self._sun_date.currentData()
        month = sun_shade.resolve_date(data).month if data is not None else None
        self._shade_leafoff_note.setVisible(sun_shade.is_leaf_off(month))
        self._reclamp_time_to_date()

    def _on_sun_date_changed(self, _index: int):
        """Changing the date re-clamps the clock, redraws the arc where it
        already is, and re-casts the shade for the new day.

        It used to re-enter anchor-placement mode, so comparing the solstices —
        the single most obvious thing to do on this tab — meant picking a date,
        pressing a button and re-clicking the map, every time.
        """
        self._apply_date_to_controls()
        self.sun_redraw_requested.emit(self._sun_config())
        self._shade_scrub.start()

    # ── The caster inventory, shown here and on the Site tab ────────────────

    def update_caster_summary(self, project_dict: dict | None):
        """Refresh the 'Casting shade: …' line from the project's existing
        features. Same formatter as the Site tab's copy — that one answers
        "did my import land?", this one answers "will this shade be real?"."""
        lbl = getattr(self, "_caster_summary", None)
        if lbl is None:
            return
        from src import sun_shade
        buildings, trees = sun_shade.caster_counts(project_dict)
        text, have = sun_shade.caster_summary(
            buildings, trees, where="Site → Features")
        lbl.setText(text)
        lbl.setStyleSheet(
            f"color: {'#a5d6a7' if have else '#ffcc80'}; font-size: 12px;")

    def mark_zones_shown(self):
        """Re-check the 'Show on map' box (without re-emitting) after a classify
        run draws the zones, so the toggle reflects what's on the map."""
        self._zones_show_cb.blockSignals(True)
        self._zones_show_cb.setChecked(True)
        self._zones_show_cb.blockSignals(False)

    def set_shade_zone_status(self, text: str):
        """Show a short result line under the Classify button."""
        if hasattr(self, "_shade_zone_status"):
            self._shade_zone_status.setText(text)

    # ═════════════════════════════════════════════════════════════════════════
    #  A4 — Wind / Windbreak
    # ═════════════════════════════════════════════════════════════════════════

    _GROUP_STYLE = (
        "QGroupBox { border: 1px solid #2e4a2e; border-radius: 4px; "
        "margin-top: 10px; padding-top: 12px; }"
        "QGroupBox::title { color: #a5d6a7; subcontrol-origin: margin; "
        "left: 6px; padding: 0 3px; }"
    )

    def _build_wind_tab(self):
        # Scrollable page — three grouped steps stack taller than the panel
        # at small window heights.
        page = QScrollArea()
        page.setWidgetResizable(True)
        page.setFrameShape(QFrame.Shape.NoFrame)
        tab = QWidget()
        page.setWidget(tab)
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(8)

        info = QLabel(
            "Where the wind comes from, and which parts of the site it misses. "
            "The rose comes with the site pin."
        )
        info.setWordWrap(True)
        info.setStyleSheet("color: #90a4ae; font-size: 12px;")
        layout.addWidget(info)

        # ── Step 1: real wind data (seasonal rose + current reading) ────────
        data_group = QGroupBox("1 · This site's wind")
        data_group.setStyleSheet(self._GROUP_STYLE)
        dg = QVBoxLayout(data_group)
        dg.setSpacing(6)

        # The rose arrives with the pin (V3.07, src/wind_flow.py); this
        # fetches it again, with a reading of the wind now.
        btn_fetch = QPushButton("Refresh wind data")
        # Secondary since the pin brings the rose (V3.07).
        btn_fetch.setStyleSheet(BTN_SECONDARY)
        btn_fetch.setToolTip(
            "Fetch this site's wind again from Open-Meteo, with a reading of "
            "the wind right now. The rose is kept for use offline.")
        btn_fetch.clicked.connect(self.wind_data_requested.emit)
        dg.addWidget(btn_fetch)

        from src.wind_rose_widget import WindRoseWidget
        self._wind_rose = WindRoseWidget()
        self._wind_rose.setToolTip(
            "Wind rose: each petal points where wind blows FROM; a longer "
            "petal = wind from there more often. Colour is strength — light "
            "blue (calm/light) through green and orange to red (very strong).")
        dg.addWidget(self._wind_rose)

        self._wind_current_lbl = QLabel("")
        self._wind_current_lbl.setStyleSheet("color: #b3e5fc; font-size: 12px;")
        dg.addWidget(self._wind_current_lbl)

        self._wind_status_lbl = QLabel(
            "No wind yet: it comes with the site pin (Site Info).")
        self._wind_status_lbl.setWordWrap(True)
        self._wind_status_lbl.setStyleSheet("color: #90a4ae; font-size: 12px;")
        dg.addWidget(self._wind_status_lbl)

        layout.addWidget(data_group)

        # ── Step 2: one direction control (the dial) + typical strength ─────
        dir_group = QGroupBox("2 · Prevailing wind")
        dir_group.setStyleSheet(self._GROUP_STYLE)
        rg = QVBoxLayout(dir_group)
        rg.setSpacing(6)

        dial_row = QHBoxLayout()
        self._wind_dial = QDial()
        self._wind_dial.setAccessibleName("Wind direction")
        self._wind_dial.setRange(0, 359)
        self._wind_dial.setWrapping(True)
        self._wind_dial.setNotchesVisible(True)
        self._wind_dial.setValue(270)
        self._wind_dial.setFixedSize(90, 90)
        self._wind_dial.setToolTip(
            "The direction the wind blows FROM (0° = N, 90° = E…).\n"
            "Set automatically from fetched data; drag to test other "
            "directions — the live wind shadow follows as you turn.")
        self._wind_dial.valueChanged.connect(self._on_wind_dial)
        self._wind_dial.sliderReleased.connect(
            lambda: self.wind_shadow_commit.emit(self._wind_dial.value()))
        dial_row.addWidget(self._wind_dial)

        dial_text = QVBoxLayout()
        dial_text.setSpacing(2)
        self._wind_dial_lbl = QLabel(self._dir_text(270))
        self._wind_dial_lbl.setStyleSheet(
            "color: #b3e5fc; font-size: 13px; font-weight: bold;")
        dial_text.addWidget(self._wind_dial_lbl)
        dial_hint = QLabel("Drag the dial to test other directions.")
        dial_hint.setWordWrap(True)
        dial_hint.setStyleSheet("color: #90a4ae; font-size: 12px;")
        dial_text.addWidget(dial_hint)
        speed_row = QHBoxLayout()
        speed_label = QLabel("Typical strength:")
        speed_row.addWidget(speed_label)
        self._wind_speed = QComboBox()
        speed_label.setBuddy(self._wind_speed)
        self._wind_speed.addItems(["Light", "Moderate", "Strong", "Very Strong"])
        self._wind_speed.setCurrentIndex(1)
        speed_row.addWidget(self._wind_speed)
        speed_row.addStretch()
        dial_text.addLayout(speed_row)
        dial_text.addStretch()
        dial_row.addLayout(dial_text, 1)
        rg.addLayout(dial_row)

        self._wind_advice_lbl = QLabel("")
        self._wind_advice_lbl.setWordWrap(True)
        self._wind_advice_lbl.setStyleSheet(
            "color: #c5e1a5; font-size: 12px; font-style: italic;")
        rg.addWidget(self._wind_advice_lbl)

        layout.addWidget(dir_group)

        # ── Step 3: what to draw on the map ──────────────────────────────────
        overlay_group = QGroupBox("3 · Show on the map")
        overlay_group.setStyleSheet(self._GROUP_STYLE)
        og = QVBoxLayout(overlay_group)
        og.setSpacing(6)

        # Live wind shadow (V1.68): per-plant sheltered zones that update as
        # you turn the dial or drag a plant.
        self._wind_shadow_chk = QCheckBox("Live wind shadow (sheltered zones)")
        self._wind_shadow_chk.setToolTip(
            "Show the leeward shelter of trees/shrubs, merged and porosity-aware. "
            "Turn the dial or drag a plant to see it update live.")
        self._wind_shadow_chk.toggled.connect(self.wind_shadow_toggled.emit)
        og.addWidget(self._wind_shadow_chk)

        # Snow-catch microsites (Step 3): winter snow drifts into the lee of
        # windbreaks — deeper-insulated, moister, slightly warmer planting spots.
        self._snow_catch_chk = QCheckBox("Snow catch (winter drifts in lee)")
        self._snow_catch_chk.setToolTip(
            "Show where winter snow drifts into the shelter of trees, shrubs and "
            "structures — insulated, moister microsites. Uses the prevailing "
            "winter wind from the fetched wind rose.")
        self._snow_catch_chk.toggled.connect(self.snow_catch_toggled.emit)
        og.addWidget(self._snow_catch_chk)

        self._wind_arrows = QCheckBox("Wind direction arrows")
        self._wind_arrows.setChecked(True)
        self._wind_arrows.setToolTip(
            "Arrows across the map showing which way the prevailing wind blows.")
        og.addWidget(self._wind_arrows)

        self._wind_shelter = QCheckBox("Shelter zones behind windbreaks")
        self._wind_shelter.setChecked(True)
        self._wind_shelter.setToolTip(
            "Hedgerows and windbreak structures show a\n"
            "sheltered zone (10× height) on the leeward side")
        og.addWidget(self._wind_shelter)

        btn_row = QHBoxLayout()
        btn_show = QPushButton("Show Wind Overlay")
        btn_show.setToolTip(
            "Draw the arrows and windbreak shelter zones for the direction on "
            "the dial. (The two checkboxes above draw live, on toggle.)")
        btn_show.setStyleSheet(BTN_PRIMARY)
        btn_show.clicked.connect(self._on_show_wind)
        btn_row.addWidget(btn_show)

        btn_clear = QPushButton("Clear")
        btn_clear.setToolTip("Remove the arrows + windbreak shelter overlay.")
        btn_clear.setStyleSheet(
            "QPushButton { background: #37474f; color: #b0bec5; border: 1px solid #546e7a; "
            "border-radius: 4px; padding: 6px; }"
            "QPushButton:hover { background: #455a64; }"
        )
        btn_clear.clicked.connect(self.wind_cleared.emit)
        btn_row.addWidget(btn_clear)
        og.addLayout(btn_row)

        layout.addWidget(overlay_group)

        layout.addStretch()
        # Hosted by the Site tab since V3.07, like Sun & Shade.
        self._wind_page = page
        self._tabs.addTab(page, "Wind")

    @staticmethod
    def _dir_text(deg: int) -> str:
        """'Wind from NW (315°)' — the dial's one human-readable readout."""
        from src.wind import dir_label
        return f"Wind from {dir_label(deg)} ({deg % 360}°)"

    def _on_show_wind(self):
        self.wind_requested.emit({
            "direction_from": self._wind_dial.value(),
            "speed_label": self._wind_speed.currentText(),
            "show_shelter": self._wind_shelter.isChecked(),
            "show_arrows": self._wind_arrows.isChecked(),
        })

    # ── Real wind data (V1.67) ──────────────────────────────────────────────

    def set_wind_status(self, text: str):
        self._wind_status_lbl.setText(text)

    def set_wind_advice(self, text: str):
        self._wind_advice_lbl.setText(text or "")

    def _on_wind_dial(self, value: int):
        self._wind_dial_lbl.setText(self._dir_text(value))
        self.wind_angle_changed_live.emit(value)

    def set_wind_data(self, rose: dict, current: dict | None):
        """Populate the Wind tab from a fetched rose + current reading: draw the
        rose, set the prevailing-direction/speed controls to the data, and show
        the live reading. Also surfaces a windbreak hint via the design hook in
        the controller (which reads the same rose from the cache)."""
        if not rose:
            self.set_wind_status(
                "Wind data unavailable (offline and nothing cached).")
            self._wind_rose.set_block(None)
            return
        annual = rose.get("annual") or {}
        self._wind_rose.set_block(annual)
        self._wind_fetched = True

        from src.wind import speed_category
        prevailing = annual.get("prevailing_deg")
        if prevailing is not None:
            blocked = self._wind_dial.blockSignals(True)
            self._wind_dial.setValue(int(prevailing) % 360)
            self._wind_dial.blockSignals(blocked)
            self._wind_dial_lbl.setText(self._dir_text(int(prevailing)))
        cat = speed_category(annual.get("mean_speed"))
        idx = self._wind_speed.findText(cat)
        if idx >= 0:
            self._wind_speed.setCurrentIndex(idx)

        if current:
            self._wind_current_lbl.setText(
                f"Now: {current['speed']:.0f} km/h from {current['dir_label']}"
                + (f", gusts {current['gusts']:.0f}" if current.get("gusts")
                   else ""))
        else:
            self._wind_current_lbl.setText("")

        label = annual.get("prevailing_label") or "—"
        mean = annual.get("mean_speed")
        calm = annual.get("calm_pct")
        src = rose.get("source", "")
        self.set_wind_status(
            f"Prevailing {label} · mean {mean:.0f} km/h · calm {calm:.0f}%  "
            f"({src}). The dial below is set to match — step 3 draws it "
            f"on the map.")

    # ═════════════════════════════════════════════════════════════════════════
    #  F51 — Phenology "what's happening now" dashboard
    # ═════════════════════════════════════════════════════════════════════════

    def _build_phenology_tab(self):
        from src.phenology_widget import PhenologyWidget
        page = QScrollArea()
        page.setWidgetResizable(True)
        page.setFrameShape(QFrame.Shape.NoFrame)
        # Design-aware: reads the live placed-plant list so "this month" is the
        # user's own design.
        self._phenology = PhenologyWidget(
            plants_provider=lambda: self._placed_plants)
        page.setWidget(self._phenology)
        # Design › Over time takes the dashboard since V3.08
        # (src/side_panel_layout.py), first of its three sections.
        self._phenology_page = page
        self._tabs.addTab(page, "This Month")

    # ═════════════════════════════════════════════════════════════════════════
    #  H1 — Habitat Value Score
    # ═════════════════════════════════════════════════════════════════════════

    def _build_habitat_tab(self):
        # Scrollable page: this tab is tall (score, value, species gallery,
        # breakdown, tips, shade) and used to overlap when squeezed into a fixed
        # height. A scroll area lets it grow instead (matches site_panel).
        page = QScrollArea()
        page.setWidgetResizable(True)
        page.setFrameShape(QFrame.Shape.NoFrame)
        tab = QWidget()
        page.setWidget(tab)
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(8)

        info = QLabel(
            "How much habitat the design provides, out of 100; what the score "
            "is made of is below it."
        )
        info.setWordWrap(True)
        info.setStyleSheet("color: #90a4ae; font-size: 12px;")
        layout.addWidget(info)

        # Big score readout
        self._habitat_score_label = QLabel("—")
        self._habitat_score_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._habitat_score_label.setStyleSheet(
            "color: #c8e6c9; font-size: 32px; font-weight: bold; "
            "background: #1a2a1a; border: 1px solid #2e4a2e; border-radius: 4px; padding: 12px;"
        )
        layout.addWidget(self._habitat_score_label)

        # Lawn-equivalent counterfactual (F10, P6/P8): the Tallamy contrast made
        # explicit — what this design provides vs. the ≈0 a conventional lawn of
        # the same ground would. Hidden until a score is computed.
        self._lawn_counterfactual_label = QLabel("")
        self._lawn_counterfactual_label.setWordWrap(True)
        self._lawn_counterfactual_label.setVisible(False)
        self._lawn_counterfactual_label.setStyleSheet(
            "color: #dcedc8; font-size: 12px; padding: 8px; "
            "background: #1a2a1a; border: 1px solid #2e4a2e; border-radius: 4px;"
        )
        layout.addWidget(self._lawn_counterfactual_label)

        # Species galleries (F11 / I1) — photos that make the value tangible.
        # "Species doing the work" = the plants (keystone / host / bird-food
        # first); "Species supported" = the fauna those plants feed/host. Both
        # show cached photos immediately and warm the rest in the background.
        def _gallery_strip(title: str):
            lbl = QLabel(title)
            lbl.setStyleSheet(
                "color: #a5d6a7; font-size: 12px; font-weight: bold; "
                "padding: 4px 0 2px 0;")
            lbl.setVisible(False)
            area = QScrollArea()
            area.setWidgetResizable(True)
            area.setFrameShape(QFrame.Shape.NoFrame)
            area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
            area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            area.setFixedHeight(122)
            area.setVisible(False)
            area.setStyleSheet(
                "background: #14241a; border: 1px solid #2e4a2e; border-radius: 4px;")
            inner = QWidget()
            row = QHBoxLayout(inner)
            row.setContentsMargins(6, 6, 6, 6)
            row.setSpacing(8)
            row.addStretch()   # keep cards left-aligned
            area.setWidget(inner)
            layout.addWidget(lbl)
            layout.addWidget(area)
            return lbl, area, row

        (self._species_gallery_label, self._species_gallery,
         self._species_gallery_row) = _gallery_strip("Species doing the work")
        (self._fauna_gallery_label, self._fauna_gallery,
         self._fauna_gallery_row) = _gallery_strip("Species supported")
        self.galleryImageReady.connect(self._on_gallery_image_ready)

        # Breakdown
        self._habitat_breakdown = QLabel("")
        self._habitat_breakdown.setWordWrap(True)
        self._habitat_breakdown.setStyleSheet(
            "color: #c8e6c9; font-size: 12px; padding: 8px; "
            "background: #1a2a1a; border: 1px solid #2e4a2e; border-radius: 4px; "
            "font-family: 'Consolas', 'Courier New', monospace;"
        )
        self._habitat_breakdown.setAlignment(Qt.AlignmentFlag.AlignTop)
        self._habitat_breakdown.setMinimumHeight(220)
        layout.addWidget(self._habitat_breakdown)

        # ── How sure are we? (F13 + F14) — the confidence block ───────────
        self._build_confidence_block(layout)

        # ── Relationship web (F5) — the design drawn as a living network ───
        self._build_relationship_web_block(layout)

        # ── Pull-a-plant impact simulator (F46) — learn by breaking it ─────
        pull_label = QLabel("Pull-a-plant — what does each plant hold up?")
        pull_label.setStyleSheet(
            "color: #a5d6a7; font-size: 12px; font-weight: bold; padding: 6px 0 2px 0;")
        layout.addWidget(pull_label)

        pull_hint = QLabel(
            "Pick a plant to see what removing it would cost: the animals "
            "left with nothing, and the score.")
        pull_hint.setWordWrap(True)
        pull_hint.setStyleSheet("color: #90a4ae; font-size: 12px;")
        layout.addWidget(pull_hint)

        self._pull_combo = QComboBox()
        self._pull_combo.setAccessibleName("Plant to pull")
        self._pull_combo.setToolTip("Preview the impact of removing this plant")
        self._pull_combo.currentIndexChanged.connect(self._on_pull_plant)
        layout.addWidget(self._pull_combo)

        self._pull_result = QLabel("")
        self._pull_result.setWordWrap(True)
        self._pull_result.setVisible(False)
        self._pull_result.setStyleSheet(
            "color: #ffe0b2; font-size: 12px; padding: 8px; "
            "background: #241a12; border: 1px solid #5a3a1e; border-radius: 4px;")
        layout.addWidget(self._pull_result)

        # ── Feed-a-chickadee provisioning scenario (F47) ──────────────────────
        chickadee_label = QLabel("Feed a chickadee brood")
        chickadee_label.setStyleSheet(
            "color: #a5d6a7; font-size: 12px; font-weight: bold; padding: 6px 0 2px 0;")
        layout.addWidget(chickadee_label)

        self._chickadee_result = QLabel(
            "One clutch of chickadees needs 6,000–9,000 caterpillars to fledge. "
            "Place plants to see whether your host plants could feed a brood.")
        self._chickadee_result.setWordWrap(True)
        self._chickadee_result.setStyleSheet(
            "color: #cfe3f0; font-size: 12px; padding: 8px; "
            "background: #12202a; border: 1px solid #1e4a5a; border-radius: 4px;")
        layout.addWidget(self._chickadee_result)

        # Tips for raising your score
        tips_label = QLabel("Tips for raising your score")
        tips_label.setStyleSheet("color: #a5d6a7; font-size: 12px; font-weight: bold; padding: 4px 0 2px 0;")
        layout.addWidget(tips_label)

        self._habitat_tips = QTextEdit()
        tips_label.setBuddy(self._habitat_tips)
        self._habitat_tips.setReadOnly(True)
        self._habitat_tips.setStyleSheet(
            "QTextEdit { background: #1a2a1a; color: #c8e6c9; "
            "border: 1px solid #2e4a2e; border-radius: 4px; padding: 6px; "
            "font-size: 12px; }"
        )
        self._habitat_tips.setMinimumHeight(160)
        layout.addWidget(self._habitat_tips)

        # Shade-zone breakdown — read-only summary of the cached shade tags
        # (Sun & Shade → "Classify planting zones"). Shown here so the light
        # mix is visible alongside habitat value without recomputing the grid.
        shade_label = QLabel("Light / shade mix")
        shade_label.setStyleSheet(
            "color: #a5d6a7; font-size: 12px; font-weight: bold; padding: 4px 0 2px 0;")
        layout.addWidget(shade_label)

        self._shade_breakdown = QLabel(
            "Run 'Classify planting zones' on the Sun & Shade tab to see\n"
            "the full-sun / partial-shade / full-shade mix.")
        self._shade_breakdown.setWordWrap(True)
        self._shade_breakdown.setStyleSheet(
            "color: #c8e6c9; font-size: 12px; padding: 6px; "
            "background: #1a2a1a; border: 1px solid #2e4a2e; border-radius: 4px;")
        layout.addWidget(self._shade_breakdown)

        # Reference link
        ref = QLabel(
            "Based on Doug Tallamy's keystone-species framework "
            "(homegrownnationalpark.org) — high-value native species support "
            "90% of insect biodiversity."
        )
        ref.setWordWrap(True)
        ref.setStyleSheet("color: #90a4ae; font-size: 12px; font-style: italic;")
        layout.addWidget(ref)

        # Short tab label so all five fit the strip even with macOS's wider
        # font; the page itself carries the full "Habitat Value" wording.
        self._habitat_page = page
        self._tabs.addTab(page, "Habitat")

    # ═════════════════════════════════════════════════════════════════════════
    #  Relationship web (F5) — P3/P5/P10
    # ═════════════════════════════════════════════════════════════════════════

    # Layer name → the edge kinds it turns on (src.db.relationships.EDGE_KINDS).
    # Grouped rather than listed one-per-kind: seven trophic checkboxes is a
    # database schema wearing a UI, and the useful question is "show me the food
    # web" / "show me the horticulture", not "show me seed_food".
    _WEB_LAYERS = [
        ("food", "Food web — who eats, sips and lays eggs here", True,
         ("larval_host", "nectar", "pollen", "fruit_food", "seed_food")),
        ("shelter", "Shelter — nest sites and cover", True,
         ("nesting", "cover")),
        ("companion", "Companion pairings — good together / keep apart", False,
         ("companion_friend", "companion_enemy")),
        ("community", "Shares an authored plant community", False,
         ("co_planted",)),
        ("derived", "Inferred: plants feeding the same wildlife", False,
         ("shared_fauna",)),
    ]

    def _build_confidence_block(self, layout):
        """"How sure are we?" — the establishment and fidelity bands (F13/F14).

        The Habitat Value Score is a confident-looking number out of 100, and
        until now nothing beside it said how much of that rests on evidence.
        These two read-outs are the counterweight, and both are **bands, never
        percentages** — see :mod:`src.confidence`, which owns the words so the
        two cannot end up on different scales.
        """
        head = QLabel("How sure are we?")
        head.setStyleSheet(
            "color: #a5d6a7; font-size: 12px; font-weight: bold; "
            "padding: 6px 0 2px 0;")
        layout.addWidget(head)

        hint = QLabel(
            "What the score cannot say: whether these species are recorded "
            "growing near you, and whether the design has the shape of the "
            "natural community here.")
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #90a4ae; font-size: 12px;")
        layout.addWidget(hint)

        self._confidence_text = QLabel(
            "Place plants to fill this in.")
        self._confidence_text.setWordWrap(True)
        self._confidence_text.setTextFormat(Qt.TextFormat.RichText)
        self._confidence_text.setStyleSheet(
            "color: #c8e6c9; font-size: 12px; padding: 8px; "
            "background: #1a2a1a; border: 1px solid #2e4a2e; "
            "border-radius: 4px;")
        layout.addWidget(self._confidence_text)

    def _refresh_confidence(self, placed_plants, ecoregion):
        """Recompute both bands. Never raises — a missing band is a blank line,
        not a broken panel."""
        from src.confidence import UNKNOWN                   # noqa: PLC0415
        blocks = []
        try:
            from src.establishment import (                  # noqa: PLC0415
                establishment_for_design, summary_band)
            est = establishment_for_design(placed_plants, ecoregion)
            band = summary_band(est)
            blocks.append(self._band_html(
                "Recorded growing here", band, est.get("lines") or []))
        except Exception as exc:                             # noqa: BLE001
            blocks.append(self._band_html(
                "Recorded growing here", UNKNOWN, [f"Unavailable: {exc}"]))
        try:
            from src.reference_fidelity import fidelity      # noqa: PLC0415
            fid = fidelity(placed_plants, ecoregion)
            blocks.append(self._band_html(
                "Like the natural community", fid["band"],
                fid.get("lines") or []))
        except Exception as exc:                             # noqa: BLE001
            blocks.append(self._band_html(
                "Like the natural community", UNKNOWN, [f"Unavailable: {exc}"]))
        self._confidence_text.setText("<br><br>".join(blocks))

    @staticmethod
    def _band_html(title: str, band, lines: list) -> str:
        """One band as a heading, its label, its basis, and the detail lines.

        The blurb is always shown, because a band label read without what it is
        based on is exactly the false confidence this block exists to prevent.
        """
        colour = {"high": "#a5d6a7", "medium": "#ffcc80",
                  "low": "#ef9a9a"}.get(band.key, "#90a4ae")
        body = "".join(f"<br>{ln}" for ln in lines if ln)
        return (f"<b>{title}:</b> <span style='color:{colour};'>"
                f"{band.label}</span>"
                f"<br><span style='color:#90a4ae;'>{band.blurb}</span>{body}")

    def _build_relationship_web_block(self, layout):
        """The relationship-web controls on the Habitat tab.

        The overlay itself is the feature; this block is a toggle, a layer
        filter and an honest read-out of what the picture contains.
        """
        head = QLabel("Relationship web — the design as a network")
        head.setStyleSheet(
            "color: #a5d6a7; font-size: 12px; font-weight: bold; "
            "padding: 6px 0 2px 0;")
        layout.addWidget(head)

        hint = QLabel(
            "Draws on the map which plants feed, host and shelter which "
            "animals. The animals sit on a ring outside the planting: a "
            "diagram, not where they live.")
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #90a4ae; font-size: 12px;")
        layout.addWidget(hint)

        self._web_toggle = QCheckBox("Show the relationship web on the map")
        self._web_toggle.setStyleSheet("color: #c8e6c9; font-size: 12px;")
        self._web_toggle.toggled.connect(self._on_web_toggled)
        layout.addWidget(self._web_toggle)

        self._web_layer_boxes = {}
        for key, label, on, _kinds in self._WEB_LAYERS:
            box = QCheckBox(label)
            box.setChecked(on)
            box.setStyleSheet(
                "color: #b0bec5; font-size: 12px; padding-left: 16px;")
            box.toggled.connect(self._on_web_layers_changed)
            layout.addWidget(box)
            self._web_layer_boxes[key] = box

        self._web_summary = QLabel("")
        self._web_summary.setWordWrap(True)
        self._web_summary.setVisible(False)
        self._web_summary.setStyleSheet(
            "color: #c8e6c9; font-size: 12px; padding: 8px; "
            "background: #16221f; border: 1px solid #2e4a4a; "
            "border-radius: 4px;")
        layout.addWidget(self._web_summary)

    def _web_kinds(self) -> tuple:
        """The edge kinds the current layer checkboxes select."""
        kinds: list[str] = []
        for key, _label, _on, kind_names in self._WEB_LAYERS:
            box = self._web_layer_boxes.get(key)
            if box is not None and box.isChecked():
                kinds.extend(kind_names)
        return tuple(kinds)

    def _on_web_toggled(self, on: bool):
        if on:
            self._refresh_relationship_web()
        else:
            self._web_summary.setVisible(False)
            self.relationship_overlay_cleared.emit()

    def _on_web_layers_changed(self, _checked: bool):
        if getattr(self, "_web_toggle", None) is not None \
                and self._web_toggle.isChecked():
            self._refresh_relationship_web()

    def _refresh_relationship_web(self):
        """Rebuild and re-emit the graph. Never raises — the web is a lens on
        the design, and a lens that can crash the panel is worse than no lens."""
        if getattr(self, "_web_toggle", None) is None \
                or not self._web_toggle.isChecked():
            return
        kinds = self._web_kinds()
        try:
            from src.relationship_graph import (build_relationship_graph,
                                                summary_lines)
            graph = build_relationship_graph(self._placed_plants or [],
                                             kinds=kinds)
            lines = summary_lines(graph)
        except Exception as exc:  # noqa: BLE001
            self._web_summary.setText(
                f"Relationship web unavailable: {exc}")
            self._web_summary.setVisible(True)
            self.relationship_overlay_cleared.emit()
            return
        if not kinds:
            lines = ["Pick at least one layer to draw."]
        self._web_summary.setText("<br>".join(lines))
        self._web_summary.setVisible(True)
        self.relationship_overlay_requested.emit(graph)

    def show_habitat_tab(self):
        """Raise the Habitat Value page (the report card's habitat-value
        deep-link, V2.13), by the page and not its place in the strip, which
        V3.07 changed."""
        from src.keyboard_help import show_panel
        show_panel(self._habitat_page)

    # ═════════════════════════════════════════════════════════════════════════
    #  Food — who the design feeds (V3.08; the Bees page, F37, generalised)
    # ═════════════════════════════════════════════════════════════════════════

    def _build_food_tab(self):
        """Design › Food (src/food_page.py): the owner's "what it feeds" page,
        the Bees page and Planning's Wildlife and Harvest calendars in one. It
        borrows this panel's photo warmer, and its map view rides the Bees
        page's two signals, which app.py already sends to the map."""
        from src.food_page import FoodPage
        self._food = FoodPage(warm_images=self._warm_gallery_images)
        self._food.map_overlay_requested.connect(self.bee_map_overlay_requested)
        self._food.map_overlay_cleared.connect(self.bee_map_overlay_cleared)
        self.galleryImageReady.connect(self._food.on_image_ready)
        self._tabs.addTab(self._food, "Food")

    # ── Pull-a-plant impact simulator (F46) ───────────────────────────────

    def _populate_pull_combo(self):
        """Fill the pull-a-plant selector with the design's distinct species.

        V2.42: this used to run **only** from ``_calc_habitat_score``, which is
        wired to a button. So the list was a snapshot of whatever was planted
        the last time somebody pressed *Calculate* — it did not follow the
        design, and after a few edits it listed species that were no longer
        placed while missing the ones that were. It read as an arbitrary list
        because that is what it had become. It is now also called from
        :meth:`set_placed_plants`, so it follows every edit.

        The selection is preserved across a refresh (rebuilding a combo the
        user has already chosen from is its own bug — it would silently reset
        their choice on every plant placed), and dropped only when the species
        it names actually leaves the design.
        """
        combo = getattr(self, "_pull_combo", None)
        if combo is None:
            return
        previous = combo.currentData()
        combo.blockSignals(True)
        combo.clear()
        by_id: dict = {}
        for p in (self._placed_plants or []):
            pid = p.get("plant_id")
            if pid is not None and pid not in by_id:
                by_id[pid] = p.get("common_name") or f"plant {pid}"
        if not by_id:
            combo.addItem("Place plants first", userData=None)
            combo.setEnabled(False)
            combo.blockSignals(False)
            self._pull_result.setVisible(False)
            return

        combo.setEnabled(True)
        combo.addItem("— pick a plant to test —", userData=None)
        for pid, name in sorted(by_id.items(), key=lambda kv: kv[1].lower()):
            combo.addItem(name, userData=pid)
        restored = False
        if previous is not None and previous in by_id:
            idx = combo.findData(previous)
            if idx >= 0:
                combo.setCurrentIndex(idx)
                restored = True
        combo.blockSignals(False)
        if restored:
            # The design changed under a live answer, so the answer is stale
            # too — recompute it rather than leave a number that no longer
            # describes anything.
            self._on_pull_plant()
        else:
            self._pull_result.setVisible(False)

    def _on_pull_plant(self, *_):
        """Render the impact of removing the selected plant (F46)."""
        combo = self._pull_combo
        pid = combo.currentData()
        if pid is None:
            self._pull_result.setVisible(False)
            return
        try:
            from src.plant_impact import pull_plant_impact
            r = pull_plant_impact(self._placed_plants, self._structures, int(pid))
        except Exception:      # noqa: BLE001 — never let the sim break the tab
            self._pull_result.setVisible(False)
            return
        if r is None:
            self._pull_result.setVisible(False)
            return
        detail = (f"Habitat Score {r['score_before']} → {r['score_after']}"
                  f"   ·   this plant feeds {r['species_supported']} species")
        lost_bits = []
        for taxon, names in r["species_lost_by_taxon"].items():
            shown = ", ".join(names[:4]) + ("…" if len(names) > 4 else "")
            lost_bits.append(shown)
        lost_line = ("<br><span style='color:#ffab91'>Lost: "
                     + "; ".join(lost_bits) + "</span>") if lost_bits else ""
        self._pull_result.setText(
            f"<b>{r['verdict']}</b><br><span style='color:#c8b08a'>{detail}"
            f"</span>{lost_line}")
        self._pull_result.setVisible(True)

    # ── Feed-a-chickadee provisioning scenario (F47) ──────────────────────

    def _update_chickadee_scenario(self):
        """Refresh the chickadee-brood provisioning story from the live design."""
        label = getattr(self, "_chickadee_result", None)
        if label is None:
            return
        try:
            from src.chickadee_scenario import chickadee_provision
            r = chickadee_provision(self._placed_plants or [])
        except Exception:      # noqa: BLE001 — never let the scenario break the tab
            return
        colors = {"clears": "#a5d6a7", "partway": "#ffe0b2",
                  "short": "#ffab91", "none": "#cfe3f0"}
        c = colors.get(r["status"], "#cfe3f0")
        body = f"<span style='color:{c}'>{r['verdict']}</span>"
        if r["host_plants"]:
            body += (f"<br><span style='color:#9fbccf; font-size:12px'>"
                     f"Capacity ≈ {r['caterpillars_low']:,}–"
                     f"{r['caterpillars_high']:,} caterpillars from "
                     f"{r['n_host_species']} host species.</span>")
        label.setText(body)

    def set_shade_breakdown(self, counts: dict | None):
        """Render the cached shade-tag mix (``{tag: n}`` from
        shade_zones.tag_counts), or a prompt when nothing is classified yet.
        Called by the main window after classification / project load."""
        if not hasattr(self, "_shade_breakdown"):
            return
        total = sum((counts or {}).values())
        if not total:
            self._shade_breakdown.setText(
                "Run 'Classify planting zones' on the Sun & Shade tab to see\n"
                "the full-sun / partial-shade / full-shade mix.")
            return

        def _pct(n):
            return f"{n} ({n * 100 // total}%)"
        self._shade_breakdown.setText(
            f"Across {total} classified spots:\n"
            f"  ☀️  Full sun       {_pct(counts.get('full_sun', 0))}\n"
            f"  ⛅  Partial shade  {_pct(counts.get('partial_shade', 0))}\n"
            f"  🌑  Full shade     {_pct(counts.get('full_shade', 0))}")

    # Structure ids that contribute to habitat value — re-exported from
    # src/habitat_score.py (where the scoring maths lives now) so the
    # tips builder below and the score stay in lock-step.
    from src.habitat_score import HABITAT_STRUCTURE_IDS as _HABITAT_STRUCTURE_IDS

    def set_placed_plants(self, plants: list[dict]):
        """Update the list of placed plants (from app.py)."""
        self._placed_plants = plants
        # Food fills itself when it is on screen (the LiveRefresh poke below).
        self._food.set_placed_plants(plants)
        # Phenology dashboard likewise reads the live design.
        if hasattr(self, "_phenology"):
            self._phenology.refresh()
        # The relationship web is a view of the design, so it follows every
        # edit — placing a keystone shrub should visibly grow the network (F5).
        self._refresh_relationship_web()
        # Pull-a-plant is a view of the design too, and was not following it:
        # its list was only rebuilt when the habitat score was recalculated by
        # hand, so it drifted out of step with what was actually planted.
        self._populate_pull_combo()
        # Same rule for the confidence bands (F13/F14) — a read-out that only
        # updates when a button is pressed is the V2.42 stale-list bug, and
        # both of these change the moment a species is added or removed.
        self._refresh_confidence(self._placed_plants or [],
                                 self._site_ecoregion())
        self._live.poke()                  # the score follows it too (V3.05)

    @staticmethod
    def _layer_lines(result) -> list:
        """The vegetation-layer rows, which say what they were scored against.

        F129 (V2.65) re-bases this component onto the reference community's own
        layers where one is known, so the denominator is no longer a fixed 5.
        The row has to name the basis: a user who sees 15/15 for three layers
        needs to know it was three layers *their grassland actually has*, and
        not a bug.
        """
        if result.layer_basis and result.layer_detail:
            detail = result.layer_detail
            filled = sum(1 for d in detail.values() if d.get("present"))
            thin = sorted(k for k, d in detail.items()
                          if not d.get("present") and d.get("have"))
            absent = sorted(k for k, d in detail.items()
                            if not d.get("present") and not d.get("have"))
            rows = [f"Vegetation layers  {filled:4d}/{len(detail)}   "
                    f"{result.score_layers:4.1f} / 15",
                    f"  (vs {result.layer_basis})"]
            if thin:
                rows.append(f"  thin: {', '.join(thin)}")
            if absent:
                rows.append(f"  absent: {', '.join(absent)}")
            return rows
        return [f"Vegetation layers  {len(result.layers_present):4d}/5   "
                f"{result.score_layers:4.1f} / 15",
                f"  ({', '.join(result.layers_present) or '—'})"]

    def _site_ecoregion(self):
        """The site's ecoregion key, cached against the pin.

        ``lookup_ecoregion`` is a point-in-polygon sweep over the shipped
        GeoJSON and this is called on every plant placement, so the answer is
        memoised on the coordinates rather than recomputed per edit.
        """
        lat = getattr(self, "_sun_lat", None)
        lng = getattr(self, "_sun_lng", None)
        if lat is None or lng is None:
            return None
        if getattr(self, "_ecoregion_at", None) == (lat, lng):
            return self._ecoregion_cache
        try:
            from src.ecoregion import lookup_ecoregion       # noqa: PLC0415
            self._ecoregion_cache = lookup_ecoregion(lat, lng)
        except Exception:                                    # noqa: BLE001
            self._ecoregion_cache = None
        self._ecoregion_at = (lat, lng)
        return self._ecoregion_cache

    def set_structures(self, structures: list[dict]):
        """Update the list of placed structures (from app.py)."""
        self._structures = structures
        self._live.poke()

    def set_lawn_conversion(self, summary: dict | None):
        """Store the lawn-conversion summary (from ``lawn_zones.conversion_summary``)
        so the F10 counterfactual can ground its contrast in the converted area.
        Re-renders the counterfactual if a score is already on screen."""
        self._lawn_conversion = summary or None
        if getattr(self, "_last_habitat_result", None) is not None:
            self._render_lawn_counterfactual(self._last_habitat_result)

    def _render_lawn_counterfactual(self, result):
        """Show the design's habitat value beside the ≈0 of an equivalent lawn
        (F10). Never raises — the counterfactual is a nicety, not the score."""
        lbl = getattr(self, "_lawn_counterfactual_label", None)
        if lbl is None:
            return
        try:
            from src.lawn_zones import lawn_counterfactual, format_lawn_counterfactual
            cf = lawn_counterfactual(result, self._lawn_conversion)
            lines = format_lawn_counterfactual(cf)
        except Exception:  # noqa: BLE001
            lines = []
        if not lines:
            lbl.setVisible(False)
            return
        head = lines[0]
        rest = lines[1:]
        html = (f"<b>vs. lawn</b><br>{head}"
                + ("<br><span style='color:#90a4ae;font-size:12px;'>"
                   + "<br>".join(rest) + "</span>" if rest else ""))
        lbl.setText(html)
        lbl.setVisible(True)

    def _calc_habitat_score(self):
        # Scoring maths moved to src/habitat_score.py (Chunk 6) so the
        # headless scripting API and this panel share one implementation.
        # The panel keeps all the rendering below.
        from src.habitat_score import compute_habitat_score, HabitatScoreError
        try:
            # The ecoregion re-bases the layer component onto the reference
            # community's own layers (F129) — a prairie planting is no longer
            # marked against a forest-garden stack it was never going to fill.
            result = compute_habitat_score(
                self._placed_plants, self._structures,
                ecoregion=self._site_ecoregion())
        except HabitatScoreError:
            self._habitat_score_label.setText("?")
            self._habitat_breakdown.setText("Plant database unavailable.")
            self._lawn_counterfactual_label.setVisible(False)
            return
        if result is None:
            self._habitat_score_label.setText("—")
            self._habitat_breakdown.setText("Place some plants and structures first.")
            self._lawn_counterfactual_label.setVisible(False)
            return

        total_int = result.total
        grade = result.grade

        # Score colour
        if total_int >= 75:
            color = "#a5d6a7"
        elif total_int >= 50:
            color = "#dcedc8"
        elif total_int >= 25:
            color = "#fff59d"
        else:
            color = "#ffab91"

        self._habitat_score_label.setText(f"{total_int} / 100")
        self._habitat_score_label.setStyleSheet(
            f"color: {color}; font-size: 32px; font-weight: bold; "
            "background: #1a2a1a; border: 1px solid #2e4a2e; border-radius: 4px; padding: 12px;"
        )

        # Lawn-equivalent counterfactual (F10): this design vs. the ≈0 of an
        # equivalent lawn, grounded in the converted area when zones are drawn.
        self._last_habitat_result = result
        self._render_lawn_counterfactual(result)
        self._populate_pull_combo()
        self._update_chickadee_scenario()

        # Species photos that make the value tangible (F11 / I1): the plants
        # doing the work and the fauna they support.
        try:
            self._render_galleries(result)
        except Exception:  # noqa: BLE001 — galleries are a nicety, never break the score
            for w in (self._species_gallery_label, self._species_gallery,
                      self._fauna_gallery_label, self._fauna_gallery):
                w.setVisible(False)

        # Breakdown text — layout unchanged from the pre-extraction code;
        # values now come off the HabitatScore result.
        lines = [
            f"{grade}",
            "",
            f"Native ratio        {result.native_ratio*100:5.0f}%    {result.score_native:4.1f} / 20",
            f"  ({result.native_species} of {result.n_species} species native to AB)",
            "",
            f"Keystone species   {len(result.keystone_species):4d}     {result.score_keystone:4.1f} / 15",
            f"Host plants        {len(result.host_species):4d}     {result.score_host:4.1f} / 10",
            f"Bird-food species  {len(result.bird_species):4d}     {result.score_bird:4.1f} / 10",
            "",
            *self._layer_lines(result),
            "",
            f"Habitat structures {len(result.habitat_struct_types):4d}     {result.score_structs:4.1f} / 10",
            f"  ({', '.join(result.habitat_struct_types) or '—'})",
            "",
            f"Bloom continuity   {len(result.bloom_months)}/7 mo   {result.score_bloom:4.1f} / 20",
            "",
            # Informational fauna support (NOT summed into the headline, so
            # existing scores stay stable as the fauna dataset grows). The
            # lepidoptera line counts larval-host species (schema v13); the
            # per-taxon line counts distinct native fauna the design supports
            # across all taxa (schema v20 expansion).
            f"Lepidoptera supported  {result.n_lepidoptera_supported:4d}    (larval-host species)",
        ]
        if getattr(result, "fauna_by_taxon", None):
            _taxon_label = {
                "lepidoptera": "butterflies/moths", "bird": "birds",
                "bee": "bees", "other_insect": "other insects",
                "mammal": "mammals",
            }
            parts = [f"{n} {_taxon_label.get(t, t)}"
                     for t, n in result.fauna_by_taxon.items()]
            lines.append("Wildlife supported   " + ", ".join(parts))
        # Food-web completeness (F3): does the design close the Tallamy chain
        # (host plants → caterpillars → the birds that eat them)? Informational,
        # never summed into the headline.
        food_web = getattr(result, "food_web", None)
        if food_web:
            _food_web_msg = {
                "complete": "Food web   supports caterpillars and the "
                            "birds that eat them",
                # V2.58: this state used to be reported as "complete". Both
                # links come from use TAGS with no wildlife record behind
                # either, and saying "supports the birds that eat them" about a
                # design we hold no bird records for is a claim the data cannot
                # carry.
                "unverified": "Food web   the plant tags suggest hosts and "
                              "bird food, but no wildlife records back it yet",
                "no_birds": "Food web   caterpillars, but no bird support "
                            "yet; add berry/seed plants",
                "no_hosts": "Food web   birds, but no host plants yet; "
                            "add caterpillar hosts",
                "empty":    "Food web   no host plants or bird support yet",
            }
            _fw_line = _food_web_msg.get(food_web.get("status"))
            if _fw_line:
                lines.append(_fw_line)
            # Coverage (V2.58). Absence of data must never read as absence of
            # relationships — the failure that made 16 native plants look like
            # a broken app rather than a thin catalogue.
            _scored = int(food_web.get("species_scored") or 0)
            _known = int(food_web.get("species_with_records") or 0)
            if _scored and _known < _scored:
                lines.append(
                    f"  Wildlife records exist for {_known} of your {_scored} "
                    f"species — the other {_scored - _known} are not known to "
                    f"support nothing, they are simply not recorded yet.")
        if result.gap_months:
            month_names = ["Jan","Feb","Mar","Apr","May","Jun",
                           "Jul","Aug","Sep","Oct","Nov","Dec"]
            lines.append(
                "  Gap months: " + ", ".join(month_names[m-1] for m in result.gap_months)
            )
            # Name the way through (F45). Reporting the gap and leaving the user
            # to find the plants that fill it was the complaint: "gap months are
            # shown for a design but there is no option to choose plants that
            # flower or fruit a particular month". There is one now.
            lines.append("    → Placement → Plants → “Blooms in…” to fill them")
        lines.append("")
        lines.append(f"Total {result.n_total_plants} plants, {result.n_species} species")

        # Estimated plant cost (schema v19) — a range, AB retail estimate.
        try:
            from src.sourcing import estimate_cost, format_cost
            low, high = estimate_cost(self._placed_plants)
            if high > 0:
                lines.append(
                    f"Est. plant cost    {format_cost(low, high)}   (AB retail estimate)")
        except Exception:  # noqa: BLE001 — cost is a nicety, never break the score
            pass

        self._habitat_breakdown.setText("\n".join(lines))

        # ── Tips: targeted suggestions for the lowest-scoring categories ──
        # Use the DB-backed id set (matches the pre-extraction behaviour
        # of keying off plant_rows.keys()).
        placed_ids = set(result.scored_plant_ids)
        tips_html = self._build_habitat_tips(
            native_ratio=result.native_ratio,
            n_keystone=len(result.keystone_species),
            n_host=len(result.host_species),
            n_bird=len(result.bird_species),
            layers_present=set(result.layers_present),
            habitat_struct_types=set(result.habitat_struct_types),
            gap_months=result.gap_months,
            placed_ids=placed_ids,
        )
        self._habitat_tips.setHtml(tips_html)

    # ── Species gallery (F11 / I1): photos of the design's high-value species ──

    def _gallery_species(self, result) -> list:
        """The design's species worth picturing, highest-value first (keystone →
        host → bird-food → other natives), limited to those with an image URL.
        Returns ``(name, cached_path_or_None, url, attribution, license)`` tuples."""
        from src.db.plants import get_plant
        from src.image_cache import get_cached_image
        recs: dict = {}
        for pid in getattr(result, "scored_plant_ids", None) or []:
            try:
                r = get_plant(pid)
            except Exception:  # noqa: BLE001
                r = None
            if r and r.get("image_url") and r.get("common_name"):
                recs.setdefault(r["common_name"], r)
        priority = (list(result.keystone_species) + list(result.host_species)
                    + list(result.bird_species))
        out: list = []
        seen: set = set()

        def _add(r):
            nm = r.get("common_name")
            if not nm or nm in seen:
                return
            seen.add(nm)
            url = r.get("image_url")
            out.append((nm, get_cached_image(url), url,
                        r.get("image_attribution", ""), r.get("image_license", "")))

        for nm in priority:
            if nm in recs:
                _add(recs[nm])
        for r in recs.values():
            if r.get("native_to_alberta"):
                _add(r)
        return out[:12]

    def _make_species_card(self, name: str, path: str,
                           attribution: str = "", license_str: str = "") -> QWidget:
        """A small thumbnail + caption card for one species. The photo credit is
        shown as the thumbnail's tooltip so CC-BY photos carry a visible credit,
        formatted by the one shared formatter (src/image_cache.credit_line)."""
        card = QWidget()
        v = QVBoxLayout(card)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(2)
        thumb = QLabel()
        thumb.setFixedSize(96, 72)
        thumb.setScaledContents(True)
        pm = QPixmap(path)
        if not pm.isNull():
            thumb.setPixmap(pm)
        from src.image_cache import credit_line
        credit = credit_line(attribution, license_str)
        if credit:
            thumb.setToolTip(credit)
        thumb.setStyleSheet("border: 1px solid #2e4a2e; border-radius: 3px;")
        cap = QLabel(name)
        cap.setWordWrap(True)
        cap.setFixedWidth(96)
        cap.setStyleSheet("color: #c8e6c9; font-size: 12px;")
        v.addWidget(thumb)
        v.addWidget(cap)
        return card

    def _fauna_gallery_species(self, result) -> list:
        """The fauna the design supports, deduped, limited to those with an image
        URL. Returns ``(name, cached_path_or_None, url, attribution, license)``."""
        from src.db.fauna import fauna_for_plants
        from src.image_cache import get_cached_image
        ids = list(getattr(result, "scored_plant_ids", None) or [])
        if not ids:
            return []
        try:
            rows = fauna_for_plants(ids)
        except Exception:  # noqa: BLE001
            return []
        out: list = []
        seen: set = set()
        for f in rows:
            nm = f.get("common_name")
            url = f.get("image_url")
            key = f.get("id") if f.get("id") is not None else nm
            if not nm or not url or key in seen:
                continue
            seen.add(key)
            out.append((nm, get_cached_image(url), url,
                        f.get("image_attribution", ""), f.get("image_license", "")))
        return out[:12]

    def _fill_gallery(self, label, area, row, items) -> list:
        """Fill one gallery strip: cached photos become cards now; the rest are
        returned as ``(url, attr, lic)`` pending tuples to warm. Shows the strip
        only when at least one photo is ready."""
        while row.count() > 1:                       # keep the trailing stretch
            it = row.takeAt(0)
            w = it.widget()
            if w is not None:
                w.deleteLater()
        pending: list = []
        shown = 0
        for name, path, url, attr, lic in items:
            if path:
                row.insertWidget(row.count() - 1,
                                 self._make_species_card(name, path, attr, lic))
                shown += 1
            elif url and url not in self._gallery_warmed:
                pending.append((url, attr, lic))
        label.setVisible(shown > 0)
        area.setVisible(shown > 0)
        return pending

    def _render_galleries(self, result):
        """Render both photo strips (plants doing the work + fauna supported),
        warming any not-yet-cached photos; the strips re-render as they land."""
        pending = self._fill_gallery(
            self._species_gallery_label, self._species_gallery,
            self._species_gallery_row, self._gallery_species(result))
        pending += self._fill_gallery(
            self._fauna_gallery_label, self._fauna_gallery,
            self._fauna_gallery_row, self._fauna_gallery_species(result))
        if pending:
            for url, _attr, _lic in pending:
                self._gallery_warmed.add(url)
            self._warm_gallery_images(pending)

    def _warm_gallery_images(self, pending: list):
        """Fetch+cache the not-yet-cached species photos off the UI thread,
        re-rendering the strip as each lands (mirrors plant_list_view's warm)."""
        # Bind the OWNER, not its bound signal — see src/qt_safety.py. A
        # gallery warm that lands after the panel is gone used to emit into
        # freed memory.
        owner = self

        class _FetchTask(QRunnable):
            def __init__(self, url, attr, lic):
                super().__init__()
                self._url, self._attr, self._lic = url, attr, lic

            def run(self):
                try:
                    from src.image_cache import resolve_image
                    from src.qt_safety import emit_if_alive
                    if resolve_image(self._url, self._attr, self._lic):
                        emit_if_alive(owner, "galleryImageReady")
                except Exception:  # noqa: BLE001 — a missing photo is not an error
                    pass

        for url, attr, lic in pending:
            QThreadPool.globalInstance().start(_FetchTask(url, attr, lic))

    def _on_gallery_image_ready(self):
        res = self._last_habitat_result
        if res is not None:
            try:
                self._render_galleries(res)
            except Exception:  # noqa: BLE001
                pass

    # Canonical layer names paired with the plant_types that fulfil them.
    _LAYER_TO_PLANT_TYPES = {
        "overstory":   ["tree"],
        "shrub":       ["shrub"],
        "herbaceous":  ["herb", "root"],
        "groundcover": ["groundcover"],
        "vine":        ["vine"],
    }

    _STRUCTURE_NAMES = {
        "pond":             "Pond",
        "swale":            "Bioswale",
        "rain_garden":      "Rain Garden",
        "rain_barrel":      "Rain Barrel",
        "native_bee_log":   "Native Bee Habitat Log",
        "bee_hotel":        "Bee Hotel",
        "brush_pile":       "Brush Pile",
        "snag":             "Snag (standing deadwood)",
        "rock_xeriscape":   "Rock Xeriscape",
        "native_lawn_patch":"Native Lawn Patch",
    }

    def _build_habitat_tips(
        self, *,
        native_ratio: float,
        n_keystone: int,
        n_host: int,
        n_bird: int,
        layers_present: set[str],
        habitat_struct_types: set[str],
        gap_months: list[int],
        placed_ids: set[int],
    ) -> str:
        """Return an HTML string of targeted tips for raising the habitat
        score. Each suggestion lists concrete Alberta-native examples
        pulled from the plant DB, excluding species already in the design."""
        try:
            from src.db.plants import get_connection
            conn = get_connection()
        except Exception:
            return "<p style='color:#90a4ae;'>Tips unavailable — plant DB not loaded.</p>"

        def examples_for_tag(tag: str, limit: int = 5) -> list[str]:
            """Native AB plants tagged `tag`, not yet placed, alphabetical.

            Schema v13: resolved via the plant_uses junction so the query
            is index-driven instead of a full-table LIKE scan.
            """
            sql = (
                "SELECT p.common_name FROM plants p "
                "JOIN plant_uses pu ON pu.plant_id = p.id "
                "JOIN uses u ON u.id = pu.use_id "
                "WHERE p.native_to_alberta = 1 AND u.key = ?"
            )
            params: list = [tag]
            if placed_ids:
                sql += " AND p.id NOT IN (" + ",".join("?" * len(placed_ids)) + ")"
                params += list(placed_ids)
            sql += " ORDER BY p.common_name"
            try:
                rows = conn.execute(sql, params).fetchall()
            except Exception:
                return []
            return [r["common_name"] for r in rows][:limit]

        def examples_for_layer(layer: str, limit: int = 5) -> list[str]:
            ptypes = self._LAYER_TO_PLANT_TYPES.get(layer, [])
            if not ptypes:
                return []
            placeholders = ",".join("?" * len(ptypes))
            sql = (
                "SELECT common_name FROM plants "
                f"WHERE native_to_alberta = 1 AND plant_type IN ({placeholders})"
            )
            params: list = list(ptypes)
            if placed_ids:
                sql += " AND id NOT IN (" + ",".join("?" * len(placed_ids)) + ")"
                params += list(placed_ids)
            sql += " ORDER BY common_name"
            try:
                rows = conn.execute(sql, params).fetchall()
            except Exception:
                return []
            return [r["common_name"] for r in rows][:limit]

        def examples_for_bloom_month(month_num: int, limit: int = 4) -> list[str]:
            """Native AB plants whose bloom_period covers `month_num`."""
            try:
                rows = conn.execute(
                    "SELECT common_name, bloom_period FROM plants "
                    "WHERE native_to_alberta = 1 AND bloom_period IS NOT NULL "
                    "  AND bloom_period <> ''"
                ).fetchall()
            except Exception:
                return []
            matches = []
            for r in rows:
                if month_num in self._parse_month_range(r["bloom_period"] or ""):
                    if r["common_name"] not in matches:
                        matches.append(r["common_name"])
            # Cheap filter against placed names (best-effort: we don't have
            # ids here, so we compare by name)
            placed_names: set[str] = set()
            if placed_ids:
                try:
                    qmarks = ",".join("?" * len(placed_ids))
                    placed_rows = conn.execute(
                        f"SELECT common_name FROM plants WHERE id IN ({qmarks})",
                        list(placed_ids)
                    ).fetchall()
                    placed_names = {r["common_name"] for r in placed_rows}
                except Exception:
                    pass
            matches = [m for m in matches if m not in placed_names]
            matches.sort()
            return matches[:limit]

        try:
            tips: list[str] = []
            month_names = ["Jan","Feb","Mar","Apr","May","Jun",
                           "Jul","Aug","Sep","Oct","Nov","Dec"]

            if native_ratio < 0.70:
                pct = int(round(native_ratio * 100))
                tips.append(
                    f"<b style='color:#a5d6a7;'>Lift the native ratio ({pct}%).</b> "
                    f"Every cultivar you swap for an Alberta native raises this score "
                    f"directly. Aim for 70%+ native — that's the Tallamy threshold for "
                    f"functional habitat."
                )

            if n_keystone < 5:
                examples = examples_for_tag("keystone_species")
                if examples:
                    tips.append(
                        f"<b style='color:#a5d6a7;'>Add keystone species "
                        f"({n_keystone} of 5).</b> Keystones support the bulk of local "
                        f"insect biodiversity. Try: {', '.join(examples)}."
                    )

            if n_host < 10:
                examples = examples_for_tag("host_plant")
                if examples:
                    tips.append(
                        f"<b style='color:#a5d6a7;'>Add host plants "
                        f"({n_host} of 10).</b> Specialist caterpillars need specific "
                        f"native hosts. Try: {', '.join(examples)}."
                    )

            if n_bird < 10:
                examples = examples_for_tag("bird_food")
                if examples:
                    tips.append(
                        f"<b style='color:#a5d6a7;'>Add bird-food species "
                        f"({n_bird} of 10).</b> Berries, seed heads, and cones feed "
                        f"resident and migratory birds. Try: {', '.join(examples)}."
                    )

            missing_layers = {"overstory","shrub","herbaceous","groundcover","vine"} - layers_present
            # Vine is often optional; surface it last
            order = ["overstory","shrub","herbaceous","groundcover","vine"]
            for layer in order:
                if layer not in missing_layers:
                    continue
                examples = examples_for_layer(layer)
                if not examples:
                    continue
                tips.append(
                    f"<b style='color:#a5d6a7;'>Add a {layer} layer.</b> "
                    f"Try: {', '.join(examples)}."
                )

            missing_structs = [
                sid for sid in self._HABITAT_STRUCTURE_IDS
                if sid not in habitat_struct_types
            ]
            if len(habitat_struct_types) < 5 and missing_structs:
                names = [self._STRUCTURE_NAMES.get(s, s) for s in missing_structs[:5]]
                tips.append(
                    f"<b style='color:#a5d6a7;'>Add habitat structures "
                    f"({len(habitat_struct_types)} of 5).</b> Structural diversity "
                    f"shelters wildlife year-round. Try: {', '.join(names)}."
                )

            if gap_months:
                gap_lines = []
                for m in gap_months[:3]:  # cap at 3 most-urgent gaps
                    examples = examples_for_bloom_month(m)
                    if examples:
                        gap_lines.append(
                            f"<i>{month_names[m-1]}:</i> {', '.join(examples)}"
                        )
                if gap_lines:
                    tips.append(
                        "<b style='color:#a5d6a7;'>Fill nectar gaps.</b> "
                        "Plants blooming in the gap months — "
                        + "; ".join(gap_lines)
                    )

            if not tips:
                return (
                    "<p style='color:#a5d6a7;'>You're hitting every category. "
                    "Keep adding species diversity and small structural elements "
                    "(snags, brush piles, water features) as your habitat matures.</p>"
                )

            body = "<ul style='margin:0;padding-left:18px;'>"
            for t in tips:
                body += f"<li style='margin-bottom:6px;'>{t}</li>"
            body += "</ul>"
            return body
        finally:
            conn.close()

    @staticmethod
    def _parse_month_range(text: str) -> list[int]:
        """Parse 'June-August' / 'May' style strings to month numbers (1-12).

        Thin delegate to src.habitat_score.parse_month_range so the panel's
        bloom-month tips and the score's bloom component use identical
        parsing."""
        from src.habitat_score import parse_month_range
        return parse_month_range(text)

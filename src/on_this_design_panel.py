"""
on_this_design_panel.py — The "On this design" review tab.

Split out of ``src/plant_panel.py`` in Chunk 4 of the strengthening plan.
Pure structural move: ``OnThisDesignPanel`` is now standalone and lives
beside the plant browser instead of inside it.

Three sub-tabs:
  • Plants — species → count (driven by PlantPanel._placed_counts).
  • Communities — community-name → instance count + member count.
  • Stats — species count, Alberta-native %, layer / function tallies.

App.py owns the instance and drives both inputs:
``set_plants_counts(plant_panel._placed_counts)`` whenever the Plants
tab signals ``placed_counts_changed``; ``set_design_data(enriched)``
inside ``_sync_planning_panel`` for Communities + Stats.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QListWidget, QListWidgetItem, QMenu,
    QSizePolicy,
)

from src.plant_list_view import _RESULTS_LIST_STYLE, _type_icon


class OnThisDesignPanel(QWidget):
    """Third inner tab (sibling of Plants and Plant Communities) reviewing
    what's currently placed. Three sub-tabs:

    - **Plants**: species → count.
    - **Communities**: community name → number of instances on the map.
    - **Stats**: species count, native %, layer breakdown, ecological-
      function tags.

    App.py owns the instance and drives both inputs:
    ``set_plants_counts(plant_panel._placed_counts)`` whenever the Plants
    tab signals ``placed_counts_changed``; ``set_design_data(enriched)``
    inside ``_sync_planning_panel`` for Communities + Stats.

    V2.13: the lists are an instrument, not a readout — clicking a species
    or community row locates it on the map, and the species context menu
    selects / removes / opens it in the Plant Library. The panel only emits;
    app.py wires the signals to ``design_review_flow``."""

    species_focus_requested = pyqtSignal(int)            # click → select+zoom
    species_select_requested = pyqtSignal(int)           # ctx: select on map
    species_remove_requested = pyqtSignal(int)           # ctx: remove all (confirmed downstream)
    species_show_in_library_requested = pyqtSignal(int)  # ctx: Plant Library
    community_focus_requested = pyqtSignal(str)          # click → zoom to members
    open_habitat_analysis_requested = pyqtSignal()       # Stats: habitat value → Analysis
    open_planning_requested = pyqtSignal()               # Stats: cost → Planning

    def __init__(self, parent=None):
        super().__init__(parent)
        from PyQt6.QtWidgets import QTabWidget, QTextBrowser
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(2)
        from src.fill_tab_widget import FillTabWidget
        self._tabs = FillTabWidget()
        self._tabs.setStyleSheet(
            "QTabWidget::pane { border: 1px solid #2e4a2e; background: #1a2a1a; }"
            "QTabBar::tab { background: #1e2e1e; color: #a5d6a7; "
            "padding: 3px 10px; border: 1px solid #2e4a2e; "
            "border-bottom: none; font-size: 11px; }"
            "QTabBar::tab:selected { background: #2e4a2e; color: #e8f5e9; }"
        )
        root.addWidget(self._tabs)

        # Plants sub-tab
        plants_widget = QWidget()
        pl = QVBoxLayout(plants_widget)
        pl.setContentsMargins(2, 2, 2, 2)
        pl.setSpacing(2)
        self._plants_count_label = QLabel("None placed yet")
        self._plants_count_label.setStyleSheet("color: #78909c; font-size: 11px;")
        pl.addWidget(self._plants_count_label)
        self._plants_list = QListWidget()
        self._plants_list.setMinimumHeight(60)
        self._plants_list.setStyleSheet(_RESULTS_LIST_STYLE)
        self._plants_list.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._plants_list.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self._plants_list.setToolTip(
            "Click a species to select and frame it on the map;\n"
            "right-click for select / remove / open in Plant Library.")
        self._plants_list.itemClicked.connect(self._on_plant_row_clicked)
        self._plants_list.setContextMenuPolicy(
            Qt.ContextMenuPolicy.CustomContextMenu)
        self._plants_list.customContextMenuRequested.connect(
            self._on_plant_row_menu)
        pl.addWidget(self._plants_list, 1)
        self._tabs.addTab(plants_widget, "Plants")

        # Communities sub-tab
        communities_widget = QWidget()
        cl = QVBoxLayout(communities_widget)
        cl.setContentsMargins(2, 2, 2, 2)
        cl.setSpacing(2)
        self._communities_count_label = QLabel("No communities placed yet")
        self._communities_count_label.setStyleSheet(
            "color: #78909c; font-size: 11px;"
        )
        cl.addWidget(self._communities_count_label)
        self._communities_list = QListWidget()
        self._communities_list.setMinimumHeight(60)
        self._communities_list.setStyleSheet(_RESULTS_LIST_STYLE)
        self._communities_list.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._communities_list.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self._communities_list.setToolTip(
            "Click a community to frame its placed members on the map.")
        self._communities_list.itemClicked.connect(
            self._on_community_row_clicked)
        cl.addWidget(self._communities_list, 1)
        self._tabs.addTab(communities_widget, "Communities")

        # Stats sub-tab
        stats_widget = QWidget()
        sl = QVBoxLayout(stats_widget)
        sl.setContentsMargins(2, 2, 2, 2)
        sl.setSpacing(2)
        self._stats_text = QTextBrowser()
        self._stats_text.setStyleSheet(
            "QTextBrowser { background: #1a2a1a; color: #c8e6c9; "
            "border: 1px solid #2e4a2e; border-radius: 4px; font-size: 12px; }"
        )
        # Deep-links: the habitat-value and cost headings are anchors into the
        # Analysis and Planning tabs (V2.13). Handle them ourselves rather than
        # letting QTextBrowser try to navigate to a made-up URL.
        self._stats_text.setOpenLinks(False)
        self._stats_text.anchorClicked.connect(self._on_stats_anchor)
        sl.addWidget(self._stats_text, 1)
        self._tabs.addTab(stats_widget, "Stats")

        # Latest enriched snapshot — stashed so Stats can refresh without
        # the caller re-pushing it.
        self._latest_enriched: list[dict] = []
        # Whole-design cost breakdown (C1) — set by app.py via set_cost_breakdown.
        self._cost_breakdown: dict | None = None
        # Habitat Value Score (F11) — set by app.py via set_habitat_value, so the
        # Stats tab shows what the design is worth, not only what it costs.
        self._habitat_value = None
        # Lawn-conversion zone summary (N2) — set via set_lawn_conversion.
        self._lawn_conversion: dict | None = None

    # ── Plants sub-tab ────────────────────────────────────────────────

    def set_plants_counts(self, counts: dict):
        self._plants_list.clear()
        if not counts:
            self._plants_count_label.setText("None placed yet")
            return
        try:
            from src.db.plants import get_plant
            total = 0
            for pid, count in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])):
                p = get_plant(pid)
                name = p["common_name"] if p else f"Plant #{pid}"
                item = QListWidgetItem(f"{name}  ×{count}")
                item.setIcon(_type_icon(p["plant_type"] if p else ""))
                item.setData(Qt.ItemDataRole.UserRole, int(pid))
                self._plants_list.addItem(item)
                total += count
            self._plants_count_label.setText(
                f"{total} plant{'s' if total != 1 else ''} placed"
                f" ({len(counts)} species) · click a row to find it"
            )
        except Exception:
            self._plants_count_label.setText(
                f"{sum(counts.values())} plants placed"
            )

    # ── Row interactions (V2.13) ──────────────────────────────────────

    def _on_plant_row_clicked(self, item: QListWidgetItem):
        pid = item.data(Qt.ItemDataRole.UserRole)
        if pid is not None:
            self.species_focus_requested.emit(int(pid))

    def _on_plant_row_menu(self, pos):
        item = self._plants_list.itemAt(pos)
        if item is None:
            return
        pid = item.data(Qt.ItemDataRole.UserRole)
        if pid is None:
            return
        pid = int(pid)
        menu = QMenu(self._plants_list)
        act_focus = menu.addAction("Zoom to on map")
        act_select = menu.addAction("Select on map")
        act_library = menu.addAction("Show in Plant Library")
        menu.addSeparator()
        act_remove = menu.addAction("Remove all from design…")
        chosen = menu.exec(self._plants_list.mapToGlobal(pos))
        if chosen is act_focus:
            self.species_focus_requested.emit(pid)
        elif chosen is act_select:
            self.species_select_requested.emit(pid)
        elif chosen is act_library:
            self.species_show_in_library_requested.emit(pid)
        elif chosen is act_remove:
            self.species_remove_requested.emit(pid)

    def _on_community_row_clicked(self, item: QListWidgetItem):
        name = item.data(Qt.ItemDataRole.UserRole)
        if name:
            self.community_focus_requested.emit(str(name))

    def _on_stats_anchor(self, url):
        """Route a Stats deep-link (custom sap: scheme) to the right tab."""
        target = url.toString()
        if target == "sap:analysis-habitat":
            self.open_habitat_analysis_requested.emit()
        elif target == "sap:planning":
            self.open_planning_requested.emit()

    # ── Communities + Stats sub-tabs ──────────────────────────────────

    def set_design_data(self, enriched: list[dict]):
        """Refresh Communities + Stats sub-tabs from the full enriched
        list of placed-plant features. Each entry should carry at least
        ``plant_id`` and (for community grouping) ``polyculture_name`` +
        ``polyculture_center_lat`` / ``polyculture_center_lng``."""
        self._latest_enriched = list(enriched or [])
        self._refresh_communities(enriched or [])
        self._refresh_stats(enriched or [])

    def _refresh_communities(self, enriched: list[dict]):
        self._communities_list.clear()
        # Group by community name; count distinct (centre lat, centre lng)
        # pairs per name to get instance count, plus total member count.
        from collections import defaultdict
        instances: dict[str, set] = defaultdict(set)
        member_counts: dict[str, int] = defaultdict(int)
        for p in enriched:
            name = (p.get("polyculture_name") or "").strip()
            if not name:
                continue
            clat = p.get("polyculture_center_lat")
            clng = p.get("polyculture_center_lng")
            key = (round(float(clat), 6), round(float(clng), 6)) if (
                clat is not None and clng is not None
            ) else p.get("placement_group_id")
            instances[name].add(key)
            member_counts[name] += 1
        if not instances:
            self._communities_count_label.setText("No communities placed yet")
            return
        for name in sorted(instances.keys(), key=str.lower):
            n_inst = len(instances[name])
            n_mem = member_counts[name]
            item = QListWidgetItem(
                f"{name}  — {n_inst} instance{'s' if n_inst != 1 else ''}"
                f", {n_mem} member{'s' if n_mem != 1 else ''}"
            )
            item.setData(Qt.ItemDataRole.UserRole, name)
            self._communities_list.addItem(item)
        total_inst = sum(len(v) for v in instances.values())
        self._communities_count_label.setText(
            f"{total_inst} community instance{'s' if total_inst != 1 else ''} "
            f"across {len(instances)} community name"
            f"{'s' if len(instances) != 1 else ''}"
        )

    def set_cost_breakdown(self, breakdown: dict | None):
        """Store the whole-design cost breakdown (from ``sourcing.design_cost``)
        and refresh the Stats tab. Keys ``plants``/``structures``/``mulch``/
        ``total`` each map to a ``(low, high)`` CAD tuple."""
        self._cost_breakdown = breakdown or None
        self._refresh_stats(self._latest_enriched)

    def set_habitat_value(self, score):
        """Store the Habitat Value Score (from ``habitat_score.compute_habitat_score``)
        and refresh the Stats tab. ``score`` is the HabitatScore result, or None
        (e.g. nothing placed / DB unavailable) — the value block then hides."""
        self._habitat_value = score
        self._refresh_stats(self._latest_enriched)

    def set_lawn_conversion(self, summary: dict | None):
        """Store the lawn-conversion zone summary (from
        ``lawn_zones.conversion_summary``) and refresh the Stats tab."""
        self._lawn_conversion = summary or None
        self._refresh_stats(self._latest_enriched)

    def _value_block_html(self) -> str:
        """The habitat-value half of value-vs-price (F11, P6): what the design is
        worth, shown directly above the cost so the two read together."""
        sc = self._habitat_value
        if not sc:
            return ""
        total = int(round(getattr(sc, "total", 0) or 0))
        grade = getattr(sc, "grade", "") or ""
        head = f"{total}/100" + (f" ({grade})" if grade else "")
        bits = []
        ns, n = getattr(sc, "native_species", 0), getattr(sc, "n_species", 0)
        if n:
            bits.append(f"{ns} of {n} plants native")
        fbt = getattr(sc, "fauna_by_taxon", None)
        if fbt:
            n_wild = sum(fbt.values())
            if n_wild:
                bits.append(f"{n_wild} wildlife species supported")
        host = getattr(sc, "host_species", None) or []
        if host:
            bits.append(f"{len(host)} caterpillar host plants")
        parts = [
            "<p><a href='sap:analysis-habitat' "
            "style='color:#a5d6a7;text-decoration:none;'>"
            f"<b>Habitat value</b> ›</a><br>{head}"
        ]
        if bits:
            parts.append("<br><span style='color:#90a4ae;font-size:10px;'>"
                         + ", ".join(bits) + "</span>")
        parts.append("</p>")
        return "".join(parts)

    def _nudges_block_html(self) -> str:
        """The 'what would help most' list (F11 companion, P6/P9): the design's
        biggest ecological gaps as ranged, actionable suggestions — so the
        score reads as a to-do list, not a verdict."""
        sc = self._habitat_value
        if not sc:
            return ""
        try:
            from src.habitat_score import habitat_nudges
            nudges = habitat_nudges(sc, limit=3)
        except Exception:
            return ""
        if not nudges:
            return ("<p><b>Where to grow next</b><br>"
                    "<span style='color:#a5d6a7;font-size:10px;'>"
                    "This design already covers the habitat basics — nice "
                    "work.</span></p>")
        items = "".join(
            f"<li style='margin-bottom:3px;'>{nd['text']}</li>"
            for nd in nudges)
        return ("<p><b>Where to grow next</b>"
                "<ul style='margin:2px 0 0 0;color:#c8e6c9;font-size:11px;'>"
                f"{items}</ul></p>")

    def _value_framing_html(self) -> str:
        """One line that reads cost and habitat value together (F11, P6): the
        spend isn't a cost, it's what buys the wildlife value above. Shown only
        when both a cost total and a habitat score are present."""
        bd = self._cost_breakdown
        sc = self._habitat_value
        if not bd or not sc or not bd.get("total"):
            return ""
        creates = []
        fbt = getattr(sc, "fauna_by_taxon", None)
        if fbt:
            n_wild = sum(fbt.values())
            if n_wild:
                creates.append(f"{n_wild} wildlife species supported")
        ns = getattr(sc, "native_species", 0)
        if ns:
            creates.append(f"{ns} native species")
        n_struct = len(getattr(sc, "habitat_struct_types", []) or [])
        if n_struct:
            creates.append(f"{n_struct} habitat structure"
                           f"{'s' if n_struct != 1 else ''}")
        if not creates:
            return ""
        return ("<p style='color:#90a4ae;font-size:10px;margin-top:2px;'>"
                "What your spend creates: " + ", ".join(creates) + ".</p>")

    def _lawn_block_html(self) -> str:
        s = self._lawn_conversion
        if not s or s.get("total_zone_m2", 0) <= 0:
            return ""
        from src.lawn_zones import ZONE_TYPES

        def area(m2):
            return f"{m2:,.0f} m²" if m2 < 10000 else f"{m2 / 10000:.2f} ha"

        parts = [
            "<p><b>Lawn conversion</b><br>",
            f"Converted: {area(s['converted_m2'])} "
            f"({s['pct_converted']:.0f}% of lawn+restoration)<br>",
            f"Lawn remaining: {area(s['lawn_remaining_m2'])}<br>",
        ]
        by = s.get("by_zone", {})
        rows = [f"{spec['label']}: {area(by[key])}"
                for key, spec in ZONE_TYPES.items() if by.get(key, 0) > 0]
        if rows:
            parts.append("<span style='color:#90a4ae;font-size:10px;'>"
                         + " · ".join(rows) + "</span>")
        parts.append("</p>")
        return "".join(parts)

    def _cost_block_html(self) -> str:
        bd = self._cost_breakdown
        if not bd:
            return ""
        from src.sourcing import format_cost

        def row(label: str, key: str) -> str:
            v = bd.get(key)
            return f"{label}: {format_cost(v[0], v[1])}<br>" if v else ""

        parts = ["<p><a href='sap:planning' "
                 "style='color:#a5d6a7;text-decoration:none;'>"
                 "<b>Estimated cost (CAD)</b> ›</a><br>",
                 row("Plants", "plants")]
        # Per-type breakdown so the plant total isn't one intimidating number,
        # with the math shown — count × per-plant range (F2 + R4).
        type_costs = bd.get("type_costs") or {}
        if type_costs:
            _LABELS = {"tree": "Trees", "shrub": "Shrubs", "vine": "Vines",
                       "herb": "Herbaceous", "grass": "Grasses",
                       "groundcover": "Groundcover", "root": "Roots/bulbs"}
            chips = []
            for t, v in sorted(type_costs.items(), key=lambda kv: -kv[1][1]):
                lo, hi = v[0], v[1]
                count = v[2] if len(v) > 2 else 0
                if hi <= 0:
                    continue
                label = _LABELS.get(t, t.replace("_", " ").title())
                if count:
                    each = format_cost(lo / count, hi / count)
                    chips.append(f"{label} {format_cost(lo, hi)} "
                                 f"({count} × {each} ea)")
                else:
                    chips.append(f"{label} {format_cost(lo, hi)}")
            if chips:
                parts.append("<span style='color:#90a4ae;font-size:10px;'>&nbsp;&nbsp;"
                             + "<br>&nbsp;&nbsp;".join(chips) + "</span><br>")
        if bd.get("structures") and bd["structures"][1] > 0:
            parts.append(row("Structures", "structures"))
        if bd.get("mulch") and bd["mulch"][1] > 0:
            parts.append(row("Mulch", "mulch"))
        tot = bd.get("total")
        if tot:
            parts.append(f"<b>Total: {format_cost(tot[0], tot[1])}</b>")
        parts.append(
            "<br><span style='color:#78909c;font-size:10px;'>AB retail/install "
            "estimate — varies by nursery, year, site.</span></p>"
        )
        return "".join(parts)

    def _refresh_stats(self, enriched: list[dict]):
        value_html = self._value_block_html()
        nudges_html = self._nudges_block_html()
        cost_html = self._cost_block_html()
        framing_html = self._value_framing_html()
        lawn_html = self._lawn_block_html()
        if not enriched:
            body = "<i style='color:#78909c;'>Nothing placed yet.</i>"
            self._stats_text.setHtml(
                body + lawn_html + value_html + nudges_html
                + cost_html + framing_html)
            return
        from src.db.plants import get_plant
        total = len(enriched)
        species: set = set()
        native = 0
        layer_counts: dict[str, int] = {}
        function_counts: dict[str, int] = {}
        type_counts: dict[str, int] = {}
        plant_cache: dict[int, dict] = {}
        for p in enriched:
            pid = p.get("plant_id")
            if not pid:
                continue
            species.add(int(pid))
            plant = plant_cache.get(pid)
            if plant is None:
                try:
                    plant = get_plant(pid) or {}
                except Exception:
                    plant = {}
                plant_cache[pid] = plant
            if plant.get("native_to_alberta") or p.get("native_to_alberta"):
                native += 1
            ptype = (plant.get("plant_type") or p.get("plant_type") or "").lower()
            if ptype:
                type_counts[ptype] = type_counts.get(ptype, 0) + 1
            # Layer + function tags only stamp on community members, but
            # try to surface them when present (the bare-plant case
            # simply contributes nothing to layer/function tallies).
            layer = (p.get("layer") or "").lower()
            if layer:
                layer_counts[layer] = layer_counts.get(layer, 0) + 1
            for fn in (p.get("functions") or []):
                key = str(fn).lower()
                function_counts[key] = function_counts.get(key, 0) + 1
        native_pct = (100.0 * native / total) if total else 0.0
        rows: list[str] = []
        rows.append(
            f"<p><b>{total}</b> plants placed · "
            f"<b>{len(species)}</b> species · "
            f"<b>{native_pct:.0f}%</b> Alberta-native</p>"
        )
        if type_counts:
            rows.append("<p><b>Plant types</b><br>")
            rows.append(
                ", ".join(
                    f"{t.replace('_', ' ')}: {n}"
                    for t, n in sorted(type_counts.items(), key=lambda kv: -kv[1])
                )
            )
            rows.append("</p>")
        if layer_counts:
            rows.append("<p><b>Vegetation layers</b><br>")
            rows.append(
                ", ".join(
                    f"{l.replace('_', ' ')}: {n}"
                    for l, n in sorted(layer_counts.items(), key=lambda kv: -kv[1])
                )
            )
            rows.append("</p>")
        if function_counts:
            rows.append("<p><b>Ecological functions</b><br>")
            rows.append(
                ", ".join(
                    f"{f.replace('_', ' ')}: {n}"
                    for f, n in sorted(function_counts.items(), key=lambda kv: -kv[1])
                )
            )
            rows.append("</p>")
        rows.append(lawn_html)
        rows.append(value_html)
        rows.append(nudges_html)
        rows.append(cost_html)
        rows.append(framing_html)
        self._stats_text.setHtml("".join(rows))

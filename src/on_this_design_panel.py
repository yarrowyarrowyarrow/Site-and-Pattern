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

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QListWidget, QListWidgetItem, QSizePolicy,
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
    inside ``_sync_planning_panel`` for Communities + Stats."""

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
        sl.addWidget(self._stats_text, 1)
        self._tabs.addTab(stats_widget, "Stats")

        # Latest enriched snapshot — stashed so Stats can refresh without
        # the caller re-pushing it.
        self._latest_enriched: list[dict] = []

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
                self._plants_list.addItem(item)
                total += count
            self._plants_count_label.setText(
                f"{total} plant{'s' if total != 1 else ''} placed"
                f" ({len(counts)} species)"
            )
        except Exception:
            self._plants_count_label.setText(
                f"{sum(counts.values())} plants placed"
            )

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
            self._communities_list.addItem(item)
        total_inst = sum(len(v) for v in instances.values())
        self._communities_count_label.setText(
            f"{total_inst} community instance{'s' if total_inst != 1 else ''} "
            f"across {len(instances)} community name"
            f"{'s' if len(instances) != 1 else ''}"
        )

    def _refresh_stats(self, enriched: list[dict]):
        if not enriched:
            self._stats_text.setHtml(
                "<i style='color:#78909c;'>Nothing placed yet.</i>"
            )
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
        self._stats_text.setHtml("".join(rows))

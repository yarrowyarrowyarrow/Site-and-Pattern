"""
food_page.py — Design › Food: who the design feeds, one animal at a time, and
the year month by month, people kept apart (V3.08).

Design principle P10 — see docs/DESIGN_PHILOSOPHY.md.

The owner's "what it feeds" page, from the V3.05 surface audit: Analysis › Bees
merged in ("a per species analysis but not one limited to just bees") with
Planning's Wildlife and Harvest calendars ("clear and distinct what is human
forage and what is animal forage"). Three parts:

  * a line saying how many animals the design feeds, by group;
  * **one animal**: any of the catalogue's, those the design already feeds
    first. A bee keeps everything the Bees page said (``bee_habitat``: tongue
    fit, nesting, its flight season); any other animal gets the plants that
    feed it here and how, the catalogue plants that would, and the months it
    finds food here (``what_it_feeds.animal_plan``). *Show it on the map*
    greys every plant that does not feed it;
  * **month by month**: one tree, each month in three groups, for pollinators,
    for birds and **for people**, the last in its own colour and always last.

The arithmetic is ``src/what_it_feeds.py`` and ``src/bee_habitat.py``; this
only draws. The page fills itself when it is on screen and the design changes
(the Design tab's ``LiveRefresh``).
"""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QPixmap
from PyQt6.QtWidgets import (
    QComboBox, QFrame, QHBoxLayout, QHeaderView, QLabel, QLineEdit,
    QPushButton, QScrollArea, QTreeWidget, QTreeWidgetItem, QVBoxLayout,
    QWidget,
)

from src import what_it_feeds as feeds

_MONTHS = ("January", "February", "March", "April", "May", "June", "July",
           "August", "September", "October", "November", "December")

#: Tongue-fit chips for a bee's floral hosts (moved with the Bees page).
_FIT_CHIP = {
    "good":      ("#1b5e20", "#a5d6a7", "good fit"),
    "plausible": ("#33450f", "#dcedc8", "workable"),
    "unknown":   ("#37474f", "#b0bec5", "—"),
}

#: The three groups of a month, in order: people last, in their own colour.
_GROUP_ROWS = (
    ("pollinators", "For pollinators: flowers", "#ce93d8"),
    ("birds", "For birds: fruit and seed", "#ffcc80"),
    ("people", "For people: what you can harvest", "#80deea"),
)

_BODY_STYLE = ("color: #c8e6c9; font-size: 12px; padding: 8px; "
               "background: #1a2a1a; border: 1px solid #2e4a2e; "
               "border-radius: 4px;")
_HEAD_STYLE = ("color: #a5d6a7; font-size: 13px; font-weight: bold; "
               "padding: 8px 0 2px 0;")
_TREE_STYLE = (
    "QTreeWidget { background: #1a2a1a; border: 1px solid #2e4a2e; "
    "color: #c8e6c9; font-size: 12px; }"
    "QTreeWidget::item { padding: 2px; }"
    "QTreeWidget::item:selected { background: #2e5a2e; }"
    "QHeaderView::section { background: #1e2e1e; color: #a5d6a7; "
    "border: none; padding: 3px; }")


class FoodPage(QScrollArea):
    """Design › Food. ``warm_images`` fetches photographs off the UI thread
    (the Design tab's photo warmer); call :meth:`on_image_ready` when one
    lands."""

    map_overlay_requested = pyqtSignal(dict)   # {"bee": label, "styles": {pid: fit}}
    map_overlay_cleared = pyqtSignal()

    def __init__(self, warm_images=None, parent=None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self._warm = warm_images
        self._warmed: set = set()
        self._plant_ids: list = []
        self._plan = None            # the bee plan or the animal plan shown
        self._plan_is_bee = False
        self._fed: list = []
        self._catalogue = None       # the catalogue's animals, read once
        # Until a person picks one, the page shows the animal the design
        # feeds most; after, it keeps theirs while the design changes.
        self._user_chose = False
        body = QWidget()
        self.setWidget(body)
        layout = QVBoxLayout(body)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(6)

        self._summary_line = QLabel("")
        self._summary_line.setWordWrap(True)
        self._summary_line.setStyleSheet("color: #c8e6c9; font-size: 13px;")
        layout.addWidget(self._summary_line)

        # ── One animal ──────────────────────────────────────────────────────
        layout.addWidget(self._heading("One animal"))
        self._find = QLineEdit()
        self._find.setPlaceholderText("Find an animal…")
        self._find.setAccessibleName("Find an animal in the list")
        self._find.setClearButtonEnabled(True)
        self._find.textChanged.connect(self._chose)
        self._find.textChanged.connect(self._fill_animals)
        layout.addWidget(self._find)
        self._animal = QComboBox()
        self._animal.setAccessibleName("Animal to look at")
        self._animal.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self._animal.setMinimumContentsLength(18)
        self._animal.currentIndexChanged.connect(self._show_animal)
        self._animal.activated.connect(self._chose)
        layout.addWidget(self._animal)

        self._map_btn = QPushButton("🗺  Show it on the map")
        self._map_btn.setCheckable(True)
        self._map_btn.setToolTip("Grey every plant on the map that does not "
                                 "feed this animal")
        self._map_btn.toggled.connect(self._on_map_toggle)
        layout.addWidget(self._map_btn)

        summ = QHBoxLayout()
        summ.setSpacing(8)
        photo_col = QVBoxLayout()
        photo_col.setSpacing(2)
        self._photo = QLabel("🐝")
        self._photo.setFixedSize(96, 72)
        self._photo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._photo.setStyleSheet("border: 1px solid #2e4a2e; border-radius: 3px; "
                                  "background: #14241a; font-size: 30px;")
        photo_col.addWidget(self._photo)
        # Visible photo credit — required for CC-BY reuse (harmless for CC0).
        self._credit = QLabel("")
        self._credit.setFixedWidth(96)
        self._credit.setWordWrap(True)
        self._credit.setStyleSheet("color: #90a4ae; font-size: 12px;")
        self._credit.setVisible(False)
        photo_col.addWidget(self._credit)
        summ.addLayout(photo_col, 0)
        self._who = QLabel("")
        self._who.setWordWrap(True)
        self._who.setTextFormat(Qt.TextFormat.RichText)
        self._who.setAlignment(Qt.AlignmentFlag.AlignTop)
        self._who.setStyleSheet("color: #c8e6c9; font-size: 12px;")
        summ.addWidget(self._who, 1)
        layout.addLayout(summ)

        self._plants_box = self._section(layout, "Plants that feed it")
        self._needs_box = self._section(layout, "What else it needs")
        self._when_box = self._section(layout, "When it finds food here")
        self._footnote = QLabel("")
        self._footnote.setWordWrap(True)
        self._footnote.setStyleSheet(
            "color: #90a4ae; font-size: 12px; font-style: italic;")
        layout.addWidget(self._footnote)

        # ── Month by month ──────────────────────────────────────────────────
        layout.addWidget(self._heading("Month by month"))
        self._gap_label = QLabel("")
        self._gap_label.setWordWrap(True)
        layout.addWidget(self._gap_label)
        self._tree = QTreeWidget()
        self._tree.setAccessibleName("Food through the year, for wildlife "
                                     "and for people")
        self._tree.setColumnCount(2)
        self._tree.setHeaderLabels(["When", "What"])
        self._tree.setStyleSheet(_TREE_STYLE)
        self._tree.header().setSectionResizeMode(
            0, QHeaderView.ResizeMode.ResizeToContents)
        self._tree.header().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch)
        self._tree.setMinimumHeight(320)
        layout.addWidget(self._tree)
        layout.addStretch()
        self._fill_animals()

    # ── Building blocks ──────────────────────────────────────────────────────

    @staticmethod
    def _heading(text: str) -> QLabel:
        label = QLabel(text)
        label.setStyleSheet(_HEAD_STYLE)
        return label

    def _section(self, layout, title: str) -> QLabel:
        head = QLabel(title)
        head.setStyleSheet("color: #a5d6a7; font-size: 12px; font-weight: "
                           "bold; padding: 4px 0 2px 0;")
        layout.addWidget(head)
        body = QLabel("")
        body.setWordWrap(True)
        body.setTextFormat(Qt.TextFormat.RichText)
        body.setAlignment(Qt.AlignmentFlag.AlignTop)
        body.setStyleSheet(_BODY_STYLE)
        layout.addWidget(body)
        body.heading = head
        return body

    # ── Inputs ───────────────────────────────────────────────────────────────

    def set_placed_plants(self, plants: list) -> None:
        """Remember the design's plants; :meth:`refresh` draws them."""
        ids = []
        for p in plants or []:
            try:
                ids.append(int(p.get("plant_id")))
            except (TypeError, ValueError):
                pass
        self._plant_ids = sorted(set(ids))

    def refresh(self) -> None:
        """Redraw everything against the current design."""
        try:
            self._fed = feeds.animals_fed(self._plant_ids)
        except Exception:                                  # noqa: BLE001
            self._fed = []
        self._summary_line.setText(self._fed_summary())
        self._fill_animals()
        self._fill_months()

    def _fed_summary(self) -> str:
        if not self._plant_ids:
            return "Place plants to see who they feed."
        food = [a for a in self._fed if a["food"]]
        if not food:
            return "No animal is recorded feeding on these plants yet."
        counts: dict = {}
        for a in food:
            counts[a["taxon"]] = counts.get(a["taxon"], 0) + 1
        groups = ", ".join(feeds.group_words(t, counts[t])
                           for t, _o, _p in feeds.GROUPS if counts.get(t))
        return f"<b>Your plants feed {len(food)} animals</b>: {groups}."

    # ── The animal list ──────────────────────────────────────────────────────

    def _entries(self) -> list:
        """``[(header, [(label, data)])]``: the design's animals first, then
        the catalogue (read once: it does not change while the app runs)."""
        out = []
        food = [a for a in self._fed if a["food"]]
        if food:
            out.append(("Fed by your design", [
                (f"{a['name']} · {len(a['plants'])} "
                 f"plant{'s' if len(a['plants']) != 1 else ''}",
                 {"fid": a["fauna_id"], "taxon": a["taxon"]})
                for a in food]))
        if self._catalogue is None:
            self._catalogue = self._catalogue_entries()
        return out + self._catalogue

    @staticmethod
    def _catalogue_entries() -> list:
        """Bees by genus (as the Bees page listed them), then each other
        group by name."""
        out = []
        try:
            from src.bee_habitat import list_target_bees
            bees = list_target_bees()
        except Exception:                                  # noqa: BLE001
            bees = []
        genus, rows = None, []
        for b in bees:
            if b["genus"] != genus:
                if rows:
                    out.append((f"Bees: {genus}", rows))
                genus, rows = b["genus"], []
            if b["is_group"]:
                label = f"{b['common_name']} (any {b['genus']})"
            elif b["common_name"] == b["scientific_name"]:
                label = b["scientific_name"]       # no English name (V3.05)
            else:
                label = f"{b['common_name']} · {b['scientific_name']}"
            rows.append((label, {"fid": b["id"], "taxon": "bee"}))
        if rows:
            out.append((f"Bees: {genus}", rows))
        try:
            from src.db.fauna import list_fauna
            for taxon, _one, plural in feeds.GROUPS:
                if taxon == "bee":
                    continue
                animals = sorted(list_fauna(taxon),
                                 key=lambda f: f["common_name"].lower())
                if animals:
                    out.append((plural.capitalize(), [
                        (f["common_name"], {"fid": f["id"], "taxon": taxon})
                        for f in animals]))
        except Exception:                                  # noqa: BLE001
            pass
        return out

    def _chose(self, *_):
        self._user_chose = True

    def _fill_animals(self, *_):
        """(Re)fill the list, narrowed by the find box, keeping the animal a
        person chose while it is still listed; else the first one, which is
        the animal the design feeds most."""
        current = self._animal.currentData() if self._user_chose else None
        words = self._find.text().strip().lower()
        combo = self._animal
        combo.blockSignals(True)
        combo.clear()
        for header, rows in self._entries():
            if words:
                rows = [r for r in rows if words in r[0].lower()]
            if not rows:
                continue
            combo.addItem(f"── {header} ──", None)
            item = combo.model().item(combo.count() - 1)
            if item is not None:
                item.setEnabled(False)
            for label, data in rows:
                combo.addItem(f"    {label}", data)
        chosen = -1
        for i in range(combo.count()):
            data = combo.itemData(i)
            if data is None:
                continue
            if chosen < 0:
                chosen = i
            if current and data == current:
                chosen = i
                break
        combo.blockSignals(False)
        if chosen >= 0:
            combo.setCurrentIndex(chosen)
        self._show_animal()

    # ── One animal ───────────────────────────────────────────────────────────

    def _show_animal(self, *_):
        data = self._animal.currentData()
        if not data:
            self._plan = None
            self._who.setText("<i>No animal matches.</i>"
                              if self._find.text().strip() else "")
            for box in (self._plants_box, self._needs_box, self._when_box):
                box.setText("—")
            self._footnote.setText("")
            return
        if data["taxon"] == "bee":
            self._show_bee(data["fid"])
        else:
            self._show_other(data["fid"])
        self._render_photo()
        if self._map_btn.isChecked():
            self.map_overlay_requested.emit(self._map_payload())

    def _show_bee(self, fid: int):
        try:
            from src.bee_habitat import build_bee_habitat_plan
            plan = build_bee_habitat_plan(fid, plant_ids=self._plant_ids)
        except Exception:                                  # noqa: BLE001
            plan = None
        self._plan, self._plan_is_bee = plan, True
        if plan is None:
            self._who.setText("<i>No data for this bee yet.</i>")
            for box in (self._plants_box, self._needs_box, self._when_box):
                box.setText("—")
            self._footnote.setText("")
            return
        self._needs_box.heading.setText("Nesting: give it a place to live")
        self._when_box.heading.setText("Food across its flight season")
        self._who.setText(self._bee_summary(plan))
        self._plants_box.setText(self._bee_floral(plan))
        self._needs_box.setText(self._bee_nesting(plan))
        self._when_box.setText(self._bee_forage(plan))
        src = (plan.attrs or {}).get("source") or ""
        conf = {"documented": "well-documented", "partial": "partly documented",
                "thin": "sparse"}.get(plan.data_confidence, plan.data_confidence)
        self._footnote.setText(
            f"Data confidence: {conf}. Floral matches shown as documented "
            f"(plant↔bee records) or inferred (genus-level hosts). {src}")

    def _show_other(self, fid: int):
        try:
            plan = feeds.animal_plan(fid, self._plant_ids)
        except Exception:                                  # noqa: BLE001
            plan = {}
        self._plan, self._plan_is_bee = plan or None, False
        if not plan:
            self._who.setText("<i>No data for this animal yet.</i>")
            for box in (self._plants_box, self._needs_box, self._when_box):
                box.setText("—")
            self._footnote.setText("")
            return
        f = plan["fauna"]
        self._needs_box.heading.setText("What else it needs")
        self._when_box.heading.setText("When it finds food here")
        bits = [f"<b>{f['common_name']}</b> <span style='color:#90a4ae;'>"
                f"<i>{f['scientific_name']}</i></span>"]
        if f.get("description"):
            bits.append(f"<span style='color:#c8e6c9;'>{f['description']}</span>")
        self._who.setText("<br>".join(bits))
        self._plants_box.setText(self._other_plants(plan))
        self._needs_box.setText(self._other_needs(plan))
        self._when_box.setText(self._months_strip(plan))
        self._footnote.setText(
            "When is read off the plants: flowers for nectar and pollen, fruit "
            "for fruit and seed, leaves (May to September) for larvae that eat "
            "the plant.")

    @staticmethod
    def _kinds(kinds, taxon: str = "") -> str:
        return ", ".join(feeds.kind_words(k, taxon) for k in kinds)

    def _other_plants(self, plan) -> str:
        taxon = plan["fauna"].get("taxon") or ""
        rows = []
        if plan["here"]:
            rows.append("<b>In your design:</b>")
            rows += [f"★ {e['name']} <span style='color:#90a4ae;'>· "
                     f"{self._kinds(e['kinds'], taxon)}</span>"
                     for e in plan["here"]]
        if plan["elsewhere"]:
            more = plan["elsewhere_total"] - len(plan["elsewhere"])
            rows.append("<br><b>Would feed it too:</b>" if plan["here"]
                        else "<b>Plants that would feed it:</b>")
            rows += [f"{e['name']} <span style='color:#90a4ae;'>· "
                     f"{self._kinds(e['kinds'], taxon)}</span>"
                     for e in plan["elsewhere"]]
            if more > 0:
                rows.append(f"<span style='color:#90a4ae;'>and {more} more in "
                            f"the catalogue</span>")
        if not rows:
            return ("<i>No plant in the catalogue is recorded feeding it: a "
                    "gap in what is known, more often than a fact about it.</i>")
        return "".join(f"<div style='padding:1px 0;'>{r}</div>" for r in rows)

    @staticmethod
    def _other_needs(plan) -> str:
        if plan.get("no_host"):
            return ("<b>A caterpillar host.</b> Nothing in your design feeds its "
                    "caterpillars; the plants listed as a caterpillar host "
                    "above would.")
        if not plan["here"]:
            return "Nothing in your design serves it yet."
        return "<i>Nothing more is recorded.</i>"

    @staticmethod
    def _months_strip(plan) -> str:
        here = set(plan["months_here"])
        cells = []
        for m in range(1, 13):
            abbr = feeds.MONTH_ABBR[m - 1]
            style = ("background:#1b5e20; color:#c8e6c9; border-radius:3px;"
                     if m in here else "color:#5f7a6a;")
            cells.append(f"<span style='{style} padding:2px 4px;'>{abbr}</span>")
        if not plan["here"]:
            note = "Nothing in your design feeds it yet."
        elif plan["gaps"]:
            note = (f"Growing-season months with nothing for it here: "
                    f"{feeds.span(plan['gaps'])}.")
        else:
            note = "Something for it all through the growing season."
        return "".join(cells) + f"<div style='padding-top:4px;'>{note}</div>"

    # ── A bee (the Bees page's renderers, moved in V3.08) ────────────────────

    @staticmethod
    def _bee_summary(plan) -> str:
        bee = plan.bee or {}
        a = plan.attrs or {}
        tongue = a.get("tongue_length")
        season = a.get("flight_season")
        cons = a.get("conservation_status")
        bits = [f"<b>{bee.get('common_name', '')}</b> <span style='color:#90a4ae;'>"
                f"<i>{bee.get('scientific_name', '')}</i></span>"]
        facts = []
        if tongue and tongue != "unknown":
            facts.append(f"{tongue}-tongued")
        elif tongue == "unknown":
            facts.append("tongue not characterised")
        if season:
            facts.append(f"flies {season}")
        if facts:
            bits.append("<span style='color:#a5d6a7;'>" + " · ".join(facts)
                        + "</span>")
        if cons:
            colour = "#ff8a65" if "risk" in cons.lower() else "#90a4ae"
            bits.append(f"<span style='color:{colour};'>{cons}</span>")
        if bee.get("description"):
            bits.append(f"<span style='color:#c8e6c9;'>{bee['description']}</span>")
        return "<br>".join(bits)

    @staticmethod
    def _bee_match_row(m) -> str:
        bg, fg, txt = _FIT_CHIP.get(m.tongue_form_fit, _FIT_CHIP["unknown"])
        chip = (f"<span style='background:{bg}; color:{fg}; border-radius:3px; "
                f"padding:0 4px; font-size:12px;'>{txt}</span>"
                if txt != "—" else "")     # a pill saying "—" says nothing (V3.05)
        bloom = (f" <span style='color:#90a4ae;'>· {m.bloom_period}</span>"
                 if m.bloom_period else "")
        basis = ("" if m.confidence == "documented" else
                 " <span style='color:#90a4ae; font-size:12px;'>(genus match)</span>")
        star = "★ " if m.in_users_list else ""
        return f"{star}{m.common_name} {chip}{bloom}{basis}"

    def _bee_floral(self, plan) -> str:
        matches = plan.floral_matches or []
        if not matches:
            return ("<i>No floral-host plants matched — this is often a cuckoo "
                    "bee that feeds itself by parasitising a host bee (see "
                    "Nesting).</i>")
        in_design = [m for m in matches if m.in_users_list]
        rows = []
        if in_design:
            rows.append("<b>In your design:</b>")
            rows += [self._bee_match_row(m) for m in in_design[:12]]
            rows.append("<br><b>Also good to add:</b>")
            others = [m for m in matches if not m.in_users_list]
        else:
            rows.append("<b>Plants that feed this bee:</b>")
            others = matches
        rows += [self._bee_match_row(m) for m in others[:14]]
        return "".join(f"<div style='padding:1px 0;'>{r}</div>" for r in rows)

    @staticmethod
    def _bee_nesting(plan) -> str:
        g = plan.nesting
        parts = [f"<b>{g.headline}</b>"]
        if g.structures:
            names = ", ".join(s.get("name", "") for s in g.structures)
            parts.append(f"<span style='color:#a5d6a7;'>Structures: {names}</span>")
        parts += [f"• {a}" for a in g.actions]
        return "".join(f"<div style='padding:1px 0;'>{p}</div>" for p in parts)

    @staticmethod
    def _bee_forage(plan) -> str:
        f = plan.forage
        if not f.flight_months:
            return f"<i>{f.note}</i>"
        flight, covered = set(f.flight_months), set(f.covered_months)
        cells = []
        for mo in range(3, 11):    # Mar–Oct strip
            abbr = feeds.MONTH_ABBR[mo - 1]
            if mo not in flight:
                style = "color:#5f7a6a;"
            elif mo in covered:
                style = "background:#1b5e20; color:#c8e6c9; border-radius:3px;"
            else:
                style = "background:#5d3a1a; color:#ffcc80; border-radius:3px;"
            cells.append(f"<span style='{style} padding:2px 5px; margin:0 1px;'>"
                         f"{abbr}</span>")
        legend = ("<div style='color:#90a4ae; font-size:12px; padding-top:4px;'>"
                  "green = a plant in bloom for it · orange = flying but no "
                  "bloom (a gap to fill)</div>")
        sug = ""
        if f.suggestions:
            names = ", ".join(s.common_name for s in f.suggestions[:6])
            sug = (f"<div style='padding-top:4px; color:#a5d6a7;'>"
                   f"Fill the gap with: {names}</div>")
        return ("".join(cells) + f"<div style='padding-top:4px;'>{f.note}</div>"
                + legend + sug)

    # ── The photograph ───────────────────────────────────────────────────────

    def _animal_row(self) -> dict:
        if self._plan is None:
            return {}
        if self._plan_is_bee:
            return self._plan.bee or {}
        fid = self._plan["fauna"]["id"]
        try:
            from src.db.fauna import get_fauna
            return get_fauna(fid) or {}
        except Exception:                                  # noqa: BLE001
            return {}

    def on_image_ready(self) -> None:
        """A photograph finished downloading: draw it if it is this one."""
        self._render_photo()

    def _render_photo(self):
        row = self._animal_row()
        icon = "🐝" if self._plan_is_bee else (row.get("icon") or "🐾")
        url = row.get("image_url") or ""
        path = None
        if url:
            try:
                from src.image_cache import get_cached_image
                path = get_cached_image(url)
            except Exception:                              # noqa: BLE001
                path = None
        pm = QPixmap(path) if path else QPixmap()
        if not pm.isNull():
            self._photo.setText("")
            self._photo.setScaledContents(True)
            self._photo.setPixmap(pm)
            from src.image_cache import credit_line
            text = credit_line(row.get("image_attribution", ""),
                               row.get("image_license", ""))
            self._credit.setText(text or "")
            self._credit.setVisible(bool(text))
            return
        self._photo.setPixmap(QPixmap())
        self._photo.setText(icon)
        self._credit.setVisible(False)
        if url and url not in self._warmed and self._warm is not None:
            self._warmed.add(url)
            self._warm([(url, row.get("image_attribution", ""),
                         row.get("image_license", ""))])

    # ── The map ──────────────────────────────────────────────────────────────

    def _map_payload(self) -> dict:
        """``{bee: label, styles: {pid: fit}}``, the map's forage view: a bee's
        floral hosts graded by tongue fit, any other animal's plants as hosts."""
        styles = {}
        label = ""
        if self._plan is not None and self._plan_is_bee:
            for m in self._plan.floral_matches:
                styles[str(m.plant_id)] = (m.tongue_form_fit if m.tongue_form_fit
                                           in ("good", "plausible") else "host")
            label = (self._plan.bee or {}).get("common_name", "")
        elif self._plan:
            for e in self._plan["here"] + self._plan["elsewhere"]:
                styles[str(e["plant_id"])] = "host"
            label = self._plan["fauna"]["common_name"]
        return {"bee": label, "styles": styles}

    def _on_map_toggle(self, on: bool):
        if on and self._plan is not None:
            self.map_overlay_requested.emit(self._map_payload())
        else:
            self.map_overlay_cleared.emit()

    # ── Month by month ───────────────────────────────────────────────────────

    def _fill_months(self):
        self._tree.clear()
        if not self._plant_ids:
            self._gap_label.setText("")
            self._tree.addTopLevelItem(QTreeWidgetItem(["—", "No plants placed yet"]))
            return
        try:
            year = feeds.month_by_month(self._plant_ids)
        except Exception:                                  # noqa: BLE001
            return
        muted, gap = QColor("#78909c"), QColor("#ef5350")
        growing = feeds.GROWING_SEASON_MONTHS
        for month in year["months"]:
            m = month["month"]
            n_poll, n_bird = len(month["pollinators"]), len(month["birds"])
            n_people = len(month["people"])
            bits = []
            if n_poll:
                bits.append(f"{n_poll} in flower")
            if n_bird:
                bits.append(f"{n_bird} in fruit")
            if n_people:
                bits.append(f"{n_people} to harvest")
            summary = " · ".join(bits) or ("— nectar gap" if m in growing else "—")
            row = QTreeWidgetItem([_MONTHS[m - 1], summary])
            if not n_poll and m in growing:
                row.setForeground(0, gap)
                row.setForeground(1, gap)
            elif not bits:
                row.setForeground(0, muted)
                row.setForeground(1, muted)
            for key, words, colour in _GROUP_ROWS:
                items = month[key]
                group = QTreeWidgetItem([words, f"({len(items)})"])
                group.setForeground(0, QColor(colour))
                for item in items:
                    text = f"{item[0]} — {item[1]}" if key == "people" else item
                    group.addChild(QTreeWidgetItem(["", text]))
                if not items:
                    group.addChild(QTreeWidgetItem(["", "—"]))
                row.addChild(group)
            self._tree.addTopLevelItem(row)
        if year["gaps"]:
            names = ", ".join(_MONTHS[m - 1][:3] for m in year["gaps"])
            self._gap_label.setText(f"⚠ Nectar gaps in the growing season: "
                                    f"{names}. Add a plant in flower then.")
            self._gap_label.setStyleSheet("color: #ef9a9a; font-size: 12px;")
        else:
            self._gap_label.setText(
                f"✓ Something in flower from {_MONTHS[min(growing) - 1]} to "
                f"{_MONTHS[max(growing) - 1]}.")
            self._gap_label.setStyleSheet("color: #a5d6a7; font-size: 12px;")

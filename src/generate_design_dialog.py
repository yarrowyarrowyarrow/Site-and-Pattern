"""
generate_design_dialog.py — the Plan My Yard dialog (PY-1, PY-9, V3.28;
docs/homeowner/07-plan-my-yard.md §4.2-§4.3, §4.7).

It opens whatever the state of the design and says first what is missing,
with a button that does it: no pin, nothing outlined, or a pin outside the two
provinces (:func:`state_for`). Ready, it asks four plain questions: where the
plants go (the beds, when there are any, or the yard outline), how full (by
cover once grown: *Fill it now*, 70%, or *Over two or three summers*, 40%;
:mod:`src.plan_cover`), front or back yard (V3.29, PY-7), what it must do (the must-haves, worded as the data
supports them) and an optional budget. The goals a beginner should not have to
pick (native here, food for pollinators) are applied without a box. With the
Advanced tools on it adds the rest: the densities as cover targets, the other
goals, the wildlife picker and *Match to site conditions*.

The class keeps its old name, which the controller and tests import. The AI
wording, the brief only the AI read, and *Build without AI* went in V3.22
(RM-3). Structure mirrors :mod:`src.preferences_dialog`.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QApplication, QButtonGroup, QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFrame,
    QGroupBox, QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem,
    QPushButton, QRadioButton, QScrollArea, QSpinBox, QVBoxLayout, QWidget,
)

from src.design_goals import GOALS, LOCAL_KEY
from src.plan_cover import COVER_TARGETS, estimate

TITLE = "Plan my yard"

#: The states of §4.2, in the order they are asked about.
NEEDS_PIN, OUTSIDE, NEEDS_OUTLINE, READY = "pin", "outside", "outline", "ready"

#: §4.2's first line for each state that is not ready (OUTSIDE says the
#: region's message instead).
FIRST_LINES = {
    NEEDS_PIN: "Find your yard first, so the plan can use your soil and sun.",
    NEEDS_OUTLINE: ("Outline where you want to plant: your whole yard, or "
                    "just the beds."),
}

#: The buttons that do what is missing: ``(label, target)``, the target in
#: :func:`src.yard_overview_flow.run_action`'s words.
NEXT_STEPS = {
    NEEDS_PIN: (("Find my yard", "site"),),
    NEEDS_OUTLINE: (("Outline my yard", "draw"),
                    ("Draw a bed", "shape:Garden Bed")),
}

#: What :meth:`exec` returns when a next-step button closed the dialog.
NEXT_STEP = 2

#: The must-haves (§4.3, decision Y6): ``(goal key, words)``. The words say
#: what the data supports: most plants have no toxicity record, so a box
#: leaves out plants *known* to be poisonous and promises nothing more.
MUST_HAVES = (
    ("well_behaved", "Leave out plants known to spread"),
    ("low_cost", "Easy to buy around {place}"),
    ("pet_friendly", "Leave out plants known to be poisonous to pets"),
    ("kid_friendly", "Leave out plants known to be poisonous to people"),
    ("food_producing", "Food for people: berries and fruit"),
)
_MUST_TIPS = {
    "well_behaved": ("Leaves out plants recorded as spreading by roots or "
                     "seeding heavily. Plants with no record are kept."),
    "pet_friendly": ("Most plants have no record either way, so this leaves "
                     "out only the ones known to be poisonous to cats and "
                     "dogs. It does not promise the rest are safe."),
    "kid_friendly": ("Most plants have no record either way, so this leaves "
                     "out only the ones known to be poisonous to people, and "
                     "thorny ones. It does not promise the rest are safe."),
}

#: How full (§4.3, decision Y3): ``(key, density for the main pass)``. The
#: cover each aims for is :data:`src.plan_cover.COVER_TARGETS`'s.
FULLNESS = (("now", "balanced"), ("summers", "balanced"))
#: What the Advanced tools add (§4.7): the densities as cover targets.
ADVANCED_FULLNESS = (("sparse", "sparse"), ("balanced", "balanced"))


#: Front or back (§4.3, Y2): ``(key, label, what it means)``.
YARDS = (
    ("front", "Front yard",
     "Seen from the street: a neat edge, and shorter plants along it."),
    ("back", "Back yard",
     "Room for a wilder look, a brush pile and a bee hotel."),
)
#: The street sides, in the compass order ``frontage`` uses.
STREET_SIDES = ("north", "north-east", "east", "south-east", "south",
                "south-west", "west", "north-west")


def state_for(*, has_pin: bool, has_area: bool, outside: bool) -> str:
    """Which of §4.2's states the design is in."""
    if not has_pin:
        return NEEDS_PIN
    if outside:
        return OUTSIDE
    if not has_area:
        return NEEDS_OUTLINE
    return READY


def must_have_words(place: str = "") -> list:
    """``[(key, words)]``, the place named where the pin is in a region."""
    out = []
    for key, words in MUST_HAVES:
        if "{place}" in words:
            words = (words.format(place=place) if place
                     else "Easy to buy")
        out.append((key, words))
    return out


def fullness_words(key: str, area_m2: float) -> str:
    """A How-full choice with its estimate (§4.3): "Fill it now: about 260
    plants, about $2,300–$4,900"."""
    est = estimate(area_m2, COVER_TARGETS[key])
    n = f"about {est['plants']:,} plant{'s' if est['plants'] != 1 else ''}"
    cost = f"about ${est['low']:,}–${est['high']:,}"
    if key == "now":
        return f"Fill it now: {n}, {cost}"
    if key == "summers":
        return f"Over two or three summers: {n} now, mulch between"
    share = f"{COVER_TARGETS[key]:.0%}"
    name = "Sparse" if key == "sparse" else "Balanced"
    return f"{name}: {share} covered once grown, {n}"


def _area_words(m2: float) -> str:
    from src.yard_overview import about_m2
    return about_m2(m2) if m2 > 0 else "size not known"


class GenerateDesignDialog(QDialog):
    """Plan My Yard: what is missing, else four questions and one button."""

    def __init__(self, *, has_boundary: bool, has_pin: bool,
                 preselected: list | None = None,
                 fauna_options: list | None = None,
                 last_plan: int = 0,
                 goals: list | None = None,
                 coverage: str = "", outside: bool = False,
                 coverage_warns: bool = False,
                 areas: dict | None = None, place: str = "",
                 advanced: bool = False,
                 setting: str = "front", street_side: str = "south",
                 parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle(TITLE)
        self.setMinimumWidth(520)
        areas = dict(areas or {})
        self._areas = areas
        self._advanced = bool(advanced)
        self._preselected = set(preselected or [])
        self._goals = [g for g in (goals or GOALS) if g.backed]
        self._add_check: QCheckBox | None = None
        self._fauna_list: QListWidget | None = None
        self._fauna_find: QLineEdit | None = None
        self._match_site_check: QCheckBox | None = None
        self._where: dict = {}
        self._full: dict = {}
        self._musts: dict = {}
        self._yard: dict = {}
        self._street: QComboBox | None = None
        self._more: dict = {}
        self.next_step = ""
        self.state = state_for(
            has_pin=has_pin, outside=outside,
            has_area=bool(has_boundary or areas.get("beds")))

        outer = QVBoxLayout(self)
        heading = QLabel(f"<b>{TITLE}</b>")
        outer.addWidget(heading)
        if self.state != READY:
            self._build_missing(outer, coverage)
            return

        # V3.05: the questions scroll, the buttons stay put, so on a
        # 1366 x 768 laptop the button is never below the screen's edge.
        body = QWidget()
        layout = QVBoxLayout(body)
        layout.setContentsMargins(0, 0, 6, 0)
        # Where the pin is (V3.25, ED-8): the region's name, or how far
        # outside it and what that changes (src/region.message).
        if coverage:
            where = QLabel(coverage)
            where.setWordWrap(True)
            where.setObjectName("plan_coverage")
            if coverage_warns:
                where.setStyleSheet("color: #ffcc80;")
            layout.addWidget(where)
        self._build_where(layout, has_boundary)
        self._build_yard(layout, setting, street_side)
        self._build_fullness(layout)
        self._build_musts(layout, place)
        self._build_budget(layout)
        if self._advanced:
            self._build_advanced(layout, fauna_options or [])
        layout.addStretch(1)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setWidget(body)
        outer.addWidget(scroll, 1)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel)
        ok_button = buttons.button(QDialogButtonBox.StandardButton.Ok)
        ok_button.setText(TITLE)
        # V3.18 (PY-5): a second run replaces the last plan, and says so
        # before it does. Plants placed by hand are never part of a plan.
        replace_h = 0
        if last_plan:
            replace = QLabel(
                f"Your last plan ({last_plan} plant"
                f"{'s' if last_plan != 1 else ''}) will be replaced. "
                "Plants you placed yourself stay.")
            replace.setWordWrap(True)
            self._add_check = QCheckBox("Add to it instead")
            self._add_check.setToolTip(
                "Keep the last plan and put this one beside it.")

            def _name_button(adding: bool) -> None:
                replace.setVisible(not adding)
                ok_button.setText("Add to my plan" if adding
                                  else "Replace my plan")

            self._add_check.toggled.connect(_name_button)
            _name_button(False)
            outer.addWidget(replace)
            outer.addWidget(self._add_check)
            replace_h = (replace.sizeHint().height()
                         + self._add_check.sizeHint().height())
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        outer.addWidget(buttons)
        self.resize(self.width(), fitted_height(
            heading.sizeHint().height() + body.sizeHint().height()
            + replace_h + buttons.sizeHint().height() + 56, self))

    # ── What is missing (§4.2, PY-9) ─────────────────────────────────────────

    def _build_missing(self, outer, coverage: str) -> None:
        line = QLabel(coverage if self.state == OUTSIDE
                      else FIRST_LINES[self.state])
        line.setWordWrap(True)
        line.setObjectName("plan_first_line")
        outer.addWidget(line)
        row = QHBoxLayout()
        self._step_buttons = []
        for label, target in NEXT_STEPS.get(self.state, ()):
            b = QPushButton(label)
            b.clicked.connect(
                lambda _c=False, t=target: self._go(t))
            row.addWidget(b)
            self._step_buttons.append(b)
        row.addStretch(1)
        outer.addLayout(row)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel)
        buttons.rejected.connect(self.reject)
        outer.addWidget(buttons)
        if self._step_buttons:
            self._step_buttons[0].setDefault(True)

    def _go(self, target: str) -> None:
        self.next_step = target
        self.done(NEXT_STEP)

    # ── The four questions (§4.3) ────────────────────────────────────────────

    def _build_where(self, layout, has_boundary: bool) -> None:
        beds, yard = self._areas.get("beds", 0), has_boundary
        box = QGroupBox("Where should the plants go?")
        col = QVBoxLayout(box)
        group = QButtonGroup(self)
        if beds:
            n = f"{beds} bed{'s' if beds != 1 else ''}"
            r = QRadioButton(f"In the beds I drew ({n}, "
                             f"{_area_words(self._areas.get('beds_m2', 0))})")
            self._where["beds"] = r
        if yard:
            r = QRadioButton(
                "Anywhere in my yard outline ("
                f"{_area_words(self._areas.get('yard_m2', 0))} to plant)")
            self._where["yard"] = r
        for r in self._where.values():
            group.addButton(r)
            col.addWidget(r)
            r.toggled.connect(self._say_fullness)
        next(iter(self._where.values())).setChecked(True)
        if len(self._where) == 1:
            # One place to plant: said, not asked.
            only = next(iter(self._where.values()))
            only.setEnabled(False)
            only.setToolTip("Draw a bed to plant only part of your yard.")
        layout.addWidget(box)

    def _build_yard(self, layout, setting: str, street_side: str) -> None:
        """Front or back (PY-7, Y2): what a beginner can answer, where a
        named style asks for a vocabulary they do not have yet."""
        box = QGroupBox("Is this a front yard or a back yard?")
        col = QVBoxLayout(box)
        group = QButtonGroup(self)
        for key, label, words in YARDS:
            r = QRadioButton(label)
            group.addButton(r)
            col.addWidget(r)
            note = QLabel(words)
            note.setWordWrap(True)
            note.setIndent(24)
            col.addWidget(note)
            self._yard[key] = r
            if key == "front":
                row = QHBoxLayout()
                row.setContentsMargins(24, 0, 0, 0)
                row.addWidget(QLabel("The street is to the"))
                self._street = QComboBox()
                self._street.setAccessibleName("Which side the street is on")
                for side in STREET_SIDES:
                    self._street.addItem(side[0].upper() + side[1:], side)
                i = self._street.findData(street_side)
                self._street.setCurrentIndex(max(0, i))
                row.addWidget(self._street)
                row.addStretch(1)
                col.addLayout(row)
                r.toggled.connect(self._street.setEnabled)
        self._yard.get(setting, self._yard["front"]).setChecked(True)
        self._street.setEnabled(self._yard["front"].isChecked())
        layout.addWidget(box)

    def _build_fullness(self, layout) -> None:
        box = QGroupBox("How full?")
        col = QVBoxLayout(box)
        group = QButtonGroup(self)
        choices = FULLNESS + (ADVANCED_FULLNESS if self._advanced else ())
        for key, _density in choices:
            r = QRadioButton()
            group.addButton(r)
            col.addWidget(r)
            self._full[key] = r
        self._full["now"].setChecked(True)
        self._full["summers"].setToolTip(
            "Fewer plants now, which fill in as they grow. Mulch the ground "
            "between them meanwhile.")
        self._say_fullness()
        layout.addWidget(box)

    def _say_fullness(self, *_args) -> None:
        if not self._full:
            return
        m2 = self.area_m2()
        for key, r in self._full.items():
            r.setText(fullness_words(key, m2))

    def _build_musts(self, layout, place: str) -> None:
        box = QGroupBox("Anything it must do?")
        col = QVBoxLayout(box)
        offered = {g.key for g in self._goals}
        for key, words in must_have_words(place):
            if key not in offered:
                continue
            cb = QCheckBox(words)
            cb.setChecked(key in self._preselected)
            if key in _MUST_TIPS:
                cb.setToolTip(_MUST_TIPS[key])
            col.addWidget(cb)
            self._musts[key] = cb
        layout.addWidget(box)

    def _build_budget(self, layout) -> None:
        row = QHBoxLayout()
        row.addWidget(QLabel("Budget (optional):"))
        self._budget = QSpinBox()
        self._budget.setRange(0, 100000)
        self._budget.setSingleStep(25)
        self._budget.setPrefix("$ ")
        self._budget.setSpecialValueText("no limit")  # shown at value 0
        self._budget.setAccessibleName("Budget for plants, optional")
        self._budget.setToolTip(
            "About how much to spend on plants. The priciest are left out to "
            "fit. Prices are estimates, not quotes.")
        row.addWidget(self._budget)
        row.addStretch(1)
        layout.addLayout(row)

    # ── What the Advanced tools add (§4.7) ───────────────────────────────────

    def _build_advanced(self, layout, fauna_options: list) -> None:
        musts = {k for k, _w in MUST_HAVES}
        more = [g for g in self._goals if g.key not in musts]
        if more:
            box = QGroupBox("More goals")
            col = QVBoxLayout(box)
            for g in more:
                cb = QCheckBox(g.label)
                cb.setChecked(g.key in self._preselected)
                if g.caveat:
                    cb.setToolTip(g.caveat)
                col.addWidget(cb)
                self._more[g.key] = cb
            layout.addWidget(box)
        if fauna_options:
            self._build_fauna(layout, fauna_options)
        self._match_site_check = QCheckBox(
            "Match to site conditions && terrain")
        self._match_site_check.setChecked(True)
        self._match_site_check.setToolTip(
            "Place moisture-loving plants in low/wet ground, drought-tolerant "
            "plants on dry slopes, and shade plants in shade, using the "
            "terrain around your pin and outline and any existing trees or "
            "buildings you've marked. Needs elevation data (online).")
        layout.addWidget(self._match_site_check)

    def _build_fauna(self, layout, fauna_options: list) -> None:
        # The controller passes fauna_options (so the dialog stays DB-free):
        # a list of {"id", "common_name", "taxon", "icon"} dicts.
        box = QGroupBox("Design for wildlife (optional)")
        col = QVBoxLayout(box)
        hint = QLabel("Tick animals to make sure the plan includes plants "
                      "that feed or host them.")
        hint.setWordWrap(True)
        col.addWidget(hint)
        # Hundreds of animals: typing finds one (the Monarch was entry
        # 446 of a list nobody could search; F196 names the same list).
        self._fauna_find = QLineEdit()
        self._fauna_find.setPlaceholderText("Find an animal…")
        self._fauna_find.setAccessibleName("Find an animal in the list")
        self._fauna_find.setClearButtonEnabled(True)
        self._fauna_find.textChanged.connect(self._filter_fauna)
        col.addWidget(self._fauna_find)
        self._fauna_list = QListWidget()
        self._fauna_list.setMaximumHeight(140)
        taxon_label = {"lepidoptera": "butterfly/moth", "bird": "bird",
                       "bee": "bee", "other_insect": "insect",
                       "mammal": "mammal"}
        for f in fauna_options:
            fid = f.get("id")
            if fid is None:
                continue
            icon = f.get("icon") or ""
            taxon = taxon_label.get(f.get("taxon", ""), f.get("taxon", ""))
            label = f"{icon} {f.get('common_name', '?')}".strip()
            if taxon:
                label += f"  ({taxon})"
            item = QListWidgetItem(label)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Unchecked)
            item.setData(Qt.ItemDataRole.UserRole, int(fid))
            self._fauna_list.addItem(item)
        col.addWidget(self._fauna_list)
        layout.addWidget(box)

    def _filter_fauna(self, text: str) -> None:
        needle = text.strip().lower()
        for i in range(self._fauna_list.count()):
            item = self._fauna_list.item(i)
            item.setHidden(bool(needle) and needle not in item.text().lower())

    # ── The answers ──────────────────────────────────────────────────────────

    def replace_last(self) -> bool:
        """Whether this run replaces the design's last plan: yes when it has
        one, unless *Add to it instead* is ticked."""
        return self._add_check is not None and not self._add_check.isChecked()

    def where(self) -> str:
        """``"beds"`` or ``"yard"``: where the plants go."""
        for key, r in self._where.items():
            if r.isChecked():
                return key
        return "yard"

    def setting(self) -> str:
        """``"front"`` or ``"back"``."""
        return "back" if self._yard.get("back") and \
            self._yard["back"].isChecked() else "front"

    def street_side(self) -> str:
        """The street side the person confirmed: one of :data:`STREET_SIDES`."""
        return (self._street.currentData() if self._street is not None
                else "south") or "south"

    def area_m2(self) -> float:
        return float(self._areas.get(
            "beds_m2" if self.where() == "beds" else "yard_m2", 0.0) or 0.0)

    def _fullness(self) -> str:
        for key, r in self._full.items():
            if r.isChecked():
                return key
        return "now"

    def cover(self) -> float:
        """The cover once grown the plan aims for (PY-4)."""
        return COVER_TARGETS[self._fullness()]

    def density(self) -> str:
        """The main pass's density: 'sparse' | 'balanced' (V1.50)."""
        return dict(FULLNESS + ADVANCED_FULLNESS).get(
            self._fullness(), "balanced")

    def match_site(self) -> bool:
        """Whether to derive wet/dry/shaded micro-zones from the terrain and
        place plants/structures accordingly (V1.48). Always, in the simple
        app."""
        return (self._match_site_check is None
                or self._match_site_check.isChecked())

    def selected_goals(self) -> list:
        """The goals the plan reads: the must-haves ticked, and, in the simple
        app, the defaults with no box (native here, food for pollinators);
        with the Advanced tools on, the More goals ticked instead."""
        offered = {g.key for g in self._goals}
        if self._advanced:
            base = [k for k, cb in self._more.items() if cb.isChecked()]
        else:
            native = LOCAL_KEY if LOCAL_KEY in offered else "native_only"
            base = [k for k in (native, "pollinator") if k in offered]
        return base + [k for k, cb in self._musts.items() if cb.isChecked()]

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

    def budget(self) -> float | None:
        """Total plant budget in CAD, or ``None`` for no limit (value 0)."""
        if self.state != READY:
            return None
        v = self._budget.value()
        return float(v) if v > 0 else None


def fitted_height(wanted: int, widget: QWidget | None = None) -> int:
    """``wanted``, or the height of the screen the dialog opens on less room
    for a title bar and a margin, whichever is smaller."""
    screen = (widget.screen() if widget is not None else None) \
        or QApplication.primaryScreen()
    if screen is None:
        return wanted
    return max(320, min(wanted, screen.availableGeometry().height() - 72))

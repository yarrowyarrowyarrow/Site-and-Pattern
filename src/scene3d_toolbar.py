"""
scene3d_toolbar.py — the controls both 3D windows share (V2.44).

Design principle P4 (time is the most undervalued design variable) and P5
(perception is constructed — make the invisible visible) — see
docs/DESIGN_PHILOSOPHY.md.

Two windows drive one viewer: ``scene3d_window.Scene3DWindow`` (the design
preview) and ``reference_ecosystem_window.ReferenceEcosystemWindow`` (the
walkable, plantable wild community). The walk mode *itself* has always been the
same in both — ``html/scene3d/08-modes.js`` is one file — but the Qt chrome
around it was not:

    Author's report: *"The walk a wild landscape should be as close in terms of
    controls to the 3D preview walk the landscape mode."*

Before V2.44 the reference window had **no time controls at all** and forced
walk mode on with **no way to leave it**. That is not a missing-features
problem, it is a duplicated-toolbar problem: the second window was built with a
hand-rolled bar rather than the first one's, so the two could only diverge.

So this module owns the controls that are genuinely about *the viewer* — when
you are looking, how much detail, where the camera is, and whether you are
walking. Controls about *the design* (Refresh from design, bake a yard photo,
presentation still, fly as a bee, seasonal tour, spotlight, flyover) stay in
``Scene3DWindow``, because a wild community has no design to refresh from and
no proposal to illustrate.

Presentation only, like ``start_screen`` and ``learn_menu``: it emits signals
and never touches a viewer, a project or the database. The windows decide what
a control *means*; this decides what it looks like and that both get the same
one.

``groups=`` picks which sections appear, so the Learn side can be deliberately
simpler than the Design side **without being a second implementation** — the
distinction that matters, and the one the V2.43 mode split turns on.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt, QSettings, pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox, QHBoxLayout, QLabel, QPushButton, QSlider, QWidget,
)

#: How far the growth timeline runs. Matches ``scene3d_window._MAX_YEAR`` —
#: imported from here by that module now, so there is one number.
MAX_YEAR = 25

#: Viewer detail. Level 0 is a STYLE, not a thinning (see 13-stylised.js), which
#: is why these are nouns rather than "Low / Medium / High".
DETAIL_LABELS = ["Stylised", "Balanced", "Lifelike"]
DETAIL_KEY = "viewer3d/detail"

_MONTHS = ["", "Jan", "Feb", "Mar", "Apr", "May", "Jun",
           "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

#: Selectable sections. ``TIME`` and ``VIEW`` are the shared core; a caller asks
#: for what it can honestly act on.
TIME = "time"        # year · month · hour
DETAIL = "detail"    # geometry detail combo
VIEW = "view"        # reset view · walk · identify
ALL = (TIME, DETAIL, VIEW)


class Scene3DToolBar(QWidget):
    """The when/how-it-looks controls over a 3D viewer.

    Signals carry values, never widgets, so a window never reaches into this
    to read a slider — which is what kept the two bars able to drift.
    """

    year_changed = pyqtSignal(int)
    month_changed = pyqtSignal(int)
    hour_changed = pyqtSignal(int)
    #: Any of the three above — the common case is "rebuild the scene", and
    #: three separate connections to one handler is three chances to forget one.
    time_changed = pyqtSignal()
    detail_changed = pyqtSignal(int)
    reset_view = pyqtSignal()
    walk_toggled = pyqtSignal(bool)
    identify_toggled = pyqtSignal(bool)

    def __init__(self, parent: QWidget | None = None, *,
                 groups=ALL, year: int = 0, month: int = 6, hour: int = 13):
        super().__init__(parent)
        self._groups = tuple(groups)

        row = QHBoxLayout(self)
        row.setContentsMargins(8, 2, 8, 2)
        row.setSpacing(6)

        if TIME in self._groups:
            self._build_time(row, year, month, hour)
        if DETAIL in self._groups:
            self._build_detail(row)
        if VIEW in self._groups:
            self._build_view(row)
        row.addStretch()

    # ── Sections ────────────────────────────────────────────────────────────

    def _build_time(self, row, year: int, month: int, hour: int):
        self._year = QSlider(Qt.Orientation.Horizontal)
        self._year.setRange(0, MAX_YEAR)
        self._year.setValue(int(year))
        self._year.setToolTip("Watch it grow — drag to a future year")
        self._year_lbl = QLabel()

        self._month = QSlider(Qt.Orientation.Horizontal)
        self._month.setRange(1, 12)
        self._month.setValue(int(month))
        self._month.setToolTip("Season — shifts foliage colour and the sun")
        self._month_lbl = QLabel()

        self._hour = QSlider(Qt.Orientation.Horizontal)
        # Full 24 h so you can drag into night — a moonlit scene with moths and
        # bats instead of the day's bees and butterflies (V2.12).
        self._hour.setRange(0, 23)
        self._hour.setValue(int(hour))
        self._hour.setToolTip(
            "Time of day — drives the sun; drag past dusk for a moonlit night "
            "(moths, bats and glowing blooms)")
        self._hour_lbl = QLabel()

        self._year.valueChanged.connect(self._on_year)
        self._month.valueChanged.connect(self._on_month)
        self._hour.valueChanged.connect(self._on_hour)

        row.addWidget(self._label("Year:"))
        row.addWidget(self._year, 2)
        row.addWidget(self._year_lbl)
        row.addWidget(self._label("Season:"))
        row.addWidget(self._month, 1)
        row.addWidget(self._month_lbl)
        row.addWidget(self._label("Time:"))
        row.addWidget(self._hour, 1)
        row.addWidget(self._hour_lbl)
        self._sync_labels()

    def _build_detail(self, row):
        self._detail = QComboBox()
        self._detail.addItems(DETAIL_LABELS)
        self._detail.setToolTip(
            "Stylised — faceted low-poly plants: a clear diagram of the "
            "planting, and by far the fastest\n"
            "Balanced — the built-in geometry\n"
            "Lifelike — the full modelled library: real leaves, bark grain "
            "and species silhouettes")
        self._detail.setCurrentIndex(self.stored_detail())
        self._detail.currentIndexChanged.connect(self._on_detail)
        row.addWidget(self._label("Detail:"))
        row.addWidget(self._detail)

    def _build_view(self, row):
        self._reset_btn = QPushButton("Reset view")
        self._reset_btn.setToolTip("Re-center the camera")
        self._reset_btn.clicked.connect(self.reset_view.emit)
        row.addWidget(self._reset_btn)

        # Checkable, and therefore leaveable. The reference window used to be
        # dropped into walk mode with no control at all, which meant the only
        # way back to an overview of the community you were standing in was to
        # close the window.
        self._walk_btn = QPushButton("🚶 Walk")
        self._walk_btn.setCheckable(True)
        self._walk_btn.setToolTip(
            "Stroll through in third person — WASD/arrows to walk, drag to "
            "look around — and meet the creatures the plants support. Toggle "
            "off for the overview.")
        self._walk_btn.toggled.connect(self.walk_toggled.emit)
        row.addWidget(self._walk_btn)

        self._id_btn = QPushButton("🔎 Identify")
        self._id_btn.setCheckable(True)
        self._id_btn.setToolTip(
            "Label every creature and list who lives here — the wildlife the "
            "plants support, without having to hover.")
        self._id_btn.toggled.connect(self.identify_toggled.emit)
        row.addWidget(self._id_btn)

    @staticmethod
    def _label(text: str) -> QLabel:
        lab = QLabel(text)
        lab.setStyleSheet("color: #90a4ae; font-size: 11px;")
        return lab

    # ── Handlers ────────────────────────────────────────────────────────────

    def _on_year(self, v: int):
        self._sync_labels()
        self.year_changed.emit(int(v))
        self.time_changed.emit()

    def _on_month(self, v: int):
        self._sync_labels()
        self.month_changed.emit(int(v))
        self.time_changed.emit()

    def _on_hour(self, v: int):
        self._sync_labels()
        self.hour_changed.emit(int(v))
        self.time_changed.emit()

    def _on_detail(self, level: int):
        QSettings().setValue(DETAIL_KEY, int(level))
        self.detail_changed.emit(int(level))

    def _sync_labels(self):
        if TIME not in self._groups:
            return
        y = self._year.value()
        self._year_lbl.setText("now" if y <= 0 else f"yr {y}")
        self._month_lbl.setText(_MONTHS[self._month.value()])
        self._hour_lbl.setText(f"{self._hour.value():02d}:00")

    # ── Values ──────────────────────────────────────────────────────────────

    @staticmethod
    def stored_detail() -> int:
        """The remembered detail level, clamped. Static so a window without a
        detail control can still honour the user's choice."""
        try:
            return max(0, min(2, int(QSettings().value(DETAIL_KEY, 1))))
        except (TypeError, ValueError):
            return 1

    def year(self) -> int:
        return self._year.value() if TIME in self._groups else 0

    def month(self) -> int:
        return self._month.value() if TIME in self._groups else 6

    def hour(self) -> int:
        return self._hour.value() if TIME in self._groups else 13

    def detail(self) -> int:
        return (self._detail.currentIndex() if DETAIL in self._groups
                else self.stored_detail())

    def set_year(self, value: int) -> None:
        if TIME in self._groups:
            self._year.setValue(int(value))

    def set_month(self, value: int) -> None:
        if TIME in self._groups:
            self._month.setValue(int(value))

    def set_walking(self, on: bool) -> None:
        """Reflect walk state without re-emitting — for a window that enters
        walk mode itself and needs the button to agree."""
        if VIEW not in self._groups:
            return
        self._walk_btn.blockSignals(True)
        self._walk_btn.setChecked(bool(on))
        self._walk_btn.blockSignals(False)

    def is_walking(self) -> bool:
        return (VIEW in self._groups) and self._walk_btn.isChecked()

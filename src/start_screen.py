"""
start_screen.py — the page the app opens on (V2.41; rebuilt V3.23, ST-4; in
two columns V3.42, F259).

Design principle P13 — see docs/DESIGN_PHILOSOPHY.md.
UI conventions: docs/UI_PRINCIPLES.md (Krug).

Two columns, the owner's choice from sketches (docs/plans/V3.42-the-start-
screen-in-two-columns.md): **Your yards** (*Plan a new yard*, the designs
newest first, each with Rename and Delete) and **Learn** (the example yard,
the walk, the lessons, the quizzes). V3.42 retired the Learn menu and the line
of what is in flower.

**Exactly one row is filled, and it is the default button** (Enter): unsaved
work to restore, else *Plan a new yard*. The owner's H3 outlines the other
two doors, the design worked on last and the Learn card. No emoji.

A block of fixed width, centred, so a bigger window shows more ground around
the same screen. Presentation only: it returns a choice for
:mod:`src.start_flow` / :mod:`src.onboarding_flow`; its parts are
:mod:`src.start_rows`.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCheckBox, QDialog, QGridLayout, QHBoxLayout, QLabel, QSizePolicy,
    QVBoxLayout, QWidget,
)

from src import app_mode
from src.branding import APP_NAME, APP_TAGLINE
from src.start_rows import (
    AMBER, FILLED, HEAD, LINK_COLUMN, OUTLINED, PLAIN, QUIET, LearnCard, Row,
    clear_layout, column_gap, heading, link, quiet, retab, rule,
)
from src.ui_style import BASE_SURFACE

#: Values returned by :meth:`StartScreen.choice`.
RECOVER = "recover"
NEW_YARD = "new_yard"
EXAMPLE = "example"
OPEN_PATH = "open_path"        # one of the listed designs: chosen_path()
ALL_DESIGNS = "all_designs"    # the saves list (SavesDialog)
OPEN_FILE = "open_file"        # the system's file dialog
#: The Learn card's doors that open a window of their own (src.app_mode).
REFERENCE = app_mode.WALK
LESSONS = app_mode.LESSONS
QUIZZES = app_mode.QUIZZES
#: Help › Check for Updates is where updating lives now; the key stays so a
#: caller that asks for it still works.
UPDATE = "update"
#: The design you were last in, opened without asking: what a launch with the
#: screen turned off does (S8), and only then.
CONTINUE = "continue"

#: How many of the person's designs the screen lists before "All N designs…".
SHOWN = 3
NAME_CHARS = 40
RECOVER_CHARS = 32
#: The block the screen is drawn in, and its Learn column, in pixels.
BODY_WIDTH = 900
LEARN_WIDTH = 310
ICON = 80

_NUMBERS = ("", "One", "Two", "Three", "Four", "Five", "Six", "Seven",
            "Eight", "Nine", "Ten", "Eleven", "Twelve")


def _home_short() -> str:
    from src import region
    return region.default().short


def cut(text: str, chars: int) -> str:
    """``text`` at most ``chars`` long, ending in "…" when it was cut."""
    text = (text or "").strip()
    return text if len(text) <= chars else text[:chars - 1].rstrip() + "…"


def walk_note(places: int) -> str:
    """The walk's line: how many wild places there are, counted."""
    if places <= 0:
        return "Native places, in 3D"
    word = _NUMBERS[places] if places < len(_NUMBERS) else str(places)
    return f"{word} native place{'s' if places != 1 else ''}, in 3D"


def learn_rows(places: int = 0) -> tuple:
    """The Learn card, in order: ``(key, title, line, tooltip)``. Every line
    starts with a capital (the owner, V3.42). The lessons' and the quizzes'
    tooltips are read from the lessons and the quiz topics, which own them."""
    try:
        from src.lessons import LESSONS as taught
        from src.quiz_topics import GROUPS
        lessons = " · ".join(t for _k, t, _s in taught)
        quizzes = " · ".join(t for _k, t, _o in GROUPS)
    except Exception:                                      # noqa: BLE001
        lessons = quizzes = ""
    return (
        (EXAMPLE, "Look at an example yard", "A finished front yard",
         f"A front-yard lawn conversion in central {_home_short()}. Opens "
         "as a copy you can change."),
        (REFERENCE, "Walk a wild landscape", walk_note(places),
         "Walk into a wild place, plant in it and pull plants out."),
        (LESSONS, "Lessons", "Native plants and design", lessons),
        (QUIZZES, "Quizzes", "Plants, animals and seasons", quizzes),
    )


class StartScreen(QDialog):
    """Ask what the person came to do. ``choice()`` is one of the constants
    above, or ``""`` if they closed it; for :data:`OPEN_PATH`,
    ``chosen_path()`` is the design.

    ``designs`` are :func:`src.start_flow.screen_designs` rows (``path``,
    ``name``, ``when``, ``line``, ``summary``, ``place``, ``error``,
    ``deletable``), newest first; ``total`` is how many there are in all.
    ``places`` is how many wild places there are to walk.

    With ``rename(screen, path)`` each design has a Rename beside it (V3.37),
    and with ``delete(screen, path)`` a Delete under that where the design
    is ``deletable`` (V3.42); each returns ``(designs, total)`` afresh, or
    ``None``, and the screen stays open and redraws its list."""

    def __init__(self, parent: QWidget | None = None, *,
                 recover: str = "", designs=(), total: int = 0,
                 show_skip: bool = False, hidden: bool = False,
                 version: str = "", places: int = 0, rename=None,
                 delete=None):
        super().__init__(parent)
        self.setWindowTitle(f"{APP_NAME} {version}" if version else APP_NAME)
        self._choice = ""
        self._path = ""
        self._primary: Row | None = None
        self._recover = bool(recover)
        self._rename = rename
        self._delete = delete
        # Carried, not inherited: this opens before the MainWindow exists.
        self.setStyleSheet(BASE_SURFACE)

        outer = QGridLayout(self)
        outer.setContentsMargins(28, 24, 28, 18)
        outer.setRowStretch(0, 1)
        outer.setRowStretch(2, 2)               # a little above the middle
        outer.setColumnStretch(0, 1)
        outer.setColumnStretch(2, 1)
        body = QWidget(self)
        body.setFixedWidth(BODY_WIDTH)
        body.setSizePolicy(QSizePolicy.Policy.Fixed,
                           QSizePolicy.Policy.Maximum)
        outer.addWidget(body, 1, 1)
        self._body = layout = QVBoxLayout(body)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        layout.addLayout(self._masthead())
        layout.addSpacing(6)
        if recover:
            row = self._add_row(layout, RECOVER, "Restore unsaved changes",
                                AMBER, note=cut(recover, RECOVER_CHARS))
            row.setToolTip(f"{APP_NAME} closed before these changes were saved.")

        columns = QHBoxLayout()
        columns.setSpacing(36)
        columns.addLayout(self._yards(), 1)
        columns.addWidget(self._learn(places), 0, Qt.AlignmentFlag.AlignTop)
        layout.addLayout(columns)

        self._rule = rule()
        self._dont_show = QCheckBox("Next time, open my last design directly")
        self._dont_show.setChecked(bool(hidden))
        self._dont_show.setToolTip("You can always reopen this from Help.")
        self._dont_show.setStyleSheet(f"color: {QUIET}; font-size: 13px;")
        for w in (self._rule, self._dont_show):
            layout.addWidget(w)
            w.setVisible(bool(show_skip))
        self._show_designs(designs, total)

        if self._primary is not None:
            self._primary.setDefault(True)
            self._primary.setFocus()

    # ── Your yards ──────────────────────────────────────────────────────────

    def _yards(self) -> QVBoxLayout:
        col = QVBoxLayout()
        col.setSpacing(10)
        col.addWidget(heading("Your yards"))
        line = QHBoxLayout()
        line.setSpacing(12)
        self._add_row(line, NEW_YARD, "Plan a new yard",
                      OUTLINED if self._recover else FILLED, plus=True,
                      described="Start a design for a new yard, from its "
                                "address.", stretch=1)
        line.addWidget(column_gap())
        col.addLayout(line)
        self._designs = QVBoxLayout()
        self._designs.setSpacing(10)
        col.addLayout(self._designs)
        col.addStretch()
        return col

    def _show_designs(self, designs, total, *, refill: bool = False,
                      focus_path: str = "") -> None:
        """Fill (or refill, after a rename or a delete) the list of designs:
        up to :data:`SHOWN` rows, the last one worked on outlined, each with
        its Rename and Delete, then "All N designs…" and "Open a file…"."""
        clear_layout(self._designs)
        designs = list(designs)[:SHOWN]
        total = max(int(total or 0), len(designs))
        if not designs:
            self._designs.addWidget(
                quiet("Designs you save will be listed here."))
        focus = None
        for i, d in enumerate(designs):
            name, path = d.get("name", ""), d.get("path", "")
            line = QHBoxLayout()
            line.setSpacing(12)
            row = self._add_row(
                line, OPEN_PATH, cut(name, NAME_CHARS),
                OUTLINED if i == 0 else PLAIN, note=d.get("line", ""),
                fact=d.get("when", ""), path=path, stretch=1)
            tip = "\n".join(t for t in (name, d.get("summary", ""),
                                        d.get("place", "")) if t)
            if tip:
                row.setToolTip(tip)
            line.addWidget(self._actions(d))
            self._designs.addLayout(line)
            if path and path == focus_path:
                focus = row
        links = QHBoxLayout()
        links.setSpacing(18)
        if total > len(designs):
            links.addWidget(self._choice_link(ALL_DESIGNS,
                                              f"All {total} designs…"))
        links.addWidget(self._choice_link(
            OPEN_FILE, "Open a file…",
            "Open a design saved somewhere else on this computer."))
        links.addStretch()
        self._designs.addLayout(links)
        if refill:                          # the rows are new
            retab(self._body)
            if self._primary is not None:
                self._primary.setDefault(True)
            (focus or self._primary or self).setFocus()

    def _actions(self, d: dict) -> QWidget:
        """Rename, and Delete under it (the owner, V3.42), in a column of
        their own so every row's right edge lines up."""
        box = QWidget()
        box.setFixedWidth(LINK_COLUMN)
        lay = QVBoxLayout(box)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(2)
        lay.addStretch()
        name, path = d.get("name", ""), d.get("path", "")
        if self._rename is not None and not d.get("error"):
            btn = link(self, "Rename", "Give this design a new name.")
            btn.clicked.connect(lambda _c=False, p=path: self._rename_design(p))
            btn.setAccessibleName(f"Rename {name}")
            lay.addWidget(btn)
        if self._delete is not None and d.get("deletable"):
            from src.plain_messages import bin_name
            btn = link(self, "Delete", f"Move this design to the {bin_name()}.",
                       deleting=True)
            btn.clicked.connect(lambda _c=False, p=path: self._delete_design(p))
            btn.setAccessibleName(f"Delete {name}")
            lay.addWidget(btn)
        lay.addStretch()
        return box

    def _rename_design(self, path: str) -> None:
        fresh = self._rename(self, path) if self._rename else None
        if fresh:
            # Written afresh, the renamed design is the newest: the first row.
            designs, total = fresh
            first = designs[0].get("path", "") if designs else ""
            self._show_designs(designs, total, refill=True,
                               focus_path=first or path)

    def _delete_design(self, path: str) -> None:
        fresh = self._delete(self, path) if self._delete else None
        if fresh:
            self._show_designs(*fresh, refill=True)

    # ── Learn ───────────────────────────────────────────────────────────────

    def _learn(self, places: int) -> QWidget:
        box = QWidget(self)
        box.setFixedWidth(LEARN_WIDTH)
        col = QVBoxLayout(box)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(10)
        col.addWidget(heading("Learn"))
        card = LearnCard(box)
        for key, title, line, tip in learn_rows(places):
            row = card.add(title, line, tip)
            row.clicked.connect(lambda _c=False, k=key: self._pick(k))
        col.addWidget(card)
        col.addStretch()
        return box

    # ── Construction helpers ────────────────────────────────────────────────

    def _masthead(self) -> QHBoxLayout:
        top = QHBoxLayout()
        top.setSpacing(16)
        try:
            from src import app_icon
            mark = QLabel()
            mark.setPixmap(app_icon.icon().pixmap(ICON, ICON))
            mark.setFixedSize(ICON, ICON)
            top.addWidget(mark)
        except Exception:                                  # noqa: BLE001
            pass                    # a missing icon must not stop the screen
        words = QVBoxLayout()
        words.setSpacing(2)
        words.addStretch()
        name = QLabel(APP_NAME)
        name.setStyleSheet(f"color: {HEAD}; font-size: 30px; font-weight: bold;")
        words.addWidget(name)
        tagline = QLabel(APP_TAGLINE)
        tagline.setStyleSheet(f"color: {QUIET}; font-size: 15px;")
        words.addWidget(tagline)
        words.addStretch()
        top.addLayout(words)
        top.addStretch()
        return top

    def _add_row(self, layout, key, title, colours, *, note="", fact="",
                 plus=False, described="", path="", stretch=0) -> Row:
        row = Row(title, colours, note=note, fact=fact, plus=plus,
                  described=described, parent=self)
        row.clicked.connect(lambda _c=False, k=key, p=path: self._pick(k, p))
        layout.addWidget(row, stretch)
        if row.primary:
            self._primary = row
        return row

    def _choice_link(self, key: str, text: str, tooltip: str = ""):
        btn = link(self, text, tooltip)
        btn.clicked.connect(lambda _c=False, k=key: self._pick(k))
        return btn

    # ── Result ──────────────────────────────────────────────────────────────

    def _pick(self, key: str, path: str = ""):
        self._choice = key
        self._path = path
        self.accept()

    def choice(self) -> str:
        return self._choice

    def chosen_path(self) -> str:
        """The design an :data:`OPEN_PATH` row stands for."""
        return self._path

    def primary_row(self):
        """The one row Enter activates (tests read it)."""
        return self._primary

    def suppressed(self) -> bool:
        """Whether the next launch skips the screen and opens the last design.

        Read on **every** close, so unticking turns the screen back on. Only
        offered when there is a last design to open (S8)."""
        return not self._dont_show.isHidden() and self._dont_show.isChecked()

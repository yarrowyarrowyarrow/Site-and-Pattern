"""
start_screen.py — the page the app opens on (V2.41).

Design principle P13 — see docs/DESIGN_PHILOSOPHY.md.
UI conventions: docs/UI_PRINCIPLES.md (Krug). This screen is the worked example
for that document, and the V2.41b rewrite is what it was written from.

User feedback: *"I would like a start up page to boot up as the first thing the
user sees, before the map loads. This start/landing page will then direct the
user to start a new design, load a previous design or explore the plant
directory."* Then, on seeing it: *"the UI of this start menu is pretty bad."*

Three doors, in the order a person needs them: a new design, one they already
have, or the plant directory. Above them, only when they mean something, the
two rows about work already in progress. Below, quietly, two places worth
knowing about.

**Generate a design is deliberately not here.** It was the primary button in
V2.40 and comes off on the author's judgement: it is not ready to lead with, and
a start screen that opens with "let the app do it" teaches the wrong thing about
what this is. It keeps its File menu entry and Ctrl+G.

What the first cut got wrong, in Krug's terms, since this is the file where the
lesson lives:

* **Happy talk.** It opened with a sentence of mission statement, above the
  controls, delaying every visit for a line nobody reads twice.
* **Instructions.** It carried the three step path at the bottom, explaining a
  journey the user had already chosen by the time they read it.
* **Words.** Every row had a full sentence of description under it, most of
  which restated the title. "Load a design / Your saved designs, newest first,
  with what is in each one."
* **Flat hierarchy.** Six rows in identical boxes at identical weight, so
  nothing looked more likely than anything else.
* **Ambiguous clickability.** The secondary actions were styled as quiet text
  and did not read as controls.

The rewrite: the description under each row became a *fact about your own
situation* (how many saves you have, what the last design was called, how big
the catalogue is), which is shorter, more useful, and only sayable once.

Presentation only: no project, no database. It returns a choice and
``onboarding_flow`` acts on it.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCheckBox, QDialog, QFrame, QHBoxLayout, QLabel, QPushButton,
    QVBoxLayout, QWidget,
)

from src.branding import APP_NAME, APP_TAGLINE
from src.ui_style import BASE_SURFACE

#: Values returned by :meth:`StartScreen.choice`.
NEW = "new"
OPEN = "open"
DIRECTORY = "directory"
#: Rows that only exist when there is something behind them.
RECOVER = "recover"
CONTINUE = "continue"
#: The quiet second tier.
EXAMPLE = "example"
REFERENCE = "reference"
#: The footer.
BLOOM = "bloom"
UPDATE = "update"

#: The three doors: ``(key, icon, title)``. The note beside each is computed,
#: because a fact about the user's own situation beats a description of the
#: button every time.
_DOORS = (
    (NEW, "🌱", "New design"),
    (OPEN, "📂", "Open a design"),
    (DIRECTORY, "📖", "Plant directory"),
)


class _Row(QPushButton):
    """One choice: icon, what it is, and one fact about it.

    Two columns rather than two stacked lines. It halves the height, and it
    puts the changing part (3 saved / Nothing saved yet) in a fixed place the
    eye can return to instead of buried at the end of a sentence.
    """

    def __init__(self, icon: str, title: str, note: str, primary: bool,
                 parent: QWidget | None = None):
        super().__init__(parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(52)
        border = "#66bb6a" if primary else "#39543a"
        bg = "#22381f" if primary else "#1c2c1c"
        self.setStyleSheet(
            f"QPushButton {{ text-align: left; padding: 6px 14px; "
            f"background: {bg}; border: 1px solid {border}; "
            f"border-radius: 6px; }}"
            f"QPushButton:hover {{ background: #2b4526; border-color: #81c784; }}"
        )
        row = QHBoxLayout(self)
        row.setContentsMargins(4, 0, 8, 0)
        row.setSpacing(12)

        mark = QLabel(icon)
        mark.setStyleSheet("font-size: 22px; background: transparent;")
        mark.setFixedWidth(30)
        mark.setAlignment(Qt.AlignmentFlag.AlignCenter)
        row.addWidget(mark)

        head = QLabel(title)
        head.setStyleSheet(
            "color: #e8f5e9; font-size: 15px; font-weight: bold; "
            "background: transparent;")
        row.addWidget(head)
        row.addStretch()

        self._note = QLabel(note)
        self._note.setStyleSheet(
            "color: #93b295; font-size: 12px; background: transparent;")
        self._note.setAlignment(Qt.AlignmentFlag.AlignRight
                                | Qt.AlignmentFlag.AlignVCenter)
        row.addWidget(self._note)


#: Secondary actions look like links, because they are ones. The first cut
#: styled them as quiet text with no underline and no cursor change, which is
#: the "make it obvious what's clickable" rule broken in the plainest way.
_LINK = (
    "QPushButton { background: transparent; border: none; color: #8fc98f; "
    "font-size: 12px; text-align: left; padding: 2px 0; "
    "text-decoration: underline; }"
    "QPushButton:hover { color: #d7f0d7; }"
)


class StartScreen(QDialog):
    """Ask what the user came to do. ``choice()`` is one of the constants
    above, or ``""`` if they closed it."""

    def __init__(self, parent: QWidget | None = None, *,
                 last_design: str = "", recover: str = "",
                 saves_count: int = 0, species_count: int = 0,
                 bloom_line: str = "", version: str = "",
                 hidden: bool = False):
        super().__init__(parent)
        self.setWindowTitle(APP_NAME)
        self.setMinimumWidth(560)
        self._choice = ""
        # Carried, not inherited: this opens before the MainWindow exists, so
        # there is no parent stylesheet to pick the app's theme up from.
        self.setStyleSheet(BASE_SURFACE)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 16)
        layout.setSpacing(9)

        # What is this? Answered once, at the top, in the two sizes that say
        # "name" and "what it does". No mission statement follows it.
        name = QLabel(APP_NAME)
        name.setStyleSheet("color: #e8f5e9; font-size: 24px; "
                           "font-weight: bold;")
        layout.addWidget(name)
        tagline = QLabel(APP_TAGLINE)
        tagline.setStyleSheet("color: #8fb98f; font-size: 13px;")
        layout.addWidget(tagline)
        layout.addSpacing(6)

        # ── Work already under way ──────────────────────────────────────────
        # Its own group, above the doors, because it is about *your* things
        # rather than about what the app can do. Unsaved work leads: it is the
        # only row with a deadline on it.
        resume = []
        if recover:
            resume.append((RECOVER, "⏱", "Recover unsaved work", recover))
        if last_design:
            resume.append((CONTINUE, "↩", "Continue", last_design))
        for i, (key, icon, title, note) in enumerate(resume):
            self._add_row(layout, key, icon, title, note,
                          primary=(i == 0 and bool(recover)))
        if resume:
            layout.addWidget(self._rule())

        # ── The three doors ─────────────────────────────────────────────────
        notes = {
            NEW: "start from your address",
            OPEN: (f"{saves_count} saved" if saves_count
                   else "nothing saved yet"),
            DIRECTORY: (f"{species_count} native species" if species_count
                        else "look up any native species"),
        }
        for key, icon, title in _DOORS:
            # One obvious starting point, and only one. When there is work to
            # resume, that is the obvious one and none of these is.
            self._add_row(layout, key, icon, title, notes[key],
                          primary=(key == NEW and not resume))

        layout.addSpacing(2)

        # ── Worth knowing about ─────────────────────────────────────────────
        # Both already shipped and both were buried in menus.
        quiet = QHBoxLayout()
        quiet.setSpacing(16)
        quiet.addWidget(self._link(
            EXAMPLE, "See a finished design",
            "A front-yard lawn conversion you can open and take apart."))
        quiet.addWidget(self._link(
            REFERENCE, "Walk a wild plant community",
            "Walk the natural community your ecoregion is reaching toward, "
            "in 3D."))
        quiet.addStretch()
        layout.addLayout(quiet)

        layout.addWidget(self._rule())

        # ── Footer ──────────────────────────────────────────────────────────
        foot = QHBoxLayout()
        if bloom_line:
            foot.addWidget(self._link(BLOOM, bloom_line,
                                      "Open these in the plant directory."))
        foot.addStretch()
        if version:
            stamp = QLabel(version)
            stamp.setStyleSheet("color: #6d8a6d; font-size: 11px;")
            foot.addWidget(stamp)
            foot.addWidget(self._link(UPDATE, "Check for updates"))
        layout.addLayout(foot)

        tail = QHBoxLayout()
        self._dont_show = QCheckBox("Skip this screen next time")
        self._dont_show.setChecked(bool(hidden))
        self._dont_show.setToolTip(
            "You can always reopen it from Help.")
        self._dont_show.setStyleSheet("color: #7f9c82; font-size: 11px;")
        tail.addWidget(self._dont_show)
        tail.addStretch()
        close = QPushButton("Close")
        close.setToolTip("Go straight to a blank map.")
        close.clicked.connect(self.reject)
        tail.addWidget(close)
        layout.addLayout(tail)

    # ── Construction helpers ────────────────────────────────────────────────

    def _add_row(self, layout, key, icon, title, note, *, primary):
        row = _Row(icon, title, note, primary, self)
        row.clicked.connect(lambda _checked=False, k=key: self._pick(k))
        layout.addWidget(row)

    def _link(self, key: str, text: str, tooltip: str = "") -> QPushButton:
        btn = QPushButton(text)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setFlat(True)
        btn.setStyleSheet(_LINK)
        if tooltip:
            btn.setToolTip(tooltip)
        btn.clicked.connect(lambda _checked=False, k=key: self._pick(k))
        return btn

    @staticmethod
    def _rule() -> QFrame:
        """A hairline that actually draws.

        `QFrame.HLine` renders from the palette's Mid/Dark roles and ignores a
        stylesheet `color:`, so the first cut's separators were invisible and
        the screen's areas were held apart by spacing alone. A 1px frame with a
        background does what was meant.
        """
        line = QFrame()
        line.setFixedHeight(1)
        line.setStyleSheet("background-color: #2f4a30; border: none;")
        return line

    # ── Result ──────────────────────────────────────────────────────────────

    def _pick(self, key: str):
        self._choice = key
        self.accept()

    def choice(self) -> str:
        return self._choice

    def suppressed(self) -> bool:
        """Whether the screen should stay shut next launch.

        Read on **every** close, not only when newly ticked, so unticking turns
        it back on. The V2.40 version only ever wrote ``True``, which made the
        box a one-way trapdoor out of the app's own front door.
        """
        return self._dont_show.isChecked()

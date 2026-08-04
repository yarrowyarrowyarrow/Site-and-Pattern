"""
start_screen.py — the page the app opens on (V2.41).

Design principle P13 — see docs/DESIGN_PHILOSOPHY.md.

User feedback: *"I would like a start up page to boot up as the first thing the
user sees, before the map loads. This start/landing page will then direct the
user to start a new design, load a previous design or explore the plant
directory."*

Replaces ``welcome_dialog.py``, which reached this shape by two corrections.
V2.31 made it a first-run greeting shown once. V2.40 moved it ahead of the map
and gave it rows that appear only when they have something behind them. What it
still lacked was a third door: the app's best material — 434 species, their
animals, their ranges — was reachable only from inside a design.

Three doors, in the order a person actually needs them:

  * **Start a new design** — the thing most launches are for.
  * **Load a design** — the V2.39 saves list.
  * **Explore the plant directory** — the reference work (F90).

Above them, only when they mean something: recover unsaved work, and continue
the design you were last in, by name. Below them, quietly: the worked example
and the walkable reference ecosystem — both already built and both previously
buried in a menu nobody opens.

**Generate a design is deliberately not here.** It was the primary button in
V2.40 and it comes off on the author's judgement: it is not ready to lead with,
and a start screen that opens with "let the AI do it" teaches people the wrong
thing about what this app is. It keeps its File-menu entry and Ctrl+G.

Presentation only. The copy describing the path comes from :mod:`src.onboarding`
so this screen, the step bar and the Site panel cannot drift; the screen itself
touches neither the project nor the database, and returns a choice for
``onboarding_flow`` to act on.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCheckBox, QDialog, QFrame, QHBoxLayout, QLabel, QPushButton,
    QVBoxLayout, QWidget,
)

from src.branding import APP_NAME, APP_TAGLINE
from src.onboarding import STEPS
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

#: The three doors. ``(key, icon, title, detail)``.
_DOORS = (
    (NEW, "🌱", "Start a new design",
     "Drop a pin on your address, draw the area you want to plant, and choose "
     "the plants yourself."),
    (OPEN, "📂", "Load a design",
     "Your saved designs, newest first — with what is in each one."),
    (DIRECTORY, "📖", "Explore the plant directory",
     "Every species in the catalogue: what it looks like, where it grows, and "
     "which animals depend on it."),
)


class _ChoiceButton(QPushButton):
    """A big, readable option row. Title + one line of what it actually does."""

    def __init__(self, icon: str, title: str, detail: str, primary: bool,
                 parent: QWidget | None = None):
        super().__init__(parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(74)
        border = "#66bb6a" if primary else "#3e5c3e"
        bg = "#22381f" if primary else "#1a2a1a"
        self.setStyleSheet(
            f"QPushButton {{ text-align: left; padding: 10px 14px; "
            f"background: {bg}; border: 1px solid {border}; "
            f"border-radius: 6px; }}"
            f"QPushButton:hover {{ background: #2b4526; border-color: #81c784; }}"
        )
        row = QHBoxLayout(self)
        row.setContentsMargins(4, 2, 4, 2)
        row.setSpacing(12)

        mark = QLabel(icon)
        mark.setStyleSheet("font-size: 26px; background: transparent;")
        mark.setFixedWidth(36)
        mark.setAlignment(Qt.AlignmentFlag.AlignCenter)
        row.addWidget(mark)

        text = QVBoxLayout()
        text.setSpacing(2)
        head = QLabel(title)
        head.setStyleSheet(
            "color: #e8f5e9; font-size: 14px; font-weight: bold; "
            "background: transparent;")
        text.addWidget(head)
        body = QLabel(detail)
        body.setWordWrap(True)
        body.setStyleSheet(
            "color: #a5c8a5; font-size: 11px; background: transparent;")
        text.addWidget(body)
        row.addLayout(text, 1)


_QUIET_LINK = (
    "QPushButton { background: transparent; border: none; color: #8fb98f; "
    "font-size: 12px; text-align: left; padding: 2px 0; }"
    "QPushButton:hover { color: #c8e6c9; text-decoration: underline; }"
)


class StartScreen(QDialog):
    """Ask what the user came to do. ``choice()`` is one of the constants
    above, or ``""`` if they closed it."""

    def __init__(self, parent: QWidget | None = None, *,
                 last_design: str = "", recover: str = "",
                 has_saves: bool = False, bloom_line: str = "",
                 version: str = "", first_run: bool = True):
        super().__init__(parent)
        self.setWindowTitle(
            f"Welcome to {APP_NAME}" if first_run else APP_NAME)
        self.setMinimumWidth(600)
        self._choice = ""
        # Carried, not inherited. The app's theme lives on MainWindow's
        # stylesheet (app.py:_APP_STYLE) and normally reaches a dialog through
        # its parent; this one opens *before the MainWindow exists*, so without
        # this it would render pale-green text on the platform's default light
        # dialog.
        self.setStyleSheet(BASE_SURFACE)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 20, 22, 16)
        layout.setSpacing(10)

        title = QLabel(f"<b>{APP_NAME}</b> — {APP_TAGLINE}")
        title.setStyleSheet("color: #e8f5e9; font-size: 19px;")
        layout.addWidget(title)

        blurb = QLabel(
            "Turn lawn into habitat for the plants, birds, bees and "
            "butterflies that already belong here.")
        blurb.setWordWrap(True)
        blurb.setStyleSheet("color: #a5c8a5; font-size: 12px;")
        layout.addWidget(blurb)

        # ── Pick up where you left off ──────────────────────────────────────
        # Conditional, and in urgency order: unsaved work from a crash first,
        # because it is the only row with a deadline on it.
        resume = []
        if recover:
            resume.append((
                RECOVER, "⏱", "Recover unsaved work",
                f"A previous session ended with unsaved changes to "
                f"“{recover}”. Open them, or start fresh and they are gone."))
        if last_design:
            resume.append((
                CONTINUE, "↩", f"Continue — “{last_design}”",
                "Reopen the design you were last working on."))

        for i, (key, icon, head, detail) in enumerate(resume):
            self._add_row(layout, key, icon, head, detail,
                          primary=(i == 0 and bool(recover)))
        if resume:
            layout.addWidget(self._rule())

        # ── The three doors ─────────────────────────────────────────────────
        # All three, always. The V2.40 dialog hid "Open a design" until you had
        # one, on the rule that a door to an empty room is worse than no door —
        # right for what was then a bonus row, wrong now that these three *are*
        # the screen. A structure that rearranges itself between your first and
        # second launch is harder to learn than one honest empty room, and the
        # saves browser explains itself and offers Browse… for a design kept
        # somewhere else. So the row stays and its second line tells the truth.
        for key, icon, head, detail in _DOORS:
            if key == OPEN and not (has_saves or last_design):
                detail = ("Nothing saved yet — designs you save appear here. "
                          "You can also open one from elsewhere on this "
                          "computer.")
            # Only the top row of the whole screen gets the primary treatment;
            # two "obvious" buttons is none.
            self._add_row(layout, key, icon, head, detail,
                          primary=(key == NEW and not resume))

        layout.addWidget(self._rule())

        # ── The quiet tier ──────────────────────────────────────────────────
        # Both already shipped and both were buried in menus: the worked
        # example behind Help, and F50's walkable reference ecosystem behind
        # View. One line each here is the whole of what they were missing.
        quiet = QHBoxLayout()
        quiet.setSpacing(18)
        quiet.addWidget(self._link(
            EXAMPLE, "🌾  Open the worked example",
            "A finished front-yard lawn conversion — open it, score it, walk "
            "it in 3D, and take it apart to see how it works."))
        quiet.addWidget(self._link(
            REFERENCE, "🌲  Walk a reference ecosystem",
            "Walk the natural plant community your ecoregion is reaching "
            "toward, in 3D."))
        quiet.addStretch()
        layout.addLayout(quiet)

        # The same three steps the step bar shows, so the screen teaches the
        # path rather than only branching on it.
        path = QLabel("Whichever you pick, the path is the same: "
                      + "  →  ".join(f"<b>{i}.</b> {s['title']}"
                                     for i, s in enumerate(STEPS, 1)))
        path.setWordWrap(True)
        path.setStyleSheet("color: #90a4ae; font-size: 11px;")
        layout.addWidget(path)

        layout.addWidget(self._rule())

        # ── Footer ──────────────────────────────────────────────────────────
        foot = QHBoxLayout()
        if bloom_line:
            # A living number on a screen you see every launch (P4/P5). Clicks
            # through to the directory already filtered to this month.
            foot.addWidget(self._link(
                BLOOM, f"🌼  {bloom_line} →",
                "See them in the plant directory."))
        foot.addStretch()
        if version:
            stamp = QLabel(version)
            stamp.setStyleSheet("color: #6d8a6d; font-size: 11px;")
            foot.addWidget(stamp)
            foot.addWidget(self._link(UPDATE, "Check for updates",
                                      "Look for a newer version."))
        layout.addLayout(foot)

        tail = QHBoxLayout()
        self._dont_show = QCheckBox("Don't show this again")
        self._dont_show.setStyleSheet("color: #90a4ae; font-size: 11px;")
        tail.addWidget(self._dont_show)
        tail.addStretch()
        close = QPushButton("Close")
        close.clicked.connect(self.reject)
        tail.addWidget(close)
        layout.addLayout(tail)

    # ── Construction helpers ────────────────────────────────────────────────

    def _add_row(self, layout, key, icon, head, detail, *, primary):
        btn = _ChoiceButton(icon, head, detail, primary, self)
        btn.clicked.connect(lambda _checked=False, k=key: self._pick(k))
        layout.addWidget(btn)

    def _link(self, key: str, text: str, tooltip: str = "") -> QPushButton:
        btn = QPushButton(text)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setFlat(True)
        btn.setStyleSheet(_QUIET_LINK)
        if tooltip:
            btn.setToolTip(tooltip)
        btn.clicked.connect(lambda _checked=False, k=key: self._pick(k))
        return btn

    @staticmethod
    def _rule() -> QFrame:
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet("color: #2e4a2e;")
        return line

    # ── Result ──────────────────────────────────────────────────────────────

    def _pick(self, key: str):
        self._choice = key
        self.accept()

    def choice(self) -> str:
        return self._choice

    def suppressed(self) -> bool:
        """True when the user asked not to be shown this again. Honoured on
        Close as well as on a choice."""
        return self._dont_show.isChecked()

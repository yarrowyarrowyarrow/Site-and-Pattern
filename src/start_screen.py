"""
start_screen.py — the page the app opens on: "Your designs" (V2.41; rebuilt
V3.23, ST-4).

Design principle P13 — see docs/DESIGN_PHILOSOPHY.md.
UI conventions: docs/UI_PRINCIPLES.md (Krug).

The owner, with a screenshot of the V3.17 screen: *"This feels unfinished,
unpolished, unprofessional. Continue, Open a design, and Design all are very
similar."* Three doors and two resume rows said the same thing five ways. The
rebuild is docs/homeowner/04-start-screen.md's Option B (the owner's S12): one
way to start a yard, then the person's own designs as named things, newest
first, with the newest the obvious row. The Learn door stays, as one quiet
link below the yard rows (S1). At the bottom, one line of what is flowering
around Edmonton this month (the owner, V3.23): a reason to go outside and look
(P11), not a control.

**Exactly one row is primary**, the dialog's default button with the focus,
so Enter does the obvious thing: unsaved work to restore, else the newest
design, else *Plan a new yard*. No emoji: the V3.17 icons read as a toy.

Presentation only: no project, no database. It returns a choice, and
:mod:`src.start_flow` / :mod:`src.onboarding_flow` act on it.
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
RECOVER = "recover"
NEW_YARD = "new_yard"
EXAMPLE = "example"
OPEN_PATH = "open_path"        # one of the listed designs: chosen_path()
ALL_DESIGNS = "all_designs"    # the saves list (SavesDialog)
OPEN_FILE = "open_file"        # the system's file dialog
LEARN = "learn"
#: Still dispatched: the Learn menu's Walk a wild landscape returns it.
REFERENCE = "reference"
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

#: Rows: a dark ground; the primary green with white words (5.13 : 1); the
#: restore row amber when it is the primary, because it is the one with a
#: deadline.
_ROW = ("QPushButton {{ text-align: left; padding: 6px 14px; "
        "background: {bg}; border: 1px solid {border}; border-radius: 6px; }}"
        "QPushButton:hover {{ background: {hover}; border-color: #a5d6a7; }}"
        "QPushButton:focus {{ border: 2px solid #e8f5e9; }}")
_PLAIN = dict(bg="#1c2c1c", border="#39543a", hover="#2b4526",
              head="#e8f5e9", note="#a5c4a7")
_PRIMARY = dict(bg="#2e7d32", border="#66bb6a", hover="#276b2b",
                head="#ffffff", note="#ffffff")
_AMBER = dict(bg="#7a4f00", border="#ffb74d", hover="#8d5c00",
              head="#ffffff", note="#ffffff")

#: Secondary actions look like links, because they are ones.
_LINK = (
    "QPushButton { background: transparent; border: none; color: #8fc98f; "
    "font-size: 13px; text-align: left; padding: 2px 0; "
    "text-decoration: underline; }"
    "QPushButton:hover { color: #d7f0d7; }"
)


def cut(text: str, chars: int) -> str:
    """``text`` at most ``chars`` long, ending in "…" when it was cut."""
    text = (text or "").strip()
    return text if len(text) <= chars else text[:chars - 1].rstrip() + "…"


class _Row(QPushButton):
    """One choice: what it is, and one fact about it, in two columns."""

    def __init__(self, title: str, note: str, colours: dict,
                 parent: QWidget | None = None):
        super().__init__(parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(46)
        self.setStyleSheet(_ROW.format(**colours))
        self.primary = colours is not _PLAIN
        row = QHBoxLayout(self)
        row.setContentsMargins(10, 0, 10, 0)
        row.setSpacing(12)
        head = QLabel(title)
        head.setStyleSheet(f"color: {colours['head']}; font-size: 15px; "
                           "font-weight: bold; background: transparent;")
        row.addWidget(head)
        row.addStretch()
        note_label = QLabel(note)
        note_label.setStyleSheet(f"color: {colours['note']}; font-size: 13px; "
                                 "background: transparent;")
        note_label.setAlignment(Qt.AlignmentFlag.AlignRight
                                | Qt.AlignmentFlag.AlignVCenter)
        row.addWidget(note_label)
        # The words are child labels, so a screen reader would hear only
        # "button" (V2.98 review, finding 17).
        self.setAccessibleName(title)
        self.setAccessibleDescription(note)


class StartScreen(QDialog):
    """Ask what the person came to do. ``choice()`` is one of the constants
    above, or ``""`` if they closed it; for :data:`OPEN_PATH`,
    ``chosen_path()`` is the design.

    ``designs`` are :func:`src.start_flow.screen_designs` rows (``path``,
    ``name``, ``when``, ``summary``, ``error``), newest first; ``total`` is how
    many there are in all. ``flowering`` is the line of what is in flower,
    ``""`` for none."""

    def __init__(self, parent: QWidget | None = None, *,
                 recover: str = "", designs=(), total: int = 0,
                 show_skip: bool = False, hidden: bool = False,
                 version: str = "", flowering: str = "",
                 flowering_tip: str = ""):
        super().__init__(parent)
        self.setWindowTitle(f"{APP_NAME} {version}" if version else APP_NAME)
        self.setMinimumWidth(560)
        self._choice = ""
        self._path = ""
        self._primary: _Row | None = None
        # Carried, not inherited: this opens before the MainWindow exists.
        self.setStyleSheet(BASE_SURFACE)
        designs = list(designs)[:SHOWN]
        total = max(int(total or 0), len(designs))

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 16)
        layout.setSpacing(9)
        layout.addLayout(self._masthead())
        layout.addSpacing(4)

        # ── Start ───────────────────────────────────────────────────────────
        if recover:
            row = self._add_row(layout, RECOVER, "Restore unsaved changes",
                                cut(recover, RECOVER_CHARS), primary="amber")
            row.setToolTip(f"{APP_NAME} closed before these changes were saved.")
        primary_new = not recover and not designs
        self._add_row(layout, NEW_YARD, "Plan a new yard",
                      "start from your address",
                      primary="green" if primary_new else "")
        quiet = QHBoxLayout()
        quiet.setSpacing(18)
        quiet.addWidget(self._link(
            EXAMPLE, "Look at an example yard",
            "A front-yard lawn conversion in central Edmonton. Opens as a "
            "copy you can change."))
        quiet.addWidget(self._link(
            LEARN, "Learn about native plants",
            "Walk a wild landscape, or take the lessons and field study."))
        quiet.addStretch()
        layout.addLayout(quiet)
        layout.addWidget(self._rule())

        # ── Your designs ────────────────────────────────────────────────────
        heading = QLabel("Your designs")
        heading.setStyleSheet("color: #e8f5e9; font-size: 15px; "
                              "font-weight: bold;")
        layout.addWidget(heading)
        if not designs:
            empty = QLabel("Designs you save will be listed here.")
            empty.setStyleSheet("color: #a5c4a7;")
            layout.addWidget(empty)
        for i, d in enumerate(designs):
            note = "can't be opened" if d.get("error") else d.get("when", "")
            row = self._add_row(
                layout, OPEN_PATH, cut(d.get("name", ""), NAME_CHARS), note,
                primary="green" if (i == 0 and not recover) else "",
                path=d.get("path", ""))
            if d.get("summary"):
                row.setToolTip(d["summary"])
        if total > len(designs):
            layout.addWidget(self._link(ALL_DESIGNS, f"All {total} designs…"))
        layout.addWidget(self._rule())

        # ── Foot ────────────────────────────────────────────────────────────
        tail = QHBoxLayout()
        self._dont_show = QCheckBox("Next time, open my last design directly")
        self._dont_show.setChecked(bool(hidden))
        self._dont_show.setToolTip("You can always reopen this from Help.")
        self._dont_show.setStyleSheet("color: #a5c4a7; font-size: 13px;")
        self._dont_show.setVisible(bool(show_skip))
        tail.addWidget(self._dont_show)
        tail.addStretch()
        tail.addWidget(self._link(
            OPEN_FILE, "Open a file…",
            "Open a design saved somewhere else on this computer."))
        layout.addLayout(tail)
        if flowering:
            line = QLabel(flowering)
            line.setWordWrap(True)
            line.setStyleSheet("color: #a5c4a7; font-size: 13px;")
            if flowering_tip:
                line.setToolTip(flowering_tip)
            layout.addWidget(line)

        if self._primary is not None:
            self._primary.setDefault(True)
            self._primary.setFocus()

    # ── Construction helpers ────────────────────────────────────────────────

    def _masthead(self) -> QHBoxLayout:
        top = QHBoxLayout()
        top.setSpacing(12)
        try:
            from src import app_icon
            mark = QLabel()
            mark.setPixmap(app_icon.icon().pixmap(48, 48))
            mark.setFixedSize(48, 48)
            top.addWidget(mark)
        except Exception:                                  # noqa: BLE001
            pass                    # a missing icon must not stop the screen
        words = QVBoxLayout()
        words.setSpacing(0)
        name = QLabel(APP_NAME)
        name.setStyleSheet("color: #e8f5e9; font-size: 24px; font-weight: bold;")
        words.addWidget(name)
        tagline = QLabel(APP_TAGLINE)
        tagline.setStyleSheet("color: #a5c4a7; font-size: 13px;")
        words.addWidget(tagline)
        top.addLayout(words)
        top.addStretch()
        return top

    def _add_row(self, layout, key, title, note, *, primary="", path=""):
        colours = {"green": _PRIMARY, "amber": _AMBER}.get(primary, _PLAIN)
        row = _Row(title, note, colours, self)
        row.clicked.connect(lambda _c=False, k=key, p=path: self._pick(k, p))
        layout.addWidget(row)
        if primary:
            self._primary = row
        return row

    def _link(self, key: str, text: str, tooltip: str = "") -> QPushButton:
        btn = QPushButton(text)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setFlat(True)
        btn.setAutoDefault(False)
        btn.setStyleSheet(_LINK)
        if tooltip:
            btn.setToolTip(tooltip)
        btn.clicked.connect(lambda _c=False, k=key: self._pick(k))
        return btn

    @staticmethod
    def _rule() -> QFrame:
        """A hairline that draws: ``QFrame.HLine`` ignores a stylesheet
        ``color:``, so a 1 px frame with a background does what is meant."""
        line = QFrame()
        line.setFixedHeight(1)
        line.setStyleSheet("background-color: #2f4a30; border: none;")
        return line

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

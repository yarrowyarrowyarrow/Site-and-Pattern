"""
welcome_dialog.py — the start menu (F44, promoted in V2.40).

Three doors, because a blank map is not a choice — it is an absence of one:

  * **Generate a design** — the fastest path to something on screen.
  * **Start from my yard** — pin, boundary, plant it yourself.
  * **Open the example** — a worked design to look at and pull apart.

Until V2.40 that was the whole of it, shown **once**, on first launch. It was a
good dialog aimed at the wrong moment: a greeting for someone who has never used
the app, which a returning user never saw again. It is now a start menu, shown
every launch, and it grows three more rows as they become true:

  * **Recover unsaved work** — a previous session died with changes in it.
  * **Continue — “<name>”** — the design you were last in, still on disk.
  * **Open a design** — the saves list (V2.39).

Each appears only when it has something to offer, so a first-time user sees
exactly the original three and a returning one sees their own work first. A row
that cannot do anything is worse than a missing row; this project has shipped
two of those.

Presentation only. The copy that describes the path comes from
:mod:`src.onboarding` so the welcome, the step bar and the Site panel cannot
drift apart, and the dialog itself neither touches the project nor the DB — it
returns a choice and the flow module acts on it.
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

#: Values returned by :meth:`WelcomeDialog.choice`.
GENERATE = "generate"
BLANK = "blank"
EXAMPLE = "example"
#: V2.40 — the rows that only exist when there is something behind them.
RECOVER = "recover"
CONTINUE = "continue"
OPEN = "open"

_CHOICES = (
    (GENERATE, "✨", "Generate a design",
     "Pick a few goals and let the app fill a bed with native plants that "
     "suit your site. Everything stays editable afterwards.", True),
    (BLANK, "🗺", "Start from my yard",
     "Drop a pin on your address, draw the area you want to plant, and "
     "choose the plants yourself.", False),
    (EXAMPLE, "🌾", "Open the example",
     "A finished front-yard lawn conversion — open it, score it, walk it in "
     "3D, and take it apart to see how it works.", False),
)


class _ChoiceButton(QPushButton):
    """A big, readable option row. Title + one line of what it actually does."""

    def __init__(self, icon: str, title: str, detail: str, primary: bool,
                 parent: QWidget | None = None):
        super().__init__(parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(76)
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


class WelcomeDialog(QDialog):
    """Ask what the user wants to do first. ``choice()`` is one of
    ``GENERATE`` / ``BLANK`` / ``EXAMPLE``, or ``""`` if they closed it."""

    def __init__(self, parent: QWidget | None = None, *,
                 last_design: str = "", recover: str = "",
                 has_saves: bool = False, first_run: bool = True):
        super().__init__(parent)
        self.setWindowTitle(
            f"Welcome to {APP_NAME}" if first_run else APP_NAME)
        self.setMinimumWidth(520)
        self._choice = ""
        # Carried, not inherited. Opened from the Help menu this dialog is a
        # child of the MainWindow and picks the theme up from its stylesheet;
        # opened as the start menu it is a top-level window that exists before
        # the MainWindow does, and the pale-green text below would be sitting
        # on the platform's default light dialog. The rows and labels set their
        # own colours, so this only paints the ground under them.
        self.setStyleSheet(BASE_SURFACE)

        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        title = QLabel(f"<b>{APP_NAME}</b> — {APP_TAGLINE}")
        title.setStyleSheet("color: #e8f5e9; font-size: 17px;")
        layout.addWidget(title)

        blurb = QLabel(
            "Turn lawn into habitat for the plants, birds, bees and "
            "butterflies that already belong here. Where would you like to "
            "start?")
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
        if has_saves or last_design:
            # Nothing saved yet means this row can only open an empty list.
            # It would explain itself, but a first-time user does not need a
            # door to an empty room on the screen that is meant to get them
            # started.
            resume.append((
                OPEN, "📂", "Open a design",
                "Your saved designs, newest first — with what is in each one."))

        for i, (key, icon, head, detail) in enumerate(resume):
            btn = _ChoiceButton(icon, head, detail, i == 0 and bool(recover),
                                self)
            btn.clicked.connect(lambda _checked=False, k=key: self._pick(k))
            layout.addWidget(btn)

        if resume:
            sep = QFrame()
            sep.setFrameShape(QFrame.Shape.HLine)
            sep.setStyleSheet("color: #2e4a2e;")
            layout.addWidget(sep)

        # ── Or start something ──────────────────────────────────────────────
        for key, icon, head, detail, primary in _CHOICES:
            # Only the top row of the whole dialog gets the primary treatment;
            # two "obvious" buttons is none.
            btn = _ChoiceButton(icon, head, detail,
                                primary and not (recover or last_design), self)
            btn.clicked.connect(lambda _checked=False, k=key: self._pick(k))
            layout.addWidget(btn)

        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet("color: #2e4a2e;")
        layout.addWidget(line)

        # The same three steps the step bar shows, so the dialog teaches the
        # path rather than just branching on it.
        path = QLabel("Whichever you pick, the path is the same: "
                      + "  →  ".join(f"<b>{i}.</b> {s['title']}"
                                     for i, s in enumerate(STEPS, 1)))
        path.setWordWrap(True)
        path.setStyleSheet("color: #90a4ae; font-size: 11px;")
        layout.addWidget(path)

        foot = QHBoxLayout()
        self._dont_show = QCheckBox("Don't show this again")
        self._dont_show.setStyleSheet("color: #90a4ae; font-size: 11px;")
        foot.addWidget(self._dont_show)
        foot.addStretch()
        close = QPushButton("Close")
        close.clicked.connect(self.reject)
        foot.addWidget(close)
        layout.addLayout(foot)

    def _pick(self, key: str):
        self._choice = key
        self.accept()

    def choice(self) -> str:
        return self._choice

    def suppressed(self) -> bool:
        """True when the user asked not to be shown this again. Honoured on
        Close as well as on a choice — dismissing *is* an answer."""
        return self._dont_show.isChecked()

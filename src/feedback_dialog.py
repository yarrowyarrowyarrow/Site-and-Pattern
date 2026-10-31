"""
feedback_dialog.py — the "tell me what you think" surface (V2.37).

Design principle P13 — see docs/DESIGN_PHILOSOPHY.md

Renders only; every decision about what a report contains lives in the Qt-free
``src/feedback.py``. Two things the layout is doing on purpose:

  * The category buttons come first and are phrased as things a person would
    say ("I got stuck"), not as issue types. A tester who cannot name their
    problem as a defect still has something worth hearing.
  * The diagnostics are shown in full, in a read-only box, before the checkbox
    that attaches them. Nothing leaves the machine that the user has not read.
  * No account is needed (FN-8, V3.31): the edition's address is shown to copy,
    *Copy message* puts the whole report on the clipboard, and *Report it on
    GitHub* is the second way. With no address named, GitHub and the copy are
    what is offered.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QApplication, QCheckBox, QDialog, QDialogButtonBox, QHBoxLayout, QLabel,
    QPlainTextEdit, QPushButton, QVBoxLayout,
)

from src.feedback import CATEGORIES, category, email_text, format_diagnostics

#: The ways a report leaves, as :meth:`FeedbackDialog.way` reports them.
EMAIL, GITHUB = "email", "github"

_CAT_STYLE = """
QPushButton {
    background: #1a2a1a; color: #c8e6c9; border: 1px solid #2e4a2e;
    border-radius: 4px; padding: 7px 10px; font-size: 12px;
}
QPushButton:hover { border-color: #4a7a4a; }
QPushButton:checked {
    background: #2e4a2e; color: #e8f5e9; border-color: #66bb6a; font-weight: bold;
}
"""


class FeedbackDialog(QDialog):
    """Collects a category + a message, and optionally the setup details."""

    def __init__(self, diagnostics: dict | None = None, parent=None,
                 address: str | None = None):
        super().__init__(parent)
        self.setWindowTitle("Send Feedback")
        self.setMinimumWidth(460)
        self._diag = diagnostics or {}
        self._key = CATEGORIES[0][0]
        if address is None:
            from src.region import feedback_address
            address = feedback_address()
        self._address = address
        self._way = ""
        self._build()

    def _build(self):
        root = QVBoxLayout(self)
        root.setSpacing(8)

        intro = QLabel(
            "Anything you noticed is worth sending — including the things that "
            "are just confusing, and the things that worked.")
        intro.setWordWrap(True)
        intro.setStyleSheet("color: #90a4ae; font-size: 12px;")
        root.addWidget(intro)

        row = QHBoxLayout()
        row.setSpacing(4)
        self._cat_btns = {}
        for key, label, _issue_label, _prompt in CATEGORIES:
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setStyleSheet(_CAT_STYLE)
            btn.clicked.connect(lambda _c=False, k=key: self._choose(k))
            row.addWidget(btn)
            self._cat_btns[key] = btn
        root.addLayout(row)

        self._prompt = QLabel()
        self._prompt.setWordWrap(True)
        self._prompt.setStyleSheet("color: #c8e6c9; font-size: 12px;")
        root.addWidget(self._prompt)

        self._text = QPlainTextEdit()
        self._text.setMinimumHeight(120)
        self._text.setStyleSheet(
            "QPlainTextEdit { background: #142014; color: #e8f5e9; "
            "border: 1px solid #2e4a2e; border-radius: 4px; padding: 6px; }")
        root.addWidget(self._text)

        self._attach = QCheckBox("Include my setup details")
        self._attach.setChecked(True)
        self._attach.setToolTip(
            "The version and operating system — what makes a report reproducible.\n"
            "Nothing about your design, your address or your site is included.")
        self._attach.stateChanged.connect(self._sync_diag)
        root.addWidget(self._attach)

        # Shown, not summarised: the user should be able to read every character
        # that will be attached before agreeing to attach it.
        self._diag_box = QLabel(format_diagnostics(self._diag))
        self._diag_box.setStyleSheet(
            "color: #90a4ae; font-size: 12px; background: #142014; "
            "border: 1px solid #24341f; border-radius: 3px; padding: 5px;")
        self._diag_box.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse)
        root.addWidget(self._diag_box)

        if self._address:
            where = QLabel(f"Email it to <b>{self._address}</b>: no account "
                           "needed. <i>Copy message</i> copies everything "
                           "above, ready to paste.")
        else:
            where = QLabel("<i>Copy message</i> copies everything above, "
                           "ready to paste into an email or a message.")
        where.setWordWrap(True)
        where.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse)
        where.setStyleSheet("color: #c8e6c9; font-size: 12px;")
        self._where = where
        root.addWidget(where)

        ways = QHBoxLayout()
        self._copy = QPushButton("Copy message")
        self._copy.clicked.connect(self._copy_message)
        ways.addWidget(self._copy)
        self._email = QPushButton("Open in my email…")
        self._email.setToolTip(
            "Opens your email program with the message filled in. If nothing "
            "opens, copy the message and send it to the address above.")
        self._email.clicked.connect(lambda: self._send(EMAIL))
        self._email.setVisible(bool(self._address))
        ways.addWidget(self._email)
        self._github = QPushButton("Report it on GitHub…")
        self._github.setToolTip(
            "Opens a prefilled report in your browser, which you can read and "
            "edit before posting. Needs a GitHub account.")
        self._github.clicked.connect(lambda: self._send(GITHUB))
        ways.addWidget(self._github)
        ways.addStretch(1)
        root.addLayout(ways)

        self._copied = QLabel("")
        self._copied.setStyleSheet("color: #a5d6a7; font-size: 12px;")
        root.addWidget(self._copied)

        note = QLabel("Nothing is sent from the app itself.")
        note.setWordWrap(True)
        note.setStyleSheet("color: #90a4ae; font-size: 12px;")
        root.addWidget(note)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

        self._text.textChanged.connect(self._sync_ok)
        self._choose(self._key)
        self._sync_ok()

    # ── state ────────────────────────────────────────────────────────────────

    def _choose(self, key: str):
        self._key = key
        for k, btn in self._cat_btns.items():
            btn.setChecked(k == key)
        self._prompt.setText(category(key)[3])

    def _sync_diag(self):
        self._diag_box.setVisible(self._attach.isChecked())

    def _sync_ok(self):
        # Nothing to send is not a report; keep the buttons honest rather than
        # opening a browser on an empty issue.
        has = bool(self._text.toPlainText().strip())
        for btn in (self._copy, self._email, self._github):
            btn.setEnabled(has)
        self._copied.setText("")

    def copy_text(self) -> str:
        return email_text(self._key, self.message(),
                          self._diag if self.wants_diagnostics() else None)

    def _copy_message(self):
        QApplication.clipboard().setText(self.copy_text())
        self._copied.setText(
            f"Copied. Paste it into an email to {self._address}."
            if self._address else "Copied.")

    def _send(self, way: str):
        self._way = way
        self.accept()

    # ── results ──────────────────────────────────────────────────────────────

    def way(self) -> str:
        """``"email"`` or ``"github"``: how the person chose to send it."""
        return self._way

    def address(self) -> str:
        return self._address

    def category_key(self) -> str:
        return self._key

    def message(self) -> str:
        return self._text.toPlainText().strip()

    def wants_diagnostics(self) -> bool:
        return self._attach.isChecked()

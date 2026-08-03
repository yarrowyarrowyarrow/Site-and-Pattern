"""
saves_dialog.py — the list of your designs (F87, V2.39).

Design principle P13 — see docs/DESIGN_PHILOSOPHY.md.

*"When loading a previously saved file they should be listed in the app rather
than opening the computer's file explorer."*

So: a list, newest first, each row saying what the design **is** — its name,
when you last touched it, how many plants and species, and the site. Enough to
tell two versions of the same yard apart without opening both.

The OS dialog is still one button away, because a design kept somewhere else is
a real thing and taking that away would be a worse trade than the one this
fixes. It is the second option now instead of the only one.

Opening goes through ``MainWindow._load_from_path`` — the same path as File →
Open and as the worked example. A second, near-identical load path is how the
panels and the title bar drift out of step.
"""

from __future__ import annotations

import os

from PyQt6.QtCore import Qt, QSize
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QListWidget, QListWidgetItem,
    QPushButton, QMessageBox, QAbstractItemView,
)

from src import saves

# Returned by exec() alongside the QDialog codes, so the caller can tell
# "chose a save" from "wants the file dialog" without a second round trip.
BROWSE = 2


class SavesDialog(QDialog):
    """Pick a design. ``chosen()`` is the path, or ``""`` if they hit Browse."""

    def __init__(self, parent=None, *, directory: str | None = None):
        super().__init__(parent)
        self.setWindowTitle("Open a Design")
        self.setMinimumSize(QSize(560, 420))
        self._directory = directory or saves.saves_dir()
        self._chosen = ""

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        self._blurb = QLabel("")
        self._blurb.setWordWrap(True)
        self._blurb.setStyleSheet("color: #90a4ae; font-size: 11px;")
        layout.addWidget(self._blurb)

        self._list = QListWidget()
        self._list.setAlternatingRowColors(True)
        self._list.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection)
        self._list.itemDoubleClicked.connect(lambda _i: self._open())
        self._list.currentItemChanged.connect(self._sync_buttons)
        layout.addWidget(self._list, 1)

        row = QHBoxLayout()
        self._btn_open = QPushButton("Open")
        self._btn_open.setDefault(True)
        self._btn_open.clicked.connect(self._open)
        row.addWidget(self._btn_open)

        self._btn_delete = QPushButton("Delete")
        self._btn_delete.clicked.connect(self._delete)
        row.addWidget(self._btn_delete)

        row.addStretch()

        btn_browse = QPushButton("Browse…")
        btn_browse.setToolTip("Open a design kept somewhere else on this "
                              "computer.")
        btn_browse.clicked.connect(lambda: self.done(BROWSE))
        row.addWidget(btn_browse)

        btn_cancel = QPushButton("Cancel")
        btn_cancel.clicked.connect(self.reject)
        row.addWidget(btn_cancel)
        layout.addLayout(row)

        self.refresh()

    # ── Contents ────────────────────────────────────────────────────────────

    def refresh(self):
        self._list.clear()
        entries = saves.list_saves(self._directory)
        for entry in entries:
            item = QListWidgetItem(
                f"{entry['name']}\n    {saves.when(entry)} · "
                f"{saves.summary_line(entry)}")
            item.setData(Qt.ItemDataRole.UserRole, entry["path"])
            if entry["error"]:
                # Listed, not hidden — a save disappearing from this list is
                # how a person concludes their work is gone. Marked so they can
                # see which one to worry about.
                item.setForeground(Qt.GlobalColor.darkYellow)
                item.setToolTip(entry["error"])
            else:
                item.setToolTip(entry["path"])
            self._list.addItem(item)

        if entries:
            self._blurb.setText(
                f"{len(entries)} design{'s' if len(entries) != 1 else ''} in "
                f"your saves folder. Double-click to open one.")
            self._list.setCurrentRow(0)
        else:
            self._blurb.setText(
                "No saved designs yet. Anything you save goes here — use "
                "Browse… to open a design kept elsewhere.")
        self._sync_buttons()

    def _sync_buttons(self, *_args):
        has = self._list.currentItem() is not None
        self._btn_open.setEnabled(has)
        self._btn_delete.setEnabled(has)

    # ── Actions ─────────────────────────────────────────────────────────────

    def _current_path(self) -> str:
        item = self._list.currentItem()
        return item.data(Qt.ItemDataRole.UserRole) if item else ""

    def _open(self):
        path = self._current_path()
        if not path:
            return
        self._chosen = path
        self.accept()

    def _delete(self):
        path = self._current_path()
        if not path:
            return
        name = os.path.basename(path)
        r = QMessageBox.question(
            self, "Delete design",
            f"Delete “{name}”?\n\nThis removes the file from your saves "
            f"folder. A one-save-old copy stays as “{name}.bak”.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel)
        if r != QMessageBox.StandardButton.Yes:
            return
        try:
            os.unlink(path)
        except OSError as exc:
            QMessageBox.warning(self, "Could not delete", str(exc))
            return
        saves.clear_cache()
        self.refresh()

    def chosen(self) -> str:
        return self._chosen

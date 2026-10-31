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

from PyQt6.QtCore import Qt, QSize
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QListWidget, QListWidgetItem,
    QPushButton, QAbstractItemView,
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
        if parent is None:
            # Opened from the start screen, before the main window (V3.37):
            # a top-level window inherits none of its stylesheet.
            from src.ui_style import WINDOW_STYLE
            self.setStyleSheet(WINDOW_STYLE)
        self._directory = directory or saves.saves_dir()
        # The design you were last in is listed when it lives elsewhere, as
        # the start screen counts it; not for a folder a caller names.
        self._include_last = directory is None
        self._chosen = ""

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        self._blurb = QLabel("")
        self._blurb.setWordWrap(True)
        self._blurb.setStyleSheet("color: #90a4ae; font-size: 12px;")
        layout.addWidget(self._blurb)

        self._list = QListWidget()
        self._list.setAlternatingRowColors(True)
        # Its own dark stripe: the palette's is near-white under Fusion, which
        # put the app's pale text on white once the list could open before
        # the main window (V3.37).
        self._list.setStyleSheet(
            "QListWidget { alternate-background-color: #213321; }")
        self._list.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection)
        # A long line is cut with "…" and whole in the tooltip, never a
        # sideways scroll bar under the list (V3.37).
        self._list.setTextElideMode(Qt.TextElideMode.ElideRight)
        self._list.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._list.itemDoubleClicked.connect(lambda _i: self._open())
        self._list.currentItemChanged.connect(self._sync_buttons)
        layout.addWidget(self._list, 1)

        row = QHBoxLayout()
        self._btn_open = QPushButton("Open")
        self._btn_open.setDefault(True)
        self._btn_open.clicked.connect(self._open)
        row.addWidget(self._btn_open)

        self._btn_rename = QPushButton("Rename…")
        self._btn_rename.setToolTip("Give this design a new name.")
        self._btn_rename.clicked.connect(self._rename)
        row.addWidget(self._btn_rename)

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
        entries = saves.your_designs(self._directory,
                                     include_last=self._include_last)
        for entry in entries:
            item = QListWidgetItem(
                f"{entry['name']}\n    {saves.when(entry)} · "
                f"{saves.summary_line(entry)}")
            item.setData(Qt.ItemDataRole.UserRole, entry["path"])
            item.setData(Qt.ItemDataRole.UserRole + 1,
                         bool(entry.get("elsewhere")))
            if entry["error"]:
                # Listed, not hidden — a save disappearing from this list is
                # how a person concludes their work is gone. Marked so they can
                # see which one to worry about.
                item.setForeground(Qt.GlobalColor.darkYellow)
                item.setToolTip(entry["error"])
            else:
                item.setToolTip("\n".join(
                    t for t in (entry["name"], entry.get("site", ""),
                                entry["path"]) if t))
            self._list.addItem(item)

        if entries:
            n = len(entries)
            where = ("in your saves folder" if not any(
                e.get("elsewhere") for e in entries) else "")
            self._blurb.setText(
                f"{n} design{'s' if n != 1 else ''}"
                + (f" {where}" if where else "")
                + ". Double-click to open one.")
            self._list.setCurrentRow(0)
        else:
            self._blurb.setText(
                "No saved designs yet. Anything you save goes here — use "
                "Browse… to open a design kept elsewhere.")
        self._sync_buttons()

    def _sync_buttons(self, *_args):
        item = self._list.currentItem()
        has = item is not None
        elsewhere = bool(has and item.data(Qt.ItemDataRole.UserRole + 1))
        self._btn_open.setEnabled(has)
        self._btn_rename.setEnabled(has)
        # A file kept outside the saves folder is the person's to delete
        # where they keep it, not from here; nor is the design open in the
        # window (V3.42, one rule with the start screen: saves.deletable).
        from src.start_flow import open_design_path
        path = self._current_path()
        is_open = has and not saves.deletable({"path": path},
                                              open_design_path(self.parent()))
        self._btn_delete.setEnabled(has and not elsewhere and not is_open)
        self._btn_delete.setToolTip(
            "This design is kept outside your saves folder." if elsewhere
            else "This design is open." if is_open else "")

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

    def _rename(self):
        """V3.23 (ST-7): a new name inside the file and on it. The design
        open in the window follows when it is the one renamed (one body with
        the start screen's Rename since V3.37: ``start_flow.rename_design``)."""
        from src import start_flow
        path = self._current_path()
        if not path:
            return
        target = start_flow.rename_design(self, path)
        if not target:
            return
        self.refresh()
        for row in range(self._list.count()):
            if self._list.item(row).data(Qt.ItemDataRole.UserRole) == target:
                self._list.setCurrentRow(row)
                break

    def _delete(self):
        """To the Recycle Bin with its backup, after a question naming the
        design (V3.42; it deleted for good before, and named the file)."""
        from src import start_flow
        path = self._current_path()
        if path and start_flow.delete_design(self, path):
            self.refresh()

    def chosen(self) -> str:
        return self._chosen

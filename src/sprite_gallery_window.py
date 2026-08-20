"""
src/sprite_gallery_window.py — the in-app 3D Sprite Gallery (V1.94).

A native window for inspecting every plant-body archetype and flower sprite the
3D viewer can render. It reuses the *real* viewer (:class:`Map3DWidget`, the same
one the 3D Preview uses) driven by Python ``apply_scene`` — no http server,
iframe, or CORS dance. Scenes come from :func:`src.sprite_gallery.gallery_scenes`
(shared with the standalone ``html/sprite_gallery.html`` generator), so the app
and the web gallery always show the same specimens.

A Detail [Stylised · Balanced · Lifelike] combo drives ``window.permaSetQuality`` so the
view stays snappy on weak hardware; the choice persists via QSettings.

**Contact sheet** (V2.29): a toggle that renders every listed sprite to a
thumbnail and lays them out in a grid. One specimen at a time is fine for
studying a plant and useless for judging the *library* — you cannot see that two
sprites are the same sprite, or which one looks worst, without putting them next
to each other. Each tile is drawn by the real viewer via ``window.permaSnapshot``
(push scene → snapshot → next), so the sheet cannot drift from what the app
renders. It honours the search box, so "Ribes" is a sheet of just the currants.

``open_sprite_gallery(main)`` is the entry point the View menu uses; it keeps a
singleton on ``main._sprite_gallery_window`` (no new MainWindow method — the
architecture guard's method ceiling stays meaningful).
"""

from __future__ import annotations

import base64

from PyQt6.QtCore import Qt, QSettings, QSize, QTimer
from PyQt6.QtGui import QIcon, QPixmap
from PyQt6.QtWidgets import (
    QComboBox, QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem,
    QProgressBar, QPushButton, QStackedWidget, QVBoxLayout, QWidget,
)

from src.map3d_widget import Map3DWidget
from src.branding import APP_NAME

# 0 Stylised · 1 Balanced · 2 Lifelike (shared with 3D Preview; see
# src/scene3d_window.py for why the labels changed in V2.34).
_DETAIL_KEY = "viewer3d/detail"
_DETAIL_LABELS = ["Stylised", "Balanced", "Lifelike"]
_THUMB_PX = 240                            # rendered size; also the grid cell size


class SpriteGalleryWindow(QWidget):
    """Browse the 3D sprite library: one labelled specimen per archetype and
    flower form, then EVERY seeded species rendered as the sprite a design
    containing it would actually show. Grouped by section, with a search box —
    the list is ~480 entries."""

    def __init__(self, main=None):
        super().__init__(None)             # top-level window
        self.setWindowTitle(f"{APP_NAME}: 3D Sprite Gallery")
        self.resize(1040, 720)

        # Built lazily/once — gallery_scenes() runs build_scene per specimen.
        from src.sprite_gallery import gallery_scenes
        self._scenes = gallery_scenes()

        self.viewer = Map3DWidget(self)
        self._list = QListWidget()
        self._list.setMaximumWidth(250)
        self._list.currentItemChanged.connect(self._on_select)

        self._caption = QLabel()
        self._caption.setWordWrap(True)
        self._caption.setTextFormat(Qt.TextFormat.RichText)
        self._caption.setMinimumHeight(46)

        self._detail = QComboBox()
        self._detail.addItems(_DETAIL_LABELS)
        self._detail.setToolTip(
            "Geometry detail — lower it if the view is sluggish on this machine")
        lvl = int(QSettings().value(_DETAIL_KEY, 1))
        self._detail.setCurrentIndex(max(0, min(2, lvl)))
        self._detail.currentIndexChanged.connect(self._on_detail)

        # ~480 entries once every seeded species is listed, so a search box is
        # not a nicety — it is how you find the plant you came here for.
        self._search = QLineEdit()
        self._search.setPlaceholderText("Search name or Latin…")
        self._search.setClearButtonEnabled(True)
        self._search.textChanged.connect(self._on_filter)

        self._populate_list()

        # ── contact sheet ────────────────────────────────────────────────
        # The viewer and the sheet share one slot: the sheet drives the viewer
        # to make its thumbnails, so they are never both useful at once.
        self._sheet = QListWidget()
        self._sheet.setViewMode(QListWidget.ViewMode.IconMode)
        self._sheet.setIconSize(QSize(_THUMB_PX, _THUMB_PX))
        self._sheet.setGridSize(QSize(_THUMB_PX + 18, _THUMB_PX + 46))
        self._sheet.setResizeMode(QListWidget.ResizeMode.Adjust)
        self._sheet.setMovement(QListWidget.Movement.Static)
        self._sheet.setWordWrap(True)
        self._sheet.setSpacing(4)
        self._sheet.itemActivated.connect(self._on_sheet_pick)
        self._sheet.itemClicked.connect(self._on_sheet_pick)

        self._stack = QStackedWidget()
        self._stack.addWidget(self.viewer)      # 0 — single specimen
        self._stack.addWidget(self._sheet)      # 1 — contact sheet

        self._sheet_btn = QPushButton("▦ Contact sheet")
        self._sheet_btn.setCheckable(True)
        self._sheet_btn.setToolTip(
            "Render every listed sprite as a thumbnail and show them together.\n"
            "Narrow the list with the search box first to build a smaller sheet.")
        self._sheet_btn.toggled.connect(self._on_sheet_toggled)

        self._progress = QProgressBar()
        self._progress.setVisible(False)
        self._progress.setTextVisible(True)

        # Sheet state: the render is a chain of single-shot timers rather than a
        # loop, so the window stays responsive and the user can cancel by
        # toggling off or searching again. `_sheet_run` invalidates a chain in
        # flight — without it, switching filters mid-render interleaves two
        # sheets into one grid.
        self._sheet_keys: list[str] = []
        self._sheet_i = 0
        self._sheet_run = 0

        left = QVBoxLayout()
        dl = QHBoxLayout()
        dl.addWidget(QLabel("Detail:"))
        dl.addWidget(self._detail, 1)
        left.addLayout(dl)
        left.addWidget(self._search)
        left.addWidget(self._sheet_btn)
        left.addWidget(self._list, 1)
        left_box = QWidget()
        left_box.setLayout(left)
        left_box.setMaximumWidth(250)

        right = QVBoxLayout()
        right.addWidget(self._stack, 1)
        right.addWidget(self._progress)
        right.addWidget(self._caption)
        right_box = QWidget()
        right_box.setLayout(right)

        root = QHBoxLayout(self)
        root.setContentsMargins(6, 6, 6, 6)
        root.addWidget(left_box)
        root.addWidget(right_box, 1)

        # Apply the saved detail level, then show the first specimen.
        self._push_quality(self._detail.currentIndex())
        for row in range(self._list.count()):
            if self._list.item(row).data(Qt.ItemDataRole.UserRole):
                self._list.setCurrentRow(row)
                break

    # ── list ──────────────────────────────────────────────────────────────
    def _populate_list(self, filter_text: str = ""):
        """Rebuild the sidebar, optionally narrowed to a search term.

        Headings come from each entry's own ``group`` rather than from sniffing
        key prefixes — the list is ~480 items once every seeded species is in it,
        so it needs real sections and a filter to be usable at all.
        """
        self._list.clear()
        needle = (filter_text or "").strip().lower()

        def section(title):
            it = QListWidgetItem(title)
            it.setFlags(Qt.ItemFlag.NoItemFlags)            # unselectable header
            f = it.font(); f.setBold(True); it.setFont(f)
            self._list.addItem(it)

        def entry(key):
            it = QListWidgetItem("  " + self._scenes[key]["name"])
            it.setData(Qt.ItemDataRole.UserRole, key)
            self._list.addItem(it)

        def matches(key, e):
            if not needle:
                return True
            # Scientific name lives in `example`, so a search for "Populus"
            # finds the aspens even though the label is the common name.
            return needle in " ".join((
                e.get("name", ""), e.get("example", ""),
                e.get("desc", ""))).lower()

        group = None
        shown = 0
        for key, e in self._scenes.items():
            if not matches(key, e):
                continue
            if e.get("group") and e["group"] != group:
                group = e["group"]
                section(group)
            entry(key)
            shown += 1
        if not shown:
            section("no sprite matches that search")
        return shown

    def _on_filter(self, text: str):
        self._populate_list(text)
        if self._sheet_btn.isChecked():
            self._start_sheet()          # the search narrows the SHEET
            return
        # Select the first real entry so the view follows the search.
        for row in range(self._list.count()):
            if self._list.item(row).data(Qt.ItemDataRole.UserRole):
                self._list.setCurrentRow(row)
                break

    def _listed_keys(self) -> list[str]:
        """The keys currently shown in the sidebar, in order (headings skipped)."""
        out = []
        for row in range(self._list.count()):
            key = self._list.item(row).data(Qt.ItemDataRole.UserRole)
            if key and key in self._scenes and key != "all":
                out.append(key)
        return out

    # ── contact sheet ────────────────────────────────────────────────────
    def _on_sheet_toggled(self, on: bool):
        self._sheet_btn.setText("◧ Single view" if on else "▦ Contact sheet")
        if on:
            self._start_sheet()
        else:
            self._sheet_run += 1                  # cancel any chain in flight
            self._progress.setVisible(False)
            self._stack.setCurrentIndex(0)
            self._on_select(self._list.currentItem())

    def _start_sheet(self):
        self._sheet_run += 1
        run = self._sheet_run
        self._sheet.clear()
        self._sheet_keys = self._listed_keys()
        self._sheet_i = 0
        self._stack.setCurrentIndex(1)
        self._progress.setMaximum(max(1, len(self._sheet_keys)))
        self._progress.setValue(0)
        self._progress.setFormat("Rendering %v / %m sprites…")
        self._progress.setVisible(True)
        self._caption.setText(
            f"<b>Contact sheet</b> &middot; {len(self._sheet_keys)} sprites"
            " &mdash; click a tile to open it.")
        # Baked GLB archetypes load asynchronously and rebuild the scene when
        # they arrive. A sheet built before that is a sheet of the PROCEDURAL
        # FALLBACK geometry — which looks like a finished answer and is not the
        # one the app draws. Wait, with a bounded number of retries.
        self._wait_for_models(run, 0)

    def _wait_for_models(self, run: int, tries: int):
        if run != self._sheet_run:
            return
        if tries > 60:                            # ~6 s — go with what we have
            self._render_next(run)
            return

        def got(ready):
            if run != self._sheet_run:
                return
            if ready:
                self._render_next(run)
            else:
                QTimer.singleShot(
                    100, lambda: self._wait_for_models(run, tries + 1))

        self.viewer.models_ready(got)

    def _render_next(self, run: int):
        if run != self._sheet_run or self._sheet_i >= len(self._sheet_keys):
            if run == self._sheet_run:
                self._progress.setVisible(False)
            return
        key = self._sheet_keys[self._sheet_i]
        entry = self._scenes[key]
        # apply_scene builds the scene AND frames the camera synchronously in the
        # viewer, so the snapshot can follow immediately — no frame to wait for.
        self.viewer.apply_scene(entry["scene"])

        def got(url):
            if run != self._sheet_run:
                return
            self._add_tile(key, entry, url)
            self._sheet_i += 1
            self._progress.setValue(self._sheet_i)
            QTimer.singleShot(0, lambda: self._render_next(run))

        self.viewer.snapshot(got, px=_THUMB_PX)

    def _add_tile(self, key: str, entry: dict, url: str):
        item = QListWidgetItem(entry.get("name") or key)
        item.setData(Qt.ItemDataRole.UserRole, key)
        item.setToolTip(f"{entry.get('name', '')}\n{entry.get('desc', '')}")
        item.setTextAlignment(Qt.AlignmentFlag.AlignHCenter
                              | Qt.AlignmentFlag.AlignTop)
        pix = _pixmap_from_data_url(url)
        if pix is not None:
            item.setIcon(QIcon(pix))
        self._sheet.addItem(item)

    def _on_sheet_pick(self, item):
        key = item.data(Qt.ItemDataRole.UserRole) if item else None
        if not key:
            return
        self._sheet_btn.setChecked(False)         # → single view via _on_sheet_toggled
        for row in range(self._list.count()):
            if self._list.item(row).data(Qt.ItemDataRole.UserRole) == key:
                self._list.setCurrentRow(row)
                break

    def _on_select(self, item, _prev=None):
        if item is None:
            return
        key = item.data(Qt.ItemDataRole.UserRole)
        if not key or key not in self._scenes:
            return
        entry = self._scenes[key]
        self.viewer.apply_scene(entry["scene"])
        ex = (f" &middot; <i>{entry['example']}</i>" if entry.get("example") else "")
        self._caption.setText(
            f"<b>{entry['name']}</b>{ex}<br>{entry.get('desc', '')}")

    # ── detail / quality ─────────────────────────────────────────────────
    def _on_detail(self, level: int):
        QSettings().setValue(_DETAIL_KEY, int(level))
        self._push_quality(level)

    def _push_quality(self, level: int):
        self.viewer.set_quality(level)


def _pixmap_from_data_url(url):
    """``QPixmap`` from a ``data:image/...;base64,...`` URL, or None.

    Qt-side decode rather than handing the URL to a QLabel: the thumbnails live
    in a QListWidget as icons, and a malformed or empty result (an unloaded
    viewer returns ``''``) must degrade to a captionless tile rather than raise
    in the middle of a 400-tile render.
    """
    if not url or "," not in url:
        return None
    try:
        raw = base64.b64decode(url.split(",", 1)[1])
    except Exception:                              # noqa: BLE001
        return None
    pix = QPixmap()
    return pix if pix.loadFromData(raw) else None


def open_sprite_gallery(main=None) -> SpriteGalleryWindow:
    """Show (or raise) the singleton sprite gallery."""
    win = getattr(main, "_sprite_gallery_window", None) if main is not None else None
    if win is None:
        win = SpriteGalleryWindow(main)
        if main is not None:
            main._sprite_gallery_window = win
    win.show()
    win.raise_()
    win.activateWindow()
    return win

"""
src/sprite_gallery_window.py — the in-app 3D Sprite Gallery (V1.94).

A native window for inspecting every plant-body archetype and flower sprite the
3D viewer can render. It reuses the *real* viewer (:class:`Map3DWidget`, the same
one the 3D Preview uses) driven by Python ``apply_scene`` — no http server,
iframe, or CORS dance. Scenes come from :func:`src.sprite_gallery.gallery_scenes`
(shared with the standalone ``html/sprite_gallery.html`` generator), so the app
and the web gallery always show the same specimens.

A Detail [Low · Medium · High] combo drives ``window.permaSetQuality`` so the
view stays snappy on weak hardware; the choice persists via QSettings.

``open_sprite_gallery(main)`` is the entry point the View menu uses; it keeps a
singleton on ``main._sprite_gallery_window`` (no new MainWindow method — the
architecture guard's method ceiling stays meaningful).
"""

from __future__ import annotations

from PyQt6.QtCore import Qt, QSettings
from PyQt6.QtWidgets import (
    QComboBox, QHBoxLayout, QLabel, QListWidget, QListWidgetItem,
    QVBoxLayout, QWidget,
)

from src.map3d_widget import Map3DWidget
from src.branding import APP_NAME

_DETAIL_KEY = "viewer3d/detail"            # 0 Low · 1 Medium · 2 High (shared with 3D Preview)
_DETAIL_LABELS = ["Low", "Medium", "High"]


class SpriteGalleryWindow(QWidget):
    """Browse the 3D sprite library — one specimen per archetype / flower form."""

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

        self._populate_list()

        left = QVBoxLayout()
        dl = QHBoxLayout()
        dl.addWidget(QLabel("Detail:"))
        dl.addWidget(self._detail, 1)
        left.addLayout(dl)
        left.addWidget(self._list, 1)
        left_box = QWidget()
        left_box.setLayout(left)
        left_box.setMaximumWidth(250)

        right = QVBoxLayout()
        right.addWidget(self.viewer, 1)
        right.addWidget(self._caption)
        right_box = QWidget()
        right_box.setLayout(right)

        root = QHBoxLayout(self)
        root.setContentsMargins(6, 6, 6, 6)
        root.addWidget(left_box)
        root.addWidget(right_box, 1)

        # Apply the saved detail level, then show the first specimen.
        self._push_quality(self._detail.currentIndex())
        if self._list.count():
            self._list.setCurrentRow(0)

    # ── list ──────────────────────────────────────────────────────────────
    def _populate_list(self):
        def section(title):
            it = QListWidgetItem(title)
            it.setFlags(Qt.ItemFlag.NoItemFlags)            # unselectable header
            f = it.font(); f.setBold(True); it.setFont(f)
            self._list.addItem(it)

        def entry(key):
            it = QListWidgetItem("  " + self._scenes[key]["name"])
            it.setData(Qt.ItemDataRole.UserRole, key)
            self._list.addItem(it)

        keys = list(self._scenes.keys())
        geom = [k for k in keys if k != "all" and not k.startswith("flower_")]
        flowers = [k for k in keys if k.startswith("flower_")]
        if "all" in self._scenes:
            entry("all")
        section("Plant-body geometry")
        for k in geom:
            entry(k)
        section("Flower sprites")
        for k in flowers:
            entry(k)

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

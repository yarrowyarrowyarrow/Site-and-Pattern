"""
photo_strip.py — a plant's photographs on its page (V3.35, F251).

Design principle P13 — see docs/DESIGN_PHILOSOPHY.md.

The plant page showed one photograph. The owner, after the colour review: "I
greatly enjoyed the multiple photos". Now the first photograph shows large,
the others as a row of thumbnails under it, and choosing one shows it large
with its own credit, linked to its page on iNaturalist (where the licence and
the observation are). The order is ``src.db.plants.photo_order``: a person's
own photograph, then the order the owner picked, the flower first.

The strip warms its own photographs, off the UI thread, and redraws when one
lands; ``qt_safety.emit_if_alive`` keeps a fetch that finishes after the page
moved on from emitting into a deleted widget.
"""

from __future__ import annotations

import html
from typing import Callable, Optional

from PyQt6.QtCore import QRunnable, QSize, Qt, QThreadPool, pyqtSignal
from PyQt6.QtGui import QIcon, QPixmap
from PyQt6.QtWidgets import (QButtonGroup, QHBoxLayout, QLabel, QToolButton,
                             QVBoxLayout, QWidget)

from src.photo_picks import caption, photo_page

_DIM = "color: #90a4ae; font-size: 12px;"
_LINK = "color: #ffe082;"
_THUMB_STYLE = (
    "QToolButton { color: #c8e6c9; background: #263238; font-size: 13px; "
    "border: 1px solid #455a64; border-radius: 4px; } "
    "QToolButton:checked { border: 2px solid #ffe082; }")
THUMB = 48
HEIGHT = 240


def credit_for(photo: dict) -> str:
    from src.image_cache import credit_line                 # noqa: PLC0415
    return credit_line(photo.get("attribution") or "",
                       photo.get("license") or "")


class PhotoStrip(QWidget):
    """The selected photograph large, its credit, and thumbnails of the rest.

    ``on_select(index)`` is told when a thumbnail is chosen, so the page can
    keep the choice across a redraw."""

    photo_ready = pyqtSignal(str)

    def __init__(self, photos: list, name: str, *, width: int = 320,
                 selected: int = 0, on_select: Optional[Callable] = None,
                 parent=None):
        super().__init__(parent)
        self._photos = [p for p in photos or [] if (p.get("url") or "").strip()]
        self._name = name or "this plant"
        self._width = width
        self._on_select = on_select
        self._selected = selected if 0 <= selected < len(self._photos) else 0
        col = QVBoxLayout(self)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(4)
        self._big = QLabel()
        self._big.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse)
        col.addWidget(self._big)
        self._credit = QLabel()
        self._credit.setStyleSheet(_DIM)
        self._credit.setWordWrap(True)
        self._credit.setTextFormat(Qt.TextFormat.RichText)
        self._credit.setOpenExternalLinks(True)
        self._credit.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextBrowserInteraction)
        col.addWidget(self._credit)
        self._thumbs: list = []
        if len(self._photos) > 1:
            row = QHBoxLayout()
            row.setSpacing(4)
            group = QButtonGroup(self)
            group.setExclusive(True)
            for i, photo in enumerate(self._photos):
                btn = QToolButton()
                btn.setCheckable(True)
                btn.setStyleSheet(_THUMB_STYLE)
                btn.setFixedSize(THUMB, THUMB)
                btn.setIconSize(QSize(THUMB - 6, THUMB - 6))
                words = caption(photo, i + 1, len(self._photos))
                credit = credit_for(photo)
                btn.setAccessibleName(f"{words}. {credit}" if credit else words)
                btn.setToolTip(btn.accessibleName())
                btn.clicked.connect(lambda _c=False, i=i: self.select(i))
                group.addButton(btn)
                row.addWidget(btn)
                self._thumbs.append(btn)
            row.addStretch()
            col.addLayout(row)
        self.photo_ready.connect(self._landed)
        self._paint()
        self._warm()

    def selected(self) -> int:
        return self._selected

    def select(self, index: int):
        if not 0 <= index < len(self._photos):
            return
        self._selected = index
        if self._on_select is not None:
            self._on_select(index)
        self._paint()

    # ── Drawing ─────────────────────────────────────────────────────────────

    def _paint(self):
        from src.image_cache import get_cached_image             # noqa: PLC0415
        for i, btn in enumerate(self._thumbs):
            btn.setChecked(i == self._selected)
            path = get_cached_image(self._photos[i]["url"])
            pix = QPixmap(path) if path else QPixmap()
            if not pix.isNull():
                btn.setIcon(QIcon(pix.scaled(
                    btn.iconSize(), Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                    Qt.TransformationMode.SmoothTransformation)))
                btn.setText("")
            else:
                btn.setText(str(i + 1))
        if not self._photos:
            self._big.setText("No photo yet.")
            self._big.setStyleSheet(_DIM)
            self._credit.hide()
            return
        photo = self._photos[self._selected]
        path = get_cached_image(photo["url"])
        pix = QPixmap(path) if path else QPixmap()
        credit = credit_for(photo)
        if pix.isNull():
            self._big.setPixmap(QPixmap())
            self._big.setText("Photo not downloaded yet: it appears when you "
                              "are online.")
            self._big.setStyleSheet(_DIM)
        else:
            # Inside 320 x 240 either way round: a herbarium sheet scaled to
            # the width alone stood 356 px tall and pushed every section below
            # the fold.
            self._big.setStyleSheet("")
            self._big.setPixmap(pix.scaled(
                QSize(self._width, HEIGHT), Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation))
        words = (caption(photo, self._selected + 1, len(self._photos))
                 if len(self._photos) > 1 else "")
        self._big.setAccessibleName(
            f"Photograph of {self._name}" + (f", {words.lower()}" if words else "")
            + (f". {credit}" if credit else ""))
        self._big.setToolTip(credit)
        page = photo_page(photo["url"])
        text = html.escape(credit)
        if credit and page:
            text = f'<a href="{html.escape(page)}" style="{_LINK}">{text}</a>'
        self._credit.setText(text)
        self._credit.setVisible(bool(credit))
        self._credit.setAccessibleName(f"Credit: {credit}" if credit else "")

    def _landed(self, url: str):
        if any(p["url"] == url for p in self._photos):
            self._paint()

    # ── Fetching ────────────────────────────────────────────────────────────

    def _warm(self):
        """Start caching every photograph not yet on disk; each one that
        lands redraws the strip."""
        try:
            from src.image_cache import get_cached_image          # noqa: PLC0415
        except Exception:                                         # noqa: BLE001
            return
        owner = self
        for photo in self._photos:
            url = photo["url"]
            if get_cached_image(url):
                continue
            attribution = photo.get("attribution") or ""
            licence = photo.get("license") or ""

            class _Fetch(QRunnable):
                def run(self, url=url, attribution=attribution,
                        licence=licence):
                    try:
                        from src.image_cache import resolve_image  # noqa: PLC0415
                        from src.qt_safety import emit_if_alive    # noqa: PLC0415
                        if resolve_image(url, attribution, licence):
                            emit_if_alive(owner, "photo_ready", url)
                    except Exception:                             # noqa: BLE001
                        pass

            try:
                QThreadPool.globalInstance().start(_Fetch())
            except Exception:                                     # noqa: BLE001
                pass

"""
src/snapshot_window.py — the "Growth Snapshots" window (F2).

A 2×2 of top-down canopy renders of the *same design* at years 1 / 5 / 15 / 30,
so the user can watch the yard fill in rather than judging it on planting day
(design principle P4 — see docs/DESIGN_PHILOSOPHY.md). All four panels share one
world→pixel transform, so a plant stays in the same spot across the grid and the
thing that visibly changes is its growth.

The scenes come from :func:`src.snapshot_timeline.build_snapshots` (which leans
on the same :func:`src.scene_contract.build_scene` the 3D view uses), so this
window owns no geometry — only the QPainter drawing, in the spirit of
:mod:`src.wind_rose_widget`.

``open_snapshot_view(main)`` is the entry point the View menu uses; it keeps a
singleton window on ``main._snapshot_window`` (no new MainWindow method — the
architecture guard's method ceiling stays meaningful), mirroring
:func:`src.scene3d_window.open_3d_view`.
"""

from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import Qt, QRectF, QPointF
from PyQt6.QtGui import QColor, QPainter, QPolygonF
from PyQt6.QtWidgets import (
    QGridLayout, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget,
)

from src.branding import APP_NAME

_BG_COLOR = "#0d160d"
_BOUNDARY_PEN = "#3e5e42"
_BOUNDARY_FILL = QColor(20, 40, 20)
_FALLBACK_PLANT_COLOR = "#66bb6a"


def _union_bounds(scenes) -> Optional[dict]:
    """The bounding box covering every scene (the per-year boxes are the same
    — plant centres don't move as they grow — but a union is robust)."""
    boxes = [s.get("bounds") for s in scenes if s and s.get("bounds")]
    if not boxes:
        return None
    return {
        "min_x": min(b["min_x"] for b in boxes),
        "min_y": min(b["min_y"] for b in boxes),
        "max_x": max(b["max_x"] for b in boxes),
        "max_y": max(b["max_y"] for b in boxes),
    }


class SnapshotCanvas(QWidget):
    """Top-down canopy render of one scene at one growth year."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._scene: Optional[dict] = None
        self._year: Optional[int] = None
        self._bounds: Optional[dict] = None
        self.setMinimumSize(220, 200)

    def set_panel(self, scene: Optional[dict], year: Optional[int],
                  bounds: Optional[dict]):
        self._scene, self._year, self._bounds = scene, year, bounds
        self.update()

    def paintEvent(self, _ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        p.fillRect(self.rect(), QColor(_BG_COLOR))

        b = self._bounds
        if not self._scene or not b:
            p.setPen(QColor("#90a4ae"))
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "—")
            p.end()
            return

        margin = 12
        span_x = max(b["max_x"] - b["min_x"], 1e-6)
        span_y = max(b["max_y"] - b["min_y"], 1e-6)
        scale = min((w - 2 * margin) / span_x, (h - 2 * margin) / span_y)
        off_x = (w - span_x * scale) / 2.0
        off_y = (h - span_y * scale) / 2.0

        def to_px(x, y):
            # +y is north → flip so north is up.
            return QPointF(off_x + (x - b["min_x"]) * scale,
                           off_y + (b["max_y"] - y) * scale)

        boundary = self._scene.get("boundary")
        if boundary:
            poly = QPolygonF([to_px(px, py) for px, py in boundary])
            p.setPen(QColor(_BOUNDARY_PEN))
            p.setBrush(_BOUNDARY_FILL)
            p.drawPolygon(poly)

        # Largest canopies first so smaller plants sit on top (a tree shouldn't
        # bury the groundcover beneath it).
        plants = sorted(self._scene.get("plants", []),
                        key=lambda pl: -(pl.get("canopy_m") or 0.0))
        p.setPen(Qt.PenStyle.NoPen)
        for pl in plants:
            centre = to_px(pl["x"], pl["y"])
            r = max((pl.get("canopy_m") or 0.3) / 2.0 * scale, 1.5)
            color = QColor(pl.get("color") or _FALLBACK_PLANT_COLOR)
            opacity = pl.get("opacity")
            if opacity is not None:
                # Fading successional plants stay dimly visible (never invisible).
                color.setAlphaF(max(0.15, min(1.0, float(opacity))))
            p.setBrush(color)
            p.drawEllipse(centre, r, r)

        p.setPen(QColor("#dcedc8"))
        font = p.font()
        font.setBold(True)
        font.setPointSize(11)
        p.setFont(font)
        label = "Mature" if self._year in (0, None) else f"Year {self._year}"
        p.drawText(QRectF(10, 6, w - 20, 22),
                   Qt.AlignmentFlag.AlignLeft, label)
        p.end()


class SnapshotWindow(QWidget):
    """The 2×2 growth-snapshot comparison for the current design."""

    def __init__(self, main):
        super().__init__(None)   # top-level window
        self._main = main
        self.setWindowTitle(f"{APP_NAME}: Growth Snapshots")
        self.resize(720, 700)

        root = QVBoxLayout(self)
        intro = QLabel(
            "Watch your design mature: the same plan at years 1, 5, 15 and 30. "
            "Plants grow and self-seeders spread; faint plants are pioneers "
            "fading as the community matures.")
        intro.setWordWrap(True)
        root.addWidget(intro)

        grid = QGridLayout()
        grid.setSpacing(8)
        self._canvases: list[SnapshotCanvas] = []
        for i in range(4):
            canvas = SnapshotCanvas(self)
            self._canvases.append(canvas)
            grid.addWidget(canvas, i // 2, i % 2)
        root.addLayout(grid, 1)

        row = QHBoxLayout()
        self._status = QLabel("")
        row.addWidget(self._status, 1)
        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self.refresh)
        row.addWidget(refresh_btn)
        root.addLayout(row)

    def refresh(self):
        """Re-read the live project and rebuild the four panels."""
        from src.snapshot_timeline import build_snapshots
        try:
            snaps = build_snapshots(self._main._project)
        except Exception:  # noqa: BLE001 — a snapshot view should never crash
            snaps = []

        bounds = _union_bounds([s["scene"] for s in snaps])
        for i, canvas in enumerate(self._canvases):
            if i < len(snaps):
                canvas.set_panel(snaps[i]["scene"], snaps[i]["year"], bounds)
            else:
                canvas.set_panel(None, None, None)

        has_plants = bool(snaps and snaps[0]["scene"].get("plants"))
        self._status.setText(
            "" if has_plants
            else "No plants placed yet. Add some to watch them grow.")


def open_snapshot_view(main) -> SnapshotWindow:
    """Show (or raise) the singleton growth-snapshot window for ``main``."""
    win = getattr(main, "_snapshot_window", None)
    if win is None:
        win = SnapshotWindow(main)
        main._snapshot_window = win
    win.show()
    win.raise_()
    win.activateWindow()
    win.refresh()
    return win

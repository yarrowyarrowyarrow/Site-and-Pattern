"""
src/scan_import_dialog.py — the "Import Yard Scan…" flow (V1.63).

GUI on top of the :mod:`src.scan_import` engine. The user picks a scan
export (PLY/XYZ/LAS), sees a top-down height preview of it, and pairs
2+ control points ("this spot on the scan ⟷ this spot on the map"):
click a spot on the preview, then click the matching spot on the live
map; repeat; Import. The engine georeferences (rotation + scale + shift),
rasterizes, vectorizes, and the scanned structures land as shade-casting
footprints — rendered through the same loader as the GeoTIFF footprint
import — plus a point-cloud sample for the 3D preview.

Split on purpose:

  * :class:`ScanAlignSession` — Qt-free pairing/state logic + preview
    raster + engine invocation, unit-testable without a display;
  * :class:`ScanImportDialog` — the Qt shell: preview label, pair list,
    one-shot hookup to the map's ``map_clicked`` bridge signal;
  * :func:`start_scan_import` — the File-menu entry point (kept off
    MainWindow so the architecture guard's method ceiling holds).
"""

from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import Qt, QObject, QThread, pyqtSignal
from PyQt6.QtGui import QImage, QPixmap
from PyQt6.QtWidgets import (
    QCheckBox, QDialog, QFileDialog, QHBoxLayout, QInputDialog, QLabel,
    QListWidget, QMessageBox, QPushButton, QVBoxLayout,
)

_PREVIEW_MAX_PX = 420       # longest preview edge
_MIN_PAIRS = 2


class ScanAlignSession:
    """Pairing state + preview raster + engine invocation (Qt-free)."""

    def __init__(self, points, *, file_path: Optional[str] = None,
                 is_splat: bool = False, up: str = "z"):
        self.points = points                  # (N, 3) aligned-input cloud
        self.file_path = file_path            # source file (splat backdrop path)
        self.is_splat = bool(is_splat)        # a Gaussian-splat PLY?
        self.up = up                          # vertical axis the points were read with
        self.pairs: list = []                 # [{"scan": (x, y), "map": (lat, lng)}]
        self.pending_scan: Optional[tuple] = None
        self._preview = None                  # cached (heights, extent, cell)

    # ── preview raster ────────────────────────────────────────────────────

    def preview_grid(self):
        """Coarse nDSM for the preview image: ``(heights_2d, extent,
        cell_m)`` with row 0 = north; NaN = no points."""
        if self._preview is None:
            import numpy as np
            from src.scan_import import rasterize_ndsm
            x = self.points[:, 0]
            y = self.points[:, 1]
            span = max(float(x.max() - x.min()), float(y.max() - y.min()),
                       1e-6)
            cell = max(0.05, span / _PREVIEW_MAX_PX)
            grid, extent = rasterize_ndsm(self.points, cell_m=cell)
            self._preview = (grid, extent, cell)
        return self._preview

    def pixel_to_scan_xy(self, px: float, py: float) -> tuple:
        """Preview pixel (col, row) → scan-frame (x, y) metres."""
        _grid, (min_x, _min_y, _max_x, max_y), cell = self.preview_grid()
        return (min_x + (px + 0.5) * cell, max_y - (py + 0.5) * cell)

    # ── pairing state machine ─────────────────────────────────────────────

    def click_scan(self, scan_xy: tuple) -> None:
        """A spot was picked on the preview — it becomes the pending half
        of the next pair (re-clicking just replaces it)."""
        self.pending_scan = (float(scan_xy[0]), float(scan_xy[1]))

    def click_map(self, lat: float, lng: float) -> bool:
        """A spot was picked on the map. Completes the pending pair;
        returns False (ignored) when no scan half is pending."""
        if self.pending_scan is None:
            return False
        self.pairs.append({"scan": self.pending_scan,
                           "map": (float(lat), float(lng))})
        self.pending_scan = None
        return True

    def remove_pair(self, index: int) -> None:
        if 0 <= index < len(self.pairs):
            self.pairs.pop(index)

    @property
    def ready(self) -> bool:
        return len(self.pairs) >= _MIN_PAIRS

    # ── engine ────────────────────────────────────────────────────────────

    def run_import(self, project_dict: dict, *,
                   cell_m: float = 0.25, min_height_m: float = 2.0) -> dict:
        """Georeference with the collected pairs and land the footprints in
        ``project_dict``. Returns ``{"features", "scan_sample"}`` (the
        :func:`src.scan_import.import_scan` shape)."""
        from src.footprint_extract import add_extracted_footprints
        from src.scan_import import (align_scan, sample_for_scene,
                                     scan_to_footprints)
        if not self.ready:
            raise ValueError(f"need at least {_MIN_PAIRS} control-point "
                             f"pairs ({len(self.pairs)} so far)")
        aligned, proj = align_scan(
            self.points,
            [p["scan"] for p in self.pairs],
            [p["map"] for p in self.pairs])
        rings = scan_to_footprints(aligned, proj, cell_m,
                                   min_height_m=min_height_m)
        return {
            "features": add_extracted_footprints(rings, project_dict,
                                                 source="scan"),
            "scan_sample": sample_for_scene(aligned, proj),
        }

    def backdrop_feature(self) -> dict:
        """Build the ``splat_backdrop`` GeoJSON feature for a Gaussian-splat
        scan from the collected control points — the same georeference the
        footprint path uses, stored as the splat's 3D placement transform."""
        from src import splat_backdrop
        if not self.ready:
            raise ValueError(f"need at least {_MIN_PAIRS} control-point "
                             f"pairs ({len(self.pairs)} so far)")
        return splat_backdrop.feature_from_alignment(
            self.points,
            [p["scan"] for p in self.pairs],
            [p["map"] for p in self.pairs],
            file_path=self.file_path, up=self.up)


def preview_qimage(session: ScanAlignSession) -> QImage:
    """Height-tinted top-down QImage of the scan (dark ground → pale
    canopy/roof), NaN cells near-black."""
    import numpy as np
    grid, _extent, _cell = session.preview_grid()
    h = np.nan_to_num(grid, nan=-1.0)
    top = max(1.0, float(np.nanmax(grid))) if np.isfinite(grid).any() else 1.0
    t = np.clip(h / top, 0.0, 1.0)
    r = (40 + t * 190).astype("uint8")
    g = (70 + t * 170).astype("uint8")
    b = (45 + t * 150).astype("uint8")
    empty = h < 0
    for ch in (r, g, b):
        ch[empty] = 18
    rows, cols = h.shape
    rgb = np.dstack([r, g, b])
    img = QImage(np.ascontiguousarray(rgb).tobytes(), cols, rows,
                 cols * 3, QImage.Format.Format_RGB888)
    return img.copy()    # detach from the numpy buffer


class _LoadWorker(QObject):
    """Read a (possibly huge) cloud file off the UI thread."""
    done = pyqtSignal(object)    # ndarray or str error

    def __init__(self, path, up="z"):
        super().__init__()
        self._path = path
        self._up = up

    def run(self):
        try:
            from src.scan_import import read_points
            self.done.emit(read_points(self._path, up=self._up))
        except Exception as exc:  # noqa: BLE001 — report, never crash
            self.done.emit(str(exc))


class _ClickableLabel(QLabel):
    clicked = pyqtSignal(float, float)    # pixel x, y in label coords

    def mousePressEvent(self, ev):
        self.clicked.emit(ev.position().x(), ev.position().y())
        super().mousePressEvent(ev)


class ScanImportDialog(QDialog):
    """Non-modal: it must coexist with clicking on the live map."""

    def __init__(self, main, session: ScanAlignSession):
        super().__init__(main)
        self._main = main
        self.session = session
        self._scale = 1.0      # preview px per raster px
        self.setWindowTitle("Import Yard Scan — match points")
        self.setModal(False)

        self._preview = _ClickableLabel()
        self._preview.setCursor(Qt.CursorShape.CrossCursor)
        img = preview_qimage(session)
        pm = QPixmap.fromImage(img)
        if pm.width() > _PREVIEW_MAX_PX or pm.height() > _PREVIEW_MAX_PX:
            scaled = pm.scaled(_PREVIEW_MAX_PX, _PREVIEW_MAX_PX,
                               Qt.AspectRatioMode.KeepAspectRatio)
            self._scale = scaled.width() / pm.width()
            pm = scaled
        self._preview.setPixmap(pm)
        self._preview.clicked.connect(self._on_preview_clicked)

        self._hint = QLabel()
        self._hint.setWordWrap(True)
        self._pairs = QListWidget()
        remove = QPushButton("Remove selected pair")
        remove.clicked.connect(self._on_remove_pair)

        # A Gaussian-splat scan can become a photoreal 3D backdrop (+ a baked
        # top-down "yard photo" map layer). Crude shade footprints are then
        # optional and off by default — the photoreal splat is the point.
        self._backdrop_chk = None
        self._footprints_chk = None
        if session.is_splat:
            self._backdrop_chk = QCheckBox(
                "Use as photoreal 3D backdrop + map photo")
            self._backdrop_chk.setChecked(True)
            self._footprints_chk = QCheckBox("Also extract shade footprints")
            self._footprints_chk.setChecked(False)

        self._import_btn = QPushButton("Import scan")
        self._import_btn.clicked.connect(self._on_import)

        right = QVBoxLayout()
        right.addWidget(self._hint)
        right.addWidget(self._pairs, 1)
        right.addWidget(remove)
        if self._backdrop_chk is not None:
            right.addWidget(self._backdrop_chk)
            right.addWidget(self._footprints_chk)
        right.addWidget(self._import_btn)
        root = QHBoxLayout(self)
        root.addWidget(self._preview)
        root.addLayout(right, 1)

        # Map half of each pair comes from the live map's click signal.
        self._main.map_widget.bridge.map_clicked.connect(self._on_map_clicked)
        self._refresh()

    # ── interactions ──────────────────────────────────────────────────────

    def _on_preview_clicked(self, px: float, py: float):
        self.session.click_scan(
            self.session.pixel_to_scan_xy(px / self._scale,
                                          py / self._scale))
        self._refresh()

    def _on_map_clicked(self, lat: float, lng: float):
        if self.session.click_map(lat, lng):
            self._refresh()

    def _on_remove_pair(self):
        row = self._pairs.currentRow()
        if row >= 0:
            self.session.remove_pair(row)
            self._refresh()

    def _refresh(self):
        self._pairs.clear()
        for i, p in enumerate(self.session.pairs, 1):
            (sx, sy), (la, ln) = p["scan"], p["map"]
            self._pairs.addItem(
                f"{i}.  scan ({sx:.1f}, {sy:.1f}) m  ⟷  "
                f"map ({la:.5f}, {ln:.5f})")
        n = len(self.session.pairs)
        if self.session.pending_scan is not None:
            self._hint.setText(
                "Now click the SAME spot on the map (the main window)…")
        elif n < _MIN_PAIRS:
            self._hint.setText(
                f"Click a recognisable spot on the scan preview (a building "
                f"corner works best), then the same spot on the map. "
                f"{_MIN_PAIRS - n} more pair(s) needed — spread them apart.")
        else:
            self._hint.setText(
                "Ready — add more pairs for accuracy, or Import.")
        self._import_btn.setEnabled(self.session.ready)

    def _on_import(self):
        m = self._main
        want_backdrop = (self._backdrop_chk is not None
                         and self._backdrop_chk.isChecked())
        # Splat scans default to backdrop-only; plain clouds always do footprints.
        want_footprints = (not self.session.is_splat
                           or (self._footprints_chk is not None
                               and self._footprints_chk.isChecked()))

        backdrop_feat = None
        if want_backdrop:
            try:
                backdrop_feat = self.session.backdrop_feature()
            except Exception as exc:  # noqa: BLE001 — surface, don't crash
                QMessageBox.critical(self, "Scan import failed", str(exc))
                return

        result = None
        if want_footprints:
            try:
                result = self.session.run_import(m._project)
            except Exception as exc:  # noqa: BLE001 — surface, don't crash
                QMessageBox.critical(self, "Scan import failed", str(exc))
                return

        n_foot = 0
        if result:
            from src.project import feature_to_shape
            for f in result["features"]:
                sh = feature_to_shape(f)
                if sh:
                    m.map_widget.load_shape(sh)
            m._scan_scene_sample = result["scan_sample"]
            n_foot = len(result["features"])

        if backdrop_feat is not None:
            m._project.setdefault("features", []).append(backdrop_feat)
            from src import splat_flow
            splat_flow.restore_splat_overlay(m)   # enables the View toggle
            win = getattr(m, "_scene3d_window", None)
            if win is not None:
                win.refresh()                     # show the backdrop now if open

        if n_foot or backdrop_feat is not None:
            m._mark_modified()

        if backdrop_feat is not None:
            m.statusBar().showMessage(
                "Yard scan added as a photoreal 3D backdrop. Open View → 3D "
                "Preview, then click “Add yard photo to map” to add the map layer."
                + (f" ({n_foot} footprint(s) too.)" if n_foot else ""), 9000)
        else:
            m.statusBar().showMessage(
                f"Scan imported — {n_foot} shade-casting footprint(s) added. "
                "See them in 3D via View → 3D Preview.", 6000)
        self.accept()

    def closeEvent(self, event):
        try:
            self._main.map_widget.bridge.map_clicked.disconnect(
                self._on_map_clicked)
        except Exception:  # noqa: BLE001 — already disconnected
            pass
        super().closeEvent(event)

    def accept(self):
        try:
            self._main.map_widget.bridge.map_clicked.disconnect(
                self._on_map_clicked)
        except Exception:  # noqa: BLE001
            pass
        super().accept()


def start_scan_import(main) -> None:
    """File → Import Yard Scan…: pick a file, load it off-thread, then
    open the alignment dialog."""
    path, _ = QFileDialog.getOpenFileName(
        main, "Import Yard Scan", "",
        "Point clouds (*.ply *.xyz *.las *.laz *.txt *.csv);;All files (*)")
    if not path:
        return

    # A Gaussian-splat PLY (Scaniverse / Polycam / Luma) can be a photoreal 3D
    # backdrop, not just a footprint source — and its vertical axis varies by
    # capture app, so ask up front (it must match how we read the points).
    from src.scan_import import is_gaussian_splat_ply
    is_splat = is_gaussian_splat_ply(path)
    up = "z"
    if is_splat:
        choice, ok = QInputDialog.getItem(
            main, "Yard scan orientation",
            "Which way is up in this capture?\n"
            "(LiDAR scans are usually Z-up; photogrammetry / Luma are often "
            "Y-up. Pick wrong and the yard will look tipped over.)",
            ["Z-up (LiDAR / most scanners)", "Y-up (photogrammetry / Luma)"],
            0, False)
        if not ok:
            return
        up = "y" if choice.startswith("Y") else "z"
    main.statusBar().showMessage("Reading scan…")

    thread = QThread(main)
    worker = _LoadWorker(path, up=up)
    worker.moveToThread(thread)

    def _loaded(result):
        thread.quit()
        if isinstance(result, str):
            QMessageBox.critical(main, "Scan import failed", result)
            main.statusBar().showMessage("Scan import failed.", 4000)
            return
        main.statusBar().showMessage(
            f"Scan loaded — {len(result):,} points.", 4000)
        session = ScanAlignSession(result, file_path=path,
                                   is_splat=is_splat, up=up)
        dlg = ScanImportDialog(main, session)
        main._scan_import_dialog = dlg     # keep a reference
        dlg.show()

    thread.started.connect(worker.run)
    worker.done.connect(_loaded)
    thread.finished.connect(thread.deleteLater)
    main._scan_import_thread = (thread, worker)   # keep references
    thread.start()

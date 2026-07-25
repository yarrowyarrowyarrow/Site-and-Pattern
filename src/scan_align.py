"""
src/scan_align.py — the Qt-free core of the "Import Yard Scan…" flow (V1.63).

:class:`ScanAlignSession` holds the control-point pairing state, rasterises the
preview grid, and invokes the :mod:`src.scan_import` engine. It has no Qt
dependency of any kind, so it is unit-testable without a display — which is the
whole reason the scan flow was split in two.

It lived inside :mod:`src.scan_import_dialog` until V2.29. That module imports
PyQt6 at the top level, so importing "the Qt-free core" pulled in Qt anyway and
its four tests errored out with ``ModuleNotFoundError: No module named 'PyQt6'``
in every environment without a GUI stack — exactly the environments the split
was designed to serve. The class is re-exported from ``scan_import_dialog`` so
existing imports keep working.

The Qt shell (:class:`~src.scan_import_dialog.ScanImportDialog`, the preview
QImage, and the File-menu entry point) stays in ``scan_import_dialog``.
"""

from __future__ import annotations

from typing import Optional

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

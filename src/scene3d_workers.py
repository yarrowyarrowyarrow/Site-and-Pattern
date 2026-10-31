"""
src/scene3d_workers.py — the 3D preview's two background jobs (V3.08).

Moved out of ``src/scene3d_window.py`` unchanged, when that window sat at its
950-line ceiling and the preview's next change (following the design, F89)
needed room. Both run on a ``QThread`` the window owns:

  * :class:`TerrainWorker` — the site's elevation grid, cache first;
  * :class:`PhotoWarmWorker` — the catalogue's species photos into the cache,
    so a click on a plant shows its photo the first time.
"""

from __future__ import annotations

import threading

from PyQt6.QtCore import QObject, pyqtSignal


class TerrainWorker(QObject):
    """Cache-first elevation fetch off the UI thread."""
    done = pyqtSignal(object)   # elevation dict or None

    def __init__(self, boundary, site_config):
        super().__init__()
        self._boundary = boundary
        self._site_config = site_config

    def run(self):
        elev = None
        try:
            from src.zoning import site_elevation_grid
            elev = site_elevation_grid(self._boundary, self._site_config)
        except Exception:
            elev = None
        self.done.emit(elev)


class PhotoWarmWorker(QObject):
    """Fill the species-photo cache off the UI thread (src/photo_warm.py).

    Emits ``batch`` every so often rather than per photo: the only thing the
    window does with it is re-push the dossier so newly-cached photos appear, and
    doing that ~380 times would rebuild the whole dossier for each one.
    """
    batch = pyqtSignal()
    done = pyqtSignal()
    _BATCH = 12

    def __init__(self):
        super().__init__()
        # Owned here, not by the warmer: closeEvent can fire before run() has
        # built one (the catalogue query happens first), and a cancel that landed
        # in that window would be lost.
        self._cancel = threading.Event()

    def run(self):
        try:
            from src.photo_warm import PhotoWarmer, catalogue_photo_rows
            rows = catalogue_photo_rows()
            PhotoWarmer(rows, on_progress=self._progress,
                        cancel_event=self._cancel).run()
        except Exception:      # noqa: BLE001 — photos are a nicety, never a dep
            pass
        self.done.emit()

    def _progress(self, done, _total, newly_cached):
        if newly_cached and done % self._BATCH == 0:
            self.batch.emit()

    def cancel(self):
        self._cancel.set()

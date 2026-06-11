"""
tests/test_scan_import_dialog.py — the scan-alignment GUI (V1.63).

ScanAlignSession (the Qt-free core) is tested without a display: pairing
state machine, preview-pixel→scan-coordinate mapping, readiness, and a
full run_import against a synthetic yard. The Qt dialog gets a smoke test
(construct, simulate preview + map clicks, import button gating) that
skips when Qt can't run here.
"""

import math
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    import numpy as np
    _HAVE_NUMPY = True
except ImportError:
    _HAVE_NUMPY = False

try:
    import shapely  # noqa: F401
    _HAVE_SHAPELY = True
except ImportError:
    _HAVE_SHAPELY = False

_LAT0, _LNG0 = 53.5, -113.5


def _yard():
    rng = np.random.default_rng(5)
    gx = rng.uniform(-10, 10, 12000)
    gy = rng.uniform(-10, 10, 12000)
    gz = rng.normal(0.0, 0.02, 12000)
    sx = rng.uniform(3.0, 7.0, 3000)
    sy = rng.uniform(2.5, 5.5, 3000)
    sz = np.full(3000, 3.0)
    return np.column_stack([np.concatenate([gx, sx]),
                            np.concatenate([gy, sy]),
                            np.concatenate([gz, sz])])


def _latlng(x, y):
    from src.projection import Projector
    return Projector(_LAT0, _LNG0).to_latlng(x, y)


@unittest.skipUnless(_HAVE_NUMPY, "numpy not installed")
class TestScanAlignSession(unittest.TestCase):

    def _session(self):
        from src.scan_import_dialog import ScanAlignSession
        return ScanAlignSession(_yard())

    def test_pairing_state_machine(self):
        s = self._session()
        # A map click with no pending scan half is ignored.
        self.assertFalse(s.click_map(_LAT0, _LNG0))
        s.click_scan((1.0, 2.0))
        # Re-clicking the scan replaces the pending half.
        s.click_scan((1.5, 2.5))
        self.assertTrue(s.click_map(_LAT0, _LNG0))
        self.assertEqual(len(s.pairs), 1)
        self.assertEqual(s.pairs[0]["scan"], (1.5, 2.5))
        self.assertFalse(s.ready)
        s.click_scan((-3.0, -3.0))
        s.click_map(*_latlng(-3.0, -3.0))
        self.assertTrue(s.ready)
        s.remove_pair(0)
        self.assertFalse(s.ready)

    def test_pixel_round_trip(self):
        s = self._session()
        grid, (min_x, _min_y, _max_x, max_y), cell = s.preview_grid()
        # Pixel (0, 0) is the north-west corner cell centre.
        x, y = s.pixel_to_scan_xy(0, 0)
        self.assertAlmostEqual(x, min_x + cell / 2, places=6)
        self.assertAlmostEqual(y, max_y - cell / 2, places=6)
        # And the preview fits the configured budget.
        self.assertLessEqual(max(grid.shape), 440)

    def test_run_import_requires_pairs(self):
        s = self._session()
        with self.assertRaises(ValueError):
            s.run_import({"features": []})

    @unittest.skipUnless(_HAVE_SHAPELY, "shapely not installed")
    def test_run_import_lands_footprints(self):
        s = self._session()
        for (x, y) in [(-10.0, -10.0), (10.0, 10.0)]:
            s.click_scan((x, y))           # identity alignment: scan == map
            s.click_map(*_latlng(x, y))
        project = {"type": "FeatureCollection", "properties": {},
                   "features": []}
        result = s.run_import(project)
        self.assertEqual(len(result["features"]), 1)
        props = result["features"][0]["properties"]
        self.assertEqual(props["source"], "scan")
        self.assertAlmostEqual(props["height_m"], 3.0, delta=0.3)
        self.assertTrue(result["scan_sample"]["points"])
        self.assertEqual(len(project["features"]), 1)


def _qt_available():
    try:
        from PyQt6.QtWidgets import QApplication  # noqa: F401
        return True
    except Exception:
        return False


@unittest.skipUnless(_HAVE_NUMPY and _qt_available(),
                     "numpy/PyQt6 not installed")
class TestScanImportDialog(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from PyQt6.QtCore import Qt
        from PyQt6.QtWidgets import QApplication
        QApplication.setAttribute(
            Qt.ApplicationAttribute.AA_ShareOpenGLContexts)
        cls._app = (QApplication.instance()
                    or QApplication(["permadesign-tests"]))

    def _fake_main(self):
        from PyQt6.QtCore import QObject, pyqtSignal
        from PyQt6.QtWidgets import QWidget

        class _Bridge(QObject):
            map_clicked = pyqtSignal(float, float)

        class _MapWidget:
            def __init__(self):
                self.bridge = _Bridge()
                self.shapes = []

            def load_shape(self, sh):
                self.shapes.append(sh)

        class _StatusBar:
            def showMessage(self, *_a, **_k):
                pass

        main = QWidget()
        main.map_widget = _MapWidget()
        main._project = {"type": "FeatureCollection", "properties": {},
                         "features": []}
        main._mark_modified = lambda: None
        main.statusBar = lambda: _StatusBar()
        return main

    def test_dialog_pairs_and_imports(self):
        from src.scan_import_dialog import (ScanAlignSession,
                                            ScanImportDialog, preview_qimage)
        main = self._fake_main()
        session = ScanAlignSession(_yard())
        self.assertFalse(preview_qimage(session).isNull())
        dlg = ScanImportDialog(main, session)
        self.assertFalse(dlg._import_btn.isEnabled())

        # Pair 1: preview click (north-west corner) + map signal.
        dlg._on_preview_clicked(1.0, 1.0)
        self.assertIsNotNone(session.pending_scan)
        main.map_widget.bridge.map_clicked.emit(*_latlng(-10.0, 10.0))
        self.assertEqual(len(session.pairs), 1)

        # Stray map clicks between pairs are ignored.
        main.map_widget.bridge.map_clicked.emit(_LAT0, _LNG0)
        self.assertEqual(len(session.pairs), 1)

        # Pair 2 → import enabled.
        px = dlg._preview.pixmap().width() - 2
        py = dlg._preview.pixmap().height() - 2
        dlg._on_preview_clicked(px, py)
        main.map_widget.bridge.map_clicked.emit(*_latlng(10.0, -10.0))
        self.assertTrue(dlg._import_btn.isEnabled())

        if _HAVE_SHAPELY:
            dlg._on_import()
            self.assertTrue(main.map_widget.shapes)
            self.assertTrue(hasattr(main, "_scan_scene_sample"))
        dlg.deleteLater()


if __name__ == "__main__":
    unittest.main()

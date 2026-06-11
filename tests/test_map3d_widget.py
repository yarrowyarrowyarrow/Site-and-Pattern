"""
tests/test_map3d_widget.py

D1 foundation — the Map3DWidget scaffold. Qt + WebEngine smoke test; skips when
PyQt6 / QtWebEngine aren't installed. Verifies the widget constructs (placeholder
when no built map3d dist), and that set_sun_for / set_scene push the expected
guarded JS through run_js (run_js is overridden to capture, so no real page).

    QT_QPA_PLATFORM=offscreen python -m unittest tests.test_map3d_widget -v
"""

import os
import sys
import unittest
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def _webengine_available():
    try:
        from PyQt6.QtWidgets import QApplication  # noqa: F401
        from PyQt6.QtWebEngineWidgets import QWebEngineView  # noqa: F401
        return True
    except Exception:
        return False


@unittest.skipUnless(_webengine_available(), "PyQt6/WebEngine not installed")
class TestMap3DWidget(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from PyQt6.QtCore import Qt
        from PyQt6.QtWidgets import QApplication
        # WebEngine needs this set before the QApplication is created.
        QApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts)
        import PyQt6.QtWebEngineWidgets  # noqa: F401
        cls._app = QApplication.instance() or QApplication(["permadesign-tests"])

    def test_constructs_without_built_dist(self):
        from src.map3d_widget import Map3DWidget, dist_index_path
        w = Map3DWidget()
        # No built map3d dist checked in → placeholder, has_scene False.
        self.assertEqual(w.has_scene, dist_index_path() is not None)
        w.deleteLater()

    def test_set_scene_pushes_guarded_plants_js(self):
        from src.map3d_widget import Map3DWidget
        w = Map3DWidget()
        captured = []
        w.run_js = lambda js: captured.append(js)   # capture instead of running
        fake = {1: {"plant_type": "tree", "years_to_maturity": 20,
                    "growth_curve": "steady", "mature_height_meters": 10.0,
                    "mature_canopy_m": 6.0}}
        placed = [{"plant_id": 1, "lat": 53.5, "lng": -113.5}]
        w.set_scene(placed, 10, get_plant=lambda pid: fake.get(pid))
        self.assertEqual(len(captured), 1)
        self.assertIn("window.permaSetPlants", captured[0])
        self.assertIn('"plant_id": 1', captured[0])
        w.deleteLater()

    def test_set_sun_for_night_is_noop(self):
        from src.map3d_widget import Map3DWidget
        w = Map3DWidget()
        captured = []
        w.run_js = lambda js: captured.append(js)
        # 1 AM local → sun below horizon → map3d_js returns None → run_js(None).
        w.set_sun_for(53.5461, -113.4938, datetime(2025, 6, 21, 1, 0))
        # run_js is called with None; the real run_js guards on truthiness, but
        # here we just confirm no JS hook string was produced.
        self.assertTrue(all(c is None for c in captured))
        w.deleteLater()


if __name__ == "__main__":
    unittest.main()

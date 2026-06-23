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
        from src.map3d_widget import (Map3DWidget, builtin_viewer_path,
                                      dist_index_path)
        w = Map3DWidget()
        # No built map3d dist checked in → the built-in scene3d viewer.
        self.assertEqual(w.has_scene, dist_index_path() is not None)
        if dist_index_path() is None:
            self.assertEqual(w.mode, "builtin")
            self.assertIsNotNone(builtin_viewer_path())
        w.deleteLater()

    def test_js_queued_until_load_finished(self):
        # Pushes that race the page load must be replayed, not dropped —
        # the && guards in the page silently no-op early calls.
        from src.map3d_widget import Map3DWidget
        w = Map3DWidget()
        ran = []

        class _FakePage:
            def runJavaScript(self, js):
                ran.append(js)

        w.page = lambda: _FakePage()           # capture instead of running
        w._loaded = False                      # simulate pre-load push
        w.apply_scene({"version": 1, "bounds": {}})
        self.assertEqual(ran, [])
        self.assertEqual(len(w._pending_js), 1)
        w._on_load_finished(True)              # page ready → replay
        self.assertEqual(len(ran), 1)
        self.assertIn("permaSetScene", ran[0])
        w.run_js("window.permaSetSun && window.permaSetSun(1.0, 2.0);")
        self.assertEqual(len(ran), 2)          # post-load runs immediately
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

    def test_apply_scene_injects_splat_localhost_url(self):
        # A splat field with an existing file → its path becomes a localhost
        # http URL Spark fetches same-origin from the viewer page (V1.77; was a
        # file:// URL through V1.76).
        import tempfile
        from src.map3d_widget import Map3DWidget
        w = Map3DWidget()
        captured = []
        w.run_js = lambda js: captured.append(js)
        d = tempfile.mkdtemp()
        p = os.path.join(d, "yard.ply")
        with open(p, "wb") as f:
            f.write(b"ply\n")
        scene = {"version": 1, "bounds": {},
                 "splat": {"path": p, "matrix": [0.0] * 16, "opacity": 1.0}}
        w.apply_scene(scene)
        self.assertEqual(len(captured), 1)
        self.assertIn("http://127.0.0.1", captured[0])
        self.assertIn("/__localfile", captured[0])
        self.assertIn('"url"', captured[0])
        # Original scene dict is not mutated (a copy is pushed).
        self.assertNotIn("url", scene["splat"])
        w.deleteLater()

    def test_apply_scene_drops_missing_splat_file(self):
        from src.map3d_widget import Map3DWidget
        w = Map3DWidget()
        captured = []
        w.run_js = lambda js: captured.append(js)
        scene = {"version": 1, "bounds": {},
                 "splat": {"path": "/no/such/yard.ply",
                           "matrix": [0.0] * 16, "opacity": 1.0}}
        w.apply_scene(scene)
        # Missing file → splat nulled so the design still renders.
        self.assertIn('"splat": null', captured[0])
        w.deleteLater()

    def test_capture_ortho_runs_guarded_hook(self):
        from src.map3d_widget import Map3DWidget
        w = Map3DWidget()
        calls = []

        class _FakePage:
            def runJavaScript(self, js, cb=None):
                calls.append((js, cb))

        w.page = lambda: _FakePage()
        w._loaded = True
        w.capture_ortho({"min_x": -5, "max_x": 5, "min_y": -5, "max_y": 5},
                        lambda u: None)
        self.assertEqual(len(calls), 1)
        self.assertIn("permaCaptureOrtho", calls[0][0])
        w.deleteLater()

    def test_capture_ortho_before_load_calls_back_empty(self):
        from src.map3d_widget import Map3DWidget
        w = Map3DWidget()
        w._loaded = False
        out = []
        w.capture_ortho({"min_x": 0, "max_x": 1, "min_y": 0, "max_y": 1},
                        out.append)
        self.assertEqual(out, [""])
        w.deleteLater()


if __name__ == "__main__":
    unittest.main()

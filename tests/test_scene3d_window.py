"""
tests/test_scene3d_window.py — the 3D Preview window (V1.62).

Qt-gated smoke tests: the window constructs against a minimal fake main,
refresh() builds a Scene JSON from the live project and pushes it through
the viewer, the year slider re-pushes with the new year, and open_3d_view
keeps a singleton on the main. The viewer's run_js is overridden to
capture — no real page, no network, no DB (plants are resolved through
build_scene's get_plant default only if a plant feature exists; these
projects use existing-feature types to stay DB-free).
"""

import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def _qt_available():
    try:
        from PyQt6.QtWidgets import QApplication  # noqa: F401
        from PyQt6.QtWebEngineWidgets import QWebEngineView  # noqa: F401
        return True
    except Exception:
        return False


def _scene_payloads(captured):
    """Parse the permaSetScene payload out of each captured JS push."""
    out = []
    for js in captured:
        if "permaSetScene(" not in js:
            continue
        start = js.index("(", js.index("permaSetScene(")) + 1
        out.append(json.loads(js[start:-2]))
    return out


@unittest.skipUnless(_qt_available(), "PyQt6/WebEngine not installed")
class TestScene3DWindow(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from PyQt6.QtCore import Qt
        from PyQt6.QtWidgets import QApplication
        QApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts)
        import PyQt6.QtWebEngineWidgets  # noqa: F401
        cls._app = QApplication.instance() or QApplication(["permadesign-tests"])

    def _fake_main(self):
        class _Fake:
            pass
        m = _Fake()
        # No boundary and no site pin → the terrain worker is never started.
        m._project = {
            "type": "FeatureCollection",
            "properties": {"site_config": {}},
            "features": [
                {"type": "Feature",
                 "geometry": {"type": "Point",
                              "coordinates": [-113.5, 53.5]},
                 "properties": {"element_type": "existing_tree",
                                "height_m": 9.0, "canopy_radius_m": 3.0}},
            ],
        }
        return m

    def test_refresh_pushes_scene_from_project(self):
        from src.scene3d_window import Scene3DWindow
        win = Scene3DWindow(self._fake_main())
        captured = []
        win.viewer.run_js = lambda js: captured.append(js)
        win.refresh()
        scenes = _scene_payloads(captured)
        self.assertEqual(len(scenes), 1)
        self.assertEqual(scenes[0]["version"], 1)
        self.assertEqual(len(scenes[0]["plants"]), 1)
        self.assertTrue(scenes[0]["plants"][0]["existing"])
        self.assertIsNone(win._thread)   # no boundary/pin → no fetch
        win.deleteLater()

    def test_year_slider_repushes_scene(self):
        from src.scene3d_window import Scene3DWindow
        win = Scene3DWindow(self._fake_main())
        captured = []
        win.viewer.run_js = lambda js: captured.append(js)
        win._year.setValue(10)
        scenes = _scene_payloads(captured)
        self.assertEqual(len(scenes), 1)
        self.assertEqual(scenes[0]["year"], 10)
        self.assertEqual(win._year_lbl.text(), "year 10")
        win.deleteLater()

    def test_open_3d_view_singleton(self):
        from src.scene3d_window import open_3d_view
        main = self._fake_main()
        w1 = open_3d_view(main)
        w2 = open_3d_view(main)
        self.assertIs(w1, w2)
        self.assertIs(main._scene3d_window, w1)
        w1.close()
        w1.deleteLater()


if __name__ == "__main__":
    unittest.main()

"""
tests/test_existing_features.py

V1.49 — marking EXISTING on-site trees / buildings as shade casters for the
design generator. These ride the existing structure placement pipeline via
reserved ids (existing_tree / existing_building) and are written as their own
project feature types (NOT placeable structures, NOT habitat-score structures).

Covers the data + controller logic without Qt: the synthetic struct-defs, the
controller routing (structure callback → existing_* feature), shade-model
pickup, removal, save/reload round-trip, and that they don't leak into the
structure catalogue or habitat score. A Qt smoke test for the panel buttons
skips gracefully when PyQt6 is unavailable.
"""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.db.structures import (  # noqa: E402
    existing_feature_def, get_all_structures, get_structure,
    EXISTING_TREE_ID, EXISTING_BUILDING_ID, EXISTING_FEATURE_IDS,
)
from src.project import new_project, project_to_map_data  # noqa: E402


class _FakeStatus:
    def showMessage(self, *a, **k):
        pass


class _FakeMain:
    """Minimal MainWindow stand-in for the map-event handlers."""

    def __init__(self):
        self._project = new_project("t")
        self._existing_feature_height_m = None
        self._undo = []
        self._modified = False

    def _push_undo(self, e):
        self._undo.append(e)

    def _mark_modified(self):
        self._modified = True

    def statusBar(self):
        return _FakeStatus()

    def _sync_planning_panel(self):
        pass


def _router(main):
    from src.controllers.map_events import MapEventRouter
    return MapEventRouter(main)


class TestExistingFeatureDefs(unittest.TestCase):
    def test_tree_is_circle_building_is_rectangle(self):
        t = existing_feature_def(EXISTING_TREE_ID, size_m=8.0, height_m=10.0)
        b = existing_feature_def(EXISTING_BUILDING_ID, size_m=6.0, height_m=5.0)
        self.assertEqual(t["shape"], "circle")
        self.assertEqual(t["height_m"], 10.0)
        self.assertEqual(b["shape"], "rectangle")
        self.assertEqual(b["width_m"], 6.0)

    def test_reserved_ids_not_in_structure_catalogue(self):
        # Existing features must NOT appear among placeable structures, and
        # must NOT resolve via get_structure (so they never count for habitat
        # score or show in the browser).
        ids = {s["id"] for s in get_all_structures()}
        self.assertFalse(EXISTING_FEATURE_IDS & ids)
        self.assertIsNone(get_structure(EXISTING_TREE_ID))
        self.assertIsNone(get_structure(EXISTING_BUILDING_ID))

    def test_not_in_habitat_structure_ids(self):
        from src.habitat_score import HABITAT_STRUCTURE_IDS
        self.assertFalse(EXISTING_FEATURE_IDS & HABITAT_STRUCTURE_IDS)


class TestControllerRouting(unittest.TestCase):
    def test_marking_writes_existing_feature_with_height(self):
        main = _FakeMain()
        main._existing_feature_height_m = 11.0   # stashed by mode controller
        _router(main)._on_structure_placed(
            EXISTING_TREE_ID, "Existing tree", 53.5, -113.5, 8.0)
        feats = [f for f in main._project["features"]
                 if f["properties"]["element_type"] == "existing_tree"]
        self.assertEqual(len(feats), 1)
        p = feats[0]["properties"]
        self.assertEqual(p["height_m"], 11.0)
        self.assertEqual(p["canopy_radius_m"], 4.0)   # size 8 → radius 4
        self.assertTrue(main._modified)

    def test_building_default_height_when_unstashed(self):
        main = _FakeMain()  # height stash left at None
        _router(main)._on_structure_placed(
            EXISTING_BUILDING_ID, "Existing building", 53.5, -113.5, 6.0)
        p = [f["properties"] for f in main._project["features"]
             if f["properties"]["element_type"] == "existing_building"][0]
        self.assertEqual(p["height_m"], 5.0)          # building default

    def test_real_structure_still_writes_structure(self):
        main = _FakeMain()
        _router(main)._on_structure_placed(
            "bee_hotel", "Bee Hotel", 53.5, -113.5, 0.6)
        ets = {f["properties"]["element_type"]
               for f in main._project["features"]}
        self.assertIn("structure", ets)
        self.assertNotIn("existing_tree", ets)

    def test_removal_drops_existing_feature(self):
        main = _FakeMain()
        main._existing_feature_height_m = 8.0
        r = _router(main)
        r._on_structure_placed(EXISTING_TREE_ID, "Existing tree",
                               53.5, -113.5, 6.0)
        r._on_structure_removed("m1", EXISTING_TREE_ID, 53.5, -113.5)
        left = [f for f in main._project["features"]
                if f["properties"]["element_type"] == "existing_tree"]
        self.assertEqual(left, [])


class TestShadeIntegration(unittest.TestCase):
    def test_shade_model_reads_marked_features(self):
        from src.shade import casters_from_project
        main = _FakeMain()
        main._existing_feature_height_m = 9.0
        r = _router(main)
        r._on_structure_placed(EXISTING_TREE_ID, "Tree", 53.5, -113.5, 7.0)
        casters = casters_from_project(main._project)
        self.assertEqual(len(casters), 1)
        self.assertEqual(casters[0]["height_m"], 9.0)
        self.assertAlmostEqual(casters[0]["radius_m"], 3.5)


class TestReloadRoundTrip(unittest.TestCase):
    def test_existing_feature_renders_on_reload(self):
        # project_to_map_data must reconstruct a struct_def so the map can draw
        # marked features through the normal loadStructure path.
        p = new_project("t")
        p["features"].append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [-113.5, 53.5]},
            "properties": {"element_type": "existing_tree", "height_m": 9.0,
                           "canopy_radius_m": 4.0, "label": "Big spruce",
                           "struct_id": "existing_tree", "size_m": 8.0},
        })
        md = project_to_map_data(p)
        self.assertEqual(len(md["structures"]), 1)
        sd = md["structures"][0]["struct_def"]
        self.assertEqual(sd["shape"], "circle")
        self.assertEqual(sd["name"], "Big spruce")

    def test_save_reload_preserves_feature(self):
        import tempfile
        from src.project import save_project, load_project
        p = new_project("t")
        p["features"].append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [-113.5, 53.5]},
            "properties": {"element_type": "existing_building", "height_m": 6.0,
                           "canopy_radius_m": 5.0, "struct_id":
                           "existing_building", "size_m": 10.0},
        })
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "t.perma.geojson")
            save_project(p, path)
            reloaded = load_project(path)
        ets = [f["properties"]["element_type"] for f in reloaded["features"]]
        self.assertIn("existing_building", ets)


def _qt_available():
    try:
        import PyQt6  # noqa: F401
        from PyQt6.QtWidgets import QApplication  # noqa: F401
        return True
    except Exception:
        return False


@unittest.skipUnless(_qt_available(), "PyQt6 not installed in this env")
class TestSitePanelShadeButtons(unittest.TestCase):
    """V1.59 — the mark/draw tools moved from Structures to Site → Shade. The
    buttons emit place_structure_requested (existing tree/building) and
    place_shape_requested (draw building / draw tree canopy) payloads carrying
    the height/size from the spinboxes."""

    _app = None

    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PyQt6.QtWidgets import QApplication
        cls._app = QApplication.instance() or QApplication([])

    def test_mark_tree_emits_structure_payload(self):
        from src.site_panel import SitePanel
        panel = SitePanel()
        captured = []
        panel.place_structure_requested.connect(captured.append)
        panel._exist_height.setValue(12.0)
        panel._exist_size.setValue(9.0)
        panel._on_mark_existing(EXISTING_TREE_ID)
        self.assertEqual(len(captured), 1)
        payload = captured[0]
        self.assertEqual(payload["id"], EXISTING_TREE_ID)
        self.assertEqual(payload["height_m"], 12.0)
        self.assertEqual(payload["size_m"], 9.0)
        panel.deleteLater()

    def test_draw_tree_canopy_emits_tree_shape(self):
        from src.site_panel import SitePanel
        panel = SitePanel()
        captured = []
        panel.place_shape_requested.connect(captured.append)
        panel._exist_height.setValue(7.0)
        panel._on_draw_tree_canopy()
        self.assertEqual(len(captured), 1)
        self.assertEqual(captured[0]["shape_type"], "Tree canopy")
        self.assertEqual(captured[0]["height_m"], 7.0)
        panel.deleteLater()

    def test_draw_building_emits_building_shape(self):
        from src.site_panel import SitePanel
        panel = SitePanel()
        captured = []
        panel.place_shape_requested.connect(captured.append)
        panel._exist_height.setValue(5.0)
        panel._on_draw_building_footprint()
        self.assertEqual(len(captured), 1)
        self.assertEqual(captured[0]["shape_type"], "Building footprint")
        self.assertEqual(captured[0]["height_m"], 5.0)
        panel.deleteLater()


if __name__ == "__main__":
    unittest.main()

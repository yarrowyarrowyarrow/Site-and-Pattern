"""
tests/test_canopy_footprint.py

V1.53 — drawing a shape with a height promotes it to a shade-casting
``canopy_footprint`` feature, and shade.casters_from_project reads it back as a
true polygon caster. Uses a minimal fake MainWindow (no Qt), mirroring
tests/test_map_events_drag.py.
"""

import json
import unittest

from src.controllers.map_events import MapEventRouter
import src.shade as shade


class _FakeStatusBar:
    def showMessage(self, *_a, **_k):
        pass


class _FakeMain:
    def __init__(self):
        self._project = {"type": "FeatureCollection", "features": []}
        self.undo_entries = []

    def _push_undo(self, entry):
        self.undo_entries.append(entry)

    def _mark_modified(self):
        pass

    def _set_mode_label(self, *_a):
        pass

    def statusBar(self):
        return _FakeStatusBar()


# A small square drawn on the map: JS sends [lat, lng] points.
_PTS = [[53.5000, -113.5000], [53.5000, -113.4999],
        [53.5001, -113.4999], [53.5001, -113.5000]]


def _router():
    main = _FakeMain()
    return MapEventRouter(main), main


class TestCanopyFootprint(unittest.TestCase):

    def test_height_zero_stays_custom_shape(self):
        router, main = _router()
        router._on_shape_complete(
            "s1", json.dumps(_PTS), "Bed", "Garden Bed",
            "#4caf50", "#2e7d32", 0.25, "", 50.0, 0.0)
        feat = main._project["features"][0]
        self.assertEqual(feat["properties"]["element_type"], "custom_shape")
        self.assertNotIn("height_m", feat["properties"])
        self.assertNotIn("cast_shade", feat["properties"])

    def test_height_promotes_to_canopy_footprint(self):
        router, main = _router()
        router._on_shape_complete(
            "s2", json.dumps(_PTS), "House", "Custom",
            "#78909c", "#546e7a", 0.4, "", 80.0, 8.0)
        feat = main._project["features"][0]
        props = feat["properties"]
        self.assertEqual(props["element_type"], "canopy_footprint")
        self.assertEqual(props["height_m"], 8.0)
        self.assertTrue(props["cast_shade"])
        # Geometry is a closed polygon ring in (lng, lat).
        self.assertEqual(feat["geometry"]["type"], "Polygon")
        ring = feat["geometry"]["coordinates"][0]
        self.assertEqual(ring[0], ring[-1])

    def test_casters_from_project_reads_footprint(self):
        router, main = _router()
        router._on_shape_complete(
            "s3", json.dumps(_PTS), "Tree", "Custom",
            "#66bb6a", "#43a047", 0.3, "", 60.0, 6.0)
        casters = shade.casters_from_project(main._project)
        self.assertEqual(len(casters), 1)
        self.assertEqual(casters[0]["height_m"], 6.0)
        self.assertIn("footprint", casters[0])

    def test_removal_by_shape_id(self):
        router, main = _router()
        router._on_shape_complete(
            "s4", json.dumps(_PTS), "House", "Custom",
            "#78909c", "#546e7a", 0.4, "", 80.0, 8.0)
        self.assertEqual(len(main._project["features"]), 1)
        router._on_shape_removed("s4")
        self.assertEqual(main._project["features"], [])


if __name__ == "__main__":
    unittest.main()

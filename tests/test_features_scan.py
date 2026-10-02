"""
tests/test_features_scan.py — Site › Features › Scan this area (F207, V3.10).

Buildings and trees in one go, added as one undo step, then a review that takes
out whatever the person unticks. The two sources (OpenStreetMap and the tree
detector) need the network, which the suite does not have, so they are stood
in for here; what is tested is the scan's own part: joining them, the review,
and the removal.
"""

import os
import sys
import unittest
from contextlib import contextmanager
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PyQt6.QtWidgets import QApplication
    _HAVE_QT = True
except ImportError:                                        # pragma: no cover
    _HAVE_QT = False


def _tree(lng, lat, label="Tree (canopy height)"):
    return {"type": "Feature",
            "geometry": {"type": "Point", "coordinates": [lng, lat]},
            "properties": {"element_type": "existing_tree", "height_m": 11.0,
                           "canopy_radius_m": 3.0, "label": label}}


def _building(lng, lat):
    d = 0.0001
    ring = [[lng, lat], [lng + d, lat], [lng + d, lat + d], [lng, lat + d],
            [lng, lat]]
    return {"type": "Feature",
            "geometry": {"type": "Polygon", "coordinates": [ring]},
            "properties": {"element_type": "canopy_footprint", "height_m": 6.0,
                           "label": "Building (OSM)", "source": "osm"}}


class _Main:
    def __init__(self):
        self._project = {"type": "FeatureCollection", "features": [],
                         "properties": {}}
        self.status, self.checkpoints, self.framed = [], [], []
        self.modified = 0
        main = self

        class _Persistence:
            @contextmanager
            def checkpoint(self, label):
                main.checkpoints.append(label)
                yield

            def render_project_to_map(self):
                pass

        class _Events:
            def _reload_existing_features(self):
                pass

        class _Site:
            def set_osm_status(self, text):
                main.status.append(text)

        class _Map:
            def fit_bounds(self, *box):
                main.framed.append(box)

        self._persistence = _Persistence()
        self._map_events = _Events()
        self.site_panel = _Site()
        self.map_widget = _Map()

    def _mark_modified(self):
        self.modified += 1

    def _sync_planning_panel(self):
        pass


class TestTheWords(unittest.TestCase):

    def test_rows_and_centres(self):
        from src import features_scan_flow as scan
        tree, bldg = _tree(-113.5, 53.5), _building(-113.5, 53.5)
        self.assertEqual(scan.describe(tree),
                         "Tree (canopy height) · crown 6 m · 11 m tall")
        self.assertEqual(scan.describe(bldg), "Building (OSM) · 6 m tall")
        self.assertEqual(scan.centre(tree), (53.5, -113.5))
        lat, lng = scan.centre(bldg)
        self.assertAlmostEqual(lat, 53.50005, places=5)
        self.assertAlmostEqual(lng, -113.49995, places=5)

    def test_what_a_scan_added_is_what_was_not_there_before(self):
        from src import features_scan_flow as scan
        old = _tree(-113.5, 53.5)
        project = {"features": [old]}
        before = {id(f) for f in project["features"]}
        new = _tree(-113.6, 53.6)
        note = {"properties": {"element_type": "annotation"}}
        project["features"] += [new, note]
        self.assertEqual(scan.found_since(project, before), [new])

    def test_the_status_line(self):
        from src import features_scan_flow as scan
        found = [_tree(0, 0), _tree(1, 1), _building(2, 2)]
        self.assertIn("1 building and 2 trees", scan.summary(found, {}, {}))
        self.assertEqual(
            scan.summary([], {"message": "OSM was offline."},
                         {"message": "No trees."}),
            "The scan added nothing new. OSM was offline. No trees.")


@unittest.skipUnless(_HAVE_QT, "PyQt6 not installed in this env")
class TestScanThenReview(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls._app = QApplication.instance() or QApplication(["sp-scan"])

    def _apply(self, main):
        """Both sources answered: one tree, one building."""
        from src import features_scan_flow as scan

        def add_buildings(_res, project, **_kw):
            project["features"].append(_building(-113.5, 53.5))
            return {"added": 1, "message": "1 building"}

        def add_trees(main_, _payload, **_kw):
            main_._project["features"].append(_tree(-113.5001, 53.5001))
            return {"added": 1, "message": "1 tree"}

        with mock.patch("src.building_flow.import_buildings_offline",
                        return_value=False), \
                mock.patch("src.osm_features.import_osm_result",
                           side_effect=add_buildings), \
                mock.patch("src.tree_detect_flow.import_tree_result",
                           side_effect=add_trees):
            scan._apply(main, {"buildings": {}, "trees": {}}, boundary=None,
                        margin=30.0, area_note="", bbox={})
        review = main._scan_review
        self.addCleanup(review.close)
        return review

    def test_both_sources_land_as_one_undo_step_and_are_reviewed(self):
        main = _Main()
        review = self._apply(main)
        self.assertEqual(main.checkpoints, ["scan this area"])
        self.assertEqual(len(main._project["features"]), 2)
        self.assertEqual(review.list.count(), 2)
        self.assertIn("1 building and 1 tree", main.status[-1])
        # A row frames its find on the map.
        review.list.setCurrentRow(1)
        self.assertTrue(main.framed)

    def test_keep_the_ticked_takes_out_the_rest_as_one_undo_step(self):
        from PyQt6.QtCore import Qt
        main = _Main()
        review = self._apply(main)
        review.list.item(0).setCheckState(Qt.CheckState.Unchecked)
        review.accept()
        kinds = [f["properties"]["element_type"]
                 for f in main._project["features"]]
        self.assertEqual(kinds, ["existing_tree"])
        self.assertEqual(main.checkpoints,
                         ["scan this area", "remove scanned features"])

    def test_keep_all_takes_nothing_out(self):
        from PyQt6.QtCore import Qt
        main = _Main()
        review = self._apply(main)
        review.list.item(0).setCheckState(Qt.CheckState.Unchecked)
        review.reject()
        self.assertEqual(len(main._project["features"]), 2)


if __name__ == "__main__":
    unittest.main()

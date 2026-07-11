"""
Tests for src/tree_edit_flow.py — persisting drag / scroll-resize of existing
tree & building marks (V2.26). Pure: a fake main with a project dict; no Qt.
"""

import unittest

from src import tree_edit_flow


class _FakeMain:
    def __init__(self, features):
        self._project = {"type": "FeatureCollection",
                         "properties": {"site_config": {}},
                         "features": features}
        self._persistence = None      # no checkpoint → runs the body directly
        self.modified = 0

    def _mark_modified(self):
        self.modified += 1


def _tree(lat, lng, radius=3.0, struct_id="existing_tree"):
    return {"type": "Feature",
            "geometry": {"type": "Point", "coordinates": [lng, lat]},
            "properties": {"element_type": ("existing_tree"
                                            if struct_id == "existing_tree"
                                            else "existing_building"),
                           "struct_id": struct_id, "canopy_radius_m": radius,
                           "height_m": 10.0, "label": "Tree (detected)"}}


class TestMove(unittest.TestCase):
    def test_move_updates_coordinates(self):
        m = _FakeMain([_tree(53.5, -113.3)])
        tree_edit_flow.on_existing_feature_moved(
            m, "mk", "existing_tree", 53.5, -113.3, 53.6, -113.2)
        coords = m._project["features"][0]["geometry"]["coordinates"]
        self.assertEqual(coords, [-113.2, 53.6])
        self.assertGreaterEqual(m.modified, 1)

    def test_move_picks_the_feature_at_the_old_position(self):
        m = _FakeMain([_tree(53.5, -113.3), _tree(53.7, -113.1)])
        tree_edit_flow.on_existing_feature_moved(
            m, "mk", "existing_tree", 53.7, -113.1, 53.71, -113.11)
        # Only the second tree moved; the first is untouched.
        self.assertEqual(
            m._project["features"][0]["geometry"]["coordinates"], [-113.3, 53.5])
        self.assertEqual(
            m._project["features"][1]["geometry"]["coordinates"],
            [-113.11, 53.71])

    def test_move_unknown_position_is_noop(self):
        m = _FakeMain([_tree(53.5, -113.3)])
        tree_edit_flow.on_existing_feature_moved(
            m, "mk", "existing_tree", 10.0, 10.0, 11.0, 11.0)
        self.assertEqual(
            m._project["features"][0]["geometry"]["coordinates"], [-113.3, 53.5])
        self.assertEqual(m.modified, 0)


class TestResize(unittest.TestCase):
    def test_resize_sets_radius_from_diameter(self):
        m = _FakeMain([_tree(53.5, -113.3, radius=3.0)])
        tree_edit_flow.on_existing_feature_resized(
            m, "mk", "existing_tree", 53.5, -113.3, 9.0)
        props = m._project["features"][0]["properties"]
        self.assertEqual(props["canopy_radius_m"], 4.5)   # diameter/2
        self.assertEqual(props["size_m"], 9.0)
        self.assertGreaterEqual(m.modified, 1)

    def test_resize_clamps_tiny(self):
        m = _FakeMain([_tree(53.5, -113.3)])
        tree_edit_flow.on_existing_feature_resized(
            m, "mk", "existing_tree", 53.5, -113.3, 0.2)
        self.assertEqual(
            m._project["features"][0]["properties"]["canopy_radius_m"], 0.5)

    def test_resize_building_mark(self):
        m = _FakeMain([_tree(53.5, -113.3, struct_id="existing_building")])
        tree_edit_flow.on_existing_feature_resized(
            m, "mk", "existing_building", 53.5, -113.3, 8.0)
        self.assertEqual(
            m._project["features"][0]["properties"]["canopy_radius_m"], 4.0)


if __name__ == "__main__":
    unittest.main()

"""
tests/test_splat_flow.py — the map-side glue (V1.65) that draws the baked
"yard photo" overlay and keeps the View toggle in sync. Headless: splat_flow
takes a ``main`` duck-type, so lightweight fakes exercise it without Qt.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import splat_backdrop as sb
from src import splat_flow


class _FakeMapWidget:
    def __init__(self):
        self.drawn = None
        self.cleared = 0

    def draw_splat_ortho_overlay(self, image, bbox, opacity):
        self.drawn = {"image": image, "bbox": bbox, "opacity": opacity}

    def clear_splat_ortho(self):
        self.cleared += 1


class _FakeToolbar:
    def __init__(self):
        self.available = None
        self.checked = None

    def set_yard_photo_available(self, available, *, checked=None):
        self.available = available
        self.checked = checked


class _FakeMain:
    def __init__(self, features):
        self._project = {"type": "FeatureCollection", "features": features,
                         "properties": {}}
        self.map_widget = _FakeMapWidget()
        self.toolbar = _FakeToolbar()
        self.modified = 0

    def _mark_modified(self):
        self.modified += 1


def _feature(ortho_png=None):
    return sb.build_feature(
        file_path="/tmp/yard.ply", origin={"lat": 53.5, "lng": -113.5},
        transform=(1.0, 0.0, 0.0, 0.0), up="z",
        bbox={"south": 53.49, "north": 53.51,
              "west": -113.51, "east": -113.49},
        ortho_png=ortho_png, opacity=0.85)


class TestRestoreSplatOverlay(unittest.TestCase):

    def test_draws_and_enables_when_png_present(self):
        m = _FakeMain([_feature(ortho_png="data:image/png;base64,AAAA")])
        splat_flow.restore_splat_overlay(m)
        self.assertEqual(m.map_widget.drawn["image"],
                         "data:image/png;base64,AAAA")
        self.assertTrue(m.toolbar.available)
        self.assertTrue(m.toolbar.checked)

    def test_enables_unchecked_when_splat_but_no_png(self):
        m = _FakeMain([_feature(ortho_png=None)])
        splat_flow.restore_splat_overlay(m)
        self.assertEqual(m.map_widget.cleared, 1)
        self.assertTrue(m.toolbar.available)   # can still bake it
        self.assertFalse(m.toolbar.checked)

    def test_clears_and_disables_when_no_splat(self):
        m = _FakeMain([])
        splat_flow.restore_splat_overlay(m)
        self.assertEqual(m.map_widget.cleared, 1)
        self.assertFalse(m.toolbar.available)


class TestApplyBakedOrtho(unittest.TestCase):

    def test_stores_png_draws_and_marks_modified(self):
        feat = _feature()
        m = _FakeMain([feat])
        ok = splat_flow.apply_baked_ortho(m, feat, "data:image/png;base64,XYZ")
        self.assertTrue(ok)
        self.assertEqual(feat["properties"]["ortho_png"],
                         "data:image/png;base64,XYZ")
        self.assertEqual(m.map_widget.drawn["image"],
                         "data:image/png;base64,XYZ")
        self.assertTrue(m.toolbar.checked)
        self.assertEqual(m.modified, 1)

    def test_rejects_non_image_result(self):
        feat = _feature()
        m = _FakeMain([feat])
        for bad in (None, "", False, "oops", 123):
            self.assertFalse(splat_flow.apply_baked_ortho(m, feat, bad))
        self.assertNotIn("ortho_png", feat["properties"])
        self.assertIsNone(m.map_widget.drawn)
        self.assertEqual(m.modified, 0)


if __name__ == "__main__":
    unittest.main()

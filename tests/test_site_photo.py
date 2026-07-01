"""
tests/test_site_photo.py — site photo map underlay (F24).

Covers src/site_photo.py (Qt-free maths + persistence):
  1. bbox_from_center: centred, aspect-correct, scales with width.
  2. build_feature: shape, embedded image, bbox ring geometry.
  3. feature_from_project / set_feature (one at a time) / clear_from_project.
  4. set_width / set_opacity recompute + clamp.
  5. overlay_payload (and None when no image).

Pure — no Qt, no DB. (The image encoding + map calls live in the Qt-side
site_photo_flow.py and aren't unit-tested here.)
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import site_photo as sp  # noqa: E402

_IMG = "data:image/jpeg;base64,QUJD"   # tiny stand-in data URL


class TestBbox(unittest.TestCase):
    def test_centered(self):
        b = sp.bbox_from_center(53.5, -113.5, 30.0, 1.0)
        self.assertAlmostEqual((b["south"] + b["north"]) / 2, 53.5, places=6)
        self.assertAlmostEqual((b["west"] + b["east"]) / 2, -113.5, places=6)

    def test_aspect_taller_image_spans_more_lat(self):
        # aspect 2.0 (tall) → on-ground height is 2× width → lat span > lng span (in m)
        from src.projection import metres_per_deg
        m_lat, m_lng = metres_per_deg(53.5)
        b = sp.bbox_from_center(53.5, -113.5, 40.0, 2.0)
        lat_m = (b["north"] - b["south"]) * m_lat
        lng_m = (b["east"] - b["west"]) * m_lng
        self.assertAlmostEqual(lat_m, 80.0, places=3)
        self.assertAlmostEqual(lng_m, 40.0, places=3)

    def test_wider_width_bigger_box(self):
        small = sp.bbox_from_center(53.5, -113.5, 10.0, 1.0)
        big = sp.bbox_from_center(53.5, -113.5, 100.0, 1.0)
        self.assertGreater(big["north"] - big["south"],
                           small["north"] - small["south"])


class TestBuildFeature(unittest.TestCase):
    def setUp(self):
        self.f = sp.build_feature(image=_IMG, center={"lat": 53.5, "lng": -113.5},
                                  width_m=30.0, aspect=0.75, name="yard.jpg")

    def test_shape(self):
        props = self.f["properties"]
        self.assertEqual(props["element_type"], "site_photo")
        self.assertEqual(props["image"], _IMG)
        self.assertEqual(props["width_m"], 30.0)
        self.assertEqual(props["aspect"], 0.75)
        self.assertEqual(props["name"], "yard.jpg")
        self.assertEqual(set(props["bbox"]), {"south", "north", "west", "east"})

    def test_geometry_is_closed_ring(self):
        ring = self.f["geometry"]["coordinates"][0]
        self.assertEqual(self.f["geometry"]["type"], "Polygon")
        self.assertEqual(ring[0], ring[-1])
        self.assertEqual(len(ring), 5)


class TestPersistence(unittest.TestCase):
    def test_set_replaces_existing(self):
        project = {"features": []}
        f1 = sp.build_feature(image=_IMG, center={"lat": 1, "lng": 2},
                              width_m=10, aspect=1.0)
        f2 = sp.build_feature(image=_IMG, center={"lat": 3, "lng": 4},
                              width_m=20, aspect=1.0)
        sp.set_feature(project, f1)
        sp.set_feature(project, f2)
        photos = [f for f in project["features"]
                  if f["properties"]["element_type"] == "site_photo"]
        self.assertEqual(len(photos), 1)
        self.assertEqual(photos[0]["properties"]["width_m"], 20)

    def test_set_feature_keeps_other_features(self):
        project = {"features": [{"properties": {"element_type": "plant"}}]}
        sp.set_feature(project, sp.build_feature(
            image=_IMG, center={"lat": 1, "lng": 2}, width_m=10, aspect=1.0))
        self.assertEqual(len(project["features"]), 2)

    def test_feature_from_project_and_clear(self):
        project = {"features": []}
        self.assertIsNone(sp.feature_from_project(project))
        sp.set_feature(project, sp.build_feature(
            image=_IMG, center={"lat": 1, "lng": 2}, width_m=10, aspect=1.0))
        self.assertIsNotNone(sp.feature_from_project(project))
        self.assertTrue(sp.clear_from_project(project))
        self.assertIsNone(sp.feature_from_project(project))
        self.assertFalse(sp.clear_from_project(project))   # nothing left


class TestMutators(unittest.TestCase):
    def setUp(self):
        self.f = sp.build_feature(image=_IMG, center={"lat": 53.5, "lng": -113.5},
                                  width_m=30.0, aspect=1.0)

    def test_set_width_recomputes_bbox_and_ring(self):
        before = self.f["properties"]["bbox"]["north"] - self.f["properties"]["bbox"]["south"]
        sp.set_width(self.f, 60.0)
        after = self.f["properties"]["bbox"]["north"] - self.f["properties"]["bbox"]["south"]
        self.assertEqual(self.f["properties"]["width_m"], 60.0)
        self.assertGreater(after, before)
        # ring geometry kept in step with the new bbox
        self.assertEqual(self.f["geometry"]["coordinates"][0][0],
                         self.f["geometry"]["coordinates"][0][-1])

    def test_set_width_clamps_min(self):
        sp.set_width(self.f, -5.0)
        self.assertGreaterEqual(self.f["properties"]["width_m"], 0.5)

    def test_set_opacity_clamps(self):
        sp.set_opacity(self.f, 5.0)
        self.assertEqual(self.f["properties"]["opacity"], 1.0)
        sp.set_opacity(self.f, -1.0)
        self.assertEqual(self.f["properties"]["opacity"], 0.0)


class TestOverlayPayload(unittest.TestCase):
    def test_payload(self):
        f = sp.build_feature(image=_IMG, center={"lat": 1, "lng": 2},
                             width_m=10, aspect=1.0, opacity=0.5)
        p = sp.overlay_payload(f)
        self.assertEqual(p["image"], _IMG)
        self.assertEqual(p["opacity"], 0.5)
        self.assertEqual(set(p["bbox"]), {"south", "north", "west", "east"})

    def test_none_without_image(self):
        self.assertIsNone(sp.overlay_payload(None))
        f = sp.build_feature(image=_IMG, center={"lat": 1, "lng": 2},
                             width_m=10, aspect=1.0)
        f["properties"]["image"] = ""
        self.assertIsNone(sp.overlay_payload(f))


if __name__ == "__main__":
    unittest.main()

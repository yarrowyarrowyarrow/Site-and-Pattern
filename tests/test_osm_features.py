"""
tests/test_osm_features.py

V1.51 — parsing OpenStreetMap (Overpass) responses into existing trees /
buildings and importing them into a project. Fixture-only (no live API; the
sandbox blocks egress and the live path degrades gracefully by design).
"""

import math
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import src.osm_features as osm  # noqa: E402
from src.project import new_project  # noqa: E402

# A representative Overpass response: a 2-storey building way, two trees
# (one with a crown diameter, one with a height tag), and a non-building way
# that must be ignored.
_FIXTURE = {"elements": [
    {"type": "way", "tags": {"building": "house", "building:levels": "2"},
     "geometry": [{"lat": 53.5000, "lon": -113.5000},
                  {"lat": 53.5000, "lon": -113.4998},
                  {"lat": 53.5002, "lon": -113.4998},
                  {"lat": 53.5002, "lon": -113.5000},
                  {"lat": 53.5000, "lon": -113.5000}]},
    {"type": "node", "tags": {"natural": "tree", "diameter_crown": "8"},
     "lat": 53.5005, "lon": -113.4995},
    {"type": "node", "tags": {"natural": "tree", "height": "15 m"},
     "lat": 53.5006, "lon": -113.4994},
    {"type": "way", "tags": {"highway": "residential"},
     "geometry": [{"lat": 53.5, "lon": -113.5}]},
]}


class TestParse(unittest.TestCase):
    def test_counts(self):
        feats = osm.parse_elements(_FIXTURE)
        self.assertEqual(sum(1 for f in feats if f["kind"] == "building"), 1)
        self.assertEqual(sum(1 for f in feats if f["kind"] == "tree"), 2)

    def test_building_height_from_levels(self):
        b = next(f for f in osm.parse_elements(_FIXTURE)
                 if f["kind"] == "building")
        self.assertEqual(b["height_m"], 6.0)        # 2 levels × 3 m
        self.assertGreater(b["radius_m"], 0)
        self.assertGreaterEqual(len(b["footprint"]), 4)   # keeps the true ring

    def test_tree_crown_to_radius(self):
        trees = [f for f in osm.parse_elements(_FIXTURE) if f["kind"] == "tree"]
        crowned = next(t for t in trees if abs(t["radius_m"] - 4.0) < 1e-6)
        self.assertEqual(crowned["radius_m"], 4.0)  # crown 8 → radius 4

    def test_tree_explicit_height(self):
        trees = [f for f in osm.parse_elements(_FIXTURE) if f["kind"] == "tree"]
        self.assertTrue(any(abs(t["height_m"] - 15.0) < 1e-6 for t in trees))

    def test_graceful_on_none_and_empty(self):
        self.assertEqual(osm.parse_elements(None), [])
        self.assertEqual(osm.parse_elements({}), [])
        self.assertEqual(osm.parse_elements({"elements": []}), [])

    def test_degenerate_building_skipped(self):
        bad = {"elements": [{"type": "way", "tags": {"building": "yes"},
                             "geometry": [{"lat": 1, "lon": 2}]}]}  # <3 pts
        self.assertEqual(osm.parse_elements(bad), [])


class TestImport(unittest.TestCase):
    def test_adds_to_project(self):
        proj = new_project("t")
        feats = osm.parse_elements(_FIXTURE)
        n = osm.add_features_to_project(feats, proj)
        self.assertEqual(n, 3)
        ets = [f["properties"]["element_type"] for f in proj["features"]]
        self.assertEqual(ets.count("existing_tree"), 2)
        # V1.58: a building with a footprint imports as a true-outline
        # canopy_footprint Polygon, not a Point existing_building.
        self.assertEqual(ets.count("canopy_footprint"), 1)
        self.assertEqual(ets.count("existing_building"), 0)

    def test_building_imports_as_true_polygon(self):
        proj = new_project("t")
        osm.add_features_to_project(osm.parse_elements(_FIXTURE), proj)
        b = next(f for f in proj["features"]
                 if f["properties"]["element_type"] == "canopy_footprint")
        self.assertEqual(b["geometry"]["type"], "Polygon")
        ring = b["geometry"]["coordinates"][0]
        self.assertEqual(ring[0], ring[-1])            # closed ring
        self.assertGreaterEqual(len(ring), 5)          # 4 corners + close
        props = b["properties"]
        self.assertTrue(props["cast_shade"])
        self.assertEqual(props["source"], "osm")
        self.assertGreater(props["height_m"], 0)
        self.assertGreater(props["canopy_radius_m"], 0)
        self.assertIn("lat", props)                    # centroid for keep-out
        self.assertIn("lng", props)

    def test_building_caster_carries_footprint(self):
        proj = new_project("t")
        osm.add_features_to_project(osm.parse_elements(_FIXTURE), proj)
        from src.shade import casters_from_project
        casters = casters_from_project(proj)
        self.assertTrue(any(c.get("footprint") for c in casters))

    def test_building_without_footprint_falls_back_to_point(self):
        proj = new_project("t")
        # A building dict lacking a usable footprint (legacy/degenerate) must
        # still import as a Point existing_building so nothing is lost.
        item = {"kind": "building", "lat": 53.5, "lng": -113.5,
                "height_m": 5.0, "radius_m": 4.0}
        n = osm.add_features_to_project([item], proj)
        self.assertEqual(n, 1)
        f = proj["features"][-1]
        self.assertEqual(f["geometry"]["type"], "Point")
        self.assertEqual(f["properties"]["element_type"], "existing_building")

    def test_reimport_dedupes_building(self):
        proj = new_project("t")
        osm.add_features_to_project(osm.parse_elements(_FIXTURE), proj)
        # Re-importing the same area adds nothing (trees + building deduped).
        n2 = osm.add_features_to_project(osm.parse_elements(_FIXTURE), proj)
        self.assertEqual(n2, 0)

    def test_dedupes_against_existing(self):
        proj = new_project("t")
        # Pre-mark a tree at the same spot as one OSM tree.
        proj["features"].append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [-113.4995, 53.5005]},
            "properties": {"element_type": "existing_tree"}})
        n = osm.add_features_to_project(osm.parse_elements(_FIXTURE), proj)
        self.assertEqual(n, 2)     # the duplicate tree is skipped

    def test_imported_features_feed_shade_and_keepout(self):
        proj = new_project("t")
        osm.add_features_to_project(osm.parse_elements(_FIXTURE), proj)
        from src.shade import casters_from_project
        from src.exclusion import keepout_circles
        self.assertEqual(len(casters_from_project(proj)), 3)
        self.assertEqual(len(keepout_circles(proj)), 3)


class TestRingHelpers(unittest.TestCase):
    """V1.58 — shared footprint-sizing helpers (OSM import, drawn shapes, and
    the footprint-edit handler all size canopy_radius_m through these)."""

    def _square(self, half_m=5.0, clat=53.5, clng=-113.5):
        dlat = half_m / 111320.0
        dlng = half_m / (111320.0 * math.cos(math.radians(clat)))
        return [[clng - dlng, clat - dlat], [clng + dlng, clat - dlat],
                [clng + dlng, clat + dlat], [clng - dlng, clat + dlat],
                [clng - dlng, clat - dlat]]

    def test_centroid_of_square(self):
        c = osm.ring_centroid(self._square())
        self.assertIsNotNone(c)
        self.assertAlmostEqual(c[0], 53.5, places=4)
        self.assertAlmostEqual(c[1], -113.5, places=4)

    def test_radius_of_square(self):
        # Half-extent 5 m → corner distance ≈ 5·√2 ≈ 7.07 m.
        r = osm.ring_radius_m(self._square(5.0))
        self.assertAlmostEqual(r, 5.0 * math.sqrt(2), delta=0.2)

    def test_radius_empty_ring(self):
        self.assertEqual(osm.ring_radius_m([]), 0.0)

    def test_centroid_degenerate_none(self):
        self.assertIsNone(osm.ring_centroid([[0, 0], [1, 1]]))


if __name__ == "__main__":
    unittest.main()

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

    def test_relation_building_outer_rings_parse(self):
        """Multipolygon buildings (V2.13): each closed outer member becomes a
        footprint; unclosed fragments and inner (courtyard) rings are skipped."""
        closed = [{"lat": 53.5000, "lon": -113.5000},
                  {"lat": 53.5000, "lon": -113.4996},
                  {"lat": 53.5003, "lon": -113.4996},
                  {"lat": 53.5003, "lon": -113.5000},
                  {"lat": 53.5000, "lon": -113.5000}]
        inner = [{"lat": 53.5001, "lon": -113.4999},
                 {"lat": 53.5001, "lon": -113.4998},
                 {"lat": 53.5002, "lon": -113.4998},
                 {"lat": 53.5001, "lon": -113.4999}]
        fragment = [{"lat": 53.5004, "lon": -113.5000},
                    {"lat": 53.5004, "lon": -113.4996},
                    {"lat": 53.5006, "lon": -113.4996}]   # not closed
        rel = {"elements": [{
            "type": "relation",
            "tags": {"building": "apartments", "building:levels": "4"},
            "members": [
                {"type": "way", "role": "outer", "geometry": closed},
                {"type": "way", "role": "inner", "geometry": inner},
                {"type": "way", "role": "outer", "geometry": fragment},
            ],
        }]}
        feats = osm.parse_elements(rel)
        self.assertEqual(len(feats), 1)
        b = feats[0]
        self.assertEqual(b["kind"], "building")
        self.assertEqual(b["height_m"], 12.0)          # 4 levels × 3 m
        self.assertGreaterEqual(len(b["footprint"]), 4)

    def test_relation_without_building_tag_ignored(self):
        rel = {"elements": [{
            "type": "relation", "tags": {"landuse": "residential"},
            "members": [{"type": "way", "role": "outer",
                         "geometry": [{"lat": 1, "lon": 1}, {"lat": 1, "lon": 2},
                                      {"lat": 2, "lon": 2}, {"lat": 1, "lon": 1}]}],
        }]}
        self.assertEqual(osm.parse_elements(rel), [])


class TestQuery(unittest.TestCase):
    _BBOX = {"south": 53.5, "west": -113.51, "north": 53.51, "east": -113.5}

    def test_building_query_includes_ways_and_relations(self):
        q = osm._query(self._BBOX, include_trees=False, include_buildings=True)
        self.assertIn('way["building"](53.5,-113.51,53.51,-113.5);', q)
        self.assertIn('relation["building"](53.5,-113.51,53.51,-113.5);', q)
        self.assertIn("out geom;", q)

    def test_tree_query_unchanged(self):
        q = osm._query(self._BBOX, include_trees=True, include_buildings=False)
        self.assertIn('node["natural"="tree"]', q)
        self.assertNotIn("building", q)


class TestBboxHelpers(unittest.TestCase):
    _TRI = [(53.5000, -113.5000), (53.5000, -113.4990), (53.5009, -113.4995)]

    def test_boundary_bbox_is_padded(self):
        """The search box grows ~30 m past the boundary so buildings whose
        corner nodes hug the drawn edge still match (V2.13 fix)."""
        bbox, note = osm.bbox_with_area_note(self._TRI, {})
        self.assertLess(bbox["south"], 53.5000)
        self.assertGreater(bbox["north"], 53.5009)
        self.assertLess(bbox["west"], -113.5000)
        self.assertGreater(bbox["east"], -113.4990)
        # ~30 m in degrees latitude.
        self.assertAlmostEqual(53.5000 - bbox["south"], 30.0 / 111320.0,
                               places=6)
        self.assertIn("boundary", note)
        self.assertIn("30 m", note)

    def test_pin_fallback_note_and_size(self):
        bbox, note = osm.bbox_with_area_note(
            None, {"latitude": 53.5, "longitude": -113.5})
        self.assertAlmostEqual(bbox["north"] - bbox["south"],
                               2 * 60.0 / 111320.0, places=6)
        self.assertIn("around the pin", note)
        self.assertIn("boundary", note)      # tells the user how to control it

    def test_no_boundary_no_pin(self):
        bbox, note = osm.bbox_with_area_note(None, {})
        self.assertIsNone(bbox)
        self.assertEqual(note, "")

    def test_back_compat_wrapper_matches(self):
        bbox = osm.bbox_from_boundary_or_pin(self._TRI, {})
        bbox2, _ = osm.bbox_with_area_note(self._TRI, {})
        self.assertEqual(bbox, bbox2)


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

    def test_building_shape_ids_unique(self):
        # Two buildings must get distinct shape_ids — a count-based scheme could
        # collide after a delete; uuids never do.
        two = {"elements": [
            {"type": "way", "tags": {"building": "yes"},
             "geometry": [{"lat": 53.5000, "lon": -113.5000},
                          {"lat": 53.5000, "lon": -113.4998},
                          {"lat": 53.5002, "lon": -113.4998},
                          {"lat": 53.5000, "lon": -113.5000}]},
            {"type": "way", "tags": {"building": "yes"},
             "geometry": [{"lat": 53.5010, "lon": -113.5010},
                          {"lat": 53.5010, "lon": -113.5008},
                          {"lat": 53.5012, "lon": -113.5008},
                          {"lat": 53.5010, "lon": -113.5010}]},
        ]}
        proj = new_project("t")
        osm.add_features_to_project(osm.parse_elements(two), proj)
        ids = [f["properties"]["shape_id"] for f in proj["features"]
               if f["properties"].get("element_type") == "canopy_footprint"]
        self.assertEqual(len(ids), 2)
        self.assertEqual(len(set(ids)), 2)          # all unique

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

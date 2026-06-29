"""
tests/test_building_store.py — the offline building-footprint pack (V1.66).

Headless stdlib unittest against a temp DB file (never the real
~/.local/share/PermaDesign/buildings.db), matching the terrain/scan tests.
Covers the tile round-trip, bbox filtering, cross-tile dedup, and the
complete/clear lifecycle.
"""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.building_store import BuildingStore


def _building(lat, lng, *, half=0.0005, height=6.0):
    """A small square building (closed [lng, lat] ring) centred on lat/lng."""
    fp = [[lng - half, lat - half], [lng + half, lat - half],
          [lng + half, lat + half], [lng - half, lat + half],
          [lng - half, lat - half]]
    return {"kind": "building", "lat": lat, "lng": lng,
            "height_m": height, "radius_m": 5.0, "footprint": fp}


class TestBuildingStore(unittest.TestCase):

    def setUp(self):
        self.path = os.path.join(tempfile.mkdtemp(), "buildings.db")
        self.store = BuildingStore(self.path)

    def _bbox(self, lat, lng, pad=0.002):
        return {"south": lat - pad, "north": lat + pad,
                "west": lng - pad, "east": lng + pad}

    def test_store_and_query_roundtrip(self):
        b = _building(53.5, -113.5, height=9.0)
        self.assertEqual(self.store.add_buildings([b]), 1)
        got = self.store.buildings_in_bbox(self._bbox(53.5, -113.5))
        self.assertEqual(len(got), 1)
        self.assertEqual(got[0]["height_m"], 9.0)
        self.assertEqual(got[0]["footprint"], b["footprint"])

    def test_far_bbox_returns_nothing(self):
        self.store.add_buildings([_building(53.5, -113.5)])
        self.assertEqual(self.store.buildings_in_bbox(self._bbox(51.0, -114.0)),
                         [])

    def test_dedup_on_reinsert(self):
        b = _building(53.5, -113.5)
        self.assertEqual(self.store.add_buildings([b]), 1)
        self.assertEqual(self.store.add_buildings([b]), 0)   # same footprint
        self.assertEqual(len(self.store.buildings_in_bbox(
            self._bbox(53.5, -113.5))), 1)

    def test_dedup_across_tiles(self):
        # A building on a 0.01° tile boundary lands in multiple tiles; a bbox
        # spanning the seam must still return it exactly once.
        b = _building(53.50, -113.50, half=0.0)   # a point on the grid line
        b = _building(53.5000, -113.5000)
        self.store.add_buildings([b])
        wide = {"south": 53.49, "north": 53.51, "west": -113.51, "east": -113.49}
        got = self.store.buildings_in_bbox(wide)
        self.assertEqual(len(got), 1)

    def test_complete_and_count_lifecycle(self):
        self.assertFalse(self.store.has_data())
        self.store.add_buildings([_building(53.5, -113.5),
                                  _building(53.501, -113.5)])
        self.store.mark_complete("Edmonton test", 2)
        self.assertTrue(self.store.has_data())
        self.assertEqual(self.store.feature_count(), 2)
        self.assertEqual(self.store.region(), "Edmonton test")

    def test_clear(self):
        self.store.add_buildings([_building(53.5, -113.5)])
        self.store.mark_complete("x", 1)
        self.store.clear()
        self.assertFalse(self.store.has_data())
        self.assertEqual(self.store.buildings_in_bbox(
            self._bbox(53.5, -113.5)), [])

    def test_non_building_items_ignored(self):
        tree = {"kind": "tree", "lat": 53.5, "lng": -113.5}
        self.assertEqual(self.store.add_buildings([tree]), 0)


if __name__ == "__main__":
    unittest.main()

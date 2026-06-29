"""
tests/test_building_downloader.py — the region download loop (V1.66).

Headless: the network fetch is injected, so the loop, tiling, cancel, and
completion are exercised without Overpass. Also asserts the stored items stay
compatible with the existing osm_features import pipeline (the whole point of
reusing the OSM item shape).
"""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import osm_features as osm
from src.building_downloader import download_region, tile_region
from src.building_store import BuildingStore

# Reuse the osm_features fixture shape: a 2-storey building way.
_BUILDING_WAY = {
    "type": "way", "tags": {"building": "house", "building:levels": "2"},
    "geometry": [{"lat": 53.5000, "lon": -113.5000},
                 {"lat": 53.5000, "lon": -113.4994},
                 {"lat": 53.5004, "lon": -113.4994},
                 {"lat": 53.5004, "lon": -113.5000},
                 {"lat": 53.5000, "lon": -113.5000}]}
_REGION = {"south": 53.49, "north": 53.51, "west": -113.51, "east": -113.49}


def _building_items():
    return osm.parse_elements({"elements": [_BUILDING_WAY]})


class TestTileRegion(unittest.TestCase):

    def test_covers_area_and_clamps(self):
        tiles = tile_region(_REGION, step_deg=0.01)
        self.assertEqual(len(tiles), 2 * 2)   # 0.02°/0.01° = 2 each way
        for t in tiles:
            self.assertGreaterEqual(t["south"], _REGION["south"] - 1e-9)
            self.assertLessEqual(t["north"], _REGION["north"] + 1e-9)
            self.assertLessEqual(t["east"], _REGION["east"] + 1e-9)

    def test_single_tile_when_region_smaller_than_step(self):
        self.assertEqual(len(tile_region(_REGION, step_deg=1.0)), 1)


class TestDownloadRegion(unittest.TestCase):

    def setUp(self):
        self.path = os.path.join(tempfile.mkdtemp(), "buildings.db")
        self.store = BuildingStore(self.path)

    def test_populates_store_and_marks_complete(self):
        # Buildings appear only in the first sub-tile; the rest are empty.
        calls = {"n": 0}

        def fetch(_subbbox):
            calls["n"] += 1
            return _building_items() if calls["n"] == 1 else []

        total = download_region(_REGION, self.store, fetch_fn=fetch,
                                pace_s=0, region_name="test")
        self.assertEqual(total, 1)
        self.assertTrue(self.store.has_data())
        self.assertEqual(self.store.region(), "test")
        got = self.store.buildings_in_bbox(_REGION)
        self.assertEqual(len(got), 1)
        self.assertEqual(got[0]["kind"], "building")

    def test_progress_reported_per_tile(self):
        seen = []
        download_region(_REGION, self.store, fetch_fn=lambda b: [],
                        on_progress=lambda tot, done, total: seen.append(done),
                        pace_s=0)
        self.assertTrue(seen)
        self.assertEqual(seen[-1], len(tile_region(_REGION)))

    def test_cancel_leaves_incomplete(self):
        total = download_region(_REGION, self.store, fetch_fn=_no_net,
                                should_cancel=lambda: True, pace_s=0)
        self.assertEqual(total, 0)
        self.assertFalse(self.store.has_data())   # not marked complete

    def test_flaky_tile_does_not_abort_run(self):
        def fetch(_b):
            raise RuntimeError("overpass hiccup")
        # Should swallow the error per-tile and still complete the region.
        download_region(_REGION, self.store, fetch_fn=fetch, pace_s=0)
        self.assertTrue(self.store.has_data())


class TestPipelineCompatibility(unittest.TestCase):
    """Stored items must still flow through add_features_to_project unchanged."""

    def test_stored_buildings_import_as_canopy_footprints(self):
        path = os.path.join(tempfile.mkdtemp(), "buildings.db")
        store = BuildingStore(path)
        store.add_buildings(_building_items())
        items = store.buildings_in_bbox(_REGION)
        proj = {"type": "FeatureCollection", "properties": {}, "features": []}
        added = osm.add_features_to_project(items, proj)
        self.assertEqual(added, 1)
        b = next(f for f in proj["features"]
                 if f["properties"]["element_type"] == "canopy_footprint")
        self.assertEqual(b["geometry"]["type"], "Polygon")
        self.assertGreater(b["properties"]["height_m"], 0)   # 2 levels × 3 m
        self.assertTrue(b["properties"]["cast_shade"])


def _no_net(_b):
    raise AssertionError("fetch should not run when cancelled before tile 0")


if __name__ == "__main__":
    unittest.main()

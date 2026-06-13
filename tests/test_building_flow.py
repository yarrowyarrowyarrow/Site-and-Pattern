"""
tests/test_building_flow.py — the per-design offline fast path (V1.66).

Headless: redirect the building DB to a temp file (never the real
~/.local/share/PermaDesign/buildings.db) and drive
building_flow.import_buildings_offline with a duck-typed ``main``. The QThread
download path (start_building_download) needs Qt and is covered manually.
"""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import building_flow, building_store
from src import osm_features as osm
from src.building_store import BuildingStore

_BUILDING_WAY = {
    "type": "way", "tags": {"building": "house", "building:levels": "2"},
    "geometry": [{"lat": 53.5000, "lon": -113.5000},
                 {"lat": 53.5000, "lon": -113.4994},
                 {"lat": 53.5004, "lon": -113.4994},
                 {"lat": 53.5004, "lon": -113.5000},
                 {"lat": 53.5000, "lon": -113.5000}]}
_BBOX = {"south": 53.49, "north": 53.51, "west": -113.51, "east": -113.49}


class _FakeRouter:
    def __init__(self):
        self.reloaded = 0

    def _reload_existing_features(self):
        self.reloaded += 1


class _FakePanel:
    def __init__(self):
        self.status = None

    def set_osm_status(self, text):
        self.status = text


class _FakeMain:
    def __init__(self):
        self._project = {"type": "FeatureCollection", "properties": {},
                         "features": []}
        self._map_events = _FakeRouter()
        self.site_panel = _FakePanel()
        self.modified = 0

    def _mark_modified(self):
        self.modified += 1


class TestImportBuildingsOffline(unittest.TestCase):

    def setUp(self):
        # Redirect the building DB to a temp file for the whole module.
        self._tmp = os.path.join(tempfile.mkdtemp(), "buildings.db")
        self._orig = building_store._db_path
        building_store._db_path = lambda: self._tmp

    def tearDown(self):
        building_store._db_path = self._orig

    def test_no_pack_returns_false(self):
        main = _FakeMain()
        self.assertFalse(building_flow.import_buildings_offline(main, _BBOX))
        self.assertEqual(main._project["features"], [])

    def test_pack_present_imports_and_returns_true(self):
        store = BuildingStore()
        store.add_buildings(osm.parse_elements({"elements": [_BUILDING_WAY]}))
        store.mark_complete("test", 1)

        main = _FakeMain()
        handled = building_flow.import_buildings_offline(main, _BBOX)
        self.assertTrue(handled)
        ets = [f["properties"]["element_type"] for f in main._project["features"]]
        self.assertIn("canopy_footprint", ets)
        self.assertEqual(main.modified, 1)
        self.assertEqual(main._map_events.reloaded, 1)
        self.assertIn("offline pack", main.site_panel.status)

    def test_pack_present_but_area_empty_returns_false(self):
        store = BuildingStore()
        store.add_buildings(osm.parse_elements({"elements": [_BUILDING_WAY]}))
        store.mark_complete("test", 1)
        far = {"south": 51.0, "north": 51.01, "west": -114.0, "east": -113.99}
        main = _FakeMain()
        self.assertFalse(building_flow.import_buildings_offline(main, far))


if __name__ == "__main__":
    unittest.main()

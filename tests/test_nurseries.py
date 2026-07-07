"""
tests/test_nurseries.py — native-plant supplier directory (schema v44/45, V2.18).

The directory is NATIVE-SPECIFIC (rebuilt from the Native Plant Society of
Saskatchewan supplier list) — no general garden centres. Verifies seeding and the
curated `native_sources_near` framing the site panel uses: the native-plant
society leads (sales & education, province-wide), the nearest native suppliers
follow, and distant mail-order suppliers are framed as "ships to you" rather than
by a discouraging distance. Runs against a fresh temp DB — no network, no Qt.
"""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_TMP_DIR = tempfile.mkdtemp(prefix="permadesign_nursery_test_")

import src.db.plants as _plants_mod  # noqa: E402

_plants_mod._DATA_DIR = _TMP_DIR
_plants_mod._DB_PATH = os.path.join(_TMP_DIR, "permadesign_test.db")

from src.db.plants import init_db  # noqa: E402
from src.db import nurseries as N  # noqa: E402

_CITIES = {
    "Regina": (50.4452, -104.6189),
    "Lumsden": (50.6500, -104.8700),
    "Saskatoon": (52.1332, -106.6700),
    "North Battleford": (52.7575, -108.2861),
}

_NATIVE_KINDS = {"society", "native_nursery", "seed_house"}


class TestNurseryDirectory(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        init_db()

    def test_directory_seeded_both_provinces(self):
        rows = N.all_nurseries()
        self.assertGreaterEqual(len(rows), 12)
        provs = {r["province"] for r in rows}
        self.assertIn("SK", provs)
        self.assertIn("AB", provs)

    def test_all_entries_native_specific(self):
        # No general garden centres — every entry is a native-plant supplier,
        # seed house, society or native-landscape designer.
        for r in N.all_nurseries():
            self.assertIn(r.get("kind"), _NATIVE_KINDS,
                          f"{r['name']} has non-native kind {r.get('kind')!r}")
            self.assertIn(r.get("sells"), ("native_specialist", "seed_or_plug"))

    def test_a_native_plant_society_exists(self):
        self.assertTrue(any(r["kind"] == "society" for r in N.all_nurseries()))

    def test_near_sorted_with_distance(self):
        near = N.nurseries_near(*_CITIES["Saskatoon"], limit=5)
        self.assertTrue(near)
        self.assertEqual([n["distance_km"] for n in near],
                         sorted(n["distance_km"] for n in near))


class TestNativeSourcesFraming(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        init_db()

    def test_every_target_city_leads_with_society(self):
        # The user's ask: for Regina/Lumsden (no local native nursery), lead with
        # the society's sales/education rather than a far garden centre.
        for city, (lat, lng) in _CITIES.items():
            rows = N.native_sources_near(lat, lng, limit=5)
            self.assertTrue(rows, f"no native sources for {city}")
            self.assertEqual(rows[0]["kind"], "society",
                             f"{city} should lead with a native-plant society")
            self.assertIn("sales", rows[0]["access"])

    def test_no_garden_centre_or_designer_ever_surfaces(self):
        # The directory carries only native sellers/societies now — no general
        # garden centres and (per user request) no landscape designers.
        for city, (lat, lng) in _CITIES.items():
            for n in N.native_sources_near(lat, lng, limit=6):
                self.assertNotIn(n.get("kind"), ("garden_centre", "designer"))
                self.assertIn(n.get("kind"), _NATIVE_KINDS)

    def test_north_battleford_has_local_native_seed(self):
        # Prairie Garden Seeds is in North Battleford — must surface as local.
        rows = N.native_sources_near(*_CITIES["North Battleford"], limit=5)
        pgs = next((n for n in rows if "Prairie Garden Seeds" in n["name"]), None)
        self.assertIsNotNone(pgs, "Prairie Garden Seeds should surface")
        self.assertEqual(pgs["city"], "North Battleford")
        self.assertLess(pgs["distance_km"], 20.0)

    def test_regina_distant_supplier_framed_as_ships(self):
        # Regina has no local native nursery; distant mail-order suppliers must
        # read "ships to you", never a bare 200 km distance.
        rows = N.native_sources_near(*_CITIES["Regina"], limit=5)
        suppliers = [n for n in rows if n["kind"] in ("native_nursery", "seed_house")]
        self.assertTrue(suppliers)
        for n in suppliers:
            if n.get("ships") and n["distance_km"] > 60:
                self.assertIn("ships to you", n["access"])

    def test_saskatoon_surfaces_local_supplier(self):
        rows = N.native_sources_near(*_CITIES["Saskatoon"], limit=5)
        local = [n for n in rows
                 if n["kind"] in ("native_nursery", "seed_house")
                 and n["distance_km"] < 40]
        self.assertTrue(local, "Saskatoon should surface a nearby native supplier")

    def test_access_label_forms(self):
        self.assertIn("province-wide", N.access_label({"kind": "society"}))
        self.assertIn("ships to you", N.access_label(
            {"kind": "seed_house", "city": "Aberdeen", "distance_km": 240, "ships": 1}))
        self.assertIn("km", N.access_label(
            {"kind": "native_nursery", "city": "Saskatoon", "distance_km": 2, "ships": 0}))

    def test_reseed_idempotent(self):
        before = len(N.all_nurseries())
        init_db()
        self.assertEqual(len(N.all_nurseries()), before)


if __name__ == "__main__":
    unittest.main()

"""
tests/test_nurseries.py — native-plant nursery directory (schema v44, V2.18).

Verifies the directory seeds from data/nurseries_master.json and that the
distance-sorted proximity queries surface the right suppliers for the
Saskatchewan cities the expansion targets (Regina, Lumsden, Saskatoon,
North Battleford). Runs against a fresh temp DB — no network, no Qt.
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

from src.db.plants import init_db, get_connection  # noqa: E402
from src.db import nurseries as N  # noqa: E402

_CITIES = {
    "Regina": (50.4452, -104.6189),
    "Lumsden": (50.6500, -104.8700),
    "Saskatoon": (52.1332, -106.6700),
    "North Battleford": (52.7575, -108.2861),
}


class TestNurseryDirectory(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        init_db()

    def test_directory_seeded(self):
        rows = N.all_nurseries()
        self.assertGreaterEqual(len(rows), 10)
        # Both prairie provinces represented.
        provs = {r["province"] for r in rows}
        self.assertIn("SK", provs)
        self.assertIn("AB", provs)

    def test_sells_maps_to_availability_enum(self):
        valid = {"native_specialist", "seed_or_plug", "garden_centre",
                 "big_box", "rare", ""}
        for r in N.all_nurseries():
            self.assertIn(r.get("sells", ""), valid)

    def test_near_returns_sorted_with_distance(self):
        near = N.nurseries_near(*_CITIES["Saskatoon"], limit=5)
        self.assertTrue(near)
        dists = [n["distance_km"] for n in near]
        self.assertEqual(dists, sorted(dists))
        for n in near:
            self.assertIn("distance_km", n)

    def test_each_target_city_has_a_nearby_supplier(self):
        # Every target city should surface at least one supplier within ~150 km
        # (a same-day drive) — the SK cities the expansion is built for.
        for city, (lat, lng) in _CITIES.items():
            near = N.nurseries_near(lat, lng, limit=3)
            self.assertTrue(near, f"no suppliers found for {city}")
            self.assertLess(near[0]["distance_km"], 150.0,
                            f"nearest supplier for {city} is too far")

    def test_regina_lumsden_share_regina_supplier(self):
        # Lumsden (Qu'Appelle valley) is served by Regina — its nearest supplier
        # should be in Regina.
        near = N.nurseries_near(*_CITIES["Lumsden"], limit=1)
        self.assertEqual(near[0]["city"], "Regina")

    def test_battleford_nearest_is_cochin_seed_house(self):
        # Prairie Garden Seeds (Cochin) is the closest supplier to the Battlefords.
        near = N.nurseries_near(*_CITIES["North Battleford"], limit=1)
        self.assertEqual(near[0]["city"], "Cochin")

    def test_province_filter(self):
        sk = N.nurseries_near(*_CITIES["Regina"], limit=20, province="SK")
        self.assertTrue(sk)
        self.assertTrue(all(n["province"] == "SK" for n in sk))

    def test_availability_channel_matching(self):
        # A native_specialist plant should only surface native/seed suppliers.
        got = N.nurseries_for_availability(
            "native_specialist", *_CITIES["Saskatoon"], limit=10)
        self.assertTrue(got)
        for n in got:
            self.assertIn(n["sells"], ("native_specialist", "seed_or_plug"))

    def test_ships_flag_present(self):
        # At least one mail-order supplier exists (serves Regina/Lumsden/Battleford
        # where local native specialists are sparse).
        self.assertTrue(any(r.get("ships") for r in N.all_nurseries()))

    def test_reseed_wipes_not_duplicates(self):
        # A second init_db (already at current version) must not double the rows.
        before = len(N.all_nurseries())
        init_db()
        self.assertEqual(len(N.all_nurseries()), before)


if __name__ == "__main__":
    unittest.main()

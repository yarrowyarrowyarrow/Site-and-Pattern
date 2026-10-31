"""
tests/test_community_regions.py — the ecoregions a community belongs in (V3.14).

The owner: "For plant communities there are none for aspen parkland or most of
the ecoregions." The habitat facet read a column that names Aspen Parkland on no
plant; it now reads the occurrence ranges, and a community belongs in an
ecoregion when every member with a known range has been recorded there.
"""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.community_regions import (                              # noqa: E402
    MIXED, UNRECORDED, community_regions, matches,
)


def _m(pid, eco=""):
    return {"plant_id": pid, "eco": eco}


class TestTheRule(unittest.TestCase):

    RANGES = {
        1: {"aspen_parkland": 40, "boreal_transition": 9},
        2: {"aspen_parkland": 12, "boreal_transition": 30,
            "mixed_grassland": 5},
        3: {"mixed_grassland": 20},
    }

    def test_every_member_recorded_there_strongest_first(self):
        self.assertEqual(community_regions([_m(1), _m(2)], self.RANGES),
                         ["aspen_parkland", "boreal_transition"])

    def test_one_member_never_recorded_there_keeps_it_out(self):
        self.assertNotIn("boreal_transition",
                         community_regions([_m(2), _m(3)], self.RANGES))
        self.assertEqual(community_regions([_m(2), _m(3)], self.RANGES),
                         ["mixed_grassland"])

    def test_a_member_with_no_known_range_counts_neither_way(self):
        """Absent is not "not there" (P9)."""
        self.assertEqual(community_regions([_m(1), _m(99)], self.RANGES),
                         ["aspen_parkland", "boreal_transition"])

    def test_no_shared_region_reads_mixed_not_generalist(self):
        self.assertEqual(community_regions([_m(1), _m(3)], self.RANGES),
                         [MIXED])

    def test_nothing_known_reads_not_recorded(self):
        self.assertEqual(community_regions([_m(98), _m(99)], {}), [UNRECORDED])

    def test_a_member_without_ranges_falls_back_to_its_column(self):
        """As ``search_plants`` does, so the two filters agree on a plant;
        an ecozone tag is not an ecoregion and says nothing here."""
        self.assertEqual(
            community_regions([_m(1), _m(50, "mixed_grassland,zone_prairies")],
                              self.RANGES), [MIXED])
        self.assertEqual(
            community_regions([_m(1), _m(51, "zone_prairies")], self.RANGES),
            ["aspen_parkland", "boreal_transition"])

    def test_wet_ground_comes_from_any_member_after_the_places(self):
        got = community_regions(
            [_m(1, "riparian"), _m(2, "wet_meadow,riparian")], self.RANGES)
        self.assertEqual(got, ["aspen_parkland", "boreal_transition",
                               "riparian", "wet_meadow"])


class TestMatchingAlongTheTree(unittest.TestCase):

    def test_an_ecozone_finds_its_ecoregions(self):
        from src.ecoregion_tree import ecozones, regions_in
        zone = next(z for z, _n in ecozones()
                    if "aspen_parkland" in {k for k, _r in regions_in(z)})
        self.assertTrue(matches(["aspen_parkland"], [zone]))

    def test_a_subregion_finds_the_ecoregion_it_lies_in(self):
        from src.ecoregion_tree import subregions_in
        sub = subregions_in("aspen_parkland")[0][0]
        self.assertTrue(matches(["aspen_parkland"], [sub]))

    def test_another_region_does_not(self):
        self.assertFalse(matches(["aspen_parkland"], ["mixed_grassland"]))
        self.assertFalse(matches([MIXED], ["aspen_parkland"]))

    def test_niches_and_fallbacks_match_themselves(self):
        self.assertTrue(matches(["aspen_parkland", "riparian"], ["riparian"]))
        self.assertTrue(matches([MIXED], [MIXED]))


class TestTheShippedLibrary(unittest.TestCase):
    """On the seeded communities and the shipped ranges."""

    @classmethod
    def setUpClass(cls):
        import src.db.plants as plants
        cls._saved = (plants._DATA_DIR, plants._DB_PATH)
        cls._dir = tempfile.mkdtemp(prefix="community_regions_")
        plants._DATA_DIR = cls._dir
        plants._DB_PATH = os.path.join(cls._dir, "t.db")
        plants.init_db()
        from src.db import polycultures
        cls.index = polycultures.get_library_index()
        cls.top = {cid: e for cid, e in cls.index.items()
                   if e["parent_id"] is None}

    @classmethod
    def tearDownClass(cls):
        import src.db.plants as plants
        plants._DATA_DIR, plants._DB_PATH = cls._saved

    def test_aspen_parkland_has_communities(self):
        """The owner's report: none did."""
        n = sum("Aspen Parkland" in e["facets"]["habitat"]
                for e in self.top.values())
        self.assertGreaterEqual(n, 20)

    def test_most_places_people_garden_have_some(self):
        from src.ecoregion import geographic_keys
        filed = {k for e in self.top.values() for k in e["regions"]}
        self.assertGreaterEqual(len(filed & set(geographic_keys())), 10)

    def test_every_member_of_an_aspen_parkland_community_is_recorded_there(self):
        import src.db.plants as plants
        from src.community_regions import ranges_by_plant
        conn = plants.get_connection()
        try:
            ranges = ranges_by_plant(conn)
            for cid, entry in self.top.items():
                if "aspen_parkland" not in entry["regions"]:
                    continue
                for (pid,) in conn.execute(
                        "SELECT plant_id FROM polyculture_members "
                        "WHERE polyculture_id = ?", (cid,)):
                    if pid in ranges:
                        self.assertIn("aspen_parkland", ranges[pid],
                                      f"{entry['name']}: plant {pid}")
        finally:
            conn.close()

    def test_labels_and_keys_agree(self):
        for entry in self.top.values():
            self.assertEqual(len(entry["regions"]),
                             len(entry["facets"]["habitat"]), entry["name"])
            self.assertNotIn("Generalist", entry["facets"]["habitat"])

    def test_the_filter_finds_them_by_ecozone(self):
        from src.db import polycultures
        by_region = polycultures.filter_library(self.index,
                                                regions=["aspen_parkland"])
        by_zone = polycultures.filter_library(self.index,
                                              regions=["zone_prairies"])
        self.assertTrue(by_region)
        self.assertLessEqual(set(by_region), set(by_zone))

    @unittest.skipUnless(
        __import__("importlib").util.find_spec("PyQt6") is not None,
        "the Site panel imports PyQt6")
    def test_the_site_tabs_link_has_something_to_browse(self):
        """It compared a list with a set from V2.37 and so never showed."""
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        try:
            from src.site_panel import SitePanel
        except ImportError as exc:                            # noqa: BLE001
            self.skipTest(str(exc))
        self.assertGreater(
            SitePanel._count_reference_communities(["aspen_parkland"]), 0)


if __name__ == "__main__":
    unittest.main()

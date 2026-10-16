"""
tests/test_plant_priority.py — which plants lead (PR-1, V3.26;
docs/homeowner/05-plants-that-lead.md, with the owner's L1 to L10).
"""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_TMP_DIR = tempfile.mkdtemp(prefix="permadesign_priority_test_")
import src.db.plants as _plants_mod  # noqa: E402
_plants_mod._DATA_DIR = _TMP_DIR
_plants_mod._DB_PATH = os.path.join(_TMP_DIR, "permadesign_test.db")

from src import plant_priority as pp  # noqa: E402


def _row(**kw):
    base = {"id": 1, "common_name": "Test Plant", "scientific_name": "Testus one",
            "plant_type": "wildflower", "bloom_period": "Jun-Jul",
            "water_needs": "low,medium", "permaculture_uses": ""}
    base.update(kw)
    return base


class TheParts(unittest.TestCase):
    """Every part's thresholds, from synthetic rows."""

    def _impact(self, rec, **kw):
        return pp.assess(_row(**kw), {1: rec}).parts

    def test_caterpillar_steps_and_the_keystone_floor(self):
        for n, pts in ((0, 0), (1, 1), (3, 2), (6, 3), (13, 4)):
            rec = pp.Record(lep=set(range(n)))
            self.assertEqual(self._impact(rec)["caterpillars"], pts, n)
        self.assertEqual(self._impact(pp.Record(), scientific_name="Salix x")
                         ["caterpillars"], 4, "woody keystone")
        self.assertEqual(self._impact(pp.Record(), scientific_name="Solidago x")
                         ["caterpillars"], 3, "herbaceous keystone")

    def test_bees_birds_specialist_season(self):
        rec = pp.Record(bees=set(range(15)), birds=set(range(5)),
                        specialist=["Snowberry Clearwing"])
        parts = self._impact(rec, bloom_period="Apr-May")
        self.assertEqual((parts["bees"], parts["birds"], parts["specialist"],
                          parts["season"]), (2, 2, 1, 1))
        grass = self._impact(pp.Record(), plant_type="grass",
                             bloom_period="May")
        self.assertEqual(grass["season"], 0, "wind-pollinated")

    def test_a_hummingbird_is_nectar_not_berries(self):
        a = pp.assess(_row(), {1: pp.Record(nectar_birds={1})})
        self.assertIn("Nectar for hummingbirds", a.reasons)
        self.assertFalse(any("Berries" in r for r in a.reasons))


class TheWords(unittest.TestCase):

    def test_nothing_recorded_says_little_recorded_never_low(self):
        a = pp.assess(_row(), {})
        self.assertEqual(a.reasons, ["Little is recorded yet about what it "
                                     "feeds"])
        self.assertEqual(a.band, pp.LITTLE)

    def test_blank_spread_says_nothing(self):
        """L5: nothing about spreading until it is checked."""
        a = pp.assess(_row(spread_habit=""), {})
        self.assertFalse(any("pread" in c or "checked" in c for c in a.cautions))
        b = pp.assess(_row(spread_habit="aggressive_rhizomatous"), {})
        self.assertIn("Spreads by runners or suckers: give it room or an edge",
                      b.cautions)

    def test_no_size_words_without_a_measured_yard(self):
        """L3: a tree is too big only against a measured area."""
        tree = _row(plant_type="tree", mature_height_meters=20,
                    mature_canopy_m=12)
        self.assertFalse(any("too big" in c for c in pp.assess(tree, {}).cautions))
        small = pp.assess(tree, {}, area_m2=180).cautions
        self.assertIn("Grows to 20 m tall: too big for a yard this size", small)
        self.assertFalse(any("too big" in c for c in
                             pp.assess(tree, {}, area_m2=20000).cautions))

    def test_no_underscores_or_notes(self):
        a = pp.assess(_row(notes="Traditional cold/flu remedy",
                           spread_habit="self_seeding",
                           permaculture_uses="bird_food"),
                      {1: pp.Record(lep={1}, bees=set(range(6)))})
        for text in a.reasons + a.cautions:
            self.assertNotIn("_", text)
            self.assertNotIn("remedy", text)


class OnTheShippedCatalogue(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        _plants_mod._DATA_DIR = _TMP_DIR
        _plants_mod._DB_PATH = os.path.join(_TMP_DIR, "permadesign_test.db")
        _plants_mod.init_db()
        from src import native_here
        cls.rows = _plants_mod.get_all_plants()
        cls.records = pp.load_records()
        names = native_here.native_names("edmonton")
        cls.edmonton = [r for r in cls.rows if r["scientific_name"] in names]
        cls.ranked = pp.rank(cls.edmonton, records=cls.records,
                             place="edmonton")

    def test_rank_never_drops_a_row(self):
        self.assertEqual(len(self.ranked), len(self.edmonton))
        self.assertEqual({r["id"] for r in self.ranked},
                         {r["id"] for r in self.edmonton})

    def test_about_forty_top_picks(self):
        counts = pp.band_counts(self.edmonton, records=self.records,
                                place="edmonton")
        self.assertTrue(30 <= counts[pp.TOP] <= 45, counts)

    def test_chokecherry_leads_with_its_cautions(self):
        """L4."""
        first = self.ranked[0]
        self.assertEqual(first["common_name"], "Chokecherry")
        a = pp.assess(first, self.records, place="edmonton")
        self.assertIn("Poisonous to pets if eaten", a.cautions)

    def test_the_top_forty(self):
        """No standing-water plant and no restoration plant no seller lists
        among the first 40; the plan's four shrubs and asters among the first
        40; every pond plant in the pond band."""
        from src import local_stock, zoning
        top = self.ranked[:40]
        for r in top:
            self.assertFalse(zoning.needs_standing_water(r), r["common_name"])
            self.assertNotEqual(local_stock.tier(r["scientific_name"]), "hard",
                                r["common_name"])
        names = [r["common_name"] for r in top]
        for n in ("Chokecherry", "Saskatoon Berry", "Red Osier Dogwood",
                  "Smooth Aster"):
            self.assertIn(n, names)
        for r in self.edmonton:
            if zoning.needs_standing_water(r):
                self.assertEqual(pp.assess(r, self.records,
                                           place="edmonton").band, pp.POND)

    def test_a_plant_off_the_local_list_goes_last(self):
        everything = pp.rank(self.rows, records=self.records, place="edmonton")
        first_away = next(i for i, r in enumerate(everything)
                          if pp.assess(r, self.records,
                                       place="edmonton").band == pp.AWAY)
        self.assertEqual(first_away, len(self.edmonton))

    def test_the_first_screen_looks_like_a_garden(self):
        """PR-3, §5: per ten rows four flowers, three shrubs or trees, two
        grasses or sedges, one groundcover or vine; nothing lost."""
        mixed = pp.interleave(self.ranked, place="edmonton")
        self.assertEqual(sorted(r["id"] for r in mixed),
                         sorted(r["id"] for r in self.ranked))
        layers = "".join(pp._LAYER.get(r["plant_type"], "?")
                         for r in mixed[:20])
        self.assertEqual(layers, pp._PATTERN * 2)
        self.assertEqual(mixed[0]["common_name"], "Joe-Pye Weed")
        for r in mixed[:20]:
            self.assertNotIn(pp.assess(r, self.records, place="edmonton").band,
                             (pp.POND, pp.AWAY), r["common_name"])
        shrubs = [r for r in mixed[:20] if r["plant_type"] == "shrub"]
        self.assertEqual(shrubs[0]["common_name"], "Chokecherry")

    def test_fast(self):
        import time
        t = time.perf_counter()
        for r in self.rows:
            pp.assess(r, self.records, place="edmonton")
        self.assertLess(time.perf_counter() - t, 0.3)


class TheCommunityLibrary(unittest.TestCase):
    """PR-9: Best picks first, a community with a member off the local list
    after every one without."""

    def test_best_picks_first(self):
        from unittest import mock
        from src.db.polycultures import sort_community_ids
        index = {
            1: {"name": "A low one", "member_ids": [10], "not_around": {}},
            2: {"name": "B high one", "member_ids": [11, 12],
                "not_around": {}},
            3: {"name": "C high but off the list", "member_ids": [11],
                "not_around": {"edmonton": ["Canada Goldenrod"]}},
        }
        with mock.patch.object(pp, "impact_by_id",
                               return_value={10: 1, 11: 9, 12: 7}):
            self.assertEqual(sort_community_ids(index, [1, 2, 3], "best",
                                                place="edmonton"), [2, 1, 3])

    def test_it_is_the_default(self):
        from src import polyculture_panel
        self.assertEqual(polyculture_panel._SORT_BY_OPTIONS[0][0], "best")


class TheRegionsDefaults(unittest.TestCase):
    """ED-10: the pack's first-run goals and its local list on."""

    def test_the_pack_says_so(self):
        from src import region
        d = region.default().defaults
        self.assertTrue(d["local_natives_only"])
        self.assertIn("local_native", d["first_run_goals"])


class TheGeneratorFollows(unittest.TestCase):
    """PR-6: the offline pool is ranked as the plant list is."""

    def test_an_edmonton_pin_picks_from_the_edmonton_list_first(self):
        _plants_mod._DATA_DIR = _TMP_DIR
        _plants_mod._DB_PATH = os.path.join(_TMP_DIR, "permadesign_test.db")
        _plants_mod.init_db()
        from src import native_here, zoning
        from src.llm_design import _rank_offline_plants
        pool = _plants_mod.search_plants(native_province="AB")
        ranked = _rank_offline_plants(pool, site=(53.5461, -113.4938))
        names = native_here.native_names("edmonton")
        first = ranked[:14]
        self.assertTrue(all(r["scientific_name"] in names for r in first),
                        [r["common_name"] for r in first])
        self.assertFalse(any(zoning.needs_standing_water(r) for r in first))


if __name__ == "__main__":
    unittest.main()

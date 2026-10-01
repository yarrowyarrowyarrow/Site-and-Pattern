"""
tests/test_plant_filters.py — the one filter vocabulary (F192, V3.00).

Qt-free. The rows for the order tests are written here, so a change to the
catalogue cannot move them; the two tests that need the catalogue redirect the
database to a temp directory, as every DB-touching module in this suite does.
"""

import inspect
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import plant_filters as pf  # noqa: E402

_TMP = tempfile.mkdtemp(prefix="sp_filters_")
import src.db.plants as _plants  # noqa: E402
_plants._DATA_DIR = _TMP
_plants._DB_PATH = os.path.join(_TMP, "permadesign_test.db")


def tearDownModule():
    shutil.rmtree(_TMP, ignore_errors=True)


class TestTheVocabulary(unittest.TestCase):

    def test_every_parameter_is_a_real_search_parameter(self):
        """A typo here is a filter that silently does nothing."""
        from src.db.plants import search_plants
        real = set(inspect.signature(search_plants).parameters)
        self.assertEqual(pf.facet_params() - real, set())

    def test_nine_facets_and_nine_qualities(self):
        self.assertEqual(len(pf.FACETS), 9)
        self.assertEqual(len(pf.QUALITIES), 9)
        self.assertEqual(len({f.key for f in pf.FACETS}
                             | {q.key for q in pf.QUALITIES}), 18)

    def test_each_facet_says_how_its_values_combine(self):
        """Role is all-of in the query (one EXISTS per tag); everything else
        any-of. The summary says so in words, so it has to be recorded."""
        combine = {f.key: f.combine for f in pf.FACETS}
        self.assertEqual(combine.pop("use"), "all")
        self.assertEqual(set(combine.values()), {"any"})

    def test_every_facet_and_quality_explains_itself(self):
        for f in pf.FACETS:
            self.assertTrue(f.tip.strip(), f.key)
            self.assertTrue(f.placeholder.strip(), f.key)
        for q in pf.QUALITIES:
            self.assertTrue(q.tip.strip(), q.key)


class TestCriteria(unittest.TestCase):

    def test_an_untouched_facet_is_absent_not_empty(self):
        kw = pf.criteria_to_kwargs({"type": [], "sun": ["full_sun"],
                                    "edible_only": False})
        self.assertEqual(kw, {"sun_req": ["full_sun"]})

    def test_months_become_numbers(self):
        kw = pf.criteria_to_kwargs({"bloom_months": ["6", "7"],
                                    "fruit_months": ["9"]})
        self.assertEqual(kw["bloom_months"], [6, 7])
        self.assertEqual(kw["fruit_months"], [9])

    def test_a_region_is_expanded_along_its_lineage(self):
        """Ticking a region must also match plants only ever tagged at its
        ecozone, and the subregions inside it (src/ecoregion_tree.py)."""
        kw = pf.criteria_to_kwargs({"ecoregion": ["aspen_parkland"]})
        self.assertIn("aspen_parkland", kw["ecoregion"])
        self.assertGreater(len(kw["ecoregion"]), 1)

    def test_native_reads_the_province_list(self):
        kw = pf.criteria_to_kwargs({"native_only": True})
        self.assertEqual(kw, {"native_province": "AB"})


class TestTheSummary(unittest.TestCase):

    def test_nothing_on_says_nothing(self):
        self.assertEqual(pf.summary({}), [])
        self.assertFalse(pf.active({"query": "aster"}))

    def test_any_reads_or_and_all_reads_and(self):
        bits = pf.summary({"type": ["shrub", "tree"],
                           "use": ["pollinator", "bird_food"]})
        self.assertIn("Type: Shrub or Tree", bits)
        self.assertIn("Role: Pollinator Support and Bird Food", bits)

    def test_many_values_are_counted_not_listed(self):
        bits = pf.summary({"colour": ["white", "yellow", "purple"]})
        self.assertEqual(len(bits), 1)
        self.assertTrue(bits[0].endswith("+1"), bits)

    def test_a_region_is_named_once_by_its_outermost_tick(self):
        """Ticking an ecozone ticks everything inside it; the line names the
        ecozone, not thirty of its regions."""
        from src.ecoregion_tree import descendants_of, ecozones
        zone, name = ecozones()[0]
        keys = [zone] + sorted(descendants_of(zone))
        self.assertEqual(pf.summary({"ecoregion": keys}),
                         [f"Restoring toward {name}"])

    def test_qualities_are_named(self):
        self.assertEqual(pf.summary({"native_only": True, "pet_safe_only": True}),
                         ["Native", "Pet safe"])


def _row(name, *, sci="", ptype="wildflower", water="medium", zmin=None,
         height=0, pid=0):
    return {"id": pid, "common_name": name, "scientific_name": sci,
            "plant_type": ptype, "water_needs": water,
            "hardiness_zone_min": zmin, "mature_height_meters": height}


class TestTheOrder(unittest.TestCase):

    def test_name_ignores_case_and_type(self):
        rows = [_row("cattail", ptype="aquatic"), _row("Aster"), _row("Birch")]
        self.assertEqual([r["common_name"] for r in pf.order_plants(rows)],
                         ["Aster", "Birch", "cattail"])

    def test_an_unknown_key_falls_back_to_name(self):
        rows = [_row("B"), _row("A")]
        self.assertEqual([r["common_name"]
                          for r in pf.order_plants(rows, "nonsense")], ["A", "B"])

    def test_suits_puts_standing_water_last_without_hiding_it(self):
        rows = [_row("Arrowhead", ptype="aquatic"), _row("Yarrow"),
                _row("Buckbean", water="high")]
        out = [r["common_name"] for r in pf.order_plants(rows, "suits")]
        self.assertEqual(out, ["Yarrow", "Arrowhead", "Buckbean"])

    def test_suits_prefers_records_near_the_site(self):
        from unittest import mock
        rows = [_row("Far", sci="Farus"), _row("Near", sci="Nearus")]
        rank = {"Farus": 0, "Nearus": 2}
        with mock.patch("src.site_fit.locality_rank",
                        lambda sci, lat, lng: rank[sci]):
            out = pf.order_plants(rows, "suits", site=(53.5, -113.5))
        self.assertEqual([r["common_name"] for r in out], ["Near", "Far"])

    def test_suits_puts_plants_not_hardy_at_the_zone_below(self):
        rows = [_row("Tender", zmin="5"), _row("Hardy", zmin="2"),
                _row("Unknown")]
        out = [r["common_name"] for r in pf.order_plants(rows, "suits", zone=3)]
        self.assertEqual(out, ["Hardy", "Unknown", "Tender"])

    def test_a_hedged_zone_is_read_not_dropped(self):
        """'4?' is a botanist's 'about 4, not verified' (P9)."""
        self.assertFalse(pf.hardy_at({"hardiness_zone_min": "4?"}, 3))
        self.assertTrue(pf.hardy_at({"hardiness_zone_min": "4?"}, 4))
        self.assertTrue(pf.hardy_at({"hardiness_zone_min": None}, 2))
        self.assertTrue(pf.hardy_at({"hardiness_zone_min": "3"}, None))

    def test_animals_supported_counts_what_it_is_given(self):
        rows = [_row("Few", pid=1), _row("Many", pid=2), _row("None", pid=3)]
        out = pf.order_plants(rows, "wildlife", wildlife_counts={1: 3, 2: 30})
        self.assertEqual([r["common_name"] for r in out], ["Many", "Few", "None"])

    def test_height_is_tallest_first(self):
        rows = [_row("Low", height=0.3), _row("Tall", height=12),
                _row("Blank")]
        self.assertEqual([r["common_name"]
                          for r in pf.order_plants(rows, "height")],
                         ["Tall", "Low", "Blank"])

    def test_a_hint_lifts_matches_whatever_the_order(self):
        rows = [_row("Aster"), _row("Willow", ptype="shrub"), _row("Birch")]
        out = pf.order_plants(rows, "name",
                              hint=lambda r: r["plant_type"] == "shrub")
        self.assertEqual([r["common_name"] for r in out],
                         ["Willow", "Aster", "Birch"])


class TestAgainstTheCatalogue(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        _plants.init_db()

    def test_native_includes_the_five_the_flag_left_out(self):
        """Five species carry the seed's '1?' in native_to_alberta, and the
        flag's filter dropped them although VASCAN records every one in
        Alberta and the list's AB badge said native."""
        from src.db.plants import search_plants
        flagged = {r["id"] for r in search_plants(native_only=True)}
        sourced = {r["id"] for r in search_plants(
            **pf.criteria_to_kwargs({"native_only": True}))}
        self.assertTrue(flagged <= sourced)
        extra = {r["common_name"] for r in search_plants()
                 if r["id"] in sourced - flagged}
        self.assertIn("Tall Anemone (Thimbleweed)", extra)
        self.assertLessEqual(len(extra), 5)

    def test_animals_are_counted_distinct(self):
        """Distinct animals, not relationship rows: one bee can take nectar
        and pollen."""
        from src.db.plants import get_connection
        counts = pf.animals_per_plant()
        conn = get_connection()
        try:
            rows = dict(conn.execute(
                "SELECT plant_id, COUNT(*) FROM plant_fauna GROUP BY plant_id"))
        finally:
            conn.close()
        self.assertTrue(counts)
        self.assertTrue(all(counts[pid] <= rows[pid] for pid in counts))
        self.assertTrue(any(counts[pid] < rows[pid] for pid in counts))


if __name__ == "__main__":
    unittest.main()

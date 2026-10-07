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

    def test_nine_facets_and_ten_qualities(self):
        # Ten since V3.12: Edmonton native (F220) beside Native.
        self.assertEqual(len(pf.FACETS), 9)
        self.assertEqual(len(pf.QUALITIES), 10)
        self.assertEqual(len({f.key for f in pf.FACETS}
                             | {q.key for q in pf.QUALITIES}), 19)

    def test_edmonton_native_asks_for_the_edmonton_list(self):
        """F220: the quality reaches search_plants as native_near, alongside
        the pin's province rather than instead of it."""
        kwargs = pf.criteria_to_kwargs(
            {"edmonton_native": True, "native_only": True}, "AB")
        self.assertEqual(kwargs, {"native_province": "AB",
                                  "native_near": "edmonton"})
        self.assertIn("Edmonton native", pf.summary({"edmonton_native": True}))

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
        # In the dropdown's order, whatever order they were ticked in.
        self.assertIn("Type: Tree or Shrub", bits)
        self.assertIn("Role: Pollinator Support and Bird Food", bits)

    def test_many_values_name_two_and_count_the_rest_by_the_rule(self):
        """Until V3.01 a box read "3 selected": a count, with the rule gone."""
        bits = pf.summary({"colour": ["white", "yellow", "purple"]})
        self.assertEqual(len(bits), 1)
        self.assertTrue(bits[0].endswith(" or 1 more"), bits)
        role = pf.facet("use")
        self.assertTrue(pf.phrase(role, ["bird_food", "host_plant",
                                         "pollinator", "aquatic"])
                        .endswith(" and 2 more"))

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


class TestTheFace(unittest.TestCase):
    """What a dropdown reads once something is ticked (F194, V3.01). Until then
    it read "Shrub", and with the placeholder gone so was the word "Type"."""

    def test_the_dimension_comes_first(self):
        self.assertEqual(pf.face(pf.facet("type"), ["shrub"]), "Type: Shrub")
        self.assertEqual(pf.face(pf.facet("bloom_months"), ["6", "7"]),
                         "Blooms in: June or July")

    def test_restoring_toward_reads_on_into_its_value(self):
        self.assertEqual(pf.face(pf.facet("ecoregion"), ["aspen_parkland"]),
                         "Restoring toward Aspen Parkland")

    def test_nothing_ticked_is_no_face_so_the_placeholder_shows(self):
        for f in pf.FACETS:
            self.assertEqual(pf.face(f, []), "", f.key)
            self.assertEqual(pf.face(f, None), "", f.key)

    def test_values_are_named_in_the_facets_order_however_they_arrived(self):
        """The dropdown reads top to bottom; a chip naming the same values in
        another order looked like another filter."""
        role = pf.facet("use")
        self.assertEqual(pf.face(role, ["bird_food", "host_plant"]),
                         pf.face(role, ["host_plant", "bird_food"]))

    def test_the_face_and_the_chip_are_the_same_words(self):
        criteria = {"type": ["tree", "shrub"], "use": ["bird_food"]}
        self.assertEqual(pf.summary(criteria),
                         [pf.face(pf.facet("type"), criteria["type"]),
                          pf.face(pf.facet("use"), criteria["use"])])


class TestTheRule(unittest.TestCase):

    def test_role_says_every_one_and_the_rest_say_one(self):
        """Role keeps plants with every role ticked; every other facet keeps
        plants with any value ticked. Only a tooltip said so before V3.01."""
        for f in pf.FACETS:
            rule = pf.rule(f)
            self.assertTrue(rule.startswith("Tick boxes to choose several."), f.key)
            if f.combine == "all":
                self.assertTrue(rule.endswith("needs every one."), f.key)
            else:
                self.assertTrue(rule.endswith("needs one."), f.key)
        self.assertEqual(pf.facet("use").combine, "all")


class TestWhatIsOn(unittest.TestCase):

    CRITERIA = {"type": ["fern"], "bloom_months": ["1"], "native_only": True,
                "edible_only": False, "query": " aster "}

    def test_each_restriction_in_the_order_it_is_drawn_search_last(self):
        self.assertEqual(pf.filters_on(self.CRITERIA), [
            ("type", "Type: Fern"), ("bloom_months", "Blooms in: January"),
            ("native_only", "Native"), ("query", "aster")])

    def test_without_takes_off_one_and_leaves_the_rest(self):
        for key, _words in pf.filters_on(self.CRITERIA):
            rest = pf.without(self.CRITERIA, key)
            self.assertNotIn(key, dict(pf.filters_on(rest)), key)
            self.assertEqual(len(pf.filters_on(rest)),
                             len(pf.filters_on(self.CRITERIA)) - 1, key)
        self.assertEqual(self.CRITERIA["type"], ["fern"], "the original moved")

    def test_without_a_facet_matches_like_nothing_was_ticked(self):
        rest = pf.without(self.CRITERIA, "type")
        self.assertNotIn("plant_type", pf.criteria_to_kwargs(rest))

    def test_nothing_on_is_an_empty_list(self):
        self.assertEqual(pf.filters_on({}), [])
        self.assertEqual(pf.filters_on({"query": "  "}), [])


class TestWhatEmptied(unittest.TestCase):
    """Which restriction emptied a result, answered without a display."""

    def _count(self, rule):
        calls = []

        def count(criteria, soil_on):
            calls.append((dict(criteria), soil_on))
            return rule(criteria, soil_on)
        return count, calls

    def test_only_removals_that_bring_plants_back_are_offered_most_first(self):
        criteria = {"type": ["fern"], "bloom_months": ["1"], "query": "x"}

        def rule(c, _soil):
            # Ferns never bloom; the search alone matches 3; ferns alone 1.
            if c.get("type") and c.get("bloom_months"):
                return 0
            return 3 if not c.get("type") else 1
        count, _calls = self._count(rule)
        on, options = pf.what_emptied(criteria, count)
        self.assertEqual([k for k, _w in on], ["type", "bloom_months", "query"])
        self.assertEqual(options, [(3, "type", "Type: Fern"),
                                   (1, "bloom_months", "Blooms in: January")])

    def test_the_soil_is_removed_by_searching_without_it(self):
        count, calls = self._count(lambda c, soil: 0 if soil else 5)
        on, options = pf.what_emptied({"native_only": True}, count,
                                      soil="Your soil: pH 8.0")
        self.assertEqual(on[-1], ("soil", "Your soil: pH 8.0"))
        self.assertEqual(options, [(5, "soil", "Your soil: pH 8.0")])
        # Every other removal still searched with the soil on.
        others = [soil for c, soil in calls if c.get("native_only") is False]
        self.assertEqual(others, [True])

    def test_a_search_that_fails_is_not_offered(self):
        def count(_c, _s):
            raise RuntimeError("no database")
        self.assertEqual(pf.what_emptied({"edible_only": True}, count)[1], [])


class TestTheSoilWords(unittest.TestCase):

    def test_the_label_says_whose_it_is(self):
        self.assertEqual(pf.soil_label(7.84), "Your soil: pH 7.8")

    def test_the_tip_says_what_the_comparison_rests_on(self):
        from src.db.plants import _SOIL_PH_TOLERANCE
        tip = pf.soil_tip(8.0, 105)
        self.assertIn("estimate for the area", tip)
        self.assertIn(f"{_SOIL_PH_TOLERANCE:g}", tip)
        self.assertIn("hiding 105 plants", tip)
        self.assertNotIn("hiding", pf.soil_tip(8.0, 0))
        self.assertIn("hiding 1 plant ", pf.soil_tip(8.0, 1))


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
        """Five species carried the seed's '1?' in native_to_alberta, and the
        flag's filter dropped them although VASCAN records every one in
        Alberta and the list's AB badge said native. V3.00 moved the pickers
        to VASCAN's provinces; V3.05 (F199) set the five flags to 1, so the
        generator's native-only filter, which reads the flag, agrees too."""
        from src.db.plants import search_plants
        flagged = {r["id"] for r in search_plants(native_only=True)}
        sourced = {r["id"] for r in search_plants(
            **pf.criteria_to_kwargs({"native_only": True}))}
        self.assertTrue(flagged <= sourced)
        names = {r["id"]: r["common_name"] for r in search_plants()}
        for name in ("Tall Anemone (Thimbleweed)", "False Box (Mountain Boxwood)",
                     "Flat-topped White Aster", "Round-leaved Alumroot",
                     "Stiff Sunflower (Rhombic-leaved Sunflower)"):
            self.assertIn(name, {names[i] for i in flagged})

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



class TestNativeTakesTheProvince(unittest.TestCase):
    """F200 (V3.05): Native filters to the pin's province."""

    def test_the_province_reaches_the_search(self):
        on = {"native_only": True}
        self.assertEqual(pf.criteria_to_kwargs(on, "SK"),
                         {"native_province": "SK"})
        self.assertEqual(pf.criteria_to_kwargs(on, "AB"),
                         {"native_province": "AB"})

    def test_no_pin_or_an_unknown_one_keeps_alberta(self):
        on = {"native_only": True}
        self.assertEqual(pf.criteria_to_kwargs(on), {"native_province": "AB"})
        self.assertEqual(pf.criteria_to_kwargs(on, "BC"),
                         {"native_province": "AB"})

    def test_native_in_reads_vascan_then_the_flag(self):
        self.assertTrue(pf.native_in({"native_provinces": "AB,SK"}, "SK"))
        self.assertFalse(pf.native_in({"native_provinces": "AB"}, "SK"))
        self.assertTrue(pf.native_in({"native_to_alberta": 1}, "AB"))
        self.assertFalse(pf.native_in({"native_to_alberta": 1}, "SK"))

if __name__ == "__main__":
    unittest.main()

"""
tests/test_local_flora.py — native around Edmonton (F220, V3.12).

The owner asked for "Edmonton specific native plants", narrower than VASCAN's
"native to Alberta", which is 415 of 424 species and takes in the mountains and
the dry south. These pin the rule on a synthetic cache first (each clause, and
the traps it exists for), then the shipped list against its inputs and the
species whose answer is known, then the sentences every page prints.
"""

import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import local_flora as lf  # noqa: E402
from src import native_here as nh  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EDMONTON = lf.PLACES["edmonton"]
BASIS = ["HUMAN_OBSERVATION", "PRESERVED_SPECIMEN", "OCCURRENCE"]
OBS, SPEC = 0, 1


def _at(km_north: float, *, unc=None, year=2000, basis=SPEC):
    """A cache row ``km_north`` kilometres north of downtown Edmonton."""
    lat0, lng0 = EDMONTON["centre"]
    return [lat0 + km_north / 111.32, lng0, unc, year, basis, 0]


def _row(name, provinces="AB,SK"):
    return {"scientific_name": name, "native_provinces": provinces,
            "native_provinces_source": "flora"}


class TestWhatCounts(unittest.TestCase):

    def test_a_record_counts_only_when_its_whole_circle_is_inside(self):
        # A sheet labelled "Edmonton" with a coarse radius is good evidence for
        # a 50 km question: the range map's 10 km cut threw out pin cherry's.
        self.assertTrue(lf.inside(*_at(1)[:3], EDMONTON))
        self.assertTrue(lf.inside(*_at(1, unc=30000)[:3], EDMONTON))
        self.assertFalse(lf.inside(*_at(45, unc=10000)[:3], EDMONTON))
        self.assertFalse(lf.inside(*_at(51)[:3], EDMONTON))

    def test_one_gathering_split_between_herbaria_counts_once(self):
        sheets = [_at(5, year=1950), _at(5, year=1950), _at(5, year=1950)]
        self.assertEqual(lf.tally(sheets, BASIS, EDMONTON)["collections"], 1)
        two_years = [_at(5, year=1950), _at(5, year=1951)]
        self.assertEqual(lf.tally(two_years, BASIS, EDMONTON)["collections"], 2)

    def test_observations_are_carried_and_never_counted(self):
        # The bur oak lesson: a city's photographs include its planted trees.
        seen = [_at(3, basis=OBS)] * 119
        ev = lf.tally(seen, BASIS, EDMONTON)
        self.assertEqual((ev["collections"], ev["observations"]), (0, 119))
        self.assertEqual(lf.tier_for(True, True, 0, 119), "observed")

    def test_the_floor_is_the_ecoregion_ranges_floor(self):
        from src.ecoregion_ranges import MIN_RECORDS
        self.assertEqual(lf.MIN_COLLECTIONS, MIN_RECORDS)
        self.assertEqual(lf.tier_for(True, True, 2, 0), "thin")
        self.assertEqual(lf.tier_for(True, True, 3, 0), "documented")

    def test_unrecorded_and_no_data_are_different_claims(self):
        far = lf.tally([_at(160)], BASIS, EDMONTON)
        self.assertEqual(far["nearest_km"], 160)
        self.assertEqual(lf.tier_for(True, True, 0, 0), "unrecorded")
        self.assertEqual(lf.tier_for(True, False, 0, 0), "no_data")


class TestTheVascanGate(unittest.TestCase):

    def test_specimens_cannot_make_a_province_non_native_local(self):
        # Bur Oak: three herbarium collections within 50 km (1935-1952) and
        # VASCAN records it introduced in Alberta.
        cache = {"basis": BASIS, "generated": "2026-01-01",
                 "species": {"Quercus macrocarpa": [
                     _at(4, year=1935), _at(6, year=1941), _at(9, year=1952)]}}
        doc = lf.derive([_row("Quercus macrocarpa", "SK")], cache)
        entry = doc["places"]["edmonton"]["species"]["Quercus macrocarpa"]
        self.assertEqual(entry["collections"], 3)
        self.assertEqual(entry["tier"], "not_in_province")
        self.assertFalse(lf.is_native(entry))

    def test_a_review_cannot_cross_it_either(self):
        species = {"Quercus macrocarpa": _row("Quercus macrocarpa", "SK")}
        with self.assertRaisesRegex(ValueError, "VASCAN"):
            lf.parse_rulings({"places": {"edmonton": {"Quercus macrocarpa": {
                "ruling": "native"}}}}, species)


class TestRulings(unittest.TestCase):

    def setUp(self):
        self.species = {"Prunus pensylvanica": _row("Prunus pensylvanica"),
                        "Acer negundo": _row("Acer negundo")}
        self.cache = {"basis": BASIS, "generated": "2026-01-01", "species": {
            "Prunus pensylvanica": [_at(1, year=1966)],
            "Acer negundo": [_at(2, year=1933), _at(4, year=1960),
                             _at(8, year=2008)]}}

    def _derive(self, rulings):
        parsed = lf.parse_rulings({"places": {"edmonton": rulings}},
                                  self.species)
        doc = lf.derive(self.species.values(), self.cache, parsed)
        return doc["places"]["edmonton"]["species"]

    def test_without_a_ruling_thin_is_out_and_documented_is_in(self):
        out = self._derive({})
        self.assertFalse(lf.is_native(out["Prunus pensylvanica"]))
        self.assertTrue(lf.is_native(out["Acer negundo"]))

    def test_a_ruling_moves_a_species_either_way_and_keeps_the_evidence(self):
        out = self._derive({
            "Prunus pensylvanica": {"ruling": "native", "on": "2026-10-08"},
            "Acer negundo": {"ruling": "not_native"}})
        self.assertTrue(lf.is_native(out["Prunus pensylvanica"]))
        self.assertFalse(lf.is_native(out["Acer negundo"]))
        self.assertEqual(out["Prunus pensylvanica"]["tier"], "thin")
        self.assertEqual(out["Acer negundo"]["collections"], 3)

    def test_a_ruling_is_a_yes_or_a_no_on_a_catalogue_species(self):
        for bad, msg in (
                ({"Prunus pensylvanica": {"ruling": "maybe"}}, "one of"),
                ({"Prunus virginiana": {"ruling": "native"}},
                 "not in the catalogue")):
            with self.subTest(msg), self.assertRaisesRegex(ValueError, msg):
                lf.parse_rulings({"places": {"edmonton": bad}}, self.species)
        with self.assertRaisesRegex(ValueError, "unknown place"):
            lf.parse_rulings({"places": {"calgary": {}}}, self.species)

    def test_no_reason_is_asked_for_or_kept(self):
        """The owner answers yes or no where confident, gives no reasons, and
        asked that none ever be shown: one written into the file by hand is
        dropped before it can reach the list."""
        parsed = lf.parse_rulings({"places": {"edmonton": {
            "Prunus pensylvanica": {"ruling": "native", "on": "2026-10-08",
                                    "reason": "SHOULD NOT SHIP"}}}},
            self.species)
        self.assertEqual(parsed["edmonton"]["Prunus pensylvanica"],
                         {"ruling": "native", "on": "2026-10-08"})
        out = self._derive({"Prunus pensylvanica": {"ruling": "native",
                                                    "reason": "SHOULD NOT SHIP"}})
        self.assertNotIn("SHOULD NOT SHIP", json.dumps(out))


class TestARenameCarriesTheRuling(unittest.TestCase):
    """``rename_taxon.py`` and ``remove_taxon.py`` re-key every file keyed by
    scientific name; a ruling left on a name the catalogue has dropped would
    stop the derivation (``parse_rulings`` refuses it), so they carry it."""

    def setUp(self):
        import pathlib
        import tempfile
        self.path = pathlib.Path(tempfile.mkdtemp()) / "rulings.json"
        self.path.write_text(json.dumps({"version": 1, "places": {"edmonton": {
            "Old name": {"ruling": "native", "on": "2026-10-07"},
            "Kept": {"ruling": "not_native", "on": "2026-10-07"}}}}),
            encoding="utf-8")

    def _rows(self):
        return json.loads(self.path.read_text(encoding="utf-8")
                          )["places"]["edmonton"]

    def test_a_rename_moves_it(self):
        from scripts.derive_local_flora import carry_rulings, rulings_for
        self.assertIn("edmonton", rulings_for("Old name", self.path))
        self.assertEqual(carry_rulings("Old name", "New name", self.path),
                         [("edmonton", "moved to New name")])
        self.assertEqual(sorted(self._rows()), ["Kept", "New name"])

    def test_a_removal_drops_it_and_a_merge_keeps_the_survivors(self):
        from scripts.derive_local_flora import carry_rulings
        carry_rulings("Old name", "Kept", self.path)
        self.assertEqual(self._rows(), {"Kept": {"ruling": "not_native",
                                                 "on": "2026-10-07"}})
        self.assertEqual(carry_rulings("Kept", "", self.path),
                         [("edmonton", "dropped")])
        self.assertEqual(self._rows(), {})

    def test_both_tools_call_it(self):
        for script in ("rename_taxon.py", "remove_taxon.py"):
            with open(os.path.join(ROOT, "scripts", script),
                      encoding="utf-8") as fh:
                self.assertIn("carry_rulings(", fh.read(), script)


class TestAReviewIsFoldedIn(unittest.TestCase):
    """The owner rules on the borderline species on a review page; ``--merge``
    brings the rulings back, from the page's export or from its database rows
    one file each, and never half-applies a review with one bad row in it."""

    def setUp(self):
        import pathlib
        import tempfile
        self.dir = pathlib.Path(tempfile.mkdtemp())
        self.path = self.dir / "rulings.json"
        self.path.write_text(json.dumps({"version": 1, "comment": "kept",
                                         "places": {"edmonton": {
            "Prunus pensylvanica": {"ruling": "not_native",
                                    "on": "2026-10-01"}}}}),
            encoding="utf-8")

    def _doc(self):
        return json.loads(self.path.read_text(encoding="utf-8"))

    def test_rulings_land_replace_and_unsettled_removes(self):
        from scripts.derive_local_flora import merge_rulings
        changes = merge_rulings({"places": {"edmonton": {
            "Prunus pensylvanica": {"ruling": "native", "on": "2026-10-07"},
            "Viburnum opulus": {"ruling": "native", "on": "2026-10-07 "},
            "Linum lewisii": {"ruling": "unsettled", "on": "2026-10-07"},
        }}}, self.path)
        self.assertEqual(changes, [
            ("edmonton", "Prunus pensylvanica", "not_native -> native"),
            ("edmonton", "Viburnum opulus", "native")])
        doc = self._doc()
        self.assertEqual(doc["comment"], "kept")
        self.assertEqual(doc["places"]["edmonton"], {
            "Prunus pensylvanica": {"ruling": "native", "on": "2026-10-07"},
            "Viburnum opulus": {"ruling": "native", "on": "2026-10-07"}})
        self.assertEqual(merge_rulings({"places": {"edmonton": {
            "Viburnum opulus": {"ruling": "unsettled"}}}}, self.path),
            [("edmonton", "Viburnum opulus", "native removed")])
        self.assertEqual(merge_rulings({"places": {"edmonton": {
            "Prunus pensylvanica": {"ruling": "native", "on": "2026-10-07"}}}},
            self.path), [])

    def test_a_reason_in_a_review_is_dropped(self):
        from scripts.derive_local_flora import merge_rulings
        merge_rulings({"places": {"edmonton": {"Viburnum opulus": {
            "ruling": "native", "reason": "SHOULD NOT SHIP"}}}}, self.path)
        self.assertNotIn("SHOULD NOT SHIP",
                         self.path.read_text(encoding="utf-8"))
        self.assertEqual(self._doc()["places"]["edmonton"]["Viburnum opulus"],
                         {"ruling": "native"})

    def test_one_bad_row_writes_nothing(self):
        from scripts.derive_local_flora import merge_rulings
        before = self.path.read_text(encoding="utf-8")
        good = {"Viburnum opulus": {"ruling": "native"}}
        for bad, msg in (
                ({"Quercus macrocarpa": {"ruling": "native"}}, "VASCAN"),
                ({"Nope nope": {"ruling": "native"}}, "not in the catalogue"),
                ({"Fragaria vesca": {"ruling": "maybe"}}, "one of")):
            with self.subTest(msg), self.assertRaisesRegex(ValueError, msg):
                merge_rulings({"places": {"edmonton": dict(good, **bad)}},
                              self.path)
            self.assertEqual(self.path.read_text(encoding="utf-8"), before)

    def test_the_pages_rows_read_as_a_review(self):
        """As ``ArtifactData list`` with ``out_dir`` saves them:
        ``<dir>/rulings/<doc id>.json``, the page's fields and no wrapper."""
        from scripts.derive_local_flora import read_review
        rows = self.dir / "dump" / "rulings"
        rows.mkdir(parents=True)
        (rows / "Viburnum_opulus.json").write_text(json.dumps({
            "by": "u_x", "common_name": "Highbush Cranberry", "group": "thin",
            "my_read": "native", "on": "2026-10-07",
            "ruling": "native", "scientific_name": "Viburnum opulus"}),
            encoding="utf-8")
        review = read_review(self.dir / "dump")
        self.assertEqual(review, {"places": {"edmonton": {"Viburnum opulus": {
            "ruling": "native", "on": "2026-10-07"}}}})
        self.assertEqual(read_review(rows), review)
        export = self.dir / "export.json"
        export.write_text(json.dumps(review), encoding="utf-8")
        self.assertEqual(read_review(export), review)

    def test_merge_rewrites_the_list_in_the_same_run(self):
        """The rulings file and the list must agree, or the data gate fails
        ("edited but not derived"), so ``--merge`` derives as well."""
        from unittest import mock
        import scripts.derive_local_flora as d
        out = self.dir / "local_flora.json"
        export = self.dir / "export.json"
        export.write_text(json.dumps({"places": {"edmonton": {
            "Prunus pensylvanica": {"ruling": "native"}}}}),
            encoding="utf-8")
        real = [p.read_bytes() for p in (d.RULINGS_PATH, d.OUTPUT_PATH)]
        with mock.patch.object(d, "RULINGS_PATH", self.path), \
                mock.patch.object(d, "OUTPUT_PATH", out), \
                mock.patch("sys.stdout"):
            self.assertEqual(d.main(["--merge", str(export)]), 0)
            self.assertEqual(d.main(["--merge", str(self.dir / "none.json")]),
                             1)
        # The shipped files are untouched: a default argument bound at import
        # once made this test write its ruling into the real one.
        self.assertEqual([p.read_bytes() for p in (d.RULINGS_PATH,
                                                   d.OUTPUT_PATH)], real)
        entry = json.loads(out.read_text(encoding="utf-8"))[
            "places"]["edmonton"]["species"]["Prunus pensylvanica"]
        self.assertEqual((entry["tier"], entry["ruling"]), ("thin", "native"))
        self.assertTrue(lf.is_native(entry))


class TestTheReviewPage(unittest.TestCase):
    """``tools/local_flora_review`` builds the page the owner rules on. Its
    database ids are what ``--merge`` reads back, so they must be valid path
    segments and one per species."""

    @classmethod
    def setUpClass(cls):
        from tools.local_flora_review import build
        cls.build = build
        cls.data, cls.unread = build.page_data()

    def test_it_holds_every_species_the_rule_cannot_settle(self):
        with open(os.path.join(ROOT, "data", "local_flora.json"),
                  encoding="utf-8") as fh:
            edm = json.load(fh)["places"]["edmonton"]["species"]
        waiting = {n for n, e in edm.items()
                   if e["tier"] in ("thin", "observed", "no_data")}
        on_page = {s["s"] for s in self.data["species"] if s["g"] != "flagged"}
        self.assertEqual(on_page, waiting)
        for s in self.data["species"]:
            if s["g"] == "flagged":
                self.assertEqual(edm[s["s"]]["tier"], "documented", s["s"])

    def test_ids_are_path_segments_one_per_species(self):
        ids = [s["id"] for s in self.data["species"]]
        self.assertEqual(len(ids), len(set(ids)))
        for i in ids:
            self.assertRegex(i, r"^[A-Za-z0-9_.~:@+-]{1,200}$")

    def test_the_page_embeds_its_data_once_and_names_the_merge(self):
        html = self.build.render(self.data)
        self.assertNotIn("/*__DATA__*/", html)
        self.assertNotIn("</script", html.split("const DATA = ", 1)[1]
                         .split(";\n", 1)[0])
        self.assertIn("derive_local_flora.py --merge", html)
        self.assertNotIn("—", html)

    def test_the_page_asks_yes_or_no_and_nothing_else(self):
        """The owner's word: answer where confident, no reasons. The only
        text box on the page is the read-only export."""
        html = self.build.render(self.data)
        self.assertIn('data-v="native"', html)
        self.assertIn('data-v="not_native"', html)
        self.assertNotIn('data-v="unsettled"', html)
        self.assertEqual(html.count("<textarea"), 1)
        self.assertIn('<textarea id="export" readonly', html)
        self.assertNotIn("reason:", html.split("<script>", 1)[1])


class TestTheDataGate(unittest.TestCase):
    """``validate-data`` (CI runs it) catches the edits a person makes by hand."""

    def setUp(self):
        import pathlib
        import shutil
        import tempfile
        from unittest import mock
        self.dir = pathlib.Path(tempfile.mkdtemp())
        for name in ("local_flora.json", "local_flora_rulings.json",
                     "plants_master.json"):
            shutil.copy(os.path.join(ROOT, "data", name), self.dir / name)
        patcher = mock.patch("src.data_quality.DATA_DIR", self.dir)
        patcher.start()
        self.addCleanup(patcher.stop)

    def _rule(self, name, ruling):
        path = self.dir / "local_flora_rulings.json"
        doc = json.loads(path.read_text(encoding="utf-8"))
        doc["places"]["edmonton"][name] = {"ruling": ruling}
        path.write_text(json.dumps(doc), encoding="utf-8")

    def test_the_shipped_pair_passes(self):
        from src.data_quality import validate_local_flora
        self.assertEqual(validate_local_flora(), ([], []))

    def test_a_ruling_added_and_not_derived_fails(self):
        from src.data_quality import validate_local_flora
        self._rule("Prunus pensylvanica", "native")
        errors, _ = validate_local_flora()
        self.assertTrue(any("not in the derived list" in e for e in errors),
                        errors)

    def test_a_ruling_across_the_vascan_gate_fails(self):
        from src.data_quality import validate_local_flora
        self._rule("Aquilegia canadensis", "native")
        errors, _ = validate_local_flora()
        self.assertTrue(any("VASCAN" in e for e in errors), errors)


class TestTheShippedList(unittest.TestCase):
    """data/local_flora.json against its inputs and the answers known."""

    @classmethod
    def setUpClass(cls):
        with open(os.path.join(ROOT, "data", "local_flora.json"),
                  encoding="utf-8") as fh:
            cls.text = fh.read()
        cls.doc = json.loads(cls.text)
        cls.edm = cls.doc["places"]["edmonton"]["species"]

    def test_it_is_what_a_fresh_derivation_writes(self):
        # A ruling added, the cache re-fetched or a species renamed without
        # re-running the script would otherwise ship a list that disagrees
        # with its own inputs, silently.
        from scripts.derive_local_flora import build
        self.assertEqual(lf.dumps(build()), self.text,
                         "stale: python scripts/derive_local_flora.py --write")

    def test_it_covers_the_whole_catalogue(self):
        with open(os.path.join(ROOT, "data", "plants_master.json"),
                  encoding="utf-8") as fh:
            names = {r["scientific_name"] for r in json.load(fh)}
        self.assertEqual(set(self.edm), names)

    def test_the_centre_is_the_maps_edmonton(self):
        from src.ecoregion_basemap import CITIES
        from src.onboarding import EXAMPLE_DEFAULT_LATLNG
        dot = next((lat, lng) for name, lat, lng in CITIES
                   if name == "Edmonton")
        self.assertEqual(tuple(EDMONTON["centre"]), dot)
        self.assertEqual(tuple(EDMONTON["centre"]), EXAMPLE_DEFAULT_LATLNG)

    def test_the_answers_that_are_known(self):
        # The parkland's defining shrub, documented by specimens alone.
        self.assertEqual(self.edm["Amelanchier alnifolia"]["tier"], "documented")
        # Bur Oak has specimens near the city and is still out (VASCAN gate).
        self.assertGreaterEqual(self.edm["Quercus macrocarpa"]["collections"], 3)
        self.assertEqual(self.edm["Quercus macrocarpa"]["tier"],
                         "not_in_province")
        # The owner's example, and both columbines of the mountains.
        for name in ("Aquilegia canadensis", "Aquilegia flavescens",
                     "Aquilegia formosa"):
            self.assertFalse(lf.is_native(self.edm[name]), name)
        self.assertTrue(lf.is_native(self.edm["Aquilegia brevistyla"]))
        # Pin cherry is not documented by its specimens; only a review can
        # put it on the list, so it is never quietly "not native".
        self.assertEqual(self.edm["Prunus pensylvanica"]["tier"], "thin")

    def test_the_text_round_trips(self):
        self.assertEqual(json.loads(lf.dumps(self.doc)), self.doc)


class TestWords(unittest.TestCase):
    """The sentence each tier prints, under a heading like "Around Edmonton"."""

    @classmethod
    def setUpClass(cls):
        species = {n: _row(n) for n in ("A a", "B b", "C c", "D d", "E e",
                                         "G g")}
        species["F f"] = _row("F f", "SK")
        cache = {"basis": BASIS, "generated": "2026-01-01", "species": {
            "A a": [_at(1, year=1915), _at(2, year=1960), _at(3, year=2017)],
            "B b": [_at(1, year=1966)],
            "C c": [_at(2, basis=OBS)] * 7,
            "D d": [_at(160)],
            "F f": [_at(1)] * 3,
            "G g": [_at(1, year=1933), _at(2, year=1960), _at(3, year=2008)]}}
        rulings = lf.parse_rulings({"places": {"edmonton": {
            "B b": {"ruling": "native"}, "G g": {"ruling": "not_native"}}}},
            species)
        nh.set_document(lf.derive(species.values(), cache, rulings))

    @classmethod
    def tearDownClass(cls):
        nh.set_document(None)

    def test_each_tier_says_what_it_rests_on(self):
        words = {n: nh.around(n)["words"] for n in "A a|B b|C c|D d|E e|F f|G g"
                 .split("|")}
        self.assertEqual(words["A a"],
                         "Native. Collected 3 times within 50 km, 1915 to 2017.")
        self.assertEqual(words["B b"], "Native, confirmed on review. Collected "
                                       "once within 50 km, in 1966.")
        self.assertEqual(words["G g"], "Not native here, on review. Collected "
                                       "3 times within 50 km, 1933 to 2008.")
        self.assertIn("never collected there", words["C c"])
        self.assertIn("planted ones are seen too", words["C c"])
        self.assertEqual(words["D d"], "Not recorded within 50 km. The nearest "
                                       "record is 160 km from Edmonton.")
        self.assertIn("no occurrence records", words["E e"])
        self.assertIn("VASCAN does not record it native to Alberta",
                      words["F f"])

    def test_below_the_floor_is_not_settled_never_not_native(self):
        nh.set_document(lf.derive([_row("B b")], {
            "basis": BASIS, "generated": "x", "species": {"B b": [_at(1)]}}))
        try:
            self.assertTrue(nh.around("B b")["words"].startswith("Not settled"))
            self.assertFalse(nh.around("B b")["native"])
        finally:
            self.setUpClass()

    def test_a_reason_in_the_list_is_never_printed(self):
        """Even one hand-written into the shipped file: the owner asked that
        their answers carry no reasons and that none be shown."""
        doc = lf.derive([_row("B b")], {
            "basis": BASIS, "generated": "x", "species": {"B b": [_at(1)]}})
        doc["places"]["edmonton"]["species"]["B b"].update(
            {"ruling": "native", "reason": "SHOULD NOT SHOW"})
        nh.set_document(doc)
        try:
            self.assertEqual(nh.around("B b")["words"],
                             "Native, confirmed on review. Collected once "
                             "within 50 km, in 2000.")
        finally:
            self.setUpClass()

    def test_an_unknown_place_is_refused_not_emptied(self):
        with self.assertRaises(ValueError):
            nh.native_names("calgary")
        self.assertEqual(nh.around("A a", "calgary"), {})

    def test_place_at_reads_the_circle(self):
        self.assertEqual(nh.place_at(53.62, -113.37), "edmonton")
        self.assertEqual(nh.place_at(52.27, -113.81), "")      # Red Deer
        self.assertEqual(nh.place_at(None, None), "")


class TestShippedWords(unittest.TestCase):

    def test_no_dash_the_website_refuses_reaches_a_sentence(self):
        nh.set_document(None)
        with open(os.path.join(ROOT, "data", "local_flora.json"),
                  encoding="utf-8") as fh:
            names = json.load(fh)["places"]["edmonton"]["species"]
        for name in names:
            words = nh.around(name)["words"]
            self.assertNotIn("—", words, name)
            self.assertNotIn("–", words, name)


class TestProvinceWords(unittest.TestCase):

    def test_it_names_the_province_a_plant_is_not_native_to(self):
        self.assertEqual(nh.province_words(_row("x", "SK")),
                         "Saskatchewan, as VASCAN records it. Not native to "
                         "Alberta.")
        self.assertEqual(nh.province_words(_row("x", "AB,SK")),
                         "Alberta and Saskatchewan, as VASCAN records it.")

    def test_an_unsourced_list_is_withheld_as_the_website_withholds_it(self):
        from src.nativity import WITHHELD_NOTE
        self.assertEqual(nh.province_words({"native_provinces": "AB"}),
                         WITHHELD_NOTE)

    def test_the_helpers_still_import_from_plant_filters(self):
        from src import plant_filters as pf
        self.assertIs(pf.native_in, nh.native_in)
        self.assertIs(pf.native_tip, nh.native_tip)
        self.assertIs(pf.PROVINCE_NAMES, nh.PROVINCE_NAMES)


if __name__ == "__main__":
    unittest.main()

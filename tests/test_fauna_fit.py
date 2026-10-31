"""
tests/test_fauna_fit.py — has this animal been recorded near this yard? (F190,
V3.37): the rule, the Edmonton pack's counts, the 3D scene that stops drawing
the ptarmigans, and the Overview's named animal.
"""

import os
import shutil
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

_TMP_DIR = tempfile.mkdtemp(prefix="permadesign_fauna_fit_")

import src.db.plants as _plants_mod  # noqa: E402

_plants_mod._DATA_DIR = _TMP_DIR
_plants_mod._DB_PATH = os.path.join(_TMP_DIR, "permadesign_test.db")

from src import fauna_fit as F  # noqa: E402

EDMONTON = (53.5461, -113.4938)
CALGARY = (51.05, -114.07)


def tearDownModule():
    shutil.rmtree(_TMP_DIR, ignore_errors=True)


def _records(**animals):
    """Counts for a made-up pack: ``name=(group, near, province)``."""
    return F.Records(key="test", province="AB", radius_km=50, fetched="",
                     animals={k.replace("_", " "): v
                              for k, v in animals.items()})


class TheRule(unittest.TestCase):

    def setUp(self):
        # Birds: 10% of the province's records are near the place, and 1,000+
        # near it per bird, so absence is telling for any bird. Bees: 10%, and
        # few records each.
        self.r = _records(
            common_bird=("bird", 50000, 400000),
            stray_bird=("bird", 2, 26000),
            mountain_bird=("bird", 0, 2000),
            rare_bird=("bird", 0, 3),
            common_bee=("bee", 90, 900),
            mountain_bee=("bee", 0, 1900),
            quiet_bee=("bee", 0, 40),
            one_bee=("bee", 1, 5))

    def test_the_shares_come_from_the_counts(self):
        self.assertAlmostEqual(self.r.shares["bird"], 50002 / 428003)
        self.assertAlmostEqual(self.r.shares["bee"], 91 / 2845)
        self.assertGreater(self.r.per_animal["bird"], F.SATURATED)
        self.assertLess(self.r.per_animal["bee"], F.SATURATED)

    def test_four_answers(self):
        band = self.r.band
        self.assertEqual(band("common bird"), F.HERE)
        self.assertEqual(band("stray bird"), F.STRAY,
                         "2 near against about 3,000 expected")
        self.assertEqual(band("mountain bird"), F.ELSEWHERE)
        self.assertEqual(band("common bee"), F.HERE)
        self.assertEqual(band("mountain bee"), F.ELSEWHERE,
                         "about 60 expected near, none recorded")
        self.assertEqual(band("one bee"), F.HERE,
                         "one record near a place is recorded near it")

    def test_absence_is_unknown_where_records_are_thin(self):
        self.assertEqual(self.r.band("quiet bee"), F.UNRECORDED,
                         "about one expected near: none is not telling (P9)")
        self.assertEqual(self.r.band("not counted"), F.UNRECORDED,
                         "an animal GBIF did not answer for is not absent")
        self.assertIsNone(self.r.near("not counted"))

    def test_a_heavily_recorded_group_misses_nobody(self):
        """Three province records predict well under one near the place, but
        a bird near Edmonton is recorded thousands of times a year: none is
        telling. The Rock Ptarmigan's case."""
        self.assertLess(self.r.expected("rare bird"), F.ABSENT_EXPECTED)
        self.assertEqual(self.r.band("rare bird"), F.ELSEWHERE)

    def test_what_the_scene_draws(self):
        self.assertTrue(self.r.drawn("common bird"))
        self.assertTrue(self.r.drawn("quiet bee"))
        for name in ("stray bird", "mountain bird", "mountain bee"):
            self.assertFalse(self.r.drawn(name), name)

    def test_a_file_this_module_did_not_write_is_refused(self):
        with self.assertRaises(ValueError):
            F.from_doc({"version": 2, "animals": {}})
        with self.assertRaises(ValueError):
            F.from_doc({"version": 1, "animals": {
                "x": {"group": "bee", "near": -1, "province": 3}}})
        with self.assertRaises(ValueError):
            F.from_doc({"version": 1, "animals": {"x": {"near": 1}}})


class TheEdmontonCounts(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.r = F.records("edmonton")

    def test_the_pack_counts_the_catalogue(self):
        """Every counted animal is a catalogue animal. One added since the
        owner's run is simply not counted (unrecorded) until the next run, so
        the floor is coverage, not equality."""
        import json
        with open(os.path.join(ROOT, "data", "fauna_master.json"),
                  encoding="utf-8") as fh:
            names = {r["scientific_name"] for r in json.load(fh)}
        self.assertIsNotNone(self.r)
        self.assertLessEqual(set(self.r.animals), names)
        self.assertGreater(len(self.r.animals), 0.95 * len(names),
                           "re-run scripts/fetch_animals_near.py")
        self.assertEqual(self.r.radius_km, 50.0)

    def test_the_ptarmigans_are_not_edmonton_birds(self):
        for name in ("Lagopus lagopus", "Lagopus leucura", "Lagopus muta"):
            self.assertEqual(self.r.band(name), F.ELSEWHERE, name)

    def test_the_backyard_birds_are(self):
        for name in ("Poecile atricapillus", "Bombycilla cedrorum",
                     "Turdus migratorius"):
            self.assertEqual(self.r.band(name), F.HERE, name)
        self.assertEqual(self.r.band("Selasphorus calliope"), F.STRAY)

    def test_a_little_recorded_bee_is_unknown_not_absent(self):
        quiet = [n for n, (g, near, prov) in self.r.animals.items()
                 if g == "bee" and near == 0 and 0 < prov < 30]
        self.assertTrue(quiet)
        for name in quiet:
            self.assertEqual(self.r.band(name), F.UNRECORDED, name)

    def test_the_shipped_file_is_what_the_counts_derive(self):
        import io
        from contextlib import redirect_stdout
        sys.path.insert(0, os.path.join(ROOT, "scripts"))
        import derive_animals_here as derive
        with redirect_stdout(io.StringIO()) as out:
            code = derive.main(["--check"])
        self.assertEqual(code, 0, out.getvalue())

    def test_a_moved_circle_is_not_written(self):
        sys.path.insert(0, os.path.join(ROOT, "scripts"))
        import derive_animals_here as derive
        from src import region
        pack = region.regions()["edmonton"]
        self.assertFalse(derive.moved(pack, {"centre": list(pack.centre),
                                             "radius_km": pack.radius_km}))
        self.assertTrue(derive.moved(pack, {"centre": list(pack.centre),
                                            "radius_km": 80}))


class WhichPack(unittest.TestCase):

    def test_a_pin_in_the_pack_uses_its_counts(self):
        self.assertEqual(F.for_point(*EDMONTON).key, "edmonton")
        self.assertEqual(F.rule(*EDMONTON)("Lagopus leucura"), F.ELSEWHERE)

    def test_no_pin_uses_the_default_pack(self):
        self.assertEqual(F.for_point().key, "edmonton")

    def test_a_pin_outside_every_pack_borrows_nothing(self):
        self.assertIsNone(F.for_point(*CALGARY))
        self.assertEqual(F.rule(*CALGARY)("Lagopus leucura"), F.UNRECORDED)


class TheScene(unittest.TestCase):
    """The ptarmigans through build_scene and wildlife_for_scene, from the
    real catalogue: Dwarf Birch feeds the Willow and White-tailed
    Ptarmigans, and Bearberry the Willow Ptarmigan."""

    @classmethod
    def setUpClass(cls):
        from src.db.plants import get_connection, init_db
        init_db()
        conn = get_connection()
        try:
            cls.ids = {r["common_name"]: r["id"] for r in conn.execute(
                "SELECT id, common_name FROM plants")}
        finally:
            conn.close()

    def _birds(self, lat, lng):
        from src.db.fauna import fauna_for_plants
        from src.project_store import plant_feature
        from src.scene_contract import build_scene
        from src.scene_wildlife import wildlife_for_scene
        names = ("Dwarf Birch", "Bearberry", "Saskatoon Berry")
        feats = [plant_feature({"plant_id": self.ids[n], "common_name": n,
                                "lat": lat, "lng": lng + i / 50000.0})
                 for i, n in enumerate(names)]
        sc = build_scene({"type": "FeatureCollection",
                          "properties": {"site_config": {}},
                          "features": feats}, year=5, wind=False)
        sc["month"], sc["is_night"] = 7, False

        def birds(ids):
            return [r for r in fauna_for_plants(ids) if r["taxon"] == "bird"]
        return {c["name"] for c in wildlife_for_scene(sc, fauna_edges=birds)}

    def test_an_edmonton_yard_draws_no_ptarmigan(self):
        drawn = self._birds(*EDMONTON)
        self.assertFalse([n for n in drawn if "Ptarmigan" in n], drawn)
        self.assertTrue(drawn, "the yard's other birds are still drawn")

    def test_outside_the_pack_nothing_changes(self):
        drawn = self._birds(*CALGARY)
        self.assertTrue([n for n in drawn if "Ptarmigan" in n], drawn)


class TheOverviewsAnimal(unittest.TestCase):

    def test_named_only_if_recorded_here_and_familiar_first(self):
        """animals_fed's order is most of the design's plants first. With the
        counts, a stray is never named and a familiar animal comes before one
        people seldom record, whatever it eats."""
        from src import yard_overview_items as yi
        r = _records(Pheucticus_melanocephalus=("bird", 1, 19000),
                     Pinicola_enucleator=("bird", 800, 9000),
                     Bombycilla_cedrorum=("bird", 17000, 140000),
                     Turdus_migratorius=("bird", 50000, 400000))
        animals = [
            {"name": "Black-headed Grosbeak", "scientific_name":
             "Pheucticus melanocephalus", "taxon": "bird", "food": True,
             "plants": {1: ["seed_food"], 2: ["seed_food"], 3: ["seed_food"]}},
            {"name": "Pine Grosbeak", "scientific_name": "Pinicola enucleator",
             "taxon": "bird", "food": True,
             "plants": {1: ["fruit_food"], 2: ["fruit_food"], 3: ["seed_food"]}},
            {"name": "Cedar Waxwing", "scientific_name": "Bombycilla cedrorum",
             "taxon": "bird", "food": True,
             "plants": {1: ["fruit_food"], 2: ["fruit_food"]}},
            {"name": "American Robin", "scientific_name": "Turdus migratorius",
             "taxon": "bird", "food": True, "plants": {1: ["fruit_food"]}},
        ]
        self.assertEqual(yi.example_animal(animals), "Black-headed Grosbeak",
                         "without counts: most of the design's plants")
        self.assertFalse(r.familiar("Pinicola enucleator"))
        self.assertEqual(yi.example_animal(animals, (), r), "Cedar Waxwing",
                         "familiar, then most of the design's plants")
        self.assertEqual(yi.example_animal(animals, ("American Robin",), r),
                         "American Robin", "the pack's familiar list leads")


if __name__ == "__main__":
    unittest.main()

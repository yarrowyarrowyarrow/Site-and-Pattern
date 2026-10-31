"""
tests/test_succulent_habit.py — each succulent's and cactus's body (F177,
V2.93; src/succulent_habit.py, html/scene3d/24-succulents.js).

Rule tests on plain dicts, the catalogue routed row by row, the counts and
seasons the block carries, the corrected rows, the viewer and Python agreeing
on the vocabulary, and an animal perched on a prickly pear at the height it is
drawn. The shapes on screen are pinned by the render probe
(tests/test_accuracy_render.py).
"""

import json
import os
import re
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_TMP_DIR = tempfile.mkdtemp(prefix="permadesign_succulent_test_")
import src.db.plants as _plants_mod  # noqa: E402

_plants_mod._DATA_DIR = _TMP_DIR
_plants_mod._DB_PATH = os.path.join(_TMP_DIR, "permadesign_test.db")

from src import succulent_habit as SH  # noqa: E402

_ROOT = Path(__file__).resolve().parent.parent
_JS = _ROOT / "html" / "scene3d"

#: Every row that gets a succulent body, by scientific name. Until V2.93 all
#: six borrowed another plant's: a grass-like star, a herb mat, a leafy bush.
EXPECTED = {
    "Opuntia polyacantha": "pads",
    "Opuntia fragilis": "pads",
    "Escobaria vivipara": "ball",
    "Yucca glauca": "swords",
    "Rhodiola integrifolia": "fleshy",
    "Sedum lanceolatum": "fleshy",
}


def _rows():
    return json.loads((_ROOT / "data" / "plants_master.json")
                      .read_text(encoding="utf-8"))


def _p(**kw):
    d = dict(plant_type="wildflower", x=0.0, y=0.0, height_m=0.2,
             canopy_m=0.4, scale_factor=1.0)
    d.update(kw)
    return d


class TheBody(unittest.TestCase):

    def test_each_succulent_row_gets_its_own_body(self):
        rows = {r["scientific_name"]: r for r in _rows()}
        for sci, want in EXPECTED.items():
            with self.subTest(sci):
                self.assertIn(sci, rows)
                self.assertEqual(SH.body_for(rows[sci]), want)

    def test_no_other_row_gets_one(self):
        """A body is a claim about a plant's habit; a row that does not record
        one of these habits is drawn as what it records."""
        for r in _rows():
            if r["scientific_name"] in EXPECTED:
                continue
            with self.subTest(r["common_name"]):
                self.assertIsNone(SH.body_for(r))

    def test_the_record_decides_not_the_name(self):
        self.assertEqual(SH.body_for(_p(growth_form="pads")), "pads")
        self.assertEqual(SH.body_for(_p(growth_form="globose")), "ball")
        self.assertEqual(SH.body_for(_p(growth_form="succulent")), "fleshy")
        self.assertEqual(SH.body_for(_p(plant_type="groundcover",
                                        growth_form="succulent")), "fleshy")
        # A rosette shrub with narrow leaves is swords; with broad ones, or
        # as a herb, it is not.
        self.assertEqual(SH.body_for(_p(plant_type="shrub", branching="rosette",
                                        leaf_shape="linear")), "swords")
        self.assertIsNone(SH.body_for(_p(plant_type="shrub", branching="rosette",
                                         leaf_shape="ovate")))
        self.assertIsNone(SH.body_for(_p(growth_form="rosette",
                                         leaf_shape="linear")))
        self.assertIsNone(SH.body_for(_p(growth_form="mat")))


class TheBlock(unittest.TestCase):

    def test_a_ball_cactus_clusters_as_it_grows(self):
        young = SH.drawn_block(_p(growth_form="globose", scale_factor=0.25,
                                  height_m=0.05), "ball")
        grown = SH.drawn_block(_p(growth_form="globose", height_m=0.15), "ball")
        self.assertEqual(young["stems"], 1)
        self.assertEqual(grown["stems"], SH.BALLS_MATURE)
        self.assertAlmostEqual(grown["ball_m"], SH.BALL_OF_HEIGHT * 0.15,
                               delta=0.001)            # rounded to the millimetre
        # The cluster is its globes, not the ground spaced for it.
        self.assertLess(grown["canopy_m"], 0.4)

    def test_a_yucca_sends_up_one_stalk_per_recorded_flowering_stem(self):
        yucca = _p(plant_type="shrub", branching="rosette", leaf_shape="linear",
                   leaf_size_cm=50.0, flowering_stems=4, height_m=0.9,
                   canopy_m=1.8, bloom_start=6, bloom_end=7, fruit_start=8,
                   fruit_end=9)
        d = SH.drawn_block(yucca, "swords")
        self.assertEqual((d["stems"], d["stalks"]), (4, 4))
        self.assertAlmostEqual(d["leaf_m"], 0.5)
        self.assertEqual(d["height_m"], 0.9)
        # The stalk stands through the flowers and the capsules after them.
        self.assertEqual(d["stalk_months"], [6, 9])

    def test_with_no_bloom_recorded_no_stalk_is_drawn(self):
        d = SH.drawn_block(_p(plant_type="shrub", branching="rosette",
                              leaf_shape="linear", flowering_stems=2), "swords")
        self.assertEqual(d["stalk_months"], [])

    def test_a_young_plant_is_smaller(self):
        grown = SH.drawn_block(_p(leaf_size_cm=50.0, flowering_stems=4), "swords")
        young = SH.drawn_block(_p(leaf_size_cm=50.0, flowering_stems=4,
                                  scale_factor=0.5), "swords")
        self.assertLess(young["leaf_m"], grown["leaf_m"])
        self.assertLess(young["stalks"], grown["stalks"])

    def test_roseroot_is_a_crown_of_stems_and_a_stonecrop_a_mat(self):
        rose = SH.drawn_block(_p(growth_form="succulent", flowering_stems=4,
                                 height_m=0.25, canopy_m=0.375,
                                 leaf_size_cm=3.0), "fleshy")
        self.assertEqual(rose["stems"], 4)
        self.assertNotIn("mat", rose)
        self.assertLess(rose["canopy_m"], 0.375)
        crop = SH.drawn_block(_p(plant_type="groundcover", growth_form="succulent",
                                 flowering_stems=8, canopy_m=0.3,
                                 bloom_start=6, bloom_end=7), "fleshy")
        self.assertTrue(crop["mat"])
        self.assertEqual(crop["canopy_m"], 0.3)       # the mat covers its ground
        self.assertEqual(crop["stalk_months"], [6, 7])

    def test_pads_fill_the_ground_they_were_given(self):
        d = SH.drawn_block(_p(plant_type="groundcover", growth_form="pads",
                              height_m=0.3, canopy_m=0.9), "pads")
        self.assertEqual((d["height_m"], d["canopy_m"]), (0.3, 0.9))

    def test_another_bodys_block_is_left_alone(self):
        vine = _p(plant_type="vine", growth_form="succulent",
                  drawn={"habit": "sprawling"})
        SH.apply_succulent_habits([vine])
        self.assertEqual(vine["drawn"], {"habit": "sprawling"})


class ThroughBuildScene(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from src.db.plants import get_connection, init_db
        init_db()
        conn = get_connection()
        try:
            cls.ids = {r["scientific_name"]: (r["id"], r["common_name"])
                       for r in conn.execute(
                           "SELECT id, common_name, scientific_name FROM plants")}
        finally:
            conn.close()

    def _plant(self, sci):
        from src.project_store import plant_feature
        from src.scene_contract import build_scene
        pid, name = self.ids[sci]
        sc = build_scene({"type": "FeatureCollection",
                          "properties": {"site_config": {}},
                          "features": [plant_feature({
                              "plant_id": pid, "common_name": name,
                              "lat": 51.05, "lng": -114.07})]},
                         year=0, wind=False)
        json.dumps(sc)                                  # plain data
        return sc["plants"][0]

    def test_the_scene_carries_each_body(self):
        for sci, want in EXPECTED.items():
            with self.subTest(sci):
                self.assertEqual(self._plant(sci)["drawn"]["body"], want)

    def test_the_yucca_is_drawn_blue_grey(self):
        """Its name is its glaucous leaves. As the shrub default it was the
        green of a dogwood."""
        from src.scene_contract import _FOLIAGE_BY_TYPE
        colour = self._plant("Yucca glauca")["color"]
        self.assertNotEqual(colour, _FOLIAGE_BY_TYPE["shrub"])
        r, g, b = (int(colour[i:i + 2], 16) for i in (1, 3, 5))
        self.assertGreater(b, r, f"{colour} is not a blue-grey")


class NoVineIsSeatedAtAYucca(unittest.TestCase):
    """A vine climbs the tree or shrub beside it (V2.89), and the generator
    seats vines at the foot of one (F181). The yucca is filed as a shrub; its
    body is a rosette of sword leaves with no crown, so neither the scene nor
    the generator treats it as a host (V2.93). Every other tree and shrub still
    is."""

    def test_the_yucca_is_the_one_tree_or_shrub_that_holds_no_vine(self):
        from src.vine_habit import holds_vines
        refused = [r["scientific_name"] for r in _rows()
                   if r.get("plant_type") in ("tree", "shrub")
                   and not holds_vines(r)]
        self.assertEqual(refused, ["Yucca glauca"])


class AnimalsPerchWhereThePlantIsDrawn(unittest.TestCase):
    """The plains prickly pear is a 30 cm groundcover. The viewer draws it
    30 cm tall from its block; the animals used the groundcover mat's 18 cm
    cap, and a bee on its flowers perched inside the pads."""

    def test_the_drawn_height_wins_over_the_mat_cap(self):
        from src import scene_wildlife as W
        pear = _p(plant_type="groundcover", growth_form="pads", height_m=0.3,
                  canopy_m=0.9)
        SH.apply_succulent_habits([pear])
        self.assertAlmostEqual(W._drawn_height(pear), 0.3)
        plain = _p(plant_type="groundcover", growth_form="mat", height_m=0.3)
        self.assertAlmostEqual(W._drawn_height(plain),
                               W.GROUNDCOVER_DRAWN_MAX_M)


class TheViewerAgrees(unittest.TestCase):
    """One vocabulary, one set of numbers, on both sides."""

    def _js(self, name):
        return (_JS / name).read_text(encoding="utf-8")

    def test_the_viewer_draws_exactly_these_bodies(self):
        m = re.search(r"window\.SUCCULENT_BODIES = \{([^}]*)\}",
                      self._js("24-succulents.js"))
        self.assertIsNotNone(m, "24-succulents.js lost SUCCULENT_BODIES")
        self.assertEqual(set(re.findall(r"(\w+):", m.group(1))), set(SH.BODIES))

    def test_the_ball_is_as_wide_as_python_says(self):
        m = re.search(r"const w = ([\d.]+);\s*// succulent_habit\.BALL_WIDTH",
                      self._js("24-succulents.js"))
        self.assertIsNotNone(m, "the ball's width is no longer tied to Python")
        self.assertEqual(float(m.group(1)), SH.BALL_WIDTH)

    def test_the_chunk_loads(self):
        html = (_ROOT / "html" / "scene3d.html").read_text(encoding="utf-8")
        self.assertIn("'scene3d/24-succulents.js'", html)

    def test_the_flowers_and_fruit_ask_where_the_body_is(self):
        for name in ("05-flowers.js", "11-fruit.js", "15-florets.js"):
            with self.subTest(name):
                self.assertTrue("succulentAnchorsFor(p)" in self._js(name),
                                f"{name} does not put blooms on a succulent's body")

    def test_the_herb_fallback_knows_the_new_habits(self):
        """Should the chunk ever fail, a cactus falls back to the herb mat, and
        the generator resolves the same baked variant for it as before."""
        sys.path.insert(0, str(_ROOT / "scripts" / "blender"))
        from assetlib import conventions             # noqa: PLC0415 (bpy-free)
        js = self._js("03-herbs.js")
        for form in ("pads", "globose"):
            with self.subTest(form):
                self.assertEqual(conventions.HERB_FORM_ALIAS[form], "mat")
                self.assertRegex(js, rf"\b{form}: 'mat'")


class TheData(unittest.TestCase):

    def test_the_cacti_record_their_habit(self):
        rows = {r["scientific_name"]: r for r in _rows()}
        self.assertEqual(rows["Opuntia polyacantha"]["growth_form"], "pads")
        self.assertEqual(rows["Opuntia fragilis"]["growth_form"], "pads")
        self.assertEqual(rows["Escobaria vivipara"]["growth_form"], "globose")

    def test_the_gate_knows_the_words(self):
        from src.data_quality import GROWTH_FORMS
        self.assertIn("pads", GROWTH_FORMS)
        self.assertIn("globose", GROWTH_FORMS)

    def test_the_seeder_agrees_with_the_data(self):
        """scripts/seed_non_woody_morphology.py wrote these values; a re-run
        must not undo them."""
        text = (_ROOT / "scripts" / "seed_non_woody_morphology.py").read_text(
            encoding="utf-8")
        for key, form in (('"Escobaria":', "globose"), ('"Opuntia":', "pads"),
                          ('"Escobaria vivipara":', "globose")):
            with self.subTest(key):
                line = next(l for l in text.splitlines()
                            if l.strip().startswith(key))
                self.assertIn(f'"{form}")', line)

    def test_the_schema_was_bumped(self):
        self.assertGreaterEqual(_plants_mod._SCHEMA_VERSION, 91)


if __name__ == "__main__":
    unittest.main()

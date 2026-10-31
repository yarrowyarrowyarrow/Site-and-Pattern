"""
tests/test_pond_habit.py — each wetland plant's body and the water under it
(F175, V2.90; src/pond_habit.py).

Rule tests on plain dicts, the catalogue routed row by row, the pond model's
water held to the constants, the corrected rows, and an animal perched on a
floating pad where the pad is drawn.
"""

import json
import math
import os
import struct
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_TMP_DIR = tempfile.mkdtemp(prefix="permadesign_pond_test_")
import src.db.plants as _plants_mod  # noqa: E402

_plants_mod._DATA_DIR = _TMP_DIR
_plants_mod._DB_PATH = os.path.join(_TMP_DIR, "permadesign_test.db")

from src import pond_habit as PH  # noqa: E402

_ROOT = Path(__file__).resolve().parent.parent

#: What each wetland row is drawn as. None: drawn by another layer entirely
#: (graminoids as grasses, the horsetail by its own builder).
EXPECTED = {
    "Yellow Pond-lily": "floating",
    "Floating Marsh-marigold": "floating",
    "Ivy-leaved Duckweed": "floating",
    "Canada Waterweed": "submerged",
    "Spiked Water-milfoil": "submerged",
    "Sago Pondweed": "submerged",
    "Common Bladderwort": "submerged",
    "Broad-leaved Arrowhead": "broadleaf",
    "Arum-leaved Arrowhead": "broadleaf",
    "Broad-leaved Water-plantain": "broadleaf",
    "Buckbean": "broadleaf",
    "Water Arum (Wild Calla)": "broadleaf",
    "Common Mare's-tail": "whorled",
    "Water Parsnip": "herb",
    "Cattail": "reed",
    "Great Bulrush": "reed",
    "Giant Bur-reed": "reed",
    "Rat Root": "reed",
    "Small Bottle Sedge": "reed",
    "River Bulrush": None,
    "Alkali Bulrush": None,
    "Three-square Rush": None,
    "Swamp Horsetail": None,
}


def _rows():
    return json.loads((_ROOT / "data" / "plants_master.json")
                      .read_text(encoding="utf-8"))


def _p(body_fields, **kw):
    d = dict(plant_type="aquatic", x=0.0, y=0.0, height_m=0.2, canopy_m=1.0)
    d.update(body_fields)
    d.update(kw)
    return d


def _pond(x=0.0, y=0.0, size=6.0, sid="pond"):
    return {"struct_id": sid, "x": x, "y": y, "size_m": size}


class TheBody(unittest.TestCase):
    """Which body, from the habit and the leaves."""

    def test_every_wetland_row_is_drawn_by_its_own_body(self):
        rows = {r["common_name"]: r for r in _rows()}
        for name, want in EXPECTED.items():
            with self.subTest(name):
                self.assertIn(name, rows)
                self.assertEqual(PH.body_for(rows[name]), want)

    def test_no_aquatic_is_left_without_one(self):
        """A new aquatic row gets a body, or is a graminoid or a horsetail."""
        for r in _rows():
            if r.get("plant_type") != "aquatic":
                continue
            with self.subTest(r["common_name"]):
                body = PH.body_for(r)
                self.assertTrue(body in PH.BODIES
                                or r.get("growth_form") == "jointed")

    def test_the_habit_decides_not_the_habitat(self):
        # A wildflower that is an emergent with broad leaves (Water Arum).
        self.assertEqual(PH.body_for(_p({"plant_type": "wildflower",
                                         "growth_form": "emergent",
                                         "leaf_shape": "cordate"})),
                         "broadleaf")
        # A plain wildflower is none of the pond's business.
        self.assertIsNone(PH.body_for(_p({"plant_type": "wildflower",
                                          "growth_form": "erect"})))
        # Graminoids are grasses wherever they stand; horsetails, horsetails.
        self.assertIsNone(PH.body_for(_p({"plant_type": "sedge",
                                          "growth_form": "emergent"})))
        self.assertIsNone(PH.body_for(_p({"growth_form": "jointed"})))


class TheWater(unittest.TestCase):

    def test_inside_the_ponds_ellipse_is_water(self):
        size = 6.0
        rx, ry = PH.POND_WATER_RX * size, PH.POND_WATER_RY * size
        self.assertEqual(PH.water_at(0, 0, [_pond()]), PH.WATER_SURFACE_M)
        self.assertEqual(PH.water_at(rx * 0.95, 0, [_pond()]), PH.WATER_SURFACE_M)
        self.assertEqual(PH.water_at(0, ry * 0.95, [_pond()]), PH.WATER_SURFACE_M)
        # The ellipse is wider east-west than north-south, as the model is.
        self.assertEqual(PH.water_at(0, rx * 0.95, [_pond()]), 0.0)
        self.assertEqual(PH.water_at(rx * 1.05, 0, [_pond()]), 0.0)

    def test_a_bigger_pond_has_more_water(self):
        self.assertEqual(PH.water_at(4.0, 0, [_pond(size=6.0)]), 0.0)
        self.assertEqual(PH.water_at(4.0, 0, [_pond(size=12.0)]),
                         PH.WATER_SURFACE_M)

    def test_only_a_pond_holds_water(self):
        self.assertEqual(PH.water_at(0, 0, [_pond(sid="swale")]), 0.0)
        self.assertEqual(PH.water_at(0, 0, []), 0.0)

    def test_the_constants_are_the_pond_models_water(self):
        """struct_pond.glb's `water` mesh: a flat sheet at WATER_SURFACE_M,
        POND_WATER_RX and _RY of the authored size across. Read from the file,
        so a re-baked pond cannot quietly put the pads under its water."""
        models = _ROOT / "html" / "assets" / "models"
        manifest = json.loads((models / "manifest.json").read_text(
            encoding="utf-8"))
        spec = manifest["structures"]["pond"]
        blob = (models / spec["file"]).read_bytes()
        n = struct.unpack_from("<I", blob, 12)[0]
        gltf = json.loads(blob[20:20 + n])
        water = next(m for m in gltf["meshes"] if m.get("name") == "water")
        acc = gltf["accessors"][water["primitives"][0]["attributes"]["POSITION"]]
        size = float(spec["size_m"])
        self.assertAlmostEqual(acc["min"][1], PH.WATER_SURFACE_M, places=3)
        self.assertAlmostEqual(acc["max"][1], PH.WATER_SURFACE_M, places=3)
        self.assertAlmostEqual(acc["max"][0] / size, PH.POND_WATER_RX, places=3)
        self.assertAlmostEqual(acc["max"][2] / size, PH.POND_WATER_RY, places=3)


class HowHighItIsDrawn(unittest.TestCase):

    def test_a_floating_plant_lies_on_the_ground_without_a_pond(self):
        d = PH.drawn_block(_p({"growth_form": "floating"}, height_m=0.2),
                           "floating", [])
        self.assertEqual(d["water_m"], 0.0)
        self.assertAlmostEqual(d["height_m"], PH.FLOATING_ABOVE_M)

    def test_in_a_pond_it_floats_on_the_water(self):
        d = PH.drawn_block(_p({"growth_form": "floating"}, height_m=0.2),
                           "floating", [_pond()])
        self.assertAlmostEqual(d["water_m"], PH.WATER_SURFACE_M)
        self.assertAlmostEqual(d["height_m"],
                               PH.WATER_SURFACE_M + PH.FLOATING_ABOVE_M)

    def test_a_short_floating_plant_is_its_own_height(self):
        d = PH.drawn_block(_p({"growth_form": "floating"}, height_m=0.02),
                           "floating", [])
        self.assertAlmostEqual(d["height_m"], 0.02)

    def test_a_submerged_plant_shows_only_what_reaches_the_surface(self):
        d = PH.drawn_block(_p({"growth_form": "submerged"}, height_m=0.5),
                           "submerged", [_pond()])
        self.assertAlmostEqual(d["height_m"],
                               PH.WATER_SURFACE_M + PH.SUBMERGED_ABOVE_M)

    def test_an_emergent_stands_at_its_height_even_in_a_pond(self):
        d = PH.drawn_block(_p({"growth_form": "emergent",
                               "leaf_shape": "sagittate"}, height_m=1.0),
                           "broadleaf", [_pond()])
        self.assertEqual(d["water_m"], 0.0)
        self.assertAlmostEqual(d["height_m"], 1.0)

    def test_a_vines_block_is_left_alone(self):
        vine = {"plant_type": "vine", "x": 0, "y": 0, "height_m": 3.0,
                "canopy_m": 1.5, "drawn": {"habit": "sprawling"}}
        PH.apply_pond_habits([vine], [_pond()])
        self.assertEqual(vine["drawn"], {"habit": "sprawling"})


class ThroughBuildScene(unittest.TestCase):

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

    def _scene(self, *features):
        from src.scene_contract import build_scene
        return build_scene({"type": "FeatureCollection",
                            "properties": {"site_config": {}},
                            "features": list(features)}, year=0, wind=False)

    def _plant(self, name, dx=0.0):
        from src.project_store import plant_feature
        return plant_feature({"plant_id": self.ids[name], "common_name": name,
                              "lat": 51.05, "lng": -114.07 + dx / 70000.0})

    def _pond_feature(self):
        from src.db.structures import get_structure
        return {"type": "Feature",
                "geometry": {"type": "Point", "coordinates": [-114.07, 51.05]},
                "properties": {"element_type": "structure",
                               "struct_def": dict(get_structure("pond"))}}

    def test_a_pond_lily_in_a_pond_is_on_its_water(self):
        sc = self._scene(self._pond_feature(), self._plant("Yellow Pond-lily"))
        d = sc["plants"][0]["drawn"]
        self.assertEqual(d["body"], "floating")
        self.assertAlmostEqual(d["water_m"], PH.WATER_SURFACE_M)

    def test_beyond_the_ponds_edge_it_is_on_the_ground(self):
        sc = self._scene(self._pond_feature(),
                         self._plant("Yellow Pond-lily", dx=5.0))
        self.assertEqual(sc["plants"][0]["drawn"]["water_m"], 0.0)

    def test_the_block_is_plain_data(self):
        sc = self._scene(self._plant("Sago Pondweed"))
        json.dumps(sc)
        self.assertEqual(sc["plants"][0]["drawn"]["body"], "submerged")


class AnimalsPerchWhereThePlantIsDrawn(unittest.TestCase):
    """A bee on a pond-lily sits at the pad, not 20 cm up where the recorded
    height would put it (the V2.88 lesson, once more)."""

    def test_on_a_floating_pad(self):
        import src.scene_wildlife as W
        lily = _p({"growth_form": "floating", "leaf_shape": "cordate"},
                  plant_id=7, common_name="Yellow Pond-lily", height_m=0.2,
                  canopy_m=1.5, x=0.0, y=0.0)
        PH.apply_pond_habits([lily], [])

        def edges(pids):
            return [{"id": 1, "plant_id": 7, "taxon": "bee",
                     "common_name": "Test Bee", "scientific_name": "Bombus x",
                     "relationship": "nectar"}] if 7 in pids else []
        crit = W.wildlife_for_scene({"plants": [lily], "month": 7,
                                     "is_night": False}, fauna_edges=edges)
        self.assertTrue(crit, "the bee should visit the pond-lily in July")
        # scene_wildlife never perches lower than 10 cm, which on a pad is
        # among its flowers. At the recorded height it sat 18 cm up.
        self.assertLessEqual(crit[0]["h"], 0.10,
                             "perched in the air above the pads, at the "
                             "recorded height")


class TheData(unittest.TestCase):
    """The rows V2.90 corrected, and the vocabulary that admits them."""

    SUBMERGED = ("Elodea canadensis", "Myriophyllum sibiricum",
                 "Stuckenia pectinata", "Utricularia vulgaris")

    def test_the_submerged_plants_are_recorded_as_submerged(self):
        rows = {r["scientific_name"]: r for r in _rows()}
        for sci in self.SUBMERGED:
            with self.subTest(sci):
                self.assertEqual(rows[sci]["growth_form"], "submerged")

    def test_water_parsnip_is_an_erect_herb(self):
        rows = {r["scientific_name"]: r for r in _rows()}
        self.assertEqual(rows["Sium suave"]["growth_form"], "erect")

    def test_the_gate_knows_the_word(self):
        from src.data_quality import GROWTH_FORMS
        self.assertIn("submerged", GROWTH_FORMS)

    def test_the_seeder_agrees_with_the_data(self):
        """scripts/seed_non_woody_morphology.py wrote these values; a re-run
        must not undo them."""
        text = (_ROOT / "scripts" / "seed_non_woody_morphology.py").read_text(
            encoding="utf-8")
        for genus, form in (("Elodea", "submerged"), ("Myriophyllum", "submerged"),
                            ("Stuckenia", "submerged"),
                            ("Utricularia", "submerged"), ("Sium", "erect")):
            with self.subTest(genus):
                line = next(l for l in text.splitlines()
                            if l.strip().startswith(f'"{genus}":'))
                self.assertIn(f'"{form}")', line)


if __name__ == "__main__":
    unittest.main()

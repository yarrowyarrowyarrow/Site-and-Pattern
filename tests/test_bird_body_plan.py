"""
tests/test_bird_body_plan.py — birds with their own bodies (F174, V2.97).

The V2.87 audit found every bird drawn as one of three songbird-shaped builds,
perched inside the crown of its plant: a Sandhill Crane 0.74 m up an arrowhead
as a three-metre songbird, a Snow Goose among the stems of a saltgrass, a hawk
inside a poplar's leaves, a grouse in a 15 cm mat. And every bird, big or
small, was drawn about 2.4 times its length: the viewer sets a model's width to
the recorded wingspan, and the builds' wings were paddles.

Held here:

* the body: the build a bird gets, by its genus (``src/bird_body_plan.py``);
* the numbers the placement copies from the builds (the bpy-free
  ``scripts/blender/assetlib/bird_builds.py``), kept equal;
* where each stance puts a bird, with plain synthetic plants, and once through
  ``wildlife_for_scene`` against the real catalogue;
* the shipped model: each build exactly as wide as its span, its folded wings
  present, and each bird's drawn length, from its recorded wingspan and its
  build's proportions, near what the field guides give.

No browser. ``tests/test_accuracy_render.py`` measures the same birds as the
viewer draws them.
"""

import json
import math
import os
import sys
import tempfile
import unittest

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)
sys.path.insert(0, os.path.join(_ROOT, "scripts", "blender"))

_TMP_DIR = tempfile.mkdtemp(prefix="permadesign_birds_test_")

import src.db.plants as _plants_mod  # noqa: E402

_plants_mod._DATA_DIR = _TMP_DIR
_plants_mod._DB_PATH = os.path.join(_TMP_DIR, "permadesign_test.db")

from assetlib import bird_builds as BB  # noqa: E402  (bpy-free)
from src import bird_body_plan as BP  # noqa: E402
from src.pond_habit import POND_WATER_RX, POND_WATER_RY, WATER_SURFACE_M  # noqa: E402
from tests.test_model_assets import parse_glb  # noqa: E402

_BIRD_GLB = os.path.join(_ROOT, "html", "assets", "models", "fauna_bird.glb")

#: Field-guide lengths, bill tip to tail tip, cm: the Cornell Lab's and
#: Sibley's ranges as recalled in the session that wrote this, since the Cornell
#: site is outside its network. That is the standing of the catalogue's own
#: wingspans (bird_morphology, ``verified = 0``), so the check is wide: it is
#: there for the error it replaced, every bird at 2 to 3 times its length. Two
#: per build where the catalogue has two; tests/test_accuracy_render.py reads it.
PUBLISHED_LENGTH_CM = {
    "American Robin": (20, 28),
    "Black-capped Chickadee": (12, 15),
    "Blue Jay": (25, 30),
    "Downy Woodpecker": (14, 18),
    "Northern Flicker": (28, 31),
    "Ruby-throated Hummingbird": (7, 9),
    "Red-tailed Hawk": (45, 65),
    "Merlin": (24, 30),
    "Great Horned Owl": (46, 63),
    "Ruffed Grouse": (43, 50),
    "Willow Ptarmigan": (35, 44),
    "Northern Shoveler": (44, 51),
    "Snow Goose": (69, 83),
    "Sandhill Crane": (80, 120),
}
#: A crane is seen standing: about a metre tall, 0.8 to 1.2 m by race.
PUBLISHED_STANDING_CM = {"Sandhill Crane": (80, 120)}
SLACK = 0.15

#: The twelve the audit found drawn as songbirds in the wrong place, and the one
#: songbird genus next to them that must stay a songbird.
_EXPECTED_PLAN = {
    "Red-tailed Hawk": "raptor", "Merlin": "raptor", "American Kestrel": "raptor",
    "Great Horned Owl": "owl",
    "Ruffed Grouse": "grouse", "Willow Ptarmigan": "grouse",
    "Rock Ptarmigan": "grouse", "White-tailed Ptarmigan": "grouse",
    "Northern Shoveler": "duck", "Snow Goose": "goose", "Sandhill Crane": "crane",
    "Downy Woodpecker": "woodpecker", "Northern Flicker": "woodpecker",
    "Ruby-throated Hummingbird": "hummer", "Rufous Hummingbird": "hummer",
    "Calliope Hummingbird": "hummer",
    "American Robin": "passerine", "Black-billed Magpie": "passerine",
    "Mourning Dove": "passerine",
}


def _catalogue_birds():
    with open(os.path.join(_ROOT, "data", "fauna_master.json"), encoding="utf-8") as fh:
        return [r for r in json.load(fh) if r.get("taxon") == "bird"]


def _wingspans_m():
    with open(os.path.join(_ROOT, "data", "bird_morphology_master.json"),
              encoding="utf-8") as fh:
        return {r["common_name"]: r["wingspan_mm"] / 1000.0
                for r in json.load(fh) if r.get("wingspan_mm")}


# ── The body ─────────────────────────────────────────────────────────────────

class GenusRoutingTest(unittest.TestCase):

    def test_every_catalogue_bird_gets_a_build_the_file_carries(self):
        for r in _catalogue_birds():
            with self.subTest(r["common_name"]):
                self.assertIn(BP.plan_for(r["scientific_name"], r["common_name"]),
                              BB.BIRD_VARIANTS)

    def test_the_big_birds_get_their_own_bodies(self):
        birds = {r["common_name"]: r for r in _catalogue_birds()}
        for name, plan in _EXPECTED_PLAN.items():
            with self.subTest(name):
                self.assertIn(name, birds, "the catalogue lost this bird")
                self.assertEqual(
                    BP.plan_for(birds[name]["scientific_name"], name), plan,
                    f"{name} ({birds[name]['scientific_name']}) is drawn as a "
                    f"{BP.plan_for(birds[name]['scientific_name'], name)}")

    def test_the_genus_finds_what_the_name_words_did_and_nothing_else(self):
        """The name words could find woodpeckers and hummingbirds; the genus
        must find the same birds, so the change of key moved nobody who was
        already drawn right."""
        def by_words(name):
            n = name.lower()
            if any(w in n for w in ("woodpecker", "sapsucker", "flicker")):
                return "woodpecker"
            return "hummer" if "hummingbird" in n else "passerine"
        for r in _catalogue_birds():
            old = by_words(r["common_name"])
            new = BP.plan_for(r["scientific_name"], r["common_name"])
            if old != "passerine" or new in ("woodpecker", "hummer"):
                with self.subTest(r["common_name"]):
                    self.assertEqual(new, old)

    def test_with_no_scientific_name_the_name_words_still_answer(self):
        self.assertEqual(BP.plan_for("", "Pileated Woodpecker"), "woodpecker")
        self.assertEqual(BP.plan_for("", "Anna's Hummingbird"), "hummer")
        # ...and nothing more: no genus means no claim to a big bird's body.
        self.assertEqual(BP.plan_for("", "Snow Goose"), "passerine")

    def test_the_appearance_carries_the_build_and_how_it_sits(self):
        hawk = BP.appearance("Red-tailed Hawk", "Buteo jamaicensis")
        self.assertEqual((hawk["build"], hawk["anim"]), ("raptor", "perch"))
        self.assertEqual(hawk["perch_pitch"], BP.PERCH_PITCH["raptor"])
        hum = BP.appearance("Rufous Hummingbird", "Selasphorus rufus")
        self.assertEqual((hum["build"], hum["anim"], hum["hummer"]),
                         ("hummer", "hover", True))
        robin = BP.appearance("American Robin", "Turdus migratorius")
        self.assertNotIn("perch_pitch", robin,
                         "a songbird sits at the viewer's own 0.45")


class TheCopiesAgreeTest(unittest.TestCase):
    """bird_body_plan mirrors three numbers from the builds, which the app cannot
    import (assetlib is Blender-side). A copy that drifts puts a hawk's feet a
    hand's width off its perch, or a duck under the water."""

    def test_perch_pitch(self):
        self.assertEqual(BP.PERCH_PITCH, BB.BIRD_PERCH_PITCH)

    def test_waterline(self):
        swimmers = [b for b, s in BP.STANCE.items() if s == "water"]
        self.assertEqual(sorted(BP.WATERLINE), sorted(swimmers))
        for b in swimmers:
            self.assertAlmostEqual(BP.WATERLINE[b], BB.waterline(b), places=4)

    def test_perch_foot(self):
        tree = [b for b, s in BP.STANCE.items() if s == "tree"]
        self.assertEqual(sorted(BP.PERCH_FOOT), sorted(tree))
        for b in tree:
            self.assertAlmostEqual(BP.PERCH_FOOT[b], BB.perch_foot(b), places=4)

    def test_every_build_has_a_stance_and_the_standing_ones_have_legs(self):
        self.assertEqual(set(BP.STANCE), set(BB.BIRD_VARIANTS))
        standing = {b for b, s in BP.STANCE.items() if s in ("ground", "water")}
        self.assertEqual(standing, set(BB.GROUND_BUILDS))
        for b in BB.BIRD_VARIANTS:
            with self.subTest(b):
                self.assertEqual("legs" in BB.BIRD_BUILDS[b], b in standing,
                                 "a standing build's origin is its feet")


# ── Where it stands ──────────────────────────────────────────────────────────

def _plant(pid, x, y, h, canopy, ptype="shrub", **kw):
    return dict({"plant_id": pid, "common_name": f"plant {pid}", "x": x, "y": y,
                 "height_m": h, "canopy_m": canopy, "plant_type": ptype}, **kw)


def _bird(name, sci, span_m, seed=4242):
    app = BP.appearance(name, sci)
    return {"kind": "bird", "name": name, "x": 0.0, "y": 0.0, "h": 1.0,
            "seed": seed, "on": "anchor", "on_id": 1, "app": app,
            "size": {"m": span_m, "true_m": span_m, "axis": "x"},
            "route": [[0.0, 0.0, 1.0]]}


def _height(p):
    return p["height_m"]


def _pond(x, y, size=6.0):
    return {"struct_id": "pond", "x": x, "y": y, "size_m": size}


class StanceTest(unittest.TestCase):

    def test_a_songbird_is_left_where_it_was(self):
        robin = _bird("American Robin", "Turdus migratorius", 0.34)
        before = json.dumps(robin, sort_keys=True)
        shrub = _plant(1, 0, 0, 3.0, 2.0)
        self.assertTrue(BP.place(robin, shrub, [shrub], {}, [shrub], _height))
        self.assertEqual(json.dumps(robin, sort_keys=True), before)

    # tree ────────────────────────────────────────────────────────────────────

    def test_a_hawk_sits_on_the_top_of_its_tree(self):
        hawk = _bird("Red-tailed Hawk", "Buteo jamaicensis", 1.22)
        poplar = _plant(1, 3.0, 4.0, 20.0, 9.0, "tree")
        self.assertTrue(BP.place(hawk, poplar, [poplar], {}, [poplar], _height))
        self.assertEqual((hawk["x"], hawk["y"]), (3.0, 4.0))
        self.assertAlmostEqual(hawk["h"], 20.0 + BP.PERCH_FOOT["raptor"] * 1.22,
                               places=2)
        self.assertEqual(hawk["app"]["anim"], "perch")

    def test_it_hunts_from_tall_trees_only_and_never_a_shrub(self):
        hawk = _bird("Red-tailed Hawk", "Buteo jamaicensis", 1.22)
        poplar = _plant(1, 0, 0, 20.0, 9.0, "tree")
        spruce = _plant(2, 12, 0, 15.0, 5.0, "tree")
        sapling = _plant(3, 5, 0, 2.0, 1.0, "tree")
        dead = _plant(4, 7, 0, 18.0, 6.0, "tree", health_state="dead")
        shrub = _plant(5, 3, 3, 4.0, 3.0, "shrub")
        plants = [poplar, spruce, sapling, dead, shrub]
        BP.place(hawk, poplar, plants, {}, [poplar], _height)
        tops = {(p["x"], p["y"]): p for p in plants}
        for x, y, h in hawk["route"]:
            p = tops.get((x, y))
            self.assertIsNotNone(p, f"a waypoint at ({x}, {y}) is on no plant's top")
            self.assertIn(p["plant_id"], (1, 2), "a sapling, a dead tree or a shrub")
            self.assertGreater(h, p["height_m"])

    def test_with_its_own_tree_too_young_it_sits_on_another_of_its_trees(self):
        hawk = _bird("Red-tailed Hawk", "Buteo jamaicensis", 1.22)
        young = _plant(1, 0, 0, 2.4, 1.2, "tree", common_name="young poplar")
        old = _plant(2, 8, 0, 18.0, 8.0, "tree", common_name="old poplar")
        BP.place(hawk, young, [young, old], {}, [young, old], _height)
        self.assertEqual((hawk["x"], hawk["y"]), (8, 0))
        self.assertEqual((hawk["on"], hawk["on_id"]), ("old poplar", 2),
                         "the label names the tree it is sitting on")

    def test_the_label_takes_the_relationship_to_the_tree_it_is_on(self):
        owl = _bird("Great Horned Owl", "Bubo virginianus", 1.15)
        owl["rel"] = "cover"
        spruce = _plant(1, 0, 0, 2.5, 1.0, "tree", common_name="White Spruce")
        aspen = _plant(2, 8, 2, 9.0, 4.0, "tree", common_name="Trembling Aspen")
        self.assertTrue(BP.place(owl, spruce, [spruce, aspen], {}, [spruce, aspen],
                                 _height, None, {1: "cover", 2: "nesting"}))
        self.assertEqual((owl["on"], owl["rel"]), ("Trembling Aspen", "nesting"))

    def test_with_no_tall_tree_of_its_own_a_hawk_circles_overhead(self):
        hawk = _bird("Red-tailed Hawk", "Buteo jamaicensis", 1.22)
        young = _plant(1, 0, 0, 2.4, 1.2, "tree")
        other = _plant(2, 10, 0, 18.0, 8.0, "tree")    # tall, but not its tree
        self.assertTrue(BP.place(hawk, young, [young, other], {}, [young], _height))
        self.assertEqual(hawk["app"]["anim"], "soar")
        self.assertEqual(len(hawk["route"]), 8)
        cx, cy = 5.0, 0.0                               # over the design
        for x, y, h in hawk["route"]:
            self.assertEqual(h, BP.SOAR_M)
            self.assertTrue(BP._SOAR_R[0] - 0.01 <= math.hypot(x - cx, y - cy)
                            <= BP._SOAR_R[1] + 0.01)

    def test_an_owl_with_no_tree_is_not_drawn(self):
        owl = _bird("Great Horned Owl", "Bubo virginianus", 1.15)
        young = _plant(1, 0, 0, 2.4, 1.2, "tree")
        self.assertFalse(BP.place(owl, young, [young], {}, [young], _height),
                         "an owl circling a yard is an owl invented (P9)")

    def test_two_raptors_never_share_a_top(self):
        taken = set()
        poplar = _plant(1, 0, 0, 20.0, 9.0, "tree")
        hawk = _bird("Red-tailed Hawk", "Buteo jamaicensis", 1.22)
        merlin = _bird("Merlin", "Falco columbarius", 0.61, seed=77)
        BP.place(hawk, poplar, [poplar], {}, [poplar], _height, taken)
        BP.place(merlin, poplar, [poplar], {}, [poplar], _height, taken)
        self.assertEqual(hawk["app"]["anim"], "perch")
        self.assertEqual(merlin["app"]["anim"], "soar",
                         "the second raptor on a one-tree design flies")

    # ground ──────────────────────────────────────────────────────────────────

    def test_a_grouse_stands_in_a_mat_and_beside_a_shrub(self):
        grouse = _bird("Ruffed Grouse", "Bonasa umbellus", 0.56)
        mat = _plant(1, 0, 0, 0.15, 1.2, "groundcover")
        shrub = _plant(2, 6, 0, 4.0, 3.0, "shrub")
        BP.place(grouse, mat, [mat, shrub], {}, [mat, shrub], _height)
        self.assertEqual(grouse["app"]["anim"], "walk")
        self.assertEqual(grouse["h"], 0.0)
        (x0, y0, _), (x1, y1, _) = grouse["route"][:2]
        self.assertLessEqual(math.hypot(x0, y0), 1.2 * 0.3 + 0.01,   # 1 cm rounding
                             "in the bearberry it eats")
        self.assertGreaterEqual(math.hypot(x1 - 6, y1), 3.0 / 2,
                                "at the saskatoon's edge, not inside it")

    def test_every_ground_waypoint_is_on_the_ground(self):
        crane = _bird("Sandhill Crane", "Grus canadensis", 1.98)
        plants = [_plant(i, i * 3.0, 0, 1.0, 0.6, "aquatic") for i in range(1, 6)]
        BP.place(crane, plants[0], plants, {}, plants[:3], _height)
        self.assertGreater(len(crane["route"]), 1, "it walks between its plants")
        self.assertTrue(all(h == 0.0 for _x, _y, h in crane["route"]))

    # water ───────────────────────────────────────────────────────────────────

    def test_with_a_pond_a_goose_floats_on_its_water(self):
        goose = _bird("Snow Goose", "Anser caerulescens", 1.45)
        grass = _plant(1, 0, 0, 0.4, 0.5, "grass")
        pond = _pond(9.0, 2.0)
        BP.place(goose, grass, [grass], {"structures": [pond]}, [grass], _height)
        self.assertEqual(goose["app"]["anim"], "walk")
        rx, ry = POND_WATER_RX * 6.0, POND_WATER_RY * 6.0
        for x, y, h in goose["route"]:
            self.assertLess(((x - 9.0) / rx) ** 2 + ((y - 2.0) / ry) ** 2, 1.0,
                            "off the water")
            self.assertAlmostEqual(
                h, WATER_SURFACE_M - BP.WATERLINE["goose"] * 1.45, places=3)

    def test_with_no_pond_a_duck_walks_like_a_ground_bird(self):
        duck = _bird("Northern Shoveler", "Anas clypeata", 0.76)
        grass = _plant(1, 0, 0, 0.4, 0.5, "grass")
        BP.place(duck, grass, [grass], {"structures": []}, [grass], _height)
        self.assertEqual(duck["app"]["anim"], "walk")
        self.assertEqual(duck["h"], 0.0)


class ThroughTheSceneTest(unittest.TestCase):
    """The same stances from the real catalogue, through build_scene and
    wildlife_for_scene, each bird alone with a plant it is tied to."""

    @classmethod
    def setUpClass(cls):
        from src.db.plants import get_connection, init_db
        init_db()
        conn = get_connection()
        try:
            cls.plant_id = {r["common_name"]: r["id"] for r in conn.execute(
                "SELECT id, common_name FROM plants")}
            cls.fauna_id = {r["common_name"]: r["id"] for r in conn.execute(
                "SELECT id, common_name FROM fauna WHERE taxon = 'bird'")}
        finally:
            conn.close()

    def _one(self, bird, plant, pond=False, night=False):
        from src.db.fauna import fauna_for_plants
        from src.db.structures import get_structure
        from src.project_store import plant_feature
        from src.scene_contract import build_scene
        from src.scene_wildlife import wildlife_for_scene
        feats = [plant_feature({"plant_id": self.plant_id[plant], "common_name": plant,
                                "lat": 51.05, "lng": -114.07})]
        if pond:
            feats.append({"type": "Feature",
                          "geometry": {"type": "Point",
                                       "coordinates": [-114.07 + 0.0001, 51.05]},
                          "properties": {"element_type": "structure",
                                         "struct_def": dict(get_structure("pond"))}})
        sc = build_scene({"type": "FeatureCollection", "properties": {"site_config": {}},
                          "features": feats}, year=0, wind=False)
        sc["month"], sc["is_night"] = 7, night
        fid = self.fauna_id[bird]
        found = wildlife_for_scene(
            sc, fauna_edges=lambda ids: [r for r in fauna_for_plants(ids)
                                         if r.get("id") == fid])
        self.assertEqual(len(found), 1, f"{bird} was not placed on {plant}")
        return found[0], sc

    def test_the_hawk_is_on_the_poplar_top(self):
        hawk, sc = self._one("Red-tailed Hawk", "Balsam Poplar")
        tree = sc["plants"][0]
        self.assertEqual((hawk["x"], hawk["y"]), (tree["x"], tree["y"]))
        self.assertGreater(hawk["h"], tree["height_m"])
        self.assertLess(hawk["h"], tree["height_m"] + 0.3)
        self.assertEqual(hawk["app"]["build"], "raptor")

    def test_a_young_spruce_sends_the_owl_to_the_aspen_it_nests_in(self):
        """The owl's best-ranked tie is cover in White Spruce; it also nests in
        Trembling Aspen. In year 1 the spruce is under 3 m and the aspen is not,
        so the owl belongs on the aspen, not out of the scene."""
        from src.db.fauna import fauna_for_plants
        from src.project_store import plant_feature
        from src.scene_contract import build_scene
        from src.scene_wildlife import wildlife_for_scene
        feats = [plant_feature({"plant_id": self.plant_id[n], "common_name": n,
                                "lat": 51.05, "lng": -114.07 + dx / 70000.0})
                 for n, dx in (("White Spruce", 0), ("Trembling Aspen", 8))]
        sc = build_scene({"type": "FeatureCollection", "properties": {"site_config": {}},
                          "features": feats}, year=1, wind=False)
        sc["month"], sc["is_night"] = 7, True
        heights = {p["common_name"]: p["height_m"] for p in sc["plants"]}
        self.assertLess(heights["White Spruce"], BP.TREE_MIN_M)
        self.assertGreaterEqual(heights["Trembling Aspen"], BP.TREE_MIN_M)
        fid = self.fauna_id["Great Horned Owl"]
        owl = [c for c in wildlife_for_scene(
            sc, fauna_edges=lambda ids: [r for r in fauna_for_plants(ids)
                                         if r.get("id") == fid])]
        self.assertEqual(len(owl), 1, "the owl was dropped with a tall aspen present")
        self.assertEqual((owl[0]["on"], owl[0]["rel"], owl[0]["app"]["anim"]),
                         ("Trembling Aspen", "nesting", "perch"))
        self.assertGreater(owl[0]["h"], heights["Trembling Aspen"])

    def test_the_grouse_is_on_the_ground_by_its_bearberry(self):
        grouse, _sc = self._one("Ruffed Grouse", "Bearberry")
        self.assertEqual((grouse["h"], grouse["app"]["anim"]), (0.0, "walk"))

    def test_the_goose_is_on_the_pond(self):
        goose, sc = self._one("Snow Goose", "Saltgrass", pond=True)
        pond = sc["structures"][0]
        self.assertGreater(math.hypot(goose["x"] - sc["plants"][0]["x"],
                                      goose["y"] - sc["plants"][0]["y"]), 3.0,
                           "still in the saltgrass, not on the pond 7 m away")
        self.assertLess(goose["h"], WATER_SURFACE_M, "floating, sunk to its waterline")
        self.assertLess(math.hypot(goose["x"] - pond["x"], goose["y"] - pond["y"]),
                        POND_WATER_RX * pond["size_m"])

    def test_the_label_says_what_the_size_is(self):
        crane, _sc = self._one("Sandhill Crane", "Broad-leaved Arrowhead")
        self.assertEqual(crane["size"].get("what"), "wingspan")
        from src.scene_wildlife import size_sentence
        self.assertTrue(size_sentence(crane["size"]).startswith("wingspan 198 cm"),
                        size_sentence(crane["size"]))


# ── The shipped model ────────────────────────────────────────────────────────

def _trs(node):
    """A glTF node's local matrix, rows of four."""
    if "matrix" in node:
        m = node["matrix"]
        return [[m[c * 4 + r] for c in range(4)] for r in range(4)]
    tx, ty, tz = node.get("translation", (0.0, 0.0, 0.0))
    qx, qy, qz, qw = node.get("rotation", (0.0, 0.0, 0.0, 1.0))
    sx, sy, sz = node.get("scale", (1.0, 1.0, 1.0))
    r = ((1 - 2 * (qy * qy + qz * qz), 2 * (qx * qy - qz * qw), 2 * (qx * qz + qy * qw)),
         (2 * (qx * qy + qz * qw), 1 - 2 * (qx * qx + qz * qz), 2 * (qy * qz - qx * qw)),
         (2 * (qx * qz - qy * qw), 2 * (qy * qz + qx * qw), 1 - 2 * (qx * qx + qy * qy)))
    return [[r[0][0] * sx, r[0][1] * sy, r[0][2] * sz, tx],
            [r[1][0] * sx, r[1][1] * sy, r[1][2] * sz, ty],
            [r[2][0] * sx, r[2][1] * sy, r[2][2] * sz, tz],
            [0.0, 0.0, 0.0, 1.0]]


def _mul(a, b):
    return [[sum(a[i][k] * b[k][j] for k in range(4)) for j in range(4)]
            for i in range(4)]


def _extent(gltf, root, skip=()):
    """(lo, hi) of every mesh under ``root`` in the root's frame, from each
    POSITION accessor's box carried through the node transforms, leaving out
    nodes whose names end with anything in ``skip``."""
    nodes = gltf["nodes"]
    lo, hi = [math.inf] * 3, [-math.inf] * 3
    eye = [[1.0 if i == j else 0.0 for j in range(4)] for i in range(4)]
    stack = [(root, eye)]
    while stack:
        i, parent = stack.pop()
        n = nodes[i]
        if any(n.get("name", "").endswith(s) for s in skip):
            continue
        m = _mul(parent, _trs(n)) if i != root else eye
        for prim in (gltf["meshes"][n["mesh"]]["primitives"] if "mesh" in n else []):
            acc = gltf["accessors"][prim["attributes"]["POSITION"]]
            for cx in (acc["min"][0], acc["max"][0]):
                for cy in (acc["min"][1], acc["max"][1]):
                    for cz in (acc["min"][2], acc["max"][2]):
                        p = [m[r][0] * cx + m[r][1] * cy + m[r][2] * cz + m[r][3]
                             for r in range(3)]
                        lo = [min(a, b) for a, b in zip(lo, p)]
                        hi = [max(a, b) for a, b in zip(hi, p)]
        stack.extend((c, m) for c in n.get("children", []))
    return lo, hi


@unittest.skipUnless(os.path.isfile(_BIRD_GLB), "no generated bird model")
class ShippedBirdModelTest(unittest.TestCase):
    """glTF frame: +x the bird's right, +y up, -z forward (Blender's +y)."""

    @classmethod
    def setUpClass(cls):
        cls.gltf, _bin = parse_glb(_BIRD_GLB)
        cls.root = {cls.gltf["nodes"][i]["name"]: i
                    for i in cls.gltf["scenes"][0]["nodes"]}

    def _measure(self, build):
        """(span, length, height, lowest point) of one build, in its own units;
        all but the span without the spread wings, which hide on a perch."""
        lo, hi = _extent(self.gltf, self.root[build])
        blo, bhi = _extent(self.gltf, self.root[build], skip=("_WingL", "_WingR"))
        return hi[0] - lo[0], bhi[2] - blo[2], bhi[1] - blo[1], blo[1]

    def test_every_build_is_in_the_file_with_both_pairs_of_wings(self):
        names = {n.get("name", "") for n in self.gltf["nodes"]}
        for b in BB.BIRD_VARIANTS:
            with self.subTest(b):
                self.assertIn(b, self.root)
                for part in ("WingL", "WingR", "FoldL", "FoldR"):
                    self.assertIn(f"{b}_{part}", names)

    def test_each_build_is_exactly_as_wide_as_its_span(self):
        """The viewer scales a bird until its width is the recorded wingspan;
        that is right only if the model's width IS its wingspan."""
        for b in BB.BIRD_VARIANTS:
            with self.subTest(b):
                span, length, _h, _low = self._measure(b)
                self.assertAlmostEqual(span, BB.span(b), delta=0.01 * BB.span(b))
                self.assertGreater(span / length, 1.2,
                                   "the wings are paddles again: V2.46's 0.65")

    def test_a_standing_build_has_its_feet_at_its_origin(self):
        for b in BB.BIRD_VARIANTS:
            with self.subTest(b):
                low = self._measure(b)[3]
                if b in BB.GROUND_BUILDS:
                    self.assertAlmostEqual(low, 0.0, delta=0.005)
                else:
                    self.assertLess(low, -0.05, "a percher is centred on its body")

    def test_each_bird_is_drawn_near_its_published_length(self):
        spans = _wingspans_m()
        birds = {r["common_name"]: r for r in _catalogue_birds()}
        for name, (lo, hi) in PUBLISHED_LENGTH_CM.items():
            b = BP.plan_for(birds[name]["scientific_name"], name)
            span, length, height, _low = self._measure(b)
            cm = length / span * spans[name] * 100
            with self.subTest(name):
                self.assertGreaterEqual(cm, lo * (1 - SLACK),
                                        f"{name} ({b}) drawn {cm:.1f} cm long")
                self.assertLessEqual(cm, hi * (1 + SLACK),
                                     f"{name} ({b}) drawn {cm:.1f} cm long")
        for name, (lo, hi) in PUBLISHED_STANDING_CM.items():
            b = BP.plan_for(birds[name]["scientific_name"], name)
            span, _length, height, _low = self._measure(b)
            cm = height / span * spans[name] * 100
            with self.subTest(name + " standing"):
                self.assertTrue(lo * (1 - SLACK) <= cm <= hi * (1 + SLACK),
                                f"{name} stands {cm:.0f} cm tall")


if __name__ == "__main__":
    unittest.main()

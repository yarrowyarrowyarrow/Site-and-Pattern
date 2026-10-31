"""
tests/test_fauna_body_plan.py — the 3D scene draws an animal as what it IS
(V2.88).

Three things the V2.87 model audit measured, each pinned here:

  * **Insects by group, not by common-name words.** 347 of the 408
    ``other_insect`` rows carry their binomial as their common name, so the old
    keyword test drew 208 wasps, beetles, bugs and ants as the fallback
    hoverfly. ``src.fauna_body_plan`` reads the description, which names the
    group in every shipped row.
  * **Moths as moths.** ``lepidoptera_attributes.kind`` is recorded for all 343
    lepidoptera; the scene guessed it from the name and drew 159 moths as
    butterflies.
  * **Not the alphabet.** The scene took the first eight bees, seven leps... by
    common name, so 65% of a daytime design's animals started with "A".
"""

import collections
import json
import os
import random
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_TMP_DIR = tempfile.mkdtemp(prefix="permadesign_bodyplan_test_")

import src.db.plants as _plants_mod  # noqa: E402

_plants_mod._DATA_DIR = _TMP_DIR
_plants_mod._DB_PATH = os.path.join(_TMP_DIR, "permadesign_test.db")

from src.db.plants import get_connection, init_db  # noqa: E402
from src import fauna_body_plan as B  # noqa: E402
import src.scene_wildlife as W  # noqa: E402

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _data(name):
    with open(os.path.join(_ROOT, "data", name), encoding="utf-8") as fh:
        return json.load(fh)


_FAUNA = _data("fauna_master.json")
_INSECTS = [r for r in _FAUNA if r.get("taxon") == "other_insect"]


def _group(row):
    return B.insect_group(row["scientific_name"], row["common_name"],
                          row.get("description") or "")


class TestEveryInsectHasAGroup(unittest.TestCase):

    def test_no_insect_falls_through(self):
        """A new insect has to be looked at, not trusted: if its description
        names no group this module knows, it would silently get the fallback
        hoverfly again — which is exactly the defect being fixed."""
        missing = [r["scientific_name"] for r in _INSECTS
                   if not B.is_known(r["scientific_name"], r["common_name"],
                                     r.get("description") or "")]
        self.assertEqual(missing, [], "insects no rule recognises: add a rule")

    def test_a_genus_is_one_body_plan(self):
        by_genus = collections.defaultdict(set)
        for r in _INSECTS:
            by_genus[r["scientific_name"].split(" ")[0]].add(_group(r))
        split = {g: s for g, s in by_genus.items() if len(s) > 1}
        self.assertEqual(split, {}, "one genus filed under two body plans")

    def test_the_groups_the_audit_counted(self):
        """The counts the V2.87 audit reported, so a rule change that moves a
        whole group shows up as a number rather than as a picture."""
        c = collections.Counter(_group(r) for r in _INSECTS)
        self.assertEqual(c["beetle"] + c["lady_beetle"], 78)
        self.assertEqual(c["wasp"] + c["social_wasp"] + c["sawfly"], 98)
        self.assertEqual(c["bug"], 33)
        self.assertEqual(c["ant"], 6)
        self.assertEqual(c["grasshopper"], 7)

    def test_named_cases(self):
        """Rows chosen because their words overlap another group's."""
        want = {
            "Dolichovespula arenaria": "social_wasp",     # Aerial Yellowjacket
            "Evodinus monticola": "beetle",               # a flower longhorn
            "Macrosiphum albifrons": "bug",               # Lupine Aphid
            "Formica fusca": "ant",
            "Allograpta obliqua": "hoverfly",
            "Sceliphron caementarium": "wasp",            # mud dauber
            "Aphilanthops frigidus": "wasp",              # "Ant-hunting wasps"
            "Cyrtophorus verrucosus": "beetle",           # "Ant-mimicking longhorns"
            "Coccinella novemnotata": "lady_beetle",
        }
        rows = {r["scientific_name"]: r for r in _INSECTS}
        checked = 0
        for sci, group in want.items():
            if sci not in rows:          # a later catalogue edit may drop one
                continue
            self.assertEqual(_group(rows[sci]), group, sci)
            checked += 1
        self.assertGreaterEqual(checked, 7, "the named cases left the catalogue")


class TestInsectsAreDrawnAsTheirGroup(unittest.TestCase):

    def test_beetles_are_beetles(self):
        """The 63 beetles the name test drew as hoverflies. Every beetle and
        lady beetle in the catalogue now gets the beetle model."""
        for r in _INSECTS:
            if _group(r) in ("beetle", "lady_beetle"):
                app = W._appearance_for(r)
                self.assertEqual(app["kind"], "beetle", r["scientific_name"])

    def test_no_wasp_or_ant_is_a_yellow_hoverfly_by_default(self):
        """Wasps stay on the fly model until they have their own (backlog C1),
        but they are flagged as stand-ins; walkers go on the beetle's crawl."""
        for r in _INSECTS:
            g = _group(r)
            app = W._appearance_for(r)
            self.assertEqual(app["group"], g)
            if g in ("wasp", "social_wasp", "sawfly", "bug", "ant",
                     "grasshopper", "thrips"):
                self.assertTrue(app.get("interim"), r["scientific_name"])
            if g in ("bug", "ant", "grasshopper", "thrips"):
                self.assertEqual(app["kind"], "beetle", r["scientific_name"])

    def test_group_sizes_are_what_the_label_prints(self):
        """With no record, the hover tip's "N mm" comes from the group, not
        from the model's kind: a grasshopper is not an 8 mm beetle."""
        hopper = next(r for r in _INSECTS if _group(r) == "grasshopper")
        app = W._appearance_for(hopper)
        s = W._size_for(hopper, app)
        self.assertAlmostEqual(s["true_m"], B.typical_size_m("grasshopper"))
        self.assertGreaterEqual(s["m"], s["true_m"])


class TestLepidopteraKind(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        attrs = [r for r in _data("lepidoptera_attributes_master.json")
                 if "scientific_name" in r]
        cls.kind = {r["scientific_name"]: r.get("kind") for r in attrs}
        cls.leps = [r for r in _FAUNA if r.get("taxon") == "lepidoptera"]

    def test_every_recorded_moth_is_drawn_as_a_moth(self):
        for r in self.leps:
            k = self.kind.get(r["scientific_name"])
            app = W._appearance_for(r, None, lep_kind=k)
            if k == "moth":
                self.assertEqual(app["kind"], "moth", r["scientific_name"])
            elif k == "skipper":
                self.assertEqual(app["kind"], "butterfly", r["scientific_name"])
                self.assertEqual(app["build"], "skipper", r["scientific_name"])
            elif k == "butterfly":
                self.assertEqual(app["kind"], "butterfly", r["scientific_name"])

    def test_the_name_is_only_the_fallback(self):
        row = {"taxon": "lepidoptera", "common_name": "Agrotis ipsilon",
               "scientific_name": "Agrotis ipsilon"}
        self.assertEqual(W._appearance_for(row)["kind"], "butterfly")
        self.assertEqual(W._appearance_for(row, lep_kind="moth")["kind"], "moth")

    def test_a_skipper_flies_like_a_skipper(self):
        """flight_model has had a skipper wingbeat since V2.45; the scene could
        never ask for it because it only passed moth or butterfly."""
        row = {"taxon": "lepidoptera", "common_name": "Hesperia comma",
               "scientific_name": "Hesperia comma"}
        skip = W._flight_for(row, lep_kind="skipper")
        fly = W._flight_for(row, lep_kind="butterfly")
        if not skip or not fly:
            self.skipTest("flight_model unavailable")
        self.assertNotEqual(skip["true_hz"], fly["true_hz"])


class TestChoosingTheAnimals(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        init_db()
        conn = get_connection()
        try:
            cls.plants = [dict(r) for r in conn.execute(
                """SELECT DISTINCT p.id AS plant_id, p.common_name,
                          p.mature_height_meters AS height_m
                   FROM plants p JOIN plant_fauna pf ON pf.plant_id = p.id""")]
        finally:
            conn.close()

    def _scene(self, plants, night=False):
        return {"month": 7, "is_night": night, "plants": [
            dict(p, x=(i % 6) * 2.0, y=(i // 6) * 2.0, canopy_m=1.0,
                 height_m=float(p["height_m"] or 0.5))
            for i, p in enumerate(plants)]}

    def test_the_alphabet_does_not_choose(self):
        """The audit's own measure: across many designs, the share of animals
        whose name starts with "A" was 65% (13% of the catalogue). A neutral
        choice lands near the catalogue share."""
        rng = random.Random(88)
        first, total = collections.Counter(), 0
        for _ in range(40):
            crit = W.wildlife_for_scene(
                self._scene(rng.sample(self.plants, min(20, len(self.plants)))))
            for c in crit:
                first[c["name"][:1].upper()] += 1
                total += 1
        self.assertGreater(total, 100)
        self.assertLess(first["A"] / total, 0.35,
                        f"{first['A']} of {total} animals start with A")

    def test_one_design_is_stable_and_two_differ(self):
        rng = random.Random(7)
        a = self._scene(rng.sample(self.plants, 20))
        b = self._scene(rng.sample(self.plants, 20))
        names = lambda s: [c["name"] for c in W.wildlife_for_scene(s)]
        self.assertEqual(names(a), names(a))
        self.assertNotEqual(set(names(a)), set(names(b)))

    def test_night_moths_are_moths(self):
        """The case that was 76% wrong: at night, every lepidopteran the scene
        places and records as a moth is drawn as one."""
        from src.db.fauna import lep_kinds
        kinds = lep_kinds()
        leps = sum(1 for r in _FAUNA if r.get("taxon") == "lepidoptera")
        self.assertEqual(len(kinds), leps, "a lepidopteran lost its kind")
        conn = get_connection()
        try:
            fid = {row[1]: row[0] for row in conn.execute(
                "SELECT id, common_name FROM fauna WHERE taxon='lepidoptera'")}
        finally:
            conn.close()
        rng = random.Random(3)
        seen = 0
        for _ in range(15):
            for c in W.wildlife_for_scene(
                    self._scene(rng.sample(self.plants, 20), night=True)):
                k = kinds.get(fid.get(c["name"]))
                if k == "moth":
                    self.assertEqual(c["kind"], "moth", c["name"])
                    seen += 1
        self.assertGreater(seen, 0, "no moth placed at night in 15 designs")


if __name__ == "__main__":
    unittest.main()

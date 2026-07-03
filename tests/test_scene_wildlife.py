"""
tests/test_scene_wildlife.py

Covers ``src.scene_wildlife`` (V2.12) — placing the animals a design's plants
support into the 3D scene, each on/near a plant it uses and with a per-species
appearance spec:

  * creatures are placed only from DOCUMENTED plant↔fauna edges to present plants
  * per-taxon caps + the global cap are respected; the mix is diverse
  * placement is deterministic (stable across re-pushes)
  * every appearance colour is a valid 6-digit hex (the viewer parses these)
  * appearance_for_fauna styles a bee by genus (metallic green sweat bee) and a
    lepidopteran by kind; non-bee/lep taxa still get a look
  * nocturnal bats are skipped from the daytime scene (P9 honesty)
  * an empty / edge-less scene yields no wildlife
"""

import os
import re
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_TMP_DIR = tempfile.mkdtemp(prefix="permadesign_wild_test_")

import src.db.plants as _plants_mod  # noqa: E402

_plants_mod._DATA_DIR = _TMP_DIR
_plants_mod._DB_PATH  = os.path.join(_TMP_DIR, "permadesign_test.db")

from src.db.plants import init_db, get_connection  # noqa: E402
import src.scene_wildlife as W  # noqa: E402

_HEX = re.compile(r"#[0-9a-fA-F]{6}")


def _scene_with_edged_plants(limit=60):
    """A synthetic scene whose plants are real DB plants that carry fauna edges."""
    conn = get_connection()
    try:
        rows = conn.execute(
            """SELECT DISTINCT p.id, p.common_name, p.plant_type,
                      p.mature_height_meters, p.mature_canopy_m
               FROM plants p JOIN plant_fauna pf ON pf.plant_id = p.id
               ORDER BY p.plant_type, p.common_name LIMIT ?""", (limit,)).fetchall()
    finally:
        conn.close()
    plants = []
    for i, (pid, name, ptype, h, c) in enumerate(rows):
        plants.append({
            "plant_id": pid, "common_name": name, "plant_type": ptype or "herb",
            "x": (i % 10) * 2.0 - 10.0, "y": (i // 10) * 2.0 - 6.0,
            "height_m": float(h or 1.0), "canopy_m": float(c or 1.0),
        })
    return {"plants": plants}


class TestSceneWildlife(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        init_db()
        cls.scene = _scene_with_edged_plants()
        cls.crit = W.wildlife_for_scene(cls.scene)

    def test_places_creatures(self):
        self.assertTrue(self.crit, "a plant-rich scene should draw wildlife")
        self.assertLessEqual(len(self.crit), W._TOTAL_CAP)

    def test_on_present_plants_only(self):
        present = {p["plant_id"] for p in self.scene["plants"]}
        names = {p["common_name"] for p in self.scene["plants"]}
        for c in self.crit:
            self.assertIn(c["on"], names)         # anchored on a scene plant
            self.assertIn(c["kind"], ("bee", "butterfly", "moth", "bird",
                                      "fly", "beetle", "mammal"))

    def test_per_taxon_caps(self):
        from collections import Counter
        # kind → taxon is many-to-one; count by the taxon caps via kinds.
        kinds = Counter(c["kind"] for c in self.crit)
        self.assertLessEqual(kinds.get("bee", 0), W._TAXON_CAP["bee"])
        self.assertLessEqual(kinds.get("bird", 0), W._TAXON_CAP["bird"])
        # A diverse yard shows more than one taxon.
        group = {"bee": "bee", "butterfly": "lep", "moth": "lep", "bird": "bird",
                 "fly": "ins", "beetle": "ins", "mammal": "mam"}
        self.assertGreaterEqual(len({group[k] for k in kinds}), 2)

    def test_no_clumping(self):
        # The de-clump fix (V2.12): no two creatures share a spot; the relaxation
        # pass keeps them at least ~min_sep apart in the ground plane so a rich
        # scene reads as individuals, not a blob.
        import math
        pts = [(c["x"], c["y"]) for c in self.crit]
        worst = min((math.hypot(pts[i][0] - pts[j][0], pts[i][1] - pts[j][1])
                     for i in range(len(pts)) for j in range(i + 1, len(pts))),
                    default=99)
        self.assertGreaterEqual(worst, 0.8, "creatures are clumping together")

    def test_spread_across_plants(self):
        # A species that uses several present plants shouldn't pile every animal
        # onto one keystone — creatures anchor to more than one plant.
        anchors = {c["on"] for c in self.crit}
        self.assertGreaterEqual(len(anchors), 3)

    def test_routes_emitted(self):
        # Every creature carries a route (≥1 waypoint); a species that uses
        # several present plants gets a multi-waypoint route so the viewer can
        # move it between them (V2.13).
        for c in self.crit:
            self.assertIn("route", c)
            self.assertGreaterEqual(len(c["route"]), 1)
            for wp in c["route"]:
                self.assertEqual(len(wp), 3)     # [x, y, h]
        self.assertTrue(any(len(c["route"]) > 1 for c in self.crit),
                        "expected some multi-plant routes")

    def test_deterministic(self):
        again = W.wildlife_for_scene(self.scene)
        self.assertEqual([(c["name"], c["x"], c["y"]) for c in self.crit],
                         [(c["name"], c["x"], c["y"]) for c in again])

    def test_all_hex_valid(self):
        for c in self.crit:
            for k, v in c["app"].items():
                if isinstance(v, str) and v.startswith("#"):
                    self.assertRegex(v, _HEX, f"{c['name']} {k}={v}")

    def test_no_bats(self):
        # Bats are nocturnal → skipped by day (they'd be a mammal 'bat' form).
        for c in self.crit:
            self.assertNotIn("bat", c["name"].lower())

    def test_empty_scene(self):
        self.assertEqual(W.wildlife_for_scene({"plants": []}), [])
        self.assertEqual(W.wildlife_for_scene({}), [])

    def test_edgeless_plants(self):
        # Plants with ids that carry no edges → no creatures.
        scene = {"plants": [{"plant_id": -999, "common_name": "x", "x": 0, "y": 0,
                             "height_m": 1, "canopy_m": 1}]}
        self.assertEqual(W.wildlife_for_scene(scene), [])


class TestSeasonalDiel(unittest.TestCase):
    """V2.12: only show creatures that are actually out — by month and day/night."""

    @classmethod
    def setUpClass(cls):
        init_db()
        cls.base = _scene_with_edged_plants()

    def _scene(self, month, night):
        return dict(self.base, month=month, is_night=night)

    def test_night_swaps_day_for_nocturnal(self):
        day = W.wildlife_for_scene(self._scene(7, False))
        night = W.wildlife_for_scene(self._scene(7, True))
        day_kinds = {c["kind"] for c in day}
        night_kinds = {c["kind"] for c in night}
        # Day has bees/butterflies; night is moths + mammals (bats/mice), no bees.
        self.assertIn("bee", day_kinds)
        self.assertNotIn("bee", night_kinds)
        self.assertTrue({"moth", "mammal"} & night_kinds,
                        "night should bring out moths and/or bats")

    def test_bats_only_at_night(self):
        day = W.wildlife_for_scene(self._scene(7, False))
        night = W.wildlife_for_scene(self._scene(7, True))
        self.assertFalse(any("bat" in c["name"].lower() for c in day))
        # Bats appear at night if any host plant supports one.
        # (Not asserting presence — depends on the sampled plant set — only that
        #  they never appear by day.)

    def test_winter_thins_to_year_round_taxa(self):
        summer = W.wildlife_for_scene(self._scene(7, False))
        winter = W.wildlife_for_scene(self._scene(1, False))
        # January (day): bees/butterflies/insects are gone; birds persist.
        self.assertLess(len(winter), len(summer))
        winter_kinds = {c["kind"] for c in winter}
        self.assertNotIn("bee", winter_kinds)
        self.assertNotIn("butterfly", winter_kinds)


class TestAppearanceForFauna(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        init_db()

    def _fid(self, like):
        conn = get_connection()
        try:
            row = conn.execute(
                "SELECT id FROM fauna WHERE scientific_name LIKE ? LIMIT 1",
                (like,)).fetchone()
            return row[0] if row else None
        finally:
            conn.close()

    def test_green_sweat_bee_is_metallic_green(self):
        fid = self._fid("Agapostemon%")
        if fid is None:
            self.skipTest("no Agapostemon seeded")
        app = W.appearance_for_fauna(fid)
        self.assertEqual(app["kind"], "bee")
        self.assertTrue(app["metallic"])

    def test_bumble_bee_is_round_yellow(self):
        fid = self._fid("Bombus%")
        app = W.appearance_for_fauna(fid)
        self.assertEqual(app["shape"], "round")
        self.assertFalse(app["metallic"])

    def test_lep_appearance_by_kind(self):
        fid = self._fid("Danaus plexippus")
        app = W.appearance_for_fauna(fid)
        self.assertEqual(app["kind"], "butterfly")
        self.assertRegex(app["fore"], _HEX)

    def test_unknown_fauna_none(self):
        self.assertIsNone(W.appearance_for_fauna(-12345))


if __name__ == "__main__":
    unittest.main()

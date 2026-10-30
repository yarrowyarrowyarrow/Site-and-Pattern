"""
tests/test_reference_layout.py — how the walks are planted (V3.39, F255).

Until V3.39 every walk was an alphabetical, uniform scatter: the Aspen Parkland
had no aspen and the Boreal Mixedwood no white spruce. These tests hold the
rules that replaced it (src/reference_layout.py), on the real catalogue and on
plain rows, and the saved-walk upgrade (src/reference_upgrade.py).
"""

import math
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_TMP_DIR = tempfile.mkdtemp(prefix="permadesign_layout_test_")
import src.db.plants as _plants_mod  # noqa: E402
_plants_mod._DATA_DIR = _TMP_DIR
_plants_mod._DB_PATH = os.path.join(_TMP_DIR, "permadesign_test.db")

from src import reference_layout as RL  # noqa: E402
from src import reference_ecosystem as RE  # noqa: E402


def _row(i, name, ptype, *, spacing=None, sun="", water="", sci=""):
    return {"id": i, "common_name": name, "plant_type": ptype,
            "scientific_name": sci or f"Genus{i} species",
            "spacing_m": spacing, "sun_requirement": sun,
            "water_needs": water}


def _cover(x, y, trees):
    return min([math.hypot(x - tx, y - ty) / r for tx, ty, r in trees]
               or [9.0])


class TheRulesOnPlainRows(unittest.TestCase):
    """The layout alone, with rows made up here: no database."""

    def setUp(self):
        self.tree = _row(1, "Tree", "tree", spacing=5, sci="Populus x")
        self.shrub = _row(2, "Shrub", "shrub", spacing=1.5)
        self.sunflower = _row(3, "Sun flower", "wildflower", spacing=0.3,
                              sun="full_sun")
        self.shadeflower = _row(4, "Shade flower", "wildflower", spacing=0.3,
                                sun="partial_shade,full_shade")
        self.grass = _row(5, "Grass", "grass", spacing=0.3, sun="full_sun")
        self.layers = [
            {"layer": "canopy", "form": "clump", "count": 6,
             "leads": [(self.tree, 6)], "fill": []},
            {"layer": "shrub", "form": "edge", "count": 6,
             "leads": [(self.shrub, 0)], "fill": []},
            {"layer": "forb", "form": "drift", "count": 12,
             "leads": [(self.sunflower, 0), (self.shadeflower, 0)],
             "fill": []},
            {"layer": "grass", "form": "matrix", "count": 20,
             "leads": [(self.grass, 0)], "fill": []},
        ]

    def test_every_layer_gets_its_count(self):
        out = RL.lay_out(self.layers, size_m=26)
        by = {}
        for row, _x, _y in out:
            by[row["id"]] = by.get(row["id"], 0) + 1
        self.assertEqual(by, {1: 6, 2: 6, 3: 6, 4: 6, 5: 20})

    def test_the_same_input_gives_the_same_walk(self):
        a = RL.lay_out(self.layers, size_m=26)
        b = RL.lay_out(self.layers, size_m=26)
        self.assertEqual([(r["id"], x, y) for r, x, y in a],
                         [(r["id"], x, y) for r, x, y in b])

    def test_light_decides_who_stands_under_the_trees(self):
        out = RL.lay_out(self.layers, size_m=26)
        r = RL.crown_m(self.tree, "canopy") / 2
        trees = [(x, y, r) for row, x, y in out if row is self.tree]
        for row, x, y in out:
            if row in (self.sunflower, self.grass):
                self.assertGreaterEqual(_cover(x, y, trees), 0.999,
                                        f"{row['common_name']} under a crown")
        shade = [_cover(x, y, trees) for row, x, y in out
                 if row is self.shadeflower]
        self.assertTrue(all(c < 1.0 for c in shade), shade)

    def test_the_walker_starts_in_a_clearing(self):
        """The scene's origin is the plants' centroid (scene_contract), and
        the walker starts there (08-modes.js walkSpawn)."""
        out = RL.lay_out(self.layers, size_m=26)
        cx = sum(x for _r, x, _y in out) / len(out)
        cy = sum(y for _r, _x, y in out) / len(out)
        self.assertAlmostEqual(cx, 0.0, places=6)
        self.assertAlmostEqual(cy, 0.0, places=6)
        for row, x, y in out:
            if row["plant_type"] in ("tree", "shrub"):
                self.assertGreater(math.hypot(x, y), RL.CLEARING_M - 0.5,
                                   row["common_name"])

    def test_a_clone_stands_close(self):
        """An aspen clone's stems come up a couple of metres apart."""
        out = RL.lay_out(self.layers, size_m=26)
        stems = [(x, y) for row, x, y in out if row is self.tree]
        gaps = [min(math.hypot(x - a, y - b) for a, b in stems if (a, b) != (x, y))
                for x, y in stems]
        self.assertTrue(all(1.0 < g < 4.0 for g in gaps), gaps)

    def test_every_lead_is_planted_however_many(self):
        leads = [(_row(10 + i, f"Flower {i}", "wildflower", spacing=0.3), 0)
                 for i in range(6)]
        fill = [_row(30 + i, f"Other {i}", "wildflower", spacing=0.3)
                for i in range(8)]
        out = RL.lay_out([{"layer": "forb", "form": "drift", "count": 22,
                           "leads": leads, "fill": fill}], size_m=26)
        names = {row["common_name"] for row, _x, _y in out}
        for row, _s in leads:
            self.assertIn(row["common_name"], names)
        self.assertEqual(len(out), 22)

    def test_sun_and_crown_read_the_catalogue_fields(self):
        self.assertEqual(RL.sun_of({"sun_requirement": "full_sun"}), "sun")
        self.assertEqual(RL.sun_of(
            {"sun_requirement": "partial_shade,full_shade"}), "shade")
        self.assertEqual(RL.sun_of(
            {"sun_requirement": "full_sun,partial_shade"}), "any")
        self.assertEqual(RL.sun_of({}), "any")
        self.assertEqual(RL.crown_m({"spacing_m": "2"}), 3.0)
        self.assertEqual(RL.crown_m({"mature_canopy_m": 4.0,
                                     "spacing_m": "2"}), 4.0)


class TheWalksOnTheCatalogue(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from src.db.plants import init_db
        init_db()
        cls.walks = {}
        for key in RE.community_keys():
            plan = RE.layer_plan(key)
            cls.walks[key] = (plan, RL.lay_out(plan, size_m=RE.SIZE_M))

    def test_every_lead_species_is_planted(self):
        for key, (plan, out) in self.walks.items():
            planted = {row["common_name"] for row, _x, _y in out}
            for spec in RE.reference_community(key)["layers"].values():
                for name, _stems in RE.lead_entries(spec):
                    self.assertIn(name, planted, f"{key}: {name}")

    def test_the_aspen_parkland_has_its_aspen(self):
        """The bug that started it: the grove had Balsam Poplar, two
        cottonwoods and Paper Birch, which sort before Trembling Aspen."""
        _plan, out = self.walks["aspen_parkland"]
        trees = [row["common_name"] for row, _x, _y in out
                 if row["plant_type"] == "tree"]
        self.assertGreaterEqual(trees.count("Trembling Aspen"), 5, trees)
        boreal = [row["common_name"] for row, _x, _y in
                  self.walks["boreal_mixedwood"][1]]
        self.assertIn("White Spruce", boreal)

    def test_counts_are_the_communities(self):
        for key, (_plan, out) in self.walks.items():
            want = sum(l["count"] for l in
                       RE.reference_community(key)["layers"].values())
            self.assertEqual(len(out), want, key)

    def test_no_sun_plant_under_a_crown_and_shade_plants_under_one(self):
        for key, (plan, out) in self.walks.items():
            canopy = {id(r) for r, _s in plan[0]["leads"]} | {
                id(r) for r in plan[0]["fill"]}
            trees = [(x, y, RL.crown_m(r, "canopy") / 2) for r, x, y in out
                     if id(r) in canopy]
            for row, x, y in out:
                if id(row) in canopy:
                    continue
                if RL.sun_of(row) == "sun":
                    self.assertGreaterEqual(
                        _cover(x, y, trees), 0.999,
                        f"{key}: {row['common_name']} is under a crown")
        plan, out = self.walks["boreal_mixedwood"]
        trees = [(x, y, RL.crown_m(r, "canopy") / 2) for r, x, y in out
                 if r["plant_type"] == "tree"]
        bunch = [_cover(x, y, trees) for r, x, y in out
                 if r["common_name"] == "Bunchberry"]
        self.assertTrue(bunch and all(c < 1.0 for c in bunch), bunch)

    def test_the_walker_never_starts_in_a_trunk(self):
        for key, (_plan, out) in self.walks.items():
            for row, x, y in out:
                if row["plant_type"] in ("tree", "shrub"):
                    self.assertGreater(math.hypot(x, y), 2.5,
                                       f"{key}: {row['common_name']}")

    def test_the_fill_suits_the_ground(self):
        """No wet-ground plant fills out the dry fescue grassland (Marsh Aster
        did, on the first draft), and no dry-ground one the wet meadow."""
        for key, wet in (("fescue_foothills", False), ("wet_meadow", True)):
            plan = self.walks[key][0]
            for spec in plan:
                for row in spec["fill"]:
                    levels = RE._water_range(row)
                    if not levels:
                        continue
                    if wet:
                        self.assertEqual(levels[1], 3, row["common_name"])
                    else:
                        self.assertEqual(levels[0], 1, row["common_name"])

    def test_the_scored_list_does_not_carry_the_leads(self):
        """The fidelity band and the habitat score read ``layers``; the leads
        are beside it, so adding them moved no design's score."""
        r = RE.resolve_reference_community("aspen_parkland")
        self.assertIn("Prairie Crocus", r["leads"]["forb"])
        self.assertNotIn("Prairie Crocus", r["layers"]["forb"])
        self.assertIn("Trembling Aspen", r["leads"]["canopy"])

    def test_the_project_records_its_version_and_centre(self):
        proj = RE.build_reference_project("riparian", center_lat=53.5,
                                          center_lng=-113.5)
        props = proj["properties"]
        self.assertEqual(props["reference_version"], RE.COMMUNITY_VERSION)
        self.assertEqual(props["reference_center"], [53.5, -113.5])

    def test_a_walk_can_plant_what_suits_its_ground(self):
        """Plant one (V3.41): any plant native here that takes the
        community's typical ground; a dry prairie plant does not suit the
        wet meadow, and a wet-ground sedge does not suit the dry prairie."""
        wet = RE.plantable_ids("wet_meadow")
        dry = RE.plantable_ids("mixedgrass_prairie")
        from src.db.plants import get_connection
        conn = get_connection()
        try:
            ids = {r["common_name"]: r["id"] for r in conn.execute(
                "SELECT id, common_name FROM plants WHERE common_name IN "
                "('Prairie Crocus', 'Water Sedge', 'Marsh Marigold')")}
        finally:
            conn.close()
        self.assertNotIn(ids["Prairie Crocus"], wet)
        self.assertIn(ids["Marsh Marigold"], wet)
        self.assertIn(ids["Prairie Crocus"], dry)
        self.assertNotIn(ids["Water Sedge"], dry)
        self.assertGreater(len(wet), 50)

    def test_the_palette_leads_with_the_leads(self):
        from src import reference_edit
        pal = reference_edit.palette("aspen_parkland")
        names = [p["common_name"] for p in pal]
        self.assertLessEqual(len(pal), reference_edit.PALETTE_SIZE)
        for lead in RE.lead_names("aspen_parkland"):
            self.assertIn(lead, names)
        canopy = [p["common_name"] for p in pal if p["layer"] == "canopy"]
        self.assertEqual(canopy[:2], ["Trembling Aspen", "Balsam Poplar"])
        order = [p["layer"] for p in pal]
        self.assertEqual(order, sorted(order, key=["canopy", "shrub", "forb",
                                                    "grass"].index))


class ASavedWalkIsUpgraded(unittest.TestCase):
    """A walk saved before V3.39 keeps the person's plants and loses its
    alphabetical trees (src/reference_upgrade.py)."""

    def _old(self):
        from src.project_store import ProjectStore
        project = {"type": "FeatureCollection", "features": [],
                   "properties": {"name": "Reference — Aspen Parkland grove",
                                  "reference_ecoregion": "aspen_parkland"}}
        store = ProjectStore(project)
        for i, (dx, dy) in enumerate(((-0.0001, -0.0001), (0.0001, 0.0001),
                                      (0.0001, -0.0001), (-0.0001, 0.0001))):
            store.add_plant(100 + i, "Old", 53.5 + dy, -113.5 + dx,
                            pattern_kind="reference")
        store.add_plant(7, "Mine", 53.50003, -113.50004, pattern_kind="user",
                        planted_year=4)
        project["features"].append({"type": "Feature", "geometry": None,
                                    "properties": {"element_type": "note"}})
        return project

    def _build(self, calls):
        def build(community, *, center_lat, center_lng):
            calls.append((community, center_lat, center_lng))
            from src.project_store import ProjectStore
            fresh = {"type": "FeatureCollection", "features": [],
                     "properties": {"reference_version": RE.COMMUNITY_VERSION,
                                    "reference_center": [center_lat,
                                                         center_lng]}}
            ProjectStore(fresh).add_plant(1, "New", center_lat, center_lng,
                                          pattern_kind="reference")
            return fresh
        return build

    def test_the_persons_plants_are_kept_and_the_shipped_ones_replaced(self):
        from src.project_store import ProjectStore
        from src.reference_upgrade import upgrade_sandbox
        calls = []
        out = upgrade_sandbox("aspen_parkland", self._old(),
                              build=self._build(calls))
        recs = ProjectStore(out).placed_plants
        names = sorted(r["common_name"] for r in recs)
        self.assertEqual(names, ["Mine", "New"])
        mine = next(r for r in recs if r["common_name"] == "Mine")
        self.assertEqual((mine["lat"], mine["lng"]), (53.50003, -113.50004))
        self.assertEqual(mine.get("planted_year"), 4)
        # The tag rides on the feature; the record does not carry it.
        feature = next(f for f in out["features"]
                       if (f.get("properties") or {}).get("common_name")
                       == "Mine")
        self.assertEqual(feature["properties"]["pattern_kind"], "user")
        # Built where the old walk stood: the middle of its shipped plants.
        self.assertEqual(len(calls), 1)
        self.assertAlmostEqual(calls[0][1], 53.5, places=7)
        self.assertAlmostEqual(calls[0][2], -113.5, places=7)
        self.assertTrue(any((f.get("properties") or {}).get("element_type")
                            == "note" for f in out["features"]))

    def test_a_current_walk_is_left_alone(self):
        from src.reference_upgrade import upgrade_sandbox
        saved = self._old()
        saved["properties"]["reference_version"] = RE.COMMUNITY_VERSION
        calls = []
        self.assertIs(upgrade_sandbox("aspen_parkland", saved,
                                      build=self._build(calls)), saved)
        self.assertEqual(calls, [])

    def test_a_recorded_centre_is_used_as_it_is(self):
        from src.reference_upgrade import upgrade_sandbox
        saved = self._old()
        saved["properties"]["reference_version"] = 1
        saved["properties"]["reference_center"] = [51.0, -114.0]
        calls = []
        upgrade_sandbox("aspen_parkland", saved, build=self._build(calls))
        self.assertEqual(calls[0][1:], (51.0, -114.0))


if __name__ == "__main__":
    unittest.main()

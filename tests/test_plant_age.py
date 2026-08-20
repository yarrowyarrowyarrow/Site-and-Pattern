"""
Per-plant age and nursery stock (V2.44).

Author's report: *"I'd like it for a plant planted at any year to start as a
young small plant not immediately at the same age as all the others that have
been planted. To this end though, trees and shrubs should start as small
versions (3 years for shrubs, 5 years for trees as noone will be planting these
from seed)."*

**The test that matters is the first class.** Everything before V2.44 drew every
plant at the design's age; the feature is opt-in per plant, and a plant with no
``planted_year`` must render byte-identically to how it did before. If that
breaks, every saved design in existence changes appearance silently — the worst
kind of regression, because nothing looks wrong until somebody who knows their
own yard opens it.
"""

from __future__ import annotations

import unittest

from src.scene3d import (NURSERY_AGE_YEARS, effective_age, growth_scale_factor,
                         nursery_age, plant_3d_state)

_TREE = {"plant_type": "tree", "years_to_maturity": 20,
         "mature_height_meters": 8.0, "growth_curve": "steady"}
_SHRUB = {"plant_type": "shrub", "years_to_maturity": 5,
          "mature_height_meters": 2.0, "growth_curve": "steady"}
_HERB = {"plant_type": "herb", "years_to_maturity": 2,
         "mature_height_meters": 0.5, "growth_curve": "steady"}


class TestNothingChangedForExistingDesigns(unittest.TestCase):
    """The backwards-compatibility contract, stated three ways."""

    def test_no_planted_year_means_the_design_year(self):
        for plant in (_TREE, _SHRUB, _HERB):
            for year in (0, 1, 3, 5, 12, 25, 40):
                self.assertEqual(
                    effective_age(plant, year, None), year,
                    f"{plant['plant_type']} at year {year}")

    def test_heights_are_unchanged_without_a_planting_date(self):
        """Computed against growth_scale_factor directly — the pre-V2.44
        definition — rather than against a recorded snapshot, so this keeps
        holding if the curve itself is ever legitimately retuned."""
        for plant in (_TREE, _SHRUB, _HERB):
            for year in (0, 1, 4, 12, 30):
                st = plant_3d_state(plant, 51.0, -114.0, year)
                expected = round(
                    plant["mature_height_meters"]
                    * growth_scale_factor(year, plant["years_to_maturity"],
                                          plant["growth_curve"]), 3)
                self.assertEqual(st["height_m"], expected)

    def test_year_zero_is_still_the_mature_reference_for_everyone(self):
        """Year 0 has meant "the design at maturity" since the growth timeline
        shipped. A plant carrying a planting date must not quietly redefine the
        one position a designer uses to see the endpoint they are aiming at."""
        for plant in (_TREE, _SHRUB):
            self.assertEqual(effective_age(plant, 0, 12), 0)
            st = plant_3d_state(plant, 51.0, -114.0, 0, planted_year=12)
            self.assertEqual(st["scale_factor"], 1.0)
            self.assertEqual(st["height_m"], plant["mature_height_meters"])


class TestNurseryStock(unittest.TestCase):
    """You do not plant a tree from seed."""

    def test_the_ages_are_the_ones_that_were_asked_for(self):
        self.assertEqual(nursery_age(_TREE), 5)
        self.assertEqual(nursery_age(_SHRUB), 3)

    def test_herbs_and_grasses_still_go_in_from_plugs(self):
        for ptype in ("herb", "groundcover", "vine", "root", ""):
            self.assertEqual(nursery_age({"plant_type": ptype}), 0)

    def test_only_woody_types_carry_a_nursery_age(self):
        self.assertEqual(set(NURSERY_AGE_YEARS), {"tree", "shrub"})

    def test_a_planted_tree_is_a_whip_not_a_seedling(self):
        """The point of the nursery age: 25% of mature, not 5% — big enough to
        look like something somebody paid for, small enough to read as new."""
        st = plant_3d_state(_TREE, 51.0, -114.0, 12, planted_year=12)
        self.assertAlmostEqual(st["scale_factor"], 0.25, places=3)
        self.assertGreater(st["height_m"], 1.5)
        self.assertLess(st["height_m"], 3.0)

    def test_a_planted_shrub_is_a_pot_sized_plant(self):
        st = plant_3d_state(_SHRUB, 51.0, -114.0, 12, planted_year=12)
        self.assertAlmostEqual(st["scale_factor"], 0.6, places=3)


class TestItActuallyGrows(unittest.TestCase):

    def test_a_new_tree_catches_up_over_the_timeline(self):
        heights = [plant_3d_state(_TREE, 51.0, -114.0, y,
                                  planted_year=12)["height_m"]
                   for y in (12, 15, 20, 27, 40)]
        self.assertEqual(heights, sorted(heights), heights)
        self.assertLess(heights[0], heights[-1])
        self.assertEqual(heights[-1], 8.0)          # mature, eventually

    def test_a_new_plant_is_smaller_than_its_established_neighbours(self):
        """The whole visible point of the feature."""
        established = plant_3d_state(_TREE, 51.0, -114.0, 12)
        just_planted = plant_3d_state(_TREE, 51.0, -114.0, 12, planted_year=12)
        self.assertLess(just_planted["height_m"], established["height_m"])

    def test_age_never_goes_negative(self):
        """Viewing a year before the plant went in. Clamped rather than
        negative, because a negative age through growth_scale_factor lands on
        the year<=0 branch and would draw it MATURE — the exact opposite."""
        self.assertGreaterEqual(effective_age(_TREE, 5, 12), 0)
        st = plant_3d_state(_TREE, 51.0, -114.0, 5, planted_year=12)
        self.assertLessEqual(st["scale_factor"], 0.25)

    def test_the_same_age_drives_growth_spread_and_succession(self):
        """One age for all three time-varying properties. Feeding two of them
        the design's age and one the plant's would put a young plant in an old
        plant's succession arc."""
        spreader = dict(_HERB, spread_habit="aggressive_rhizomatous")
        young = plant_3d_state(spreader, 51.0, -114.0, 20, planted_year=20)
        old = plant_3d_state(spreader, 51.0, -114.0, 20)
        self.assertLess(young["spread_factor"], old["spread_factor"])


class TestItRoundTrips(unittest.TestCase):
    """planted_year is project data — it must survive a save/load."""

    def test_it_survives_the_geojson_feature(self):
        from src.project_store import (plant_feature, plant_record_from_feature)
        rec = {"plant_id": 7, "common_name": "Aspen",
               "lat": 51.0, "lng": -114.0, "planted_year": 12}
        back = plant_record_from_feature(plant_feature(dict(rec)))
        self.assertEqual(back["planted_year"], 12)

    def test_the_store_stamps_it_and_keeps_the_two_views_in_step(self):
        from src.project_store import ProjectStore
        store = ProjectStore({"type": "FeatureCollection", "features": []})
        store.add_plant(7, "Aspen", 51.0, -114.0, planted_year=12)
        self.assertEqual(store.placed_plants[0]["planted_year"], 12)
        self.assertEqual(store.check_consistency(), [])

    def test_omitting_it_leaves_no_trace(self):
        """An undated plant must not acquire a key at all — a `planted_year:
        null` in the feature would be a second way to say 'absent'."""
        from src.project_store import ProjectStore, plant_feature
        store = ProjectStore({"type": "FeatureCollection", "features": []})
        store.add_plant(7, "Aspen", 51.0, -114.0)
        self.assertNotIn("planted_year", store.placed_plants[0])
        self.assertNotIn("planted_year",
                         store.features[0]["properties"])

    def test_redo_restores_the_date_rather_than_re_stamping_it(self):
        """A plant put back by an undo is the same plant. Re-dating it would
        make it younger every time the user changed their mind."""
        from src.project_store import ProjectStore
        store = ProjectStore({"type": "FeatureCollection", "features": []})
        rec = store.add_plant(7, "Aspen", 51.0, -114.0, planted_year=4)
        fid = rec["feature_id"]
        store.remove_plant(7, 51.0, -114.0, feature_id=fid)
        store.add_plant(7, "Aspen", 51.0, -114.0,
                        feature_id=fid, planted_year=4)
        self.assertEqual(store.placed_plants[0]["planted_year"], 4)
        self.assertEqual(store.placed_plants[0]["feature_id"], fid)


class TestTheSceneCarriesIt(unittest.TestCase):

    def test_no_plant_is_drawn_at_the_designs_age_by_accident(self):
        """Read as text: exercising build_scene needs the catalogue, and the
        thing worth pinning is the wiring — a ``plant_3d_state`` call that
        forgot the kwarg would silently ignore every planting date.

        The rule is precise rather than blanket, because there are two honest
        ways to give a plant its own age and ``scene_contract`` uses both:

        * **placed plants** pass the design's ``year`` plus ``planted_year``,
          and V2.44's :func:`effective_age` resolves the two;
        * **regeneration recruits** pass their own age directly
          (``int(rc["age"]) + 1``) — a self-seeded volunteer really did come
          from seed, so it needs no nursery age and no planting date.

        What must never appear is a call passing the bare ``year`` with no
        planting date: that is a placed plant drawn at the design's age.
        """
        import ast
        import pathlib
        src = (pathlib.Path(__file__).resolve().parent.parent
               / "src" / "scene_contract.py").read_text(encoding="utf-8")
        calls = [n for n in ast.walk(ast.parse(src))
                 if isinstance(n, ast.Call)
                 and getattr(n.func, "id", "") == "plant_3d_state"]
        self.assertTrue(calls, "scene_contract no longer calls plant_3d_state")
        for call in calls:
            age_arg = call.args[3] if len(call.args) > 3 else None
            passes_bare_year = (isinstance(age_arg, ast.Name)
                                and age_arg.id == "year")
            has_planted = "planted_year" in [kw.arg for kw in call.keywords]
            self.assertFalse(
                passes_bare_year and not has_planted,
                f"plant_3d_state at line {call.lineno} draws a placed plant at "
                f"the design's age — it needs planted_year=")

    def test_the_sandbox_stamps_what_it_plants(self):
        import ast
        import pathlib
        src = (pathlib.Path(__file__).resolve().parent.parent
               / "src" / "reference_edit_flow.py").read_text(encoding="utf-8")
        fn = next(n for n in ast.walk(ast.parse(src))
                  if isinstance(n, ast.FunctionDef)
                  and n.name == "on_plant_requested")
        self.assertIn("planted_year", ast.dump(fn))


if __name__ == "__main__":
    unittest.main()

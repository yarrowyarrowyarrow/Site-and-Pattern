"""
tests/test_conversion_plan.py — the year-by-year lawn → habitat schedule (F17).

Covers src/conversion_plan.py:
  1. Stage scaffold: five restoration bands, in order, each carrying its
     succession.restoration_stage name.
  2. Plant grouping into the right bands (woody → structure year 0; pioneers →
     early; matrix → years 3–4; self-spreaders → fill; climax → year 10+).
  3. Lawn-area step appears only when conversion zones are drawn, and uses
     lawn + restoration (not remnant) area.
  4. render_schedule_text content.
  5. Empty design still produces a sensible (generic-cadence) schedule.

Pure: an injected get_plant keeps the logic DB-free.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import conversion_plan as cp  # noqa: E402
from src.lawn_zones import conversion_summary, ZONE_TYPES  # noqa: E402


_PLANTS = {
    1: {"id": 1, "common_name": "Trembling Aspen", "plant_type": "tree",
        "years_to_maturity": 30},                      # woody + climax (heuristic)
    2: {"id": 2, "common_name": "Fireweed", "plant_type": "herb",
        "permaculture_uses": "early_successional"},     # pioneer
    3: {"id": 3, "common_name": "Wild Bergamot", "plant_type": "herb"},  # matrix
    4: {"id": 4, "common_name": "Wild Strawberry", "plant_type": "groundcover",
        "spread_habit": "self_seeding"},                # fill
    5: {"id": 5, "common_name": "Saskatoon", "plant_type": "shrub"},     # woody
}


def _get_plant(pid):
    return dict(_PLANTS.get(pid, {}))


def _placed():
    out = []
    for pid in (1, 2, 3, 4, 5):
        out.append({"plant_id": pid, "common_name": _PLANTS[pid]["common_name"]})
    return out


def _zone(key, area):
    return {"type": "Feature", "properties": {
        "element_type": "custom_shape",
        "shape_type": ZONE_TYPES[key]["label"], "area_m2": area}}


class TestStageScaffold(unittest.TestCase):
    def setUp(self):
        self.sched = cp.build_conversion_schedule(_placed(), get_plant=_get_plant)

    def test_five_ordered_stages(self):
        labels = [s.year_label for s in self.sched.stages]
        self.assertEqual(labels,
                         ["Year 0", "Years 1–2", "Years 3–4", "Years 5–9", "Year 10+"])

    def test_stage_names_from_succession(self):
        from src.succession import restoration_stage
        self.assertEqual(self.sched.stages[0].stage, restoration_stage(0))
        self.assertEqual(self.sched.stages[1].stage, restoration_stage(1))
        self.assertEqual(self.sched.stages[4].stage, restoration_stage(10))

    def test_every_stage_has_tasks(self):
        for st in self.sched.stages:
            self.assertTrue(st.tasks, f"{st.year_label} has no tasks")

    def test_species_and_plant_counts(self):
        self.assertEqual(self.sched.species_count, 5)
        self.assertEqual(self.sched.total_plants, 5)


class TestPlantGrouping(unittest.TestCase):
    def setUp(self):
        self.sched = cp.build_conversion_schedule(_placed(), get_plant=_get_plant)

    def _stage(self, label):
        return next(s for s in self.sched.stages if s.year_label == label)

    def test_woody_planted_year_zero(self):
        y0 = " ".join(self._stage("Year 0").tasks)
        self.assertIn("Saskatoon", y0)
        self.assertIn("Trembling Aspen", y0)
        self.assertIn("woody structure", y0)

    def test_pioneers_in_early_stages(self):
        y0 = " ".join(self._stage("Year 0").tasks)
        self.assertIn("Fireweed", y0)   # pioneer planted at year 0

    def test_matrix_in_years_three_four(self):
        y3 = " ".join(self._stage("Years 3–4").tasks)
        self.assertIn("Wild Bergamot", y3)

    def test_self_spreader_is_fill(self):
        y3 = " ".join(self._stage("Years 3–4").tasks)
        self.assertIn("Wild Strawberry", y3)

    def test_climax_year_ten(self):
        y10 = " ".join(self._stage("Year 10+").tasks)
        self.assertIn("Trembling Aspen", y10)   # long-lived tree → climax


class TestLawnArea(unittest.TestCase):
    def test_removal_step_appears_with_zones(self):
        summary = conversion_summary([
            _zone("lawn_remaining", 80.0),
            _zone("restoration_year_1", 20.0),
            _zone("existing_remnant", 500.0),   # remnant excluded from target
        ])
        sched = cp.build_conversion_schedule(_placed(), summary=summary,
                                             get_plant=_get_plant)
        self.assertEqual(sched.target_m2, 100.0)   # 80 + 20
        self.assertTrue(sched.has_zones)
        y0 = " ".join(sched.stages[0].tasks)
        self.assertIn("smother", y0.lower())
        self.assertIn("100", y0)

    def test_no_removal_step_without_zones(self):
        sched = cp.build_conversion_schedule(_placed(), get_plant=_get_plant)
        self.assertFalse(sched.has_zones)
        y0 = " ".join(sched.stages[0].tasks).lower()
        self.assertNotIn("smother", y0)


class TestRender(unittest.TestCase):
    def test_text_contains_sections(self):
        summary = conversion_summary([_zone("lawn_remaining", 100.0)])
        sched = cp.build_conversion_schedule(_placed(), summary=summary,
                                             get_plant=_get_plant)
        text = cp.render_schedule_text(sched)
        self.assertIn("PHASED CONVERSION", text)
        self.assertIn("Year 0", text)
        self.assertIn("Year 10+", text)
        self.assertIn("of lawn to habitat", text)
        self.assertIn("•", text)


class TestEmptyDesign(unittest.TestCase):
    def test_empty_still_builds(self):
        sched = cp.build_conversion_schedule([], get_plant=_get_plant)
        self.assertEqual(sched.total_plants, 0)
        self.assertEqual(len(sched.stages), 5)
        text = cp.render_schedule_text(sched)
        self.assertIn("PHASED CONVERSION", text)


if __name__ == "__main__":
    unittest.main()

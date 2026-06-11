"""
tests/test_project_store.py — the single write path for placed plants.

Three layers of protection:

  1. Unit tests for every ProjectStore mutation (add / remove / batch /
     polyculture / move) — both structures always agree afterwards.
  2. A scripted editing session asserting ``check_consistency()`` stays
     empty after every step, plus a tamper test proving the checker
     actually detects drift.
  3. A source-tree guard: no module under src/ may mutate
     ``_placed_plants`` directly any more — all writes go through the
     store. This is the tripwire that keeps future call sites from
     reintroducing the hand-rolled dual-store bookkeeping.

Pure Python — no Qt, no DB.
"""

import os
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.project_store import (                       # noqa: E402
    COORD_TOL_DEG, ProjectStore, plant_feature,
    plant_record_from_feature, store_for,
)

_SRC = Path(__file__).resolve().parent.parent / "src"


def _store():
    return ProjectStore({"type": "FeatureCollection",
                         "properties": {}, "features": []})


class TestConverters(unittest.TestCase):

    def test_round_trip_minimal(self):
        rec = {"plant_id": 7, "common_name": "Wild Bergamot",
               "lat": 53.5, "lng": -113.5}
        back = plant_record_from_feature(plant_feature(rec))
        self.assertEqual(back, rec)

    def test_round_trip_full(self):
        rec = {"plant_id": 7, "common_name": "Wild Bergamot",
               "lat": 53.5, "lng": -113.5,
               "polyculture_name": "Pollinator Mound",
               "polyculture_center_lat": 53.5001,
               "polyculture_center_lng": -113.5001,
               "placement_group_id": "pg_abc"}
        f = plant_feature(rec, pattern_kind="grid", quantity=1)
        self.assertEqual(f["properties"]["pattern_kind"], "grid")
        self.assertEqual(plant_record_from_feature(f), rec)

    def test_empty_optionals_are_omitted(self):
        rec = {"plant_id": 1, "common_name": "X", "lat": 1.0, "lng": 2.0,
               "polyculture_name": "", "placement_group_id": ""}
        props = plant_feature(rec)["properties"]
        self.assertNotIn("polyculture_name", props)
        self.assertNotIn("placement_group_id", props)

    def test_non_plant_features_yield_none(self):
        self.assertIsNone(plant_record_from_feature(
            {"type": "Feature", "geometry": {"type": "Point",
                                             "coordinates": [1, 2]},
             "properties": {"element_type": "structure"}}))
        self.assertIsNone(plant_record_from_feature(
            {"type": "Feature",
             "geometry": {"type": "Polygon", "coordinates": []},
             "properties": {"element_type": "plant"}}))


class TestMutations(unittest.TestCase):

    def test_add_plant_lands_in_both(self):
        s = _store()
        rec = s.add_plant(3, "Prairie Crocus", 53.5, -113.5,
                          placement_group_id="pg_1")
        self.assertEqual(s.placed_plants, [rec])
        self.assertEqual(len(s.features), 1)
        self.assertEqual(s.features[0]["geometry"]["coordinates"],
                         [-113.5, 53.5])
        self.assertEqual(s.check_consistency(), [])

    def test_remove_plant_oldest_vs_newest(self):
        s = _store()
        s.add_plant(3, "A", 53.5, -113.5, placement_group_id="pg_old")
        s.add_plant(3, "A", 53.5, -113.5, placement_group_id="pg_new")
        removed = s.remove_plant(3, 53.5, -113.5, newest_first=True)
        self.assertEqual(removed["placement_group_id"], "pg_new")
        self.assertEqual(s.placed_plants[0]["placement_group_id"], "pg_old")
        self.assertEqual(s.check_consistency(), [])

    def test_remove_plant_tolerates_float_noise(self):
        s = _store()
        s.add_plant(3, "A", 53.5, -113.5)
        self.assertIsNotNone(
            s.remove_plant(3, 53.5 + COORD_TOL_DEG / 2,
                           -113.5 - COORD_TOL_DEG / 2))
        self.assertEqual(s.placed_plants, [])
        self.assertEqual(s.features, [])

    def test_remove_missing_returns_none(self):
        s = _store()
        s.add_plant(3, "A", 53.5, -113.5)
        self.assertIsNone(s.remove_plant(4, 53.5, -113.5))
        self.assertEqual(len(s.placed_plants), 1)

    def test_batch_removal_multiset_semantics(self):
        s = _store()
        # Three identical plants at one spot; remove exactly two.
        for _ in range(3):
            s.add_plant(5, "Yarrow", 53.0, -113.0)
        removed = s.remove_plants_batch([(5, 53.0, -113.0),
                                         (5, 53.0, -113.0)])
        self.assertEqual(len(removed), 2)
        self.assertEqual(len(s.placed_plants), 1)
        self.assertEqual(len(s.features), 1)
        self.assertEqual(s.check_consistency(), [])

    def test_batch_removal_leaves_non_plants_alone(self):
        s = _store()
        s.features.append({"type": "Feature",
                           "geometry": {"type": "Point",
                                        "coordinates": [-113.0, 53.0]},
                           "properties": {"element_type": "structure",
                                          "struct_id": "pond"}})
        s.add_plant(5, "Yarrow", 53.0, -113.0)
        s.remove_plants_batch([(5, 53.0, -113.0)])
        self.assertEqual(len(s.features), 1)
        self.assertEqual(s.features[0]["properties"]["element_type"],
                         "structure")

    def test_remove_polyculture_only_takes_the_anchored_instance(self):
        s = _store()
        for k in range(3):
            s.add_plant(k + 1, f"P{k}", 53.0 + k * 1e-5, -113.0,
                        polyculture_name="Mound",
                        polyculture_center_lat=53.0,
                        polyculture_center_lng=-113.0,
                        placement_group_id="pg_a")
        for k in range(3):
            s.add_plant(k + 1, f"P{k}", 54.0 + k * 1e-5, -113.0,
                        polyculture_name="Mound",
                        polyculture_center_lat=54.0,
                        polyculture_center_lng=-113.0,
                        placement_group_id="pg_a")
        n = s.remove_polyculture("Mound", 53.0, -113.0)
        self.assertEqual(n, 3)
        self.assertEqual(len(s.placed_plants), 3)
        self.assertTrue(all(p["polyculture_center_lat"] == 54.0
                            for p in s.placed_plants))
        self.assertEqual(s.check_consistency(), [])

    def test_move_plant_updates_both(self):
        s = _store()
        s.add_plant(3, "A", 53.5, -113.5, placement_group_id="pg_1")
        self.assertTrue(s.move_plant(3, 53.5, -113.5, 53.6, -113.6))
        self.assertEqual(s.placed_plants[0]["lat"], 53.6)
        self.assertEqual(s.features[0]["geometry"]["coordinates"],
                         [-113.6, 53.6])
        self.assertEqual(s.check_consistency(), [])

    def test_move_plant_group_constraint(self):
        s = _store()
        # Two same-id plants at the same spot in different groups: the
        # group-constrained move must not touch the other group's feature.
        s.add_plant(3, "A", 53.5, -113.5, placement_group_id="pg_1")
        s.add_plant(3, "A", 53.5, -113.5, placement_group_id="pg_2")
        s.move_plant(3, 53.5, -113.5, 53.6, -113.6, group_id="pg_2")
        moved = [f for f in s.features
                 if f["geometry"]["coordinates"] == [-113.6, 53.6]]
        self.assertEqual(len(moved), 1)
        self.assertEqual(moved[0]["properties"]["placement_group_id"],
                         "pg_2")


class TestConsistencySession(unittest.TestCase):
    """A scripted editing session — the invariant holds after every step,
    matching the gesture mix of a real session (singles, communities,
    batches, moves, undo-style newest-first removals)."""

    def test_session_stays_consistent(self):
        s = _store()

        def ok():
            self.assertEqual(s.check_consistency(), [])

        s.add_plant(1, "Saskatoon", 53.50, -113.50,
                    placement_group_id="pg_a")
        ok()
        for k in range(4):
            s.add_plant(2, "Yarrow", 53.51 + k * 1e-5, -113.51,
                        placement_group_id="pg_b", pattern_kind="row")
        ok()
        for k in range(3):
            s.add_plant(3, "Bergamot", 53.52, -113.52 + k * 1e-5,
                        polyculture_name="Mound",
                        polyculture_center_lat=53.52,
                        polyculture_center_lng=-113.52,
                        placement_group_id="pg_c")
        ok()
        s.move_plant(1, 53.50, -113.50, 53.505, -113.505)
        ok()
        s.remove_plant(1, 53.505, -113.505, newest_first=True)  # undo-style
        ok()
        s.remove_plants_batch([(2, 53.51, -113.51),
                               (2, 53.51001, -113.51)])
        ok()
        s.remove_polyculture("Mound", 53.52, -113.52)
        ok()
        self.assertEqual(len(s.placed_plants), 2)
        self.assertEqual(len(s.features), 2)

    def test_checker_detects_drift(self):
        s = _store()
        s.add_plant(1, "Saskatoon", 53.5, -113.5)
        # Bypass the store — the historical bug pattern.
        s.placed_plants.append({"plant_id": 9, "common_name": "Rogue",
                                "lat": 1.0, "lng": 2.0})
        self.assertTrue(s.check_consistency())

    def test_set_project_rebuilds_index(self):
        s = _store()
        rec = {"plant_id": 4, "common_name": "Wolf Willow",
               "lat": 53.0, "lng": -113.0, "placement_group_id": "pg_x"}
        s.set_project({"type": "FeatureCollection", "properties": {},
                       "features": [plant_feature(rec)]})
        self.assertEqual(s.placed_plants, [rec])
        self.assertEqual(s.check_consistency(), [])


class TestStoreFor(unittest.TestCase):

    def test_wraps_fake_main_by_reference(self):
        class Fake:
            pass
        fake = Fake()
        fake._project = {"features": []}
        fake._placed_plants = []
        s = store_for(fake)
        s.add_plant(1, "X", 53.0, -113.0)
        # The fake's own references observe the mutation.
        self.assertEqual(len(fake._placed_plants), 1)
        self.assertEqual(len(fake._project["features"]), 1)
        # And the store is cached for the next call.
        self.assertIs(store_for(fake), s)


class TestSingleWritePathGuard(unittest.TestCase):
    """No module under src/ may mutate ``_placed_plants`` directly —
    additions, removals and reassignment all go through ProjectStore.
    (Reads stay free; panels keeping their *own* lists of the same name
    are fine — the pattern banned here is mutating MainWindow's index
    from outside the store.)"""

    _BANNED = re.compile(
        r"\._placed_plants\s*(=[^=]|\.append|\.pop|\.clear|\.extend"
        r"|\.insert|\.remove)\b")
    # Panels own private lists that merely share the attribute name; they
    # are not MainWindow's index.
    _EXEMPT = {"planning_panel.py", "analysis_panel.py"}

    def test_no_direct_placed_plants_mutation_in_src(self):
        offenders = []
        for py in sorted(_SRC.rglob("*.py")):
            if py.name in self._EXEMPT or py.name == "project_store.py":
                continue
            for lineno, line in enumerate(
                    py.read_text(encoding="utf-8").splitlines(), 1):
                if self._BANNED.search(line):
                    offenders.append(f"  {py.relative_to(_SRC.parent)}:"
                                     f"{lineno}  {line.strip()}")
        if offenders:
            self.fail(
                "Direct _placed_plants mutation outside ProjectStore — "
                "route these through src/project_store.py:\n"
                + "\n".join(offenders))


if __name__ == "__main__":
    unittest.main()

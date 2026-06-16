"""
tests/test_area_fill.py

N3′ — polygon-fill placement core. Pure geometry (no Qt / DB): lay interior
points on a spacing grid inside a drawn ring, and distribute them across a
community's members by cover weight.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.area_fill import (  # noqa: E402
    fill_points, assign_members, plan_fill, matrix_members, plan_matrix_fill,
)

# A ~30 m square near Edmonton, as a GeoJSON [lng, lat] ring (unclosed is fine
# for the ray-cast). 30 m ≈ 0.00027° lat; lng scaled by cos(53.5°)≈0.595.
_LAT = 53.5
_DLAT = 30.0 / 111_320.0
_DLNG = 30.0 / (111_320.0 * 0.5948)
_RING = [
    [-113.50, _LAT],
    [-113.50 + _DLNG, _LAT],
    [-113.50 + _DLNG, _LAT + _DLAT],
    [-113.50, _LAT + _DLAT],
]


class TestFillPoints(unittest.TestCase):
    def test_points_land_inside_and_scale_with_spacing(self):
        coarse = fill_points(_RING, spacing_m=10.0)
        fine = fill_points(_RING, spacing_m=5.0)
        self.assertGreater(len(coarse), 0)
        # Halving spacing roughly quadruples the count (area density ×4).
        self.assertGreater(len(fine), len(coarse) * 2)

    def test_all_points_inside_ring(self):
        from src.geometry import point_in_ring
        for lat, lng in fill_points(_RING, spacing_m=6.0):
            self.assertTrue(point_in_ring(lat, lng, _RING))

    def test_degenerate_inputs(self):
        self.assertEqual(fill_points([], 5.0), [])
        self.assertEqual(fill_points(_RING, 0), [])
        self.assertEqual(fill_points(_RING, -3), [])


class TestAssignMembers(unittest.TestCase):
    def test_proportional_allocation(self):
        pts = [(0.0, 0.0)] * 100
        out = assign_members(pts, [("a", 3), ("b", 1)])
        self.assertEqual(len(out), 100)
        from collections import Counter
        c = Counter(k for k, _, _ in out)
        self.assertEqual(c["a"], 75)
        self.assertEqual(c["b"], 25)

    def test_exact_count_with_largest_remainder(self):
        pts = [(0.0, 0.0)] * 10
        out = assign_members(pts, [("a", 1), ("b", 1), ("c", 1)])
        self.assertEqual(len(out), 10)          # 4/3/3 — sums to 10, none lost
        from collections import Counter
        self.assertEqual(sum(Counter(k for k, _, _ in out).values()), 10)

    def test_single_species(self):
        pts = [(1.0, 2.0), (3.0, 4.0)]
        out = assign_members(pts, [(42, 1)])
        self.assertEqual([k for k, _, _ in out], [42, 42])
        self.assertEqual(out[0], (42, 1.0, 2.0))

    def test_zero_weight_falls_back_to_even(self):
        pts = [(0.0, 0.0)] * 4
        out = assign_members(pts, [("a", 0), ("b", 0)])
        from collections import Counter
        c = Counter(k for k, _, _ in out)
        self.assertEqual(c["a"], 2)
        self.assertEqual(c["b"], 2)

    def test_empty(self):
        self.assertEqual(assign_members([], [("a", 1)]), [])
        self.assertEqual(assign_members([(0, 0)], []), [])


class TestPlanFill(unittest.TestCase):
    def test_end_to_end(self):
        out = plan_fill(_RING, [("oak", 1), ("fescue", 4)], spacing_m=6.0)
        self.assertGreater(len(out), 0)
        keys = {k for k, _, _ in out}
        self.assertEqual(keys, {"oak", "fescue"})
        # fescue (4×) should dominate
        from collections import Counter
        c = Counter(k for k, _, _ in out)
        self.assertGreater(c["fescue"], c["oak"])


class TestMatrix(unittest.TestCase):
    def test_matrix_members_weighting(self):
        m = matrix_members("fescue", ["aster", "bergamot"], matrix_share=0.6)
        self.assertEqual(m[0], ("fescue", 0.6))
        # features split the remaining 0.4 evenly
        self.assertAlmostEqual(m[1][1], 0.2)
        self.assertAlmostEqual(m[2][1], 0.2)
        # the matrix key is never duplicated into the feature list
        m2 = matrix_members("fescue", ["fescue", "aster"], matrix_share=0.7)
        self.assertEqual([k for k, _ in m2], ["fescue", "aster"])

    def test_matrix_share_clamped(self):
        self.assertEqual(matrix_members("g", ["a"], matrix_share=5.0)[0][1], 0.95)
        self.assertEqual(matrix_members("g", ["a"], matrix_share=0.0)[0][1], 0.1)

    def test_matrix_fill_is_matrix_dominant(self):
        out = plan_matrix_fill(_RING, "fescue", ["aster", "bergamot"],
                               spacing_m=4.0, matrix_share=0.7)
        self.assertGreater(len(out), 0)
        from collections import Counter
        c = Counter(k for k, _, _ in out)
        # the matrix species covers more ground than any single feature
        self.assertGreater(c["fescue"], c["aster"])
        self.assertGreater(c["fescue"], c["bergamot"])


class TestAreaFillController(unittest.TestCase):
    """The controller places a fill via the same dual-store bookkeeping the
    generator uses (markers + project features + one shared group)."""

    @classmethod
    def setUpClass(cls):
        import tempfile
        cls._tmp = tempfile.mkdtemp(prefix="permadesign_fill_test_")
        import src.db.plants as plants_mod
        plants_mod._DATA_DIR = cls._tmp
        plants_mod._DB_PATH = os.path.join(cls._tmp, "t.db")
        from src.db.plants import init_db, search_plants
        init_db()
        rows = search_plants()
        cls._a, cls._b = rows[0]["id"], rows[1]["id"]

    def _stub_main(self):
        import types
        calls = {"markers": 0}

        class MW:
            def place_plant_marker(self, *a, **k):
                calls["markers"] += 1

        class PP:
            def on_plants_placed_batch(self, batch):
                calls["batch"] = len(batch)

        class SB:
            def showMessage(self, *a, **k):
                pass

        main = types.SimpleNamespace(
            map_widget=MW(), plant_panel=PP(), _placed_plants=[],
            _project={"features": []},
            _plant_info=lambda pid: (1.0, "herb", None),
            _mark_modified=lambda: None, _sync_planning_panel=lambda: None,
            statusBar=lambda: SB())
        return main, calls

    def test_fill_places_into_both_stores(self):
        from src.controllers.area_fill_controller import AreaFillController
        main, calls = self._stub_main()
        n = AreaFillController(main).fill(
            _RING, [(self._a, 1), (self._b, 1)], spacing_m=6.0, poly_name="Mix")
        self.assertGreater(n, 0)
        self.assertEqual(calls["markers"], n)
        self.assertEqual(len(main._placed_plants), n)
        self.assertEqual(len(main._project["features"]), n)
        # all under one placement group (deletes as a unit)
        groups = {p["placement_group_id"] for p in main._placed_plants}
        self.assertEqual(len(groups), 1)
        # features are tagged as an area fill
        self.assertTrue(all(
            f["properties"]["pattern_kind"] == "area_fill"
            for f in main._project["features"]))

    def test_empty_ring_places_nothing(self):
        from src.controllers.area_fill_controller import AreaFillController
        main, _ = self._stub_main()
        self.assertEqual(
            AreaFillController(main).fill([], [(self._a, 1)], spacing_m=6.0), 0)
        self.assertEqual(main._placed_plants, [])

    # ── R3: fill with whole community units ──────────────────────────────────

    def _polyculture(self):
        return {"name": "Test Guild", "members": [
            {"plant_id": self._a, "common_name": "Centre Plant",
             "offset_x": 0.0, "offset_y": 0.0},
            {"plant_id": self._b, "common_name": "Edge Plant",
             "offset_x": 2.0, "offset_y": 0.0},
        ]}

    def test_fill_communities_places_whole_units(self):
        from src.controllers.area_fill_controller import AreaFillController
        main, calls = self._stub_main()
        n = AreaFillController(main).fill_communities(
            _RING, self._polyculture(), spacing_m=4.0)
        self.assertGreater(n, 0)
        # Every unit expands to BOTH members (units, not a member scatter).
        self.assertEqual(len(main._placed_plants), n * 2)
        self.assertEqual(calls["markers"], n * 2)
        # Each placement keeps its community centre + name (so it reads as a
        # community placement everywhere downstream).
        centres = set()
        for p in main._placed_plants:
            self.assertEqual(p["polyculture_name"], "Test Guild")
            centres.add((p["polyculture_center_lat"],
                         p["polyculture_center_lng"]))
        self.assertEqual(len(centres), n)   # one distinct centre per unit
        # The edge member sits ~2 m east of its unit's centre.
        import math
        edge = next(p for p in main._placed_plants
                    if p["common_name"] == "Edge Plant")
        dx = (edge["lng"] - edge["polyculture_center_lng"]) \
            * 111_320.0 * math.cos(math.radians(edge["lat"]))
        self.assertAlmostEqual(dx, 2.0, delta=0.05)
        # One shared placement group: the fill deletes as a unit.
        self.assertEqual(
            len({p["placement_group_id"] for p in main._placed_plants}), 1)

    def test_fill_communities_tiny_area_drops_one_at_centroid(self):
        from src.controllers.area_fill_controller import AreaFillController
        main, _ = self._stub_main()
        # A ~3 m square: far too small for the unit grid, but one unit fits.
        d = 3.0 / 111_320.0
        tiny = [[-113.5, _LAT], [-113.5 + d, _LAT],
                [-113.5 + d, _LAT + d], [-113.5, _LAT + d]]
        n = AreaFillController(main).fill_communities(
            tiny, self._polyculture(), spacing_m=4.0)
        self.assertEqual(n, 1)
        self.assertEqual(len(main._placed_plants), 2)

    def test_fill_communities_empty_members(self):
        from src.controllers.area_fill_controller import AreaFillController
        main, _ = self._stub_main()
        self.assertEqual(AreaFillController(main).fill_communities(
            _RING, {"name": "x", "members": []}, spacing_m=4.0), 0)

    def _community(self, name, a, b):
        return {"id": abs(hash(name)) % 100000, "name": name, "members": [
            {"plant_id": a, "common_name": "C", "offset_x": 0.0, "offset_y": 0.0},
            {"plant_id": b, "common_name": "E", "offset_x": 1.5, "offset_y": 0.0},
        ]}

    def test_fill_community_mix_scatters_both(self):
        from src.controllers.area_fill_controller import AreaFillController
        main, calls = self._stub_main()
        mix = [
            {"id": 1, "weight": 1, "name": "Guild A",
             "polyculture": self._community("Guild A", self._a, self._b)},
            {"id": 2, "weight": 1, "name": "Guild B",
             "polyculture": self._community("Guild B", self._b, self._a)},
        ]
        n = AreaFillController(main).fill_community_mix(_RING, mix, spacing_m=2.0)
        self.assertGreater(n, 1)
        names = {p["polyculture_name"] for p in main._placed_plants}
        self.assertEqual(names, {"Guild A", "Guild B"})   # both represented
        # 2 members per unit; one shared placement group.
        self.assertEqual(len(main._placed_plants), n * 2)
        self.assertEqual(
            len({p["placement_group_id"] for p in main._placed_plants}), 1)

    def test_fill_community_mix_empty(self):
        from src.controllers.area_fill_controller import AreaFillController
        main, _ = self._stub_main()
        self.assertEqual(
            AreaFillController(main).fill_community_mix(_RING, [], 2.0), 0)


if __name__ == "__main__":
    unittest.main()

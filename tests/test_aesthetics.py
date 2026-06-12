"""
tests/test_aesthetics.py — composition scoring for generated designs (V1.62).

Covers the pure aesthetic_score terms (tall-north/low-south gradient, bed
cohesion, repetition rhythm) and their integration in ScoredPositioner's
take_best (80% ecology / 20% composition). Synthetic grids, no DB, no Qt.
"""

import math
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.placement_score import (  # noqa: E402
    CellEnv, aesthetic_score, build_cell_env_map,
)
from src.llm_design import ScoredPositioner  # noqa: E402

_LAT0, _LNG0 = 53.5, -113.5
_SPACING_M = 6.0
_DLAT = _SPACING_M / 111320.0
_DLNG = _SPACING_M / (111320.0 * math.cos(math.radians(_LAT0)))


def _grid(rows=10, cols=10):
    """A rows×cols placement grid spaced 6 m, row 0 = south."""
    return [(_LAT0 + r * _DLAT, _LNG0 + c * _DLNG)
            for r in range(rows) for c in range(cols)]


def _dist_m(a, b):
    cos_lat = math.cos(a[0] * math.pi / 180)
    dx = (b[1] - a[1]) * 111320.0 * cos_lat
    dy = (b[0] - a[0]) * 111320.0
    return math.hypot(dx, dy)


_TREE = {"id": 1, "mature_height_meters": 10.0, "plant_type": "tree"}
_GROUNDCOVER = {"id": 2, "mature_height_meters": 0.2,
                "plant_type": "groundcover"}
_MID = {"id": 3, "mature_height_meters": 2.0, "plant_type": "shrub"}


class TestAestheticScore(unittest.TestCase):

    _RANGE = (_LAT0, _LAT0 + 9 * _DLAT)

    def _score(self, plant, cell, anchors=()):
        return aesthetic_score(plant, cell, lat_range=self._RANGE,
                               anchors=list(anchors), spacing_m=_SPACING_M)

    def test_tall_plants_prefer_north(self):
        south, north = (_LAT0, _LNG0), (self._RANGE[1], _LNG0)
        self.assertGreater(self._score(_TREE, north),
                           self._score(_TREE, south))

    def test_low_plants_prefer_south(self):
        south, north = (_LAT0, _LNG0), (self._RANGE[1], _LNG0)
        self.assertGreater(self._score(_GROUNDCOVER, south),
                           self._score(_GROUNDCOVER, north))

    def test_mid_height_is_gradient_neutral(self):
        south, north = (_LAT0, _LNG0), (self._RANGE[1], _LNG0)
        self.assertAlmostEqual(self._score(_MID, south),
                               self._score(_MID, north), places=6)

    def test_cohesion_prefers_joining_the_bed(self):
        anchor = (_LAT0 + 5 * _DLAT, _LNG0 + 5 * _DLNG, 1, 10.0)
        near = (_LAT0 + 5 * _DLAT, _LNG0 + 7 * _DLNG)    # 12 m — in band
        far = (_LAT0 + 5 * _DLAT, _LNG0 + 60 * _DLNG)    # 360 m — island
        self.assertGreater(self._score(_MID, near, [anchor]),
                           self._score(_MID, far, [anchor]))

    def test_rhythm_penalises_mega_clump(self):
        anchor = (_LAT0 + 5 * _DLAT, _LNG0 + 5 * _DLNG, _MID["id"], 2.0)
        fused = (_LAT0 + 5 * _DLAT, _LNG0 + 6 * _DLNG)   # 6 m — too close
        spaced = (_LAT0 + 5 * _DLAT, _LNG0 + 8 * _DLNG)  # 18 m — rhythmic
        self.assertGreater(self._score(_MID, spaced, [anchor]),
                           self._score(_MID, fused, [anchor]))

    def test_bounded_zero_one(self):
        for cell in [(_LAT0, _LNG0), (self._RANGE[1], _LNG0)]:
            for plant in (_TREE, _GROUNDCOVER, _MID, {}):
                s = self._score(plant, cell)
                self.assertGreaterEqual(s, 0.0)
                self.assertLessEqual(s, 1.0)

    def test_no_lat_range_is_neutral(self):
        s = aesthetic_score(_TREE, (_LAT0, _LNG0), lat_range=None,
                            anchors=[])
        self.assertAlmostEqual(s, 0.40 * 0.5 + 0.35 * 0.5 + 0.25 * 0.5,
                               places=6)


class TestPositionerIntegration(unittest.TestCase):
    """take_best on a uniform environment — ecology equal everywhere, so
    composition decides."""

    def _positioner(self):
        cells = _grid()
        return ScoredPositioner(build_cell_env_map(cells), None, cells), cells

    def test_tree_anchors_at_the_north_edge(self):
        pos, cells = self._positioner()
        anchor = pos.take_best(_TREE)
        self.assertAlmostEqual(anchor[0], max(c[0] for c in cells), places=9)

    def test_groundcover_lands_well_south_of_the_tree(self):
        # The gradient pulls low plants south while cohesion keeps them
        # attached to the bed — the optimum is "in front of the tree",
        # several rows south of it, not fused to it and not at the far
        # fence.
        pos, _ = self._positioner()
        tree_anchor = pos.take_best(_TREE)
        pos.note_anchor(tree_anchor, _TREE)
        gc_anchor = pos.take_best(_GROUNDCOVER)
        rows_south = (tree_anchor[0] - gc_anchor[0]) / _DLAT
        self.assertGreaterEqual(rows_south, 2.0)

    def test_second_species_joins_the_bed(self):
        pos, _ = self._positioner()
        a1 = pos.take_best(_MID)
        pos.note_anchor(a1, _MID)
        a2 = pos.take_best({"id": 9, "mature_height_meters": 2.0})
        d = _dist_m(a1, a2)
        self.assertLessEqual(d, _SPACING_M * 4 + 0.5)   # cohesion band
        self.assertGreater(d, 0.0)

    def test_same_species_repeats_at_rhythm_distance(self):
        pos, _ = self._positioner()
        a1 = pos.take_best(_MID)
        pos.note_anchor(a1, _MID)
        a2 = pos.take_best(_MID)
        d = _dist_m(a1, a2)
        self.assertGreaterEqual(d, _SPACING_M * 1.5 - 0.5)
        self.assertLessEqual(d, _SPACING_M * 5 + 0.5)

    def test_ecology_outvotes_composition(self):
        # A full-sun plant: the sunny southern cell must beat the shaded
        # northern cell even though tall plants 'want' to go north.
        sunny_south = (_LAT0, _LNG0)
        shaded_north = (_LAT0 + 9 * _DLAT, _LNG0)
        env = {
            sunny_south: CellEnv(0.0, 0.5, 0.0, -1.0, False),
            shaded_north: CellEnv(0.95, 0.5, 0.0, -1.0, False),
        }
        pos = ScoredPositioner(env, None, [sunny_south, shaded_north])
        tall_sun_lover = {"id": 5, "mature_height_meters": 8.0,
                          "plant_type": "tree", "sun_requirement": "full_sun"}
        anchor = pos.take_best(tall_sun_lover)
        self.assertEqual(anchor, sunny_south)


if __name__ == "__main__":
    unittest.main()

"""
tests/test_leaf_off_shade.py

Leaf-off winter shade (V2.13): declared-deciduous tree crowns cast a reduced
weight (bare branches) during the Oct–Apr leaf-off window, evergreens and
untagged trees keep the legacy opaque behaviour, and a cell under both a
full and a leaf-off caster takes the max, never the sum. Qt-free.
"""

import os
import sys
import unittest
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import shade
from src.projection import M_PER_DEG_LAT
import math

_LAT, _LNG = 53.5, -113.5      # Edmonton-ish
_SIZE_M = 40.0                 # site square, metres
_N = 21                        # odd → a grid line passes through the centre


def _elev():
    half_lat = (_SIZE_M / 2) / M_PER_DEG_LAT
    half_lng = (_SIZE_M / 2) / (M_PER_DEG_LAT * math.cos(math.radians(_LAT)))
    return {
        "grid": [[0.0] * _N for _ in range(_N)],
        "rows": _N, "cols": _N,
        "bbox": {"north": _LAT + half_lat, "south": _LAT - half_lat,
                 "east": _LNG + half_lng, "west": _LNG - half_lng},
    }


def _tree(foliage=None, lat=_LAT, lng=_LNG, height=8.0, radius=4.0):
    c = {"lat": lat, "lng": lng, "height_m": height, "radius_m": radius,
         "kind": "tree"}
    if foliage:
        c["foliage"] = foliage
    return c


_WINTER_NOON = datetime(2025, 12, 21, 12, 0)
_SUMMER_NOON = datetime(2025, 6, 21, 12, 0)


def _values(grid):
    return {round(v, 4) for row in grid for v in row}


class TestSplitCastersByLeaf(unittest.TestCase):

    def test_summer_everything_full(self):
        full, reduced = shade._split_casters_by_leaf(
            [_tree("deciduous"), _tree("evergreen"), _tree()], 6)
        self.assertEqual(len(full), 3)
        self.assertEqual(reduced, [])

    def test_winter_only_declared_deciduous_reduced(self):
        cs = [_tree("deciduous"), _tree("evergreen"), _tree()]
        full, reduced = shade._split_casters_by_leaf(cs, 12)
        self.assertEqual(len(reduced), 1)
        self.assertEqual(reduced[0]["foliage"], "deciduous")
        self.assertEqual(len(full), 2)

    def test_deciduous_building_never_reduced(self):
        b = {"lat": _LAT, "lng": _LNG, "height_m": 5.0, "radius_m": 4.0,
             "kind": "building", "foliage": "deciduous"}
        full, reduced = shade._split_casters_by_leaf([b], 1)
        self.assertEqual(reduced, [])
        self.assertEqual(len(full), 1)

    def test_no_month_means_full(self):
        full, reduced = shade._split_casters_by_leaf([_tree("deciduous")], None)
        self.assertEqual(reduced, [])
        self.assertEqual(len(full), 1)


class TestLeafOffWeighting(unittest.TestCase):

    def _grid_at(self, foliage, when):
        return shade.shade_grid_at([_tree(foliage)], _elev(), when,
                                   terrain=False)

    def test_winter_deciduous_casts_reduced_shade(self):
        vals = _values(self._grid_at("deciduous", _WINTER_NOON))
        self.assertIn(shade._LEAF_OFF_WEIGHT, vals)
        self.assertNotIn(1.0, vals)

    def test_winter_evergreen_casts_full_shade(self):
        vals = _values(self._grid_at("evergreen", _WINTER_NOON))
        self.assertIn(1.0, vals)
        self.assertNotIn(shade._LEAF_OFF_WEIGHT, vals)

    def test_winter_untagged_tree_keeps_legacy_full_shade(self):
        vals = _values(self._grid_at(None, _WINTER_NOON))
        self.assertIn(1.0, vals)
        self.assertNotIn(shade._LEAF_OFF_WEIGHT, vals)

    def test_summer_deciduous_casts_full_shade(self):
        vals = _values(self._grid_at("deciduous", _SUMMER_NOON))
        self.assertIn(1.0, vals)
        self.assertNotIn(shade._LEAF_OFF_WEIGHT, vals)

    def test_mixed_casters_take_max_not_sum(self):
        # A deciduous tree plus an untagged tree at the same spot: every cell
        # the untagged one shades reads 1.0 (max), nothing exceeds 1.0, and
        # no cell reads the 1.3 a sum would produce.
        grid = shade.shade_grid_at([_tree("deciduous"), _tree(None)],
                                   _elev(), _WINTER_NOON, terrain=False)
        vals = _values(grid)
        self.assertLessEqual(max(vals), 1.0)
        self.assertIn(1.0, vals)

    def test_offset_full_caster_leaves_reduced_cells_visible(self):
        # Deciduous tree at centre + untagged tree well to the east: cells
        # shaded only by the deciduous crown keep the reduced weight while the
        # untagged tree's cells read full — both weights present in one grid.
        east_lng = _LNG + 15.0 / (M_PER_DEG_LAT * math.cos(math.radians(_LAT)))
        grid = shade.shade_grid_at(
            [_tree("deciduous"), _tree(None, lng=east_lng)],
            _elev(), _WINTER_NOON, terrain=False)
        vals = _values(grid)
        self.assertIn(shade._LEAF_OFF_WEIGHT, vals)
        self.assertIn(1.0, vals)
        self.assertLessEqual(max(vals), 1.0)


class TestCastersFromProjectFoliage(unittest.TestCase):

    def _project(self, props):
        return {"features": [{
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [_LNG, _LAT]},
            "properties": props,
        }]}

    def test_existing_tree_carries_foliage(self):
        casters = shade.casters_from_project(self._project({
            "element_type": "existing_tree", "height_m": 6.0,
            "canopy_radius_m": 3.0, "tree_foliage": "deciduous"}))
        self.assertEqual(len(casters), 1)
        self.assertEqual(casters[0]["foliage"], "deciduous")

    def test_legacy_tree_has_no_foliage_key(self):
        casters = shade.casters_from_project(self._project({
            "element_type": "existing_tree", "height_m": 6.0,
            "canopy_radius_m": 3.0}))
        self.assertEqual(len(casters), 1)
        self.assertNotIn("foliage", casters[0])

    def test_drawn_tree_canopy_carries_foliage(self):
        ring = [[_LNG, _LAT], [_LNG + 1e-4, _LAT],
                [_LNG + 1e-4, _LAT + 1e-4], [_LNG, _LAT]]
        casters = shade.casters_from_project({"features": [{
            "type": "Feature",
            "geometry": {"type": "Polygon", "coordinates": [ring]},
            "properties": {"element_type": "canopy_footprint",
                           "height_m": 5.0, "canopy_radius_m": 3.0,
                           "caster_kind": "tree",
                           "tree_foliage": "evergreen"},
        }]})
        self.assertEqual(len(casters), 1)
        self.assertEqual(casters[0]["foliage"], "evergreen")

    def test_building_ignores_foliage(self):
        casters = shade.casters_from_project(self._project({
            "element_type": "existing_building", "height_m": 5.0,
            "canopy_radius_m": 4.0, "tree_foliage": "deciduous"}))
        self.assertEqual(len(casters), 1)
        self.assertNotIn("foliage", casters[0])


if __name__ == "__main__":
    unittest.main()

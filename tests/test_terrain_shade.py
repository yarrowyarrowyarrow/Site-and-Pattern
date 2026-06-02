"""
tests/test_terrain_shade.py

V1.55 — DEM horizon ray-march for terrain self-shadowing. Pure geometry on
synthetic elevation grids; no Qt, no network. Exercises both the numpy and the
pure-Python paths (the latter forced via the ``_HAVE_NUMPY`` flag so it is
covered even where numpy is installed).
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import src.terrain_shade as ts  # noqa: E402

# ~ a 45 m square at Edmonton-ish latitude on a 9×9 grid → ~5.5 m cells, the
# same scale as tests/test_shade.py.
_N = 9
_BBOX = {"north": 53.50020, "south": 53.49980,
         "east": -113.49966, "west": -113.50034}


def _flat(z=100.0):
    return {"grid": [[z] * _N for _ in range(_N)], "rows": _N, "cols": _N,
            "bbox": _BBOX}


def _ns_ridge(col, height, base=100.0):
    """A single tall N–S wall at column ``col`` (a ridge running north-south),
    flat ``base`` elsewhere."""
    grid = [[base] * _N for _ in range(_N)]
    for r in range(_N):
        grid[r][col] = base + height
    return {"grid": grid, "rows": _N, "cols": _N, "bbox": _BBOX}


def _total(mask):
    return sum(v for row in mask for v in row)


class TestHasRelief(unittest.TestCase):
    def test_flat_has_no_relief(self):
        self.assertFalse(ts.has_relief(_flat()))

    def test_ridge_has_relief(self):
        self.assertTrue(ts.has_relief(_ns_ridge(4, 20.0)))

    def test_empty_grid_has_no_relief(self):
        self.assertFalse(ts.has_relief({"grid": []}))


class TestTerrainShadowMask(unittest.TestCase):
    def test_flat_grid_returns_none(self):
        # No relief → nothing to cast; the caller keeps footprint-only behaviour.
        self.assertIsNone(ts.terrain_shadow_mask(_flat(), 90.0, 20.0))

    def test_low_sun_returns_full_shaped_mask(self):
        m = ts.terrain_shadow_mask(_ns_ridge(4, 20.0), 90.0, 20.0)
        self.assertIsNotNone(m)
        self.assertEqual(len(m), _N)
        self.assertTrue(all(len(row) == _N for row in m))
        self.assertTrue(all(v in (0.0, 1.0) for row in m for v in row))

    def test_sun_below_horizon_returns_none(self):
        # Altitude at/under the useful-shadow floor → no mask.
        self.assertIsNone(ts.terrain_shadow_mask(_ns_ridge(4, 30.0), 90.0, 3.0))

    def test_zenith_casts_nothing(self):
        # Sun nearly overhead → a 20 m wall casts essentially no shadow.
        m = ts.terrain_shadow_mask(_ns_ridge(4, 20.0), 90.0, 89.0)
        self.assertIsNotNone(m)
        self.assertEqual(_total(m), 0.0)

    def test_ridge_shadows_its_western_lee_under_an_eastern_sun(self):
        # Sun due east (az=90), low (alt=15°): the N–S wall at col 4 blocks the
        # sun from the cells to its WEST (cols < 4), which fall into shadow.
        # Cells EAST of the wall (cols > 4) see the eastern sun unobstructed.
        m = ts.terrain_shadow_mask(_ns_ridge(4, 30.0), 90.0, 15.0)
        self.assertIsNotNone(m)
        west = sum(m[r][c] for r in range(_N) for c in range(0, 4))
        east = sum(m[r][c] for r in range(_N) for c in range(5, _N))
        self.assertGreater(west, 0.0)
        self.assertEqual(east, 0.0)

    def test_shadow_flips_with_the_sun(self):
        # Same ridge, sun now in the WEST (az=270): the lee is on the EAST side.
        m = ts.terrain_shadow_mask(_ns_ridge(4, 30.0), 270.0, 15.0)
        self.assertIsNotNone(m)
        west = sum(m[r][c] for r in range(_N) for c in range(0, 4))
        east = sum(m[r][c] for r in range(_N) for c in range(5, _N))
        self.assertGreater(east, 0.0)
        self.assertEqual(west, 0.0)


class TestNumpyAndPythonPaths(unittest.TestCase):
    def _python_mask(self, *args):
        orig = ts._HAVE_NUMPY
        try:
            ts._HAVE_NUMPY = False
            return ts.terrain_shadow_mask(*args)
        finally:
            ts._HAVE_NUMPY = orig

    def test_pure_python_path_masks_the_lee(self):
        m = self._python_mask(_ns_ridge(4, 30.0), 90.0, 15.0)
        self.assertIsNotNone(m)
        self.assertGreater(_total(m), 0.0)

    def test_python_matches_default_path(self):
        # Where numpy is installed this cross-checks the two implementations;
        # where it is absent both sides are the Python path (trivially equal).
        ridge = _ns_ridge(4, 30.0)
        self.assertEqual(self._python_mask(ridge, 90.0, 15.0),
                         ts.terrain_shadow_mask(ridge, 90.0, 15.0))


if __name__ == "__main__":
    unittest.main()

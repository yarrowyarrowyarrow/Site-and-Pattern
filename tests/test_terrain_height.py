"""
tests/test_terrain_height.py — the ground under everything in the 3D scene.

`terrainHeightAt` (html/scene3d/02-plants.js) answers "how high is the ground
here?" for plants, flowers, wildlife, GLB structures, walk-mode footing, the bee
camera and the inspect card. One function, six callers, so a fault in it shows up
as six unrelated-looking bugs.

It had one: the cell indices were clamped to the grid but the interpolation
FRACTIONS were not, so a point outside the terrain bbox turned the bilinear blend
into a linear extrapolation and the ground climbed away into the sky. A tester
reported it as "some plants are flying in the air rather than being on the
ground" (V2.38).

Ported to Python rather than driven through a browser, the same way
tests/test_pattern_placement.py ports the map's pattern geometry — with a source
guard below so the port cannot quietly drift from the JS it mirrors.
"""

import os
import pathlib
import re
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_JS = (pathlib.Path(__file__).resolve().parent.parent
       / "html" / "scene3d" / "02-plants.js")


def terrain_height_at(scene_x, scene_y, t):
    """Port of the JS. Keep behaviourally identical."""
    if not t or t["rows"] < 2 or t["cols"] < 2:
        return 0
    col = (scene_x - t["min_x"]) / (t["max_x"] - t["min_x"]) * (t["cols"] - 1)
    row = (t["max_y"] - scene_y) / (t["max_y"] - t["min_y"]) * (t["rows"] - 1)
    c0 = max(0, min(t["cols"] - 2, int(col // 1)))
    r0 = max(0, min(t["rows"] - 2, int(row // 1)))
    fc = min(1.0, max(0.0, col - c0))
    fr = min(1.0, max(0.0, row - r0))
    h = t["heights"]
    h00, h01 = h[r0][c0], h[r0][c0 + 1]
    h10, h11 = h[r0 + 1][c0], h[r0 + 1][c0 + 1]
    return (h00 * (1 - fc) + h01 * fc) * (1 - fr) + (h10 * (1 - fc) + h11 * fc) * fr


# A gentle north-facing slope: 2 m of fall over 100 m. Nothing exotic — this is
# an ordinary yard, which is the point.
_SLOPE = {"rows": 3, "cols": 3, "min_x": -50, "max_x": 50,
          "min_y": -50, "max_y": 50,
          "heights": [[2, 2, 2], [1, 1, 1], [0, 0, 0]]}


class TestInsideTheGrid(unittest.TestCase):
    def test_centre_interpolates(self):
        self.assertAlmostEqual(terrain_height_at(0, 0, _SLOPE), 1.0, places=6)

    def test_corners_are_exact(self):
        self.assertAlmostEqual(terrain_height_at(-50, 50, _SLOPE), 2.0, places=6)
        self.assertAlmostEqual(terrain_height_at(50, -50, _SLOPE), 0.0, places=6)

    def test_it_still_interpolates_between_samples(self):
        """The clamp must not flatten the terrain it exists to follow."""
        quarter = terrain_height_at(0, 25, _SLOPE)
        self.assertGreater(quarter, 1.0)
        self.assertLess(quarter, 2.0)


class TestOutsideTheGrid(unittest.TestCase):
    """The bug. Outside the bbox the height must settle to the nearest edge, not
    keep climbing along the last known slope."""

    def test_far_outside_does_not_fly(self):
        for metres in (10, 50, 200, 1000, 10_000):
            with self.subTest(metres=metres):
                h = terrain_height_at(0, 50 + metres, _SLOPE)
                self.assertAlmostEqual(
                    h, 2.0, places=6,
                    msg=f"{metres} m outside the grid returned {h:.1f} m — "
                        f"the ground is extrapolating again")

    def test_the_other_three_sides_too(self):
        self.assertAlmostEqual(terrain_height_at(0, -1000, _SLOPE), 0.0, places=6)
        self.assertAlmostEqual(terrain_height_at(-1000, 0, _SLOPE), 1.0, places=6)
        self.assertAlmostEqual(terrain_height_at(1000, 0, _SLOPE), 1.0, places=6)

    def test_diagonal_corners_clamp_on_both_axes(self):
        self.assertAlmostEqual(terrain_height_at(9e3, 9e3, _SLOPE), 2.0, places=6)
        self.assertAlmostEqual(terrain_height_at(-9e3, -9e3, _SLOPE), 0.0, places=6)

    def test_a_steeper_grid_still_settles(self):
        """The failure scaled with slope, so a steep grid is the harder case."""
        steep = dict(_SLOPE, heights=[[40, 40, 40], [20, 20, 20], [0, 0, 0]])
        self.assertAlmostEqual(terrain_height_at(0, 5000, steep), 40.0, places=6)

    def test_no_terrain_is_ground_level(self):
        self.assertEqual(terrain_height_at(0, 0, None), 0)
        self.assertEqual(terrain_height_at(0, 0, {"rows": 1, "cols": 1}), 0)


class TestPortMatchesTheJs(unittest.TestCase):
    """Source guard: this file is only worth anything while it mirrors the JS."""

    @classmethod
    def setUpClass(cls):
        src = _JS.read_text(encoding="utf-8")
        start = src.index("function terrainHeightAt(")
        cls.fn = src[start:src.index("\n}", start)]

    def test_both_fractions_are_clamped(self):
        for name in ("fc", "fr"):
            m = re.search(rf"const {name} = (.+?);", self.fn)
            self.assertIsNotNone(m, f"{name} not found — did the JS change shape?")
            expr = m.group(1)
            self.assertIn("Math.min(1", expr.replace(" ", ""),
                          f"{name} is no longer clamped: {expr!r}")
            self.assertIn("Math.max(0", expr.replace(" ", ""),
                          f"{name} is no longer clamped: {expr!r}")

    def test_the_cell_indices_are_still_clamped(self):
        self.assertIn("Math.min(t.cols - 2", self.fn)
        self.assertIn("Math.min(t.rows - 2", self.fn)

    def test_every_caller_goes_through_this_one_function(self):
        """Six surfaces depend on it; a hand-rolled second copy would drift."""
        base = _JS.parent
        callers = [p.name for p in sorted(base.glob("*.js"))
                   if "terrainHeightAt(" in p.read_text(encoding="utf-8")]
        self.assertGreaterEqual(len(callers), 5, callers)
        defs = [p.name for p in sorted(base.glob("*.js"))
                if "function terrainHeightAt(" in p.read_text(encoding="utf-8")]
        self.assertEqual(defs, ["02-plants.js"],
                         f"terrain height is defined in more than one place: {defs}")


if __name__ == "__main__":
    unittest.main()

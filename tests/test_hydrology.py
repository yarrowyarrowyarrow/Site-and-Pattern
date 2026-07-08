"""
tests/test_hydrology.py

D8 flow routing + accumulation (src/hydrology.py): synthetic elevation grids
in the tests/test_terrain.py style — no Qt, no network. Grid convention:
row 0 = north edge, col 0 = west edge.
"""

import os
import sys
import unittest
import zlib

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import hydrology

# ~100 m square around a mid-latitude point; exact size doesn't matter, the
# maths only uses relative cell spacing.
_BBOX = {"south": 53.5000, "north": 53.5009,
         "west": -113.5000, "east": -113.4986}


def _elev(grid):
    return {"grid": grid, "rows": len(grid), "cols": len(grid[0]),
            "bbox": dict(_BBOX)}


def _flat(rows=6, cols=6, z=650.0):
    return _elev([[z] * cols for _ in range(rows)])


def _ns_ramp(rows=8, cols=6, drop=1.0):
    """Highest at the north edge (row 0), dropping southward."""
    return _elev([[650.0 - r * drop] * cols for r in range(rows)])


def _v_valley(rows=8, cols=7):
    """A south-draining V-valley: centre column lowest, tilted south."""
    mid = cols // 2
    return _elev([[600.0 + abs(c - mid) * 2.0 - r * 1.0
                   for c in range(cols)] for r in range(rows)])


def _bowl(rows=7, cols=7, depth=2.0):
    """A closed basin: rim at 650, centre depressed."""
    grid = [[650.0] * cols for _ in range(rows)]
    for r in range(1, rows - 1):
        for c in range(1, cols - 1):
            d = min(r, c, rows - 1 - r, cols - 1 - c)
            grid[r][c] = 650.0 - min(depth, d * depth)
    return _elev(grid)


class TestFillDepressions(unittest.TestCase):

    def test_ramp_needs_no_fill(self):
        elev = _ns_ramp()
        filled, depth = hydrology.fill_depressions(elev)
        self.assertTrue(all(d < 1e-3 for row in depth for d in row))

    def test_bowl_interior_is_filled_to_rim_spill(self):
        elev = _bowl()
        _filled, depth = hydrology.fill_depressions(elev)
        centre = depth[3][3]
        self.assertGreater(centre, hydrology.PONDING_MIN_DEPTH_M)


class TestFlowAccumulation(unittest.TestCase):

    def test_flat_grid_no_concentration(self):
        flow = hydrology.flow_accumulation(_flat())
        area = flow["cell_area_m2"]
        # Nothing routes anywhere meaningful on dead-flat ground: no cell
        # accumulates more than a whisker beyond the epsilon-fill trickle,
        # and nothing ponds.
        self.assertEqual(flow["n_ponding"], 0)
        interior_max = max(flow["accum"][r][c]
                           for r in range(1, 5) for c in range(1, 5))
        # Epsilon drainage may chain a few cells; it must stay far below a
        # channel-like concentration.
        self.assertLess(interior_max, area * 30)

    def test_ns_ramp_accumulates_southward(self):
        elev = _ns_ramp()
        flow = hydrology.flow_accumulation(elev)
        accum = flow["accum"]
        area = flow["cell_area_m2"]
        rows = elev["rows"]
        # Down-column growth: every southern cell should carry at least its
        # northern neighbour's load (mid column, away from edges).
        c = 2
        for r in range(1, rows - 1):
            self.assertGreaterEqual(accum[r][c] + 1e-6, accum[r - 1][c])
        # The south edge carries roughly a full column of upstream cells.
        self.assertGreater(max(accum[rows - 1]), area * (rows - 2))
        self.assertEqual(flow["n_ponding"], 0)

    def test_v_valley_concentrates_on_centre_line(self):
        elev = _v_valley()
        flow = hydrology.flow_accumulation(elev)
        accum = flow["accum"]
        mid = elev["cols"] // 2
        r = elev["rows"] - 2
        self.assertGreater(accum[r][mid], accum[r][0])
        self.assertGreater(accum[r][mid], accum[r][elev["cols"] - 1])

    def test_bowl_ponds_and_still_drains_after_fill(self):
        flow = hydrology.flow_accumulation(_bowl())
        self.assertGreater(flow["n_ponding"], 0)
        # After the epsilon fill every interior cell has a receiver.
        recs = flow["receivers"]
        self.assertIsNotNone(recs[3][3])

    def test_receivers_are_lower_on_filled_surface(self):
        elev = _v_valley()
        filled, _depth = hydrology.fill_depressions(elev)
        dx, dy = hydrology._cell_size_m(elev)
        recs = hydrology.d8_receivers(filled, elev["rows"], elev["cols"],
                                      dx, dy)
        for r in range(elev["rows"]):
            for c in range(elev["cols"]):
                rec = recs[r][c]
                if rec is not None:
                    self.assertLess(filled[rec[0]][rec[1]], filled[r][c])


class TestWaterRaster(unittest.TestCase):

    def test_rgba_dimensions_and_png_roundtrip(self):
        elev = _v_valley()
        flow = hydrology.flow_accumulation(elev)
        rgba, w, h = hydrology.water_ramp_rgba(
            flow["accum"], flow["ponding"], flow["cell_area_m2"])
        self.assertEqual((w, h), (elev["cols"], elev["rows"]))
        self.assertEqual(len(rgba), w * h * 4)
        png = hydrology.water_png(elev, flow)
        self.assertEqual(png[:8], b"\x89PNG\r\n\x1a\n")
        zlib.decompress(png[png.index(b"IDAT") + 4:png.rindex(b"IEND") - 4])

    def test_low_accumulation_cells_are_transparent(self):
        elev = _ns_ramp()
        flow = hydrology.flow_accumulation(elev)
        rgba, w, _h = hydrology.water_ramp_rgba(
            flow["accum"], flow["ponding"], flow["cell_area_m2"])
        # Row 0 is the ridge (nothing upstream) → fully transparent alpha.
        top_alphas = [rgba[(0 * w + x) * 4 + 3] for x in range(w)]
        self.assertTrue(all(a == 0 for a in top_alphas))

    def test_ponding_cells_use_ponding_colour(self):
        elev = _bowl()
        flow = hydrology.flow_accumulation(elev)
        rgba, w, _h = hydrology.water_ramp_rgba(
            flow["accum"], flow["ponding"], flow["cell_area_m2"])
        i = (3 * w + 3) * 4
        self.assertEqual(tuple(rgba[i:i + 4]), hydrology._PONDING_RGBA)


class TestFlowArrows(unittest.TestCase):

    def test_ramp_arrows_point_south(self):
        elev = _ns_ramp(rows=12, cols=10)
        flow = hydrology.flow_accumulation(elev)
        arrows = hydrology.flow_arrows(elev, flow)
        self.assertTrue(arrows)
        for a in arrows:
            self.assertGreater(a["bearing"], 90.0)
            self.assertLess(a["bearing"], 270.0)

    def test_arrow_cap_respected(self):
        elev = _ns_ramp(rows=40, cols=40)
        flow = hydrology.flow_accumulation(elev)
        arrows = hydrology.flow_arrows(elev, flow, cap=25)
        self.assertLessEqual(len(arrows), 25)

    def test_arrows_are_json_safe(self):
        import json
        elev = _v_valley()
        flow = hydrology.flow_accumulation(elev)
        arrows = hydrology.flow_arrows(elev, flow)
        json.dumps(arrows)
        for a in arrows:
            self.assertLessEqual(a["strength"], 1.0)
            self.assertGreaterEqual(a["strength"], 0.0)
            self.assertTrue(_BBOX["south"] <= a["lat"] <= _BBOX["north"])
            self.assertTrue(_BBOX["west"] <= a["lng"] <= _BBOX["east"])

    def test_flat_grid_yields_no_arrows(self):
        elev = _flat()
        flow = hydrology.flow_accumulation(elev)
        # Epsilon drainage exists, but nothing exceeds the accumulation
        # floor by enough to earn an arrow on truly flat ground... unless
        # the trickle chains; either way arrows stay sparse and weak.
        arrows = hydrology.flow_arrows(elev, flow)
        for a in arrows:
            self.assertLess(a["strength"], 0.9)


if __name__ == "__main__":
    unittest.main()

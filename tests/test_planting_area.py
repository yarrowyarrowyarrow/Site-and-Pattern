"""
tests/test_planting_area.py — one planting area, one mulch depth (V3.20, OV-3).

The Report card, the planting plan and three pages of the PDF each summed the
area of every drawn shape and bought mulch for it, so drawing a path made the
mulch dearer (OVF-3), and the cost used 7.5 cm of mulch where the site-prep
sheet said 5–8 cm. Each now asks ``yard_overview.bed_area_m2``.
"""

import math
import os
import re
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import sourcing, yard_overview  # noqa: E402

try:
    import shapely  # noqa: F401
    _HAVE_SHAPELY = True
except ImportError:                                        # pragma: no cover
    _HAVE_SHAPELY = False

_LAT, _LNG = 53.5461, -113.4938          # central Edmonton
_M_LAT = 111320.0
_M_LNG = 111320.0 * math.cos(math.radians(_LAT))


def _square(east, north, w, h):
    """A ``[lng, lat]`` ring ``w`` × ``h`` m, its corner ``east``, ``north``
    metres from the origin."""
    pts = [(east, north), (east + w, north), (east + w, north + h),
           (east, north + h), (east, north)]
    return [[_LNG + x / _M_LNG, _LAT + y / _M_LAT] for x, y in pts]


def _feature(kind, ring, shape_type=None):
    props = {"element_type": kind}
    if shape_type:
        props["shape_type"] = shape_type
    return {"type": "Feature", "properties": props,
            "geometry": {"type": "Polygon", "coordinates": [ring]}}


def _project(*features):
    return {"type": "FeatureCollection", "features": list(features)}


BOUNDARY = _feature("property_boundary", _square(0, 0, 20, 10))       # 200 m²
PATH = _feature("custom_shape", _square(1, 1, 10, 1), "Pathway")       # 10 m²
BED = _feature("custom_shape", _square(5, 4, 5, 4), "Garden Bed")      # 20 m²
HOUSE = _feature("canopy_footprint", _square(12, 2, 6, 5),
                 "Building (OSM)")                                    # 30 m²


class ThePlantingArea(unittest.TestCase):

    def test_a_bed_is_the_planting_area_and_a_path_is_not(self):
        area = yard_overview.bed_area_m2(_project(BOUNDARY, PATH, BED))
        self.assertAlmostEqual(area, 20.0, delta=0.2)

    def test_a_boundary_alone_is_planted_whole(self):
        self.assertAlmostEqual(yard_overview.bed_area_m2(_project(BOUNDARY)),
                               200.0, delta=1.0)

    def test_with_no_bed_the_path_lawn_and_house_come_off(self):
        lawn = _feature("custom_shape", _square(0, 7, 20, 3), "Lawn Area")
        area = yard_overview.bed_area_m2(
            _project(BOUNDARY, PATH, HOUSE, lawn))
        self.assertAlmostEqual(area, 200 - 10 - 30 - 60, delta=1.0)

    def test_a_tree_canopy_is_not_a_building(self):
        canopy = _feature("canopy_footprint", _square(2, 2, 3, 3),
                          "Tree canopy")
        self.assertAlmostEqual(
            yard_overview.bed_area_m2(_project(BOUNDARY, canopy)),
            200.0, delta=1.0)

    @unittest.skipUnless(_HAVE_SHAPELY, "shapely not installed in this env")
    def test_overlapping_beds_count_once(self):
        other = _feature("custom_shape", _square(7, 4, 5, 4), "Mulch Area")
        self.assertAlmostEqual(
            yard_overview.bed_area_m2(_project(BED, other)), 28.0, delta=0.3)

    def test_nothing_drawn_is_nothing(self):
        self.assertEqual(yard_overview.bed_area_m2(_project()), 0.0)
        self.assertEqual(yard_overview.bed_area_m2({}), 0.0)


class OneDepthOfMulch(unittest.TestCase):

    def test_the_cost_and_the_sheet_use_one_depth(self):
        from src.site_prep import MULCH_DEPTH_CM, build_site_prep
        prep = build_site_prep({}, [], bed_area_m2=20.0,
                               get_plant=lambda _p: {})
        self.assertEqual((prep.mulch_m3_low, prep.mulch_m3_high),
                         (round(20 * MULCH_DEPTH_CM[0] / 100, 1),
                          round(20 * MULCH_DEPTH_CM[1] / 100, 1)))
        lo, hi = sourcing.mulch_cost(20.0)
        self.assertAlmostEqual(lo, prep.mulch_m3_low
                               * sourcing.MULCH_PRICE_PER_M3[0], places=1)
        self.assertAlmostEqual(hi, prep.mulch_m3_high
                               * sourcing.MULCH_PRICE_PER_M3[1], places=1)

    def test_a_path_does_not_change_the_mulch_cost(self):
        with_path = sourcing.design_cost(
            [], mulch_area_m2=yard_overview.bed_area_m2(
                _project(BOUNDARY, BED, PATH)))
        without = sourcing.design_cost(
            [], mulch_area_m2=yard_overview.bed_area_m2(
                _project(BOUNDARY, BED)))
        self.assertEqual(with_path["mulch"], without["mulch"])


class NoPlaceSumsTheShapesItself(unittest.TestCase):
    """The five copies of the sum are gone, and none comes back."""

    def test_no_custom_shape_area_sum(self):
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        sum_of_shapes = re.compile(
            r'get\("area_m2"\)[^\n]*\n[^\n]*\n[^\n]*"custom_shape"')
        for name in ("app.py", "pdf_export.py", "planting_plan_export.py"):
            with open(os.path.join(root, "src", name), encoding="utf-8") as fh:
                self.assertIsNone(sum_of_shapes.search(fh.read()), name)


if __name__ == "__main__":
    unittest.main()

"""
tests/test_landing_check.py — where a placement landed, in words (F198, V3.05).

The V2.98 review placed four shrubs that came down half outside the yard, on
top of grasses and wildflowers, and nothing said so. src/landing_check.py says
so; it never refuses, so these tests check what it says, not what it allows.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import landing_check as lc  # noqa: E402

LAT, LNG = 53.5, -113.5
M_LAT = 1 / 111320.0                       # one metre of latitude
M_LNG = 1 / (111320.0 * 0.5948)            # one metre of longitude at 53.5°


def at(east_m, north_m, pid=1, name="Saskatoon Berry"):
    return {"plant_id": pid, "common_name": name,
            "lat": LAT + north_m * M_LAT, "lng": LNG + east_m * M_LNG}


# A 10 m square yard, as [lat, lng].
YARD = [[LAT, LNG], [LAT, LNG + 10 * M_LNG], [LAT + 10 * M_LAT, LNG + 10 * M_LNG],
        [LAT + 10 * M_LAT, LNG], [LAT, LNG]]


def radius(pid):
    return {1: 0.75, 2: 0.15}.get(pid, 0.5)        # shrub, grass


class TestWhereItLanded(unittest.TestCase):

    def test_half_a_row_outside_the_yard(self):
        row = [at(8, 5), at(9.5, 5), at(11, 5), at(12.5, 5)]
        got = lc.check(row, [], [YARD], radius)
        self.assertEqual((got.placed, got.outside), (4, 2))
        self.assertEqual(lc.note(got), "2 of 4 landed outside the boundary.")

    def test_on_top_of_a_grass(self):
        grass = at(5, 5, pid=2, name="Blue Grama Grass")
        shrub = at(5.3, 5)                         # inside the shrub's 0.75 m
        got = lc.check([shrub], [grass], [YARD], radius)
        self.assertEqual(got.on_top, [("Saskatoon Berry", "Blue Grama Grass")])
        self.assertEqual(lc.note(got),
                         "It sits inside Blue Grama Grass's circle.")

    def test_clear_ground_says_nothing(self):
        got = lc.check([at(5, 5)], [at(1, 1, pid=2)], [YARD], radius)
        self.assertEqual(lc.note(got), "")

    def test_no_boundary_is_not_outside_one(self):
        got = lc.check([at(50, 50)], [], [], radius)
        self.assertEqual(got.outside, 0)
        self.assertFalse(got.has_boundary)
        self.assertEqual(lc.note(got), "")

    def test_both_at_once_in_one_sentence(self):
        grass = at(5, 5, pid=2, name="Blue Grama Grass")
        got = lc.check([at(5.2, 5), at(20, 5)], [grass], [YARD], radius)
        self.assertEqual(
            lc.note(got),
            "1 of 2 landed outside the boundary; 1 sits inside Blue Grama "
            "Grass's circle.")

    def test_the_boundary_is_read_off_the_project(self):
        project = {"features": [{
            "type": "Feature",
            "geometry": {"type": "Polygon",
                         "coordinates": [[[p[1], p[0]] for p in YARD]]},
            "properties": {"element_type": "property_boundary"}}]}
        rings = lc.boundary_rings(project)
        self.assertEqual(len(rings), 1)
        self.assertEqual(lc.check([at(20, 20)], [], rings, radius).outside, 1)


if __name__ == "__main__":
    unittest.main()

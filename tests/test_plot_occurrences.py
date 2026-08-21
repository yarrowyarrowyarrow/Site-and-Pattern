"""
The occurrence plotter (F139, V2.75).

An outside botanical review asked what the published site could not answer:
*where in the ecoregion are those records?* Every range on the site is a
whole-polygon shade derived from a count, so a species clustered in ten
kilometres at the mountain front and a species spread across the whole region
draw the same picture.

These tests run against a synthetic cache, because the real one is a dev
artefact written by a run with egress and is not in the repo. What they pin is
the part that can be wrong silently: whether a dot lands where the coordinate
actually is.
"""

import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import scripts.plot_occurrences as P              # noqa: E402
import scripts.seed_ecoregion_ranges as S        # noqa: E402

_O = S.Occurrence

#: Inside Northern Continental Divide, within 5 km of Aspen Parkland. The
#: review's own hypothetical -- "a mountain species that shows up in Aspen
#: Parkland" -- as a coordinate.
MONTANE_NEAR_PARKLAND = (50.1165, -114.2478)
EDMONTON = (53.55, -113.49)                       # well inside aspen_parkland


class TestADotLandsWhereTheCoordinateIs(unittest.TestCase):
    """The one thing this tool can get wrong without anybody noticing.

    A second projector 2% off the one the shading uses would put dots just
    outside their own regions, which reads as a data error and would send
    somebody hunting the wrong bug. So the overlay goes through
    `ecoregion_map.projector`, and this proves it agrees with the polygons.
    """

    def test_an_edmonton_dot_falls_inside_the_parkland_polygon(self):
        from src.ecoregion_map import (frame_height, projector,
                                       region_geometry)
        width = 720
        project = projector(width, frame_height(width))
        x, y = project(EDMONTON[1], EDMONTON[0])

        # The same polygon, through the same projector, in SVG space.
        rings = [[project(lon, lat) for lon, lat in ring]
                 for ring in region_geometry()["aspen_parkland"]]
        self.assertTrue(
            any(_point_in_ring_xy(x, y, ring) for ring in rings),
            "the dot for Edmonton did not land inside Aspen Parkland")

    def test_a_montane_dot_does_not_land_in_the_parkland(self):
        """The negative case, which is the one that matters here: the buffer
        bug made a montane record *count* as parkland, and a plotter that drew
        it inside the parkland would corroborate the error instead of showing
        it."""
        from src.ecoregion_map import (frame_height, projector,
                                       region_geometry)
        width = 720
        project = projector(width, frame_height(width))
        x, y = project(MONTANE_NEAR_PARKLAND[1], MONTANE_NEAR_PARKLAND[0])
        rings = [[project(lon, lat) for lon, lat in ring]
                 for ring in region_geometry()["aspen_parkland"]]
        self.assertFalse(any(_point_in_ring_xy(x, y, ring) for ring in rings))

    def test_the_overlay_is_drawn_above_the_regions(self):
        svg = P.species_svg("Testus", [_O(*EDMONTON)], width=420)
        self.assertLess(svg.index("class=\"occ\""), svg.rindex("</svg>"))
        self.assertGreater(svg.index("class=\"occ\""),
                           svg.index("</path>") if "</path>" in svg else 0)


def _point_in_ring_xy(x, y, ring) -> bool:
    """Ray casting in SVG space — deliberately a second implementation.

    Reusing `ecoregion._point_in_ring` would test the projector against
    itself; this asks whether the drawing agrees with the geometry.
    """
    inside = False
    n = len(ring)
    for i in range(n):
        x1, y1 = ring[i]
        x2, y2 = ring[(i + 1) % n]
        if (y1 > y) != (y2 > y):
            xin = (x2 - x1) * (y - y1) / ((y2 - y1) or 1e-12) + x1
            if x < xin:
                inside = not inside
    return inside


class TestUncertaintyIsVisible(unittest.TestCase):
    """A 30 m GPS fix and a 5 km 'near the lake' are different observations,
    and the pipeline treated them as one until V2.75."""

    def test_a_coarser_record_gets_a_bigger_dot(self):
        tight = P._radius(50.0, scale=0.01)
        loose = P._radius(5_000.0, scale=0.01)
        self.assertGreater(loose, tight)

    def test_an_unrecorded_uncertainty_is_drawn_hollow(self):
        """Not recorded and recorded-as-precise must not look the same (P9)."""
        from src.ecoregion_map import frame_height, projector
        project = projector(420, frame_height(420))
        blank = P.points_svg([_O(*EDMONTON, None)], project, scale=0.01)
        known = P.points_svg([_O(*EDMONTON, 40.0)], project, scale=0.01)
        self.assertIn('fill="none"', blank)
        self.assertNotIn('fill="none"', known)

    def test_a_huge_uncertainty_is_capped(self):
        """One county-level record must not cover a fifth of the map and read
        as a claim rather than a caveat."""
        self.assertEqual(P._radius(10_000_000.0, scale=1.0), P._MAX_R)

    def test_the_tooltip_says_when_nothing_was_recorded(self):
        from src.ecoregion_map import frame_height, projector
        project = projector(420, frame_height(420))
        svg = P.points_svg([_O(*EDMONTON, None)], project, scale=0.01)
        self.assertIn("uncertainty unrecorded", svg)


class TestBufferArtefacts(unittest.TestCase):
    """The measurement, not the argument.

    An artefact is a (species, region) pair the buffered lookup would claim and
    containment does not. It is how the cost of the V2.67 bug is reported as a
    number rather than reasoned about.
    """

    def test_a_montane_species_stops_claiming_parkland(self):
        cache = {"Aster alpinus": [_O(*MONTANE_NEAR_PARKLAND, 30.0)] * 6}
        total, artefacts, worst = P.buffer_artefacts(cache)
        self.assertEqual(artefacts, 1)
        self.assertIn(("Aster alpinus", "aspen_parkland", 6), worst)

    def test_a_species_well_inside_a_region_has_no_artefact(self):
        cache = {"Amelanchier alnifolia": [_O(*EDMONTON, 20.0)] * 30}
        total, artefacts, _worst = P.buffer_artefacts(cache)
        self.assertEqual(total, 1)
        self.assertEqual(artefacts, 0)

    def test_below_the_floor_is_not_counted_either_way(self):
        """Two records were never a claim, so they are not an artefact."""
        cache = {"Sparse thing": [_O(*MONTANE_NEAR_PARKLAND, 30.0)] * 2}
        total, artefacts, _worst = P.buffer_artefacts(cache)
        self.assertEqual((total, artefacts), (0, 0))


class TestTheMissingCacheIsLoud(unittest.TestCase):
    def test_it_refuses_rather_than_drawing_an_empty_map(self):
        """An empty map of a species with 400 records is the failure that
        looks most like a finding."""
        with self.assertRaises(SystemExit) as caught:
            P._require({})
        self.assertEqual(caught.exception.code, 1)

    def test_a_populated_cache_passes(self):
        P._require({"Testus": [_O(*EDMONTON)]})


class TestTheCacheItIsBuiltOn(unittest.TestCase):
    def test_the_plotter_reads_what_the_seeder_writes(self):
        """One format, two scripts. The pair is the whole point of F136."""
        tmp = Path(tempfile.mkdtemp()) / "plant_occurrences.json"
        points = [_O(53.55, -113.49, 25.0, 2019, "HUMAN_OBSERVATION", "inat")]
        S.write_cache({"Testus plantus": points}, path=tmp)
        self.assertEqual(S.read_cache(tmp)["Testus plantus"], points)

    def test_the_real_cache_is_not_committed(self):
        """It is a dev artefact of a run with egress, and a synthetic one
        sitting in data/fetched would be indistinguishable from real data."""
        self.assertFalse(
            S.CACHE_PATH.exists() and "SYNTHETIC" in
            S.CACHE_PATH.read_text(encoding="utf-8")[:400],
            "a synthetic fixture cache is present in data/fetched")


if __name__ == "__main__":
    unittest.main()

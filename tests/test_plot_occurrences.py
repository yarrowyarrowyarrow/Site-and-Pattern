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


class TestTheContactSheet(unittest.TestCase):
    """The mode for looking at many species at once, which is how the colour
    backlog got worked (`scripts/colour_worklist.py --sheet`) and how a range
    audit would be."""

    def setUp(self):
        self._real = P._cache
        P._cache = lambda: {
            "Aster alpinus": [_O(*MONTANE_NEAR_PARKLAND, 30.0)] * 6,
            "Amelanchier alnifolia": [_O(*EDMONTON, 20.0)] * 30,
        }

    def tearDown(self):
        P._cache = self._real

    def test_it_writes_one_figure_per_species_worst_first(self):
        out = Path(tempfile.mkdtemp()) / "sheet.html"
        self.assertEqual(P.main(["--sheet", str(out), "--limit", "2"]), 0)
        html = out.read_text(encoding="utf-8")
        self.assertEqual(html.count("<figure>"), 2)
        self.assertEqual(html.count("class=\"occ\""), 2)
        # Ordered by record count, so the species with most to look at is first.
        self.assertLess(html.index("Amelanchier alnifolia"),
                        html.index("Aster alpinus"))

    def test_the_record_count_travels_with_each_thumbnail(self):
        """A dot map with no count is the same failure the site had: the
        picture cannot distinguish six records from six hundred."""
        out = Path(tempfile.mkdtemp()) / "sheet.html"
        P.main(["--sheet", str(out), "--limit", "2"])
        self.assertIn("30 records", out.read_text(encoding="utf-8"))


class TestTheMissingCacheIsLoud(unittest.TestCase):
    def test_it_refuses_rather_than_drawing_an_empty_map(self):
        """An empty map of a species with 400 records is the failure that
        looks most like a finding."""
        with self.assertRaises(SystemExit) as caught:
            P._require({})
        self.assertEqual(caught.exception.code, 1)

    def test_a_populated_cache_passes(self):
        P._require({"Testus": [_O(*EDMONTON)]})


class TestOnlyTheRecordsWeMayDraw(unittest.TestCase):
    """The specimen and licence filters (F141, V2.77).

    Two rules, and both fail dangerously in the permissive direction: an
    unknown licence treated as publishable puts somebody's records on a public
    page without the right, and an absent licence table treated as "nothing is
    publishable" draws a blank map that reads as a finding about the herbaria.
    """

    TABLE = {"herbarium": "CC_BY", "public": "CC0", "restricted": "CC_BY_NC"}

    def _points(self):
        return [
            _O(53.55, -113.49, 30.0, 1954, "PRESERVED_SPECIMEN", "herbarium"),
            _O(53.56, -113.48, 30.0, 1961, "PRESERVED_SPECIMEN", "public"),
            _O(53.57, -113.47, 30.0, 1978, "PRESERVED_SPECIMEN", "restricted"),
            _O(53.58, -113.46, 30.0, 2024, "HUMAN_OBSERVATION", "public"),
            _O(53.59, -113.45, 30.0, 2025, "HUMAN_OBSERVATION", "unlisted"),
        ]

    def test_the_specimen_filter_keeps_only_specimens(self):
        kept = P.specimens(self._points())
        self.assertEqual(len(kept), 3)
        self.assertTrue(all(p.basis == "PRESERVED_SPECIMEN" for p in kept))

    def test_a_noncommercial_dataset_is_not_drawable(self):
        kept = P.publishable(self._points(), self.TABLE)
        self.assertNotIn("restricted", {p.dataset_key for p in kept})

    def test_a_dataset_absent_from_the_table_is_dropped_not_defaulted(self):
        """Absent is not permissive. The same rule the photo pipeline runs on."""
        kept = P.publishable(self._points(), self.TABLE)
        self.assertNotIn("unlisted", {p.dataset_key for p in kept})

    def test_the_two_filters_compose(self):
        kept, why = P.drawable(self._points(), only_specimens=True,
                               only_publishable=True, table=self.TABLE)
        self.assertEqual({p.dataset_key for p in kept}, {"herbarium", "public"})
        self.assertEqual(why["not a specimen"], 2)
        self.assertEqual(why["licence does not permit redrawing"], 1)

    def test_nothing_is_dropped_silently(self):
        """Every refusal is counted and reasoned, so a thin map is explicable."""
        _kept, why = P.drawable(self._points(), only_specimens=True,
                                only_publishable=True, table=self.TABLE)
        self.assertEqual(sum(why.values()), 3)

    def test_no_filters_means_no_drop_reasons(self):
        kept, why = P.drawable(self._points(), only_specimens=False,
                               only_publishable=False)
        self.assertEqual(len(kept), 5)
        self.assertEqual(why, {})

    def test_a_missing_licence_table_refuses_rather_than_withholding(self):
        missing = Path(tempfile.mkdtemp()) / "nope.json"
        with self.assertRaises(P.NoLicenceTable) as caught:
            P.licences(missing)
        self.assertIn("fetch_dataset_licences.py", str(caught.exception))

    def test_the_committed_table_parses_and_names_real_licences(self):
        """Guards the join key: a table keyed on anything but datasetKey would
        silently drop every record and look like a licence problem."""
        try:
            table = P.licences()
        except P.NoLicenceTable:
            self.skipTest("dataset licence table is a dev artefact")
        self.assertTrue(table)
        self.assertTrue(set(table.values()) <= {
            "CC0", "CC_BY", "CC_BY_NC", "CC_BY_SA", "CC_BY_NC_SA",
            "UNSPECIFIED"}, sorted(set(table.values())))


class TestAFilteredMapSaysSo(unittest.TestCase):
    """A region shaded from 300 records showing four dots reads as broken.

    It is not broken -- it is two statements on one picture -- and the only
    thing that makes it honest is the sentence beside it.
    """

    PTS = [_O(53.55, -113.49, 30.0, 1954, "PRESERVED_SPECIMEN", "h"),
           _O(53.56, -113.48, 30.0, 2024, "HUMAN_OBSERVATION", "i"),
           _O(53.57, -113.47, 30.0, 2025, "HUMAN_OBSERVATION", "i")]

    def test_the_caption_states_both_counts_and_the_reason(self):
        text = P.caption("Testus", 3, 1, {"not a specimen": 2})
        self.assertIn("1 of 3", text)
        self.assertIn("2 not a specimen", text)

    def test_it_says_the_shading_is_not_the_dots(self):
        text = P.caption("Testus", 3, 1, {"not a specimen": 2})
        self.assertIn("derived from all 3", text)

    def test_an_unfiltered_map_gets_no_apology(self):
        self.assertEqual(P.caption("Testus", 3, 3, {}), "3 records, all drawn.")

    def test_zero_drawable_is_named_as_a_publishing_gap_not_an_absence(self):
        """The failure that looks most like a finding, in words."""
        text = P.caption("Testus", 3, 0, {"not a specimen": 3})
        self.assertIn("gap in what may be drawn", text)
        self.assertNotIn("all drawn", text)

    def test_the_shading_survives_a_filter_that_empties_the_dots(self):
        """The published range is a claim about ALL the evidence. Filtering the
        picture must not quietly filter the claim."""
        import re
        full = P.species_svg("Testus", self.PTS, width=360)
        thin = P.species_svg("Testus", self.PTS, width=360, dots=[])
        self.assertGreater(full.count("<circle"), thin.count("<circle"))
        self.assertEqual(0, thin.count("<circle"))
        # Everything that is not a dot is byte-identical, which is a stronger
        # claim than "the region is still mentioned": it pins the shading, the
        # confidence band and the tooltip text all at once.
        strip = lambda svg: re.sub(r'<g class="occ">.*?</g>', "", svg, flags=re.S)
        self.assertEqual(strip(full), strip(thin))
        self.assertIn("Aspen Parkland", strip(thin))

    def test_dots_default_to_every_point(self):
        a = P.species_svg("Testus", self.PTS, width=360)
        b = P.species_svg("Testus", self.PTS, width=360, dots=self.PTS)
        self.assertEqual(a, b)


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

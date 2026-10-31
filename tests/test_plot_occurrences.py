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
        self.assertEqual(P._radius(10_000_000.0, scale=1.0),
                         P._MAX_R_FRAC * 720.0)

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


class TestTheDotsScaleWithTheMap(unittest.TestCase):
    """The clamps were absolute SVG units (V2.78).

    360 of 422 dots on a real species sit at the minimum radius, so in practice
    every dot was one fixed size while the map around it scaled: a 360px
    contact-sheet thumbnail drew its dots two and a half times larger relative
    to the ground than the 900px version of the same map. Two renderings of one
    species that disagree about how crowded it is, and nothing said so.
    """

    def test_the_floor_is_a_fraction_of_the_width(self):
        small = P._radius(None, 0.0, 360.0)
        large = P._radius(None, 0.0, 900.0)
        self.assertAlmostEqual(large / small, 2.5, places=6)

    def test_the_ceiling_scales_too(self):
        huge = 10_000_000.0
        self.assertAlmostEqual(P._radius(huge, 1.0, 900.0) /
                               P._radius(huge, 1.0, 360.0), 2.5, places=6)

    def test_a_stated_uncertainty_still_means_metres(self):
        """Between the clamps the radius is the record's own number through the
        projection's own scale, which is the whole point of the encoding."""
        r = P._radius(2000.0, 0.004, 720.0)
        self.assertAlmostEqual(r, 8.0, places=6)

    def test_an_unrecorded_uncertainty_is_still_hollow_at_any_size(self):
        for width in (360.0, 900.0):
            svg = P.points_svg([_O(53.55, -113.49, None, 2019, "", "")],
                               lambda lon, lat: (10.0, 10.0), width=width)
            self.assertIn('fill="none"', svg)


class TestTheKey(unittest.TestCase):
    """There was none, for two versions (V2.78).

    A reader met a picture running three independent encodings at once --
    region fill for confidence, dot colour for the kind of record, dot size for
    how precisely that record knows where it is -- and no statement of any of
    them. The one that misleads hardest unexplained is the hollow dot: it means
    *this record stated no accuracy* and looks like a circle drawn for emphasis.
    """

    def test_it_explains_all_three_dot_encodings(self):
        key = P.legend_svg(width=720)
        self.assertIn("specimen", key)
        self.assertIn("coarser location", key)
        self.assertIn("no location accuracy", key)

    def test_a_specimens_only_map_does_not_key_a_colour_it_never_draws(self):
        self.assertNotIn("an observation", P.legend_svg(specimens_only=True))
        self.assertIn("an observation", P.legend_svg(specimens_only=False))

    def test_the_key_is_not_clipped_away(self):
        """It sits in the corner of the *frame*, which on this projection is
        over British Columbia. Through `overlay` the subject clip deletes it,
        which is why `map_svg` grew a separate `chrome` seam."""
        from src.ecoregion_map import map_svg
        svg = map_svg({}, width=720, height=664,
                      overlay='<g class="occ"/>',
                      chrome=P.legend_svg(width=720))
        self.assertIn("occ-legend", svg)
        self.assertGreater(svg.index("occ-legend"), svg.rindex("clip-path"))

    def test_a_real_map_carries_it(self):
        svg = P.species_svg("Testus", [_O(53.55, -113.49, 30.0, 1954,
                                          "PRESERVED_SPECIMEN", "h")] * 4,
                            width=360)
        self.assertIn("occ-legend", svg)


class TestOnlyTheRecordsWeMayDraw(unittest.TestCase):
    """The specimen and licence filters (F141, V2.77; the NC rule V2.80).

    Two rules, and both fail dangerously in the permissive direction: an
    unknown licence treated as publishable puts somebody's records on a public
    page without the right, and an absent licence table treated as "nothing is
    publishable" draws a blank map that reads as a finding about the herbaria.

    **V2.80 changed one of them deliberately.** `publishable` now uses
    `PUBLISHABLE_COORDINATES`, which permits `CC_BY_NC` -- a photograph is
    redistributed as a work, a coordinate is a fact about a place -- while the
    photograph pipeline keeps the stricter set. It is not a loosening by
    accident: of 365,092 drawable records, 329,267 are NC observations, so the
    old rule drew a map that was 94% herbarium specimens and called it the
    observation record. `tests/test_occurrence_points.py` pins the two sets
    against each other; these pin what the filter does with them.
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

    def test_a_noncommercial_dataset_IS_drawable_as_a_coordinate(self):
        """Reversed in V2.80, on the author's decision. This test asserted the
        opposite for three releases and was right to until the rule changed."""
        kept = P.publishable(self._points(), self.TABLE)
        self.assertIn("restricted", {p.dataset_key for p in kept})

    def test_the_photograph_rule_is_not_what_moved(self):
        """The reason NC is acceptable here is specific to coordinates. If
        this ever passes for `PUBLISHABLE`, the photo pipeline has been
        loosened by somebody editing the wrong constant."""
        from scripts.fetch_dataset_licences import PUBLISHABLE
        self.assertNotIn("CC_BY_NC", PUBLISHABLE)

    def test_a_dataset_absent_from_the_table_is_dropped_not_defaulted(self):
        """Absent is not permissive. The same rule the photo pipeline runs on."""
        kept = P.publishable(self._points(), self.TABLE)
        self.assertNotIn("unlisted", {p.dataset_key for p in kept})

    def test_the_two_filters_compose(self):
        kept, why = P.drawable(self._points(), only_specimens=True,
                               only_publishable=True, table=self.TABLE)
        # `restricted` is CC_BY_NC and survives now; `unlisted` is absent from
        # the table and still does not, but it is an observation so the
        # specimen filter takes it first.
        self.assertEqual({p.dataset_key for p in kept},
                         {"herbarium", "public", "restricted"})
        self.assertEqual(why["not a specimen"], 2)
        self.assertNotIn("licence does not permit redrawing", why)

    def test_nothing_is_dropped_silently(self):
        """Every refusal is counted and reasoned, so a thin map is explicable."""
        _kept, why = P.drawable(self._points(), only_specimens=True,
                                only_publishable=True, table=self.TABLE)
        self.assertEqual(sum(why.values()), 2)

    def test_an_unlisted_licence_is_still_counted_when_it_is_reached(self):
        """The composition test above never reaches the licence filter for
        `unlisted`, because it is an observation. Without the specimen filter
        in the way, absent must still not be permissive."""
        _kept, why = P.drawable(self._points(), only_specimens=False,
                                only_publishable=True, table=self.TABLE)
        self.assertEqual(why["licence does not permit redrawing"], 1)

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


class TestOnlyGroundThisCatalogueSpeaksFor(unittest.TestCase):
    """No dot outside Alberta and Saskatchewan (F142, V2.78).

    The GBIF harvest is bounded by the polygons' *bounding box* plus half a
    degree, which reaches into British Columbia, Montana, Manitoba and the
    Northwest Territories. The derivation ignores those records correctly; the
    drawing did not, because `map_svg`'s overlay seam sits outside its subject
    clip group. **551 of 1,251 records for one species** were being drawn over
    ground the layer has no authority over, on a map whose entire argument is
    about what a shaded region claims.
    """

    GOLDEN_BC = (51.30, -116.97)
    REVELSTOKE_BC = (50.998, -118.196)
    BANFF_AB = (51.18, -115.57)          # mountains, near the coarse border
    GREAT_FALLS_MT = (47.50, -111.30)
    BRANDON_MB = (49.85, -99.95)

    def test_a_british_columbia_record_is_not_drawn(self):
        from src.subject_area import in_subject_provinces
        self.assertFalse(in_subject_provinces(*self.GOLDEN_BC))
        self.assertFalse(in_subject_provinces(*self.REVELSTOKE_BC))

    def test_montana_and_manitoba_are_not_drawn_either(self):
        """The bbox reaches past three borders, not one."""
        from src.subject_area import in_subject_provinces
        self.assertFalse(in_subject_provinces(*self.GREAT_FALLS_MT))
        self.assertFalse(in_subject_provinces(*self.BRANDON_MB))

    def test_a_mountain_record_on_the_alberta_side_survives(self):
        """The province outline is Natural Earth at 193 vertices. Dropping a
        real Banff specimen because our basemap cut a corner would be the same
        class of error as the 5 km buffer."""
        from src.subject_area import in_subject_provinces
        self.assertTrue(in_subject_provinces(*self.BANFF_AB))
        self.assertTrue(in_subject_provinces(49.05, -113.91))   # Waterton
        self.assertTrue(in_subject_provinces(51.42, -116.18))   # Lake Louise

    def test_the_filter_is_unconditional(self):
        """A licence or a basis decides whether a record we counted may be
        drawn. A record in British Columbia was never counted at all, so no
        filter setting should put it on the map."""
        pts = [_O(*self.BANFF_AB, 30.0, 1954, "HUMAN_OBSERVATION", "i"),
               _O(*self.GOLDEN_BC, 30.0, 1955, "HUMAN_OBSERVATION", "i")]
        kept, why = P.drawable(pts, only_specimens=False,
                               only_publishable=False)
        self.assertEqual(len(kept), 1)
        self.assertEqual(why[P.OUT_OF_SUBJECT], 1)

    def test_the_basemap_shim_still_answers(self):
        """`ecoregion_basemap` kept a re-export when V2.78 extracted this, in
        the same shape as its `_point_in_ring` shim. A silent break here would
        look like a geography bug rather than a moved import."""
        from src.ecoregion_basemap import in_subject_provinces as shim
        from src.subject_area import in_subject_provinces as impl
        for point in (self.GOLDEN_BC, self.BANFF_AB, self.BRANDON_MB):
            self.assertEqual(shim(*point), impl(*point), point)

    def test_the_overlay_is_clipped_to_the_subject_provinces(self):
        """The backstop, for the dot a few hundred metres over a simplified
        border that the caller cannot settle either way."""
        from src.ecoregion_basemap import SUBJECT_CLIP_ID
        from src.ecoregion_map import map_svg
        svg = map_svg({}, width=360, height=332, overlay='<g class="occ"/>')
        self.assertIn(f'<g clip-path="url(#{SUBJECT_CLIP_ID})">'
                      f'<g class="occ"/></g>', svg)


class TestAFilteredMapSaysSo(unittest.TestCase):
    """A region shaded from 300 records showing four dots reads as broken.

    It is not broken -- it is several statements on one picture -- and the only
    thing that makes it honest is the sentence beside it.
    """

    PTS = [_O(53.55, -113.49, 30.0, 1954, "PRESERVED_SPECIMEN", "h"),
           _O(53.56, -113.48, 30.0, 2024, "HUMAN_OBSERVATION", "i"),
           _O(53.57, -113.47, 30.0, 2025, "HUMAN_OBSERVATION", "i")]

    def test_the_numbers_close(self):
        """Every record is in exactly one tier. The first two drafts each lost
        a group -- 551 records to a wrong denominator, then 9 to the floor."""
        text = P.caption("Testus", held=1251, counted=691, drawn=422,
                         dropped={P.OUT_OF_SUBJECT: 551,
                                  "not a specimen": 268,
                                  "licence does not permit redrawing": 10})
        self.assertIn("422 of the 700", text)        # 422 + 268 + 10
        self.assertIn("derived from 691 of them", text)
        self.assertIn("other 9", text)               # 700 - 691, the floor
        self.assertIn("further 551", text)

    def test_it_says_the_shading_is_not_the_dots(self):
        text = P.caption("Testus", 3, 1, 1, {"not a specimen": 2})
        self.assertIn("not from the dots", text)

    def test_an_unfiltered_map_gets_no_apology(self):
        text = P.caption("Testus", 3, 3, 3, {})
        self.assertIn("all of them", text)
        self.assertNotIn("further", text)

    def test_records_elsewhere_are_named_even_when_nothing_is_filtered(self):
        """The out-of-province count is not a publishing decision, so it is
        reported whether or not the caller filtered anything."""
        text = P.caption("Testus", 10, 4, 4, {P.OUT_OF_SUBJECT: 6})
        self.assertIn("further 6", text)
        self.assertIn("neither counted nor drawn", text)

    def test_zero_drawable_is_named_as_a_publishing_gap_not_an_absence(self):
        text = P.caption("Testus", 3, 3, 0, {"not a specimen": 3})
        self.assertIn("gap in what may be drawn", text)
        self.assertIn("No dot is drawable", text)
        # The shading is still a full claim about the three records; only the
        # drawing is empty. And with no dots there is nothing to contrast.
        self.assertIn("derived from all of them.", text)
        self.assertNotIn("not from the dots", text)

    def test_the_shading_survives_a_filter_that_empties_the_dots(self):
        """The published range is a claim about ALL the evidence. Filtering the
        picture must not quietly filter the claim."""
        import re
        full = P.species_svg("Testus", self.PTS, width=360)
        thin = P.species_svg("Testus", self.PTS, width=360, dots=[])
        self.assertGreater(full.count("<circle"), thin.count("<circle"))
        # Everything that is not a dot is byte-identical, which is a stronger
        # claim than "the region is still mentioned": it pins the shading, the
        # confidence band and the tooltip text all at once.
        strip = lambda svg: re.sub(r'<g clip-path="[^"]*"><g class="occ">.*?</g></g>',
                                   "", svg, flags=re.S)
        self.assertEqual(strip(full), strip(thin))
        self.assertIn("Aspen Parkland", strip(thin))

    def test_no_record_dot_survives_an_emptied_filter(self):
        """Counted inside the records group, not over the whole file: the key
        draws circles too, and it is chrome rather than evidence."""
        import re
        thin = P.species_svg("Testus", self.PTS, width=360, dots=[])
        group = re.search(r'<g class="occ">(.*?)</g>', thin, re.S)
        self.assertEqual(group.group(1).count("<circle"), 0)
        self.assertIn("occ-legend", thin)

    def test_dots_default_to_every_point(self):
        a = P.species_svg("Testus", self.PTS, width=360)
        b = P.species_svg("Testus", self.PTS, width=360, dots=self.PTS)
        self.assertEqual(a, b)

    def test_the_tiers_never_go_negative_on_real_data(self):
        """The V2.78 caption printed *"the other -5 fall in regions with too
        few records to shade"* on Blanketflower.

        `counted` was `sum(r["occurrences"])`, a count of **claims**, and it was
        being subtracted from a count of **records**. V2.76 established that
        containment credits a record to one region, and that is very nearly
        true: the surveyed polygons are simplified to ~900 m independently, so
        adjacent regions overlap by a sliver and 0.81% of in-region points match
        two. Calgary is 587 of the first 692, where aspen_parkland and
        fescue_grassland cross.
        """
        import scripts.seed_ecoregion_ranges as seeder
        cache = seeder.read_cache()
        if not cache:
            self.skipTest("the point cache is a dev artefact")
        # The species it actually happened on, plus the largest few.
        names = ["Gaillardia aristata"] + sorted(
            cache, key=lambda n: -len(cache[n]))[:4]
        for name in names:
            points = cache.get(name)
            if not points:
                continue
            dots, why = P.drawable(points, only_specimens=True,
                                   only_publishable=False)
            _svg, counted = P.species_svg(name, points, width=360, dots=dots,
                                          with_counted=True)
            subject = len(dots) + sum(
                n for w, n in why.items() if w != P.OUT_OF_SUBJECT)
            self.assertLessEqual(
                counted, subject,
                f"{name}: the shading counts {counted} of {subject} records, "
                f"which prints a negative remainder")
            self.assertIn(f"other {subject - counted:,}",
                          P.caption(name, len(points), counted, len(dots), why)
                          if counted != subject else
                          f"other {subject - counted:,}")

    def test_counted_is_records_not_claims(self):
        """A point inside two overlapping polygons is one record. Summing the
        rows counted it twice, which is what printed a negative remainder.

        V2.81 changed what the right answer is rather than how it is reached.
        Such a point is inside the border margin by construction, so it now
        shades nothing and is counted nowhere -- and the caption must still
        balance, which is the invariant that actually broke last time. The
        count and the shading are asserted to come from the same rule, because
        a caption counting by one rule under a map drawn by another is the
        failure this test exists for."""
        overlap = _O(51.1206, -114.0966, 4.0, 2026, "HUMAN_OBSERVATION", "i")
        from src.ecoregion_ranges import _containment_lookup, _record_lookup
        if len(_containment_lookup(*overlap[:2])) < 2:
            self.skipTest("polygons no longer overlap at Calgary")
        self.assertEqual(_record_lookup(*overlap[:2]), [],
                         "an overlap is inside the margin by construction")
        points = [overlap] * 6
        _svg, counted = P.species_svg("Testus", points, width=360,
                                      with_counted=True)
        self.assertEqual(counted, 0,
                         "six records too near a border shade nothing, and "
                         "the caption must not claim them as evidence")

    def test_the_counted_number_is_not_the_held_number(self):
        """`len(points)` was the caption's denominator and was wrong: records
        outside every region are held and shade nothing."""
        pts = list(self.PTS) + [_O(51.30, -116.97, 30.0, 1970,
                                   "PRESERVED_SPECIMEN", "h")] * 4
        _svg, counted = P.species_svg("Testus", pts, width=360,
                                      with_counted=True)
        self.assertEqual(counted, 3)
        self.assertEqual(len(pts), 7)


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

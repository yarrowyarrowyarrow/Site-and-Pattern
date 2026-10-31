"""
The range map, and the two ways it was drawing nothing (V2.80).

`src/range_map.py` shipped in V2.79 with no tests and no caller: it existed to
produce sample renders for the author, who reported that all three palettes
looked identical. The handover attributed that to mark density -- 10-30 record
marks land in each grid square, so the wash is buried -- and that arithmetic is
correct but was not the cause.

The cause was that the wash was **never on the page**. The renderer draws the
subject provinces, then the range, then the province outlines again so an edge
stays legible against the wash; the second pass reused the same CSS class as the
first, whose fill is opaque white. Every build painted the range out again
immediately after drawing it.

A second layer was silently unstyled for the same kind of reason: `water_svg`
and `cities_svg` are shared with the ecoregion maps and emit `ecomap-*` classes
that live in `html/site/site.css`, so an SVG this module calls self-contained
rendered every lake black and every river not at all.

Neither failure raises. Both are invisible to a test that checks the string
parses, which is why these tests assert about **paint order and applied
colour** rather than about well-formedness.
"""

import os
import re
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import range_map as M                       # noqa: E402
from src import species_range as R                   # noqa: E402

# A handful of cells across southern Alberta and into Saskatchewan, with the
# counts a real species has: mostly ones, one cell holding a city.
CELLS = [(49.0, -113.5, 1), (49.25, -113.25, 3), (50.75, -114.25, 812),
         (51.0, -114.25, 140), (52.0, -110.0, 17), (53.5, -113.5, 96)]
POINTS = [(49.1, -113.4), (50.8, -114.2), (52.1, -110.1)]


def _classes(svg: str, name: str) -> list:
    """Byte offsets of every element carrying ``class="name"``."""
    return [m.start() for m in re.finditer(rf'class="{name}"', svg)]


class TestTheRangeSurvivesToThePage(unittest.TestCase):
    """The V2.79 bug, pinned. It is one line of paint order and it cost the
    whole increment's visual work."""

    def setUp(self):
        self.svg = M.range_svg(CELLS, width=640)

    def test_every_cell_is_drawn(self):
        drawn = sum(len(_classes(self.svg, f"c{i}")) for i in range(5))
        self.assertEqual(drawn, len(CELLS))

    def test_nothing_opaque_is_painted_over_the_range_afterwards(self):
        """`.subj` carries the white province fill. If any lands after the last
        range cell, the range is invisible however good the palette is."""
        last_cell = max(max(_classes(self.svg, f"c{i}") or [-1])
                        for i in range(5))
        for after in _classes(self.svg, "subj"):
            self.assertLess(after, last_cell,
                            "a filled province polygon is drawn over the range")

    def test_the_border_redraw_still_happens_but_carries_no_fill(self):
        """The redraw is wanted -- it keeps a province edge legible where the
        wash sits against it. It just must not be a fill."""
        self.assertTrue(_classes(self.svg, "subjline"))
        self.assertIn(".rangemap .subjline{fill:none", self.svg)

    def test_the_palettes_actually_differ_on_the_page(self):
        """The author's report was that they were identical. They were."""
        seen = {M.range_svg(CELLS, palette=name) for name in M.PALETTES}
        self.assertEqual(len(seen), len(M.PALETTES))


class TestTheCellsCarryTheDensity(unittest.TestCase):

    def test_a_cell_is_classed_by_its_band(self):
        svg = M.range_svg([(49.0, -113.5, 1), (50.75, -114.25, 812)])
        self.assertEqual(len(_classes(svg, "c0")), 1)
        self.assertEqual(len(_classes(svg, "c4")), 1)

    def test_presence_only_input_still_draws(self):
        """A caller holding cells and no counts is not an error, and must not
        silently render an empty map."""
        svg = M.range_svg([(49.0, -113.5), (50.75, -114.25)])
        self.assertEqual(len(_classes(svg, "cell")), 2)

    def test_a_count_mapping_is_accepted_as_it_comes_out_of_cell_counts(self):
        svg = M.range_svg(R.cell_counts([(53.55, -113.49)] * 40))
        self.assertEqual(len(_classes(svg, "c3")), 1)

    def test_no_cells_draws_no_cells_and_does_not_raise(self):
        """P9's rule, the same one `phenology_bar` follows: nothing recorded
        draws nothing rather than an empty grid asserting absence."""
        svg = M.range_svg([])
        self.assertEqual(sum(len(_classes(svg, f"c{i}")) for i in range(5)), 0)
        self.assertNotIn("records per square", svg)


class TestTheKeyIsDrawnWhereverTheRampIs(unittest.TestCase):
    """A five-step wash a reader cannot decode is decoration, and one they
    decode as abundance is worse than decoration."""

    def test_the_ramp_gets_a_key(self):
        svg = M.range_svg(CELLS, width=640)
        self.assertIn("records per square", svg)
        for label in R.BAND_LABELS:
            self.assertIn(f">{label}<", svg)

    def test_the_key_says_records_and_not_a_word_that_means_abundance(self):
        svg = M.range_svg(CELLS, width=640).lower()
        for word in ("abundance", "abundant", "common", "density"):
            self.assertNotIn(word, svg)

    def test_a_presence_only_map_gets_no_key_because_there_is_no_ramp(self):
        svg = M.range_svg([(49.0, -113.5), (50.75, -114.25)])
        self.assertNotIn("records per square", svg)

    def test_a_thumbnail_drops_the_key_rather_than_drawing_it_unreadably(self):
        self.assertNotIn("records per square", M.range_svg(CELLS, width=300))


class TestTheMarksAreOffUntilAsked(unittest.TestCase):
    """The default view is the wash. The marks are what the F147 toggle turns
    on over the top of it."""

    def test_marks_are_not_drawn_by_default(self):
        svg = M.range_svg(CELLS, specimens=POINTS, observations=POINTS)
        self.assertEqual(_classes(svg, "spec"), [])
        self.assertEqual(_classes(svg, "obs"), [])

    def test_marks_all_draws_both_layers(self):
        svg = M.range_svg(CELLS, specimens=POINTS, observations=POINTS,
                          marks="all")
        self.assertEqual(len(_classes(svg, "spec")), len(POINTS))
        self.assertEqual(len(_classes(svg, "obs")), len(POINTS))

    def test_specimens_are_filled_and_observations_hollow(self):
        """Shape, not only hue, so the distinction survives greyscale, print
        and a red-green deficiency."""
        svg = M.range_svg(CELLS, specimens=POINTS, observations=POINTS,
                          marks="all")
        self.assertRegex(svg, r"\.rangemap \.spec\{fill:#[0-9a-f]{6}")
        self.assertIn(".rangemap .obs{fill:none", svg)

    def test_marks_few_keeps_only_the_single_record_cells(self):
        """The squares the wash says least about -- the lightest band, which a
        reader is likeliest to take for nothing at all."""
        svg = M.range_svg(CELLS, observations=POINTS, marks="few")
        self.assertEqual(len(_classes(svg, "obs")), 1)

    def test_an_occurrence_row_with_extra_fields_drops_in(self):
        """Every other stage of this pipeline takes the cache's rows directly;
        unpacking `for lat, lng in ...` here raised on the third field."""
        rows = [(49.1, -113.4, "2019-06-01", "specimen")]
        svg = M.range_svg(CELLS, specimens=rows, marks="all")
        self.assertEqual(len(_classes(svg, "spec")), 1)


class TestTheSvgIsAsSelfContainedAsItClaims(unittest.TestCase):
    """It is published standalone and it was styling only half of itself."""

    def test_the_shared_basemap_classes_are_styled_here(self):
        svg = M.range_svg(CELLS, width=640)
        for css in ("ecomap-lake", "ecomap-river", "ecomap-city",
                    "ecomap-place", "ecomap-prov-label"):
            self.assertIn(f".rangemap .{css}{{", svg,
                          f"{css} is emitted by the shared basemap and would "
                          f"fall back to site.css, or to black")

    def test_a_lake_is_not_black(self):
        """SVG's default fill. Opened on its own, every lake was."""
        svg = M.range_svg(CELLS, width=640)
        rule = re.search(r"\.rangemap \.ecomap-lake\{fill:(#[0-9a-f]{6})", svg)
        self.assertIsNotNone(rule)
        self.assertNotIn(rule.group(1), ("#000000", "#000"))

    def test_a_river_is_stroked_or_it_is_invisible(self):
        """`water_svg` emits `fill="none"` polylines. With no stroke rule that
        is a line nobody can see rather than a line in the wrong colour."""
        svg = M.range_svg(CELLS, width=640)
        self.assertRegex(svg, r"\.rangemap \.ecomap-river\{[^}]*stroke:#")

    def test_the_palette_entries_reach_the_page(self):
        """`water`, `river` and `city` sat in the palette table for a whole
        release without being applied to anything."""
        for name, pal in M.PALETTES.items():
            svg = M.range_svg(CELLS, palette=name, width=640)
            for key in ("water", "river", "city", "paper", "border"):
                self.assertIn(pal[key], svg, f"{name}.{key} never drawn")

    def test_every_palette_carries_a_full_ramp(self):
        for name, pal in M.PALETTES.items():
            self.assertEqual(len(pal["ramp"]), len(R.BAND_LABELS), name)


class TestTheLayersCanBeToggled(unittest.TestCase):
    """F147's control. The two mark kinds go in their own `<g>` so one CSS rule
    hides a layer -- rendering two whole maps to show one at a time would
    double the bytes for the same picture."""

    def _svg(self):
        return M.range_svg(CELLS, specimens=POINTS, observations=POINTS,
                           marks="all")

    def test_each_kind_gets_its_own_group(self):
        svg = self._svg()
        self.assertIn('<g class="layer-spec">', svg)
        self.assertIn('<g class="layer-obs">', svg)

    def test_an_empty_layer_draws_no_empty_group(self):
        svg = M.range_svg(CELLS, specimens=POINTS, marks="all")
        self.assertIn('<g class="layer-spec">', svg)
        self.assertNotIn('<g class="layer-obs">', svg)

    def test_the_svg_carries_its_own_toggle_rules(self):
        """Inside the SVG, so a standalone file toggles too rather than only
        working when the site stylesheet is present."""
        svg = self._svg()
        self.assertIn(".rangemap.only-spec .layer-obs{display:none}", svg)
        self.assertIn(".rangemap.only-obs .layer-spec{display:none}", svg)

    def test_neither_class_shows_both(self):
        """A viewer with no CSS at all, or no JavaScript, must see everything
        rather than nothing."""
        svg = self._svg()
        self.assertNotIn('class="rangemap only-', svg)



if __name__ == "__main__":
    unittest.main()

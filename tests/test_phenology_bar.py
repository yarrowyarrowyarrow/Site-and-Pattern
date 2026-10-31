"""
The phenology bar (F143, V2.78).

The catalogue has carried `bloom_period` on 424 of 430 species since its first
seed file and has shown it three ways, all of them text. None of them answer
the question a person reading a plant list has -- *what is flowering in July,
and does anything carry August* -- because comparing two species means reading
two strings against a calendar held in the head.

What these tests pin is mostly the refusals: the empty bar that would claim a
plant never flowers, the year-end wrap that reads as two windows, and the
second parser that would be free to disagree with the first.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import phenology_bar as P                    # noqa: E402


class TestNothingRecordedDrawsNothing(unittest.TestCase):
    """P9. Twelve empty cells is not the absence of a claim -- it is the claim
    that we checked and this plant never flowers, and for the six species with
    no bloom window that would be false."""

    def test_no_months_returns_the_empty_string(self):
        self.assertEqual(P.phenology_svg(), "")
        self.assertEqual(P.phenology_svg([], []), "")

    def test_an_unparseable_string_draws_nothing_rather_than_guessing(self):
        self.assertEqual(P.parse_period("whenever it feels like it"), [])
        self.assertEqual(P.phenology_svg(P.parse_period("")), "")

    def test_fruit_alone_still_draws(self):
        """285 species have a fruit period; a shrub whose bloom nobody wrote
        down still has something to say."""
        self.assertIn("<svg", P.phenology_svg([], [9, 10]))

    def test_out_of_range_months_are_ignored_not_wrapped(self):
        self.assertEqual(P.phenology_svg([0, 13]), "")


class TestItReadsTheSameStringsTheCatalogueHas(unittest.TestCase):
    """37 distinct spellings across 424 species: en dash, hyphen, short and
    long names. A second parser here would be free to disagree with the one
    the rest of the app has used since V1.x, so this delegates."""

    def test_it_delegates_to_the_existing_parser(self):
        from src.habitat_score import parse_month_range
        for text in ("June–August", "Jun-Jul", "May-June", "July–August",
                     "August–September", "May"):
            self.assertEqual(P.parse_period(text), parse_month_range(text),
                             text)

    def test_every_spelling_in_the_shipped_data_parses(self):
        import json
        with open(os.path.join(os.path.dirname(__file__), "..", "data",
                               "plants_master.json"), encoding="utf-8") as fh:
            rows = json.load(fh)
        rows = rows if isinstance(rows, list) else rows.get("plants", [])
        unread = sorted({r["bloom_period"] for r in rows
                         if r.get("bloom_period")
                         and not P.parse_period(r["bloom_period"])})
        self.assertEqual(unread, [], "bloom windows the bar cannot read")


class TestTheWordsMatchThePicture(unittest.TestCase):
    """The accessible name, the tooltip, and the line under the bar are the
    same sentence. A picture of a calendar is unreadable to a screen reader and
    in greyscale, and this catalogue has an outside review's worth of evidence
    that the second group exists."""

    def test_a_plain_range(self):
        self.assertEqual(P.alt_text([6, 7, 8]), "Flowers June to August")

    def test_one_month_is_not_a_range(self):
        self.assertEqual(P.alt_text([6]), "Flowers in June")

    def test_bloom_and_fruit_are_one_sentence(self):
        self.assertEqual(P.alt_text([6, 7], [9]),
                         "Flowers June to July; fruits in September")

    def test_a_window_across_the_year_end_is_one_window(self):
        """`Nov-Feb` parses to [11, 12, 1, 2]; sorted that reads as January to
        December, which is the opposite of what it says."""
        self.assertEqual(P.alt_text(P.parse_period("Nov-Feb")),
                         "Flowers November to February")

    def test_all_year_says_so(self):
        self.assertEqual(P.alt_text(list(range(1, 13))), "Flowers all year")

    def test_the_svg_carries_the_words(self):
        svg = P.phenology_svg([6, 7, 8], [9])
        self.assertIn("Flowers June to August; fruits in September", svg)
        self.assertIn("<title>", svg)
        self.assertIn('role="img"', svg)


class TestItIsSelfContained(unittest.TestCase):
    """Same contract as ecoregion_map: no script, no external reference, no
    dependency. It is embedded directly in a page with a strict CSP."""

    SVG = None

    def setUp(self):
        self.SVG = P.phenology_svg([6, 7, 8], [9, 10])

    def test_no_script_and_no_external_reference(self):
        # The SVG namespace URI is an identifier, not a fetch -- nothing
        # retrieves it -- so it comes out before the substring check rather
        # than being special-cased inside a loop that would then pass for the
        # wrong reason.
        body = self.SVG.replace('xmlns="http://www.w3.org/2000/svg"', "")
        for forbidden in ("<script", "http://", "https://", "<image",
                          "xlink:href", "@import", "url("):
            self.assertNotIn(forbidden, body, forbidden)

    def test_twelve_months_are_drawn_per_row(self):
        """Not just the months that are on: the empty half is what makes it a
        calendar rather than a bar of unknown length."""
        self.assertEqual(self.SVG.count("<rect"), 1 + 12 + 12)   # season + 2 rows

    def test_one_row_when_there_is_no_fruit(self):
        self.assertEqual(P.phenology_svg([6, 7]).count("<rect"), 1 + 12)

    def test_it_scales_with_its_container(self):
        self.assertIn('width="100%"', self.SVG)
        self.assertIn("viewBox=", self.SVG)


class TestTheCaveatTravelsWithIt(unittest.TestCase):
    """P9. The window is a stated range from horticultural references, not a
    phenology series, and a bar looks like a measurement."""

    def test_it_says_what_the_data_is_not(self):
        self.assertIn("rather than phenology records", P.CAVEAT)
        self.assertIn("peak", P.CAVEAT)

    def test_the_species_page_carries_it(self):
        from src.static_site_species import _phenology
        cell = _phenology({"bloom": "June–August", "fruit": "September"})
        self.assertIn("<svg", cell)
        self.assertIn("phenology-alt", cell)
        self.assertIn("horticultural references", cell)

    def test_a_species_with_no_window_gets_no_row(self):
        from src.static_site_species import _phenology
        self.assertEqual(_phenology({"bloom": "", "fruit": ""}), "")


if __name__ == "__main__":
    unittest.main()

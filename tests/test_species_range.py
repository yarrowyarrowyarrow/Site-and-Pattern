"""
The range stops being made of ecoregions (F145, V2.79).

Since V2.38 a species range has been drawn by shading ecoregions, and every fix
from V2.75 onward improved *how* that shading was derived while leaving the
assumption underneath alone. The author named it after seeing the corrected
maps: *"this range does not neatly conform to ecoregions."* It does not,
because it is not made of them.

What these tests pin is mostly what a cell refuses to claim. The failure mode
is not a crash -- it is a picture that asserts more than the records support,
which is the whole subject of the review this work came out of.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import species_range as R                   # noqa: E402

EDMONTON = (53.55, -113.49)
CALGARY = (51.05, -114.07)
GOLDEN_BC = (51.30, -116.97)
GREAT_FALLS_MT = (47.50, -111.30)


class TestACellIsWhereARecordIs(unittest.TestCase):

    def test_a_coordinate_lands_in_one_cell(self):
        self.assertEqual(R.cell_of(*EDMONTON), (53.5, -113.5))

    def test_cells_are_half_open_so_nothing_lands_in_two(self):
        """Floor, not round. Rounding makes a cell straddle its own label and
        puts a point on a boundary into whichever neighbour wins a
        floating-point comparison."""
        self.assertEqual(R.cell_of(53.50, -113.50), (53.5, -113.5))
        self.assertEqual(R.cell_of(53.4999, -113.5001), (53.25, -113.75))
        self.assertNotEqual(R.cell_of(53.4999, -113.49),
                            R.cell_of(53.5001, -113.49))

    def test_two_records_in_one_square_are_one_cell(self):
        cells = R.occupied_cells([EDMONTON, (53.56, -113.48)])
        self.assertEqual(len(cells), 1)

    def test_an_empty_species_has_no_range(self):
        self.assertEqual(R.occupied_cells([]), [])

    def test_the_output_is_sorted_so_a_rerun_diffs_cleanly(self):
        a = R.occupied_cells([CALGARY, EDMONTON])
        b = R.occupied_cells([EDMONTON, CALGARY])
        self.assertEqual(a, b)
        self.assertEqual(a, sorted(a))

    def test_a_coarser_grid_merges_cells(self):
        pts = [EDMONTON, (53.8, -113.9)]
        self.assertGreater(len(R.occupied_cells(pts, step=0.25)),
                           len(R.occupied_cells(pts, step=1.0)))


class TestItDrawsNoGroundWeDoNotSpeakFor(unittest.TestCase):
    """F142's rule, in the new renderer. 31.7% of the harvest is outside the
    two provinces, and a range map of British Columbia drawn by a catalogue
    that covers Alberta and Saskatchewan is the same error in a new file."""

    def test_british_columbia_is_dropped(self):
        self.assertEqual(R.occupied_cells([GOLDEN_BC]), [])

    def test_montana_is_dropped(self):
        self.assertEqual(R.occupied_cells([GREAT_FALLS_MT]), [])

    def test_the_subject_filter_can_be_turned_off_for_a_caller_that_pre_filtered(self):
        """The seeder filters once and passes the survivors, so paying for the
        polygon test twice per record over half a million records is waste."""
        self.assertEqual(len(R.occupied_cells([GOLDEN_BC], subject_only=False)),
                         1)

    def test_a_real_species_keeps_its_alberta_records(self):
        cells = R.occupied_cells([EDMONTON, CALGARY, GOLDEN_BC])
        self.assertEqual(len(cells), 2)


class TestTheCountIsKeptAndSaysWhatItIs(unittest.TestCase):
    """V2.80. The first build drew presence in one colour and could not be
    read; shading by count is what makes the picture legible. The count is
    recording effort as much as it is the plant, and the risk here is not a
    crash -- it is a reader taking a dark square for abundance."""

    def test_records_in_a_cell_are_counted(self):
        pts = [EDMONTON, (53.56, -113.48), (53.51, -113.40), CALGARY]
        counts = R.cell_counts(pts)
        self.assertEqual(counts[(53.5, -113.5)], 3)
        self.assertEqual(counts[(51.0, -114.25)], 1)

    def test_presence_and_counts_agree_about_which_cells_exist(self):
        pts = [EDMONTON, EDMONTON, CALGARY, GOLDEN_BC]
        self.assertEqual(sorted(R.cell_counts(pts)), R.occupied_cells(pts))

    def test_out_of_province_records_are_not_counted_either(self):
        self.assertEqual(R.cell_counts([GOLDEN_BC, GREAT_FALLS_MT]), {})

    def test_the_bands_climb_and_a_single_record_is_the_lightest(self):
        self.assertEqual(R.density_band(1), 0)
        self.assertEqual(R.density_band(3), 1)
        self.assertEqual(R.density_band(12), 2)
        self.assertEqual(R.density_band(60), 3)
        self.assertEqual(R.density_band(4000), 4)

    def test_every_band_has_a_label_to_read_it_by(self):
        """A five-step ramp with no key is decoration."""
        self.assertEqual(len(R.BAND_LABELS), len(R.DENSITY_BREAKS) + 1)

    def test_the_caption_denies_the_ramp_is_an_abundance(self):
        text = R.caption([(53.5, -113.5, 400)])
        self.assertIn("roads and towns", text)

    def test_a_presence_only_caption_does_not_explain_a_ramp_nobody_drew(self):
        self.assertNotIn("roads and towns", R.caption([(53.5, -113.5)]))

    def test_the_shipped_comment_refuses_the_abundance_reading_too(self):
        doc = R.build_document({"Testus": {(53.5, -113.5): 400}})
        self.assertIn("not an abundance", doc["comment"])


class TestNothingRecordedDrawsNothing(unittest.TestCase):
    """The `phenology_bar` rule (P9). An empty grid would assert that we
    checked everywhere and found it nowhere."""

    def test_no_cells_means_no_caption(self):
        self.assertEqual(R.caption([]), "")

    def test_a_species_with_no_cells_is_left_out_of_the_document(self):
        doc = R.build_document({"Present sp.": [(53.5, -113.5)],
                                "Absent sp.": []})
        self.assertIn("Present sp.", doc["species"])
        self.assertNotIn("Absent sp.", doc["species"])


class TestTheCaptionRefusesTheClaimsAPictureImplies(unittest.TestCase):
    """A shaded square looks like "it grows here", and at 0.25 degrees that is
    28 km of ground on one record."""

    def setUp(self):
        self.text = R.caption([(53.5, -113.5)] * 3)

    def test_it_states_the_resolution(self):
        self.assertIn("28 km", self.text)

    def test_it_denies_the_square_is_uniformly_occupied(self):
        self.assertIn("not a claim that the plant grows throughout", self.text)

    def test_it_says_unshaded_is_unrecorded_not_absent(self):
        """The distinction `establishment.py` draws between unlikely and
        unknown, in the one place a reader meets it as a picture."""
        self.assertIn("unrecorded rather than", self.text)

    def test_the_shipped_comment_says_the_same(self):
        doc = R.build_document({"Testus": [(53.5, -113.5)]})
        self.assertIn("does NOT mean", doc["comment"])
        self.assertIn("unrecorded rather than absent", doc["comment"])


class TestTheShippedFile(unittest.TestCase):

    def test_it_round_trips(self):
        counts = {(51.0, -114.25): 7, (53.5, -113.5): 1}
        doc = R.build_document({"Testus": counts})
        self.assertEqual(R.parse_document(doc)["Testus"],
                         [(51.0, -114.25, 7), (53.5, -113.5, 1)])

    def test_a_caller_with_only_presence_does_not_have_to_invent_a_count(self):
        doc = R.build_document({"Testus": [(51.0, -114.25)]})
        self.assertEqual(R.parse_document(doc)["Testus"], [(51.0, -114.25, 1)])

    def test_it_records_the_resolution_it_was_built_at(self):
        """A file that does not say its own cell size cannot be drawn, and
        cannot be checked against a later run at a different one."""
        self.assertEqual(R.build_document({}, step=0.5)["cell_degrees"], 0.5)

    def test_a_malformed_row_is_skipped_not_crashed(self):
        blob = {"species": {"Testus": [[53.5, -113.5, 4], [1], "nope", None]}}
        self.assertEqual(R.parse_document(blob)["Testus"], [(53.5, -113.5, 4)])

    def test_a_version_1_row_reads_as_one_record_not_as_zero(self):
        """The file only ever held cells with at least one record in them, so a
        missing count is one. Reading a missing field as an absence is the
        mistake this repo has now made three times."""
        blob = {"version": 1, "species": {"Testus": [[53.5, -113.5]]}}
        self.assertEqual(R.parse_document(blob)["Testus"], [(53.5, -113.5, 1)])

    def test_a_missing_file_parses_to_nothing(self):
        self.assertEqual(R.parse_document({}), {})
        self.assertEqual(R.parse_document(None), {})


if __name__ == "__main__":
    unittest.main()

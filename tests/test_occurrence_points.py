"""
The records themselves, published (F147, V2.80).

The author's ask, after seeing the grid map:

    "The range picture (with the option to toggle the 2 kinds of observation
     data [catalogue vs iNaturalist]) should appear on the site too."

What these pin is mostly what does NOT reach the file. Three filters decide
that -- precision, subject area, licence -- and each has already been the
subject of a bug in this pipeline: V2.78's 31.7% of dots drawn over British
Columbia, V2.75's rate limit logged as absence, and the licence table's rule
that an unknown licence is not a permissive one.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import occurrence_points as P                # noqa: E402


class _Rec(tuple):
    """A cache row with a `basis`, the duck type the pipeline passes around."""

    def __new__(cls, lat, lng, basis=""):
        self = super().__new__(cls, (lat, lng))
        self.basis = basis
        return self


SPEC = "PRESERVED_SPECIMEN"
OBS = "HUMAN_OBSERVATION"


class TestTheTwoKindsStayApart(unittest.TestCase):
    """A pressed sheet in a cabinet and a photograph somebody uploaded are
    different evidence. A map that merges them silently asserts they are not."""

    def test_a_preserved_specimen_is_a_specimen(self):
        self.assertEqual(P.kind_of(_Rec(51.0, -114.0, SPEC)), P.KEY_SPECIMEN)

    def test_a_human_observation_is_not(self):
        self.assertEqual(P.kind_of(_Rec(51.0, -114.0, OBS)), P.KEY_OBSERVATION)

    def test_an_unknown_basis_is_an_observation_not_a_specimen(self):
        """`OCCURRENCE` is real and appears in the cache. Calling an unknown
        basis a herbarium specimen would upgrade the evidence, which is the
        direction that overstates."""
        self.assertEqual(P.kind_of(_Rec(51.0, -114.0, "OCCURRENCE")),
                         P.KEY_OBSERVATION)
        self.assertEqual(P.kind_of((51.0, -114.0)), P.KEY_OBSERVATION)

    def test_they_are_kept_in_separate_lists(self):
        got = P.marks([_Rec(51.0, -114.0, SPEC), _Rec(52.0, -113.0, OBS)])
        self.assertEqual(got[P.KEY_SPECIMEN], [(51.0, -114.0)])
        self.assertEqual(got[P.KEY_OBSERVATION], [(52.0, -113.0)])


class TestDedupeIsARenderingDecision(unittest.TestCase):
    """Not subsampling, which would be an editorial decision needing a caption.
    0.01 degrees is under half a pixel at every width the site draws."""

    def test_two_records_in_the_same_square_are_one_mark(self):
        pts = [_Rec(51.0000, -114.0000, OBS), _Rec(51.0009, -114.0007, OBS)]
        self.assertEqual(len(P.marks(pts)[P.KEY_OBSERVATION]), 1)

    def test_records_a_kilometre_apart_stay_two(self):
        pts = [_Rec(51.00, -114.00, OBS), _Rec(51.02, -114.00, OBS)]
        self.assertEqual(len(P.marks(pts)[P.KEY_OBSERVATION]), 2)

    def test_a_specimen_never_dedupes_away_an_observation(self):
        """Same square, different evidence. Collapsing them would lose the
        distinction the toggle exists for."""
        pts = [_Rec(51.0, -114.0, SPEC), _Rec(51.0, -114.0, OBS)]
        got = P.marks(pts)
        self.assertEqual(len(got[P.KEY_SPECIMEN]), 1)
        self.assertEqual(len(got[P.KEY_OBSERVATION]), 1)

    def test_output_is_sorted_so_a_rerun_diffs_cleanly(self):
        a = P.marks([_Rec(52.0, -113.0, OBS), _Rec(51.0, -114.0, OBS)])
        b = P.marks([_Rec(51.0, -114.0, OBS), _Rec(52.0, -113.0, OBS)])
        self.assertEqual(a, b)
        self.assertEqual(a[P.KEY_OBSERVATION],
                         sorted(a[P.KEY_OBSERVATION]))


class TestTheShippedFile(unittest.TestCase):

    def test_it_round_trips(self):
        doc = P.build_document({"Testus sp.": P.marks(
            [_Rec(51.0, -114.0, SPEC), _Rec(52.0, -113.0, OBS)])})
        got = P.parse_document(doc)["Testus sp."]
        self.assertEqual(got[P.KEY_SPECIMEN], [(51.0, -114.0)])
        self.assertEqual(got[P.KEY_OBSERVATION], [(52.0, -113.0)])

    def test_a_species_with_no_marks_is_left_out(self):
        doc = P.build_document({"Absent sp.": {"s": [], "o": []},
                                "Present sp.": {"s": [(51.0, -114.0)], "o": []}})
        self.assertIn("Present sp.", doc["species"])
        self.assertNotIn("Absent sp.", doc["species"])

    def test_an_empty_kind_is_not_written(self):
        doc = P.build_document({"Testus sp.": {"s": [(51.0, -114.0)], "o": []}})
        self.assertNotIn("o", doc["species"]["Testus sp."])

    def test_a_malformed_row_is_skipped_not_crashed(self):
        blob = {"species": {"T": {"s": [[51.0, -114.0], [1], "nope", None]}}}
        self.assertEqual(P.parse_document(blob)["T"]["s"], [(51.0, -114.0)])

    def test_a_missing_file_parses_to_nothing(self):
        self.assertEqual(P.parse_document({}), {})
        self.assertEqual(P.parse_document(None), {})

    def test_the_comment_refuses_the_abundance_reading(self):
        doc = P.build_document({"T": {"s": [(51.0, -114.0)], "o": []}})
        self.assertIn("not how much plant there is", doc["comment"])


class TestTheCaptionRefusesWhatDotsImply(unittest.TestCase):
    """Dot density tracks collection effort. A reader who counts dots and
    concludes "commonest here" has been misled by the picture."""

    def test_nothing_recorded_says_nothing(self):
        self.assertEqual(P.caption({}), "")
        self.assertEqual(P.caption({"s": [], "o": []}), "")

    def test_it_names_both_counts(self):
        text = P.caption({"s": [(1, 2)] * 5, "o": [(1, 2)] * 33})
        self.assertIn("5 herbarium specimens", text)
        self.assertIn("33 field observations", text)

    def test_it_says_dense_means_looked_at_not_commonest(self):
        text = P.caption({"s": [(1, 2)], "o": []})
        self.assertIn("where people have looked", text)
        self.assertIn("not where the plant is commonest", text)

    def test_it_says_empty_ground_is_unsurveyed(self):
        """The `establishment.py` distinction between unlikely and unknown, in
        the one place a reader meets it as a picture."""
        self.assertIn("unsurveyed rather than unoccupied",
                      P.caption({"s": [(1, 2)], "o": []}))

    def test_it_explains_the_two_mark_shapes(self):
        text = P.caption({"s": [(1, 2)], "o": [(3, 4)]})
        self.assertIn("pressed sheet", text)
        self.assertIn("community agreement", text)

    def test_one_of_something_is_not_plural(self):
        text = P.caption({"s": [(1, 2)], "o": [(3, 4)]})
        self.assertIn("1 herbarium specimen ", text)
        self.assertIn("1 field observation", text)


class TestTheLicenceSplitIsDeliberate(unittest.TestCase):
    """The author's V2.79 decision, implemented here: a photograph is
    redistributed as a work, a coordinate is a fact about a place."""

    def test_coordinates_accept_noncommercial_and_photographs_do_not(self):
        from scripts.fetch_dataset_licences import (PUBLISHABLE,
                                                    PUBLISHABLE_COORDINATES)
        self.assertIn("CC_BY_NC", PUBLISHABLE_COORDINATES)
        self.assertNotIn("CC_BY_NC", PUBLISHABLE)

    def test_the_coordinate_set_is_a_superset(self):
        """Anything publishable as a work is publishable as a coordinate.
        Two independently maintained lists would eventually disagree the
        other way round, which is the direction that leaks."""
        from scripts.fetch_dataset_licences import (PUBLISHABLE,
                                                    PUBLISHABLE_COORDINATES)
        self.assertTrue(set(PUBLISHABLE) <= set(PUBLISHABLE_COORDINATES))

    def test_an_unknown_licence_is_still_not_permissive(self):
        from scripts.fetch_dataset_licences import PUBLISHABLE_COORDINATES
        for token in ("UNSPECIFIED", "UNSUPPORTED", "", "CC_BY_NC_ND"):
            self.assertNotIn(token, PUBLISHABLE_COORDINATES)


if __name__ == "__main__":
    unittest.main()

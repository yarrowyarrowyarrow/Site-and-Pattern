"""
tests/test_count_open_photos.py — the count of photographs that may ship
(V3.34): the licence set, the report on what the colour review showed, and the
questions asked of iNaturalist, with the network replaced.
"""

import io
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))

from src import data_quality  # noqa: E402

import count_open_photos as cop  # noqa: E402


def _photo(licence):
    return {"url": "https://example/x.jpg", "license": licence}


EVIDENCE = {
    "Ratibida columnifera": {"taxon": {"id": 1}, "photos": [
        _photo("cc-by-nc"), _photo("cc-by"), _photo("cc-by-nc")]},
    "Silene acaulis": {"taxon": {"id": 2}, "photos": [
        _photo("cc-by-nc"), _photo(None)]},
    "Lemna trisulca": {"found": False},
}


class TheLicences(unittest.TestCase):

    def test_the_same_set_the_data_gate_allows(self):
        self.assertEqual(set(cop.OPEN), data_quality._PLANT_IMAGE_LICENSES)

    def test_the_second_tier_is_non_commercial_and_never_no_derivatives(self):
        self.assertFalse(set(cop.NC) & set(cop.OPEN))
        self.assertTrue(all("-nc" in code for code in cop.NC))
        self.assertFalse(any("-nd" in code for code in cop.NC + cop.OPEN))

    def test_what_the_colour_review_showed(self):
        text = "\n".join(cop.seen_report(EVIDENCE))
        self.assertIn("5 photographs shown, of 2 plants", text)
        self.assertIn("May ship: 1 of 5 (20%)", text)
        self.assertIn("at least one that may ship: 1 of 2", text)
        self.assertIn("none", text, "a photo with no licence is counted")
        self.assertIn("Non-commercial: 3 of 5 (60%)", text)

    def test_an_empty_cache_says_so(self):
        self.assertIn("No photographs", cop.seen_report({})[0])


class TheCount(unittest.TestCase):

    def test_four_questions_each_with_its_own_filter(self):
        asked = []

        def fake_get(path, params):
            asked.append(dict(params))
            lic = params.get("photo_license", "")
            return {"total_results": {"cc0,cc-by,cc-by-sa": 7,
                                      "cc-by-nc,cc-by-nc-sa": 50}.get(lic, 70)}

        with mock.patch.object(cop.inat, "get", fake_get):
            got = cop.count_one("Ratibida columnifera", 1, delay=0)
        self.assertEqual(got["open_anywhere"], 7)
        self.assertEqual(got["nc_anywhere"], 50)
        self.assertEqual(got["any_anywhere"], 70)
        self.assertEqual(len(asked), 4, "the cached taxon is not asked again")
        here, anywhere, nc, everything = asked
        self.assertEqual(here["photo_license"], "cc0,cc-by,cc-by-sa")
        self.assertIn("swlat", here)
        self.assertNotIn("swlat", anywhere)
        self.assertEqual(nc["photo_license"], "cc-by-nc,cc-by-nc-sa")
        self.assertNotIn("photo_license", everything)
        self.assertTrue(all(q["quality_grade"] == "research" for q in asked))

    def test_an_earlier_count_is_asked_only_what_it_lacks(self):
        """A plant counted before the non-commercial question was added."""
        earlier = {"taxon": 1, "open_here": 2, "open_anywhere": 4,
                   "any_anywhere": 40}
        self.assertTrue(cop.lacks(earlier))
        asked = []

        def fake_get(path, params):
            asked.append(dict(params))
            return {"total_results": 30}

        with mock.patch.object(cop.inat, "get", fake_get):
            got = cop.count_one("Ratibida columnifera", None, delay=0,
                                have=earlier)
        self.assertEqual(len(asked), 1)
        self.assertEqual(asked[0]["photo_license"], "cc-by-nc,cc-by-nc-sa")
        self.assertEqual((got["open_anywhere"], got["nc_anywhere"]), (4, 30))
        self.assertFalse(cop.lacks(got))
        self.assertFalse(cop.lacks({"taxon": None, "note": "no taxon"}))

    def test_a_plant_with_no_cached_taxon_is_looked_up(self):
        def fake_get(path, params):
            if path == "/taxa":
                return {"results": [{"id": 9, "name": "Picea glauca"}]}
            return {"total_results": 3}

        with mock.patch.object(cop.inat, "get", fake_get):
            got = cop.count_one("Picea glauca", None, delay=0)
        self.assertEqual(got["taxon"], 9)

    def test_the_summary_bands_and_names_the_plants_with_none(self):
        counts = {
            "A a": {"taxon": 1, "open_here": 0, "open_anywhere": 0,
                    "nc_anywhere": 0, "any_anywhere": 40},
            "B b": {"taxon": 2, "open_here": 3, "open_anywhere": 12,
                    "nc_anywhere": 30, "any_anywhere": 60},
            "D d": {"taxon": 4, "open_here": 0, "open_anywhere": 1,
                    "nc_anywhere": 5, "any_anywhere": 0},
            "C c": {"taxon": None, "note": "no taxon"},
        }
        lines = cop.summary(counts, {"A a": "Plant A"})
        text = "\n".join(lines)
        self.assertIn("3 plants counted; 1 not found", text)
        self.assertIn("may ship, in Alberta and Saskatchewan: none: 2, "
                      "1 to 5: 1", text)
        self.assertIn("may ship, anywhere: none: 1, 1 to 5: 1, 6 to 20: 1",
                      text)
        self.assertIn("non-commercial photo, anywhere: none: 1, 1 to 5: 1, "
                      "6 to 20: 0, more than 20: 1", text)
        self.assertIn("13 of 100 observations (13%) have a photo that may "
                      "ship; 35 (35%) a non-commercial one", text)
        self.assertIn("Short of choice (fewer than 3 that may ship): 2 "
                      "plants. Non-commercial photos would give 1 of them 3 "
                      "or more.", text)
        self.assertIn("No photo that may ship, anywhere (1): Plant A", text)
        self.assertIn("Neither kind, anywhere (1): Plant A", text)

    def test_a_summary_before_the_nc_count_says_nothing_of_it(self):
        counts = {"A a": {"taxon": 1, "open_here": 0, "open_anywhere": 0,
                          "any_anywhere": 40}}
        text = "\n".join(cop.summary(counts, {}))
        self.assertNotIn("non-commercial", text)
        self.assertNotIn("Short of choice", text)

    def test_seen_needs_no_network(self):
        with tempfile.TemporaryDirectory() as tmp, \
                mock.patch.object(cop.inat, "EVIDENCE",
                                  Path(tmp) / "missing.json"), \
                mock.patch.object(cop.inat, "get",
                                  side_effect=AssertionError("asked")):
            out = io.StringIO()
            with redirect_stdout(out):
                self.assertEqual(cop.main(["--seen"]), 0)
        self.assertIn("No photographs", out.getvalue())


if __name__ == "__main__":
    unittest.main()

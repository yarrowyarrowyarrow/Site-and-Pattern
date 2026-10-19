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

    def test_what_the_colour_review_showed(self):
        text = "\n".join(cop.seen_report(EVIDENCE))
        self.assertIn("5 photographs shown, of 2 plants", text)
        self.assertIn("May ship: 1 of 5 (20%)", text)
        self.assertIn("at least one that may ship: 1 of 2", text)
        self.assertIn("none", text, "a photo with no licence is counted")

    def test_an_empty_cache_says_so(self):
        self.assertIn("No photographs", cop.seen_report({})[0])


class TheCount(unittest.TestCase):

    def test_three_questions_with_the_filter_only_where_meant(self):
        asked = []

        def fake_get(path, params):
            asked.append(dict(params))
            return {"total_results": 7 if "photo_license" in params else 70}

        with mock.patch.object(cop.inat, "get", fake_get):
            got = cop.count_one("Ratibida columnifera", 1, delay=0)
        self.assertEqual(got["open_anywhere"], 7)
        self.assertEqual(got["any_anywhere"], 70)
        self.assertEqual(len(asked), 3, "the cached taxon is not asked again")
        here, anywhere, everything = asked
        self.assertEqual(here["photo_license"], "cc0,cc-by,cc-by-sa")
        self.assertIn("swlat", here)
        self.assertNotIn("swlat", anywhere)
        self.assertNotIn("photo_license", everything)
        self.assertTrue(all(q["quality_grade"] == "research" for q in asked))

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
                    "any_anywhere": 40},
            "B b": {"taxon": 2, "open_here": 3, "open_anywhere": 12,
                    "any_anywhere": 60},
            "C c": {"taxon": None, "note": "no taxon"},
        }
        text = "\n".join(cop.summary(counts, {"A a": "Plant A"}))
        self.assertIn("2 plants counted; 1 not found", text)
        self.assertIn("in Alberta and Saskatchewan: none: 1, 1 to 5: 1", text)
        self.assertIn("anywhere: none: 1, 1 to 5: 0, 6 to 20: 1", text)
        self.assertIn("12 of 100 observations (12%)", text)
        self.assertIn("No photo that may ship, anywhere (1): Plant A", text)

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

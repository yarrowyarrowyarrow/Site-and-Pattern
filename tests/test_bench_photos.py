"""
tests/test_bench_photos.py — the curation bench's photo strip (V2.36).

Why this file exists at all: **nothing guarded the bench**, and it broke in a way
that produced no error. V2.35 replaced its single reference photo with a
seven-slot strip fed from `data/plant_photos.json`; that file was empty, so all
323 photographs the catalogue already ships simply stopped being drawn. Every
test passed. The tool's whole purpose is comparing a sprite against a photograph
and it silently had no photographs.

So: the vocabulary is pinned to the one in `src/db/photos.py` (a drift there
reorders which photo the app shows, which is also silent), and the sort loop is
exercised end to end.

Pattern from tests/test_flower_morphology.py — imports the script directly.
Never touches `data/plant_photos.json`: `_PHOTOS_JSON` is redirected to a temp
file for every test.
"""

import json
import os
import sys
import tempfile
import unittest

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)
sys.path.insert(0, os.path.join(_ROOT, "scripts"))

import tune_morphology as bench                             # noqa: E402

_SCI = "Rudbeckia hirta"


class TestVocabulary(unittest.TestCase):
    def test_the_bench_names_the_same_slots_as_the_database(self):
        """The bench's list is a separate literal from `src/db/photos.py`'s, in
        a separate language (the HTML has a third copy). A drift does not raise
        — it files photographs into a slot the app never reads."""
        from src.db import photos                            # noqa: PLC0415
        self.assertEqual(tuple(bench.PHOTO_SLOTS), tuple(photos.SLOTS))

    def test_the_html_names_them_too(self):
        with open(os.path.join(_ROOT, "html", "tune_morphology.html"),
                  encoding="utf-8") as fh:
            html = fh.read()
        for slot in bench.PHOTO_SLOTS:
            self.assertIn(f"'{slot}'", html,
                          f"the bench page does not offer the {slot!r} slot")

    def test_unsorted_is_not_one_of_the_real_slots(self):
        """It is a queue, not a place a photograph lives. If it ever became a
        real slot, `coverage()` would start counting unjudged photos as
        coverage — the exact false precision this bucket exists to avoid."""
        self.assertNotIn(bench.UNSORTED, bench.PHOTO_SLOTS)


class TestSorting(unittest.TestCase):
    def setUp(self):
        self._real = bench._PHOTOS_JSON
        self._tmp = tempfile.mkdtemp()
        bench._PHOTOS_JSON = os.path.join(self._tmp, "plant_photos.json")

    def tearDown(self):
        bench._PHOTOS_JSON = self._real

    def _rows(self):
        with open(bench._PHOTOS_JSON, encoding="utf-8") as fh:
            return json.load(fh)

    def _write(self, rows):
        with open(bench._PHOTOS_JSON, "w", encoding="utf-8") as fh:
            json.dump(rows, fh)

    def test_a_shipped_photo_shows_up_as_unsorted(self):
        """The regression, stated as a test. `image_url` is populated for 323
        species and the strip has to show it."""
        rec = bench._rec_for(_SCI)
        self.assertTrue(rec.get("image_url"), "fixture species lost its photo")
        by = bench.photos_by_slot(_SCI, rec)
        self.assertEqual(len(by[bench.UNSORTED]), 1)
        self.assertEqual(by[bench.UNSORTED][0]["url"], rec["image_url"])
        self.assertFalse(any(by[s] for s in bench.PHOTO_SLOTS),
                         "an unjudged photo must not count as slot coverage")

    def test_the_credit_travels_with_the_photo(self):
        """CC-BY obliges a visible credit. A photo shown in the bench without
        one is the same licence problem as a photo shown in the app without
        one."""
        rec = bench._rec_for(_SCI)
        p = bench.photos_by_slot(_SCI, rec)[bench.UNSORTED][0]
        self.assertEqual(p["attribution"], rec.get("image_attribution"))
        self.assertEqual(p["license"], rec.get("image_license"))

    def test_an_unsorted_photo_cannot_be_deleted(self):
        """`_i` is the row index the delete endpoint takes. There is no row —
        the photo lives in plants_master.json, which this pane does not own."""
        rec = bench._rec_for(_SCI)
        self.assertIsNone(bench.photos_by_slot(_SCI, rec)[bench.UNSORTED][0]["_i"])

    def test_sorting_moves_it_out_of_the_queue(self):
        rec = bench._rec_for(_SCI)
        self._write([{"scientific_name": _SCI, "slot": "habit",
                      "url": rec["image_url"], "attribution": "x",
                      "license": "cc-by", "source": "inaturalist"}])
        by = bench.photos_by_slot(_SCI, rec)
        self.assertEqual(len(by["habit"]), 1)
        self.assertEqual(by[bench.UNSORTED], [],
                         "a sorted photo is still sitting in the queue — it "
                         "would be counted twice and offered for sorting again")

    def test_a_species_with_no_photo_has_an_empty_queue(self):
        by = bench.photos_by_slot("Nothingia inventa", {})
        self.assertEqual(by[bench.UNSORTED], [])
        self.assertTrue(all(by[s] == [] for s in bench.PHOTO_SLOTS))

    def test_a_users_own_photo_never_lands_in_the_queue(self):
        """The queue is 'somebody has to look at this'. A photo you imported
        into a named slot yourself has already been judged, by you."""
        rec = bench._rec_for(_SCI)
        self._write([{"scientific_name": _SCI, "slot": "flower",
                      "url": "data/photos/mine.jpg", "source": "owner"}])
        by = bench.photos_by_slot(_SCI, rec)
        self.assertEqual(len(by["flower"]), 1)
        self.assertEqual(len(by[bench.UNSORTED]), 1,
                         "the shipped photo should still need sorting — it is "
                         "a different photograph from the one you imported")


class TestLookupLinks(unittest.TestCase):
    def test_the_freely_reusable_source_comes_first(self):
        """Order is by licence, not by quality. FNA has the best descriptions
        and is copyrighted; Budd's is a Government of Canada publication AND the
        right region, so it is what somebody should reach for first."""
        links = bench.lookup_links("Rudbeckia hirta")
        self.assertIn("Budd", links[0]["name"])

    def test_only_some_links_offer_to_be_read(self):
        links = bench.lookup_links("Rudbeckia hirta")
        readable = [l["name"] for l in links if l.get("read")]
        self.assertTrue(readable)
        self.assertLess(len(readable), len(links),
                        "every link became machine-readable — the point is that "
                        "most of these are for a person's eyes")

    def test_no_links_without_a_name(self):
        self.assertEqual(bench.lookup_links(""), [])


class TestFloraFetchIsOffByDefault(unittest.TestCase):
    def test_the_switch_defaults_to_off(self):
        """Fetching a published description is a decision somebody makes at a
        command line after reading a site's terms, not a default."""
        self.assertFalse(bench.FLORA_FETCH)

    def test_there_is_no_bulk_path(self):
        """The structural property that makes this a reading aid rather than a
        scrape. If a loop over species ever appears in flora_read.py, that is
        the change worth arguing about, and this fails so it gets argued."""
        with open(os.path.join(_ROOT, "src", "flora_read.py"),
                  encoding="utf-8") as fh:
            src = fh.read()
        import re                                            # noqa: PLC0415
        body = "\n".join(l for l in src.splitlines()
                         if not l.strip().startswith(("#", "*")))
        for bad in (r"for\s+\w*url\w*\s+in", r"for\s+\w*sci\w*\s+in",
                    r"def\s+read_all", r"def\s+read_many", r"def\s+read_species_list"):
            self.assertIsNone(re.search(bad, body),
                              f"flora_read.py grew a bulk path: {bad}")


if __name__ == "__main__":
    unittest.main()

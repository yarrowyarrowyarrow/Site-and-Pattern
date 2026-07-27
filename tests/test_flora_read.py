"""
tests/test_flora_read.py — the one-page-at-a-time flora reader (V2.36).

Two kinds of test here, and the second kind is the unusual one.

**Does it read correctly?** Botanical prose has two traps that both produce a
confident wrong number, which is worse than no number because the 3D render then
makes it look considered:

  "ray florets 8-16"   the bare `florets` phrase matches INSIDE this, so the
                       disc count silently becomes the ray count
  "stems 10-30 cm"     that is a HEIGHT, and nothing in the sentence but the
                       unit distinguishes it from a count of stems

**Does it stay a reading aid?** The restraint in this module is structural, not
a promise in a docstring — no bulk path, robots checked, no prose retained, no
cache. Those properties are only worth anything if a later change that removes
one of them fails a test rather than passing review.

Entirely offline: every parser test runs on a fixture, and the network tests
assert refusal rather than success.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import flora_read                                  # noqa: E402
from src.flora_read import (NotPermitted, parse_description,  # noqa: E402
                            robots_allows, strip_html)

# An FNA-style description. Written to the idiom, not copied from one.
_FIXTURE = """
<html><body><p><b>Rudbeckia hirta</b> Linnaeus. Plants 30-100 cm.
Stems usually branched distally, hispid. Leaves: blades lanceolate to ovate,
5-15 cm. Heads 5-9 cm diam. Ray florets 8-16; laminae 15-40 mm, yellow.
Disc florets 60-90; corollas brown-purple, 3-4 mm.</p></body></html>
"""


class TestReading(unittest.TestCase):
    def test_the_four_numbers_come_off_a_description(self):
        r = parse_description(_FIXTURE, citation="FNA vol. 21")
        self.assertEqual(r.petal_count, 12)          # midpoint of 8-16
        self.assertEqual(r.florets_per_head, 75)     # midpoint of 60-90
        self.assertEqual(r.flower_diameter_cm, 7.0)  # midpoint of 5-9 cm

    def test_ray_florets_do_not_leak_into_the_disc_count(self):
        r = parse_description("Ray florets 8-16. Corollas yellow.")
        self.assertEqual(r.petal_count, 12)
        self.assertIsNone(r.florets_per_head,
                          "the bare `florets` pattern matched inside `ray "
                          "florets` — the disc count is now the ray count")

    def test_a_stem_height_is_not_a_stem_count(self):
        r = parse_description("Stems 10-30 cm, erect from a caudex.")
        self.assertIsNone(r.flowering_stems,
                          "a plant's height in centimetres was recorded as its "
                          "number of flowering stems")

    def test_a_real_stem_count_still_reads(self):
        self.assertEqual(parse_description("Scapes 2-6 per plant.").flowering_stems, 4)

    def test_parenthetical_extremes_are_dropped(self):
        """Floras hedge: `(5-)8-13(-21)`. The typical range is what the
        generator wants; the once-in-a-thousand specimen is noise."""
        r = parse_description("Ray florets (5-)8-13(-21).")
        self.assertEqual(r.petal_count, 10)

    def test_a_sentence_ending_full_stop_does_not_truncate_a_number(self):
        r = parse_description("Disc florets 60-90. Heads 4-6 cm diam.")
        self.assertEqual(r.florets_per_head, 75)

    def test_millimetres_become_centimetres(self):
        self.assertEqual(
            parse_description("Heads 8-14 mm diam.").flower_diameter_cm, 1.1)

    def test_a_value_the_catalogue_cannot_hold_is_dropped_not_clamped(self):
        """A goldenrod's several-hundred-floret spray is off the scale the
        catalogue keeps. Silently storing the ceiling would read as a
        measurement (P9)."""
        r = parse_description("Disc florets 250-500.")
        self.assertIsNone(r.florets_per_head)

    def test_a_description_with_no_numbers_proposes_nothing(self):
        r = parse_description("A cheerful plant of moist meadows.", citation="x")
        self.assertEqual(r.as_patch(), {},
                         "an unparseable page produced a patch — it would "
                         "overwrite real values with guesses")

    def test_a_reading_carries_its_provenance(self):
        patch = parse_description(_FIXTURE, citation="FNA vol. 21").as_patch()
        self.assertEqual(patch["flower_data_source"], "flora")
        self.assertEqual(patch["flower_data_citation"], "FNA vol. 21")

    def test_a_missing_field_is_absent_rather_than_null(self):
        """A `None` in the patch would clear a number somebody measured with a
        ruler."""
        patch = parse_description("Heads 4-6 cm diam.").as_patch()
        self.assertIn("flower_diameter_cm", patch)
        self.assertNotIn("petal_count", patch)


class TestKeepsNoProse(unittest.TestCase):
    def test_the_result_holds_numbers_and_a_citation_and_nothing_else(self):
        """The whole ethical claim is 'only the facts'. What comes back is four
        numbers, the citation the CALLER supplied, and the matched phrases —
        which are short and exist so a person can check the reading."""
        r = parse_description(_FIXTURE, citation="FNA vol. 21")
        blob = repr(r)
        self.assertNotIn("lanceolate", blob)
        self.assertNotIn("caudex", blob)
        self.assertNotIn("hispid", blob)
        for phrase in r.matched:
            self.assertLess(len(phrase), 60, f"matched phrase is prose: {phrase}")

    def test_there_is_no_cache(self):
        """A disk cache would mean the page is stored, which is the thing this
        module says it does not do."""
        with open(os.path.join(os.path.dirname(__file__), os.pardir,
                               "src", "flora_read.py"), encoding="utf-8") as fh:
            src = fh.read()
        for bad in ("shelve", "pickle", "sqlite3", "cache_dir", "CACHE_DIR"):
            self.assertNotIn(bad, src, f"flora_read.py grew a {bad}")

    def test_strip_html_drops_scripts_not_just_tags(self):
        text = strip_html("<script>var x='florets 99';</script><p>Petals 5.</p>")
        self.assertNotIn("99", text)
        self.assertIn("Petals 5", text)


class TestRefusesRatherThanAsks(unittest.TestCase):
    def test_robots_fails_closed_on_an_unreachable_host(self):
        """The usual convention is to assume allowed when robots.txt cannot be
        read, because that optimises for the crawler getting its data. Here a
        wrong 'yes' costs somebody's goodwill, so it is the other way round."""
        flora_read._robots_cache.clear()
        self.assertFalse(robots_allows("https://no-such-host.invalid/page"))

    def test_a_non_http_url_is_refused_without_a_lookup(self):
        self.assertFalse(robots_allows("file:///etc/passwd"))
        self.assertFalse(robots_allows("ftp://example.invalid/x"))
        self.assertFalse(robots_allows("not a url"))

    def test_fetch_raises_rather_than_proceeding_when_robots_says_no(self):
        flora_read._robots_cache.clear()
        with self.assertRaises(NotPermitted):
            flora_read.fetch_page("https://no-such-host.invalid/page")

    def test_it_identifies_itself(self):
        """An anonymous User-Agent is the mark of somebody expecting to be
        objected to. The operator of any server this touches should be able to
        tell what it is and who to complain to."""
        ua = flora_read.USER_AGENT
        self.assertIn("Site-and-Pattern", ua)
        self.assertIn("noncommercial", ua)
        self.assertIn("http", ua)

    def test_it_waits_between_requests(self):
        self.assertGreaterEqual(flora_read.MIN_INTERVAL_S, 1.0)


class TestProvenanceGate(unittest.TestCase):
    """A number read out of a flora has to say WHICH flora, and the data gate
    is what makes that stick — the reader fills the citation in on its own, but
    a person typing values by hand can leave it blank."""

    def test_a_claimed_source_without_a_citation_is_an_error(self):
        from src import data_quality                         # noqa: PLC0415
        real = data_quality._load_json_list
        data_quality._load_json_list = lambda p: (
            [{"scientific_name": "Testus fictus", "flower_data_source": "flora",
              "flower_data_citation": ""}]
            if "plants_master" in str(p) else real(p))
        try:
            errors, _ = data_quality.validate_flower_provenance()
        finally:
            data_quality._load_json_list = real
        self.assertTrue(any("no citation" in e for e in errors))

    def test_a_cited_source_passes(self):
        from src import data_quality                         # noqa: PLC0415
        real = data_quality._load_json_list
        data_quality._load_json_list = lambda p: (
            [{"scientific_name": "Testus fictus", "flower_data_source": "flora",
              "flower_data_citation": "FNA vol. 21"}]
            if "plants_master" in str(p) else real(p))
        try:
            errors, warnings = data_quality.validate_flower_provenance()
        finally:
            data_quality._load_json_list = real
        self.assertEqual(errors, [])
        self.assertEqual(warnings, [], "a verified species still reported none")

    def test_the_shipped_catalogue_passes_the_gate(self):
        from src.data_quality import validate_flower_provenance  # noqa: PLC0415
        errors, _ = validate_flower_provenance()
        self.assertEqual(errors, [])


if __name__ == "__main__":
    unittest.main()

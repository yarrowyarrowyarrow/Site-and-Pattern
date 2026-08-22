"""
The nativity claim gets the mark it never had (F144, V2.78).

This is the outside botanical review's actual criticism, and the generator that
produced the field says so in its own retirement docstring: *"many species
listed as native to AB and SK are native to only one. They are reading the
output of this file."*

Flower colour has carried a provenance note since V2.48. Safety has one. Leaf
shape has one. The field a site called GrowNativePlants is named for had none,
which is exactly backwards, and 354 of 430 species publish "AB, SK" from a
heuristic about ecoregion continuity.

The sourced replacement is VASCAN (F137), whose fetcher is written and tested
and has never run because the project's sessions cannot reach
data.canadensys.net. These tests pin the interim answer and the seam the real
one arrives through.
"""

import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import nativity as N                        # noqa: E402


class TestTheClaimSaysWhatItRestsOn(unittest.TestCase):

    def test_ab_and_sk_names_the_inference_that_produced_it(self):
        """Not a vague "unverified": the reader is owed the actual heuristic,
        which is that the ecoregions continue across the 110th meridian."""
        note = N.provenance({"native_provinces": "AB,SK"})["note"]
        self.assertIn("ecoregions that continue across", note)
        self.assertIn("not from a range map", note)

    def test_alberta_alone_names_a_different_provenance(self):
        """One string, two provenances. Alberta rests on an editorial flag from
        the first seed file; Saskatchewan on the ecoregion heuristic. A single
        note for both would be false for one of them."""
        note = N.provenance({"native_provinces": "AB"})["note"]
        self.assertIn("Alberta flag", note)
        self.assertNotIn("ecoregions that continue", note)

    def test_a_hand_set_code_is_not_credited_to_the_heuristic(self):
        """One row reads "SK,MB". The generator preserved it rather than
        producing it, so saying it inferred it would be its own false claim."""
        note = N.provenance({"native_provinces": "SK,MB"})["note"]
        self.assertIn("not checked against a published flora", note)
        self.assertNotIn("ecoregions that continue", note)

    def test_no_claim_gets_no_note(self):
        self.assertEqual(N.provenance({"native_provinces": ""})["note"], "")
        self.assertFalse(N.provenance({})["inferred"])

    def test_it_reads_the_directory_entry_shape_too(self):
        """`species_entry` renames the field to `native`, and the website reads
        the entry rather than the row. A function that knew only the raw key
        would pass every test here and render nothing on 430 published pages."""
        self.assertEqual(N.provenance({"native": "AB,SK"})["note"],
                         N.provenance({"native_provinces": "AB,SK"})["note"])
        self.assertTrue(N.provenance({"native": "AB,SK"})["note"])


class TestTheSeamVascanArrivesThrough(unittest.TestCase):
    """When the fetch runs, each species gains a real per-species source and
    the derived note must get out of the way."""

    def test_a_checked_source_carries_no_mark(self):
        """A verified value carries no mark. Marking everything trains the eye
        to skip the mark, which loses the one case that matters -- the rule is
        `src.confidence.annotate`'s and is borrowed, not restated."""
        row = {"native_provinces": "AB,SK", N.SOURCE_FIELD: "flora"}
        self.assertEqual(N.provenance(row)["note"], "")
        self.assertFalse(N.provenance(row)["inferred"])

    def test_an_inferred_source_uses_the_shared_vocabulary(self):
        from src.confidence import mark
        row = {"native_provinces": "AB,SK", N.SOURCE_FIELD: "estimated"}
        self.assertEqual(N.provenance(row)["note"], mark("estimated").label)

    def test_a_source_beats_the_derived_note(self):
        """Once the column exists the heuristic sentence is wrong for that
        species, so it must not survive alongside the sourced answer."""
        row = {"native_provinces": "AB,SK", N.SOURCE_FIELD: "flora"}
        self.assertNotIn("ecoregions", N.provenance(row)["note"])

    def test_the_column_does_not_exist_yet_and_that_is_recorded(self):
        """If this starts failing, VASCAN has landed and `provenance` should
        read the column rather than infer from the shape of the value."""
        with open(os.path.join(os.path.dirname(__file__), "..", "data",
                               "plants_master.json"), encoding="utf-8") as fh:
            rows = json.load(fh)
        rows = rows if isinstance(rows, list) else rows.get("plants", [])
        have = [r for r in rows if r.get(N.SOURCE_FIELD)]
        self.assertEqual(have, [], "VASCAN has run: read the column, not the "
                                   "shape of the value")


class TestEveryPublishedClaimIsMarked(unittest.TestCase):
    """The failure mode is silent: a note that renders nowhere looks exactly
    like a catalogue whose claims are all sourced."""

    def test_every_shipped_species_with_a_claim_gets_a_note(self):
        with open(os.path.join(os.path.dirname(__file__), "..", "data",
                               "plants_master.json"), encoding="utf-8") as fh:
            rows = json.load(fh)
        rows = rows if isinstance(rows, list) else rows.get("plants", [])
        claimed = [r for r in rows if (r.get("native_provinces") or "").strip()]
        self.assertGreater(len(claimed), 400)
        unmarked = [r.get("scientific_name") for r in claimed
                    if not N.provenance(r)["note"]]
        self.assertEqual(unmarked, [])

    def test_the_species_page_renders_it(self):
        from src.static_site_species import _native
        cell = _native({"native": "AB,SK"})
        self.assertIn("AB, SK", cell)
        self.assertIn("ecoregions that continue across", cell)
        self.assertIn('class="src"', cell)      # the class the colour note uses

    def test_a_species_with_no_claim_renders_an_empty_cell(self):
        from src.static_site_species import _native
        self.assertEqual(_native({"native": ""}), "")


if __name__ == "__main__":
    unittest.main()

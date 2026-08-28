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

The sourced replacement is VASCAN (F137). **It has now run** (V2.80): the
author downloaded the Darwin Core Archive on a machine with egress, and 414
species carry `native_provinces_source = "flora"` while ~20 that VASCAN
could not settle -- a removal, a rename, or a lineage the reader could not
follow -- deliberately carry nothing and keep the derived note.

These tests pin both halves, and the seam test that used to count down to
this day is inverted rather than deleted.
"""

import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import nativity as N                        # noqa: E402


def _shipped() -> list:
    """The shipped plant rows. Both files, because `garden_plants.json` also
    carries `native_provinces` and a guard that reads only the master would
    pass while half the catalogue drifted."""
    out = []
    for name in ("plants_master.json", "garden_plants.json"):
        path = os.path.join(os.path.dirname(__file__), "..", "data", name)
        with open(path, encoding="utf-8") as fh:
            rows = json.load(fh)
        out += rows if isinstance(rows, list) else rows.get("plants", [])
    return out


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

    def test_vascan_has_landed_and_most_species_carry_a_real_source(self):
        """This test used to assert the column was EMPTY, as a countdown: *"if
        this starts failing, VASCAN has landed"*. It started failing in V2.80,
        when the author ran the Darwin Core Archive and 414 species gained a
        source read from a published flora. Inverted rather than deleted, so
        the invariant it was protecting -- that nothing writes this field by
        accident -- keeps a guard."""
        rows = _shipped()
        sourced = [r for r in rows if r.get(N.SOURCE_FIELD)]
        self.assertGreater(len(sourced), 400)
        for row in sourced:
            self.assertEqual(row[N.SOURCE_FIELD], "flora",
                             f"{row.get('scientific_name')} carries an "
                             f"unexpected source value")

    def test_the_species_vascan_could_not_settle_keep_no_source(self):
        """A handful of species are a removal, a rename, or a lineage the
        archive reader could not follow. Stamping those would publish "read
        from a published flora" over an answer no flora gave, which is the
        exact overstatement this whole line of work exists to remove.

        V2.80 worked that list down from ~20 to **six**, and the arithmetic is
        the point: four introduced species removed, eight renamed to the
        accepted taxon, and the renames then **sourced themselves** when the
        author re-ran the archive under the corrected names -- which is what
        clearing the source on a rename was for.

        The six that remain are two distinct and permanent reasons, so this
        asserts one example of each rather than a list every data pass
        invalidates. An earlier version pinned *Urtica gracilis* as unsourced
        and failed the moment the re-run sourced it, which was the test
        working: it had recorded a state that was supposed to be temporary."""
        rows = _shipped()
        blank = [r.get("scientific_name") for r in rows
                 if not r.get(N.SOURCE_FIELD)]
        self.assertTrue(blank, "every species sourced: check nothing stamped "
                               "the unresolved ones")

        # Recorded by VASCAN, but not for Alberta or Saskatchewan. No rename
        # resolves this one, so it is a stable pin.
        self.assertIn("Spiraea douglasii", blank)
        # A cultivar; no flora carries it at all, and none ever will.
        self.assertIn("Prunus tomentosa", blank)
        # The renamed eight are sourced now, from the archive rather than from
        # a transcription -- the whole reason a rename blanks the field.
        self.assertNotIn("Urtica gracilis subsp. gracilis", blank)
        self.assertLessEqual(len(blank), 8,
                             f"the withheld list should be down to the "
                             f"cultivars and the absentees: {sorted(blank)}")

        # Removed outright, so not merely unsourced -- gone.
        names = {r.get("scientific_name") for r in rows}
        for gone in ("Helianthus annuus", "Achillea millefolium",
                     "Oligoneuron rigidum"):
            self.assertNotIn(gone, names)


class TestEveryPublishedClaimIsMarked(unittest.TestCase):
    """The failure mode is silent: a note that renders nowhere looks exactly
    like a catalogue whose claims are all sourced."""

    def test_every_shipped_species_with_a_claim_is_sourced_or_marked(self):
        """Before V2.80 this read "gets a note", because nothing was sourced
        and an unmarked claim could only be an unmarked inference. Now 414
        species are read from a flora and correctly carry NO note -- a checked
        value is not marked, or the eye learns to skip the mark. So the
        invariant generalises rather than relaxes: a published claim is either
        sourced or marked, and never silently neither."""
        claimed = [r for r in _shipped()
                   if (r.get("native_provinces") or "").strip()]
        self.assertGreater(len(claimed), 400)
        naked = [r.get("scientific_name") for r in claimed
                 if not r.get(N.SOURCE_FIELD) and not N.provenance(r)["note"]]
        self.assertEqual(naked, [])

    def test_the_species_page_withholds_an_unsourced_claim(self):
        """V2.80. It used to render "AB, SK" with the heuristic named beside
        it. The author's instruction was to stop making the inference at all,
        so the province list is no longer published for an unsourced row --
        the row says the claim is not established instead."""
        from src.nativity import WITHHELD_NOTE
        from src.static_site_species import _native
        cell = _native({"native": "AB,SK"})
        self.assertNotIn("AB, SK", cell)
        self.assertIn("Not established", cell)
        self.assertIn(WITHHELD_NOTE.split(".")[0], cell)
        # `.src` is the class the flower-colour note uses, so the two
        # provenance statements on a page read as the same kind of thing.
        self.assertIn('class="src"', cell)

    def test_the_species_page_renders_a_sourced_claim_plainly(self):
        from src.static_site_species import _native
        cell = _native({"native": "AB,SK", N.SOURCE_FIELD: "flora"})
        self.assertIn("AB, SK", cell)
        self.assertNotIn("Not established", cell)
        # No mark at all: a checked value carries none, or the eye learns to
        # skip the mark and loses the one case that matters.
        self.assertNotIn('class="src"', cell)

    def test_a_species_with_no_claim_renders_an_empty_cell(self):
        from src.static_site_species import _native
        self.assertEqual(_native({"native": ""}), "")


if __name__ == "__main__":
    unittest.main()

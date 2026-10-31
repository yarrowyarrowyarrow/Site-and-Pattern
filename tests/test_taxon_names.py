"""The two names a reader actually reads, and the gates over them (V2.82).

A report that two harebell cards had swapped common names turned out to be one
outdated binomial — *Campanula alaskana*, which the repository's own VASCAN
extract had resolved to *Campanula rotundifolia* two releases earlier. Nothing
had ever compared a row's name to the accepted name sitting beside it, and four
of V2.80's eight renames had landed on ranks the checklist does not carry.

These tests hold three things:

* ``binomial`` reads a name the way an authority string actually works, because
  reading it by eye is what produced those four renames;
* the shipped catalogue agrees with the extract, or says why in an allowlist;
* no two rows lead with the same common name, which is what made the wrong
  binomial visible in the first place.
"""

import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from src.taxon_names import binomial, is_infraspecific       # noqa: E402


class TestBinomial(unittest.TestCase):
    """Every case here is a real string out of the VASCAN archive."""

    def test_the_authority_is_dropped(self):
        self.assertEqual(binomial("Campanula rotundifolia Linnaeus"),
                         "Campanula rotundifolia")
        self.assertEqual(
            binomial("Deschampsia cespitosa (Linnaeus) Palisot de Beauvois"),
            "Deschampsia cespitosa")

    def test_a_rank_marker_is_part_of_the_name(self):
        self.assertEqual(
            binomial("Spiraea splendens var. rosea (A. Gray) Kartesz & Gandhi"),
            "Spiraea splendens var. rosea")
        self.assertEqual(
            binomial("Hedysarum boreale subsp. mackenziei (Richardson) S.L. Welsh"),
            "Hedysarum boreale subsp. mackenziei")

    def test_a_rank_after_the_authority_is_not_reattached(self):
        """``Primula pauciflora (Greene) A.R. Mast & Reveal var. pauciflora``.

        The autonym trails the authority, so it is not a rank on the name being
        read — and treating it as one is exactly how a species became a
        subspecies four times in V2.80.
        """
        self.assertEqual(
            binomial("Primula pauciflora (Greene) A.R. Mast & Reveal "
                     "var. pauciflora"),
            "Primula pauciflora")

    def test_the_four_V2_80_renames_would_have_been_caught(self):
        wrong = {
            "Stachys pilosa Nuttall": "Stachys pilosa var. pilosa",
            "Urtica gracilis Aiton": "Urtica gracilis subsp. gracilis",
            "Oenothera cespitosa Nuttall": "Oenothera cespitosa subsp. cespitosa",
            "Deschampsia cespitosa (Linnaeus) Palisot de Beauvois":
                "Deschampsia cespitosa subsp. cespitosa",
        }
        for authored, shipped in wrong.items():
            self.assertNotEqual(binomial(authored), shipped)
            self.assertTrue(is_infraspecific(shipped))
            self.assertFalse(is_infraspecific(binomial(authored)))

    def test_empty_in_empty_out(self):
        self.assertEqual(binomial(""), "")
        self.assertEqual(binomial(None), "")


class TestAcceptedNameGate(unittest.TestCase):

    def test_the_shipped_catalogue_agrees_with_the_extract(self):
        from src.data_quality import validate_accepted_names
        errors, warnings = validate_accepted_names()
        self.assertEqual(errors, [], "\n".join(errors))
        self.assertEqual(warnings, [], "\n".join(warnings))

    def test_the_extract_is_actually_present(self):
        """A skipped check passes, which is the failure this repository keeps
        finding. If the extract goes missing the gate must say so."""
        from src.data_quality import _accepted_names
        accepted = _accepted_names()
        self.assertIsNotNone(accepted)
        self.assertGreater(len(accepted), 400)

    def test_a_synonym_of_another_row_is_an_error_with_no_allowlist(self):
        import src.data_quality as dq
        rows = [{"scientific_name": "Testus oldus", "common_name": "Old Test"},
                {"scientific_name": "Testus newus", "common_name": "New Test"}]
        real_rows, real_acc = dq._load_json_list, dq._accepted_names
        dq._load_json_list = lambda p: rows if "plants_master" in str(p) else []
        dq._accepted_names = lambda: {
            "Testus oldus": {"accepted_name": "Testus newus Author"}}
        try:
            # Even allowlisted, a collision with another row still fails: it is
            # two pages for one plant, not a nomenclatural preference.
            dq.KNOWN_NOMENCLATURE["Testus oldus"] = "allowlisted on purpose"
            errors, _ = dq.validate_accepted_names()
        finally:
            dq.KNOWN_NOMENCLATURE.pop("Testus oldus", None)
            dq._load_json_list, dq._accepted_names = real_rows, real_acc
        self.assertEqual(len(errors), 1)
        self.assertIn("ALSO a row in this catalogue", errors[0])

    def test_an_unaccepted_name_is_an_error_unless_allowlisted(self):
        import src.data_quality as dq
        rows = [{"scientific_name": "Testus oldus", "common_name": "Old Test"}]
        real_rows, real_acc = dq._load_json_list, dq._accepted_names
        dq._load_json_list = lambda p: rows if "plants_master" in str(p) else []
        dq._accepted_names = lambda: {
            "Testus oldus": {"accepted_name": "Elsewherea nova Author"}}
        try:
            errors, _ = dq.validate_accepted_names()
            self.assertEqual(len(errors), 1)
            self.assertIn("does not accept", errors[0])
            dq.KNOWN_NOMENCLATURE["Testus oldus"] = "kept on purpose, for a test"
            allowed, _ = dq.validate_accepted_names()
        finally:
            dq.KNOWN_NOMENCLATURE.pop("Testus oldus", None)
            dq._load_json_list, dq._accepted_names = real_rows, real_acc
        self.assertEqual(allowed, [])

    def test_an_invalid_rank_cannot_be_allowlisted(self):
        """V2.80's four bad renames were not a disagreement about nomenclature,
        they were taxa the checklist does not carry. No reason excuses one."""
        import src.data_quality as dq
        rows = [{"scientific_name": "Testus oldus subsp. oldus",
                 "common_name": "Old Test"}]
        real_rows, real_acc = dq._load_json_list, dq._accepted_names
        dq._load_json_list = lambda p: rows if "plants_master" in str(p) else []
        dq._accepted_names = lambda: {
            "Testus oldus subsp. oldus": {"accepted_name": "Testus oldus Author"}}
        dq.KNOWN_NOMENCLATURE["Testus oldus subsp. oldus"] = "tried to excuse it"
        try:
            errors, _ = dq.validate_accepted_names()
        finally:
            dq.KNOWN_NOMENCLATURE.pop("Testus oldus subsp. oldus", None)
            dq._load_json_list, dq._accepted_names = real_rows, real_acc
        self.assertEqual(len(errors), 1)
        self.assertIn("rank the checklist does not carry", errors[0])

    def test_every_allowlist_entry_names_a_row_that_exists(self):
        """An entry that outlives the row it excused turns a temporary silence
        into a permanent one — the reason KNOWN_NATIVITY_CONFLICTS was emptied
        in V2.80 rather than left populated."""
        import json
        from src.data_quality import DATA_DIR, KNOWN_NOMENCLATURE
        here = {r.get("scientific_name") for r in json.loads(
            (DATA_DIR / "plants_master.json").read_text(encoding="utf-8"))}
        for name, reason in KNOWN_NOMENCLATURE.items():
            self.assertIn(name, here, f"{name} is allowlisted and not here")
            self.assertTrue(reason.strip(), f"{name} has no reason")


class TestCommonNameCollisions(unittest.TestCase):

    def test_no_two_rows_lead_with_the_same_common_name(self):
        from src.data_quality import validate_common_name_collisions
        errors, _ = validate_common_name_collisions()
        self.assertEqual(errors, [], "\n".join(errors))

    def test_a_trailing_alias_does_not_hide_a_collision(self):
        """The three real cases all looked distinct to an exact-match check:
        'False Dragonhead' vs 'False Dragonhead (Western Obedient Plant)'."""
        import src.data_quality as dq
        rows = [{"scientific_name": "Testus a", "common_name": "Test Flower"},
                {"scientific_name": "Testus b",
                 "common_name": "Test Flower (Other Name)"}]
        real = dq._load_json_list
        dq._load_json_list = lambda p: rows if "plants_master" in str(p) else []
        try:
            errors, _ = dq.validate_common_name_collisions()
        finally:
            dq._load_json_list = real
        self.assertEqual(len(errors), 1)
        self.assertIn("test flower", errors[0])


class TestBothGatesAreWiredIntoValidateAll(unittest.TestCase):
    """A validator nothing calls is a validator that does not run — the V2.42
    finding that `plant_fauna_master.json` had never been read by the gate."""

    def test_validate_all_calls_them(self):
        import src.data_quality as dq
        called = []
        real_acc, real_col = (dq.validate_accepted_names,
                              dq.validate_common_name_collisions)
        dq.validate_accepted_names = lambda: (called.append("accepted") or
                                              ([], []))
        dq.validate_common_name_collisions = lambda: (called.append("common") or
                                                      ([], []))
        try:
            dq.validate_all()
        finally:
            dq.validate_accepted_names = real_acc
            dq.validate_common_name_collisions = real_col
        self.assertEqual(sorted(called), ["accepted", "common"])


if __name__ == "__main__":
    unittest.main()

"""
tests/test_bench_provenance.py — a correction that would be undone is refused.

A user corrected `florets_per_head` from 24 to 1 in the morphology bench, saved,
and the change was accepted. It would have been deleted by the next run of
``scripts/seed_flower_morphology.py``, which overwrites any species whose
``flower_data_source`` still reads ``estimated`` — the rule that stops a genus
default from erasing the only real numbers in the catalogue.

Nothing said so. It surfaced weeks later, and only because
``test_the_seeder_is_idempotent`` noticed the shipped file no longer matched
what the seeder would produce — a failure that names neither the species nor
the reason.

A bench that accepts a change it knows to be temporary is the same fault as a
control that looks live and is not.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts import tune_morphology as bench                # noqa: E402


class TestProvenanceGap(unittest.TestCase):

    def test_a_number_changed_without_a_source_is_refused(self):
        rec = {"scientific_name": "Achillea millefolium",
               "flower_data_source": "estimated"}
        gap = bench._provenance_gap(rec, {"florets_per_head": 1}, {})
        self.assertIsNotNone(gap)
        self.assertIn("florets_per_head", gap)
        self.assertIn("flower_data_source", gap)
        self.assertIn("flower_data_citation", gap)

    def test_the_message_names_what_to_set_it_to(self):
        """A refusal that does not say how to proceed is just an obstacle."""
        rec = {"flower_data_source": "estimated"}
        gap = bench._provenance_gap(rec, {"petal_count": 5}, {})
        for value in ("photo", "flora", "measured"):
            self.assertIn(value, gap)
        self.assertNotIn("estimated and", gap)      # never offered as an answer

    def test_a_missing_source_counts_as_estimated(self):
        gap = bench._provenance_gap({}, {"petal_count": 5}, {})
        self.assertIsNotNone(gap)

    def test_setting_the_source_in_the_same_save_is_allowed(self):
        """The ordinary case: correct the number and name the source together."""
        rec = {"flower_data_source": "estimated"}
        gap = bench._provenance_gap(
            rec, {"petal_count": 5, "flower_data_source": "flora"},
            {"petal_count": 5, "flower_data_source": "flora",
             "flower_data_citation": "Budd's 442"})
        self.assertIsNone(gap)

    def test_a_species_someone_already_owns_is_freely_editable(self):
        rec = {"flower_data_source": "measured"}
        self.assertIsNone(bench._provenance_gap(rec, {"petal_count": 5}, {}))

    def test_editing_only_the_provenance_fields_is_allowed(self):
        rec = {"flower_data_source": "estimated"}
        self.assertIsNone(bench._provenance_gap(
            rec, {"flower_data_citation": "FNA vol. 21"}, {}))

    def test_the_two_groups_are_independent(self):
        """A leaf read out of a flora must not be blocked by the flower half
        still being an estimate, or vice versa."""
        rec = {"flower_data_source": "estimated", "leaf_data_source": "flora"}
        self.assertIsNone(bench._provenance_gap(rec, {"leaf_shape": "ovate"}, {}))
        self.assertIsNotNone(bench._provenance_gap(rec, {"petal_count": 5}, {}))

    def test_every_editable_value_field_is_covered_by_a_group(self):
        """A field in neither group could be corrected with no provenance at
        all — the gap this exists to close, reopened by an omission."""
        covered = set()
        for _src, _cite, fields in bench.PROVENANCE_GROUPS:
            covered.update(fields)
        provenance = {"flower_data_source", "flower_data_citation",
                      "leaf_data_source", "leaf_data_citation"}
        self.assertEqual(set(bench.FIELDS) - provenance, covered)

    def test_the_save_endpoint_actually_calls_it(self):
        """AST-only: the guard is useless if the handler does not consult it,
        and it must run BEFORE the write."""
        import ast
        import pathlib
        src = (pathlib.Path(__file__).resolve().parent.parent
               / "scripts" / "tune_morphology.py").read_text(encoding="utf-8")
        tree = ast.parse(src)
        gap_line = next((n.lineno for n in ast.walk(tree)
                         if isinstance(n, ast.Call)
                         and isinstance(n.func, ast.Name)
                         and n.func.id == "_provenance_gap"), None)
        self.assertIsNotNone(gap_line, "the save endpoint ignores the guard")
        save_lines = [n.lineno for n in ast.walk(tree)
                      if isinstance(n, ast.Call)
                      and isinstance(n.func, ast.Name) and n.func.id == "_save"]
        self.assertTrue(save_lines)
        self.assertLess(gap_line, max(save_lines))


if __name__ == "__main__":
    unittest.main()

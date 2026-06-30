"""
tests/test_field_notes.py — site-walk field notes (F6).

Covers src/field_notes.py:
  1. normalize: drops unknown prompt keys, coerces shapes, treats a note as
     implicitly checked, strips whitespace.
  2. get/set on a project's properties (round-trip, stamps updated, clears when
     empty).
  3. is_empty.
  4. format_field_notes content.

Pure — no Qt, no DB.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import field_notes as fn  # noqa: E402


class TestNormalize(unittest.TestCase):
    def test_empty_inputs(self):
        for bad in (None, {}, {"observations": None}, "nope", 5):
            n = fn.normalize(bad)
            self.assertEqual(n["observations"], {})
            self.assertEqual(n["free_text"], "")

    def test_drops_unknown_keys(self):
        n = fn.normalize({"observations": {
            "water_pools": {"checked": True, "note": "back corner"},
            "bogus_key": {"checked": True, "note": "x"},
        }})
        self.assertIn("water_pools", n["observations"])
        self.assertNotIn("bogus_key", n["observations"])

    def test_note_implies_checked(self):
        n = fn.normalize({"observations": {
            "wind": {"checked": False, "note": "funnels down the side yard"}}})
        self.assertTrue(n["observations"]["wind"]["checked"])

    def test_blank_unchecked_entry_dropped(self):
        n = fn.normalize({"observations": {
            "wind": {"checked": False, "note": "   "}}})
        self.assertEqual(n["observations"], {})

    def test_strips_whitespace(self):
        n = fn.normalize({"free_text": "  soggy NE corner  "})
        self.assertEqual(n["free_text"], "soggy NE corner")


class TestGetSet(unittest.TestCase):
    def test_round_trip_and_updated_stamp(self):
        project = {"properties": {}}
        stored = fn.set_field_notes(project, {
            "observations": {"snow_drifts": {"checked": True, "note": "north fence"}},
            "free_text": "magpies nest in the spruce",
        })
        self.assertIn("field_notes", project["properties"])
        self.assertTrue(stored["updated"])   # stamped
        got = fn.get_field_notes(project)
        self.assertEqual(got["observations"]["snow_drifts"]["note"], "north fence")
        self.assertEqual(got["free_text"], "magpies nest in the spruce")

    def test_set_empty_clears_block(self):
        project = {"properties": {"field_notes": {
            "observations": {"wind": {"checked": True, "note": "x"}}}}}
        out = fn.set_field_notes(project, {"observations": {}, "free_text": ""})
        self.assertEqual(out, {})
        self.assertNotIn("field_notes", project["properties"])

    def test_get_on_bare_project(self):
        self.assertTrue(fn.is_empty(fn.get_field_notes({})))
        self.assertTrue(fn.is_empty(fn.get_field_notes({"properties": {}})))


class TestIsEmpty(unittest.TestCase):
    def test_empty_and_nonempty(self):
        self.assertTrue(fn.is_empty(None))
        self.assertTrue(fn.is_empty({"observations": {}, "free_text": ""}))
        self.assertFalse(fn.is_empty({"free_text": "something"}))
        self.assertFalse(fn.is_empty(
            {"observations": {"wind": {"checked": True, "note": ""}}}))


class TestFormat(unittest.TestCase):
    def test_empty_returns_blank(self):
        self.assertEqual(fn.format_field_notes({}), "")

    def test_renders_prompts_and_free_text(self):
        text = fn.format_field_notes({
            "observations": {
                "water_pools": {"checked": True, "note": "back corner stays wet"},
                "volunteers": {"checked": True, "note": ""},
            },
            "free_text": "clay near the fence",
        })
        self.assertIn("SITE-WALK FIELD NOTES", text)
        self.assertIn("water pool", text.lower())
        self.assertIn("back corner stays wet", text)
        self.assertIn("Other observations:", text)
        self.assertIn("clay near the fence", text)

    def test_prompts_have_unique_stable_keys(self):
        keys = [k for k, _ in fn.FIELD_PROMPTS]
        self.assertEqual(len(keys), len(set(keys)))


if __name__ == "__main__":
    unittest.main()

"""
tests/test_pattern_language.py — F4 pattern-language framing for communities.

Covers src/pattern_language.py against the real seeded catalogue (temp DB):
  1. build_pattern returns the five sections + derived fact lists + related
  2. authored problem/solution are used when present
  3. description fallback for user-created communities with no authored text
  4. derived context facts (sun / zone / native) populate from member plants
  5. derived forces surface ecological signals (keystone / food-web / bloom)
  6. related patterns include a community's seeded variation
  7. pattern_card_html carries the five headings + a clickable community: anchor
"""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Redirect the DB to a temp dir before importing anything that opens it.
_TMP_DIR = tempfile.mkdtemp(prefix="permadesign_patlang_")
import src.db.plants as _plants_mod
_plants_mod._DATA_DIR = _TMP_DIR
_plants_mod._DB_PATH = os.path.join(_TMP_DIR, "permadesign_test.db")

from src.db.plants import init_db
from src.db import polycultures
from src import pattern_language


class PatternLanguageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()
        cls.all = polycultures.get_all_polycultures(top_level_only=False)
        cls.by_name = {c["name"]: c for c in cls.all}

    def _pattern(self, name):
        rec = polycultures.get_polyculture_by_id(self.by_name[name]["id"])
        return rec, pattern_language.build_pattern(rec, all_communities=self.all)

    def test_build_pattern_has_all_sections(self):
        _, pat = self._pattern("Apple Tree Community")
        for key in ("problem", "context", "forces", "solution",
                    "context_facts", "forces_facts", "related", "name"):
            self.assertIn(key, pat)
        self.assertIsInstance(pat["context_facts"], list)
        self.assertIsInstance(pat["forces_facts"], list)

    def test_authored_problem_and_solution_used(self):
        rec, pat = self._pattern("Apple Tree Community")
        # The seed authored real text — the pattern must surface it verbatim.
        self.assertTrue(rec.get("problem"))
        self.assertEqual(pat["problem"], rec["problem"].strip())
        self.assertEqual(pat["solution"], rec["solution"].strip())

    def test_description_fallback_for_unauthored_community(self):
        pid = polycultures.create_polyculture(
            "Pattern Fallback Mix",
            "A simple description. A second sentence follows.",
            None,
        )
        rec = polycultures.get_polyculture_by_id(pid)
        pat = pattern_language.build_pattern(rec, all_communities=self.all)
        # problem = first sentence; solution = full description.
        self.assertEqual(pat["problem"], "A simple description.")
        self.assertEqual(pat["solution"],
                         "A simple description. A second sentence follows.")

    def test_context_facts_derived_from_members(self):
        _, pat = self._pattern("Caterpillar Host Garden")
        facts = " · ".join(pat["context_facts"]).lower()
        self.assertTrue(any("zone" in f.lower() for f in pat["context_facts"]),
                        "expected a hardiness-zone fact")
        # The host garden is built from natives → a native-share fact appears.
        self.assertIn("native", facts)

    def test_forces_surface_ecological_signals(self):
        _, pat = self._pattern("Caterpillar Host Garden")
        joined = " | ".join(pat["forces_facts"]).lower()
        # Willows etc. are keystones; the food-web (F3) line and a bloom span
        # should also be derived.
        self.assertIn("keystone", joined)
        self.assertTrue("caterpillar" in joined or "bird" in joined,
                        "expected a food-web force line")
        self.assertIn("nectar", joined)

    def test_related_includes_variation(self):
        _, pat = self._pattern("Apple Tree Community")
        relations = {(r["name"], r["relation"]) for r in pat["related"]}
        self.assertIn(("Shade-Tolerant", "Variation"), relations)

    def test_variation_links_back_to_base(self):
        _, pat = self._pattern("Shade-Tolerant")
        rels = {r["relation"] for r in pat["related"]}
        self.assertIn("Base pattern", rels)

    def test_card_html_has_headings_and_anchor(self):
        _, pat = self._pattern("Apple Tree Community")
        html = pattern_language.pattern_card_html(pat)
        for heading in ("Problem", "Context", "Forces", "Solution",
                        "Related patterns"):
            self.assertIn(heading, html)
        self.assertIn("community:", html)

    def test_card_html_escapes_dynamic_text(self):
        # A name with an ampersand must not corrupt the HTML.
        pat = {"name": "A & B", "problem": "x", "context": "", "forces": "",
               "solution": "y", "context_facts": [], "forces_facts": [],
               "related": [], "center": "", "n_members": 0}
        html = pattern_language.pattern_card_html(pat)
        self.assertIn("A &amp; B", html)


if __name__ == "__main__":
    unittest.main()

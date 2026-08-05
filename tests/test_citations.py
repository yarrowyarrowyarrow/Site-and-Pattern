"""
tests/test_citations.py

The bibliography and its renderer (V2.42).

`src/citations.py` exists because the app's ecological data was always cited and
the citations were never displayed — `plant_fauna.source` reached the view model
and was dropped by every widget. These tests pin the two properties that make
showing them worth doing: a placeholder is never rendered as if it were a real
reference, and an unverified bibliographic record is never dressed up as a
checked one.
"""

import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import citations as C  # noqa: E402

_DATA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                     "data", "sources_master.json")


class TestRegistry(unittest.TestCase):

    def test_registry_loads(self):
        self.assertTrue(C.all_sources(), "no sources loaded")

    def test_every_source_used_by_the_data_resolves(self):
        """The gate enforces this at build time; this catches a renderer that
        cannot resolve what the gate accepted."""
        with open(os.path.join(os.path.dirname(_DATA),
                               "plant_fauna_master.json"), encoding="utf-8") as f:
            records = json.load(f)
        unresolved = set()
        for rec in records:
            if not isinstance(rec, dict) or "plant" not in rec:
                continue
            for key in (k.strip() for k in (rec.get("source") or "").split(",")):
                if key and C.resolve(key) is None:
                    unresolved.add(key)
        self.assertEqual(unresolved, set())

    def test_keys_are_stable_identifiers_not_prose(self):
        for rec in C.all_sources():
            key = rec["key"]
            self.assertNotIn(" ", key, f"{key!r} looks like prose, not a key")
            self.assertEqual(key, key.lower())


class TestFormatting(unittest.TestCase):

    def test_full_citation_has_author_year_and_title(self):
        text = C.format_citation("wilson_carril_2015_bees")
        self.assertIn("Wilson", text)
        self.assertIn("2015", text)
        self.assertIn("The Bees in Your Backyard", text)

    def test_short_form_is_author_year(self):
        self.assertEqual(
            C.format_citation("acorn_sheldon_butterflies_ab", short=True),
            "Acorn & Sheldon 2006")

    def test_three_or_more_authors_collapse_to_et_al(self):
        self.assertEqual(
            C.format_citation("pohl_et_al_2018_checklist", short=True),
            "Pohl et al. 2018")

    def test_legacy_alias_still_resolves(self):
        """Data normalised to keys in V2.42, but a stale string must not render
        as a dead end."""
        self.assertEqual(
            C.format_citation("Acorn & Sheldon 2006", short=True),
            "Acorn & Sheldon 2006")

    def test_unknown_key_returns_itself_rather_than_nothing(self):
        self.assertEqual(C.format_citation("no_such_work"), "no_such_work")

    def test_empty_source_renders_empty(self):
        self.assertEqual(C.format_citation(""), "")
        self.assertEqual(C.format_sources(""), "")

    def test_composite_source_renders_every_work(self):
        text = C.format_sources(
            "anbc_alberta_native_bees,sheffield_et_al_2014_grasslands,"
            "wilson_carril_2015_bees", short=True)
        self.assertIn("Sheffield", text)
        self.assertIn("Wilson", text)
        self.assertIn("Alberta Native Bee Council", text)

    def test_no_author_year_run_together_artefacts(self):
        """Regression: the surname splitter emitted 'Acorn & and Sheldon'."""
        for rec in C.all_sources():
            short = C.format_citation(rec["key"], short=True)
            self.assertNotIn(" and ", short, f"{rec['key']}: {short!r}")
            self.assertNotIn("&  ", short)


class TestHonestyRules(unittest.TestCase):

    def test_placeholder_is_detected(self):
        self.assertTrue(C.is_placeholder("unattributed_prairie_pollination"))
        self.assertFalse(C.is_placeholder("wilson_carril_2015_bees"))

    def test_placeholder_never_renders_as_a_citation(self):
        """The whole reason it exists: 16 edges were seeded with a source
        string naming no work, and attaching them to a nearby real citation
        would assert a coverage nobody claimed."""
        text = C.format_citation("unattributed_prairie_pollination")
        self.assertIn("unattributed", text.lower())
        for name in ("Acorn", "Sheldon", "Pohl", "Wilson"):
            self.assertNotIn(name, text)

    def test_placeholder_is_excluded_from_author_lists(self):
        rec = C.resolve("unattributed_prairie_pollination")
        self.assertEqual((rec.get("authors") or "").strip(), "")

    def test_disclaimer_says_both_things(self):
        """It must disclaim the bibliographic details AND the claim support —
        they are separate limitations and dropping either overstates."""
        d = C.disclaimer().lower()
        self.assertIn("not been checked", d)
        self.assertTrue("verified" in d or "confirmed" in d)

    def test_record_confidence_vocabulary(self):
        for rec in C.all_sources():
            self.assertIn(rec.get("record_confidence"),
                          ("verified", "unverified"), rec["key"])

    def test_no_fabricated_isbns(self):
        """Nothing in this registry may carry an identifier nobody checked."""
        for rec in C.all_sources():
            if rec.get("record_confidence") == "unverified":
                self.assertNotIn("isbn", {k.lower() for k in rec},
                                 f"{rec['key']} claims an ISBN it has not "
                                 "verified")


if __name__ == "__main__":
    unittest.main()

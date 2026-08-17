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
import re
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


class TestTheTitleIsNotPrintedTwice(unittest.TestCase):
    """V2.65. 17 of the 114 records were parsed out of a GloBI study title, so
    `authors` is a *prefix of* `title` rather than a separate field. Printing
    both gave "Robertson, C (1929). Robertson, C. 1929. Flowers and insects…".

    Harmless while the bibliography was unpublished; the first thing a reader
    sees now that it is on the website's About page.
    """

    def test_the_classic_author_year_title_shape_prints_once(self):
        self.assertTrue(C._title_restates(
            "Robertson, C", "Robertson, C. 1929. Flowers and insects.", 1929))

    def test_a_short_author_is_caught_when_the_year_follows(self):
        """`Small, E` is six letters — under the length rule on its own. The
        year immediately after it is what makes the restatement certain."""
        self.assertTrue(C._title_restates(
            "Small, E", "Small, E. 1976. Insect pollinators of Mer Bleue.", 1976))

    def test_a_short_author_alone_is_not_enough(self):
        """"Li" opening "Lichens of Alberta" is a coincidence, not a
        restatement, and dropping the year over it would lose real data."""
        self.assertFalse(C._title_restates("Li", "Lichens of Alberta", None))

    def test_a_separate_author_and_title_are_both_kept(self):
        self.assertFalse(C._title_restates(
            "Acorn, J. and Sheldon, I.", "Butterflies of Alberta", 2006))
        out = C.format_citation("acorn_sheldon_butterflies_ab")
        self.assertIn("Acorn, J. and Sheldon, I. (2006)", out)
        self.assertIn("Butterflies of Alberta", out)

    def test_no_shipped_record_prints_its_author_twice(self):
        """Over the real bibliography, which is the only test that would have
        caught this. One exception: an institutional author who is also the
        publisher ("Cornell Lab of Ornithology") is correct citation practice,
        not the parsing bug."""
        doubled = []
        for rec in C.all_sources():
            authors = (rec.get("authors") or "").strip()
            if len(authors) < 10 or authors == (rec.get("publisher") or "").strip():
                continue
            if C.format_citation(rec["key"]).count(authors[:18]) > 1:
                doubled.append(rec["key"])
        self.assertEqual(doubled, [])


class TestNoDatabaseNamespaceReachesAnAuthor(unittest.TestCase):
    """V2.65. GloBI namespaces some study titles by the collection they came
    from — `bascompte:Robertson, C. 1929. …` is the Bascompte web-of-life
    database. Left on, the prefix became the author's surname in five records
    and was published as one."""

    def test_no_author_field_carries_a_namespace(self):
        offenders = [r["key"] for r in C.all_sources()
                     if ":" in (r.get("authors") or "")[:20]]
        self.assertEqual(offenders, [], f"namespace in an author: {offenders}")

    def test_no_title_field_carries_a_namespace(self):
        offenders = [r["key"] for r in C.all_sources()
                     if re.match(r"^[a-z][a-z0-9_-]{2,}:(?!//)", r.get("title") or "")]
        self.assertEqual(offenders, [], f"namespace in a title: {offenders}")

    def test_the_keys_were_left_alone(self):
        """The repair fixed display fields only. Keys are slugged from the
        ORIGINAL title and every edge in the seed points at them, so rewriting
        one would orphan its edges — the reason this looks half-done."""
        self.assertTrue(any("bascompte" in r["key"] for r in C.all_sources()))

    def test_every_repaired_record_still_resolves(self):
        for rec in C.all_sources():
            self.assertIsNotNone(C.resolve(rec["key"]), rec["key"])


if __name__ == "__main__":
    unittest.main()

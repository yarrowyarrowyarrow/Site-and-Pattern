"""
The VASCAN nativity machinery (F137, V2.75).

An outside botanical review said many species listed as native to "AB, SK" are
native to only one, and that a number of names are out of date. Both are true.
`native_provinces` is generated from a hand-authored boolean plus the plant's
ecoregion tags, no plant record carries a citation of any kind, and the
catalogue has no taxonomic backbone -- a scientific name is a free string
checked by one regex.

**What these tests deliberately do NOT do is assert VASCAN's response shape.**
V2.59 lost an afternoon to a fetch that guessed a field name while its test
fixture encoded the same guess, so the suite stayed green and the code was
wrong 55 times. The parser here accepts several spellings per field, the
`--probe` mode reports which ones the live API actually returns, and these
tests pin the *judgement* -- what happens once a shape has been parsed -- which
is the part that can be reasoned about offline.
"""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import scripts.fetch_flora_nativity as F                       # noqa: E402
import scripts.ingest_flora_nativity as I                      # noqa: E402


def _match(**over):
    m = {"scientificName": "Testus plantus L.",
         "taxonomicStatus": "accepted",
         "distribution": [{"locationID": "CA-AB", "establishmentMeans": "native"},
                          {"locationID": "CA-SK", "establishmentMeans": "native"}]}
    m.update(over)
    return {"results": [{"searchedTerm": "Testus plantus", "matches": [m]}]}


class _Throttle:
    limited = 0
    sleep = 0.0

    def wait(self):
        pass


def _get(payload):
    def get_json(url, timeout, throttle):
        return payload
    return get_json


class TestParsingIsForgivingAboutSpelling(unittest.TestCase):
    """Because the shape is a guess until --probe says otherwise.

    Not tolerance for its own sake: a parser that reads one wrong key returns
    "no distribution" for every species, which looks exactly like a species
    with no record and is therefore invisible.
    """

    def _lookup(self, payload):
        return F.lookup("Testus plantus", throttle=_Throttle(),
                        get_json=_get(payload))

    def test_the_documented_spelling(self):
        got = self._lookup(_match())
        self.assertEqual(got["provinces"], {"AB": "native", "SK": "native"})

    def test_distributions_plural(self):
        payload = _match()
        m = payload["results"][0]["matches"][0]
        m["distributions"] = m.pop("distribution")
        self.assertEqual(self._lookup(payload)["provinces"],
                         {"AB": "native", "SK": "native"})

    def test_occurrence_status_instead_of_establishment_means(self):
        payload = _match(distribution=[
            {"locationID": "CA-AB", "occurrenceStatus": "introduced"}])
        self.assertEqual(self._lookup(payload)["provinces"],
                         {"AB": "introduced"})

    def test_a_bare_province_code(self):
        payload = _match(distribution=[
            {"locality": "SK", "establishmentMeans": "native"}])
        self.assertEqual(self._lookup(payload)["provinces"], {"SK": "native"})

    def test_provinces_we_do_not_ask_about_are_dropped(self):
        payload = _match(distribution=[
            {"locationID": "CA-ON", "establishmentMeans": "native"},
            {"locationID": "CA-AB", "establishmentMeans": "native"}])
        self.assertEqual(self._lookup(payload)["provinces"], {"AB": "native"})

    def test_no_match_is_not_an_error(self):
        got = self._lookup({"results": [{"searchedTerm": "x", "matches": []}]})
        self.assertFalse(got["matched"])
        self.assertEqual(got["provinces"], {})


class TestAbsentIsNotEstimated(unittest.TestCase):
    """A province listed with no establishment word says nothing about origin.

    src/confidence.py's central rule, and the one that put a red flower on the
    blue columbine when it was broken. VASCAN being silent about origin is the
    absence of a claim, never a claim of nativeness.
    """

    def test_a_blank_establishment_means_is_unstated_not_native(self):
        got = F.assess({"matched": True,
                        "provinces": {"AB": "", "SK": ""}})
        self.assertEqual(got["origin"], "unstated")
        self.assertEqual(got["native_provinces"], "")
        self.assertEqual(got["verdict"], "review")

    def test_unstated_never_becomes_a_verdict(self):
        got = F.assess({"matched": True, "provinces": {"AB": ""}})
        self.assertNotIn(got["verdict"], ("confirm", "not_here"))


class TestTheFourAnswers(unittest.TestCase):
    def test_native_here(self):
        got = F.assess({"matched": True,
                        "provinces": {"AB": "native", "SK": "native"}})
        self.assertEqual((got["origin"], got["verdict"], got["native_provinces"]),
                         ("native", "confirm", "AB,SK"))

    def test_native_in_only_one_province(self):
        """The review's actual complaint, as a returnable answer."""
        got = F.assess({"matched": True,
                        "provinces": {"AB": "native", "SK": "introduced"}})
        self.assertEqual(got["native_provinces"], "AB")

    def test_introduced_here_is_refused_however_it_is_worded(self):
        for word in ("introduced", "introduced: adventive", "ephemeral",
                     "excluded", "extirpated"):
            got = F.assess({"matched": True, "provinces": {"AB": word}})
            self.assertEqual(got["verdict"], "not_here", word)

    def test_recorded_from_neither_province(self):
        """The Helianthus giganteus shape: eastern species, no AB/SK row."""
        got = F.assess({"matched": True, "provinces": {}})
        self.assertEqual((got["origin"], got["verdict"]), ("absent", "not_here"))

    def test_an_unmatched_name_is_reviewed_not_condemned(self):
        got = F.assess({"matched": False})
        self.assertEqual(got["verdict"], "review")
        self.assertIn("superseded", got["why"])


class TestAFailureIsNotAnAbsence(unittest.TestCase):
    """The distinction an earlier run got wrong, at a cost of 208 species
    recorded as growing nowhere."""

    def test_a_refused_species_is_kept_out_of_the_results(self):
        import scripts.seed_ecoregion_ranges as seeder

        def refuse(url, timeout, throttle):
            raise seeder.FetchFailed("HTTP 429")

        got = F.fetch_all(["Testus plantus"], verbose=False,
                          throttle=_Throttle(), get_json=refuse)
        self.assertEqual(got["results"], {})
        self.assertEqual(len(got["failed"]), 1)

    def test_the_written_file_names_them(self):
        tmp = Path(tempfile.mkdtemp()) / "flora_nativity.json"
        blob = F.write({}, [("Testus plantus", "HTTP 429")], path=tmp)
        self.assertEqual(blob["failed"][0]["name"], "Testus plantus")
        self.assertIn("VASCAN", blob["source"])


class TestTheIngestProposesAndDoesNotApply(unittest.TestCase):
    """V2.59, V2.60 and V2.64 each caught a wrong apply because a human read a
    report first. The separation is the lesson, not the caution."""

    def _buckets(self, said, claimed="AB,SK"):
        fetched = {"results": {"Testus plantus": said}}
        rows = {"Testus plantus": {"scientific_name": "Testus plantus",
                                   "common_name": "Test Plant",
                                   "native_provinces": claimed}}
        return I.compare(fetched, rows)

    def test_a_narrowed_province_is_proposed_with_what_it_removes(self):
        b = self._buckets({"verdict": "confirm", "origin": "native",
                           "native_provinces": "AB"})
        self.assertEqual(len(b["narrow"]), 1)
        self.assertEqual(b["narrow"][0]["removes"], "SK")

    def test_agreement_is_a_confirm(self):
        b = self._buckets({"verdict": "confirm", "origin": "native",
                           "native_provinces": "AB,SK"})
        self.assertEqual(len(b["confirm"]), 1)
        self.assertEqual(b["narrow"], [])

    def test_a_synonym_goes_to_the_name_bucket_and_nowhere_else(self):
        b = self._buckets({"verdict": "confirm", "origin": "native",
                           "native_provinces": "AB,SK", "is_synonym": True,
                           "accepted_name": "Realus plantus"})
        self.assertEqual(len(b["name"]), 1)
        self.assertEqual(b["confirm"], [])
        self.assertEqual(b["name"][0]["accepted_name"], "Realus plantus")

    def test_not_here_is_reported_not_removed(self):
        b = self._buckets({"verdict": "not_here", "origin": "introduced",
                           "native_provinces": "", "why": "introduced in AB"})
        self.assertEqual(len(b["not_here"]), 1)
        # The catalogue on disk is untouched: compare() takes rows as an
        # argument and returns proposals. There is no write path at all.
        self.assertFalse(hasattr(I, "apply"))

    def test_a_species_vascan_was_not_asked_about_is_skipped(self):
        b = I.compare({"results": {}},
                      {"Testus plantus": {"scientific_name": "Testus plantus",
                                          "native_provinces": "AB,SK"}})
        self.assertEqual(sum(len(v) for v in b.values()), 0)

    def test_a_missing_fetch_file_refuses_rather_than_reporting_nothing(self):
        self.assertEqual(I.load_fetched(Path("/nonexistent/x.json")), {})
        self.assertEqual(I.main([]), 1)


class TestTheGeneratorItReplaces(unittest.TestCase):
    def test_it_is_superseded_and_says_so(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "tpp", Path(__file__).resolve().parent.parent
            / "scripts" / "tag_prairie_provenance.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        self.assertEqual(mod.SUPERSEDED_IN, "V2.75")
        self.assertIn("fetch_flora_nativity", mod.__doc__)


if __name__ == "__main__":
    unittest.main()

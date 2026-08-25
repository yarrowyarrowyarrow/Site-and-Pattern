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
        """Point the module at a path that does not exist rather than relying
        on the repo not having the file. It passed for two releases only
        because nobody had run the fetch yet, so it was asserting a fact about
        the working tree instead of about the guard (found V2.79, when the
        real `flora_nativity.json` landed and it started failing)."""
        self.assertEqual(I.load_fetched(Path("/nonexistent/x.json")), {})
        was = I.FETCHED
        I.FETCHED = Path(tempfile.mkdtemp()) / "absent.json"
        try:
            self.assertEqual(I.main([]), 1)
        finally:
            I.FETCHED = was


class TestAMissingFieldIsNotAnAbsence(unittest.TestCase):
    """VASCAN publishes distribution on the LOWEST accepted taxon (F148, V2.79).

    The real responses, probed rather than imagined:

        Amelanchier alnifolia               species     no distribution block
        Amelanchier alnifolia var. alnifolia variety    AB, SK, MB native
        Alnus incana                        species     no distribution block
        Alnus incana subsp. tenuifolia      subspecies  AB, SK native

    `assess()` let a **missing** block fall through to `origin: absent,
    verdict: not_here`, with a `why` reading *"VASCAN records no Alberta or
    Saskatchewan distribution."* That sentence is false, and it put **173 of
    434 species** -- Saskatoon Berry among them, the defining parkland shrub --
    outside the province they are native to.

    Third instance in this repo of *a failure is not an absence*: the V2.75
    rate limit logged 208 throttled species as growing nowhere, and the V2.78
    harvest cap made a truncated fetch indistinguishable from a complete one.
    """

    #: The real Amelanchier alnifolia shape.
    NO_BLOCK = {"matched": True, "accepted_name": "Amelanchier alnifolia",
                "taxon_rank": "species", "has_distribution": False,
                "provinces": {}}

    def test_a_matched_taxon_with_no_distribution_is_never_not_here(self):
        self.assertNotEqual(F.assess(self.NO_BLOCK)["verdict"], "not_here")
        self.assertEqual(F.assess(self.NO_BLOCK)["verdict"], "review")

    def test_it_does_not_claim_vascan_recorded_an_absence(self):
        why = F.assess(self.NO_BLOCK)["why"]
        self.assertIn("NOT a statement that the plant is absent", why)
        self.assertNotIn("records no Alberta or Saskatchewan", why)

    def test_it_names_the_rank_so_the_cause_is_readable(self):
        self.assertIn("rank species", F.assess(self.NO_BLOCK)["why"])

    def test_it_claims_no_provinces_either(self):
        """Unknown is not a licence to keep the existing claim: the verdict is
        `review`, and `native_provinces` stays empty."""
        self.assertEqual(F.assess(self.NO_BLOCK)["native_provinces"], "")
        self.assertEqual(F.assess(self.NO_BLOCK)["origin"], "undetermined")

    def test_a_block_naming_neither_province_still_says_no(self):
        """The fix must not delete the ability to report a real absence -- that
        would trade one silent failure for another."""
        row = {"matched": True, "taxon_rank": "species",
               "has_distribution": True, "provinces": {"MB": "native"}}
        self.assertEqual(F.assess(row)["verdict"], "not_here")
        self.assertEqual(F.assess(row)["origin"], "absent")

    def test_the_infraspecific_taxon_reports_native(self):
        """The var. alnifolia response, which is where the answer lives."""
        row = {"matched": True, "taxon_rank": "variety",
               "has_distribution": True,
               "provinces": {"AB": "native", "SK": "native", "MB": "native"}}
        self.assertEqual(F.assess(row)["verdict"], "confirm")
        self.assertEqual(F.assess(row)["native_provinces"], "AB,SK")

    def test_lookup_records_whether_a_block_was_present(self):
        """`provinces == {}` cannot distinguish "no block" from "a block naming
        no province we asked about". Those want different verdicts."""
        def fake(url, timeout, throttle):
            return {"results": [{"matches": [{
                "scientificName": "Testus plantus", "taxonRank": "species",
                "vernacularNames": []}]}]}
        got = F.lookup("Testus plantus", get_json=fake, throttle=_NoWait())
        self.assertFalse(got["has_distribution"])
        self.assertEqual(got["taxon_rank"], "species")

    def test_lookup_records_a_present_block(self):
        def fake(url, timeout, throttle):
            return {"results": [{"matches": [{
                "scientificName": "Testus plantus", "taxonRank": "variety",
                "distribution": [{"locationID": "ISO 3166-2:CA-AB",
                                  "locality": "AB",
                                  "establishmentMeans": "native"}]}]}]}
        got = F.lookup("Testus plantus", get_json=fake, throttle=_NoWait())
        self.assertTrue(got["has_distribution"])
        self.assertEqual(got["provinces"], {"AB": "native"})

    def test_the_ingest_keeps_it_out_of_not_here(self):
        fetched = {"results": {"Amelanchier alnifolia": dict(
            self.NO_BLOCK, **F.assess(self.NO_BLOCK))}}
        rows = {"Amelanchier alnifolia": {"native_provinces": "AB,SK",
                                          "common_name": "Saskatoon Berry"}}
        buckets = I.compare(fetched, rows)
        self.assertEqual(len(buckets["not_here"]), 0)
        self.assertEqual(len(buckets["undetermined"]), 1)


class _NoWait:
    sleep = 0.0
    limited = 0

    def wait(self):
        pass

    def rate_limited(self):
        pass


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



class TestTheApplyWritesOnlyWhatVascanEarns(unittest.TestCase):
    """V2.80. `--apply` is the first thing in this pipeline that writes to the
    seed files, and three earlier applies in this repo went wrong on their
    first run (23 Monarch caterpillars on goldenrod, 62 good bird edges
    binned, 20 animals connected to nothing). What is pinned here is mostly
    what it must NOT touch."""

    def setUp(self):
        import scripts.ingest_flora_nativity as I
        self.I = I
        self.buckets = {
            "narrow": [{"scientific_name": "Yucca glauca", "vascan": "AB"},
                       {"scientific_name": "Echinacea angustifolia",
                        "vascan": "SK"}],
            "confirm": [{"scientific_name": "Amelanchier alnifolia"}],
            "not_here": [{"scientific_name": "Helianthus annuus"}],
            "name": [{"scientific_name": "Andropogon gerardii"}],
            "undetermined": [{"scientific_name": "Urtica dioica"}],
        }
        self.tmp = Path(tempfile.mkdtemp())
        (self.tmp / "data").mkdir()
        self.rows = [
            {"scientific_name": "Yucca glauca", "native_provinces": "AB,SK",
             "native_to_alberta": 1},
            {"scientific_name": "Echinacea angustifolia",
             "native_provinces": "AB,SK", "native_to_alberta": 1},
            {"scientific_name": "Amelanchier alnifolia",
             "native_provinces": "AB,SK", "native_to_alberta": 1},
            {"scientific_name": "Helianthus annuus",
             "native_provinces": "AB,SK", "native_to_alberta": 1},
            {"scientific_name": "Andropogon gerardii",
             "native_provinces": "AB,SK", "native_to_alberta": 1},
            {"scientific_name": "Urtica dioica", "native_provinces": "AB,SK",
             "native_to_alberta": 1},
        ]
        (self.tmp / "data" / "plants_master.json").write_text(
            json.dumps(self.rows), encoding="utf-8")
        self._root = I.PROJECT_ROOT
        self._files = I.PLANT_FILES
        I.PROJECT_ROOT = self.tmp
        I.PLANT_FILES = ("plants_master.json",)

    def tearDown(self):
        self.I.PROJECT_ROOT = self._root
        self.I.PLANT_FILES = self._files

    def _run(self):
        out = self.I._apply(self.buckets)
        rows = json.loads(
            (self.tmp / "data" / "plants_master.json").read_text(
                encoding="utf-8"))
        return out, {r["scientific_name"]: r for r in rows}

    def test_a_narrowed_species_loses_the_province_vascan_has_no_row_for(self):
        _, by = self._run()
        self.assertEqual(by["Yucca glauca"]["native_provinces"], "AB")
        self.assertEqual(by["Echinacea angustifolia"]["native_provinces"],
                         "SK")

    def test_losing_alberta_also_clears_the_alberta_flag(self):
        """`native_to_alberta` is a separate column and the app's actual native
        filter and habitat-score input. Narrowing the string and leaving the
        flag set puts two fields in one row in contradiction, and the score
        reads the one that would still be wrong."""
        _, by = self._run()
        self.assertEqual(by["Echinacea angustifolia"]["native_to_alberta"], 0)
        self.assertEqual(by["Yucca glauca"]["native_to_alberta"], 1)

    def test_an_uncertain_alberta_flag_is_read_not_crashed_on(self):
        """Some rows carry "1?" -- native to Alberta, editorially uncertain --
        and `db/plants.py` has always read it as truthy. A plain int() raises
        on it, in an apply that walks every row in the catalogue."""
        self.assertTrue(self.I._ab_flag({"native_to_alberta": "1?"}))
        self.assertTrue(self.I._ab_flag({"native_to_alberta": 1}))
        self.assertFalse(self.I._ab_flag({"native_to_alberta": 0}))
        self.assertFalse(self.I._ab_flag({}))

    def test_an_uncertain_flag_vascan_agrees_with_is_left_alone(self):
        """The question mark is an editorial hedge about Alberta that
        `src/nativity.py` reads as one. Replacing it with a clean 1 because a
        flora happens to agree would destroy something somebody meant."""
        self.rows[0]["native_to_alberta"] = "1?"      # Yucca, narrowed to AB
        (self.tmp / "data" / "plants_master.json").write_text(
            json.dumps(self.rows), encoding="utf-8")
        out, by = self._run()
        self.assertEqual(by["Yucca glauca"]["native_to_alberta"], "1?")
        # Only Yucca. Echinacea legitimately loses Alberta in this fixture.
        self.assertNotIn("Yucca glauca", [n for n, _ in out["ab_flag"]])

    def test_a_confirmed_species_is_sourced_but_not_rewritten(self):
        _, by = self._run()
        row = by["Amelanchier alnifolia"]
        self.assertEqual(row["native_provinces"], "AB,SK")
        self.assertEqual(row[self.I.SOURCE_KEY], "flora")

    def test_the_three_unresolved_buckets_are_left_completely_alone(self):
        """A removal, a rename, and a lineage the reader could not follow.
        Stamping any of them would publish "read from a published flora" over
        an answer no flora gave."""
        _, by = self._run()
        for name in ("Helianthus annuus", "Andropogon gerardii",
                     "Urtica dioica"):
            self.assertEqual(by[name]["native_provinces"], "AB,SK", name)
            self.assertNotIn(self.I.SOURCE_KEY, by[name], name)

    def test_the_source_key_is_the_one_nativity_actually_reads(self):
        """Spelling it a second time here would make the write a silent no-op:
        it would succeed, and every page would go on saying "inferred"."""
        from src.nativity import SOURCE_FIELD
        self.assertEqual(self.I.SOURCE_KEY, SOURCE_FIELD)

    def test_running_it_twice_changes_nothing_the_second_time(self):
        self._run()
        again, _ = self._run()
        self.assertEqual(again["narrowed"], [])
        self.assertEqual(again["sourced"], 0)
        self.assertEqual(again["ab_flag"], [])


if __name__ == "__main__":
    unittest.main()

"""
Reading VASCAN's checklist instead of asking it 434 questions (F149, V2.79).

The API attaches distribution to the lowest accepted taxon and cannot
enumerate a taxon's children -- three probes established both:

    Amelanchier alnifolia                   matched, no distribution
    Amelanchier alnifolia var. alnifolia    AB, SK, MB native
    Amelanchier alnifolia var               numMatches: 0

The fixtures below are built from those real responses, including the one that
matters most: *Alnus incana*'s Alberta taxon is `subsp. tenuifolia`, NOT the
autonym `subsp. incana`. Any shortcut that guesses the autonym resolves
Amelanchier and silently misses Alnus, and a rule that answers some species and
skips others produces a result that looks complete and is not.
"""

import os
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts import vascan_archive as A                # noqa: E402

TAXON = "\t".join(["taxonID", "parentNameUsageID", "acceptedNameUsageID",
                   "scientificName", "taxonRank", "taxonomicStatus"])
#: **The real VASCAN v37.17 distribution header**, not a convenient one.
#: `distribution.txt` is a Darwin Core *extension*: it does not repeat
#: `taxonID`, it references the core row through the column `meta.xml` declares
#: as `<coreid>`, which here is `id`. The first version of these tests wrote
#: `taxonID` in both files, so the reader shipped unable to open the archive it
#: exists to read and refused it outright on the author's machine:
#:     the distribution file has no taxonID column; header was
#:     ['id', 'locationID', 'locality', 'countryCode', ...]
#: The two trailing columns are real too, and are here so a row's fields are
#: not silently read one position off.
DIST = "\t".join(["id", "locationID", "locality", "countryCode",
                  "occurrenceStatus", "establishmentMeans", "source",
                  "occurrenceRemarks"])

#: Test rows stay written as `(id, locationID, locality, occurrenceStatus,
#: establishmentMeans)` because those are the five fields the reader uses; the
#: rest of the real header is filled in around them.
def _dist_row(row) -> list:
    tid, loc_id, locality, status, means = row
    return [tid, loc_id, locality, "CA", status, means, "", ""]


def _archive(taxon_rows, dist_rows, *, as_dir=False):
    """A minimal Darwin Core Archive, as a zip or an unpacked directory."""
    tmp = Path(tempfile.mkdtemp())
    taxon = "\n".join([TAXON] + ["\t".join(r) for r in taxon_rows])
    dist = "\n".join([DIST] + ["\t".join(_dist_row(r)) for r in dist_rows])
    if as_dir:
        (tmp / "taxon.txt").write_text(taxon, encoding="utf-8")
        (tmp / "distribution.txt").write_text(dist, encoding="utf-8")
        return tmp
    path = tmp / "vascan.zip"
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("taxon.txt", taxon)
        zf.writestr("distribution.txt", dist)
    return path


#: The two real cases, plus a synonym and an introduced sibling.
TAXA = [
    # Amelanchier: species with no distribution of its own, autonym has it.
    ["8617", "809", "", "Amelanchier alnifolia (Nuttall) Nuttall ex M. Roemer",
     "species", "accepted"],
    ["8616", "8617", "", "Amelanchier alnifolia (Nuttall) var. alnifolia",
     "variety", "accepted"],
    # Alnus: the Alberta taxon is NOT the autonym.
    ["3676", "800", "", "Alnus incana (Linnaeus) Moench", "species",
     "accepted"],
    ["3677", "3676", "", "Alnus incana subsp. tenuifolia (Nuttall) Breitung",
     "subspecies", "accepted"],
    ["3678", "3676", "", "Alnus incana subsp. incana", "subspecies",
     "accepted"],
    # A species whose distribution sits on its own record.
    ["2432", "774", "", "Acorus americanus (Rafinesque) Rafinesque", "species",
     "accepted"],
    # A synonym pointing at Acorus.
    ["9999", "774", "2432", "Acorus calamus var. americanus", "variety",
     "synonym"],
]

DISTS = [
    ["8616", "ISO 3166-2:CA-AB", "AB", "", "native"],
    ["8616", "ISO 3166-2:CA-SK", "SK", "", "native"],
    ["3677", "ISO 3166-2:CA-AB", "AB", "", "native"],
    ["3677", "ISO 3166-2:CA-SK", "SK", "", "native"],
    ["3678", "ISO 3166-2:CA-AB", "AB", "excluded", ""],
    ["2432", "ISO 3166-2:CA-AB", "AB", "", "native"],
    ["9999", "ISO 3166-2:CA-MB", "MB", "", "introduced"],
]

PROV = ("AB", "SK", "MB")


class TestTheRollUp(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        src = _archive(TAXA, DISTS)
        cls.taxa = A.read_taxa(src)
        cls.dist = A.read_distribution(src, PROV)

    def look(self, name):
        return A.lookup(self.taxa, self.dist, name, PROV)

    def test_a_species_inherits_from_its_accepted_variety(self):
        """The Amelanchier case: no distribution of its own, the autonym has
        it, and the species is what the catalogue asked about."""
        got = self.look("Amelanchier alnifolia")
        self.assertTrue(got["matched"])
        self.assertTrue(got["has_distribution"])
        self.assertEqual(got["provinces"], {"AB": "native", "SK": "native"})

    def test_it_finds_a_taxon_that_is_not_the_autonym(self):
        """The Alnus case, and the whole reason the autonym shortcut was
        rejected: Alberta's alder is subsp. tenuifolia, not subsp. incana."""
        got = self.look("Alnus incana")
        self.assertEqual(got["provinces"]["AB"], "native")
        self.assertEqual(got["provinces"]["SK"], "native")

    def test_native_in_one_child_beats_excluded_in_a_sibling(self):
        """subsp. incana is excluded from AB; subsp. tenuifolia is native
        there. One variety being absent says nothing about the species."""
        self.assertEqual(self.look("Alnus incana")["provinces"]["AB"],
                         "native")

    def test_a_species_with_its_own_distribution_still_works(self):
        got = self.look("Acorus americanus")
        self.assertEqual(got["provinces"]["AB"], "native")

    def test_a_synonym_does_not_vote(self):
        """The Acorus synonym carries an MB introduced row. Counting it would
        let a name VASCAN has superseded decide where the plant grows."""
        self.assertNotIn("MB", self.look("Acorus americanus")["provinces"])

    def test_an_unknown_name_matches_nothing_and_claims_nothing(self):
        got = self.look("Testus plantus")
        self.assertFalse(got["matched"])
        self.assertFalse(got["has_distribution"])
        self.assertEqual(got["provinces"], {})

    def test_authorship_is_ignored_when_matching(self):
        """VASCAN writes the author string; the catalogue writes a binomial."""
        self.assertTrue(self.look("Amelanchier alnifolia")["matched"])

    def test_the_rank_travels_so_the_cause_stays_readable(self):
        self.assertEqual(self.look("Amelanchier alnifolia")["taxon_rank"],
                         "species")


class TestItRefusesRatherThanGuessing(unittest.TestCase):
    """A wrong archive that parses is worse than no archive -- the rule
    `tools/ecoregions/fetch.py` already states for unreachable sources."""

    def test_a_missing_taxon_file_says_which_file(self):
        tmp = Path(tempfile.mkdtemp())
        path = tmp / "empty.zip"
        with zipfile.ZipFile(path, "w") as zf:
            zf.writestr("readme.txt", "nothing here")
        with self.assertRaises(A.ArchiveProblem) as caught:
            A.read_taxa(path)
        self.assertIn("taxon", str(caught.exception))

    def test_a_file_that_is_not_a_zip_says_so(self):
        tmp = Path(tempfile.mkdtemp()) / "notazip.zip"
        tmp.write_text("plain text", encoding="utf-8")
        with self.assertRaises(A.ArchiveProblem):
            A.read_taxa(tmp)

    def test_a_taxon_file_without_the_columns_names_the_header(self):
        src = _archive([["1", "2"]], [])
        # header written above is the real one, so build a bad one by hand
        tmp = Path(tempfile.mkdtemp())
        (tmp / "taxon.txt").write_text("colA\tcolB\n1\t2", encoding="utf-8")
        (tmp / "distribution.txt").write_text("id\n1", encoding="utf-8")
        with self.assertRaises(A.ArchiveProblem) as caught:
            A.read_taxa(tmp)
        self.assertIn("colA", str(caught.exception))
        del src

    def test_a_distribution_file_with_nothing_to_join_on_names_the_header(self):
        tmp = Path(tempfile.mkdtemp())
        (tmp / "taxon.txt").write_text("taxonID\tscientificName\n1\tTestus sp.",
                                       encoding="utf-8")
        (tmp / "distribution.txt").write_text("colA\tcolB\n1\tAB",
                                              encoding="utf-8")
        with self.assertRaises(A.ArchiveProblem) as caught:
            A.read_distribution(tmp, PROV)
        self.assertIn("colA", str(caught.exception))

    def test_an_unpacked_directory_works_too(self):
        """Unzipping first is a reasonable thing for a person to have done."""
        src = _archive(TAXA, DISTS, as_dir=True)
        taxa = A.read_taxa(src)
        dist = A.read_distribution(src, PROV)
        self.assertEqual(
            A.lookup(taxa, dist, "Amelanchier alnifolia", PROV)["provinces"],
            {"AB": "native", "SK": "native"})

    def test_an_extension_that_does_repeat_taxonid_still_wins_on_it(self):
        """`taxonID` is tried before `id`, so an archive published the other
        way round is not read through a column that happens to be called
        `id` and means something else."""
        tmp = Path(tempfile.mkdtemp())
        (tmp / "taxon.txt").write_text("taxonID\tscientificName\n7\tTestus sp.",
                                       encoding="utf-8")
        (tmp / "distribution.txt").write_text(
            "id\ttaxonID\tlocality\testablishmentMeans\n"
            "999\t7\tAB\tnative", encoding="utf-8")
        taxa = A.read_taxa(tmp)
        dist = A.read_distribution(tmp, PROV)
        self.assertEqual(
            A.lookup(taxa, dist, "Testus sp.", PROV)["provinces"],
            {"AB": "native"})

    def test_full_uri_column_headers_are_accepted(self):
        """Archives are published with bare terms and with full URIs; guessing
        one spelling would fail on half of them."""
        tmp = Path(tempfile.mkdtemp())
        (tmp / "taxon.txt").write_text(
            "http://rs.tdwg.org/dwc/terms/taxonID\t"
            "http://rs.tdwg.org/dwc/terms/scientificName\n"
            "1\tTestus plantus", encoding="utf-8")
        (tmp / "distribution.txt").write_text(
            "http://rs.tdwg.org/dwc/terms/taxonID\t"
            "http://rs.tdwg.org/dwc/terms/locality\t"
            "http://rs.tdwg.org/dwc/terms/establishmentMeans\n"
            "1\tAB\tnative", encoding="utf-8")
        taxa = A.read_taxa(tmp)
        dist = A.read_distribution(tmp, PROV)
        self.assertEqual(
            A.lookup(taxa, dist, "Testus plantus", PROV)["provinces"],
            {"AB": "native"})


class TestItFeedsTheExistingJudgement(unittest.TestCase):
    """The archive path must produce what `assess()` already takes, so the
    verdicts, `--reassess` and the ingest all keep working unchanged."""

    def test_assess_confirms_a_rolled_up_species(self):
        from scripts.fetch_flora_nativity import assess
        src = _archive(TAXA, DISTS)
        got = A.lookup(A.read_taxa(src), A.read_distribution(src, PROV),
                       "Amelanchier alnifolia", PROV)
        verdict = assess(got)
        self.assertEqual(verdict["verdict"], "confirm")
        self.assertEqual(verdict["native_provinces"], "AB,SK")

    def test_a_species_with_nothing_anywhere_stays_undetermined(self):
        """Never `not_here` -- the F148 rule, in the new code path."""
        from scripts.fetch_flora_nativity import assess
        src = _archive([["1", "", "", "Testus plantus", "species", "accepted"]],
                       [])
        got = A.lookup(A.read_taxa(src), A.read_distribution(src, PROV),
                       "Testus plantus", PROV)
        self.assertEqual(assess(got)["verdict"], "review")
        self.assertEqual(assess(got)["origin"], "undetermined")


class TestItCanExplainOneAnswer(unittest.TestCase):
    """The real archive left nine species with no distribution -- fireweed and
    stinging nettle among them, which nobody doubts are in Alberta. A verdict
    that is wrong about those is a bug in this reader, and the difference is
    only visible from inside the archive."""

    @classmethod
    def setUpClass(cls):
        src = _archive(TAXA, DISTS)
        cls.taxa = A.read_taxa(src)
        cls.dist = A.read_distribution(src, PROV)

    def _explain(self, name):
        return A.explain(self.taxa, self.dist, name, PROV)

    def test_it_shows_the_child_the_distribution_actually_came_from(self):
        text = self._explain("Amelanchier alnifolia")
        self.assertIn("var. alnifolia", text)
        self.assertIn("has distribution", text)
        self.assertIn("'AB': 'native'", text)

    def test_it_lists_every_taxon_the_binomial_matched_not_just_the_winner(self):
        """Picking the wrong one of several is the failure this cannot
        otherwise be told apart from the archive having no rows."""
        text = self._explain("Alnus incana")
        self.assertIn("subsp. tenuifolia", text)
        self.assertIn("subsp. incana", text)

    def test_a_name_the_checklist_does_not_carry_says_so(self):
        text = self._explain("Nonexistus fakus")
        self.assertIn("does not carry", text)

    def test_an_empty_result_says_which_of_the_two_shapes_it_is(self):
        """No descendants at all is a different problem from descendants that
        carry no row, and the fix is different."""
        tmp = Path(tempfile.mkdtemp())
        (tmp / "taxon.txt").write_text(
            "taxonID\tparentNameUsageID\tscientificName\ttaxonRank\t"
            "taxonomicStatus\n"
            "1\t\tLonelius solus\tspecies\taccepted", encoding="utf-8")
        (tmp / "distribution.txt").write_text(
            "id\tlocality\testablishmentMeans\n", encoding="utf-8")
        taxa = A.read_taxa(tmp)
        dist = A.read_distribution(tmp, PROV)
        text = A.explain(taxa, dist, "Lonelius solus", PROV)
        self.assertIn("NOTHING FOUND", text)
        self.assertIn("no accepted taxa beneath", text)

    def test_it_writes_nothing(self):
        """It is a diagnostic, run against a puzzling row in a file somebody
        has already generated."""
        before = A.read_distribution(_archive(TAXA, DISTS), PROV)
        self._explain("Amelanchier alnifolia")
        self.assertEqual(len(before), len(self.dist))


#: **Straight out of the author's real archive** (VASCAN v37.17), ids and all.
#: `_canonical` reduces a name to its first two words, so nine taxa collapse
#: onto "Chamaenerion angustifolium" and two of them are accepted at rank
#: species -- the plant, and a hybrid formula. The tie was broken by dict
#: order, the hybrid won, and fireweed was published as having no Alberta
#: distribution while its two AB/SK/MB-native subspecies went unread.
FIREWEED_TAXA = [
    ["17491", "29483", "17491",
     "Chamaenerion angustifolium (Linnaeus) Scopoli", "species", "accepted"],
    ["29497", "17491", "29497",
     "Chamaenerion angustifolium (Linnaeus) Scopoli subsp. angustifolium",
     "subspecies", "accepted"],
    ["29484", "29483", "29484",
     "Chamaenerion angustifolium subsp. angustifolium "
     "\u00d7 Chamaenerion latifolium", "species", "accepted"],
    ["29498", "17491", "29498",
     "Chamaenerion angustifolium subsp. circumvagum (Mosquin) Moldenke",
     "subspecies", "accepted"],
    ["29509", "", "29498",
     "Chamaenerion angustifolium subsp. macrophyllum (Hausskn.) Czerepanov",
     "subspecies", "synonym"],
    ["29507", "", "29498",
     "Chamaenerion angustifolium var. abbreviatum Lunell", "variety",
     "synonym"],
]

FIREWEED_DISTS = [
    ["29497", "ISO 3166-2:CA-AB", "AB", "", "native"],
    ["29497", "ISO 3166-2:CA-SK", "SK", "", "native"],
    ["29498", "ISO 3166-2:CA-AB", "AB", "", "native"],
    ["29498", "ISO 3166-2:CA-MB", "MB", "", "native"],
]


class TestTheHybridDoesNotWinTheName(unittest.TestCase):
    """V2.80. Found by pointing --explain at the real archive, which is the
    only place this was visible: nothing raised, and the answer -- fireweed
    is not recorded from Alberta -- was merely false."""

    @classmethod
    def setUpClass(cls):
        src = _archive(FIREWEED_TAXA, FIREWEED_DISTS)
        cls.taxa = A.read_taxa(src)
        cls.dist = A.read_distribution(src, PROV)

    def look(self):
        return A.lookup(self.taxa, self.dist, "Chamaenerion angustifolium",
                        PROV)

    def test_the_plant_is_found_not_the_hybrid(self):
        got = self.look()
        self.assertNotIn("\u00d7", got["accepted_name"])
        self.assertIn("Scopoli", got["accepted_name"])

    def test_its_subspecies_distribution_rolls_up(self):
        self.assertEqual(self.look()["provinces"],
                         {"AB": "native", "SK": "native", "MB": "native"})

    def test_a_hybrid_formula_is_not_a_plain_binomial(self):
        self.assertFalse(A._is_plain_binomial(
            "Chamaenerion angustifolium subsp. angustifolium "
            "\u00d7 Chamaenerion latifolium"))
        self.assertFalse(A._is_plain_binomial("Salix \u00d7 rubens Schrank"))

    def test_an_ordinary_species_name_is(self):
        for name in ("Chamaenerion angustifolium (Linnaeus) Scopoli",
                     "Amelanchier alnifolia (Nuttall) Nuttall ex M. Roemer",
                     "Urtica dioica Linnaeus"):
            self.assertTrue(A._is_plain_binomial(name), name)

    def test_an_infraspecific_name_is_not(self):
        for name in ("Alnus incana subsp. tenuifolia (Nuttall) Breitung",
                     "Urtica dioica var. gracilis (Aiton) R.L. Taylor",
                     "Spiraea alba var. latifolia (Aiton) Dippel"):
            self.assertFalse(A._is_plain_binomial(name), name)

    def test_a_shorter_hybrid_name_still_loses(self):
        """The first cut of this test passed without the hybrid rule at all,
        because the plant's name happened to be shorter than the hybrid's and
        the length tiebreak carried it. A hybrid formula written without
        authorship is shorter, and then only the rule saves it."""
        taxa_rows = [
            ["1", "", "1", "Chamaenerion angustifolium (Linnaeus) Scopoli",
             "species", "accepted"],
            ["2", "", "2",
             "Chamaenerion angustifolium \u00d7 latifolium", "species",
             "accepted"],
            ["3", "1", "3",
             "Chamaenerion angustifolium (Linnaeus) Scopoli subsp. "
             "angustifolium", "subspecies", "accepted"],
        ]
        src = _archive(taxa_rows, [["3", "ISO 3166-2:CA-AB", "AB", "",
                                    "native"]])
        taxa, dist = A.read_taxa(src), A.read_distribution(src, PROV)
        got = A.lookup(taxa, dist, "Chamaenerion angustifolium", PROV)
        self.assertNotIn("\u00d7", got["accepted_name"])
        self.assertEqual(got["provinces"], {"AB": "native"})

    def test_the_choice_does_not_depend_on_dict_order(self):
        """The original tie was broken by whichever taxon Python happened to
        iterate first. A reproducible wrong answer is bad; an irreproducible
        one cannot even be diagnosed."""
        src = _archive(list(reversed(FIREWEED_TAXA)), FIREWEED_DISTS)
        taxa, dist = A.read_taxa(src), A.read_distribution(src, PROV)
        flipped = A.lookup(taxa, dist, "Chamaenerion angustifolium", PROV)
        self.assertEqual(flipped["accepted_name"],
                         self.look()["accepted_name"])
        self.assertEqual(flipped["provinces"], self.look()["provinces"])


class TestItSuggestsTheNameThatIsActuallyHere(unittest.TestCase):
    """V2.80. `--explain` answers *why did this get no answer*; this answers
    the question that follows, which is *then what is the plant called*.

    The author, after reading the report: **"the names should be correct and
    the list should only include native not introduced plants that do occur in
    AB and SK according to VASCAN."** Eight of the sixteen unresolved species
    look like *Urtica dioica*: VASCAN carries the binomial, records it from
    nowhere here, and the plant that grows here is a different accepted
    species."""

    TAXA = [
        ["1", "", "1", "Urtica dioica Linnaeus", "species", "accepted"],
        ["2", "1", "2", "Urtica dioica Linnaeus subsp. dioica", "subspecies",
         "accepted"],
        ["3", "", "4", "Urtica dioica subsp. gracilis (Aiton) Selander",
         "subspecies", "synonym"],
        ["4", "", "4", "Urtica gracilis Aiton", "species", "accepted"],
        ["5", "", "5", "Urtica urens Linnaeus", "species", "accepted"],
    ]
    DISTS = [
        ["4", "ISO 3166-2:CA-AB", "AB", "", "native"],
        ["4", "ISO 3166-2:CA-SK", "SK", "", "native"],
        ["5", "ISO 3166-2:CA-AB", "AB", "", "introduced"],
    ]

    @classmethod
    def setUpClass(cls):
        src = _archive(cls.TAXA, cls.DISTS)
        cls.taxa = A.read_taxa(src)
        cls.dist = A.read_distribution(src, PROV)

    def _suggest(self, name="Urtica dioica"):
        return A.suggest(self.taxa, self.dist, name, PROV)

    def test_it_finds_the_accepted_species_that_is_recorded_here(self):
        self.assertIn("Urtica gracilis", self._suggest())

    def test_it_searches_by_genus_because_the_binomial_is_the_broken_part(self):
        """The exact name is the thing that is wrong, so it cannot be the thing
        we look up."""
        self.assertIn("Urtica gracilis", self._suggest("Urtica dioica"))

    def test_a_native_candidate_is_listed_before_an_introduced_one(self):
        """An introduced record answers a different question, and putting it
        first invites somebody to adopt it by mistake."""
        out = self._suggest()
        self.assertLess(out.index("Urtica gracilis"), out.index("Urtica urens"))
        self.assertIn("<-- native here", out)

    def test_a_synonym_is_not_offered_as_a_new_name(self):
        """`subsp. gracilis` points at the accepted species; renaming to a
        synonym would move the problem rather than fix it."""
        self.assertNotIn("subsp. gracilis", self._suggest())

    def test_a_genus_with_nothing_recorded_here_says_so(self):
        """Not a rename: something else is wrong, and a silent empty list would
        read as "no candidates" rather than "wrong question"."""
        out = A.suggest(self.taxa, self.dist, "Nonexistus fakus", PROV)
        self.assertIn("not a rename", out)

    def test_it_writes_nothing(self):
        before = dict(self.taxa)
        self._suggest()
        self.assertEqual(before, self.taxa)



if __name__ == "__main__":
    unittest.main()

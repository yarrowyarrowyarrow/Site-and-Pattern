"""
The confidence block (F8, F12, F13, F14, F28) — one vocabulary, two bands, and
the distinctions they exist to keep.

These tests are mostly about what the modules REFUSE to say. A band that is
willing to report "medium" about no evidence, or a mark that renders an
estimate the same way as a measurement, would pass every functional test and
defeat the entire point (P9).
"""

import unittest

from src import confidence as C
from src.establishment import establishment_for_design, summary_band
from src.reference_fidelity import LAYER_TYPES, fidelity


class TestTheVocabularyRefusesToGuess(unittest.TestCase):

    def test_a_band_with_no_evidence_is_unknown_not_middle(self):
        """The whole module turns on this.

        Every scorer in this codebase degrades to a neutral 0.5, and bucketing
        that naively prints "medium confidence" about nothing — the exact bug
        V2.51 found in the ecoregion maps.
        """
        self.assertIs(C.band("establishment", "high", known=False), C.UNKNOWN)
        self.assertIs(C.band("fidelity", "high", known=False), C.UNKNOWN)
        self.assertFalse(C.UNKNOWN.known)
        self.assertNotEqual(C.UNKNOWN.key, "medium")

    def test_an_unknown_scale_or_key_yields_unknown(self):
        self.assertIs(C.band("no-such-scale", "high"), C.UNKNOWN)
        self.assertIs(C.band("establishment", "wat"), C.UNKNOWN)
        self.assertIs(C.band("establishment", ""), C.UNKNOWN)

    def test_every_band_carries_a_blurb_saying_what_it_rests_on(self):
        """A label without its basis is a confident-looking noise."""
        for scale, bands in C.SCALES.items():
            for key, b in bands.items():
                self.assertTrue(b.blurb.strip(),
                                f"{scale}.{key} has no blurb")
                self.assertEqual(b.key, key)


class TestAbsentIsNotEstimated(unittest.TestCase):
    """F28's central distinction.

    A blank field means the app knows it does not know. ``estimated`` means a
    genus default was written in and looks exactly like a measurement — the
    more dangerous of the two, and the one that put a red flower on the blue
    columbine.
    """

    def test_blank_and_estimated_are_different_marks(self):
        self.assertIsNot(C.mark(""), C.mark("estimated"))
        self.assertFalse(C.mark("").recorded)
        self.assertTrue(C.mark("estimated").recorded)
        self.assertTrue(C.mark("estimated").inferred)

    def test_an_unknown_provenance_word_is_not_guessed_at(self):
        """A new seed word shows up as an honest gap, not as whichever mark it
        happened to sort next to."""
        self.assertIs(C.mark("brand_new_word"), C.UNRECORDED)

    def test_checked_values_are_not_inferred(self):
        for key in ("measured", "flora", "photo", "checked", "name",
                    "epithet", "documented"):
            self.assertFalse(C.is_inferred(key), key)
        for key in ("estimated", "derived", "recorded"):
            self.assertTrue(C.is_inferred(key), key)

    def test_annotate_marks_only_what_needs_marking(self):
        """Marking everything trains the eye to skip the mark."""
        self.assertEqual(C.annotate("13 rays", "measured"), "13 rays")
        self.assertIn("not verified", C.annotate("13 rays", "estimated"))
        self.assertIn("not recorded", C.annotate("13 rays", ""))


class TestTheLanguageHelpers(unittest.TestCase):

    def test_an_absence_is_phrased_as_an_absence_of_record(self):
        line = C.no_record_of("providing bird food")
        self.assertIn("recorded", line)
        self.assertNotIn("Nothing provides", line)

    def test_a_count_says_what_it_counts(self):
        self.assertEqual(C.hedge_count(3, "bee species"),
                         "3 documented bee species")

    def test_a_noun_already_plural_is_not_pluralised_again(self):
        self.assertNotIn("speciess", C.hedge_count(4, "bird species"))

    def test_one_is_singular(self):
        self.assertEqual(C.hedge_count(1, "bird"), "1 documented bird")


class TestEstablishmentBand(unittest.TestCase):

    def test_thresholds_come_from_the_module_that_owns_them(self):
        from src.ecoregion_ranges import CONFIDENCE_BANDS
        for floor, expected in CONFIDENCE_BANDS:
            self.assertEqual(C.establishment_band(floor).key, expected)

    def test_below_the_floor_is_unknown_not_low(self):
        """Under-collected and absent look identical from here, and the app
        must not turn one into the other."""
        self.assertFalse(C.establishment_band(2).known)
        self.assertFalse(C.establishment_band(0).known)
        self.assertFalse(C.establishment_band(None).known)


#: Kept module-level, not as a class attribute: a plain function stored on a
#: class becomes a *bound method* on attribute access, so `self.RANGES(ids)`
#: would silently pass `self` as the first argument. The resulting TypeError is
#: swallowed by establishment_for_design's degrade-to-unknown branch, which is
#: correct behaviour for a broken lookup and a confusing test failure.
_RANGES = {
    1: [{"ecoregion": "aspen_parkland", "occurrences": 312, "source": "GBIF"}],
    2: [{"ecoregion": "aspen_parkland", "occurrences": 4, "source": "GBIF"}],
    3: [{"ecoregion": "boreal_mixedwood", "occurrences": 90,
         "source": "GBIF"}],
}


def _ranges_for(ids):
    return {i: _RANGES.get(i, []) for i in ids}


class TestEstablishmentForDesign(unittest.TestCase):

    PLANTS = [
        {"plant_id": 1, "common_name": "Saskatoon Berry"},
        {"plant_id": 1, "common_name": "Saskatoon Berry"},
        {"plant_id": 2, "common_name": "Blazingstar"},
        {"plant_id": 3, "common_name": "Bunchberry"},
    ]

    def _run(self, ecoregion="aspen_parkland"):
        return establishment_for_design(self.PLANTS, ecoregion,
                                        ranges_for=_ranges_for)

    def test_species_are_banded_by_their_record_in_THIS_ecoregion(self):
        r = self._run()
        by_name = {e["name"]: e for e in r["species"]}
        self.assertEqual(by_name["Saskatoon Berry"]["band"].key, "high")
        self.assertEqual(by_name["Blazingstar"]["band"].key, "low")
        # Recorded elsewhere is not recorded here.
        self.assertFalse(by_name["Bunchberry"]["band"].known)

    def test_copies_collapse_to_one_species_row(self):
        r = self._run()
        self.assertEqual(len(r["species"]), 3)
        saskatoon = next(e for e in r["species"]
                         if e["name"] == "Saskatoon Berry")
        self.assertEqual(saskatoon["n"], 2)

    def test_no_pin_means_no_band_at_all(self):
        r = establishment_for_design(self.PLANTS, None,
                                     ranges_for=_ranges_for)
        self.assertFalse(r["known"])
        self.assertFalse(summary_band(r).known)

    def test_the_summary_takes_the_weakest_evidenced_rung(self):
        """Not an average — forty well-recorded natives must not hide the one
        nobody has collected here."""
        self.assertEqual(summary_band(self._run()).key, "low")

    def test_an_unrecorded_species_is_named_as_a_gap_in_the_record(self):
        lines = " ".join(self._run()["lines"])
        self.assertIn("Bunchberry", lines)
        self.assertIn("not evidence they will not grow", lines)

    def test_a_failing_lookup_degrades_to_unknown(self):
        def boom(_ids):
            raise RuntimeError("db gone")
        r = establishment_for_design(self.PLANTS, "aspen_parkland",
                                     ranges_for=boom)
        self.assertFalse(r["known"])


class TestReferenceFidelity(unittest.TestCase):

    #: **Common** names, because that is what the real
    #: `resolve_reference_community` returns: it appends
    #: ``r["common_name"] or r["scientific_name"]``, and every seeded row has a
    #: common name. A first version of this fixture used scientific names on
    #: both sides, which made a broken genus match look correct — see
    #: `reference_fidelity._tokens`.
    REF = {"name": "Aspen Parkland grove", "layers": {
        "canopy": ["Trembling Aspen"] * 4,
        "shrub": ["Saskatoon Berry"] * 8,
        "forb": ["Canada Goldenrod"] * 12,
        "grass": ["Rough Fescue"] * 8}}

    @staticmethod
    def _p(ptype, n, sci="", common=""):
        return [{"plant_type": ptype, "scientific_name": sci,
                 "common_name": common}] * n

    def _fid(self, plants):
        return fidelity(plants, "aspen_parkland", resolve=lambda _e: self.REF)

    def test_a_design_with_every_layer_scores_high(self):
        plants = (self._p("tree", 2, "Populus tremuloides", "Trembling Aspen")
                  + self._p("shrub", 3, "Amelanchier alnifolia",
                            "Saskatoon Berry")
                  + self._p("wildflower", 6, "Solidago canadensis",
                            "Canada Goldenrod")
                  + self._p("grass", 4, "Festuca hallii", "Rough Fescue"))
        r = self._fid(plants)
        self.assertEqual(r["band"].key, "high")
        self.assertEqual(r["missing_layers"], [])

    def test_it_matches_a_reference_species_across_name_forms(self):
        """The bug an end-to-end probe caught: the reference resolves to common
        names and a placed plant is matched on its scientific name, so
        comparing one to the other found nothing on a design built entirely out
        of the reference community."""
        r = self._fid(self._p("shrub", 3, "Amelanchier alnifolia",
                              "Saskatoon Berry"))
        self.assertTrue(r["matched_species"],
                        "a reference species in the design was not matched")

    def test_a_forb_only_planting_is_a_long_way_off(self):
        r = self._fid(self._p("wildflower", 4, "Echinacea purpurea",
                              "Purple Coneflower"))
        self.assertEqual(r["band"].key, "low")
        self.assertIn("canopy", r["missing_layers"])

    def test_nothing_placed_is_unknown_not_zero(self):
        """A catalogue gap must not be reported as a design failure."""
        r = self._fid([])
        self.assertFalse(r["known"])
        self.assertIsNone(r["score"])
        self.assertFalse(r["band"].known)

    def test_structure_outweighs_name_matching(self):
        """Matching names while missing whole layers must not score well."""
        only_names = self._p("wildflower", 12, "Solidago canadensis",
                             "Canada Goldenrod")
        r = self._fid(only_names)
        self.assertLess(r["score"], 0.6)

    def test_the_band_never_contradicts_its_own_blurb(self):
        """"Close to the reference" says *most layers are represented*.

        The species bonus alone could lift a design over that threshold with
        three of four layers thin — a real six-plant parkland design scored
        0.68 that way on an end-to-end probe.
        """
        sparse = (self._p("tree", 1, "Populus tremuloides", "Trembling Aspen")
                  + self._p("shrub", 1, "Amelanchier alnifolia",
                            "Saskatoon Berry")
                  + self._p("wildflower", 1, "Solidago canadensis",
                            "Canada Goldenrod")
                  + self._p("grass", 1, "Festuca hallii", "Rough Fescue"))
        r = self._fid(sparse)
        self.assertGreater(len(r["missing_layers"]), 1)
        self.assertNotEqual(r["band"].key, "high")

    def test_the_reported_score_never_contradicts_the_band(self):
        """A caller reading score 0.68 beside band 'medium' reads a
        contradiction; the band is the answer this module stands behind."""
        sparse = (self._p("tree", 1, "Populus tremuloides", "Trembling Aspen")
                  + self._p("shrub", 1, "Amelanchier alnifolia",
                            "Saskatoon Berry")
                  + self._p("wildflower", 1, "Solidago canadensis",
                            "Canada Goldenrod")
                  + self._p("grass", 1, "Festuca hallii", "Rough Fescue"))
        r = self._fid(sparse)
        from src.confidence import fidelity_band
        self.assertEqual(fidelity_band(r["score"]).key, r["band"].key)

    def test_the_layer_map_matches_the_walkable_reference(self):
        """Two layer maps that drift apart would make the score and the 3D
        reference disagree about the same design."""
        from src.reference_ecosystem import _LAYER_TYPES
        self.assertEqual(LAYER_TYPES, _LAYER_TYPES)


class TestTheCriticStoppedAssertingAbsences(unittest.TestCase):
    """F8. The bug was not loose wording; it was an absence claim read off the
    weaker of two sources the app holds for the same question."""

    @staticmethod
    def _habitat(**food_web):
        return {"components": {"host": {"score": 0}, "bird_food": {"score": 0},
                               "keystone": {"score": 9}, "bloom": {},
                               "layers": {"present": ["tree", "shrub", "forb"]},
                               "structures": {"score": 5}},
                "food_web": food_web}

    def test_it_does_not_deny_host_plants_its_own_edges_document(self):
        from src.design_critic import critique_lines
        lines = critique_lines(self._habitat(
            caterpillars=True, n_caterpillars=7, birds=True, n_birds=3,
            status="complete"))
        joined = " ".join(lines)
        self.assertIn("recorded laying eggs", joined)
        self.assertNotIn("without host plants there are no caterpillars",
                         joined)

    def test_a_real_absence_is_still_reported_as_one(self):
        from src.design_critic import critique_lines
        lines = critique_lines(self._habitat(
            caterpillars=False, n_caterpillars=0, birds=False, n_birds=0,
            status="empty"))
        self.assertTrue(any("recorded" in ln for ln in lines))


class TestTheDataGateSeesTheContradiction(unittest.TestCase):

    def test_the_contradiction_is_closed(self):
        """**These two used to assert the contradiction was present.** V2.53
        found it, measured it at 48 species, and deliberately left it: the fix
        moves every affected design's Habitat Value Score, which the
        headline-stability rule reserves to the author. F120 took that decision
        in V2.65, so the assertion inverts — the gate must now find nothing.

        Kept rather than deleted, and kept in this file, because the thing
        worth guarding is that tags and cited edges *agree*. A future seed
        edit that reintroduces the gap fails here."""
        from src.data_quality import use_tags_vs_edges
        self.assertEqual(use_tags_vs_edges(), {})

    def test_it_would_still_report_as_a_warning_not_an_error(self):
        """The severity is the part that has not changed. Were the gap to come
        back it is a warning: a seed correction that moves scores is a decision
        to take deliberately, never a build to break."""
        from src.data_quality import validate_use_tags_against_edges
        errors, warnings = validate_use_tags_against_edges()
        self.assertEqual(errors, [])
        self.assertEqual(warnings, [])


class TestCitationsReachTheDesignSurfaces(unittest.TestCase):
    """F12. `src/citations.py` shipped in V2.42 and reached only the directory
    species page and Help - Data Sources."""

    EDGES = [
        {"id": 10, "plant_id": 1, "common_name": "Monarch",
         "scientific_name": "Danaus plexippus", "taxon": "lepidoptera",
         "relationship": "larval_host", "specificity": "specialist",
         "source": "acorn_sheldon_butterflies_ab"},
        {"id": 11, "plant_id": 1, "common_name": "Mystery Bee",
         "scientific_name": "X y", "taxon": "bee", "relationship": "pollen",
         "specificity": "generalist",
         "source": "unattributed_prairie_pollination"},
    ]

    def _entry(self):
        from src.scene_dossier import build_dossier
        d = build_dossier(
            {"year": 5, "plants": [{"plant_id": 1, "common_name": "Milkweed"}]},
            get_plant=lambda _i: {"id": 1, "common_name": "Milkweed",
                                  "plant_type": "wildflower"},
            fauna_edges=lambda _p: self.EDGES,
            fauna_attrs=lambda *_a, **_k: {})
        return d["plants"]["1"]

    def test_the_dossier_card_carries_a_citation_per_edge(self):
        users = {u["name"]: u for u in self._entry()["users"]}
        self.assertIn("Acorn", users["Monarch"]["source"])

    def test_a_placeholder_is_never_rendered_as_a_citation(self):
        users = {u["name"]: u for u in self._entry()["users"]}
        self.assertEqual(users["Mystery Bee"]["source"], "")

    def test_unattributed_edges_are_counted_rather_than_hidden(self):
        block = self._entry()["sources"]
        self.assertEqual(block["unattributed"], 1)
        self.assertEqual(len(block["works"]), 1)

    def test_the_relationship_web_names_the_works_it_rests_on(self):
        from src.relationship_graph import summary_lines
        stats = {"species": 3, "wildlife": 5, "edges": 9,
                 "documented_edges": 9, "derived_edges": 0,
                 "recorded_edges": 0,
                 "works": ["Acorn & Sheldon 2006", "Wilson & Carril 2015"]}
        lines = summary_lines({"stats": stats})
        self.assertTrue(any("Acorn & Sheldon 2006" in ln for ln in lines))


if __name__ == "__main__":
    unittest.main()

"""
tests/test_fauna_sourcing.py — the F125 sourcing pipeline (V2.59).

``plant_fauna`` covers 99 of 437 species. The fix is real cited records, and the
development container's egress policy denies GloBI, GBIF and iNaturalist — so
the fetch runs on the author's machine and the *review* runs here.

Which means the gates are the part that must not rot. An aggregator returns what
it has, not what is true in Alberta, and this catalogue's confidence work only
means anything if a `documented` edge is genuinely documented. Everything below
is network-free: the fetcher's mapping is exercised against a fixture response,
and the ingester's gates against a synthetic candidate file.
"""

import importlib.util
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _load(name):
    path = os.path.join(_ROOT, "scripts", f"{name}.py")
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_fetch = _load("fetch_fauna_edges")
_ingest = _load("ingest_fauna_edges")


def _row(name, interaction, path, citation="A study 2020"):
    return {"target_taxon_name": name, "interaction_type": interaction,
            "target_taxon_path": path, "study_citation": citation}


_BEE = "Animalia | Arthropoda | Insecta | Hymenoptera | Apidae"
_LEP = "Animalia | Arthropoda | Insecta | Lepidoptera | Nymphalidae"
_BIRD = "Animalia | Chordata | Aves | Passeriformes"
_MAMMAL = "Animalia | Chordata | Mammalia | Artiodactyla"


class TestTheFetcherMapsConservatively(unittest.TestCase):
    """An interaction that cannot be mapped is dropped, never guessed into the
    nearest available word."""

    def _edges(self, rows, known=frozenset(), existing=frozenset()):
        plant = {"common_name": "Test Plant", "scientific_name": "Testus plantus"}
        return _fetch.to_edges(plant, rows, set(known), set(existing))[0]

    def test_flower_visits_and_pollination_map(self):
        edges = self._edges([_row("Bombus huntii", "flowersVisitedBy", _BEE),
                             _row("Apis mellifera", "pollinatedBy", _BEE)])
        self.assertEqual({e["relationship"] for e in edges},
                         {"nectar", "pollen"})

    def test_a_caterpillar_eating_is_a_larval_host(self):
        edges = self._edges([_row("Danaus plexippus", "eatenBy", _LEP)])
        self.assertEqual(edges[0]["relationship"], "larval_host")

    def test_a_bird_eating_is_fruit_forage(self):
        edges = self._edges([_row("Bombycilla cedrorum", "eatenBy", _BIRD)])
        self.assertEqual(edges[0]["relationship"], "fruit_food")

    def test_mammal_browse_is_dropped(self):
        """The seven relationships have no slot for browse. A deer stripping
        willow is not `fruit_food`, and `cover` means the plant *shelters* the
        animal — a different claim. Forcing it would be the exact failure V2.58
        was spent undoing."""
        self.assertEqual(
            self._edges([_row("Odocoileus hemionus", "eatenBy", _MAMMAL)]), [])

    def test_a_sap_sucking_insect_is_dropped(self):
        """'eats' covers leaf miners, gall wasps and aphids. None of those is
        forage."""
        hemiptera = "Animalia | Arthropoda | Insecta | Hemiptera | Aphididae"
        self.assertEqual(
            self._edges([_row("Aphis nerii", "eatenBy", hemiptera)]), [])

    def test_non_animals_are_dropped(self):
        self.assertEqual(
            self._edges([_row("Puccinia graminis", "eatenBy",
                              "Fungi | Basidiomycota")]), [])

    def test_genus_only_records_are_dropped(self):
        """Not a species, so not an edge that can be keyed on."""
        self.assertEqual(self._edges([_row("Bombus", "flowersVisitedBy", _BEE)]),
                         [])

    def test_duplicates_collapse(self):
        edges = self._edges([_row("Bombus huntii", "flowersVisitedBy", _BEE),
                             _row("Bombus huntii", "flowersVisitedBy", _BEE)])
        self.assertEqual(len(edges), 1)

    def test_already_seeded_edges_are_skipped(self):
        existing = {("test plant", "bombus huntii", "nectar")}
        self.assertEqual(
            self._edges([_row("Bombus huntii", "flowersVisitedBy", _BEE)],
                        existing=existing), [])

    def test_new_animals_are_flagged_not_silently_used(self):
        plant = {"common_name": "Test Plant", "scientific_name": "T. plantus"}
        edges, new = _fetch.to_edges(
            plant, [_row("Bombus huntii", "flowersVisitedBy", _BEE)],
            known_fauna=set(), existing=set())
        self.assertFalse(edges[0]["_known_fauna"])
        self.assertEqual(new[0]["scientific_name"], "Bombus huntii")

    def test_the_reporting_study_travels_with_the_edge(self):
        edges = self._edges([_row("Bombus huntii", "flowersVisitedBy", _BEE,
                                  citation="Cariveau et al. 2016")])
        self.assertIn("Cariveau", edges[0]["_citation"])
        self.assertIn("Cariveau", edges[0]["notes"])

    def test_the_query_is_region_limited(self):
        """GloBI is global. A bumblebee recorded on Achillea in a New Zealand
        garden is not evidence about an Alberta yard."""
        self.assertTrue(_fetch._BBOX)
        west, south, east, north = [float(x) for x in _fetch._BBOX.split(",")]
        self.assertLess(west, -50)
        self.assertGreater(north, 45)


class TestTheIngestGates(unittest.TestCase):
    """Report first, apply second. Each gate reports a count, so a run says what
    was thrown away and why."""

    def _review(self, candidates):
        return _ingest.review(candidates)

    def _c(self, **kw):
        base = {"plant": "Wild Bergamot", "fauna": "Newus specius",
                "relationship": "nectar", "_taxon": "bee",
                "_citation": "A study", "notes": "n"}
        base.update(kw)
        return base

    def test_a_clean_candidate_survives(self):
        self.assertEqual(len(self._review([self._c()])["kept"]), 1)

    def test_an_edge_with_no_study_is_refused(self):
        """This table is defined as documented records. An edge with no
        reporting study is an assertion wearing the word 'documented'."""
        out = self._review([self._c(_citation="")])
        self.assertEqual(out["kept"], [])
        self.assertTrue(any("reporting study" in r for r in out["rejected"]))

    def test_a_relationship_outside_the_schema_is_refused(self):
        out = self._review([self._c(relationship="grazing")])
        self.assertEqual(out["kept"], [])

    def test_a_taxon_outside_the_schema_is_refused(self):
        out = self._review([self._c(_taxon="reptile")])
        self.assertEqual(out["kept"], [])

    def test_a_plant_we_do_not_stock_is_refused(self):
        out = self._review([self._c(plant="Saguaro Cactus")])
        self.assertEqual(out["kept"], [])

    def test_genus_level_animals_are_refused(self):
        self.assertEqual(self._review([self._c(fauna="Bombus")])["kept"], [])

    def test_duplicates_within_the_file_collapse(self):
        self.assertEqual(len(self._review([self._c(), self._c()])["kept"]), 1)

    def test_edges_needing_a_new_animal_are_separated(self):
        """They cannot be written yet: a fauna row needs a common name, a taxon
        and a nativity call, none of which an interaction record supplies and
        all of which show up in the UI."""
        out = self._review([self._c(fauna="Newus specius")])
        self.assertTrue(out["kept"][0]["_new_fauna"])
        self.assertIn("Newus specius", out["new_fauna"])

    def test_the_schema_vocabularies_match_the_database(self):
        """Restated in the ingester as a gate. If schema.sql ever changes these
        and this copy does not, --apply would write a value the CHECK
        constraint rejects at seed time."""
        with open(os.path.join(_ROOT, "src", "db", "schema.sql"),
                  encoding="utf-8") as fh:
            sql = fh.read()
        for rel in _ingest._RELATIONSHIPS:
            self.assertIn(f"'{rel}'", sql, f"{rel} is not in schema.sql")
        for taxon in _ingest._TAXA:
            self.assertIn(f"'{taxon}'", sql, f"{taxon} is not in schema.sql")

    def test_review_never_writes(self):
        """The safety property of the two-step design."""
        path = os.path.join(_ROOT, "data", "plant_fauna_master.json")
        before = os.path.getmtime(path)
        self._review([self._c() for _ in range(5)])
        self.assertEqual(os.path.getmtime(path), before)


class TestTheFetcherReadsTheRealCatalogue(unittest.TestCase):
    def test_it_finds_the_plants_fauna_and_existing_edges(self):
        plants, fauna, existing = _fetch.load_catalogue()
        self.assertGreater(len(plants), 400)
        self.assertGreater(len(fauna), 100)
        self.assertGreater(len(existing), 300)
        self.assertTrue(all(p.get("scientific_name") for p in plants))


if __name__ == "__main__":
    unittest.main()

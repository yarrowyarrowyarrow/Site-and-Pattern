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


def _row(name, interaction, path, citation="A study 2020", life_stage=""):
    """One GloBI row in the shape the live API actually returns.

    `study_title` and `target_specimen_life_stage` are the real column names,
    confirmed by running `--probe` against the API. The first version of this
    fixture used `study_citation`, which does not exist — **the same wrong guess
    the code made**, so the test passed while both were wrong and every fetched
    edge would have arrived uncited and been binned by the ingest gate. A
    fixture invented from the same assumption as the code under test proves
    nothing; only the live probe settled it.
    """
    return {"target_taxon_name": name, "interaction_type": interaction,
            "target_taxon_path": path, "study_title": citation,
            "target_specimen_life_stage": life_stage}


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
        edges = self._edges([_row("Danaus plexippus", "eatenBy", _LEP,
                                  life_stage="larva")])
        self.assertEqual(edges[0]["relationship"], "larval_host")

    def test_an_adult_lepidopteran_eating_is_nectar_not_a_larval_host(self):
        """Adults have no chewing mouthparts. Filing an adult nectar record as
        a larval host would claim the plant feeds caterpillars it may never
        host — and the life stage is right there in the response."""
        edges = self._edges([_row("Vanessa cardui", "eatenBy", _LEP,
                                  life_stage="adult")])
        self.assertEqual(edges[0]["relationship"], "nectar")

    def test_an_unrecorded_life_stage_stays_with_the_conservative_reading(self):
        """Most 'eats' records on a plant are herbivory, so an unstated stage
        keeps the larval-host reading rather than inventing certainty."""
        edges = self._edges([_row("Papilio machaon", "eatenBy", _LEP)])
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
        """Reads `study_title` — see _row. This assertion failing is what
        caught the wrong column name."""
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
                "source": "globi", "_citation": "A study", "notes": "n"}
        base.update(kw)
        return base

    def test_a_clean_candidate_survives(self):
        self.assertEqual(len(self._review([self._c()])["kept"]), 1)

    def test_an_edge_with_no_source_is_refused(self):
        """The provenance standard, as revised in V2.59.

        It originally demanded a named reporting study and rejected all 14,111
        candidates, because GloBI only fills `study_title` when asked for
        observations rather than distinct interactions. The bar is now "a
        registered, checkable source" — GloBI qualifies, an empty string does
        not. That is a real weakening and it is recorded as one, in the
        bibliography record and in the source key itself.
        """
        out = self._review([self._c(source="")])
        self.assertEqual(out["kept"], [])
        self.assertTrue(any("no source" in r for r in out["rejected"]))

    def test_an_edge_with_a_source_but_no_named_study_is_accepted(self):
        """The 2,546 edges F125 actually shipped are exactly this shape."""
        self.assertEqual(len(self._review([self._c(_citation="")])["kept"]), 1)

    def test_nectar_is_refused_on_a_wind_pollinated_plant(self):
        """A grass, sedge or rush has no nectar. GloBI recording a hoverfly on
        a bulrush is a true observation of a visit and a false statement about
        a reward. Reuses the app's own wind-pollinated vocabulary so this and
        the flower-colour classifier cannot disagree."""
        out = self._review([self._c(plant="Big Bluestem", relationship="nectar")])
        self.assertEqual(out["kept"], [])
        self.assertTrue(any("wind-pollinated" in r for r in out["rejected"]))

    def test_pollen_is_still_allowed_on_a_grass(self):
        """Bees genuinely collect grass and sedge pollen — dropping that too
        would trade one wrong claim for a missing true one."""
        out = self._review([self._c(plant="Big Bluestem", relationship="pollen",
                                    fauna="Newus specius")])
        self.assertEqual(len(out["kept"]), 1)

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


class TestTheBirdRouting(unittest.TestCase):
    """V2.60. GloBI's `eatenBy` is not `fruit_food`, and V2.59 read it that way.

    Of the 33 plants that ended up carrying a bird `fruit_food` edge, **ten
    bear no fruit at all** — Lodgepole Pine, White Spruce, Tamarack, Paper
    Birch, Trembling Aspen, Balsam Poplar and four composites. A crossbill on a
    tamarack eats seeds; a sapsucker on a birch drinks sap, which the schema
    cannot express. And GloBI filed three `flowersVisitedBy` records for a
    White-crowned Sparrow, which does not nectar.

    Same failure as the Monarch bug: an unspecific verb read as a specific
    claim. Same answer: refuse what the record cannot support.
    """

    def test_a_frugivore_on_a_fruiting_plant_keeps_fruit_food(self):
        self.assertEqual(
            _ingest.route_bird("fruit_food", {"fruit"}, True), "fruit_food")

    def test_a_frugivore_on_a_fruitless_plant_does_not_claim_fruit(self):
        """The bug, in one line. A waxwing 'eating' a spruce is not eating
        fruit, because a spruce has none."""
        self.assertEqual(_ingest.route_bird("fruit_food", {"fruit"}, False), "")

    def test_a_granivore_becomes_seed_food(self):
        """The recovery, not just the refusal. A White-winged Crossbill on a
        tamarack is a real and useful relationship — it is `seed_food`."""
        self.assertEqual(
            _ingest.route_bird("fruit_food", {"seeds"}, False), "seed_food")

    def test_a_sapsucker_is_dropped_rather_than_forced(self):
        """Sap has no slot in the seven relationships. Dropped as mammal
        browse was, and recoverable from an observations-mode re-fetch."""
        self.assertEqual(_ingest.route_bird("fruit_food", {"sap"}, False), "")
        self.assertEqual(_ingest.route_bird("fruit_food", {"sap"}, True), "")

    def test_only_a_nectarivore_nectars(self):
        self.assertEqual(_ingest.route_bird("nectar", {"nectar"}, False),
                         "nectar")
        self.assertEqual(_ingest.route_bird("nectar", {"seeds"}, False), "")

    def test_a_bird_that_takes_nothing_from_plants_yields_nothing(self):
        """An empty feeds set is a decision, not a gap: a Red-tailed Hawk eats
        no plant, so every plant record for one is a food-web artifact."""
        self.assertEqual(_ingest.route_bird("fruit_food", set(), True), "")
        self.assertEqual(_ingest.route_bird("nectar", set(), True), "")


class TestTheBirdCuration(unittest.TestCase):
    """The 67 birds F125 held, decided one at a time. Every verdict is an
    unsourced call — the same footing as the 142 fauna rows already shipped —
    which is why it is a diffable table and why these guard its shape."""

    def setUp(self):
        self.mod = _load("curate_birds")

    def test_every_held_bird_has_a_verdict(self):
        """A bird the table forgets is silently dropped by the ingest gate,
        which reads as 'no records' rather than 'nobody looked'."""
        self.assertEqual(self.mod.curate()["missing"], [])

    def test_the_verdicts_are_the_three_defined_ones(self):
        for name, row in self.mod.BIRDS.items():
            self.assertIn(row[0], ("include", "hold", "reject"), name)

    def test_ab_native_is_derived_from_the_province_list(self):
        """Two fields that could disagree, so only one is authored."""
        for r in self.mod.curate()["include"]:
            self.assertEqual(r["ab_native"],
                             1 if "AB" in r["native_provinces"].split(",")
                             else 0, r["scientific_name"])

    def test_introduced_species_are_rejected(self):
        """The European Starling genuinely eats chokecherry. It must still not
        become a row: this app recommends plants FOR the animals it lists."""
        for name in ("Sturnus vulgaris", "Myiopsitta monachus",
                     "Turdus philomelos"):
            self.assertEqual(self.mod.BIRDS[name][0], "reject", name)

    def test_the_feeds_vocabulary_is_closed(self):
        allowed = {"fruit", "seeds", "nectar", "buds", "sap", "insects"}
        for name, feeds in self.mod.feeds_map().items():
            self.assertTrue(feeds <= allowed, f"{name}: {feeds - allowed}")

    def test_the_gate_covers_the_birds_already_in_the_catalogue(self):
        """Leaving them out is not neutral — the first run of this gate binned
        62 existing edges belonging to the 24 hand-curated species."""
        import json
        with open(os.path.join(_ROOT, "data", "fauna_master.json"),
                  encoding="utf-8") as fh:
            rows = json.load(fh)
        seeded = {r["scientific_name"] for r in rows
                  if isinstance(r, dict) and r.get("taxon") == "bird"}
        judged = set(self.mod.feeds_map())
        self.assertEqual(seeded - judged, set())

    def test_a_deprecated_name_resolves_onto_the_catalogue_row(self):
        """`Picoides pubescens` is the Downy Woodpecker under its old genus and
        the catalogue already holds it as `Dryobates pubescens`. Without the
        synonym it would have been written as a second Downy Woodpecker."""
        self.assertEqual(self.mod.SYNONYMS["Picoides pubescens"],
                         "Dryobates pubescens")
        self.assertNotIn("Picoides pubescens", self.mod.BIRDS)


class TestTheAppliedEdgesSurviveTheirOwnGates(unittest.TestCase):
    """The property `--refit` exists to keep true: a gate added after an
    `--apply` must not leave contradicting rows behind in the seed file."""

    def test_no_edge_is_stated_twice(self):
        """A `--refit` re-route can land on top of an edge that already exists.

        The first version tracked only the rows it rewrote, so when the
        goldfinch's GloBI `fruit_food` on Common Sunflower became `seed_food`
        it landed beside a **hand-authored, Cornell-cited** `seed_food` row and
        both survived. Four pairs like that. The DB dedupes on insert, so
        nothing broke visibly — which is exactly why it needs a test: a `globi`
        duplicate shadowing a real citation is the kind of rot that is only
        ever found by counting.
        """
        import collections
        import json
        with open(os.path.join(_ROOT, "data", "plant_fauna_master.json"),
                  encoding="utf-8") as fh:
            rows = [r for r in json.load(fh) if r.get("plant")]
        counts = collections.Counter(
            (r["plant"].strip().lower(), r["fauna"].strip().lower(),
             r.get("relationship", "")) for r in rows)
        dupes = [k for k, v in counts.items() if v > 1]
        self.assertEqual(dupes, [], f"edges stated twice: {dupes}")

    def test_no_bird_claims_fruit_on_a_plant_that_bears_none(self):
        import json
        data = os.path.join(_ROOT, "data")

        def rows(name):
            with open(os.path.join(data, name), encoding="utf-8") as fh:
                blob = json.load(fh)
            return blob if isinstance(blob, list) else next(
                v for v in blob.values() if isinstance(v, list))

        fauna = {r["scientific_name"].strip().lower(): r
                 for r in rows("fauna_master.json") if isinstance(r, dict)}
        fruiting = set()
        for name in ("plants_master.json", "garden_plants.json"):
            for p in rows(name):
                if p.get("common_name") and (
                        (p.get("fruit_period") or "").strip()
                        or (p.get("fruit_form") or "").strip()):
                    fruiting.add(p["common_name"].strip().lower())
        bad = [
            (e["plant"], e["fauna"]) for e in rows("plant_fauna_master.json")
            if e.get("plant") and e.get("relationship") == "fruit_food"
            and fauna.get(e["fauna"].strip().lower(), {}).get("taxon") == "bird"
            and e["plant"].strip().lower() not in fruiting
        ]
        self.assertEqual(bad, [], f"fruit claimed on fruitless plants: {bad}")


class TestObservationMode(unittest.TestCase):
    """F128, V2.61. The mode that carries a study, a life stage and a body
    part — the three fields V2.59 wanted and could not have."""

    def test_the_observation_forms_ask_for_observations(self):
        for name, builder in _fetch._OBS_FORMS:
            params = dict(builder("Monarda fistulosa"))
            self.assertEqual(params.get("includeObservations"), "true", name)

    def test_a_mistyped_flag_is_an_error_not_a_different_run(self):
        """`--observations` typed with a space became `--` and `observations`,
        neither of which matched the old `in sys.argv` check — so a run meant
        to fetch citations silently ran the DEFAULT mode, resumed the old
        checkpoint, and two hours later rewrote the identical uncited file.

        The mode a long unattended run is in must never be decided by a
        substring test. argparse rejects what it does not recognise.
        """
        import contextlib
        import io
        parser = _fetch.build_parser()
        for argv in (["--", "observations"], ["-observations"],
                     ["--observations=yes"], ["observations"]):
            with self.assertRaises(SystemExit, msg=argv), \
                    contextlib.redirect_stderr(io.StringIO()):
                parser.parse_args(argv)

    def test_the_flag_actually_sets_the_mode(self):
        """The other half. A parser that rejects everything would pass the
        test above and be useless."""
        parser = _fetch.build_parser()
        self.assertTrue(parser.parse_args(["--observations"]).observations)
        self.assertFalse(parser.parse_args([]).observations)
        # argparse accepts unambiguous prefixes, which is a help rather than a
        # hazard — `--obs` can only mean one thing here.
        self.assertTrue(parser.parse_args(["--obs"]).observations)

    def test_the_default_forms_still_do_not(self):
        """Observation mode multiplies the row count several times over. It
        must be opted into, not inherited."""
        for name, builder in _fetch._FORMS:
            self.assertNotIn("includeObservations",
                             dict(builder("Monarda fistulosa")), name)

    def test_a_column_is_read_through_its_aliases(self):
        """V2.59 hard-coded `study_citation`, which does not exist, and the
        fixture repeated the guess so the suite passed while both were wrong.
        Nobody here can reach the API, so the code reads whichever spelling
        turns up and `--probe` reports which ones are real."""
        self.assertEqual(
            _fetch._pick({"study_title": "Robertson 1929"}, "citation"),
            "Robertson 1929")
        self.assertEqual(
            _fetch._pick({"target_specimen_body_part_name": "seed"},
                         "body_part"), "seed")
        self.assertEqual(_fetch._pick({}, "citation"), "")

    def test_an_empty_alias_falls_through_to_the_next(self):
        """A column that exists and a column that is populated are different
        facts — the distinction that cost 14,111 edges."""
        self.assertEqual(
            _fetch._pick({"study_citation": "  ", "study_title": "Smith 2011"},
                         "citation"), "Smith 2011")

    def test_life_stage_and_body_part_travel_with_the_edge(self):
        plant = {"common_name": "Test Plant", "scientific_name": "T. plantus"}
        row = _row("Bombus huntii", "flowersVisitedBy", _BEE)
        row["target_specimen_body_part_name"] = "flower"
        row["target_specimen_life_stage"] = "adult"
        edges, _ = _fetch.to_edges(plant, [row], set(), set())
        self.assertEqual(edges[0]["_body_part"], "flower")
        self.assertEqual(edges[0]["_life_stage"], "adult")


class TestCitationUpgrade(unittest.TestCase):
    """Turning `globi` into a named study — what "proper citations" means."""

    def test_a_title_with_a_year_splits_into_authors_and_year(self):
        r = _ingest.study_record("Robertson C 1929 Flowers and insects")
        self.assertEqual(r["year"], 1929)
        self.assertEqual(r["authors"], "Robertson C")
        self.assertTrue(r["key"].startswith("globi_"))

    def test_a_specimen_url_is_filed_as_one_not_as_a_study(self):
        """What the live probe actually returned. `study_title` is 100%
        populated and the first value sampled was
        `https://scan-bugs.org/portal/collections/individual/index…` — a
        museum specimen record, because much of GloBI is collection
        aggregation rather than literature.

        It is a real citation: one identifiable record a person can open,
        strictly more than `globi` said. It is not a study, and filing it as
        one would be the same category error this pipeline keeps undoing.
        """
        r = _ingest.study_record(
            "https://scan-bugs.org:443/portal/collections/individual/index.php"
            "?occid=12345678")
        self.assertEqual(r["kind"], "specimen_record")
        self.assertEqual(r["key"], "globi_scan_bugs_org")
        self.assertIn("scan-bugs.org", r["title"])
        self.assertIsNone(r["year"])
        self.assertNotIn("occid", r["key"],
                         "the per-record id must not end up in the key")

    def test_every_record_from_one_portal_shares_one_key(self):
        """Otherwise the bibliography grows one entry per specimen — tens of
        thousands of them — and stops being a bibliography."""
        a = _ingest.study_record("https://scan-bugs.org/portal/x?occid=1")
        b = _ingest.study_record("https://scan-bugs.org/portal/y?occid=999")
        self.assertEqual(a["key"], b["key"])

    def test_a_title_with_no_year_still_makes_a_record(self):
        """GloBI study titles are free text, not structured bibliography. A
        dataset name is still a better citation than 'an aggregator has it'."""
        r = _ingest.study_record("A dataset of pollinator visits")
        self.assertIsNone(r["year"])
        self.assertEqual(r["authors"], "")
        self.assertEqual(r["title"], "A dataset of pollinator visits")

    def test_the_record_admits_it_was_parsed_not_transcribed(self):
        """A machine-split author field is not a reading of the work, and the
        bibliography has a field for saying so."""
        r = _ingest.study_record("Cariveau DP 2016 The allometry of proboscis")
        self.assertEqual(r["record_confidence"], "unverified")
        self.assertIn("Parsed from the study title", r["record_note"])

    def test_the_key_is_stable_for_the_same_title(self):
        a = _ingest.study_record("Robertson C 1929 Flowers and insects")
        b = _ingest.study_record("Robertson  C  1929  Flowers and insects")
        self.assertEqual(a["key"], b["key"])

    def test_the_record_has_every_field_the_bibliography_requires(self):
        import json
        with open(os.path.join(_ROOT, "data", "sources_master.json"),
                  encoding="utf-8") as fh:
            existing = json.load(fh)["sources"]
        required = set(existing[0]) & {"key", "authors", "year", "title",
                                       "kind", "covers", "record_confidence"}
        r = _ingest.study_record("Robertson C 1929 Flowers")
        self.assertEqual(required - set(r), set())


class TestTheNativityGate(unittest.TestCase):
    """"Only flora and fauna native to AB and SK", made checkable.

    The catalogue asserts nativity as a boolean nobody sourced: 142 of 167
    fauna rows carry `ab_native = 1` and no province data at all. This gate
    replaces the assertion with a count, for the animals that do not yet have
    a human verdict behind them.
    """

    def setUp(self):
        self.mod = _load("fetch_fauna_nativity")

    def test_introduced_is_refused_however_many_records(self):
        """The whole reason occurrence cannot stand in for nativity. A
        European Starling has tens of thousands of Alberta records."""
        ok, why = _ingest.nativity_verdict(
            {"ab_records": 90000, "sk_records": 40000, "origin": "introduced"})
        self.assertFalse(ok)
        self.assertIn("introduced", why)

    def test_no_records_here_is_refused(self):
        ok, why = _ingest.nativity_verdict(
            {"ab_records": 0, "sk_records": 0, "origin": "unstated"})
        self.assertFalse(ok)
        self.assertIn("no georeferenced records", why)

    def test_a_handful_of_records_is_refused_as_too_thin(self):
        """Present and *established here* are different claims, and one
        mis-georeferenced record is how a desert quail gets in."""
        ok, why = _ingest.nativity_verdict(
            {"ab_records": 1, "sk_records": 0, "origin": "unstated"})
        self.assertFalse(ok)
        self.assertIn("too thin", why)

    def test_the_four_probe_species_land_where_the_live_run_put_them(self):
        """Pinned against the real 2026-08-16 probe output, so the checklist
        path cannot regress into the occurrence-facet dead end it replaced.

        The starling is the one that matters: 267,995 Alberta records, and
        `reject` is still the right answer. Occurrence proves presence and
        says nothing whatever about belonging.
        """
        cases = [
            ("Danaus plexippus",   370, 596, ["NATIVE"],     "accept"),
            ("Callipepla gambelii",  0,   0, [],             "reject"),
            ("Sturnus vulgaris", 267995, 15778, ["INTRODUCED"], "reject"),
            ("Apis mellifera",    3671, 451, ["INTRODUCED"], "reject"),
        ]
        for name, ab, sk, means, expected in cases:
            self.assertEqual(self.mod.assess(ab, sk, means)["verdict"],
                             expected, name)

    def test_checklist_values_are_deduplicated(self):
        """The probe returned `['NATIVE'] * 9` for one monarch — nine
        checklists agreeing, not nine pieces of evidence. Multiplied by 3,065
        species it is just file bloat."""
        import inspect
        src = inspect.getsource(self.mod.establishment_from_checklists)
        self.assertIn("sorted(out)", src)
        self.assertIn("out = set()", src)

    def test_disagreeing_checklists_go_to_a_human(self):
        """One checklist saying native and another saying introduced is a
        real disagreement between sources. The first cut resolved it silently
        by whichever test fired first."""
        a = self.mod.assess(500, 200, ["NATIVE", "INTRODUCED"])
        self.assertEqual(a["origin"], "conflicted")
        self.assertEqual(a["verdict"], "review")
        ok, why = _ingest.nativity_verdict(
            {"ab_records": 500, "sk_records": 200, "origin": "conflicted"})
        self.assertFalse(ok)
        self.assertIn("disagree", why)

    def test_a_well_recorded_species_passes(self):
        ok, _ = _ingest.nativity_verdict(
            {"ab_records": 400, "sk_records": 120, "origin": "unstated"})
        self.assertTrue(ok)

    def test_the_floor_is_the_one_the_catalogue_already_uses(self):
        """A module does not own a threshold another module already owns. If
        these drift, a species is 'present enough' for one feature and not the
        other, and nobody finds it for a year."""
        from src.ecoregion_ranges import MIN_RECORDS
        self.assertEqual(_ingest._occurrence_floor(), MIN_RECORDS)

    def test_a_missing_fetch_stands_the_gate_down_rather_than_binning_all(self):
        """The fetch needs egress this repo does not have. A missing
        measurement is not evidence of absence (P9) — with no file the gate
        must fall back to V2.60 behaviour, not reject the catalogue."""
        self.assertEqual(_ingest._nativity(), {})
        out = _ingest.review([{
            "plant": "Wild Bergamot", "fauna": "Newus specius",
            "relationship": "nectar", "_taxon": "bee", "source": "globi",
            "notes": "GloBI flowersVisitedBy"}])
        self.assertEqual(len(out["kept"]), 1, out["rejected"])

    def test_the_gate_actually_fires_when_the_fetch_has_run(self):
        """The one that matters, and the one nothing else here can prove.

        Every other test above exercises `nativity_verdict` in isolation.
        This drives the real `review()` with a real nativity file on disk, so
        a gate that is written but never wired — which is exactly how V2.59
        shipped `fruit_food` on conifers — cannot pass.
        """
        import json
        import shutil
        path = os.path.join(_ROOT, "data", "fetched", "fauna_nativity.json")
        backup = path + ".testbak"
        existed = os.path.exists(path)
        if existed:
            shutil.copy2(path, backup)
        try:
            with open(path, "w", encoding="utf-8") as fh:
                json.dump({
                    "Goodus specius": {"ab_records": 400, "sk_records": 90,
                                       "origin": "unstated"},
                    "Alienus specius": {"ab_records": 0, "sk_records": 0,
                                        "origin": "unstated"},
                    "Introducus specius": {"ab_records": 5000,
                                           "sk_records": 900,
                                           "origin": "introduced"},
                }, fh)
            cands = [
                {"plant": "Wild Bergamot", "fauna": name,
                 "relationship": "nectar", "_taxon": "bee", "source": "globi",
                 "notes": "GloBI flowersVisitedBy"}
                for name in ("Goodus specius", "Alienus specius",
                             "Introducus specius", "Unmeasured specius")
            ]
            out = _ingest.review(cands)
            self.assertEqual([k["fauna"] for k in out["kept"]],
                             ["Goodus specius"])
            reasons = " ".join(out["rejected"])
            for expect in ("no georeferenced records", "introduced",
                           "nativity fetch not run"):
                self.assertIn(expect, reasons)
        finally:
            os.remove(path)
            if existed:
                shutil.move(backup, path)

    def test_an_animal_already_in_the_catalogue_is_not_re_litigated(self):
        """Its nativity was decided when the row was authored. Overruling a
        human on occurrence counts — which cannot tell native from merely
        present — would be the gate exceeding what it can measure."""
        import json
        import shutil
        path = os.path.join(_ROOT, "data", "fetched", "fauna_nativity.json")
        backup = path + ".testbak"
        existed = os.path.exists(path)
        if existed:
            shutil.copy2(path, backup)
        try:
            # Deliberately damning data for a species the catalogue holds.
            with open(path, "w", encoding="utf-8") as fh:
                json.dump({"Bombus huntii": {"ab_records": 0, "sk_records": 0,
                                             "origin": "introduced"}}, fh)
            out = _ingest.review([{
                "plant": "Showy Milkweed", "fauna": "Bombus huntii",
                "relationship": "pollen", "_taxon": "bee", "source": "globi",
                "notes": "GloBI pollinatedBy"}])
            self.assertEqual(len(out["kept"]), 1, out["rejected"])
        finally:
            os.remove(path)
            if existed:
                shutil.move(backup, path)

    def test_the_province_boxes_hold_the_cities_they_should(self):
        """Both provinces are surveyed rectangles, which is why a box works at
        all. Pinned against real coordinates so a typo in a bound is caught."""
        inside = {
            "AB": [("Edmonton", 53.55, -113.49), ("Calgary", 51.05, -114.07),
                   ("Fort McMurray", 56.73, -111.38)],
            "SK": [("Regina", 50.45, -104.62), ("Saskatoon", 52.13, -106.67),
                   ("Prince Albert", 53.20, -105.75)],
        }
        for code, cities in inside.items():
            lo_lat, hi_lat, lo_lng, hi_lng = self.mod.PROVINCE_BOXES[code]
            for name, lat, lng in cities:
                self.assertTrue(lo_lat <= lat <= hi_lat and
                                lo_lng <= lng <= hi_lng,
                                f"{name} should be inside {code}")

    def test_the_boxes_exclude_the_neighbours(self):
        outside = [("Vancouver", 49.28, -123.12), ("Winnipeg", 49.90, -97.14),
                   ("Toronto", 43.65, -79.38)]
        for code in ("AB", "SK"):
            lo_lat, hi_lat, lo_lng, hi_lng = self.mod.PROVINCE_BOXES[code]
            for name, lat, lng in outside:
                self.assertFalse(lo_lat <= lat <= hi_lat and
                                 lo_lng <= lng <= hi_lng,
                                 f"{name} must not be inside {code}")

    def test_the_two_boxes_meet_at_the_shared_meridian(self):
        """AB's east edge and SK's west edge are the same line, 110°W. A gap
        would lose every record on the border; an overlap would double-count."""
        self.assertEqual(self.mod.PROVINCE_BOXES["AB"][3],
                         self.mod.PROVINCE_BOXES["SK"][2])

    def test_assess_keeps_presence_and_origin_apart(self):
        """Occurrence is not nativity, and the output must never collapse the
        two. `origin: unstated` is the common case and is not a claim of
        nativeness (P9 — absent is not estimated)."""
        a = self.mod.assess(200, 30, [])
        self.assertEqual(a["provinces"], "AB,SK")
        self.assertEqual(a["origin"], "unstated")
        self.assertEqual(a["verdict"], "review")

    def test_a_disqualifying_establishment_value_is_matched_loosely(self):
        """GBIF carries both the Darwin Core vocabulary and publisher free
        text, so 'INTRODUCED', 'introduced', and 'Introduced (naturalised)'
        all have to land the same way."""
        for value in ("INTRODUCED", "introduced", "Introduced (naturalised)",
                      "INVASIVE", "MANAGED"):
            self.assertEqual(self.mod.assess(500, 10, [value])["verdict"],
                             "reject", value)


class TestTheFetcherReadsTheRealCatalogue(unittest.TestCase):
    def test_it_finds_the_plants_fauna_and_existing_edges(self):
        plants, fauna, existing = _fetch.load_catalogue()
        self.assertGreater(len(plants), 400)
        self.assertGreater(len(fauna), 100)
        self.assertGreater(len(existing), 300)
        self.assertTrue(all(p.get("scientific_name") for p in plants))


if __name__ == "__main__":
    unittest.main()

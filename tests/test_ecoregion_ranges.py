"""
tests/test_ecoregion_ranges.py — range derived from evidence, not from a guess.

User feedback: *"Saskatoon Berry shows up for mixed grassland and moist mixed
grassland but fails to show up for aspen parkland which it is a chief plant
of."*

They were right, and the cause was not one bad row. The catalogue's ecoregion
tags were generated heuristically and never sourced: ``moist_mixedgrass`` sits
on 246 of 434 plants and ``aspen_parkland`` on 136, in an Alberta-first app
centred on Edmonton, and 39 native trees and shrubs carry no parkland tag at
all.

The replacement derives range from georeferenced occurrence records and keeps
the count and a confidence band beside every claim (P9). The GBIF fetch itself
runs at dev time on a machine with open egress — the project's cloud sessions
get 403 CONNECT for ``api.gbif.org`` — so the *logic* lives in
``src/ecoregion_ranges.py`` with the records injected, which is the only way
the interesting behaviour (two records versus three) is testable at all.
"""

import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_TMP_DIR = tempfile.mkdtemp(prefix="permadesign_ecoranges_")
import src.db.plants as _plants_mod                       # noqa: E402
_plants_mod._DATA_DIR = _TMP_DIR
_plants_mod._DB_PATH = os.path.join(_TMP_DIR, "t.db")

from src import ecoregion_ranges as R                     # noqa: E402


# Fixture geography: a lookup that does not need the shipped polygons, so the
# threshold rules are tested on their own rather than through Alberta.
def _fake_lookup(lat, lng):
    if lat >= 100:                      # the overlap band
        return ["aspen_parkland", "western_alberta_upland"]
    if lat >= 50:
        return ["aspen_parkland"]
    if lat >= 10:
        return ["mid_boreal_uplands"]
    return []                            # outside coverage


#: True while ``data/plant_ecoregions.json`` is keyed to a retired vocabulary —
#: the window between adopting a new polygon layer and re-running
#: ``scripts/seed_ecoregion_ranges.py`` against it.
#:
#: A **precondition**, not a bug, and it has exactly one alarm:
#: ``TestTheShippedEnvelope.test_every_derived_key_is_a_real_geographic_
#: ecoregion`` stays RED for the whole window and names the command. Tests that
#: merely need *some* species to have a live range skip on this instead, so one
#: stale input reports as one failure rather than a dozen — a suite where a
#: dozen reds are "expected" is a suite nobody reads.
#:
#: The predicate lives in ``src`` rather than here because it is a real
#: question about app state, not a test convenience: during the window the app
#: shows ranges that are not merely missing but *wrong*. See ``stale_keys``.
_STALE_RANGES = bool(R.stale_keys())
_STALE_WHY = ("data/plant_ecoregions.json is still keyed to the retired "
              "ecoregion vocabulary. Re-run:  python "
              "scripts/seed_ecoregion_ranges.py")


def _points(**counts):
    """``_points(aspen_parkland=5)`` → five points inside that region."""
    lat_for = {"aspen_parkland": 60.0, "mid_boreal_uplands": 20.0,
               "nowhere": 0.0, "overlap": 100.0}
    out = []
    for region, n in counts.items():
        out.extend([(lat_for[region], 0.0)] * n)
    return out


class TestTheThreshold(unittest.TestCase):
    """Where the line sits, and why it sits there."""

    def test_three_records_is_a_claim(self):
        rows = R.ranges_for_species(_points(aspen_parkland=3),
                                    lookup=_fake_lookup)
        self.assertEqual([r["ecoregion"] for r in rows], ["aspen_parkland"])
        self.assertEqual(rows[0]["occurrences"], 3)

    def test_two_records_is_a_coincidence(self):
        """A misidentified herbarium sheet plus a garden escape will do two."""
        self.assertEqual(
            R.ranges_for_species(_points(aspen_parkland=2), lookup=_fake_lookup),
            [])

    def test_what_fell_short_is_reported_not_discarded(self):
        """A species sitting at two records somewhere is the case a human
        should look at. A pipeline that only prints what it kept cannot be
        audited."""
        pts = _points(aspen_parkland=40, mid_boreal_uplands=2)
        rows = R.ranges_for_species(pts, lookup=_fake_lookup)
        thin = R.dropped_regions(pts, lookup=_fake_lookup)
        self.assertEqual([r["ecoregion"] for r in rows], ["aspen_parkland"])
        self.assertEqual(thin, {"mid_boreal_uplands": 2})

    def test_the_threshold_is_adjustable_without_editing_the_rule(self):
        pts = _points(aspen_parkland=2)
        self.assertEqual(R.ranges_for_species(pts, lookup=_fake_lookup), [])
        rows = R.ranges_for_species(pts, lookup=_fake_lookup, min_records=1)
        self.assertEqual(rows[0]["occurrences"], 2)


class TestConfidence(unittest.TestCase):
    """Three records and three hundred must not read the same."""

    def test_the_bands(self):
        self.assertEqual(R.confidence_for(500), "high")
        self.assertEqual(R.confidence_for(20), "high")
        self.assertEqual(R.confidence_for(19), "medium")
        self.assertEqual(R.confidence_for(8), "medium")
        self.assertEqual(R.confidence_for(7), "low")
        self.assertEqual(R.confidence_for(3), "low")

    def test_below_the_floor_has_no_band(self):
        self.assertEqual(R.confidence_for(2), "")
        self.assertEqual(R.confidence_for(0), "")

    def test_every_derived_row_carries_one(self):
        rows = R.ranges_for_species(
            _points(aspen_parkland=300, mid_boreal_uplands=4),
            lookup=_fake_lookup)
        self.assertEqual([(r["ecoregion"], r["confidence"]) for r in rows],
                         [("aspen_parkland", "high"),
                          ("mid_boreal_uplands", "low")])

    def test_the_bands_are_ordered_and_named_consistently(self):
        labels = [label for _floor, label in R.CONFIDENCE_BANDS]
        self.assertEqual(labels, list(R.CONFIDENCE_ORDER))
        floors = [floor for floor, _label in R.CONFIDENCE_BANDS]
        self.assertEqual(floors, sorted(floors, reverse=True),
                         "bands must descend, or confidence_for short-circuits "
                         "on the wrong one")


class TestCountingPoints(unittest.TestCase):
    def test_a_lookup_returning_two_regions_counts_for_both(self):
        """Whatever the injected lookup returns is counted, all of it.

        This is about the counting rule, not about geometry: the *caller*
        decides what a point is in. With the real polygons that is now
        containment only (see TestARecordIsEvidenceAboutOnePlace) — the ELC
        regions tile, so two answers means the lookup was asked a different
        question, and answering it is the caller's business.
        """
        rows = R.ranges_for_species(_points(overlap=10), lookup=_fake_lookup)
        self.assertEqual({r["ecoregion"] for r in rows},
                         {"aspen_parkland", "western_alberta_upland"})
        self.assertTrue(all(r["occurrences"] == 10 for r in rows))

    def test_records_outside_every_region_are_ignored(self):
        rows = R.ranges_for_species(
            _points(aspen_parkland=5, nowhere=900), lookup=_fake_lookup)
        self.assertEqual([r["ecoregion"] for r in rows], ["aspen_parkland"])

    def test_commonest_first_then_alphabetical(self):
        """A stable order means a re-run's diff is real change in GBIF, not
        dict ordering."""
        pts = (_points(aspen_parkland=5) + _points(mid_boreal_uplands=5)
               + _points(overlap=5))
        rows = R.ranges_for_species(pts, lookup=_fake_lookup)
        counts = [r["occurrences"] for r in rows]
        self.assertEqual(counts, sorted(counts, reverse=True))
        tied = [r["ecoregion"] for r in rows if r["occurrences"] == 5]
        self.assertEqual(tied, sorted(tied))

    def test_junk_points_do_not_crash_the_run(self):
        """One malformed record must not lose a whole species' range."""
        pts = [None, (), (None, None), ("x", "y"), (60.0, 0.0),
               (60.0, 0.0), (60.0, 0.0)]
        rows = R.ranges_for_species(pts, lookup=_fake_lookup)
        self.assertEqual(rows[0]["occurrences"], 3)

    def test_no_records_is_no_claim(self):
        self.assertEqual(R.ranges_for_species([], lookup=_fake_lookup), [])


class TestTheShippedFile(unittest.TestCase):
    def test_the_envelope_carries_run_level_provenance(self):
        """'confidence: high' means nothing without knowing what was counted,
        when, and against what threshold."""
        doc = R.build_document({"Amelanchier alnifolia": []},
                               source="GBIF, retrieved 2026-08-02",
                               generated="2026-08-02")
        self.assertEqual(doc["version"], R.FILE_VERSION)
        self.assertEqual(doc["generated"], "2026-08-02")
        self.assertIn("GBIF", doc["source"])
        self.assertEqual(doc["min_records"], R.MIN_RECORDS)

    def test_species_are_sorted_so_a_rerun_diffs_cleanly(self):
        doc = R.build_document({"Zizia aurea": [], "Amelanchier alnifolia": []},
                               source="x", generated="y")
        self.assertEqual(list(doc["species"]),
                         ["Amelanchier alnifolia", "Zizia aurea"])

    def test_it_round_trips(self):
        rows = R.ranges_for_species(_points(aspen_parkland=30),
                                    lookup=_fake_lookup)
        doc = R.build_document({"Amelanchier alnifolia": rows},
                               source="x", generated="y")
        back = R.parse_document(json.loads(json.dumps(doc)))
        self.assertEqual(back["Amelanchier alnifolia"], rows)

    def test_a_missing_file_means_nothing_derived_yet(self):
        """Not an error, ever: the derivation is an optional dev-time run, and
        failing here would take the catalogue down over a file whose whole job
        is to be optional."""
        for junk in (None, {}, [], {"species": "nope"}, {"species": {}}):
            self.assertEqual(R.parse_document(junk), {})

    def test_malformed_rows_are_skipped_not_fatal(self):
        back = R.parse_document({"species": {
            "Good sp.": [{"ecoregion": "aspen_parkland", "occurrences": 9,
                          "confidence": "medium"}],
            "Bad sp.":  ["not a dict", {"no_ecoregion": 1}],
            "Odd sp.":  [{"ecoregion": "aspen_parkland",
                          "occurrences": "many", "confidence": "certain"}],
        }})
        self.assertIn("Good sp.", back)
        self.assertNotIn("Bad sp.", back)
        # An unusable count and an invented band degrade to the honest floor.
        self.assertEqual(back["Odd sp."][0]["occurrences"], 0)
        self.assertEqual(back["Odd sp."][0]["confidence"], "low")

    def test_a_missing_confidence_is_computed_from_the_count(self):
        back = R.parse_document({"species": {
            "Sp.": [{"ecoregion": "aspen_parkland", "occurrences": 42}]}})
        self.assertEqual(back["Sp."][0]["confidence"], "high")


class TestOnlyGeographyIsDerivable(unittest.TestCase):
    """No coordinate can tell you a species grows in wet ground."""

    def test_the_moisture_niches_are_not_in_the_polygon_vocabulary(self):
        from src.ecoregion import geographic_keys, MOISTURE_NICHES
        geo = set(geographic_keys())
        for key, _name, _where in MOISTURE_NICHES:
            self.assertNotIn(key, geo)

    def test_a_real_lookup_never_yields_one(self):
        from src.ecoregion import lookup_ecoregions, is_moisture_niche
        for lat, lng in [(53.55, -113.49), (52.13, -106.67), (49.7, -112.8),
                         (53.0, -114.8), (56.7, -111.4)]:
            for key in lookup_ecoregions(lat, lng):
                self.assertFalse(is_moisture_niche(key))


class TestTheDerivationScript(unittest.TestCase):
    """The script's own logic, with the network replaced by a stub."""

    # The script runs against the SHIPPED polygons (no lookup injection), so
    # these use real coordinates — which also makes them a check that the two
    # halves of the pipeline agree about Alberta.
    _EDMONTON     = (53.55, -113.49)     # aspen_parkland
    # V2.68: was commented `mid_boreal_uplands`, one of the six hand-traced
    # regions. Under the surveyed layer this point sits INSIDE Wabasca Lowland
    # and within 5 km of Mid-Boreal Uplands.
    #
    # V2.75: it therefore derives as Wabasca Lowland alone. The paragraph that
    # stood here argued the second key was the P9 answer — "a yard on a
    # boundary is genuinely in both, and saying so" — and that is still true
    # *of a yard*. It is not true of a herbarium sheet. Site detection keeps
    # the buffer; range derivation counts containment, because a record is
    # evidence about the place it was made and nowhere else. Same coordinate,
    # two questions, two right answers.
    _FORT_MCMURRAY = (56.73, -111.38)    # in wabasca_lowland, near mid_boreal_uplands

    def test_it_drives_the_derivation_per_species(self):
        from scripts.seed_ecoregion_ranges import derive

        def fake_fetch(name, *, verbose=False):
            return {
                # Thirty parkland records and two boreal ones: the first is a
                # claim, the second is reported as short of the threshold.
                "Amelanchier alnifolia": ([self._EDMONTON] * 30
                                          + [self._FORT_MCMURRAY] * 2),
                "Nothing recordedii": [],
            }.get(name, [])

        ranges, dropped, none, failed = derive(
            ["Amelanchier alnifolia", "Nothing recordedii"],
            min_records=3, verbose=False, fetch=fake_fetch, throttle=_NoWait())
        self.assertEqual(failed, [])
        self.assertEqual(list(ranges), ["Amelanchier alnifolia"])
        self.assertEqual(ranges["Amelanchier alnifolia"],
                         [{"ecoregion": "aspen_parkland", "occurrences": 30,
                           "confidence": "high"}])
        # The near-miss report names the region the two records are IN, and
        # not the one they are merely near (V2.75). Before the buffer was
        # taken out of derivation this read `{"wabasca_lowland": 2,
        # "mid_boreal_uplands": 2}` — two records producing four.
        self.assertEqual(dropped["Amelanchier alnifolia"],
                         {"wabasca_lowland": 2})
        self.assertEqual(none, ["Nothing recordedii"])

    def test_the_saskatoon_berry_case_end_to_end(self):
        """The item that started this: parkland records must produce a
        parkland tag. It never could before, because range was a guess."""
        from scripts.seed_ecoregion_ranges import derive
        ranges, _dropped, _none, _failed = derive(
            ["Amelanchier alnifolia"], min_records=3, verbose=False,
            fetch=lambda name, *, verbose=False, throttle=None:
                [self._EDMONTON] * 312,
            throttle=_NoWait())
        keys = [r["ecoregion"] for r in ranges["Amelanchier alnifolia"]]
        self.assertIn("aspen_parkland", keys)

    def test_a_species_with_nothing_in_range_writes_no_rows(self):
        """No records inside the polygons is a real finding, and it writes
        nothing — so the species keeps the tags it already had. (The *failure*
        case, which must not look like this, is in
        TestRateLimitingIsNotAbsence below.)"""
        from scripts.seed_ecoregion_ranges import derive
        ranges, _dropped, none, _failed = derive(
            ["Unreachable sp."], min_records=3, verbose=False,
            fetch=lambda name, *, verbose=False, throttle=None: [],
            throttle=_NoWait())
        self.assertEqual(ranges, {})
        self.assertEqual(none, ["Unreachable sp."])

    def test_it_reads_the_real_catalogue(self):
        from scripts.seed_ecoregion_ranges import catalogue_species
        names = catalogue_species()
        self.assertGreater(len(names), 400)
        self.assertIn("Amelanchier alnifolia", names)
        self.assertEqual(names, sorted(names))
        self.assertEqual(len(names), len(set(names)))

    def test_cultivated_records_are_excluded(self):
        """A botanical garden is not an ecoregion."""
        from scripts.seed_ecoregion_ranges import EXCLUDED_BASES
        self.assertIn("LIVING_SPECIMEN", EXCLUDED_BASES)


if __name__ == "__main__":
    unittest.main()


class TestSeedingIntoTheCatalogue(unittest.TestCase):
    """The DB half: derived rows override the heuristic column, moisture
    niches survive, and a species the derivation missed keeps what it had."""

    _FIXTURE = {
        "version": 1, "generated": "2026-08-02", "min_records": 3,
        "source": "GBIF occurrence search, retrieved 2026-08-02",
        "species": {
            "Amelanchier alnifolia": [
                {"ecoregion": "aspen_parkland", "occurrences": 312,
                 "confidence": "high"},
                # V2.68: was `boreal_mixedwood`, one of the six hand-traced
                # regions. It survived here as a fixture value for a whole
                # increment after the survey retired the key — and the seeder
                # was rejecting it correctly the entire time, by exactly the
                # rule the "atlantis" case below exists to prove. A fixture
                # that names a dead key tests the rejection path twice and the
                # acceptance path never.
                {"ecoregion": "mid_boreal_uplands", "occurrences": 44,
                 "confidence": "high"},
            ],
            # A key no polygon defines — must never reach the table, or it
            # would be a row no filter can select.
            "Bogus sp.": [{"ecoregion": "atlantis", "occurrences": 99,
                           "confidence": "high"}],
        },
    }

    @classmethod
    def setUpClass(cls):
        import json as _json
        # Point the seeder at a temp file rather than writing the fixture into
        # data/ — a test that leaves a derived-looking file in the repo is one
        # crashed run away from committing fake ranges.
        cls._real_path = _plants_mod._ECOREGION_RANGES_PATH
        cls._path = os.path.join(_TMP_DIR, "plant_ecoregions.json")
        with open(cls._path, "w", encoding="utf-8") as f:
            _json.dump(cls._FIXTURE, f)
        _plants_mod._ECOREGION_RANGES_PATH = cls._path
        if os.path.exists(_plants_mod._DB_PATH):
            os.remove(_plants_mod._DB_PATH)
        _plants_mod.invalidate_plant_cache()
        _plants_mod.init_db()
        cls._plants = _plants_mod.get_all_plants()

    @classmethod
    def tearDownClass(cls):
        _plants_mod._ECOREGION_RANGES_PATH = cls._real_path
        if os.path.exists(_plants_mod._DB_PATH):
            os.remove(_plants_mod._DB_PATH)
        _plants_mod.invalidate_plant_cache()

    def test_the_repo_is_not_carrying_a_fixture(self):
        """Guard on this very file: the shipped data/plant_ecoregions.json must
        only ever be real derived output, never a test's fixture."""
        import json as _json
        if not os.path.exists(self._real_path):
            return                       # not derived yet — the normal state
        with open(self._real_path, encoding="utf-8") as f:
            shipped = _json.load(f)
        self.assertNotIn("Bogus sp.", shipped.get("species", {}))

    def _plant(self, scientific):
        for p in self._plants:
            if (p.get("scientific_name") or "").strip() == scientific:
                return p
        self.fail(f"{scientific} not in the catalogue")

    def test_the_table_exists_at_schema_v59(self):
        conn = _plants_mod.get_connection()
        try:
            names = [r[0] for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'")]
        finally:
            conn.close()
        self.assertIn("plant_ecoregions", names)
        self.assertGreaterEqual(_plants_mod._SCHEMA_VERSION, 59)

    def test_saskatoon_berry_finally_says_parkland(self):
        """The reported bug, from the shipped path rather than a unit test."""
        p = self._plant("Amelanchier alnifolia")
        self.assertIn("aspen_parkland", p["ecoregion"].split(","))

    def test_the_derived_range_replaces_the_unsourced_one(self):
        p = self._plant("Amelanchier alnifolia")
        self.assertEqual(p["ecoregion"].split(","),
                         ["aspen_parkland", "mid_boreal_uplands"])

    def test_the_evidence_travels_with_the_claim(self):
        p = self._plant("Amelanchier alnifolia")
        rows = p["ecoregion_evidence"]
        self.assertEqual([r["ecoregion"] for r in rows],
                         ["aspen_parkland", "mid_boreal_uplands"])
        self.assertEqual(rows[0]["occurrences"], 312)
        self.assertEqual(rows[0]["confidence"], "high")
        self.assertIn("GBIF", rows[0]["source"])

    def test_the_frozen_api_alias_moves_with_it(self):
        """``ab_ecoregion`` is part of the agent-API contract (schema v42)."""
        p = self._plant("Amelanchier alnifolia")
        self.assertEqual(p["ab_ecoregion"], p["ecoregion"])

    def test_a_species_with_no_derived_rows_keeps_its_tags(self):
        """The catalogue must never get *smaller* because a download has not
        been run for every species."""
        untouched = [p for p in self._plants
                     if not p.get("ecoregion_evidence") and p.get("ecoregion")]
        self.assertGreater(len(untouched), 300)

    def test_a_key_outside_the_polygon_vocabulary_is_dropped(self):
        conn = _plants_mod.get_connection()
        try:
            n = conn.execute("SELECT COUNT(*) FROM plant_ecoregions "
                             "WHERE ecoregion = 'atlantis'").fetchone()[0]
        finally:
            conn.close()
        self.assertEqual(n, 0)

    def test_moisture_niches_survive_a_derived_override(self):
        """A coordinate cannot assert 'wet ground', so the derivation must not
        be able to delete it either."""
        from src.ecoregion import is_moisture_niche
        conn = _plants_mod.get_connection()
        try:
            row = conn.execute(
                "SELECT id, scientific_name, ecoregion FROM plants "
                "WHERE ecoregion LIKE '%riparian%' LIMIT 1").fetchone()
            self.assertIsNotNone(row, "no riparian plant to test with")
            conn.execute(
                "INSERT OR REPLACE INTO plant_ecoregions "
                "(plant_id, ecoregion, occurrences, confidence, source) "
                "VALUES (?, 'aspen_parkland', 50, 'high', 'test')", (row["id"],))
            conn.commit()
        finally:
            conn.close()
        _plants_mod.invalidate_plant_cache()
        p = self._plant_fresh(row["scientific_name"])
        tags = p["ecoregion"].split(",")
        self.assertIn("aspen_parkland", tags)
        self.assertIn("riparian", tags)
        self.assertTrue(any(is_moisture_niche(t) for t in tags))

    def _plant_fresh(self, scientific):
        for p in _plants_mod.get_all_plants():
            if (p.get("scientific_name") or "").strip() == scientific:
                return p
        self.fail(f"{scientific} not in the catalogue")


    def test_the_filter_finds_a_species_by_its_DERIVED_range(self):
        """The bug surviving its own fix, guarded.

        The read side overlays derived ranges onto ``ecoregion`` *after* the
        query runs, so a filter that read only the column would still hide the
        species the derivation just corrected — Saskatoon Berry would keep its
        parkland tag in the plant card and stay missing from the parkland
        filter, which is exactly what the user reported.
        """
        hits = _plants_mod.search_plants(ecoregion=["aspen_parkland"])
        names = {h["common_name"] for h in hits}
        self.assertIn("Saskatoon Berry", names)

    def test_the_filter_still_reads_the_column_for_undeivided_species(self):
        """Species the derivation has not covered must keep filtering on their
        existing tags — the parkland list must not shrink to one plant.

        V2.68: was `moist_mixedgrass`, which the survey retired. Those 245
        species now carry `zone_prairies` instead, because the measurement
        could not put them in one ecoregion (39% Moist Mixed Grassland, 36%
        Aspen Parkland) but could put 92% of them in one ecozone. That is the
        heuristic tag resting at the level its evidence supports, and it is
        the whole reason the ecozone level exists."""
        hits = _plants_mod.search_plants(ecoregion=["zone_prairies"])
        self.assertGreater(len(hits), 100)

    def test_moisture_niches_still_filter(self):
        hits = _plants_mod.search_plants(ecoregion=["riparian"])
        self.assertGreater(len(hits), 50)

    def test_the_legacy_api_parameter_name_takes_the_same_path(self):
        """``ab_ecoregion`` is part of the frozen agent-API contract (v42)."""
        a = _plants_mod.search_plants(ecoregion=["aspen_parkland"])
        b = _plants_mod.search_plants(ab_ecoregion=["aspen_parkland"])
        self.assertEqual({p["id"] for p in a}, {p["id"] for p in b})


class TestTheShippedEnvelope(unittest.TestCase):
    """The shipped file, in whichever state it is in.

    It ships empty until the GBIF run happens, and populated afterwards. These
    have to hold for BOTH — the first version asserted the file was empty,
    which broke the moment the derivation actually ran. A test that only passes
    while a feature is unfinished is worse than no test: it fails as a reward
    for doing the work.
    """

    def _shipped(self):
        import pathlib
        path = (pathlib.Path(__file__).resolve().parent.parent
                / "data" / "plant_ecoregions.json")
        self.assertTrue(path.exists(), "the envelope should ship")
        with open(path, encoding="utf-8") as f:
            return json.load(f)

    def test_it_is_a_valid_document(self):
        doc = self._shipped()
        self.assertEqual(doc["version"], R.FILE_VERSION)
        self.assertEqual(doc["min_records"], R.MIN_RECORDS)
        self.assertIsInstance(doc["species"], dict)

    def test_an_empty_envelope_parses_to_nothing_rather_than_failing(self):
        """The 'not derived yet' state must be a no-op, not a crash — a missing
        or empty file means every species keeps the tags it already had."""
        self.assertEqual(R.parse_document({"version": 1, "species": {}}), {})
        self.assertEqual(R.parse_document({}), {})

    def test_the_shipped_file_parses_to_whatever_it_holds(self):
        parsed = R.parse_document(self._shipped())
        self.assertEqual(set(parsed), set(self._shipped()["species"]))
        for name, rows in parsed.items():
            self.assertTrue(rows, f"{name} has an empty row list")
            for row in rows:
                self.assertIn(row["confidence"], R.CONFIDENCE_ORDER)
                self.assertGreaterEqual(row["occurrences"], 0)

    def test_every_derived_key_is_a_real_geographic_ecoregion(self):
        """A key outside the polygon vocabulary would be a row no filter can
        select — and riparian/wet_meadow must never appear, since no coordinate
        can assert wet ground.

        **This is the alarm for a stale derivation, and it is meant to stay red
        through the whole window** where the polygons have moved and the ranges
        have not yet been re-derived (see `_shipped_ranges_are_stale`). It is
        deliberately the ONLY red one: everything downstream skips, so a stale
        input reports as a single actionable failure rather than a dozen reds
        that train the reader to stop looking.

        Do not translate the old keys onto the new regions to clear it. Fanning
        one `boreal_mixedwood` record across nine Boreal Plains ecoregions
        asserts nine occurrences where the evidence supports one, which is P9
        failing through the back door. Re-derive."""
        from src.ecoregion import geographic_keys
        valid = set(geographic_keys())
        for name, rows in R.parse_document(self._shipped()).items():
            for row in rows:
                self.assertIn(row["ecoregion"], valid,
                              f"{name}: {row['ecoregion']!r} is not a region "
                              f"any polygon defines. {_STALE_WHY}")

    def test_a_populated_file_must_carry_its_provenance(self):
        """The moment it has species in it, it has to say where they came from
        and when — 'confidence: high' means nothing without that."""
        doc = self._shipped()
        if doc["species"]:
            self.assertTrue(doc["source"], "derived ranges with no source")
            self.assertTrue(doc["generated"], "derived ranges with no date")


class TestRateLimitingIsNotAbsence(unittest.TestCase):
    """The first real run's failure mode, guarded.

    GBIF answered HTTP 429 after 228 species and the script recorded each
    throttled species as having "no georeferenced records" — which reads as
    *this plant grows nowhere*. That is the exact class of unsourced claim this
    pipeline exists to remove, arriving through the back door.
    """

    def test_a_failed_fetch_is_reported_not_recorded_as_empty(self):
        from scripts.seed_ecoregion_ranges import derive, FetchFailed

        def flaky(name, *, verbose=False, throttle=None):
            if name == "Throttled sp.":
                raise FetchFailed("HTTP 429")
            return [(53.55, -113.49)] * 20

        ranges, _dropped, none, failed = derive(
            ["Good sp.", "Throttled sp."], min_records=3, verbose=False,
            fetch=flaky, throttle=_NoWait())
        self.assertEqual([n for n, _why in failed], ["Throttled sp."])
        self.assertNotIn("Throttled sp.", none,
                         "a throttle was recorded as 'no records' — that is "
                         "the bug this test exists for")
        self.assertNotIn("Throttled sp.", ranges)
        self.assertIn("Good sp.", ranges)

    def test_a_genuine_absence_is_still_reported_as_one(self):
        from scripts.seed_ecoregion_ranges import derive
        _ranges, _dropped, none, failed = derive(
            ["Empty sp."], min_records=3, verbose=False,
            fetch=lambda name, *, verbose=False, throttle=None: [],
            throttle=_NoWait())
        self.assertEqual(none, ["Empty sp."])
        self.assertEqual(failed, [])

    def test_the_throttle_slows_down_and_stays_slow(self):
        """A 429 means the *sustained* rate was too high, so returning to the
        old pace would just earn another one."""
        from scripts.seed_ecoregion_ranges import _Throttle, MAX_SLEEP
        t = _Throttle(1.0)
        t.rate_limited()
        self.assertGreater(t.sleep, 1.0)
        first = t.sleep
        t.rate_limited()
        self.assertGreater(t.sleep, first)
        for _ in range(50):
            t.rate_limited()
        self.assertLessEqual(t.sleep, MAX_SLEEP)
        self.assertEqual(t.limited, 52)

    def test_the_query_is_bounded_to_the_polygons(self):
        """Everything outside the polygons is discarded downstream, so asking
        GBIF for it was pure cost — and it was most of the cost."""
        from scripts.seed_ecoregion_ranges import polygon_bbox
        from src.ecoregion import _load_features
        lat_min, lat_max, lng_min, lng_max = polygon_bbox()
        self.assertLess(lat_min, lat_max)
        self.assertLess(lng_min, lng_max)
        # Walked recursively rather than as list-of-rings: the surveyed layer
        # is full of MultiPolygons, which nest one level deeper, and this test
        # carried the same assumption as the code it was guarding. A guard
        # written against the shape of the old data is not a guard.
        def positions(node):
            if (isinstance(node, (list, tuple)) and len(node) >= 2
                    and all(isinstance(v, (int, float)) for v in node[:2])):
                yield float(node[0]), float(node[1])
                return
            if isinstance(node, (list, tuple)):
                for child in node:
                    yield from positions(child)

        checked = 0
        for feature in _load_features():
            for lng, lat in positions(feature["geometry"]["coordinates"]):
                checked += 1
                self.assertGreaterEqual(lat, lat_min)
                self.assertLessEqual(lat, lat_max)
                self.assertGreaterEqual(lng, lng_min)
                self.assertLessEqual(lng, lng_max)
        self.assertGreater(checked, 0, "no coordinates were checked at all")

    def test_the_bbox_is_padded_so_a_boundary_record_is_not_lost(self):
        from scripts.seed_ecoregion_ranges import polygon_bbox
        tight = polygon_bbox(pad=0.0)
        padded = polygon_bbox(pad=0.5)
        self.assertLess(padded[0], tight[0])
        self.assertGreater(padded[1], tight[1])

    def test_resume_skips_what_is_done_and_retries_what_is_not(self):
        """A species with rows is finished. A species with none might have been
        a genuine absence or a rate-limit casualty, and there is no way to tell
        after the fact — so it gets retried, which makes a throttled run
        self-healing."""
        import scripts.seed_ecoregion_ranges as script
        derived = script.load_existing.__doc__
        self.assertIn("Only species with ROWS count as done", derived)
        doc = {"version": 1, "species": {
            "Done sp.": [{"ecoregion": "aspen_parkland", "occurrences": 9,
                          "confidence": "medium"}],
            "Empty sp.": []}}
        parsed = R.parse_document(doc)
        self.assertIn("Done sp.", parsed)
        self.assertNotIn("Empty sp.", parsed)


class _NoWait:
    """A throttle that does not actually sleep, for the tests."""
    sleep = 0.0
    limited = 0

    def wait(self):
        pass

    def rate_limited(self):
        self.limited += 1


class TestTheSuiteStaysOffline(unittest.TestCase):
    """A measured 771 live internet requests per run, needed by nothing.

    Every fetcher in this app degrades gracefully when offline — that is the
    design — so those downloads bought nothing and cost a slow, flaky suite
    that burns a public API's quota. A user on Windows started getting HTTP 429
    back from Open-Meteo during an ordinary test run, which is how it surfaced.
    """

    def test_the_guard_is_installed(self):
        """Also catches the wrong invocation, which is how this was found.

        ``python -m unittest discover -s tests`` makes ``tests/`` the top-level
        directory, so its modules import as top-level names and
        ``tests/__init__.py`` — where the guard lives — never runs. ``-t .``
        keeps ``tests`` a package. A guard that silently does not install is
        worse than no guard, so this fails loudly and says which command.
        """
        import urllib.request
        self.assertNotEqual(
            urllib.request.urlopen.__name__, "urlopen",
            "The offline guard did not install. Run the suite as:\n"
            "    python -m unittest discover -s tests -t .\n"
            "(without -t, tests/__init__.py is never imported). If the "
            "command was right, the guard in tests/__init__.py is gone.")

    def test_reaching_the_internet_raises_offline(self):
        import urllib.error, urllib.request
        with self.assertRaises(urllib.error.URLError):
            urllib.request.urlopen("https://api.open-meteo.com/v1/elevation")

    def test_localhost_and_file_urls_still_work(self):
        """test_web_assets runs its own server; several tests serve fixtures
        from file://. Neither is the internet."""
        import tempfile, urllib.request, pathlib
        with tempfile.NamedTemporaryFile("wb", suffix=".txt", delete=False) as fh:
            fh.write(b"local")
            path = fh.name
        try:
            with urllib.request.urlopen(pathlib.Path(path).as_uri()) as resp:
                self.assertEqual(resp.read(), b"local")
        finally:
            os.unlink(path)

    def test_a_blocked_fetch_looks_like_being_offline(self):
        """URLError, not a bespoke exception — so the code under test takes the
        same path a real offline user takes, rather than a path only the suite
        ever sees."""
        from src.http_utils import http_get_json
        self.assertIsNone(http_get_json("https://api.gbif.org/v1/occurrence/search"))


class TestTheFilterAgreesWithTheCard(unittest.TestCase):
    """A plant returned by the parkland filter must say parkland on its card.

    The first version of the derived-range filter ORed the junction with the
    column, while the read side lets the junction SUPERSEDE the column. So a
    species whose stale tags said parkland but whose occurrence records say
    otherwise came back from the parkland filter showing a range that did not
    include parkland. Reported as a test failure the moment the real GBIF data
    landed, which is the only time it could have shown up.
    """

    @classmethod
    def setUpClass(cls):
        # Against the REAL shipped ranges, not a fixture: the disagreement this
        # class exists for only appears once actual derived data is present.
        # (TestSeedingIntoTheCatalogue tears the DB down after itself, and runs
        # first alphabetically, so this rebuilds one.)
        if os.path.exists(_plants_mod._DB_PATH):
            os.remove(_plants_mod._DB_PATH)
        _plants_mod.invalidate_plant_cache()
        _plants_mod.init_db()

    @classmethod
    def tearDownClass(cls):
        if os.path.exists(_plants_mod._DB_PATH):
            os.remove(_plants_mod._DB_PATH)
        _plants_mod.invalidate_plant_cache()

    @staticmethod
    def _keys_that_match_something():
        """Geographic keys the catalogue can actually answer, right now.

        **Not a hard-coded list, and that is the point.** These two tests
        filtered on `boreal_mixedwood` and `mixedgrass_prairie` for a whole
        increment after the survey retired those keys, and stayed green the
        entire time — because a dead key matches nothing, `for p in []` runs
        no assertions, and `set() | set() == set()`. A test that cannot fail
        is not evidence.

        Reading the live keys off the data means the vocabulary can move again
        without quietly hollowing these out, and the floor below catches the
        case where it moves so far that nothing matches at all.
        """
        from src.ecoregion import geographic_keys

        return [key for key in geographic_keys()
                if _plants_mod.search_plants(ecoregion=[key])]

    @unittest.skipIf(_STALE_RANGES, _STALE_WHY)
    def test_the_catalogue_can_answer_some_region_at_all(self):
        """The floor under the two tests below. If this fails, the tag
        vocabulary and the catalogue have come apart completely."""
        live = self._keys_that_match_something()
        self.assertGreaterEqual(
            len(live), 3,
            "fewer than three of the geographic regions match any plant — "
            "either the tags were cleared without being re-derived, or the "
            "polygon vocabulary moved and nothing followed it")

    def test_every_result_claims_the_region_it_was_found_under(self):
        from src.ecoregion_tree import lineage_keys

        for key in self._keys_that_match_something():
            for p in _plants_mod.search_plants(ecoregion=[key]):
                tags = (p.get("ecoregion") or "").split(",")
                # A hit may claim the key itself or anything on its lineage:
                # a plant tagged only "Prairies" is a legitimate answer to a
                # Mixed Grassland query. See src/ecoregion_tree.py.
                self.assertTrue(set(tags) & set(lineage_keys(key)),
                                f"{p['common_name']} came back under {key} but "
                                f"its range reads {p.get('ecoregion')!r}")

    @unittest.skipIf(_STALE_RANGES, _STALE_WHY)
    def test_a_multi_select_is_the_union_of_its_parts(self):
        live = self._keys_that_match_something()
        one, two = live[0], live[-1]
        a = {p["id"] for p in _plants_mod.search_plants(ecoregion=[one])}
        b = {p["id"] for p in _plants_mod.search_plants(ecoregion=[two])}
        both = {p["id"] for p in _plants_mod.search_plants(
            ecoregion=[one, two])}
        self.assertTrue(a, f"{one} matched nothing")
        self.assertTrue(b, f"{two} matched nothing")
        self.assertEqual(a | b, both)

    def test_a_moisture_niche_still_filters_off_the_column(self):
        """riparian and wet_meadow are never derived, so they must keep
        reading the column even for species that DO have derived rows."""
        for key in ("riparian", "wet_meadow"):
            hits = _plants_mod.search_plants(ecoregion=[key])
            self.assertTrue(hits, f"{key} matched nothing")
            for p in hits:
                self.assertIn(key, (p.get("ecoregion") or "").split(","))

    def test_geography_and_moisture_combine_as_a_union(self):
        geo = {p["id"] for p in _plants_mod.search_plants(ecoregion=["aspen_parkland"])}
        wet = {p["id"] for p in _plants_mod.search_plants(ecoregion=["riparian"])}
        both = {p["id"] for p in _plants_mod.search_plants(
            ecoregion=["aspen_parkland", "riparian"])}
        self.assertEqual(geo | wet, both)


class TestARecordIsEvidenceAboutOnePlace(unittest.TestCase):
    """The 5 km buffer must not reach range derivation (V2.75).

    ``ecoregion._NEAR_BOUNDARY_M`` was written in V2.67 to answer *which
    ecoregion is this yard in*, replacing the deliberate overlap V2.38 had
    drawn into the placeholder polygons. ``ranges_for_species`` defaulted its
    lookup to the same function and inherited the buffer silently, so the
    shipped counts credit a record to every region within five kilometres of
    it. Measured over 4,000 random points inside the layer, 16.4% land in two
    or more.

    An outside review of the published site noticed the symptom and blamed the
    ~900 m boundary simplification. The simplification is real and is the
    smaller half.
    """

    #: A real coordinate in Northern Continental Divide whose buffered lookup
    #: also returns Aspen Parkland. This is the reviewer's own hypothetical --
    #: "a mountain species that shows up in Aspen Parkland" -- as a fact about
    #: the shipped polygons rather than a worry.
    MONTANE_NEAR_PARKLAND = (50.1165, -114.2478)

    #: Montane and nowhere near an edge. The point above turned out to be
    #: inside the *boundary margin* too (V2.81), so it can no longer carry the
    #: half of this regression that says a montane record still counts for its
    #: own region.
    MONTANE_DEEP = (49.05, -113.90)

    def test_the_two_questions_give_different_answers_at_a_boundary(self):
        from src.ecoregion import lookup_ecoregions
        lat, lng = self.MONTANE_NEAR_PARKLAND
        buffered = lookup_ecoregions(lat, lng)
        contained = lookup_ecoregions(lat, lng, near_m=0.0)
        self.assertEqual(contained, ["northern_continental_divide"])
        self.assertIn("aspen_parkland", buffered)
        self.assertEqual(buffered[0], contained[0],
                         "the containing region must still sort first")

    def test_derivation_is_not_buffered(self):
        """The regression. Three records at one montane coordinate must not
        make a parkland claim."""
        rows = R.ranges_for_species([self.MONTANE_DEEP] * 3)
        self.assertEqual([r["ecoregion"] for r in rows],
                         ["northern_continental_divide"])

    def test_site_detection_keeps_its_buffer(self):
        """The default is unchanged on purpose: every other caller is asking
        where a yard is, and there the second answer is the point."""
        from src.ecoregion import _NEAR_BOUNDARY_M, lookup_ecoregions
        self.assertEqual(_NEAR_BOUNDARY_M, 5_000.0)
        lat, lng = self.MONTANE_NEAR_PARKLAND
        self.assertGreater(len(lookup_ecoregions(lat, lng)), 1)

    def test_an_interior_point_is_unaffected(self):
        """The fix must be invisible away from edges, or it is not a fix."""
        from src.ecoregion import lookup_ecoregions
        interior = (52.5, -113.0)
        self.assertEqual(lookup_ecoregions(*interior),
                         lookup_ecoregions(*interior, near_m=0.0))

    def test_dropped_regions_uses_the_same_rule(self):
        """Otherwise the near-miss report would name regions the derivation
        never considered, which is worse than not reporting."""
        near = R.dropped_regions([self.MONTANE_DEEP] * 2)
        self.assertNotIn("aspen_parkland", near)
        self.assertEqual(near, {"northern_continental_divide": 2})


class TestABorderCannotBeReadCloserThanItIsDrawn(unittest.TestCase):
    """A record must be further inside a region than the outline's own error
    before it counts for that region (V2.81).

    V2.75 took the 5 km buffer out of range derivation and left plain
    containment behind, which asks which side of a line a point falls on and
    answers to the metre. These lines are simplified to about 900 m. Reported
    from the published site, on the map where the dots are all in the Rockies:

        "Aspen parkland cannot be absorbing these mountain native species,
         such as mountain forgetmenot and alberta penstemmon."

    The measurement behind this class, which is what makes it a bug and not a
    preference: *Penstemon albertinus* published **17 Aspen Parkland records**
    beside 284 montane ones. All 17 sit in a single 663 m by 291 m patch, 25 to
    202 metres inside the parkland boundary. It is one population next to a
    line drawn to a kilometre, published as a region a mountain plant reaches.
    """

    #: The cluster itself, from ``data/fetched/plant_occurrences.json``.
    THE_SEVENTEEN = (50.4173, -114.5445)

    def test_the_reported_case(self):
        rows = R.ranges_for_species([TestARecordIsEvidenceAboutOnePlace
                                     .MONTANE_DEEP] * 300
                                    + [self.THE_SEVENTEEN] * 17)
        self.assertEqual([r["ecoregion"] for r in rows],
                         ["northern_continental_divide"],
                         "17 records in one 600 m patch just inside the line "
                         "is not a parkland range")

    def test_containment_alone_would_still_get_it_wrong(self):
        """Naming what the old rule did, so this cannot be mistaken for the
        V2.75 fix arriving late. Containment puts the cluster in the parkland
        and is not wrong about the geometry -- the geometry is what cannot be
        read that closely."""
        from src.ecoregion import lookup_ecoregions
        self.assertEqual(lookup_ecoregions(*self.THE_SEVENTEEN, near_m=0.0),
                         ["aspen_parkland"])

    def test_the_margin_is_the_number_the_drawings_disclose(self):
        """Not a tuned threshold. ``ecoregion_map.CAVEAT`` prints "about 900 m"
        under every map on the site; this is that sentence as arithmetic, and
        the two must not drift."""
        from src.ecoregion import SIMPLIFICATION_M
        from src.ecoregion_map import CAVEAT
        self.assertEqual(SIMPLIFICATION_M, 900.0)
        self.assertIn("900 m", CAVEAT)

    def test_a_deep_record_is_untouched(self):
        from src.ecoregion import confident_ecoregion
        self.assertEqual(confident_ecoregion(52.5, -113.0), ["aspen_parkland"])

    #: Real cached records that containment puts inside two regions at once --
    #: the Calgary parkland/fescue crossing the Method page used to disclose,
    #: and the same artefact twice in the mountains.
    DOUBLY_CONTAINED = (
        (51.1220, -114.0979, "aspen_parkland", "fescue_grassland"),
        (52.3916, -116.3555, "eastern_continental_ranges",
         "western_alberta_upland"),
        (52.8819, -118.4508, "eastern_continental_ranges",
         "western_continental_ranges"),
    )

    def test_a_record_now_counts_for_at_most_one_region(self):
        """The overlap this replaces. Each region's share of a common border
        was simplified separately, so neighbours overlap by a sliver and a
        record inside one counted for both -- eight in a thousand, which the
        Method page disclosed as a known limit.

        A doubly contained point is by construction within the margin of a
        boundary, so this is now structurally impossible rather than measured
        and apologised for. Both halves are asserted: that these coordinates
        really are the old double count, and that they no longer are."""
        from src.ecoregion import confident_ecoregion, lookup_ecoregions
        for lat, lng, first, second in self.DOUBLY_CONTAINED:
            self.assertEqual(sorted(lookup_ecoregions(lat, lng, near_m=0.0)),
                             sorted((first, second)),
                             "this coordinate is meant to be an overlap")
            self.assertEqual(confident_ecoregion(lat, lng), [])

    def test_zero_margin_is_the_old_rule(self):
        """Kept as a seam so a test can characterise what changed, and so the
        margin is a decision this module states rather than one it hides."""
        from src.ecoregion import confident_ecoregion
        self.assertEqual(confident_ecoregion(*self.THE_SEVENTEEN, margin=0),
                         ["aspen_parkland"])
        self.assertEqual(confident_ecoregion(*self.THE_SEVENTEEN), [])

    def test_the_layers_outer_edge_is_not_a_boundary_either(self):
        """A record just inside the BC line still counts for its region.

        The ambiguity this rule exists for is *which of two ecoregions*, and
        at the edge of the study area there is no second one to be confused
        with -- the open question there is *is this on our ground at all*,
        which `subject_area` answers separately and which V2.78 already fixed.
        Measuring to any ring rather than to a different region's would have
        deleted the whole western edge of the montane record."""
        from src.ecoregion import confident_ecoregion, lookup_ecoregions
        edge = (52.20, -117.28)          # montane, close to British Columbia
        self.assertEqual(lookup_ecoregions(*edge, near_m=0.0),
                         ["eastern_continental_ranges"])
        self.assertEqual(confident_ecoregion(*edge),
                         ["eastern_continental_ranges"])

    def test_an_internal_subregion_seam_is_not_a_boundary(self):
        """The layer splits every ecoregion by Alberta natural subregion, so
        Aspen Parkland alone is nine features and 65 polygon parts. Measuring
        to the nearest *ring* would treat those internal seams as borders and
        delete records from the middle of a region. The distance is measured
        only to parts of a DIFFERENT region."""
        import json
        import pathlib
        from src.ecoregion import confident_ecoregion
        path = (pathlib.Path(__file__).parent.parent / "data"
                / "ecoregions_canada.geojson")
        feats = json.loads(path.read_text(encoding="utf-8"))["features"]
        subs = {(f["properties"] or {}).get("ab_subregion") or ""
                for f in feats
                if (f["properties"] or {}).get("key") == "aspen_parkland"}
        self.assertGreater(len(subs), 2, "the seams this guards must exist")
        self.assertEqual(confident_ecoregion(52.5, -113.0), ["aspen_parkland"])


class TestARenameReachesTheCacheToo(unittest.TestCase):
    """A re-derivation must not be able to lose a species (V2.81).

    ``scripts/rename_taxon.py`` re-keyed the three shipped files keyed by
    scientific name and not the raw point cache the first two are *derived
    from*. Nothing broke and nothing warned at rename time. The bill arrived an
    increment later: the V2.81 re-derivation wrote **407 species where the file
    had 415**, and seven of the eight missing ones were still in the catalogue,
    having been renamed in V2.80.

    The seeder does print a warning naming them, and it printed it on the
    second line of a 900-line log, where it was scrolled past. A guard nobody
    reads is a guard that has to fail instead.
    """

    def test_every_shipped_species_is_still_in_the_cache(self):
        """The exact failure: a name in the derived file that the cache cannot
        produce again is one re-run away from vanishing."""
        import scripts.seed_ecoregion_ranges as seeder
        cache = seeder.read_cache()
        if not cache:
            self.skipTest("the point cache is a dev artefact")
        shipped = R.parse_document(
            json.loads(seeder.OUTPUT_PATH.read_text(encoding="utf-8")))
        orphans = sorted(set(shipped) - set(cache))
        self.assertEqual(orphans, [],
                         "these have derived ranges that no re-derivation "
                         "could reproduce; the cache still holds them under "
                         "an older name")

    def test_the_rename_tool_rekeys_the_cache(self):
        """Fixing the data without fixing the tool would put the next rename
        straight back here."""
        from scripts.rename_taxon import BY_SCIENTIFIC
        self.assertIn("fetched/plant_occurrences.json", BY_SCIENTIFIC)

    def test_the_cache_speaks_the_catalogues_names(self):
        """The other direction, as a warning rather than a hard rule: a cached
        name that is not a catalogue name is either a rename that has not
        reached the cache or a species that has left. Both are fine to hold
        points for -- what is not fine is the reverse, above."""
        import pathlib

        import scripts.seed_ecoregion_ranges as seeder
        cache = seeder.read_cache()
        if not cache:
            self.skipTest("the point cache is a dev artefact")
        root = pathlib.Path(__file__).parent.parent / "data"
        catalogue = {row["scientific_name"]
                     for name in ("plants_master.json", "garden_plants.json")
                     for row in json.loads(
                         (root / name).read_text(encoding="utf-8"))
                     if isinstance(row, dict) and row.get("scientific_name")}
        self.assertEqual(sorted(set(catalogue) - set(cache)), [],
                         "a catalogue species the cache cannot answer for "
                         "derives to nothing, which reads as grows nowhere")


class TestARederivationIsNotARetrieval(unittest.TestCase):
    """``source`` is a *retrieval* date and must not follow the clock (V2.81).

    ``_write`` stamped ``retrieved {today}`` on every run, including
    ``--from-cache``, which fetches nothing at all. The V2.81 re-derivation
    would have published "retrieved 2026-08-31" against a harvest taken on the
    24th -- on 421 species pages, under a Method-page heading whose entire job
    is answering *as of when*, and with the cache sitting right there saying
    otherwise. Two facts wearing one date; only ``generated`` is today's.
    """

    def test_a_cache_run_keeps_the_harvests_date(self):
        from scripts.seed_ecoregion_ranges import CACHE_PATH, _retrieved_source
        if not CACHE_PATH.exists():
            self.skipTest("the point cache is a dev artefact")
        cached = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
        self.assertEqual(_retrieved_source(True), cached["source"])

    def test_a_live_run_dates_itself(self):
        from datetime import date

        from scripts.seed_ecoregion_ranges import _retrieved_source
        self.assertIn(date.today().isoformat(), _retrieved_source(False))

    def test_the_shipped_file_did_not_redate_its_harvest(self):
        """The regression as it would actually be seen: the file says it was
        retrieved when the records were, not when the file was written."""
        import scripts.seed_ecoregion_ranges as seeder
        if not seeder.CACHE_PATH.exists():
            self.skipTest("the point cache is a dev artefact")
        cache = json.loads(seeder.CACHE_PATH.read_text(encoding="utf-8"))
        shipped = json.loads(seeder.OUTPUT_PATH.read_text(encoding="utf-8"))
        self.assertIn(cache["generated"], shipped["source"])


class TestThePointCache(unittest.TestCase):
    """The raw points survive a run (V2.75).

    Until now the pipeline kept only derived counts, so every later question
    about the derivation cost a fresh harvest of ~400,000 GBIF records. That is
    why the 5 km buffer could be diagnosed and not re-derived, and why the site
    could publish "31 occurrence records" and never show where they are.
    """

    def setUp(self):
        import pathlib
        import scripts.seed_ecoregion_ranges as seeder
        self.seeder = seeder
        self.tmp = pathlib.Path(tempfile.mkdtemp()) / "plant_occurrences.json"

    def _points(self):
        O = self.seeder.Occurrence
        return [
            O(53.5501, -113.4900, 25.0, 2019, "HUMAN_OBSERVATION", "inat"),
            O(53.5600, -113.5000, None, 1908, "PRESERVED_SPECIMEN", "herb"),
            O(53.5700, -113.5100, 50_000.0, 2001, "HUMAN_OBSERVATION", "inat"),
        ]

    def test_it_round_trips_every_field(self):
        pts = self._points()
        self.seeder.write_cache({"Testus plantus": pts}, path=self.tmp)
        self.assertEqual(self.seeder.read_cache(self.tmp)["Testus plantus"],
                         pts)

    def test_a_missing_cache_is_empty_not_an_error(self):
        self.assertEqual(self.seeder.read_cache(self.tmp / "nope"), {})

    def test_the_interned_tables_do_not_confuse_two_species(self):
        """`basis` and `dataset_key` are stored once and referenced by index.
        An off-by-one there would relabel records silently, which is the worst
        failure a provenance cache can have."""
        O = self.seeder.Occurrence
        blob = {"A": [O(50.0, -110.0, None, 2000, "PRESERVED_SPECIMEN", "herb")],
                "B": [O(51.0, -111.0, None, 2001, "HUMAN_OBSERVATION", "inat")]}
        self.seeder.write_cache(blob, path=self.tmp)
        back = self.seeder.read_cache(self.tmp)
        self.assertEqual(back["A"][0].basis, "PRESERVED_SPECIMEN")
        self.assertEqual(back["A"][0].dataset_key, "herb")
        self.assertEqual(back["B"][0].basis, "HUMAN_OBSERVATION")
        self.assertEqual(back["B"][0].dataset_key, "inat")

    def test_an_occurrence_still_works_as_a_lat_lng_pair(self):
        """The derivation reads point[0] and point[1]. If that ever stopped
        being true, every range in the catalogue would quietly become empty."""
        rows = R.ranges_for_species(
            [self.seeder.Occurrence(53.55, -113.49)] * 4)
        self.assertEqual([r["ecoregion"] for r in rows], ["aspen_parkland"])

    def test_a_plain_tuple_is_still_accepted(self):
        """Old test doubles and any caller with bare pairs keep working."""
        rows = R.ranges_for_species([(53.55, -113.49)] * 4)
        self.assertEqual([r["ecoregion"] for r in rows], ["aspen_parkland"])


class TestTheSpecimenPass(unittest.TestCase):
    """The herbarium half, asked for as its own query (F140, V2.77).

    ``MAX_RECORDS_PER_SPECIES`` bounds the harvest and GBIF orders newest
    first, so for a common plant the six-thousand-record window is the last few
    years of phone observations and the century of specimens behind it never
    arrives. Sixteen species in this catalogue sit at that cap holding 89,964
    records and thirty-one specimens between them. Nobody noticed, because a
    truncated harvest and a complete one look identical once cached.
    """

    def setUp(self):
        import pathlib
        import scripts.seed_ecoregion_ranges as seeder
        self.seeder = seeder
        self.O = seeder.Occurrence
        self.tmp = pathlib.Path(tempfile.mkdtemp()) / "plant_occurrences.json"

    def test_it_asks_gbif_for_specimens_and_not_for_everything(self):
        """The whole point: filtering the answer cannot reach what the cap cut."""
        seen = {}

        def fake(name, *, verbose=False, throttle=None, basis_of_record="",
                 **_kw):
            seen[name] = basis_of_record
            return [self.O(53.55, -113.49, 30.0, 1911, basis_of_record, "herb")]

        harvest, failed = self.seeder.specimen_pass(
            ["Testus plantus"], throttle=_NoWait(), verbose=False, fetch=fake)
        self.assertEqual(seen["Testus plantus"], "PRESERVED_SPECIMEN")
        self.assertEqual(len(harvest["Testus plantus"]), 1)
        self.assertEqual(failed, [])

    def test_a_refusal_is_not_recorded_as_having_no_specimens(self):
        """Same rule the main harvest learned in V2.75, in the new code path."""
        def flaky(name, **_kw):
            raise self.seeder.FetchFailed("HTTP 429")

        harvest, failed = self.seeder.specimen_pass(
            ["Testus plantus"], throttle=_NoWait(), verbose=False, fetch=flaky)
        self.assertEqual(harvest, {})
        self.assertEqual([n for n, _why in failed], ["Testus plantus"])

    def test_a_genuine_absence_is_recorded_as_an_empty_list(self):
        harvest, failed = self.seeder.specimen_pass(
            ["Testus plantus"], throttle=_NoWait(), verbose=False,
            fetch=lambda name, **_kw: [])
        self.assertEqual(harvest, {"Testus plantus": []})
        self.assertEqual(failed, [])

    def test_hitting_the_cap_is_reported_rather_than_looking_like_the_end(self):
        """The bug's mechanism, pinned. A harvest that stopped because we
        stopped asking must not be indistinguishable from one GBIF ended."""
        pages = {"n": 0}

        def _get_json(url, timeout, throttle):
            pages["n"] += 1
            return {"results": [{"decimalLatitude": 53.55,
                                 "decimalLongitude": -113.49,
                                 "basisOfRecord": "HUMAN_OBSERVATION"}]
                                * self.seeder.PAGE_SIZE,
                    "endOfRecords": False}

        original = self.seeder._get_json
        self.seeder._get_json = _get_json
        try:
            truncated = []
            self.seeder.fetch_occurrences("Testus plantus", throttle=_NoWait(),
                                          truncated=truncated)
            self.assertEqual(truncated, ["Testus plantus"])
        finally:
            self.seeder._get_json = original

    def test_a_harvest_gbif_ended_is_not_reported_as_truncated(self):
        def _get_json(url, timeout, throttle):
            return {"results": [{"decimalLatitude": 53.55,
                                 "decimalLongitude": -113.49,
                                 "basisOfRecord": "PRESERVED_SPECIMEN"}],
                    "endOfRecords": True}

        original = self.seeder._get_json
        self.seeder._get_json = _get_json
        try:
            truncated = []
            self.seeder.fetch_occurrences("Testus plantus", throttle=_NoWait(),
                                          truncated=truncated)
            self.assertEqual(truncated, [])
        finally:
            self.seeder._get_json = original

    # ── merging into the cache ──────────────────────────────────────────────

    def test_the_same_sheet_twice_is_counted_once(self):
        """A duplicate inflates the number a confidence band is computed from,
        which is the one number the whole pipeline exists to keep honest."""
        sheet = self.O(53.55, -113.49, 30.0, 1911, "PRESERVED_SPECIMEN", "herb")
        self.seeder.write_cache({"Testus plantus": [sheet]}, path=self.tmp)
        merged, added = self.seeder.merge_into_cache(
            {"Testus plantus": [sheet]}, path=self.tmp)
        self.assertEqual(len(merged["Testus plantus"]), 1)
        self.assertEqual(added, {})

    def test_two_collectors_at_one_trailhead_stay_two_records(self):
        """De-duplicating on coordinates alone would collapse exactly what a
        dot map is drawn to show."""
        self.seeder.write_cache({"Testus plantus": [
            self.O(53.55, -113.49, 30.0, 1911, "PRESERVED_SPECIMEN", "herb")]},
            path=self.tmp)
        merged, added = self.seeder.merge_into_cache({"Testus plantus": [
            self.O(53.55, -113.49, 30.0, 1974, "PRESERVED_SPECIMEN", "herb")]},
            path=self.tmp)
        self.assertEqual(len(merged["Testus plantus"]), 2)
        self.assertEqual(added, {"Testus plantus": 1})

    def test_a_restated_uncertainty_is_still_the_same_record(self):
        """GBIF exports re-state these; the sheet in the cabinet is one sheet."""
        self.seeder.write_cache({"Testus plantus": [
            self.O(53.55, -113.49, 30.0, 1911, "PRESERVED_SPECIMEN", "herb")]},
            path=self.tmp)
        merged, added = self.seeder.merge_into_cache({"Testus plantus": [
            self.O(53.55, -113.49, 250.0, 1911, "PRESERVED_SPECIMEN", "herb")]},
            path=self.tmp)
        self.assertEqual(len(merged["Testus plantus"]), 1)
        self.assertEqual(added, {})

    def test_a_species_the_cache_never_held_is_added_whole(self):
        self.seeder.write_cache({"Testus plantus": []}, path=self.tmp)
        merged, added = self.seeder.merge_into_cache({"Novus sp.": [
            self.O(53.55, -113.49, 30.0, 1911, "PRESERVED_SPECIMEN", "herb")]},
            path=self.tmp)
        self.assertEqual(added, {"Novus sp.": 1})
        self.assertIn("Novus sp.", merged)

    def test_merging_never_drops_what_was_already_there(self):
        old = [self.O(50.0, -110.0, None, 2000, "HUMAN_OBSERVATION", "inat")]
        self.seeder.write_cache({"Testus plantus": old}, path=self.tmp)
        merged, _added = self.seeder.merge_into_cache({"Testus plantus": [
            self.O(53.55, -113.49, 30.0, 1911, "PRESERVED_SPECIMEN", "herb")]},
            path=self.tmp)
        self.assertIn(old[0], merged["Testus plantus"])


class TestDerivingWithoutTheNetwork(unittest.TestCase):
    """``--from-cache`` (F140, V2.77).

    The cache was built so no later question about this derivation would need
    egress, and until now nothing read it that way: a changed threshold or a
    corrected polygon still meant a fresh harvest on somebody's laptop. This is
    the seam that makes the derivation, and its diff, reproducible anywhere.
    """

    def test_it_derives_the_same_rows_the_network_run_would(self):
        from scripts.seed_ecoregion_ranges import cache_fetcher, derive
        O = __import__("scripts.seed_ecoregion_ranges",
                       fromlist=["Occurrence"]).Occurrence
        points = [O(53.55, -113.49, 30.0, 1911, "PRESERVED_SPECIMEN", "h")] * 5
        live, _d, _n, _f = derive(
            ["Testus plantus"], min_records=3, verbose=False,
            fetch=lambda name, **_kw: points, throttle=_NoWait())
        cached, _d, _n, _f = derive(
            ["Testus plantus"], min_records=3, verbose=False,
            fetch=cache_fetcher({"Testus plantus": points}),
            throttle=_NoWait())
        self.assertEqual(live, cached)
        self.assertEqual([r["ecoregion"] for r in cached["Testus plantus"]],
                         ["aspen_parkland"])

    def test_a_species_absent_from_the_cache_derives_to_nothing(self):
        """And the CLI says so before writing, because "no rows" reads as
        "grows nowhere" and the cache is not the catalogue."""
        from scripts.seed_ecoregion_ranges import cache_fetcher, derive
        ranges, _d, none, failed = derive(
            ["Absent sp."], min_records=3, verbose=False,
            fetch=cache_fetcher({}), throttle=_NoWait())
        self.assertEqual(ranges, {})
        self.assertEqual(none, ["Absent sp."])
        self.assertEqual(failed, [])

    def test_the_committed_points_agree_with_the_committed_ranges(self):
        """A spot check on the real pair, cheap enough to run every time.

        The full re-derivation over 555,477 points takes about forty minutes of
        CPU and was run once (V2.77: 420 species, zero differing rows). This
        samples it, so a cache and a shipped file that drift apart -- a
        re-fetch committed without a re-derivation, or the reverse -- fails
        here rather than being discovered by somebody reading a map.
        """
        import scripts.seed_ecoregion_ranges as seeder
        cache = seeder.read_cache()
        if not cache:
            self.skipTest("the point cache is a dev artefact")
        with open(seeder.OUTPUT_PATH, encoding="utf-8") as f:
            shipped = R.parse_document(json.load(f))
        # The ten largest: most records, most chances to disagree, and they
        # cover every ecoregion between them.
        sample = sorted(shipped, key=lambda n: -len(cache.get(n) or []))[:10]
        self.assertTrue(sample)
        for name in sample:
            points, _refused = seeder.usable_points(cache[name])
            got = {(r["ecoregion"], r["occurrences"], r["confidence"])
                   for r in R.ranges_for_species(points)}
            want = {(r["ecoregion"], r["occurrences"], r["confidence"])
                    for r in shipped[name]}
            self.assertEqual(got, want, name)

    def test_it_makes_no_request(self):
        """The suite's offline guard would fail this if it reached the network,
        but stating it is what makes the guarantee readable."""
        from scripts.seed_ecoregion_ranges import cache_fetcher
        fetch = cache_fetcher({"Testus plantus": [(53.55, -113.49)]})
        self.assertEqual(len(fetch("Testus plantus")), 1)
        self.assertEqual(fetch("Nobody sp."), [])


class TestCoordinateUncertainty(unittest.TestCase):
    """A record states what it can support, and the pipeline had never read it.

    The direct answer to the boundary objection: better than any threshold on
    counts, because it acts per record and for a stated reason.
    """

    def setUp(self):
        import scripts.seed_ecoregion_ranges as seeder
        self.seeder = seeder

    def test_a_record_georeferenced_to_the_county_is_refused(self):
        O = self.seeder.Occurrence
        kept, refused = self.seeder.usable_points(
            [O(53.55, -113.49, 25.0), O(53.55, -113.49, 40_000.0)])
        self.assertEqual(len(kept), 1)
        self.assertEqual(refused, 1)

    def test_no_stated_uncertainty_is_kept(self):
        """Absent is not estimated (src/confidence.py). Most herbarium sheets
        state none, and dropping them would silently prefer phone photographs
        to museum specimens."""
        O = self.seeder.Occurrence
        kept, refused = self.seeder.usable_points([O(53.55, -113.49, None)])
        self.assertEqual(len(kept), 1)
        self.assertEqual(refused, 0)

    def test_the_threshold_is_adjustable(self):
        O = self.seeder.Occurrence
        pts = [O(53.55, -113.49, 8_000.0)]
        self.assertEqual(self.seeder.usable_points(pts)[1], 0)
        self.assertEqual(
            self.seeder.usable_points(pts, max_uncertainty_m=1_000.0)[1], 1)

    def test_derive_applies_it_and_the_cache_keeps_what_it_refused(self):
        """The filter is a derivation-time decision; the cache holds what GBIF
        actually returned, so revisiting the threshold costs no network."""
        O = self.seeder.Occurrence
        coarse = [O(53.55, -113.49, 90_000.0)] * 5
        fine = [O(53.55, -113.49, 30.0)] * 4
        harvest: dict = {}
        ranges, _dropped, _none, _failed = self.seeder.derive(
            ["Testus plantus"], min_records=3, verbose=False,
            fetch=lambda name, *, verbose=False, throttle=None: coarse + fine,
            throttle=_NoWait(), collect=harvest)
        self.assertEqual(ranges["Testus plantus"][0]["occurrences"], 4)
        self.assertEqual(len(harvest["Testus plantus"]), 9)

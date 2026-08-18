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
        return ["aspen_parkland", "subalpine_montane"]
    if lat >= 50:
        return ["aspen_parkland"]
    if lat >= 10:
        return ["boreal_mixedwood"]
    return []                            # outside coverage


def _points(**counts):
    """``_points(aspen_parkland=5)`` → five points inside that region."""
    lat_for = {"aspen_parkland": 60.0, "boreal_mixedwood": 20.0,
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
        pts = _points(aspen_parkland=40, boreal_mixedwood=2)
        rows = R.ranges_for_species(pts, lookup=_fake_lookup)
        thin = R.dropped_regions(pts, lookup=_fake_lookup)
        self.assertEqual([r["ecoregion"] for r in rows], ["aspen_parkland"])
        self.assertEqual(thin, {"boreal_mixedwood": 2})

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
            _points(aspen_parkland=300, boreal_mixedwood=4),
            lookup=_fake_lookup)
        self.assertEqual([(r["ecoregion"], r["confidence"]) for r in rows],
                         [("aspen_parkland", "high"),
                          ("boreal_mixedwood", "low")])

    def test_the_bands_are_ordered_and_named_consistently(self):
        labels = [label for _floor, label in R.CONFIDENCE_BANDS]
        self.assertEqual(labels, list(R.CONFIDENCE_ORDER))
        floors = [floor for floor, _label in R.CONFIDENCE_BANDS]
        self.assertEqual(floors, sorted(floors, reverse=True),
                         "bands must descend, or confidence_for short-circuits "
                         "on the wrong one")


class TestCountingPoints(unittest.TestCase):
    def test_an_overlap_counts_for_both_regions(self):
        """Not double-counting: the species really is recorded from a place
        that is in both, and 'first match wins' is the bug being undone."""
        rows = R.ranges_for_species(_points(overlap=10), lookup=_fake_lookup)
        self.assertEqual({r["ecoregion"] for r in rows},
                         {"aspen_parkland", "subalpine_montane"})
        self.assertTrue(all(r["occurrences"] == 10 for r in rows))

    def test_records_outside_every_region_are_ignored(self):
        rows = R.ranges_for_species(
            _points(aspen_parkland=5, nowhere=900), lookup=_fake_lookup)
        self.assertEqual([r["ecoregion"] for r in rows], ["aspen_parkland"])

    def test_commonest_first_then_alphabetical(self):
        """A stable order means a re-run's diff is real change in GBIF, not
        dict ordering."""
        pts = (_points(aspen_parkland=5) + _points(boreal_mixedwood=5)
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
    _FORT_MCMURRAY = (56.73, -111.38)    # boreal_mixedwood

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
        self.assertEqual(dropped["Amelanchier alnifolia"],
                         {"boreal_mixedwood": 2})
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
                {"ecoregion": "boreal_mixedwood", "occurrences": 44,
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
                         ["aspen_parkland", "boreal_mixedwood"])

    def test_the_evidence_travels_with_the_claim(self):
        p = self._plant("Amelanchier alnifolia")
        rows = p["ecoregion_evidence"]
        self.assertEqual([r["ecoregion"] for r in rows],
                         ["aspen_parkland", "boreal_mixedwood"])
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
        existing tags — the parkland list must not shrink to one plant."""
        hits = _plants_mod.search_plants(ecoregion=["moist_mixedgrass"])
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
        can assert wet ground."""
        from src.ecoregion import geographic_keys
        valid = set(geographic_keys())
        for name, rows in R.parse_document(self._shipped()).items():
            for row in rows:
                self.assertIn(row["ecoregion"], valid, name)

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

    def test_every_result_claims_the_region_it_was_found_under(self):
        for key in ("aspen_parkland", "boreal_mixedwood", "mixedgrass_prairie"):
            for p in _plants_mod.search_plants(ecoregion=[key]):
                tags = (p.get("ecoregion") or "").split(",")
                self.assertIn(key, tags,
                              f"{p['common_name']} came back under {key} but "
                              f"its range reads {p.get('ecoregion')!r}")

    def test_a_multi_select_is_the_union_of_its_parts(self):
        a = {p["id"] for p in _plants_mod.search_plants(ecoregion=["aspen_parkland"])}
        b = {p["id"] for p in _plants_mod.search_plants(ecoregion=["boreal_mixedwood"])}
        both = {p["id"] for p in _plants_mod.search_plants(
            ecoregion=["aspen_parkland", "boreal_mixedwood"])}
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

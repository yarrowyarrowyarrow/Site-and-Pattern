"""
tests/test_lep_habitat.py

Covers the V2.12 Lepidoptera data spine (schema v40 ``lepidoptera_attributes``
table + seed) and the ``src.lep_habitat`` "fly as a butterfly" selection core:

  * schema/seed round-trip and enum integrity
  * P9 honesty: non-feeding adults (giant silk moths / some sphinxes) have NO
    nectar genera and yield zero nectar targets — never a silent generalist guess
  * nectar-plant selection (documented edges + genus fallback) resolves to plants
  * larval-host selection reuses the documented ``larval_host`` edges
  * flight-month parsing for the seasonal tour
  * the shipped lepidoptera-attributes data validates against the fauna registry
"""

import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Redirect the DB to a temp directory before importing anything that opens it.
_TMP_DIR = tempfile.mkdtemp(prefix="permadesign_lep_test_")

import src.db.plants as _plants_mod  # noqa: E402

_plants_mod._DATA_DIR = _TMP_DIR
_plants_mod._DB_PATH  = os.path.join(_TMP_DIR, "permadesign_test.db")

from src.db.plants import init_db, get_connection  # noqa: E402
from src.db import fauna as F  # noqa: E402
import src.lep_habitat as LH  # noqa: E402

_DATA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                     "data", "lepidoptera_attributes_master.json")


def _fid(scientific_name: str):
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT id FROM fauna WHERE scientific_name = ?", (scientific_name,)
        ).fetchone()
        return row[0] if row else None
    finally:
        conn.close()


class TestLepSchemaSeed(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        init_db()

    def test_attributes_populated(self):
        conn = get_connection()
        try:
            n = conn.execute(
                "SELECT COUNT(*) FROM lepidoptera_attributes").fetchone()[0]
        finally:
            conn.close()
        self.assertGreaterEqual(n, 25, "expected the Alberta lep roster to seed")

    def test_every_lep_has_attributes(self):
        # Each seeded lep row resolves to a fauna row with taxon='lepidoptera'.
        leps = F.list_lepidoptera_with_attributes()
        self.assertGreaterEqual(len(leps), 25)
        for lp in leps:
            self.assertIn(lp.get("lep_kind"), ("butterfly", "moth", "skipper"),
                          f"{lp['common_name']} has no/invalid kind")
            self.assertTrue(lp.get("flight_season"),
                            f"{lp['common_name']} has no flight season")

    def test_kind_and_overwintering_enums(self):
        conn = get_connection()
        try:
            kinds = {r[0] for r in conn.execute(
                "SELECT DISTINCT kind FROM lepidoptera_attributes")}
            stages = {r[0] for r in conn.execute(
                "SELECT DISTINCT overwintering_stage FROM lepidoptera_attributes")}
        finally:
            conn.close()
        self.assertTrue(kinds <= {"butterfly", "moth", "skipper"})
        self.assertTrue(stages <= {"egg", "larva", "pupa", "adult",
                                   "migrant", "unknown", None})


class TestNectarAndHostSelection(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        init_db()

    def test_monarch_nectar_and_hosts(self):
        fid = _fid("Danaus plexippus")
        self.assertIsNotNone(fid)
        nectar = LH.nectar_plant_ids_for_lep(fid)
        hosts = LH.larval_host_ids_for_lep(fid)
        # Genus-level nectar fallback resolves to many composite/milkweed plants…
        self.assertGreater(len(nectar), 5)
        # …and the milkweed larval hosts are the documented edges.
        self.assertGreaterEqual(len(hosts), 1)

    def test_nonfeeding_moth_has_no_nectar(self):
        # Giant silk moths do not feed as adults — nectar list is empty (P9),
        # but they still carry larval host plants (their caterpillars feed).
        for sci in ("Antheraea polyphemus", "Hyalophora cecropia"):
            fid = _fid(sci)
            self.assertIsNotNone(fid, sci)
            self.assertEqual(LH.nectar_plant_ids_for_lep(fid), [],
                             f"{sci} should have no adult nectar plants")
            self.assertGreater(len(LH.larval_host_ids_for_lep(fid)), 0,
                               f"{sci} should still have larval hosts")

    def test_flight_months_parse(self):
        fid = _fid("Danaus plexippus")
        months = LH.flight_months_for_lep(fid)
        self.assertTrue(set(months) <= set(range(1, 13)))
        self.assertIn(7, months, "Monarch flies mid-summer")

    def test_list_targets_sorted_butterflies_first(self):
        targets = LH.list_target_lepidoptera()
        self.assertGreaterEqual(len(targets), 25)
        kinds = [t["kind"] for t in targets]
        # Butterflies/skippers sort ahead of moths (the combo grouping).
        last_butterfly = max((i for i, k in enumerate(kinds)
                              if k in ("butterfly", "skipper")), default=-1)
        first_moth = min((i for i, k in enumerate(kinds) if k == "moth"),
                         default=len(kinds))
        self.assertLess(last_butterfly, first_moth)


class TestShippedData(unittest.TestCase):

    def test_master_json_valid(self):
        with open(_DATA, encoding="utf-8") as fh:
            entries = json.load(fh)
        records = [e for e in entries if "scientific_name" in e]
        self.assertGreaterEqual(len(records), 25)
        seen = set()
        for e in records:
            sci = e["scientific_name"]
            self.assertNotIn(sci, seen, f"duplicate {sci}")
            seen.add(sci)
            self.assertIn(e.get("kind"), ("butterfly", "moth", "skipper"), sci)
            self.assertIn(e.get("overwintering_stage"),
                          ("egg", "larva", "pupa", "adult", "migrant", "unknown"), sci)
            self.assertTrue(e.get("flight_season"), sci)

    def test_seed_resolves_against_fauna(self):
        # Every seeded record must match a lepidoptera fauna row by scientific
        # name (else the seed silently drops it).
        init_db()
        with open(_DATA, encoding="utf-8") as fh:
            names = [e["scientific_name"] for e in json.load(fh)
                     if "scientific_name" in e]
        conn = get_connection()
        try:
            known = {r[0] for r in conn.execute(
                "SELECT scientific_name FROM fauna WHERE taxon='lepidoptera'")}
        finally:
            conn.close()
        missing = [n for n in names if n not in known]
        self.assertEqual(missing, [],
                         f"lep attrs reference unknown fauna: {missing}")


if __name__ == "__main__":
    unittest.main()

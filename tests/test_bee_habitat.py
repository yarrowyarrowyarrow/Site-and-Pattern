"""
tests/test_bee_habitat.py

Covers the F37 native-bee data spine (schema v39 ``bee_attributes`` table +
seed) and the ``src.bee_habitat`` "design for a bee" core:

  * schema/seed round-trip and enum integrity
  * P9 honesty: a graded tongue length is asserted only for Bombus
  * floral-host matching (documented edges + genus fallback, design-first order)
  * tongue↔flower-form fit heuristic
  * nesting-habit → habitat-structure mapping (incl. cuckoo → host bee)
  * flight-season forage coverage + gap detection
  * end-to-end plan for a bumble bee and a cuckoo bee
  * the shipped bee-attributes data validates
"""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Redirect the DB to a temp directory before importing anything that opens it.
_TMP_DIR = tempfile.mkdtemp(prefix="permadesign_bee_test_")

import src.db.plants as _plants_mod  # noqa: E402

_plants_mod._DATA_DIR = _TMP_DIR
_plants_mod._DB_PATH  = os.path.join(_TMP_DIR, "permadesign_test.db")

from src.db.plants import init_db, get_connection  # noqa: E402
from src.db import fauna as F  # noqa: E402
import src.bee_habitat as BH  # noqa: E402


def _fid(scientific_name: str) -> int | None:
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT id FROM fauna WHERE scientific_name = ?", (scientific_name,)
        ).fetchone()
        return row[0] if row else None
    finally:
        conn.close()


class TestBeeSchemaSeed(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        init_db()

    def test_bee_attributes_populated(self):
        conn = get_connection()
        try:
            n = conn.execute("SELECT COUNT(*) FROM bee_attributes").fetchone()[0]
        finally:
            conn.close()
        self.assertGreater(n, 40, "expected the Apidae roster to seed many bees")

    def test_every_attr_row_is_a_bee(self):
        conn = get_connection()
        try:
            orphans = conn.execute(
                "SELECT COUNT(*) FROM bee_attributes ba "
                "LEFT JOIN fauna f ON f.id = ba.fauna_id "
                "WHERE f.taxon IS NULL OR f.taxon != 'bee'"
            ).fetchone()[0]
        finally:
            conn.close()
        self.assertEqual(orphans, 0)

    def test_key_apidae_genera_present(self):
        genera = {b["genus"] for b in BH.list_target_bees()}
        for g in ("Bombus", "Anthophora", "Nomada", "Melissodes"):
            self.assertIn(g, genera)

    def test_enum_integrity(self):
        for row in F.list_bees_with_attributes():
            nh = row.get("nesting_habit")
            tl = row.get("tongue_length")
            if nh is not None:
                self.assertIn(nh, BH._DEEP_FORMS | BH._OPEN_FORMS | {
                    "ground", "cavity", "pithy_stem", "social_ground",
                    "cleptoparasite", "unknown"})
            if tl is not None:
                self.assertIn(tl, {"short", "medium", "long", "unknown"})

    def test_bombus_terricola_has_graded_tongue(self):
        attrs = F.bee_attributes_for(_fid("Bombus terricola"))
        self.assertIn(attrs.get("tongue_length"), {"short", "medium", "long"})

    def test_p9_graded_tongue_only_for_bombus(self):
        """A graded tongue length must never be asserted for a non-Bombus bee."""
        for row in F.list_bees_with_attributes():
            if row.get("tongue_length") in {"short", "medium", "long"}:
                self.assertTrue(
                    str(row["scientific_name"]).startswith("Bombus "),
                    f"{row['scientific_name']} should not carry a graded tongue")


class TestTongueFormFit(unittest.TestCase):

    def test_long_tongue_deep_flower_is_good(self):
        self.assertEqual(BH.tongue_form_fit("long", "bell"), "good")
        self.assertEqual(BH.tongue_form_fit("long", "spike"), "good")

    def test_short_tongue_open_flower_is_good(self):
        self.assertEqual(BH.tongue_form_fit("short", "daisy"), "good")
        self.assertEqual(BH.tongue_form_fit("short", "umbel"), "good")

    def test_unknown_tongue_never_claims_fit(self):
        self.assertEqual(BH.tongue_form_fit("unknown", "bell"), "unknown")
        self.assertEqual(BH.tongue_form_fit(None, "daisy"), "unknown")

    def test_unknown_form_never_claims_fit(self):
        self.assertEqual(BH.tongue_form_fit("long", "none"), "unknown")
        self.assertEqual(BH.tongue_form_fit("long", ""), "unknown")


class TestFloralMatching(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        init_db()

    def test_genus_fallback_matches(self):
        # Bombus terricola forages on Rubus/Ribes/Viola etc. (genus fallback).
        matches = BH.floral_matches_for_bee(_fid("Bombus terricola"))
        self.assertTrue(matches, "expected genus-level floral matches")
        self.assertTrue(all(isinstance(m, BH.FloralMatch) for m in matches))
        self.assertTrue(any(m.match_basis in ("genus", "both") for m in matches))

    def test_design_plants_sorted_first_and_flagged(self):
        tid = _fid("Bombus terricola")
        all_matches = BH.floral_matches_for_bee(tid)
        self.assertTrue(all_matches)
        chosen = all_matches[-1].plant_id            # pick one that isn't already first
        matches = BH.floral_matches_for_bee(tid, plant_ids=[chosen])
        flagged = [m for m in matches if m.plant_id == chosen][0]
        self.assertTrue(flagged.in_users_list)
        self.assertEqual(matches[0].plant_id, chosen,
                         "a design plant should sort to the top")

    def test_cuckoo_bee_has_no_floral_hosts(self):
        matches = BH.floral_matches_for_bee(_fid("Nomada bella"))
        self.assertEqual(matches, [])


class TestNestingGuidance(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        init_db()

    def test_cavity_bee_recommends_bee_hotel(self):
        g = BH.nesting_guidance(_fid("Osmia lignaria"))
        self.assertEqual(g.nesting_habit, "cavity")
        self.assertIn("bee_hotel", g.structure_ids)
        # every recommended structure id resolves to a real structure def
        for s in g.structures:
            self.assertIn("name", s)

    def test_social_bumblebee_recommends_ground_habitat(self):
        g = BH.nesting_guidance(_fid("Bombus terricola"))
        self.assertEqual(g.nesting_habit, "social_ground")
        self.assertTrue(g.structure_ids)

    def test_cuckoo_bee_has_no_structure_but_names_host(self):
        g = BH.nesting_guidance(_fid("Nomada bella"))
        self.assertEqual(g.nesting_habit, "cleptoparasite")
        self.assertEqual(g.structure_ids, [])
        self.assertTrue(any("Andrena" in a for a in g.actions),
                        "cuckoo guidance should name the host bee genus")

    def test_all_recommended_structure_ids_are_real(self):
        from src.db import structures as S
        for bee in BH.list_target_bees():
            g = BH.nesting_guidance(bee["id"])
            for sid in g.structure_ids:
                self.assertIsNotNone(S.get_structure(sid), f"bad structure id {sid}")


class TestForageCoverage(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        init_db()

    def test_gap_detection(self):
        tid = _fid("Bombus terricola")
        matches = BH.floral_matches_for_bee(tid)
        # Consider only a single spring-blooming host → summer/autumn gaps appear.
        spring = [m for m in matches if "may" in m.bloom_period.lower()][:1]
        cov = BH.forage_coverage(tid, spring)
        self.assertTrue(cov.flight_months)
        self.assertTrue(cov.gap_months, "a spring-only host should leave gaps")
        # gap + covered partition the flight window
        self.assertEqual(sorted(cov.covered_months + cov.gap_months),
                         sorted(cov.flight_months))

    def test_undocumented_flight_season_is_skipped(self):
        cov = BH.forage_coverage(_fid("Nomada bella"), [])
        self.assertEqual(cov.flight_months, [])
        self.assertIn("skipped", cov.note.lower())


class TestPlanEndToEnd(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        init_db()

    def test_bumblebee_plan(self):
        plan = BH.build_bee_habitat_plan(_fid("Bombus terricola"))
        self.assertIsNotNone(plan)
        self.assertEqual(plan.bee["taxon"], "bee")
        self.assertTrue(plan.floral_matches)
        self.assertTrue(plan.nesting.structure_ids)
        self.assertTrue(plan.forage.flight_months)
        self.assertEqual(plan.data_confidence, "documented")

    def test_cuckoo_plan(self):
        plan = BH.build_bee_habitat_plan(_fid("Nomada bella"))
        self.assertIsNotNone(plan)
        self.assertEqual(plan.nesting.nesting_habit, "cleptoparasite")
        self.assertEqual(plan.floral_matches, [])

    def test_non_bee_returns_none(self):
        # A lepidoptera id must not build a bee plan.
        self.assertIsNone(BH.build_bee_habitat_plan(_fid("Danaus plexippus")))

    def test_target_plant_ids_match_floral_matches(self):
        # The shared "chosen bee -> plant ids" selection the 3D fly-through uses.
        tid = _fid("Bombus terricola")
        ids = BH.target_plant_ids_for_bee(tid)
        self.assertTrue(ids)
        self.assertEqual(set(ids),
                         {m.plant_id for m in BH.floral_matches_for_bee(tid)})

    def test_target_plant_ids_empty_for_cuckoo(self):
        self.assertEqual(BH.target_plant_ids_for_bee(_fid("Nomada bella")), [])


class TestBeeDataQuality(unittest.TestCase):

    def test_shipped_bee_attributes_validate(self):
        from src.data_quality import validate_bee_attributes
        errors, _ = validate_bee_attributes()
        self.assertEqual(errors, [], "\n".join(errors))


if __name__ == "__main__":
    unittest.main()

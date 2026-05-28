"""
tests/test_habitat_score.py

Characterization tests for src/habitat_score.py — the Qt-free habitat
scoring extracted out of AnalysisPanel in Chunk 6. These pin the maths
so the GUI panel and the headless scripting API can never drift.

Uses the temp-DB seed pattern from tests/test_polycultures.py: redirect
the DB to a tempdir and init_db() so real seeded plants back the score.
The pure-function tests (parse_month_range) need no DB at all.
"""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Redirect the DB to a temp dir BEFORE importing anything that opens it.
_TMP_DIR = tempfile.mkdtemp(prefix="permadesign_habitat_test_")
import src.db.plants as _plants_mod  # noqa: E402
_plants_mod._DATA_DIR = _TMP_DIR
_plants_mod._DB_PATH = os.path.join(_TMP_DIR, "permadesign_test.db")

from src.db.plants import init_db, get_connection, get_all_plants  # noqa: E402
from src.habitat_score import (  # noqa: E402
    compute_habitat_score,
    parse_month_range,
    HabitatScore,
    HabitatScoreError,
    CANONICAL_LAYERS,
    HABITAT_STRUCTURE_IDS,
)


class TestParseMonthRange(unittest.TestCase):
    """Pure parser — no DB."""

    def test_single_month(self):
        self.assertEqual(parse_month_range("May"), [5])
        self.assertEqual(parse_month_range("July"), [7])

    def test_simple_range(self):
        self.assertEqual(parse_month_range("June-August"), [6, 7, 8])

    def test_dash_variants(self):
        # en-dash and em-dash both normalise to a plain range.
        self.assertEqual(parse_month_range("Jun–Aug"), [6, 7, 8])
        self.assertEqual(parse_month_range("Jun—Aug"), [6, 7, 8])

    def test_year_wrap(self):
        # Nov-Feb wraps the year boundary.
        self.assertEqual(parse_month_range("Nov-Feb"), [11, 12, 1, 2])

    def test_empty(self):
        self.assertEqual(parse_month_range(""), [])
        self.assertEqual(parse_month_range(None), [])


class TestComputeHabitatScoreEmpty(unittest.TestCase):

    def test_nothing_placed_returns_none(self):
        self.assertIsNone(compute_habitat_score([], []))


class TestComputeHabitatScoreSeeded(unittest.TestCase):
    """Score real seeded plants so the component maths is exercised
    end-to-end against the shipped data."""

    @classmethod
    def setUpClass(cls):
        init_db()
        cls.plants = get_all_plants()
        # A handful of real plant_ids to place.
        cls.some_ids = [p["id"] for p in cls.plants[:8]]

    def test_returns_habitat_score_dataclass(self):
        placed = [{"plant_id": pid} for pid in self.some_ids]
        result = compute_habitat_score(placed, [])
        self.assertIsInstance(result, HabitatScore)
        self.assertGreaterEqual(result.total, 0)
        self.assertLessEqual(result.total, 100)

    def test_total_equals_sum_of_components(self):
        placed = [{"plant_id": pid} for pid in self.some_ids]
        r = compute_habitat_score(placed, [])
        component_sum = (r.score_native + r.score_keystone + r.score_host
                         + r.score_bird + r.score_layers + r.score_structs
                         + r.score_bloom)
        self.assertEqual(r.total, int(round(component_sum)))

    def test_species_dedup_but_total_counts_all(self):
        # Placing the same plant twice = 1 species, 2 total plants.
        pid = self.some_ids[0]
        r = compute_habitat_score(
            [{"plant_id": pid}, {"plant_id": pid}], []
        )
        self.assertEqual(r.n_species, 1)
        self.assertEqual(r.n_total_plants, 2)

    def test_native_ratio_bounds(self):
        placed = [{"plant_id": pid} for pid in self.some_ids]
        r = compute_habitat_score(placed, [])
        self.assertGreaterEqual(r.native_ratio, 0.0)
        self.assertLessEqual(r.native_ratio, 1.0)
        # score_native is exactly ratio * 20
        self.assertAlmostEqual(r.score_native, r.native_ratio * 20)

    def test_layers_are_canonical_only(self):
        placed = [{"plant_id": pid} for pid in self.some_ids]
        r = compute_habitat_score(placed, [])
        for layer in r.layers_present:
            self.assertIn(layer, CANONICAL_LAYERS)
        # 3 pts per layer, capped at 5 layers (15 pts).
        self.assertAlmostEqual(r.score_layers, min(len(r.layers_present), 5) * 3)

    def test_structures_score(self):
        # Two recognised habitat structures + one bogus → 2 distinct types.
        placed = [{"plant_id": self.some_ids[0]}]
        structures = [
            {"id": "pond"},
            {"id": "bee_hotel"},
            {"id": "not_a_real_structure"},
        ]
        r = compute_habitat_score(placed, structures)
        self.assertEqual(set(r.habitat_struct_types), {"pond", "bee_hotel"})
        self.assertAlmostEqual(r.score_structs, 2 * 2)  # 2 pts per type

    def test_structure_id_fallbacks(self):
        # Structures matched by 'type' or slugified 'name', not just 'id'.
        placed = [{"plant_id": self.some_ids[0]}]
        r_type = compute_habitat_score(placed, [{"type": "swale"}])
        self.assertIn("swale", r_type.habitat_struct_types)
        r_name = compute_habitat_score(placed, [{"name": "Rain Garden"}])
        self.assertIn("rain_garden", r_name.habitat_struct_types)

    def test_structures_only_no_plants(self):
        # Structures alone still produce a score (not None).
        r = compute_habitat_score([], [{"id": "pond"}])
        self.assertIsInstance(r, HabitatScore)
        self.assertEqual(r.n_species, 0)
        self.assertAlmostEqual(r.score_structs, 2)

    def test_bloom_gap_months_within_growing_season(self):
        placed = [{"plant_id": pid} for pid in self.some_ids]
        r = compute_habitat_score(placed, [])
        for m in r.gap_months:
            self.assertIn(m, range(4, 11))
        # bloom + gap partition the 7 growing-season months.
        self.assertEqual(
            sorted(set(r.bloom_months) | set(r.gap_months)),
            list(range(4, 11)),
        )

    def test_as_dict_is_json_shaped(self):
        placed = [{"plant_id": pid} for pid in self.some_ids]
        d = compute_habitat_score(placed, []).as_dict()
        self.assertIn("total", d)
        self.assertIn("components", d)
        self.assertEqual(d["components"]["native"]["max"], 20)
        self.assertEqual(d["components"]["bloom"]["max"], 20)
        self.assertIn("lepidoptera_supported", d)

    def test_accepts_injected_connection(self):
        # Passing a connection avoids opening/closing one internally.
        conn = get_connection()
        try:
            placed = [{"plant_id": self.some_ids[0]}]
            r = compute_habitat_score(placed, [], connection=conn)
            self.assertIsInstance(r, HabitatScore)
            # Connection still usable afterward (not closed by the call).
            conn.execute("SELECT 1").fetchone()
        finally:
            conn.close()

    def test_scored_plant_ids_are_db_backed(self):
        # A bogus id contributes a placed plant but no DB row → excluded
        # from scored_plant_ids and species counts.
        placed = [{"plant_id": self.some_ids[0]}, {"plant_id": 10_000_000}]
        r = compute_habitat_score(placed, [])
        self.assertIn(self.some_ids[0], r.scored_plant_ids)
        self.assertNotIn(10_000_000, r.scored_plant_ids)
        self.assertEqual(r.n_species, 1)
        self.assertEqual(r.n_total_plants, 2)


if __name__ == "__main__":
    unittest.main()

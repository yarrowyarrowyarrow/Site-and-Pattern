"""
tests/test_sourcing.py

Covers the cost/sourcing layer added in V1.45 (schema v19):
  * src/sourcing.py pricing helpers (pure, injected get_plant — no DB)
  * the seeded price + availability data and the new search_plants filters
    (max_unit_price, common_only), via a sandboxed temp DB.
"""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.sourcing import (  # noqa: E402
    plant_price_range, estimate_cost, trim_to_budget, format_cost,
    TYPE_PRICE_DEFAULTS,
    structure_cost, mulch_cost, design_cost,
)

# ── Fake catalogue for the pure-helper tests ────────────────────────────────
_FAKE = {
    1: {"plant_type": "tree", "price_low_cad": 60, "price_high_cad": 150},
    2: {"plant_type": "herb"},                         # unpriced → type default
    3: {"plant_type": "shrub", "price_low_cad": 25, "price_high_cad": 50},
    4: {"plant_type": "mystery"},                      # unknown type → fallback
}


def _fake_get(pid):
    return _FAKE.get(pid)


class TestPricingHelpers(unittest.TestCase):

    def test_explicit_price_wins(self):
        self.assertEqual(plant_price_range(_FAKE[1]), (60.0, 150.0))

    def test_type_default_fallback(self):
        self.assertEqual(plant_price_range(_FAKE[2]), TYPE_PRICE_DEFAULTS["herb"])

    def test_unknown_type_fallback(self):
        # falls back to the herb-like default range, never crashes
        lo, hi = plant_price_range(_FAKE[4])
        self.assertLess(lo, hi)

    def test_low_high_normalised(self):
        # mis-ordered explicit prices are returned low-first
        self.assertEqual(
            plant_price_range({"price_low_cad": 50, "price_high_cad": 25}),
            (25.0, 50.0))

    def test_estimate_cost_sums_quantity(self):
        # tuples and dicts both accepted; quantity multiplies
        low, high = estimate_cost([(1, 1), (3, 2)], get_plant=_fake_get)
        self.assertEqual(low, 60 + 25 * 2)
        self.assertEqual(high, 150 + 50 * 2)

    def test_estimate_cost_accepts_placed_dicts(self):
        low, high = estimate_cost(
            [{"plant_id": 2, "quantity": 3}], get_plant=_fake_get)
        self.assertEqual((low, high),
                         (TYPE_PRICE_DEFAULTS["herb"][0] * 3,
                          TYPE_PRICE_DEFAULTS["herb"][1] * 3))

    def test_trim_to_budget_drops_priciest_first(self):
        kept, dropped = trim_to_budget(
            [(1, 1), (2, 1), (3, 1)], budget=30, get_plant=_fake_get)
        # tree(mid 105) and shrub(mid 37.5) dropped; herb(mid 12) kept
        self.assertEqual(kept, [(2, 1)])
        self.assertEqual(dropped, 2)

    def test_trim_keeps_at_least_one(self):
        kept, dropped = trim_to_budget(
            [(1, 1), (3, 1)], budget=1, get_plant=_fake_get)
        self.assertEqual(len(kept), 1)      # never empties the design
        self.assertEqual(dropped, 1)

    def test_trim_noop_without_budget(self):
        items = [(1, 1), (3, 1)]
        self.assertEqual(trim_to_budget(items, None, get_plant=_fake_get),
                         (items, 0))

    def test_format_cost(self):
        self.assertEqual(format_cost(8.0, 16.0), "$8–$16")


_FAKE_STRUCTS = {
    "pond":    {"id": "pond", "install_cost_cad": (400.0, 2000.0)},
    "snag":    {"id": "snag", "install_cost_cad": (0.0, 0.0)},
    "mystery": {"id": "mystery"},   # no install cost recorded → 0
}


def _fake_struct(sid):
    return _FAKE_STRUCTS.get(sid)


class TestWholeDesignCost(unittest.TestCase):
    """C1 — costing structures + mulch + the combined design total."""

    def test_structure_cost_sums_dicts(self):
        lo, hi = structure_cost(
            [_FAKE_STRUCTS["pond"], _FAKE_STRUCTS["snag"]],
            get_structure=_fake_struct)
        self.assertEqual((lo, hi), (400.0, 2000.0))

    def test_structure_cost_accepts_ids(self):
        lo, hi = structure_cost(["pond", "pond"], get_structure=_fake_struct)
        self.assertEqual((lo, hi), (800.0, 4000.0))

    def test_structure_cost_missing_is_zero(self):
        self.assertEqual(
            structure_cost([{"id": "mystery"}], get_structure=_fake_struct),
            (0.0, 0.0))

    def test_mulch_cost_volume_math(self):
        # 100 m² × 0.075 m = 7.5 m³, costed against the per-m³ range.
        lo, hi = mulch_cost(100.0)
        self.assertAlmostEqual(lo, 7.5 * 35.0, places=2)
        self.assertAlmostEqual(hi, 7.5 * 75.0, places=2)

    def test_mulch_cost_zero_or_none_area(self):
        self.assertEqual(mulch_cost(0), (0.0, 0.0))
        self.assertEqual(mulch_cost(None), (0.0, 0.0))

    def test_design_cost_combines_and_totals(self):
        bd = design_cost([(1, 1)], structures=["pond"], mulch_area_m2=100.0,
                         get_plant=_fake_get, get_structure=_fake_struct)
        self.assertEqual(bd["plants"], (60.0, 150.0))
        self.assertEqual(bd["structures"], (400.0, 2000.0))
        self.assertEqual(bd["total"][0],
                         bd["plants"][0] + bd["structures"][0] + bd["mulch"][0])
        self.assertEqual(bd["total"][1],
                         bd["plants"][1] + bd["structures"][1] + bd["mulch"][1])


class TestStructureCatalogueCost(unittest.TestCase):
    def test_every_structure_has_install_cost(self):
        from src.db.structures import get_all_structures
        for s in get_all_structures():
            ic = s.get("install_cost_cad")
            self.assertIsNotNone(ic, msg=s["id"])
            self.assertEqual(len(ic), 2, msg=s["id"])
            self.assertLessEqual(ic[0], ic[1], msg=s["id"])


class TestSeededSourcingData(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.mkdtemp(prefix="permadesign_sourcing_test_")
        import src.db.plants as plants_mod
        plants_mod._DATA_DIR = cls._tmp
        plants_mod._DB_PATH = os.path.join(cls._tmp, "t.db")
        from src.db.plants import init_db
        init_db()

    def test_every_plant_priced(self):
        from src.db.plants import search_plants
        rows = search_plants()
        self.assertTrue(rows)
        # the seed script prices every record
        self.assertTrue(all(r.get("price_low_cad") is not None for r in rows))
        self.assertTrue(all(r.get("availability_class") for r in rows))

    def test_trees_cost_more_than_forbs(self):
        from src.db.plants import search_plants
        trees = search_plants(plant_type="tree")
        herbs = search_plants(plant_type="herb")
        self.assertTrue(trees and herbs)
        self.assertGreater(max(r["price_high_cad"] for r in trees),
                           max(r["price_high_cad"] for r in herbs))

    def test_max_unit_price_filter(self):
        from src.db.plants import search_plants
        cheap = search_plants(max_unit_price=20)
        self.assertTrue(cheap)
        # nothing returned has a low price above the cap
        self.assertTrue(all((r.get("price_low_cad") or 0) <= 20 for r in cheap))
        # and it actually excludes pricey trees
        names = {r["common_name"] for r in cheap}
        pricey = {r["common_name"] for r in search_plants(plant_type="tree")
                  if r["price_low_cad"] > 20}
        self.assertTrue(pricey)
        self.assertTrue(names.isdisjoint(pricey))

    def test_common_only_excludes_rare(self):
        from src.db.plants import search_plants
        common = {r["common_name"] for r in search_plants(common_only=True)}
        rare = {r["common_name"] for r in search_plants()
                if r.get("availability_class") in ("rare", "seed_or_plug")}
        if rare:
            self.assertTrue(common.isdisjoint(rare))
        # native specialists still count as "common enough"
        self.assertTrue(common)


if __name__ == "__main__":
    unittest.main()

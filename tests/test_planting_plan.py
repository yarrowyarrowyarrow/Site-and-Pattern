"""
tests/test_planting_plan.py — the design → buy-it/plant-it Planting Plan (F40).

Covers src/planting_plan.py:
  1. Aggregation: quantity + species counts, native vs cultivated tally.
  2. Per-species facts: form by type, extended cost = unit × qty, spacing,
     planting window, nursery-source bucketing.
  3. Phasing: woody → structure, spreaders → fill, the rest → matrix.
  4. Totals: grand = plants + structures + mulch.
  5. render_plan_text content (sections, subtotals, total, phased block, sources).
  6. Edge: empty design → empty plan, no crash.
  7. planting_window: calendar months when known, sensible fallback otherwise.
  8. Integration: the real seeded DB get_plant path.

Mostly pure (an injected ``get_plant`` keeps the logic tests DB-free); one
integration test uses the temp-DB seed.
"""

import os
import sys
import tempfile
import unittest
from contextlib import closing

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Redirect the DB to a temp dir so the integration test never touches the real DB.
_TMP_DIR = tempfile.mkdtemp(prefix="permadesign_test_pp_")
import src.db.plants as _plants_mod
_plants_mod._DATA_DIR = _TMP_DIR
_plants_mod._DB_PATH = os.path.join(_TMP_DIR, "permadesign_test.db")

from src import planting_plan as pp


# A small, fully-specified plant catalogue for deterministic logic tests.
_PLANTS = {
    1: {"id": 1, "common_name": "Saskatoon", "scientific_name": "Amelanchier alnifolia",
        "plant_type": "shrub", "native_to_alberta": 1,
        "price_low_cad": 25, "price_high_cad": 50},
    2: {"id": 2, "common_name": "Wild Bergamot", "scientific_name": "Monarda fistulosa",
        "plant_type": "herb", "native_to_alberta": 1, "spacing_m": 0.45},
    3: {"id": 3, "common_name": "Trembling Aspen", "scientific_name": "Populus tremuloides",
        "plant_type": "tree", "native_to_alberta": 1},
    4: {"id": 4, "common_name": "Hosta", "scientific_name": "Hosta sieboldiana",
        "plant_type": "herb", "native_to_alberta": 0},
    5: {"id": 5, "common_name": "Wild Strawberry", "scientific_name": "Fragaria virginiana",
        "plant_type": "groundcover", "native_to_alberta": 1,
        "spread_habit": "self_seeding"},
}


def _fake_get_plant(pid):
    return dict(_PLANTS.get(pid, {}))


def _placed():
    """3× Saskatoon, 2× Wild Bergamot, 1× Aspen, 4× Hosta, 5× Wild Strawberry."""
    spec = {1: 3, 2: 2, 3: 1, 4: 4, 5: 5}
    out = []
    for pid, n in spec.items():
        for _ in range(n):
            out.append({"plant_id": pid, "common_name": _PLANTS[pid]["common_name"]})
    return out


class TestAggregation(unittest.TestCase):
    def setUp(self):
        self.plan = pp.build_planting_plan(_placed(), get_plant=_fake_get_plant)

    def test_counts(self):
        self.assertEqual(self.plan.total_plants, 15)
        self.assertEqual(self.plan.species_count, 5)
        self.assertEqual(self.plan.native_count, 11)   # 3+2+1+5
        self.assertEqual(self.plan.cultivated_count, 4)

    def test_items_sorted_by_name(self):
        names = [i.common_name for i in self.plan.items]
        self.assertEqual(names, sorted(names, key=str.lower))

    def test_extended_cost_is_unit_times_qty(self):
        sask = next(i for i in self.plan.items if i.common_name == "Saskatoon")
        self.assertEqual((sask.unit_low, sask.unit_high), (25.0, 50.0))
        self.assertEqual(sask.ext_low, 75.0)
        self.assertEqual(sask.ext_high, 150.0)

    def test_plants_total_is_sum_of_items(self):
        self.assertEqual(self.plan.plants_low, sum(i.ext_low for i in self.plan.items))
        self.assertEqual(self.plan.plants_high, sum(i.ext_high for i in self.plan.items))
        # 75+16+45+32+40 = 208 ; 150+32+120+64+80 = 446
        self.assertEqual(self.plan.plants_low, 208.0)
        self.assertEqual(self.plan.plants_high, 446.0)

    def test_form_by_type(self):
        forms = {i.common_name: i.form for i in self.plan.items}
        self.assertEqual(forms["Saskatoon"], "container")
        self.assertEqual(forms["Wild Bergamot"], "plug or seed")

    def test_source_buckets(self):
        bucket = {i.common_name: i.source_bucket for i in self.plan.items}
        self.assertEqual(bucket["Saskatoon"], "native_woody")
        self.assertEqual(bucket["Trembling Aspen"], "native_woody")
        self.assertEqual(bucket["Wild Bergamot"], "native_herb")
        self.assertEqual(bucket["Wild Strawberry"], "native_herb")
        self.assertEqual(bucket["Hosta"], "cultivated")

    def test_spacing_and_window_populated(self):
        for it in self.plan.items:
            self.assertGreater(it.spacing_m, 0.0)
            self.assertTrue(it.planting_window)
        # explicit spacing_m is honoured
        berg = next(i for i in self.plan.items if i.common_name == "Wild Bergamot")
        self.assertEqual(berg.spacing_m, 0.45)
        # bigger plants get wider spacing than smaller ones
        sask = next(i for i in self.plan.items if i.common_name == "Saskatoon")
        self.assertGreater(sask.spacing_m, berg.spacing_m)


class TestPhasing(unittest.TestCase):
    def setUp(self):
        self.plan = pp.build_planting_plan(_placed(), get_plant=_fake_get_plant)

    def test_structure_phase_is_woody(self):
        structure = {i.common_name for i in self.plan.items_by_phase(pp.PHASE_STRUCTURE)}
        self.assertEqual(structure, {"Saskatoon", "Trembling Aspen"})

    def test_spreader_goes_to_fill(self):
        fill = {i.common_name for i in self.plan.items_by_phase(pp.PHASE_FILL)}
        self.assertEqual(fill, {"Wild Strawberry"})

    def test_matrix_is_the_rest(self):
        matrix = {i.common_name for i in self.plan.items_by_phase(pp.PHASE_MATRIX)}
        self.assertEqual(matrix, {"Wild Bergamot", "Hosta"})


class TestTotalsWithStructuresAndMulch(unittest.TestCase):
    def setUp(self):
        structs = [{"id": "bee_hotel", "name": "Bee hotel",
                    "install_cost_cad": (40.0, 80.0)}]
        self.plan = pp.build_planting_plan(
            _placed(), structures=structs, bed_area_m2=10.0,
            get_plant=_fake_get_plant, get_structure=lambda _sid: None)

    def test_structure_and_mulch_costs(self):
        self.assertEqual((self.plan.struct_low, self.plan.struct_high), (40.0, 80.0))
        # 10 m² at the site-prep sheet's 5–8 cm (V3.20, OV-3): 0.5 m³ × $35
        # to 0.8 m³ × $75.
        self.assertEqual((self.plan.mulch_low, self.plan.mulch_high), (17.5, 60.0))
        self.assertEqual(len(self.plan.structures_detail), 1)

    def test_grand_total_is_plants_plus_structures_plus_mulch(self):
        self.assertEqual(self.plan.grand_low, 208.0 + 40.0 + 17.5)
        self.assertEqual(self.plan.grand_high, 446.0 + 80.0 + 60.0)


class TestRenderText(unittest.TestCase):
    def test_text_contains_key_sections(self):
        plan = pp.build_planting_plan(_placed(), get_plant=_fake_get_plant)
        text = pp.render_plan_text(plan)
        self.assertIn("Planting Plan", text)
        self.assertIn("WHAT TO BUY", text)
        self.assertIn("NATIVE TREES & SHRUBS", text)
        self.assertIn("Saskatoon", text)
        self.assertIn("Subtotal:", text)
        self.assertIn("ESTIMATED TOTAL:", text)
        self.assertIn("WHEN TO PLANT", text)
        self.assertIn(pp.PHASE_STRUCTURE, text)
        # No pin, no suppliers: the list is "near you" (V3.18, EDF-1).
        self.assertIn(pp.NO_PIN_SOURCES, text)

    def test_suppliers_are_the_ones_passed_in_and_no_others(self):
        """Until V3.18 every plan printed four Calgary-area suppliers, two in
        no directory, whatever the yard (EDF-1)."""
        plan = pp.build_planting_plan(_placed(), get_plant=_fake_get_plant)
        text = pp.render_plan_text(plan, sources=[
            ("Arnica Wildflowers", "Edmonton · 3 km", ""),
            ("TreeTime.ca", "Edmonton · 6 km", "https://www.treetime.ca")])
        self.assertIn("Arnica Wildflowers — Edmonton · 3 km", text)
        self.assertIn("https://www.treetime.ca", text)
        for gone in ("ALCLA", "Bow Valley", "Bedrock", "sources:"):
            self.assertNotIn(gone, text)
        self.assertNotIn(pp.NO_PIN_SOURCES, text)


class TestThePrintoutsWords(unittest.TestCase):
    """WD-5 (V3.30): "Where to buy around Edmonton", and a price said as the
    pack says it, never "AB retail"."""

    EDMONTON = {"latitude": 53.52, "longitude": -113.50}

    def test_the_heading_names_the_place(self):
        self.assertEqual(pp.buy_heading(self.EDMONTON),
                         "Where to buy around Edmonton")
        self.assertEqual(pp.buy_heading({"latitude": 50.0,
                                         "longitude": -110.5}),
                         "Where to buy near your yard")

    def test_the_price_words(self):
        self.assertEqual(pp.price_words(self.EDMONTON),
                         "an estimate at Edmonton native nurseries; prices "
                         "vary by nursery and year")
        self.assertNotIn("Edmonton", pp.price_words(
            {"latitude": 43.65, "longitude": -79.38}))

    def test_the_text_plan(self):
        plan = pp.build_planting_plan(_placed(), get_plant=_fake_get_plant)
        text = pp.render_plan_text(
            plan, sources=[("Arnica Wildflowers", "Edmonton · 3 km", "")],
            site_config=self.EDMONTON)
        self.assertIn("Where to buy around Edmonton:", text)
        self.assertIn("at Edmonton native nurseries", text)
        for gone in ("AB retail", "seed sources near your yard"):
            self.assertNotIn(gone, text)


class TestPlantingWindow(unittest.TestCase):
    def test_calendar_month_when_known(self):
        # Trembling Aspen is transplanted in May in the seeded calendar.
        win = pp.planting_window({"common_name": "Trembling Aspen", "plant_type": "tree"})
        self.assertIn("May", win)

    def test_fallback_when_unknown(self):
        win = pp.planting_window({"common_name": "Nonexistent Plant", "plant_type": "shrub"})
        self.assertTrue(win)
        self.assertNotEqual(win.strip(), "")


class TestEmptyDesign(unittest.TestCase):
    def test_empty_plan_does_not_crash(self):
        plan = pp.build_planting_plan([], get_plant=_fake_get_plant)
        self.assertEqual(plan.total_plants, 0)
        self.assertEqual(plan.species_count, 0)
        self.assertEqual(plan.items, [])
        self.assertEqual(plan.grand_low, 0.0)
        text = pp.render_plan_text(plan)
        self.assertIn("Planting Plan", text)


class TestRealDBIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from src.db.plants import init_db
        init_db()

    def test_the_plan_and_the_order_file_name_the_same_suppliers(self):
        """One directory, one list (V3.18, EDF-1): every supplier the order
        file names for the native channels is in the plan's list, and the
        plan names nothing the directory does not hold."""
        from src.db.nurseries import all_nurseries
        from src.order_file import suppliers_for
        sc = {"latitude": 53.5461, "longitude": -113.4938}
        names = [nm for nm, _w, _u in pp.sources_near(sc)]
        self.assertTrue(names, "no suppliers near Edmonton")
        directory = {n["name"] for n in all_nurseries()}
        self.assertTrue(set(names) <= directory, set(names) - directory)
        for channel in ("native_specialist", "seed_or_plug"):
            for entry in suppliers_for(channel, sc["latitude"],
                                       sc["longitude"]):
                self.assertIn(entry.split(" (")[0], names, (channel, entry))

    def test_no_pin_no_suppliers(self):
        self.assertEqual(pp.sources_near({}), [])
        self.assertEqual(pp.sources_near(None), [])

    def test_builds_from_seeded_get_plant(self):
        from src.db.plants import get_connection
        # closing(), not `with get_connection()`: sqlite3's own context
        # manager commits or rolls back a TRANSACTION and leaves the
        # connection open, which is where this suite's
        # 'ResourceWarning: unclosed database' noise came from.
        with closing(get_connection()) as conn:
            row = conn.execute(
                "SELECT id, common_name FROM plants "
                "WHERE native_to_alberta = 1 LIMIT 1"
            ).fetchone()
        self.assertIsNotNone(row, "expected at least one seeded native plant")
        pid, name = row[0], row[1]
        placed = [{"plant_id": pid, "common_name": name}] * 3
        plan = pp.build_planting_plan(placed)   # default get_plant → real DB
        self.assertEqual(plan.total_plants, 3)
        self.assertEqual(plan.species_count, 1)
        item = plan.items[0]
        self.assertTrue(item.form)
        self.assertGreater(item.spacing_m, 0.0)
        self.assertTrue(item.planting_window)


if __name__ == "__main__":
    unittest.main()

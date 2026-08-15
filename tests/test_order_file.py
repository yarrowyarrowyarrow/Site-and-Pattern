"""
tests/test_order_file.py — an order file a nursery accepts (F92, V2.57).

F40 produces the buy list as prose and as a PDF page, which is right for a
document somebody reads and wrong for the next step: attaching a file to an
email to a nursery. This is that last centimetre.

Qt-free throughout — it builds rows and writes CSV text.
"""

import csv
import io
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_TMP = tempfile.mkdtemp(prefix="permadesign_order_")
try:
    import src.db.plants as _plants_mod
    _plants_mod._DATA_DIR = _TMP
    _plants_mod._DB_PATH = os.path.join(_TMP, "t.db")
except Exception:  # pragma: no cover
    pass

from src import order_file as of  # noqa: E402
from src.project_store import ProjectStore  # noqa: E402

_CATALOGUE = {
    1: {"id": 1, "common_name": "Saskatoon Berry", "scientific_name": "Amelanchier alnifolia",
        "plant_type": "shrub", "availability_class": "native_specialist",
        "price_low_cad": 12.0, "price_high_cad": 20.0},
    2: {"id": 2, "common_name": "Wild Bergamot", "scientific_name": "Monarda fistulosa",
        "plant_type": "wildflower", "availability_class": "garden_centre",
        "price_low_cad": 6.0, "price_high_cad": 10.0},
    3: {"id": 3, "common_name": "Blue Grama", "scientific_name": "Bouteloua gracilis",
        "plant_type": "grass", "availability_class": "seed_or_plug",
        "price_low_cad": 4.0, "price_high_cad": 7.0},
}
_GP = lambda pid: _CATALOGUE.get(pid, {})            # noqa: E731


def _project(with_pin=True):
    props = {}
    if with_pin:
        props["site_config"] = {"latitude": 53.5461, "longitude": -113.4938}
    return {"type": "FeatureCollection", "features": [], "properties": props}


def _design(counts=((1, 2), (2, 3), (3, 1)), with_pin=True):
    p = _project(with_pin)
    store = ProjectStore(p)
    for i, (pid, n) in enumerate(counts):
        name = _CATALOGUE.get(pid, {}).get("common_name", f"Plant {pid}")
        for j in range(n):
            store.add_plant(pid, name,
                            53.5461 + (i * 10 + j) * 1e-5, -113.4938)
    return p, store.placed_plants


class TestOrderLines(unittest.TestCase):
    def test_one_line_per_species_with_quantities(self):
        project, placed = _design()
        lines = of.build_order_lines(placed, project, get_plant=_GP)
        self.assertEqual(len(lines), 3)
        self.assertEqual({l.common_name: l.qty for l in lines},
                         {"Saskatoon Berry": 2, "Wild Bergamot": 3,
                          "Blue Grama": 1})

    def test_numbers_match_the_planting_map(self):
        """Line 7 on the order must be plant 7 on the drawing. Two documents
        that number the same plants differently are worse than one."""
        from src.planting_map import build_planting_map
        project, placed = _design()
        pm = build_planting_map(placed, project, get_plant=_GP)
        lines = of.build_order_lines(placed, project, get_plant=_GP)
        self.assertEqual([l.number for l in lines],
                         [e.number for e in pm.key])
        self.assertEqual([l.plant_id for l in lines],
                         [e.plant_id for e in pm.key])

    def test_botanical_names_are_carried(self):
        """The common name is what a person says; the botanical name is what a
        nursery fills the order against."""
        project, placed = _design()
        for line in of.build_order_lines(placed, project, get_plant=_GP):
            self.assertTrue(line.scientific_name,
                            f"{line.common_name} has no botanical name")

    def test_line_totals_are_unit_times_quantity(self):
        project, placed = _design()
        for line in of.build_order_lines(placed, project, get_plant=_GP):
            self.assertAlmostEqual(line.total_low, line.unit_low * line.qty, 2)
            self.assertAlmostEqual(line.total_high, line.unit_high * line.qty, 2)

    def test_totals_add_up(self):
        project, placed = _design()
        lines = of.build_order_lines(placed, project, get_plant=_GP)
        qty, low, high = of.order_totals(lines)
        self.assertEqual(qty, 6)
        self.assertAlmostEqual(low, 12 * 2 + 6 * 3 + 4 * 1, 2)
        self.assertAlmostEqual(high, 20 * 2 + 10 * 3 + 7 * 1, 2)
        self.assertLess(low, high)


class TestGrouping(unittest.TestCase):
    def test_grouped_by_sourcing_channel(self):
        project, placed = _design()
        groups = dict(of.group_by_channel(
            of.build_order_lines(placed, project, get_plant=_GP)))
        self.assertEqual(set(groups), {"native_specialist", "garden_centre",
                                       "seed_or_plug"})

    def test_hardest_to_find_comes_first(self):
        """The things needing a phone call go at the top, not buried under the
        things you can pick up on the way home."""
        project, placed = _design()
        order = [ch for ch, _g in of.group_by_channel(
            of.build_order_lines(placed, project, get_plant=_GP))]
        self.assertLess(order.index("native_specialist"),
                        order.index("garden_centre"))

    def test_empty_channels_are_dropped(self):
        """An empty 'Big-box' heading tells a reader there is something to buy
        there."""
        project, placed = _design(counts=((1, 2),))
        groups = of.group_by_channel(
            of.build_order_lines(placed, project, get_plant=_GP))
        self.assertEqual(len(groups), 1)

    def test_an_unrecorded_channel_still_gets_a_row(self):
        cat = dict(_CATALOGUE)
        cat[9] = {"id": 9, "common_name": "Mystery", "scientific_name": "Ignotum",
                  "plant_type": "shrub", "availability_class": ""}
        project, placed = _design(counts=((9, 1),))
        lines = of.build_order_lines(placed, project,
                                     get_plant=lambda p: cat.get(p, {}))
        groups = dict(of.group_by_channel(lines))
        self.assertIn("", groups)
        self.assertIn("not recorded", of.CHANNEL_LABELS[""])


class TestSuppliers(unittest.TestCase):
    def test_no_pin_means_no_suppliers_rather_than_a_national_list(self):
        """The whole point is 'near you'. A national list dressed as a local
        one is exactly the false precision this codebase keeps removing."""
        self.assertEqual(of.suppliers_for("native_specialist", None, None), [])

    def test_site_latlng_reads_the_pin(self):
        self.assertEqual(of.site_latlng(_project()),
                         (53.5461, -113.4938))
        self.assertEqual(of.site_latlng(_project(with_pin=False)),
                         (None, None))


class TestCsv(unittest.TestCase):
    def _rows(self, **kw):
        project, placed = _design(**kw)
        lines = of.build_order_lines(placed, project, get_plant=_GP)
        text = of.write_csv(lines, project)
        return list(csv.reader(io.StringIO(text))), lines

    def test_the_header_is_the_declared_columns(self):
        rows, _ = self._rows()
        self.assertEqual(rows[0], list(of.COLUMNS))

    def test_every_species_appears(self):
        rows, lines = self._rows()
        blob = "\n".join(",".join(r) for r in rows)
        for line in lines:
            self.assertIn(line.scientific_name, blob)

    def test_it_carries_a_total_row(self):
        rows, lines = self._rows()
        total = [r for r in rows if r and r[0] == "TOTAL"]
        self.assertEqual(len(total), 1)
        qty, _low, _high = of.order_totals(lines)
        self.assertEqual(total[0][4], str(qty))

    def test_the_price_caveat_travels_with_the_file(self):
        """The file is what leaves the app; a range is an estimate and the
        reader is about to spend money against it."""
        rows, _ = self._rows()
        blob = " ".join(" ".join(r) for r in rows).lower()
        self.assertIn("estimate", blob)
        self.assertIn("confirm before ordering", blob)

    def test_channel_tokens_never_reach_the_file(self):
        """`native_specialist` is a database token. A nursery should never be
        sent one."""
        rows, _ = self._rows()
        blob = " ".join(" ".join(r) for r in rows)
        for token in ("native_specialist", "seed_or_plug", "garden_centre",
                      "big_box"):
            self.assertNotIn(token, blob)

    def test_an_empty_design_still_writes_a_valid_file(self):
        text = of.write_csv([], _project())
        rows = list(csv.reader(io.StringIO(text)))
        self.assertEqual(rows[0], list(of.COLUMNS))


class TestWriteToDisk(unittest.TestCase):
    def test_it_round_trips_through_a_file(self):
        project, placed = _design()
        lines = of.build_order_lines(placed, project, get_plant=_GP)
        path = os.path.join(tempfile.mkdtemp(prefix="order_"), "o.csv")
        of.write_order_file(path, lines, project)
        with open(path, "r", encoding="utf-8-sig", newline="") as fh:
            rows = list(csv.reader(fh))
        self.assertEqual(rows[0], list(of.COLUMNS))

    def test_no_blank_line_between_every_row(self):
        """csv does its own line endings; without newline="" every row is
        double-spaced on Windows, where most of this app's users are."""
        project, placed = _design()
        lines = of.build_order_lines(placed, project, get_plant=_GP)
        path = os.path.join(tempfile.mkdtemp(prefix="order2_"), "o.csv")
        of.write_order_file(path, lines, project)
        with open(path, "rb") as fh:
            raw = fh.read()
        self.assertNotIn(b"\r\r\n", raw)


class TestNoNewDependency(unittest.TestCase):
    def test_csv_only_and_stdlib_only(self):
        """XLSX was deliberately skipped: openpyxl is not installed, not a
        declared dependency, and a new runtime import is the class of change
        that has broken the frozen Windows build before."""
        path = os.path.join(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__))), "src", "order_file.py")
        with open(path, "r", encoding="utf-8") as fh:
            src = fh.read()
        for dep in ("openpyxl", "xlsxwriter", "pandas"):
            self.assertNotIn(f"import {dep}", src)


if __name__ == "__main__":
    unittest.main()

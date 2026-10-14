"""
tests/test_one_spacing.py — one spacing for one plant, wherever it is printed
(V3.19, QF-9).

The first review (R20) found Wild Bergamot "0.3 m apart" on its page and
"0.9 m apart" in the PDF's planting-map key. The 0.9 was not the generator's
(it lays Wild Bergamot out at 0.5 m) and not the catalogue's: the buy list read
the seed file's key, ``spacing_m``, off a database row whose column is
``spacing_meters``, found nothing, and printed the layer/spread estimate for
every real plant. Its tests passed because their fake catalogue used the seed
file's key. These read the real catalogue row.
"""

import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_TMP = tempfile.mkdtemp(prefix="one_spacing_")
import src.db.plants as _plants  # noqa: E402
_plants._DATA_DIR = _TMP
_plants._DB_PATH = os.path.join(_TMP, "permadesign_test.db")

from src import planting_spacing  # noqa: E402

try:
    from PyQt6.QtWidgets import QApplication, QLabel
    _HAVE_QT = True
except Exception:                                          # noqa: BLE001
    _HAVE_QT = False

_SEED = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(
    __file__))), "data", "plants_master.json")


_APP = None


def setUpModule():
    _plants.init_db()


def _app():
    """The one QApplication, held so it is not collected under a widget."""
    global _APP
    _APP = QApplication.instance() or QApplication(["permadesign-tests"])
    return _APP


def tearDownModule():
    shutil.rmtree(_TMP, ignore_errors=True)


def _row(name):
    from src.db.plants import get_connection, get_plant
    conn = get_connection()
    try:
        pid = conn.execute("SELECT id FROM plants WHERE common_name = ?",
                           (name,)).fetchone()["id"]
    finally:
        conn.close()
    return get_plant(pid)


def _example():
    """The worked example on the real catalogue: two Wild Bergamot in it."""
    from src import onboarding
    from src.project_store import ProjectStore
    project, missing = onboarding.build_example_project()
    assert not missing, missing
    return project, ProjectStore(project).placed_plants


class _Recorder:
    """A painter that keeps the text it is asked to draw and ignores the
    rest, so a PDF page's words can be read without a PDF reader."""

    def __init__(self):
        self.texts = []

    def drawText(self, *args):
        self.texts.append(str(args[-1]))

    def __getattr__(self, _name):
        return lambda *a, **k: None


class TestTheNumberTold(unittest.TestCase):

    def test_the_catalogue_column_is_read(self):
        """A database row names it ``spacing_meters``; the buy list read
        ``spacing_m`` and so never saw it."""
        from src.planting_plan import _spacing_for
        berg = _row("Wild Bergamot")
        self.assertEqual(berg["spacing_meters"], 0.3)
        self.assertEqual(_spacing_for(berg), 0.3)
        self.assertEqual(planting_spacing.spacing_to_plant_m(berg), 0.3)
        # The number it printed instead, so this test means something.
        self.assertAlmostEqual(
            planting_spacing.plant_spacing(berg, base_m=0.45), 0.878)

    def test_it_is_the_circle_the_map_draws(self):
        """The map draws every placed plant ``spacing_meters`` across
        (``MainWindow._plant_info``), generated or hand-placed, so the number
        a person is told is the one they see drawn."""
        from src.db.plants import get_all_plants
        off = [r["common_name"] for r in get_all_plants()
               if planting_spacing.spacing_to_plant_m(r)
               != float(r["spacing_meters"])]
        self.assertEqual(off, [])

    def test_every_shipped_plant_carries_its_own_spacing(self):
        """So the estimate never stands in for a catalogue plant on the page,
        the buy list or the key."""
        import json
        with open(_SEED, encoding="utf-8") as fh:
            rows = json.load(fh)
        bare = [r["common_name"] for r in rows
                if not float(r.get("spacing_m") or 0) > 0]
        self.assertEqual(bare, [])

    def test_printed_one_way(self):
        """The key printed ``:.1f``: 0.25 m read "0.2" and 0.45 m "0.5"."""
        words = planting_spacing.spacing_words
        self.assertEqual(words(0.3), "0.3 m")
        self.assertEqual(words(0.25), "0.25 m")
        self.assertEqual(words(0.45), "0.45 m")
        self.assertEqual(words(0.878), "0.9 m")
        self.assertEqual(words(3), "3 m")
        self.assertEqual(words(None), "")

    def test_a_row_with_no_spacing_is_estimated(self):
        est = planting_spacing.spacing_to_plant_m(
            {"plant_type": "shrub", "mature_canopy_m": 2.0})
        self.assertEqual(est, 2.0)


class TestWildBergamotAgrees(unittest.TestCase):
    """The acceptance: the page and the PDF say the same for Wild Bergamot."""

    def test_the_species_entry(self):
        from src.plant_directory import species_entry
        berg = _row("Wild Bergamot")
        self.assertEqual(species_entry(berg["id"])["spacing_m"], 0.3)

    def test_the_text_plan_and_its_key(self):
        from src import planting_plan_export
        from src.planting_plan import build_planting_plan
        project, placed = _example()
        plan = build_planting_plan(placed)
        text = planting_plan_export.assemble(project, placed, [], plan)
        berg = [ln for ln in text.splitlines() if "Wild Bergamot" in ln]
        self.assertTrue(any("space ~0.3 m" in ln for ln in berg), berg)
        self.assertTrue(any("2 plants, 0.3 m apart" in ln for ln in berg),
                        berg)
        self.assertFalse(any("0.9 m" in ln for ln in berg), berg)

    @unittest.skipUnless(_HAVE_QT, "PyQt6 not installed in this env")
    def test_the_pdf_key_and_buy_list(self):
        _app()
        from src import pdf_export
        from src.planting_map import build_planting_map
        from src.planting_plan import build_planting_plan
        project, placed = _example()
        plan = build_planting_plan(placed)

        page = _Recorder()
        pdf_export._draw_planting_map(
            page, 600.0, 800.0, build_planting_map(placed, project, plan=plan),
            1.0)
        key = [t for t in page.texts if "Wild Bergamot" in t]
        self.assertEqual(len(key), 1, page.texts)
        self.assertTrue(key[0].endswith("×2  ·  0.3 m apart"), key)

        page = _Recorder()
        pdf_export._draw_planting_plan(page, 600.0, 800.0, plan, 1.0)
        at = page.texts.index("Wild Bergamot")
        # Species, Form, Qty, then Space.
        self.assertEqual(page.texts[at + 3], "0.3 m")

    @unittest.skipUnless(_HAVE_QT, "PyQt6 not installed in this env")
    def test_the_plant_page(self):
        _app()
        from src.species_page import SpeciesPage
        page = SpeciesPage()
        self.addCleanup(page.deleteLater)
        page.show_plant(_row("Wild Bergamot"))
        size = [lbl.text() for lbl in page.findChildren(QLabel)
                if "apart" in lbl.text()]
        self.assertEqual(len(size), 1, size)
        self.assertTrue(size[0].endswith("0.3 m apart"), size)


if __name__ == "__main__":
    unittest.main()

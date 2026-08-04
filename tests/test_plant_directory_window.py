"""
tests/test_plant_directory_window.py — the directory as a window (F90, V2.41).

The Qt-free half is covered in ``test_plant_directory.py``. These run the real
widget against the real catalogue, because the two things most likely to break
here cannot be seen from the core: whether it opens **with no MainWindow**, and
whether the facet strip is actually wired to the query rather than merely drawn.

The database is redirected to a temp directory, as every DB-touching module in
this suite does — these must never touch the real catalogue at
``~/.local/share/Site & Pattern/``.
"""

import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_TMP = tempfile.mkdtemp(prefix="sp_dir_")

# The house redirect, in two halves and both are load-bearing.
#
# Patch the module's own path constants at import — `user_paths.user_data_dir`
# is the wrong lever, because `_DB_PATH` is what `get_connection` actually
# reads. Then call `init_db()` at **setUpClass**, not here: these globals are
# last-write-wins across the whole suite, so by the time a test runs, the path
# may belong to whichever module was imported after this one. Seeding at run
# time initialises whatever the global points at then, which is why
# `test_plant_panel_smoke` does the same and why doing it at import failed the
# moment this module ran beside it.
import src.db.plants as _plants
_plants._DATA_DIR = _TMP
_plants._DB_PATH = os.path.join(_TMP, "permadesign_test.db")

try:
    from PyQt6.QtWidgets import QApplication, QLabel
    _HAVE_QT = True
except Exception:                                          # noqa: BLE001
    _HAVE_QT = False


def tearDownModule():
    shutil.rmtree(_TMP, ignore_errors=True)


@unittest.skipUnless(_HAVE_QT, "PyQt6 not installed in this env")
class TestTheDirectoryWindow(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls._app = QApplication.instance() or QApplication(["permadesign-tests"])
        _plants.init_db()
        from src.plant_directory_window import PlantDirectoryWindow
        # No MainWindow anywhere in this test — that is the requirement.
        cls.win = PlantDirectoryWindow(None)

    @classmethod
    def tearDownClass(cls):
        cls.win.close()
        cls.win.deleteLater()

    def setUp(self):
        self.win.preset({})

    def test_it_opens_with_no_mainwindow_and_shows_the_catalogue(self):
        self.assertIsNone(self.win._main)
        self.assertGreater(len(self.win._rows), 300)
        self.assertIn("species", self.win._count.text())

    def test_every_facet_and_toggle_is_drawn(self):
        from src import plant_directory as pd
        self.assertEqual(set(self.win._combos), {f[0] for f in pd.FACETS})
        self.assertEqual(set(self.win._toggles), {t[0] for t in pd.TOGGLES})

    def test_a_toggle_actually_narrows_the_result(self):
        """The control has to reach the query. A filter that only repaints is
        the exact dead-control shape V2.37 shipped twice."""
        before = len(self.win._rows)
        self.win._toggles["keystone_only"].setChecked(True)
        self.addCleanup(self.win._toggles["keystone_only"].setChecked, False)
        after = len(self.win._rows)
        self.assertLess(after, before)
        self.assertGreater(after, 0)

    def test_the_search_box_reaches_the_query(self):
        self.win._search.setText("saskatoon")
        self.addCleanup(self.win._search.setText, "")
        names = [r["common_name"] for r in self.win._rows]
        self.assertTrue(any("Saskatoon" in n for n in names), names[:5])

    def test_a_facet_reaches_the_query(self):
        combo = self.win._combos["type"]
        self.addCleanup(lambda: combo.set_checked_keys([], emit=True))
        combo.set_checked_keys(["tree"], emit=True)
        types = {r.get("plant_type") for r in self.win._rows}
        self.assertEqual(types, {"tree"})

    def test_selecting_a_species_fills_the_page(self):
        self.win._search.setText("saskatoon")
        self.addCleanup(self.win._search.setText, "")
        self.win._show_species(self.win._rows[0])
        text = " ".join(l.text() for l in self.win._pane.findChildren(QLabel))
        self.assertIn("Saskatoon Berry", text)
        self.assertIn("Amelanchier", text)
        for heading in ("Conditions", "Size", "Found in"):
            self.assertIn(heading, text)

    def test_the_page_shows_range_evidence_not_a_bare_region(self):
        self.win._search.setText("saskatoon")
        self.addCleanup(self.win._search.setText, "")
        self.win._show_species(self.win._rows[0])
        text = " ".join(l.text() for l in self.win._pane.findChildren(QLabel))
        self.assertIn("records", text)
        self.assertIn("confidence", text)

    def test_conditions_read_as_words_not_snake_case(self):
        self.win._search.setText("saskatoon")
        self.addCleanup(self.win._search.setText, "")
        self.win._show_species(self.win._rows[0])
        texts = [l.text() for l in self.win._pane.findChildren(QLabel)]
        conditions = texts[texts.index("Conditions") + 1]
        self.assertIn("Full Sun", conditions)
        self.assertNotIn("full_sun", conditions)

    def test_a_colour_hex_never_reaches_the_page(self):
        """`flower_color` holds either a name or a hex triplet; the hex drives
        the 3D bloom and is meaningless as prose."""
        self.win._search.setText("saskatoon")
        self.addCleanup(self.win._search.setText, "")
        self.win._show_species(self.win._rows[0])
        for label in self.win._pane.findChildren(QLabel):
            self.assertNotIn("#", label.text())

    def test_preset_replaces_rather_than_merges(self):
        """The window is a singleton. Merging would silently AND today's
        request onto whatever was left in the box last time."""
        self.win._search.setText("saskatoon")
        self.win._toggles["keystone_only"].setChecked(True)
        self.win.preset({"type": ["tree"]})
        self.assertEqual(self.win._search.text(), "")
        self.assertFalse(self.win._toggles["keystone_only"].isChecked())
        self.assertEqual({r.get("plant_type") for r in self.win._rows}, {"tree"})

    def test_an_empty_result_clears_the_species_page(self):
        self.win._search.setText("zzzzz-no-such-plant")
        self.addCleanup(self.win._search.setText, "")
        self.assertEqual(self.win._rows, [])
        text = " ".join(l.text() for l in self.win._pane.findChildren(QLabel))
        self.assertIn("Pick a species", text)

    def test_opening_a_species_asks_for_its_photo(self):
        """The list warms photos only when a row is *expanded*, and the species
        page never expands anything — so without this it would say "not
        downloaded yet" for every species the user did not happen to expand."""
        asked = []
        original = self.win._model.warm_photo
        self.win._model.warm_photo = lambda p: asked.append(p.get("id"))
        self.addCleanup(setattr, self.win._model, "warm_photo", original)
        self.win._search.setText("saskatoon")
        self.addCleanup(self.win._search.setText, "")
        self.win._show_species(self.win._rows[0])
        self.assertEqual(asked, [self.win._rows[0]["id"]])

    def test_the_quiz_gets_the_species_you_filtered_to(self):
        """`field_study.generate_quiz` already took an arbitrary plant list —
        it was written design-aware but never required a design. Study a
        filter, then be tested on it."""
        self.win._toggles["keystone_only"].setChecked(True)
        self.addCleanup(self.win._toggles["keystone_only"].setChecked, False)
        expected = list(self.win._rows)
        self.win._open_quiz()
        quiz = self.win._quiz_window
        self.addCleanup(quiz.close)
        self.assertEqual(quiz._provider(), expected)
        self.assertIn(str(len(expected)), quiz.windowTitle())


@unittest.skipUnless(_HAVE_QT, "PyQt6 not installed in this env")
class TestTheSingleton(unittest.TestCase):

    def setUp(self):
        import src.plant_directory_window as mod
        self.mod = mod
        self._app = QApplication.instance() or QApplication(["permadesign-tests"])
        _plants.init_db()
        self.addCleanup(self._reset)

    def _reset(self):
        win = self.mod._WINDOW
        if win is not None:
            win.close()
            win.deleteLater()
        self.mod._WINDOW = None

    def test_opening_twice_without_a_mainwindow_reuses_one_window(self):
        first = self.mod.open_plant_directory(None)
        second = self.mod.open_plant_directory(None)
        self.assertIs(first, second)

    def test_it_hangs_the_singleton_on_main_when_there_is_one(self):
        """The pattern open_3d_view and open_snapshot_view use, so no new
        MainWindow method is needed and the guard's method ceiling holds."""
        class _FakeMain:
            pass

        main = _FakeMain()
        win = self.mod.open_plant_directory(main)
        self.addCleanup(win.close)
        self.assertIs(main._plant_directory_window, win)
        self.assertIs(self.mod.open_plant_directory(main), win)

    def test_a_bloom_preset_arrives_filtered(self):
        win = self.mod.open_plant_directory(None, {"bloom_months": ["6"]})
        self.assertEqual(win._combos["bloom_months"].checked_keys(), ["6"])


if __name__ == "__main__":
    unittest.main()

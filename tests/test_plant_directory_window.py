"""
tests/test_plant_directory_window.py — the directory as a window (F90, V2.41;
built from the shared picker and page since V3.00).

The Qt-free half is covered in ``test_plant_directory.py``. These run the real
widget against the real catalogue, because the two things most likely to break
here cannot be seen from the core: whether it opens **with no MainWindow**, and
whether the filters are actually wired to the query rather than merely drawn.

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
    from PyQt6.QtWidgets import QApplication, QLabel, QWidget
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
        self.win.page.show_empty()
        self.win.preset({})

    def _search(self, text: str):
        self.win.picker.search_box.setText(text)
        self.win.picker.refresh()          # not waiting for the debounce
        self.addCleanup(self.win.preset, {})

    def _show_first(self):
        self.win.page.show_plant(self.win.rows()[0])
        return " ".join(l.text() for l in self.win.page.findChildren(QLabel))

    def test_it_opens_with_no_mainwindow_and_shows_the_catalogue(self):
        self.assertIsNone(self.win._main)
        self.assertGreater(len(self.win.rows()), 300)
        self.assertIn("plants", self.win.picker.count_label.text())

    def test_every_facet_and_quality_is_drawn(self):
        from src import plant_directory as pd
        self.assertEqual(set(self.win.picker.combos), {f[0] for f in pd.FACETS})
        self.assertEqual(set(self.win.picker.chips), {t[0] for t in pd.TOGGLES})

    def test_a_reference_room_shows_its_filters_and_reads_by_name(self):
        self.assertTrue(self.win.picker.filters_open())
        self.assertEqual(self.win.picker.order(), "name")
        names = [r["common_name"].lower() for r in self.win.rows()]
        self.assertEqual(names, sorted(names))

    def test_a_quality_actually_narrows_the_result(self):
        """The control has to reach the query. A filter that only repaints is
        the exact dead-control shape V2.37 shipped twice."""
        before = len(self.win.rows())
        chip = self.win.picker.chips["supports_specialist"]
        chip.setChecked(True)
        self.addCleanup(chip.setChecked, False)
        after = len(self.win.rows())
        self.assertLess(after, before)
        self.assertGreater(after, 0)

    def test_the_search_box_reaches_the_query(self):
        self._search("saskatoon")
        names = [r["common_name"] for r in self.win.rows()]
        self.assertTrue(any("Saskatoon" in n for n in names), names[:5])

    def test_a_facet_reaches_the_query(self):
        combo = self.win.picker.combos["type"]
        self.addCleanup(lambda: combo.set_checked_keys([], emit=True))
        combo.set_checked_keys(["tree"], emit=True)
        types = {r.get("plant_type") for r in self.win.rows()}
        self.assertEqual(types, {"tree"})

    def test_selecting_a_species_fills_the_page(self):
        self._search("saskatoon")
        self.win.picker.view.setCurrentIndex(self.win.picker.model.index(0, 0))
        text = " ".join(l.text() for l in self.win.page.findChildren(QLabel))
        self.assertIn("Saskatoon Berry", text)
        self.assertIn("Amelanchier", text)
        for heading in ("Conditions", "Size", "Found in", "Roles"):
            self.assertIn(heading, text)

    def test_the_page_shows_range_evidence_not_a_bare_region(self):
        self._search("saskatoon")
        text = self._show_first()
        self.assertIn("records", text)
        self.assertIn("confidence", text)

    def test_conditions_read_as_words_not_snake_case(self):
        self._search("saskatoon")
        self._show_first()
        texts = [l.text() for l in self.win.page.findChildren(QLabel)]
        conditions = texts[texts.index("Conditions") + 1]
        self.assertIn("Full Sun", conditions)
        self.assertNotIn("full_sun", conditions)

    def test_a_colour_hex_never_reaches_the_page(self):
        """`flower_color` holds either a name or a hex triplet; the hex drives
        the 3D bloom and is meaningless as prose."""
        import re
        self._search("saskatoon")
        self._show_first()
        for label in self.win.page.findChildren(QLabel):
            shown = re.sub(r"<[^>]+>", "", label.text())   # what is read
            self.assertNotIn("#", shown)

    def test_preset_replaces_rather_than_merges(self):
        """The window is a singleton. Merging would silently AND today's
        request onto whatever was left in the box last time."""
        self.win.picker.search_box.setText("saskatoon")
        self.win.picker.chips["edible_only"].setChecked(True)
        self.win.preset({"type": ["tree"]})
        self.assertEqual(self.win.picker.search_box.text(), "")
        self.assertFalse(self.win.picker.chips["edible_only"].isChecked())
        self.assertEqual({r.get("plant_type") for r in self.win.rows()}, {"tree"})

    def test_an_empty_result_clears_the_species_page(self):
        self._search("saskatoon")
        self._show_first()
        self._search("zzzzz-no-such-plant")
        self.assertEqual(self.win.rows(), [])
        self.assertEqual(self.win.page.shown_id(), 0)
        text = " ".join(l.text() for l in self.win.page.findChildren(QLabel))
        self.assertIn("Pick a species", text)
        self.assertIn("No plants match", self.win.picker.count_label.text())

    def test_opening_a_species_asks_for_its_photo(self):
        """The list fetches a photo only when asked, and the page is the only
        thing that asks — without this it would say "not downloaded yet" for
        the whole session."""
        asked = []
        self.win.page._photo_warmer = lambda p: asked.append(p.get("id"))
        self.addCleanup(setattr, self.win.page, "_photo_warmer",
                        self.win.picker.model.warm_photo)
        self._search("saskatoon")
        self._show_first()
        self.assertEqual(asked, [self.win.rows()[0]["id"]])

    def test_without_a_design_the_page_offers_no_place(self):
        self._search("saskatoon")
        self._show_first()
        self.assertIsNone(self.win.page.findChild(QWidget, "placeButton"))

    def test_the_quiz_gets_the_species_you_filtered_to(self):
        """`field_study.generate_quiz` already took an arbitrary plant list —
        it was written design-aware but never required a design. Study a
        filter, then be tested on it."""
        chip = self.win.picker.chips["supports_specialist"]
        chip.setChecked(True)
        self.addCleanup(chip.setChecked, False)
        expected = list(self.win.rows())
        self.win._open_quiz()
        quiz = self.win._quiz_window
        self.addCleanup(quiz.close)
        self.assertEqual(quiz._provider(), expected)
        self.assertIn(str(len(expected)), quiz.windowTitle())


@unittest.skipUnless(_HAVE_QT, "PyQt6 not installed in this env")
class TestPlacingFromTheDirectory(unittest.TestCase):
    """With a design open the page offers Place, which hands the plant to the
    Browse tab armed and brings the map forward (V3.00)."""

    def setUp(self):
        self._app = QApplication.instance() or QApplication(["permadesign-tests"])
        _plants.init_db()

        class _Panel:
            def __init__(self):
                self.placed, self.mixed = [], []

            def placed_count(self, pid):
                return 2

            def in_mix(self, pid):
                return any(p.get("id") == pid for p in self.mixed)

            def place_from_elsewhere(self, plant):
                self.placed.append(plant.get("id"))

            def add_to_mix(self, plant):
                self.mixed.append(plant)

        class _Main:
            def __init__(self):
                self.plant_panel = _Panel()
                self.raised = 0

            def raise_(self):
                self.raised += 1

            def activateWindow(self):
                pass

        from src.plant_directory_window import PlantDirectoryWindow
        self.main = _Main()
        self.win = PlantDirectoryWindow(self.main)
        self.addCleanup(self.win.deleteLater)
        self.addCleanup(self.win.close)
        self.win.picker.search_box.setText("saskatoon")
        self.win.picker.refresh()
        self.win.picker.view.setCurrentIndex(self.win.picker.model.index(0, 0))

    def test_the_page_says_how_many_are_in_the_design(self):
        texts = [l.text() for l in self.win.page.findChildren(QLabel)]
        self.assertIn("2 in this design", texts)

    def test_place_hands_the_plant_to_the_panel_and_raises_the_map(self):
        button = self.win.page.findChild(QWidget, "placeButton")
        self.assertIn("Saskatoon Berry", button.accessibleName())
        button.click()
        self.assertEqual(self.main.plant_panel.placed, [self.win.rows()[0]["id"]])
        self.assertEqual(self.main.raised, 1)

    def test_add_to_mix_goes_to_the_panel_and_the_button_says_so(self):
        mix = self.win.page.findChild(QWidget, "speciesPageMix")
        mix.click()
        self.assertEqual(len(self.main.plant_panel.mixed), 1)
        self.assertEqual(mix.text(), "In the mix")
        self.assertFalse(mix.isEnabled())


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
        self.assertEqual(win.picker.combos["bloom_months"].checked_keys(), ["6"])


if __name__ == "__main__":
    unittest.main()

"""
tests/test_filter_area.py — the picker's filters in two tiers (V3.14).

The owner, of the Plant Library's filters: "This is also so so busy and needs
work." Nineteen controls showed at once. The everyday ones now show first and
the rest wait behind More filters, which says how many of them are on.
"""

import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_TMP = tempfile.mkdtemp(prefix="sp_filter_area_")
import src.db.plants as _plants  # noqa: E402
_plants._DATA_DIR = _TMP
_plants._DB_PATH = os.path.join(_TMP, "permadesign_test.db")

try:
    from PyQt6.QtWidgets import QApplication, QWidget
    _HAVE_QT = True
except Exception:                                          # noqa: BLE001
    _HAVE_QT = False


def tearDownModule():
    shutil.rmtree(_TMP, ignore_errors=True)


@unittest.skipUnless(_HAVE_QT, "PyQt6 not installed in this env")
class TestTwoTiers(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls._app = (QApplication.instance()
                    or QApplication(["permadesign-tests"]))
        _plants.init_db()

    def _picker(self, **kwargs):
        from src.plant_picker import PlantPicker
        holder = QWidget()
        self.addCleanup(holder.deleteLater)
        picker = PlantPicker(holder, filters_open=True, **kwargs)
        picker.refresh()
        return picker

    def test_every_filter_is_in_exactly_one_tier(self):
        from src import plant_filters as pf
        from src.filter_area import EVERYDAY
        keys = {f.key for f in pf.FACETS} | {q.key for q in pf.QUALITIES}
        self.assertLessEqual(set(EVERYDAY), keys, "a key in EVERYDAY is no "
                             "filter: it would silently show nothing")
        picker = self._picker()
        self.assertEqual(set(picker.combos), {f.key for f in pf.FACETS})
        self.assertEqual(set(picker.chips), {q.key for q in pf.QUALITIES})

    def test_a_side_panel_shows_the_everyday_ones_first(self):
        from src.filter_area import EVERYDAY
        picker = self._picker()
        area = picker.filter_area
        self.assertFalse(area.more_open())
        shown = {k for k, w in {**picker.combos, **picker.chips}.items()
                 if w.isVisibleTo(picker)}
        self.assertEqual(shown, set(EVERYDAY))
        self.assertLessEqual(len(shown), 8, "the panel is busy again")
        area.more_button.click()
        self.assertTrue(area.more_open())
        self.assertTrue(all(w.isVisibleTo(picker) for w in
                            {**picker.combos, **picker.chips}.values()))

    def test_the_directory_window_shows_both(self):
        self.assertTrue(self._picker(wide=True).filter_area.more_open())

    def test_a_filter_past_the_fold_is_never_silent(self):
        picker = self._picker()
        picker.set_criteria({"fruit_months": ["8"], "edible_only": True})
        area = picker.filter_area
        self.assertIn("2 on", area.more_button.text())
        self.assertIn("Fruits in: August", picker.chip_texts())
        self.assertIn("Edible", picker.chip_texts())
        picker.remove("edible_only")
        self.assertIn("1 on", area.more_button.text())
        picker.clear_filters()
        self.assertEqual(area.more_button.text(), "More filters ▸")

    def test_the_soil_toggle_stays_with_the_everyday_ones(self):
        picker = self._picker()
        picker.set_soil_ph(6.8)
        self.assertFalse(picker.soil_toggle.isHidden())
        self.assertIs(picker.soil_toggle, picker.filter_area.everyday_chips.soil)
        self.assertIsNone(picker.filter_area.more_chips.soil)

    def test_native_names_the_province_whichever_tier_it_is_in(self):
        picker = self._picker()
        picker.set_site((52.13, -106.67))          # Saskatoon
        self.assertIn("Saskatchewan", picker.chips["native_only"].toolTip())


if __name__ == "__main__":
    unittest.main()

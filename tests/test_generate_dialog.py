"""
tests/test_generate_dialog.py

Headless-Qt tests for src/generate_design_dialog.py, the Plan My Yard dialog
(PY-1, PY-9, V3.28): what it says when something is missing, the four
questions, and what the Advanced tools add, including the V1.47 "design for
wildlife" fauna picker. The dialog takes its
fauna_options as a plain list of dicts (it never touches the DB), so these
tests need no temp DB.

Same skip-gracefully pattern as tests/test_plant_panel_smoke.py — skips cleanly
when PyQt6 is unavailable. Run locally with::

    QT_QPA_PLATFORM=offscreen python -m unittest tests.test_generate_dialog -v
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Force offscreen platform BEFORE importing anything Qt-touching.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def _qt_available():
    try:
        import PyQt6  # noqa: F401
        from PyQt6.QtWidgets import QApplication  # noqa: F401
        return True
    except Exception:
        return False


_FAUNA_OPTS = [
    {"id": 8, "common_name": "Monarch", "taxon": "lepidoptera", "icon": "🦋"},
    {"id": 12, "common_name": "Bumblebees", "taxon": "bee", "icon": "🐝"},
]


@unittest.skipUnless(_qt_available(), "PyQt6 not installed in this env")
class TestGenerateDialogFaunaPicker(unittest.TestCase):

    _app = None

    @classmethod
    def setUpClass(cls):
        from PyQt6.QtWidgets import QApplication
        cls._app = QApplication.instance() or QApplication(["permadesign-tests"])

    def _make(self, **kw):
        from src.generate_design_dialog import GenerateDesignDialog
        kw.setdefault("has_boundary", True)
        kw.setdefault("has_pin", True)
        kw.setdefault("advanced", True)     # the picker is an advanced tool
        return GenerateDesignDialog(**kw)

    def test_no_picker_without_options(self):
        dlg = self._make()
        self.assertIsNone(dlg._fauna_list)
        self.assertEqual(dlg.selected_fauna(), [])
        dlg.deleteLater()

    def test_picker_lists_options(self):
        dlg = self._make(fauna_options=_FAUNA_OPTS)
        self.assertIsNotNone(dlg._fauna_list)
        self.assertEqual(dlg._fauna_list.count(), 2)
        self.assertEqual(dlg.selected_fauna(), [])      # nothing ticked yet
        dlg.deleteLater()

    def test_selection_returns_ids_not_rows(self):
        from PyQt6.QtCore import Qt
        dlg = self._make(fauna_options=_FAUNA_OPTS)
        dlg._fauna_list.item(0).setCheckState(Qt.CheckState.Checked)
        self.assertEqual(dlg.selected_fauna(), [8])     # the id, not the row
        dlg._fauna_list.item(1).setCheckState(Qt.CheckState.Checked)
        self.assertEqual(sorted(dlg.selected_fauna()), [8, 12])
        dlg.deleteLater()

    def test_option_without_id_is_skipped(self):
        dlg = self._make(fauna_options=[{"common_name": "Nameless"}] + _FAUNA_OPTS)
        self.assertEqual(dlg._fauna_list.count(), 2)    # the id-less one dropped
        dlg.deleteLater()


@unittest.skipUnless(_qt_available(), "PyQt6 not installed in this env")
class TestTheDialogFitsALaptop(unittest.TestCase):
    """V3.05: the dialog was 769 px tall, taller than a 1366 x 768 screen,
    so Generate and Cancel sat below its bottom edge (the surface audit)."""

    _app = None

    @classmethod
    def setUpClass(cls):
        from PyQt6.QtWidgets import QApplication
        cls._app = QApplication.instance() or QApplication(["permadesign-tests"])

    def _many(self, n=720):
        return [{"id": i, "common_name": f"Animal {i}", "taxon": "bee",
                 "icon": "🐝"} for i in range(1, n)] + [
            {"id": 9999, "common_name": "Monarch", "taxon": "lepidoptera",
             "icon": "🦋"}]

    def _make(self):
        from src.generate_design_dialog import GenerateDesignDialog
        return GenerateDesignDialog(has_boundary=True, has_pin=True,
                                    advanced=True,
                                    areas={"beds": 2, "beds_m2": 31.0,
                                           "yard_m2": 150.0},
                                    last_plan=42,
                                    fauna_options=self._many())

    def test_it_is_never_taller_than_the_screen(self):
        dlg = self._make()
        avail = dlg.screen().availableGeometry().height()
        self.assertLessEqual(dlg.height(), avail - 72)
        dlg.deleteLater()

    def test_the_buttons_are_outside_the_scroll(self):
        from PyQt6.QtWidgets import QDialogButtonBox, QScrollArea
        dlg = self._make()
        scroll = dlg.findChild(QScrollArea)
        buttons = dlg.findChild(QDialogButtonBox)
        self.assertIsNotNone(scroll)
        self.assertFalse(scroll.isAncestorOf(buttons),
                         "Generate would scroll out of sight with the goals")
        dlg.deleteLater()

    def test_typing_finds_an_animal(self):
        dlg = self._make()
        dlg._fauna_find.setText("monarch")
        shown = [dlg._fauna_list.item(i).text()
                 for i in range(dlg._fauna_list.count())
                 if not dlg._fauna_list.item(i).isHidden()]
        self.assertEqual(len(shown), 1)
        self.assertIn("Monarch", shown[0])
        dlg._fauna_find.setText("")
        hidden = sum(dlg._fauna_list.item(i).isHidden()
                     for i in range(dlg._fauna_list.count()))
        self.assertEqual(hidden, 0)
        dlg.deleteLater()


def _dialog(**kw):
    from src.generate_design_dialog import GenerateDesignDialog
    kw.setdefault("has_boundary", True)
    kw.setdefault("has_pin", True)
    kw.setdefault("areas", {"beds": 0, "beds_m2": 0.0, "yard_m2": 150.0})
    return GenerateDesignDialog(**kw)


def _texts(dlg):
    from PyQt6.QtWidgets import QAbstractButton, QLabel
    return ([w.text() for w in dlg.findChildren(QLabel)]
            + [w.text() for w in dlg.findChildren(QAbstractButton)])


@unittest.skipUnless(_qt_available(), "PyQt6 not installed in this env")
class TestWhatIsMissing(unittest.TestCase):
    """§4.2: the first line says what is missing, a button does it."""

    @classmethod
    def setUpClass(cls):
        from PyQt6.QtWidgets import QApplication
        cls._app = QApplication.instance() or QApplication(["permadesign-tests"])

    def _buttons(self, dlg):
        return [(b.text(), b) for b in dlg._step_buttons]

    def test_no_pin(self):
        from src.generate_design_dialog import NEEDS_PIN
        dlg = _dialog(has_pin=False)
        self.assertEqual(dlg.state, NEEDS_PIN)
        self.assertIn("Find your yard first, so the plan can use your soil "
                      "and sun.", _texts(dlg))
        self.assertEqual([t for t, _b in self._buttons(dlg)], ["Find my yard"])
        dlg.deleteLater()

    def test_a_pin_and_nothing_outlined(self):
        dlg = _dialog(has_boundary=False, areas={})
        self.assertIn("Outline where you want to plant: your whole yard, or "
                      "just the beds.", _texts(dlg))
        self.assertEqual([t for t, _b in self._buttons(dlg)],
                         ["Outline my yard", "Draw a bed"])
        dlg.deleteLater()

    def test_outside_says_the_regions_message_and_offers_nothing(self):
        dlg = _dialog(outside=True, coverage="Far from here.")
        self.assertIn("Far from here.", _texts(dlg))
        self.assertEqual(dlg._step_buttons, [])
        self.assertNotIn("Plan my yard", [t for t in _texts(dlg)
                                          if t != "<b>Plan my yard</b>"])
        dlg.deleteLater()

    def test_a_bed_alone_is_ready(self):
        from src.generate_design_dialog import READY
        dlg = _dialog(has_boundary=False,
                      areas={"beds": 1, "beds_m2": 18.0, "yard_m2": 0.0})
        self.assertEqual(dlg.state, READY)
        self.assertEqual(dlg.where(), "beds")
        dlg.deleteLater()

    def test_each_button_closes_with_its_step(self):
        from src.generate_design_dialog import NEXT_STEP
        for kw, want in (({"has_pin": False}, ["site"]),
                         ({"has_boundary": False, "areas": {}},
                          ["draw", "shape:Garden Bed"])):
            for i, target in enumerate(want):
                dlg = _dialog(**kw)
                dlg._step_buttons[i].click()
                self.assertEqual(dlg.result(), NEXT_STEP)
                self.assertEqual(dlg.next_step, target)
                dlg.deleteLater()

    def test_each_step_arms_the_right_tool(self):
        """PY-9: the targets are the overview's, which open the tools."""
        from unittest import mock
        from src import yard_overview_flow
        main = mock.MagicMock()
        yard_overview_flow.run_action(main, "site")
        main.site_panel.focus_address_search.assert_called_once()
        yard_overview_flow.run_action(main, "draw")
        main._enter_boundary_mode.assert_called_once()
        yard_overview_flow.run_action(main, "shape:Garden Bed")
        main.toolbar.shape_tool.set_type.assert_called_once_with("Garden Bed")


@unittest.skipUnless(_qt_available(), "PyQt6 not installed in this env")
class TestTheFourQuestions(unittest.TestCase):
    """§4.3, simple and advanced."""

    @classmethod
    def setUpClass(cls):
        from PyQt6.QtWidgets import QApplication
        cls._app = QApplication.instance() or QApplication(["permadesign-tests"])

    def test_where_is_asked_only_with_beds(self):
        dlg = _dialog()
        self.assertEqual(list(dlg._where), ["yard"])
        self.assertFalse(dlg._where["yard"].isEnabled())
        dlg.deleteLater()
        dlg = _dialog(areas={"beds": 2, "beds_m2": 31.0, "yard_m2": 150.0})
        self.assertEqual(list(dlg._where), ["beds", "yard"])
        self.assertEqual(dlg.where(), "beds")              # chosen first
        self.assertIn("In the beds I drew (2 beds, about 30 m²)", _texts(dlg))
        dlg._where["yard"].setChecked(True)
        self.assertEqual(dlg.where(), "yard")
        dlg.deleteLater()

    def test_how_full_by_cover(self):
        dlg = _dialog()
        self.assertEqual(dlg.cover(), 0.70)
        self.assertTrue(dlg._full["now"].text().startswith(
            "Fill it now: about "))
        self.assertIn("$", dlg._full["now"].text())
        dlg._full["summers"].setChecked(True)
        self.assertEqual(dlg.cover(), 0.40)
        self.assertTrue(dlg._full["summers"].text().startswith(
            "Over two or three summers: about "))
        self.assertTrue(dlg._full["summers"].text().endswith(
            " now, mulch between"))
        dlg.deleteLater()

    def test_the_estimate_follows_where(self):
        dlg = _dialog(areas={"beds": 1, "beds_m2": 18.0, "yard_m2": 150.0})
        bed = dlg._full["now"].text()
        dlg._where["yard"].setChecked(True)
        self.assertNotEqual(dlg._full["now"].text(), bed)
        dlg.deleteLater()

    def test_must_haves_word_for_word(self):
        dlg = _dialog(place="Edmonton",
                      preselected=["well_behaved", "low_cost"])
        self.assertEqual([cb.text() for cb in dlg._musts.values()], [
            "Leave out plants known to spread",
            "Easy to buy around Edmonton",
            "Leave out plants known to be poisonous to pets",
            "Leave out plants known to be poisonous to people",
            "Food for people: berries and fruit"])
        self.assertEqual([k for k, cb in dlg._musts.items() if cb.isChecked()],
                         ["well_behaved", "low_cost"])
        dlg.deleteLater()

    def test_simple_goals_are_native_here_and_pollinators_and_the_musts(self):
        from src.design_goals import LOCAL_KEY
        dlg = _dialog(preselected=["well_behaved"])
        self.assertEqual(dlg.selected_goals(),
                         [LOCAL_KEY, "pollinator", "well_behaved"])
        dlg.deleteLater()

    def test_simple_has_no_advanced_controls_or_ai(self):
        dlg = _dialog(fauna_options=_FAUNA_OPTS)
        self.assertIsNone(dlg._fauna_list)
        self.assertEqual(list(dlg._full), ["now", "summers"])
        self.assertIsNone(dlg._match_site_check)
        self.assertEqual(dlg._more, {})
        words = " ".join(_texts(dlg))
        for bad in ("AI", "brief", "Ollama", "Sparse", "density",
                    "Generate", "boundary", "species"):
            self.assertNotIn(bad, words)
        dlg.deleteLater()

    def test_advanced_adds_densities_goals_picker_and_terrain(self):
        dlg = _dialog(advanced=True, fauna_options=_FAUNA_OPTS,
                      preselected=["pollinator", "well_behaved"])
        self.assertEqual(list(dlg._full),
                         ["now", "summers", "sparse", "balanced"])
        dlg._full["sparse"].setChecked(True)
        self.assertEqual((dlg.cover(), dlg.density()), (0.25, "sparse"))
        self.assertIsNotNone(dlg._fauna_list)
        self.assertIsNotNone(dlg._match_site_check)
        self.assertIn("pollinator", dlg._more)
        self.assertEqual(dlg.selected_goals(), ["pollinator", "well_behaved"])
        dlg.deleteLater()

    def test_the_button_says_plan_my_yard(self):
        from PyQt6.QtWidgets import QDialogButtonBox
        dlg = _dialog()
        box = dlg.findChild(QDialogButtonBox)
        ok = box.button(QDialogButtonBox.StandardButton.Ok)
        self.assertEqual(ok.text(), "Plan my yard")
        self.assertEqual(dlg.windowTitle(), "Plan my yard")
        dlg.deleteLater()


class TestTheEstimate(unittest.TestCase):
    """The counts in the labels say about (§4.3)."""

    def test_more_cover_takes_more_plants(self):
        from src.plan_cover import estimate
        now, later = estimate(150, 0.70), estimate(150, 0.40)
        self.assertGreater(now["plants"], later["plants"])
        self.assertLess(now["low"], now["high"])
        self.assertEqual(estimate(0, 0.7)["plants"], 0)

    def test_it_is_near_what_the_probe_yard_placed(self):
        """248 and 92 plants were placed on the probe's 150 m² (V3.29;
        267 and 95 in V3.28, before the fill took the widest plants)."""
        from src.plan_cover import estimate
        self.assertLess(abs(estimate(150, 0.70)["plants"] - 248), 248 * 0.25)
        self.assertLess(abs(estimate(150, 0.40)["plants"] - 92), 92 * 0.25)


if __name__ == "__main__":
    unittest.main()

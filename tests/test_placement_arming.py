"""
tests/test_placement_arming.py — selecting is the arming gesture (V2.37).

User feedback: "selecting a plant or plant community or building a plant
community mix should be sufficient to then place that unit on the map, an auto
select if you will instead of having to press 'Place on Map' ... often I end up
placing the wrong thing (the last thing) because I haven't hit the button."

The failure mode these guard is specific: arming was a separate act, so the map
kept holding whatever was armed *last*. Changing the species, the mix or the
pattern without pressing again meant the next map click planted the previous
choice — a wrong plant in the ground, which is expensive to notice and annoying
to undo. So the assertions are about *re-arming on every change*, not merely
about the first arm working.

Offscreen Qt; skipped where PyQt6 isn't importable.
"""

import os
import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PyQt6.QtWidgets import QApplication
    _HAVE_QT = True
except ImportError:                                  # pragma: no cover
    _HAVE_QT = False

import src.db.plants as _plants_mod                  # noqa: E402


@unittest.skipUnless(_HAVE_QT, "PyQt6 not installed in this env")
class TestPlantPanelArming(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._app = QApplication.instance() or QApplication(["permadesign-tests"])
        cls._tmp = tempfile.mkdtemp(prefix="permadesign_arm_")
        _plants_mod._DATA_DIR = cls._tmp
        _plants_mod._DB_PATH = os.path.join(cls._tmp, "t.db")
        cls._orig_dir = _plants_mod._user_data_dir
        _plants_mod._user_data_dir = lambda: pathlib.Path(cls._tmp)
        from src.db.plants import init_db
        init_db()

    @classmethod
    def tearDownClass(cls):
        _plants_mod._user_data_dir = cls._orig_dir

    def _panel(self):
        from src.plant_panel import PlantPanel
        from src.db.plants import search_plants
        panel = PlantPanel()
        self._plants = search_plants()[:3]
        return panel

    def test_selecting_a_plant_arms_the_map(self):
        panel = self._panel()
        armed = []
        panel.place_plant_requested.connect(
            lambda pid, name, qty, pat: armed.append(name))

        panel._selected_plant = self._plants[0]
        panel._auto_arm()

        self.assertEqual(armed, [self._plants[0]["common_name"]])
        self.assertTrue(panel._armed)

    def test_changing_the_plant_rearms_with_the_new_one(self):
        """The reported bug: the map kept holding the previous choice."""
        panel = self._panel()
        armed = []
        panel.place_plant_requested.connect(
            lambda pid, name, qty, pat: armed.append(name))

        panel._selected_plant = self._plants[0]
        panel._auto_arm()
        panel._selected_plant = self._plants[1]
        panel._auto_arm()

        self.assertEqual(armed[-1], self._plants[1]["common_name"],
                         "the map is still armed with the previous plant")

    def test_changing_the_pattern_rearms(self):
        panel = self._panel()
        armed = []
        panel.place_plant_requested.connect(
            lambda pid, name, qty, pat: armed.append(pat.get("kind")))

        panel._selected_plant = self._plants[0]
        panel._auto_arm()
        panel._placement.set_kind("row")
        panel._on_pattern_kind_changed("row")

        self.assertEqual(armed[-1], "row",
                         "switching to Row left the map armed with the old pattern")

    def test_setting_the_count_after_arming_reaches_the_map(self):
        """The V2.38 regression report: "I manually increased the number using
        the arrows from auto to 11. When I placed it it was only 3 plants."

        Auto-arming reads the pattern at SELECTION time. Only the pattern KIND
        announced itself, so a Count set afterwards never reached the map and it
        placed the `auto` count derived from spacing instead.
        """
        panel = self._panel()
        armed = []
        panel.place_plant_requested.connect(
            lambda pid, name, qty, pat: armed.append(pat))

        panel._selected_plant = self._plants[0]
        panel._placement.set_kind("row")
        panel._auto_arm()
        self.assertIsNone(armed[-1]["params"].get("count") or None)

        panel._placement._row_count.setValue(11)
        panel._rearm_timer.stop()          # fire the debounce now, not in 150 ms
        panel._on_pattern_params_changed()
        panel._rearm_timer.stop()
        panel._auto_arm()

        self.assertEqual(armed[-1]["params"].get("count"), 11,
                         "the map is still armed with the old count")

    def test_every_placement_parameter_announces_itself(self):
        """The root cause was one un-emitted signal, so the guard is that no
        control feeding current_pattern() stays silent. A new spinner added
        without a connection fails here rather than in someone's garden."""
        panel = self._panel()
        controls = panel._placement
        watched = [
            (controls._row_count, 7), (controls._grid_rows, 4),
            (controls._grid_cols, 3), (controls._circle_count, 9),
            (controls._fill_spacing, 2.5), (controls._overlap_slider, 20),
        ]
        for control, value in watched:
            with self.subTest(control=control.objectName() or type(control).__name__):
                seen = []
                controls.patternChanged.connect(lambda: seen.append(1))
                control.setValue(value)
                self.assertTrue(seen, f"{control} changed without announcing it")
                controls.patternChanged.disconnect()

        for box in (controls._row_drift, controls._grid_stagger,
                    controls._circle_fill, controls._fill_matrix,
                    controls._canopy_base_checkbox):
            with self.subTest(box=box.text()):
                seen = []
                controls.patternChanged.connect(lambda: seen.append(1))
                box.toggle()
                self.assertTrue(seen, f"{box.text()!r} toggled silently")
                controls.patternChanged.disconnect()

    def test_parameter_changes_are_debounced(self):
        """Each re-arm is a round trip to the map; holding a spinner arrow
        emits per tick. Without the delay that is the lag the tester felt."""
        panel = self._panel()
        panel._selected_plant = self._plants[0]
        panel._auto_arm()
        armed = []
        panel.place_plant_requested.connect(lambda *a: armed.append(a))

        for n in range(2, 12):             # holding the up-arrow
            panel._placement._row_count.setValue(n)

        self.assertEqual(armed, [], "re-armed mid-drag instead of waiting")
        self.assertTrue(panel._rearm_timer.isActive())

    def test_a_parameter_change_while_disarmed_does_not_arm(self):
        """Fiddling with the controls before choosing a plant must not seize
        the map."""
        panel = self._panel()
        armed = []
        panel.place_plant_requested.connect(lambda *a: armed.append(a))
        panel._placement._row_count.setValue(5)
        self.assertEqual(armed, [])
        self.assertFalse(panel._rearm_timer.isActive())

    def test_fill_area_still_needs_an_explicit_press(self):
        """Fill Area enters polygon-draw mode immediately rather than arming a
        click, so auto-arming it would hijack the map during list navigation."""
        panel = self._panel()
        fills = []
        panel.fill_area_requested.connect(lambda *a: fills.append(a))

        panel._placement.set_kind("fill")
        panel._selected_plant = self._plants[0]
        panel._auto_arm()

        self.assertEqual(fills, [], "Fill Area armed itself from a selection")

    def test_the_button_says_what_is_armed(self):
        """Selection arms silently, so the chip is the only thing left
        answering "what am I about to place?"."""
        panel = self._panel()
        panel._selected_plant = self._plants[0]
        panel._auto_arm()

        label = panel._place_btn.text()
        self.assertIn(self._plants[0]["common_name"], label)
        self.assertNotEqual(label, "Place on Map")

    def test_standing_down_restores_the_plain_button(self):
        panel = self._panel()
        panel._selected_plant = self._plants[0]
        panel._auto_arm()
        panel.set_armed(False)

        self.assertFalse(panel._armed)
        self.assertEqual(panel._place_btn.text(), "Place on Map")

    def test_the_chip_click_asks_to_cancel_rather_than_re_arming(self):
        panel = self._panel()
        cancels = []
        panel.placement_cancelled.connect(lambda: cancels.append(1))
        placements = []
        panel.place_plant_requested.connect(lambda *a: placements.append(a))

        panel._selected_plant = self._plants[0]
        panel._auto_arm()
        before = len(placements)
        panel._on_place_btn_clicked()

        self.assertEqual(cancels, [1])
        self.assertEqual(len(placements), before, "clicking the chip re-armed")


@unittest.skipUnless(_HAVE_QT, "PyQt6 not installed in this env")
class TestMainWindowStandsPanelsDown(unittest.TestCase):
    """The chip is a claim about the map, so ending placement must withdraw it —
    otherwise the panel says "Placing:" at a map that stopped listening."""

    def test_cancel_draw_clears_both_panels(self):
        import ast
        src = pathlib.Path(__file__).resolve().parent.parent / "src" / "app.py"
        tree = ast.parse(src.read_text(encoding="utf-8"))
        fn = next(n for n in ast.walk(tree)
                  if isinstance(n, ast.FunctionDef) and n.name == "_cancel_draw")
        body = ast.dump(fn)
        self.assertIn("set_armed", body,
                      "_cancel_draw no longer stands the panels down")

    def test_cancel_signals_are_wired(self):
        src = (pathlib.Path(__file__).resolve().parent.parent
               / "src" / "app.py").read_text(encoding="utf-8")
        self.assertIn("placement_cancelled.connect", src)
        self.assertIn("placementCancelled.connect", src)


if __name__ == "__main__":
    unittest.main()


@unittest.skipUnless(_HAVE_QT, "PyQt6 not installed in this env")
class TestTwoLineFacetItems(unittest.TestCase):
    """V2.38 user feedback, with a screenshot: the ecoregion list clipped every
    entry mid-word — "Moist Mixed Gras...ina (Saskatoon)" — because the name and
    the geography were packed into one label in a combo that shares its row
    50/50. The name now gets its own line and the place sits under it."""

    @classmethod
    def setUpClass(cls):
        cls._app = QApplication.instance() or QApplication(["permadesign-tests"])

    def _combo(self):
        from src.filter_widgets import CheckableComboBox
        from src.plant_panel import _ECOREGION_CHOICES, _ECOREGION_DISPLAY
        c = CheckableComboBox(placeholder="Restoring toward…")
        for _label, key in _ECOREGION_CHOICES:
            if not key:
                continue
            name, where = _ECOREGION_DISPLAY[key]
            c.add_check_item(name, key, subtitle=where)
        return c

    def test_every_region_has_a_name_and_a_place(self):
        from src.plant_panel import _ECOREGION_CHOICES, _ECOREGION_DISPLAY
        for _label, key in _ECOREGION_CHOICES:
            if not key:
                continue
            self.assertIn(key, _ECOREGION_DISPLAY)
            name, where = _ECOREGION_DISPLAY[key]
            self.assertTrue(name.strip(), key)
            self.assertTrue(where.strip(), key)
            self.assertNotIn("(", name,
                             f"{key}: the place is still packed into the name")

    def test_the_item_carries_the_subtitle_separately(self):
        from src.filter_widgets import SUBTITLE_ROLE
        combo = self._combo()
        item = combo.model().item(0)
        self.assertEqual(item.text(), "Aspen Parkland")
        self.assertEqual(item.data(SUBTITLE_ROLE), "central AB / SK")

    def test_rows_are_tall_enough_for_two_lines(self):
        from PyQt6.QtWidgets import QStyleOptionViewItem
        combo = self._combo()
        delegate = combo.itemDelegate()
        opt = QStyleOptionViewItem()
        opt.initFrom(combo.view())
        two = delegate.sizeHint(opt, combo.model().index(0, 0)).height()
        self.assertGreater(two, opt.fontMetrics.height() * 1.8,
                           "the second line has nowhere to go")

    def test_the_popup_is_wider_than_the_combo_that_opens_it(self):
        """The clipping came from the popup inheriting a half-row-wide combo."""
        combo = self._combo()
        self.assertGreaterEqual(combo.view().minimumWidth(), 260)

    def test_many_selections_summarise_rather_than_clip(self):
        combo = self._combo()
        combo.set_checked_keys(["aspen_parkland", "moist_mixed_grassland",
                        "riparian"])
        self.assertEqual(combo.lineEdit().text(), "3 selected")
        # …but the full list stays reachable.
        self.assertIn("Moist Mixed Grassland", combo.lineEdit().toolTip())

    def test_one_or_two_selections_still_name_themselves(self):
        combo = self._combo()
        combo.set_checked_keys(["riparian"])
        self.assertEqual(combo.lineEdit().text(), "Riparian")

    def test_items_without_a_subtitle_are_untouched(self):
        """Every other facet combo shares this widget and must not change."""
        from src.filter_widgets import CheckableComboBox
        plain = CheckableComboBox(placeholder="Any")
        plain.add_check_item("Full Sun", "full_sun")
        self.assertFalse(getattr(plain, "_two_line", False))

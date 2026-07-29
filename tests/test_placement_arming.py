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
        cls._app = QApplication.instance() or QApplication([])
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

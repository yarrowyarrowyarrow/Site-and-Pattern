"""
tests/test_shape_tool.py — Draw › Shape, with Hedgerow folded in (V3.07).

The Structures tab's Shapes and Hedgerow pages moved to the Draw row as one
tool on the owner's answers to the V3.05 surface audit. What the form emits is
what the two pages emitted, to the same handlers, so the map's side is
unchanged; these pin the form and the button.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PyQt6.QtWidgets import QApplication
    _HAVE_QT = True
except Exception:                                          # noqa: BLE001
    _HAVE_QT = False


@unittest.skipUnless(_HAVE_QT, "PyQt6 not installed in this env")
class TestTheShapeForm(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls._app = QApplication.instance() or QApplication(["sp-tests"])

    def setUp(self):
        from src.shape_tool import ShapeTool
        self.tool = ShapeTool()
        self.addCleanup(self.tool.deleteLater)
        self.areas, self.lines, self.drawn = [], [], []
        self.tool.place_shape_requested.connect(self.areas.append)
        self.tool.place_hedgerow_requested.connect(self.lines.append)
        self.tool.drawing.connect(lambda: self.drawn.append(True))

    def _types(self):
        combo = self.tool._type
        return [combo.itemText(i) for i in range(combo.count())
                if combo.itemData(i) is not None]

    def test_areas_zones_and_lines_in_one_list(self):
        from src.lawn_zones import ZONE_TYPES
        from src.shape_tool import AREA_PRESETS, LINE_KINDS
        self.assertEqual(self._types(),
                         list(AREA_PRESETS)
                         + [s["label"] for s in ZONE_TYPES.values()]
                         + [words for words, _style in LINE_KINDS])

    def test_an_area_draws_as_the_shapes_page_did(self):
        self.tool.set_type("Pathway")
        self.tool._label.setText("Front path")
        self.tool._height.setValue(0.0)
        self.tool._draw.click()
        self.assertEqual(self.lines, [])
        self.assertEqual(self.areas, [{
            "shape_type": "Pathway", "label": "Front path",
            "fill_color": "#8d6e63", "stroke_color": "#5d4037",
            "fill_opacity": 0.35, "dash_array": "8 4", "height_m": 0.0}])
        self.assertEqual(self.drawn, [True])

    def test_a_hedge_is_a_line_with_the_hedgerow_pages_settings(self):
        self.assertTrue(self.tool.set_type("Windbreak"))
        self.assertFalse(self.tool._area.isVisibleTo(self.tool))
        self.assertTrue(self.tool._line.isVisibleTo(self.tool))
        self.tool._species.setText("Caragana")
        self.tool._draw.click()
        self.assertEqual(self.areas, [])
        self.assertEqual(self.lines, [{
            "style": "windbreak", "width_m": 1.5, "spacing_m": 1.0,
            "species": "Caragana", "color": "#4caf50"}])

    def test_a_lawn_conversion_zone_takes_its_own_colours(self):
        from src.lawn_zones import ZONE_TYPES
        spec = next(iter(ZONE_TYPES.values()))
        self.tool.set_type(spec["label"])
        payload = self.tool.area_payload()
        self.assertEqual((payload["fill_color"], payload["stroke_color"]),
                         (spec["fill"], spec["stroke"]))
        self.assertTrue(self.tool._area.isVisibleTo(self.tool))


@unittest.skipUnless(_HAVE_QT, "PyQt6 not installed in this env")
class TestTheDrawRowButton(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls._app = QApplication.instance() or QApplication(["sp-tests"])

    def setUp(self):
        from src.toolbar import MainToolbar
        self.bar = MainToolbar()
        self.addCleanup(self.bar.deleteLater)
        self.areas, self.lines = [], []
        self.bar.place_shape_requested.connect(self.areas.append)
        self.bar.place_hedgerow_requested.connect(self.lines.append)

    def test_shape_sits_beside_boundary(self):
        from PyQt6.QtWidgets import QToolButton
        words = [b.text() for b in self.bar.findChildren(QToolButton)
                 if b.text()]
        self.assertIn("▱ Shape", words)
        self.assertLess(words.index("⬡ Boundary"), words.index("▱ Shape"))
        self.assertLess(words.index("▱ Shape"), words.index("📏 Measure"))

    def test_draw_arms_the_map_and_shows_the_tool_on(self):
        self.bar._act_measure.setChecked(True)
        self.bar.shape_tool.set_type("Garden Bed")
        self.bar.shape_tool._draw.click()
        self.assertEqual(len(self.areas), 1)
        self.assertTrue(self.bar._shape_btn.isChecked())
        self.assertFalse(self.bar._act_measure.isChecked())
        self.bar.shape_tool.set_type("Fence")
        self.bar.shape_tool._draw.click()
        self.assertEqual(self.lines[-1]["style"], "fence")

    def test_finishing_or_cancelling_puts_it_back(self):
        self.bar.shape_tool._draw.click()
        self.bar.reset_draw_buttons()
        self.assertFalse(self.bar._shape_btn.isChecked())
        self.bar.shape_tool._draw.click()
        cancelled = []
        self.bar.cancel_draw_requested.connect(lambda: cancelled.append(1))
        self.bar._on_cancel()
        self.assertFalse(self.bar._shape_btn.isChecked())
        self.assertEqual(cancelled, [1])

    def test_another_tool_turns_it_off(self):
        self.bar.shape_tool._draw.click()
        self.bar._act_boundary.setChecked(True)
        self.bar._on_boundary_toggled(True)
        self.assertFalse(self.bar._shape_btn.isChecked())

    def test_draw_closes_the_menu(self):
        menu = self.bar._shape_btn.menu()
        menu.popup(self.bar.mapToGlobal(self.bar.rect().bottomLeft()))
        self._app.processEvents()
        self.assertTrue(menu.isVisible())
        self.bar.shape_tool._draw.click()
        self._app.processEvents()
        self.assertFalse(menu.isVisible())


if __name__ == "__main__":
    unittest.main()

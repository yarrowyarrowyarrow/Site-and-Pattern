"""
tests/test_placement_bar.py — the bar over the map while you place (F193, V2.98).

The pattern settings moved out of a collapsible section of the side panel, where
a column that does not scroll squeezed them to 11 px (0 px at 1366 × 768), into
a bar that floats over the map while placing. These tests pin what makes that
honest:

* **It says what the next click will do**, in words, for every pattern and
  source (``placement_arming.describe``, Qt-free).
* **It shows while the map is placing and goes the moment it stops**, including
  when the map stops on its own (Esc in the map, a finished fill). Before V2.98
  Python never heard about those, and one click on empty map after Esc planted a
  whole community outside the yard. The map now reports every mode, stamped, and
  a report that crossed a newer change is ignored.
* **It is reachable by a screen reader**: a sibling of the map in its column,
  never a child of the web view, whose accessible interface reports only the
  page.
* **It meets the review's baseline**: 13 px text, 4.5:1 contrast, visible focus.

Offscreen Qt; the Qt parts skip where PyQt6 isn't importable.
"""

import os
import pathlib
import re
import sys
import tempfile
import unittest
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PyQt6.QtCore import QObject, pyqtSignal
    from PyQt6.QtWidgets import QApplication, QWidget
    _HAVE_QT = True
except ImportError:                                  # pragma: no cover
    _HAVE_QT = False

import src.db.plants as _plants_mod                  # noqa: E402

_ROOT = pathlib.Path(__file__).resolve().parent.parent


# ── The sentence ─────────────────────────────────────────────────────────────

class TestDescribe(unittest.TestCase):
    """What the bar's first line says. Qt-free."""

    def _d(self, *a, **k):
        from src.placement_arming import describe
        return describe(*a, **k)

    def test_every_pattern_says_what_the_clicks_are(self):
        for kind, click in [("row", "start point"), ("grid", "opposite corner"),
                            ("circle", "centre"), ("fill", "double-click")]:
            with self.subTest(kind=kind):
                headline, instruction = self._d("plants", kind, "Wild Bergamot")
                self.assertIn("Wild Bergamot", headline)
                self.assertIn(click, instruction)

    def test_single_says_click_the_map_and_that_it_repeats(self):
        """The map stays armed after a click, which nothing said (the review's
        finding 8); since V2.99 the bar does."""
        self.assertEqual(self._d("plants", "single", "Wild Bergamot"),
                         ("Placing Wild Bergamot",
                          "Click the map to place it. Each click places another."))
        _, instruction = self._d("communities", "single", "Aromatic Herb Circle")
        self.assertIn("Each click places another.", instruction)

    def test_a_burst_says_how_many(self):
        headline, instruction = self._d("plants", "single", "Wild Bergamot", qty=5)
        self.assertIn("5 at a time", headline)
        self.assertIn("cluster of 5", instruction)

    def test_a_mix_is_named_as_a_mix(self):
        headline, _ = self._d("plants", "row", "Alpine Aster", mix=3)
        self.assertEqual(headline, "Placing your 3-plant mix in a row")
        headline, _ = self._d("communities", "grid", "", mix=2)
        self.assertEqual(headline, "Placing your 2-community mix in a grid")

    def test_single_names_the_plant_even_with_a_mix_built(self):
        """The V2.37 chip said "the mix" in Single, where the map places the
        selected plant itself."""
        headline, _ = self._d("plants", "single", "Wild Bergamot", mix=3)
        self.assertEqual(headline, "Placing Wild Bergamot")

    def test_a_community_says_where_its_centre_goes(self):
        _, instruction = self._d("communities", "single", "Aromatic Herb Circle")
        self.assertIn("centre", instruction)

    def test_nothing_named_still_reads(self):
        headline, _ = self._d("plants", "row", "")
        self.assertIn("the selection", headline)

    def test_no_em_dashes(self):
        """House style for user-facing copy (the site guards the same rule)."""
        from src.placement_arming import describe
        for source in ("plants", "communities"):
            for kind in ("single", "row", "grid", "circle", "fill"):
                for mix in (0, 3):
                    text = " ".join(describe(source, kind, "X", qty=2, mix=mix))
                    self.assertNotIn("—", text, (source, kind, mix))


# ── The map reports its mode ─────────────────────────────────────────────────

class TestTheMapReportsItsMode(unittest.TestCase):
    """Static: the JS and the Python halves of the mode report."""

    def test_set_mode_reports_every_mode_with_the_stamp(self):
        js = (_ROOT / "html" / "map" / "05-features.js").read_text(encoding="utf-8")
        body = js[js.index("function setMode(mode, data)"):]
        body = body[:body.index("\n    }\n")]
        self.assertIn("bridge.onModeChanged(mode, _pyModeSeq)", body,
                      "setMode no longer tells Python the mode it entered, so "
                      "Esc in the map leaves the bar saying 'Placing'")

    def test_refilling_keeps_the_corners_drawn(self):
        """Selection arms Fill since V2.98, so re-arming mid-drawing must not
        restart the polygon (the reason V2.37 left Fill out)."""
        js = (_ROOT / "html" / "map" / "05-features.js").read_text(encoding="utf-8")
        case = js[js.index("case 'fill':"):]
        case = case[:case.index("break;")]
        self.assertIn("if (wasMode !== 'fill') shapePoints = [];", case)

    def test_every_python_mode_change_is_stamped(self):
        """A mode change sent without the stamp would make its own report look
        current next to a newer one."""
        src = (_ROOT / "src" / "map_widget.py").read_text(encoding="utf-8")
        self.assertNotRegex(
            src, r"self\.run_js\(map_js\.(set_mode|set_mode_with_payload|cancel_draw)\(",
            "a mode change bypasses _run_mode_js")
        self.assertGreaterEqual(src.count("self._run_mode_js(map_js."), 9)

    def test_stamp_builder(self):
        from src import map_js
        self.assertEqual(map_js.stamp_mode(7), "_pyModeSeq = 7; ")


# ── The bar's style ──────────────────────────────────────────────────────────

def _luminance(hex_colour: str) -> float:
    h = hex_colour.lstrip("#")
    rgb = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    lin = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
           for c in rgb]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def _contrast(a: str, b: str) -> float:
    la, lb = sorted((_luminance(a), _luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


class TestTheBarsStyle(unittest.TestCase):
    """The review's baseline, on the one surface this increment builds."""

    @classmethod
    def setUpClass(cls):
        from src import placement_bar
        cls.style = placement_bar._STYLE
        cls.rules = re.findall(r"([^{}]+)\{([^{}]*)\}", cls.style)
        bar = [body for sel, body in cls.rules if sel.strip() == "#placementBar"]
        cls.bar_bg = re.search(r"background-color:\s*(#[0-9a-fA-F]{6})",
                               bar[0]).group(1)

    def test_text_is_at_least_13px(self):
        sizes = [int(s) for s in re.findall(r"font-size:\s*(\d+)px", self.style)]
        self.assertTrue(sizes)
        self.assertGreaterEqual(min(sizes), 13)

    def test_every_text_colour_clears_4_5_to_1(self):
        for selector, body in self.rules:
            fg = re.search(r"(?<![-\w])color:\s*(#[0-9a-fA-F]{6})", body)
            if not fg:
                continue
            bg = re.search(r"background-color:\s*(#[0-9a-fA-F]{6})", body)
            ground = bg.group(1) if bg else self.bar_bg
            with self.subTest(selector=selector.strip()):
                self.assertGreaterEqual(_contrast(fg.group(1), ground), 4.5)

    def test_every_control_shows_focus(self):
        for kind in ("QPushButton", "QSpinBox", "QDoubleSpinBox", "QCheckBox"):
            with self.subTest(kind=kind):
                self.assertRegex(self.style, rf"{kind}[^{{,]*:focus")

    def test_the_images_it_names_ship(self):
        """Qt draws a styled arrow or tick only from an image; a missing file
        draws nothing at all."""
        for name in ("spin-up.svg", "spin-down.svg", "check.svg"):
            with self.subTest(name=name):
                self.assertTrue((_ROOT / "html" / "assets" / "ui" / name).is_file())


# ── The bar itself ───────────────────────────────────────────────────────────

@unittest.skipUnless(_HAVE_QT, "PyQt6 not installed in this env")
class TestPlacementBar(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls._app = QApplication.instance() or QApplication(["permadesign-tests"])

    def _bar(self):
        from PyQt6.QtWidgets import QLabel, QVBoxLayout
        from src.placement_bar import PlacementBar
        holder = QWidget()
        holder.resize(900, 600)
        column = QVBoxLayout(holder)
        column.setContentsMargins(0, 40, 0, 0)
        anchor = QWidget()
        column.addWidget(anchor)
        bar = PlacementBar(holder, anchor=anchor)
        page = QLabel("plants page")
        accessory = QLabel("accessory")
        bar.add_page("plants", page, accessory=accessory)
        bar.add_page("communities", QLabel("communities page"))
        holder.show()
        self._app.processEvents()
        self.addCleanup(holder.deleteLater)
        return holder, anchor, bar, page, accessory

    def test_hidden_until_something_is_placed(self):
        _h, _a, bar, _p, _acc = self._bar()
        self.assertFalse(bar.isVisible())
        self.assertEqual(bar.source, "")

    def test_shows_the_source_page_and_the_sentence(self):
        _h, _a, bar, page, accessory = self._bar()
        bar.show_page("plants", "Placing Wild Bergamot in a row",
                      "Click the start point, then the end point.")
        self.assertTrue(bar.isVisible())
        self.assertTrue(page.isVisible())
        self.assertTrue(accessory.isVisible())
        self.assertEqual(bar.source, "plants")
        self.assertEqual(bar.status_text(),
                         "Placing Wild Bergamot in a row. Click the start "
                         "point, then the end point.")
        self.assertNotIn("<", bar.status_text(),
                         "a screen reader would read the markup")

    def test_the_other_sources_accessory_stays_out(self):
        _h, _a, bar, page, accessory = self._bar()
        bar.show_page("communities", "Placing X", "Click.")
        self.assertFalse(page.isVisible())
        self.assertFalse(accessory.isVisible())

    def test_sits_over_the_top_of_the_map_clear_of_the_zoom_buttons(self):
        from src import placement_bar as pb
        _h, anchor, bar, _p, _acc = self._bar()
        bar.show_page("plants", "Placing X", "Click.")
        bar.refit()
        origin = anchor.mapTo(bar.parentWidget(), anchor.rect().topLeft())
        self.assertEqual(bar.y(), origin.y() + pb._INSET_TOP)
        self.assertGreaterEqual(bar.x(), origin.x() + pb._INSET_LEFT)
        self.assertLessEqual(bar.x() + bar.width(),
                             origin.x() + anchor.width() - pb._INSET_RIGHT)
        self.assertGreaterEqual(bar.height(), bar.heightForWidth(bar.width()))

    def test_done_asks_to_stop(self):
        _h, _a, bar, _p, _acc = self._bar()
        seen = []
        bar.done_requested.connect(lambda: seen.append(1))
        bar._done.click()
        self.assertEqual(seen, [1])

    def test_hide_bar_forgets_the_source(self):
        _h, _a, bar, _p, _acc = self._bar()
        bar.show_page("plants", "Placing X", "Click.")
        bar.hide_bar()
        self.assertFalse(bar.isVisible())
        self.assertEqual(bar.source, "")


# ── The flow, against a stand-in main window ─────────────────────────────────

if _HAVE_QT:
    class _FakeBridge(QObject):
        mode_changed = pyqtSignal(str, int)

    class _FakeMap(QWidget):
        def __init__(self, parent=None):
            super().__init__(parent)
            self.bridge = _FakeBridge()
            self.mode_seq = 0


@unittest.skipUnless(_HAVE_QT, "PyQt6 not installed in this env")
class TestPlacementBarFlow(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls._app = QApplication.instance() or QApplication(["permadesign-tests"])
        cls._tmp = tempfile.mkdtemp(prefix="permadesign_bar_")
        _plants_mod._DATA_DIR = cls._tmp
        _plants_mod._DB_PATH = os.path.join(cls._tmp, "t.db")
        cls._orig_dir = _plants_mod._user_data_dir
        _plants_mod._user_data_dir = lambda: pathlib.Path(cls._tmp)
        from src.db.plants import init_db
        init_db()

    @classmethod
    def tearDownClass(cls):
        _plants_mod._user_data_dir = cls._orig_dir

    def _main(self):
        from PyQt6.QtWidgets import QVBoxLayout
        from src import placement_bar_flow
        from src.plant_panel import PlantPanel
        from src.polyculture_panel import PolyculturePanel
        column = QWidget()
        QVBoxLayout(column).addWidget(_FakeMap())
        map_widget = column.findChild(_FakeMap)
        calls = []
        main = SimpleNamespace(
            map_widget=map_widget,
            plant_panel=PlantPanel(),
            polyculture_panel=PolyculturePanel(),
            _current_mode="none",
            _cancel_draw=lambda: calls.append("cancel"),
            _set_mode_label=lambda text: calls.append(("label", text)),
            toolbar=SimpleNamespace(
                reset_draw_buttons=lambda: calls.append("reset")),
            _pending_community_pattern={"name": "x"},
            _pending_community_pattern_mix=None,
            _pending_fill={"members": [(1, 1.0)]},
        )
        placement_bar_flow.install(main)
        column.show()
        self._app.processEvents()
        self.addCleanup(column.deleteLater)
        from src.db.plants import search_plants
        self._plant = search_plants(query="bergamot")[0]
        return main, calls

    def _arm_plant(self, main):
        main.plant_panel._place_plant(self._plant)
        main._current_mode = "plant"

    def test_the_bar_is_a_sibling_of_the_map_never_its_child(self):
        """Qt's accessible interface for the web view reports only the page:
        measured in V2.98, a child of the map view is absent from AT-SPI."""
        main, _ = self._main()
        bar = main.placement_bar
        self.assertIs(bar.parentWidget(), main.map_widget.parentWidget())
        self.assertFalse(main.map_widget.isAncestorOf(bar))

    def test_arming_shows_the_bar_with_what_was_armed(self):
        main, _ = self._main()
        self._arm_plant(main)
        bar = main.placement_bar
        self.assertTrue(bar.isVisible())
        self.assertEqual(bar.source, "plants")
        self.assertIn(self._plant["common_name"], bar.status_text())

    def test_arming_one_panel_stands_the_other_down(self):
        main, _ = self._main()
        main.polyculture_panel._arm_as("Aromatic Herb Circle")
        self.assertTrue(main.polyculture_panel._armed)
        self._arm_plant(main)
        self.assertFalse(main.polyculture_panel._armed,
                         "both panels claim the map")
        self.assertEqual(main.placement_bar.source, "plants")

    def test_esc_in_the_map_stands_everything_down(self):
        main, calls = self._main()
        self._arm_plant(main)
        main.map_widget.bridge.mode_changed.emit("none", main.map_widget.mode_seq)
        self.assertFalse(main.placement_bar.isVisible())
        self.assertFalse(main.plant_panel._armed)
        self.assertEqual(main._current_mode, "none")
        self.assertIn(("label", "Ready"), calls)
        self.assertIn("reset", calls)
        self.assertIsNone(main._pending_community_pattern)
        self.assertNotIn("cancel", calls,
                         "_cancel_draw would send the map a cancel of its own")

    def test_a_finished_fill_keeps_its_spec_for_the_polygon(self):
        """The map leaves fill mode *before* it hands over the polygon."""
        main, _ = self._main()
        main._current_mode = "fill"
        main.map_widget.bridge.mode_changed.emit("none", main.map_widget.mode_seq)
        self.assertEqual(main._pending_fill, {"members": [(1, 1.0)]})

    def test_another_tool_stands_placing_down_but_keeps_its_label(self):
        main, calls = self._main()
        self._arm_plant(main)
        main._current_mode = "measure"          # Python entered Measure first
        main.map_widget.bridge.mode_changed.emit("measure", main.map_widget.mode_seq)
        self.assertFalse(main.placement_bar.isVisible())
        self.assertFalse(main.plant_panel._armed)
        self.assertNotIn(("label", "Ready"), calls)

    def test_a_report_that_crossed_a_newer_change_is_ignored(self):
        main, _ = self._main()
        self._arm_plant(main)
        stale = main.map_widget.mode_seq
        main.map_widget.mode_seq += 1           # Python sent a newer change
        main.map_widget.bridge.mode_changed.emit("none", stale)
        self.assertTrue(main.placement_bar.isVisible())
        self.assertTrue(main.plant_panel._armed)
        self.assertEqual(main._current_mode, "plant")

    def test_entering_a_placing_mode_needs_nothing(self):
        main, calls = self._main()
        self._arm_plant(main)
        main.map_widget.bridge.mode_changed.emit("plant", main.map_widget.mode_seq)
        self.assertTrue(main.placement_bar.isVisible())
        self.assertEqual(calls, [])

    def test_done_is_the_one_cancel_path(self):
        main, calls = self._main()
        self._arm_plant(main)
        main.placement_bar._done.click()
        self.assertEqual(calls, ["cancel"])

    def test_every_target_in_the_bar_is_24px_tall(self):
        """WCAG 2.2's minimum, on the rendered widgets and on the minimum the
        bar's style sheet sets. (AT-SPI reports a check box's extents smaller
        than the widget, 20 px against 26 in the running app, so the size is
        read from the widgets, not from the accessibility tree.)"""
        from PyQt6.QtWidgets import QAbstractButton, QAbstractSpinBox, QCheckBox
        main, _ = self._main()
        for box in main.plant_panel._placement.findChildren(QCheckBox):
            with self.subTest(box=box.text()):
                self.assertGreaterEqual(box.minimumHeight(), 24)
        self._arm_plant(main)
        for kind in ("single", "row", "grid", "circle", "fill"):
            main.plant_panel._placement.set_kind(kind)
            self._app.processEvents()
            for w in main.placement_bar.findChildren(QWidget):
                if w.isVisible() and isinstance(w, (QAbstractButton,
                                                    QAbstractSpinBox)):
                    with self.subTest(kind=kind, widget=w.accessibleName()
                                      or getattr(w, "text", lambda: "")()):
                        self.assertGreaterEqual(w.height(), 24)

    def test_every_control_in_the_bar_has_a_name(self):
        """What a screen reader announces. The review found the Overlap slider
        announced as "Placement Mode" and Qty and the colour with no name."""
        from PyQt6.QtWidgets import (QAbstractButton, QAbstractSpinBox,
                                     QCheckBox)
        main, _ = self._main()
        self._arm_plant(main)
        for kind in ("single", "row", "grid", "circle", "fill"):
            main.plant_panel._placement.set_kind(kind)
            self._app.processEvents()
            for w in main.placement_bar.findChildren(QWidget):
                if not w.isVisible():
                    continue
                if isinstance(w, QAbstractSpinBox):
                    name = w.accessibleName()     # its text is only the value
                elif isinstance(w, (QCheckBox, QAbstractButton)):
                    name = w.accessibleName() or w.text()
                else:
                    continue
                with self.subTest(kind=kind, widget=type(w).__name__):
                    self.assertTrue(name.strip(), f"unnamed {w!r}")


# ── A column that scrolls instead of squeezing ───────────────────────────────

@unittest.skipUnless(_HAVE_QT, "PyQt6 not installed in this env")
class TestScrollColumn(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls._app = QApplication.instance() or QApplication(["permadesign-tests"])

    def _column(self, heights, *, wrap=False):
        from PyQt6.QtWidgets import QLabel
        from src.scroll_column import scroll_column
        owner = QWidget()
        col = scroll_column(owner)
        if wrap:
            label = QLabel("a label long enough to wrap onto a second line " * 3)
            label.setWordWrap(True)
            col.addWidget(label)
        for h in heights:
            w = QWidget()
            w.setMinimumHeight(h)
            col.addWidget(w)
        owner.resize(300, 400)
        owner.show()
        self._app.processEvents()
        self.addCleanup(owner.deleteLater)
        return owner

    def test_fits_without_scrolling(self):
        owner = self._column([100, 100])
        self.assertFalse(owner._column_scroll.verticalScrollBar().isVisible())

    def test_scrolls_rather_than_squeezing(self):
        owner = self._column([200, 200, 200])
        self.assertTrue(owner._column_scroll.verticalScrollBar().isVisible())
        for w in owner._column_scroll.widget().findChildren(QWidget):
            self.assertGreaterEqual(w.height(), w.minimumHeight())

    def test_a_wrapping_label_does_not_make_it_scroll(self):
        """Height-for-width made QScrollArea treat the preferred height as the
        minimum: the Communities column scrolled with nothing squeezed."""
        owner = self._column([100, 100], wrap=True)
        self.assertFalse(owner._column_scroll.verticalScrollBar().isVisible())


if __name__ == "__main__":
    unittest.main()

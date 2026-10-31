"""
tests/test_visual_floor.py — text no smaller than 12 px, controls no smaller
than 24 (F195, V3.03).

Measured on V3.02: Plant Communities drew 19 of its 21 pieces of text under
12 px and Field Notes 21 of 23; the source held 164 font sizes below 12 px; and
every side tab had controls under WCAG 2.5.8's 24 px. The floors are read from
the source here, and from the real window, tab by tab, in ``test_app_smoke``.
"""

import os
import pathlib
import re
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_ROOT = pathlib.Path(__file__).resolve().parent.parent
_TMP = tempfile.mkdtemp(prefix="sp_visual_")
import src.db.plants as _plants  # noqa: E402
_plants._DATA_DIR = _TMP
_plants._DB_PATH = os.path.join(_TMP, "permadesign_test.db")

try:
    from PyQt6.QtCore import Qt
    from PyQt6.QtWidgets import (
        QApplication, QCheckBox, QComboBox, QLineEdit, QMainWindow,
        QPushButton, QSlider, QSpinBox, QToolBar, QToolButton, QVBoxLayout,
        QWidget,
    )
    _HAVE_QT = True
except Exception:                                          # noqa: BLE001
    _HAVE_QT = False


def tearDownModule():
    shutil.rmtree(_TMP, ignore_errors=True)


def _desktop_sources():
    """The desktop app's own text: the panels and dialogs, the map page and
    its scripts. Not the PDF export (print sizes) or the public website."""
    files = (sorted((_ROOT / "src").glob("*.py"))
             + sorted((_ROOT / "src" / "controllers").glob("*.py"))
             + [_ROOT / "html" / "map.html"]
             + sorted((_ROOT / "html" / "map").glob("*.js")))
    return [p for p in files
            if p.name != "pdf_export.py" and not p.name.startswith("static_site")]


class TestNoTextUnder12px(unittest.TestCase):

    def test_no_font_size_under_12px_in_the_source(self):
        small = re.compile(r"font-size\s*:\s*([0-9.]+)px", re.I)
        offenders = []
        for path in _desktop_sources():
            for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                for size in small.findall(line):
                    if float(size) < 12:
                        offenders.append(f"{path.relative_to(_ROOT)}:{n}: {size}px")
        self.assertEqual(offenders, [])

    def test_no_font_sized_under_12px_in_code(self):
        pixel = re.compile(r"setPixelSize\(\s*(\d+)\s*\)")
        point = re.compile(r"setPointSize\(\s*(\d+)\s*\)")
        offenders = []
        for path in _desktop_sources():
            if path.suffix != ".py":
                continue
            text = path.read_text(encoding="utf-8")
            offenders += [f"{path.name}: setPixelSize({v})"
                          for v in pixel.findall(text) if int(v) < 12]
            offenders += [f"{path.name}: setPointSize({v})"
                          for v in point.findall(text) if int(v) < 9]
        self.assertEqual(offenders, [])


@unittest.skipUnless(_HAVE_QT, "PyQt6 not installed in this env")
class TestEveryControlAt24px(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls._app = QApplication.instance() or QApplication(["permadesign-tests"])
        from src import target_size
        target_size.install(cls._app)

    def _window(self, *widgets):
        window = QWidget()
        self.addCleanup(window.deleteLater)
        self.addCleanup(window.close)
        lay = QVBoxLayout(window)
        for w in widgets:
            lay.addWidget(w)
        window.show()
        self._app.processEvents()
        return window

    def test_the_small_controls_measured_on_v3_02_reach_24(self):
        tick = QCheckBox("Show contour lines")
        spin = QSpinBox()
        combo = QComboBox()
        combo.addItem("Any sun")
        search = QLineEdit()
        slider = QSlider(Qt.Orientation.Horizontal)
        self._window(tick, spin, combo, search, slider)
        for w in (tick, spin, combo, search, slider):
            with self.subTest(control=type(w).__name__):
                self.assertGreaterEqual(w.height(), 24)

    def test_a_button_fixed_smaller_is_raised(self):
        close = QPushButton("×")
        close.setFixedSize(16, 16)
        self._window(close)
        self.assertGreaterEqual(close.width(), 24)
        self.assertGreaterEqual(close.height(), 24)

    def test_a_vertical_slider_is_made_wide_enough(self):
        slider = QSlider(Qt.Orientation.Vertical)
        self._window(slider)
        self.assertGreaterEqual(slider.width(), 24)

    def test_a_minimum_is_given_back_when_its_text_outgrows_it(self):
        """Browse's Place button is made empty and named later: a 24 px floor
        set while empty would let a layout squeeze its words."""
        place = QPushButton("")
        self._window(place)
        place.setText("Place Alkali Cord Grass on the map")
        place.hide()
        place.show()
        self._app.processEvents()
        self.assertEqual(place.minimumWidth(), 0)
        self.assertGreaterEqual(place.width(), place.minimumSizeHint().width())

    def test_a_toolbar_still_overflows_rather_than_squeezing(self):
        """The first build set 24 on every button, and the View toolbar shrank
        its buttons to 24 px: "S…ite", "B…ary", "Mea…ement"."""
        window = QMainWindow()
        self.addCleanup(window.deleteLater)
        self.addCleanup(window.close)
        bar = QToolBar()
        window.addToolBar(bar)
        for words in ("Satellite", "Boundary", "Measurement", "Plants",
                      "Canopy", "Structures", "Yard photo"):
            bar.addAction(words)
        window.resize(300, 200)
        window.show()
        self._app.processEvents()
        for button in bar.findChildren(QToolButton):
            if button.isVisible() and button.text():
                with self.subTest(button=button.text()):
                    self.assertGreaterEqual(button.width(),
                                            button.fontMetrics().horizontalAdvance(button.text()))

    def test_a_controls_own_parts_are_not_counted(self):
        from src import target_size
        spin = QSpinBox()
        self._window(spin)
        self.assertFalse(target_size.counts(spin.findChild(QLineEdit)))
        self.assertTrue(target_size.counts(spin))

    def test_a_checkbox_with_no_words_is_made_24_wide(self):
        """Its words are part of what you click; without them, its box is
        all there is (Field Notes' questions stand beside their boxes)."""
        from PyQt6.QtWidgets import QHBoxLayout, QLabel
        bare = QCheckBox()
        worded = QCheckBox("Show contour lines")
        row = QWidget()                    # as in Field Notes: words beside
        line = QHBoxLayout(row)
        line.addWidget(bare)
        line.addWidget(QLabel("Where does water pool?"), 1)
        self._window(row, worded)
        self.assertGreaterEqual(bare.width(), 24)
        self.assertEqual(worded.minimumWidth(), 0)


@unittest.skipUnless(_HAVE_QT, "PyQt6 not installed in this env")
class TestABoxYouCanSee(unittest.TestCase):
    """Fusion, the style Linux and CI draw in, outlined an unchecked box in the
    panel's own colour darkened: 1.11:1 on the panels (V3.03, measured on the
    real window). ``indicator_style`` draws the box itself."""

    @classmethod
    def setUpClass(cls):
        cls._app = QApplication.instance() or QApplication(["permadesign-tests"])
        from src import indicator_style
        indicator_style.install(cls._app)

    def _drawn(self, *controls, style=None):
        from tests import _visual
        panel = QWidget()
        self.addCleanup(panel.deleteLater)
        self.addCleanup(panel.close)
        panel.setStyleSheet("QWidget { background: #1e2a1e; color: #c8e6c9; }")
        lay = QVBoxLayout(panel)
        for c in controls:
            if style is not None:
                c.setStyle(style)
            # Nothing here may take focus: once any earlier test has pressed a
            # key, focus_ring rings whatever gains focus, and its yellow over
            # the box's edge read 11.6:1 in the full suite.
            c.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            lay.addWidget(c)
        panel.show()
        self._app.processEvents()
        image = panel.grab().toImage()
        return [_visual.indicator(image, panel, c) for c in controls]

    def test_every_state_clears_3_to_1_on_the_panel(self):
        from PyQt6.QtWidgets import QRadioButton
        from tests._visual import contrast
        box, ticked = QCheckBox("Show contour lines"), QCheckBox("Show grid")
        ticked.setChecked(True)
        ring, chosen = QRadioButton("Metres"), QRadioButton("Feet")
        chosen.setChecked(True)
        for name, (edge, ground, inside) in zip(
                ("box", "ticked", "ring", "chosen"),
                self._drawn(box, ticked, ring, chosen)):
            with self.subTest(control=name):
                self.assertGreaterEqual(contrast(edge, ground), 3.0)
        (_e, ground, inside), = self._drawn(QCheckBox("again"))
        self.assertLess(contrast(inside, ground), 1.2)      # empty when off
        ticked2 = QCheckBox("on")
        ticked2.setChecked(True)
        (_e, ground, inside), = self._drawn(ticked2)
        self.assertGreaterEqual(contrast(inside, ground), 3.0)   # filled when on

    def test_fusion_alone_did_not(self):
        from PyQt6.QtWidgets import QStyleFactory
        from tests._visual import contrast
        fusion = QStyleFactory.create("fusion")
        self.addCleanup(fusion.deleteLater)
        (edge, ground, _inside), = self._drawn(QCheckBox("Show contour lines"),
                                               style=fusion)
        self.assertLess(contrast(edge, ground), 1.5)


@unittest.skipUnless(_HAVE_QT, "PyQt6 not installed in this env")
class TestFieldNotesQuestionsWrap(unittest.TestCase):
    """A checkbox's words cannot wrap: at 12 px in DejaVu Sans, the font CI
    draws in, the longest question needed 392 px and the tab scrolled
    sideways. The box keeps the question as its name; the words beside it
    wrap and tick it."""

    @classmethod
    def setUpClass(cls):
        cls._app = QApplication.instance() or QApplication(["permadesign-tests"])
        from src.site_panel import SitePanel
        cls._panel = SitePanel()

    @classmethod
    def tearDownClass(cls):
        cls._panel.close()
        cls._panel.deleteLater()

    def _words(self, box):
        from src.site_panel import _QuestionWords
        return next(w for w in self._panel.findChildren(_QuestionWords)
                    if w._box is box)

    def test_each_box_is_named_by_its_question_whose_words_wrap(self):
        from src.field_notes import FIELD_PROMPTS
        for key, prompt in FIELD_PROMPTS:
            box = self._panel._fn_checks[key]
            with self.subTest(question=key):
                self.assertEqual(box.text(), "")
                self.assertEqual(box.accessibleName(), prompt)
                words = self._words(box)
                self.assertEqual(words.text(), prompt)
                self.assertTrue(words.wordWrap())

    def test_a_click_on_the_words_ticks_the_box(self):
        from PyQt6.QtCore import QPoint
        from PyQt6.QtTest import QTest
        box = self._panel._fn_checks["water_pools"]
        box.setChecked(False)
        words = self._words(box)
        QTest.mouseClick(words, Qt.MouseButton.LeftButton, pos=QPoint(5, 5))
        self.assertTrue(box.isChecked())
        QTest.mouseClick(words, Qt.MouseButton.LeftButton, pos=QPoint(5, 5))
        self.assertFalse(box.isChecked())


if __name__ == "__main__":
    unittest.main()

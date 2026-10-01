"""
tests/test_filter_widgets.py — the multi-select dropdown (F194, V3.01).

V2.98 saw the Type box read "● Shrub" with nothing ticked, above 16 asters, and
V3.00 could not reproduce it with a mouse. Three ordinary inputs did it, each by
making Shrub the combo's *current item*: Qt draws that item's icon beside the
text (the dot is Shrub's swatch), and rewrites the text with its name whenever
its data changes, which ticking it does, after our own handler has run. Each
input is driven here the way a person drives it, then Shrub is unticked.

Also here: the line each list opens on, saying how its ticked values combine,
and a box that reads its dimension once something is ticked.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PyQt6.QtCore import QEvent, QPoint, QPointF, Qt
    from PyQt6.QtGui import QKeyEvent, QMouseEvent, QWheelEvent
    from PyQt6.QtWidgets import QApplication
    _HAVE_QT = True
except Exception:                                          # noqa: BLE001
    _HAVE_QT = False


def _app():
    return QApplication.instance() or QApplication(["permadesign-tests"])


TYPES = {"tree": "Tree", "shrub": "Shrub", "vine": "Vine", "fern": "Fern"}


@unittest.skipUnless(_HAVE_QT, "PyQt6 not installed in this env")
class TestNoStaleLabel(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls._app = _app()

    def _combo(self, **kwargs):
        from src.filter_widgets import CheckableComboBox
        from src.plant_list_view import _type_icon
        combo = CheckableComboBox(placeholder="Any type", **kwargs)
        for key, label in TYPES.items():
            combo.add_check_item(label, key, icon=_type_icon(key))
        combo.resize(200, 26)
        combo.show()
        self.addCleanup(combo.deleteLater)
        self.addCleanup(combo.hidePopup)
        self._app.processEvents()
        return combo

    def _row(self, combo, key):
        model = combo.model()
        return next(model.item(i) for i in range(model.rowCount())
                    if model.item(i).data(Qt.ItemDataRole.UserRole) == key)

    def _untick_shrub_and_check(self, combo):
        shrub = self._row(combo, "shrub")
        shrub.setCheckState(Qt.CheckState.Checked)
        shrub.setCheckState(Qt.CheckState.Unchecked)
        self._app.processEvents()
        self.assertEqual(combo.checked_keys(), [])
        self.assertEqual(combo.currentIndex(), -1)
        self.assertEqual(combo.lineEdit().text(), "",
                         "the box names a value nothing has ticked")
        self.assertTrue(combo.itemIcon(combo.currentIndex()).isNull(),
                        "a swatch is drawn beside the box")

    def test_the_wheel_over_the_box(self):
        """Scrolling the panel with the pointer passing over the box."""
        combo = self._combo()
        for _ in range(2):
            QApplication.sendEvent(combo, QWheelEvent(
                QPointF(50, 10), QPointF(combo.mapToGlobal(QPoint(50, 10))),
                QPoint(0, 0), QPoint(0, -120), Qt.MouseButton.NoButton,
                Qt.KeyboardModifier.NoModifier, Qt.ScrollPhase.NoScrollPhase,
                False))
        self.assertEqual(combo.currentIndex(), -1)
        self._untick_shrub_and_check(combo)

    def test_an_arrow_key_on_the_box(self):
        combo = self._combo()
        combo.setFocus()
        for _ in range(2):
            QApplication.sendEvent(combo, QKeyEvent(
                QEvent.Type.KeyPress, Qt.Key.Key_Down,
                Qt.KeyboardModifier.NoModifier))
        combo.hidePopup()
        self.assertEqual(combo.currentIndex(), -1)
        self._untick_shrub_and_check(combo)

    def test_space_then_return_in_the_open_list(self):
        """A keyboard walk: Space ticks Shrub, Return closes the list. Return
        on a row is Qt's "choose this one", which made it current."""
        combo = self._combo()
        combo.showPopup()
        view = combo.view()
        view.setCurrentIndex(self._row(combo, "shrub").index())
        for key in (Qt.Key.Key_Space, Qt.Key.Key_Return):
            QApplication.sendEvent(view, QKeyEvent(
                QEvent.Type.KeyPress, key, Qt.KeyboardModifier.NoModifier))
            self._app.processEvents()
        self.assertEqual(combo.checked_keys(), ["shrub"])
        self.assertEqual(combo.currentIndex(), -1)
        self._row(combo, "shrub").setCheckState(Qt.CheckState.Unchecked)
        self._app.processEvents()
        self.assertEqual(combo.lineEdit().text(), "")

    def test_a_current_item_set_from_code_is_undone_too(self):
        combo = self._combo()
        combo.setCurrentIndex(1)
        self.assertEqual(combo.currentIndex(), -1)
        self._untick_shrub_and_check(combo)


@unittest.skipUnless(_HAVE_QT, "PyQt6 not installed in this env")
class TestInputMeaning(unittest.TestCase):
    """A multi-select has no next value to step to."""

    @classmethod
    def setUpClass(cls):
        cls._app = _app()

    def _combo(self):
        from src.filter_widgets import CheckableComboBox
        combo = CheckableComboBox(placeholder="Any")
        for key, label in TYPES.items():
            combo.add_check_item(label, key)
        combo.show()
        self.addCleanup(combo.deleteLater)
        self.addCleanup(combo.hidePopup)
        return combo

    def test_the_wheel_is_passed_on_so_the_panel_scrolls(self):
        combo = self._combo()
        event = QWheelEvent(
            QPointF(5, 5), QPointF(combo.mapToGlobal(QPoint(5, 5))),
            QPoint(0, 0), QPoint(0, -120), Qt.MouseButton.NoButton,
            Qt.KeyboardModifier.NoModifier, Qt.ScrollPhase.NoScrollPhase, False)
        event.accept()
        combo.wheelEvent(event)
        self.assertFalse(event.isAccepted())

    def test_down_and_space_open_the_list(self):
        for key in (Qt.Key.Key_Down, Qt.Key.Key_Up, Qt.Key.Key_Space):
            combo = self._combo()
            combo.setFocus()
            QApplication.sendEvent(combo, QKeyEvent(
                QEvent.Type.KeyPress, key, Qt.KeyboardModifier.NoModifier))
            self._app.processEvents()
            self.assertTrue(combo.view().isVisible(), key)
            combo.hidePopup()


@unittest.skipUnless(_HAVE_QT, "PyQt6 not installed in this env")
class TestTheRuleLine(unittest.TestCase):
    """The line a list opens on, saying how its ticked values combine."""

    RULE = "Tick as many as you like. A plant needs one."

    @classmethod
    def setUpClass(cls):
        cls._app = _app()

    def _combo(self):
        from src.filter_widgets import CheckableComboBox
        combo = CheckableComboBox(placeholder="Any type", rule=self.RULE)
        for key, label in TYPES.items():
            combo.add_check_item(label, key)
        combo.show()
        self.addCleanup(combo.deleteLater)
        self.addCleanup(combo.hidePopup)
        return combo

    def test_it_is_the_first_row_and_cannot_be_ticked(self):
        combo = self._combo()
        first = combo.model().item(0)
        self.assertEqual(first.text(), self.RULE)
        self.assertEqual(combo.rule_text(), self.RULE)
        self.assertFalse(first.isCheckable())
        self.assertFalse(first.isEnabled())
        self.assertFalse(first.isSelectable())

    def test_setting_the_ticks_does_not_give_it_a_box(self):
        """``setCheckState`` on every row would hand the rule a checkbox."""
        combo = self._combo()
        combo.set_checked_keys(["fern"])
        self.assertIsNone(combo.model().item(0).data(
            Qt.ItemDataRole.CheckStateRole))
        self.assertEqual(combo.checked_keys(), ["fern"])

    def test_clicking_it_ticks_nothing(self):
        combo = self._combo()
        combo.showPopup()
        view = combo.view()
        point = view.visualRect(combo.model().index(0, 0)).center()
        release = QMouseEvent(
            QEvent.Type.MouseButtonRelease, QPointF(point),
            QPointF(view.viewport().mapToGlobal(point)),
            Qt.MouseButton.LeftButton, Qt.MouseButton.NoButton,
            Qt.KeyboardModifier.NoModifier)
        combo.eventFilter(view.viewport(), release)
        self.assertEqual(combo.checked_keys(), [])
        self.assertEqual(combo.lineEdit().text(), "")

    def test_the_list_is_wide_enough_to_say_it(self):
        combo = self._combo()
        self.assertGreaterEqual(
            combo.view().minimumWidth(),
            combo.fontMetrics().horizontalAdvance(self.RULE))


@unittest.skipUnless(_HAVE_QT, "PyQt6 not installed in this env")
class TestTheFace(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls._app = _app()

    def _combo(self):
        from src.filter_widgets import CheckableComboBox
        combo = CheckableComboBox(placeholder="Any type")
        for key, label in TYPES.items():
            combo.add_check_item(label, key)
        self.addCleanup(combo.deleteLater)
        return combo

    def test_a_face_reads_the_dimension(self):
        combo = self._combo()
        combo.set_face(lambda keys: "Type: " + " or ".join(keys))
        combo.set_checked_keys(["tree", "fern"])
        self.assertEqual(combo.lineEdit().text(), "Type: tree or fern")
        combo.set_checked_keys([])
        self.assertEqual(combo.lineEdit().text(), "",
                         "with nothing ticked the placeholder shows")

    def test_a_long_face_shows_its_start(self):
        """A line edit given text scrolls to its cursor, at the end; a face
        wider than the box showed its tail and lost the dimension."""
        combo = self._combo()
        combo.set_face(lambda keys: "Flower colour: " + ", ".join(keys) * 8)
        combo.set_checked_keys(["tree"])
        self.assertEqual(combo.lineEdit().cursorPosition(), 0)

    def test_without_a_face_it_reads_as_before(self):
        combo = self._combo()
        combo.set_checked_keys(["tree", "shrub", "fern"])
        self.assertEqual(combo.lineEdit().text(), "3 selected")
        combo.set_checked_keys(["vine"])
        self.assertEqual(combo.lineEdit().text(), "Vine")


if __name__ == "__main__":
    unittest.main()

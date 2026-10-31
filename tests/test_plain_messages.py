"""
tests/test_plain_messages.py — a failed open, save or plan says what happened
and what to do, and closing asks to save (V3.18, WD-4).

docs/homeowner/09-words.md §3.7. A damaged design file showed a JSON parser's
"Expecting value: line 1 column 1", and closing with unsaved work offered only
*Exit anyway?*. Every box goes through ``plain_messages._run``, replaced here so
nothing waits for an answer.
"""

import json
import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from src import plain_messages as pm  # noqa: E402


def _qt():
    try:
        from PyQt6.QtWidgets import QApplication
        return QApplication.instance() or QApplication(["plain-messages"])
    except Exception:                                      # noqa: BLE001
        return None


class TestTheWords(unittest.TestCase):

    def test_open_names_the_file_and_says_the_rest_are_fine(self):
        text = pm.open_failed_text("/home/a/Back yard.perma.geojson")
        self.assertTrue(text.startswith(
            "Couldn't open \"Back yard.perma.geojson\"."), text)
        self.assertIn("damaged or from a newer version", text)
        self.assertIn("Your other designs are fine", text)

    def test_save_says_the_work_is_still_open_and_what_to_try(self):
        text = pm.save_failed_text("Back yard")
        self.assertIn("Couldn't save \"Back yard\"", text)
        self.assertIn("still open", text)
        self.assertIn("Save As", text)

    def test_a_plan_failure_is_worded_by_its_cause(self):
        self.assertIn("no plants matched everything you asked for",
                      pm.plan_failed_text(
                          "offline generation found no plants or "
                          "communities to place"))
        self.assertIn("no yard outline or address",
                      pm.plan_failed_text("no site location: pass a "
                                          "boundary or site_config"))
        self.assertIn("Check that your yard outline or bed is closed",
                      pm.plan_failed_text("Unexpected error: KeyError 'x'"))

    def test_no_message_carries_the_generators_words(self):
        for detail in ("offline generation found no plants or communities",
                       "no site location: pass a boundary",
                       "Unexpected error during generation: boom"):
            text = pm.plan_failed_text(detail)
            self.assertNotIn("offline generation", text)
            self.assertNotIn("site_config", text)
            self.assertNotIn("boom", text)

    def test_the_two_questions_name_the_design(self):
        self.assertEqual(pm.save_before_closing_text("Back yard"),
                         "Save changes to \"Back yard\" before closing?")
        self.assertEqual(
            pm.discard_for_new_text("Back yard"),
            "Discard unsaved changes to \"Back yard\" and start a new yard?")
        self.assertIn("this design", pm.save_before_closing_text(""))


@unittest.skipIf(_qt() is None, "PyQt6 not installed in this env")
class TestTheBoxes(unittest.TestCase):

    def setUp(self):
        self.app = _qt()
        self.shown = []

    def _answer(self, button=None):
        def run(box):
            self.shown.append(box)
            return button
        return mock.patch.object(pm, "_run", run)

    def test_a_damaged_file_shows_the_new_text_and_no_parser_message(self):
        from src.project import load_project
        path = os.path.join(tempfile.mkdtemp(), "Back yard.perma.geojson")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write('{"type": "FeatureCollection", "features": [')
        with self._answer(), \
                self.assertLogs("sitepattern", level="ERROR") as logs:
            try:
                load_project(path)
            except Exception:                              # noqa: BLE001
                pm.tell_open_failed(None, path)
        box = self.shown[0]
        self.assertEqual(box.text(), pm.open_failed_text(path))
        self.assertNotIn("Expecting", box.text())
        self.assertNotIn("line 1", box.text())
        self.assertIn("log", box.detailedText())
        record = logs.records[0]
        self.assertIsInstance(record.exc_info[1], json.JSONDecodeError)

    def test_the_exit_prompt_has_three_buttons(self):
        from PyQt6.QtWidgets import QMessageBox
        B = QMessageBox.StandardButton
        for button, expected in ((B.Save, "save"), (B.Discard, "discard"),
                                 (B.Cancel, "cancel")):
            with self._answer(button):
                self.assertEqual(pm.ask_save_before_closing(None, "Yard"),
                                 expected)
        box = self.shown[-1]
        self.assertEqual(len(box.buttons()), 3)
        self.assertEqual(box.button(B.Discard).text(), "Don't save")
        self.assertEqual(box.text(), "Save changes to \"Yard\" before closing?")

    def test_starting_a_new_yard_defaults_to_keeping_the_work(self):
        from PyQt6.QtWidgets import QMessageBox
        B = QMessageBox.StandardButton
        with self._answer(B.Cancel):
            self.assertFalse(pm.ask_discard_for_new(None, "Yard"))
        with self._answer(B.Discard):
            self.assertTrue(pm.ask_discard_for_new(None, "Yard"))
        self.assertEqual(self.shown[-1].defaultButton(),
                         self.shown[-1].button(B.Cancel))


def _main_window_class():
    try:
        import PyQt6.QtWebEngineWidgets  # noqa: F401
        from src.app import MainWindow
        return MainWindow
    except Exception:                                      # noqa: BLE001
        return None


@unittest.skipIf(_qt() is None or _main_window_class() is None,
                 "needs PyQt6 and PyQt6-WebEngine")
class TestClosingWithUnsavedWork(unittest.TestCase):
    """The window stays open unless the work is saved or let go."""

    def _close(self, choice, save_works=True):
        fake = mock.MagicMock()
        fake._modified = True
        fake._project = {"properties": {"project_name": "Yard"}}

        def on_save():
            if save_works:
                fake._modified = False

        fake._on_save.side_effect = on_save
        event = mock.MagicMock()
        with mock.patch.object(pm, "ask_save_before_closing",
                               return_value=choice):
            try:
                _main_window_class().closeEvent(fake, event)
            except TypeError:
                pass          # past the prompt: super() needs a real window
        return fake, event

    def test_cancel_keeps_the_window(self):
        fake, event = self._close("cancel")
        event.ignore.assert_called_once()
        fake._on_save.assert_not_called()

    def test_a_save_that_did_not_happen_keeps_the_window(self):
        fake, event = self._close("save", save_works=False)
        fake._on_save.assert_called_once()
        event.ignore.assert_called_once()

    def test_a_save_that_worked_closes(self):
        fake, event = self._close("save", save_works=True)
        fake._on_save.assert_called_once()
        event.ignore.assert_not_called()

    def test_dont_save_closes_without_saving(self):
        fake, event = self._close("discard")
        fake._on_save.assert_not_called()
        event.ignore.assert_not_called()


if __name__ == "__main__":
    unittest.main()

"""
tests/test_guide.py — the guide inside the app (F253, V3.38).

The owner: *"'How to plan your yard' button simply takes you to the github
repo website… not sure what that's about."* Help › How to Plan Your Yard now
opens ``data/guide.md`` in a window. These tests hold three things:

* the guide ships and has five steps, the README's five, word for word, so
  the two places a person reads them cannot drift;
* every control a step names is a control the app has;
* the window builds, shows the steps, closes with the main window (it is
  parented to it), and opens once however often it is asked for.
"""

import os
import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from src import guide  # noqa: E402

_ROOT = pathlib.Path(__file__).resolve().parent.parent


def _qt_available() -> bool:
    try:
        from PyQt6.QtWidgets import QApplication  # noqa: F401
        return True
    except Exception:                                      # noqa: BLE001
        return False


class TheGuideShips(unittest.TestCase):

    def test_the_file_is_in_the_shipped_data_folder(self):
        self.assertEqual(guide.GUIDE_FILE[0], "data",
                         "data/ is what the installer bundles")
        self.assertTrue(os.path.exists(guide.guide_path()))
        self.assertNotEqual(guide.guide_text(), guide.MISSING)

    def test_it_has_five_steps(self):
        self.assertEqual(len(guide.numbered_steps(guide.guide_text())), 5)

    def test_the_readme_says_the_same_five_steps(self):
        readme = (_ROOT / "README.md").read_text(encoding="utf-8")
        self.assertEqual(guide.numbered_steps(readme),
                         guide.numbered_steps(guide.guide_text()),
                         "README.md's 'Your first yard, in five steps' and "
                         "data/guide.md have drifted apart: change both")

    def test_it_keeps_what_the_readme_promises_a_newcomer(self):
        text = guide.guide_text()
        for words in ("not an identification guide",
                      "What leaves your computer", "Send Feedback",
                      "Advanced tools", "Undo"):
            self.assertIn(words, text)

    def test_an_unreadable_file_still_says_something(self):
        missing = os.path.join(tempfile.mkdtemp(), "nope.md")
        self.assertEqual(guide.guide_text(missing), guide.MISSING)
        self.assertIn("Reinstalling", guide.MISSING)


class TheStepsNameRealControls(unittest.TestCase):
    """A guide that names a button the app no longer has sends a beginner
    looking for something that is not there."""

    CONTROLS = ("Click my yard on the map", "Draw on the map", "Garden Bed",
                "Plan my yard", "Try another", "Export PDF",
                "Where This &Data Came From", "Send &Feedback",
                "&Start Screen",
                # V3.42: the guide sent people to "Learn about native
                # plants" after it had gone; the Learn doors are named here.
                "Walk a wild landscape", "Quizzes")

    def test_each_control_exists_in_the_source(self):
        source = "\n".join(p.read_text(encoding="utf-8")
                           for p in (_ROOT / "src").rglob("*.py"))
        for control in self.CONTROLS:
            with self.subTest(control=control):
                self.assertIn(control, source)

    def test_the_guide_names_them(self):
        text = guide.guide_text()
        for control in self.CONTROLS:
            with self.subTest(control=control):
                self.assertIn(control.replace("&", ""), text)


class ReadingTheSteps(unittest.TestCase):

    def test_steps_stop_at_the_next_heading(self):
        text = ("# Guide\n\n## Your first yard, in five steps\n\n"
                "1. One.\n2. Two.\n\n## Afterwards\n\n1. Not a step.\n")
        self.assertEqual(guide.numbered_steps(text), ["One.", "Two."])

    def test_a_deeper_heading_inside_does_not_end_them(self):
        text = ("### Your first yard, in five steps\n1. One.\n"
                "#### A note\n2. Two.\n### Next\n3. Three.\n")
        self.assertEqual(guide.numbered_steps(text), ["One.", "Two."])

    def test_no_heading_no_steps(self):
        self.assertEqual(guide.numbered_steps("1. Loose.\n"), [])


@unittest.skipUnless(_qt_available(), "PyQt6 not installed in this env")
class TheWindow(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from PyQt6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication(["test_guide"])

    def test_it_shows_the_steps(self):
        from PyQt6.QtWidgets import QWidget
        from src.guide_window import open_guide
        main = QWidget()
        self.addCleanup(main.close)
        win = open_guide(main)
        self.addCleanup(win.close)
        shown = win.page.toPlainText()
        self.assertIn("Your first yard, in five steps", shown)
        self.assertIn("Plan my yard", shown)
        self.assertNotIn("github.com", shown.lower())

    def test_it_belongs_to_the_main_window_and_opens_once(self):
        from PyQt6.QtWidgets import QWidget
        from src.guide_window import open_guide
        main = QWidget()
        self.addCleanup(main.close)
        first = open_guide(main)
        self.addCleanup(first.close)
        self.assertIs(first.parent(), main,
                      "parented, so it closes with the app and never keeps "
                      "it running on its own")
        self.assertFalse(first.isModal())
        self.assertIs(open_guide(main), first)

    def test_its_controls_are_named(self):
        from PyQt6.QtWidgets import QPushButton, QWidget
        from src.guide_window import open_guide
        main = QWidget()
        self.addCleanup(main.close)
        win = open_guide(main)
        self.addCleanup(win.close)
        self.assertTrue(win.page.accessibleName())
        for button in win.findChildren(QPushButton):
            self.assertTrue(button.accessibleName() or button.text())


if __name__ == "__main__":
    unittest.main()

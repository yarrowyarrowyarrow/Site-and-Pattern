"""
tests/test_start_menu.py — the launch screen grows into what you have (V2.40).

*"I'd like to have a start menu where the option to load a previous design or
start a new one appears."*

The dialog existed (F44) and was aimed at the wrong moment: a first-run greeting
shown once, which a returning user never saw again. It is now a start menu —
every launch, suppressible — with three rows that appear only when they have
something behind them.

The rule these hold down: **a row that cannot do anything must not be drawn.**
This project has shipped two dead controls (the sun slider connected to nothing,
the never-applied quiz colouring) and both taught a user that a feature existed
and did not work.
"""

import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PyQt6.QtWidgets import QApplication, QPushButton, QLabel
    _HAVE_QT = True
except Exception:                                          # noqa: BLE001
    _HAVE_QT = False


@unittest.skipUnless(_HAVE_QT, "PyQt6 not installed in this env")
class TestWhatTheMenuOffers(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._app = QApplication.instance() or QApplication([])

    def _rows(self, **kwargs):
        from src.welcome_dialog import WelcomeDialog
        dlg = WelcomeDialog(**kwargs)
        return [b.findChildren(QLabel)[1].text()
                for b in dlg.findChildren(QPushButton) if b.findChildren(QLabel)]

    def test_a_first_time_user_sees_only_the_three_doors(self):
        """Nothing saved, nothing to continue, nothing to recover — so nothing
        about opening or resuming, which would only lead to an empty room."""
        rows = self._rows()
        self.assertEqual(len(rows), 3)
        for word in ("Recover", "Continue", "Open a design"):
            self.assertFalse(any(word in r for r in rows), word)

    def test_having_saves_adds_the_open_row(self):
        rows = self._rows(has_saves=True)
        self.assertTrue(any("Open a design" in r for r in rows))
        self.assertFalse(any("Continue" in r for r in rows))

    def test_a_last_design_adds_continue_and_names_it(self):
        rows = self._rows(last_design="Back Yard", has_saves=True)
        self.assertTrue(any("Continue" in r and "Back Yard" in r for r in rows))

    def test_unsaved_work_is_the_top_row(self):
        """The only row with a deadline on it goes where the eye lands."""
        rows = self._rows(last_design="Back Yard", recover="Back Yard",
                          has_saves=True)
        self.assertIn("Recover", rows[0])

    def test_the_recovery_row_names_the_design(self):
        from src.welcome_dialog import WelcomeDialog
        dlg = WelcomeDialog(recover="Back Yard")
        detail = " ".join(l.text() for l in dlg.findChildren(QLabel))
        self.assertIn("Back Yard", detail)

    def test_the_title_stops_saying_welcome_once_you_have_work(self):
        from src.welcome_dialog import WelcomeDialog
        self.assertIn("Welcome", WelcomeDialog().windowTitle())
        self.assertNotIn(
            "Welcome",
            WelcomeDialog(last_design="Back Yard", first_run=False).windowTitle())

    def test_exactly_one_row_is_the_obvious_one(self):
        """Two primary buttons is none."""
        from src.welcome_dialog import WelcomeDialog
        for kwargs in ({}, {"has_saves": True},
                       {"last_design": "X", "has_saves": True},
                       {"last_design": "X", "recover": "X", "has_saves": True}):
            dlg = WelcomeDialog(**kwargs)
            primary = [b for b in dlg.findChildren(QPushButton)
                       if "#66bb6a" in (b.styleSheet() or "")]
            self.assertLessEqual(len(primary), 1, kwargs)

    def test_every_row_returns_a_choice_the_flow_handles(self):
        """A row whose key nothing acts on is a button that does nothing."""
        import ast
        import pathlib
        from src import welcome_dialog as wd
        src = (pathlib.Path(__file__).resolve().parent.parent
               / "src" / "onboarding_flow.py").read_text(encoding="utf-8")
        fn = next(n for n in ast.walk(ast.parse(src))
                  if isinstance(n, ast.FunctionDef) and n.name == "show_welcome")
        handled = ast.dump(fn)
        for name in ("RECOVER", "CONTINUE", "OPEN", "GENERATE", "BLANK",
                     "EXAMPLE"):
            self.assertTrue(hasattr(wd, name), name)
            self.assertIn(name, handled, f"{name} is offered but never acted on")


@unittest.skipUnless(_HAVE_QT, "PyQt6 not installed in this env")
class TestItActuallyStaysAStartMenu(unittest.TestCase):
    """The bug this nearly shipped with: auto-marking it seen on every launch
    would suppress the menu after the first one — exactly the behaviour V2.40
    replaces."""

    def test_the_launch_path_does_not_mark_it_seen(self):
        import ast
        import pathlib
        src = (pathlib.Path(__file__).resolve().parent.parent
               / "src" / "onboarding_flow.py").read_text(encoding="utf-8")
        fn = next(n for n in ast.walk(ast.parse(src))
                  if isinstance(n, ast.FunctionDef)
                  and n.name == "_welcome_if_alive")
        self.assertNotIn("mark_seen", ast.dump(fn),
                         "the launch path marks the menu seen — it will show "
                         "once and never again")

    def test_only_the_checkbox_suppresses_it(self):
        import ast
        import pathlib
        src = (pathlib.Path(__file__).resolve().parent.parent
               / "src" / "onboarding_flow.py").read_text(encoding="utf-8")
        fn = next(n for n in ast.walk(ast.parse(src))
                  if isinstance(n, ast.FunctionDef) and n.name == "show_welcome")
        setter = next((n for n in ast.walk(fn)
                       if isinstance(n, ast.Call)
                       and isinstance(n.func, ast.Attribute)
                       and n.func.attr == "setValue"), None)
        self.assertIsNotNone(setter)
        guard = ast.dump(next(n for n in ast.walk(fn)
                              if isinstance(n, ast.If)
                              and "suppressed" in ast.dump(n)))
        self.assertIn("suppressed", guard)
        self.assertNotIn("mark_seen", guard,
                         "dismissing the menu still counts as 'never again'")

    def test_the_checkbox_is_still_there(self):
        from src.welcome_dialog import WelcomeDialog
        from PyQt6.QtWidgets import QCheckBox
        dlg = WelcomeDialog()
        boxes = [c.text() for c in dlg.findChildren(QCheckBox)]
        self.assertTrue(any("again" in b for b in boxes), boxes)


class TestRecoveryIsNotConditionalOnAPreference(unittest.TestCase):
    """Unsaved work must not depend on how you feel about greetings.

    The menu offers recovery as its top row; when the menu is turned OFF the
    standalone prompt has to still fire, or a user who dismissed a greeting
    silently loses the crash-recovery path with it.
    """

    def test_the_controller_still_offers_it_when_the_menu_is_off(self):
        import ast
        import pathlib
        src = (pathlib.Path(__file__).resolve().parent.parent / "src"
               / "controllers" / "persistence.py").read_text(encoding="utf-8")
        fn = next(n for n in ast.walk(ast.parse(src))
                  if isinstance(n, ast.FunctionDef)
                  and n.name == "maybe_offer_autosave_recovery")
        dump = ast.dump(fn)
        self.assertIn("should_show_welcome", dump)
        self.assertIn("_recovery_from_menu", dump)

    def test_the_menu_tells_the_controller_it_is_asking(self):
        import ast
        import pathlib
        src = (pathlib.Path(__file__).resolve().parent.parent
               / "src" / "onboarding_flow.py").read_text(encoding="utf-8")
        fn = next(n for n in ast.walk(ast.parse(src))
                  if isinstance(n, ast.FunctionDef) and n.name == "show_welcome")
        self.assertIn("_recovery_from_menu", ast.dump(fn))


class TestTheLastDesignMemory(unittest.TestCase):
    def setUp(self):
        import src.settings as settings_mod
        self.dir = tempfile.mkdtemp(prefix="sp_last_")
        self.addCleanup(shutil.rmtree, self.dir, ignore_errors=True)
        self._orig = settings_mod._CONFIG_PATH
        settings_mod._CONFIG_PATH = os.path.join(self.dir, "config.json")
        self.addCleanup(setattr, settings_mod, "_CONFIG_PATH", self._orig)

    def test_nothing_remembered_is_an_empty_string(self):
        from src import saves
        self.assertEqual(saves.last_design(), "")

    def test_it_round_trips(self):
        from src import saves
        path = os.path.join(self.dir, "a.perma.geojson")
        open(path, "w").close()
        saves.remember_last_design(path)
        self.assertEqual(saves.last_design(), os.path.abspath(path))

    def test_a_deleted_design_is_forgotten_rather_than_offered(self):
        """A Continue button that opens a file the user has since deleted is a
        dead control."""
        from src import saves
        path = os.path.join(self.dir, "gone.perma.geojson")
        open(path, "w").close()
        saves.remember_last_design(path)
        os.unlink(path)
        self.assertEqual(saves.last_design(), "")

    def test_a_corrupt_config_is_survivable(self):
        import src.settings as settings_mod
        from src import saves
        with open(settings_mod._CONFIG_PATH, "w") as f:
            f.write("{not json")
        self.assertEqual(saves.last_design(), "")
        saves.remember_last_design("/tmp/x")      # must not raise

    def test_remembering_never_breaks_the_save_that_called_it(self):
        import src.settings as settings_mod
        from src import saves
        settings_mod._CONFIG_PATH = os.path.join(
            self.dir, "no", "such", "dir", "config.json")
        saves.remember_last_design("/tmp/x")       # must not raise


if __name__ == "__main__":
    unittest.main()

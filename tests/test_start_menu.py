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
        cls._app = QApplication.instance() or QApplication(["permadesign-tests"])

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
                  if isinstance(n, ast.FunctionDef) and n.name == "_dispatch")
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

    @classmethod
    def setUpClass(cls):
        cls._app = QApplication.instance() or QApplication(["permadesign-tests"])

    def _flow_fn(self, name):
        import ast
        import pathlib
        src = (pathlib.Path(__file__).resolve().parent.parent
               / "src" / "onboarding_flow.py").read_text(encoding="utf-8")
        return next(n for n in ast.walk(ast.parse(src))
                    if isinstance(n, ast.FunctionDef) and n.name == name)

    def test_the_launch_path_does_not_mark_it_seen(self):
        import ast
        for name in ("choose_start_action", "_open_menu"):
            self.assertNotIn("mark_seen", ast.dump(self._flow_fn(name)),
                             f"{name} marks the menu seen — it will show once "
                             f"and never again")

    def test_only_the_checkbox_suppresses_it(self):
        import ast
        fn = self._flow_fn("_open_menu")
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

    def test_both_entry_points_offer_the_same_rows(self):
        """The launch sequence and Help → Welcome build the menu from one body.
        Two copies of "which rows exist" become two answers to it within a
        release or two."""
        import ast
        for name in ("choose_start_action", "show_welcome"):
            dump = ast.dump(self._flow_fn(name))
            self.assertIn("_open_menu", dump, name)
            self.assertNotIn("WelcomeDialog", dump,
                             f"{name} builds its own menu instead of sharing "
                             f"_open_menu")

    def test_the_checkbox_is_still_there(self):
        from src.welcome_dialog import WelcomeDialog
        from PyQt6.QtWidgets import QCheckBox
        dlg = WelcomeDialog()
        boxes = [c.text() for c in dlg.findChildren(QCheckBox)]
        self.assertTrue(any("again" in b for b in boxes), boxes)


class TestItOpensBeforeTheMap(unittest.TestCase):
    """*"I want an actual window to open (ahead of seeing the map) which will
    be the 'start menu'. I'm not seeing that."*

    V2.40's first cut scheduled the menu 150 ms after ``MainWindow.__init__``
    returned, so the map painted first and the menu arrived as a modal on top
    of it — a greeting, not a start screen. The fix is an ordering, and an
    ordering is exactly the kind of thing that gets quietly undone, so it is
    pinned here rather than left to the eye.
    """

    @classmethod
    def setUpClass(cls):
        if _HAVE_QT:
            cls._app = (QApplication.instance()
                        or QApplication(["permadesign-tests"]))

    def _tree(self, relpath):
        import ast
        import pathlib
        src = (pathlib.Path(__file__).resolve().parent.parent
               / relpath).read_text(encoding="utf-8")
        return ast.parse(src)

    def test_main_asks_before_it_builds_the_window(self):
        import ast
        tree = self._tree("main.py")
        asked = built = None
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            if isinstance(node.func, ast.Attribute) and \
                    node.func.attr == "choose_start_action":
                asked = node.lineno
            if isinstance(node.func, ast.Name) and node.func.id == "MainWindow":
                built = node.lineno
        self.assertIsNotNone(asked, "main.py never opens the start menu")
        self.assertIsNotNone(built, "main.py never builds the MainWindow")
        self.assertLess(asked, built,
                        "the start menu opens after the map is built — it is a "
                        "greeting over the app again, not a start screen")

    def test_the_answer_is_acted_on_after_the_window_exists(self):
        import ast
        tree = self._tree("main.py")
        acted = next((n.lineno for n in ast.walk(tree)
                      if isinstance(n, ast.Call)
                      and isinstance(n.func, ast.Attribute)
                      and n.func.attr == "act_on_start_choice"), None)
        built = next(n.lineno for n in ast.walk(tree)
                     if isinstance(n, ast.Call)
                     and isinstance(n.func, ast.Name)
                     and n.func.id == "MainWindow")
        self.assertIsNotNone(acted, "the user's choice is read and dropped")
        self.assertGreater(acted, built)

    def test_the_window_no_longer_opens_it_itself(self):
        """Two menus on one launch is worse than the problem being fixed.
        Help → Welcome may still open it; ``MainWindow.__init__`` may not."""
        import ast
        cls = next(n for n in ast.walk(self._tree("src/app.py"))
                   if isinstance(n, ast.ClassDef) and n.name == "MainWindow")
        init = next(n for n in cls.body
                    if isinstance(n, ast.FunctionDef) and n.name == "__init__")
        opens = {"show_welcome", "maybe_show_welcome", "choose_start_action",
                 "_open_menu"}
        for node in ast.walk(init):
            if (isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Attribute)
                    and node.func.attr in opens):
                self.fail(f"MainWindow.__init__ opens the start menu "
                          f"({node.func.attr}) — a launch would show two")

    def test_the_menu_needs_no_mainwindow_to_open(self):
        """It reads what it offers from disk. If it ever grows a `main`
        argument, the ordering above becomes impossible."""
        import ast
        fn = next(n for n in ast.walk(self._tree("src/onboarding_flow.py"))
                  if isinstance(n, ast.FunctionDef)
                  and n.name == "choose_start_action")
        self.assertEqual([a.arg for a in fn.args.args], [],
                         "choose_start_action takes an argument — it can no "
                         "longer run before the MainWindow exists")

    @unittest.skipUnless(_HAVE_QT, "PyQt6 not installed in this env")
    def test_it_is_a_real_top_level_window(self):
        """Parented to a MainWindow it is a sheet over an app. Parentless it is
        a window of its own — which is what "an actual window opens" means."""
        from src.welcome_dialog import WelcomeDialog
        dlg = WelcomeDialog(None)
        self.assertIsNone(dlg.parent())
        self.assertTrue(dlg.isWindow())

    @unittest.skipUnless(_HAVE_QT, "PyQt6 not installed in this env")
    def test_it_paints_its_own_background(self):
        """The dark theme lives on MainWindow's stylesheet and used to reach
        this dialog by inheritance. Opening first means there is nothing to
        inherit from, and pale-green text on the platform's default light
        dialog is close to unreadable."""
        from src.welcome_dialog import WelcomeDialog
        self.assertIn("background-color", WelcomeDialog(None).styleSheet())

    @unittest.skipUnless(_HAVE_QT, "PyQt6 not installed in this env")
    def test_choosing_a_row_before_any_window_exists_returns_that_choice(self):
        """The end-to-end shape of the launch: no MainWindow anywhere, a real
        dialog opens, a row is clicked, and the answer comes back to be carried
        into the window that has not been built yet."""
        from PyQt6.QtCore import QTimer
        from src import onboarding_flow, welcome_dialog

        self._isolate()
        seen = {}

        def _click():
            # activeModalWidget, not "any WelcomeDialog in topLevelWidgets" —
            # earlier tests leave un-exec'd dialogs lying around, and clicking
            # one of those hangs this test on the modal that is really open.
            dlg = QApplication.activeModalWidget()
            seen["dlg"] = dlg
            if not isinstance(dlg, welcome_dialog.WelcomeDialog):
                return
            seen["parent"] = dlg.parent()
            btn = next(b for b in dlg.findChildren(QPushButton)
                       if any("Generate a design" in l.text()
                              for l in b.findChildren(QLabel)))
            btn.click()

        def _watchdog():
            # A hanging test is far worse than a failing one.
            dlg = QApplication.activeModalWidget()
            if dlg is not None:
                dlg.reject()

        QTimer.singleShot(0, _click)
        QTimer.singleShot(4000, _watchdog)
        choice = onboarding_flow.choose_start_action()

        self.assertIsInstance(seen.get("dlg"), welcome_dialog.WelcomeDialog,
                              "no start menu window opened")
        self.assertIsNone(seen["parent"], "the menu is parented to something")
        self.assertEqual(choice, welcome_dialog.GENERATE)

    @unittest.skipUnless(_HAVE_QT, "PyQt6 not installed in this env")
    def test_a_suppressed_menu_opens_nothing_and_answers_nothing(self):
        from src import onboarding_flow
        fake = self._isolate()
        fake.d[onboarding_flow.SEEN_WELCOME_KEY] = True
        self.assertEqual(onboarding_flow.choose_start_action(), "")

    def _isolate(self):
        """Point the menu's three sources of truth — the suppress flag, the
        saves folder, the autosave — at nothing, so the test neither reads nor
        writes the machine it is running on."""
        from src import onboarding_flow, saves
        import src.settings as settings_mod

        class _FakeSettings:
            def __init__(self):
                self.d = {}

            def value(self, key, default=None, type=None):
                return self.d.get(key, default)

            def setValue(self, key, value):
                self.d[key] = value

        fake = _FakeSettings()
        self.addCleanup(setattr, onboarding_flow, "_settings",
                        onboarding_flow._settings)
        onboarding_flow._settings = lambda: fake

        tmp = tempfile.mkdtemp(prefix="sp_menu_")
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        self.addCleanup(setattr, saves, "saves_dir", saves.saves_dir)
        saves.saves_dir = lambda: tmp
        self.addCleanup(setattr, settings_mod, "_CONFIG_PATH",
                        settings_mod._CONFIG_PATH)
        settings_mod._CONFIG_PATH = os.path.join(tmp, "config.json")
        self.addCleanup(setattr, onboarding_flow, "_autosave_pending",
                        onboarding_flow._autosave_pending)
        onboarding_flow._autosave_pending = lambda: False
        return fake


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

    def _recovery_fn(self):
        import ast
        import pathlib
        src = (pathlib.Path(__file__).resolve().parent.parent / "src"
               / "controllers" / "persistence.py").read_text(encoding="utf-8")
        return next(n for n in ast.walk(ast.parse(src))
                    if isinstance(n, ast.FunctionDef)
                    and n.name == "maybe_offer_autosave_recovery")

    def test_an_unreadable_autosave_is_discarded_whatever_the_menu_does(self):
        """The menu draws no Recover row for a file it could not read, so a
        controller that stands aside for the menu here leaves a corrupt autosave
        that nothing ever cleans up. Shipped that way in V2.40's first cut."""
        import ast
        fn = self._recovery_fn()
        # The method deletes the autosave in two places (unreadable, and after
        # a restore or a decline); it is the *first* that has to come early —
        # before the "the menu will offer it" early return, or it is
        # unreachable while the menu is on.
        discard = min(n.lineno for n in ast.walk(fn)
                      if isinstance(n, ast.Call)
                      and isinstance(n.func, ast.Attribute)
                      and n.func.attr == "clear_autosave")
        stand_aside = min(n.lineno for n in ast.walk(fn)
                          if isinstance(n, ast.Name)
                          and n.id == "should_show_welcome")
        self.assertLess(discard, stand_aside)

    def test_the_legacy_autosave_is_migrated_before_the_menu_asks(self):
        """V2.40 moved the menu ahead of the MainWindow, which is where the
        migration used to be triggered. A user upgrading from before V2.39 gets
        no Recover row unless the menu migrates first."""
        import ast
        import pathlib
        src = (pathlib.Path(__file__).resolve().parent.parent
               / "src" / "onboarding_flow.py").read_text(encoding="utf-8")
        fn = next(n for n in ast.walk(ast.parse(src))
                  if isinstance(n, ast.FunctionDef)
                  and n.name == "_autosave_pending")
        self.assertIn("migrate_legacy_autosave", ast.dump(fn))

    def test_the_menu_tells_the_controller_it_is_asking(self):
        import ast
        import pathlib
        src = (pathlib.Path(__file__).resolve().parent.parent
               / "src" / "onboarding_flow.py").read_text(encoding="utf-8")
        fn = next(n for n in ast.walk(ast.parse(src))
                  if isinstance(n, ast.FunctionDef) and n.name == "_dispatch")
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

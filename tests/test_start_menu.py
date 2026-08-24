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
        """The row *titles*."""
        return [labels[1].text() for labels in self._row_labels(**kwargs)]

    def _details(self, **kwargs):
        """The second line under each row title."""
        return [labels[2].text() for labels in self._row_labels(**kwargs)
                if len(labels) > 2]

    def _row_labels(self, **kwargs):
        from src.start_screen import StartScreen
        dlg = StartScreen(**kwargs)
        return [b.findChildren(QLabel)
                for b in dlg.findChildren(QPushButton) if b.findChildren(QLabel)]

    def test_a_first_time_user_sees_only_the_three_doors(self):
        """Nothing saved, nothing to continue, nothing to recover — so the
        three doors and nothing about resuming."""
        rows = self._rows()
        self.assertEqual(len(rows), 3)
        for word in ("Recover", "Continue"):
            self.assertFalse(any(word in r for r in rows), word)

    def test_the_three_doors_do_not_rearrange_between_launches(self):
        """V2.41: the Load row used to be hidden until you had a save. A screen
        whose structure changes between your first and second launch is harder
        to learn than one honest empty room — and the row says so."""
        self.assertEqual(self._rows(), self._rows(saves_count=3))
        empty = self._details()
        stocked = self._details(saves_count=3)
        self.assertTrue(any("nothing saved yet" in d for d in empty), empty)
        self.assertFalse(any("nothing saved yet" in d for d in stocked))

    def test_having_saves_does_not_add_a_continue_row(self):
        """Saved designs and *the one you were last in* are different facts."""
        rows = self._rows(saves_count=3)
        self.assertFalse(any("Continue" in r for r in rows))

    def test_a_last_design_adds_continue_and_names_it(self):
        """The name sits in the note column beside "Continue", not inside the
        title. Same shape as every other row, so the eye finds the changing
        part in the same place each time."""
        pairs = list(zip(self._rows(last_design="Back Yard", saves_count=3),
                         self._details(last_design="Back Yard", saves_count=3)))
        self.assertIn(("Continue", "Back Yard"), pairs)

    def test_unsaved_work_is_the_top_row(self):
        """The only row with a deadline on it goes where the eye lands."""
        rows = self._rows(last_design="Back Yard", recover="Back Yard",
                          saves_count=3)
        self.assertIn("Recover", rows[0])

    def test_the_recovery_row_names_the_design(self):
        from src.start_screen import StartScreen
        dlg = StartScreen(recover="Back Yard")
        detail = " ".join(l.text() for l in dlg.findChildren(QLabel))
        self.assertIn("Back Yard", detail)

    def test_it_says_what_it_is_and_then_stops_talking(self):
        """Krug: happy talk must die, and so must instructions.

        The first cut opened with a sentence of mission statement above the
        controls and closed with the three-step path below them. Neither is
        read twice, and both push the choice further down the screen. The name
        and the tagline answer "what is this"; the rows answer "what can I do";
        nothing else is prose.
        """
        from src.start_screen import StartScreen
        from src.branding import APP_NAME, APP_TAGLINE
        dlg = StartScreen()
        loose = [l.text() for l in dlg.findChildren(QLabel)
                 if not isinstance(l.parent(), QPushButton)]
        self.assertIn(APP_NAME, loose)
        self.assertIn(APP_TAGLINE, loose)
        for text in loose:
            self.assertLessEqual(
                len(text.split()), 8,
                f"prose on the start screen: {text!r}")

    def test_a_row_says_a_fact_about_you_not_a_description_of_itself(self):
        """Krug: get rid of half the words, then half of what is left. The
        second line used to restate the title ("Load a design / Your saved
        designs, newest first, with what is in each one"). It now carries the
        one thing the title cannot: how many you have."""
        details = self._details(saves_count=3, species_count=434)
        self.assertIn("3 saved", details)
        # V2.43: the catalogue size moved behind the Learn door with the plant
        # directory itself, and the Learn row says the fact the *learner* owns
        # instead — how much of it they have found.
        self.assertIn("434 species to find", details)
        self.assertIn("37 of 581 species discovered",
                      self._details(discovery_line="37 of 581 species discovered"))
        for d in details:
            self.assertLessEqual(len(d.split()), 5, d)

    def test_exactly_one_row_is_the_obvious_one(self):
        """Two primary buttons is none."""
        from src.start_screen import StartScreen
        for kwargs in ({}, {"saves_count": 3},
                       {"last_design": "X", "saves_count": 3},
                       {"last_design": "X", "recover": "X", "saves_count": 3}):
            dlg = StartScreen(**kwargs)
            primary = [b for b in dlg.findChildren(QPushButton)
                       if "#66bb6a" in (b.styleSheet() or "")]
            self.assertLessEqual(len(primary), 1, kwargs)

    def test_every_row_returns_a_choice_the_flow_handles(self):
        """A row whose key nothing acts on is a button that does nothing."""
        import ast
        import pathlib
        from src import start_screen as wd
        src = (pathlib.Path(__file__).resolve().parent.parent
               / "src" / "onboarding_flow.py").read_text(encoding="utf-8")
        fn = next(n for n in ast.walk(ast.parse(src))
                  if isinstance(n, ast.FunctionDef) and n.name == "_dispatch")
        handled = ast.dump(fn)
        for name in ("RECOVER", "CONTINUE", "OPEN", "DESIGN", "DIRECTORY",
                     "EXAMPLE", "REFERENCE", "BLOOM", "UPDATE"):
            self.assertTrue(hasattr(wd, name), name)
            self.assertIn(name, handled, f"{name} is offered but never acted on")

    def test_generate_is_not_a_row(self):
        """V2.41, on the author's call: Generate a design was the *primary*
        button and comes off entirely. It is not ready to lead with, and a
        start screen that opens with "let the AI do it" teaches the wrong thing
        about what this app is. It keeps File → Generate Design… and Ctrl+G."""
        from src import start_screen
        self.assertFalse(hasattr(start_screen, "GENERATE"))
        rows = self._rows()
        self.assertFalse(any("Generate" in r for r in rows), rows)


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

    def test_the_checkbox_turns_the_screen_back_on_as_well_as_off(self):
        """It shipped one-way in V2.40: `if dlg.suppressed(): setValue(True)`,
        which could switch the app's front door off and never on. The only
        route back was hand-editing PermaDesign.conf. The write must be
        unconditional so unticking is an answer too."""
        import ast
        fn = self._flow_fn("_open_menu")
        setter = next((n for n in ast.walk(fn)
                       if isinstance(n, ast.Call)
                       and isinstance(n.func, ast.Attribute)
                       and n.func.attr == "setValue"), None)
        self.assertIsNotNone(setter, "nothing records the preference")
        self.assertIn("suppressed", ast.dump(setter),
                      "the stored value is not the checkbox's state")
        for node in ast.walk(fn):
            if isinstance(node, ast.If) and "setValue" in ast.dump(node):
                self.fail("the preference is written only under a condition — "
                          "unticking the box will not turn the screen back on")

    def test_the_screen_reflects_the_stored_preference(self):
        """A checkbox that does not show its current state is a guess."""
        from src.start_screen import StartScreen
        from PyQt6.QtWidgets import QCheckBox
        for hidden in (True, False):
            box = StartScreen(hidden=hidden).findChildren(QCheckBox)[0]
            self.assertEqual(box.isChecked(), hidden)

    def test_the_dead_key_is_not_read_any_more(self):
        """V2.31 wrote `onboarding/welcome_seen` itself, the first time the
        welcome ever appeared, meaning "has been seen". V2.40 reused the key
        for "asked not to see this again" without migrating it, so every
        install older than V2.40 started up with the screen already off. The
        fix is a new key, not a reinterpretation of a value nobody set."""
        import ast
        import pathlib
        src = (pathlib.Path(__file__).resolve().parent.parent
               / "src" / "onboarding_flow.py").read_text(encoding="utf-8")
        fn = next(n for n in ast.walk(ast.parse(src))
                  if isinstance(n, ast.FunctionDef)
                  and n.name == "should_show_welcome")
        # Names it *reads*, not names its docstring mentions — the docstring is
        # where the dead key is explained and has to be able to say so.
        read = {n.id for n in ast.walk(fn) if isinstance(n, ast.Name)}
        self.assertNotIn("SEEN_WELCOME_KEY", read)
        self.assertIn("START_SCREEN_OFF_KEY", read)

    def test_both_entry_points_offer_the_same_rows(self):
        """The launch sequence and Help → Welcome build the menu from one body.
        Two copies of "which rows exist" become two answers to it within a
        release or two."""
        import ast
        for name in ("choose_start_action", "show_welcome"):
            dump = ast.dump(self._flow_fn(name))
            # V2.43: both go through _menu_loop, which is the one body that
            # calls _open_menu — and which also owns the Learn menu behind the
            # first door, so Back has somewhere to go from either entry point.
            self.assertIn("_menu_loop", dump, name)
            self.assertNotIn("StartScreen", dump,
                             f"{name} builds its own screen instead of sharing "
                             f"_menu_loop")
        self.assertIn("_open_menu", ast.dump(self._flow_fn("_menu_loop")))

    def test_the_checkbox_is_still_there(self):
        from src.start_screen import StartScreen
        from PyQt6.QtWidgets import QCheckBox
        dlg = StartScreen()
        boxes = [c.text() for c in dlg.findChildren(QCheckBox)]
        self.assertTrue(any("Skip this screen" in b for b in boxes), boxes)


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

    def test_nothing_is_shown_before_the_start_screen(self):
        """The invariant, stated as what the user actually experiences.

        It used to read "choose_start_action comes before MainWindow(…)", which
        V2.41 made false in the letter while keeping it in the spirit: the
        window is now *constructed* first, deliberately, on a zero-timer that
        runs inside the screen's own modal loop so the Leaflet load overlaps
        with the seconds you spend reading. Construction is invisible. What
        must not happen before the screen is a `show()`.
        """
        import ast
        tree = self._tree("main.py")
        asked = next((n.lineno for n in ast.walk(tree)
                      if isinstance(n, ast.Call)
                      and isinstance(n.func, ast.Attribute)
                      and n.func.attr == "choose_start_action"), None)
        self.assertIsNotNone(asked, "main.py never opens the start screen")
        shown = [n.lineno for n in ast.walk(tree)
                 if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                 and n.func.attr == "show"]
        self.assertTrue(shown, "main.py never shows the main window")
        self.assertGreater(min(shown), asked,
                           "something is shown before the start screen — it is "
                           "a greeting over the app again, not a start screen")

    def test_the_window_is_warmed_behind_the_screen(self):
        """Construction has to be deferred into the screen's event loop, or the
        map starts loading only *after* a door is picked and the screen becomes
        a straight regression in perceived speed."""
        import ast
        tree = self._tree("main.py")
        warmed = [n for n in ast.walk(tree)
                  if isinstance(n, ast.Call)
                  and isinstance(n.func, ast.Attribute)
                  and n.func.attr == "singleShot"
                  and "MainWindow" in ast.dump(n)]
        self.assertTrue(warmed,
                        "MainWindow is not built behind the start screen — "
                        "picking a door will then wait on the map")

    def test_the_answer_is_acted_on_after_the_window_is_shown(self):
        import ast
        tree = self._tree("main.py")
        acted = next((n.lineno for n in ast.walk(tree)
                      if isinstance(n, ast.Call)
                      and isinstance(n.func, ast.Attribute)
                      and n.func.attr == "act_on_start_choice"), None)
        self.assertIsNotNone(acted, "the user's choice is read and dropped")
        shown = min(n.lineno for n in ast.walk(tree)
                    if isinstance(n, ast.Call)
                    and isinstance(n.func, ast.Attribute)
                    and n.func.attr == "show")
        self.assertGreater(acted, shown)

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
        from src.start_screen import StartScreen
        dlg = StartScreen(None)
        self.assertIsNone(dlg.parent())
        self.assertTrue(dlg.isWindow())

    @unittest.skipUnless(_HAVE_QT, "PyQt6 not installed in this env")
    def test_it_paints_its_own_background(self):
        """The dark theme lives on MainWindow's stylesheet and used to reach
        this dialog by inheritance. Opening first means there is nothing to
        inherit from, and pale-green text on the platform's default light
        dialog is close to unreadable."""
        from src.start_screen import StartScreen
        self.assertIn("background-color", StartScreen(None).styleSheet())

    @unittest.skipUnless(_HAVE_QT, "PyQt6 not installed in this env")
    def test_choosing_a_row_before_any_window_exists_returns_that_choice(self):
        """The end-to-end shape of the launch: no MainWindow anywhere, a real
        dialog opens, a row is clicked, and the answer comes back to be carried
        into the window that has not been built yet."""
        from PyQt6.QtCore import QTimer
        from src import onboarding_flow, start_screen

        self._isolate()
        seen = {}

        def _click():
            # activeModalWidget, not "any StartScreen in topLevelWidgets" —
            # earlier tests leave un-exec'd screens lying around, and clicking
            # one of those hangs this test on the modal that is really open.
            dlg = QApplication.activeModalWidget()
            seen["dlg"] = dlg
            if not isinstance(dlg, start_screen.StartScreen):
                return
            seen["parent"] = dlg.parent()
            btn = next(b for b in dlg.findChildren(QPushButton)
                       if any("Open a design" in l.text()
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

        self.assertIsInstance(seen.get("dlg"), start_screen.StartScreen,
                              "no start screen window opened")
        self.assertIsNone(seen["parent"], "the screen is parented to something")
        self.assertEqual(choice, start_screen.OPEN)

    @unittest.skipUnless(_HAVE_QT, "PyQt6 not installed in this env")
    def test_a_suppressed_menu_opens_nothing_and_answers_nothing(self):
        from src import onboarding_flow
        fake = self._isolate()
        fake.d[onboarding_flow.START_SCREEN_OFF_KEY] = True
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
        open(path, "w", encoding="utf-8").close()
        saves.remember_last_design(path)
        self.assertEqual(saves.last_design(), os.path.abspath(path))

    def test_a_deleted_design_is_forgotten_rather_than_offered(self):
        """A Continue button that opens a file the user has since deleted is a
        dead control."""
        from src import saves
        path = os.path.join(self.dir, "gone.perma.geojson")
        open(path, "w", encoding="utf-8").close()
        saves.remember_last_design(path)
        os.unlink(path)
        self.assertEqual(saves.last_design(), "")

    def test_a_corrupt_config_is_survivable(self):
        import src.settings as settings_mod
        from src import saves
        with open(settings_mod._CONFIG_PATH, "w", encoding="utf-8") as f:
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

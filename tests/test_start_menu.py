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
    """V3.23 (ST-4, docs/homeowner/04-start-screen.md §5, Option B): one way
    to start a yard, then the person's own designs, newest first."""

    @classmethod
    def setUpClass(cls):
        cls._app = QApplication.instance() or QApplication(["permadesign-tests"])

    def _screen(self, **kwargs):
        from src.start_screen import StartScreen
        dlg = StartScreen(**kwargs)
        self.addCleanup(dlg.deleteLater)
        return dlg

    def _rows(self, dlg):
        """``[(title, note)]`` of the rows, top to bottom."""
        out = []
        for b in dlg.findChildren(QPushButton):
            labels = b.findChildren(QLabel)
            if len(labels) == 2:
                out.append((labels[0].text(), labels[1].text()))
        return out

    def _links(self, dlg):
        return [b.text() for b in dlg.findChildren(QPushButton)
                if not b.findChildren(QLabel)]

    @staticmethod
    def _designs(n):
        return [{"path": f"/tmp/d{i}.perma.geojson", "name": f"Design {i}",
                 "when": f"{i + 1} days ago", "summary": "3 plants",
                 "error": ""} for i in range(n)]

    def test_a_first_run_offers_one_way_to_start(self):
        dlg = self._screen()
        self.assertEqual(self._rows(dlg),
                         [("Plan a new yard", "start from your address")])
        self.assertEqual(dlg.primary_row().accessibleName(), "Plan a new yard")
        texts = [l.text() for l in dlg.findChildren(QLabel)]
        self.assertIn("Designs you save will be listed here.", texts)
        self.assertIn("Look at an example yard", self._links(dlg))
        self.assertIn("Open a file…", self._links(dlg))

    def test_the_learn_door_stays_as_one_quiet_link(self):
        """S1: the Learn door is kept, below the yard rows, not as a row."""
        dlg = self._screen()
        self.assertIn("Learn about native plants", self._links(dlg))
        self.assertNotIn("Learn", [t for t, _n in self._rows(dlg)])

    def test_returning_lists_the_newest_three_and_leads_with_the_newest(self):
        dlg = self._screen(designs=self._designs(3), total=5)
        rows = self._rows(dlg)
        self.assertEqual([t for t, _n in rows],
                         ["Plan a new yard", "Design 0", "Design 1", "Design 2"])
        self.assertEqual(rows[1][1], "1 days ago")
        self.assertEqual(dlg.primary_row().accessibleName(), "Design 0")
        self.assertIn("All 5 designs…", self._links(dlg))

    def test_no_all_designs_link_when_every_design_is_listed(self):
        dlg = self._screen(designs=self._designs(2), total=2)
        self.assertFalse(any(l.startswith("All ") for l in self._links(dlg)))

    def test_unsaved_work_leads_and_names_its_design(self):
        dlg = self._screen(recover="A very long design name that goes on and on",
                           designs=self._designs(1), total=1)
        title, note = self._rows(dlg)[0]
        self.assertEqual(title, "Restore unsaved changes")
        self.assertLessEqual(len(note), 32)
        self.assertTrue(note.endswith("…"))
        self.assertEqual(dlg.primary_row().accessibleName(),
                         "Restore unsaved changes")

    def test_exactly_one_row_is_primary_and_it_is_the_default(self):
        """Two primary buttons is none; Enter activates the one there is."""
        from src.start_screen import _Row
        for kwargs in ({}, {"designs": self._designs(3), "total": 3},
                       {"recover": "X", "designs": self._designs(2), "total": 2}):
            dlg = self._screen(**kwargs)
            primary = [r for r in dlg.findChildren(_Row) if r.primary]
            self.assertEqual(len(primary), 1, kwargs)
            self.assertTrue(primary[0].isDefault(), kwargs)

    def test_a_design_row_returns_its_path(self):
        from src.start_screen import OPEN_PATH
        dlg = self._screen(designs=self._designs(2), total=2)
        row = next(b for b in dlg.findChildren(QPushButton)
                   if b.accessibleName() == "Design 1")
        row.click()
        self.assertEqual(dlg.choice(), OPEN_PATH)
        self.assertEqual(dlg.chosen_path(), "/tmp/d1.perma.geojson")

    def test_an_unreadable_design_says_so(self):
        designs = self._designs(1)
        designs[0]["error"] = "not a project file"
        rows = self._rows(self._screen(designs=designs, total=1))
        self.assertEqual(rows[1][1], "can't be opened")

    def test_long_names_are_cut(self):
        designs = self._designs(1)
        designs[0]["name"] = "x" * 70
        title = self._rows(self._screen(designs=designs, total=1))[1][0]
        self.assertEqual(len(title), 40)
        self.assertTrue(title.endswith("…"))

    def test_it_says_what_it_is_and_has_no_emoji(self):
        from src.branding import APP_NAME, APP_TAGLINE
        dlg = self._screen(designs=self._designs(1), total=1, recover="X")
        texts = [l.text() for l in dlg.findChildren(QLabel)]
        self.assertIn(APP_NAME, texts)
        self.assertEqual(APP_TAGLINE, "Native plant yards for Edmonton")
        self.assertIn(APP_TAGLINE, texts)
        for text in texts + self._links(dlg):
            self.assertFalse(any(ord(c) > 0x2FFF for c in text), text)

    def test_the_title_names_the_version(self):
        self.assertEqual(self._screen(version="V3.23").windowTitle(),
                         "Site & Pattern V3.23")
        self.assertEqual(self._screen().windowTitle(), "Site & Pattern")

    def test_the_flowering_line_shows_only_when_there_is_one(self):
        line = "In flower around Edmonton in July: Harebell and 4 more."
        with_line = [l.text() for l in self._screen(
            flowering=line).findChildren(QLabel)]
        self.assertIn(line, with_line)
        without = [l.text() for l in self._screen().findChildren(QLabel)]
        self.assertFalse(any(t.startswith("In flower") for t in without))

    def test_every_choice_is_carried_out(self):
        """A row whose key nothing acts on is a button that does nothing."""
        import ast
        import pathlib
        from src import start_screen as wd
        root = pathlib.Path(__file__).resolve().parent.parent / "src"
        handled = ""
        for mod, fn_name in (("onboarding_flow.py", "_dispatch"),
                             ("start_flow.py", "dispatch")):
            tree = ast.parse((root / mod).read_text(encoding="utf-8"))
            handled += ast.dump(next(
                n for n in ast.walk(tree)
                if isinstance(n, ast.FunctionDef) and n.name == fn_name))
        for name in ("RECOVER", "NEW_YARD", "EXAMPLE", "OPEN_PATH",
                     "ALL_DESIGNS", "OPEN_FILE", "CONTINUE", "REFERENCE"):
            self.assertTrue(hasattr(wd, name), name)
            self.assertIn(name, handled, f"{name} is offered but never acted on")

    def test_generate_is_not_a_row(self):
        from src import start_screen
        self.assertFalse(hasattr(start_screen, "GENERATE"))
        rows = self._rows(self._screen())
        self.assertFalse(any("Generate" in t for t, _n in rows), rows)


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
        import pathlib
        src = (pathlib.Path(__file__).resolve().parent.parent
               / "src" / "start_flow.py").read_text(encoding="utf-8")
        fn = next(n for n in ast.walk(ast.parse(src))
                  if isinstance(n, ast.FunctionDef) and n.name == "open_screen")
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
            box = StartScreen(hidden=hidden, show_skip=True
                              ).findChildren(QCheckBox)[0]
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

    def test_the_checkbox_is_offered_only_with_a_last_design(self):
        """S8: *Next time, open my last design directly*, which means nothing
        when there is no last design."""
        from src.start_screen import StartScreen
        from PyQt6.QtWidgets import QCheckBox
        with_last = StartScreen(show_skip=True).findChildren(QCheckBox)[0]
        self.assertEqual(with_last.text(),
                         "Next time, open my last design directly")
        self.assertFalse(with_last.isHidden())
        without = StartScreen().findChildren(QCheckBox)[0]
        self.assertTrue(without.isHidden())
        without.setChecked(True)
        self.assertFalse(without.parent().suppressed())


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
            btn = next((b for b in dlg.findChildren(QPushButton)
                        if b.text() == "Look at an example yard"), None)
            if btn is None:
                dlg.reject()
                return
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
        self.assertEqual(choice, start_screen.EXAMPLE)

    @unittest.skipUnless(_HAVE_QT, "PyQt6 not installed in this env")
    def test_closing_the_screen_at_launch_quits(self):
        """S7: X or Esc on the start screen at launch quits the app."""
        from PyQt6.QtCore import QTimer
        from src import onboarding_flow
        self._isolate()

        def _close():
            dlg = QApplication.activeModalWidget()
            if dlg is not None:
                dlg.reject()

        QTimer.singleShot(0, _close)
        self.assertEqual(onboarding_flow.choose_start_action(),
                         onboarding_flow.QUIT)

    @unittest.skipUnless(_HAVE_QT, "PyQt6 not installed in this env")
    def test_a_suppressed_menu_opens_the_last_design_or_nothing(self):
        """S8: turned off, a launch opens the last design, else the blank
        map. Nothing is shown either way."""
        from src import onboarding_flow, saves, start_screen
        fake = self._isolate()
        fake.d[onboarding_flow.START_SCREEN_OFF_KEY] = True
        self.assertEqual(onboarding_flow.choose_start_action(), "")
        path = os.path.join(saves.saves_dir(), "Yard.perma.geojson")
        with open(path, "w", encoding="utf-8") as f:
            f.write("{}")
        saves.remember_last_design(path)
        self.assertEqual(onboarding_flow.choose_start_action(),
                         start_screen.CONTINUE)

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
        # The flowering line reads the plant database; this test touches none.
        from src import start_flow
        self.addCleanup(setattr, start_flow, "flowering", start_flow.flowering)
        start_flow.flowering = lambda month=None: ("", "")
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


@unittest.skipUnless(_HAVE_QT, "PyQt6 not installed in this env")
class TestAChoiceAfterTheMapHasLoaded(unittest.TestCase):
    """F197 (V3.04). The window is built behind the start screen, so the map
    usually says it is ready while the screen is still up; the choice then
    waited for a ``map_ready`` that had already gone by, and Continue, Open a
    design, See a finished design and Recover did nothing. Traced in the V2.98
    review: map ready at 1.92 s, Continue at 25.87 s, no design."""

    @classmethod
    def setUpClass(cls):
        cls._app = QApplication.instance() or QApplication(["permadesign-tests"])

    def _main(self, ready: bool):
        """A stand-in window: a live Qt object (the choice is dropped for a
        window that has gone), whose map has or has not loaded."""
        from types import SimpleNamespace
        from PyQt6.QtCore import QObject, pyqtSignal

        class Bridge(QObject):
            map_ready = pyqtSignal()

        main = QObject()
        main.map_widget = SimpleNamespace(is_ready=ready, bridge=Bridge(main))
        self.addCleanup(main.deleteLater)
        return main

    def _act(self, main, choice="continue"):
        from src import onboarding_flow
        done = []
        original = onboarding_flow._dispatch
        onboarding_flow._dispatch = lambda m, c: done.append(c)
        self.addCleanup(setattr, onboarding_flow, "_dispatch", original)
        onboarding_flow.act_on_start_choice(main, choice)
        self._app.processEvents()
        return done

    def test_a_choice_made_after_the_map_loaded_is_carried_out(self):
        for choice in ("continue", "open", "example", "recover"):
            with self.subTest(choice=choice):
                self.assertEqual(self._act(self._main(ready=True), choice), [choice])

    def test_a_choice_made_before_still_waits_for_the_map_and_runs_once(self):
        main = self._main(ready=False)
        done = self._act(main)
        self.assertEqual(done, [])
        main.map_widget.bridge.map_ready.emit()
        main.map_widget.bridge.map_ready.emit()     # a reload: not twice
        self.assertEqual(done, ["continue"])


if __name__ == "__main__":
    unittest.main()

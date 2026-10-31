"""
Learn mode (V2.43): the boot-time door split, the species-discovery ledger,
and the editable reference landscapes.

The three things worth guarding here, in order of how badly they would hurt:

1. **The ledger must survive a reseed.** A schema bump wipes and rebuilds the
   catalogue. If it also wiped the record of what somebody had found, the loss
   would be silent and total, and nothing on screen would look wrong.
2. **Learn mode must not open the design app.** That is the entire content of
   the split — "the beginner does not meet the map" — and it is one boolean
   away from quietly regressing.
3. **Edits must go through ProjectStore.** ``tests/test_project_store.py``
   greps for violations in ``src/``, but a module that hand-rolled the same
   mutation through a helper would slip past a grep; this checks the sandbox
   actually round-trips.
"""

from __future__ import annotations

import os
import shutil
import tempfile
import unittest

try:
    from PyQt6.QtWidgets import QApplication
    _HAVE_QT = True
except ImportError:                                        # pragma: no cover
    _HAVE_QT = False


class _TempDataDir(unittest.TestCase):
    """Redirect the DB and saves folder into a temp dir, per the house pattern
    in tests/test_polycultures.py. Never touches the real user data."""

    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.mkdtemp()
        cls._old_xdg = os.environ.get("XDG_DATA_HOME")
        os.environ["XDG_DATA_HOME"] = cls._tmp
        from src.db import plants
        plants.init_db()

    @classmethod
    def tearDownClass(cls):
        if cls._old_xdg is None:
            os.environ.pop("XDG_DATA_HOME", None)
        else:
            os.environ["XDG_DATA_HOME"] = cls._old_xdg
        shutil.rmtree(cls._tmp, ignore_errors=True)


# ── The ledger ───────────────────────────────────────────────────────────────

class TestDiscoveryLedger(_TempDataDir):

    def setUp(self):
        from src.db.plants import get_connection
        conn = get_connection()
        with conn:
            conn.execute("DELETE FROM discovered_species")
            conn.execute("DELETE FROM learn_state")
        conn.close()

    def test_first_sighting_is_reported_as_new(self):
        """So a caller can say "new!" without querying first."""
        from src.db import progress
        self.assertTrue(progress.record_seen("fauna", "Bombus huntii"))
        self.assertFalse(progress.record_seen("fauna", "Bombus huntii"))

    def test_reseeing_does_not_rewrite_the_first_sighting(self):
        """The first time you found something is the fact worth keeping. An
        "inspected" that later became "caught" used to be the kind of thing a
        naive upsert would quietly overwrite."""
        from src.db import progress
        from src.db.plants import get_connection
        progress.record_seen("fauna", "Danaus plexippus",
                             how=progress.HOW_INSPECTED)
        progress.record_seen("fauna", "Danaus plexippus",
                             how=progress.HOW_CAUGHT)
        conn = get_connection()
        row = conn.execute(
            "SELECT how, times_seen FROM discovered_species "
            " WHERE scientific_name = 'Danaus plexippus'").fetchone()
        conn.close()
        self.assertEqual(row[0], progress.HOW_INSPECTED)
        self.assertEqual(row[1], 2)

    def test_it_survives_a_reseed(self):
        """THE test in this file.

        A schema bump destroys and rebuilds the catalogue. The ledger is
        user-authored and is deliberately absent from the reseed wipe list in
        ``plants.init_db``; if somebody ever adds it there "for consistency",
        this fails.
        """
        from src.db import plants, progress
        progress.record_seen("fauna", "Bombus huntii")
        progress.record_seen("plant", "Monarda fistulosa")
        progress.set_state(progress.LAST_COMMUNITY, "wet_meadow")

        conn = plants.get_connection()
        with conn:
            conn.execute("UPDATE _schema_version SET version = 1")
        conn.close()
        plants.init_db()             # forces the full reseed path

        self.assertEqual(progress.discovered(),
                         {"Bombus huntii", "Monarda fistulosa"})
        self.assertEqual(progress.get_state(progress.LAST_COMMUNITY),
                         "wet_meadow")

    def test_the_ledger_is_not_in_the_reseed_wipe_list(self):
        """Read as text, so it fails at the moment somebody types the DELETE
        rather than only when a user upgrades."""
        import pathlib
        src = (pathlib.Path(__file__).resolve().parent.parent
               / "src" / "db" / "plants.py").read_text(encoding="utf-8")
        for table in ("discovered_species", "learn_state"):
            self.assertNotIn(f"DELETE FROM {table}", src,
                             f"{table} holds user-authored rows and must "
                             f"never be wiped by the reseed")

    def test_coverage_counts_against_the_live_catalogue(self):
        """A fraction whose denominator is a stored constant goes stale and
        lies (P9)."""
        from src.db import progress
        progress.record_seen("plant", "Monarda fistulosa")
        cov = progress.coverage()
        self.assertEqual(cov["plants_seen"], 1)
        self.assertGreater(cov["plants_total"], 100)
        self.assertEqual(cov["total"],
                         cov["plants_total"] + cov["fauna_total"])
        self.assertIn("species discovered", progress.coverage_line())

    def test_nothing_here_raises_on_a_broken_database(self):
        """These feed a start screen. A count that cannot be read must never
        be the reason the app's front door fails to open."""
        from unittest import mock
        from src.db import progress
        with mock.patch.object(progress, "_conn", return_value=None):
            self.assertEqual(progress.discovered(), set())
            self.assertEqual(progress.coverage_line(), "")
            self.assertFalse(progress.record_seen("fauna", "X"))
            self.assertEqual(progress.get_state("k", "fallback"), "fallback")


# ── The routing ──────────────────────────────────────────────────────────────

class TestTheDoorSplit(unittest.TestCase):
    """Qt-free: routing is the part that must be testable without a display."""

    def test_learn_choices_do_not_open_the_design_app(self):
        from src import app_mode
        for key in (app_mode.WALK, app_mode.LESSONS, app_mode.QUIZZES):
            self.assertFalse(app_mode.opens_main_window(key), key)

    def test_a_dismissed_start_screen_still_opens_the_app(self):
        """"" has always meant "start me on the blank map". Turning it into
        "show nothing" would leave the user with no app at all."""
        from src import app_mode
        self.assertTrue(app_mode.opens_main_window(""))
        self.assertTrue(app_mode.opens_main_window(app_mode.DESIGN))
        # The example sits in the Learn card and is a design, on the map.
        self.assertTrue(app_mode.opens_main_window("example"))

    def test_main_gates_the_window_on_the_mode(self):
        """Read main.py as text — the alternative is launching the real app."""
        import pathlib
        src = (pathlib.Path(__file__).resolve().parent.parent
               / "main.py").read_text(encoding="utf-8")
        self.assertIn("app_mode.opens_main_window(choice)", src)
        self.assertIn("window.show()", src)

    def test_the_learn_menu_is_gone(self):
        """V3.42 (the owner): the walk, the lessons and the quizzes are on
        the start screen, so the second screen they sat behind, and its Back,
        went."""
        import importlib.util
        from src import app_mode, learn_flow
        for name in ("LEARN", "BACK", "LEARN_DOORS", "learn_notes", "STUDIO",
                     "GUIDE"):
            self.assertFalse(hasattr(app_mode, name), name)
        self.assertFalse(hasattr(learn_flow, "open_learn_menu"))
        self.assertIsNone(importlib.util.find_spec("src.learn_menu"))

    def test_every_learn_door_is_acted_on(self):
        """A row whose key nothing dispatches is a button that does nothing."""
        import ast
        import pathlib
        from src import app_mode
        src = (pathlib.Path(__file__).resolve().parent.parent
               / "src" / "onboarding_flow.py").read_text(encoding="utf-8")
        fn = next(n for n in ast.walk(ast.parse(src))
                  if isinstance(n, ast.FunctionDef) and n.name == "_dispatch")
        handled = ast.dump(fn)
        names = {app_mode.WALK: "REFERENCE", app_mode.LESSONS: "LESSONS",
                 app_mode.QUIZZES: "QUIZZES"}
        self.assertEqual(set(names), set(app_mode._LEARN_ONLY))
        for key, const in names.items():
            self.assertIn(f"id='{const}'", handled,
                          f"{key} is offered but never acted on")

    def test_cancel_returns_to_the_start_screen(self):
        """All N designs… and Open a file… open over the start screen, and
        Cancel comes back to it (V3.37); the Learn menu's Back did too until
        V3.42. Without the loop the only way out would be to quit."""
        import ast
        import pathlib
        src = (pathlib.Path(__file__).resolve().parent.parent
               / "src" / "onboarding_flow.py").read_text(encoding="utf-8")
        fn = next(n for n in ast.walk(ast.parse(src))
                  if isinstance(n, ast.FunctionDef) and n.name == "_menu_loop")
        self.assertTrue(any(isinstance(n, ast.While) for n in ast.walk(fn)),
                        "_menu_loop must loop, or Cancel has nowhere to go")


# ── The sandbox ──────────────────────────────────────────────────────────────

class TestEditableReferenceLandscapes(_TempDataDir):

    def setUp(self):
        from src import reference_edit
        reference_edit.reset_sandbox("aspen_parkland")
        self.center = (51.05, -114.07)

    def _placed(self, project):
        from src.project_store import ProjectStore
        return ProjectStore(project).placed_plants

    def test_a_fresh_community_is_the_curated_one(self):
        from src import reference_edit
        project = reference_edit.open_sandbox("aspen_parkland",
                                              center=self.center)
        self.assertGreater(len(self._placed(project)), 10)

    def test_planting_and_pulling_round_trip(self):
        from src import reference_edit
        project = reference_edit.open_sandbox("aspen_parkland",
                                              center=self.center)
        before = len(self._placed(project))
        pick = reference_edit.palette("aspen_parkland")[0]

        rec = reference_edit.plant_at(project, pick["plant_id"],
                                      pick["common_name"], self.center,
                                      3.0, -2.0)
        self.assertEqual(len(self._placed(project)), before + 1)

        found = reference_edit.nearest_plant(project, self.center, 3.0, -2.0)
        self.assertIsNotNone(found)
        self.assertEqual(found["plant_id"], pick["plant_id"])

        reference_edit.pull_at(project, found["plant_id"], found["lat"],
                               found["lng"],
                               feature_id=found.get("feature_id", ""))
        self.assertEqual(len(self._placed(project)), before)
        self.assertEqual(rec["common_name"], pick["common_name"])

    def test_the_two_structures_stay_in_step(self):
        """The project's features and the placed-plant index are two views of
        one thing; every bug from bypassing ProjectStore was a divergence
        between them."""
        from src import reference_edit
        from src.project_store import ProjectStore
        project = reference_edit.open_sandbox("aspen_parkland",
                                              center=self.center)
        pick = reference_edit.palette("aspen_parkland")[0]
        reference_edit.plant_at(project, pick["plant_id"],
                                pick["common_name"], self.center, 1.0, 1.0)
        store = ProjectStore(project)
        self.assertEqual(store.check_consistency(), [])

    def test_metres_round_trip_through_the_app_projection(self):
        """A hand-rolled constant here would drift from the scene the sandbox
        is drawn in."""
        from src import reference_edit
        lat, lng = reference_edit.offset_latlng(51.05, -114.07, 5.0, -3.0)
        dx, dy = reference_edit.local_offset(lat, lng, 51.05, -114.07)
        self.assertAlmostEqual(dx, 5.0, places=3)
        self.assertAlmostEqual(dy, -3.0, places=3)

    def test_the_palette_is_the_community_not_the_catalogue(self):
        """A wild community is a set of plants that belong together; a palette
        offering everything teaches the opposite."""
        from src import reference_edit
        from src.db.plants import get_all_plants
        pal = reference_edit.palette("mixedgrass_prairie")
        self.assertTrue(pal)
        self.assertLessEqual(len(pal), reference_edit.PALETTE_SIZE)
        self.assertLess(len(pal), len(get_all_plants()))
        for item in pal:
            self.assertIn(item["layer"],
                          {"canopy", "shrub", "forb", "grass"})

    def test_a_sandbox_persists_and_resets(self):
        from src import reference_edit
        project = reference_edit.open_sandbox("aspen_parkland",
                                              center=self.center)
        pick = reference_edit.palette("aspen_parkland")[0]
        reference_edit.plant_at(project, pick["plant_id"],
                                pick["common_name"], self.center, 4.0, 4.0)
        n = len(self._placed(project))
        self.assertTrue(reference_edit.save_sandbox("aspen_parkland", project))

        reopened = reference_edit.open_sandbox("aspen_parkland",
                                               center=self.center)
        self.assertEqual(len(self._placed(reopened)), n)

        reference_edit.reset_sandbox("aspen_parkland")
        self.assertIsNone(reference_edit.load_sandbox("aspen_parkland"))

    def test_a_corrupt_sandbox_reads_as_absent(self):
        """It puts the user back in the pristine community rather than in
        front of a traceback."""
        from src import reference_edit
        path = reference_edit.sandbox_path("aspen_parkland")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("{ not json")
        self.assertIsNone(reference_edit.load_sandbox("aspen_parkland"))
        self.assertGreater(
            len(self._placed(reference_edit.open_sandbox(
                "aspen_parkland", center=self.center))), 0)

    def test_the_consequence_is_plant_impacts_own_verdict(self):
        """Not a second answer to "what does pulling this cost". The app must
        not grow two."""
        import ast
        import pathlib
        from src import reference_edit
        src = (pathlib.Path(__file__).resolve().parent.parent
               / "src" / "reference_edit.py").read_text(encoding="utf-8")
        fn = next(n for n in ast.walk(ast.parse(src))
                  if isinstance(n, ast.FunctionDef)
                  and n.name == "pull_consequence")
        self.assertIn("pull_plant_impact", ast.dump(fn))

        project = reference_edit.open_sandbox("aspen_parkland",
                                              center=self.center)
        placed = self._placed(project)
        line = reference_edit.pull_consequence(placed, placed[0]["plant_id"])
        self.assertTrue(line)

    def test_pulling_something_absent_says_nothing_rather_than_raising(self):
        from src import reference_edit
        self.assertEqual(reference_edit.pull_consequence([], 999999), "")


# ── The windows ──────────────────────────────────────────────────────────────

@unittest.skipUnless(_HAVE_QT, "PyQt6 not installed in this env")
class TestTheLearnScreens(_TempDataDir):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._app = QApplication.instance() or QApplication(["tests"])

    def _screen(self, **kwargs):
        from src.start_screen import StartScreen
        dlg = StartScreen(**kwargs)
        self.addCleanup(dlg.deleteLater)
        return dlg

    def test_the_learn_card_offers_four_doors_in_order(self):
        """V3.42 (the owner): the example, the walk, the lessons and the
        quizzes, grouped as Learn on the start screen, Lessons and Quizzes as
        separate items. V3.22 took the Plant Directory out (RM-10, S4)."""
        from src.start_rows import LearnCard
        dlg = self._screen()
        card = dlg.findChild(LearnCard)
        self.assertEqual([r.words[0] for r in card.rows],
                         ["Look at an example yard", "Walk a wild landscape",
                          "Lessons", "Quizzes"])

    def test_each_learn_door_returns_its_key(self):
        from src import app_mode
        from src import start_screen as s
        from src.start_rows import LearnCard
        keys = [s.EXAMPLE, app_mode.WALK, app_mode.LESSONS, app_mode.QUIZZES]
        for i, key in enumerate(keys):
            dlg = self._screen()
            dlg.findChild(LearnCard).rows[i].click()
            self.assertEqual(dlg.choice(), key)
        # The walk keeps the key the start screen used for it before V2.43.
        self.assertEqual(s.REFERENCE, app_mode.WALK)

    def test_each_learn_line_is_short_and_starts_with_a_capital(self):
        """The owner, V3.42: the description "sentence" starts with a
        capital. Five words at most, the start screen's rule for a note."""
        from src.start_screen import learn_rows, walk_note
        for places in (0, 1, 7, 30):
            for _key, title, line, _tip in learn_rows(places):
                # A capital, or a figure ("30 native places", "24 plants"):
                # never a small letter.
                self.assertTrue(line and not line[0].islower(), (title, line))
                self.assertLessEqual(len(line.split()), 5, line)
        self.assertEqual(walk_note(7), "Seven native places, in 3D")
        self.assertEqual(walk_note(1), "One native place, in 3D")
        self.assertEqual(walk_note(0), "Native places, in 3D")

    def test_the_walk_counts_its_places(self):
        """Counted, not typed: the number on the screen is the walks there
        are."""
        from src import learn_flow
        from src.reference_ecosystem import community_keys
        self.assertEqual(learn_flow.community_count(), len(community_keys()))

    def test_the_lessons_and_quizzes_tooltips_come_from_their_owners(self):
        """A rewrite of the lessons touches nothing else (V3.41's rule), so
        the tooltip reads their titles rather than repeating them."""
        from src.lessons import LESSONS
        from src.quiz_topics import GROUPS
        from src import app_mode
        from src.start_screen import learn_rows
        tips = {k: tip for k, _t, _l, tip in learn_rows()}
        for _k, title, _steps in LESSONS:
            self.assertIn(title, tips[app_mode.LESSONS])
        for _k, title, _topics in GROUPS:
            self.assertIn(title, tips[app_mode.QUIZZES])

    def test_the_lessons_window_takes_a_landscape(self):
        """LearnPanel is design-aware and had nothing to talk about in Learn
        mode until the sandbox became a real project."""
        from src import reference_edit
        from src.learn_window import LearnStudioWindow
        from src.project_store import ProjectStore
        project = reference_edit.open_sandbox("aspen_parkland",
                                              center=(51.05, -114.07))
        plants = ProjectStore(project).placed_plants
        win = LearnStudioWindow(plants, "Aspen Parkland grove")
        self.assertEqual(len(win.panel._placed_plants), len(plants))
        win.set_plants([])
        self.assertEqual(win.panel._placed_plants, [])
        win.close()

    def test_the_lessons_window_opens_with_no_sandbox_at_all(self):
        """A first-time learner is never shown a locked door."""
        from src.learn_window import LearnStudioWindow
        win = LearnStudioWindow([], "")
        self.assertIsNotNone(win.panel)
        win.close()

    def test_the_lessons_window_has_no_present(self):
        """V3.38 (F258): the tour told a wild community it "began as lawn".
        The Learn window keeps Field Study and Lessons; the main window's
        panel still builds Present for Share › Present (the owner's D4)."""
        from src.learn_window import LearnStudioWindow
        from src.learn_panel import LearnPanel
        win = LearnStudioWindow([], "")
        tabs = win.panel._tabs
        self.assertEqual([tabs.tabText(i) for i in range(tabs.count())],
                         ["Field Study", "Lessons"])
        self.assertFalse(hasattr(win.panel, "_docent"))
        win.set_plants([])                 # refreshes without a docent
        win.close()
        panel = LearnPanel()
        self.assertTrue(hasattr(panel, "_present_page"))
        panel.deleteLater()

    def test_lessons_and_quizzes_each_open_their_own_page(self):
        """V3.42 (the owner): separate doors, so each window shows the page
        it was opened for, under its own title, with no tab bar to the other."""
        from src import app_mode
        from src.learn_window import LearnStudioWindow
        for page, title, shown in ((app_mode.LESSONS, "Lessons", "_lesson_track"),
                                   (app_mode.QUIZZES, "Quizzes", "_field_study")):
            win = LearnStudioWindow([], "Aspen Parkland grove", page=page)
            self.assertEqual(win.windowTitle(),
                             f"Site & Pattern: {title} — Aspen Parkland grove")
            tabs = win.panel._tabs
            self.assertTrue(tabs.currentWidget().isAncestorOf(
                getattr(win.panel, shown)), page)
            self.assertTrue(tabs.tabBar().isHidden(), page)
            win.close()

    def test_the_last_lesson_can_be_left(self):
        """Its button read Finish and was disabled, so it could never be
        pressed (V3.38). Since V3.41 the end of a lesson leads to the next,
        and the end of the last starts them again."""
        from src.lesson_track_widget import LessonTrackWidget
        w = LessonTrackWidget(plants_provider=lambda: [])
        lessons = w._lesson_box.count()
        self.assertEqual(lessons, 3)
        for n in range(lessons):
            self.assertEqual(w._lesson_box.currentIndex(), n)
            for _ in range(len(w._steps) - 1):
                w._next.click()
            self.assertEqual(w._i, len(w._steps) - 1)
            self.assertTrue(w._next.isEnabled())
            self.assertEqual(w._next.text(), "Next lesson →"
                             if n + 1 < lessons else "Start again")
            w._next.click()
            self.assertEqual(w._i, 0)
        self.assertEqual(w._lesson_box.currentIndex(), 0)
        w.deleteLater()

    def test_a_lesson_talks_about_a_landscape_you_choose(self):
        """V3.41: "taught against your design" meant the walk's sandbox, and
        read as unclear. The first landscape is named for what it is, and a
        walk can be chosen instead."""
        from src.learn_window import LearnStudioWindow
        win = LearnStudioWindow([], title="Aspen Parkland grove")
        w = win.panel._lesson_track
        self.assertEqual(w._about.itemText(0),
                         "The walk you planted in: Aspen Parkland grove")
        walk = next(i for i in range(w._about.count())
                    if w._about.itemData(i) == ("walk", "boreal_mixedwood"))
        w._about.setCurrentIndex(walk)
        self.assertTrue(w._readout.isVisibleTo(w))
        self.assertIn("Boreal Mixedwood", w._readout.text())
        self.assertIn("caterpillar", w._readout.text())
        win.close()

    def test_the_lessons_door_opens_its_window(self):
        """V3.17 shipped this door dead: a NameError (``_sandbox_plants``)
        swallowed by ``_safely``, then main.py's safety net showed the design
        window instead. Nothing opened the door in a test until V3.18."""
        from types import SimpleNamespace
        from src import app_mode, learn_flow
        from src.learn_window import LearnStudioWindow
        main = SimpleNamespace()
        with self.assertNoLogs("sitepattern", level="ERROR"):
            learn_flow.open_studio(main)
            learn_flow.open_studio(main, page=app_mode.QUIZZES)
        windows = getattr(main, "_learn_windows", {})
        lessons = windows.get(app_mode.LESSONS)
        quizzes = windows.get(app_mode.QUIZZES)
        self.assertIsInstance(lessons, LearnStudioWindow,
                              "the Lessons door opened nothing")
        self.assertIsInstance(quizzes, LearnStudioWindow,
                              "the Quizzes door opened nothing")
        self.assertIsNot(lessons, quizzes)
        self.assertTrue(lessons.isVisible() and quizzes.isVisible())
        # A second click raises the window it opened, not another.
        learn_flow.open_studio(main, page=app_mode.LESSONS)
        self.assertIs(main._learn_windows[app_mode.LESSONS], lessons)
        lessons.close()
        quizzes.close()

    def test_a_door_that_fails_is_logged_not_swallowed(self):
        """V3.18 (ST-3): ``_safely`` names what failed in the app's log."""
        from src import learn_flow, onboarding_flow
        for flow in (learn_flow, onboarding_flow):
            with self.assertLogs("sitepattern", level="ERROR") as logs:
                flow._safely(lambda: 1 / 0, "The thing")
            self.assertTrue(any("The thing could not open" in line
                                and "ZeroDivisionError" in line
                                for line in logs.output), logs.output)


# ── The viewer contract ──────────────────────────────────────────────────────

class TestTheEditingBridge(unittest.TestCase):
    """The JS↔Python seam, read as text — the alternative is a real GPU."""

    def _js(self):
        import pathlib
        return (pathlib.Path(__file__).resolve().parent.parent
                / "html" / "scene3d" / "16-editing.js").read_text(encoding="utf-8")

    def test_the_chunk_is_loaded_by_the_viewer(self):
        import pathlib
        html_dir = pathlib.Path(__file__).resolve().parent.parent / "html"
        html = (html_dir / "scene3d.html").read_text(encoding="utf-8")
        self.assertIn("qwebchannel.js", html)
        # The chunk list left the page in V3.39 (html/scene3d/chunks.js).
        chunks = (html_dir / "scene3d" / "chunks.js").read_text(
            encoding="utf-8")
        # After 15-florets.js in the list: its pointer handlers must register
        # after 10-inspect.js's so both see the same click.
        entry = "'scene3d/16-editing.js',"
        self.assertIn(entry, chunks)
        self.assertGreater(chunks.index(entry),
                           chunks.index("'scene3d/15-florets.js',"))

    def test_the_viewer_reports_coordinates_and_decides_nothing(self):
        """Geometry in, coordinates out. Placement logic here would be a
        second write path for the project dict."""
        js = self._js()
        self.assertIn("bridge.plantAt(", js)
        self.assertIn("bridge.pullAt(", js)
        # Strip the comments before looking for state mutation — the header
        # explains ProjectStore at length, which is the point.
        code = "\n".join(ln for ln in js.splitlines()
                         if not ln.lstrip().startswith("//"))
        for forbidden in ("features.push", "placed_plants", "ProjectStore",
                          "plant_feature"):
            self.assertNotIn(forbidden, code,
                             "the viewer must not carry placement logic")

    def test_the_scene_to_world_mapping_is_written_down(self):
        """World Z is negative scene Y. Getting it backwards mirrors every
        placement, which looks almost right."""
        self.assertIn("-_hitPoint.z", self._js())

    def test_it_degrades_without_qt(self):
        """A plain browser, the fork build, a screenshot harness — all must
        behave exactly as the viewer did before V2.43."""
        js = self._js()
        self.assertIn("typeof QWebChannel === 'undefined'", js)
        self.assertIn("if (!_editMode || !_bridge) return;", js)

    def test_the_trowel_suppresses_the_inspect_card(self):
        """A click meant to pull a plant must not also open its dossier."""
        import pathlib
        inspect = (pathlib.Path(__file__).resolve().parent.parent
                   / "html" / "scene3d" / "10-inspect.js").read_text(encoding="utf-8")
        self.assertIn("window.__permaEditMode", inspect)
        self.assertIn("window.__permaEditMode", self._js())

    def test_the_bridge_slot_name_is_not_shadowed_by_a_signal(self):
        """QWebChannel puts signals and slots in one JS namespace: a signal
        sharing a slot's name shadows it with an object that is not callable,
        and the viewer calls ``bridge.inspected(...)``."""
        from src.map3d_widget import Scene3DBridge
        self.assertTrue(callable(getattr(Scene3DBridge, "inspected", None)))
        self.assertIn("species_inspected", dir(Scene3DBridge))

    def test_the_fork_build_gets_no_bridge(self):
        """web3d/dist is a separate app that does not carry 16-editing.js, so
        a channel there would register an object nothing ever calls."""
        import ast
        import pathlib
        src = (pathlib.Path(__file__).resolve().parent.parent
               / "src" / "map3d_widget.py").read_text(encoding="utf-8")
        self.assertIn('if self.mode == "builtin":', src)
        tree = ast.parse(src)
        self.assertTrue(any(isinstance(n, ast.ClassDef)
                            and n.name == "Scene3DBridge"
                            for n in ast.walk(tree)))

    def test_the_edit_mode_js_builder_round_trips(self):
        from src import map3d_js
        js = map3d_js.set_edit_mode("plant", {"plant_id": 7,
                                              "common_name": "Bergamot"})
        self.assertIn("window.permaSetEditMode &&", js)
        self.assertIn('"plant_id": 7', js)
        self.assertIn("window.permaSetEditMode(\"\", null)",
                      map3d_js.set_edit_mode(""))


if __name__ == "__main__":
    unittest.main()

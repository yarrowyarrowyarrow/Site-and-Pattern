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
    from PyQt6.QtWidgets import QApplication, QLabel, QPushButton
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
        for key in (app_mode.WALK, app_mode.GUIDE, app_mode.STUDIO):
            self.assertFalse(app_mode.opens_main_window(key), key)

    def test_a_dismissed_start_screen_still_opens_the_app(self):
        """"" has always meant "start me on the blank map". Turning it into
        "show nothing" would leave the user with no app at all."""
        from src import app_mode
        self.assertTrue(app_mode.opens_main_window(""))
        self.assertTrue(app_mode.opens_main_window(app_mode.DESIGN))

    def test_main_gates_the_window_on_the_mode(self):
        """Read main.py as text — the alternative is launching the real app."""
        import pathlib
        src = (pathlib.Path(__file__).resolve().parent.parent
               / "main.py").read_text(encoding="utf-8")
        self.assertIn("app_mode.opens_main_window(choice)", src)
        self.assertIn("window.show()", src)

    def test_the_learn_doors_reuse_the_existing_choice_keys(self):
        """WALK and GUIDE are the keys the start screen already used for these
        surfaces, so ``onboarding_flow._dispatch`` needed no second way to say
        the same thing."""
        from src import app_mode
        from src import start_screen
        self.assertEqual(app_mode.WALK, start_screen.REFERENCE)
        self.assertEqual(app_mode.GUIDE, start_screen.DIRECTORY)

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
        for key, _icon, _title in app_mode.LEARN_DOORS:
            const = {app_mode.WALK: "REFERENCE", app_mode.GUIDE: "DIRECTORY",
                     app_mode.STUDIO: "STUDIO"}[key]
            self.assertIn(const, handled, f"{key} is offered but never acted on")

    def test_back_returns_to_the_start_screen(self):
        """The Learn menu is a second screen, not a dead end. Without the loop
        the only way out of a wrong door would be to quit."""
        import ast
        import pathlib
        src = (pathlib.Path(__file__).resolve().parent.parent
               / "src" / "onboarding_flow.py").read_text(encoding="utf-8")
        fn = next(n for n in ast.walk(ast.parse(src))
                  if isinstance(n, ast.FunctionDef) and n.name == "_menu_loop")
        self.assertTrue(any(isinstance(n, ast.While) for n in ast.walk(fn)),
                        "_menu_loop must loop, or Back has nowhere to go")

    def test_notes_survive_having_nothing_to_say(self):
        """Every one of these runs before any project exists."""
        from src import app_mode
        notes = app_mode.learn_notes()
        self.assertEqual(set(notes), {app_mode.WALK, app_mode.GUIDE,
                                      app_mode.STUDIO})
        for text in notes.values():
            self.assertTrue(text)
            # Same five-word ceiling the start screen's rows are held to.
            self.assertLessEqual(len(text.split()), 5, text)


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

    def _rows(self, dlg):
        return [lab.text() for b in dlg.findChildren(QPushButton)
                for lab in b.findChildren(QLabel)]

    def test_the_learn_menu_offers_every_door(self):
        from src import app_mode
        from src.learn_menu import LearnMenu
        text = " ".join(self._rows(LearnMenu()))
        for _key, _icon, title in app_mode.LEARN_DOORS:
            self.assertIn(title, text)

    def test_a_row_returns_its_key(self):
        from src import app_mode
        from src.learn_menu import LearnMenu
        dlg = LearnMenu()
        dlg._pick(app_mode.WALK)
        self.assertEqual(dlg.choice(), app_mode.WALK)

    def test_back_is_offered(self):
        from src.learn_menu import BACK, LearnMenu
        dlg = LearnMenu()
        labels = [b.text() for b in dlg.findChildren(QPushButton)]
        self.assertTrue(any("Back" in t for t in labels), labels)
        dlg._pick(BACK)
        self.assertEqual(dlg.choice(), BACK)

    def test_the_menu_needs_no_mainwindow(self):
        """It can open before anything else exists — same property the start
        screen has had since V2.40."""
        from src.learn_menu import LearnMenu
        dlg = LearnMenu()
        self.assertIsNone(dlg.parent())
        self.assertIn("background-color", dlg.styleSheet())

    def test_the_lessons_window_takes_a_landscape(self):
        """LearnPanel is design-aware and had nothing to talk about in Learn
        mode until the sandbox became a real project."""
        from src import reference_edit
        from src.learn_menu import LearnStudioWindow
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
        from src.learn_menu import LearnStudioWindow
        win = LearnStudioWindow([], "")
        self.assertIsNotNone(win.panel)
        win.close()


# ── The viewer contract ──────────────────────────────────────────────────────

class TestTheEditingBridge(unittest.TestCase):
    """The JS↔Python seam, read as text — the alternative is a real GPU."""

    def _js(self):
        import pathlib
        return (pathlib.Path(__file__).resolve().parent.parent
                / "html" / "scene3d" / "16-editing.js").read_text(encoding="utf-8")

    def test_the_chunk_is_loaded_by_the_viewer(self):
        import pathlib
        html = (pathlib.Path(__file__).resolve().parent.parent
                / "html" / "scene3d.html").read_text(encoding="utf-8")
        self.assertIn("scene3d/16-editing.js", html)
        self.assertIn("qwebchannel.js", html)
        # Last in the FILES array: its pointer handlers must register after
        # 10-inspect.js's so both see the same click. Matched against the
        # array entry, not the first mention — the comment above the
        # qwebchannel tag names the file too.
        entry = "'scene3d/16-editing.js',"
        self.assertIn(entry, html)
        self.assertGreater(html.index(entry),
                           html.index("'scene3d/15-florets.js',"))

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

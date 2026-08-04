"""
tests/test_onboarding.py

The cold-start path (F44 / F45) — src/onboarding.py's Qt-free core, plus a
headless-Qt smoke test of the widgets that render it.

What matters here is that the guidance is *true about the project in front of
the user*, and that the worked example is a real design rather than a token:

  * a step is done when the project actually contains the thing, and the steps
    are independent (drawing a boundary before dropping a pin still counts);
  * the strip retires itself once the path is walked;
  * the example resolves species against the LIVE catalogue and reports what it
    could not resolve, instead of silently shipping a thinner design (P9);
  * the example's plants go through ProjectStore, so its two structures agree
    exactly as they would if the user had clicked each plant onto the map;
  * the Generate defaults a first-timer gets are real goal keys.

The pure tests need neither Qt nor the DB (the catalogue lookup is injected).
"""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_TMP_DIR = tempfile.mkdtemp(prefix="permadesign_onboarding_test_")
try:
    import src.db.plants as _plants_mod
    _plants_mod._DATA_DIR = _TMP_DIR
    _plants_mod._DB_PATH = os.path.join(_TMP_DIR, "permadesign_test.db")
except Exception:                                    # pragma: no cover
    pass

from src import onboarding  # noqa: E402


def _project(*, pin=False, boundary=False, plants=False) -> dict:
    proj = {"type": "FeatureCollection",
            "properties": {"site_config": {}}, "features": []}
    if pin:
        proj["properties"]["site_config"] = {"latitude": 53.5,
                                             "longitude": -113.5}
    if boundary:
        proj["features"].append(
            {"properties": {"element_type": "property_boundary"}})
    if plants:
        proj["features"].append({"properties": {"element_type": "plant"}})
    return proj


def _fake_lookup(known):
    """Catalogue stand-in: only ``known`` names resolve."""
    def lookup(name):
        if name in known:
            return {"id": 1000 + sorted(known).index(name),
                    "common_name": name}
        return None
    return lookup


class TestSteps(unittest.TestCase):

    def test_empty_project_is_on_step_one(self):
        step = onboarding.first_step(_project())
        self.assertEqual(step["index"], 1)
        self.assertEqual(step["key"], "pin")
        self.assertFalse(step["complete"])

    def test_pin_advances_to_the_boundary(self):
        step = onboarding.first_step(_project(pin=True))
        self.assertEqual(step["key"], "boundary")
        self.assertEqual(step["index"], 2)

    def test_all_three_done_reports_complete(self):
        step = onboarding.first_step(
            _project(pin=True, boundary=True, plants=True))
        self.assertTrue(step["complete"])

    def test_steps_are_independent_not_a_strict_sequence(self):
        # Someone who drew a boundary before dropping a pin HAS done step 2;
        # telling them otherwise would be wrong about their own screen.
        progress = onboarding.steps_progress(_project(boundary=True))
        by_key = {s["key"]: s["done"] for s in progress}
        self.assertTrue(by_key["boundary"])
        self.assertFalse(by_key["pin"])
        # …and the next thing to do is still the pin.
        self.assertEqual(onboarding.first_step(_project(boundary=True))["key"],
                         "pin")

    def test_every_step_has_a_short_label_for_the_chip(self):
        # The strip clips without these; the guard is cheap.
        for step in onboarding.STEPS:
            self.assertTrue(step.get("short"), step)
            self.assertLess(len(step["short"]), len(step["title"]) + 6, step)

    def test_first_step_line_is_plain_text(self):
        line = onboarding.first_step_line(_project())
        self.assertIn("Step 1 of 3", line)
        self.assertNotIn("<", line)

    def test_missing_site_config_is_not_a_crash(self):
        self.assertEqual(onboarding.first_step({})["key"], "pin")
        self.assertEqual(onboarding.first_step({"features": None})["key"], "pin")


class TestGenerateDefaults(unittest.TestCase):

    def test_first_run_goals_are_real_goal_keys(self):
        from src.design_goals import GOALS
        keys = {g.key for g in GOALS}
        for key in onboarding.FIRST_RUN_GOALS:
            self.assertIn(key, keys, f"{key} is not a real design goal")

    def test_defaults_are_a_beginner_set_not_everything(self):
        from src.design_goals import GOALS
        self.assertLess(len(onboarding.FIRST_RUN_GOALS), len(GOALS))
        # The two that keep a first design from disappointing: it stays in its
        # bed, and it can actually be bought.
        self.assertIn("well_behaved", onboarding.FIRST_RUN_GOALS)
        self.assertIn("low_cost", onboarding.FIRST_RUN_GOALS)


class TestExampleGeometry(unittest.TestCase):

    def test_boundary_ring_is_closed_and_the_right_size(self):
        from src.projection import metres_per_deg
        lat, lng = 53.5, -113.5
        ring = onboarding.example_boundary_ring(lat, lng)
        self.assertEqual(ring[0], ring[-1], "ring must close")
        self.assertEqual(len(ring), 5)
        m_lat, m_lng = metres_per_deg(lat)
        width = abs(ring[1][0] - ring[0][0]) * m_lng
        depth = abs(ring[2][1] - ring[1][1]) * m_lat
        self.assertAlmostEqual(width, onboarding.EXAMPLE_WIDTH_M, delta=0.1)
        self.assertAlmostEqual(depth, onboarding.EXAMPLE_DEPTH_M, delta=0.1)

    def test_ring_is_lng_lat_order(self):
        # GeoJSON order — the classic trap in this codebase.
        ring = onboarding.example_boundary_ring(53.5, -113.5)
        for lng, lat in ring:
            self.assertLess(lng, 0.0)
            self.assertGreater(lat, 0.0)


class TestExampleResolution(unittest.TestCase):

    def test_resolves_against_the_catalogue_it_is_given(self):
        wanted = {c[0] for c, _ in onboarding.EXAMPLE_PLANTING}
        placements, missing = onboarding.resolve_example_planting(
            _fake_lookup(wanted))
        self.assertEqual(missing, [])
        self.assertEqual(len(placements), len(onboarding.EXAMPLE_PLANTING))

    def test_falls_back_to_the_next_candidate(self):
        # Golden Bean is authored with Purple Prairie Clover as its fallback.
        known = {c[0] for c, _ in onboarding.EXAMPLE_PLANTING} - {"Golden Bean"}
        known.add("Purple Prairie Clover")
        placements, missing = onboarding.resolve_example_planting(
            _fake_lookup(known))
        self.assertEqual(missing, [])
        self.assertNotIn("Golden Bean", {p["common_name"] for p in placements})

    def test_unresolvable_entries_are_reported_not_swallowed(self):
        placements, missing = onboarding.resolve_example_planting(
            _fake_lookup(set()))
        self.assertEqual(placements, [])
        self.assertEqual(len(missing), len(onboarding.EXAMPLE_PLANTING))

    def test_every_authored_name_resolves_against_the_real_catalogue(self):
        # The point of authoring names instead of ids: this test tells us the
        # day a seed-data change breaks the example, instead of a user finding
        # a thin design.
        from src.db.plants import init_db
        init_db()
        _placements, missing = onboarding.resolve_example_planting()
        self.assertEqual(
            missing, [],
            f"example species not in the shipped catalogue: {missing}")


class TestExampleProject(unittest.TestCase):

    def _build(self):
        wanted = {c[0] for c, _ in onboarding.EXAMPLE_PLANTING}
        return onboarding.build_example_project(
            53.5, -113.5, lookup=_fake_lookup(wanted))

    def test_has_a_boundary_a_pin_and_plants(self):
        project, missing = self._build()
        self.assertEqual(missing, [])
        kinds = [f["properties"]["element_type"] for f in project["features"]]
        self.assertEqual(kinds.count("property_boundary"), 1)
        self.assertEqual(kinds.count("plant"),
                         len(onboarding.EXAMPLE_PLANTING))
        sc = project["properties"]["site_config"]
        self.assertAlmostEqual(sc["latitude"], 53.5, places=4)

    def test_it_completes_every_getting_started_step(self):
        # The example is the "show me a finished one" door: it must not open
        # onto a screen that still nags about step 1.
        project, _ = self._build()
        self.assertTrue(onboarding.first_step(project)["complete"])

    def test_placed_plants_go_through_the_store(self):
        from src.project_store import ProjectStore
        project, _ = self._build()
        store = ProjectStore(project)
        self.assertEqual(store.check_consistency(), [])
        self.assertEqual(len(store.placed_plants),
                         len(onboarding.EXAMPLE_PLANTING))

    def test_plants_land_inside_the_boundary(self):
        project, _ = self._build()
        ring = next(f for f in project["features"]
                    if f["properties"]["element_type"]
                    == "property_boundary")["geometry"]["coordinates"][0]
        lngs = [p[0] for p in ring]
        lats = [p[1] for p in ring]
        for f in project["features"]:
            if f["properties"]["element_type"] != "plant":
                continue
            lng, lat = f["geometry"]["coordinates"]
            self.assertTrue(min(lngs) <= lng <= max(lngs), f)
            self.assertTrue(min(lats) <= lat <= max(lats), f)

    def test_defaults_to_alberta_when_given_no_position(self):
        wanted = {c[0] for c, _ in onboarding.EXAMPLE_PLANTING}
        project, _ = onboarding.build_example_project(
            lookup=_fake_lookup(wanted))
        sc = project["properties"]["site_config"]
        self.assertAlmostEqual(sc["latitude"],
                               onboarding.EXAMPLE_DEFAULT_LATLNG[0], places=4)

    def test_the_example_carries_its_own_priorities(self):
        project, _ = self._build()
        self.assertEqual(
            project["properties"]["site_config"]["priorities"],
            list(onboarding.FIRST_RUN_GOALS))


# ── Widgets ──────────────────────────────────────────────────────────────────

def _qt_available():
    try:
        from PyQt6.QtWidgets import QApplication  # noqa: F401
        return True
    except Exception:                                # pragma: no cover
        return False


@unittest.skipUnless(_qt_available(), "PyQt6 not installed in this env")
class TestFirstStepBar(unittest.TestCase):
    """The strip renders what the core computed, and its chips are controls."""

    @classmethod
    def setUpClass(cls):
        from PyQt6.QtWidgets import QApplication
        cls._app = QApplication.instance() or QApplication(["tests"])

    def _bar(self):
        from src.first_step_bar import FirstStepBar
        return FirstStepBar()

    def _render(self, bar, project):
        bar.set_progress(onboarding.steps_progress(project),
                         onboarding.first_step(project))

    def test_chips_show_short_labels_and_mark_the_live_step(self):
        bar = self._bar()
        self._render(bar, _project())
        self.assertIn("Drop a pin", bar._chips[0].text())
        self.assertIn("1.", bar._chips[0].text())

    def test_done_steps_are_ticked(self):
        bar = self._bar()
        self._render(bar, _project(pin=True))
        self.assertIn("✓", bar._chips[0].text())
        self.assertNotIn("✓", bar._chips[1].text())

    def test_chip_click_emits_its_own_key_after_a_rerender(self):
        # The chips are rebound on every refresh; a stale lambda would send
        # the wrong key, which is the kind of bug that only shows up in use.
        bar = self._bar()
        got = []
        bar.step_clicked.connect(got.append)
        self._render(bar, _project())
        self._render(bar, _project(pin=True, boundary=True))
        bar._chips[2].click()
        self.assertEqual(got, ["plants"])

    def test_detail_is_elided_not_clipped(self):
        bar = self._bar()
        bar.resize(300, 30)
        self._render(bar, _project())
        shown = bar._detail.text()
        full = onboarding.first_step(_project())["detail"]
        self.assertNotEqual(shown, full)
        self.assertEqual(bar._detail.toolTip(), full,
                         "the full sentence must survive as a tooltip")


@unittest.skipUnless(_qt_available(), "PyQt6 not installed in this env")
class TestStartScreen(unittest.TestCase):
    """V2.41 — ``welcome_dialog.py`` became ``start_screen.py``. One start
    surface, not two, so the Help menu and the launch path cannot drift."""

    @classmethod
    def setUpClass(cls):
        from PyQt6.QtWidgets import QApplication
        cls._app = QApplication.instance() or QApplication(["tests"])

    def test_offers_the_three_doors(self):
        from src.start_screen import DIRECTORY, NEW, OPEN, _DOORS
        self.assertEqual([d[0] for d in _DOORS], [NEW, OPEN, DIRECTORY])

    def test_choice_is_empty_until_picked(self):
        from src.start_screen import DIRECTORY, StartScreen
        screen = StartScreen()
        self.assertEqual(screen.choice(), "")
        screen._pick(DIRECTORY)
        self.assertEqual(screen.choice(), DIRECTORY)


class TestWiringContract(unittest.TestCase):
    """Static guard on the app.py ↔ flow-module seam.

    None of this fails at import time — a missing refresh call just means the
    strip quietly stops updating, which is exactly the class of bug that only
    shows up in use. Read as text so it runs without Qt.
    """

    @staticmethod
    def _src(rel):
        from pathlib import Path
        return (Path(__file__).resolve().parent.parent / rel
                ).read_text(encoding="utf-8")

    def test_app_wires_every_strip_signal(self):
        app = self._src("src/app.py")
        for sig in ("generate_requested", "step_clicked", "dismissed"):
            self.assertIn(f"first_step_bar.{sig}.connect", app,
                          f"the strip's {sig} signal is never connected")

    def test_guidance_is_refreshed_on_every_path_that_changes_state(self):
        # _mark_modified covers mutations; load and new bypass it (they reset
        # the modified flag), so each needs its own call.
        self.assertIn("onboarding_flow.refresh",
                      self._src("src/controllers/persistence.py"))
        app = self._src("src/app.py")
        self.assertGreaterEqual(
            app.count("onboarding_flow.refresh(self)"), 3,
            "expected refresh on construction, on load, and on new project")

    def test_generate_is_reachable_without_opening_a_menu(self):
        # F44's point stands — the easiest path out of a blank map must not be
        # menu-only — but the surface changed: the permanent Draw-toolbar
        # button was removed (a once-per-project action does not belong among
        # the drawing tools), leaving the getting-started strip, which shows
        # exactly while a user still needs it and then retires itself.
        self.assertIn("generate_requested", self._src("src/first_step_bar.py"))
        self.assertIn("first_step_bar.generate_requested.connect",
                      self._src("src/app.py"))

    def test_generate_is_not_on_the_draw_toolbar(self):
        # Removing it is the point; a future "promote it back" would silently
        # undo a deliberate decision, so pin it.
        toolbar = self._src("src/toolbar.py")
        self.assertNotIn("generate_requested", toolbar)
        self.assertNotIn("Generate Design\"", toolbar)
        self.assertNotIn("toolbar.generate_requested.connect",
                         self._src("src/app.py"))

    def test_both_generate_actions_are_disabled_together(self):
        gen = self._src("src/controllers/generation.py")
        self.assertEqual(gen.count("set_generate_enabled"), 2,
                         "the strip's button must grey out with the menu "
                         "action while a run is in flight")

    def test_flow_exposes_what_app_and_menus_call(self):
        from src import onboarding_flow
        for name in ("refresh", "choose_start_action", "act_on_start_choice",
                     "show_welcome", "open_example", "on_step_clicked",
                     "set_step_bar_hidden", "step_bar_hidden", "example_path"):
            self.assertTrue(hasattr(onboarding_flow, name), name)

    def test_no_new_mainwindow_methods(self):
        # F44 is a flow module precisely so it costs none; if this creeps, the
        # architecture guard's ceiling stops being the backstop it should be.
        import ast
        tree = ast.parse(self._src("src/app.py"))
        cls = next(n for n in tree.body
                   if isinstance(n, ast.ClassDef) and n.name == "MainWindow")
        n = len([m for m in cls.body if isinstance(m, ast.FunctionDef)])
        self.assertLessEqual(n, 140)


if __name__ == "__main__":
    unittest.main()

"""
The shared 3D toolbar, the edit animations, the net, and split view (V2.44).

Author's report, in four parts:

* *"The walk a wild landscape should be as close in terms of controls to the 3D
  preview walk the landscape mode."*
* *"I'd like the animations for planting a tree/plant, removing one, catching a
  critter."*
* *"the split screen 3D and map mode so you can edit the design in more ways
  than one."*

Walk mode itself was never the problem — ``html/scene3d/08-modes.js`` is one
file driving both windows. The problem was two hand-rolled Qt toolbars over it,
which could only diverge. The parity test below is what stops that happening
again, and it is the test in this file worth keeping if the others go.
"""

from __future__ import annotations

import ast
import pathlib
import unittest

try:
    # QtWebEngineWidgets MUST be imported before any QApplication exists, or
    # Qt raises "AA_ShareOpenGLContexts must be set before a QCoreApplication
    # instance is created". Importing it up here — not inside a test — is what
    # lets this module run on its own as well as inside the whole suite.
    from PyQt6.QtWebEngineWidgets import QWebEngineView    # noqa: F401
    from PyQt6.QtWidgets import QApplication, QPushButton
    _HAVE_QT = True
    _HAVE_WEBENGINE = True
except ImportError:                                        # pragma: no cover
    try:
        from PyQt6.QtWidgets import QApplication, QPushButton
        _HAVE_QT = True
    except ImportError:
        _HAVE_QT = False
    _HAVE_WEBENGINE = False

_ROOT = pathlib.Path(__file__).resolve().parent.parent


def _read(*parts) -> str:
    return (_ROOT.joinpath(*parts)).read_text(encoding="utf-8")


# ── The toolbar ──────────────────────────────────────────────────────────────

class TestTheTwoWindowsCannotDrift(unittest.TestCase):
    """Qt-free: the constants and the wiring, read as text."""

    def test_the_numbers_have_exactly_one_home(self):
        """MAX_YEAR / DETAIL_LABELS / DETAIL_KEY were duplicated between the
        two windows. A second copy of "the timeline runs to 25" is a second
        answer to it within a release or two."""
        window = _read("src", "scene3d_window.py")
        self.assertIn("from src.scene3d_toolbar import", window)
        for name in ("_MAX_YEAR = 25", '_DETAIL_KEY = "viewer3d/detail"'):
            self.assertNotIn(name, window,
                             "scene3d_window re-declares a shared constant")

    def test_both_windows_agree_on_the_stored_detail_key(self):
        from src import scene3d_toolbar, scene3d_window
        self.assertEqual(scene3d_window._DETAIL_KEY, scene3d_toolbar.DETAIL_KEY)
        self.assertEqual(scene3d_window._MAX_YEAR, scene3d_toolbar.MAX_YEAR)
        self.assertEqual(scene3d_window._DETAIL_LABELS,
                         scene3d_toolbar.DETAIL_LABELS)

    def test_the_sandbox_offers_the_same_viewer_controls(self):
        """The parity the author asked for, checked as *capability* rather
        than pixel layout: every viewer control the 3D preview has, the
        reference window can also reach."""
        ref = _read("src", "reference_ecosystem_window.py")
        for wiring in ("time_changed", "detail_changed", "reset_view",
                       "walk_toggled", "identify_toggled"):
            self.assertIn(wiring, ref,
                          f"the sandbox does not wire {wiring}")

    def test_walk_mode_is_no_longer_forced_on(self):
        """It used to re-enter walk mode on every scene rebuild — so the user
        was put back on their feet after every single plant, with no control
        that could say otherwise."""
        ref = _read("src", "reference_ecosystem_window.py")
        # Code, not prose: the comment above the fixed line quotes the old call
        # to explain it, and a raw substring search matches that too.
        code = "\n".join(ln for ln in ref.splitlines()
                         if not ln.lstrip().startswith("#"))
        self.assertNotIn("set_walk_mode(True)", code,
                         "walk mode is being forced on again")
        self.assertIn("set_walk_mode(self.toolbar.is_walking())", code)


@unittest.skipUnless(_HAVE_QT, "PyQt6 not installed in this env")
class TestTheToolbarWidget(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls._app = QApplication.instance() or QApplication(["tests"])

    def test_it_reports_what_the_user_set(self):
        from src.scene3d_toolbar import Scene3DToolBar
        tb = Scene3DToolBar(year=12)
        self.assertEqual(tb.year(), 12)
        tb.set_year(20)
        self.assertEqual(tb.year(), 20)

    def test_moving_a_time_slider_asks_for_one_rebuild(self):
        """Three sliders, one `time_changed` — three separate connections to
        one handler is three chances to forget one."""
        from src.scene3d_toolbar import Scene3DToolBar
        tb = Scene3DToolBar()
        seen = []
        tb.time_changed.connect(lambda: seen.append(1))
        tb.set_year(7)
        tb.set_month(9)
        self.assertEqual(len(seen), 2)

    def test_walk_can_be_turned_off(self):
        """The actual gap: the sandbox had no way out of walk mode."""
        from src.scene3d_toolbar import Scene3DToolBar
        tb = Scene3DToolBar()
        states = []
        tb.walk_toggled.connect(states.append)
        btn = next(b for b in tb.findChildren(QPushButton) if "Walk" in b.text())
        btn.click()
        btn.click()
        self.assertEqual(states, [True, False])

    def test_set_walking_does_not_re_emit(self):
        """A window that enters walk mode itself needs the button to agree
        without firing the handler that put it there."""
        from src.scene3d_toolbar import Scene3DToolBar
        tb = Scene3DToolBar()
        fired = []
        tb.walk_toggled.connect(fired.append)
        tb.set_walking(True)
        self.assertTrue(tb.is_walking())
        self.assertEqual(fired, [])

    def test_a_window_can_ask_for_less_without_a_second_implementation(self):
        """`groups=` is what lets the Learn side be simpler than the Design
        side while staying one widget."""
        from src.scene3d_toolbar import Scene3DToolBar
        tb = Scene3DToolBar(groups=("view",))
        self.assertEqual(tb.year(), 0)          # no slider, honest default
        self.assertEqual(tb.detail(), tb.stored_detail())
        self.assertFalse(any("Detail" in b.text()
                             for b in tb.findChildren(QPushButton)))


# ── The animations ───────────────────────────────────────────────────────────

class TestTheEditAnimations(unittest.TestCase):
    """Read as text — three.js tweens need a GPU and a real frame clock."""

    def _anim(self) -> str:
        return _read("html", "scene3d", "17-anim.js")

    def test_the_chunk_is_loaded_and_stepped(self):
        html = _read("html", "scene3d.html")
        self.assertIn("'scene3d/17-anim.js',", html)
        modes = _read("html", "scene3d", "08-modes.js")
        self.assertIn("stepTweens(t)", modes)
        # Same forward-reference guard stepThreads uses: this chunk loads after
        # the render loop is already running.
        self.assertIn("typeof stepTweens === 'function'", modes)

    def test_all_three_animations_exist(self):
        js = self._anim()
        for fn in ("function animatePlant", "function animatePull",
                   "function animateCatch"):
            self.assertIn(fn, js)

    def test_the_edit_happens_after_the_animation_not_before(self):
        """THE ordering contract. Every edit ends in a full scene rebuild,
        which destroys an animation already in flight — so the bridge call is
        the animation's completion callback, not the click handler's body."""
        editing = _read("html", "scene3d", "16-editing.js")
        for call in ("animatePlant(pt.x, pt.y, send)",
                     "animatePull(inst, send)",
                     "animateCatch(critter, send)"):
            self.assertIn(call, editing,
                          "an edit is not being animated before it is sent")

    def test_every_path_still_performs_the_edit(self):
        """These tweens own the user's action, not just its decoration. A
        missing animation must degrade to an instant edit, never to no edit."""
        editing = _read("html", "scene3d", "16-editing.js")
        self.assertEqual(editing.count("else send();"), 3,
                         "an animation path can swallow the edit")

    def test_pulling_animates_the_instance_that_was_clicked(self):
        """scenePick returns the plant *id*, which several instances of a
        species share; pulling has to move exactly the one under the cursor."""
        js = self._anim()
        self.assertIn("function pickInstance", js)
        self.assertIn("h.instanceId", js)
        self.assertIn("instanceMatrix.needsUpdate", js)

    def test_a_caught_creature_is_released(self):
        """P11, and the only version of a catching mechanic that does not
        teach a child to remove pollinators from a habitat."""
        js = self._anim()
        self.assertIn("critter.scale.copy(s0)", js)


class TestTheNet(unittest.TestCase):

    def test_caught_is_a_different_claim_from_seen(self):
        from src.map3d_widget import Scene3DBridge
        self.assertTrue(callable(getattr(Scene3DBridge, "caught", None)))
        self.assertIn("species_caught", dir(Scene3DBridge))

    def test_the_ledger_records_it_as_caught(self):
        src = _read("src", "reference_edit_flow.py")
        fn = next(n for n in ast.walk(ast.parse(src))
                  if isinstance(n, ast.FunctionDef) and n.name == "on_caught")
        self.assertIn("HOW_CAUGHT", ast.dump(fn))

    def test_the_viewer_knows_the_verb(self):
        editing = _read("html", "scene3d", "16-editing.js")
        self.assertIn("'net'", editing)
        self.assertIn("bridge.caught(", editing)


# ── Split view ───────────────────────────────────────────────────────────────

class TestSplitView(unittest.TestCase):

    def test_it_costs_mainwindow_no_methods(self):
        """A controller shim, like persistence and map_events — the method
        ceiling is meaningful and 126/140 is not much headroom."""
        app = _read("src", "app.py")
        self.assertIn("_split_view.toggle(self, checked)", app)
        self.assertNotIn("def _on_toggle_split", app)

    def test_the_map_is_kept_in_step_from_one_place(self):
        """Every feature mutation in the app lands in _mark_modified. Wiring
        this per call site would miss one within a release."""
        persistence = _read("src", "controllers", "persistence.py")
        fn = next(n for n in ast.walk(ast.parse(persistence))
                  if isinstance(n, ast.FunctionDef)
                  and n.name == "_mark_modified")
        self.assertIn("request_sync", ast.dump(fn))

    def test_syncing_is_debounced(self):
        """Dragging a plant fires an update per mouse-move, and build_scene
        walks every feature while the viewer rebuilds every instanced mesh."""
        src = _read("src", "controllers", "split_view.py")
        self.assertIn("QTimer", src)
        self.assertIn("setSingleShot(True)", src)

    def test_request_sync_is_safe_when_the_split_is_closed(self):
        """Callers must never have to ask first."""
        from src.controllers import split_view

        class _Bare:
            pass
        split_view.request_sync(_Bare())          # must not raise

    def test_the_pane_is_lazy(self):
        """A second QWebEngineView is real memory and a real GPU context; a
        user who never opens the split must pay nothing."""
        from src.controllers import split_view

        class _Bare:
            pass
        ctl = split_view.controller(_Bare())
        self.assertFalse(ctl.active)
        self.assertIsNone(ctl.viewer)

    def test_it_closes_the_viewer_before_deleting_it(self):
        """close() before deleteLater(), or closeEvent never runs and the
        widget's workers are never stopped — the V2.40 'QThread destroyed while
        still running' abort, which surfaces in an unrelated later test."""
        src = _read("src", "controllers", "split_view.py")
        i_close = src.index("self.viewer.close()")
        i_delete = src.index("self.viewer.deleteLater()")
        self.assertLess(i_close, i_delete)

    def test_learn_mode_does_not_get_it(self):
        """Deliberate: a second view of the same place is exactly the
        complexity the Learn door exists to remove."""
        learn = _read("src", "learn_flow.py") + _read("src", "learn_menu.py")
        self.assertNotIn("split_view", learn)


@unittest.skipUnless(_HAVE_WEBENGINE, "PyQt6-WebEngine not installed")
class TestSplitViewReparenting(unittest.TestCase):
    """The one piece of this increment with real bugs available.

    Opening the split takes the map *out* of its column, puts it in a new
    vertical splitter, and puts the splitter back where the map was; closing
    undoes all of that. Get the order wrong and Qt takes the map down with the
    splitter's parent, leaving a working app with no map in it.

    A real ``Map3DWidget`` is a QWebEngineView, which is slow and needs a GPU,
    so it is stubbed — the geometry being tested is Qt layout surgery and does
    not care what the second pane contains.
    """

    @classmethod
    def setUpClass(cls):
        cls._app = QApplication.instance() or QApplication(["tests"])

    def _fake_main(self):
        from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget
        main = QWidget()
        col = QWidget(main)
        lay = QVBoxLayout(col)
        # Something above the map, like app.py's getting-started strip — so the
        # test would catch an index assumption that only works at position 0.
        lay.addWidget(QLabel("strip"))
        main.map_widget = QWidget(col)
        lay.addWidget(main.map_widget, 1)
        main._project = {"type": "FeatureCollection", "features": []}
        self._keep = (main, col)          # keep alive for the test's lifetime
        return main

    def _patched(self):
        """Stand in for Map3DWidget. A real one is a QWebEngineView — slow,
        GPU-hungry, and irrelevant: the geometry under test is Qt layout
        surgery and does not care what the second pane contains. The stub
        still answers the viewer API the controller uses, so a call that goes
        missing shows up here rather than at runtime."""
        from unittest import mock
        from PyQt6.QtWidgets import QWidget
        import src.map3d_widget

        class _StubViewer(QWidget):
            bridge = None

            def apply_scene(self, scene):
                self.scenes = getattr(self, "scenes", []) + [scene]

            def set_wildlife(self, creatures, summary=None):
                pass

        return mock.patch.object(src.map3d_widget, "Map3DWidget", _StubViewer)

    def test_opening_puts_the_map_in_a_splitter_and_keeps_it_visible(self):
        from PyQt6.QtWidgets import QSplitter
        from src.controllers import split_view
        main = self._fake_main()
        ctl = split_view.controller(main)
        with self._patched():
            ctl.toggle(True)
        self.assertTrue(ctl.active)
        self.assertIsInstance(main.map_widget.parentWidget(), QSplitter)
        # The strip is still above it — the map went back where it was, not to
        # the top of the column.
        col = self._keep[1]
        self.assertEqual(col.layout().count(), 2)

    def test_closing_gives_the_map_its_column_back(self):
        from src.controllers import split_view
        main = self._fake_main()
        ctl = split_view.controller(main)
        col = self._keep[1]
        with self._patched():
            ctl.toggle(True)
            ctl.toggle(False)
        self.assertFalse(ctl.active)
        self.assertIsNone(ctl.viewer)
        self.assertIs(main.map_widget.parentWidget(), col)
        self.assertEqual(col.layout().indexOf(main.map_widget), 1)

    def test_it_survives_being_opened_and_closed_repeatedly(self):
        """The reparenting is the kind of code that works once and leaks or
        crashes on the third round."""
        from src.controllers import split_view
        main = self._fake_main()
        ctl = split_view.controller(main)
        col = self._keep[1]
        with self._patched():
            for _ in range(3):
                ctl.toggle(True)
                ctl.toggle(False)
        self.assertIs(main.map_widget.parentWidget(), col)
        self.assertEqual(col.layout().count(), 2)

    def test_a_debounced_rebuild_that_lands_after_close_is_survivable(self):
        """The hazard the debounce creates: a sync requested during a drag can
        fire *after* the user closed the split, by which point the viewer is a
        half-torn-down C++ object. An exception escaping a Qt slot calls
        qFatal() — a process abort with no traceback, surfacing in whatever ran
        next. This app has been bitten by exactly that twice (V2.38, V2.40)."""
        from src.controllers import split_view
        main = self._fake_main()
        ctl = split_view.controller(main)
        with self._patched():
            ctl.toggle(True)
            ctl.request_sync()          # a drag lands...
            ctl.toggle(False)           # ...and the user closes the split
            ctl._rebuild_scene()        # the timer fires anyway
        self.assertFalse(ctl.active)

    def test_toggling_to_the_state_it_is_already_in_does_nothing(self):
        from src.controllers import split_view
        main = self._fake_main()
        ctl = split_view.controller(main)
        with self._patched():
            ctl.toggle(True)
            viewer = ctl.viewer
            ctl.toggle(True)
            self.assertIs(ctl.viewer, viewer, "the pane was rebuilt")
            ctl.toggle(False)
            ctl.toggle(False)
        self.assertFalse(ctl.active)


if __name__ == "__main__":
    unittest.main()

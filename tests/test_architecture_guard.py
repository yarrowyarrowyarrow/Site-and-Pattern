"""
tests/test_architecture_guard.py

Locks in the Chunk 4 + 5 decomposition (D2) and the Chunk 6 public-API
surface (D3) so they can't silently backslide.

Pure ast / inspect — no Qt, no DB.

--- D2: structural ceilings ---

The Chunk 5 decomposition used the SHIM pattern: each method extracted
to a controller left a one-line delegating shim on MainWindow, so the
public surface (signals, menu wiring, tests) kept working. That means
MainWindow's METHOD COUNT didn't drop — but its LINE COUNT did
(3,924 → ~2,250). So the meaningful regression signal here is line
count + a cap on fat-method regrowth, not the raw method count the
roadmap first sketched (50 methods / 1000 lines assumed a later
shim-removal cleanup that hasn't happened — and may never, since the
shims are cheap and keep Qt signal wiring stable).

Ceilings are set ~15% above the current state: enough headroom for
normal edits, tight enough that a multi-hundred-line blob landing back
in app.py or plant_panel.py — instead of in a controller / module —
trips the guard and prompts an extraction.

--- D3: agent API contract ---

Snapshots the names + signatures of the public scripting facade
(src.permadesign_api) and the MCP tool surface. A change here is a
breaking change for agents / scripts / the CLI, so it must be a
deliberate, reviewed edit to the EXPECTED_* maps below — never an
accident.
"""

import ast
import inspect
import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_SRC = Path(__file__).resolve().parent.parent / "src"


def _line_count(path: Path) -> int:
    with open(path, encoding="utf-8") as f:
        return sum(1 for _ in f)


def _method_count(path: Path, class_name: str) -> int:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            return sum(
                1 for n in node.body
                if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
            )
    raise AssertionError(f"class {class_name} not found in {path}")


class TestStructuralCeilings(unittest.TestCase):
    """D2 — keep the decomposed modules from regrowing."""

    # (path, ceiling) — current value in the comment.
    # V2.22 recalibration: ceilings exist to stop the NEXT monolith, so they
    # must cover today's biggest files, not only the ones that burned us in
    # V1.64. When one trips, the fix is extraction (a module/controller/
    # split script), never raising the number without a split plan.
    _HTML = _SRC.parent / "html"
    LINE_CEILINGS = [
        (_SRC / "app.py", 2600),                       # 2402 now
        # V2.41: 1600/1600 — NO headroom. The plant directory was built as its
        # own surface partly for this reason: a reference work's worth of
        # controls cannot land here. The next thing that needs a line from this
        # file must extract the placement/polyculture-mix half first, which is
        # roughly 55% of it and has wanted separating since Chunk 4.
        (_SRC / "plant_panel.py", 1600),               # 1600 now — AT CEILING
        # V1.81: @undoable on every feature + overlay-toggle handler (exhaustive
        # undo) and the wind/sun/sector/pin/shade undo wiring.
        # V2.22: headroom restored (was 2 lines!) — new handlers still belong
        # in flow modules; the terrain-queue block is the natural extraction
        # when this trips again.
        (_SRC / "controllers" / "map_events.py", 2100),# ~1903 now
        # V2.22: the three biggest panels, previously unguarded — each is
        # already past the size plant_panel.py was split at (Chunk 4).
        (_SRC / "polyculture_panel.py", 2900),         # ~2527 now
        (_SRC / "site_panel.py", 2700),                # ~2240 now
        (_SRC / "analysis_panel.py", 2450),            # ~2214 now
        # V2.41 — the plant directory (F90). Opted in on arrival rather than
        # when they first hurt: a ceiling added late is a ceiling set around
        # whatever shape the file drifted into.
        (_SRC / "plant_directory.py", 600),            # 489 now
        (_SRC / "plant_directory_window.py", 640),     # 518 now
        (_SRC / "start_screen.py", 380),               # 292 now
        (_SRC / "onboarding_flow.py", 620),            # ~551 now
        # V2.43 — Learn mode. Opted in on arrival, the V2.41 precedent: a
        # ceiling added late is a ceiling set around whatever shape the file
        # drifted into. learn_flow.py exists *because* this guard fired — the
        # Learn wiring took onboarding_flow.py to 646/620 and the honest fix
        # was the split it asks for, not a bigger number.
        (_SRC / "learn_flow.py", 260),                 # 129 now
        (_SRC / "learn_menu.py", 300),                 # 144 now
        (_SRC / "app_mode.py", 200),                   # 124 now
        (_SRC / "reference_edit.py", 340),             # 297 now
        (_SRC / "db" / "progress.py", 320),            # 275 now
        # V2.45: the wingbeat physics. Mostly derivation and sourcing notes —
        # the numbers are short and the reasoning is not, which is the right
        # ratio for a file whose job is to be argued with.
        (_SRC / "flight_model.py", 620),               # 519 now
        # V2.46c: opted in on arrival at 907/980, the V2.41 precedent. This
        # file does two separable jobs — deciding WHICH animals are in a scene
        # and where (the placement half, wildlife_for_scene + _relax_spacing)
        # and deciding what each one LOOKS like and how big it is (the
        # appearance half, _appearance_for / _size_for / _flight_for). That is
        # the seam when this trips; do not raise the number.
        (_SRC / "scene_wildlife.py", 980),             # 907 now
        # V2.43: the reference window went from a read-only diorama (163
        # lines) to an editable sandbox. When this trips, the split is the
        # edit half — the bridge slots and the trowel — into its own _flow.
        (_SRC / "reference_ecosystem_window.py", 450),  # 414 now
        # V2.44: the edit half, extracted when the toolbar and the net took the
        # window past 450. The ceiling comment above had named this exact seam
        # in advance, which is the guard working as intended.
        (_SRC / "reference_edit_flow.py", 260),        # 142 now
        (_SRC / "scene3d_toolbar.py", 340),            # 259 now
        (_SRC / "controllers" / "split_view.py", 320),  # 253 now
        # V2.46: plant / remove / net in the *design*, not just the sandbox.
        # A separate module from reference_edit_flow on purpose — a design edit
        # goes on the undo stack, redraws the map and moves the score, and
        # collapsing the two would mean one of those happening quietly in the
        # wrong place. When this trips, the seam is the widget half
        # (build_tools/set_mode) away from the bridge handlers.
        (_SRC / "scene3d_edit_flow.py", 400),          # 312 now
        # V2.46: opted in on arrival, like learn_flow.py before it. This file
        # hand-rolls the toolbar the V2.44 extraction was meant to share (the
        # note at the import explains why that swap was deferred), so the
        # ceiling is set where it is to make the next growth pay for it.
        (_SRC / "scene3d_window.py", 950),             # 911 now
        # V1.64: the former 4,900-line map.html monolith — keep the shell
        # thin and the split files from regrowing into a new monolith.
        (_HTML / "map.html", 400),                     # ~235 now
        (_HTML / "map" / "01-core.js", 950),           # ~885 now
        (_HTML / "map" / "02-boundary.js", 750),       # ~623 now
        (_HTML / "map" / "03-plants.js", 950),         # ~931 now
        (_HTML / "map" / "04-tools.js", 450),          # ~367 now
        # V2.26: +editable existing features (drag + scroll-resize of detected/
        # marked trees & buildings) — in-domain growth for the features file,
        # kept together to avoid the cross-chunk load-order traps a split adds.
        (_HTML / "map" / "05-features.js", 1200),      # ~1120 now
        # V2.13: + water flow & accumulation overlay (raster + arrow lattice).
        (_HTML / "map" / "06-overlays.js", 1560),      # ~1490 now
        # V2.31 (F5): the relationship-web overlay went into its own chunk
        # rather than onto 06-overlays.js, which was already the biggest of
        # the six. Geometry stays in src/relationship_graph.py — if this file
        # grows past its ceiling the cause is almost certainly ecology logic
        # that belongs in Python.
        (_HTML / "map" / "07-network.js", 400),        # ~200 now
        # V2.24: scene3d.html was a single ~4,200-line <script> — the exact
        # monolith shape the V1.64 split killed. It is now the HTML shell + a
        # bootstrap module; the viewer lives in html/scene3d/*.js loaded in
        # order (shared-global classic scripts like html/map/*.js). Keep each
        # chunk under its own ceiling; the fix when one trips is a further split,
        # not a bigger number.
        (_HTML / "scene3d.html", 400),                 # 391 now — 9 LEFT
        (_HTML / "scene3d" / "01-core.js", 700),       # ~531 now
        # V2.33 (F63): plantMaterial + the procedural surfaces moved OUT of
        # 02-plants.js into their own chunk. 02-plants was at 626/700 and both
        # the surface work and the real-wind work land in the same function, so
        # the fix was the split the ceiling asks for rather than a bigger number.
        (_HTML / "scene3d" / "01b-surface.js", 550),   # ~403 now
        (_HTML / "scene3d" / "02-plants.js", 700),     # ~468 now
        (_HTML / "scene3d" / "03-herbs.js", 700),      # ~431 now
        (_HTML / "scene3d" / "04-quality.js", 900),    # ~629 now
        (_HTML / "scene3d" / "05-flowers.js", 800),    # ~565 now
        (_HTML / "scene3d" / "06-fly.js", 950),        # ~732 now
        (_HTML / "scene3d" / "07-wildlife.js", 800),   # ~550 now
        (_HTML / "scene3d" / "08-modes.js", 600),      # ~496 now
        # V2.46b: the walker's body and his held net, extracted when the net
        # took 08-modes.js to 625/600. The seam was chosen for load order as
        # much as for size: nothing in here is called from the animation
        # loop, which is what the 19-roster.js split got wrong.
        (_HTML / "scene3d" / "20-walker.js", 400),     # ~159 now
        # V2.27: Blender GLB model assets — manifest fetch + GLTF part
        # extraction + fauna clone/tint. When this trips, split the fauna
        # half into 10-models-fauna.js.
        (_HTML / "scene3d" / "09-models.js", 650),     # ~453 now
        (_HTML / "scene3d" / "10-inspect.js", 600),    # ~526 now
        # V2.33: 11-fruit.js shipped in V2.29 and was never added here, so the
        # newest viewer chunk was the only unguarded one.
        (_HTML / "scene3d" / "11-fruit.js", 600),      # ~231 now
        # V2.33 (F66): the eight graminoid seed-head drawings took
        # 05-flowers.js to 799 of its 800, so they went into their own chunk —
        # the split this ceiling asks for rather than a bigger number.
        (_HTML / "scene3d" / "12-seedheads.js", 400),  # ~125 now
        # V2.34: the Stylised body builders. 04-quality.js was at 885 of its 900
        # and this is a self-contained second look, not more of the first one.
        (_HTML / "scene3d" / "13-stylised.js", 400),   # ~115 now
        # V2.34: the four procedural layer tufts, moved out of
        # 04-quality.js when the Stylised switch took it past 900.
        (_HTML / "scene3d" / "14-layers.js", 400),     # ~101 now
        # V2.34: the bloom as geometry — florets, discs and the nine
        # inflorescence architectures. 05-flowers.js was at 737 of its
        # 800 and this is a different thing from a canvas drawing.
        (_HTML / "scene3d" / "15-florets.js", 500),    # ~429 now
        # V2.43: click-to-plant + the viewer's first QWebChannel. Geometry in,
        # coordinates out — if this file grows past its ceiling the cause is
        # almost certainly placement logic that belongs in
        # src/reference_edit.py, where the single write path is.
        (_HTML / "scene3d" / "16-editing.js", 300),    # 206 now
        # V2.44: the tween registry and the plant/pull/catch animations. If
        # this outgrows its ceiling the cause is almost certainly a fourth
        # animation that wants its own chunk, not a bigger number here.
        (_HTML / "scene3d" / "17-anim.js", 340),       # 239 now
        # V2.45: the flight model's viewer half — real hertz, the bout
        # envelope, and the body offset that comes out of it. The physics and
        # every number live in src/flight_model.py; if this file grows past its
        # ceiling the cause is almost certainly allometry that belongs there.
        (_HTML / "scene3d" / "18-flight.js", 300),     # 168 now
        # V2.46: the roster, the always-on labels and the "show its plants"
        # spotlight — split out of 07-wildlife.js when life-size scaling and
        # creature collision took it to 852 of its 800. The line the split
        # follows: 07 is the animals, 19 is how they are explained to a person.
        (_HTML / "scene3d" / "19-roster.js", 300),     # 177 now
    ]

    def test_module_line_ceilings(self):
        offenders = []
        for path, ceiling in self.LINE_CEILINGS:
            n = _line_count(path)
            if n > ceiling:
                offenders.append(
                    f"{path.relative_to(_SRC.parent)}: {n} lines > {ceiling} "
                    f"— extract logic into a module/controller instead of "
                    f"growing this file."
                )
        if offenders:
            self.fail("\n".join(offenders))

    def test_mainwindow_method_ceiling(self):
        # Shims keep the count ~stable; a jump means fat methods landed
        # back on MainWindow instead of in a controller. V2.22: reset from
        # 135 (which the class sat AT, forcing new wiring into lambdas) to
        # the post-updater-deletion count + real headroom — the ceiling
        # should catch regrowth, not ration every addition.
        n = _method_count(_SRC / "app.py", "MainWindow")
        self.assertLessEqual(
            n, 140,
            f"MainWindow has {n} methods (>140). New behaviour should go "
            f"in a controller/flow module, not as a fat method here.",
        )

    def test_controllers_still_exist(self):
        # The four Chunk 5 controllers must remain present + constructed.
        controllers = ["update_flow", "mode", "persistence", "map_events"]
        for name in controllers:
            self.assertTrue(
                (_SRC / "controllers" / f"{name}.py").exists(),
                f"controller src/controllers/{name}.py disappeared",
            )
        app_src = (_SRC / "app.py").read_text(encoding="utf-8")
        for ctor in ["UpdateFlowController(self)", "ModeController(self)",
                     "PersistenceController(self)", "MapEventRouter(self)"]:
            self.assertIn(
                ctor, app_src,
                f"MainWindow.__init__ no longer constructs {ctor}",
            )

    def test_plant_panel_split_modules_exist(self):
        # The Chunk 4 split must stay split.
        for name in ["plant_list_view", "on_this_design_panel"]:
            self.assertTrue(
                (_SRC / f"{name}.py").exists(),
                f"src/{name}.py (Chunk 4 split) disappeared",
            )


class TestUpdaterStaysNonDestructive(unittest.TestCase):
    """V2.22 deleted the updater's 'Discard & update' path (`git reset
    --hard` from a dialog box); V2.25 restored one-click updating WITHOUT
    it. Local changes may be stashed — recoverable by design — but the
    updater must never be able to destroy work."""

    # V2.29: version_branch.py joined the list. It is where the updater's git
    # commands actually live, and it gained a `git reset --merge` (to clear the
    # conflicted index a failed stash-pop leaves behind) — one keystroke from the
    # `--hard` this guard exists to keep out. `--merge` refuses rather than
    # clobbering unrelated local edits; `--hard` does not, which is the whole
    # difference and why only one of them is allowed.
    _FILES = [("controllers", "update_flow.py"), (None, "version_branch.py")]

    # Exact-match, not substring: both files legitimately *discuss* `reset
    # --hard` in prose (the module comment records that the path stays dead, and
    # abort_conflicted_state explains why it uses --merge instead). A git
    # argument is exactly the token; a sentence mentioning it never is. Banning
    # the substring would force the code to stop documenting its own history.
    _BANNED = {"--hard", "clean", "-f", "--force"}

    def _command_strings(self, src):
        """Every string literal the module could pass to a subprocess, i.e. all
        of them except docstrings."""
        tree = ast.parse(src)
        docstrings = set()
        for node in ast.walk(tree):
            if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef,
                                 ast.AsyncFunctionDef)):
                doc = ast.get_docstring(node, clean=False)
                if doc is not None:
                    docstrings.add(doc)
        return [n.value for n in ast.walk(tree)
                if isinstance(n, ast.Constant) and isinstance(n.value, str)
                and n.value not in docstrings]

    def test_no_destructive_git_in_the_update_path(self):
        for subdir, name in self._FILES:
            path = (_SRC / subdir / name) if subdir else (_SRC / name)
            for literal in self._command_strings(path.read_text(
                    encoding="utf-8")):
                self.assertNotIn(
                    literal.strip(), self._BANNED,
                    f"{name} passes {literal!r} to git — the one-click updater "
                    "must stay non-destructive (stash, never discard).")

    def test_both_update_paths_check_for_conflicts_first(self):
        """V2.29 — a field report: "Merging is not possible because you have
        unmerged files", from a checkout the updater itself had left conflicted.

        git refuses to merge, switch branches OR stash while the index holds
        unmerged entries, so an update attempted in that state cannot succeed,
        and the failure text pointed at `git pull --ff-only`, which fails
        identically. Both paths must therefore establish a clean index BEFORE
        touching the repo. AST-only — the flow needs Qt to run, and this is
        exactly the wiring a refactor drops silently.
        """
        tree = ast.parse((_SRC / "controllers" / "update_flow.py").read_text(
            encoding="utf-8"))
        found = {}
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef):
                continue
            if node.name not in ("_on_check_for_updates",
                                 "_perform_source_update"):
                continue
            found[node.name] = any(
                isinstance(c.func, ast.Attribute)
                and c.func.attr == "_clear_conflicts_if_any"
                for c in ast.walk(node) if isinstance(c, ast.Call))
        self.assertEqual(sorted(found), ["_on_check_for_updates",
                                         "_perform_source_update"],
                         "an update path went missing from update_flow.py")
        for name, checks in found.items():
            self.assertTrue(
                checks,
                f"{name} no longer calls _clear_conflicts_if_any — a checkout "
                "with unmerged files would strand the user again, with advice "
                "that fails the same way.")


class TestAnalysisPanelTabsRegistered(unittest.TestCase):
    """V1.54 — guard the regression where the 'Habitat Value' tab vanished:
    its ``addTab`` had slipped past a ``return`` in a sibling method, so the tab
    was never registered. AST-only (the panel needs Qt to instantiate).
    V2.25: also covers the Learn panel, which uses the same builder pattern."""

    # (file, class) pairs whose _build_*_tab methods must each call addTab.
    _PANELS = [("analysis_panel.py", "AnalysisPanel"),
               ("learn_panel.py", "LearnPanel")]

    def _func(self, class_name, method_name, filename="analysis_panel.py"):
        tree = ast.parse((_SRC / filename).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name == class_name:
                for n in node.body:
                    if isinstance(n, ast.FunctionDef) and n.name == method_name:
                        return n
        raise AssertionError(f"{class_name}.{method_name} not found")

    def _calls_addtab(self, node) -> bool:
        for n in ast.walk(node):
            if (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                    and n.func.attr == "addTab"):
                return True
        return False

    def _builders(self, filename):
        tree = ast.parse((_SRC / filename).read_text(encoding="utf-8"))
        return [n.name for n in ast.walk(tree)
                if isinstance(n, ast.FunctionDef)
                and n.name.startswith("_build_") and n.name.endswith("_tab")]

    def test_every_build_tab_registers_a_tab(self):
        # Each _build_*_tab must actually call self._tabs.addTab(...).
        self.assertIn("_build_habitat_tab", self._builders("analysis_panel.py"))
        self.assertIn("_build_field_study_tab",
                      self._builders("learn_panel.py"))
        for filename, class_name in self._PANELS:
            for name in self._builders(filename):
                fn = self._func(class_name, name, filename)
                self.assertTrue(
                    self._calls_addtab(fn),
                    f"{class_name}.{name} no longer calls addTab — its tab "
                    f"won't appear. Did an addTab slip past a return into "
                    f"another method?",
                )

    def test_set_shade_breakdown_has_no_dead_code_after_return(self):
        fn = self._func("AnalysisPanel", "set_shade_breakdown")
        # No addTab should live in the setter (that was the misplaced line),
        # and the setter must not register tabs.
        self.assertFalse(
            self._calls_addtab(fn),
            "set_shade_breakdown should not call addTab — the Habitat tab "
            "registration belongs at the end of _build_habitat_tab.",
        )


class TestAgentApiContract(unittest.TestCase):
    """D3 — freeze the public scripting + MCP surface."""

    # Public facade: function name → (positional/keyword param names).
    # Update DELIBERATELY when you intend an API change.
    EXPECTED_API_FUNCTIONS = {
        "query_plants": ["filters"],            # **filters
        "list_polycultures": ["top_level_only"],
        "list_structures": [],
        "run_analysis": ["project"],
        "pull_plant_impact": ["project", "plant_id"],   # F46 (V2.13)
        "chickadee_provision": ["project"],             # F47 (V2.13)
        "relationship_web": ["project", "kinds"],       # F5  (V2.31)
        "plant_relationships": ["plant_id"],            # F7  (V2.31)
        "phenology": ["project", "month"],              # F51 (V2.13)
        "lesson_track": ["project"],                    # F53 (V2.13)
        "reference_community": ["ecoregion"],           # F50 (V2.13)
        "docent_script": ["project"],                   # F52 (V2.13)
        "export_plant_catalogue_docx": ["out_path"],
    }

    EXPECTED_PROJECT_METHODS = {
        "create", "load", "save", "set_boundary", "place_plant",
        "place_polyculture", "place_structure", "as_dict", "validate",
        "analyze", "name", "placed_plants", "structures",
    }

    EXPECTED_MCP_TOOLS = {
        "query_plants", "list_communities", "list_structures",
        "create_project", "place_plant", "place_community",
        "place_structure", "analyze_project", "project_summary",
        "export_catalogue", "generate_design",
    }

    def test_facade_exports_stable(self):
        import src.permadesign_api as api
        for name in self.EXPECTED_API_FUNCTIONS:
            self.assertTrue(hasattr(api, name),
                            f"public API lost function {name}()")
        # __all__ should advertise exactly the intended surface.
        self.assertEqual(
            set(api.__all__),
            set(self.EXPECTED_API_FUNCTIONS) | {"Project"},
            "src.permadesign_api.__all__ changed — update the contract "
            "snapshot if this is intentional.",
        )

    def test_facade_function_params_stable(self):
        import src.permadesign_api as api
        for name, expected in self.EXPECTED_API_FUNCTIONS.items():
            sig = inspect.signature(getattr(api, name))
            params = list(sig.parameters)
            self.assertEqual(
                params, expected,
                f"{name}{sig} params changed; expected {expected}. Update "
                f"the contract snapshot deliberately if intended.",
            )

    def test_project_public_methods_stable(self):
        from src.permadesign_api import Project
        public = {n for n in dir(Project) if not n.startswith("_")}
        missing = self.EXPECTED_PROJECT_METHODS - public
        self.assertFalse(missing, f"Project lost public members: {missing}")

    def test_mcp_tool_surface_stable(self):
        import src.mcp_server as mcp
        names = {spec["name"] for spec in mcp.TOOL_SPECS}
        self.assertEqual(
            names, self.EXPECTED_MCP_TOOLS,
            "MCP tool surface changed — update EXPECTED_MCP_TOOLS "
            "deliberately if intended.",
        )


class TestTheTestSuiteCanReachItsOwnSummary(unittest.TestCase):
    """Guards against two ways a module has aborted the whole run rather than
    failing a test. Both cost hours to find, because the abort happens in a
    *later* module than the one at fault and prints no test name."""

    def test_no_module_builds_a_qapplication_with_an_empty_argv(self):
        """``QApplication([])`` leaves Chromium without an ``argv[0]``.

        Whichever module constructs the QApplication first decides this for the
        whole process, and the next ``QWebEngineView`` anywhere in the run dies
        with *"Argument list is empty, the program name is not passed to
        QCoreApplication"* — a process abort, in a module that did nothing
        wrong. Pass a name.
        """
        offenders = []
        for path in sorted(Path(__file__).resolve().parent.glob("test_*.py")):
            for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
                if (isinstance(node, ast.Call)
                        and isinstance(node.func, ast.Name)
                        and node.func.id == "QApplication"
                        and len(node.args) == 1
                        and isinstance(node.args[0], ast.List)
                        and not node.args[0].elts):
                    offenders.append(f"{path.name}:{node.lineno}")
        self.assertEqual(
            offenders, [],
            "QApplication([]) aborts any later QWebEngineView in the run — "
            'pass a program name, e.g. QApplication(["permadesign-tests"])')

    def test_every_window_teardown_closes_before_it_deletes(self):
        """A ``QThread`` destroyed while running is ``qFatal()``.

        Windows stop their workers in ``closeEvent``, so a teardown that calls
        ``deleteLater()`` without ``close()`` leaves live threads on the
        deferred-delete queue. Nothing happens until the next event loop runs —
        which is some unrelated later test opening a dialog, where the process
        aborts with ``QThread: Destroyed while thread '' is still running``.
        ``qt_safety.stop_threads`` is the alternative when a real ``close()``
        is not wanted.
        """
        offenders = []
        for path in sorted(Path(__file__).resolve().parent.glob("test_*.py")):
            lines = path.read_text(encoding="utf-8").splitlines()
            for i, line in enumerate(lines):
                if ".deleteLater()" not in line:
                    continue
                target = line.strip().split(".deleteLater")[0]
                window = "\n".join(lines[max(0, i - 6):i])
                if (f"{target}.close()" in window
                        or f"stop_threads({target})" in window):
                    continue
                # Dialogs and plain widgets own no workers; only the window
                # variables that might.
                if any(w in target for w in ("win", "w1", "_win", "main")):
                    offenders.append(f"{path.name}:{i + 1}  {line.strip()}")
        self.assertEqual(
            offenders, [],
            "deleteLater() on a window without close() or stop_threads() "
            "first — its workers outlive it and abort the run later")


if __name__ == "__main__":
    unittest.main()

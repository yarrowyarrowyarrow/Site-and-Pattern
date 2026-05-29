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
    LINE_CEILINGS = [
        (_SRC / "app.py", 2600),                       # ~2251 now
        (_SRC / "plant_panel.py", 1600),               # ~1390 now
        (_SRC / "controllers" / "map_events.py", 1700),# ~1438 now
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
        # back on MainWindow instead of in a controller.
        n = _method_count(_SRC / "app.py", "MainWindow")
        self.assertLessEqual(
            n, 135,
            f"MainWindow has {n} methods (>135). New behaviour should go "
            f"in a controller with a thin shim, not as a fat method here.",
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


class TestAgentApiContract(unittest.TestCase):
    """D3 — freeze the public scripting + MCP surface."""

    # Public facade: function name → (positional/keyword param names).
    # Update DELIBERATELY when you intend an API change.
    EXPECTED_API_FUNCTIONS = {
        "query_plants": ["filters"],            # **filters
        "list_polycultures": ["top_level_only"],
        "list_structures": [],
        "run_analysis": ["project"],
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


if __name__ == "__main__":
    unittest.main()

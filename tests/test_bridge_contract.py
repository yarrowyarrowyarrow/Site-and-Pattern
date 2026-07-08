"""
tests/test_bridge_contract.py — the OTHER half of the Python↔JS bridge
contract (V1.63).

tests/test_map_js.py already guards Python→JS (every function name the
map_js builders emit must be defined in html/map.html). This module
guards the remaining directions, which had no net under them:

  1. JS→Python: every ``bridge.<name>(`` call in html/map.html must
     resolve to a method on MapBridge — a renamed/removed slot otherwise
     fails silently inside the page at runtime.
  2. The 3D viewer hooks: every ``window.perma*`` hook the map3d_js
     builders emit must be registered by html/scene3d.html (the built-in
     viewer) — the && guards would otherwise silently no-op every push.

Static text + AST only — no Qt, no browser. This is the contract net
that makes a later map.html modularization safe to attempt: any split
that loses an entry point or a bridge call trips one of these suites.
"""

import ast
import os
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_ROOT = Path(__file__).resolve().parent.parent
_MAP_HTML = _ROOT / "html" / "map.html"
_SCENE_HTML = _ROOT / "html" / "scene3d.html"
_MAP_WIDGET = _ROOT / "src" / "map_widget.py"
_MAP3D_JS = _ROOT / "src" / "map3d_js.py"


def _mapbridge_methods() -> set:
    """Method names defined on MapBridge (AST — no Qt import needed)."""
    tree = ast.parse(_MAP_WIDGET.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == "MapBridge":
            return {n.name for n in node.body
                    if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
    raise AssertionError("MapBridge class not found in src/map_widget.py")


def _mapbridge_signals() -> set:
    """pyqtSignal attribute names on MapBridge (class-level assignments)."""
    tree = ast.parse(_MAP_WIDGET.read_text(encoding="utf-8"))
    out = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == "MapBridge":
            for stmt in node.body:
                if (isinstance(stmt, ast.Assign)
                        and isinstance(stmt.value, ast.Call)
                        and getattr(stmt.value.func, "id", "") == "pyqtSignal"):
                    for t in stmt.targets:
                        if isinstance(t, ast.Name):
                            out.add(t.id)
    return out


def _map_js_source() -> str:
    """map.html plus every html/map/*.js split file (V1.64) — the bridge
    calls can live in any of them."""
    out = _MAP_HTML.read_text(encoding="utf-8")
    for js in sorted((_MAP_HTML.parent / "map").glob("*.js")):
        out += "\n" + js.read_text(encoding="utf-8")
    return out


class TestJsToPythonBridge(unittest.TestCase):
    """Every bridge.<name>( call on the JS side resolves on MapBridge."""

    def test_all_bridge_calls_resolve(self):
        html = _map_js_source()
        called = set(re.findall(r"\bbridge\.(\w+)\s*\(", html))
        self.assertTrue(called, "the map JS makes no bridge calls — did "
                                "the QWebChannel wiring move?")
        known = _mapbridge_methods() | _mapbridge_signals()
        missing = sorted(c for c in called if c not in known)
        self.assertFalse(
            missing,
            "the map JS calls bridge methods that don't exist on "
            f"MapBridge (renamed slot?): {missing}")


class TestScene3DHooks(unittest.TestCase):
    """Every window.perma* hook the map3d_js builders emit is registered
    by the built-in viewer."""

    def test_builder_hooks_are_registered(self):
        builders_src = _MAP3D_JS.read_text(encoding="utf-8")
        hooks = set(re.findall(r"window\.(perma\w+)", builders_src))
        self.assertTrue(hooks)
        viewer = _SCENE_HTML.read_text(encoding="utf-8")
        missing = sorted(
            h for h in hooks
            if not re.search(rf"window\.{h}\s*=", viewer))
        self.assertFalse(
            missing,
            "html/scene3d.html never registers these hooks the Python "
            f"side pushes to (every push would silently no-op): {missing}")

    def test_reset_view_hook_registered(self):
        # Driven outside map3d_js (scene3d_window's "Reset view" button and the
        # sprite gallery both call it raw) — before V2.12 it was never defined,
        # so the button silently did nothing.
        viewer = _SCENE_HTML.read_text(encoding="utf-8")
        self.assertRegex(
            viewer, r"window\.permaResetView\s*=",
            "html/scene3d.html must register window.permaResetView — the 3D "
            "window's Reset-view button and the sprite gallery both call it")

    def test_viewer_does_not_register_unknown_hooks(self):
        # The reverse: a hook registered in the viewer but never driven
        # from Python is dead code or a naming drift.
        viewer = _SCENE_HTML.read_text(encoding="utf-8")
        registered = set(re.findall(r"window\.(permaSet\w+)\s*=", viewer))
        builders_src = _MAP3D_JS.read_text(encoding="utf-8")
        driven = set(re.findall(r"window\.(permaSet\w+)", builders_src))
        unknown = sorted(registered - driven)
        self.assertFalse(
            unknown,
            f"scene3d.html registers hooks nothing in map3d_js drives: "
            f"{unknown}")


if __name__ == "__main__":
    unittest.main()

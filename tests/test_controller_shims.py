"""
tests/test_controller_shims.py

Static guard for Chunk 5's controller-decomposition pattern: every
``self._<controller_attr>.<method>()`` call site inside ``src/app.py``
must resolve to a real method on the controller's class.

The Chunk 4 fallout (V1.40 → V1.40.1 patch) was caused by a moved name
that resolved at import time but crashed at runtime when a function body
finally executed. Chunk 5 introduces a sibling class of the same risk:
``MainWindow._on_check_for_updates`` is a one-line shim
``return self._update_flow._on_check_for_updates()`` and a typo in the
controller method name would fail only when the user triggered the
menu action.

This test:

  1. Reads ``src/app.py`` and finds every attribute defined in
     ``MainWindow.__init__`` whose value is a call to a class imported
     from ``src.controllers`` — that's the registry of (attr, class).
  2. For each ``self._<attr>.<method>(...)`` call in MainWindow, asserts
     ``<method>`` is defined on the controller class.

Pure ast, no PyQt6, no QApplication — runs unconditionally in CI.
"""

from __future__ import annotations

import ast
import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_SRC_DIR = Path(__file__).resolve().parent.parent / "src"


def _controller_classes_in(controllers_dir: Path) -> dict[str, set[str]]:
    """Map of ``ClassName -> {method_name, …}`` for every class defined in
    ``src/controllers/*.py`` (excluding ``__init__.py``)."""
    out: dict[str, set[str]] = {}
    for py in sorted(controllers_dir.glob("*.py")):
        if py.name == "__init__.py":
            continue
        tree = ast.parse(py.read_text(encoding="utf-8"))
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.ClassDef):
                out[node.name] = {
                    m.name for m in node.body
                    if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef))
                }
    return out


def _controller_imports_in(tree: ast.Module) -> set[str]:
    """Names imported from ``src.controllers.*`` at the top of the module."""
    names: set[str] = set()
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.ImportFrom) and (node.module or "").startswith(
                "src.controllers"):
            for alias in node.names:
                names.add(alias.asname or alias.name)
    return names


def _find_main_window(tree: ast.Module) -> ast.ClassDef | None:
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.ClassDef) and node.name == "MainWindow":
            return node
    return None


def _self_attr_to_controller_class(
    mw: ast.ClassDef, controller_names: set[str],
) -> dict[str, str]:
    """Find every ``self.<attr> = <ControllerName>(self)`` inside
    ``MainWindow.__init__`` and return ``{attr: ControllerName}``."""
    out: dict[str, str] = {}
    init = None
    for node in mw.body:
        if isinstance(node, ast.FunctionDef) and node.name == "__init__":
            init = node
            break
    if init is None:
        return out
    for stmt in ast.walk(init):
        if not isinstance(stmt, ast.Assign):
            continue
        if not isinstance(stmt.value, ast.Call):
            continue
        called = stmt.value.func
        if not isinstance(called, ast.Name):
            continue
        if called.id not in controller_names:
            continue
        for target in stmt.targets:
            if (isinstance(target, ast.Attribute)
                    and isinstance(target.value, ast.Name)
                    and target.value.id == "self"):
                out[target.attr] = called.id
    return out


def _shim_calls(mw: ast.ClassDef, controller_attrs: set[str]) -> list[tuple[str, str, int]]:
    """Find every ``self.<controller_attr>.<method>`` Attribute chain in
    MainWindow's body. Returns a list of ``(controller_attr, method, lineno)``."""
    calls: list[tuple[str, str, int]] = []
    for node in ast.walk(mw):
        if (isinstance(node, ast.Attribute)
                and isinstance(node.value, ast.Attribute)
                and isinstance(node.value.value, ast.Name)
                and node.value.value.id == "self"
                and node.value.attr in controller_attrs):
            calls.append((node.value.attr, node.attr, node.lineno))
    return calls


class TestControllerShimsResolve(unittest.TestCase):

    def test_every_shim_resolves_to_a_real_controller_method(self):
        with open(_SRC_DIR / "app.py", encoding="utf-8") as f:
            app_tree = ast.parse(f.read())

        controller_methods = _controller_classes_in(_SRC_DIR / "controllers")
        # If the controllers directory is empty (pre-Chunk 5), there's
        # nothing to check — that's a pass, not a failure.
        if not controller_methods:
            self.skipTest("no controllers defined yet")

        imported = _controller_imports_in(app_tree)
        relevant = {n for n in imported if n in controller_methods}
        self.assertTrue(
            relevant,
            "src/app.py imports nothing from src.controllers — did the"
            " import path drift?",
        )

        mw = _find_main_window(app_tree)
        self.assertIsNotNone(mw, "MainWindow class not found in src/app.py")

        attr_to_cls = _self_attr_to_controller_class(mw, relevant)
        self.assertTrue(
            attr_to_cls,
            "MainWindow.__init__ never constructs any imported controller"
            " — extraction is half-wired.",
        )

        unresolved: list[str] = []
        for attr, method, lineno in _shim_calls(mw, set(attr_to_cls)):
            cls = attr_to_cls[attr]
            if method not in controller_methods[cls]:
                unresolved.append(
                    f"  src/app.py:{lineno}  self.{attr}.{method}()"
                    f"  →  {cls} has no method '{method}'"
                )
        if unresolved:
            self.fail(
                "Shim methods on MainWindow call controller methods that "
                "don't exist:\n" + "\n".join(unresolved)
            )


if __name__ == "__main__":
    unittest.main()

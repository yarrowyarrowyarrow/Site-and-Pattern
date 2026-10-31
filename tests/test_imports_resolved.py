"""
tests/test_imports_resolved.py

Static guard: every top-level module under ``src/`` parses, and every
``_UPPER_CASE``-style "module-level private constant" referenced inside
function/method bodies is either imported or defined in the same module.

This is the safety net that would have caught the V1.40 regression where
Chunk 4's plant_panel.py split moved ``_PLANT_OBJ_ROLE`` to
``plant_list_view.py`` but left three references behind in PlantPanel
without re-importing it — a bug Python's import machinery cannot detect
at load time because function bodies don't execute until called.

The check runs without PyQt6 (it's pure ast), so it stays effective in
CI environments where the Qt smoke tests skip.
"""

import ast
import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_SRC_DIR = Path(__file__).resolve().parent.parent / "src"


def _bound_anywhere(tree: ast.Module) -> set[str]:
    """Every name that *something* in this module binds — module-level
    or otherwise. Imports inside function bodies count (terrain.py /
    terrain_downloader.py rely on local imports to break a cycle);
    assignments inside ``try / except`` count (``_HAVE_QT`` is set this
    way in src/terrain.py).

    The check is approximate: it won't catch "defined in function A but
    referenced from function B at module level," but that scenario is
    much less common than the regression we're guarding against (a
    constant moved to another module, leaving naked references behind).
    """
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            for alias in node.names:
                names.add(alias.asname or alias.name)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                # ``import foo`` exposes ``foo``; ``import foo.bar`` also
                # exposes ``foo`` (the package root).
                names.add(alias.asname or alias.name.split(".", 1)[0])
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = (node.targets if isinstance(node, ast.Assign)
                       else [node.target])
            for t in targets:
                if isinstance(t, ast.Name):
                    names.add(t.id)
                elif isinstance(t, ast.Tuple):
                    for elt in t.elts:
                        if isinstance(elt, ast.Name):
                            names.add(elt.id)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef,
                                ast.ClassDef)):
            names.add(node.name)
    return names


def _private_const_refs(tree: ast.Module) -> set[str]:
    """``_UPPER_CASE`` Name references anywhere in the module.

    Restricting to UPPER_CASE keeps the check focused on the regression
    class — module-private constants — and avoids tripping on the
    countless ``self._lower`` instance attributes and local variables.
    """
    refs: set[str] = set()
    for node in ast.walk(tree):
        if (isinstance(node, ast.Name)
                and isinstance(node.ctx, ast.Load)
                and node.id.startswith("_")
                and node.id[1:].replace("_", "").isupper()
                and node.id[1:].replace("_", "") != ""):
            refs.add(node.id)
    return refs


class TestPrivateConstantsResolve(unittest.TestCase):
    """For every ``src/*.py`` and ``src/**/*.py``, every ``_UPPER_CASE``
    name referenced in a function body must be importable or defined
    in the same module. Catches the Chunk 4 regression class where a
    moved constant silently broke at runtime."""

    def _scan(self, py_file: Path) -> list[str]:
        with open(py_file, encoding="utf-8") as f:
            src = f.read()
        try:
            tree = ast.parse(src)
        except SyntaxError as e:
            return [f"  syntax error at line {e.lineno}: {e.msg}"]

        bound = _bound_anywhere(tree)
        refs = _private_const_refs(tree)
        # Builtins are never named _FOO, so no need to subtract them.
        unresolved = sorted(refs - bound)
        return unresolved

    def test_every_src_module(self):
        offenders: dict[str, list[str]] = {}
        py_files = sorted(_SRC_DIR.rglob("*.py"))
        self.assertGreater(len(py_files), 0, "no src/ files found?")
        for path in py_files:
            missing = self._scan(path)
            if missing:
                offenders[str(path.relative_to(_SRC_DIR.parent))] = missing
        if offenders:
            lines = ["Unresolved _UPPER_CASE references:"]
            for f, names in offenders.items():
                lines.append(f"  {f}:")
                for n in names:
                    lines.append(f"    {n}")
            self.fail("\n".join(lines))


def _top_level_names(tree: ast.Module) -> set[str]:
    """What ``from <this module> import X`` can find: names bound at module
    level, including inside module-level ``if`` / ``try`` / ``with`` blocks
    (``try: import x except ImportError: x = None`` is common here)."""
    names: set[str] = set()

    def bind(target):
        if isinstance(target, ast.Name):
            names.add(target.id)
        elif isinstance(target, (ast.Tuple, ast.List)):
            for elt in target.elts:
                bind(elt)

    def visit(body):
        for node in body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef,
                                 ast.ClassDef)):
                names.add(node.name)
            elif isinstance(node, ast.Assign):
                for t in node.targets:
                    bind(t)
            elif isinstance(node, (ast.AnnAssign, ast.AugAssign)):
                bind(node.target)
            elif isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    names.add(alias.asname or alias.name)
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    names.add(alias.asname or alias.name.split(".", 1)[0])
            elif isinstance(node, (ast.If, ast.With, ast.For, ast.While)):
                visit(node.body)
                visit(getattr(node, "orelse", []) or [])
            elif isinstance(node, ast.Try):
                visit(node.body)
                visit(node.orelse)
                visit(node.finalbody)
                for handler in node.handlers:
                    visit(handler.body)

    visit(tree.body)
    return names


class TestFromImportsResolve(unittest.TestCase):
    """Every ``from src.x import name`` names something ``src/x.py`` defines.

    The check above passes as long as a name is *bound* in the module that
    uses it, and an import statement binds its name even when the module it
    imports from no longer has it. That is how ``terrain_downloader`` went on
    importing ``_USER_AGENT`` from ``src.terrain`` after the constant moved to
    ``src.http_utils``: the import sits at the top of a module that loads only
    when *Download Edmonton Data* is pressed, so the first anyone heard of it
    was every press of that button aborting the app (found by the V3.05 surface
    audit's click pass). Function-level imports are common in this codebase,
    to keep start-up light, which is exactly what hides this class from a
    plain ``import src.foo``.
    """

    def test_every_imported_name_exists(self):
        root = _SRC_DIR.parent
        cache: dict = {}
        offenders: list[str] = []
        for path in sorted(_SRC_DIR.rglob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if not (isinstance(node, ast.ImportFrom) and node.level == 0
                        and node.module and (node.module == "src"
                                             or node.module.startswith("src."))):
                    continue
                parts = node.module.split(".")
                module_file = root.joinpath(*parts).with_suffix(".py")
                package_init = root.joinpath(*parts, "__init__.py")
                target = (module_file if module_file.exists()
                          else package_init if package_init.exists() else None)
                where = f"{path.relative_to(root)}:{node.lineno}"
                if target is None:
                    offenders.append(f"{where}: no module {node.module}")
                    continue
                if target not in cache:
                    cache[target] = _top_level_names(
                        ast.parse(target.read_text(encoding="utf-8")))
                defined = cache[target]
                if "__getattr__" in defined:
                    continue        # a module that answers any name it is asked
                for alias in node.names:
                    if alias.name == "*" or alias.name in defined:
                        continue
                    submodule = root.joinpath(*parts, alias.name)
                    if (submodule.with_suffix(".py").exists()
                            or (submodule / "__init__.py").exists()):
                        continue
                    offenders.append(
                        f"{where}: {node.module} has no {alias.name}")
        if offenders:
            self.fail("Imports of names their module does not define:\n  "
                      + "\n  ".join(offenders))


if __name__ == "__main__":
    unittest.main()

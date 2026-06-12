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


if __name__ == "__main__":
    unittest.main()

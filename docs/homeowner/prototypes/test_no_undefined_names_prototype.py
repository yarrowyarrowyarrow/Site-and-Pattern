"""
tests/test_no_undefined_names.py — a name nothing defines fails here, not in
somebody's hands (proposed; prototype kept outside the repo).

The Lessons door called ``_sandbox_plants()`` when the function is
``sandbox_plants()``. Python only looks a name up when the line runs, the
door's ``_safely`` swallowed the NameError, and main.py's safety net then
showed the design window: "Learn opens the regular app". No test opened the
door, so the suite stayed green. This reads every module with the standard
library's ``symtable`` (no dependency to install, so it can never skip) and
fails on any name a function uses that the module, its imports and the
builtins do not define.
"""

import builtins
import pathlib
import symtable
import unittest

ROOT = pathlib.Path("/home/user/Site-and-Pattern")
TREES = ("src", "scripts", "tools")
FILES = ("main.py",)
_BUILTINS = set(dir(builtins)) | {
    "__file__", "__name__", "__doc__", "__spec__", "__loader__",
    "__package__", "__builtins__", "__path__", "__class__"}


def _module_names(top) -> set:
    names = {s.get_name() for s in top.get_symbols()
             if s.is_assigned() or s.is_imported() or s.is_namespace()}
    stack = list(top.get_children())
    while stack:               # `global x` then `x = ...` binds a module name
        t = stack.pop()
        stack.extend(t.get_children())
        names |= {s.get_name() for s in t.get_symbols()
                  if s.is_declared_global() and s.is_assigned()}
    return names


def undefined_names(source: str, filename: str) -> list:
    if "import *" in source:   # cannot be checked by reading; none in src/
        return []
    top = symtable.symtable(source, filename, "exec")
    known = _module_names(top) | _BUILTINS
    out, stack = [], list(top.get_children())
    while stack:
        t = stack.pop()
        stack.extend(t.get_children())
        for s in t.get_symbols():
            if (s.is_referenced() and s.is_global()
                    and not s.is_declared_global()
                    and s.get_name() not in known):
                out.append(f"{filename}: {t.get_name()}() "
                           f"(from line {t.get_lineno()}) uses "
                           f"{s.get_name()!r}, which nothing defines")
    return out


def _files():
    for tree in TREES:
        yield from sorted((ROOT / tree).rglob("*.py"))
    for name in FILES:
        yield ROOT / name


class TestNoUndefinedNames(unittest.TestCase):

    def test_the_checker_finds_the_bug_that_shipped(self):
        bad = "def sandbox_plants():\n    pass\ndef go():\n    return _sandbox_plants()\n"
        self.assertEqual(len(undefined_names(bad, "x.py")), 1)
        good = bad.replace("_sandbox_plants()", "sandbox_plants()")
        self.assertEqual(undefined_names(good, "x.py"), [])

    def test_no_module_uses_a_name_nothing_defines(self):
        found = []
        for path in _files():
            found += undefined_names(path.read_text(encoding="utf-8"),
                                     str(path.relative_to(ROOT)))
        self.assertEqual(found, [], "\n".join(found))


if __name__ == "__main__":
    unittest.main()

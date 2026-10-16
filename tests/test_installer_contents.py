"""
tests/test_installer_contents.py — what the installer leaves out (V3.22, RM-7;
docs/homeowner/03-what-goes.md).

``scripts/packaging/permadesign.spec`` had copied the whole ``data/`` and
``html/`` folders: about 33 MB that no installed copy reads, the raw downloads
in ``data/fetched/`` the seed scripts derive the catalogue from, and the probe
pages and tuning benches the tests open from the source tree. The spec now
walks both folders and leaves out what ``_NOT_SHIPPED`` names. This reads the
spec's own patterns and walker and runs them over the tree, so the test cannot
pass on a copy of the list that has drifted from the build's.
"""

import ast
import fnmatch
import os
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_ROOT = Path(__file__).resolve().parent.parent
_SPEC = _ROOT / "scripts" / "packaging" / "permadesign.spec"


def _spec_parts():
    """``_NOT_SHIPPED`` and ``_tree`` from the spec, run as the build runs
    them (with the repo root as ``_ROOT``)."""
    tree = ast.parse(_SPEC.read_text(encoding="utf-8"))
    keep = [n for n in tree.body
            if (isinstance(n, ast.Assign) and any(
                getattr(t, "id", "") == "_NOT_SHIPPED" for t in n.targets))
            or (isinstance(n, ast.FunctionDef) and n.name == "_tree")]
    space = {"os": os, "fnmatch": fnmatch, "_ROOT": str(_ROOT)}
    exec(compile(ast.Module(body=keep, type_ignores=[]), str(_SPEC), "exec"),
         space)
    return space["_NOT_SHIPPED"], space["_tree"]


class TheInstallerLeavesOutWhatNobodyReads(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.patterns, tree = _spec_parts()
        cls.shipped = {dest + "/" + os.path.basename(src)
                       for src, dest in tree("data") + tree("html")}

    def test_the_spec_names_the_five_exclusions(self):
        self.assertEqual(set(self.patterns), {
            "data/fetched/*", "html/*_probe.html",
            "html/inspect_probe_data.json", "html/tune_*.html",
            "html/sprite_gallery*"})

    def test_the_spec_no_longer_copies_whole_folders(self):
        src = _SPEC.read_text(encoding="utf-8")
        self.assertNotIn("(os.path.join(_ROOT, 'data'), 'data')", src)
        self.assertNotIn("(os.path.join(_ROOT, 'html'), 'html')", src)
        self.assertIn("_tree('data') + _tree('html')", src)

    def test_nothing_excluded_is_shipped(self):
        for rel in ("data/fetched/plant_occurrences.json",
                    "html/offline_probe.html", "html/tune_fauna.html",
                    "html/sprite_gallery.html",
                    "html/sprite_gallery_scenes.json",
                    "html/inspect_probe_data.json"):
            if (_ROOT / rel).exists():
                self.assertNotIn(rel, self.shipped)
        self.assertFalse([p for p in self.shipped
                          if p.startswith("data/fetched/")])

    def test_every_page_the_app_opens_still_ships(self):
        for rel in ("html/map.html", "html/scene3d.html",
                    "html/map/01-core.js", "html/scene3d/01-core.js",
                    "html/vendor/three/three.module.js",
                    "html/vendor/leaflet/leaflet.js",
                    "data/plants_master.json",
                    "data/regions/edmonton/local_flora.json",
                    "data/regions/edmonton/region.json", "data/edition.json"):
            self.assertIn(rel, self.shipped, rel)
        # Every html/ path the app's code names, but for the excluded ones it
        # names only in comments about the benches.
        named = set()
        for path in (_ROOT / "src").rglob("*.py"):
            named |= set(re.findall(r"html/[A-Za-z0-9_/.-]+\.(?:html|js|glb)",
                                    path.read_text(encoding="utf-8")))
        missing = sorted(n for n in named
                         if (_ROOT / n).exists() and n not in self.shipped
                         and not any(fnmatch.fnmatch(n, p)
                                     for p in self.patterns))
        self.assertEqual(missing, [])

    def test_it_saves_what_the_plan_said(self):
        left_out = sum(f.stat().st_size for d in ("data", "html")
                       for f in (_ROOT / d).rglob("*") if f.is_file()
                       and any(fnmatch.fnmatch(
                           f.relative_to(_ROOT).as_posix(), p)
                           for p in self.patterns))
        # 03-what-goes.md: "about 33 MB smaller uncompressed".
        self.assertGreater(left_out, 30 * 1024 * 1024)


if __name__ == "__main__":
    unittest.main()

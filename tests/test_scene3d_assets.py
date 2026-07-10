"""
tests/test_scene3d_assets.py

Guards the V1.77 fix for the 3D viewer regression: the built-in viewer
(html/scene3d.html) must load three.js + Spark from VENDORED, LOCAL assets via
the importmap — never from a CDN. A newer bundled Chromium (first CI-built
Windows installer, V1.76) broke the old `file://` + CDN ES-module path, so this
test fails the build if a CDN import sneaks back in or a vendored file goes
missing.

Pure file reads — no Qt, no DB.
"""

import json
import os
import re
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SCENE3D = os.path.join(_ROOT, "html", "scene3d.html")
_VENDOR = os.path.join(_ROOT, "html", "vendor")


def _read(path):
    with open(path, "r", encoding="utf-8") as fh:
        return fh.read()


class SceneViewerAssetsTest(unittest.TestCase):
    def setUp(self):
        self.html = _read(_SCENE3D)

    def _importmap(self):
        m = re.search(
            r'<script type="importmap">\s*(\{.*?\})\s*</script>',
            self.html, re.DOTALL)
        self.assertIsNotNone(m, "scene3d.html has no importmap")
        return json.loads(m.group(1))["imports"]

    def test_importmap_has_no_remote_urls(self):
        for key, target in self._importmap().items():
            self.assertFalse(
                target.startswith(("http://", "https://", "//")),
                f"importmap '{key}' still points at a remote URL: {target}")

    def test_importmap_targets_are_vendored_and_exist(self):
        imports = self._importmap()
        # The three keys the viewer (and Spark) rely on.
        for key in ("three", "three/addons/", "@sparkjsdev/spark"):
            self.assertIn(key, imports, f"importmap missing '{key}'")
        for key, target in imports.items():
            self.assertTrue(
                target.startswith("./vendor/"),
                f"importmap '{key}' should be vendored under ./vendor/: {target}")
            # A trailing-slash prefix mapping (three/addons/) points at a dir.
            rel = target[len("./"):]
            path = os.path.join(_ROOT, "html", *rel.split("/"))
            if target.endswith("/"):
                self.assertTrue(os.path.isdir(path),
                                f"vendored dir missing for '{key}': {path}")
            else:
                self.assertTrue(os.path.isfile(path),
                                f"vendored file missing for '{key}': {path}")

    def test_required_vendor_files_present(self):
        # Including Pass.js, which Spark imports via 'three/addons/...', and
        # three.core.js, which three.module.js re-exports from (V1.77 bug).
        required = [
            ("three", "three.module.js"),
            ("three", "three.core.js"),
            ("three", "addons", "controls", "OrbitControls.js"),
            ("three", "addons", "utils", "BufferGeometryUtils.js"),
            ("three", "addons", "postprocessing", "Pass.js"),
            ("spark", "spark.module.js"),
        ]
        for parts in required:
            path = os.path.join(_VENDOR, *parts)
            self.assertTrue(os.path.isfile(path), f"missing vendored asset: {path}")

    def test_vendored_imports_resolve(self):
        """Every import inside every vendored module must resolve to a file that
        EXISTS — relative siblings (e.g. three.module.js → ./three.core.js, the
        V1.77 bug) and bare specifiers via the importmap alike. A serving test
        can't catch this because it never executes the JS; this static walk does.
        """
        import_map = self._importmap()
        html_dir = os.path.join(_ROOT, "html")

        def resolve(spec, from_path):
            if spec.startswith("."):                         # relative sibling
                return os.path.normpath(
                    os.path.join(os.path.dirname(from_path), spec))
            if spec in import_map:                           # exact importmap key
                return os.path.normpath(
                    os.path.join(html_dir, import_map[spec].lstrip("./")))
            for key, tgt in import_map.items():              # prefix importmap key
                if key.endswith("/") and spec.startswith(key):
                    return os.path.normpath(os.path.join(
                        html_dir, tgt.lstrip("./"), spec[len(key):]))
            return None

        # Line-anchored so import-like text inside bundled string literals
        # (e.g. Spark's inline workers) and JSDoc comment examples don't match.
        spec_re = re.compile(
            r"^\s*(?:import|export)\b[^\n]*?\bfrom\s*['\"]([^'\"]+)['\"]"
            r"|^\s*import\s*\(\s*['\"]([^'\"]+)['\"]", re.M)

        js_files = []
        for root, _dirs, files in os.walk(_VENDOR):
            js_files += [os.path.join(root, f) for f in files if f.endswith(".js")]
        self.assertTrue(js_files, "no vendored .js files found")

        for path in js_files:
            for m in spec_re.finditer(_read(path)):
                spec = m.group(1) or m.group(2)
                resolved = resolve(spec, path)
                rel = os.path.relpath(path, _ROOT)
                self.assertIsNotNone(
                    resolved,
                    f"{rel} imports {spec!r} — resolves via neither a relative "
                    f"path nor the importmap")
                self.assertTrue(
                    os.path.isfile(resolved),
                    f"{rel} imports {spec!r} → MISSING file "
                    f"{os.path.relpath(resolved, _ROOT)}")

    def test_no_cdn_references_anywhere_in_html(self):
        # The HTML shell and every split viewer chunk (html/scene3d/*.js, V2.24).
        srcs = [self.html]
        chunk_dir = os.path.join(_ROOT, "html", "scene3d")
        if os.path.isdir(chunk_dir):
            for f in sorted(os.listdir(chunk_dir)):
                if f.endswith(".js"):
                    srcs.append(_read(os.path.join(chunk_dir, f)))
        for src in srcs:
            self.assertNotIn("unpkg.com", src)
            self.assertNotIn("sparkjs.dev", src)

    def test_split_chunks_use_no_es_imports(self):
        # The chunks are CLASSIC scripts sharing globals (THREE etc. come from the
        # bootstrap module); a stray ES `import`/`export` would throw at load.
        # Dynamic `import(...)` (Spark) is fine and stays.
        chunk_dir = os.path.join(_ROOT, "html", "scene3d")
        if not os.path.isdir(chunk_dir):
            self.skipTest("viewer not split into chunks")
        bad = []
        static_im = re.compile(r"^\s*(?:import\s+[^(]|export\b)", re.M)
        for f in sorted(os.listdir(chunk_dir)):
            if not f.endswith(".js"):
                continue
            if static_im.search(_read(os.path.join(chunk_dir, f))):
                bad.append(f)
        self.assertFalse(bad, f"split chunks must not use static ES import/export "
                              f"(they are classic scripts): {bad}")


if __name__ == "__main__":
    unittest.main()

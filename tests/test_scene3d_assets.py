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
        # Including Pass.js, which Spark imports via 'three/addons/...'.
        required = [
            ("three", "three.module.js"),
            ("three", "addons", "controls", "OrbitControls.js"),
            ("three", "addons", "utils", "BufferGeometryUtils.js"),
            ("three", "addons", "postprocessing", "Pass.js"),
            ("spark", "spark.module.js"),
        ]
        for parts in required:
            path = os.path.join(_VENDOR, *parts)
            self.assertTrue(os.path.isfile(path), f"missing vendored asset: {path}")

    def test_no_cdn_references_anywhere_in_html(self):
        self.assertNotIn("unpkg.com", self.html)
        self.assertNotIn("sparkjs.dev", self.html)


if __name__ == "__main__":
    unittest.main()

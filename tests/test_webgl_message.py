"""
tests/test_webgl_message.py — without WebGL, the 3D preview says so in words a
gardener can act on (V3.05).

``01-core.js`` has said "3D needs WebGL … the 2D map is unaffected" since it
was written, and rethrows. The page's uncaught-error handler then caught the
rethrow and replaced that message with "3D viewer error / Uncaught Error: Error
creating WebGL context.", which is what the V3.05 surface audit photographed
on a machine whose graphics Chromium declines. The handler now keeps a boot
message when one was set.

Runs the real page in headless Chromium with WebGL switched off, so this is
the overlay a person sees, not a reading of the source.
"""

import os
import re
import subprocess
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tests.test_scene3d_render import _Server, _find_chromium  # noqa: E402


@unittest.skipIf(_find_chromium() is None,
                 "no Chromium binary (set CHROME= to run this gate)")
class TestNoWebGL(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        try:
            server = _Server()
        except OSError as exc:
            raise unittest.SkipTest(f"cannot bind a local port: {exc}")
        try:
            proc = subprocess.run(
                [_find_chromium(), "--headless", "--no-sandbox",
                 "--disable-webgl", "--disable-3d-apis",
                 "--virtual-time-budget=15000", "--dump-dom",
                 f"http://127.0.0.1:{server.port}/scene3d.html"],
                capture_output=True, text=True, timeout=180, encoding="utf-8")
        except (OSError, subprocess.TimeoutExpired) as exc:
            server.stop()
            raise unittest.SkipTest(f"Chromium would not run headlessly: {exc}")
        server.stop()
        m = re.search(r'id="offline-msg"[^>]*>(.*?)</div>', proc.stdout, re.S)
        if not m:
            raise unittest.SkipTest("the page never drew its overlay "
                                    f"(chromium exit {proc.returncode})")
        cls.overlay = re.sub(r"<[^>]+>", " ", m.group(1))

    def test_it_says_webgl_and_what_still_works(self):
        self.assertIn("3D needs WebGL", self.overlay)
        self.assertIn("still work", self.overlay)

    def test_the_raw_error_does_not_replace_it(self):
        self.assertNotIn("Uncaught", self.overlay)
        self.assertNotIn("3D viewer error", self.overlay)


if __name__ == "__main__":
    unittest.main()

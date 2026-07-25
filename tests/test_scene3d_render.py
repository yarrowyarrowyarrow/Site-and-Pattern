"""
tests/test_scene3d_render.py — the render-level proportion gate (V2.29).

Every other guard checks a *part*: triangle budgets, node names, the manifest,
the authored aspect of the GLBs, the builder strings. The V2.29 deformation slid
past all of them, because each part was correct and it was their **composition**
that was wrong — archetype geometry (normalised one way) multiplied by the
instance transform (scaled another way) stretched every tree by its species'
height/canopy ratio, up to 4.2x on a lodgepole pine.

So this test boots the real viewer in headless Chromium, pushes one plant at a
time of known dimensions, and reads back the bounding box the viewer actually
built (``window.permaMeasure``). If a plant is asked for at 25 m x 7.5 m and
comes out 25 m x 25 m, this fails and nothing else does.

It is deliberately tolerant: the residual is the honest gap between an
archetype's authored aspect (a median over the species that map to it) and the
dimensions of the individual instance, which runs ~10%. The failure being
guarded against is a factor of two to four.

Self-skips when there is no Chromium binary or no free port, so the ordinary
suite is unaffected; the harness page is ``html/aspect_probe.html``, which
doubles as a hand-run dev page.
"""

import json
import os
import re
import shutil
import socket
import subprocess
import sys
import threading
import unittest
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_HTML = os.path.join(_ROOT, "html")

# Generous: this catches breakage by a factor of 2-4, not the ~10% residual
# between an archetype's authored aspect and one instance's real dimensions.
ASPECT_TOLERANCE = 0.30


def _find_chromium():
    """A Chromium/Chrome binary, or None. Honours CHROME, then the Playwright
    browser dir this project already relies on, then PATH."""
    env = os.environ.get("CHROME")
    if env and os.path.isfile(env):
        return env
    pw = os.environ.get("PLAYWRIGHT_BROWSERS_PATH", "/opt/pw-browsers")
    if os.path.isdir(pw):
        for entry in sorted(os.listdir(pw)):
            cand = os.path.join(pw, entry, "chrome-linux", "chrome")
            if os.path.isfile(cand):
                return cand
    for name in ("chromium", "chromium-browser", "google-chrome", "chrome"):
        found = shutil.which(name)
        if found:
            return found
    return None


class _Server:
    """Serve html/ on an ephemeral loopback port for the life of the test."""

    def __init__(self):
        handler = partial(_QuietHandler, directory=_HTML)
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        self.port = self.httpd.server_address[1]
        self.thread = threading.Thread(target=self.httpd.serve_forever,
                                       daemon=True)
        self.thread.start()

    def stop(self):
        self.httpd.shutdown()
        self.httpd.server_close()


class _QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


@unittest.skipIf(_find_chromium() is None,
                 "no Chromium binary (set CHROME= to run this gate)")
class Scene3DRenderTest(unittest.TestCase):
    measured = None

    @classmethod
    def setUpClass(cls):
        chrome = _find_chromium()
        try:
            server = _Server()
        except OSError as exc:                       # no loopback port
            raise unittest.SkipTest(f"cannot bind a local port: {exc}")
        try:
            url = f"http://127.0.0.1:{server.port}/aspect_probe.html"
            proc = subprocess.run(
                [chrome, "--headless", "--no-sandbox", "--disable-gpu-sandbox",
                 "--enable-unsafe-swiftshader", "--use-angle=swiftshader",
                 "--virtual-time-budget=45000", "--dump-dom", url],
                capture_output=True, text=True, timeout=240)
        except (OSError, subprocess.TimeoutExpired) as exc:
            server.stop()
            raise unittest.SkipTest(f"Chromium would not run headlessly: {exc}")
        server.stop()
        match = re.search(r"MEASURED (\[.*?\])</title>", proc.stdout, re.S)
        if not match:
            raise unittest.SkipTest(
                "the probe never reported — no WebGL in this environment "
                f"(chromium exit {proc.returncode})")
        cls.measured = json.loads(match.group(1))

    def test_every_case_rendered_something(self):
        self.assertTrue(self.measured, "no cases measured")
        for row in self.measured:
            self.assertGreater(
                row["groups"], 0,
                f"{row['genus']}: nothing was built for it at all")
            self.assertGreater(row["height_m"], 0, f"{row['genus']}: zero height")
            self.assertGreater(row["width_m"], 0, f"{row['genus']}: zero width")

    def test_rendered_height_matches_the_scene(self):
        """Height is the axis the instance transform sets directly, so it should
        land almost exactly — a miss here means the unit frame is broken."""
        for row in self.measured:
            self.assertAlmostEqual(
                row["height_m"] / row["want_h"], 1.0, delta=0.15,
                msg=f"{row['genus']}: asked {row['want_h']} m tall, rendered "
                    f"{row['height_m']} m")

    def test_rendered_proportions_match_the_species(self):
        """The composition check: geometry x instance transform must land on the
        proportions the scene asked for. This is the one that would have caught
        the V2.29 deformation, where trees rendered 2-4x too tall for their
        crown while every part-level guard stayed green."""
        worst = max(self.measured, key=lambda r: r["err"])
        for row in self.measured:
            self.assertLess(
                row["err"], ASPECT_TOLERANCE,
                msg=f"{row['genus']}: asked for {row['want_h']}x{row['want_w']} m "
                    f"(aspect {row['want_h'] / row['want_w']:.2f}), rendered "
                    f"{row['height_m']}x{row['width_m']} m — the archetype and the "
                    f"instance transform disagree about proportions")
        # Surfaced on success too: a creeping worst case is the early warning.
        print(f"\n  worst rendered aspect error: {worst['err'] * 100:.0f}% "
              f"({worst['genus']})")


if __name__ == "__main__":
    unittest.main()

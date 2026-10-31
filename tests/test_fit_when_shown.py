"""
tests/test_fit_when_shown.py — a design opened before the map can be seen (V3.04).

F197's fix carries out a start-screen choice made after the map has loaded,
which is most of them: the window is built behind the start screen, so the
page has loaded long before anyone clicks. But it is still hidden then, 0 x 0,
and Qt's 100 x 30 for a moment as the window shows, and Leaflet frames a design
to the size the map has. The example yard opened at zoom 18.4, a dot in an empty
map, where the same design opened into the laid-out window frames at 22.8.

``fitWhenShown`` (html/map/02-boundary.js) fits as well as it can and, when the
map is hidden or that small, fits again once when it is first given a real size.
Run in node against a stubbed map, the real script, as test_map_keyboard does.
"""

import json
import pathlib
import shutil
import subprocess
import unittest

_ROOT = pathlib.Path(__file__).resolve().parent.parent
_MAP = _ROOT / "html" / "map"

_STUBS = r"""
var fits = [], handlers = {};
var document = {visibilityState: 'hidden'};
var size = {x: 0, y: 0};
var map = {
  getSize: function () { return size; },
  fitBounds: function (b, o) { fits.push([b, o || null, size.x, size.y]); },
  on: function (e, fn) { (handlers[e] = handlers[e] || []).push(fn); }
};
function resize(x, y, vis) {
  size = {x: x, y: y};
  if (vis) document.visibilityState = vis;
  (handlers.resize || []).forEach(function (fn) { fn(); });
}
"""


def _node():
    return shutil.which("node") or shutil.which("nodejs")


def _run(steps: str):
    """02-boundary.js with ``steps`` after it; returns every fitBounds call as
    [bounds, options, width, height] and how many resize listeners it added."""
    script = "\n".join([
        _STUBS,
        (_MAP / "02-boundary.js").read_text(encoding="utf-8"),
        steps,
        "console.log(JSON.stringify({fits: fits,"
        " listeners: (handlers.resize || []).length}));",
    ])
    proc = subprocess.run([_node(), "-"], input=script, capture_output=True,
                          text=True, timeout=60, encoding="utf-8")
    if proc.returncode != 0:
        raise AssertionError(f"node failed: {proc.stderr}")
    return json.loads(proc.stdout)


@unittest.skipIf(_node() is None, "no node binary")
class TestAFitMadeBeforeTheMapIsShown(unittest.TestCase):

    def test_is_made_again_when_the_map_has_a_size(self):
        r = _run("fitWhenShown('yard');"
                 "resize(100, 30, 'visible');"      # Qt's default, for a moment
                 "resize(936, 748);"                 # laid out
                 "resize(1200, 800);")               # the user resizes, later
        self.assertEqual([f[2:] for f in r["fits"]], [[0, 0], [936, 748]],
                         "fitted at 0 x 0 and never again, or again on every resize")
        self.assertEqual(r["fits"][1][0], "yard")

    def test_waits_while_the_page_is_hidden_whatever_its_size(self):
        r = _run("fitWhenShown('yard');"
                 "resize(936, 748);"                 # sized but still hidden
                 "resize(936, 748, 'visible');")
        self.assertEqual(len(r["fits"]), 2)
        self.assertEqual(r["fits"][1][2:], [936, 748])

    def test_keeps_its_options(self):
        r = _run("fitWhenShown('yard', {padding: [30, 30]});"
                 "resize(936, 748, 'visible');")
        self.assertEqual(r["fits"][1][1], {"padding": [30, 30]})


@unittest.skipIf(_node() is None, "no node binary")
class TestAFitMadeOnAVisibleMap(unittest.TestCase):

    def test_is_made_once_and_left_alone(self):
        """File → Open, the usual case: a later resize must not throw the
        user's view back to the design."""
        r = _run("resize(936, 748, 'visible');"
                 "fitWhenShown('yard');"
                 "resize(1200, 800);")
        self.assertEqual(len(r["fits"]), 1)

    def test_a_visible_fit_cancels_a_waiting_one(self):
        r = _run("fitWhenShown('first');"          # hidden: waits
                 "resize(936, 748, 'visible');"     # made again: 'first'
                 "fitWhenShown('second');"          # visible: no wait
                 "resize(1200, 800);")
        self.assertEqual([f[0] for f in r["fits"]], ["first", "first", "second"])

    def test_adds_one_listener_however_often_it_is_called(self):
        r = _run("fitWhenShown('a'); fitWhenShown('b'); fitWhenShown('c');")
        self.assertEqual(r["listeners"], 1)


class TestDesignsOpenThroughIt(unittest.TestCase):

    def test_load_boundary_fits_through_fit_when_shown(self):
        src = (_MAP / "05-features.js").read_text(encoding="utf-8")
        start = src.index("function loadBoundary(")
        body = src[start:src.index("\n    }", start)]
        self.assertIn("fitWhenShown(", body)
        self.assertNotIn("map.fitBounds(", body)


if __name__ == "__main__":
    unittest.main()

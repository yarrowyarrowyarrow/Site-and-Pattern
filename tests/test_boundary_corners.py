"""
tests/test_boundary_corners.py — the map keeps an outline's corners once each
(V3.19, QF-14, from the review of the build).

Refusing an outline that crosses itself (``src/outline_check.py``) made two
old habits of html/map/02-boundary.js visible as false refusals:

* Both presses of the double-click that closes an outline reached
  ``handleBoundaryClick``, so the second added a corner. On the exact spot it
  was harmless, but a press a pixel or two off left a sliver of a side running
  back across the one before it: a square clicked in order was refused as
  crossing itself (8 of 24 offsets within 2 px, on a 10 m square at zoom 20).
  A click within ``_SAME_CORNER_PX`` of the last corner now adds none.
* A saved ring is closed, so an outline opened from a file, or redrawn by
  undo, kept its first corner twice: two handles on one spot, and dragging the
  top one pulled a spur out of the outline that was refused as a crossing.
  ``boundaryCorners`` drops the repeat where the page takes an outline in, as
  ``outline_check.corners`` does in Python.

Run in node against the real script, as tests/test_boundary_side_labels.py
runs it. The real page, with real presses, is tests/test_offline_map.py.
"""

import json
import pathlib
import shutil
import subprocess
import unittest

from src import outline_check

_ROOT = pathlib.Path(__file__).resolve().parent.parent
_MAP = _ROOT / "html" / "map"

# A map 1e-6 degrees to the pixel on both axes, north up, enough of Leaflet
# for handleBoundaryClick and the drawing line it redraws.
_STUBS = r"""
var K = 1e6;
function pt(x, y) {
  return {x: x, y: y,
          distanceTo: function (o) { return Math.hypot(o.x - x, o.y - y); }};
}
var map = {
  latLngToContainerPoint: function (ll) { return pt(ll.lng * K, -ll.lat * K); },
  removeLayer: function () {}
};
var drawn = {addTo: function () { return this; }};
var L = {
  latLng: function (a, b) {
    return Array.isArray(a) ? {lat: a[0], lng: a[1]} : {lat: a, lng: b};
  },
  polyline: function () { return drawn; },
  circleMarker: function () { return drawn; }
};
var polygonPoints = [], drawingPolygon = false, polygonPolyline = null;
var drawnItems = {};
var closed = 0;
function press(xPx, yPx) { handleBoundaryClick(-yPx / K, xPx / K); }
"""

_LAT, _LNG, _D = 53.5461, -113.4938, 0.0002
_SQUARE = [[_LAT - _D, _LNG - _D], [_LAT - _D, _LNG + _D],
           [_LAT + _D, _LNG + _D], [_LAT + _D, _LNG - _D]]


def _node():
    return shutil.which("node") or shutil.which("nodejs")


def _run(steps: str):
    script = "\n".join([_STUBS, (_MAP / "02-boundary.js").read_text(encoding="utf-8"),
                        # Closing is finishBoundaryPolygon's, not this test's.
                        "finishBoundaryPolygon = function () { closed += 1; };",
                        steps])
    proc = subprocess.run([_node(), "-"], input=script, capture_output=True,
                          text=True, timeout=60, encoding="utf-8")
    if proc.returncode != 0:
        raise AssertionError(f"node failed: {proc.stderr}")
    return json.loads(proc.stdout)


@unittest.skipIf(_node() is None, "no node binary")
class TestAPressOnTheLastCorner(unittest.TestCase):

    def _square_then(self, dx, dy):
        """Three corners of a 100 px square, the fourth, then a second press
        ``dx``, ``dy`` pixels from the fourth: the corners kept."""
        return _run("""
            [[0, 100], [100, 100], [100, 0], [0, 0]].forEach(function (p) {
              press(p[0], p[1]); });
            press(%d, %d);
            console.log(JSON.stringify({corners: polygonPoints, closed: closed}));
            """ % (dx, dy))

    def test_a_second_press_a_pixel_off_adds_no_corner(self):
        """The double-click that closes the outline, its second press a pixel
        right of and above the first."""
        out = self._square_then(1, -1)
        self.assertEqual(len(out["corners"]), 4, out)
        self.assertEqual(out["closed"], 0)

    @unittest.skipUnless(outline_check._HAVE_SHAPELY, "shapely not installed")
    def test_no_press_within_the_double_click_reach_is_refused(self):
        """Every second press within 2 px of the fourth corner, the reach of a
        double-click on Windows: the square Python is sent never crosses."""
        for dx in range(-2, 3):
            for dy in range(-2, 3):
                with self.subTest(dx=dx, dy=dy):
                    out = self._square_then(dx, dy)
                    self.assertEqual(len(out["corners"]), 4)
                    self.assertFalse(outline_check.crosses_itself(out["corners"]))

    def test_a_press_further_off_is_a_corner(self):
        out = self._square_then(6, 0)
        self.assertEqual(len(out["corners"]), 5, out)

    def test_a_press_by_the_first_corner_still_closes(self):
        out = self._square_then(0, 103)            # 3 px from the first corner
        self.assertEqual(out["closed"], 1)
        self.assertEqual(len(out["corners"]), 4)


@unittest.skipIf(_node() is None, "no node binary")
class TestTheCornersTheMapKeeps(unittest.TestCase):

    CASES = {
        "closed, as saved": _SQUARE + [_SQUARE[0]],
        "a corner twice": _SQUARE[:2] + [_SQUARE[1]] + _SQUARE[2:],
        "both": _SQUARE[:2] + [_SQUARE[1]] + _SQUARE[2:] + [_SQUARE[0]],
        "open, as drawn": _SQUARE,
        "one corner": [_SQUARE[0], _SQUARE[0]],
        "none": [],
    }

    def test_each_corner_once(self):
        out = _run("console.log(JSON.stringify(%s.map(boundaryCorners)));"
                   % json.dumps(list(self.CASES.values())))
        for (name, pts), got in zip(self.CASES.items(), out):
            with self.subTest(name):
                want = _SQUARE if len(pts) > 2 else pts[:1]
                self.assertEqual(got, want)

    def test_the_page_and_python_agree(self):
        """The page keeps the corners Python's crossing test reads."""
        out = _run("console.log(JSON.stringify(%s.map(boundaryCorners)));"
                   % json.dumps(list(self.CASES.values())))
        for pts, got in zip(self.CASES.values(), out):
            self.assertEqual(got, [list(p) for p in outline_check.corners(pts)])


if __name__ == "__main__":
    unittest.main()

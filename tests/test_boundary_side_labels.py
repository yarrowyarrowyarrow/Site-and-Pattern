"""
tests/test_boundary_side_labels.py — no "0.0 m" on a boundary (V3.19, QF-8, R19).

The review opened a saved design and saw its outline's closing corner labelled
"0.0 m". A saved ring is closed, so an outline read back from a file repeats
its first corner at the end, and html/map/02-boundary.js labelled the side from
that copy to the first corner, which has no length. A double-click that closes
an outline can leave two corners on one spot the same way. Now a side under
5 cm has no label (``boundarySideLabel``, pure).

Run in node against the real script, as tests/test_fit_when_shown.py runs it.
The real page is checked offline by tests/test_offline_map.py.
"""

import json
import pathlib
import shutil
import subprocess
import unittest

_ROOT = pathlib.Path(__file__).resolve().parent.parent
_MAP = _ROOT / "html" / "map"

_STUBS = r"""
var map = {}, made = [];
var L = {
  layerGroup: function () { return {addTo: function () { return this; }}; },
  divIcon: function (o) { return o; },
  marker: function (at, o) {
    return {addTo: function () { made.push(o.icon.html.replace(/<[^>]+>/g, '')); }};
  }
};
function escH(s) { return String(s); }
"""

_LAT, _LNG, _D = 53.5461, -113.4938, 0.0002
_YARD = [[_LAT - _D, _LNG - _D * 1.5], [_LAT - _D, _LNG + _D * 1.5],
         [_LAT + _D, _LNG + _D * 1.5], [_LAT + _D, _LNG - _D * 1.5]]


def _node():
    return shutil.which("node") or shutil.which("nodejs")


def _run(steps: str):
    script = "\n".join([_STUBS, (_MAP / "02-boundary.js").read_text(encoding="utf-8"),
                        steps])
    proc = subprocess.run([_node(), "-"], input=script, capture_output=True,
                          text=True, timeout=60, encoding="utf-8")
    if proc.returncode != 0:
        raise AssertionError(f"node failed: {proc.stderr}")
    return json.loads(proc.stdout)


@unittest.skipIf(_node() is None, "no node binary")
class TestASideLabel(unittest.TestCase):

    def test_no_label_under_five_centimetres(self):
        cases = [0, 0.001, 0.049, 0.05, 0.3, 9.94, 10, 43.6, float("nan")]
        out = _run("console.log(JSON.stringify(%s.map(boundarySideLabel)));"
                   % json.dumps(cases))                   # NaN is JS too
        self.assertEqual(out, ["", "", "", "0.1 m", "0.3 m", "9.9 m", "10 m",
                               "44 m", ""])

    def test_an_outline_read_back_from_a_file(self):
        """Four sides and four labels, where the repeated first corner gave a
        fifth, "0.0 m"."""
        out = _run("_makeBoundaryLengthLabels(%s, '#4caf50');"
                   "console.log(JSON.stringify(made));"
                   % json.dumps(_YARD + [_YARD[0]]))
        self.assertEqual(out, ["40 m", "44 m", "40 m", "44 m"])

    def test_two_corners_on_one_spot(self):
        """A double-click that closes the outline can put two corners on one
        spot: one side between them, and no label for it."""
        out = _run("_makeBoundaryLengthLabels(%s, '#4caf50');"
                   "console.log(JSON.stringify(made));"
                   % json.dumps(_YARD[:3] + [_YARD[2]] + _YARD[3:]))
        self.assertEqual(out, ["40 m", "44 m", "40 m", "44 m"])


if __name__ == "__main__":
    unittest.main()

"""
tests/test_offline_map.py — the map says why it is blank when it cannot load
(V3.19, QF-6, R9).

The review: "Offline, the map is a blank grey area with no message saying the
map could not load." The basemap's ``tileerror`` handler (html/map/01-core.js)
fell back from one tile host to the next and, with the last one failing too,
said nothing. Now each base map is watched by ``watchBaseTiles``
(html/map/11-map-furniture.js): once a screenful has answered with no tile
drawn, a base map that never drew one hands over to the next, and the last
shows *The map needs an internet connection to load. Your design is safe.*
until a tile draws.

The decision is ``basemapVerdict``, pure, run in node as test_map_furniture
runs the scale; ``watchBaseTiles`` runs in node against a stub layer. Then the
real page, offline in headless Chromium (``html/offline_probe.html``, the
harness tests/test_boundary_press.py uses): the line shows, takes no clicks,
and goes when a tile draws. The same run reads what the review found wrong at
yard scale on the same page: the "0.0 m" side (QF-8), the scale in kilometres
(QF-18) and an edited outline put back (QF-14).
"""

import json
import pathlib
import shutil
import subprocess
import unittest

_ROOT = pathlib.Path(__file__).resolve().parent.parent
_SCRIPT = _ROOT / "html" / "map" / "11-map-furniture.js"
_TEXT = "The map needs an internet connection to load. Your design is safe."


def _node():
    return shutil.which("node") or shutil.which("nodejs")


_STUBS = r"""
var made = [];
var document = {
  createElement: function (tag) {
    var el = {tag: tag, style: {}, attrs: {}, textContent: '',
              setAttribute: function (k, v) { this.attrs[k] = v; }};
    made.push(el);
    return el;
  },
  body: {appendChild: function () {}}
};
function stubLayer() {
  var on = {}, drawn = 0;
  return {
    on: function (ev, fn) { (on[ev] = on[ev] || []).push(fn); },
    getContainer: function () {
      return {querySelectorAll: function () { return {length: drawn}; }};
    },
    fire: function (ev) { (on[ev] || []).forEach(function (fn) { fn(); }); },
    draw: function (n) { drawn = n; }
  };
}
function shown() {
  var el = made[0];
  if (!el || el.style.display === 'none') return null;
  return {text: el.textContent, role: el.attrs.role,
          clicks: /pointer-events:none/.test(el.style.cssText) ? 'none' : 'some'};
}
"""


def _run(steps: str):
    """11-map-furniture.js with stubs, then ``steps``, which must print."""
    script = "\n".join([_STUBS, _SCRIPT.read_text(encoding="utf-8"), steps])
    proc = subprocess.run([_node(), "-"], input=script, capture_output=True,
                          text=True, timeout=60, encoding="utf-8")
    if proc.returncode != 0:
        raise AssertionError(f"node failed: {proc.stderr}")
    return json.loads(proc.stdout)


@unittest.skipIf(_node() is None, "no node binary")
class TestTheVerdict(unittest.TestCase):

    def test_what_a_screenful_says(self):
        cases = [[3, False, True], [3, True, False],   # tiles drawn: say nothing
                 [0, False, True],                      # never drew: try the next
                 [0, False, False],                     # the last: offline
                 [0, True, True]]                       # drew before: offline
        out = _run("console.log(JSON.stringify(%s.map(function (c) {"
                   " return basemapVerdict(c[0], c[1], c[2]); })));"
                   % json.dumps(cases))
        self.assertEqual(out, ["ok", "ok", "next", "offline", "offline"])


@unittest.skipIf(_node() is None, "no node binary")
class TestWatchingTheTiles(unittest.TestCase):

    def test_the_last_base_map_failing_says_so_until_a_tile_draws(self):
        out = _run("""
            var layer = stubLayer();
            watchBaseTiles(layer, null);
            var before = shown();
            layer.fire('loading'); layer.fire('tileerror'); layer.fire('load');
            var offline = shown();
            layer.draw(1); layer.fire('tileload');
            console.log(JSON.stringify({before: before, offline: offline,
                                        after: shown()}));""")
        self.assertIsNone(out["before"])
        self.assertEqual(out["offline"], {"text": _TEXT, "role": "status",
                                          "clicks": "none"})
        self.assertIsNone(out["after"])

    def test_a_base_map_that_never_drew_hands_over_without_a_word(self):
        out = _run("""
            var layer = stubLayer(), handed = 0;
            watchBaseTiles(layer, function () { handed += 1; });
            layer.fire('tileerror'); layer.fire('load');
            console.log(JSON.stringify({handed: handed, said: shown()}));""")
        self.assertEqual(out, {"handed": 1, "said": None})

    def test_a_base_map_that_worked_is_kept_when_the_connection_drops(self):
        """A screenful failing after tiles have drawn is the connection, not a
        dead host: the next base map would fail too, and the one that worked
        is what comes back when the connection does."""
        out = _run("""
            var layer = stubLayer(), handed = 0;
            watchBaseTiles(layer, function () { handed += 1; });
            layer.draw(4); layer.fire('tileload'); layer.fire('load');
            var fine = shown();
            layer.draw(0); layer.fire('tileerror'); layer.fire('load');
            console.log(JSON.stringify({fine: fine, handed: handed,
                                        said: shown()}));""")
        self.assertIsNone(out["fine"])
        self.assertEqual(out["handed"], 0)
        self.assertEqual(out["said"]["text"], _TEXT)

    def test_a_screenful_with_some_tiles_drawn_says_nothing(self):
        out = _run("""
            var layer = stubLayer();
            watchBaseTiles(layer, null);
            layer.draw(2); layer.fire('tileerror'); layer.fire('load');
            console.log(JSON.stringify({said: shown()}));""")
        self.assertIsNone(out["said"])


class TestTheCoreHandsOverItsLayers(unittest.TestCase):
    """Source guard: the watcher is only as good as the layers given to it."""

    def test_every_base_map_and_the_photo_are_watched(self):
        core = (_ROOT / "html" / "map" / "01-core.js").read_text(encoding="utf-8")
        self.assertIn("watchBaseTiles(osmLayer,", core)
        self.assertIn("watchBaseTiles(satelliteLayer, null)", core)


def _chromium():
    from tests.test_scene3d_render import _find_chromium
    return _find_chromium()


@unittest.skipIf(_chromium() is None,
                 "no Chromium binary (set CHROME= to run this gate)")
class TheMapPageOffline(unittest.TestCase):
    m = None

    @classmethod
    def setUpClass(cls):
        from tests.test_boundary_press import _run_probe
        cls.m = _run_probe("offline_probe.html")

    def setUp(self):
        self.assertNotIn("error", self.m, self.m.get("error"))

    def test_the_map_says_it_needs_a_connection(self):
        n = self.m["notice"]
        self.assertIsNotNone(n, "a blank map and no word")
        self.assertEqual(n["text"], _TEXT)
        self.assertEqual(n["role"], "status")
        # Both tile hosts were tried before it said so.
        self.assertIn("openstreetmap", self.m["basemap"])

    def test_the_line_takes_no_clicks(self):
        n = self.m["notice"]
        self.assertEqual(n["pointer"], "none")
        self.assertNotEqual(n["under"], "sp-offline")
        self.assertEqual(self.m["corners_after_click"], 1,
                         "a click on the line did not reach the map")

    def test_it_goes_when_a_tile_draws(self):
        self.assertFalse(self.m["after_a_tile"])

    def test_an_outline_from_a_file_has_no_zero_side(self):
        """QF-8 (R19): four sides labelled, and no "0.0 m" for the repeated
        first corner."""
        labels = self.m["side_labels"]
        self.assertEqual(len(labels), 4, labels)
        self.assertNotIn("0.0 m", labels)

    def test_an_edited_outline_is_put_back_with_its_handles(self):
        r = self.m["restored"]
        self.assertEqual(len(r["points"]), 4)
        self.assertAlmostEqual(r["points"][0][0], 53.5461 - 0.0002)
        self.assertEqual(r["editing"], "b1")
        self.assertEqual(r["handles"], 4)

    def test_the_scale_is_metres_across_a_yard(self):
        """QF-18 (R18): Automatic, the default; a click fixes the other unit
        from the one shown, and tells Python."""
        self.assertRegex(self.m["scale_yard"], r"^[0-9.]+ m$")
        self.assertRegex(self.m["scale_county"], r"^[0-9.]+ km$")
        click = self.m["scale_click"]
        self.assertRegex(click["label"], r" km$")
        self.assertEqual(click["told"], [["onScaleUnitChanged", "km"]])


if __name__ == "__main__":
    unittest.main()

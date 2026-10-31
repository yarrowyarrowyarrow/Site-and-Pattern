"""
tests/test_offline_map.py — the map says why it is blank when it cannot load
(V3.19, QF-6, R9).

The review: "Offline, the map is a blank grey area with no message saying the
map could not load." The basemap's ``tileerror`` handler (html/map/01-core.js)
fell back from one tile host to the next and, with the last one failing too,
said nothing. Now each base map is watched by ``watchBaseTiles``
(html/map/11-map-furniture.js): a base map that never drew a tile hands over
to the next after eight errors or a screenful with none drawn, one that drew is
kept when the connection drops, and the last shows *The map needs an internet
connection to load. Your design is safe.* above the scale bar until a tile
draws. When the connection comes back, the tiles are asked for again.

The decision is ``basemapVerdict``, pure, run in node as test_map_furniture
runs the scale; ``watchBaseTiles`` runs in node against a stub layer. Then the
real page, offline in headless Chromium (``html/offline_probe.html``, the
harness tests/test_boundary_press.py uses): the line shows, takes no clicks,
sits off the yard and goes when a tile draws. The same run reads what the
review found wrong at yard scale on the same page: the "0.0 m" side (QF-8), the
scale in kilometres (QF-18) and an outline that crosses itself (QF-14),
including the two ordinary gestures the build's review found refused: a
double-click whose second press lands a pixel off, and a corner of an outline
opened from a file dragged outward.
"""

import json
import pathlib
import shutil
import subprocess
import unittest

from src import outline_check

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
var window = {
  on: {},
  addEventListener: function (ev, fn) { (this.on[ev] = this.on[ev] || []).push(fn); },
  fire: function (ev) { (this.on[ev] || []).forEach(function (fn) { fn(); }); }
};
function stubLayer() {
  var on = {}, drawn = 0;
  return {
    redrawn: 0,
    on: function (ev, fn) { (on[ev] = on[ev] || []).push(fn); },
    getContainer: function () {
      return {querySelectorAll: function () { return {length: drawn}; }};
    },
    fire: function (ev) { (on[ev] || []).forEach(function (fn) { fn(); }); },
    draw: function (n) { drawn = n; },
    redraw: function () { this.redrawn += 1; }
  };
}
// Print once every hand-over waiting on a timer has run.
function later(fn) { setTimeout(function () { console.log(JSON.stringify(fn())); }, 5); }
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
            later(function () { return {handed: handed, said: shown()}; });""")
        self.assertEqual(out, {"handed": 1, "said": None})

    def test_eight_errors_from_a_base_map_that_never_drew_hand_over(self):
        """A dead host on a big map, before the screenful has answered: the
        count 01-core.js kept until V3.19, now kept with the rest here."""
        out = _run("""
            var layer = stubLayer(), handed = 0;
            watchBaseTiles(layer, function () { handed += 1; });
            for (var i = 0; i < 7; i++) layer.fire('tileerror');
            var seven = 0;
            setTimeout(function () { seven = handed; }, 0);
            for (i = 0; i < 5; i++) layer.fire('tileerror');
            later(function () { return {seven: seven, handed: handed}; });""")
        self.assertEqual(out, {"seven": 0, "handed": 1})

    def test_a_base_map_that_worked_is_kept_when_the_connection_drops(self):
        """A screenful failing after tiles have drawn is the connection, not a
        dead host: the next base map would fail too, and the one that worked
        is what comes back when the connection does. Neither the screenful
        nor any number of errors hands it over (the review found the error
        count still did)."""
        out = _run("""
            var layer = stubLayer(), handed = 0;
            watchBaseTiles(layer, function () { handed += 1; });
            layer.draw(4); layer.fire('tileload'); layer.fire('load');
            var fine = shown();
            layer.draw(0);
            for (var i = 0; i < 20; i++) layer.fire('tileerror');
            layer.fire('load');
            later(function () { return {fine: fine, handed: handed,
                                        said: shown()}; });""")
        self.assertIsNone(out["fine"])
        self.assertEqual(out["handed"], 0)
        self.assertEqual(out["said"]["text"], _TEXT)

    def test_the_hand_over_waits_for_leaflet(self):
        """The review: handing over removes the layer, and Leaflet reads the
        layer's map straight after firing 'load' (``this._map._fadeAnimated``
        in ``_tileReady``), so a hand-over made inside 'load' threw a
        TypeError into the log on every offline start of a small map."""
        out = _run("""
            var layer = stubLayer(), handed = 0, threw = null;
            layer._map = {_fadeAnimated: true};
            watchBaseTiles(layer, function () { handed += 1; layer._map = null; });
            try {
              layer.fire('tileerror'); layer.fire('load');
              void layer._map._fadeAnimated;        // what Leaflet reads next
            } catch (e) { threw = String(e); }
            later(function () { return {threw: threw, handed: handed}; });""")
        self.assertEqual(out, {"threw": None, "handed": 1})

    def test_the_connection_back_asks_again_for_the_tiles(self):
        """The review: Leaflet never asks again for a tile that failed, so
        the line and the grey map stayed after the connection came back."""
        out = _run("""
            var base = stubLayer(), photo = stubLayer();
            watchBaseTiles(base, null); watchBaseTiles(photo, null);
            base.fire('tileerror'); base.fire('load');
            window.fire('online');
            var asked = [base.redrawn, photo.redrawn], says = !!shown();
            base.draw(1); base.fire('tileload');
            console.log(JSON.stringify({asked: asked, says: says,
                                        after: shown()}));""")
        # Asked again, and the line stays until a tile draws: still true.
        self.assertEqual(out, {"asked": [1, 1], "says": True, "after": None})

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

    def test_one_place_decides_a_hand_over(self):
        """The core's own eight-error swap ignored whether its host had drawn,
        so a dropped connection swapped the person's base map (the review)."""
        core = (_ROOT / "html" / "map" / "01-core.js").read_text(encoding="utf-8")
        self.assertNotIn("osmLayer.on('tileerror'", core)


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

    def test_the_line_sits_off_the_yard_and_clear_of_the_scale(self):
        """The review: centred, it covered the middle of the yard (what the
        view frames) for as long as the person was offline. Now one line at
        the bottom, above the scale bar and not touching it."""
        line, scale, page = (self.m["places"][k] for k in ("line", "scale", "map"))
        height = page["bottom"] - page["top"]
        self.assertGreater(line["top"], page["top"] + height * 0.75, line)
        self.assertLessEqual(line["bottom"], scale["top"], (line, scale))
        self.assertLess(line["bottom"] - line["top"], 40, "more than one line")

    def test_export_pdf_can_hold_the_line_off(self):
        """The review: Export PDF's map page is a grab of this page, and the
        line was printed on the plan. The real page hides it on request and
        shows it again after (tests/test_offline_notice_print.py has the
        rest)."""
        self.assertEqual(self.m["held"], {"held": False, "after": True})

    def test_the_connection_back_asks_again(self):
        """The review: Leaflet never asks again for a failed tile, so the line
        stayed after the connection came back. The base map is redrawn; here
        it is still offline, so the line stays, which is still true."""
        self.assertEqual(self.m["online"], {"redrawn": 1, "still_says": True})

    def test_a_hand_over_inside_leaflets_load_throws_nothing(self):
        """The review: a base map handed over from inside Leaflet's 'load'
        threw "Cannot read properties of null (reading '_fadeAnimated')"."""
        self.assertEqual(self.m["hand_over"], {"handed": 1, "errors": []})
        self.assertEqual(self.m["errors"], [])

    def test_an_outline_from_a_file_has_no_zero_side(self):
        """QF-8 (R19): four sides labelled, and no "0.0 m" for the repeated
        first corner."""
        labels = self.m["side_labels"]
        self.assertEqual(len(labels), 4, labels)
        self.assertNotIn("0.0 m", labels)

    def test_an_outline_from_a_file_has_one_handle_per_corner(self):
        """The review: the repeated first corner was kept on the map, so it
        had two handles on one spot."""
        self.assertEqual(self.m["opened"], {"corners": 4, "handles": 4})

    def test_an_edited_outline_is_put_back_with_its_handles(self):
        r = self.m["restored"]
        self.assertEqual(len(r["points"]), 4)
        self.assertAlmostEqual(r["points"][0][0], 53.5461 - 0.0002)
        self.assertEqual(r["editing"], "b1")
        self.assertEqual(r["handles"], 4)

    @unittest.skipUnless(outline_check._HAVE_SHAPELY, "shapely not installed")
    def test_a_square_closed_by_a_double_click_a_pixel_off_is_kept(self):
        """QF-14, the review: both presses of the closing double-click added a
        corner, and the second, a pixel right of and above the first, left a
        sliver of a side that read as a crossing, so a square clicked in order
        was refused. One corner there now, and nothing crosses."""
        corners = self.m["double_click"]
        self.assertIsNotNone(corners, "the outline was never closed")
        self.assertEqual(len(corners), 4, corners)
        self.assertFalse(outline_check.crosses_itself(corners))

    def test_the_closing_double_click_does_not_zoom(self):
        """The owner, V3.23: a double-click that closed an outline also zoomed
        the map, because Leaflet's own double-click zoom ran before the app's
        handler. It zooms now only with no tool armed."""
        # Who zoomed, by the mode at the time: only the no-tool double-click.
        self.assertEqual(self.m["double_click_zooms"], ["none"])

    @unittest.skipUnless(outline_check._HAVE_SHAPELY, "shapely not installed")
    def test_a_corner_of_an_outline_from_a_file_drags_like_any_other(self):
        """QF-14, the review: on an outline opened from a file (or redrawn by
        undo), the handle on top of the first corner was the repeated
        corner's; dragging it left the real one behind as a spur, and the
        edit was refused as crossing. The same drag on a freshly drawn outline
        was kept."""
        r = self.m["reopened_drag"]
        # Said in full when it fails (V3.38): CI once read 0 here and printed
        # only "0 != 4", which cannot tell a press that missed the handle (and
        # so ended edit mode) from handles that were never drawn.
        why = (f"{r.get('handles_open')} handles before the drag; it landed "
               f"on {r.get('target')} ({r.get('where')})")
        self.assertEqual(r.get("handles_open"), 4, why)
        self.assertEqual(r["handles"], 4, why)
        self.assertIsNotNone(r["sent"], f"the drag was never reported: it "
                                        f"landed on {r.get('target')} "
                                        f"({r.get('where')})")
        self.assertEqual(len(r["sent"]), 4, r["sent"])
        self.assertNotAlmostEqual(r["sent"][0][0], 53.5461 - 0.0002, places=7,
                                  msg="the first corner did not move")
        self.assertFalse(outline_check.crosses_itself(r["sent"]))

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

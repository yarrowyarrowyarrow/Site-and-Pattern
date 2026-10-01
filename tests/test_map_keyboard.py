"""
tests/test_map_keyboard.py — the map without a mouse (F195, V3.02).

Until V3.02 every map tool acted on a click, so a keyboard could pan the map
and do nothing on it. ``html/map/09-keyboard.js`` makes Enter on the focused
map act at its centre and Shift+Enter finish a drawing. It is run here in node
against a stubbed map and page, the way ``test_place_action`` runs the
footprint: the real script, not a description of it.
"""

import json
import pathlib
import shutil
import subprocess
import unittest

_ROOT = pathlib.Path(__file__).resolve().parent.parent
_MAP = _ROOT / "html" / "map"

_STUBS = r"""
var calls = [], elements = {};
function _el(tag) {
  return {tag: tag, style: {}, attrs: {}, children: [],
          setAttribute: function (k, v) { this.attrs[k] = v; },
          appendChild: function (c) { this.children.push(c);
                                      if (c.id) elements[c.id] = c; }};
}
var container = _el('div');
container.classes = {};
container.focus = function () { document.activeElement = container;
                                calls.push(['focus']); };
container.classList = {toggle: function (c, on) { container.classes[c] = !!on; }};
var other = _el('a');
var document = {
  listeners: {}, activeElement: null, head: _el('head'),
  addEventListener: function (t, fn) {
    (this.listeners[t] = this.listeners[t] || []).push(fn); },
  getElementById: function (id) { return elements[id] || null; },
  createElement: function (tag) { return _el(tag); }
};
var map = {handlers: {}, getContainer: function () { return container; },
           getCenter: function () { return {lat: 53.5, lng: -113.5}; },
           on: function (e, fn) { this.handlers[e] = fn; }};
var currentMode = 'none';
function onMapClick(e) { calls.push(['click', e.latlng.lat, e.latlng.lng]); }
function onMapMouseMove(e) { calls.push(['move', e.latlng.lat, e.latlng.lng]); }
function finishDrawing() { calls.push(['finish']); }
function hideCursorFootprint() { calls.push(['hide']); }
function key(k, shift, on) {
  document.activeElement = on || container;
  var ev = {key: k, shiftKey: !!shift, prevented: false,
            preventDefault: function () { this.prevented = true; }};
  document.listeners.keydown.forEach(function (fn) { fn(ev); });
  return ev.prevented;
}
function mouse() {
  document.listeners.mousedown.forEach(function (fn) { fn({}); });
}
function mark() {
  var el = elements['sp-centre-mark'];
  return el ? el.style.display : 'absent';
}
"""


def _node():
    return shutil.which("node") or shutil.which("nodejs")


def _run(steps: str):
    """Run 09-keyboard.js with ``steps`` after ``initMapKeyboard()``; return
    what the steps report through ``out``."""
    script = "\n".join([
        _STUBS,
        (_MAP / "09-keyboard.js").read_text(encoding="utf-8"),
        "initMapKeyboard();",
        "var out = {};",
        steps,
        "console.log(JSON.stringify({out: out, calls: calls}));",
    ])
    proc = subprocess.run([_node(), "-e", script], capture_output=True,
                          text=True, timeout=60, encoding="utf-8")
    if proc.returncode != 0:
        raise AssertionError(f"node failed: {proc.stderr}")
    return json.loads(proc.stdout)


@unittest.skipIf(_node() is None, "no node binary")
class TestEnterActsAtTheCentre(unittest.TestCase):

    def test_enter_places_at_the_centre_while_a_tool_is_chosen(self):
        got = _run("currentMode = 'plant'; out.prevented = key('Enter');")
        self.assertIn(["click", 53.5, -113.5], got["calls"])
        self.assertTrue(got["out"]["prevented"])

    def test_every_click_tool_answers_enter(self):
        for mode in ("plant", "polyculture", "structure", "boundary",
                     "hedgerow", "shape", "fill", "contour", "measure",
                     "annotate", "sun_anchor"):
            with self.subTest(mode=mode):
                got = _run(f"currentMode = '{mode}'; key('Enter');")
                self.assertIn(["click", 53.5, -113.5], got["calls"])

    def test_no_tool_or_a_drag_tool_means_enter_does_nothing(self):
        for mode in ("none", "select", "terrain_rect"):
            with self.subTest(mode=mode):
                got = _run(f"currentMode = '{mode}'; key('Enter');")
                self.assertNotIn("click", [c[0] for c in got["calls"]])

    def test_shift_enter_finishes_what_a_double_click_does(self):
        got = _run("currentMode = 'boundary'; key('Enter', true);")
        self.assertIn(["finish"], got["calls"])
        self.assertNotIn("click", [c[0] for c in got["calls"]])

    def test_enter_on_a_control_inside_the_map_presses_that_control(self):
        """The zoom buttons and the legend take Enter themselves."""
        got = _run("currentMode = 'plant'; out.prevented = key('Enter', false, other);")
        self.assertEqual(got["calls"], [])
        self.assertFalse(got["out"]["prevented"])


@unittest.skipIf(_node() is None, "no node binary")
class TestTheCentreMark(unittest.TestCase):

    def test_the_mark_shows_while_the_keyboard_drives_a_tool(self):
        got = _run("currentMode = 'plant'; out.before = mark(); key('ArrowLeft');"
                   " out.after = mark();")
        self.assertIn(got["out"]["before"], ("absent", "none"))
        self.assertEqual(got["out"]["after"], "block")
        # The footprint is drawn at the centre the moment the keyboard is in.
        self.assertIn(["move", 53.5, -113.5], got["calls"])

    def test_a_mouse_press_hands_the_map_back(self):
        got = _run("currentMode = 'plant'; key('ArrowLeft'); mouse();"
                   " out.after = mark();")
        self.assertEqual(got["out"]["after"], "none")
        self.assertIn(["hide"], got["calls"])

    def test_the_previews_follow_the_centre_as_the_map_pans(self):
        got = _run("currentMode = 'plant'; key('ArrowLeft'); calls.length = 0;"
                   " map.handlers.move();")
        self.assertEqual(got["calls"], [["move", 53.5, -113.5]])

    def test_no_tool_no_mark(self):
        got = _run("currentMode = 'none'; key('ArrowLeft'); out.after = mark();")
        self.assertIn(got["out"]["after"], ("absent", "none"))


@unittest.skipIf(_node() is None, "no node binary")
class TestTheMapsFocusRing(unittest.TestCase):
    """The browser's own ring sat a pixel outside a container that fills the
    page, so the map was the one Tab stop with no visible focus. The page
    draws one inside its edge, over the panes and the controls."""

    def test_the_ring_follows_the_keyboard_not_the_mouse(self):
        got = _run("key('ArrowLeft'); out.on = container.classes['sp-keyboard'];"
                   " mouse(); out.off = container.classes['sp-keyboard'];")
        self.assertTrue(got["out"]["on"])
        self.assertFalse(got["out"]["off"])

    def test_f6_lands_on_the_map_itself_with_the_ring_showing(self):
        """From the side panel (keyboard_help.PaneSwitch): the container, not
        the zoom button or link that last had focus inside the page."""
        got = _run("currentMode = 'plant'; focusMapByKeyboard();"
                   " out.ring = container.classes['sp-keyboard'];"
                   " out.mark = mark();")
        self.assertIn(["focus"], got["calls"])
        self.assertTrue(got["out"]["ring"])
        self.assertEqual(got["out"]["mark"], "block")     # a tool is chosen

    def test_it_is_drawn_inside_the_edge_and_over_everything(self):
        got = _run("out.css = document.head.children.map("
                   "function (c) { return c.textContent; }).join(' ');")
        css = got["out"]["css"]
        self.assertIn(".leaflet-container:focus-visible::after", css)
        self.assertIn(".leaflet-container.sp-keyboard:focus::after", css)
        rule = css[css.index(".leaflet-container:focus-visible::after"):]
        # Inset 0 on every side: Leaflet's own outline sits outside and is lost.
        for side in ("left: 0", "top: 0", "right: 0", "bottom: 0"):
            self.assertIn(side, rule)
        # Above Leaflet's controls (z-index 1000), and never in a click's way.
        self.assertIn("z-index: 1100", rule)
        self.assertIn("pointer-events: none", rule)


@unittest.skipIf(_node() is None, "no node binary")
class TestWhatTheMapSaysAboutItself(unittest.TestCase):

    def test_a_screen_reader_hears_how_to_use_it(self):
        got = _run("out.role = container.attrs.role;"
                   " out.label = container.attrs['aria-label'];")
        self.assertEqual(got["out"]["role"], "application")
        self.assertIn("Enter", got["out"]["label"])
        self.assertIn("Arrow keys", got["out"]["label"])
        self.assertIn("F6", got["out"]["label"])        # and how to leave


class TestTheScriptIsLoaded(unittest.TestCase):

    def test_map_html_loads_it_after_the_footprint_and_core_calls_it(self):
        html = (_ROOT / "html" / "map.html").read_text(encoding="utf-8")
        self.assertLess(html.index("map/08-footprint.js"),
                        html.index("map/09-keyboard.js"))
        core = (_MAP / "01-core.js").read_text(encoding="utf-8")
        self.assertIn("initMapKeyboard()", core)
        self.assertIn("function finishDrawing()", core)
        features = (_MAP / "05-features.js").read_text(encoding="utf-8")
        self.assertIn("syncCentreMark()", features)


if __name__ == "__main__":
    unittest.main()

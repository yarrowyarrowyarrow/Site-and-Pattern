"""
tests/test_plant_key.py — one colour scheme for plants, and a legend that says
it (F195, V3.03).

Until V3.03 a marker was outlined in its own pale fill colour (1.0:1 to 2.1:1
against the yard), community members were coloured by layer until the design
was reopened, the community builder had a third table of its own, and the map
legend listed six of the twelve types. ``html/map/10-plant-key.js`` now holds
the colour table, the outline rule and the legend; it is run here in node, the
way ``test_map_keyboard`` runs 09-keyboard.js.
"""

import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_ROOT = pathlib.Path(__file__).resolve().parent.parent
_MAP = _ROOT / "html" / "map"
_KEY = (_MAP / "10-plant-key.js").read_text(encoding="utf-8")

#: The yard as drawn: #4caf50 at 18% over the plain basemap (measured on
#: screen at 1366 x 768, V3.03).
_YARD = (195, 213, 195)


def _node():
    return shutil.which("node") or shutil.which("nodejs")


def _run(steps: str):
    """Run 10-plant-key.js, then ``steps``; return what they put in ``out``."""
    stubs = r"""
var elements = {plants: {innerHTML: ''}};
var document = {getElementById: function (id) {
  return id === 'legend-plants' ? elements.plants : null; }};
"""
    script = "\n".join([stubs, _KEY, "var out = {};", steps,
                        "console.log(JSON.stringify(out));"])
    proc = subprocess.run([_node(), "-e", script], capture_output=True,
                          text=True, timeout=60, encoding="utf-8")
    if proc.returncode != 0:
        raise AssertionError(f"node failed: {proc.stderr}")
    return json.loads(proc.stdout)


def _hex(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def _lum(c):
    def ch(v):
        v /= 255
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    return 0.2126 * ch(c[0]) + 0.7152 * ch(c[1]) + 0.0722 * ch(c[2])


def _contrast(a, b):
    la, lb = sorted([_lum(a), _lum(b)], reverse=True)
    return (la + 0.05) / (lb + 0.05)


def _over(top, alpha, under):
    return tuple(round(alpha * t + (1 - alpha) * u) for t, u in zip(top, under))


class TestTheTablesAgree(unittest.TestCase):
    """The map's copies of the Python tables, which a comment had asked to be
    kept in sync since V1.87 and nothing checked."""

    def test_the_colours_are_member_colors_type_colors(self):
        from src.member_colors import TYPE_COLORS
        block = _KEY[_KEY.index("var TYPE_COLORS = {"):]
        block = block[:block.index("};")]
        js = dict(re.findall(r"'(\w+)':\s*'(#[0-9a-fA-F]{6})'", block))
        self.assertEqual(js, TYPE_COLORS)

    def test_the_words_are_the_type_filters_in_its_order(self):
        from src.plant_facets import _TYPE_LABELS
        block = _KEY[_KEY.index("var TYPE_WORDS = ["):]
        block = block[:block.index("];")]
        js = re.findall(r"\['(\w+)',\s*'([^']+)'\]", block)
        self.assertEqual(js, list(_TYPE_LABELS.items()))

    def test_every_word_has_a_colour(self):
        from src.member_colors import TYPE_COLORS
        from src.plant_facets import _TYPE_LABELS
        self.assertEqual(set(_TYPE_LABELS) - set(TYPE_COLORS), set())


@unittest.skipIf(_node() is None, "no node binary")
class TestTheOutline(unittest.TestCase):

    def _edges(self):
        from src.member_colors import TYPE_COLORS
        got = _run("out.edges = {};"
                   " Object.keys(TYPE_COLORS).forEach(function (k) {"
                   "   out.edges[k] = markerEdge(TYPE_COLORS[k]); });")
        return TYPE_COLORS, got["edges"]

    def test_every_type_clears_3_to_1_on_the_yard(self):
        colours, edges = self._edges()
        for kind, edge in edges.items():
            with self.subTest(kind=kind, edge=edge):
                self.assertGreaterEqual(_contrast(_hex(edge), _YARD), 3.0)

    def test_every_type_clears_3_to_1_under_a_trees_canopy(self):
        """A community's small members sit on its tree's canopy disc; on
        V3.02 they measured 1.0 to 1.8:1 there."""
        colours, edges = self._edges()
        canopy = _over(_hex(colours["tree"]), 0.35, _YARD)
        for kind, edge in edges.items():
            with self.subTest(kind=kind):
                self.assertGreaterEqual(_contrast(_hex(edge), canopy), 3.0)

    def test_the_old_outline_did_not(self):
        """The rule this replaced: the fill colour itself."""
        colours, _ = self._edges()
        self.assertLess(_contrast(_hex(colours["grass"]), _YARD), 1.1)

    def test_one_style_for_every_marker(self):
        got = _run("out.s = plantMarkerStyle('#ab47bc');"
                   " out.edge = markerEdge('#ab47bc');"
                   " out.mine = plantColour({customColor: '#123456', plantType: 'tree'});"
                   " out.typed = plantColour({plantType: 'grass'});"
                   " out.bad = markerEdge('nonsense');")
        self.assertEqual(got["s"], {"color": got["edge"], "weight": 2,
                                    "fillColor": "#ab47bc", "fillOpacity": 0.35})
        self.assertEqual(got["edge"], "#441c4b")      # 60% darker, same hue
        self.assertEqual(got["mine"], "#123456")      # your colour wins
        self.assertEqual(got["typed"], "#cddc39")
        self.assertTrue(got["bad"].startswith("#"))


@unittest.skipIf(_node() is None, "no node binary")
class TestTheLegend(unittest.TestCase):

    def test_it_lists_every_type_in_its_colour(self):
        from src.member_colors import TYPE_COLORS
        from src.plant_facets import _TYPE_LABELS
        html = _run("out.html = elements.plants.innerHTML;")["html"]
        for kind, words in _TYPE_LABELS.items():
            with self.subTest(kind=kind):
                self.assertIn(words, html)
                self.assertIn("background:" + TYPE_COLORS[kind], html)
        # Wildflowers, purple, 11 of the example's 19 plants: not in the
        # V3.02 legend at all.
        self.assertIn("Wildflower", html)
        self.assertIn("own colour", html)

    def test_the_dashed_ring_is_named_for_what_draws_it(self):
        """V3.02's legend called it "Community outline", and nothing on the
        map draws one: the dashed light-green ring is the Canopy view's and
        the placing footprint's."""
        html = _run("out.html = elements.plants.innerHTML;")["html"]
        self.assertNotIn("Community outline", html)
        self.assertIn("Mature spread, with Canopy on", html)
        for script in ("04-tools.js", "08-footprint.js"):
            with self.subTest(script=script):
                self.assertIn("color: '#a5d6a7'", (_MAP / script).read_text(encoding="utf-8"))

    def test_map_html_holds_the_hook_and_loads_the_script_last(self):
        page = (_ROOT / "html" / "map.html").read_text(encoding="utf-8")
        self.assertIn('id="legend-plants"', page)
        self.assertNotIn("Vegetation Layers", page)
        self.assertLess(page.index('src="map/09-keyboard.js"'),
                        page.index('src="map/10-plant-key.js"'))
        # The close control is a button, so the keyboard reaches it.
        self.assertIn('<button class="legend-close"', page)


_LEAFLET = _ROOT / "html" / "vendor" / "leaflet" / "leaflet.js"


def _project_circles(with_key: bool):
    """``[[radius_m, width_px, height_px], …]`` for small circles around the
    example yard at zoom 22.9, projected by the vendored Leaflet itself, with
    or without 10-plant-key.js loaded after it."""
    script = r"""
var screen = {}, devicePixelRatio = 1;
var navigator = {userAgent: 'node', platform: '', maxTouchPoints: 0};
var document = {documentElement: {style: {}}, addEventListener: function () {},
  createElement: function () { return {getContext: function () { return null; },
                                       style: {}}; }};
var window = {screen: screen, navigator: navigator, document: document,
              devicePixelRatio: 1};
var module = {exports: {}};
(new Function('exports', 'module', 'window', 'document', 'navigator', 'screen',
  @@LEAFLET@@))(module.exports, module, window, document, navigator, screen);
var L = module.exports;
@@KEY@@
var crs = L.CRS.EPSG3857, zoom = 22.9, out = [];
var map = {options: {crs: crs},
  project: function (ll) { return crs.latLngToPoint(L.latLng(ll), zoom); },
  unproject: function (p) { return crs.pointToLatLng(L.point(p), zoom); },
  getPixelOrigin: function () { return L.point(0, 0); }};
[[53.5461, -113.4938], [53.54615, -113.49391], [53.54607, -113.49372]]
  .forEach(function (at) {
    [0.1, 0.15, 0.25, 1.25].forEach(function (r) {
      var c = L.circle(at, {radius: r});
      c._map = map;
      c._clickTolerance = function () { return 0; };
      c._project();
      out.push([r, c._radius, c._radiusY]);
    });
  });
console.log(JSON.stringify(out));
"""
    script = (script.replace("@@KEY@@", _KEY if with_key else "")
                    .replace("@@LEAFLET@@",
                             json.dumps(_LEAFLET.read_text(encoding="utf-8"))))
    # On stdin: Leaflet is past the 128 KB a single argument may be.
    proc = subprocess.run([_node(), "-"], input=script, capture_output=True,
                          text=True, timeout=60, encoding="utf-8")
    if proc.returncode != 0:
        raise AssertionError(f"node failed: {proc.stderr[-500:]}")
    return json.loads(proc.stdout)


@unittest.skipIf(_node() is None, "no node binary")
class TestAPlantIsDrawnRound(unittest.TestCase):
    """Leaflet 1.9 drew a 0.1 m plant 4.75 px wide and 8.42 tall at the
    example's zoom, and its neighbour 8.23 wide: a meadow of ellipses. Run
    against the vendored Leaflet, so an upgrade that fixes or changes it shows
    up here."""

    def test_leaflet_alone_draws_small_circles_as_ellipses(self):
        worst = max(abs(w - h) / h for _r, w, h in _project_circles(False))
        self.assertGreater(worst, 0.3)

    def test_with_the_key_every_circle_is_as_wide_as_it_is_tall(self):
        for r, w, h in _project_circles(True):
            with self.subTest(radius_m=r):
                self.assertAlmostEqual(w, h, places=6)

    def test_the_size_is_the_one_the_height_always_had(self):
        before = _project_circles(False)
        after = _project_circles(True)
        self.assertEqual([h for _r, _w, h in before], [h for _r, _w, h in after])


class TestEveryMarkerIsStyledByTheKey(unittest.TestCase):

    def test_no_other_script_reads_the_colour_table(self):
        for path in sorted(_MAP.glob("*.js")):
            if path.name == "10-plant-key.js":
                continue
            with self.subTest(script=path.name):
                self.assertNotIn("TYPE_COLORS[", path.read_text(encoding="utf-8"))

    def test_placing_selecting_and_restoring_go_through_it(self):
        plants = (_MAP / "03-plants.js").read_text(encoding="utf-8")
        core = (_MAP / "01-core.js").read_text(encoding="utf-8")
        self.assertIn("plantMarkerStyle(color)", plants)          # placing
        self.assertIn("plantMarkerStyle(newColor)", plants)       # recolour
        self.assertIn("plantMarkerStyle(plantColour(", core)      # deselect


class TestPythonsColour(unittest.TestCase):

    def test_your_colour_then_the_type_then_a_default(self):
        from src.member_colors import DEFAULT_COLOR, TYPE_COLORS, plant_color
        self.assertEqual(plant_color({"marker_color": "#123456",
                                      "plant_type": "tree"}), "#123456")
        self.assertEqual(plant_color({"plant_type": "wildflower"}),
                         TYPE_COLORS["wildflower"])
        self.assertEqual(plant_color({"plant_type": "unheard-of"}), DEFAULT_COLOR)
        self.assertEqual(plant_color(None), DEFAULT_COLOR)

    def test_the_layer_tables_are_gone(self):
        import src.member_colors as mc
        for name in ("LAYER_COLORS", "FUNCTION_COLORS", "member_color"):
            self.assertFalse(hasattr(mc, name), name)

    def test_the_builders_canvas_reads_on_its_dark_ground(self):
        """The builder draws on #0d1f0d and now in the type colours, which run
        down to rush brown: its edges are lightened, not darkened."""
        try:
            from PyQt6.QtGui import QColor
        except Exception:                                     # noqa: BLE001
            self.skipTest("PyQt6 not installed in this env")
        from src.member_colors import TYPE_COLORS
        ground = _hex("#0d1f0d")
        for kind, colour in TYPE_COLORS.items():
            edge = QColor(colour).lighter(170)
            with self.subTest(kind=kind):
                self.assertGreaterEqual(
                    _contrast((edge.red(), edge.green(), edge.blue()), ground), 3.0)
        source = (_ROOT / "src" / "polyculture_panel.py").read_text(encoding="utf-8")
        self.assertIn("color.lighter(170)", source)
        self.assertIn("return plant_color(plant)", source)


if __name__ == "__main__":
    unittest.main()

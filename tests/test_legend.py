"""
tests/test_legend.py — the legend names what is on the map, at the detail
asked for (F217, V3.11).

The owner: "I also liked the idea of hiding anything from the legend that does
not appear on the map as those are superfluous and distracting", boundaries
"simply saying 'boundary'" or by the names given them ("city park land",
"private lot"), and plants "simple (ie. tree, shrub, etc.) or go down to the
species level", the latter "a bit more automatic".

Until V3.11 the legend was a fixed list in map.html: every entry whether drawn
or not, all eleven plant types, and a Structures section that was not true
(category colours no structure is drawn in; an "Animal" category that no
longer exists). ``html/map/12-legend.js`` builds it from what is drawn, in
three parts, two of them pure, so node runs them here; the browser half runs
the real page (``html/legend_probe.html``) in headless Chromium.

F218: "I didn't realize there were numbers as I did not zoom in enough." The
species numbers are laid out at every zoom by ``html/map/13-species-numbers.js``
(``numberGroups``, pure, run here too), and a species line rings its plants.
"""

import json
import os
import pathlib
import shutil
import subprocess
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_ROOT = pathlib.Path(__file__).resolve().parent.parent
_MAP = _ROOT / "html" / "map"


def _node():
    return shutil.which("node") or shutil.which("nodejs")


def _run(steps: str):
    """10-plant-key.js, 12-legend.js and 13-species-numbers.js, then
    ``steps``; what they put in ``out``."""
    script = "\n".join([
        (_MAP / "10-plant-key.js").read_text(encoding="utf-8"),
        (_MAP / "12-legend.js").read_text(encoding="utf-8"),
        (_MAP / "13-species-numbers.js").read_text(encoding="utf-8"),
        "var out = {};", steps, "console.log(JSON.stringify(out));"])
    proc = subprocess.run([_node(), "-"], input=script, capture_output=True,
                          text=True, timeout=60, encoding="utf-8")
    if proc.returncode != 0:
        raise AssertionError(f"node failed: {proc.stderr}")
    return json.loads(proc.stdout)


def _model(snap: dict, plants="type", boundaries="simple"):
    """legendModel as {section key: [label, …]}, plus the raw sections."""
    got = _run(f"out.s = legendModel({json.dumps(snap)}, "
               f"{{plants: {json.dumps(plants)}, boundaries: {json.dumps(boundaries)}}});")
    return {s["key"]: [i["label"] for i in s["items"]] for s in got["s"]}, got["s"]


_PLANTS = [
    {"id": 42, "name": "Wild Bergamot", "type": "wildflower", "colour": "#ab47bc", "custom": False},
    {"id": 42, "name": "Wild Bergamot", "type": "wildflower", "colour": "#ab47bc", "custom": False},
    {"id": 3, "name": "Bur Oak", "type": "tree", "colour": "#2e7d32", "custom": False},
    {"id": 11, "name": "Prairie Smoke", "type": "wildflower", "colour": "#ff5722", "custom": True},
    {"id": 7, "name": "harebell", "type": "wildflower", "colour": "#ab47bc", "custom": False},
]


@unittest.skipIf(_node() is None, "no node binary")
class TestOnlyWhatIsDrawn(unittest.TestCase):

    def test_an_empty_map_says_so(self):
        got = _run("out.s = legendModel({}, legendDetail); out.h = legendHtml(out.s);")
        self.assertEqual(got["s"], [])
        self.assertIn("Nothing on the map yet.", got["h"])

    def test_only_the_types_drawn_in_the_type_filters_order(self):
        labels, _ = _model({"plants": _PLANTS})
        # Tree before Wildflower (the Type filter's order), no Shrub, Grass, …
        # and the plant given its own colour by name, since no type explains it.
        self.assertEqual(labels["plants"], ["Tree", "Wildflower", "Prairie Smoke"])

    def test_the_canopy_ring_only_while_drawn(self):
        on, _ = _model({"plants": _PLANTS, "canopy": True})
        off, _ = _model({"plants": _PLANTS, "canopy": False})
        self.assertEqual(on["plants"][-1], "Mature spread (Canopy view)")
        self.assertNotIn("Mature spread (Canopy view)", off["plants"])
        self.assertNotIn("plants", _model({"canopy": True})[0])

    def test_every_kind_appears_only_when_there(self):
        snap = {"structures": [{"name": "Pond", "icon": "💧", "stroke": "#1565c0",
                                "fill": "#42a5f5", "round": True}] * 2,
                "hedgerows": [{"label": "Fence", "colour": "#795548", "dashed": True}],
                "shapes": [{"label": "Building (OSM)", "stroke": "#546e7a",
                            "fill": "#90a4ae", "dashed": True, "casts": True}],
                "measurements": 3,
                "analysis": {"sun": True, "shade": False, "contour": "#44cc00", "wind": False}}
        labels, _ = _model(snap)
        self.assertEqual(labels, {
            "structures": ["💧 Pond"],                       # two ponds, one line
            "other": ["Fence", "Building (OSM), casts shade", "Measurement"],
            "analysis": ["Sun path", "Contour"]})

    def test_the_old_fixed_entries_are_gone_from_the_page(self):
        page = (_ROOT / "html" / "map.html").read_text(encoding="utf-8")
        legend = page[page.index('<div id="map-legend">'):page.index("<!-- Leaflet JS")]
        for stale in ("Animal", "Infrastructure", "Custom shape", "legend-item"):
            with self.subTest(stale=stale):
                self.assertNotIn(stale, legend)
        self.assertIn('<div id="legend-body"></div>', legend)


@unittest.skipIf(_node() is None, "no node binary")
class TestSpecies(unittest.TestCase):

    def test_numbered_counted_and_in_the_planting_plans_order(self):
        labels, sections = _model({"plants": _PLANTS}, plants="species")
        items = sections[0]["items"]
        self.assertEqual([(i["num"], i["label"], i["count"]) for i in items],
                         [(1, "Bur Oak", 1), (2, "harebell", 1),
                          (3, "Prairie Smoke", 1), (4, "Wild Bergamot", 2)])
        # Each in its own colour: its type's, or the one you gave it.
        self.assertEqual([i["swatch"]["colour"] for i in items],
                         ["#2e7d32", "#ab47bc", "#ff5722", "#ab47bc"])

    def test_the_numbers_are_the_printed_planting_plans(self):
        """The page's numbering against src/planting_map.py's, which keys the
        PDF's planting map to the buy list: one species, one number, three
        places."""
        from src.planting_map import _numbering
        placed = [{"plant_id": 42, "common_name": "Wild Bergamot"},
                  {"plant_id": 3, "common_name": "Bur Oak"},
                  {"plant_id": 9, "common_name": "bur oak"},     # same name, lower id wins
                  {"plant_id": 7, "common_name": "Harebell"},
                  {"plant_id": 5, "common_name": "Žluťoučký kůň"},
                  {"plant_id": 8, "common_name": "Aster, Smooth"},
                  {"plant_id": 42, "common_name": "Wild Bergamot"}]
        py = _numbering(placed, None, None)
        js = _run("out.n = speciesNumbers(" + json.dumps(
            [{"id": p["plant_id"], "name": p["common_name"]} for p in placed]) + ");")["n"]
        self.assertEqual({int(k): v for k, v in js.items()}, py)


def _groups(points, **opts):
    """numberGroups (13-species-numbers.js) on plain points."""
    return _run(f"out.g = numberGroups({json.dumps(points)}, {json.dumps(opts)});")["g"]


def _plant(key, species, num, x, y, r=3):
    return {"key": key, "id": species, "num": num, "x": x, "y": y, "r": r}


@unittest.skipIf(_node() is None, "no node binary")
class TestNumbersAtEveryZoom(unittest.TestCase):
    """F218. The owner, of the first Species legend: "I didn't realize there
    were numbers as I did not zoom in enough." A number was drawn only on a
    plant at least 7 px across on screen, so at a whole yard's zoom there were
    none, and nothing said so. Where they go is worked out in screen pixels by
    a pure function, run here."""

    def test_a_plant_big_enough_holds_its_own_number(self):
        g = _groups([_plant("a", "3", 1, 100, 100, r=20), _plant("b", "3", 1, 160, 100, r=20)])
        self.assertEqual([(t["key"], t["dx"], t["dy"], t["members"]) for t in g["tags"]],
                         [("a", 0, 0, ["a"]), ("b", 0, 0, ["b"])])
        self.assertEqual(g["hidden"], 0)

    def test_a_drift_of_small_plants_shares_one_number_on_its_middle_plant(self):
        drift = [_plant(f"a{i}", "7", 7, 100 + 6 * i, 100 + 4 * (i % 2)) for i in range(5)]
        g = _groups(drift)
        self.assertEqual([(t["key"], sorted(t["members"])) for t in g["tags"]],
                         [("a2", ["a0", "a1", "a2", "a3", "a4"])])

    def test_far_apart_the_same_species_is_numbered_twice(self):
        g = _groups([_plant("a", "7", 7, 100, 100), _plant("b", "7", 7, 104, 102),
                     _plant("c", "7", 7, 220, 100)])
        self.assertEqual(sorted(sorted(t["members"]) for t in g["tags"]), [["a", "b"], ["c"]])

    def test_two_species_never_share_a_number(self):
        mixed = [_plant("a1", "1", 1, 100, 100), _plant("b1", "2", 2, 104, 100),
                 _plant("a2", "1", 1, 108, 100), _plant("b2", "2", 2, 112, 100)]
        g = _groups(mixed)
        self.assertEqual({t["num"]: sorted(t["members"]) for t in g["tags"]},
                         {1: ["a1", "a2"], 2: ["b1", "b2"]})

    def test_none_covers_another_none_strays_and_none_is_lost_silently(self):
        crowd = [_plant(f"c{s}", str(s), s, 50 + s % 3, 50 + s % 2) for s in range(1, 13)]
        g = _groups(crowd)
        self.assertGreater(g["hidden"], 0)
        self.assertEqual(len(g["tags"]) + g["hidden"], 12)
        boxes = [(t["x"] - t["w"] / 2, t["y"] - 8, t["x"] + t["w"] / 2, t["y"] + 8)
                 for t in g["tags"]]
        for i, a in enumerate(boxes):
            for b in boxes[i + 1:]:
                self.assertFalse(a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3],
                                 f"{a} covers {b}")
        for t in g["tags"]:                     # beside its plant: one step at most
            self.assertLessEqual(abs(t["dx"]), t["w"] + 2)
            self.assertLessEqual(abs(t["dy"]), 18)

    def test_a_plants_own_number_keeps_its_middle(self):
        """A drift of five round a shrub's middle would otherwise put its
        number there, where it reads as the shrub's."""
        drift = [_plant(f"g{i}", "2", 2, 100 + d, 100) for i, d in enumerate((-8, -4, 0, 4, 8))]
        g = _groups(drift + [_plant("s", "9", 9, 100, 100, r=30)])
        where = {t["num"]: (t["dx"], t["dy"]) for t in g["tags"]}
        self.assertEqual(where[9], (0, 0))
        self.assertNotEqual(where[2], (0, 0))

    def test_a_label_on_the_map_is_avoided_when_there_is_room_and_covered_when_not(self):
        small = _groups([_plant("a", "1", 1, 100, 100)], labels=[[92, 94, 108, 106]])
        self.assertNotEqual((small["tags"][0]["dx"], small["tags"][0]["dy"]), (0, 0))
        # A small yard's labels are bigger than it: covering beats hiding.
        huge = _groups([_plant("a", "1", 1, 100, 100)], labels=[[0, 0, 300, 300]])
        self.assertEqual((huge["tags"][0]["dx"], huge["tags"][0]["dy"], huge["hidden"]), (0, 0, 0))

    def test_the_same_map_lays_out_the_same(self):
        pts = [_plant(f"p{i}", str(i % 5), i % 5 + 1, (i * 37) % 200, (i * 53) % 150,
                      r=(i % 4) * 4) for i in range(40)]
        self.assertEqual(_groups(pts), _groups(pts))

    def test_the_old_rule_is_gone(self):
        js = (_MAP / "12-legend.js").read_text(encoding="utf-8")
        self.assertNotIn("_NUMBER_MIN_RADIUS_PX", js)
        self.assertNotIn("setOpacity", js)


@unittest.skipIf(_node() is None, "no node binary")
class TestBoundaries(unittest.TestCase):

    _B = [{"id": "b1", "colour": "#4caf50", "name": ""},
          {"id": "b2", "colour": "#2196f3", "name": "Private lot"},
          {"id": "b3", "colour": "#2196f3", "name": "Private lot"},
          {"id": "b4", "colour": "#2196f3", "name": ""}]

    def test_simple_is_one_line_with_a_swatch_per_colour(self):
        _, sections = _model({"boundaries": self._B})
        items = sections[0]["items"]
        self.assertEqual([i["label"] for i in items], ["Boundary"])
        self.assertEqual([s["colour"] for s in items[0]["swatches"]], ["#4caf50", "#2196f3"])
        self.assertNotIn("ids", items[0])

    def test_named_is_a_line_per_colour_and_name_naming_every_boundary_on_it(self):
        _, sections = _model({"boundaries": self._B}, boundaries="named")
        self.assertEqual([(i["label"], i["ids"]) for i in sections[0]["items"]],
                         [("Boundary", ["b1"]), ("Private lot", ["b2", "b3"]),
                          ("Boundary", ["b4"])])

    def test_each_section_carries_its_switch(self):
        _, sections = _model({"plants": _PLANTS, "boundaries": self._B},
                             plants="species", boundaries="named")
        self.assertEqual([(s["key"], s["value"], [o[0] for o in s["options"]])
                          for s in sections],
                         [("plants", "species", ["type", "species"]),
                          ("boundaries", "named", ["simple", "named"])])


@unittest.skipIf(_node() is None, "no node binary")
class TestTheHtml(unittest.TestCase):

    def _html(self, snap, plants="type", boundaries="simple"):
        return _run(f"out.t = []; out.h = legendHtml(legendModel({json.dumps(snap)}, "
                    f"{{plants: {json.dumps(plants)}, boundaries: {json.dumps(boundaries)}}}), out.t);")

    def test_a_name_is_text_never_markup(self):
        got = self._html({"boundaries": [{"id": "b1", "colour": "#4caf50",
                                          "name": '<img src=x onerror="alert(1)">'}]},
                         boundaries="named")
        self.assertNotIn("<img", got["h"])
        self.assertIn("&lt;img src=x onerror=&quot;alert(1)&quot;&gt;", got["h"])
        self.assertEqual(got["t"], [{"ids": ["b1"], "name": '<img src=x onerror="alert(1)">'}])

    def test_a_colour_from_a_file_cannot_write_style(self):
        got = self._html({"shapes": [{"label": "Bed", "stroke": "red;background:url(x)",
                                      "fill": "#8d6e63", "dashed": False, "casts": False}]})
        self.assertNotIn("url(x)", got["h"])
        self.assertIn("#888888", got["h"])

    def test_switches_are_buttons_saying_which_is_on(self):
        got = self._html({"plants": _PLANTS}, plants="species")
        self.assertIn('data-legend="plants" data-value="species" aria-pressed="true"', got["h"])
        self.assertIn('data-legend="plants" data-value="type" aria-pressed="false"', got["h"])
        self.assertIn('<b class="legend-num">1</b> Bur Oak', got["h"])

    def test_a_species_is_a_button_that_finds_its_plants(self):
        got = self._html({"plants": _PLANTS}, plants="species")
        self.assertIn('class="legend-item legend-find" data-find="42" aria-pressed="false"',
                      got["h"])
        self.assertIn('aria-label="Show on the map: 4 Wild Bergamot, 2 plants"', got["h"])
        self.assertIn('aria-label="Show on the map: 1 Bur Oak, 1 plant"', got["h"])
        self.assertNotIn("data-find", self._html({"plants": _PLANTS})["h"])

    def test_a_named_line_is_a_button_with_a_name_a_screen_reader_says(self):
        got = self._html({"boundaries": [{"id": "b1", "colour": "#4caf50", "name": "Lot"}]},
                         boundaries="named")
        self.assertIn('class="legend-item legend-name" data-item="0"', got["h"])
        self.assertIn('aria-label="Name it: Lot"', got["h"])

    def test_no_text_under_twelve_pixels(self):
        css = (_ROOT / "html" / "map.html").read_text(encoding="utf-8")
        block = css[css.index("V3.11 (F217)"):css.index(".sp-species-num")]
        for size in __import__("re").findall(r"font-size:\s*(\d+)px", block):
            self.assertGreaterEqual(int(size), 12)


class TestTheSwitchesAreRemembered(unittest.TestCase):

    def test_normalise_keeps_known_values_and_defaults_the_rest(self):
        from src.legend_flow import normalise
        self.assertEqual(normalise("species", "named"), ("species", "named"))
        self.assertEqual(normalise(" Species ", "NAMED"), ("species", "named"))
        self.assertEqual(normalise(None, 42), ("type", "simple"))
        self.assertEqual(normalise("everything", ""), ("type", "simple"))

    def test_the_page_loads_the_legend_and_its_numbers_last_and_the_shape_edit_where_it_was(self):
        page = (_ROOT / "html" / "map.html").read_text(encoding="utf-8")
        order = [line.split('"')[1] for line in page.splitlines()
                 if '<script src="map/' in line]
        self.assertEqual(order[-2:], ["map/12-legend.js", "map/13-species-numbers.js"])
        self.assertEqual(order.index("map/02b-shape-edit.js"),
                         order.index("map/02-boundary.js") + 1)


def _chromium():
    from tests.test_scene3d_render import _find_chromium
    return _find_chromium()


@unittest.skipIf(_chromium() is None, "no Chromium binary (set CHROME= to run this gate)")
class OnTheMap(unittest.TestCase):
    m = None

    @classmethod
    def setUpClass(cls):
        from tests.test_boundary_press import _run_probe
        cls.m = _run_probe("legend_probe.html")

    def setUp(self):
        self.assertNotIn("error", self.m, self.m.get("error"))

    def test_empty_then_only_what_is_drawn(self):
        self.assertEqual(self.m["empty"], {"_note": "Nothing on the map yet."})
        self.assertEqual(self.m["by_type"], {"plants": ["Tree", "Wildflower", "Prairie Smoke"]})

    def test_everything_drawn_is_named(self):
        self.assertEqual(self.m["everything"], {
            "plants": ["Tree", "Wildflower", "Prairie Smoke"],
            "boundaries": ["Boundary"],
            "structures": ["💧 Pond", "🌲 Existing tree, coniferous"],
            "other": ["Fence", "Shed", "Building (OSM), casts shade", "Measurement"]})

    def test_hidden_with_the_view_bar_it_leaves_the_legend(self):
        self.assertFalse(self.m["boundaries_hidden"])
        self.assertFalse(self.m["measure_hidden"])
        self.assertFalse(self.m["plants_hidden"])
        self.assertEqual((self.m["canopy_on"], self.m["canopy_off"]), (1, 0))

    def test_simple_boundaries(self):
        self.assertEqual(self.m["boundaries_simple"], {"lines": ["Boundary"], "swatches": 2})

    def test_species_numbered_on_the_map_and_remembered(self):
        s = self.m["species"]
        self.assertEqual(s["lines"], ["1 Bur Oak ×1", "2 Harebell ×1",
                                      "3 Prairie Smoke ×1", "4 Wild Bergamot ×2"])
        self.assertEqual(s["told"], [["species", "simple"]])
        self.assertEqual(s["focus"], "species", "the switch lost the keyboard")
        # A white tag, so it reads on a satellite photo, at the 12 px floor.
        self.assertEqual(s["look"], ["rgb(255, 255, 255)", "12px"])
        self.assertTrue(self.m["follows"], "a dragged plant left its number behind")

    def test_close_in_every_plant_holds_its_own_number(self):
        own = self.m["own"]
        self.assertEqual(own["numbers"], ["1", "2", "3", "4", "4"])
        self.assertLess(own["off"], 1.0, "a number is not on the plant it names")
        self.assertIsNone(own["note"])

    def test_further_out_a_close_pair_shares_one_number(self):
        """F218: at this zoom every plant was under 7 px and none had one."""
        g = self.m["grouped"]
        self.assertEqual(g["numbers"], ["1", "2", "3", "4"])
        self.assertEqual(g["bergamot"], [2], "the two Wild Bergamots did not share one")
        self.assertEqual(g["overlapping"], 0)
        self.assertIsNone(g["note"])

    def test_crowded_none_covers_another_and_the_legend_counts_the_rest(self):
        c = self.m["crowded"]
        self.assertEqual(c["species"], 12)
        self.assertEqual(c["overlapping"], 0)
        waiting = c["species"] - c["tags"]
        self.assertGreater(waiting, 0)
        self.assertEqual(c["note"], f"Zoom in for {waiting} more number" +
                         ("" if waiting == 1 else "s"))
        self.assertIsNone(c["after"], "the note outlived the crowd")

    def test_a_species_in_the_legend_rings_its_plants(self):
        f = self.m["find"]
        self.assertEqual(f["buttons"], 4)
        self.assertEqual(f["label"], "Show on the map: 4 Wild Bergamot, 2 plants")
        # Two plants, a dark ring and a white one each, on the plants.
        self.assertEqual((f["hover"], f["on_plants"], f["left"]), (4, True, 0))
        self.assertEqual(f["pinned"], [4, "true"])
        self.assertEqual(f["rebuilt"], [4, "true"], "a rebuild let the kept species go")
        self.assertEqual((f["tabbed"], f["tabbed_away"]), (2, 4))
        self.assertGreaterEqual(f["far_radius"], 7, "a dot's ring is too small to find")
        self.assertEqual(f["unpinned"], [0, "false"])
        self.assertEqual(f["type"], [0, 0])
        self.assertEqual(f["species_again"], 0)

    def test_named_boundaries(self):
        n = self.m["named"]
        self.assertEqual(n["lines"], ["Boundary", "Boundary"])
        self.assertEqual(n["told"], ["species", "named"])
        self.assertEqual(n["after"], ["City park land", "Private lot"])
        self.assertEqual(n["asked"], [[["b2"], "Private lot"]])
        self.assertTrue(n["escaped"])
        self.assertEqual(n["grouped"], ["City park land", "Private lot"])
        self.assertEqual(n["asked_both"], [["b2", "b3"]])

    def test_closed_it_takes_its_numbers_and_rings_and_python_sets_it_back(self):
        self.assertEqual(self.m["open_rings"], 4)
        self.assertEqual((self.m["closed_numbers"], self.m["closed_rings"]), (0, 0))
        b = self.m["back"]
        self.assertEqual(b["detail"], {"plants": "type", "boundaries": "simple"})
        self.assertEqual(b["plants"], ["Tree", "Wildflower", "Prairie Smoke"])
        self.assertEqual(b["boundaries"], ["Boundary"])
        self.assertEqual(b["numbers"], 0)


if __name__ == "__main__":
    unittest.main()

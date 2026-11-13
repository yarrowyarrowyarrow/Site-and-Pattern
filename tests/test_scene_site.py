"""
tests/test_scene_site.py — what the ground is, in the 3D scene (V3.45, F262;
src/scene_site.py).

The V3.43 review, findings 2 and 3: a bed, mulch, a lawn, a path, a patio and
a pond were all one meadow texture running to the horizon; a hedge or a fence
was not in the scene; there was no street; a house was a tan box. These hold
the fields that say otherwise to their rules: one vocabulary of surfaces with
the tools that draw them, lawn inside the outline and pale outside (the
owner's D3), a street only where its side is known, and a roof that never
makes a building taller than it is recorded. Pure: no Qt, no database, no
browser.
"""

import json
import math
import os
import re
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import scene_site as S                               # noqa: E402
from src.scene_contract import build_scene                    # noqa: E402
from src.project_store import plant_feature                   # noqa: E402

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_LAT, _LNG = 53.5, -113.5
_KY = 111320.0
_KX = 111320.0 * math.cos(math.radians(_LAT))

# A 15 x 37 m lot about its own centre.
LOT = (-7.6, -18.3, 7.6, 18.3)


def _ll(x, y):
    return [_LNG + x / _KX, _LAT + y / _KY]


def _ring(x0, y0, x1, y1):
    r = [_ll(x, y) for x, y in ((x0, y0), (x1, y0), (x1, y1), (x0, y1))]
    return r + [r[0]]


def _outline():
    return {"type": "Feature",
            "geometry": {"type": "Polygon", "coordinates": [_ring(*LOT)]},
            "properties": {"element_type": "property_boundary"}}


def _shape(kind, box, **props):
    return {"type": "Feature",
            "geometry": {"type": "Polygon", "coordinates": [_ring(*box)]},
            "properties": {"element_type": "custom_shape", "shape_type": kind,
                           "fill_color": "#4caf50", **props}}


def _building(box, height=6.5):
    return {"type": "Feature",
            "geometry": {"type": "Polygon", "coordinates": [_ring(*box)]},
            "properties": {"element_type": "canopy_footprint",
                           "shape_type": "Building (OSM)", "height_m": height}}


def _line(style, points, **props):
    return {"type": "Feature",
            "geometry": {"type": "LineString",
                         "coordinates": [_ll(x, y) for x, y in points]},
            "properties": {"element_type": "hedgerow", "style": style,
                           "width_m": 1.5, **props}}


def _road(points, highway="residential", name="81 Avenue NW"):
    """A road line as ``frontage.store_roads`` keeps one with the design."""
    from src.frontage import ROAD_ELEMENT_TYPE
    return {"type": "Feature",
            "geometry": {"type": "LineString",
                         "coordinates": [_ll(x, y) for x, y in points]},
            "properties": {"element_type": ROAD_ELEMENT_TYPE,
                           "highway": highway, "name": name}}


def _project(*features, **site):
    return {"type": "FeatureCollection",
            "properties": {"site_config": dict(site)},
            "features": list(features)}


def _scene(project, **kw):
    return build_scene(project, get_plant=lambda _i: {}, wind=False, **kw)


def _site_js() -> str:
    with open(os.path.join(_ROOT, "html", "scene3d", "02c-site.js"),
              encoding="utf-8") as fh:
        return fh.read()


class OneVocabularyOfSurfaces(unittest.TestCase):
    """A shape type the tools can draw and the scene cannot name would be
    drawn as nothing, which is what all of them were until V3.45."""

    def test_every_type_the_shape_tool_offers_has_a_kind(self):
        from src.lawn_zones import ZONE_TYPES
        try:
            from src.shape_tool import AREA_PRESETS
            names = list(AREA_PRESETS)
        except Exception:                       # no Qt here: read the source
            src = open(os.path.join(_ROOT, "src", "shape_tool.py"),
                       encoding="utf-8").read()
            start = src.index("AREA_PRESETS = {")
            block = src[start:src.index("\n}\n", start)]
            names = re.findall(r'^\s+"([^"]+)":\s+\{', block, re.M)
        names += [z["label"] for z in ZONE_TYPES.values()]
        self.assertGreaterEqual(len(names), 12)
        for name in names:
            self.assertIn(name, S.SURFACE_KINDS, name)

    def test_every_shape_the_overview_measures_has_a_kind(self):
        from src.yard_overview import BED_SHAPES, NOT_PLANTED
        for name in BED_SHAPES + NOT_PLANTED:
            self.assertIn(name, S.SURFACE_KINDS, name)
            self.assertNotEqual(S.surface_kind(name), S.CUSTOM, name)

    def test_a_planted_shape_is_not_drawn_as_what_nobody_plants_in(self):
        """One vocabulary: the Overview's two lists must not land on one look
        (a bed drawn as paving, a path drawn as soil)."""
        from src.yard_overview import BED_SHAPES, NOT_PLANTED
        hard = {S.surface_kind(n) for n in ("Pathway", "Patio / Deck",
                                            "Water Feature")}
        for name in BED_SHAPES:
            self.assertNotIn(S.surface_kind(name), hard, name)
        self.assertEqual(S.surface_kind("Lawn Area"), "lawn")
        self.assertEqual(S.surface_kind("Lawn — to convert"), "lawn",
                         "it is lawn today, whatever is planned for it")
        self.assertNotEqual(S.surface_kind("Garden Bed"), "lawn")
        self.assertTrue(set(NOT_PLANTED) <= set(S.SURFACE_KINDS))

    def test_an_unknown_type_keeps_the_persons_colour(self):
        self.assertEqual(S.surface_kind("Sandbox"), S.CUSTOM)
        self.assertEqual(S.surface_kind(""), S.CUSTOM)
        self.assertEqual(S.surface_kind(None), S.CUSTOM)
        scene = _scene(_project(_shape("Sandbox", (0, 0, 3, 3),
                                       fill_color="#ffcc00")))
        row = scene["surfaces"][0]
        self.assertEqual((row["kind"], row["color"]), ("custom", "#ffcc00"))

    def test_the_viewer_has_a_look_for_every_kind(self):
        js = _site_js()
        block = js[js.index("const SURFACE_LOOK = {"):js.index("\n};\n")]
        looks = set(re.findall(r"^\s{2}(\w+):\s+\{", block, re.M))
        self.assertTrue(set(S.KINDS) <= looks, set(S.KINDS) - looks)
        # ... and for what is not the design: the ground and the street.
        self.assertTrue({"pale", "sidewalk", "road"} <= looks)

    def test_the_viewer_knows_every_kind_of_line(self):
        js = _site_js()
        self.assertIn("ln.kind === 'fence'", js)
        for kind in S.LINE_HEIGHT_M:
            if kind != "fence":
                self.assertRegex(js, rf"\b{kind}: 0x[0-9a-f]{{6}}", kind)


class TheGround(unittest.TestCase):

    def test_lawn_inside_the_outline_and_pale_outside(self):
        """The owner's D3."""
        scene = _scene(_project(_outline()))
        self.assertEqual(scene["ground"], S.GROUND_PALE)
        base = scene["surfaces"][0]
        self.assertEqual((base["kind"], base.get("base")), ("lawn", True))
        self.assertEqual(base["ring"], scene["boundary"])
        self.assertEqual(len(scene["surfaces"]), 1)

    def test_a_yard_with_no_outline_has_no_lawn_nobody_drew(self):
        """A pin and a bed: nothing says where the yard ends, so nothing is
        lawn but what was drawn as lawn."""
        scene = _scene(_project(_shape("Garden Bed", (0, 0, 4, 3))))
        self.assertEqual(scene["ground"], S.GROUND_PALE)
        self.assertEqual([s["kind"] for s in scene["surfaces"]], ["bed"])
        self.assertNotIn("base", scene["surfaces"][0])

    def test_a_walk_through_a_wild_community_is_a_meadow(self):
        project = _project(_outline())
        project["properties"]["reference_version"] = 3
        scene = _scene(project)
        self.assertEqual(scene["ground"], S.GROUND_MEADOW)
        self.assertEqual(scene["surfaces"], [])
        self.assertIsNone(scene["street"])

    def test_the_drawn_areas_come_in_the_order_they_were_drawn(self):
        scene = _scene(_project(
            _outline(),
            _shape("Garden Bed", (-7, -17, 1, -11), label="Front bed"),
            _shape("Pathway", (2, -18, 3.2, -9)),
            _shape("Water Feature", (-6, 10, -3, 13)),
            _shape("Mulch Area", (0, 8, 4, 12))))
        self.assertEqual([s["kind"] for s in scene["surfaces"]],
                         ["lawn", "bed", "path", "water", "mulch"])
        bed = scene["surfaces"][1]
        self.assertEqual(bed["label"], "Front bed")
        self.assertEqual(len(bed["ring"]), 4, "an open ring, like the outline")
        self.assertAlmostEqual(bed["ring"][0][0], -7.0, places=1)
        self.assertNotIn("color", bed, "a bed's colour is the viewer's")

    def test_a_shape_with_a_height_is_a_building_not_a_surface(self):
        scene = _scene(_project(_outline(), _building((-5, -9, 5, 3))))
        self.assertEqual([s["kind"] for s in scene["surfaces"]], ["lawn"])
        self.assertEqual(len(scene["buildings"]), 1)
        tall = _shape("Custom", (0, 0, 2, 2), height_m=3.0)
        self.assertEqual(S.surfaces(_project(tall), _Proj(), None), [])

    def test_it_is_plain_data(self):
        scene = _scene(_project(
            _outline(), _shape("Custom", (0, 0, 2, 2)),
            _line("fence", [(-7, 5), (-7, 18)]), street_side="south"))
        again = json.loads(json.dumps(scene))
        for key in ("ground", "surfaces", "lines", "street"):
            self.assertEqual(again[key], scene[key], key)


class _Proj:
    """A projector that reads [lng, lat] as metres, for the unit tests."""

    def to_xy(self, lat, lng):
        return (lng - _LNG) * _KX, (lat - _LAT) * _KY


class TheLines(unittest.TestCase):

    def test_a_fence_and_a_hedge_reach_the_scene(self):
        scene = _scene(_project(
            _outline(), _line("fence", [(-7.6, 3), (-7.6, 18.3), (0, 18.3)]),
            _line("hedge", [(7, 4), (7, 12)], width_m=1.0)))
        fence, hedge = scene["lines"]
        self.assertEqual(fence["kind"], "fence")
        self.assertEqual(len(fence["points"]), 3)
        self.assertAlmostEqual(fence["points"][1][1], 18.3, places=1)
        self.assertEqual((hedge["kind"], hedge["width_m"]), ("hedge", 1.0))

    def test_a_height_is_one_estimate_a_kind(self):
        """Nothing in a design records how tall a hedge or a fence is."""
        self.assertEqual(sorted(S.LINE_HEIGHT_M),
                         ["fence", "hedge", "living_fence", "windbreak"])
        try:
            from src.shape_tool import LINE_KINDS
            styles = {style for _w, style in LINE_KINDS}
        except Exception:                       # no Qt here: read the source
            src = open(os.path.join(_ROOT, "src", "shape_tool.py"),
                       encoding="utf-8").read()
            start = src.index("LINE_KINDS = (")
            block = src[start:src.index("\n)\n", start)]
            styles = set(re.findall(r'\("[^"]+", "(\w+)"\)', block))
        self.assertEqual(styles, set(S.LINE_HEIGHT_M))
        for kind, height in S.LINE_HEIGHT_M.items():
            row = S.lines(_project(_line(kind, [(0, 0), (5, 0)])), _Proj())[0]
            self.assertEqual(row["height_m"], height)
        self.assertGreater(S.LINE_HEIGHT_M["windbreak"],
                           S.LINE_HEIGHT_M["hedge"])
        self.assertLess(S.LINE_HEIGHT_M["fence"], 1.6,
                        "a fence a person can see over, not a wall nobody drew")

    def test_a_fence_is_boards_whatever_width_the_line_carries(self):
        row = S.lines(_project(_line("fence", [(0, 0), (5, 0)], width_m=1.5)),
                      _Proj())[0]
        self.assertEqual(row["width_m"], S.FENCE_WIDTH_M)

    def test_an_unknown_style_is_a_hedge_and_a_point_is_not_a_line(self):
        row = S.lines(_project(_line("pergola", [(0, 0), (5, 0)])), _Proj())[0]
        self.assertEqual(row["kind"], "hedge")
        self.assertEqual(S.lines(_project(_line("fence", [(0, 0)])), _Proj()), [])


class TheStreet(unittest.TestCase):

    def test_an_assumed_street_is_not_drawn(self):
        """South with nothing to go on: the Overview says "taken to be the
        south side" in words. A road in the picture would say it as fact."""
        self.assertIsNone(_scene(_project(_outline()))["street"])

    def test_no_outline_no_street(self):
        scene = _scene(_project(_shape("Garden Bed", (0, 0, 4, 3)),
                                street_side="south"))
        self.assertIsNone(scene["street"])

    def test_the_persons_answer_draws_a_sidewalk_and_a_road(self):
        street = _scene(_project(_outline(), street_side="south"))["street"]
        self.assertEqual((street["how"], street["bearing"]), ("told", 180.0))
        self.assertNotIn("roads", street)
        walk_ys = sorted({p[1] for p in street["sidewalk"]})
        road_ys = sorted({p[1] for p in street["road"]})
        edge = LOT[1]
        self.assertAlmostEqual(walk_ys[1], edge - S.SIDEWALK_OUT_M
                               + S.SIDEWALK_WIDTH_M / 2, places=1)
        self.assertAlmostEqual(walk_ys[1] - walk_ys[0], S.SIDEWALK_WIDTH_M,
                               places=1)
        self.assertAlmostEqual(road_ys[1], edge - S.ROAD_NEAR_M, places=1)
        self.assertAlmostEqual(road_ys[1] - road_ys[0], S.ROAD_WIDTH_M,
                               places=1)
        self.assertLess(road_ys[1], walk_ys[0], "the road is past the sidewalk")
        xs = [p[0] for p in street["road"]]
        self.assertLess(min(xs), LOT[0] - 100)
        self.assertGreater(max(xs), LOT[2] + 100)

    def test_the_neighbour_stands_on_the_sidewalk(self):
        """``scene_views.street_view`` stands them a sidewalk out; this is the
        sidewalk."""
        scene = _scene(_project(_outline(), street_side="south"))
        eye_y = scene["views"]["street"]["eye"][1]
        ys = sorted({p[1] for p in scene["street"]["sidewalk"]})
        self.assertTrue(ys[0] <= eye_y <= ys[1], (eye_y, ys))

    def test_it_follows_the_side_the_person_names(self):
        street = _scene(_project(_outline(), street_side="east"))["street"]
        self.assertEqual(street["bearing"], 90.0)
        xs = sorted({p[0] for p in street["road"]})
        self.assertAlmostEqual(xs[0], LOT[2] + S.ROAD_NEAR_M, places=1)

    def test_recorded_road_lines_are_drawn_where_they_are(self):
        """A scanned site keeps its road lines with the design (V2.58): the
        street is measured from them, and they are what is drawn."""
        road = _road([(-80, -30), (80, -30)])
        street = _scene(_project(_outline(), road))["street"]
        self.assertEqual(street["how"], "measured")
        self.assertNotIn("road", street, "no schematic road beside a real one")
        self.assertEqual(len(street["roads"]), 1)
        line = street["roads"][0]
        self.assertEqual(line["width_m"],
                         S.ROAD_CLASS_WIDTH_M["residential"])
        self.assertEqual(line["name"], "81 Avenue NW")
        self.assertAlmostEqual(line["points"][0][1], -30.0, places=1)
        self.assertIn("sidewalk", street)        # 11.7 m off: room for one

    def test_no_sidewalk_is_squeezed_onto_a_road(self):
        road = _road([(-80, -22.5), (80, -22.5)])          # its edge 0.2 m out
        street = _scene(_project(_outline(), road))["street"]
        self.assertNotIn("sidewalk", street)
        self.assertEqual(len(street["roads"]), 1)

    def test_a_road_far_from_the_yard_is_left_off(self):
        near = _road([(-80, -30), (80, -30)])
        far = _road([(600, -900), (900, -900)], name="Somewhere else")
        street = _scene(_project(_outline(), near, far))["street"]
        self.assertEqual([r["name"] for r in street["roads"]],
                         ["81 Avenue NW"])
        for x, y in street["roads"][0]["points"]:
            self.assertLessEqual(math.hypot(x, y), S.ROAD_REACH_M)


class TheRoof(unittest.TestCase):

    HOUSE = [[-5.4, -9.3], [5.4, -9.3], [5.4, 2.7], [-5.4, 2.7]]

    def test_a_house_gets_a_gable_along_its_long_side(self):
        roof = S.roof_for(self.HOUSE, 6.5)
        self.assertEqual(roof["form"], "gable")
        (x0, y0), (x1, y1) = roof["ridge"]
        self.assertEqual((x0, x1), (0.0, 0.0), "over the middle")
        self.assertEqual(sorted((y0, y1)), [-9.3, 2.7], "the long way")

    def test_the_ridge_is_inside_the_recorded_height(self):
        """The building is never taller than the shade map's: the ridge is at
        the recorded height and the walls stop lower."""
        for height in (2.8, 3.4, 6.5, 9.0, 14.0):
            roof = S.roof_for(self.HOUSE, height)
            self.assertEqual(roof["form"], "gable", height)
            self.assertGreater(roof["rise_m"], 0.29)
            self.assertGreaterEqual(height - roof["rise_m"],
                                    S.GABLE_MIN_WALL_M - 0.01, height)
            self.assertLessEqual(roof["rise_m"],
                                 height * S.GABLE_MAX_SHARE + 0.01)
        self.assertEqual(S.roof_for(self.HOUSE, 2.4)["form"], "flat",
                         "too low for walls and a roof")

    def test_only_a_clean_four_corner_footprint(self):
        ell = [[0, 0], [10, 0], [10, 6], [5, 6], [5, 10], [0, 10]]
        self.assertEqual(S.roof_for(ell, 6.5), {"form": "flat"})
        kite = [[0, 0], [10, 1], [11, 9], [-2, 7]]
        self.assertEqual(S.roof_for(kite, 6.5), {"form": "flat"})
        triangle = [[0, 0], [8, 0], [4, 7]]
        self.assertEqual(S.roof_for(triangle, 6.5), {"form": "flat"})
        self.assertEqual(S.roof_for([], 6.5), {"form": "flat"})

    def test_a_turned_rectangle_is_still_a_house(self):
        turned = []
        for x, y in self.HOUSE:
            a = math.radians(30)
            turned.append([x * math.cos(a) - y * math.sin(a),
                           x * math.sin(a) + y * math.cos(a)])
        roof = S.roof_for(turned, 6.5)
        self.assertEqual(roof["form"], "gable")
        (x0, y0), (x1, y1) = roof["ridge"]
        self.assertAlmostEqual(math.hypot(x1 - x0, y1 - y0), 12.0, places=1)

    def test_a_warehouse_and_a_shed_wall_get_a_flat_roof(self):
        warehouse = [[0, 0], [40, 0], [40, 22], [0, 22]]
        self.assertEqual(S.roof_for(warehouse, 9.0)["form"], "flat")
        sliver = [[0, 0], [8, 0], [8, 1.5], [0, 1.5]]
        self.assertEqual(S.roof_for(sliver, 3.0)["form"], "flat")

    def test_every_building_carries_one_and_a_tree_crown_none(self):
        crown = _building((2, 12, 6, 16), 8.0)
        crown["properties"].update(shape_type="Tree canopy",
                                   caster_kind="tree")
        scene = _scene(_project(_outline(), _building((-5.4, -9.3, 5.4, 2.7)),
                                crown))
        kinds = {b["kind"]: b for b in scene["buildings"]}
        self.assertEqual(kinds["building"]["roof"]["form"], "gable")
        self.assertNotIn("roof", kinds["canopy"])
        self.assertEqual(kinds["building"]["height_m"], 6.5,
                         "the recorded height is not touched")

    def test_the_views_and_the_shade_do_not_read_it(self):
        """Additive: a plant's place, the views and the focus are what they
        were without the site fields."""
        lng, lat = _ll(-3, -14)
        project = _project(_outline(), _building((-5.4, -9.3, 5.4, 2.7)),
                           plant_feature({"plant_id": 1, "common_name": "Forb",
                                          "lat": lat, "lng": lng}))
        plain = _scene(project)
        project["features"] += [_shape("Garden Bed", (-7, -17, 1, -11)),
                                _line("fence", [(-7.6, 3), (-7.6, 18.3)])]
        drawn = _scene(project)
        for key in ("focus", "views", "bounds", "plants", "boundary"):
            self.assertEqual(drawn[key], plain[key], key)


if __name__ == "__main__":
    unittest.main()

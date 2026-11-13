"""
tests/test_yard_render.py — the whole-yard gate (V3.43).

Six audits of the 3D preview rendered one plant at a time. For years nobody
rendered a yard, and the faults of the whole picture went unseen while every
part-level guard stayed green: every house a see-through green box, the camera
framing a 50 m stage with the yard about 1% of it, Walk the garden starting
inside the house, the "sidewalk" view of the PDF's before/after page 22 m
outside the lot behind a trunk, fruit 17 cm across, a plant the timeline had
lost drawn as a pale ghost, and "Year 0 · 367 plants · 4 structure
footprint(s)" over a design fully grown with a third of those plants dead.

So this builds a yard through the real ``build_scene`` (a house, a drawn tree
crown, a boulevard tree, plants that the timeline shades out and lives out),
pushes it into the real viewer in headless Chromium, and reads the whole picture
back (``html/yard_probe.html``). Against V3.42's viewer 12 of the 18 checks
fail, which is how the gate was shown to see the faults it is for::

    YARD_VIEWER_ROOT=<a V3.42 checkout>/html python -m unittest tests.test_yard_render

Skips with no Chromium binary or no WebGL, as the other render gates do; a
viewer that THROWS fails (``fail_on_viewer_errors``, V3.37).
"""

import copy
import json
import math
import os
import re
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import render_yard                                            # noqa: E402
from src.project_store import plant_feature                   # noqa: E402
from src.scene_contract import build_scene, standing_plants   # noqa: E402
from tests.test_scene3d_render import fail_on_viewer_errors   # noqa: E402
from tests.test_scene_contract import _FAKE_PLANTS            # noqa: E402

_LAT, _LNG = 53.5, -113.5
_KY = 111320.0
_KX = 111320.0 * math.cos(math.radians(_LAT))

#: One forb with an id of its own, so the probe can find the plant this test
#: marks as declining.
_PLANTS = dict(_FAKE_PLANTS)
_PLANTS[12] = {"plant_type": "wildflower", "years_to_maturity": 2,
               "growth_curve": "steady", "mature_height_meters": 0.9,
               "mature_canopy_m": 0.6, "common_name": "Marked forb"}
DECLINING = 12
YEAR = 25


def _ll(x, y):
    return [_LNG + x / _KX, _LAT + y / _KY]


def _ring(x0, y0, x1, y1):
    r = [_ll(x, y) for x, y in ((x0, y0), (x1, y0), (x1, y1), (x0, y1))]
    return r + [r[0]]


def _plant(pid, name, x, y):
    lng, lat = _ll(x, y)
    return plant_feature({"plant_id": pid, "common_name": name,
                          "lat": lat, "lng": lng})


def _area(kind, box, **props):
    return {"type": "Feature",
            "geometry": {"type": "Polygon", "coordinates": [_ring(*box)]},
            "properties": {"element_type": "custom_shape", "shape_type": kind,
                           "fill_color": "#4caf50", **props}}


def _line(style, points):
    return {"type": "Feature",
            "geometry": {"type": "LineString",
                         "coordinates": [_ll(x, y) for x, y in points]},
            "properties": {"element_type": "hedgerow", "style": style,
                           "width_m": 1.5}}


#: What a few minutes of Draw › Shape leave on the ground (V3.45).
DRAWN = [
    _area("Garden Bed", (-7.0, -17.5, 6.5, -10.5)),
    _area("Pathway", (-0.6, -18.3, 0.6, -9.3)),          # across the bed
    _area("Lawn Area", (-7.0, 4.0, 1.0, 12.0)),
    _area("Water Feature", (3.0, 5.0, 6.0, 8.0)),
    _area("Mulch Area", (-7.0, 13.0, 1.0, 17.5)),
    _area("Custom", (2.5, 9.5, 6.5, 11.5), fill_color="#ff8800"),
    _line("fence", [(-7.6, 3.0), (-7.6, 18.3), (0.0, 18.3)]),
    _line("hedge", [(7.0, 4.0), (7.0, 12.0)]),
]


def _yard() -> dict:
    """A 15 x 37 m lot, street to the south, as a scan and a plan leave it."""
    feats = [
        {"type": "Feature",
         "geometry": {"type": "Polygon",
                      "coordinates": [_ring(-7.6, -18.3, 7.6, 18.3)]},
         "properties": {"element_type": "property_boundary"}},
        # The house, as Scan this area stores it: a canopy_footprint.
        {"type": "Feature",
         "geometry": {"type": "Polygon",
                      "coordinates": [_ring(-5.4, -9.3, 5.4, 2.7)]},
         "properties": {"element_type": "canopy_footprint", "height_m": 6.5,
                        "shape_type": "Building (OSM)", "cast_shade": True,
                        "source": "osm", "lat": _LAT, "lng": _LNG,
                        "canopy_radius_m": 6.0}},
        # A tree's crown drawn by hand, behind the house.
        {"type": "Feature",
         "geometry": {"type": "Polygon",
                      "coordinates": [_ring(2.0, 12.0, 6.0, 16.0)]},
         "properties": {"element_type": "canopy_footprint", "height_m": 8.0,
                        "shape_type": "Tree canopy", "caster_kind": "tree",
                        "cast_shade": True}},
        # The boulevard tree, between the sidewalk and the yard.
        {"type": "Feature",
         "geometry": {"type": "Point", "coordinates": _ll(-3.6, -20.8)},
         "properties": {"element_type": "existing_tree", "height_m": 14.0,
                        "canopy_radius_m": 5.5, "tree_foliage": "deciduous",
                        "label": "Tree"}},
        _plant(7, "Aspen", -3.0, -13.0),
        _plant(6, "Saskatoon", 4.5, -15.0),
        _plant(DECLINING, "Marked forb", 5.5, -12.0),
    ]
    for i in range(8):                    # full-sun forbs under the aspen
        feats.append(_plant(8, "Sun forb", -4.5 + (i % 4) * 0.8,
                            -14.0 + (i // 4) * 1.6))
    for i in range(30):                   # a short-lived kind, in the back
        feats.append(_plant(10, "Short-lived forb", -6.0 + (i % 6) * 0.9,
                            7.0 + (i // 6) * 0.9))
    # The person's answer in Plan My Yard: the street is to the south.
    return {"type": "FeatureCollection",
            "properties": {"site_config": {"street_side": "south"}},
            "features": feats + DRAWN}


def _scenes():
    from datetime import datetime
    when = datetime(2025, 7, 21, 13, 0)
    scene = build_scene(_yard(), year=YEAR, get_plant=_PLANTS.get, wind=False,
                        when=when)
    for p in scene["plants"]:
        if p.get("plant_id") == DECLINING:
            # Marked by hand: the one thing here build_scene did not decide.
            p.update(health=0.3, health_state="declining", opacity=0.65)
    # What any scene made before V3.43 looks like to the viewer: no focus, no
    # views. Another origin, so the viewer frames it afresh.
    legacy = copy.deepcopy(build_scene(_yard(), year=0, get_plant=_PLANTS.get,
                                       wind=False, when=when))
    legacy["focus"], legacy["views"] = None, {}
    legacy["origin"]["lat"] += 0.01
    # ... and before V3.45: no word on the ground, and no roof hint.
    for key in ("ground", "surfaces", "lines", "street"):
        legacy.pop(key)
    for b in legacy["buildings"]:
        b.pop("roof", None)
    # ... and before V3.46: no season and no notes.
    for key in ("season", "timeline_notes"):
        legacy.pop(key)
    for p in legacy["plants"]:
        p.pop("season", None)
    winter = build_scene(_yard(), year=YEAR, get_plant=_PLANTS.get, wind=False,
                         when=datetime(2025, 1, 21, 13, 0))
    return scene, legacy, winter


def _seasons():
    """The same yard in the same year on 21 April, September and October, and
    a meadow from before V3.46 in October, which has only its month."""
    from datetime import datetime
    out = {name: build_scene(_yard(), year=YEAR, get_plant=_PLANTS.get,
                             wind=False, when=datetime(2025, month, 21, 13, 0))
           for name, month in (("apr", 4), ("sep", 9), ("oct", 10))}
    meadow = copy.deepcopy(_scenes()[1])
    meadow["month"] = 10
    meadow["origin"]["lat"] += 0.01
    return out, meadow


@unittest.skipIf(render_yard.find_chromium() is None,
                 "no Chromium binary (set CHROME= to run this gate)")
class TheWholeYard(unittest.TestCase):
    got = None
    scene = None

    @classmethod
    def setUpClass(cls):
        cls.scene, legacy, winter = _scenes()
        seasons, meadow = _seasons()
        job = {"scene": cls.scene, "legacy": legacy, "winter": winter,
               "declining_id": DECLINING,
               # V3.46: a herb, a shrub and a tree to read through the year.
               "herb_id": DECLINING, "shrub_id": 6, "tree_id": 7,
               "seasons": seasons, "meadow_october": meadow,
               "walk_points": [["side_yard", -6.6, -3.0],
                               ["in_the_house", 0.5, -3.0]]}
        try:
            server = render_yard.Server(
                {"/__yard/job.json": job},
                viewer_root=os.environ.get("YARD_VIEWER_ROOT", render_yard.HTML))
        except OSError as exc:
            raise unittest.SkipTest(f"cannot bind a local port: {exc}")
        try:
            dom = render_yard.run_probe(
                server.url("yard_probe.html?job=/__yard/job.json"),
                timeout=420)
        except (OSError, RuntimeError, Exception) as exc:    # noqa: BLE001
            server.stop()
            raise unittest.SkipTest(f"Chromium would not run headlessly: {exc}")
        server.stop()
        fail_on_viewer_errors(dom)
        match = re.search(r"<title>MEASURED (\{.*\})</title>", dom, re.S)
        if not match:
            raise unittest.SkipTest("the probe never reported: no WebGL in "
                                    "this environment")
        import html as _html
        cls.got = json.loads(_html.unescape(match.group(1)))

    # ── the scene is the one the gate needs ──────────────────────────────────

    def test_the_fixture_still_has_every_case_in_it(self):
        """Loud if the growth or succession models move the fixture out from
        under the assertions below."""
        plants = self.scene["plants"]
        kinds = {b["kind"] for b in self.scene["buildings"]}
        self.assertEqual(kinds, {"building", "canopy"})
        self.assertTrue(any(p.get("gone") == "shade" for p in plants))
        self.assertTrue(any(p.get("gone") == "short_lived" for p in plants))
        self.assertTrue(any(p["plant_id"] == 10 for p in
                            standing_plants(self.scene)))
        self.assertTrue(self.scene["views"]["street"])
        self.assertTrue(self.scene["views"]["house"])
        self.assertEqual([s_["kind"] for s_ in self.scene["surfaces"]],
                         ["lawn", "bed", "path", "lawn", "water", "mulch",
                          "custom"])
        self.assertEqual([ln["kind"] for ln in self.scene["lines"]],
                         ["fence", "hedge"])
        self.assertEqual(self.scene["street"]["how"], "told")
        # V3.46: notes of more than one kind, and a herb that stands all year.
        kinds = [n["kind"] for n in self.scene["timeline_notes"]["notes"]]
        self.assertIn("shade", kinds)
        self.assertIn("short_lived", kinds)
        self.assertTrue(any(p["plant_id"] == DECLINING and not p.get("gone")
                            for p in plants))

    # ── buildings ────────────────────────────────────────────────────────────

    def test_a_house_is_solid_and_a_drawn_crown_is_not(self):
        house, crown = self.got["meshes"]["buildings"], self.got["meshes"]["canopys"]
        self.assertFalse(house["see_through"], "the house is see-through: "
                         "V3.42 drew every scanned building as a green canopy")
        self.assertTrue(crown["see_through"])
        self.assertNotEqual(house["colour"], crown["colour"])

    # ── the yard itself (V3.45) ──────────────────────────────────────────────

    @staticmethod
    def _apart(a, b):
        return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))

    def _surface(self, kind, which=0):
        rows = [s_ for s_ in self.got["site"]["surfaces"]
                if s_["name"] == f"surface:{kind}"]
        return rows[which]

    def test_every_drawn_area_reaches_the_picture_as_its_kind(self):
        """Finding 2: nothing drawn on the ground reached 3D. A bed, mulch, a
        lawn, a path and a pond were one meadow texture."""
        drawn = [s_["name"] for s_ in self.got["site"]["surfaces"]]
        self.assertEqual(drawn, ["surface:" + s_["kind"]
                                 for s_ in self.scene["surfaces"]])
        for row in self.got["site"]["surfaces"]:
            self.assertEqual("surface:" + row["look"], row["name"])

    def test_a_bed_is_not_lawn_coloured(self):
        lawn, bed = self._surface("lawn")["colour"], self._surface("bed")["colour"]
        self.assertGreater(self._apart(lawn, bed), 60,
                           f"a bed {bed} reads as lawn {lawn}")
        self.assertGreater(lawn[1], lawn[0], "lawn is not green")
        self.assertGreater(bed[0], bed[1] - 1, "a bed is not soil-coloured")
        for kind in ("path", "water", "mulch"):
            other = self._surface(kind)["colour"]
            self.assertGreater(self._apart(lawn, other), 40, (kind, other))
            self.assertGreater(self._apart(bed, other), 25, (kind, other))
        water = self._surface("water")["colour"]
        self.assertGreater(water[2], water[0], "water is not blue")

    def test_a_custom_shape_keeps_the_persons_colour(self):
        self.assertEqual(self._surface("custom")["colour"], [255, 136, 0])

    def test_lawn_inside_the_outline_and_pale_outside(self):
        """The owner's D3: where nothing is drawn."""
        ground = self.got["site"]["ground"]
        self.assertEqual(ground["look"], "pale")
        lawn = self._surface("lawn")["colour"]
        self.assertGreater(self._apart(ground["colour"], lawn), 30,
                           "the yard does not stand out from the ground round it")
        r, g, b = ground["colour"]
        self.assertLess(max(r, g, b) - min(r, g, b), 30,
                        f"the ground outside is not neutral: {ground['colour']}")
        self.assertGreater(min(r, g, b), 150, "the ground outside is not pale")

    def test_a_path_lies_over_a_bed_and_a_bed_over_the_lawn(self):
        """The path crosses the bed in this yard. Each kind has its place in
        the pile, so the two do not flicker where they overlap."""
        base, bed = self._surface("lawn", 0), self._surface("bed")
        path = self._surface("path")
        self.assertLess(base["order"], bed["order"])
        self.assertLess(bed["order"], path["order"])
        self.assertLess(base["lift"], bed["lift"])
        self.assertLess(bed["lift"], path["lift"])
        self.assertLess(path["lift"], 0.05, "a path floats over the ground")
        self.assertGreater(base["lift"], self.got["site"]["ground"]["lift"])

    def test_the_street_is_drawn_pale_where_its_side_is_known(self):
        names = sorted(s_["name"] for s_ in self.got["site"]["street"])
        self.assertEqual(names, ["street:road", "street:sidewalk"])
        for row in self.got["site"]["street"]:
            r, g, b = row["colour"]
            self.assertLess(max(r, g, b) - min(r, g, b), 20,
                            f"{row['name']} has a colour of its own")
            self.assertGreater(min(r, g, b), 140, f"{row['name']} is not pale")

    def test_a_house_has_a_roof_inside_its_recorded_height(self):
        """Plain massing: light walls, a darker roof, and never taller than
        the shade map's building."""
        walls, roofs = self.got["site"]["walls"], self.got["site"]["roofs"]
        self.assertIsNotNone(roofs, "the house has no roof")
        self.assertAlmostEqual(roofs["top"], 6.5, delta=0.01,
                               msg="the ridge is not at the recorded height")
        self.assertAlmostEqual(walls["top"], 6.5, delta=0.01)   # the gable end
        rise = next(b["roof"]["rise_m"] for b in self.scene["buildings"]
                    if b["kind"] == "building")
        self.assertLess(roofs["low"], 6.5 - rise, "the roof has no overhang")
        self.assertGreater(roofs["low"], 6.5 - rise - 0.5)
        self.assertGreater(sum(walls["colour"]), sum(roofs["colour"]) + 150,
                           "the roof is not darker than the walls")
        r, g, b = walls["colour"]
        self.assertLess(max(r, g, b) - min(r, g, b), 30, "the walls are coloured")

    def test_a_fence_and_a_hedge_stand_where_they_were_drawn(self):
        lines = self.got["site"]["lines"]
        self.assertEqual(sorted(lines), ["fences", "hedges:hedge"])
        self.assertAlmostEqual(lines["fences"]["low"], 0.0, delta=0.02)
        self.assertAlmostEqual(lines["fences"]["top"], 1.28, delta=0.03)
        self.assertAlmostEqual(lines["hedges:hedge"]["top"], 1.2, delta=0.02)
        r, g, b = lines["hedges:hedge"]["colour"]
        self.assertGreater(g, max(r, b), "a hedge is not green")

    def test_snow_lies_on_the_soft_ground_and_the_roofs(self):
        winter = self.got["winter"]
        by = {}
        for row in winter["surfaces"]:
            by.setdefault(row["look"], row)
        for kind in ("lawn", "bed", "mulch", "path"):
            self.assertTrue(by[kind]["snow"], f"{kind} is not under snow")
        self.assertGreater(min(by["lawn"]["colour"]), 215)
        self.assertLess(sum(by["path"]["colour"]), sum(by["lawn"]["colour"]),
                        "a path under snow reads the same as a bed under snow")
        self.assertFalse(by["water"]["snow"])
        self.assertGreater(min(winter["roofs"]["colour"]), 215,
                           "no snow on the roof")
        self.assertNotEqual(winter["ground"]["look"], "pale")

    def test_a_scene_from_before_keeps_its_meadow_and_its_boxes(self):
        """The probes, the sprite gallery and any scene made before V3.45
        carry none of these fields."""
        site = self.got["legacy"]["site"]
        self.assertEqual(site["ground"]["look"], "")           # the meadow
        self.assertGreater(site["ground"]["colour"][1],
                           site["ground"]["colour"][2] + 30)
        self.assertEqual(site["surfaces"], [])
        self.assertEqual(site["street"], [])
        self.assertEqual(site["lines"], {})
        self.assertIsNone(site["roofs"])
        self.assertAlmostEqual(site["walls"]["top"], 6.5, delta=0.01)

    # ── the seasons (V3.46) ──────────────────────────────────────────────────

    @staticmethod
    def _tall(rows):
        return max(r["tall"] for r in rows)

    @staticmethod
    def _body(rows):
        """The mesh that carries the plant's own body: its tallest."""
        return max(rows, key=lambda r: r["tall"])

    def _then(self, name):
        if "seasons" not in self.got:
            self.fail("the viewer has no season of its own (before V3.46)")
        return self.got["january"] if name == "jan" else self.got["seasons"][name]

    def test_a_herb_is_a_hand_high_in_april_not_at_its_july_height(self):
        """Finding 7: perennials stood at July height on 21 April."""
        july = self._tall(self.got["july"]["herb"])
        april = self._tall(self._then("apr")["herb"])
        self.assertAlmostEqual(july, 0.9, delta=0.02)
        self.assertLess(april, 0.3 * july,
                        f"a herb stands {april} m tall on 21 April")
        self.assertGreater(april, 0.05, "the herb is not drawn at all")

    def test_a_herb_is_green_in_july_and_dry_in_october_and_in_the_snow(self):
        """Finding 7: green through October, green in January snow."""
        # The fixture's herb is the one marked as declining, so in July it is
        # read off a healthy neighbour of the same kind: the lost plants' kind.
        for name in ("oct", "jan"):
            r, g, _b = self._body(self._then(name)["herb"])["rgb"]
            self.assertGreaterEqual(r, g, f"a herb is green in {name}")
        r, g, _b = self._body(self._then("apr")["herb"])["rgb"]
        self.assertGreater(g, r, "a herb coming up in April is not green")

    def test_a_shrub_drops_its_leaves_exactly_when_a_tree_does(self):
        """Finding 7: trees went bare in winter and shrubs never did."""
        def leaves(rows):                  # the smaller mesh of the two
            return min(r["tall"] for r in rows)
        for kind in ("shrub", "tree"):
            rows = self.got["july"][kind]
            self.assertEqual(len(rows), 2, f"a {kind} is leaves and wood")
            self.assertGreater(leaves(rows), 0.5, f"a {kind} is bare in July")
            self.assertGreater(leaves(self._then("sep")[kind]), 0.5,
                               f"a {kind} is bare in September")
            for name in ("jan", "apr", "oct"):
                rows = self._then(name)[kind]
                self.assertLess(leaves(rows), 0.01,
                                f"a {kind} keeps its leaves in {name}")
                self.assertGreater(self._tall(rows), 0.5,
                                   f"a bare {kind} has no wood left in {name}")

    def test_leaves_turn_in_september(self):
        def green(row):
            return row["rgb"][1] - row["rgb"][0]
        for kind in ("shrub", "tree"):
            july = self.got["july"][kind]
            # A plant's meshes come in one order: its leaves are July's greener.
            leaves = max(range(len(july)), key=lambda i: green(july[i]))
            self.assertLess(green(self._then("sep")[kind][leaves]),
                            green(july[leaves]) - 0.02,
                            f"a {kind}'s leaves are July's green in September")

    def test_a_dormant_meadow_is_tawny_not_olive(self):
        """The October ground: the green texture times a straw colour came
        out dark olive. A scene that names no ground is a meadow."""
        r, g, b = self.got["meadow_october"]["colour"]
        self.assertGreater(r, g, f"the October meadow is green: {(r, g, b)}")
        self.assertGreater(r + g + b, 400,
                           f"the October meadow is dark: {(r, g, b)}")

    def test_the_lawn_wakes_tan_and_is_green_all_summer(self):
        def lawn(site):
            return next(s_ for s_ in site["surfaces"]
                        if s_["name"] == "surface:lawn")["colour"]
        r, g, _b = lawn(self.got["site"])
        self.assertGreater(g, r + 15, "the lawn is not green in July")
        r, g, _b = lawn(self._then("apr")["site"])
        self.assertGreater(r, g - 8, "the lawn is summer green on 21 April")
        r, g, _b = lawn(self._then("oct")["site"])
        self.assertGreater(g, r, "the lawn has gone to straw by 21 October")

    def test_snow_falls_only_while_snow_lies(self):
        self.assertTrue(self._then("jan")["snowing"])
        for name in ("apr", "sep", "oct"):
            self.assertFalse(self._then(name)["snowing"], name)
            self.assertFalse(any(s_["snow"] for s_ in
                                 self._then(name)["site"]["surfaces"]), name)

    def test_a_hedge_is_twigs_when_the_leaves_are_down(self):
        def hedge(site):
            return site["lines"]["hedges:hedge"]["colour"]
        r, g, b = hedge(self.got["site"])
        self.assertGreater(g, max(r, b))
        for name in ("apr", "oct", "jan"):
            r, g, b = hedge(self._then(name)["site"])
            self.assertGreaterEqual(r, g, f"a hedge is in leaf in {name}")

    # ── what the years took, where and which (V3.46) ─────────────────────────

    def _timeline(self, state):
        if "timeline" not in self.got:
            self.fail("the viewer shows no notes (before V3.46)")
        return self.got["timeline"][state]

    def _notes(self):
        return self.scene["timeline_notes"]["notes"]

    def test_the_notes_are_shut_until_asked_for(self):
        shut = self._timeline("shut")
        self.assertEqual(shut["chip"], "Show where, and which plants")
        self.assertEqual(shut["rows"], [])
        self.assertEqual(shut["rings"], [])

    def test_opened_they_say_where_and_which_and_ring_every_spot(self):
        """Finding 6: "136 lost to shade" said how many and nothing else."""
        opened = self._timeline("open")
        self.assertEqual(opened["chip"], "Hide where")
        self.assertEqual(opened["heading"],
                         "By " + self.scene["timeline_notes"]["when"])
        self.assertEqual(opened["rows"],
                         [n["text"] + n["kinds"] for n in self._notes()])
        self.assertEqual(opened["about"], self.scene["timeline_notes"]["about"])
        spots = sorted([round(x, 2), round(y, 2), n["kind"]]
                       for n in self._notes() for x, y in n["spots"])
        self.assertEqual(sorted([x, y, kind] for x, y, _h, kind
                                in opened["rings"]), spots)
        self.assertTrue(spots)
        for _x, _y, height, _kind in opened["rings"]:
            self.assertAlmostEqual(height, 0.05, delta=0.01,
                                   msg="a ring is not lying on the ground")

    def test_one_note_rings_only_its_own_spots(self):
        one = self._timeline("one")
        self.assertEqual(len(one["rings"]), len(self._notes()[0]["spots"]))
        self.assertEqual({r[3] for r in one["rings"]},
                         {self._notes()[0]["kind"]})
        self.assertEqual(len(self._timeline("all_again")["rings"]),
                         len(self._timeline("open")["rings"]))

    def test_they_stay_open_through_a_slider_move(self):
        """Every slider move rebuilds the scene; the list and the rings are
        put back, or a person reading them loses them at the first touch."""
        after = self._timeline("after_a_push")
        self.assertEqual(after["rows"], self._timeline("open")["rows"])
        self.assertEqual(len(after["rings"]), len(self._timeline("open")["rings"]))

    def test_they_shut(self):
        shut = self._timeline("shut_again")
        self.assertEqual(shut["rows"], [])
        self.assertEqual(shut["rings"], [])
        self.assertEqual(shut["chip"], "Show where, and which plants")

    def test_their_text_is_12_px_and_their_buttons_24(self):
        opened = self._timeline("open")
        size, tall = opened["chip_px"]
        self.assertGreaterEqual(size, 12)
        self.assertGreaterEqual(tall, 24)
        self.assertGreaterEqual(opened["smallest_px"], 12)
        for size, tall in opened["row_px"]:
            self.assertGreaterEqual(size, 12)
            self.assertGreaterEqual(tall, 24)

    def test_a_scene_with_nothing_lost_has_no_button(self):
        self.assertFalse(self.got["legacy"]["chip"])

    # ── the camera ───────────────────────────────────────────────────────────

    def test_the_window_opens_on_the_yard(self):
        yard = self.got["opening"]["yard"]
        self.assertTrue(yard["inside"], f"part of the yard is out of frame: {yard}")
        self.assertGreater(yard["tall"], 0.45,
                           f"the yard is a small part of the picture: {yard}")
        self.assertGreater(yard["wide"], 0.30, yard)

    def test_a_scene_with_no_focus_frames_the_stage_as_before(self):
        """The probe pages and any scene saved before V3.43 carry no focus."""
        b = self.scene["bounds"]
        r = max(b["max_x"] - b["min_x"], b["max_y"] - b["min_y"]) * 0.75
        far = r * math.sqrt(0.9 ** 2 + 0.85 ** 2 + 1.1 ** 2)   # frameCamera's
        self.assertAlmostEqual(self.got["legacy"]["camera"]["far"], far,
                               delta=0.5)
        self.assertGreater(self.got["legacy"]["camera"]["far"],
                           self.got["opening"]["camera"]["far"] * 1.15)

    def test_leaving_walk_frames_the_yard_again(self):
        self.assertTrue(self.got["after_walk"]["yard"]["inside"])
        self.assertGreater(self.got["after_walk"]["yard"]["tall"], 0.45)

    def test_the_street_view_stands_where_the_scene_says(self):
        street = self.scene["views"]["street"]
        (ex, ey), (lx, ly) = street["eye"], street["look"]
        at, looks = self.got["street"]["at"], self.got["street"]["looks_at"]
        self.assertAlmostEqual(at[0], ex, delta=0.02)
        self.assertAlmostEqual(at[2], -ey, delta=0.02)
        self.assertAlmostEqual(at[1], 1.65, delta=0.02)      # eye height
        self.assertAlmostEqual(looks[0], lx, delta=0.02)
        self.assertAlmostEqual(looks[2], -ly, delta=0.02)
        # Just outside the south edge (y = -18.3), not across the street.
        self.assertTrue(-18.3 - 8 < ey < -18.3, ey)

    def test_the_view_inside_the_yard_is_a_few_steps_on(self):
        lx, ly = self.scene["views"]["street"]["look"]
        at = self.got["in_yard"]["at"]
        self.assertAlmostEqual(math.hypot(at[0] - lx, -at[2] - ly), 3.0,
                               delta=0.1)
        self.assertAlmostEqual(at[1], 1.65, delta=0.02)

    def test_a_scene_with_no_street_view_keeps_the_old_preset(self):
        self.assertGreater(self.got["legacy"]["street"]["at"][2], 30)

    # ── walking ──────────────────────────────────────────────────────────────

    def test_the_walker_starts_on_the_street_side_facing_in(self):
        street = self.scene["views"]["street"]
        (ex, ey), (lx, ly) = street["eye"], street["look"]
        walk = self.got["walk"]
        self.assertFalse(walk["inside_a_building"],
                         "Walk the garden starts inside the house")
        self.assertAlmostEqual(walk["at"][0], ex, delta=0.02)
        self.assertAlmostEqual(walk["at"][1], ey, delta=0.02)
        self.assertAlmostEqual(walk["yaw"], math.atan2(lx - ex, ly - ey),
                               delta=0.01)

    def test_a_house_stops_him_at_its_walls_not_at_a_circle(self):
        """The house was a circle 7.3 m in radius on a lot 7.6 m to each side:
        both side yards were closed, and nothing led from front to back."""
        side = self.got["walls"]["side_yard"]
        self.assertEqual(side["to"], [-6.6, -3.0], "the side yard is blocked")
        pushed = self.got["walls"]["in_the_house"]
        self.assertFalse(pushed["inside"], "he was left standing in the house")
        x, y = pushed["to"]
        self.assertTrue(abs(x) > 5.4 or y > 2.7 or y < -9.3, pushed)

    # ── what stands ──────────────────────────────────────────────────────────

    def test_a_plant_that_is_gone_is_not_drawn(self):
        drawn = self.got["drawn"]
        self.assertNotIn("8", drawn, "plants lost to shade are still drawn")
        standing = sum(1 for p in standing_plants(self.scene)
                       if p["plant_id"] == 10)
        placed = sum(1 for p in self.scene["plants"] if p["plant_id"] == 10)
        self.assertLess(standing, placed)
        self.assertEqual(drawn.get("10"), standing,
                         "a short-lived kind past its years is drawn in full: "
                         "V3.42 drew the ones that were gone as pale ghosts")
        self.assertIn("7", drawn)

    def test_a_declining_plant_turns_toward_straw_never_sky(self):
        c = self.got["declining"]
        self.assertIsNotNone(c, "the marked forb was not drawn at all")
        self.assertLess(c["b"], c["r"], f"it is blended toward the sky: {c}")

    def test_fruit_is_no_wider_than_a_hand(self):
        sizes = self.got["fruit_m"]
        self.assertTrue(sizes, "the saskatoon carries no fruit in July")
        self.assertLessEqual(max(sizes), 0.16,
                             f"fruit drawn {max(sizes) * 100:.0f} cm across")

    # ── the words ────────────────────────────────────────────────────────────

    def test_the_line_at_the_top_says_what_is_there(self):
        hud = self.got["hud"]
        # The toolbar's own words since V3.44 (src/scene3d_stops.py).
        from src.scene3d_stops import when_words
        self.assertIn(when_words(YEAR, 7), hud)
        self.assertNotIn(f"Year {YEAR}", hud)
        self.assertIn("July", hud)
        self.assertIn("1 tree already here", hud)
        dead = sum(1 for p in self.scene["plants"] if p.get("gone") == "shade")
        lived = sum(1 for p in self.scene["plants"]
                    if p.get("gone") == "short_lived")
        self.assertIn(f"{dead} lost to shade", hud)
        self.assertIn(f"{lived} short-lived, gone", hud)
        standing = sum(1 for p in standing_plants(self.scene)
                       if p.get("plant_id") is not None)
        self.assertIn(f"{standing} plants", hud)
        self.assertNotIn("footprint", hud)

    def test_year_zero_is_called_fully_grown(self):
        hud = self.got["legacy"]["hud"]
        self.assertIn("Fully grown", hud)
        self.assertNotIn("Year 0", hud)
        self.assertNotIn("lost to shade", hud)

    # ── the named viewpoints (V3.44) ─────────────────────────────────────────

    def test_from_the_street_is_the_street_view(self):
        self.assertEqual(self.got["views"]["street"]["at"],
                         self.got["street"]["at"])
        self.assertEqual(self.got["views"]["street"]["looks_at"],
                         self.got["street"]["looks_at"])

    def test_from_the_house_stands_at_the_wall_looking_out(self):
        house = self.scene["views"]["house"]
        (ex, ey), (lx, ly) = house["eye"], house["look"]
        got = self.got["views"]["house"]
        at, looks = got["at"], got["looks_at"]
        self.assertAlmostEqual(at[0], ex, delta=0.02)
        self.assertAlmostEqual(at[2], -ey, delta=0.02)
        self.assertAlmostEqual(at[1], 1.65, delta=0.02)      # eye height
        self.assertAlmostEqual(looks[0], lx, delta=0.02)
        self.assertAlmostEqual(looks[2], -ly, delta=0.02)
        self.assertLess(looks[1], at[1], "it looks down at the planting")
        # A step outside the back wall (y = 2.7), not inside the house: the
        # 30 forbs behind it outnumber the 11 plants in front.
        self.assertTrue(2.7 < ey < 2.7 + 1.5, ey)
        self.assertGreater(ly, ey, "it looks away from the house")
        self.assertNotEqual(at, self.got["views"]["street"]["at"])

    def test_from_above_holds_the_whole_yard_north_up(self):
        above = self.got["views"]["above"]
        focus = self.scene["focus"]
        cx = (focus["min_x"] + focus["max_x"]) / 2
        cy = (focus["min_y"] + focus["max_y"]) / 2
        self.assertTrue(above["yard"]["inside"],
                        f"part of the yard is out of frame: {above['yard']}")
        self.assertGreater(max(above["yard"]["tall"], above["yard"]["wide"]),
                           0.8, "the yard is a small part of the picture")
        self.assertAlmostEqual(above["at"][0], cx, delta=0.05)
        self.assertAlmostEqual(above["looks_at"][0], cx, delta=0.05)
        self.assertAlmostEqual(above["looks_at"][2], -cy, delta=0.05)
        self.assertGreater(above["at"][1], 20, "it is not looking down")
        # A hair south of the centre (+z is south), so north is at the top.
        self.assertGreater(above["at"][2], above["looks_at"][2])
        self.assertLess(above["at"][2] - above["looks_at"][2], 1.0)

    def test_a_view_the_scene_cannot_give_shows_the_whole_yard(self):
        nowhere = self.got["views"]["nowhere"]
        self.assertTrue(nowhere["yard"]["inside"])
        self.assertAlmostEqual(nowhere["far"],
                               self.got["opening"]["camera"]["far"], delta=0.1)
        # ... and a scene with no house in it: the stage, as Reset view gives.
        self.assertAlmostEqual(self.got["legacy"]["house"]["far"],
                               self.got["legacy"]["camera"]["far"], delta=0.1)

    def test_the_speed_bar_is_for_when_animals_are_the_subject(self):
        """It sat over every picture. Walking among them or Identify makes
        them the subject; a yard just being looked at does not."""
        animals = self.got["animals"]
        self.assertFalse(animals["at_rest"])
        self.assertTrue(animals["identify"])
        self.assertFalse(animals["after"])
        self.assertTrue(animals["walking"])
        with open(os.path.join(render_yard.HTML, "scene3d", "07-wildlife.js"),
                  encoding="utf-8") as fh:
            src = fh.read()
        self.assertIn("const show = _speedBarWanted();", src)
        self.assertIn("if (!_speedBarWanted()) return;", src,
                      "Space pauses animals with no bar on screen to say so")
        self.assertRegex(src, r"_wildSpeed !== 1 \|\| typeof animalsAreSubject",
                         "a paused scene must keep its bar")

    # ── the frame-rate readout ───────────────────────────────────────────────

    def test_the_readout_shows_only_when_asked_for(self):
        perf = self.got["perf"]
        self.assertFalse(perf["before"], "the readout is on without being asked")
        self.assertTrue(perf["shown"], "Ctrl+Shift+F did not show it")
        self.assertTrue(perf["hidden"], "Ctrl+Shift+F did not hide it again")
        for key in ("fps", "frame_ms", "triangles", "calls", "plants", "detail"):
            self.assertIn(key, perf["reads"])


class TheProbeIsADevPage(unittest.TestCase):

    def test_the_viewer_knows_nothing_of_it(self):
        with open(os.path.join(render_yard.HTML, "scene3d", "chunks.js"),
                  encoding="utf-8") as fh:
            self.assertNotIn("yard_probe", fh.read())

    def test_it_loads_the_error_watcher(self):
        with open(os.path.join(render_yard.HTML, "yard_probe.html"),
                  encoding="utf-8") as fh:
            self.assertIn('src="probe_watch.js"', fh.read())


if __name__ == "__main__":
    unittest.main()

"""
tests/test_pond_planting.py — water plants go in the pond (F185, V2.95).

Until V2.95 a water plant the design asked for was positioned like any other
plant, and the pond was placed after them all: in a measured design, 0 of 6 water
plants stood in water, 9 to 28 m from the pond. A seeded pond community landed on
dry ground as a unit, a pond the spec left bare stayed bare, and in the app the
generated pond never reached the map at all.

The first class is the geometry, no database. The second drives the generator end
to end with a fake AI client (no network, no zoning) and asks the 3D scene where
each water plant is, since the scene is what decides whether a pond-lily floats.
The third is the app's side: the generated structures reach the live project.
"""

import math
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_TMP_DIR = tempfile.mkdtemp(prefix="permadesign_pond_planting_test_")
_DB_PATH = os.path.join(_TMP_DIR, "permadesign_test.db")
import src.db.plants as _plants_mod  # noqa: E402
import src.permadesign_api as _api  # noqa: E402


def _use_our_db() -> None:
    from src.db.plants import init_db
    _plants_mod._DATA_DIR = _TMP_DIR
    _plants_mod._DB_PATH = _DB_PATH
    init_db()
    _api._DB_READY = True


import src.llm_design as llm  # noqa: E402
from src import pond_habit  # noqa: E402
from src import pond_planting as pp  # noqa: E402
from src.zoning import needs_standing_water  # noqa: E402

_LAT, _LNG = 53.5461, -113.4938
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _seed_rows() -> list:
    import json
    with open(os.path.join(_ROOT, "data", "plants_master.json"),
              encoding="utf-8") as fh:
        return json.load(fh)


# ── the geometry, no database ────────────────────────────────────────────────

class _Placed:
    """Just enough of a Project for PondSeats: plants placed so far."""

    def __init__(self):
        self.placed_plants = []

    def put(self, row, spot):
        self.placed_plants.append({"plant_id": row["id"], "lat": spot[0],
                                   "lng": spot[1]})


class TheRule(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        rows = _seed_rows()
        for i, r in enumerate(rows):
            r.setdefault("id", i + 1)
        cls.rows = {r["common_name"]: r for r in rows}
        cls.by_id = {r["id"]: r for r in rows}

    def seats(self, placed, size=6.0):
        return pp.PondSeats(placed, [pp.Pond(_LAT, _LNG, size)],
                            row_of=lambda pid: self.by_id.get(pid, {}))

    def test_every_water_plant_has_a_role_and_nothing_else_does(self):
        roles = {}
        for name, r in self.rows.items():
            role = pp.role_of(r)
            self.assertEqual(role is not None, needs_standing_water(r), name)
            if role:
                roles.setdefault(role, []).append(name)
        self.assertEqual(len(roles[pp.OPEN]), 7, roles[pp.OPEN])
        self.assertEqual(len(roles[pp.MARGIN]), 16, roles[pp.MARGIN])
        self.assertIn("Yellow Pond-lily", roles[pp.OPEN])
        self.assertIn("Sago Pondweed", roles[pp.OPEN])
        self.assertIn("Cattail", roles[pp.MARGIN])

    def _uv(self, spot, size=6.0):
        return pp.Pond(_LAT, _LNG, size).uv(*spot)

    def test_open_water_seats_are_on_the_water_the_scene_draws(self):
        placed = _Placed()
        seats = self.seats(placed)
        pond = [{"struct_id": "pond", "x": 0.0, "y": 0.0, "size_m": 6.0}]
        for name in ("Yellow Pond-lily", "Sago Pondweed", "Canada Waterweed",
                     "Floating Marsh-marigold"):
            spot = seats.seat(self.rows[name])
            self.assertIsNotNone(spot, name)
            placed.put(self.rows[name], spot)
            u, v = self._uv(spot)
            with self.subTest(name):
                self.assertLessEqual(math.hypot(u, v), pp.OPEN_REACH + 1e-6)
                x, y = pp.Pond(_LAT, _LNG, 6.0).xy(*spot)
                self.assertGreater(pond_habit.water_at(x, y, pond), 0.0,
                                   "the 3D scene would draw it on dry ground")

    def test_emergents_stand_in_the_shallows_on_the_north_shore(self):
        placed = _Placed()
        seats = self.seats(placed)
        for _ in range(8):
            spot = seats.seat(self.rows["Cattail"])
            self.assertIsNotNone(spot)
            placed.put(self.rows["Cattail"], spot)
            u, v = self._uv(spot)
            self.assertAlmostEqual(math.hypot(u, v), pp.MARGIN_REACH, delta=1e-6)
            bearing = math.degrees(math.atan2(u, v))
            self.assertLessEqual(abs(bearing), pp.SHORE_ARC_DEG + 1e-6,
                                 "an emergent on the open south shore")
        # The first one is due north.
        u, v = self._uv((placed.placed_plants[0]["lat"],
                         placed.placed_plants[0]["lng"]))
        self.assertAlmostEqual(u, 0.0, places=6)

    def test_seats_keep_their_spacing(self):
        placed = _Placed()
        seats = self.seats(placed)
        for _ in range(12):
            spot = seats.seat(self.rows["Cattail"])
            if spot is None:
                break
            placed.put(self.rows["Cattail"], spot)
        pond = pp.Pond(_LAT, _LNG, 6.0)
        pts = [pond.xy(p["lat"], p["lng"]) for p in placed.placed_plants]
        need = pp.spacing_m(self.rows["Cattail"])
        for i, a in enumerate(pts):
            for b in pts[i + 1:]:
                self.assertGreaterEqual(math.dist(a, b), need - 1e-6)

    def test_floating_leaves_shade_at_most_half_the_water(self):
        """Filled by leaves at the pond's rim, clear of the open water's seats,
        so what refuses the next floating plant is the shade and not the room."""
        pond = pp.Pond(_LAT, _LNG, 6.0)
        big = dict(self.rows["Yellow Pond-lily"], id=-1, spacing_m=2.0)
        self.by_id[-1] = big
        small = self.rows["Floating Marsh-marigold"]
        weed = self.rows["Sago Pondweed"]
        leaf = math.pi * (pp.spacing_m(big) / 2.0) ** 2
        half = pp.FLOATING_SHARE * pond.water_m2
        placed = _Placed()
        rim = [(0.97 * math.sin(a), 0.97 * math.cos(a))
               for a in (math.radians(d) for d in (0, 120, 240))]
        for u, v in rim[:2]:
            placed.put(big, pond.at(u, v))
        self.assertLess(2 * leaf + math.pi * (pp.spacing_m(small) / 2) ** 2, half)
        self.assertIsNotNone(self.seats(placed).seat(small),
                             "under half shaded, a small leaf fits")
        placed.put(big, pond.at(*rim[2]))
        self.assertGreater(3 * leaf, half)
        self.assertIsNone(self.seats(placed).seat(small),
                          "more than half the water shaded by floating leaves")
        self.assertIsNotNone(self.seats(placed).seat(weed),
                             "a submerged plant shades nothing")

    def test_no_pond_no_seat(self):
        seats = pp.PondSeats(_Placed(), [])
        self.assertFalse(seats)
        self.assertIsNone(seats.seat(self.rows["Cattail"]))

    def test_the_pond_communities_are_the_seeded_pond_assemblages(self):
        wet = [self.rows[n] for n in ("Cattail", "Buckbean", "Yellow Pond-lily")]
        dry = [self.rows[n] for n in ("Wild Bergamot", "Boreal Yarrow")]
        self.assertTrue(pp.is_pond_community(wet + dry[:1]))
        self.assertFalse(pp.is_pond_community(dry + [self.rows["Cattail"]]))
        self.assertFalse(pp.is_pond_community([]))

    def test_the_milfoil_is_never_chosen_by_the_generator_itself(self):
        # First in the pool, so without the rule it would be the submerged pick.
        milfoil = self.rows["Spiked Water-milfoil"]
        rows = [milfoil] + [r for r in self.rows.values()
                            if needs_standing_water(r) and r is not milfoil]
        self.assertEqual(pond_habit.body_for(milfoil), "submerged")
        chosen = pp.bare_pond_choices(rows)
        names = [r["common_name"] for r, _ in chosen]
        self.assertNotIn("Spiked Water-milfoil", names)
        self.assertEqual([pp.role_of(r) for r, _ in chosen],
                         [pp.OPEN, pp.OPEN, pp.MARGIN, pp.MARGIN])
        bodies = [pond_habit.body_for(r) for r, _ in chosen]
        self.assertEqual(bodies[:2], ["floating", "submerged"])


# ── the generator, end to end ────────────────────────────────────────────────

class _FakeClient:
    endpoint = "fake://local"
    model = "fake-model"

    def __init__(self, spec):
        self._spec = spec

    def generate_spec(self, prompt, context, extra_hints=None):
        return self._spec


def _square(side_m=30.0):
    dlat = side_m / 111320.0
    dlng = side_m / (111320.0 * math.cos(math.radians(_LAT)))
    return [(_LAT, _LNG), (_LAT + dlat, _LNG), (_LAT + dlat, _LNG + dlng),
            (_LAT, _LNG + dlng)]


def _generate(spec, **kw):
    return llm.generate_design(
        "pond", boundary=_square(), client=_FakeClient(spec),
        match_site=False, revise=False, density="none", **kw)


_DRY = [{"query": "Wild Bergamot", "quantity": 4},
        {"query": "Red Osier Dogwood", "quantity": 2},
        {"query": "Blue Grama Grass", "quantity": 5}]
_WET = [{"query": "Yellow Pond-lily", "quantity": 2},
        {"query": "Cattail", "quantity": 3},
        {"query": "Sago Pondweed", "quantity": 1}]
_POND = [{"id": "pond"}]


def _notes(project):
    return project.as_dict().get("properties", {}).get("generation_warnings", [])


class TheGenerator(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        _use_our_db()
        from src.scene_contract import build_scene
        from src.db.plants import get_plant
        cls.build_scene = staticmethod(build_scene)
        cls.get_plant = staticmethod(get_plant)

    def scene(self, project):
        return self.build_scene(project.as_dict(), year=0, wind=False)

    def water_plants(self, scene):
        return [p for p in scene["plants"]
                if needs_standing_water(self.get_plant(p["plant_id"]) or {})]

    def assert_in_the_pond(self, scene, plants):
        ponds = [s for s in scene["structures"] if s["struct_id"] == "pond"]
        self.assertTrue(ponds, "no pond in the scene")
        for p in plants:
            with self.subTest(p["common_name"], x=p["x"], y=p["y"]):
                self.assertGreater(
                    pond_habit.water_at(p["x"], p["y"], ponds), 0.0,
                    f"{p['common_name']} is on dry ground")
                body = (p.get("drawn") or {}).get("body")
                if body in ("floating", "submerged"):
                    self.assertGreater(p["drawn"]["water_m"], 0.0,
                                       "the scene draws it on the ground")

    def test_the_spec_water_plants_go_in_the_pond(self):
        proj = _generate({"plants": _DRY + _WET, "structures": _POND})
        scene = self.scene(proj)
        wet = self.water_plants(scene)
        self.assertEqual(sorted(p["common_name"] for p in wet),
                         ["Cattail"] * 3 + ["Sago Pondweed"]
                         + ["Yellow Pond-lily"] * 2)
        self.assert_in_the_pond(scene, wet)

    def test_with_no_pond_they_are_left_out_and_named(self):
        proj = _generate({"plants": _DRY + _WET})
        self.assertEqual(self.water_plants(self.scene(proj)), [])
        notes = [n for n in _notes(proj) if n.startswith("Left out")]
        self.assertEqual(len(notes), 1, _notes(proj))
        for name in ("Yellow Pond-lily", "Cattail", "Sago Pondweed"):
            self.assertIn(name, notes[0])
        self.assertIn("no pond", notes[0])

    def test_the_dry_design_is_not_moved_by_its_water_plants(self):
        """Water plants are taken out of the spec before anything is placed, so
        the rest of the design is laid out exactly as it would be without them."""
        with_water = _generate({"plants": _DRY + _WET, "structures": _POND})
        without = _generate({"plants": _DRY, "structures": _POND})

        def dry(p):
            return sorted((q["common_name"], round(q["lat"], 7), round(q["lng"], 7))
                          for q in p.placed_plants
                          if not needs_standing_water(
                              self.get_plant(q["plant_id"]) or {}))
        self.assertEqual(dry(with_water), dry(without))

    def test_a_bare_pond_is_planted(self):
        proj = _generate({"plants": _DRY, "structures": _POND})
        scene = self.scene(proj)
        wet = self.water_plants(scene)
        self.assert_in_the_pond(scene, wet)
        bodies = [(p.get("drawn") or {}).get("body") for p in wet]
        self.assertIn("floating", bodies)
        self.assertIn("submerged", bodies)
        margin = {p["common_name"] for p in wet
                  if (p.get("drawn") or {}).get("body")
                  not in ("floating", "submerged")}
        self.assertGreaterEqual(len(margin), 2, wet)
        self.assertNotIn("Spiked Water-milfoil",
                         {p["common_name"] for p in wet})
        self.assertTrue(any(n.startswith("Planted the pond") for n in _notes(proj)),
                        _notes(proj))

    def test_a_pond_community_is_seated_in_the_pond(self):
        proj = _generate({"plants": _DRY, "structures": _POND,
                          "communities": [{"name": "Pond & Aquatic Edge",
                                           "count": 1}]})
        members = [q for q in proj.placed_plants
                   if q.get("polyculture_name") == "Pond & Aquatic Edge"]
        self.assertEqual(len(members), 9, [q["common_name"] for q in members])
        pond = pp.ponds_in(proj.as_dict()["features"])[0]
        for q in members:
            u, v = pond.uv(q["lat"], q["lng"])
            with self.subTest(q["common_name"]):
                self.assertLessEqual(math.hypot(u, v), 1.0,
                                     "a pond-community member out of the water")
        self.assertFalse(any(n.startswith("Planted the pond")
                             for n in _notes(proj)),
                         "a pond the spec planted was planted again")

    def test_a_pond_the_user_drew_takes_the_water_plants(self):
        from src.db.structures import get_structure
        pond_ll = (_LAT + 20 / 111320.0,
                   _LNG + 20 / (111320.0 * math.cos(math.radians(_LAT))))
        existing = [{"type": "Feature",
                     "geometry": {"type": "Point",
                                  "coordinates": [pond_ll[1], pond_ll[0]]},
                     "properties": {"element_type": "structure",
                                    "struct_id": "pond",
                                    "struct_def": dict(get_structure("pond"))}}]
        proj = _generate({"plants": _DRY + _WET}, existing_features=existing)
        pond = pp.ponds_in(existing)[0]
        wet = [q for q in proj.placed_plants
               if needs_standing_water(self.get_plant(q["plant_id"]) or {})]
        self.assertEqual(len(wet), 6)
        for q in wet:
            u, v = pond.uv(q["lat"], q["lng"])
            self.assertLessEqual(math.hypot(u, v), 1.0, q["common_name"])
        self.assertFalse(any(n.startswith("Planted the pond")
                             for n in _notes(proj)),
                         "the user's own pond was planted for them")

    def test_an_animal_fed_only_by_water_plants_gets_one_in_the_pond(self):
        from src.db.fauna import list_fauna
        animal = list_fauna()[0]
        # Neither is among what the review plants in a bare pond, so the animal
        # is not already served when its top-up runs.
        wet = [self.get_plant(self._id("Giant Bur-reed")),
               self.get_plant(self._id("Yellow Pond-lily"))]
        proj = _generate({"plants": _DRY, "structures": _POND})
        before = len(proj.placed_plants)
        seats = llm._pond_seats(proj)
        llm._apply_fauna_feedback(proj, [animal["id"]], lambda **f: list(wet),
                                  (_LAT, _LNG), _square(), pond=seats)
        self.assertEqual(len(proj.placed_plants), before + 1)
        added = proj.placed_plants[-1]
        self.assertIn(added["common_name"], ("Giant Bur-reed", "Yellow Pond-lily"))
        pond = pp.ponds_in(proj.as_dict()["features"])[0]
        u, v = pond.uv(added["lat"], added["lng"])
        self.assertLessEqual(math.hypot(u, v), 1.0)
        self.assertFalse(any("standing water" in n and animal["common_name"] in n
                             for n in _notes(proj)))

    def _id(self, name):
        from src.db.plants import get_connection
        conn = get_connection()
        try:
            return conn.execute("SELECT id FROM plants WHERE common_name = ?",
                                (name,)).fetchone()["id"]
        finally:
            conn.close()


# ── the app: the generated structures reach the map ─────────────────────────

class TheAppKeepsTheStructures(unittest.TestCase):
    """``_render`` copied only plants into the live project (until V2.95)."""

    @classmethod
    def setUpClass(cls):
        try:
            import src.controllers.generation as gen  # PyQt6 at import
        except Exception as exc:  # noqa: BLE001
            raise unittest.SkipTest(f"generation controller needs PyQt6: {exc}")
        cls.gen = gen
        _use_our_db()

    def test_render_carries_the_pond_onto_the_map(self):
        from unittest import mock
        proj = _generate({"plants": _DRY + _WET, "structures": _POND})

        main = mock.MagicMock()
        main._project = {"type": "FeatureCollection", "features": [],
                         "properties": {}}
        main._placed_plants = {}
        main._store = None
        del main._persistence                         # no checkpoint wiring
        main._plant_info.return_value = (0.5, "wildflower", None)
        ctl = self.gen.GenerationController(main)
        with mock.patch.object(self.gen, "QMessageBox"), \
                mock.patch.object(self.gen, "store_for") as store:
            ctl._render(proj)
        feats = [f for f in main._project["features"]
                 if f["properties"].get("element_type") == "structure"]
        self.assertEqual([f["properties"]["struct_id"] for f in feats], ["pond"])
        props = feats[0]["properties"]
        self.assertEqual(props["struct_def"]["id"], "pond")
        self.assertEqual(props["size_m"], 6.0)
        self.assertEqual(main.map_widget.load_structure.call_count, 1)
        sd, lat, lng = main.map_widget.load_structure.call_args[0]
        self.assertEqual(sd["id"], "pond")
        self.assertEqual(feats[0]["geometry"]["coordinates"], [lng, lat])
        self.assertTrue(store.return_value.add_plant.called)


if __name__ == "__main__":
    unittest.main()

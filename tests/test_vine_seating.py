"""
tests/test_vine_seating.py — the generator plants a vine at the foot of a tree
or shrub (F181, V2.90), and says so when nothing can hold one (the owner's
option c).

The first class is pure geometry (no DB). The second drives the generator end
to end with a fake LLM client, no network and no zoning, and asks the 3D scene
itself whether each vine climbs.
"""

import inspect
import math
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_TMP_DIR = tempfile.mkdtemp(prefix="permadesign_vine_seating_test_")
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
from src import vine_seating as vs  # noqa: E402
from src.projection import Projector  # noqa: E402

_LAT, _LNG = 53.5461, -113.4938


def _xy(host, spot):
    """``spot`` in metres east and north of ``host``."""
    return Projector(*host).to_xy(*spot)


def _bearing(host, spot):
    x, y = _xy(host, spot)
    return math.degrees(math.atan2(x, y)) % 360.0


class TheSeat(unittest.TestCase):
    """Where one vine goes, with no database."""

    HOST = (_LAT, _LNG)

    def _seats(self, fits=lambda la, ln: True):
        return vs.VineSeats(fits)

    def test_half_the_crown_radius_from_the_centre_within_bounds(self):
        self.assertAlmostEqual(vs.seat_distance_m(3.0), 0.6)
        self.assertAlmostEqual(vs.seat_distance_m(1.2), 0.3)
        self.assertAlmostEqual(vs.seat_distance_m(0.4), vs.SEAT_MIN_M)
        self.assertAlmostEqual(vs.seat_distance_m(12.0), vs.SEAT_MAX_M)

    def test_how_many_vines_a_host_carries(self):
        self.assertEqual(vs.capacity("shrub", 1.5), 1)
        self.assertEqual(vs.capacity("shrub", 3.0), 2)
        self.assertEqual(vs.capacity("tree", 5.0), 2)
        self.assertEqual(vs.capacity("tree", 7.5), 3)
        # The owner's rule: nothing but a tree or shrub holds a vine up.
        for other in ("wildflower", "grass", "vine", "groundcover", ""):
            self.assertEqual(vs.capacity(other, 5.0), 0, other)

    def test_only_a_tree_or_shrub_becomes_a_host(self):
        seats = self._seats()
        seats.add_host(*self.HOST, "wildflower", 1.0)
        seats.add_host(*self.HOST, "vine", 1.5)
        self.assertEqual(seats.hosts, 0)
        self.assertIsNone(seats.seat([self.HOST]))

    def test_the_first_vine_goes_on_the_sunny_side_at_the_base(self):
        seats = self._seats()
        seats.add_host(*self.HOST, "shrub", 3.0)
        spot = seats.seat([self.HOST])
        self.assertIsNotNone(spot)
        self.assertAlmostEqual(_bearing(self.HOST, spot), 180.0, delta=0.5)
        self.assertAlmostEqual(math.hypot(*_xy(self.HOST, spot)), 0.6,
                               delta=0.01)

    def test_a_second_vine_on_one_host_goes_round_it(self):
        seats = self._seats()
        seats.add_host(*self.HOST, "shrub", 3.0)
        a = seats.seat([self.HOST])
        b = seats.seat([self.HOST, a])
        gap = abs(_bearing(self.HOST, a) - _bearing(self.HOST, b)) % 360
        self.assertGreaterEqual(min(gap, 360 - gap), vs.MIN_SEPARATION_DEG)

    def test_a_full_host_takes_no_more(self):
        seats = self._seats()
        seats.add_host(*self.HOST, "shrub", 1.0)          # room for one
        placed = [self.HOST, seats.seat([self.HOST])]
        self.assertIsNone(seats.seat(placed))

    def test_the_least_used_host_goes_first(self):
        other = Projector(*self.HOST).to_latlng(10.0, 0.0)
        seats = self._seats()
        seats.add_host(*self.HOST, "shrub", 3.0)
        seats.add_host(*other, "shrub", 3.0)
        placed = [self.HOST, other]
        a = seats.seat(placed)
        b = seats.seat(placed + [a])
        near = lambda s, h: math.hypot(*_xy(h, s)) < 1.0      # noqa: E731
        self.assertTrue(near(a, self.HOST))
        self.assertTrue(near(b, other), "both vines went on the first shrub")

    def test_a_seat_that_may_not_be_planted_is_passed_over(self):
        proj = Projector(*self.HOST)

        def fits(la, ln):                  # nothing south of the host
            return proj.to_xy(la, ln)[1] > -0.1
        seats = self._seats(fits)
        seats.add_host(*self.HOST, "shrub", 3.0)
        spot = seats.seat([self.HOST])
        self.assertAlmostEqual(_bearing(self.HOST, spot), 270.0, delta=0.5)

    def test_a_seat_on_top_of_another_plant_is_passed_over(self):
        proj = Projector(*self.HOST)
        herb = proj.to_latlng(0.0, -0.55)  # 5 cm from the south seat
        seats = self._seats()
        seats.add_host(*self.HOST, "shrub", 3.0)
        spot = seats.seat([self.HOST, herb])
        self.assertNotAlmostEqual(_bearing(self.HOST, spot), 180.0, delta=1)

    def test_the_host_does_not_crowd_its_own_vine(self):
        seats = self._seats()
        seats.add_host(*self.HOST, "shrub", 0.8)          # seat 0.25 m out
        self.assertIsNotNone(seats.seat([self.HOST]))


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


def _generate(plants):
    return llm.generate_design(
        "vines", boundary=_square(), client=_FakeClient({"plants": plants}),
        match_site=False, revise=False, density="none")


def _vines(scene):
    return [p for p in scene["plants"] if p.get("plant_type") == "vine"]


class TheGenerator(unittest.TestCase):
    """End to end: a generated design, asked of the 3D scene."""

    WOODY_AND_VINES = [
        {"query": "Red Osier Dogwood", "quantity": 1},
        {"query": "Trembling Aspen", "quantity": 1},
        {"query": "Wild Clematis", "quantity": 3},
        {"query": "Wild Vetch", "quantity": 2},
    ]
    VINES_ONLY = [
        {"query": "Wild Clematis", "quantity": 1},
        {"query": "Wild Vetch", "quantity": 2},
        {"query": "yarrow", "quantity": 3},
    ]

    @classmethod
    def setUpClass(cls):
        _use_our_db()
        from src.scene_contract import build_scene
        cls.build_scene = staticmethod(build_scene)

    def test_every_vine_climbs_a_tree_or_shrub_beside_it(self):
        project = _generate(self.WOODY_AND_VINES)
        scene = self.build_scene(project.as_dict(), year=0, wind=False)
        vines = _vines(scene)
        self.assertEqual(len(vines), 5)
        for v in vines:
            with self.subTest(v["common_name"], x=v["x"], y=v["y"]):
                self.assertEqual(v["drawn"]["habit"], "climbing",
                                 "a generated vine with a host in the design "
                                 "was left on the ground")
                self.assertIn(v["drawn"]["support"]["plant_type"],
                              ("tree", "shrub"))

    def test_a_vine_is_seated_at_the_base_of_its_host(self):
        project = _generate(self.WOODY_AND_VINES)
        scene = self.build_scene(project.as_dict(), year=0, wind=False)
        for v in _vines(scene):
            s = v["drawn"].get("support")
            with self.subTest(v["common_name"]):
                self.assertIsNotNone(s, "seated on nothing")
                d = math.hypot(v["x"] - s["x"], v["y"] - s["y"])
                self.assertGreaterEqual(d, vs.SEAT_MIN_M - 0.02)
                self.assertLessEqual(d, vs.SEAT_MAX_M + 0.02)

    def test_no_host_carries_more_than_its_share(self):
        project = _generate(self.WOODY_AND_VINES)
        scene = self.build_scene(project.as_dict(), year=0, wind=False)
        plants = scene["plants"]
        per_host = {}
        for v in _vines(scene):
            s = v["drawn"].get("support")
            self.assertIsNotNone(s, f"{v['common_name']} is seated on nothing")
            per_host[s["index"]] = per_host.get(s["index"], 0) + 1
        for i, n in per_host.items():
            host = plants[i]
            with self.subTest(host["common_name"]):
                self.assertLessEqual(
                    n, vs.capacity(host["plant_type"], host["canopy_m"]))

    def test_with_a_host_for_every_vine_there_is_no_note(self):
        project = _generate(self.WOODY_AND_VINES)
        notes = project.as_dict()["properties"].get("generation_warnings", [])
        self.assertFalse([n for n in notes if n.startswith("Nothing here")])

    def test_with_nothing_to_climb_a_vine_is_placed_and_noted(self):
        project = _generate(self.VINES_ONLY)
        names = [p["common_name"] for p in project.placed_plants]
        self.assertEqual(names.count("Wild Clematis"), 1)
        self.assertEqual(names.count("Wild Vetch"), 2)
        notes = [n for n in project.as_dict()["properties"].get(
            "generation_warnings", []) if n.startswith("Nothing here")]
        self.assertEqual(len(notes), 1, "option (c): exactly one note")
        self.assertIn("Wild Clematis", notes[0])
        self.assertIn("Wild Vetch (×2)", notes[0])

    def test_the_same_design_seats_the_same_way(self):
        a = [(p["plant_id"], round(p["lat"], 9), round(p["lng"], 9))
             for p in _generate(self.WOODY_AND_VINES).placed_plants]
        b = [(p["plant_id"], round(p["lat"], 9), round(p["lng"], 9))
             for p in _generate(self.WOODY_AND_VINES).placed_plants]
        self.assertEqual(a, b)

    def test_both_generators_end_with_the_note(self):
        for fn in (llm.generate_design, llm.generate_design_offline):
            with self.subTest(fn.__name__):
                self.assertIn("_note_vines_without_support(project, "
                              "existing_features)", inspect.getsource(fn))


class TheNote(unittest.TestCase):
    """What the note counts: the whole design, but only the generated vines."""

    @classmethod
    def setUpClass(cls):
        _use_our_db()
        cls.ids = {r["common_name"]: r["id"] for r in (
            _api.query_plants(query="Wild Vetch")[:1]
            + _api.query_plants(query="Red Osier Dogwood")[:1])}

    def _feature(self, name, dx=0.0, dy=0.0):
        from src.project_store import plant_feature
        lat, lng = Projector(_LAT, _LNG).to_latlng(dx, dy)
        return plant_feature({"plant_id": self.ids[name], "common_name": name,
                              "lat": lat, "lng": lng})

    def _project(self, *features):
        return {"type": "FeatureCollection",
                "properties": {"site_config": {}},
                "features": list(features)}

    def test_a_lone_vine_is_named(self):
        gen = self._project(self._feature("Wild Vetch"))
        self.assertEqual(vs.vines_with_nothing_to_climb(gen), ["Wild Vetch"])

    def test_a_shrub_already_in_the_users_design_holds_a_generated_vine(self):
        gen = self._project(self._feature("Wild Vetch", dy=-0.6))
        users = [self._feature("Red Osier Dogwood")]
        self.assertEqual(vs.vines_with_nothing_to_climb(gen, users), [])

    def test_the_users_own_vines_are_not_reported(self):
        gen = self._project()
        users = [self._feature("Wild Vetch", dx=20.0)]
        self.assertEqual(vs.vines_with_nothing_to_climb(gen, users), [])

    def test_the_note_reads_as_a_sentence(self):
        self.assertEqual(
            vs.climb_note(["Wild Vetch"]),
            "Nothing here for Wild Vetch to climb: no tree or shrub stands "
            "beside it, so it grows along the ground. Plant it at the foot of "
            "a shrub or tree and it will climb.")
        self.assertIn("Purple Peavine and Wild Vetch (×2) to climb",
                      vs.climb_note(["Wild Vetch", "Purple Peavine",
                                     "Wild Vetch"]))


if __name__ == "__main__":
    unittest.main()

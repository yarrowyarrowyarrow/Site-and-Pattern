"""
tests/test_open_ground.py — where the design review plants what it adds
(F183, V2.91).

Until V2.91 the critic's repairs and the goal and wildlife top-ups put every
plant they added on the boundary's first 6 m grid cell: a willow, a buckbean and
a sunflower stood on one point, and the buckbean, a bog plant, went into a dry
yard. Three classes:

  1. ``OpenGround`` on hand-built designs (temp DB, no network, no zoning).
  2. The generator end to end with a fake LLM client, and the two top-ups with
     fake catalogue searches.
  3. ``zoning.needs_standing_water`` against the seed data.
"""

import json
import math
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_TMP_DIR = tempfile.mkdtemp(prefix="permadesign_open_ground_test_")
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
from src.open_ground import OpenGround  # noqa: E402
from src.projection import Projector  # noqa: E402

_LAT, _LNG = 53.5461, -113.4938
_EDM = {"latitude": _LAT, "longitude": _LNG}
_SW = Projector(_LAT, _LNG)


def _at(x, y):
    """``(lat, lng)`` of a point ``x`` m east and ``y`` m north of the SW
    corner every test boundary starts from."""
    return _SW.to_latlng(x, y)


def _box(w, h):
    return [_at(0, 0), _at(0, h), _at(w, h), _at(w, 0)]


def _m(a, b):
    return Projector(*a).distance_m(a[0], a[1], b[0], b[1])


class _Fake:
    endpoint = "fake://"
    model = "fake"

    def __init__(self, spec):
        self.spec = spec

    def generate_spec(self, prompt, context, extra_hints=None):
        return self.spec


class _Base(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        _use_our_db()
        from src.permadesign_api import query_plants
        cls.rows = {r["common_name"]: r for r in query_plants()}

    def row(self, name):
        self.assertIn(name, self.rows, f"catalogue lost {name!r}")
        return self.rows[name]

    def project(self, boundary=None):
        from src.permadesign_api import Project
        return Project.create("open-ground-test", site_config=_EDM,
                              boundary=boundary)

    def place(self, proj, name, spot):
        proj.place_plant(self.row(name)["id"], spot[0], spot[1], quantity=1)

    def yarrow_drift(self, proj, cx, cy, n=3, step=0.6):
        for i in range(n):
            for j in range(n):
                self.place(proj, "Boreal Yarrow",
                           _at(cx + (i - 1) * step, cy + (j - 1) * step))

    def others(self, proj, spot):
        """Distance from ``spot`` to the nearest placed plant not at it."""
        return min((_m(spot, (p["lat"], p["lng"]))
                    for p in proj.placed_plants
                    if _m(spot, (p["lat"], p["lng"])) > 1e-6),
                   default=float("inf"))


class TestOpenGround(_Base):
    """One plant at a time, from the plants actually placed."""

    def add(self, proj, ground, name):
        spot = ground.spot_for(self.row(name))
        self.place(proj, name, spot)
        return spot

    def test_three_additions_stand_apart_at_their_spacing(self):
        b = _box(20, 20)
        proj = self.project(b)
        self.yarrow_drift(proj, 10, 10)
        ground = llm._open_ground(proj, b, _at(10, 10))
        names = ("Basket Willow", "Rough Fescue", "Maximilian Sunflower")
        spots = [self.add(proj, ground, n) for n in names]
        self.assertEqual(len({(round(a, 7), round(b_, 7)) for a, b_ in spots}),
                         3, "additions share a spot")
        placed = proj.placed_plants
        for name, spot in zip(names, spots):
            own = llm._plant_spacing_m(self.row(name)["id"])
            with self.subTest(name):
                self.assertTrue(llm._inside_boundary(b, *spot))
                for p in placed:
                    d = _m(spot, (p["lat"], p["lng"]))
                    if d < 1e-6:
                        continue
                    need = (own + llm._plant_spacing_m(p["plant_id"])) / 2
                    self.assertGreaterEqual(d + 1e-6, need,
                                            f"{name} crowds {p['common_name']}")
                # With no terrain to choose by, it joins the planting rather
                # than standing alone in a corner of a 20 m yard.
                self.assertLess(self.others(proj, spot), 3.0)

    def test_keep_out_is_kept_out_of(self):
        b = _box(20, 20)
        proj = self.project(b)
        self.yarrow_drift(proj, 10, 10)
        tree = _at(13, 10)                     # an existing tree beside it
        ground = llm._open_ground(proj, b, _at(10, 10),
                                  keepout=[(tree[0], tree[1], 4.0)])
        for name in ("Basket Willow", "Maximilian Sunflower"):
            spot = self.add(proj, ground, name)
            own = llm._plant_spacing_m(self.row(name)["id"])
            with self.subTest(name):
                self.assertGreaterEqual(_m(spot, tree) + 1e-6, 4.0 + own / 2)

    def test_a_drawn_restoration_zone_is_planted_into(self):
        b = _box(20, 20)
        proj = self.project(b)
        self.yarrow_drift(proj, 10, 10)
        zone = [[ln, la] for la, ln in
                (_at(14, 1), _at(19, 1), _at(19, 6), _at(14, 6), _at(14, 1))]
        ground = llm._open_ground(proj, b, _at(10, 10), fills=[zone])
        from src.geometry import point_in_ring
        spot = self.add(proj, ground, "Wild Bergamot")
        self.assertTrue(point_in_ring(spot[0], spot[1], zone))

    def test_a_full_yard_gets_the_least_crowded_spot_not_a_stack(self):
        b = _box(3, 3)
        proj = self.project(b)
        ground = llm._open_ground(proj, b, _at(1.5, 1.5))
        cells = ground._grid([], 0.5)
        hole = cells[len(cells) // 2]
        for c in cells:
            if c != hole:
                self.place(proj, "Wild Bergamot", c)
        # A sunflower needs 0.625 m from a bergamot; the hole leaves 0.5 m,
        # so no spot is free and the hole is the least crowded one.
        spot = ground.spot_for(self.row("Maximilian Sunflower"))
        self.assertLess(_m(spot, hole), 0.01)
        self.assertGreater(self.others(proj, spot), 0.4)

    def test_a_vine_goes_to_the_foot_of_a_shrub(self):
        b = _box(20, 20)
        proj = self.project(b)
        shrub = _at(10, 10)
        self.place(proj, "Basket Willow", shrub)
        ground = llm._open_ground(proj, b, shrub)
        spot = ground.spot_for(self.row("Blue Clematis"))
        self.assertTrue(0.25 - 1e-6 <= _m(spot, shrub) <= 0.6 + 1e-6)
        x, y = Projector(*shrub).to_xy(*spot)
        self.assertAlmostEqual(math.degrees(math.atan2(x, y)) % 360, 180, 3,
                               "the sunny side first")

    def test_a_shrub_that_holds_its_vine_is_not_given_another(self):
        # Common Snowberry's crown is under 2 m: it carries one vine.
        b = _box(20, 20)
        proj = self.project(b)
        shrub = _at(10, 10)
        self.place(proj, "Common Snowberry", shrub)
        ground = llm._open_ground(proj, b, shrub)
        first = self.add(proj, ground, "Blue Clematis")
        self.assertLessEqual(_m(first, shrub), 0.6 + 1e-6)
        second = self.add(proj, ground, "Blue Clematis")
        self.assertGreater(_m(second, shrub), 0.6,
                           "a second vine seated on a one-vine shrub")

    def test_the_designs_own_pond_is_kept_out_of(self):
        # The main pass places structures after its plants, so the keep-out
        # it was handed never had the pond. Leave only the pond open.
        b = _box(8, 8)
        proj = self.project(b)
        pond = _at(4, 4)
        proj.place_structure("pond", pond[0], pond[1])
        ground = llm._open_ground(proj, b, pond)
        for c in ground._grid([], 0.5):
            if _m(c, pond) > 3.3:
                self.place(proj, "Wild Bergamot", c)
        spot = ground.spot_for(self.row("Wild Bergamot"))
        self.assertGreaterEqual(_m(spot, pond) + 1e-6, 3.0 + 0.25)

    def test_with_no_boundary_it_still_finds_room_beside_the_planting(self):
        proj = self.project(None)
        self.yarrow_drift(proj, 0, 0)
        ground = llm._open_ground(proj, None, _at(0, 0))
        spot = ground.spot_for(self.row("Maximilian Sunflower"))
        near = self.others(proj, spot)
        self.assertGreaterEqual(near + 1e-6, (0.75 + 0.6) / 2)
        self.assertLess(near, 3.0)

    def test_with_the_terrain_known_it_picks_ground_that_suits_the_plant(self):
        # East half low and wet, west half high and dry: a willow that likes
        # it moist goes east, a fescue that likes it dry goes west.
        from src.placement_score import CellEnv
        b = _box(20, 20)
        env = {}
        for i in range(4):
            for j in range(4):
                x, y = 2.5 + 5 * i, 2.5 + 5 * j
                env[_at(x, y)] = CellEnv(shade_fraction=0.0,
                                         elevation_pct=0.0 if x > 10 else 1.0,
                                         slope_pct=0.0, aspect_deg=-1.0,
                                         is_edge=False)
        for name, east in (("Basket Willow", True), ("Rough Fescue", False)):
            proj = self.project(b)
            self.yarrow_drift(proj, 10, 10)
            ground = llm._open_ground(proj, b, _at(10, 10), cell_env_map=env)
            x, _y = _SW.to_xy(*ground.spot_for(self.row(name)))
            with self.subTest(name):
                self.assertEqual(x > 10, east, f"{name} at x={x:.1f} m")

    def test_the_same_design_gives_the_same_spot(self):
        spots = []
        for _ in range(2):
            b = _box(20, 20)
            proj = self.project(b)
            self.yarrow_drift(proj, 10, 10)
            spots.append(llm._open_ground(proj, b, _at(10, 10))
                         .spot_for(self.row("Basket Willow")))
        self.assertEqual(spots[0], spots[1])


class TestTheFollowUpSteps(_Base):
    """The generator's repairs and top-ups, end to end and with fakes."""

    def _llm_design(self, **kw):
        from src.db.fauna import list_fauna
        monarch = next((f for f in list_fauna()
                        if "monarch" in (f.get("common_name") or "").lower()),
                       None)
        return llm.generate_design(
            "x", boundary=_box(30, 30), site_config=_EDM,
            client=_Fake({"plants": [{"query": "yarrow", "quantity": 3}]}),
            fauna_ids=[monarch["id"]] if monarch else None,
            match_site=False, revise=False, density="none", **kw)

    def test_what_the_review_adds_stands_apart(self):
        proj = self._llm_design()
        added = [p for p in proj.placed_plants
                 if p["common_name"] != "Boreal Yarrow"]
        self.assertGreaterEqual(len(added), 3, "the review added nothing")
        spots = {(round(p["lat"], 7), round(p["lng"], 7)) for p in added}
        self.assertEqual(len(spots), len(added),
                         "two additions share a spot")
        from src.zoning import needs_standing_water
        from src.db.plants import get_plant
        for p in added:
            with self.subTest(p["common_name"]):
                self.assertGreater(self.others(proj, (p["lat"], p["lng"])),
                                   0.3)
                self.assertFalse(needs_standing_water(get_plant(p["plant_id"])),
                                 "a water plant added to a dry yard")

    def test_offline_additions_stand_apart_too(self):
        # An offline design is usually good enough that the review adds one
        # plant. A thin pool (one species, no communities, no meadow mix)
        # makes it add more. The mix went in V3.14: its forbs rank by
        # availability too since then, and the Smooth Aster it now takes
        # flowers into October, the gap this test had relied on.
        with mock.patch.object(llm, "_OFFLINE_PLANT_CAP", 1), \
                mock.patch.object(llm, "_select_offline_communities",
                                  lambda *a, **k: []), \
                mock.patch.object(llm, "_offline_plant_mix",
                                  lambda *a, **k: None):
            proj = llm.generate_design_offline(
                boundary=_box(12, 18), site_config=_EDM, match_site=False)
        notes = proj.as_dict()["properties"].get("generation_warnings", [])
        names = [n.split("Added ", 1)[1].split(" — ")[0]
                 for n in notes if n.startswith("Added ") and " — " in n]
        self.assertGreaterEqual(len(names), 2, notes)
        spots = [(p["lat"], p["lng"]) for p in proj.placed_plants
                 if p["common_name"] in names]
        self.assertEqual(len(spots), len(names))
        self.assertEqual(len({(round(a, 7), round(b, 7)) for a, b in spots}),
                         len(spots), "two additions share a spot")
        for s in spots:
            self.assertGreater(self.others(proj, s), 0.3)

    def test_an_animal_fed_only_by_water_plants_gets_a_note_not_a_plant(self):
        from src.db.fauna import list_fauna
        animal = list_fauna()[0]
        wet = [self.row("Broad-leaved Arrowhead"), self.row("Yellow Pond-lily")]
        b = _box(20, 20)
        proj = self.project(b)
        llm._apply_fauna_feedback(proj, [animal["id"]], lambda **f: list(wet),
                                  _at(10, 10), b)
        self.assertEqual(proj.placed_plants, [])
        notes = proj.as_dict()["properties"].get("generation_warnings", [])
        self.assertTrue(any(animal["common_name"] in n
                            and "Broad-leaved Arrowhead" in n
                            and "Yellow Pond-lily" in n
                            and "standing water" in n for n in notes), notes)
        self.assertFalse(any(n.startswith("Added plants") for n in notes))

    def test_the_wildlife_top_up_takes_the_first_dry_ground_plant(self):
        from src.db.fauna import list_fauna
        animal = list_fauna()[0]
        rows = [self.row("Buckbean"), self.row("Wild Bergamot")]
        b = _box(20, 20)
        proj = self.project(b)
        llm._apply_fauna_feedback(proj, [animal["id"]], lambda **f: list(rows),
                                  _at(10, 10), b)
        self.assertEqual([p["common_name"] for p in proj.placed_plants],
                         ["Wild Bergamot"])

    def test_the_goal_top_up_skips_water_plants(self):
        b = _box(20, 20)
        proj = self.project(b)
        rows = [self.row("Buckbean"), self.row("Wild Bergamot")]
        llm._apply_goal_feedback(proj, ["native_only"], lambda **f: list(rows),
                                 _at(10, 10), b)
        self.assertEqual([p["common_name"] for p in proj.placed_plants],
                         ["Wild Bergamot"])

        proj = self.project(b)
        llm._apply_goal_feedback(proj, ["native_only"],
                                 lambda **f: [self.row("Buckbean")],
                                 _at(10, 10), b)
        self.assertEqual(proj.placed_plants, [])
        notes = proj.as_dict()["properties"].get("generation_warnings", [])
        self.assertTrue(any("standing water" in n for n in notes), notes)


class TestWhatNeedsStandingWater(unittest.TestCase):
    """The test is narrower than 'likes it wet' on purpose (V2.91)."""

    @classmethod
    def setUpClass(cls):
        from src.zoning import needs_standing_water
        path = Path(__file__).resolve().parent.parent / "data" / \
            "plants_master.json"
        rows = json.loads(path.read_text(encoding="utf-8"))
        cls.by = {r["common_name"]: r for r in rows}
        cls.wet = {n for n, r in cls.by.items() if needs_standing_water(r)}

    def test_every_aquatic_and_every_emergent_needs_water(self):
        for n, r in self.by.items():
            if (r.get("plant_type") == "aquatic"
                    or r.get("growth_form") in ("emergent", "floating",
                                                "submerged")):
                self.assertIn(n, self.wet)
        # The bulrushes filed as sedges, and Water Arum filed as a wildflower.
        for n in ("Alkali Bulrush", "River Bulrush", "Three-square Rush",
                  "Water Arum (Wild Calla)", "Buckbean"):
            self.assertIn(n, self.wet)

    def test_the_plants_that_merely_like_it_wet_do_not(self):
        for n in ("Basket Willow", "Pussy Willow", "Red Osier Dogwood",
                  "Bunchberry", "Meadowsweet", "Flat-topped White Aster"):
            with self.subTest(n):
                self.assertIn(n, self.by)
                self.assertNotIn(n, self.wet)
        self.assertFalse(any(self.by[n].get("plant_type") in ("tree", "shrub")
                             for n in self.wet))


if __name__ == "__main__":
    unittest.main()

"""
tests/test_yard_overview.py — how your yard is doing (OV-1, OV-13, WD-7,
PY-12; V3.27; docs/homeowner/06-yard-overview.md).

Six items in a fixed order, in plain words, every number from the function the
advanced page and the PDF use; cover once grown, the bare ground, and the yard
either side of the house.
"""

import math
import os
import shutil
import sys
import tempfile
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_TMP = tempfile.mkdtemp(prefix="yard_overview_")
import src.db.plants as _plants  # noqa: E402
_plants._DATA_DIR = _TMP
_plants._DB_PATH = os.path.join(_TMP, "permadesign_test.db")

from src import yard_overview as yo  # noqa: E402
from src import yard_overview_items as yi  # noqa: E402

try:
    import shapely  # noqa: F401
    _HAVE_SHAPELY = True
except ImportError:                                        # pragma: no cover
    _HAVE_SHAPELY = False

_LAT, _LNG = 53.5461, -113.4938
_M_LAT = 111320.0
_M_LNG = 111320.0 * math.cos(math.radians(_LAT))


def tearDownModule():
    shutil.rmtree(_TMP, ignore_errors=True)


def _db():
    _plants._DATA_DIR = _TMP
    _plants._DB_PATH = os.path.join(_TMP, "permadesign_test.db")
    _plants.init_db()


def _at(x, y):
    return _LAT + y / _M_LAT, _LNG + x / _M_LNG


def _square(east, north, w, h):
    pts = [(east, north), (east + w, north), (east + w, north + h),
           (east, north + h), (east, north)]
    return [[_LNG + x / _M_LNG, _LAT + y / _M_LAT] for x, y in pts]


def _feature(kind, ring, shape_type=None):
    props = {"element_type": kind}
    if shape_type:
        props["shape_type"] = shape_type
    return {"type": "Feature", "properties": props,
            "geometry": {"type": "Polygon", "coordinates": [ring]}}


def _project(*features, pin=True):
    sc = {"latitude": _LAT, "longitude": _LNG} if pin else {}
    return {"type": "FeatureCollection",
            "properties": {"project_name": "Test yard", "site_config": sc},
            "features": list(features)}


def _plant(project, pid, name, x, y):
    from src.project_store import ProjectStore
    lat, lng = _at(x, y)
    ProjectStore(project).add_plant(pid, name, lat, lng)


def _rows(*pairs):
    """A ``get_plant`` over ``{id: canopy metres}``."""
    table = {pid: {"id": pid, "common_name": f"P{pid}",
                   "mature_canopy_m": width} for pid, width in pairs}
    return lambda pid: table.get(pid)


@unittest.skipUnless(_HAVE_SHAPELY, "shapely not installed")
class CoverOnceGrown(unittest.TestCase):

    def test_discs_clipped_to_the_area(self):
        p = _project(_feature("property_boundary", _square(0, 0, 10, 5)))
        _plant(p, 1, "P1", 2, 2.5)                       # 2 m disc, inside
        _plant(p, 2, "P2", 10, 2.5)                      # 2 m disc, half out
        c = yo.cover(p, get_plant=_rows((1, 2.0), (2, 2.0)))
        self.assertAlmostEqual(c["area_m2"], 50, delta=0.5)
        self.assertAlmostEqual(c["covered_m2"], 1.5 * math.pi, delta=0.1)
        self.assertEqual(yo.share_words(c["share"]), "less than a fifth")

    def test_the_share_words(self):
        for share, words in ((0.9, "almost all"), (0.31, "about a third"),
                             (0.75, "about three quarters"), (0.5,
                             "about half"), (0.1, "less than a fifth")):
            self.assertEqual(yo.share_words(share), words)

    def test_no_outline_no_cover(self):
        self.assertIsNone(yo.cover(_project()))

    def test_the_bare_ground_and_where_filling_plants(self):
        p = _project(_feature("property_boundary", _square(0, 0, 4, 3)))
        _plant(p, 1, "P1", 1, 1.5)
        grid = yo.fill_points(p, 0.6, get_plant=_rows((1, 2.0)))
        self.assertTrue(grid)
        for lat, lng in grid:
            x, y = (lng - _LNG) * _M_LNG, (lat - _LAT) * _M_LAT
            self.assertGreater(math.hypot(x - 1, y - 1.5), 0.99)
            self.assertTrue(0 <= x <= 4 and 0 <= y <= 3)


@unittest.skipUnless(_HAVE_SHAPELY, "shapely not installed")
class FrontAndBack(unittest.TestCase):
    """PY-12: the yard either side of the house, the street to the south
    when no road is known."""

    def test_a_lot_with_its_house(self):
        p = _project(_feature("property_boundary", _square(0, 0, 15, 30)),
                     _feature("canopy_footprint", _square(2, 10, 11, 9),
                              "Building (OSM)"))
        parts = yo.yard_parts(p)
        total = yo.bed_area_m2(p)
        self.assertAlmostEqual(parts["front"] + parts["back"], total, delta=1)
        self.assertAlmostEqual(parts["front"], 15 * 14.5 - 11 * 4.5, delta=1)
        self.assertTrue(parts["assumed"])
        self.assertEqual(yo.parts_words(parts),
                         "Front yard about 170 m², back yard about 180 m².")

    def test_no_house_one_yard_no_outline_none(self):
        p = _project(_feature("property_boundary", _square(0, 0, 10, 10)))
        self.assertEqual(set(yo.yard_parts(p)), {"whole"})
        self.assertEqual(yo.parts_words(yo.yard_parts(p)), "")
        self.assertIsNone(yo.yard_parts(_project()))


class AnimalsByEnglishName(unittest.TestCase):
    """WD-7: an animal is named only by an English name."""

    def test_latin_and_generic_names_are_not_english(self):
        self.assertEqual(yi.english_name(
            {"name": "Andrena amphibola", "scientific_name":
             "Andrena amphibola"}), "")
        self.assertEqual(yi.english_name({"name": "A Leafcutter Bee"}), "")
        self.assertEqual(yi.english_name({"name": "Cedar Waxwing"}),
                         "Cedar Waxwing")

    def test_a_berry_eating_bird_first_then_the_familiar_list(self):
        animals = [
            {"name": "Monarch", "taxon": "lepidoptera", "food": True,
             "plants": {1: ["larval_host"]}},
            {"name": "Cedar Waxwing", "taxon": "bird", "food": True,
             "plants": {2: ["fruit_food"]}},
            {"name": "Ruby-throated Hummingbird", "taxon": "bird",
             "food": True, "plants": {3: ["nectar"]}},
        ]
        self.assertEqual(yi.example_animal(animals), "Cedar Waxwing")
        self.assertEqual(yi.example_animal(animals, ("Monarch",)), "Monarch")


class TheSixItems(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        _db()
        from src.onboarding import build_example_project
        cls.example, _ = build_example_project()
        t = time.perf_counter()
        cls.items = yi.overview(cls.example)
        cls.seconds = time.perf_counter() - t
        cls.by_key = {it.key: it for it in cls.items}

    def test_the_fixed_order_and_a_status_word_each(self):
        """O7, and §4 rule 7."""
        self.assertEqual([it.key for it in self.items],
                         ["food", "flowers", "native", "cover", "street",
                          "cost"])
        for it in self.items:
            self.assertIn(it.status_word, ("Looks good", "Worth a look",
                                           "To plan for"))
            self.assertTrue(it.lines)

    def test_under_three_hundred_words_and_plain(self):
        self.assertLessEqual(yi.word_count(self.items), 300)
        text = yi.as_text(self.items)
        for word in ("species", "/100", "_", "score"):
            self.assertNotIn(word, text)
        for pid in {p["plant_id"] for p in
                    __import__("src.project_store", fromlist=["x"])
                    .ProjectStore(self.example).placed_plants}:
            sci = (_plants.get_plant(pid) or {}).get("scientific_name")
            self.assertNotIn(sci, text)

    def test_numbers_come_from_their_sources(self):
        """§4 rule 5: one number, one source."""
        from src import sourcing, what_it_feeds as w
        from src.maintenance_calendar import build_maintenance_calendar
        from src.project_store import ProjectStore
        placed = ProjectStore(self.example).placed_plants
        ids = {p["plant_id"] for p in placed}
        counts = w.food_counts(ids)
        food = self.by_key["food"].lines[0]
        self.assertIn(f"food for {counts['bee']} kinds of bee", food)
        self.assertIn(f"{counts['lepidoptera']} of butterfly and moth", food)
        self.assertIn(f"{counts['bird']} of bird", food)
        lo, hi = sourcing.estimate_cost(placed)
        self.assertIn(sourcing.format_cost(lo, hi),
                      self.by_key["cost"].lines[0])
        band = build_maintenance_calendar(placed, []).bands[0]
        self.assertIn(f"{band.hours_low:,.0f}–{band.hours_high:,.0f} hours",
                      self.by_key["cost"].lines[1])
        gaps = w.month_by_month(ids)["gaps"]
        self.assertEqual(self.by_key["flowers"].status == yi.LOOK, bool(gaps))

    def test_the_example_reads_as_the_plan_says(self):
        """§6.1, with the catalogue as it is now."""
        self.assertIn("such as the Cedar Waxwing", self.by_key["food"].lines[0])
        self.assertIn(yi.CAVEAT, self.by_key["food"].lines)
        self.assertEqual(self.by_key["flowers"].action,
                         "Find an October flower")
        self.assertIn("about a third", self.by_key["cover"].lines[0])
        self.assertEqual(self.by_key["cover"].target, "fill_gaps")
        self.assertEqual(self.by_key["street"].action, "Draw a mown strip")
        self.assertIn("taken to be the south side",
                      self.by_key["street"].lines[1])
        self.assertIn("at Edmonton native nurseries",
                      self.by_key["cost"].lines[0])
        self.assertIn(yi.heading(self.example).split(" · ")[-1],
                      "19 plants, 14 kinds")

    def test_no_bylaw_sentence(self):
        """O5: Edmonton's pack carries no street rule."""
        self.assertNotIn("bylaw", yi.as_text(self.items).lower())

    def test_fast(self):
        self.assertLess(self.seconds, 1.5)

    def test_an_off_list_plant_is_named_with_a_swap(self):
        from src import native_here
        names = native_here.native_names("edmonton")
        away = next(r for r in _plants.get_all_plants()
                    if r["scientific_name"] not in names)
        p = _project(_feature("property_boundary", _square(0, 0, 5, 5)))
        _plant(p, away["id"], away["common_name"], 2, 2)
        item = next(it for it in yi.overview(p) if it.key == "native")
        self.assertEqual(item.status, yi.LOOK)
        self.assertIn(f"{away['common_name']} is not", item.lines[0])
        self.assertEqual(item.target, f"swap:{away['id']}")

    def test_empty_and_unpinned(self):
        empty = yi.overview(_project())
        self.assertEqual([it.key for it in empty], ["empty"])
        self.assertEqual(empty[0].lines, [yi.EMPTY])
        p = _project(pin=False)
        row = _plants.get_all_plants()[0]
        _plant(p, row["id"], row["common_name"], 1, 1)
        by = {it.key: it for it in yi.overview(p)}
        self.assertEqual(by["native"].target, "site:pin")
        self.assertEqual(by["cover"].target, "draw:boundary")


if __name__ == "__main__":
    unittest.main()

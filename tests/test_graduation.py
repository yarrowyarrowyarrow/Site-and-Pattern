"""
tests/test_graduation.py — taking the sandbox landscape into Design (F104, V2.55).

Learn mode was a side room: you could walk a wild community, plant into it and
pull things out, and none of it could go anywhere. Graduation is the door out —
the landscape you built, moved to your own address, saved as an ordinary design.

The transform is the part worth testing hard, because getting it subtly wrong
would move the plants *nearly* right and nobody would notice until a design was
built on it. Qt-free, so all of it runs headless.
"""

import math
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_TMP = tempfile.mkdtemp(prefix="permadesign_graduation_")
try:
    import src.db.plants as _plants_mod
    _plants_mod._DATA_DIR = _TMP
    _plants_mod._DB_PATH = os.path.join(_TMP, "t.db")
except Exception:  # pragma: no cover
    pass

from src import graduation  # noqa: E402
from src.project_store import ProjectStore  # noqa: E402
from src.reference_edit import local_offset  # noqa: E402

_CALGARY = (51.05, -114.07)
_EDMONTON = (53.5461, -113.4938)


def _sandbox(center=_CALGARY, n=6, name="Reference — Aspen Parkland grove"):
    project = {"type": "FeatureCollection", "features": [],
               "properties": {"name": name,
                              "reference_ecoregion": "aspen_parkland"}}
    store = ProjectStore(project)
    from src.reference_edit import offset_latlng
    # A deliberately lopsided scatter: a symmetric one would hide a bug that
    # mirrors or rotates the landscape.
    for i in range(n):
        dx, dy = (i * 1.7) - 2.0, (i * i * 0.4) - 3.0
        lat, lng = offset_latlng(center[0], center[1], dx, dy)
        store.add_plant(i + 1, f"Plant {i}", lat, lng)
    return project


class TestCentroid(unittest.TestCase):
    def test_empty_project_has_no_centroid(self):
        self.assertIsNone(graduation.plant_centroid(
            {"type": "FeatureCollection", "features": [], "properties": {}}))

    def test_centroid_is_the_mean_not_the_bounding_box(self):
        """One outlying shrub should not drag the whole middle into its
        corner, which is what a bbox centre would do."""
        project = {"type": "FeatureCollection", "features": [],
                   "properties": {}}
        store = ProjectStore(project)
        for lng in (-114.07, -114.07, -114.07, -114.00):
            store.add_plant(1, "x", 51.05, lng)
        lat, lng = graduation.plant_centroid(project)
        self.assertAlmostEqual(lat, 51.05, places=9)
        self.assertAlmostEqual(lng, (-114.07 * 3 + -114.00) / 4, places=9)


class TestRecentre(unittest.TestCase):
    def test_the_centroid_lands_on_the_target(self):
        project = _sandbox()
        moved = graduation.recentre(project, _EDMONTON)
        self.assertEqual(moved, 6)
        lat, lng = graduation.plant_centroid(project)
        self.assertAlmostEqual(lat, _EDMONTON[0], places=6)
        self.assertAlmostEqual(lng, _EDMONTON[1], places=6)

    def test_relative_geometry_is_preserved(self):
        """The claim the whole feature rests on: it is the same landscape,
        somewhere else. Every plant keeps its metre offsets from the middle."""
        project = _sandbox()
        origin = graduation.plant_centroid(project)
        before = sorted(
            local_offset(r["lat"], r["lng"], origin[0], origin[1])
            for r in graduation.plant_records(project))

        graduation.recentre(project, _EDMONTON)
        new_origin = graduation.plant_centroid(project)
        after = sorted(
            local_offset(r["lat"], r["lng"], new_origin[0], new_origin[1])
            for r in graduation.plant_records(project))

        for (ax, ay), (bx, by) in zip(before, after):
            self.assertLess(math.hypot(ax - bx, ay - by), 0.01,
                            "the landscape was distorted by the move")

    def test_pairwise_distances_survive(self):
        """Stated separately from the offsets because a uniform scaling would
        pass an offset check done against a rescaled centroid."""
        project = _sandbox()
        def dists(p):
            recs = graduation.plant_records(p)
            o = graduation.plant_centroid(p)
            pts = [local_offset(r["lat"], r["lng"], o[0], o[1]) for r in recs]
            return sorted(math.hypot(a[0] - b[0], a[1] - b[1])
                          for i, a in enumerate(pts) for b in pts[i + 1:])

        before = dists(project)
        graduation.recentre(project, _EDMONTON)
        for a, b in zip(before, dists(project)):
            self.assertAlmostEqual(a, b, places=2)

    def test_no_target_moves_nothing(self):
        project = _sandbox()
        self.assertEqual(graduation.recentre(project, None), 0)


class TestGraduate(unittest.TestCase):
    def test_the_sandbox_is_left_alone(self):
        """Graduate a landscape, then keep playing — the sandbox must be
        exactly as you left it."""
        project = _sandbox()
        before = [(r["lat"], r["lng"]) for r in graduation.plant_records(project)]
        graduation.graduate(project, _EDMONTON)
        after = [(r["lat"], r["lng"]) for r in graduation.plant_records(project)]
        self.assertEqual(before, after)

    def test_it_carries_the_site_config_across(self):
        """Without this the graduation is a downgrade: _load_from_path replays
        this block to restore the pin and every Site Info reading, so a project
        arriving without it opens at the right address with a blank panel —
        and overwrites the site data the user already had."""
        project = _sandbox()
        sc = {"latitude": _EDMONTON[0], "longitude": _EDMONTON[1],
              "hardiness": {"zone": 4}, "soil": {"ph": 7.4}}
        out = graduation.graduate(project, _EDMONTON, site_config=sc)
        self.assertEqual(out["properties"]["site_config"]["hardiness"],
                         {"zone": 4})

    def test_the_site_config_is_copied_not_aliased(self):
        project = _sandbox()
        sc = {"latitude": 1.0, "longitude": 2.0, "soil": {"ph": 7.4}}
        out = graduation.graduate(project, None, site_config=sc)
        out["properties"]["site_config"]["soil"]["ph"] = 9.9
        self.assertEqual(sc["soil"]["ph"], 7.4,
                         "the graduated project shares the design's site dict")

    def test_it_records_where_it_came_from(self):
        out = graduation.graduate(_sandbox(), _EDMONTON)
        self.assertEqual(out["properties"]["graduated_from"], "aspen_parkland")

    def test_the_name_keeps_the_place_and_drops_the_demo_word(self):
        out = graduation.graduate(_sandbox(), _EDMONTON)
        name = out["properties"]["name"]
        self.assertIn("Aspen Parkland grove", name)
        self.assertNotIn("Reference", name)

    def test_no_pin_still_graduates(self):
        """Refusing would put a wall exactly where the feature is trying to
        open a door. It comes across at its own coordinates instead."""
        project = _sandbox()
        origin = graduation.plant_centroid(project)
        out = graduation.graduate(project, None)
        self.assertEqual(len(graduation.plant_records(out)), 6)
        moved = graduation.plant_centroid(out)
        self.assertAlmostEqual(moved[0], origin[0], places=9)
        self.assertAlmostEqual(moved[1], origin[1], places=9)


class TestSaveAsDesign(unittest.TestCase):
    def test_it_writes_a_readable_design(self):
        import json
        out = graduation.graduate(_sandbox(), _EDMONTON)
        directory = tempfile.mkdtemp(prefix="permadesign_grad_saves_")
        path = graduation.save_as_design(out, directory)
        self.assertTrue(os.path.exists(path))
        with open(path, "r", encoding="utf-8") as fh:
            back = json.load(fh)
        self.assertEqual(back["type"], "FeatureCollection")
        self.assertEqual(len(ProjectStore(back).placed_plants), 6)

    def test_two_graduations_do_not_overwrite_each_other(self):
        directory = tempfile.mkdtemp(prefix="permadesign_grad_saves2_")
        a = graduation.save_as_design(
            graduation.graduate(_sandbox(), _EDMONTON), directory)
        b = graduation.save_as_design(
            graduation.graduate(_sandbox(), _EDMONTON), directory)
        self.assertNotEqual(a, b)


class TestTheFlowUsesTheAppsOwnLoader(unittest.TestCase):
    """Source shape. Assigning ``main._project`` directly would skip the map
    re-render, the undo clear and the site-data replay — the graduated design
    would open as a special case rather than as a design."""

    def test_it_goes_through_load_from_path(self):
        path = os.path.join(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__))), "src", "graduation_flow.py")
        with open(path, "r", encoding="utf-8") as fh:
            src = fh.read()
        self.assertIn("_load_from_path", src)
        self.assertNotIn("main._project =", src,
                         "graduation assigns the project directly — that skips "
                         "render_project_to_map and the site-data replay")


if __name__ == "__main__":
    unittest.main()

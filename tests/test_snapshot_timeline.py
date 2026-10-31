"""
tests/test_snapshot_timeline.py — the Year 1/5/15/30 growth snapshots (F2).

Pins the Qt-free core: which years get rendered (clamped to the design's own
maturity horizon) and that the scenes really show the plants growing. Pure
Python — injected ``get_plant``, no Qt, no DB, no network, in the same spirit
as tests/test_scene_contract.py.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.snapshot_timeline import (   # noqa: E402
    SNAPSHOT_YEARS, snapshot_years, build_snapshots, placed_records,
)
from src.project_store import plant_feature   # noqa: E402

_LAT, _LNG = 53.5, -113.5

_FAKE_PLANTS = {
    # A long-lived tree (matures at 40) so the horizon reaches year 30.
    1: {"plant_type": "tree", "years_to_maturity": 40, "growth_curve": "steady",
        "mature_height_meters": 10.0, "mature_canopy_m": 6.0,
        "deciduous_evergreen": "deciduous"},
    # A fast shrub (matures at 5) — on its own the design's horizon clamps up
    # to the floor, never out to 30.
    2: {"plant_type": "shrub", "years_to_maturity": 5, "growth_curve": "steady",
        "mature_height_meters": 2.0, "mature_canopy_m": 1.5},
}


def _get_plant(pid):
    return _FAKE_PLANTS.get(pid)


def _project(plant_ids):
    feats = [plant_feature({"plant_id": pid, "common_name": f"P{pid}",
                            "lat": _LAT, "lng": _LNG})
             for pid in plant_ids]
    return {"type": "FeatureCollection", "properties": {"site_config": {}},
            "features": feats}


class TestSnapshotYears(unittest.TestCase):

    def test_long_lived_design_reaches_year_30(self):
        years = snapshot_years([{"plant_id": 1}], get_plant=_get_plant)
        self.assertEqual(years, [1, 5, 15, 30])

    def test_short_lived_design_clamps_30_to_horizon(self):
        # Only a fast shrub → horizon clamps to the 20-year floor, so the
        # year-30 panel collapses onto the horizon rather than faking change.
        years = snapshot_years([{"plant_id": 2}], get_plant=_get_plant)
        self.assertNotIn(30, years)
        self.assertEqual(max(years), 20)
        self.assertEqual(years, sorted(set(years)))   # sorted + de-duped

    def test_empty_design_still_returns_four_sorted_years(self):
        years = snapshot_years([], get_plant=_get_plant)
        self.assertEqual(years, [1, 5, 15, 20])

    def test_first_year_is_always_year_one(self):
        self.assertEqual(min(SNAPSHOT_YEARS), 1)
        self.assertEqual(snapshot_years([{"plant_id": 1}],
                                        get_plant=_get_plant)[0], 1)


class TestBuildSnapshots(unittest.TestCase):

    def test_placed_records_finds_plants(self):
        recs = placed_records(_project([1, 2]))
        self.assertEqual({r["plant_id"] for r in recs}, {1, 2})

    def test_one_scene_per_year_with_matching_year(self):
        proj = _project([1])
        snaps = build_snapshots(proj, get_plant=_get_plant)
        self.assertEqual([s["year"] for s in snaps], [1, 5, 15, 30])
        for s in snaps:
            self.assertEqual(s["scene"]["year"], s["year"])
            self.assertIn("plants", s["scene"])

    def test_canopy_grows_then_plateaus_over_the_years(self):
        proj = _project([1])
        snaps = build_snapshots(proj, get_plant=_get_plant)

        def _canopy(scene):
            return scene["plants"][0]["canopy_m"]

        canopies = [_canopy(s["scene"]) for s in snaps]
        # Non-decreasing across years (steady growth, then mature plateau).
        for earlier, later in zip(canopies, canopies[1:]):
            self.assertLessEqual(earlier, later)
        # And it actually grew — year 1 is smaller than the mature size.
        self.assertLess(canopies[0], canopies[-1])

    def test_empty_design_yields_empty_plant_lists(self):
        snaps = build_snapshots(_project([]), get_plant=_get_plant)
        self.assertEqual(len(snaps), 4)
        for s in snaps:
            self.assertEqual(s["scene"]["plants"], [])



class TestWhatTheWindowSays(unittest.TestCase):
    """V3.05 (surface audit): the window promised "years 1, 5, 15 and 30"
    above a last panel reading Year 20, and drew an 11 x 8 m yard inside the
    3D stage's 50 m box, a tenth of each panel."""

    def test_the_sentence_names_the_years_shown(self):
        from src.snapshot_timeline import years_line
        line = years_line([1, 5, 15, 20])
        self.assertIn("years 1, 5, 15 and 20", line)
        self.assertNotIn("30", line)
        self.assertIn("year 20", line)

    def test_an_uncapped_design_says_nothing_about_stopping(self):
        from src.snapshot_timeline import SNAPSHOT_YEARS, years_line
        self.assertNotIn("stops", years_line(list(SNAPSHOT_YEARS)))

    def test_the_frame_is_the_yard_not_the_stage(self):
        from src.snapshot_timeline import content_bounds
        scene = {"boundary": [[0, 0], [11, 0], [11, 8], [0, 8]],
                 "plants": [{"x": 2.0, "y": 2.0, "canopy_m": 4.0}],
                 "bounds": {"min_x": -25, "min_y": -25,
                            "max_x": 25, "max_y": 25}}
        b = content_bounds([scene])
        self.assertLess(b["max_x"] - b["min_x"], 15)
        self.assertLess(b["max_y"] - b["min_y"], 12)
        self.assertLessEqual(b["min_x"], 0.0 - 1.0)   # the crown is inside

    def test_nothing_drawn_is_no_frame(self):
        from src.snapshot_timeline import content_bounds
        self.assertIsNone(content_bounds([{"plants": [], "boundary": None}]))


if __name__ == "__main__":
    unittest.main()

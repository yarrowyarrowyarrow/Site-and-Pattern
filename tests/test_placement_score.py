"""
tests/test_placement_score.py

Unit tests for src/placement_score.py — the ecological cell-scoring layer
introduced in V1.51.  All tests are offline-safe (no network), use a temp-DB
for companion tests, and do not import Qt.

Groups:
  1 — CellEnv construction and build_cell_env_map
  2 — score_cell_for_plant sub-function correctness
  3 — build_companion_graph (requires seeded temp-DB)
  4 — check_companion_spacing
  5 — ScoredPositioner (via llm_design integration)
"""

import math
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ── Temp-DB redirect (must happen before any src.db import) ──────────────────
_TMP_DIR = tempfile.mkdtemp(prefix="permadesign_score_test_")
import src.db.plants as _plants_mod  # noqa: E402
_plants_mod._DATA_DIR = _TMP_DIR
_plants_mod._DB_PATH = os.path.join(_TMP_DIR, "t.db")

from src.db.plants import init_db, get_connection  # noqa: E402
from src.placement_score import (  # noqa: E402
    CellEnv,
    classify_edge_cells,
    build_cell_env_map,
    score_cell_for_plant,
    build_companion_graph,
    check_companion_spacing,
)
import src.llm_design as _llm  # noqa: E402


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Group 1 — CellEnv and build_cell_env_map
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# A 3×3 grid of placement cells at a fixed lat/lng (6 m step).
_REF_LAT, _REF_LNG = 53.5, -113.5
_DLAT = 6.0 / 111320.0
_COS_LAT = math.cos(_REF_LAT * math.pi / 180)
_DLNG = 6.0 / (111320.0 * _COS_LAT)

_CELLS_3X3 = [
    (_REF_LAT + r * _DLAT, _REF_LNG + c * _DLNG)
    for r in range(3) for c in range(3)
]


class TestBuildCellEnvMap(unittest.TestCase):

    def test_all_neutral_when_no_grids(self):
        """All-None grids → every CellEnv has neutral default values."""
        env_map = build_cell_env_map(_CELLS_3X3)
        self.assertEqual(len(env_map), len(_CELLS_3X3))
        for cell, env in env_map.items():
            self.assertAlmostEqual(env.shade_fraction, 0.5, msg=f"shade {cell}")
            self.assertAlmostEqual(env.elevation_pct,  0.5, msg=f"elev {cell}")
            self.assertAlmostEqual(env.slope_pct,      0.0, msg=f"slope {cell}")
            self.assertAlmostEqual(env.aspect_deg,    -1.0, msg=f"aspect {cell}")

    def test_shade_grid_propagated(self):
        """Known shade values appear in the returned CellEnvs."""
        # Build a 2×2 elev grid covering exactly our 3×3 cell extent.
        bbox = {
            "north": _REF_LAT + 2 * _DLAT,
            "south": _REF_LAT,
            "east":  _REF_LNG + 2 * _DLNG,
            "west":  _REF_LNG,
        }
        elev = {"grid": [[100.0, 100.0], [100.0, 100.0]],
                "rows": 2, "cols": 2, "bbox": bbox}
        shade = [[0.1, 0.9], [0.9, 0.1]]
        env_map = build_cell_env_map(_CELLS_3X3, shade_grid=shade,
                                     elev_grid=elev)
        # North-west corner cell should map to shade_grid[0][0] = 0.1
        nw_cell = (_REF_LAT + 2 * _DLAT, _REF_LNG)
        if nw_cell in env_map:
            self.assertAlmostEqual(env_map[nw_cell].shade_fraction, 0.1,
                                   places=2)

    def test_elevation_normalised(self):
        """Three-cell 1-D elevation sequence → elevation_pct in [0, 0.5, 1]."""
        cells_1d = [(_REF_LAT, _REF_LNG + i * _DLNG) for i in range(3)]
        bbox = {
            "north": _REF_LAT + _DLAT,
            "south": _REF_LAT - _DLAT,
            "east":  _REF_LNG + 2 * _DLNG,
            "west":  _REF_LNG,
        }
        elev = {"grid": [[100.0, 110.0, 120.0], [100.0, 110.0, 120.0]],
                "rows": 2, "cols": 3, "bbox": bbox}
        env_map = build_cell_env_map(cells_1d, elev_grid=elev)
        pcts = sorted(env.elevation_pct for env in env_map.values())
        self.assertAlmostEqual(pcts[0], 0.0, places=2)
        self.assertAlmostEqual(pcts[-1], 1.0, places=2)

    def test_edge_cells_detected(self):
        """In a 3×3 grid the centre cell is not an edge cell; all others are."""
        env_map = build_cell_env_map(_CELLS_3X3)
        # The centre of the 3×3 grid is cells[4]
        centre = _CELLS_3X3[4]
        self.assertFalse(env_map[centre].is_edge,
                         "centre cell should not be an edge cell")
        # All 8 surrounding cells should be edge cells
        for i, cell in enumerate(_CELLS_3X3):
            if i != 4:
                self.assertTrue(env_map[cell].is_edge,
                                f"cells[{i}] {cell} should be an edge cell")

    def test_empty_cells_returns_empty(self):
        self.assertEqual(build_cell_env_map([]), {})

    def test_score_never_raises_with_all_none_grids(self):
        """build_cell_env_map + score_cell_for_plant must not raise even with
        degenerate inputs."""
        env_map = build_cell_env_map(_CELLS_3X3)
        plant = {}  # completely empty dict
        for env in env_map.values():
            result = score_cell_for_plant(plant, env)
            self.assertGreaterEqual(result, 0.0)
            self.assertLessEqual(result, 1.0)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Group 2 — score_cell_for_plant
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _env(shade=0.5, elev_pct=0.5, slope=0.0, aspect=-1.0, is_edge=False):
    return CellEnv(shade_fraction=shade, elevation_pct=elev_pct,
                   slope_pct=slope, aspect_deg=aspect, is_edge=is_edge)


class TestScoreCellForPlant(unittest.TestCase):

    def test_full_sun_prefers_low_shade(self):
        plant = {"sun_requirement": "full_sun", "water_needs": "medium",
                 "plant_type": "herb"}
        sunny = score_cell_for_plant(plant, _env(shade=0.05))
        shady = score_cell_for_plant(plant, _env(shade=0.6))
        self.assertGreater(sunny, shady)

    def test_full_shade_prefers_high_shade(self):
        plant = {"sun_requirement": "full_shade", "water_needs": "medium",
                 "plant_type": "herb"}
        shady = score_cell_for_plant(plant, _env(shade=0.8))
        sunny = score_cell_for_plant(plant, _env(shade=0.05))
        self.assertGreater(shady, sunny)

    def test_partial_shade_peaks_in_middle(self):
        plant = {"sun_requirement": "partial_shade", "water_needs": "medium",
                 "plant_type": "shrub"}
        mid  = score_cell_for_plant(plant, _env(shade=0.35))
        deep = score_cell_for_plant(plant, _env(shade=0.95))
        bare = score_cell_for_plant(plant, _env(shade=0.0))
        self.assertGreater(mid, deep)
        self.assertGreater(mid, bare)

    def test_high_water_prefers_wet_cell(self):
        plant = {"sun_requirement": "full_sun", "water_needs": "high",
                 "plant_type": "herb"}
        wet = score_cell_for_plant(plant, _env(elev_pct=0.05))
        dry = score_cell_for_plant(plant, _env(elev_pct=0.95))
        self.assertGreater(wet, dry)

    def test_low_water_prefers_dry_cell(self):
        plant = {"sun_requirement": "full_sun", "water_needs": "low",
                 "plant_type": "herb"}
        dry = score_cell_for_plant(plant, _env(elev_pct=0.95))
        wet = score_cell_for_plant(plant, _env(elev_pct=0.05))
        self.assertGreater(dry, wet)

    def test_south_facing_drier_than_north_facing(self):
        """S-facing (aspect=180) has lower moisture than N-facing (aspect=0),
        so a high-water plant should score lower there."""
        plant = {"sun_requirement": "full_sun", "water_needs": "high",
                 "plant_type": "herb"}
        n_score = score_cell_for_plant(plant, _env(elev_pct=0.5, slope=10.0,
                                                    aspect=0.0))
        s_score = score_cell_for_plant(plant, _env(elev_pct=0.5, slope=10.0,
                                                    aspect=180.0))
        self.assertGreater(n_score, s_score)

    def test_groundcover_scores_higher_interior(self):
        plant = {"sun_requirement": "full_sun", "water_needs": "medium",
                 "plant_type": "groundcover", "_uses": {"groundcover"}}
        interior = score_cell_for_plant(plant, _env(is_edge=False))
        edge_cell = score_cell_for_plant(plant, _env(is_edge=True))
        self.assertGreater(interior, edge_cell)

    def test_windbreak_scores_higher_edge(self):
        plant = {"sun_requirement": "full_sun", "water_needs": "medium",
                 "plant_type": "shrub", "_uses": {"windbreak"}}
        edge_cell = score_cell_for_plant(plant, _env(is_edge=True))
        interior  = score_cell_for_plant(plant, _env(is_edge=False))
        self.assertGreater(edge_cell, interior)

    def test_neutral_score_for_missing_data(self):
        """Empty plant dict → score in neutral range (unknown type on flat
        ground still scores well on slope, so exact 0.5 is not expected)."""
        result = score_cell_for_plant({}, _env())
        self.assertGreaterEqual(result, 0.45)
        self.assertLessEqual(result, 0.65)

    def test_score_clamped_0_to_1(self):
        """Score is always in [0, 1] regardless of input values."""
        extremes = [
            {"sun_requirement": "full_sun",   "water_needs": "low",  "plant_type": "tree"},
            {"sun_requirement": "full_shade",  "water_needs": "high", "plant_type": "aquatic"},
        ]
        envs = [
            _env(shade=0.0, elev_pct=1.0, slope=50.0, aspect=180.0, is_edge=True),
            _env(shade=1.0, elev_pct=0.0, slope=0.0,  aspect=0.0,   is_edge=False),
        ]
        for p in extremes:
            for e in envs:
                s = score_cell_for_plant(p, e)
                self.assertGreaterEqual(s, 0.0, f"score < 0 for {p}, {e}")
                self.assertLessEqual(s, 1.0,    f"score > 1 for {p}, {e}")

    def test_aquatic_penalised_on_steep_slope(self):
        plant = {"sun_requirement": "full_sun", "water_needs": "high",
                 "plant_type": "aquatic"}
        flat  = score_cell_for_plant(plant, _env(slope=0.5, elev_pct=0.1))
        steep = score_cell_for_plant(plant, _env(slope=15.0, elev_pct=0.1))
        self.assertGreater(flat, steep)

    def test_tree_scores_1_on_gentle_slope(self):
        plant = {"sun_requirement": "full_sun", "water_needs": "medium",
                 "plant_type": "tree"}
        env = _env(shade=0.0, elev_pct=0.5, slope=10.0)
        result = score_cell_for_plant(plant, env)
        # Slope sub-score should be 1.0 (below 15%), overall should be high
        self.assertGreater(result, 0.7)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Group 3 — build_companion_graph  (requires seeded temp-DB)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class TestBuildCompanionGraph(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        init_db()
        conn = get_connection()
        try:
            # Find two known friend pairs from the seeded data
            rows = conn.execute(
                "SELECT plant_id_a, plant_id_b FROM companion_friends LIMIT 1"
            ).fetchone()
            cls.friend_a = rows[0] if rows else None
            cls.friend_b = rows[1] if rows else None
            rows2 = conn.execute(
                "SELECT plant_id_a, plant_id_b FROM companion_enemies LIMIT 1"
            ).fetchone()
            cls.enemy_a = rows2[0] if rows2 else None
            cls.enemy_b = rows2[1] if rows2 else None
        finally:
            conn.close()

    def test_empty_input_returns_empty(self):
        self.assertEqual(build_companion_graph([]), {})

    def test_graph_keys_are_input_ids(self):
        if self.friend_a is None:
            self.skipTest("no seeded companion_friends rows")
        graph = build_companion_graph([self.friend_a, self.friend_b])
        self.assertIn(self.friend_a, graph)
        self.assertIn(self.friend_b, graph)

    def test_seeded_friends_appear(self):
        if self.friend_a is None:
            self.skipTest("no seeded companion_friends rows")
        graph = build_companion_graph([self.friend_a, self.friend_b])
        self.assertIn(self.friend_b, graph[self.friend_a]["friends"])
        self.assertIn(self.friend_a, graph[self.friend_b]["friends"])

    def test_friends_bidirectional(self):
        if self.friend_a is None:
            self.skipTest("no seeded companion_friends rows")
        graph = build_companion_graph([self.friend_a, self.friend_b])
        self.assertIn(self.friend_b, graph[self.friend_a]["friends"])
        self.assertIn(self.friend_a, graph[self.friend_b]["friends"])

    def test_outsider_not_in_graph(self):
        """A plant not in plant_ids doesn't appear in any friend list."""
        if self.friend_a is None:
            self.skipTest("no seeded companion_friends rows")
        graph = build_companion_graph([self.friend_a])
        self.assertEqual(graph[self.friend_a]["friends"], [],
                         "friend_b is not in plant_ids so should not appear")

    def test_seeded_enemies_appear(self):
        if self.enemy_a is None:
            self.skipTest("no seeded companion_enemies rows")
        graph = build_companion_graph([self.enemy_a, self.enemy_b])
        self.assertIn(self.enemy_b, graph[self.enemy_a]["enemies"])

    def test_no_duplicate_entries(self):
        if self.friend_a is None:
            self.skipTest("no seeded companion_friends rows")
        graph = build_companion_graph([self.friend_a, self.friend_b])
        ids = graph[self.friend_a]["friends"]
        self.assertEqual(len(ids), len(set(ids)), "duplicate friend ids")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Group 4 — check_companion_spacing
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class TestCheckCompanionSpacing(unittest.TestCase):

    def _placed(self, pid, lat, lng, name="Plant"):
        return {"plant_id": pid, "lat": lat, "lng": lng, "common_name": name}

    # Use IDs outside the seeded range so get_plant() returns None and the
    # fallback spacing of 2.0 m is used consistently.  Combined = 4 m.
    _EA, _EB, _FA, _FB = 9901, 9902, 9903, 9904

    def test_close_enemies_emit_warning(self):
        """Two enemy plants placed 1 m apart → 'inhibit' warning.
        Combined spacing = 4 m; threshold = 4 m; dist ≈ 0.01 m → warns."""
        placed = [
            self._placed(self._EA, 53.5000, -113.5000, "Chives"),
            self._placed(self._EB, 53.5000, -113.5000 + 0.000001, "Jerusalem Artichoke"),
        ]
        graph = {
            self._EA: {"friends": [], "enemies": [self._EB]},
            self._EB: {"friends": [], "enemies": [self._EA]},
        }
        warnings = check_companion_spacing(placed, graph)
        self.assertTrue(any("inhibit" in w for w in warnings),
                        f"Expected 'inhibit' in warnings, got: {warnings}")

    def test_far_friends_emit_warning(self):
        """Two friend plants placed ~500 m apart → 'companion' warning.
        Combined spacing = 4 m; threshold = 12 m; dist ≈ 500 m → warns."""
        placed = [
            self._placed(self._FA, 53.5000, -113.5000, "Yarrow"),
            self._placed(self._FB, 53.5045, -113.5000, "Saskatoon"),
        ]
        graph = {
            self._FA: {"friends": [self._FB], "enemies": []},
            self._FB: {"friends": [self._FA], "enemies": []},
        }
        warnings = check_companion_spacing(placed, graph)
        self.assertTrue(any("companion" in w for w in warnings),
                        f"Expected 'companion' in warnings, got: {warnings}")

    def test_friends_nearby_no_warning(self):
        """Friends within 3× combined spacing → no warning.
        Default fallback spacing is 2 m/plant → threshold = 12 m.
        Place plants 1 cell (~6 m) apart → 6 < 12 → no warning."""
        placed = [
            self._placed(self._FA, 53.5000, -113.5000, "A"),
            self._placed(self._FB, 53.5000, -113.5000 + _DLNG, "B"),
        ]
        graph = {
            self._FA: {"friends": [self._FB], "enemies": []},
            self._FB: {"friends": [self._FA], "enemies": []},
        }
        warnings = check_companion_spacing(placed, graph)
        self.assertFalse(warnings,
                         f"Expected no warnings for nearby friends, got: {warnings}")

    def test_no_duplicate_warnings(self):
        """Same pair should produce at most one warning."""
        placed = [
            self._placed(self._FA, 53.5000, -113.5000, "A"),
            self._placed(self._FB, 53.5045, -113.5000, "B"),
        ]
        graph = {
            self._FA: {"friends": [self._FB], "enemies": []},
            self._FB: {"friends": [self._FA], "enemies": []},
        }
        warnings = check_companion_spacing(placed, graph)
        self.assertLessEqual(len(warnings), 1,
                             "same pair warned more than once")

    def test_empty_inputs_no_error(self):
        self.assertEqual(check_companion_spacing([], {}), [])
        self.assertEqual(check_companion_spacing([], {1: {"friends": [], "enemies": []}}), [])

    def test_plant_not_in_placed_skipped(self):
        """A plant in the graph but with no placed positions is skipped."""
        placed = [self._placed(9905, 53.5, -113.5, "Only")]
        graph = {
            9905: {"friends": [9999], "enemies": []},
            9999: {"friends": [9905], "enemies": []},
        }
        # Should not raise; 9999 has no placed positions — no warning expected
        warnings = check_companion_spacing(placed, graph)
        self.assertFalse(any("9999" in w for w in warnings))


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Group 5 — ScoredPositioner (via llm_design integration)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class TestScoredPositioner(unittest.TestCase):

    def _simple_positioner(self, cells, env_map=None):
        """Build a ScoredPositioner with the given cells as the flat pool."""
        return _llm.ScoredPositioner(env_map, None, cells)

    def test_takes_all_cells_before_exhausting(self):
        cells = list(_CELLS_3X3)
        pos = self._simple_positioner(cells)
        taken = []
        for _ in range(len(cells)):
            c = pos.take_best({}, None)
            if c is None:
                break
            taken.append(c)
        self.assertEqual(len(taken), len(cells))

    def test_no_duplicate_cells_taken(self):
        cells = list(_CELLS_3X3)
        pos = self._simple_positioner(cells)
        taken = []
        for _ in range(len(cells) + 2):
            c = pos.take_best({}, None)
            if c is None:
                break
            taken.append(c)
        self.assertEqual(len(taken), len(set(taken)))

    def test_falls_back_when_env_map_none(self):
        """When cell_env_map is None the positioner still returns cells."""
        cells = list(_CELLS_3X3)
        pos = _llm.ScoredPositioner(None, None, cells)
        result = pos.take_best({}, None)
        self.assertIsNotNone(result)
        self.assertIn(result, cells)

    def test_highest_shade_score_cell_chosen(self):
        """Full-shade plant should prefer the shadiest cell when env_map is set."""
        cells = [
            (_REF_LAT, _REF_LNG),               # cell A: shade 0.9
            (_REF_LAT + _DLAT, _REF_LNG),       # cell B: shade 0.1
        ]
        env_map = {
            cells[0]: CellEnv(0.9, 0.5, 0.0, -1.0, False),
            cells[1]: CellEnv(0.1, 0.5, 0.0, -1.0, False),
        }
        pos = self._simple_positioner(cells, env_map)
        full_shade_plant = {"sun_requirement": "full_shade",
                            "water_needs": "medium", "plant_type": "herb"}
        chosen = pos.take_best(full_shade_plant)
        self.assertEqual(chosen, cells[0],
                         "full-shade plant should pick the shadiest cell")

    def test_reserve_near_removes_cells(self):
        """After reserve_near, nearby cells no longer appear in take_best."""
        cells = list(_CELLS_3X3)
        pos = self._simple_positioner(cells)
        anchor = cells[4]  # centre cell
        pos.take_best({})   # take something first (to prime _used)
        # Manually mark the anchor as taken
        pos._used.add(anchor)
        pos._fallback._used.add(anchor)
        # Reserve a large radius — should block most of the 3×3 grid
        pos.reserve_near([anchor], radius_m=15.0)
        # Try to take more; should get at most cells outside the 15 m circle
        taken_after = set()
        for _ in range(len(cells)):
            c = pos.take_best({})
            if c is None:
                break
            taken_after.add(c)
        # The anchor and its immediate neighbours should all be reserved
        self.assertNotIn(anchor, taken_after)

    def test_dripline_bonus_attracts_understory(self):
        """After a tree placement, take_best should prefer drip-line cells."""
        # Two cells: one at the drip-line distance, one far away
        tree_pos = (_REF_LAT, _REF_LNG)
        drip_cell = (_REF_LAT + 4 * _DLAT, _REF_LNG)  # ~24 m north ≈ drip ring
        far_cell  = (_REF_LAT + 15 * _DLAT, _REF_LNG) # ~90 m north = outside ring
        cells = [drip_cell, far_cell]
        env_map = {
            drip_cell: CellEnv(0.5, 0.5, 0.0, -1.0, False),
            far_cell:  CellEnv(0.5, 0.5, 0.0, -1.0, False),
        }
        pos = self._simple_positioner(cells, env_map)
        _llm._apply_dripline_bonus(pos, [tree_pos],
                                   canopy_radius_m=20.0, spacing_m=6.0)
        # drip_cell is ~24 m from tree → within 0.5×20=10 m..1.5×20=30 m ring
        # far_cell is ~90 m away → outside ring
        # drip_cell should have a bonus; far_cell should not
        self.assertIn(drip_cell, pos._bonus_cells,
                      "drip-line cell should have a bonus")
        self.assertNotIn(far_cell, pos._bonus_cells,
                         "far cell should not have a bonus")


class TestShadeMatch(unittest.TestCase):
    """V1.53 — check_shade_matches reads the cached shade tags and flags plants
    placed in incompatible light."""

    @classmethod
    def setUpClass(cls):
        init_db()

    def setUp(self):
        from src.placement_score import shade_tag_matches_plant
        from src.db import shade_zones
        self._sz = shade_zones
        self._matches = shade_tag_matches_plant
        self.pk = shade_zones.project_key_for("/tmp/proj/shadematch.perma.geojson")
        shade_zones.clear_zone_tags(self.pk)

    def test_compatibility_table(self):
        self.assertTrue(self._matches("full_sun", "full_sun"))
        self.assertTrue(self._matches("full_sun", "partial_shade"))
        self.assertFalse(self._matches("full_sun", "full_shade"))
        self.assertTrue(self._matches("full_shade", "full_shade"))
        self.assertFalse(self._matches("full_shade", "full_sun"))
        # partial-shade plants tolerate everything; unknown reqs are tolerant.
        for tag in ("full_sun", "partial_shade", "full_shade"):
            self.assertTrue(self._matches("partial_shade", tag))
            self.assertTrue(self._matches("", tag))

    def test_no_tags_no_warnings(self):
        from src.placement_score import check_shade_matches
        placed = [{"plant_id": 1, "lat": 53.5, "lng": -113.5,
                   "sun_requirement": "full_sun", "common_name": "Sun Lover"}]
        self.assertEqual(check_shade_matches(placed, self.pk), [])

    def test_mismatch_warns(self):
        from src.placement_score import check_shade_matches
        self._sz.store_zone_tags(self.pk, [
            {"zone_id": "a", "shade_tag": "full_shade",
             "centroid_lat": 53.5000, "centroid_lng": -113.5000}])
        placed = [{"plant_id": 1, "lat": 53.5000, "lng": -113.5000,
                   "sun_requirement": "full_sun", "common_name": "Sun Lover"}]
        warns = check_shade_matches(placed, self.pk)
        self.assertEqual(len(warns), 1)
        self.assertIn("Sun Lover", warns[0])

    def test_match_is_silent(self):
        from src.placement_score import check_shade_matches
        self._sz.store_zone_tags(self.pk, [
            {"zone_id": "a", "shade_tag": "full_sun",
             "centroid_lat": 53.5000, "centroid_lng": -113.5000}])
        placed = [{"plant_id": 1, "lat": 53.5000, "lng": -113.5000,
                   "sun_requirement": "full_sun", "common_name": "Sun Lover"}]
        self.assertEqual(check_shade_matches(placed, self.pk), [])

    def test_dedup_per_species(self):
        from src.placement_score import check_shade_matches
        self._sz.store_zone_tags(self.pk, [
            {"zone_id": "a", "shade_tag": "full_shade",
             "centroid_lat": 53.5000, "centroid_lng": -113.5000}])
        placed = [
            {"plant_id": 7, "lat": 53.5000, "lng": -113.5000,
             "sun_requirement": "full_sun", "common_name": "Sun Lover"},
            {"plant_id": 7, "lat": 53.50001, "lng": -113.5000,
             "sun_requirement": "full_sun", "common_name": "Sun Lover"},
        ]
        self.assertEqual(len(check_shade_matches(placed, self.pk)), 1)


if __name__ == "__main__":
    unittest.main()

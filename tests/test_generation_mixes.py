"""
tests/test_generation_mixes.py — the generator drives the app's placement
modes end-to-end (V2.23).

The manual app can repeat a community N times in a pattern, scatter a
weighted MIX of communities as pockets, and interleave a weighted MIX of
species through one stand (the Communities tab / Place Mix gestures).
These tests pin the generator's equivalents: spec ``communities[].count``
+ ``layout``, ``community_mixes`` and ``plant_mixes`` — resolved, budgeted
and placed deterministically with no LLM and no network (fake client, same
pattern as tests/test_llm_design.py).
"""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_TMP_DIR = tempfile.mkdtemp(prefix="permadesign_mixes_test_")
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

_EDM = {"latitude": 53.5461, "longitude": -113.4938}


class _FakeClient:
    def __init__(self, spec):
        self._spec = spec
        self.endpoint = "fake://local"
        self.model = "fake-model"

    def generate_spec(self, prompt, context, extra_hints=None):
        return self._spec


def _smallest_communities(n: int) -> list[dict]:
    """The n seeded communities with the smallest natural footprint —
    keeps multi-pocket placements comfortably inside the default boundary."""
    from src.db.polycultures import (
        community_natural_radius, get_polyculture_by_id,
    )
    comms = [c for c in _api.list_polycultures() if c.get("id") is not None]
    comms.sort(key=lambda c: community_natural_radius(
        get_polyculture_by_id(c["id"]) or {}))
    return comms[:n]


def _community_instances(project) -> dict[str, set]:
    """polyculture_name → set of distinct center anchors among placed plants."""
    out: dict[str, set] = {}
    for p in project.placed_plants:
        name = p.get("polyculture_name")
        clat, clng = (p.get("polyculture_center_lat"),
                      p.get("polyculture_center_lng"))
        if name and clat is not None:
            out.setdefault(name, set()).add((round(clat, 7), round(clng, 7)))
    return out


class TestResolutionUnits(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _use_our_db()

    def test_community_count_and_layout_clamped(self):
        comm = _smallest_communities(1)[0]
        groups = llm._resolve_communities(
            [{"query": comm["name"], "count": 400, "layout": "spiral"}],
            _api.list_polycultures())
        self.assertEqual(len(groups), 1)
        self.assertEqual(groups[0]["count"], llm._MAX_COMMUNITY_COUNT)
        self.assertEqual(groups[0]["layout"], "",
                         "unknown layout names must fall back to ''")

    def test_bare_string_entry_is_one_instance(self):
        comm = _smallest_communities(1)[0]
        groups = llm._resolve_communities([comm["name"]],
                                          _api.list_polycultures())
        self.assertEqual(groups, [{"id": comm["id"], "count": 1,
                                   "layout": ""}])

    def test_community_mix_drops_unmatched_and_dedupes(self):
        comms = _smallest_communities(2)
        mixes = llm._resolve_community_mixes(
            [{"communities": [
                {"query": comms[0]["name"], "weight": 2},
                {"query": comms[0]["name"], "weight": 9},  # dupe → ignored
                {"query": "zzz no such community", "weight": 5},
                {"query": comms[1]["name"]},
            ], "count": 6}],
            _api.list_polycultures())
        self.assertEqual(len(mixes), 1)
        self.assertEqual([m[0] for m in mixes[0]["members"]],
                         [comms[0]["id"], comms[1]["id"]])
        self.assertEqual(mixes[0]["members"][0][1], 2)
        self.assertEqual(mixes[0]["count"], 6)

    def test_expected_mix_counts_match_even_split(self):
        counts = llm._expected_mix_counts([(1, 2), (2, 1)], 6)
        self.assertEqual(counts, {1: 4, 2: 2})

    def test_plant_mix_resolution_caps_quantity(self):
        mixes = llm._resolve_plant_mixes(
            [{"plants": [{"query": "yarrow", "weight": 3},
                         {"query": "wild bergamot"}],
              "quantity": 100000, "layout": "drift"}],
            _api.query_plants, None)
        self.assertEqual(len(mixes), 1)
        self.assertEqual(mixes[0]["quantity"], 60)
        self.assertEqual(len(mixes[0]["members"]), 2)

    def test_spec_with_only_mixes_is_valid(self):
        llm._validate_spec({"community_mixes": [{"communities": []}]})
        llm._validate_spec({"plant_mixes": [{"plants": []}]})
        with self.assertRaises(Exception):
            llm._validate_spec({"structures": []})


class TestMixPlacement(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _use_our_db()

    def test_community_count_places_n_instances(self):
        comm = _smallest_communities(1)[0]
        client = _FakeClient({"communities": [
            {"query": comm["name"], "count": 2}]})
        project = llm.generate_design("two pockets", site_config=_EDM,
                                      client=client)
        instances = _community_instances(project)
        self.assertIn(comm["name"], instances)
        self.assertEqual(len(instances[comm["name"]]), 2,
                         "count: 2 should yield two distinct anchors")

    def test_community_row_layout_places_n_instances(self):
        comm = _smallest_communities(1)[0]
        client = _FakeClient({"communities": [
            {"query": comm["name"], "count": 3, "layout": "row"}]})
        project = llm.generate_design("a community row", site_config=_EDM,
                                      client=client)
        instances = _community_instances(project)
        self.assertEqual(len(instances.get(comm["name"], set())), 3)

    def test_community_mix_honours_weight_ratio(self):
        a, b = _smallest_communities(2)
        client = _FakeClient({"community_mixes": [
            {"communities": [{"query": a["name"], "weight": 2},
                             {"query": b["name"], "weight": 1}],
             "count": 6}]})
        project = llm.generate_design("a mosaic", site_config=_EDM,
                                      client=client)
        instances = _community_instances(project)
        self.assertEqual(len(instances.get(a["name"], set())), 4,
                         "2:1 over six pockets = 4 of the heavier type")
        self.assertEqual(len(instances.get(b["name"], set())), 2)

    def test_plant_mix_interleaves_by_ratio(self):
        yarrow = _api.query_plants(query="yarrow")[0]["id"]
        bergamot = _api.query_plants(query="wild bergamot")[0]["id"]
        client = _FakeClient({"plant_mixes": [
            {"plants": [{"query": "yarrow", "weight": 3},
                        {"query": "wild bergamot", "weight": 1}],
             "quantity": 8, "layout": "grid"}]})
        project = llm.generate_design("a meadow mix", site_config=_EDM,
                                      client=client)
        counts: dict[int, int] = {}
        for p in project.placed_plants:
            counts[p["plant_id"]] = counts.get(p["plant_id"], 0) + 1
        self.assertEqual(counts.get(yarrow, 0), 6,
                         "3:1 over eight positions = six of the heavier")
        self.assertEqual(counts.get(bergamot, 0), 2)
        for p in project.placed_plants:
            self.assertAlmostEqual(p["lat"], _EDM["latitude"], delta=0.01)
            self.assertAlmostEqual(p["lng"], _EDM["longitude"], delta=0.01)

    def test_single_member_mixes_fold_down(self):
        comm = _smallest_communities(1)[0]
        client = _FakeClient({
            "community_mixes": [{"communities": [
                {"query": comm["name"], "weight": 3},
                {"query": "zzz nothing", "weight": 1}], "count": 2}],
            "plant_mixes": [{"plants": [
                {"query": "yarrow"},
                {"query": "zzz nothing"}], "quantity": 4}],
        })
        project = llm.generate_design("folded", site_config=_EDM,
                                      client=client)
        instances = _community_instances(project)
        self.assertEqual(len(instances.get(comm["name"], set())), 2,
                         "1-member community mix folds to count instances")
        yarrow = _api.query_plants(query="yarrow")[0]["id"]
        n_yarrow = sum(1 for p in project.placed_plants
                       if p["plant_id"] == yarrow)
        self.assertEqual(n_yarrow, 4,
                         "1-member plant mix folds to a plain plant group")

    def test_mix_placement_is_deterministic(self):
        a, b = _smallest_communities(2)
        spec = {
            "plant_mixes": [{"plants": [{"query": "yarrow", "weight": 2},
                                        {"query": "gaillardia"}],
                             "quantity": 9, "layout": "drift"}],
            "community_mixes": [{"communities": [
                {"query": a["name"]}, {"query": b["name"]}], "count": 4}],
        }

        def _coords():
            project = llm.generate_design("same twice", site_config=_EDM,
                                          client=_FakeClient(dict(spec)))
            return sorted((p["plant_id"], round(p["lat"], 9),
                           round(p["lng"], 9))
                          for p in project.placed_plants)

        self.assertEqual(_coords(), _coords())

    def test_tiny_budget_drops_mixes_but_keeps_a_design(self):
        client = _FakeClient({
            "plants": [{"query": "yarrow", "quantity": 2}],
            "plant_mixes": [{"plants": [{"query": "prairie crocus"},
                                        {"query": "gaillardia"}],
                             "quantity": 20}],
            "community_mixes": [{"communities": [
                {"query": c["name"]} for c in _smallest_communities(2)],
                "count": 4}],
        })
        project = llm.generate_design("cheap", site_config=_EDM,
                                      client=client, budget=5.0)
        self.assertGreaterEqual(len(project.placed_plants), 1,
                                "budget trim must keep at least one plant")
        self.assertFalse(_community_instances(project),
                         "a $5 budget cannot afford community pockets")


if __name__ == "__main__":
    unittest.main()

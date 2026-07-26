"""
tests/test_relationship_graph.py

The relationship-web overlay's Qt-free core (F5) — src/relationship_graph.py.

The graph is a *claim about the design* rendered as geometry, so the tests here
are mostly about honesty and readability rather than pixels:

  * one node per species, not per placement (or the picture becomes a hairball);
  * animals ring the planting, outside it, marked ``on_ring`` so nothing implies
    a bumble bee has an address in the yard (P9);
  * the readability cap keeps specialists and reports what it dropped;
  * "held up by a single plant" falls out of the graph, matching what the
    pull-a-plant simulator says in words;
  * an empty or edgeless design produces a well-formed empty graph, never a
    crash and never an invented edge.

No DB: the edge provider and the fauna lookup are injected.
"""

import math
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.db.relationships import Edge  # noqa: E402
from src.relationship_graph import (  # noqa: E402
    DEFAULT_KINDS,
    build_relationship_graph,
    summary_lines,
    _mean_bearing,
    _spread_angles,
)

_LAT, _LNG = 51.05, -114.07


def _placed(pid, name, dlat=0.0, dlng=0.0):
    return {"plant_id": pid, "common_name": name,
            "lat": _LAT + dlat, "lng": _LNG + dlng}


def _fauna(ids):
    return {i: {"id": i, "common_name": f"Animal {i}",
                "scientific_name": f"Genus sp{i}", "taxon": "bee"}
            for i in ids}


def _provider(edges):
    def provide(plant_ids, kinds=None):
        wanted = set(kinds) if kinds else None
        return [e for e in edges
                if (wanted is None or e.kind in wanted)
                and e.a_id in set(plant_ids)]
    return provide


def _edge(kind, a, b_type, b, detail="", strength=0.7, evidence="documented"):
    return Edge(kind=kind, a_id=a, b_type=b_type, b_id=b,
                directed=(b_type == "fauna"), strength=strength,
                evidence=evidence, detail=detail)


class TestNodes(unittest.TestCase):

    def test_one_node_per_species_at_the_placement_centroid(self):
        placed = [_placed(1, "Bergamot", 0.0, 0.0),
                  _placed(1, "Bergamot", 0.0002, 0.0),
                  _placed(2, "Aspen", 0.0004, 0.0)]
        g = build_relationship_graph(
            placed, edges_provider=_provider([]), fauna_lookup=_fauna)
        plants = [n for n in g["nodes"] if n["type"] == "plant"]
        self.assertEqual(len(plants), 2)
        berg = next(n for n in plants if n["plant_id"] == 1)
        self.assertEqual(berg["count"], 2)
        self.assertAlmostEqual(berg["lat"], _LAT + 0.0001, places=6)

    def test_fauna_sit_outside_the_planting_and_say_so(self):
        placed = [_placed(1, "Bergamot"), _placed(2, "Aspen", 0.0003)]
        edges = [_edge("nectar", 1, "fauna", 50)]
        g = build_relationship_graph(placed, edges_provider=_provider(edges),
                                     fauna_lookup=_fauna)
        animal = next(n for n in g["nodes"] if n["type"] == "fauna")
        self.assertTrue(animal["on_ring"])
        ring = g["ring"]
        d_lat = (animal["lat"] - ring["lat"]) * 111320.0
        d_lng = ((animal["lng"] - ring["lng"]) * 111320.0
                 * math.cos(math.radians(ring["lat"])))
        self.assertAlmostEqual(math.hypot(d_lat, d_lng), ring["radius_m"],
                               delta=0.5)

    def test_ring_clears_the_furthest_plant(self):
        placed = [_placed(1, "A"), _placed(2, "B", 0.0009)]   # ~100 m apart
        g = build_relationship_graph(placed, edges_provider=_provider(
            [_edge("nectar", 1, "fauna", 50)]), fauna_lookup=_fauna)
        # Half the span from the centroid, plus the margin.
        self.assertGreater(g["ring"]["radius_m"], 50.0)

    def test_isolated_plants_are_named_not_hidden(self):
        placed = [_placed(1, "Bergamot"), _placed(2, "Lonely Sedge", 0.0002)]
        g = build_relationship_graph(placed, edges_provider=_provider(
            [_edge("nectar", 1, "fauna", 50)]), fauna_lookup=_fauna)
        self.assertEqual(g["stats"]["isolated"], ["Lonely Sedge"])

    def test_plants_without_coordinates_are_skipped(self):
        placed = [_placed(1, "Bergamot"),
                  {"plant_id": 2, "common_name": "No Position"}]
        g = build_relationship_graph(placed, edges_provider=_provider([]),
                                     fauna_lookup=_fauna)
        self.assertEqual(g["stats"]["species"], 1)


class TestEdges(unittest.TestCase):

    def test_edges_carry_both_endpoints_so_the_js_does_no_lookups(self):
        placed = [_placed(1, "Bergamot")]
        g = build_relationship_graph(placed, edges_provider=_provider(
            [_edge("nectar", 1, "fauna", 50)]), fauna_lookup=_fauna)
        e = g["edges"][0]
        for key in ("a_lat", "a_lng", "b_lat", "b_lng", "color", "phrase"):
            self.assertIn(key, e)

    def test_edge_to_a_dropped_node_is_dropped_too(self):
        # Cap of 1 keeps one animal; the other's edge must not survive as a
        # line to nowhere.
        placed = [_placed(1, "Bergamot")]
        edges = [_edge("nectar", 1, "fauna", 50),
                 _edge("nectar", 1, "fauna", 51)]
        g = build_relationship_graph(placed, edges_provider=_provider(edges),
                                     fauna_lookup=_fauna, max_fauna=1)
        self.assertEqual(len(g["edges"]), 1)
        self.assertEqual(g["stats"]["dropped_fauna"], 1)

    def test_degree_counts_both_ends(self):
        placed = [_placed(1, "Bergamot")]
        edges = [_edge("nectar", 1, "fauna", 50),
                 _edge("pollen", 1, "fauna", 51)]
        g = build_relationship_graph(placed, edges_provider=_provider(edges),
                                     fauna_lookup=_fauna)
        plant = next(n for n in g["nodes"] if n["type"] == "plant")
        self.assertEqual(plant["degree"], 2)

    def test_legend_names_only_the_kinds_actually_drawn(self):
        placed = [_placed(1, "Bergamot")]
        g = build_relationship_graph(placed, edges_provider=_provider(
            [_edge("nectar", 1, "fauna", 50)]), fauna_lookup=_fauna)
        self.assertEqual([l["kind"] for l in g["legend"]], ["nectar"])

    def test_unknown_kinds_are_filtered_out_of_the_request(self):
        placed = [_placed(1, "Bergamot")]
        seen = {}

        def provide(plant_ids, kinds=None):
            seen["kinds"] = kinds
            return []

        build_relationship_graph(placed, kinds=("nectar", "telepathy"),
                                 edges_provider=provide, fauna_lookup=_fauna)
        self.assertEqual(seen["kinds"], ("nectar",))

    def test_default_kinds_lead_with_the_food_web(self):
        self.assertIn("larval_host", DEFAULT_KINDS)
        # Companion/community edges are horticultural bookkeeping and would
        # swamp the food web by count — opt-in only.
        self.assertNotIn("co_planted", DEFAULT_KINDS)
        self.assertNotIn("shared_fauna", DEFAULT_KINDS)


class TestHonesty(unittest.TestCase):

    def test_specialists_survive_the_readability_cap(self):
        placed = [_placed(1, "Milkweed"), _placed(2, "Aster", 0.0001)]
        edges = [_edge("nectar", 2, "fauna", 60),
                 _edge("nectar", 2, "fauna", 61),
                 _edge("larval_host", 1, "fauna", 99, detail="specialist")]
        g = build_relationship_graph(placed, edges_provider=_provider(edges),
                                     fauna_lookup=_fauna, max_fauna=1)
        kept = [n for n in g["nodes"] if n["type"] == "fauna"]
        self.assertEqual(len(kept), 1)
        self.assertTrue(kept[0]["specialist"])
        self.assertEqual(kept[0]["fauna_id"], 99)

    def test_single_support_animals_are_counted(self):
        placed = [_placed(1, "Milkweed"), _placed(2, "Aster", 0.0001)]
        edges = [_edge("nectar", 1, "fauna", 50),   # both plants feed 50
                 _edge("nectar", 2, "fauna", 50),
                 _edge("nectar", 2, "fauna", 51)]   # only Aster feeds 51
        g = build_relationship_graph(placed, edges_provider=_provider(edges),
                                     fauna_lookup=_fauna)
        self.assertEqual(g["stats"]["single_support"], 1)
        shared = next(n for n in g["nodes"] if n.get("fauna_id") == 50)
        self.assertFalse(shared["only_source"])

    def test_derived_edges_are_reported_separately(self):
        placed = [_placed(1, "A"), _placed(2, "B", 0.0001)]
        edges = [_edge("shared_fauna", 1, "plant", 2, evidence="derived")]
        g = build_relationship_graph(placed, kinds=("shared_fauna",),
                                     edges_provider=_provider(edges),
                                     fauna_lookup=_fauna)
        self.assertEqual(g["stats"]["derived_edges"], 1)
        self.assertIn("inferred", " ".join(summary_lines(g)))

    def test_summary_says_what_was_dropped(self):
        placed = [_placed(1, "Bergamot")]
        edges = [_edge("nectar", 1, "fauna", 50 + i) for i in range(5)]
        g = build_relationship_graph(placed, edges_provider=_provider(edges),
                                     fauna_lookup=_fauna, max_fauna=2)
        text = " ".join(summary_lines(g))
        self.assertIn("3 further wildlife species are supported", text)

    def test_summary_headline_counts_only_documented_edges(self):
        # With derived links on, calling the whole total "documented" would
        # contradict the very next line of the same summary.
        placed = [_placed(1, "A"), _placed(2, "B", 0.0001)]
        edges = [_edge("nectar", 1, "fauna", 50),
                 _edge("shared_fauna", 1, "plant", 2, evidence="derived")]
        g = build_relationship_graph(placed, kinds=("nectar", "shared_fauna"),
                                     edges_provider=_provider(edges),
                                     fauna_lookup=_fauna)
        self.assertEqual(g["stats"]["edges"], 2)
        self.assertIn("1 documented relationship ", summary_lines(g)[0] + " ")

    def test_summary_agrees_in_number(self):
        placed = [_placed(1, "Bergamot")]
        edges = [_edge("nectar", 1, "fauna", 50)]
        g = build_relationship_graph(placed, edges_provider=_provider(edges),
                                     fauna_lookup=_fauna)
        text = " ".join(summary_lines(g))
        self.assertIn("1 wildlife species is held up", text)
        self.assertNotIn("species are held up", text)

    def test_empty_design_is_well_formed(self):
        g = build_relationship_graph([], edges_provider=_provider([]))
        self.assertEqual(g["nodes"], [])
        self.assertEqual(g["edges"], [])
        self.assertEqual(g["stats"]["species"], 0)
        self.assertIn("Place some plants", summary_lines(g)[0])


class TestRingGeometry(unittest.TestCase):

    def test_mean_bearing_wraps_around_north(self):
        self.assertAlmostEqual(_mean_bearing([350.0, 10.0]) % 360.0, 0.0,
                               places=4)

    def test_spread_pushes_coincident_angles_apart(self):
        out = _spread_angles([10.0, 10.0, 10.0], min_gap=5.0)
        gaps = [out[i + 1] - out[i] for i in range(len(out) - 1)]
        self.assertTrue(all(g >= 4.99 for g in gaps), out)

    def test_spread_falls_back_to_even_spacing_when_the_ring_is_full(self):
        out = _spread_angles([0.0] * 10, min_gap=45.0)
        self.assertEqual(len(out), 10)
        self.assertEqual(len(set(round(a, 3) for a in out)), 10)

    def test_animals_sit_toward_the_plants_that_support_them(self):
        # Two plants far apart; each feeds its own animal. The animals must end
        # up on opposite sides of the ring, not stacked together.
        placed = [_placed(1, "North Plant", 0.0006, 0.0),
                  _placed(2, "South Plant", -0.0006, 0.0)]
        edges = [_edge("nectar", 1, "fauna", 50),
                 _edge("nectar", 2, "fauna", 51)]
        g = build_relationship_graph(placed, edges_provider=_provider(edges),
                                     fauna_lookup=_fauna)
        a = next(n for n in g["nodes"] if n.get("fauna_id") == 50)
        b = next(n for n in g["nodes"] if n.get("fauna_id") == 51)
        self.assertGreater(a["lat"], g["ring"]["lat"])
        self.assertLess(b["lat"], g["ring"]["lat"])


class TestPanelLayerTable(unittest.TestCase):
    """The Habitat tab's layer checkboxes and the edge vocabulary must not
    drift apart — a new EdgeKind with no checkbox is invisible, and a checkbox
    naming a dead kind silently does nothing.

    Read via AST so this runs in the PyQt6-less test container too.
    """

    @staticmethod
    def _layers():
        import ast
        from pathlib import Path
        root = Path(__file__).resolve().parent.parent
        tree = ast.parse((root / "src" / "analysis_panel.py")
                         .read_text(encoding="utf-8"))
        cls = next(n for n in tree.body if isinstance(n, ast.ClassDef))
        for node in cls.body:
            if (isinstance(node, ast.Assign)
                    and getattr(node.targets[0], "id", "") == "_WEB_LAYERS"):
                return ast.literal_eval(node.value)
        raise AssertionError("AnalysisPanel._WEB_LAYERS not found")

    def test_every_kind_is_offered_exactly_once(self):
        from src.db.relationships import EDGE_KINDS
        seen = set()
        for _key, _label, _on, kinds in self._layers():
            for kind in kinds:
                self.assertIn(kind, EDGE_KINDS,
                              f"panel offers unknown edge kind {kind!r}")
                self.assertNotIn(kind, seen,
                                 f"{kind!r} is offered by two layers")
                seen.add(kind)
        self.assertEqual(seen, set(EDGE_KINDS),
                         f"no checkbox reaches: {set(EDGE_KINDS) - seen}")

    def test_checked_by_default_matches_default_kinds(self):
        checked = {k for _key, _l, on, kinds in self._layers() if on
                   for k in kinds}
        self.assertEqual(checked, set(DEFAULT_KINDS))


if __name__ == "__main__":
    unittest.main()

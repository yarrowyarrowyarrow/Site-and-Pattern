"""
tests/test_relationships.py

The unified relationship-edges layer (F7, schema v51) — src/db/relationships.py
and the ``relationship_edges`` VIEW it reads.

Covers the properties that make the layer trustworthy rather than merely
present:

  * the view unions all four documented edge shapes and only those;
  * a design-scoped query keeps plant→fauna edges but drops plant↔plant edges
    with one end outside the design;
  * mirror rows collapse to one edge per unordered pair;
  * a specialist edge outranks a generalist one;
  * derived (computed) edges are labelled as derived and never masquerade as
    seeded records (P9);
  * an unknown ``kind`` is dropped rather than guessed at.
"""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_TMP_DIR = tempfile.mkdtemp(prefix="permadesign_rel_test_")

import src.db.plants as _plants_mod  # noqa: E402

_plants_mod._DATA_DIR = _TMP_DIR
_plants_mod._DB_PATH = os.path.join(_TMP_DIR, "permadesign_test.db")

from src.db.plants import init_db, get_connection  # noqa: E402
from src.db import relationships as R  # noqa: E402


class TestEdgeVocabulary(unittest.TestCase):
    """The registry is the shared vocabulary — the view, the graph, the legend
    and the panel all key off it."""

    def test_documented_and_derived_partition_the_kinds(self):
        self.assertEqual(
            set(R.DOCUMENTED_KINDS) | set(R.DERIVED_KINDS),
            set(R.EDGE_KINDS))
        self.assertFalse(set(R.DOCUMENTED_KINDS) & set(R.DERIVED_KINDS))

    def test_every_plant_fauna_relationship_has_a_kind(self):
        # The schema's CHECK list must be fully covered, or an edge type would
        # silently vanish from every consumer of the layer.
        for rel in ("larval_host", "nectar", "pollen", "seed_food",
                    "fruit_food", "nesting", "cover"):
            self.assertIn(rel, R.EDGE_KINDS)
            self.assertEqual(R.EDGE_KINDS[rel].b_type, "fauna")

    def test_larval_host_outweighs_nectar(self):
        # Tallamy's point, encoded: hosting caterpillars is the scarcer and
        # more consequential service.
        self.assertGreater(R.EDGE_KINDS["larval_host"].weight,
                           R.EDGE_KINDS["nectar"].weight)

    def test_edge_kinds_filter_by_group(self):
        trophic = {k["kind"] for k in R.edge_kinds("trophic")}
        self.assertIn("larval_host", trophic)
        self.assertNotIn("companion_friend", trophic)


class TestViewAgainstSeedData(unittest.TestCase):
    """The view over the real seeded catalogue."""

    @classmethod
    def setUpClass(cls):
        init_db()

    def test_view_exists_and_covers_every_source_table(self):
        conn = get_connection()
        try:
            kinds = {r["kind"] for r in conn.execute(
                "SELECT DISTINCT kind FROM relationship_edges")}
        finally:
            conn.close()
        self.assertTrue(kinds, "relationship_edges view is empty")
        # plant_fauna and polyculture membership are both seeded, so both
        # families must show up.
        self.assertTrue(kinds & {"nectar", "larval_host"},
                        f"no plant_fauna edges in the view: {kinds}")
        self.assertIn("co_planted", kinds)
        self.assertTrue(kinds <= set(R.DOCUMENTED_KINDS),
                        f"view emits kinds outside the vocabulary: "
                        f"{kinds - set(R.DOCUMENTED_KINDS)}")

    def test_view_row_counts_match_the_source_tables(self):
        """The view must not invent or lose plant→fauna edges.

        V2.42: the view gained a second plant→fauna arm (`plant_fauna_derived`),
        so this is now a per-evidence identity rather than a single total. That
        split is the point — the documented count must stay *exactly*
        `plant_fauna`, or derived edges have leaked into the documented
        population.
        """
        conn = get_connection()
        try:
            documented_src = conn.execute(
                "SELECT COUNT(*) FROM plant_fauna "
                "WHERE COALESCE(source,'') <> ''").fetchone()[0]
            documented_view = conn.execute(
                "SELECT COUNT(*) FROM relationship_edges "
                "WHERE b_type = 'fauna' AND evidence = 'documented'"
            ).fetchone()[0]
            derived_src = conn.execute(
                "SELECT COUNT(*) FROM plant_fauna_derived").fetchone()[0]
            derived_view = conn.execute(
                "SELECT COUNT(*) FROM relationship_edges "
                "WHERE b_type = 'fauna' AND evidence = 'derived'").fetchone()[0]
            total_src = conn.execute(
                "SELECT COUNT(*) FROM plant_fauna").fetchone()[0]
            total_view = conn.execute(
                "SELECT COUNT(*) FROM relationship_edges "
                "WHERE b_type = 'fauna'").fetchone()[0]
        finally:
            conn.close()
        self.assertEqual(documented_src, documented_view)
        self.assertEqual(derived_src, derived_view)
        self.assertEqual(total_src + derived_src, total_view)

    def test_co_planted_pairs_are_unordered_and_self_free(self):
        conn = get_connection()
        try:
            bad = conn.execute(
                "SELECT COUNT(*) FROM relationship_edges "
                "WHERE kind = 'co_planted' AND a_id >= b_id").fetchone()[0]
        finally:
            conn.close()
        self.assertEqual(bad, 0)

    def test_edges_for_plant_finds_a_known_host(self):
        pid = _pid("Common Milkweed") or _pid("Showy Milkweed")
        if pid is None:
            self.skipTest("no milkweed in the seeded catalogue")
        edges = R.edges_for_plant(pid)
        self.assertTrue(edges)
        self.assertIn("larval_host", {e.kind for e in edges})

    def test_neighbourhood_resolves_names_and_groups(self):
        pid = _pid("Common Milkweed") or _pid("Showy Milkweed")
        if pid is None:
            self.skipTest("no milkweed in the seeded catalogue")
        n = R.neighbourhood(pid)
        self.assertEqual(n["plant_id"], pid)
        self.assertGreater(n["total"], 0)
        kinds = [g["kind"] for g in n["groups"]]
        self.assertIn("larval_host", kinds)
        host = next(g for g in n["groups"] if g["kind"] == "larval_host")
        self.assertTrue(any("Monarch" in it["name"] for it in host["items"]),
                        f"monarch not among milkweed's hosts: {host['items']}")
        # V2.42: `evidence` has three states, so "all documented" is no longer
        # the invariant — a neighbourhood legitimately mixes cited records with
        # derived genus-level ones. What must hold is that every item declares
        # one of the three, and that the monarch↔milkweed edge — the app's
        # best-attested relationship — is still a documented record.
        for it in host["items"]:
            self.assertIn(it["evidence"], ("documented", "recorded", "derived"))
        monarch = next(it for it in host["items"] if "Monarch" in it["name"])
        self.assertEqual(monarch["evidence"], "documented")
        self.assertTrue(monarch.get("source"),
                        "a documented edge has to say where it came from")


def _pid(common_name: str):
    conn = get_connection()
    try:
        row = conn.execute("SELECT id FROM plants WHERE common_name = ?",
                           (common_name,)).fetchone()
        return row["id"] if row else None
    finally:
        conn.close()


# ── Behaviour on a synthetic, fully-controlled edge set ──────────────────────

class _FakeCursor(list):
    """Iterable like a sqlite3 cursor, and answers ``fetchall``."""

    def fetchall(self):
        return list(self)


class _FakeConn:
    """A tiny in-memory stand-in so the query semantics can be tested against
    edges we chose, not whatever the catalogue happens to contain."""

    def __init__(self, rows):
        self._rows = rows

    def execute(self, sql, params=()):
        params = list(params)
        if "FROM relationship_edges" in sql and "fauna f" in sql:
            return _FakeCursor(
                {"pid": r["a_id"], "fid": r["b_id"],
                 "name": f"animal {r['b_id']}"}
                for r in self._rows
                if r["b_type"] == "fauna" and r["a_id"] in params)
        if "FROM relationship_edges" in sql:
            kinds = [p for p in params if isinstance(p, str)]
            ids = [p for p in params if isinstance(p, int)]
            return _FakeCursor(
                dict(r) for r in self._rows
                if r["kind"] in kinds
                and (r["a_id"] in ids
                     or (r["b_type"] == "plant" and r["b_id"] in ids)))
        return _FakeCursor()

    def close(self):
        pass


def _row(kind, a, b_type, b, directed=1, detail="", source=""):
    return {"kind": kind, "a_id": a, "b_type": b_type, "b_id": b,
            "directed": directed, "detail": detail, "source": source}


class TestQuerySemantics(unittest.TestCase):

    def _connect(self, rows):
        return lambda: _FakeConn(rows)

    def test_plant_plant_edge_needs_both_ends_in_the_design(self):
        rows = [_row("companion_friend", 1, "plant", 2, 0),
                _row("companion_friend", 1, "plant", 99, 0)]
        edges = R.edges_among([1, 2], kinds=["companion_friend"],
                              connect=self._connect(rows))
        self.assertEqual(len(edges), 1)
        self.assertEqual({edges[0].a_id, edges[0].b_id}, {1, 2})

    def test_plant_fauna_edge_needs_only_its_plant(self):
        rows = [_row("nectar", 1, "fauna", 50, 1, "generalist")]
        edges = R.edges_among([1], kinds=["nectar"],
                              connect=self._connect(rows))
        self.assertEqual(len(edges), 1)
        self.assertEqual(edges[0].b_type, "fauna")
        self.assertTrue(edges[0].directed)

    def test_mirror_rows_collapse_to_one_edge(self):
        rows = [_row("companion_friend", 1, "plant", 2, 0),
                _row("companion_friend", 2, "plant", 1, 0)]
        edges = R.edges_among([1, 2], kinds=["companion_friend"],
                              connect=self._connect(rows))
        self.assertEqual(len(edges), 1)

    def test_self_pairs_are_dropped(self):
        rows = [_row("companion_friend", 1, "plant", 1, 0)]
        edges = R.edges_among([1], kinds=["companion_friend"],
                              connect=self._connect(rows))
        self.assertEqual(edges, [])

    def test_specialist_edge_is_stronger_than_generalist(self):
        rows = [_row("larval_host", 1, "fauna", 50, 1, "specialist"),
                _row("larval_host", 2, "fauna", 51, 1, "generalist")]
        edges = R.edges_among([1, 2], kinds=["larval_host"],
                              connect=self._connect(rows))
        by_plant = {e.a_id: e for e in edges}
        self.assertGreater(by_plant[1].strength, by_plant[2].strength)

    def test_unknown_kind_is_dropped_not_guessed(self):
        rows = [_row("telepathy", 1, "fauna", 50)]
        edges = R.edges_among([1], kinds=["nectar", "telepathy"],
                              connect=self._connect(rows))
        self.assertEqual(edges, [])

    def test_documented_edges_carry_their_source(self):
        rows = [_row("nectar", 1, "fauna", 50, 1, "generalist", "Xerces 2018")]
        edges = R.edges_among([1], kinds=["nectar"],
                              connect=self._connect(rows))
        self.assertEqual(edges[0].source, "Xerces 2018")
        self.assertEqual(edges[0].evidence, "documented")

    def test_empty_design_returns_nothing(self):
        self.assertEqual(R.edges_among([]), [])
        self.assertEqual(R.edges_among([1], kinds=[]), [])


class TestDerivedEdges(unittest.TestCase):
    """The second-order edge only a unified layer can see — and the honesty
    contract around it."""

    def _connect(self, rows):
        return lambda: _FakeConn(rows)

    def test_two_plants_feeding_one_animal_are_linked(self):
        rows = [_row("nectar", 1, "fauna", 50),
                _row("nectar", 2, "fauna", 50)]
        edges = R.shared_fauna_edges([1, 2], connect=self._connect(rows))
        self.assertEqual(len(edges), 1)
        self.assertEqual({edges[0].a_id, edges[0].b_id}, {1, 2})

    def test_derived_edges_are_labelled_derived(self):
        rows = [_row("nectar", 1, "fauna", 50),
                _row("nectar", 2, "fauna", 50)]
        edges = R.shared_fauna_edges([1, 2], connect=self._connect(rows))
        self.assertEqual(edges[0].evidence, "derived")
        self.assertEqual(edges[0].kind, "shared_fauna")

    def test_more_shared_species_means_a_stronger_link(self):
        few = [_row("nectar", 1, "fauna", 50), _row("nectar", 2, "fauna", 50)]
        many = few + [_row("pollen", 1, "fauna", 51),
                      _row("pollen", 2, "fauna", 51)]
        a = R.shared_fauna_edges([1, 2], connect=self._connect(few))[0]
        b = R.shared_fauna_edges([1, 2], connect=self._connect(many))[0]
        self.assertGreater(b.strength, a.strength)

    def test_an_animal_with_one_host_creates_no_link(self):
        rows = [_row("nectar", 1, "fauna", 50)]
        self.assertEqual(R.shared_fauna_edges([1, 2],
                                              connect=self._connect(rows)), [])

    def test_derived_edges_are_opt_in(self):
        rows = [_row("nectar", 1, "fauna", 50), _row("nectar", 2, "fauna", 50)]
        without = R.edges_among([1, 2], kinds=["nectar"],
                                connect=self._connect(rows))
        self.assertNotIn("shared_fauna", {e.kind for e in without})
        with_derived = R.edges_among([1, 2], kinds=["nectar", "shared_fauna"],
                                     connect=self._connect(rows))
        self.assertIn("shared_fauna", {e.kind for e in with_derived})


if __name__ == "__main__":
    unittest.main()

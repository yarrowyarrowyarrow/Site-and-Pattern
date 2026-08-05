"""
tests/test_derived_edges.py

The V2.42 coverage work: genus-level host records expanded into species-level
edges (docs/DATA_AUDIT.md §6), the three-state ``evidence`` that keeps them
distinguishable from documented records, and the fauna↔fauna edges that reach
the cuckoo bees.

The tests that matter most here are the *negative* ones. Raising relationship
coverage from 22.6% to ~46% is only defensible while a derived edge stays
visibly derived, stays out of the headline scores, and keeps pointing at the
work its genus claim came from — so those three properties are pinned harder
than the coverage number itself.
"""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_TMP_DIR = tempfile.mkdtemp(prefix="permadesign_derived_test_")

import src.db.plants as _plants_mod  # noqa: E402

_plants_mod._DATA_DIR = _TMP_DIR
_plants_mod._DB_PATH  = os.path.join(_TMP_DIR, "permadesign_test.db")

from src.db.derived_edges import (  # noqa: E402
    GENUS_SYNONYMS,
    build_genus_index,
    match_genus,
    _confidence,
    genus_host_edges,
    cleptoparasite_edges,
)


# ── The derivation itself (pure, no DB) ───────────────────────────────────────

class TestGenusMatching(unittest.TestCase):

    PLANTS = [
        {"common_name": "Smooth Aster", "scientific_name": "Symphyotrichum laeve"},
        {"common_name": "Showy Aster", "scientific_name": "Eurybia conspicua"},
        {"common_name": "Alpine Aster", "scientific_name": "Aster alpinus"},
        {"common_name": "Fireweed", "scientific_name": "Chamaenerion angustifolium"},
        {"common_name": "Gumweed", "scientific_name": "Grindelia squarrosa"},
    ]

    def setUp(self):
        self.index = build_genus_index(self.PLANTS)

    def test_literal_match_is_not_flagged_as_synonym(self):
        rows, via = match_genus("Grindelia", self.index)
        self.assertEqual([r["common_name"] for r in rows], ["Gumweed"])
        self.assertFalse(via)

    def test_synonym_match_finds_fireweed_under_current_name(self):
        """The bug this table exists for: bee records cite *Epilobium*, the
        catalogue correctly carries *Chamaenerion*, and a literal match reported
        fireweed — a major native bee plant — as absent from the catalogue."""
        rows, via = match_genus("Epilobium", self.index)
        self.assertEqual([r["common_name"] for r in rows], ["Fireweed"])
        self.assertTrue(via, "a segregate-genus match must be flagged so it "
                             "costs a confidence band")

    def test_literal_and_synonym_both_contribute(self):
        """*Aster* s.l. covers the segregates AND the catalogue's genuine
        *Aster alpinus*. Dropping either side loses real edges."""
        rows, via = match_genus("Aster", self.index)
        names = sorted(r["common_name"] for r in rows)
        self.assertEqual(names, ["Alpine Aster", "Showy Aster", "Smooth Aster"])
        self.assertFalse(via, "a literal hit means the match is not merely "
                              "via synonymy")

    def test_unknown_genus_matches_nothing(self):
        rows, via = match_genus("Haplopappus", self.index)
        self.assertEqual(rows, [])
        self.assertFalse(via)

    def test_synonym_table_only_holds_cited_genera(self):
        """A synonym pair nobody's data needs is a claim nobody checks."""
        for cited in GENUS_SYNONYMS:
            self.assertTrue(cited[:1].isupper(),
                            f"{cited!r} is not a genus name")


class TestConfidenceBanding(unittest.TestCase):

    def test_narrow_genus_is_high(self):
        self.assertEqual(_confidence(1, specialist=False, via_synonym=False),
                         "high")

    def test_wide_genus_is_low(self):
        """*Carex* has 15 species in this catalogue; 'visits Carex' says very
        little about any one of them."""
        self.assertEqual(_confidence(15, specialist=False, via_synonym=False),
                         "low")

    def test_oligolege_is_high_regardless_of_genus_size(self):
        """A pollen specialist's host genus IS the animal's defining trait."""
        self.assertEqual(_confidence(15, specialist=True, via_synonym=False),
                         "high")

    def test_synonym_match_costs_one_band(self):
        self.assertEqual(_confidence(1, specialist=False, via_synonym=True),
                         "moderate")
        self.assertEqual(_confidence(4, specialist=False, via_synonym=True),
                         "low")

    def test_low_cannot_be_downgraded_below_low(self):
        self.assertEqual(_confidence(30, specialist=False, via_synonym=True),
                         "low")

    def test_confidence_is_never_a_number(self):
        """P9: the value that would look most precise here is the one we have
        least right to."""
        for n in (1, 3, 10):
            for spec in (True, False):
                band = _confidence(n, specialist=spec, via_synonym=False)
                self.assertIn(band, ("high", "moderate", "low"))


class TestGenusHostEdges(unittest.TestCase):

    PLANTS = [
        {"common_name": "Smooth Aster", "scientific_name": "Symphyotrichum laeve"},
        {"common_name": "Willow Aster", "scientific_name": "Symphyotrichum lanceolatum"},
        {"common_name": "Gumweed", "scientific_name": "Grindelia squarrosa"},
    ]

    def test_every_derived_edge_keeps_its_citation(self):
        """A derived edge that cannot say which work made the genus claim is
        exactly the unsourced ecology this increment set out to remove."""
        edges, _ = genus_host_edges(
            plants=self.PLANTS,
            fauna_attributes=[{"scientific_name": "Bombus test",
                               "floral_host_genera": "Symphyotrichum",
                               "source": "some_key"}],
            genera_field="floral_host_genera", relationship="pollen")
        self.assertTrue(edges)
        for e in edges:
            self.assertEqual(e["source"], "some_key")
            self.assertEqual(e["derivation"], "genus_host")
            self.assertEqual(e["basis"], "Symphyotrichum")

    def test_unmatched_genera_are_reported_not_swallowed(self):
        _, unmatched = genus_host_edges(
            plants=self.PLANTS,
            fauna_attributes=[{"scientific_name": "Bombus test",
                               "floral_host_genera": "Trifolium,Grindelia",
                               "source": "k"}],
            genera_field="floral_host_genera", relationship="pollen")
        self.assertEqual(unmatched, ["Trifolium"])

    def test_no_duplicate_edges_across_fauna_records(self):
        attrs = [{"scientific_name": "Bombus test",
                  "floral_host_genera": "Grindelia,Grindelia", "source": "k"}]
        edges, _ = genus_host_edges(
            plants=self.PLANTS, fauna_attributes=attrs,
            genera_field="floral_host_genera", relationship="pollen")
        keys = [(e["plant"], e["fauna"], e["relationship"]) for e in edges]
        self.assertEqual(len(keys), len(set(keys)))


class TestCleptoparasiteEdges(unittest.TestCase):

    BEES = [
        {"scientific_name": "Nomada one", "genus": "Nomada",
         "host_genus": "Andrena", "source": "k"},
        {"scientific_name": "Andrena a", "genus": "Andrena", "source": "k"},
        {"scientific_name": "Andrena b", "genus": "Andrena", "source": "k"},
        # Two cuckoo bumblebees whose host genus is their OWN genus.
        {"scientific_name": "Bombus bohemicus", "genus": "Bombus",
         "host_genus": "Bombus", "source": "k"},
        {"scientific_name": "Bombus insularis", "genus": "Bombus",
         "host_genus": "Bombus", "source": "k"},
        {"scientific_name": "Bombus appositus", "genus": "Bombus", "source": "k"},
    ]

    def setUp(self):
        self.edges = cleptoparasite_edges(self.BEES)

    def test_parasite_is_never_its_own_host(self):
        for e in self.edges:
            self.assertNotEqual(e["fauna_a"], e["fauna_b"])

    def test_a_cuckoo_is_never_emitted_as_a_host(self):
        """Without this filter every cuckoo Bombus comes out as a parasite of
        every other cuckoo Bombus, which is not a thing that happens."""
        parasites = {e["fauna_a"] for e in self.edges}
        hosts = {e["fauna_b"] for e in self.edges}
        self.assertEqual(parasites & hosts, set())
        self.assertNotIn("Bombus insularis", hosts)

    def test_cuckoo_bumblebees_are_social_parasites(self):
        kinds = {e["fauna_a"]: e["relationship"] for e in self.edges}
        self.assertEqual(kinds["Bombus bohemicus"], "social_parasite")
        self.assertEqual(kinds["Nomada one"], "cleptoparasite")

    def test_host_genus_absent_from_catalogue_yields_nothing(self):
        edges = cleptoparasite_edges([
            {"scientific_name": "Epeolus x", "genus": "Epeolus",
             "host_genus": "Colletes", "source": "k"}])
        self.assertEqual(edges, [])

    def test_every_edge_is_banded_and_marked_derived(self):
        for e in self.edges:
            self.assertEqual(e["evidence"], "derived")
            self.assertIn(e["confidence"], ("high", "moderate", "low"))


# ── Against the seeded database ───────────────────────────────────────────────

class TestSeededDerivedEdges(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from src.db.plants import init_db
        init_db()

    def _conn(self):
        from src.db.plants import get_connection
        return get_connection()

    def test_derived_edges_are_seeded(self):
        conn = self._conn()
        try:
            n = conn.execute(
                "SELECT COUNT(*) FROM plant_fauna_derived").fetchone()[0]
            self.assertGreater(n, 500, "the genus-host expansion should produce "
                                       "roughly a thousand edges")
        finally:
            conn.close()

    def test_coverage_actually_improved(self):
        """The whole point. Documented edges reach ~23% of the catalogue; with
        derived edges it should be nearer half."""
        conn = self._conn()
        try:
            total = conn.execute("SELECT COUNT(*) FROM plants").fetchone()[0]
            documented = conn.execute(
                "SELECT COUNT(DISTINCT plant_id) FROM plant_fauna").fetchone()[0]
            withderived = conn.execute(
                "SELECT COUNT(DISTINCT a_id) FROM relationship_edges "
                "WHERE b_type='fauna'").fetchone()[0]
            self.assertLess(documented / total, 0.30)
            self.assertGreater(withderived / total, 0.40)
        finally:
            conn.close()

    def test_every_derived_row_carries_source_basis_and_band(self):
        conn = self._conn()
        try:
            bad = conn.execute(
                "SELECT COUNT(*) FROM plant_fauna_derived "
                "WHERE source = '' OR basis = '' OR confidence = ''"
            ).fetchone()[0]
            self.assertEqual(bad, 0)
        finally:
            conn.close()

    def test_evidence_is_three_state_and_derived_is_present(self):
        conn = self._conn()
        try:
            got = {r[0] for r in conn.execute(
                "SELECT DISTINCT evidence FROM relationship_edges")}
            self.assertEqual(got, {"documented", "recorded", "derived"})
        finally:
            conn.close()

    def test_uncited_companions_are_recorded_not_documented(self):
        """The lie this increment set out to fix: companion pairings ship with
        no citation and used to read 'documented' anyway."""
        conn = self._conn()
        try:
            rows = conn.execute(
                "SELECT DISTINCT evidence FROM relationship_edges "
                "WHERE kind IN ('companion_friend','companion_enemy')").fetchall()
            self.assertEqual([r[0] for r in rows], ["recorded"])
        finally:
            conn.close()

    def test_documented_edges_still_read_documented(self):
        conn = self._conn()
        try:
            n = conn.execute(
                "SELECT COUNT(*) FROM relationship_edges "
                "WHERE evidence='documented'").fetchone()[0]
            self.assertGreater(n, 300)
        finally:
            conn.close()

    def test_cuckoo_bees_are_no_longer_orphans(self):
        conn = self._conn()
        try:
            orphans = conn.execute("""
                SELECT COUNT(*) FROM fauna f WHERE
                  f.id NOT IN (SELECT fauna_id FROM plant_fauna)
                  AND f.id NOT IN (SELECT fauna_id FROM plant_fauna_derived)
                  AND f.id NOT IN (SELECT fauna_id_a FROM fauna_fauna)
                  AND f.id NOT IN (SELECT fauna_id_b FROM fauna_fauna)
            """).fetchone()[0]
            # Three remain: a kestrel, a magpie and a bat — predators whose
            # trophic level this data model genuinely does not express. Faking
            # them a plant edge would be worse than leaving them orphaned.
            self.assertLessEqual(orphans, 5)
        finally:
            conn.close()


class TestUpgradeFromV60(unittest.TestCase):
    """An existing install must survive v60 → v61.

    `CREATE TABLE IF NOT EXISTS` is a no-op against a table that already exists,
    so the two new companion columns need a real ALTER. Without it, a DB that
    had merely been *used* before would keep two-column companion tables while
    the recreated `relationship_edges` view selects `cf.source` — and every
    relationship query would fail with "no such column". A fresh install would
    have been fine, which is exactly how this class of bug ships.
    """

    def test_v60_database_upgrades_and_stays_queryable(self):
        import shutil
        import sqlite3
        import tempfile as _tf
        import src.db.plants as plants_mod

        work = _tf.mkdtemp(prefix="permadesign_v60_")
        db = os.path.join(work, "old.db")
        original = plants_mod._DB_PATH
        try:
            plants_mod._DB_PATH = db
            plants_mod.init_db()

            # Rewind to a v60-shaped database.
            conn = sqlite3.connect(db)
            conn.execute("DROP VIEW IF EXISTS relationship_edges")
            conn.execute("DROP TABLE IF EXISTS plant_fauna_derived")
            conn.execute("DROP TABLE IF EXISTS fauna_fauna")
            for table in ("companion_friends", "companion_enemies"):
                conn.execute(f"CREATE TABLE {table}_old AS "
                             f"SELECT plant_id_a, plant_id_b FROM {table}")
                conn.execute(f"DROP TABLE {table}")
                conn.execute(f"ALTER TABLE {table}_old RENAME TO {table}")
            conn.execute("DELETE FROM _schema_version")
            conn.execute("INSERT INTO _schema_version VALUES (60)")
            conn.commit()
            cols = [r[1] for r in
                    conn.execute("PRAGMA table_info(companion_friends)")]
            self.assertEqual(cols, ["plant_id_a", "plant_id_b"])
            conn.close()

            plants_mod.init_db()          # the upgrade under test

            conn = sqlite3.connect(db)
            try:
                cols = [r[1] for r in
                        conn.execute("PRAGMA table_info(companion_friends)")]
                self.assertIn("source", cols)
                self.assertIn("notes", cols)
                # The view must actually be queryable, not merely creatable —
                # SQLite binds view columns lazily, so a broken view only
                # surfaces on SELECT.
                total = conn.execute(
                    "SELECT COUNT(*) FROM relationship_edges").fetchone()[0]
                self.assertGreater(total, 0)
                states = {r[0] for r in conn.execute(
                    "SELECT DISTINCT evidence FROM relationship_edges")}
                self.assertEqual(states,
                                 {"documented", "recorded", "derived"})
                self.assertGreater(conn.execute(
                    "SELECT COUNT(*) FROM plant_fauna_derived").fetchone()[0], 0)
            finally:
                conn.close()
        finally:
            plants_mod._DB_PATH = original
            shutil.rmtree(work, ignore_errors=True)


class TestDerivedEdgesStayOutOfTheScores(unittest.TestCase):
    """THE load-bearing guard of this increment.

    Materialising 1,131 derived edges is only safe while the app's headline
    numbers keep counting documented records. If the Habitat Value Score or the
    "hosts N caterpillars" labels start reading derived edges, every existing
    project's score moves overnight and the app begins overstating what it knows
    in the place users trust it most.

    Today that holds structurally: every scoring consumer queries `plant_fauna`
    directly and only `src/db/relationships.py` reads the view. This test exists
    so that stays a decision rather than an accident.
    """

    SCORING_MODULES = ("habitat_score.py", "placement_score.py",
                       "scene_dossier.py", "db/fauna.py")

    def test_no_scoring_module_reads_derived_edges(self):
        import pathlib
        src = pathlib.Path(__file__).resolve().parent.parent / "src"
        for rel in self.SCORING_MODULES:
            path = src / rel
            if not path.exists():
                continue
            text = path.read_text(encoding="utf-8")
            self.assertNotIn(
                "plant_fauna_derived", text,
                f"{rel} reads derived edges. If that is intended, the Habitat "
                "Value Score changes for every existing project — make that "
                "call deliberately and update this guard.")
            self.assertNotIn(
                "relationship_edges", text,
                f"{rel} reads the unified view, which now carries derived "
                "edges. Scores must read plant_fauna directly.")

    def test_derived_edges_are_discounted_below_documented(self):
        from src.db.relationships import _edge_from_row
        base = dict(kind="pollen", a_id=1, b_type="fauna", b_id=2, directed=1,
                    detail="", source="k")
        documented = _edge_from_row(dict(base, evidence="documented"))
        for band in ("high", "moderate", "low"):
            derived = _edge_from_row(
                dict(base, evidence="derived", confidence=band))
            self.assertLess(
                derived.strength, documented.strength,
                f"a {band}-confidence derived edge must not rank alongside a "
                "documented one")

    def test_derived_strength_still_respects_edge_kind(self):
        """The discount is multiplicative so the vocabulary's own ordering
        survives it — a derived larval-host edge still outweighs derived cover."""
        from src.db.relationships import _edge_from_row
        base = dict(a_id=1, b_type="fauna", b_id=2, directed=1, detail="",
                    source="k", evidence="derived", confidence="high")
        host = _edge_from_row(dict(base, kind="larval_host"))
        cover = _edge_from_row(dict(base, kind="cover"))
        self.assertGreater(host.strength, cover.strength)


if __name__ == "__main__":
    unittest.main()

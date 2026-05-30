"""
tests/test_fauna.py

Verifies the schema v13 / V1.31 ``fauna`` registry and ``plant_fauna``
relationship junction. Confirms the headline data claims:

  * Monarch (Danaus plexippus) → Asclepias only (specialist)
  * Aspen / willow / birch host high lepidoptera counts
  * Lepidoptera-supported aggregation matches per-plant queries
"""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Redirect the DB to a temp directory before importing anything that opens it.
_TMP_DIR = tempfile.mkdtemp(prefix="permadesign_fauna_test_")

import src.db.plants as _plants_mod  # noqa: E402

_plants_mod._DATA_DIR = _TMP_DIR
_plants_mod._DB_PATH  = os.path.join(_TMP_DIR, "permadesign_test.db")

from src.db.plants import init_db, get_connection  # noqa: E402
from src.db.fauna import (  # noqa: E402
    list_fauna,
    fauna_for_plant,
    plants_for_fauna,
    lepidoptera_supported_by_plants,
    fauna_supported_by_plants,
    keystone_rank_lepidoptera,
)


def _pid(common_name: str) -> int | None:
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT id FROM plants WHERE common_name = ?", (common_name,)
        ).fetchone()
        return row[0] if row else None
    finally:
        conn.close()


def _fid(scientific_name: str) -> int | None:
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT id FROM fauna WHERE scientific_name = ?", (scientific_name,)
        ).fetchone()
        return row[0] if row else None
    finally:
        conn.close()


class TestFaunaSchema(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        init_db()

    # ── Registry ───────────────────────────────────────────────────────

    def test_fauna_table_populated(self):
        all_fauna = list_fauna()
        self.assertGreater(len(all_fauna), 20,
            "Expected at least 20 fauna entries in the registry")

    def test_lepidoptera_present(self):
        leps = list_fauna(taxon="lepidoptera")
        self.assertGreater(len(leps), 15,
            "Expected at least 15 lepidoptera entries")

    def test_birds_present(self):
        birds = list_fauna(taxon="bird")
        self.assertGreater(len(birds), 5)

    def test_bees_present(self):
        bees = list_fauna(taxon="bee")
        self.assertGreater(len(bees), 3)

    # ── Headline relationships ─────────────────────────────────────────

    def test_monarch_only_hosts_on_milkweed(self):
        monarch = _fid("Danaus plexippus")
        self.assertIsNotNone(monarch)
        hosts = plants_for_fauna(monarch, relationship="larval_host")
        host_names = {h["common_name"] for h in hosts}
        # Every host must be an Asclepias (milkweed). The DB ships at least
        # two: Showy Milkweed and Green Milkweed.
        self.assertIn("Showy Milkweed", host_names)
        self.assertIn("Green Milkweed", host_names)
        for h in hosts:
            sci = (h.get("scientific_name") or "").lower()
            self.assertTrue(
                sci.startswith("asclepias"),
                f"Monarch larval host {h['common_name']} is not an Asclepias: {sci}",
            )

    def test_showy_milkweed_links_to_monarch_as_specialist(self):
        pid = _pid("Showy Milkweed")
        self.assertIsNotNone(pid)
        rows = fauna_for_plant(pid)
        monarch_rows = [
            r for r in rows
            if r.get("scientific_name") == "Danaus plexippus"
            and r.get("relationship") == "larval_host"
        ]
        self.assertEqual(len(monarch_rows), 1)
        self.assertEqual(monarch_rows[0]["specificity"], "specialist")

    def test_aspen_is_lepidoptera_keystone(self):
        pid = _pid("Trembling Aspen")
        self.assertIsNotNone(pid)
        # Should host at least 4 lepidoptera species (swallowtails,
        # mourning cloak, white admiral, tortoiseshell, polyphemus moth …).
        rank = keystone_rank_lepidoptera(pid)
        self.assertGreaterEqual(rank, 4, f"Aspen lepidoptera count: {rank}")

    def test_pussy_willow_supports_yellow_warbler_nesting(self):
        pid = _pid("Pussy Willow")
        self.assertIsNotNone(pid)
        rows = fauna_for_plant(pid)
        yw = [r for r in rows
              if r.get("scientific_name") == "Setophaga petechia"
              and r.get("relationship") == "nesting"]
        self.assertEqual(len(yw), 1)

    # ── Aggregations used by the Habitat Value Score ───────────────────

    def test_lepidoptera_supported_by_single_milkweed_includes_monarch(self):
        pid = _pid("Showy Milkweed")
        supported = lepidoptera_supported_by_plants([pid])
        monarch = _fid("Danaus plexippus")
        self.assertIn(monarch, supported)

    def test_lepidoptera_supported_empty_input(self):
        self.assertEqual(lepidoptera_supported_by_plants([]), set())

    def test_lepidoptera_supported_union_grows_with_more_plants(self):
        aspen   = _pid("Trembling Aspen")
        willow  = _pid("Pussy Willow")
        milkweed = _pid("Showy Milkweed")
        a = lepidoptera_supported_by_plants([aspen])
        b = lepidoptera_supported_by_plants([aspen, willow])
        c = lepidoptera_supported_by_plants([aspen, willow, milkweed])
        # Adding plants can only grow (or keep) the supported set.
        self.assertGreaterEqual(len(b), len(a))
        self.assertGreaterEqual(len(c), len(b))
        # Milkweed should add Monarch specifically.
        self.assertIn(_fid("Danaus plexippus"), c)

    def test_fauna_supported_per_taxon(self):
        aspen = _pid("Trembling Aspen")
        leps = fauna_supported_by_plants([aspen], taxon="lepidoptera")
        birds = fauna_supported_by_plants([aspen], taxon="bird")
        # Aspen has many lepidoptera; should also have at least one bird link
        # (chickadee cover). The exact counts are dataset-defined; the
        # invariant is non-emptiness.
        self.assertGreater(len(leps), 0)
        self.assertGreater(len(birds), 0)


class TestFaunaExpansionV20(unittest.TestCase):
    """V1.46 (schema v20): the registry grew to ~2.5× with the first
    other_insect + mammal taxa, and search_plants gained fauna-support filters
    backed by the plant_fauna junction."""

    @classmethod
    def setUpClass(cls):
        init_db()
        cls.fauna = list_fauna()
        cls.by_sci = {f["scientific_name"]: f for f in cls.fauna}

    def test_expanded_count(self):
        # 35 -> ~89 (a 2-3x expansion).
        self.assertGreaterEqual(len(self.fauna), 80)

    def test_all_five_taxa_present(self):
        taxa = {f["taxon"] for f in self.fauna}
        self.assertSetEqual(
            taxa, {"lepidoptera", "bird", "bee", "other_insect", "mammal"})

    def test_new_taxa_have_records(self):
        # other_insect and mammal are brand new in this chunk.
        counts = {t: sum(1 for f in self.fauna if f["taxon"] == t)
                  for t in ("other_insect", "mammal")}
        self.assertGreaterEqual(counts["other_insect"], 5)
        self.assertGreaterEqual(counts["mammal"], 3)

    def test_introduced_species_marked_non_native(self):
        # The drone fly is introduced; it must not claim ab_native.
        drone = self.by_sci.get("Eristalis tenax")
        self.assertIsNotNone(drone)
        self.assertEqual(drone["ab_native"], 0)

    def test_host_for_fauna_filter(self):
        from src.db.plants import search_plants
        sphinx = self.by_sci.get("Pachysphinx modesta")  # Big Poplar Sphinx
        self.assertIsNotNone(sphinx)
        hosts = {p["common_name"]
                 for p in search_plants(host_for_fauna_id=sphinx["id"])}
        self.assertTrue(hosts, "expected larval-host plants for the sphinx")
        self.assertTrue(hosts & {"Balsam Poplar", "Trembling Aspen",
                                 "Pussy Willow"})

    def test_supports_fauna_superset_of_host(self):
        from src.db.plants import search_plants
        sphinx = self.by_sci.get("Pachysphinx modesta")
        host = {p["common_name"]
                for p in search_plants(host_for_fauna_id=sphinx["id"])}
        any_rel = {p["common_name"]
                   for p in search_plants(supports_fauna_id=sphinx["id"])}
        self.assertTrue(host.issubset(any_rel))

    def test_supports_specialist_filter(self):
        from src.db.plants import search_plants
        sp = search_plants(supports_specialist=True)
        allp = search_plants()
        self.assertLess(len(sp), len(allp))         # a genuine subset
        self.assertTrue(sp, "seed data includes specialist relationships")
        for p in sp[:5]:                            # each really has one
            rels = fauna_for_plant(p["id"])
            self.assertTrue(any(r.get("specificity") == "specialist"
                                for r in rels))

    def test_allowed_filters_include_fauna(self):
        import src.llm_design as llm
        for k in ("host_for_fauna_id", "supports_fauna_id",
                  "supports_specialist"):
            self.assertIn(k, llm._ALLOWED_FILTERS)

    def test_fauna_digest_builds_and_reaches_brief(self):
        import src.llm_design as llm
        digest = llm._fauna_digest()
        self.assertTrue(digest)
        msgs = llm._build_messages(
            "x", {"community_names": [], "structure_ids": [],
                  "site": {}, "fauna_note": digest})
        self.assertIn("NATIVE FAUNA", msgs[0]["content"])


if __name__ == "__main__":
    unittest.main()

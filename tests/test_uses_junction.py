"""
tests/test_uses_junction.py

Verifies the schema v13 / V1.31 migration of the comma-delimited
``plants.permaculture_uses`` blob into the normalized ``uses`` lookup +
``plant_uses`` junction tables.

Each test runs against a fresh temp DB so we never touch the real user data.
"""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Redirect the DB to a temp directory before importing anything that opens it.
_TMP_DIR = tempfile.mkdtemp(prefix="permadesign_uses_test_")

import src.db.plants as _plants_mod  # noqa: E402

_plants_mod._DATA_DIR = _TMP_DIR
_plants_mod._DB_PATH  = os.path.join(_TMP_DIR, "permadesign_test.db")

from src.db.plants import (  # noqa: E402
    init_db,
    get_connection,
    get_plant,
    get_all_plants,
    get_plant_uses,
    plants_with_use,
    plant_uses_for_ids,
    search_plants,
    _USE_DEFINITIONS,
)


class TestUsesJunction(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        init_db()

    # ── Lookup table ────────────────────────────────────────────────────

    def test_uses_lookup_populated(self):
        conn = get_connection()
        try:
            n = conn.execute("SELECT COUNT(*) FROM uses").fetchone()[0]
        finally:
            conn.close()
        # Should at least equal the number of canonical definitions.
        self.assertGreaterEqual(n, len(_USE_DEFINITIONS))

    def test_uses_lookup_has_canonical_keys(self):
        conn = get_connection()
        try:
            keys = {r[0] for r in conn.execute("SELECT key FROM uses").fetchall()}
        finally:
            conn.close()
        # Sample a handful of the highest-stakes ecological tags.
        for key in ("keystone_species", "host_plant", "bird_food",
                    "pollinator", "nitrogen_fixer"):
            self.assertIn(key, keys, f"Missing canonical use key: {key}")

    # ── Junction population ─────────────────────────────────────────────

    def test_plant_uses_populated_from_seed(self):
        conn = get_connection()
        try:
            n = conn.execute("SELECT COUNT(*) FROM plant_uses").fetchone()[0]
        finally:
            conn.close()
        # Conservative lower bound: at least one tag per plant on average.
        self.assertGreater(n, 400)

    def test_plant_uses_matches_seed_json(self):
        """For every seeded plant, the junction tag set must match the canonical
        tokens in the source JSON ``permaculture_uses`` field. The denormalized
        DB column was dropped in schema v37, so the JSON file is now the seed
        source the junction is populated from — this is the safety-net parity
        invariant."""
        import json
        project_root = os.path.dirname(
            os.path.dirname(os.path.abspath(__file__))
        )
        name_to_tokens: dict[str, set] = {}
        for fname in ("plants_master.json", "garden_plants.json"):
            with open(os.path.join(project_root, "data", fname),
                      encoding="utf-8") as f:
                for rec in json.load(f):
                    raw = rec.get("permaculture_uses") or ""
                    if isinstance(raw, list):
                        raw = ",".join(raw)
                    name_to_tokens[(rec.get("common_name") or "").lower()] = {
                        t.strip() for t in raw.split(",") if t.strip()
                    }
        conn = get_connection()
        try:
            uses_keys = {
                r[0] for r in conn.execute("SELECT key FROM uses").fetchall()
            }
            rows = conn.execute(
                "SELECT id, common_name FROM plants ORDER BY id LIMIT 80"
            ).fetchall()
        finally:
            conn.close()
        checked = 0
        for pid, name in rows:
            tokens = name_to_tokens.get((name or "").lower())
            if tokens is None:
                continue  # inserted by another test module, not from seed JSON
            json_canonical = tokens & uses_keys
            junction = set(get_plant_uses(pid))
            self.assertEqual(
                json_canonical, junction,
                f"plant_id={pid} {name!r}: json={json_canonical} "
                f"junction={junction}",
            )
            checked += 1
        self.assertGreater(checked, 0, "no JSON-seeded plants found to compare")

    # ── Query helpers ───────────────────────────────────────────────────

    def test_plants_with_use_keystone_is_non_empty(self):
        ids = plants_with_use("keystone_species")
        self.assertGreater(len(ids), 0)

    def test_plant_uses_for_ids_bulk(self):
        # Pick plants that we know have uses (real seeded natives, not the
        # bare dummy plants other test modules insert).
        conn = get_connection()
        try:
            ids = [r[0] for r in conn.execute(
                "SELECT DISTINCT pu.plant_id FROM plant_uses pu LIMIT 5"
            ).fetchall()]
        finally:
            conn.close()
        self.assertGreater(len(ids), 0)
        bulk = plant_uses_for_ids(ids)
        # Contract: returned keys are a subset of the input ids, and every
        # plant we queried (all of which have uses) must appear with a
        # non-empty set.
        self.assertLessEqual(set(bulk.keys()), set(ids))
        for pid in ids:
            self.assertIn(pid, bulk)
            self.assertGreater(len(bulk[pid]), 0)

    # ── search_plants() — filters now go through the junction ────────────

    def test_search_keystone_only_uses_junction(self):
        results = search_plants(keystone_only=True)
        keystone_ids = plants_with_use("keystone_species")
        result_ids = {r["id"] for r in results}
        self.assertEqual(result_ids, keystone_ids)

    def test_search_host_plant_only_uses_junction(self):
        """The host_plant filter must yield exactly the junction's tagged set."""
        new_results = {r["id"] for r in search_plants(host_plant_only=True)}
        self.assertEqual(new_results, plants_with_use("host_plant"))

    def test_search_bird_food_uses_junction(self):
        new_results = {r["id"] for r in search_plants(bird_food_only=True)}
        self.assertEqual(new_results, plants_with_use("bird_food"))

    # ── schema v37: column dropped, blob synthesized on read ─────────────

    def test_permaculture_uses_column_dropped(self):
        conn = get_connection()
        try:
            cols = {
                r[1] for r in conn.execute(
                    "PRAGMA table_info(plants)").fetchall()
            }
        finally:
            conn.close()
        self.assertNotIn("permaculture_uses", cols)

    def test_get_plant_synthesizes_uses_from_junction(self):
        conn = get_connection()
        try:
            pid = conn.execute(
                "SELECT plant_id FROM plant_uses LIMIT 1").fetchone()[0]
        finally:
            conn.close()
        plant = get_plant(pid)
        self.assertIn("permaculture_uses", plant)
        derived = {t for t in plant["permaculture_uses"].split(",") if t}
        self.assertEqual(derived, set(get_plant_uses(pid)))
        self.assertGreater(len(derived), 0)

    def test_get_all_plants_synthesizes_uses(self):
        with_uses = [p for p in get_all_plants()
                     if (p.get("permaculture_uses") or "")]
        self.assertGreater(len(with_uses), 0)
        sample = with_uses[0]
        derived = {t for t in sample["permaculture_uses"].split(",") if t}
        self.assertEqual(derived, set(get_plant_uses(sample["id"])))

    def test_keyword_search_matches_use_tag_via_junction(self):
        """A keyword equal to a use key resolves through the EXISTS-on-junction
        clause, so every plant carrying that tag is returned."""
        by_keyword = {r["id"] for r in search_plants(query="nitrogen_fixer")}
        by_tag = plants_with_use("nitrogen_fixer")
        self.assertGreater(len(by_tag), 0)
        self.assertTrue(by_tag.issubset(by_keyword))


class TestUsesVocabularyRefresh(unittest.TestCase):
    """V1.37 refresh of `_USE_DEFINITIONS`. Verifies the dropped /
    renamed / promoted tags are reflected in the seeded `uses` lookup
    table and (for the renames) that the existing JSON data files no
    longer carry the old keys."""

    @classmethod
    def setUpClass(cls):
        init_db()

    def _seeded_keys(self) -> set[str]:
        conn = get_connection()
        try:
            return {r[0] for r in conn.execute("SELECT key FROM uses").fetchall()}
        finally:
            conn.close()

    def test_dropped_tags_not_in_lookup(self):
        keys = self._seeded_keys()
        for dropped in ("biomass", "pest_deterrent",
                        "food_forest", "edible_landscape"):
            self.assertNotIn(dropped, keys,
                             f"Dropped tag {dropped!r} should not be in `uses`")

    def test_renamed_tags_use_new_keys(self):
        keys = self._seeded_keys()
        # New canonical names (V1.37 first pass)
        for new in ("riparian_filter", "canopy_layer"):
            self.assertIn(new, keys, f"Expected canonical tag {new!r}")
        # Old names no longer canonical
        for old in ("water_purification", "overstory"):
            self.assertNotIn(old, keys, f"Old tag {old!r} should be renamed")
        # V1.37 second pass: "Pioneer Species" reverted to
        # "Early Successional" — user feedback flagged the colonizer
        # framing of "pioneer". Key kept as the original
        # `early_successional`.
        self.assertIn("early_successional", keys)
        self.assertNotIn("pioneer_species", keys)

    def test_no_data_record_references_dropped_or_old_tags(self):
        """The migration script that ran in V1.37 must have cleaned up
        every record — if a tag here surfaces in any record, the data
        files and the lookup table will drift apart on next reseed."""
        import json, os
        forbidden = {
            "biomass", "pest_deterrent", "food_forest", "edible_landscape",
            "water_purification", "overstory", "pioneer_species",
        }
        project_root = os.path.dirname(
            os.path.dirname(os.path.abspath(__file__))
        )
        for fname in ("plants_master.json", "garden_plants.json"):
            path = os.path.join(project_root, "data", fname)
            with open(path, encoding="utf-8") as f:
                records = json.load(f)
            for r in records:
                tags = (r.get("permaculture_uses") or "").split(",")
                tags = {t.strip() for t in tags if t.strip()}
                overlap = tags & forbidden
                self.assertFalse(
                    overlap,
                    f"{fname}: {r.get('common_name')!r} still has "
                    f"forbidden tag(s) {overlap}",
                )


if __name__ == "__main__":
    unittest.main()

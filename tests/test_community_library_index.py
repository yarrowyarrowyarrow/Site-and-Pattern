"""
tests/test_community_library_index.py

Tests for the Plant Community Library's batched search/filter/sort backbone
(V2.13): polycultures.get_library_index / filter_library / sort_community_ids
/ facet_filter_choices. These replace the panel's old per-community query
storm, so the index must carry everything the list needs.
"""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Redirect the DB to a temp directory so tests never touch the real user DB.
_TMP_DIR = tempfile.mkdtemp(prefix="permadesign_test_")

import src.db.plants as _plants_mod

_plants_mod._DATA_DIR = _TMP_DIR
_plants_mod._DB_PATH = os.path.join(_TMP_DIR, "permadesign_test.db")

from src.db import polycultures
from src.db.plants import init_db, get_connection


def _add_plant(conn, name, sci="", ptype="wildflower", sun="full_sun",
               water="low", native=1, eco=""):
    cur = conn.execute(
        "INSERT INTO plants (common_name, scientific_name, plant_type, "
        "sun_requirement, water_needs, native_to_alberta, ab_ecoregion) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (name, sci, ptype, sun, water, native, eco),
    )
    conn.commit()
    return cur.lastrowid


def _add_fauna(conn, name="Test Bee"):
    cur = conn.execute(
        "INSERT INTO fauna (scientific_name, common_name, taxon) "
        "VALUES (?, ?, 'bee')",
        (f"Testus {name.lower().replace(' ', '_')}", name),
    )
    conn.commit()
    return cur.lastrowid


def _link_fauna(conn, plant_id, fauna_id, rel="nectar"):
    conn.execute(
        "INSERT INTO plant_fauna (plant_id, fauna_id, relationship) "
        "VALUES (?, ?, ?)",
        (plant_id, fauna_id, rel),
    )
    conn.commit()


class TestLibraryIndex(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        init_db()

    def setUp(self):
        conn = get_connection()
        for table in ("polyculture_members", "polycultures", "plant_fauna",
                      "fauna", "plant_uses", "plants"):
            conn.execute(f"DELETE FROM {table}")
        conn.commit()

        # Two top-level communities + one variation under the first.
        self.aster = _add_plant(conn, "Smooth Aster", "Symphyotrichum laeve",
                                sun="full_sun", water="low", native=1,
                                eco="aspen_parkland")
        self.fern = _add_plant(conn, "Ostrich Fern", "Matteuccia struthiopteris",
                               ptype="fern", sun="full_shade", water="high",
                               native=1, eco="boreal_mixedwood")
        self.hosta = _add_plant(conn, "Hosta", "Hosta sieboldiana",
                                sun="full_shade", water="medium", native=0)
        conn.close()

        self.sunny = polycultures.create_polyculture(
            "Sunny Meadow", "Dry prairie patch", None)
        polycultures.add_polyculture_member(self.sunny, self.aster,
                                            "herbaceous", 0, 0)

        self.shady = polycultures.create_polyculture(
            "Shade Corner", "Moist woodland floor", None)
        polycultures.add_polyculture_member(self.shady, self.fern,
                                            "herbaceous", 0, 0)
        polycultures.add_polyculture_member(self.shady, self.hosta,
                                            "groundcover", 1, 0)

        # The variation shares the parent's member so its facets match the
        # parent's — facet-filter tests stay crisp (the parent can't sneak
        # through a facet filter via a divergent child).
        self.variation = polycultures.create_polyculture(
            "Sunny Meadow — Moist", "Wetter variation", None,
            parent_id=self.sunny)
        polycultures.add_polyculture_member(self.variation, self.aster,
                                            "herbaceous", 0, 0)

    # ── get_library_index ────────────────────────────────────────────────

    def test_index_covers_all_communities(self):
        idx = polycultures.get_library_index()
        self.assertEqual(set(idx), {self.sunny, self.shady, self.variation})

    def test_index_children_and_parent_links(self):
        idx = polycultures.get_library_index()
        self.assertEqual(idx[self.sunny]["children"], [self.variation])
        self.assertEqual(idx[self.variation]["parent_id"], self.sunny)
        self.assertEqual(idx[self.shady]["children"], [])

    def test_index_counts_and_native_pct(self):
        idx = polycultures.get_library_index()
        self.assertEqual(idx[self.shady]["member_count"], 2)
        self.assertEqual(idx[self.shady]["native_pct"], 50)   # fern yes, hosta no
        self.assertEqual(idx[self.sunny]["native_pct"], 100)

    def test_index_fauna_count(self):
        conn = get_connection()
        bee = _add_fauna(conn, "Bumble Bee")
        moth = _add_fauna(conn, "Police Car Moth")
        _link_fauna(conn, self.aster, bee)
        _link_fauna(conn, self.aster, moth, rel="larval_host")
        conn.close()
        idx = polycultures.get_library_index()
        self.assertEqual(idx[self.sunny]["fauna_count"], 2)
        self.assertEqual(idx[self.shady]["fauna_count"], 0)

    def test_index_search_blob_has_scientific_names(self):
        idx = polycultures.get_library_index()
        self.assertIn("matteuccia", idx[self.shady]["search_blob"])
        self.assertIn("woodland", idx[self.shady]["search_blob"])

    def test_index_facets_match_get_community_facets(self):
        idx = polycultures.get_library_index()
        for cid, facets in polycultures.get_community_facets().items():
            self.assertEqual(idx[cid]["facets"], facets)

    def test_empty_community_gets_neutral_facets(self):
        empty = polycultures.create_polyculture("Empty", "", None)
        idx = polycultures.get_library_index()
        self.assertEqual(idx[empty]["member_count"], 0)
        self.assertEqual(idx[empty]["facets"]["function"], ["Generalist"])

    # ── filter_library ───────────────────────────────────────────────────

    def test_filter_no_criteria_returns_all_top_level(self):
        idx = polycultures.get_library_index()
        out = polycultures.filter_library(idx)
        self.assertEqual(set(out), {self.sunny, self.shady})
        self.assertTrue(out[self.sunny]["self"])

    def test_filter_search_matches_scientific_name(self):
        idx = polycultures.get_library_index()
        out = polycultures.filter_library(idx, search="Symphyotrichum")
        self.assertEqual(set(out), {self.sunny})

    def test_filter_search_via_variation_only(self):
        # "Wetter" appears only in the variation's description.
        idx = polycultures.get_library_index()
        out = polycultures.filter_library(idx, search="wetter")
        self.assertEqual(set(out), {self.sunny})
        self.assertFalse(out[self.sunny]["self"])
        self.assertEqual(out[self.sunny]["children"], [self.variation])

    def test_filter_single_facet(self):
        idx = polycultures.get_library_index()
        out = polycultures.filter_library(idx, facets={"sun": ["Shade"]})
        self.assertIn(self.shady, out)
        self.assertNotIn(self.sunny, out)

    def test_filter_facets_and_across_or_within(self):
        idx = polycultures.get_library_index()
        # OR within a facet: either sun value passes both communities.
        out = polycultures.filter_library(
            idx, facets={"sun": ["Full Sun", "Shade"]})
        self.assertEqual(set(out), {self.sunny, self.shady})
        # AND across facets: sunny is Full Sun but not Wet → only shady.
        out = polycultures.filter_library(
            idx, facets={"sun": ["Full Sun", "Shade"], "moisture": ["Wet"]})
        self.assertEqual(set(out), {self.shady})

    def test_filter_search_and_facets_combine(self):
        idx = polycultures.get_library_index()
        out = polycultures.filter_library(
            idx, search="patch", facets={"sun": ["Full Sun"]})
        self.assertEqual(set(out), {self.sunny})
        out = polycultures.filter_library(
            idx, search="patch", facets={"sun": ["Shade"]})
        self.assertEqual(out, {})

    # ── sort_community_ids ───────────────────────────────────────────────

    def test_sort_name_default(self):
        idx = polycultures.get_library_index()
        ids = [self.sunny, self.shady]
        self.assertEqual(polycultures.sort_community_ids(idx, ids),
                         [self.shady, self.sunny])

    def test_sort_members_desc(self):
        idx = polycultures.get_library_index()
        ids = [self.sunny, self.shady]
        self.assertEqual(
            polycultures.sort_community_ids(idx, ids, key="members"),
            [self.shady, self.sunny])

    def test_sort_wildlife_desc_with_name_tiebreak(self):
        conn = get_connection()
        bee = _add_fauna(conn)
        _link_fauna(conn, self.aster, bee)
        conn.close()
        idx = polycultures.get_library_index()
        ids = [self.shady, self.sunny]
        self.assertEqual(
            polycultures.sort_community_ids(idx, ids, key="wildlife"),
            [self.sunny, self.shady])

    def test_sort_native_desc(self):
        idx = polycultures.get_library_index()
        ids = [self.shady, self.sunny]
        self.assertEqual(
            polycultures.sort_community_ids(idx, ids, key="native"),
            [self.sunny, self.shady])

    def test_sort_modified_newest_first(self):
        conn = get_connection()
        conn.execute("UPDATE polycultures SET modified='2026-01-01 00:00:00'")
        conn.execute(
            "UPDATE polycultures SET modified='2026-06-01 00:00:00' WHERE id=?",
            (self.shady,))
        conn.commit()
        conn.close()
        idx = polycultures.get_library_index()
        ids = [self.sunny, self.shady]
        self.assertEqual(
            polycultures.sort_community_ids(idx, ids, key="modified"),
            [self.shady, self.sunny])

    def test_sort_unknown_key_falls_back_to_name(self):
        idx = polycultures.get_library_index()
        ids = [self.sunny, self.shady]
        self.assertEqual(
            polycultures.sort_community_ids(idx, ids, key="nonsense"),
            [self.shady, self.sunny])

    # ── facet_filter_choices ─────────────────────────────────────────────

    def test_choices_cover_derived_values(self):
        """Every categorical facet value the reducers can emit (bar the
        catch-alls) must be offered as a filter choice."""
        choices = polycultures.facet_filter_choices()
        idx = polycultures.get_library_index()
        catch_alls = {"Unsorted", "Mixed", "Unknown", "Other"}
        for entry in idx.values():
            for facet, val in entry["facets"].items():
                vals = val if isinstance(val, list) else [val]
                for v in vals:
                    if v in catch_alls:
                        continue
                    self.assertIn(v, choices[facet],
                                  f"{facet} value {v!r} missing from choices")

    def test_ecoregion_labels_alias(self):
        self.assertEqual(
            polycultures.ECOREGION_LABELS["aspen_parkland"], "Aspen Parkland")


if __name__ == "__main__":
    unittest.main()

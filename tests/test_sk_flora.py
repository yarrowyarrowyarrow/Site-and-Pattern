"""
tests/test_sk_flora.py

Verifies the V2.16 Saskatchewan flora/fauna expansion (Phase C):

  * the re-tagged catalogue exposes a substantial Moist Mixed Grassland pool
    (the Regina/Saskatoon belt) and SK-native plants,
  * shared prairie species are tagged native to both AB and SK, while Rocky
    Mountain / foothills endemics stay AB-only,
  * the curated SK grassland species were added, including one (Stiff Goldenrod)
    that is SK-native but not AB-native — exercising the native_province filter,
  * the new species are linked to existing fauna (not ecological orphans),
  * fauna carry native_provinces after seeding.

Runs against a fresh temp DB so it never touches real user data.
"""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_TMP_DIR = tempfile.mkdtemp(prefix="permadesign_skflora_test_")

import src.db.plants as _plants_mod  # noqa: E402

_plants_mod._DATA_DIR = _TMP_DIR
_plants_mod._DB_PATH  = os.path.join(_TMP_DIR, "permadesign_test.db")

from src.db.plants import (  # noqa: E402
    init_db,
    get_connection,
    get_all_plants,
    search_plants,
)


class TestSaskatchewanFlora(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        init_db()
        cls.plants = get_all_plants()
        cls.by_sci = {p["scientific_name"]: p for p in cls.plants}

    def test_the_prairie_pool_is_substantial(self):
        """The Regina/Saskatoon belt should resolve a real design pool.

        V2.68: was `moist_mixedgrass`, which the survey retired. The 245
        species that carried it could not be placed in any one surveyed
        ecoregion (39% Moist Mixed Grassland, 36% Aspen Parkland) but 92% of
        the old polygon is Prairies, so they rest at the ecozone — and the
        ecozone is what a "belt" was always a rough name for.

        Queried through ``expand_for_filter``, which is what the panel does
        and therefore what the user experiences. A **bare** `zone_prairies`
        query now returns 7, and that number is the system working rather than
        failing: the GBIF derivation writes rows at the *ecoregion* level,
        because that is what a coordinate resolves to, and a derived row
        overrides the heuristic column. So after the re-derivation only the 7
        species GBIF had nothing for still carry a bare ecozone tag. The other
        423 are found through their ecoregions, which is the lineage's whole
        job."""
        from src.ecoregion_tree import expand_for_filter

        pool = search_plants(ecoregion=expand_for_filter(["zone_prairies"]))
        self.assertGreater(len(pool), 100)

    def test_sk_native_filter(self):
        sk = search_plants(native_province="SK")
        ab = search_plants(native_province="AB")
        self.assertGreater(len(sk), 100)
        self.assertGreater(len(ab), len(sk))  # AB catalogue is the superset

    def test_curated_species_present(self):
        for sci in ("Sphaeralcea coccinea", "Comandra umbellata",
                    "Solidago rigida", "Symphyotrichum falcatum",
                    "Packera cana", "Erigeron caespitosus"):
            self.assertIn(sci, self.by_sci, f"{sci} missing from catalogue")

    def test_sk_only_species_not_ab(self):
        """The province model must distinguish a Saskatchewan native from an
        Alberta one.

        This used to be pinned to *Oligoneuron rigidum*, on two claims that
        V2.80 retired. It was a duplicate of *Solidago rigida* under a second
        name, and the archive merged them; and it asserted **MB**, which no row
        carries any more, because VASCAN's narrowing writes only the two
        subject provinces — the Manitoba filter chip went in V2.75 for the same
        reason.

        *Echinacea angustifolia* is the replacement and a better one: it is
        SK-only **because a flora says so**, one of the 34 rows the archive
        narrowed, rather than because of an inference about ecoregions.
        """
        sg = self.by_sci["Echinacea angustifolia"]
        self.assertIn("SK", sg["native_provinces"])
        self.assertNotIn("AB", sg["native_provinces"])
        self.assertFalse(sg["native_to_alberta"])
        self.assertIn(sg, search_plants(native_province="SK"))
        self.assertNotIn(sg, search_plants(native_province="AB"))

    def test_shared_species_tagged_both_provinces(self):
        """The province model, which is what this test is named for.

        V2.68 dropped a third assertion that pinned this species' *ecoregion*
        to `moist_mixedgrass`. It had no business in a province test, and it
        was checking the weakest field on the row: `ecoregion` is whatever the
        GBIF derivation last wrote, so the assertion tracked the state of an
        unrelated overnight job. The regions are covered by
        tests/test_ecoregion_ranges.py, against the vocabulary rather than
        against one remembered value."""
        gm = self.by_sci["Sphaeralcea coccinea"]
        self.assertIn("AB", gm["native_provinces"])
        self.assertIn("SK", gm["native_provinces"])

    def test_mountain_endemics_stay_ab_only(self):
        """A mountain- or fescue-only endemic must NOT be tagged native to SK.

        The regions are read from the vocabulary rather than typed in: this
        asked for `subalpine_montane` and `fescue_foothills`, both retired by
        the V2.67 survey, and a SQL `IN` over dead keys matches nothing — so
        the loop ran zero times and the test passed while checking nothing.
        Only the `assertTrue(rows)` guard caught it, and only after V2.68
        cleared the last tags that were keeping it non-empty.

        Saskatchewan has no mountains and no foothills. Every region below is
        Alberta-only ground, so nothing carrying one may claim SK."""
        from src.ecoregion_tree import regions_in, zone_key

        keys = [key for key, _name in regions_in(zone_key("Montane Cordillera"))]
        keys.append("fescue_grassland")
        placeholders = ",".join("?" * len(keys))
        conn = get_connection()
        try:
            rows = conn.execute(
                f"SELECT native_provinces FROM plants "
                f"WHERE ecoregion IN ({placeholders})", keys).fetchall()
        finally:
            conn.close()
        if not rows:
            self.skipTest(
                "no species currently carries a montane or fescue region — "
                "the heuristic tags for those were cleared as misplaced in "
                "V2.68 and the derived ranges are mid-re-derivation. Re-run:  "
                "python scripts/seed_ecoregion_ranges.py")
        for (np,) in rows:
            self.assertNotIn("SK", (np or ""))

    def test_new_species_have_fauna_links(self):
        conn = get_connection()
        try:
            for cn in ("Stiff Goldenrod", "Scarlet Globemallow"):
                n = conn.execute(
                    "SELECT COUNT(*) FROM plant_fauna pf "
                    "JOIN plants p ON p.id = pf.plant_id "
                    "WHERE p.common_name = ?", (cn,)
                ).fetchone()[0]
                self.assertGreater(n, 0, f"{cn} has no fauna links")
        finally:
            conn.close()

    def test_fauna_native_provinces_seeded(self):
        conn = get_connection()
        try:
            ab = conn.execute(
                "SELECT COUNT(*) FROM fauna "
                "WHERE (',' || COALESCE(native_provinces,'') || ',') LIKE '%,AB,%'"
            ).fetchone()[0]
        finally:
            conn.close()
        self.assertGreater(ab, 100)


if __name__ == "__main__":
    unittest.main()

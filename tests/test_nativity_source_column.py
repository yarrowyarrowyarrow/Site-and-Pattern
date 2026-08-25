"""
The province source has to survive the database (schema v79, V2.80).

The apply that writes `native_provinces_source` into the seed JSON is only half
a change, and the missing half fails **silently**: a seed field with no column
behind it is dropped on load, `nativity.provenance` sees nothing, and all 430
published pages go on saying the claim is inferred. Nothing raises. The JSON
diff looks right, the report says 414 rows stamped, and the website is
unchanged.

That is the shape of this repo's most expensive class of bug -- "I edited the
seed JSON but nothing changed" is entry 8 in the legacy-lessons ledger -- so it
gets a test that goes all the way through a real reseed rather than one that
checks the JSON.
"""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Redirect the DB before importing anything that opens it.
_TMP_DIR = tempfile.mkdtemp(prefix="siteandpattern_nativity_src_")

import src.db.plants as _plants_mod                   # noqa: E402

_plants_mod._DATA_DIR = _TMP_DIR
_plants_mod._DB_PATH = os.path.join(_TMP_DIR, "permadesign_test.db")

from src.db.plants import (                           # noqa: E402
    _SCHEMA_VERSION, get_all_plants, get_connection, init_db,
)
from scripts.ingest_flora_nativity import _ab_flag as _ab  # noqa: E402
from src.nativity import SOURCE_FIELD, provenance     # noqa: E402


def _by_name() -> dict:
    return {r.get("scientific_name"): r for r in get_all_plants()}


class TestTheColumnExistsAndIsSeeded(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        init_db()
        cls.rows = _by_name()

    def test_the_column_is_there(self):
        with get_connection() as conn:
            cols = {r[1] for r in conn.execute("PRAGMA table_info(plants)")}
        self.assertIn("native_provinces_source", cols)

    def test_the_schema_version_was_bumped_or_nobody_reseeds(self):
        """Without a bump an existing install never re-reads the seed files, so
        the column arrives empty and stays empty forever."""
        self.assertGreaterEqual(_SCHEMA_VERSION, 79)

    def test_a_sourced_species_arrives_sourced(self):
        self.assertEqual(self.rows["Amelanchier alnifolia"][SOURCE_FIELD],
                         "flora")

    def test_the_page_stops_calling_a_sourced_claim_inferred(self):
        """The whole point. `provenance` reads the row the DB returns, not the
        JSON, and this is the assertion that would have caught a seed field
        with no column behind it."""
        got = provenance(self.rows["Amelanchier alnifolia"])
        self.assertFalse(got["inferred"])
        self.assertEqual(got["note"], "")

    def test_an_unsourced_species_still_names_its_heuristic(self):
        """~20 species VASCAN could not settle. Blank is the honest answer and
        the derived note is still the right thing to show."""
        got = provenance(self.rows["Urtica dioica"])
        self.assertTrue(got["inferred"])
        self.assertIn("ecoregions that continue across", got["note"])


class TestTheNarrowingReachedTheDatabase(unittest.TestCase):
    """The 34 species where a published flora disagreed with an inference."""

    @classmethod
    def setUpClass(cls):
        init_db()
        cls.rows = _by_name()

    def test_a_narrowed_species_lost_the_province(self):
        self.assertEqual(self.rows["Yucca glauca"]["native_provinces"], "AB")
        self.assertEqual(
            self.rows["Echinacea angustifolia"]["native_provinces"], "SK")

    def test_the_alberta_flag_agrees_with_the_province_list(self):
        """Two columns saying different things about one plant, where the one
        the Habitat Value Score reads is the stale one. Checked across the
        whole catalogue, not just the seven that changed."""
        wrong = [
            name for name, row in self.rows.items()
            if (row.get("native_provinces") or "").strip()
            and _ab(row)
            != ("AB" in (row.get("native_provinces") or "").split(","))
        ]
        self.assertEqual(wrong, [])


if __name__ == "__main__":
    unittest.main()

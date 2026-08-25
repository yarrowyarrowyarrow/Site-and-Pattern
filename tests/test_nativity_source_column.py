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



class TestItSurvivesEveryLayerOutToThePage(unittest.TestCase):
    """Where this actually broke, after the column and the reseed were both
    verified working.

    The seed file had the field, the database had the field, and a test in the
    class above proved it survived a real reseed -- and every one of the 430
    built pages still read *"not checked against a published flora"*. The
    website does not render the database row: it renders
    `plant_directory.species_entry`, which builds an explicit dict, and the
    dict never copied the key across.

    `src/nativity.py` already warns about the sibling of this trap for the
    `native` key itself. Testing one layer short of the page is what let it
    through, so these go to the page.
    """

    def _entry(self, **over):
        from src.plant_directory import species_entry
        row = {"common_name": "Test Plant", "scientific_name": "Testus sp.",
               "native_provinces": "SK", "native_to_alberta": 0}
        row.update(over)
        return species_entry(
            1, get_plant=lambda _i: row, fauna_for_plant=lambda _i: [],
            neighbourhood=lambda *a, **k: {}, ranges_for=lambda *a, **k: [],
            calendar_for=lambda *a, **k: {}, photos_for=lambda *a, **k: [])

    def test_the_directory_entry_carries_the_source(self):
        self.assertEqual(self._entry(**{SOURCE_FIELD: "flora"})[SOURCE_FIELD],
                         "flora")

    def test_a_sourced_entry_gets_no_note(self):
        self.assertEqual(provenance(self._entry(**{SOURCE_FIELD: "flora"})),
                         {"note": "", "inferred": False})

    def test_an_unsourced_entry_still_gets_one(self):
        self.assertTrue(provenance(self._entry())["note"])

    def test_the_rendered_cell_stops_saying_not_checked(self):
        """The actual published string. This is the assertion that failed
        against a database, a reseed and a seed file that were all correct."""
        from src.static_site_species import _native
        cell = _native(self._entry(**{SOURCE_FIELD: "flora"}))
        self.assertIn("SK", cell)
        self.assertNotIn("not checked", cell)
        self.assertNotIn("ecoregions", cell)

    def test_the_rendered_cell_withholds_an_unsourced_claim(self):
        """V2.80 stopped annotating the inference and started refusing to
        publish it: *"I do not want any inference being made... only facts
        backed by data."* The province list must not reach the page."""
        from src.static_site_species import _native
        cell = _native(self._entry())
        self.assertIn("Not established", cell)
        self.assertNotIn(">SK<", cell)

    def test_the_inspect_card_carries_it_too(self):
        """`scene_dossier._plant_entry` is the same shape for the 3D card and
        had the same gap."""
        from src.scene_dossier import _NATIVITY_SOURCE
        self.assertEqual(_NATIVITY_SOURCE, SOURCE_FIELD)


if __name__ == "__main__":
    unittest.main()

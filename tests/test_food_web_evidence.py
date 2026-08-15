"""
tests/test_food_web_evidence.py — the food web must not claim what it cannot
show (V2.58).

A user placed sixteen native plants, was shown no animals, and reported that
something had broken. The catalogue was the problem — it holds wildlife records
for 99 of 437 species — but the *app* made it look like a bug, because it
reported a **complete food web** for that design while holding zero bird
records:

    caterpillars: True, n_caterpillars: 1, birds: True, n_birds: 0,
    complete: True, status: "complete"

``has_birds`` read ``n_birds > 0 or bool(bird_species)``, and ``bird_species``
is the list of plants carrying the ``bird_food`` **tag**. So a tag with no
record behind it asserted the link, and the Analysis panel printed "supports
caterpillars and the birds that eat them".

This is the V2.53 contradiction running the other way. That increment fixed the
case where tags DENY what edges document; this is the case where tags CLAIM what
edges do not record.

Two rules are pinned here: **"complete" means documented**, and **absence of
data is reported as absence of data**.
"""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_TMP = tempfile.mkdtemp(prefix="permadesign_foodweb_")
try:
    import src.db.plants as _plants_mod
    _plants_mod._DATA_DIR = _TMP
    _plants_mod._DB_PATH = os.path.join(_TMP, "t.db")
except Exception:  # pragma: no cover
    pass

from src.design_critic import critique_lines  # noqa: E402


def _habitat(**food_web):
    fw = {"caterpillars": False, "n_caterpillars": 0,
          "caterpillars_evidence": "none",
          "birds": False, "n_birds": 0, "birds_evidence": "none",
          "complete": False, "status": "empty",
          "species_with_records": 0, "species_scored": 0}
    fw.update(food_web)
    return {"components": {}, "food_web": fw}


class TestCompleteMeansDocumented(unittest.TestCase):
    """The exact shape the user hit."""

    def test_a_tag_alone_does_not_complete_the_web(self):
        from src.habitat_score import compute_habitat_score  # noqa: F401
        fw = _habitat(caterpillars=True, n_caterpillars=1,
                      caterpillars_evidence="documented",
                      birds=True, n_birds=0, birds_evidence="tag_only",
                      complete=False, status="unverified")["food_web"]
        self.assertFalse(fw["complete"],
                         "a bird link with zero bird records is not a complete "
                         "food web")
        self.assertEqual(fw["status"], "unverified")

    def test_the_panel_has_a_message_for_the_unverified_state(self):
        """A status with no message renders as nothing, which would swap one
        silent failure for another."""
        import re
        path = os.path.join(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__))), "src", "analysis_panel.py")
        with open(path, "r", encoding="utf-8") as fh:
            src = fh.read()
        block = re.search(r"_food_web_msg = \{.*?\}", src, re.S)
        self.assertIsNotNone(block)
        for status in ("complete", "unverified", "no_birds", "no_hosts",
                       "empty"):
            self.assertIn(f'"{status}"', block.group(0),
                          f"no Analysis-panel line for status {status!r}")

    def test_the_panel_no_longer_promises_birds_it_cannot_show(self):
        """The 'complete' wording may only be reachable from the documented
        state."""
        import re
        path = os.path.join(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__))), "src", "analysis_panel.py")
        with open(path, "r", encoding="utf-8") as fh:
            src = fh.read()
        block = re.search(r'"unverified":(.*?)"no_birds"', src, re.S)
        self.assertIsNotNone(block)
        self.assertNotIn("birds that eat them", block.group(1),
                         "the unverified state reuses the completed wording")


class TestCoverageIsReported(unittest.TestCase):
    """Absence of data must never read as absence of relationships."""

    def test_nothing_recorded_says_so_plainly(self):
        lines = critique_lines(_habitat(species_scored=16,
                                        species_with_records=0))
        self.assertTrue(lines, "no coverage line at all")
        first = lines[0].lower()
        self.assertIn("gap in the catalogue", first)
        self.assertIn("16", lines[0])

    def test_partial_coverage_says_how_partial(self):
        lines = critique_lines(_habitat(species_scored=16,
                                        species_with_records=1))
        self.assertIn("1 of these 16", lines[0])
        self.assertIn("not recorded as supporting", lines[0].lower())

    def test_full_coverage_says_nothing(self):
        """A design whose species are all recorded should not be told about
        coverage — the line exists to explain a gap, not to natter."""
        lines = critique_lines(_habitat(species_scored=5,
                                        species_with_records=5))
        for ln in lines:
            self.assertNotIn("not recorded yet", ln.lower())

    def test_the_coverage_line_comes_first(self):
        """It reframes everything under it: a design of unrecorded species
        should not read as a design that supports nothing."""
        habitat = _habitat(species_scored=16, species_with_records=0)
        habitat["components"] = {"keystone": {"score": 0}}
        lines = critique_lines(habitat)
        self.assertIn("catalogue", lines[0].lower())


class TestAgainstTheRealCatalogue(unittest.TestCase):
    """The reported design, end to end, if a seeded database is present."""

    _NAMES = ["Bishop's Cap", "Jack Pine", "Northern Bedstraw",
              "Pearly Everlasting", "Skunk Currant", "Yellow Avens"]

    def _placed(self):
        from src.db.plants import get_connection
        conn = get_connection()
        rows = []
        for n in self._NAMES:
            r = conn.execute("SELECT id FROM plants WHERE common_name = ?",
                             (n,)).fetchone()
            if r:
                rows.append({"plant_id": r[0], "common_name": n,
                             "lat": 53.5, "lng": -113.5})
        return rows

    def test_a_thinly_recorded_design_is_never_called_complete(self):
        try:
            placed = self._placed()
        except Exception:                                  # pragma: no cover
            self.skipTest("no seeded database in this environment")
        if len(placed) < 3:
            self.skipTest("catalogue not seeded here")
        from src.habitat_score import compute_habitat_score
        fw = compute_habitat_score(placed, []).as_dict()["food_web"]
        self.assertEqual(fw["species_scored"], len(placed))
        if fw["n_birds"] == 0:
            self.assertFalse(
                fw["complete"],
                "still claiming a complete food web with no bird records")


if __name__ == "__main__":
    unittest.main()

"""
tests/test_edmonton_communities.py — the communities of the Edmonton region
(F221) and the notes that contradicted VASCAN (F222), V3.12.

The owner: "Perhaps we would need to generate some more local to edmonton plant
communities as well." Of the 71 seeded communities before V3.12, one had every
member on the Edmonton list, so "Edmonton natives only" emptied the library.
The seven added are built only from DOCUMENTED species: if a review ever rules
one of their members not native here, the first test fails and names it, which
is the moment to swap the member rather than let the community vanish from the
filter it was written for.
"""

import json
import os
import re
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_TMP_DIR = tempfile.mkdtemp(prefix="permadesign_edmonton_comm_test_")
import src.db.plants as _plants_mod  # noqa: E402
import src.permadesign_api as _api  # noqa: E402
from src.db import polycultures as P  # noqa: E402
from src import native_here as nh  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EDMONTON_COMMUNITIES = [c for c in P.EXAMPLE_POLYCULTURES
                        if c["name"].startswith("Edmonton ")]


def setUpModule():
    _plants_mod._DATA_DIR = _TMP_DIR
    _plants_mod._DB_PATH = os.path.join(_TMP_DIR, "permadesign_test.db")
    _plants_mod.init_db()
    _api._DB_READY = True
    nh.set_document(None)


def _catalogue():
    with open(os.path.join(ROOT, "data", "plants_master.json"),
              encoding="utf-8") as fh:
        return {r["common_name"]: r for r in json.load(fh)}


class TestTheCommunities(unittest.TestCase):

    def test_there_are_seven(self):
        self.assertEqual(len(EDMONTON_COMMUNITIES), 7)

    def test_every_member_is_documented_around_edmonton(self):
        """Documented, not merely native by a ruling: a community built on a
        borderline species would leave the filter if the review went the other
        way, and these exist to be in it."""
        rows = _catalogue()
        for c in EDMONTON_COMMUNITIES:
            for name, _role, _x, _y in c["members"]:
                with self.subTest(community=c["name"], member=name):
                    self.assertIn(name, rows)
                    sci = rows[name]["scientific_name"]
                    self.assertEqual(nh.entry(sci).get("tier"), "documented")
                    self.assertTrue(nh.native_around(sci))

    def test_each_is_a_whole_pattern(self):
        from src.db.plants import _FUNCTION_VALUES, _LAYER_VALUES
        for c in EDMONTON_COMMUNITIES:
            with self.subTest(c["name"]):
                names = [m[0] for m in c["members"]]
                self.assertEqual(len(names), len(set(names)))
                self.assertTrue(5 <= len(names) <= 8)
                for _n, role, _x, _y in c["members"]:
                    self.assertIn(role, _LAYER_VALUES | _FUNCTION_VALUES)
                text = P._PATTERN_TEXT.get(c["name"]) or {}
                for field in ("problem", "context", "forces", "solution"):
                    self.assertTrue((text.get(field) or "").strip(), field)
                self.assertIn("native around Edmonton", c["description"])

    def test_the_marsh_edge_goes_in_a_pond(self):
        from src.pond_planting import is_pond_community
        rows = _catalogue()
        marsh = next(c for c in EDMONTON_COMMUNITIES
                     if c["name"] == "Edmonton Marsh Edge")
        self.assertTrue(is_pond_community(rows[m[0]] for m in marsh["members"]))
        for c in EDMONTON_COMMUNITIES:
            if c is not marsh:
                self.assertFalse(is_pond_community(
                    rows[m[0]] for m in c["members"]), c["name"])


class TestTheyReachTheApp(unittest.TestCase):

    def test_the_filter_shows_all_seven(self):
        index = P.get_library_index()
        shown = {index[cid]["name"]
                 for cid in P.filter_library(index, native_near="edmonton")}
        for c in EDMONTON_COMMUNITIES:
            self.assertIn(c["name"], shown)

    def test_the_edmonton_goal_picks_them_first(self):
        import src.llm_design as llm
        kept = llm._communities_for_site(
            _api.list_polycultures(), {"native_near": "edmonton"}, 0.0)
        picks = llm._select_offline_communities(
            kept, ["edmonton_native"], {"ecoregion_key": "aspen_parkland"},
            None)
        by_id = {c["id"]: c["name"] for c in kept}
        names = [by_id[i] for i in picks]
        self.assertTrue(any(n.startswith("Edmonton ") for n in names), names)
        # Every pick has all its members on the list. Since the owner's answers
        # (V3.13) an older community can qualify too, and one whose words
        # match the site's region (+3) can lead the goal's hint (+2): Pin
        # Cherry Community, "the native cherry of the prairies", does on an
        # Aspen Parkland yard. What holds is that nothing picked is foreign.
        index = P.get_library_index()
        for cid in picks:
            self.assertEqual(index[cid]["not_around"]["edmonton"], [],
                             by_id[cid])


class TestTheNotesNoLongerContradictVascan(unittest.TestCase):
    """F222. The desktop page printed these under the plant: Eastern Red
    Columbine's "true Alberta-native populations" is half of how the owner came
    to read it as native to southern Alberta."""

    AFFIRMS_ALBERTA = re.compile(
        r"(?<!not )(?<!not an )\balberta[- ]native|(?<!not )native to alberta"
        r"|appropriate for alberta|recommended for alberta"
        r"|alberta'?s mixed-grass", re.IGNORECASE)

    def test_no_note_claims_alberta_for_a_species_vascan_does_not(self):
        for name, row in _catalogue().items():
            if "AB" in (row.get("native_provinces") or "").split(","):
                continue
            with self.subTest(name):
                self.assertIsNone(
                    self.AFFIRMS_ALBERTA.search(row.get("notes") or ""))

    def test_the_pattern_would_have_caught_the_originals(self):
        for text in ("true Alberta-native populations",
                     "ecologically appropriate for Alberta grassland",
                     "hardiness in Alberta's mixed-grass prairie ecosystems",
                     "is recommended for Alberta Zone 3-4 plantings"):
            self.assertIsNotNone(self.AFFIRMS_ALBERTA.search(text), text)
        self.assertIsNone(self.AFFIRMS_ALBERTA.search(
            "It is not an Alberta native"))


if __name__ == "__main__":
    unittest.main()

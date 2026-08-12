"""
tests/test_flower_colour.py — the colour filter (V2.47).

``flower_color`` has held a hex since schema v31 and nothing could filter on it.
What these hold down:

  * **the bucket boundaries**, asserted against the *shipped seed data* rather
    than against invented hexes — a reseed that recolours a species fails here
    instead of silently re-filing it under a different colour;
  * **the grasses stay out of "yellow."** All 79 are wind-pollinated and their
    `#cbbd80` is the absence of a showy flower. This is the assertion the whole
    module exists for;
  * **an unrecorded colour matches nothing**, the rule ``_month_filter`` already
    applies to bloom windows (P9);
  * **the filter reaches the query layer** — a facet that names a parameter
    nobody reads is the exact shape of the V2.37 dead-control bugs.
"""

import json
import os
import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_TMP_DIR = tempfile.mkdtemp(prefix="permadesign_colour_test_")

import src.db.plants as _plants_mod  # noqa: E402

_plants_mod._DATA_DIR = _TMP_DIR
_plants_mod._DB_PATH = os.path.join(_TMP_DIR, "permadesign_test.db")

from src.db.plants import init_db, search_plants          # noqa: E402
from src.flower_colour import (                           # noqa: E402
    COLOUR_KEYS, COLOUR_LABELS, WIND_POLLINATED_TYPES, bucket_counts, classify,
    classify_hex, matches,
)

_ROOT = pathlib.Path(__file__).resolve().parent.parent


def _seed_rows() -> list:
    return json.loads((_ROOT / "data" / "plants_master.json")
                      .read_text(encoding="utf-8"))


class TestTheClassifierAgainstTheShippedData(unittest.TestCase):
    """Boundaries asserted against the real palette. The thresholds were chosen
    at the gaps between the 23 hexes actually in use, so the seed data is the
    only honest fixture."""

    #: The distribution as measured when the filter was built. A change here is
    #: either a data change worth noticing or a classifier regression; both
    #: should stop the build rather than quietly re-file 79 grasses.
    EXPECTED = {
        "straw": 79, "yellow": 77, "white": 75, "purple": 61, "pink": 43,
        "cream": 26, "blue": 16, "red": 8, "orange": 3, "brown": 2,
    }

    def test_every_seeded_species_lands_where_it_did(self):
        counts = bucket_counts(_seed_rows())
        got = {k: v for k, v in counts.items() if k}
        self.assertEqual(got, self.EXPECTED)

    def test_the_unrecorded_stay_unrecorded(self):
        """44 rows record no flower colour. They must classify to "" — not to
        white, which is what a naive parse of an empty hex would give."""
        self.assertEqual(bucket_counts(_seed_rows()).get(""), 44)

    def test_no_seeded_hex_falls_through_unclassified(self):
        unclassified = sorted({
            (r.get("flower_color") or "").strip() for r in _seed_rows()
            if (r.get("flower_color") or "").strip()
            and not classify(r)})
        self.assertEqual(unclassified, [])

    def test_every_bucket_key_is_in_the_published_vocabulary(self):
        for key in bucket_counts(_seed_rows()):
            if key:
                self.assertIn(key, COLOUR_KEYS)
                self.assertIn(key, COLOUR_LABELS)


class TestTheGrassesAreNotYellow(unittest.TestCase):
    """The assertion the module exists for. Poaceae, Cyperaceae and Juncaceae
    are wind-pollinated: `#cbbd80` is the *absence* of a showy flower, and
    filing 79 species under "yellow" beside a black-eyed susan would be a claim
    the data does not make (P9)."""

    def test_every_grass_sedge_and_rush_classifies_as_straw(self):
        wrong = [(r["common_name"], classify(r)) for r in _seed_rows()
                 if r.get("plant_type") in WIND_POLLINATED_TYPES
                 and (r.get("flower_color") or "").strip()
                 and classify(r) != "straw"]
        self.assertEqual(wrong, [])

    def test_nothing_else_is_filed_as_straw(self):
        strays = [r["common_name"] for r in _seed_rows()
                  if classify(r) == "straw"
                  and r.get("plant_type") not in WIND_POLLINATED_TYPES]
        self.assertEqual(strays, [])

    def test_the_taxonomic_rule_beats_the_hex(self):
        """The rule is checked before the colour on purpose: the reason is
        botanical, not chromatic. A grass with a bright hex is still a grass."""
        self.assertEqual(
            classify({"plant_type": "grass", "flower_color": "#f2c11e"}),
            "straw")
        self.assertEqual(
            classify({"plant_type": "wildflower", "flower_color": "#f2c11e"}),
            "yellow")

    def test_a_grass_with_no_colour_is_still_unrecorded(self):
        """The wind-pollinated rule must not invent a value where there is
        none — "" in, "" out."""
        self.assertEqual(classify({"plant_type": "grass", "flower_color": ""}), "")


class TestTheAwkwardBoundaries(unittest.TestCase):
    """The two thresholds that are not obvious, pinned so a later tidy-up
    cannot round them off."""

    def test_pale_lilac_is_purple_not_white(self):
        """`#c9b8e0` sits at saturation 0.18. The obvious "low saturation is
        white" rule swallows it, which is why white is capped at 0.12."""
        self.assertEqual(classify_hex("#c9b8e0"), "purple")

    def test_cream_is_not_white(self):
        self.assertEqual(classify_hex("#ece6c8"), "cream")
        self.assertEqual(classify_hex("#f2f2ea"), "white")

    def test_periwinkle_is_blue_not_purple(self):
        self.assertEqual(classify_hex("#7e7fc4"), "blue")
        self.assertEqual(classify_hex("#8e6fc4"), "purple")

    def test_dull_warm_darks_are_brown_not_yellow(self):
        self.assertEqual(classify_hex("#8a6f3c"), "brown")
        self.assertEqual(classify_hex("#f2c11e"), "yellow")

    def test_a_malformed_hex_returns_nothing_rather_than_raising(self):
        for bad in ("", "#fff", "not a colour", "#zzzzzz", None):
            self.assertEqual(classify_hex(bad), "")


class TestMatches(unittest.TestCase):

    def test_an_empty_selection_is_no_restriction(self):
        plant = {"plant_type": "wildflower", "flower_color": "#f2c11e"}
        self.assertTrue(matches(plant, []))
        self.assertTrue(matches(plant, None))

    def test_an_uncoloured_plant_matches_no_colour(self):
        plant = {"plant_type": "shrub", "flower_color": ""}
        for key in COLOUR_KEYS:
            self.assertFalse(matches(plant, [key]))


class TestTheFilterReachesTheQueryLayer(unittest.TestCase):
    """A facet naming a parameter nobody reads is a control that does nothing —
    the exact shape of the V2.37 bugs. These run against a real temp DB."""

    @classmethod
    def setUpClass(cls):
        init_db()

    def test_search_plants_accepts_and_applies_the_filter(self):
        every = search_plants()
        yellow = search_plants(flower_colours=["yellow"])
        self.assertGreater(len(yellow), 0)
        self.assertLess(len(yellow), len(every))
        for plant in yellow:
            self.assertEqual(classify(plant), "yellow")

    def test_an_empty_filter_does_not_restrict(self):
        self.assertEqual(len(search_plants(flower_colours=[])),
                         len(search_plants()))

    def test_multiple_colours_are_a_union(self):
        white = search_plants(flower_colours=["white"])
        yellow = search_plants(flower_colours=["yellow"])
        both = search_plants(flower_colours=["white", "yellow"])
        self.assertEqual(len(both), len(white) + len(yellow))

    def test_it_composes_with_the_other_filters(self):
        """Colour is a post-query pass; it must not discard the SQL filters
        applied before it."""
        rows = search_plants(flower_colours=["purple"], plant_type=["wildflower"])
        self.assertGreater(len(rows), 0)
        for plant in rows:
            self.assertEqual(plant["plant_type"], "wildflower")
            self.assertEqual(classify(plant), "purple")

    def test_the_directory_facet_drives_it(self):
        from src import plant_directory as pd
        kwargs = pd.criteria_to_kwargs({"colour": ["blue"]})
        self.assertEqual(kwargs.get("flower_colours"), ["blue"])
        rows = pd.search({"colour": ["blue"]})
        self.assertGreater(len(rows), 0)
        for plant in rows:
            self.assertEqual(classify(plant), "blue")


class TestTheZoneRangeSurvivesItsData(unittest.TestCase):
    """A regression guard, not a colour test — but it was found by this work.

    ``hardiness_zone_min`` ships one row reading ``'4?'``. ``int('4?')`` raised
    ``ValueError`` and took the whole species page down, so False Box could not
    be opened in the plant directory at all. The ``?`` is a real hedge and P9
    says show it, not swallow it.
    """

    @classmethod
    def setUpClass(cls):
        init_db()

    def test_a_hedged_zone_renders_rather_than_raising(self):
        from src.plant_directory import _zone_range
        self.assertEqual(
            _zone_range({"hardiness_zone_min": "4?", "hardiness_zone_max": 8}),
            "zone 4?–8")

    def test_ordinary_zones_are_unchanged(self):
        from src.plant_directory import _zone_range
        self.assertEqual(
            _zone_range({"hardiness_zone_min": 2, "hardiness_zone_max": 5}),
            "zone 2–5")
        self.assertEqual(
            _zone_range({"hardiness_zone_min": 3, "hardiness_zone_max": 3}),
            "zone 3")
        self.assertEqual(_zone_range({}), "")

    def test_every_seeded_species_builds_a_page(self):
        """The bug was one row in 434. Only sweeping them all would have caught
        it, so the guard sweeps them all."""
        from src.plant_directory import species_entry
        from src.db.plants import get_all_plants
        broken = []
        for plant in get_all_plants():
            try:
                species_entry(plant["id"])
            except Exception as exc:                       # noqa: BLE001
                broken.append((plant["common_name"], repr(exc)))
        self.assertEqual(broken, [])


if __name__ == "__main__":
    unittest.main()

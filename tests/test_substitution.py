"""
tests/test_substitution.py — "the nursery is out" (F91, V2.57).

Every plant tool has "similar plants" and every one means similar height and
colour — a similarity between objects, which is the frame P10 exists to reject.
This one means *ecologically equivalent*: same group, overlapping site envelope,
overlapping supported fauna — and it reports the trade rather than hiding it.

Fully injectable, so none of this touches the real catalogue.
"""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_TMP = tempfile.mkdtemp(prefix="permadesign_sub_")
try:
    import src.db.plants as _plants_mod
    _plants_mod._DATA_DIR = _TMP
    _plants_mod._DB_PATH = os.path.join(_TMP, "t.db")
except Exception:  # pragma: no cover
    pass

from src import substitution as sub  # noqa: E402

# A small synthetic catalogue. Ids are also the fauna-set keys below.
_PLANTS = {
    1: {"id": 1, "common_name": "Saskatoon", "scientific_name": "Amelanchier alnifolia",
        "plant_type": "shrub", "sun_requirement": "full_sun,partial_shade",
        "water_needs": "medium", "hardiness_zone_min": 2, "hardiness_zone_max": 6,
        "bloom_period": "May", "native_to_alberta": 1, "availability_class": "native_specialist"},
    2: {"id": 2, "common_name": "Chokecherry", "scientific_name": "Prunus virginiana",
        "plant_type": "shrub", "sun_requirement": "full_sun",
        "water_needs": "medium", "hardiness_zone_min": 2, "hardiness_zone_max": 7,
        "bloom_period": "June", "native_to_alberta": 1, "availability_class": "native_specialist"},
    3: {"id": 3, "common_name": "Desert Sage", "scientific_name": "Salvia deserta",
        "plant_type": "shrub", "sun_requirement": "full_sun",
        "water_needs": "low", "hardiness_zone_min": 7, "hardiness_zone_max": 9,
        "bloom_period": "July", "native_to_alberta": 0, "availability_class": "rare"},
    4: {"id": 4, "common_name": "Blue Grama", "scientific_name": "Bouteloua gracilis",
        "plant_type": "grass", "sun_requirement": "full_sun",
        "water_needs": "low", "hardiness_zone_min": 3, "hardiness_zone_max": 8,
        "bloom_period": "July", "native_to_alberta": 1, "availability_class": "seed_or_plug"},
    5: {"id": 5, "common_name": "Unrelated Shrub", "scientific_name": "Nihil nihil",
        "plant_type": "shrub", "sun_requirement": "full_sun",
        "water_needs": "medium", "hardiness_zone_min": 2, "hardiness_zone_max": 6,
        "bloom_period": "May", "native_to_alberta": 1, "availability_class": "garden_centre"},
}

#: plant id → supported fauna ids. Saskatoon and Chokecherry overlap heavily;
#: Unrelated Shrub shares nothing.
_FAUNA = {1: {10, 11, 12, 13}, 2: {10, 11, 12, 90}, 3: {10, 11, 12, 13},
          4: {50}, 5: {77, 78}}
_FAUNA_NAMES = {10: "Cedar Waxwing", 11: "Mason Bee", 12: "Ruffed Grouse",
                13: "Pine Grosbeak", 50: "Deer Mouse", 77: "Aphid",
                78: "Ant", 90: "Bohemian Waxwing"}


def _get_plant(pid):
    return _PLANTS.get(int(pid), {})


def _all_plants():
    return list(_PLANTS.values())


def _supported_by(ids, taxon=""):
    # One taxon carries everything in this fixture; the real query is per-taxon
    # and the union is what substitution uses.
    if taxon != "lepidoptera":
        return set()
    out = set()
    for pid in ids:
        out |= _FAUNA.get(int(pid), set())
    return out


def _get_fauna(fid):
    return {"common_name": _FAUNA_NAMES.get(int(fid), "")}


_KW = dict(get_plant=_get_plant, all_plants=_all_plants,
           supported_by=_supported_by, get_fauna=_get_fauna)


class TestCandidateFiltering(unittest.TestCase):
    def test_it_offers_the_ecological_near_match(self):
        swaps = sub.substitutes(1, **_KW)
        self.assertTrue(swaps)
        self.assertEqual(swaps[0].common_name, "Chokecherry")
        self.assertEqual(swaps[0].kept, 3)
        self.assertEqual(swaps[0].original_total, 4)

    def test_a_different_group_is_never_offered(self):
        """A grass is not a substitute for a shrub, however similar the site."""
        names = [s.common_name for s in sub.substitutes(1, **_KW)]
        self.assertNotIn("Blue Grama", names)

    def test_an_unsurvivable_zone_is_excluded(self):
        """Zone 7-9 cannot stand in for a zone 2-6 plant at any price."""
        names = [s.common_name for s in sub.substitutes(1, **_KW)]
        self.assertNotIn("Desert Sage", names)

    def test_a_shrub_sharing_no_wildlife_is_excluded(self):
        """Same layer, same site, zero relationships kept — that is a different
        plant, and calling it equivalent is the false reassurance this module
        exists to avoid."""
        names = [s.common_name for s in sub.substitutes(1, **_KW)]
        self.assertNotIn("Unrelated Shrub", names)

    def test_the_original_is_never_its_own_substitute(self):
        self.assertNotIn(1, [s.plant_id for s in sub.substitutes(1, **_KW)])


class TestTheEnvelopeIsToleranceNotEquality(unittest.TestCase):
    """sun_requirement is comma-separated — "full_sun,partial_shade" is one
    plant tolerating both. Comparing whole strings rejected 76 of 80 candidate
    grasses against the real catalogue before this was caught."""

    def test_overlapping_sun_tolerances_match(self):
        a = {"sun_requirement": "full_sun,partial_shade"}
        b = {"sun_requirement": "full_sun"}
        self.assertTrue(sub._envelope_ok(a, b))
        self.assertTrue(sub._envelope_ok(b, a))

    def test_disjoint_sun_tolerances_do_not(self):
        self.assertFalse(sub._envelope_ok({"sun_requirement": "full_shade"},
                                          {"sun_requirement": "full_sun"}))

    def test_a_blank_does_not_exclude(self):
        """Blank means 'not recorded', and excluding on it would hide good
        candidates — the absent-is-not-a-value rule from V2.53."""
        self.assertTrue(sub._envelope_ok({"sun_requirement": ""},
                                         {"sun_requirement": "full_sun"}))


class TestZoneParsing(unittest.TestCase):
    """The column is not reliably numeric: '4?' is a real stored value, and
    int() on it crashed the whole feature on the first shrub."""

    def test_a_question_mark_zone_is_read_not_raised(self):
        self.assertEqual(sub._zone("4?"), 4)
        self.assertEqual(sub._zone(3), 3)
        self.assertIsNone(sub._zone(None))
        self.assertIsNone(sub._zone("unknown"))

    def test_an_unreadable_zone_stops_constraining(self):
        a = {"hardiness_zone_min": "3?", "hardiness_zone_max": "junk"}
        b = {"hardiness_zone_min": 8, "hardiness_zone_max": 9}
        self.assertTrue(sub._envelope_ok(a, b))


class TestThinlyRecordedPlants(unittest.TestCase):
    """With one recorded relationship, "keep 25%" collapses into "keep that
    exact species", so a thinly-recorded plant would return nothing — punishing
    the user for a gap in the data rather than telling them about the plants."""

    def test_a_one_relationship_plant_still_gets_candidates(self):
        plants = dict(_PLANTS)
        plants[6] = dict(plants[4], id=6, common_name="Rough Fescue")
        kw = dict(_KW, all_plants=lambda: list(plants.values()),
                  get_plant=lambda p: plants.get(int(p), {}))
        swaps = sub.substitutes(4, **kw)
        self.assertTrue(swaps, "a thinly-recorded grass got no substitutes")

    def test_the_sentence_admits_the_comparison_is_thin(self):
        plants = dict(_PLANTS)
        plants[6] = dict(plants[4], id=6, common_name="Rough Fescue")
        kw = dict(_KW, all_plants=lambda: list(plants.values()),
                  get_plant=lambda p: plants.get(int(p), {}))
        line = sub.swap_lines(4, **kw)[0]
        self.assertIn("thin", line.lower())

    def test_a_well_recorded_plant_says_no_such_thing(self):
        self.assertNotIn("thin", sub.swap_lines(1, **_KW)[0].lower())


class TestTheSentence(unittest.TestCase):
    def test_it_reports_the_gain_and_the_loss(self):
        """The gain alone is a sales pitch; the loss alone would stop a
        substitution that is, on balance, fine."""
        line = sub.swap_lines(1, **_KW)[0]
        self.assertIn("keeps 3 of 4", line)
        self.assertIn("You lose 1", line)
        self.assertIn("Pine Grosbeak", line)

    def test_it_names_what_is_added(self):
        self.assertIn("Adds 1", sub.swap_lines(1, **_KW)[0])

    def test_it_reports_a_bloom_shift(self):
        line = sub.swap_lines(1, **_KW)[0]
        self.assertIn("month later", line)     # May → June

    def test_no_bloom_shift_is_not_mentioned(self):
        swap = sub.Swap(plant_id=2, common_name="X", scientific_name="Y",
                        kept=3, original_total=4, lost=["Z"], gained=0,
                        price_low=1.0, price_high=2.0, availability="",
                        bloom_shift=0)
        self.assertNotIn("Blooms", sub.swap_line("A", swap))

    def test_a_plant_with_no_relationships_says_so(self):
        """Rather than printing "keeps 0 of 0" as though that were a finding."""
        swap = sub.Swap(plant_id=2, common_name="X", scientific_name="Y",
                        kept=0, original_total=0, lost=[], gained=0,
                        price_low=1.0, price_high=2.0, availability="",
                        bloom_shift=0)
        line = sub.swap_line("Mystery Plant", swap)
        self.assertIn("no wildlife relationships are recorded", line)
        self.assertNotIn("keeps 0 of 0", line)


class TestTheGroupMapCoversTheCatalogue(unittest.TestCase):
    """habitat_score.PLANT_TYPE_TO_LAYER knows six plant_types; the catalogue
    holds eleven, and the five it misses are 311 of 437 species. Using it here
    would leave substitution dead for most of the app — see F124."""

    def test_every_catalogue_plant_type_has_a_group(self):
        """Read from the shipped seed JSON, not the database.

        This module redirects the DB to an empty temp dir, so a query here
        would skip — and a skipped test proves nothing, least of all this one,
        which is the guard against the gap that made F91 dead for 311 species.
        The JSON is the authoritative source the DB is seeded from anyway.
        """
        import json
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        types = set()
        for name in ("plants_master.json", "garden_plants.json"):
            path = os.path.join(root, "data", name)
            with open(path, "r", encoding="utf-8") as fh:
                blob = json.load(fh)
            rows = (blob if isinstance(blob, list)
                    else next(v for v in blob.values() if isinstance(v, list)))
            types |= {(r.get("plant_type") or "").strip()
                      for r in rows if (r.get("plant_type") or "").strip()}
        self.assertGreater(len(types), 5, "no plant types read from the seed")
        missing = sorted(t for t in types
                         if t.lower() not in sub.SUBSTITUTION_GROUPS)
        self.assertFalse(
            missing,
            f"plant types with no substitution group: {missing} — every plant "
            f"of those types would silently have no substitutes")

    def test_graminoids_and_forbs_are_kept_apart(self):
        """Both are 'herbaceous' to the layer map, but swapping a wind-
        pollinated grass for an insect-pollinated forb is a bad
        recommendation however equal their layer."""
        self.assertNotEqual(sub.SUBSTITUTION_GROUPS["grass"],
                            sub.SUBSTITUTION_GROUPS["wildflower"])
        self.assertEqual(sub.SUBSTITUTION_GROUPS["grass"],
                         sub.SUBSTITUTION_GROUPS["sedge"])


if __name__ == "__main__":
    unittest.main()

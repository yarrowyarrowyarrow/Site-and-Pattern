"""
tests/test_creature_community.py

Covers ``src.creature_community.build_creature_community`` (V2.12) — the
"design a community for a creature" generator behind the plant-community panel's
"For a creature…" option:

  * a butterfly community carries both nectar plants and larval hosts, in layers
  * a non-feeding moth (giant silk moth) yields a host-plant-only community (P9)
  * a bee community carries nectar/pollen plants
  * members have unique spatial offsets (no stacking at the origin)
  * the generated members round-trip through the polyculture write path
  * non-bee/lep fauna (e.g. a bird) yields None
"""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_TMP_DIR = tempfile.mkdtemp(prefix="permadesign_cc_test_")

import src.db.plants as _plants_mod  # noqa: E402

_plants_mod._DATA_DIR = _TMP_DIR
_plants_mod._DB_PATH  = os.path.join(_TMP_DIR, "permadesign_test.db")

from src.db.plants import init_db, get_connection  # noqa: E402
from src.db import polycultures  # noqa: E402
import src.creature_community as CC  # noqa: E402


def _fid(scientific_name: str):
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT id FROM fauna WHERE scientific_name = ?", (scientific_name,)
        ).fetchone()
        return row[0] if row else None
    finally:
        conn.close()


class TestCreatureCommunity(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        init_db()

    def test_butterfly_has_nectar_and_hosts_in_layers(self):
        com = CC.build_creature_community(_fid("Papilio canadensis"))
        self.assertIsNotNone(com)
        self.assertIn("Swallowtail", com["name"])
        hosts = [m for m in com["members"] if not m["functions"]]
        nectar = [m for m in com["members"] if "pollinator" in m["functions"]]
        self.assertTrue(hosts, "a swallowtail garden must carry larval hosts")
        self.assertTrue(nectar, "…and adult nectar plants")
        layers = {m["layer"] for m in com["members"]}
        self.assertTrue({"overstory", "shrub_layer", "herbaceous"} & layers)
        # Host trees/shrubs are noted as caterpillar hosts.
        self.assertTrue(any("Caterpillar host" in m["notes"] for m in hosts))

    def test_nonfeeding_moth_is_host_only(self):
        com = CC.build_creature_community(_fid("Hyalophora cecropia"))
        self.assertIsNotNone(com)
        self.assertTrue(com["members"])
        # No adult nectar → every member is a larval host (no 'pollinator').
        self.assertTrue(all(not m["functions"] for m in com["members"]),
                        "a non-feeding moth community should be host-only")
        self.assertIn("host", com["description"].lower())

    def test_bee_community_has_forage(self):
        bid = None
        for row in get_connection().execute(
                "SELECT id FROM fauna WHERE taxon='bee' LIMIT 1"):
            bid = row[0]
        com = CC.build_creature_community(bid)
        self.assertIsNotNone(com)
        self.assertTrue(any("pollinator" in m["functions"] for m in com["members"]))

    def test_offsets_are_unique(self):
        com = CC.build_creature_community(_fid("Danaus plexippus"))
        offs = [(m["offset_x"], m["offset_y"]) for m in com["members"]]
        self.assertEqual(len(set(offs)), len(offs), "members must not stack")

    def test_members_round_trip_through_write_path(self):
        com = CC.build_creature_community(_fid("Danaus plexippus"))
        new_id = polycultures.create_polyculture(com["name"], com["description"], None)
        # Must not raise — the member dicts match the write-path contract.
        polycultures.replace_polyculture_members(new_id, com["members"])
        saved = polycultures.get_polyculture_by_id(new_id)
        self.assertEqual(len(saved["members"]), len(com["members"]))

    def test_non_pollinator_fauna_returns_none(self):
        # A bird is neither a bee nor a lepidopteran → no community.
        bird_id = None
        for row in get_connection().execute(
                "SELECT id FROM fauna WHERE taxon='bird' LIMIT 1"):
            bird_id = row[0]
        if bird_id is not None:
            self.assertIsNone(CC.build_creature_community(bird_id))


if __name__ == "__main__":
    unittest.main()

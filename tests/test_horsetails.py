"""
tests/test_horsetails.py — what the catalogue says a horsetail is (V2.89, F176).

The four *Equisetum* species were recorded as three plant types (herb, rush,
aquatic) with the marsh habit `emergent`, so the 3D scene drew them as a grass
tuft, a reed tuft and two rush tufts — and two of them carried the grass
`flower_form: plume` in the graminoid straw colour, so they wore seed-head plumes
from June to September. A horsetail has no flowers at all: it makes spores in a
cone. These tests pin the records the viewer now draws from
(html/scene3d/14-layers.js buildHorsetailGeo).
"""

import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.data_quality import GROWTH_FORMS, STEM_BRANCHINGS  # noqa: E402

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

with open(os.path.join(_ROOT, "data", "plants_master.json"),
          encoding="utf-8") as _fh:
    _ROWS = json.load(_fh)

_EQUISETUM = [r for r in _ROWS
              if (r.get("scientific_name") or "").startswith("Equisetum ")]


class HorsetailRecords(unittest.TestCase):

    def test_the_catalogue_carries_four(self):
        self.assertEqual(len(_EQUISETUM), 4,
                         "a horsetail was added or lost: check it is jointed")

    def test_every_horsetail_is_jointed(self):
        """True of the whole genus by definition, so not a guess about any one
        species — and `plant_type` stays what it was, because it drives layers,
        filters and the website."""
        self.assertIn("jointed", GROWTH_FORMS)
        for r in _EQUISETUM:
            with self.subTest(r["scientific_name"]):
                self.assertEqual(r.get("growth_form"), "jointed")

    def test_only_horsetails_are_jointed(self):
        others = [r["scientific_name"] for r in _ROWS
                  if r.get("growth_form") == "jointed"
                  and not r["scientific_name"].startswith("Equisetum ")]
        self.assertEqual(others, [], "the horsetail body applied to a non-horsetail")

    def test_each_records_where_its_whorls_are(self):
        want = {"Equisetum arvense": "branched_throughout",
                "Equisetum fluviatile": "branched_above",
                "Equisetum hyemale": "unbranched",
                "Equisetum variegatum": "unbranched"}
        for r in _EQUISETUM:
            with self.subTest(r["scientific_name"]):
                self.assertIn(r.get("stem_branching"), STEM_BRANCHINGS)
                self.assertEqual(r["stem_branching"], want[r["scientific_name"]])

    def test_no_horsetail_carries_a_flower(self):
        for r in _EQUISETUM:
            with self.subTest(r["scientific_name"]):
                self.assertIn(r.get("flower_form"), (None, "", "none"))
                self.assertFalse(r.get("flower_color"))
                self.assertFalse(r.get("bloom_period"))
                self.assertFalse(r.get("inflorescence_form"))

    def test_the_values_are_not_claimed_from_a_flora(self):
        """The flora sites were unreachable when these were set (V2.89), so no
        horsetail may claim its habit was read from one without a citation —
        the gate's own rule, restated where the values were written."""
        for r in _EQUISETUM:
            with self.subTest(r["scientific_name"]):
                if (r.get("leaf_data_source") or "") in ("flora", "measured", "photo"):
                    self.assertTrue(r.get("leaf_data_citation"))


if __name__ == "__main__":
    unittest.main()

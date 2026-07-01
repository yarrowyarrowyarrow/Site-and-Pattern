"""
tests/test_snow_microsite.py — snow-catch microsite zones (Step 3).

Covers src/snow_microsite.py:
  1. snow_catch_payload relabels wind-shelter strength bands as catch depth and
     passes the geometry through (with an injected merge fn — no shapely needed).
  2. winter_prevailing_deg: winter block first, annual fallback, None when absent.
  3. interpretation text framing (lee = insulated/moist; windward = scoured).

Pure — no Qt, no DB, no shapely.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import snow_microsite as sm  # noqa: E402


def _fake_merged(casters, wind_from_deg):
    return {
        "bands": [
            {"strength": "weak",     "rings": [[[1, 2], [3, 4], [5, 6]]]},
            {"strength": "moderate", "rings": [[[7, 8], [9, 10], [11, 12]]]},
            {"strength": "strong",   "rings": [[[1, 1], [2, 2], [3, 3]]]},
        ],
        "wind_from_deg": wind_from_deg,
    }


class TestSnowCatchPayload(unittest.TestCase):
    def test_relabels_and_passes_geometry(self):
        out = sm.snow_catch_payload([{"x": 1}], 315.0, merged_fn=_fake_merged)
        catches = [b["catch"] for b in out["bands"]]
        self.assertEqual(catches, ["light", "moderate", "deep"])
        self.assertEqual(out["bands"][2]["rings"], [[[1, 1], [2, 2], [3, 3]]])
        self.assertEqual(out["wind_from_deg"], 315.0)

    def test_empty_when_no_bands(self):
        out = sm.snow_catch_payload([], 270.0,
                                    merged_fn=lambda c, d: {"bands": [],
                                                            "wind_from_deg": d})
        self.assertEqual(out["bands"], [])
        self.assertEqual(out["wind_from_deg"], 270.0)


class TestWinterPrevailing(unittest.TestCase):
    def test_winter_block_used(self):
        rose = {"seasons": {"winter": {"prevailing_deg": 315.0}},
                "annual": {"prevailing_deg": 270.0}}
        self.assertEqual(sm.winter_prevailing_deg(rose), 315.0)

    def test_falls_back_to_annual(self):
        rose = {"seasons": {"winter": {"prevailing_deg": None}},
                "annual": {"prevailing_deg": 270.0}}
        self.assertEqual(sm.winter_prevailing_deg(rose), 270.0)

    def test_none_when_absent(self):
        self.assertIsNone(sm.winter_prevailing_deg(None))
        self.assertIsNone(sm.winter_prevailing_deg({"seasons": {}, "annual": {}}))


class TestInterpretation(unittest.TestCase):
    def test_mentions_lee_and_windward(self):
        text = " ".join(sm.interpretation("NW")).lower()
        self.assertIn("lee", text)
        self.assertIn("windward", text)
        self.assertIn("winter wind", text)

    def test_no_label_omits_wind_line(self):
        notes = sm.interpretation()
        self.assertTrue(notes)
        self.assertFalse(any("winter wind" in n.lower() for n in notes))


if __name__ == "__main__":
    unittest.main()

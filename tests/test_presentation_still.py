"""
tests/test_presentation_still.py — F69, the render you can put in a proposal.

The join this guards is a specific one: :mod:`src.docent`'s beats have carried
``year``, ``season_month`` and ``camera`` since V2.13 and **nothing read them**
— the docent widget shows the title and narration, the 3D window runs its own
hard-coded flyover storyboard. If a future change drops those fields from the
beats, or the camera vocabulary drifts from the viewer's, the still silently
falls back to a default and the feature quietly stops being data-driven.

Qt-free and DB-free: the docent script is injectable.
"""

import os
import re
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import presentation_still as ps

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _script(*beats):
    return {"beats": list(beats)}


def _beat(bid, **kw):
    b = {"id": bid, "title": bid.title(), "narration": "A sentence. And more.",
         "year": 0, "season_month": 6, "camera": "overview"}
    b.update(kw)
    return b


class TestStillFromBeat(unittest.TestCase):
    def test_carries_the_beats_camera_year_and_season(self):
        st = ps.still_from_beat(_beat("brood", year=10, season_month=8,
                                      camera="walk"))
        self.assertEqual((st["year"], st["month"], st["camera"]),
                         (10, 8, "walk"))

    def test_unknown_camera_falls_back_rather_than_failing(self):
        st = ps.still_from_beat(_beat("x", camera="helicopter"))
        self.assertEqual(st["camera"], ps.DEFAULT_CAMERA)

    def test_garbage_month_and_year_are_clamped(self):
        st = ps.still_from_beat(_beat("x", year=-4, season_month=99))
        self.assertEqual(st["year"], 0)
        self.assertTrue(1 <= st["month"] <= 12)

    def test_empty_beat_still_produces_a_usable_spec(self):
        st = ps.still_from_beat({})
        self.assertIn(st["camera"], ps.CAMERA_PRESETS)
        self.assertTrue(1 <= st["month"] <= 12)


class TestStills(unittest.TestCase):
    def test_one_still_per_beat_in_tour_order(self):
        stills = ps.presentation_stills(
            {}, script=_script(_beat("opening"), _beat("score", year=3),
                               _beat("close", year=12)))
        self.assertEqual([s["id"] for s in stills],
                         ["opening", "score", "close"])

    def test_cover_is_the_design_grown_up_not_on_install_day(self):
        """P4's argument, as one image: a photograph of a new planting shows
        bare mulch, which is exactly what puts people off."""
        cover = ps.cover_still(
            {}, script=_script(_beat("opening", year=0),
                               _beat("close", year=12, season_month=11)))
        self.assertEqual(cover["year"], 12)
        self.assertEqual(cover["month"], 7, "the cover is high summer")
        self.assertEqual(cover["camera"], ps.DEFAULT_CAMERA)

    def test_cover_exists_even_for_an_empty_design(self):
        cover = ps.cover_still({}, script=_script())
        self.assertIsNotNone(cover, "a document with no picture is the failure")

    def test_render_request_asks_for_print_resolution(self):
        req = ps.render_request(ps.still_from_beat(_beat("x", year=5)))
        self.assertGreaterEqual(req["width"] * req["pixel_ratio"], 2400,
                                "a page image needs ~300 dpi across ~10 inches")
        self.assertLessEqual(req["width"], 2048,
                             "permaSnapshot clamps each edge to 2048")
        self.assertGreater(req["pixel_ratio"], 1,
                           "without an explicit ratio the capture's real size "
                           "depends on the display the app happens to be on")


class TestViewerContract(unittest.TestCase):
    """The presets have to exist at both ends, or a beat's camera does nothing."""

    def _read(self, rel):
        with open(os.path.join(_ROOT, rel), encoding="utf-8") as fh:
            return fh.read()

    def test_viewer_implements_every_preset(self):
        src = self._read("html/scene3d/08-modes.js")
        self.assertIn("permaSetCameraPreset", src)
        table = re.search(r"const _CAMERA_PRESETS = \{(.*?)\n\};", src, re.S)
        self.assertIsNotNone(table, "08-modes.js lost _CAMERA_PRESETS")
        have = set(re.findall(r"^\s{2}(\w+):\s*\{", table.group(1), re.M))
        missing = set(ps.CAMERA_PRESETS) - have
        self.assertFalse(
            missing,
            f"src/presentation_still.py offers {sorted(missing)} but the viewer "
            f"implements {sorted(have)} — a beat asking for one of those would "
            f"silently render from the default camera")

    def test_docent_beats_only_use_cameras_the_viewer_knows(self):
        src = self._read("src/docent.py")
        used = set(re.findall(r'camera="(\w+)"', src))
        self.assertTrue(used, "docent.py stopped naming cameras on its beats")
        unknown = used - set(ps.CAMERA_PRESETS)
        self.assertFalse(
            unknown,
            f"docent beats ask for {sorted(unknown)}, which "
            f"src/presentation_still.py and the viewer do not implement")

    def test_beats_still_carry_the_three_fields_the_still_needs(self):
        src = self._read("src/docent.py")
        for field in ("year", "season_month", "camera"):
            self.assertIn(field, src, f"docent beats lost `{field}`")


if __name__ == "__main__":
    unittest.main()

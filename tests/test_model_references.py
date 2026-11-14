"""scripts/model_references.py (V3.47): which plants, which photographs, and
the cameras. Offline: nothing is downloaded or rendered here."""

import json
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import model_references as mr  # noqa: E402
from src import native_here  # noqa: E402


def _args(**kw):
    base = {"only": None, "place": None, "all_plants": False}
    base.update(kw)
    return SimpleNamespace(**base)


class WhichPlants(unittest.TestCase):

    def test_default_is_the_regions_native_list(self):
        rows = mr.plants(_args())
        self.assertEqual({r["scientific_name"] for r in rows},
                         set(native_here.native_names()))

    def test_only_takes_either_name(self):
        rows = mr.plants(_args(only=["wild bergamot", "Populus tremuloides"]))
        self.assertEqual(sorted(r["scientific_name"] for r in rows),
                         ["Monarda fistulosa", "Populus tremuloides"])

    def test_almost_every_native_has_a_gallery_scene(self):
        """The renders come from the gallery's scenes: a native without one is
        named by ``status`` and needs scripts/make_gallery_scene.py."""
        scenes = json.loads(mr.SCENES.read_text(encoding="utf-8"))
        rows = mr.plants(_args())
        missing = [r for r in rows
                   if f"species_{mr.slug(r['scientific_name'])}" not in scenes]
        self.assertLessEqual(len(missing), 3, [r["scientific_name"] for r in missing])


class WhichPhotographs(unittest.TestCase):
    ROW = {"scientific_name": "Monarda fistulosa", "common_name": "Wild Bergamot",
           "image_url": "https://example.org/now.jpg"}

    def test_candidates_win_in_the_sheets_order_without_repeats(self):
        cands = {"Monarda fistulosa": {"groups": {
            "fruit": [{"url": "u3"}], "flower": [{"url": "u1"}, {"url": "u2"}],
            "now": [{"url": "u1"}]}}}
        photos, source = mr.photos_for(self.ROW, cands, {})
        self.assertEqual(source, "candidates")
        self.assertEqual([p["url"] for p in photos], ["u1", "u2", "u3"])
        self.assertEqual([p["group"] for p in photos], ["flower", "flower", "fruit"])

    def test_without_candidates_the_catalogues_photos_are_used(self):
        shipped = {"Monarda fistulosa": [{"url": "s1", "attribution": "x"}]}
        photos, source = mr.photos_for(self.ROW, {}, shipped)
        self.assertEqual(source, "shipped")
        self.assertEqual([p["url"] for p in photos], ["s1", "https://example.org/now.jpg"])


class Cameras(unittest.TestCase):

    def test_framed_on_the_plants_size(self):
        small = mr.views({"height_m": 0.5, "canopy_m": 0.4})
        tree = mr.views({"height_m": 20, "canopy_m": 8})
        self.assertLess(small["side"]["at"][2], 1.0)
        self.assertGreater(tree["side"]["at"][2], 20)
        self.assertEqual(tree["side"]["looks_at"], [0, 10.0, 0])


if __name__ == "__main__":
    unittest.main()

"""
test_sprite_gallery.py — the gallery scene generator (Qt-free).

`src.sprite_gallery.gallery_scenes()` is the single source of truth for the
in-app gallery window AND the standalone html gallery, so it must cover every
genus archetype + flower form and emit valid, serialisable Scene JSON.
"""

import json
import unittest

from src.sprite_gallery import gallery_scenes, GEOMETRY, FORMS


class TestGalleryScenes(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.scenes = gallery_scenes()

    def test_covers_every_geometry_and_flower(self):
        keys = set(self.scenes)
        # Each curated geometry specimen + each flower form is present, plus "all".
        for key, *_ in GEOMETRY:
            self.assertIn(key, keys, key)
        for form in FORMS:
            self.assertIn(f"flower_{form}", keys, form)
        self.assertIn("all", keys)

    def test_headline_species_distinct_and_present(self):
        # The species the user asked to tell apart must each be their own entry.
        for key in ("conifer_spruce", "conifer_pine", "conifer_fir",
                    "tree_aspen", "tree_birch", "tree_oak", "shrub_dogwood"):
            self.assertIn(key, self.scenes)

    def test_entries_are_valid_serialisable_scenes(self):
        for key, entry in self.scenes.items():
            self.assertTrue(entry["name"])
            scene = entry["scene"]
            self.assertIn("bounds", scene)
            self.assertTrue(scene["plants"], key)          # at least one specimen
            json.dumps(scene)                              # must not raise

    def test_genus_flows_to_scene_plants(self):
        # The viewer keys species geometry off `genus`; confirm it's emitted.
        spruce = self.scenes["conifer_spruce"]["scene"]["plants"][0]
        self.assertEqual(spruce["genus"], "picea")
        pine = self.scenes["conifer_pine"]["scene"]["plants"][0]
        self.assertEqual(pine["genus"], "pinus")
        self.assertNotEqual(spruce["color"], pine["color"])   # different greens

    def test_new_flower_forms_use_real_species(self):
        pea = self.scenes["flower_pea"]["scene"]["plants"][0]
        self.assertEqual(pea["flower_form"], "pea")
        whorl = self.scenes["flower_whorl"]["scene"]["plants"][0]
        self.assertEqual(whorl["flower_form"], "whorl")


if __name__ == "__main__":
    unittest.main()

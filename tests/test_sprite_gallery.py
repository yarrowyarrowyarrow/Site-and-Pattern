"""
test_sprite_gallery.py — the gallery scene generator (Qt-free).

`src.sprite_gallery.gallery_scenes()` is the single source of truth for the
in-app gallery window AND the standalone html gallery, so it must cover every
genus archetype + flower form and emit valid, serialisable Scene JSON.
"""

import json
import re
import unittest
from pathlib import Path

import src.sprite_gallery as sprite_gallery
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

    def test_a_vine_entry_shows_it_climbing_and_alone(self):
        # V2.89: a vine climbs the tree or shrub beside it, or lies on the
        # ground, so a lone specimen would only ever show the sprawl.
        entries = {k: e["scene"]["plants"] for k, e in self.scenes.items()
                   if k.startswith("species_")
                   and any(p.get("plant_type") == "vine"
                           for p in e["scene"]["plants"])}
        self.assertTrue(entries, "no vine species in the gallery")
        for key, plants in entries.items():
            vines = {p["drawn"]["habit"]: p for p in plants
                     if p.get("plant_type") == "vine"}
            host = next(p for p in plants if p.get("plant_type") != "vine")
            with self.subTest(key):
                self.assertEqual(sorted(vines), ["climbing", "sprawling"])
                # On the shrub's right-hand edge as the gallery camera sees
                # it (east-north-east), not hidden behind or inside it.
                self.assertGreater(vines["climbing"]["x"], host["x"])
                self.assertGreater(vines["climbing"]["y"], host["y"])

    def test_a_floating_or_submerged_plant_is_shown_on_water(self):
        # V2.90: on the lawn a pond-lily is a scatter of pads on grass.
        shown = 0
        for key, e in self.scenes.items():
            if not key.startswith("species_"):
                continue
            for p in e["scene"]["plants"]:
                if (p.get("drawn") or {}).get("body") in ("floating",
                                                          "submerged"):
                    shown += 1
                    with self.subTest(key):
                        self.assertGreater(p["drawn"]["water_m"], 0,
                                           "drawn on dry ground")
        self.assertGreaterEqual(shown, 7, "the pond's species went missing")

    def test_seed_reads_pin_utf8_encoding(self):
        # Regression (V1.95): bare read_text()/write_text() use the locale codec
        # (cp1252 on Windows) and crash on the seed JSON's en-dashes / accented
        # names. Every file read/write in the gallery module must pin an encoding.
        text = Path(sprite_gallery.__file__).read_text(encoding="utf-8")
        for m in re.finditer(r"\.(?:read|write)_text\(([^)]*)\)", text):
            self.assertIn("encoding", m.group(1),
                          "read_text()/write_text() without encoding= "
                          "in sprite_gallery.py (cp1252 crash on Windows)")


if __name__ == "__main__":
    unittest.main()

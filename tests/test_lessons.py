"""
tests/test_lessons.py — three lessons, a first draft for the owner (F88, V3.41).

The owner found the old four "incredibly basic", "AI-sounding", and taught
"against your design", which in the Learn window meant the walk's sandbox.
These hold the draft's shape and its rules (src/lessons.py): the owner's three
lessons, a pointer and sources on each page, no place typed in, no plant-use
knowledge (P12), the glossary's words, none of the stock phrases that read as
written by a machine, every source in the bibliography, and readouts about a
landscape that say true things about it.
"""

import os
import pathlib
import re
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import lessons as L  # noqa: E402

_ROOT = pathlib.Path(__file__).resolve().parent.parent

#: Words that read as written by a machine; the owner called the old lessons
#: "AI-sounding".
_STOCK = ("delve", "tapestry", "embark", "journey", "unlock", "elevate",
          "seamless", "vibrant", "holistic", "leverage", "realm", "testament",
          "boasts", "game-changer", "dive into", "in today's", "navigate the",
          "it's important to note", "crucial role", "plays a vital")


def _all_text():
    for key, title, pages in L.LESSONS:
        yield title
        for page in pages:
            yield page["title"]
            yield from page["text"]
            yield page["look"]


class TheDraftsShape(unittest.TestCase):

    def test_the_owners_three_lessons(self):
        self.assertEqual([t for _k, t, _p in L.LESSONS], [
            "Designing for biodiversity",
            "Site factors to consider in design",
            "Aesthetic considerations"])

    def test_each_page_has_text_a_pointer_and_a_readout_key(self):
        for key, _title, pages in L.LESSONS:
            self.assertGreaterEqual(len(pages), 5, key)
            for page in pages:
                words = sum(len(t.split()) for t in page["text"])
                self.assertTrue(50 <= words <= 220, (page["title"], words))
                self.assertTrue(page["look"].strip(), page["title"])
                self.assertIn(page["readout"], set(L._READOUTS) | {""})

    def test_the_four_old_lessons_are_in_the_first(self):
        titles = " ".join(p["title"] for p in L.LESSONS[0][2]).lower()
        for idea in ("feed far more", "caterpillar", "over time",
                     "ranges"):
            self.assertIn(idea, titles)

    def test_every_source_is_written_out_and_in_the_bibliography(self):
        refs = (_ROOT / "docs" / "REFERENCES.md").read_text(encoding="utf-8")
        for _k, _t, pages in L.LESSONS:
            for page in pages:
                for cite in page["sources"]:
                    self.assertIn(cite, L.SOURCES)
                    author = cite.split()[0].rstrip(",")
                    self.assertIn(author, refs, cite)


class TheRulesForTheText(unittest.TestCase):

    def test_no_place_is_typed_in(self):
        """The region guard's rule (V3.24): the place comes from the pack."""
        from src import region
        short = region.default().short.lower()
        for text in _all_text():
            self.assertNotIn(short, text.lower(), text[:60])
        filled = L.lesson("site")["pages"][0]["text"]
        self.assertTrue(any(region.default().short in t for t in filled))
        self.assertFalse(any("{place}" in t for t in filled))

    def test_nothing_about_how_anyone_uses_plants(self):
        """P12, with the word list the example tool refuses notes by."""
        sys.path.insert(0, str(_ROOT / "scripts"))
        from make_example import P12_WORDS
        for text in _all_text():
            for word in P12_WORDS:
                self.assertNotIn(word, text.lower(), text[:60])

    def test_the_glossarys_words(self):
        from src.vocabulary import NEVER
        for text in _all_text():
            for word in NEVER:
                self.assertIsNone(
                    re.search(rf"\b{re.escape(word.lower())}\b", text.lower()),
                    f"{word!r} in {text[:60]!r}")
            self.assertNotIn("forb", text.lower())

    def test_none_of_the_stock_phrases(self):
        for text in _all_text():
            for phrase in _STOCK:
                self.assertNotIn(phrase, text.lower(), text[:60])
            self.assertNotIn("—", text, "no em dashes (the site's rule too)")


def _row(i, name, ptype, **kw):
    row = {"id": i, "plant_id": i, "common_name": name, "plant_type": ptype}
    row.update(kw)
    return row


ROWS = {
    1: _row(1, "Trembling Aspen", "tree", years_to_maturity=10,
            mature_height_m=20, sun_requirement="full_sun",
            water_needs="low,medium", bloom_period="Apr-May"),
    2: _row(2, "Wild Bergamot", "wildflower", years_to_maturity=2,
            mature_height_m=0.8, sun_requirement="full_sun,partial_shade",
            water_needs="low,medium", bloom_period="Jul-Aug"),
    3: _row(3, "June Grass", "grass", years_to_maturity=3,
            mature_height_m=0.4, sun_requirement="full_sun",
            water_needs="low", bloom_period="Jun-Jul"),
}


def _land(placed=None, **kw):
    placed = placed if placed is not None else [
        {"plant_id": 1}, {"plant_id": 2}, {"plant_id": 2}, {"plant_id": 2},
        {"plant_id": 3}]
    return L.landscape(placed, get_plant=ROWS.get, **kw)


class TheReadoutsSayTrueThings(unittest.TestCase):

    def test_nothing_planted(self):
        self.assertEqual(L.readout("height", _land([])),
                         "Nothing is planted here yet.")

    def test_keystone(self):
        said = L.readout("keystone", _land(),
                         get_keystone=lambda pid: {1: 13, 2: 0, 3: 1}[pid])
        self.assertEqual(said, "The plants here recorded as food for the "
                               "most kinds of caterpillar: Trembling Aspen "
                               "(13), June Grass (1).")

    def test_neighbours(self):
        edges = [{"id": 10, "plant_id": 1}, {"id": 10, "plant_id": 2},
                 {"id": 11, "plant_id": 2}]
        self.assertEqual(L.readout("neighbours", _land(),
                                   fauna_edges=lambda ids: edges),
                         "2 kinds of animal are recorded with its plants: "
                         "1 with only one plant here, 1 with two or more.")

    def test_time_height_layers_drifts_colour(self):
        land = _land()
        self.assertEqual(L.readout("over_time", land),
                         "Of its kinds of plant, 1 reach their size in a year "
                         "or two, 1 in three to five years, and 1 take six "
                         "years or more.")
        self.assertIn("1 of its kinds of plant stay under half a metre",
                      L.readout("height", land))
        self.assertEqual(L.readout("layers", land),
                         "Its kinds of plant: 1 tree, 1 wildflower, "
                         "1 grass.")
        self.assertEqual(L.readout("drifts", land),
                         "1 of its plants are planted three or more times, "
                         "and 2 only once.")
        colour = L.readout("colour", land)
        self.assertIn("Nothing recorded in flower in September, October.",
                      colour)

    def test_sun_and_water(self):
        self.assertEqual(L.readout("sun", _land()),
                         "Of its 3 kinds of plant, 3 take full sun and 1 part "
                         "shade; many take more than one.")

    def test_shelter_and_what_was_there(self):
        land = _land(structures=[{"id": "brush_pile", "name": "Brush pile"}],
                     features=[{"properties": {"element_type":
                                               "existing_tree"}}])
        self.assertEqual(L.readout("shelter", land), "Placed here: Brush pile.")
        self.assertEqual(L.readout("already", land),
                         "Marked as already there: 1 tree.")

    def test_a_saved_design_is_read_from_its_file(self):
        from src.project_store import ProjectStore
        project = {"type": "FeatureCollection", "features": [],
                   "properties": {"name": "My yard"}}
        ProjectStore(project).add_plant(2, "Wild Bergamot", 53.5, -113.5)
        project["features"].append({"type": "Feature", "properties": {
            "element_type": "structure", "struct_def": {"name": "Bee log"}}})
        land = L.from_project(project, get_plant=ROWS.get)
        self.assertEqual(land["name"], "My yard")
        self.assertEqual([s["name"] for s in land["structures"]], ["Bee log"])
        self.assertEqual(len(land["placed"]), 1)


if __name__ == "__main__":
    unittest.main()

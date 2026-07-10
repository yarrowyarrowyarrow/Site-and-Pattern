"""
tests/test_field_study.py — the Field Study quiz layer (F48).

Covers src/field_study.py:
  1. Well-formed questions (4 options, in-range answer, non-empty prompt).
  2. Determinism: same seed → same quiz.
  3. Specialist questions — the answer is a real host, distractors are not.
  4. identify de-dup — repeated identify questions have distinct answers.
  5. Design-aware 'gap' question fires from a food-web status.
  6. identify only asks about plants whose photo passes ``image_available``
     (V2.25 — no photo-ID questions without a showable photo).
  7. Integration against the seeded temp DB.

Logic tests inject ``plants`` / ``specialists`` / ``image_available``
(DB-free); one integration test uses the temp-DB seed.
"""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_TMP_DIR = tempfile.mkdtemp(prefix="permadesign_quiz_test_")
import src.db.plants as _plants_mod  # noqa: E402
_plants_mod._DATA_DIR = _TMP_DIR
_plants_mod._DB_PATH = os.path.join(_TMP_DIR, "permadesign_test.db")

from src.field_study import generate_quiz  # noqa: E402


def _plants(n=20):
    out = []
    types = ["tree", "shrub", "wildflower", "grass"]
    for i in range(n):
        out.append({
            "common_name": f"Plant {i}", "scientific_name": f"Genus sp{i}",
            "plant_type": types[i % len(types)],
            "bloom_period": "Jun-Aug", "mature_height_meters": 1 + i % 5,
            "image_url": f"http://x/{i}.jpg" if i % 2 == 0 else "",
        })
    return out


def _specialists():
    return [
        {"fauna": "Monarch", "taxon": "lepidoptera",
         "plant": "Plant 0", "plant_id": 0},
        {"fauna": "Monarch", "taxon": "lepidoptera",
         "plant": "Plant 2", "plant_id": 2},
        {"fauna": "Sage Skipper", "taxon": "lepidoptera",
         "plant": "Plant 4", "plant_id": 4},
    ]


class TestQuizLogic(unittest.TestCase):

    def _quiz(self, **kw):
        # image_available accepts any URL here so the logic tests exercise
        # identify generation without a real image cache.
        return generate_quiz(seed=kw.pop("seed", 1), n=kw.pop("n", 5),
                             plants=_plants(), specialists=_specialists(),
                             image_available=kw.pop("image_available",
                                                    lambda u: bool(u)), **kw)

    def test_well_formed(self):
        for q in self._quiz(n=6):
            self.assertTrue(q["prompt"])
            self.assertEqual(len(q["options"]), 4)
            self.assertIn(q["answer_index"], range(4))
            self.assertIn(q["type"], ("identify", "specialist", "gap"))

    def test_deterministic(self):
        a = self._quiz(seed=42)
        b = self._quiz(seed=42)
        self.assertEqual([(q["prompt"], q["options"]) for q in a],
                         [(q["prompt"], q["options"]) for q in b])

    def test_specialist_answer_is_a_host(self):
        hosts = {"Monarch": {"Plant 0", "Plant 2"}, "Sage Skipper": {"Plant 4"}}
        found = False
        for q in generate_quiz(seed=3, n=8, plants=_plants(),
                               specialists=_specialists()):
            if q["type"] != "specialist":
                continue
            found = True
            answer = q["options"][q["answer_index"]]
            # the prompt names the fauna
            who = next(f for f in hosts if f in q["prompt"])
            self.assertIn(answer, hosts[who])
            for i, o in enumerate(q["options"]):
                if i != q["answer_index"]:
                    self.assertNotIn(o, hosts[who])
        self.assertTrue(found, "expected at least one specialist question")

    def test_identify_answers_distinct(self):
        ids = [q["options"][q["answer_index"]]
               for q in self._quiz(seed=5, n=8) if q["type"] == "identify"]
        self.assertEqual(len(ids), len(set(ids)))

    def test_gap_question_from_state(self):
        q = generate_quiz(placed_plants=[{"plant_id": 1}], seed=1, n=3,
                          plants=_plants(), specialists=_specialists(),
                          design_state={"status": "no_birds"})
        gaps = [x for x in q if x["type"] == "gap"]
        self.assertTrue(gaps, "a no_birds design should yield a gap question")
        ans = gaps[0]["options"][gaps[0]["answer_index"]]
        self.assertIn("bird", ans.lower())

    def test_identify_requires_showable_photo(self):
        # Only a fixed subset of photo URLs counts as "cached" — identify
        # questions must draw their target from exactly that pool.
        ok = {"http://x/4.jpg", "http://x/8.jpg", "http://x/12.jpg",
              "http://x/16.jpg", "http://x/0.jpg"}
        qs = self._quiz(seed=2, n=10, image_available=lambda u: u in ok)
        idents = [q for q in qs if q["type"] == "identify"]
        self.assertTrue(idents, "expected identify questions from the ok pool")
        for q in idents:
            self.assertIn(q["image_url"], ok)

    def test_identify_absent_when_no_photos_showable(self):
        qs = self._quiz(seed=3, n=8, image_available=lambda u: False)
        self.assertTrue(qs, "quiz should still exist (specialist questions)")
        self.assertFalse([q for q in qs if q["type"] == "identify"],
                         "no identify questions without showable photos")


class TestQuizIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from src.db.plants import init_db
        init_db()

    def test_real_db_quiz(self):
        # The temp environment has an empty image cache, so accept any URL —
        # the cache-gating logic itself is covered by the unit tests above.
        _any = {"image_available": (lambda u: bool(u))}
        q = generate_quiz(seed=7, n=5, **_any)
        self.assertEqual(len(q), 5)
        for x in q:
            self.assertEqual(len(x["options"]), 4)
            self.assertIn(x["answer_index"], range(4))
        # both question kinds appear from the seeded data
        kinds = {x["type"] for x in generate_quiz(seed=9, n=8, **_any)}
        self.assertIn("identify", kinds)
        self.assertIn("specialist", kinds)

    def test_real_db_quiz_cold_cache_has_no_identify(self):
        # Default image gate + empty cache dir ⇒ specialist-only quiz, never
        # a photo question without a photo.
        kinds = {x["type"] for x in generate_quiz(seed=9, n=8)}
        self.assertNotIn("identify", kinds)


if __name__ == "__main__":
    unittest.main()

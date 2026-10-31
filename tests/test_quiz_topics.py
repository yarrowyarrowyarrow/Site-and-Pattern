"""
tests/test_quiz_topics.py — Field Study by topic (F208, V3.40).

The owner found the quiz "very random" and asked for choice and grouping. These
hold the rules of src/quiz_topics.py on a small catalogue made up here: each
topic asks only its own kind of question, a wrong answer is never secretly
right, an animal is named by its English name and is one species, a focus
narrows the plants, and a topic that cannot fill the quiz says so rather than
borrowing another topic's questions.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import quiz_topics as Q  # noqa: E402


def _p(i, name, ptype, *, bloom="", sun="full_sun", water="low", photo=True):
    return {"id": i, "common_name": name, "scientific_name": f"Genus{i} sp{i}",
            "plant_type": ptype, "bloom_period": bloom,
            "sun_requirement": sun, "water_needs": water,
            "image_url": f"https://photos/{i}.jpg" if photo else ""}


PLANTS = [
    _p(1, "Blue Grama", "grass", bloom="Jul-Aug"),
    _p(2, "June Grass", "grass", bloom="Jun-Jul"),
    _p(3, "Rough Fescue", "grass", bloom="May-Jun"),
    _p(4, "Water Sedge", "sedge", bloom="Jun-Jul", water="medium,high"),
    _p(5, "Wild Bergamot", "wildflower", bloom="Jul-Aug", water="low,medium"),
    _p(6, "Prairie Crocus", "wildflower", bloom="Apr-May"),
    _p(7, "Smooth Aster", "wildflower", bloom="Aug-Sep",
       sun="full_sun,partial_shade"),
    _p(8, "Bunchberry", "groundcover", bloom="Jun-Jul",
       sun="partial_shade,full_shade", water="medium"),
    _p(9, "Trembling Aspen", "tree", bloom="Apr-May", water="low,medium"),
    _p(10, "Chokecherry", "shrub", bloom="May-Jun", water="low,medium"),
    _p(11, "Saskatoon Berry", "shrub", bloom="May", water="low,medium"),
    _p(12, "Pussy Willow", "shrub", bloom="Apr-May", water="medium,high"),
    _p(13, "Showy Milkweed", "wildflower", bloom="Jun-Aug", photo=False),
]


def _e(pid, fid, name, sci, taxon, rel, spec="generalist",
       source="acorn_sheldon_butterflies_ab"):
    return {"plant_id": pid, "fauna_id": fid, "name": name,
            "scientific_name": sci, "taxon": taxon, "relationship": rel,
            "specificity": spec, "source": source}


EDGES = [
    _e(9, 1, "Mourning Cloak", "Nymphalis antiopa", "lepidoptera",
       "larval_host"),
    _e(12, 1, "Mourning Cloak", "Nymphalis antiopa", "lepidoptera",
       "larval_host"),
    _e(5, 1, "Mourning Cloak", "Nymphalis antiopa", "lepidoptera", "nectar"),
    _e(10, 2, "Cedar Waxwing", "Bombycilla cedrorum", "bird", "fruit_food"),
    _e(11, 2, "Cedar Waxwing", "Bombycilla cedrorum", "bird", "fruit_food"),
    _e(5, 3, "Two-spotted Bumble Bee", "Bombus bimaculatus", "bee", "nectar"),
    _e(13, 4, "Monarch", "Danaus plexippus", "lepidoptera", "larval_host",
       "specialist"),
    _e(5, 5, "Andrena hippotes", "Andrena hippotes", "bee", "pollen"),
    _e(7, 6, "Mining Bees", "Andrena spp.", "bee", "pollen", "specialist"),
    _e(10, 7, "Forest Tent Caterpillar", "Malacosoma disstria",
       "lepidoptera", "larval_host"),
    # A specimen database's "host": where it was collected (V3.40).
    _e(9, 8, "Herald Moth", "Scoliopteryx libatrix", "lepidoptera",
       "larval_host", source="globi_scan_bugs_org"),
]


def _quiz(topic, **kw):
    kw.setdefault("plants", PLANTS)
    kw.setdefault("edges", EDGES)
    kw.setdefault("image_ok", lambda url: True)
    kw.setdefault("seed", 3)
    return Q.build_quiz(topic, **kw)


def _answer(q):
    return q["options"][q["answer_index"]]


class EveryTopicAsksItsOwnQuestions(unittest.TestCase):

    def test_each_topic_is_well_formed_and_of_its_own_kind(self):
        walk = [{"plant_id": 9}, {"plant_id": 10}, {"plant_id": 5}]
        for topic in Q.TOPIC_WORDS:
            qs = _quiz(topic, n=5, walk_plants=walk)
            self.assertTrue(qs, topic)
            for q in qs:
                self.assertEqual(len(q["options"]), 4, (topic, q))
                self.assertEqual(len(set(q["options"])), 4, (topic, q))
                self.assertTrue(0 <= q["answer_index"] < 4)
                self.assertTrue(q["prompt"] and q["explanation"])

    def test_a_grass_among_grasses(self):
        for q in _quiz("grasses", n=4):
            self.assertEqual(q["type"], "identify")
            for name in q["options"]:
                kind = next(p["plant_type"] for p in PLANTS
                            if p["common_name"] == name)
                self.assertIn(kind, Q.KINDS["grasses"], q)

    def test_a_plant_is_named_only_from_a_photo_on_this_computer(self):
        qs = _quiz("wildflowers", n=10,
                   image_ok=lambda url: url.endswith("/5.jpg"))
        self.assertEqual([_answer(q) for q in qs], ["Wild Bergamot"])

    def test_the_caterpillar_answer_is_a_host_and_no_other_option_is(self):
        hosts = {"Trembling Aspen", "Pussy Willow"}
        for seed in range(12):
            for q in _quiz("caterpillars", n=3, seed=seed):
                if "Mourning Cloak" not in q["prompt"]:
                    continue
                self.assertIn(_answer(q), hosts)
                self.assertEqual(len(set(q["options"]) & hosts), 1, q)

    def test_a_moth_named_for_its_caterpillar_reads_right(self):
        prompts = {q["prompt"] for seed in range(12)
                   for q in _quiz("caterpillars", n=3, seed=seed)}
        self.assertIn("Which of these plants is the Forest Tent "
                      "Caterpillar recorded eating?", prompts)
        self.assertNotIn("Forest Tent Caterpillar caterpillars",
                         " ".join(prompts))

    def test_caterpillar_food_comes_from_a_published_guide(self):
        """A quiz marks every other answer wrong, so a specimen database's
        "host", often only where the moth was collected, is not asked."""
        text = " ".join(q["prompt"] for seed in range(20)
                        for q in _quiz("caterpillars", n=5, seed=seed))
        self.assertNotIn("Herald Moth", text)
        q = next(q for seed in range(20)
                 for q in _quiz("caterpillars", n=5, seed=seed)
                 if "Mourning Cloak" in q["prompt"])
        self.assertIn("recorded eating", q["prompt"])

    def test_birds_and_bees(self):
        for q in _quiz("birds", n=3):
            self.assertIn("Cedar Waxwing", q["prompt"])
            self.assertIn(_answer(q), {"Chokecherry", "Saskatoon Berry"})
            self.assertIn("the fruit of", q["explanation"])
        for q in _quiz("bees", n=3):
            self.assertIn("Two-spotted Bumble Bee", q["prompt"])
            self.assertEqual(_answer(q), "Wild Bergamot")

    def test_animals_have_english_names_and_are_one_species(self):
        """WD-7, and "Mining Bees" (Andrena spp.) is a group, not "the"
        anything."""
        text = " ".join(q["prompt"] for t in ("bees", "depends", "caterpillars")
                        for s in range(8) for q in _quiz(t, n=5, seed=s))
        self.assertNotIn("Andrena hippotes", text)
        self.assertNotIn("Mining Bees", text)
        self.assertIn("Monarch", text)

    def test_when_it_flowers(self):
        for q in _quiz("flowering", n=6):
            month = q["prompt"].split(" in ")[1].rstrip("?")
            right = next(p for p in PLANTS if p["common_name"] == _answer(q))
            self.assertIn(month[:3], right["bloom_period"] + " "
                          + Q._span(Q._months(right)), q)

    def test_where_it_grows(self):
        for q in _quiz("growing", n=6):
            right = next(p for p in PLANTS if p["common_name"] == _answer(q))
            self.assertIn("takes", q["explanation"])
            words = q["prompt"]
            water = next(k for k, v in Q._WATER_WORDS.items()
                         if f"in {v} ground" in words)
            self.assertIn(water, right["water_needs"])

    def test_the_landscape_you_walked(self):
        walk = [{"plant_id": 9}, {"plant_id": 10}, {"plant_id": 12}]
        qs = _quiz("landscape", n=6, walk_plants=walk)
        grows = [q for q in qs if "grows in the landscape" in q["prompt"]]
        self.assertTrue(grows)
        for q in grows:
            self.assertIn(_answer(q), {"Trembling Aspen", "Chokecherry",
                                       "Pussy Willow"})
            others = set(q["options"]) - {_answer(q)}
            self.assertFalse(others & {"Trembling Aspen", "Chokecherry",
                                       "Pussy Willow"})


class FocusLengthAndHonesty(unittest.TestCase):

    def test_a_focus_narrows_the_plants(self):
        local = lambda: {"Genus5 sp5", "Genus6 sp6", "Genus7 sp7"}  # noqa: E731
        for q in _quiz("wildflowers", n=5, focus=Q.LOCAL, local=local):
            self.assertIn(_answer(q), {"Wild Bergamot", "Prairie Crocus",
                                       "Smooth Aster"})
        walk = lambda key: {"Blue Grama", "June Grass"}  # noqa: E731
        qs = _quiz("grasses", n=5, focus="mixedgrass_prairie", community=walk)
        self.assertEqual({_answer(q) for q in qs}, {"Blue Grama", "June Grass"})

    def test_too_few_questions_are_fewer_not_borrowed(self):
        qs = _quiz("depends", n=20)
        self.assertEqual(len(qs), 1, "one animal depends on a few plants here")
        self.assertEqual({q["type"] for q in qs}, {"depends"})
        self.assertEqual(_quiz("landscape", n=5, walk_plants=[]), [])

    def test_one_question_per_subject(self):
        subjects = [q["subject"] for q in _quiz("any_plant", n=20)]
        self.assertEqual(len(subjects), len(set(subjects)))

    def test_photo_status_counts_the_topics_plants(self):
        self.assertEqual(Q.photo_status("wildflowers", Q.ALL, PLANTS,
                                        lambda url: url.endswith("5.jpg")),
                         (1, 4))
        self.assertEqual(Q.photo_status("flowering", Q.ALL, PLANTS,
                                        lambda url: True), (0, 0))

    def test_an_unknown_topic_is_refused(self):
        with self.assertRaises(ValueError):
            _quiz("nonsense")

    def test_the_best_score_is_kept_by_share_then_count(self):
        store = {}
        get = lambda k, d="": store.get(k, d)  # noqa: E731
        put = store.__setitem__
        self.assertTrue(Q.record("birds", "all", 3, 5, get=get, put=put))
        self.assertFalse(Q.record("birds", "all", 5, 10, get=get, put=put))
        self.assertTrue(Q.record("birds", "all", 10, 10, get=get, put=put))
        self.assertFalse(Q.record("birds", "all", 5, 5, get=get, put=put))
        self.assertEqual(Q.best("birds", "all", get=get), (10, 10))
        self.assertEqual(Q.best("bees", "all", get=get), (0, 0))

    def test_the_groups_cover_every_topic_once(self):
        keys = [k for _g, _w, topics in Q.GROUPS for k, _t in topics]
        self.assertEqual(len(keys), len(set(keys)))
        self.assertLessEqual(Q.PHOTO_TOPICS, set(keys))


if __name__ == "__main__":
    unittest.main()

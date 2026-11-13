"""
tests/test_scene3d_creatures.py — which pollinator the 3D window's tools start
on (V3.44, F261; src/scene3d_creatures.py).

It was the first row of a list sorted by genus: *Agapostemon femoratus*, known
only by its Latin name, whether or not the design held a plant it uses, so
*Show its plants* lit nothing on most designs. Qt-free, and the catalogue is
injected, so this runs anywhere.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import scene3d_creatures as C                        # noqa: E402


def _bee(fid, name, sci):
    return (f"    {name}", {"taxon": "bee", "fid": fid, "kind": "bee",
                            "name": name, "scientific_name": sci})


ROWS = [
    ("── Agapostemon ──", None),
    _bee(1, "Agapostemon femoratus", "Agapostemon femoratus"),
    _bee(2, "A Sweat Bee", "Agapostemon texanus"),
    ("── Bombus ──", None),
    _bee(3, "Half-black Bumble Bee", "Bombus vagans"),
    _bee(4, "Tricoloured Bumble Bee", "Bombus ternarius"),
]


def _fed(*animals):
    """``animals_fed``'s shape: the animal on the most plants first."""
    return lambda _ids: [{"fauna_id": fid, "food": food}
                         for fid, food in animals]


class TheDefaultPollinator(unittest.TestCase):

    def test_it_is_one_the_design_feeds(self):
        index = C.default_row(ROWS, [10, 11], fed=_fed((4, True), (3, True)))
        self.assertEqual(ROWS[index][1]["name"], "Tricoloured Bumble Bee")

    def test_never_one_with_only_a_latin_or_a_generic_name(self):
        """WD-7: 820 of the catalogue's 1,144 animals carry only their Latin
        name, and "A Sweat Bee" is nobody's name for anything."""
        index = C.default_row(ROWS, [10], fed=_fed((1, True), (2, True),
                                                   (3, True)))
        self.assertEqual(ROWS[index][1]["name"], "Half-black Bumble Bee")

    def test_an_animal_the_design_only_shelters_is_not_fed_by_it(self):
        index = C.default_row(ROWS, [10], fed=_fed((4, False), (3, True)))
        self.assertEqual(ROWS[index][1]["fid"], 3)

    def test_an_empty_design_starts_on_the_first_with_an_english_name(self):
        for ids, fed in (([], _fed((4, True))), ([10], _fed()),
                         ([None], _fed((4, True)))):
            index = C.default_row(ROWS, ids, fed=fed)
            self.assertEqual(ROWS[index][1]["name"], "Half-black Bumble Bee")

    def test_a_heading_is_never_chosen(self):
        latin_only = ROWS[:3]
        index = C.default_row(latin_only, [10], fed=_fed())
        self.assertIsNotNone(latin_only[index][1])
        self.assertIsNone(C.default_row([], [10], fed=_fed()))
        self.assertIsNone(C.default_row([("── Bombus ──", None)], [],
                                        fed=_fed()))

    def test_a_fault_in_the_records_falls_back(self):
        def broken(_ids):
            raise RuntimeError("no such table")
        index = C.default_row(ROWS, [10], fed=broken)
        self.assertEqual(ROWS[index][1]["fid"], 3)


if __name__ == "__main__":
    unittest.main()

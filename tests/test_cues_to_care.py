"""
tests/test_cues_to_care.py — will the neighbours read it as cared for?
(F75, V2.56).

The app critiques a design ecologically and had never critiqued whether it
survives *socially*, which is what actually decides whether it is still there in
three years. Nassauer's cues to care: a wild planting is accepted when it carries
visible signs of human intention around it.

Qt-free throughout; the catalogue comes in through an injected ``get_plant``.
"""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_TMP = tempfile.mkdtemp(prefix="permadesign_cues_")
try:
    import src.db.plants as _plants_mod
    _plants_mod._DATA_DIR = _TMP
    _plants_mod._DB_PATH = os.path.join(_TMP, "t.db")
except Exception:  # pragma: no cover
    pass

from src import cues_to_care as cc  # noqa: E402
from src.project_store import ProjectStore  # noqa: E402

_CATALOGUE = {
    1: {"common_name": "Wild Bergamot", "mature_height_meters": 0.6,
        "plant_type": "perennial", "flower_color": "#a06fd0"},
    2: {"common_name": "Saskatoon", "mature_height_meters": 4.0,
        "plant_type": "shrub", "flower_color": "#ffffff"},
    3: {"common_name": "Blue Grama", "mature_height_meters": 0.4,
        "plant_type": "grass", "flower_color": "#cbbd80"},
}
_GP = lambda pid: _CATALOGUE.get(pid, {})            # noqa: E731


def _project(shapes=(), structures=(), boundary=False, plants=()):
    feats = []
    for st in shapes:
        feats.append({"type": "Feature",
                      "properties": {"element_type": "custom_shape",
                                     "shape_type": st},
                      "geometry": {"type": "Polygon", "coordinates": [[]]}})
    for sid in structures:
        feats.append({"type": "Feature",
                      "properties": {"element_type": "structure",
                                     "structure_id": sid},
                      "geometry": {"type": "Point", "coordinates": [0, 0]}})
    if boundary:
        feats.append({"type": "Feature",
                      "properties": {"element_type": "property_boundary"},
                      "geometry": {"type": "Polygon", "coordinates": [[]]}})
    p = {"type": "FeatureCollection", "features": feats, "properties": {}}
    store = ProjectStore(p)
    for pid, lat, n in plants:
        for i in range(n):
            store.add_plant(pid, _CATALOGUE.get(pid, {}).get("common_name", "x"),
                            lat + i * 1e-6, -114.07)
    return p


def _cue(project, key):
    return {c.key: c for c in cc.assess(project, get_plant=_GP)}[key]


class TestEachCueFiresIndependently(unittest.TestCase):
    """Every cue on its own: present when its evidence is there, absent when it
    is not, and never leaning on another cue's evidence."""

    def test_mown_edge(self):
        from src.lawn_zones import ZONE_TYPES
        self.assertFalse(_cue(_project(), cc.MOWN_EDGE).present)
        for shapes in (("Lawn Area",),
                       (ZONE_TYPES["lawn_remaining"]["label"],)):
            with self.subTest(shapes=shapes):
                self.assertTrue(_cue(_project(shapes=shapes),
                                     cc.MOWN_EDGE).present)
        self.assertTrue(_cue(_project(structures=("native_lawn_patch",)),
                             cc.MOWN_EDGE).present)

    def test_crisp_border(self):
        self.assertFalse(_cue(_project(), cc.CRISP_BORDER).present)
        self.assertTrue(_cue(_project(shapes=("Garden Bed",)),
                             cc.CRISP_BORDER).present)
        self.assertTrue(_cue(_project(boundary=True), cc.CRISP_BORDER).present)
        self.assertTrue(_cue(_project(structures=("fence",)),
                             cc.CRISP_BORDER).present)

    def test_visible_path(self):
        self.assertFalse(_cue(_project(), cc.VISIBLE_PATH).present)
        self.assertTrue(_cue(_project(shapes=("Pathway",)),
                             cc.VISIBLE_PATH).present)
        self.assertTrue(_cue(_project(shapes=("Patio / Deck",)),
                             cc.VISIBLE_PATH).present)

    def test_a_lawn_shape_is_not_a_border_and_a_bed_is_not_a_path(self):
        """The three shape cues must not read each other's evidence."""
        lawn = _project(shapes=("Lawn Area",))
        self.assertFalse(_cue(lawn, cc.CRISP_BORDER).present)
        self.assertFalse(_cue(lawn, cc.VISIBLE_PATH).present)
        bed = _project(shapes=("Garden Bed",))
        self.assertFalse(_cue(bed, cc.MOWN_EDGE).present)
        self.assertFalse(_cue(bed, cc.VISIBLE_PATH).present)


class TestHeightGrading(unittest.TestCase):
    def test_tall_at_the_back_reads_as_graded(self):
        p = _project(plants=((1, 51.0500, 4), (2, 51.0510, 3)))
        self.assertTrue(_cue(p, cc.HEIGHT_GRADED).present)

    def test_tall_at_the_front_is_a_finding(self):
        """Not merely 'not graded' — a screen of tall plants at the street is a
        real problem and gets its own sentence."""
        p = _project(plants=((2, 51.0500, 3), (1, 51.0510, 4)))
        cue = _cue(p, cc.HEIGHT_GRADED)
        self.assertFalse(cue.present)
        self.assertIn("front", cue.line.lower())

    def test_too_few_plants_has_no_opinion(self):
        """None, not False. A design with two plants is not badly graded — it
        is unjudgeable, and inventing a finding from absence is the thing this
        codebase keeps catching itself doing."""
        self.assertIsNone(_cue(_project(plants=((1, 51.05, 2),)),
                               cc.HEIGHT_GRADED).present)

    def test_unknown_heights_vote_on_nothing(self):
        p = _project(plants=((99, 51.0500, 4),))     # not in the catalogue
        self.assertIsNone(_cue(p, cc.HEIGHT_GRADED).present)


class TestShowyRepeat(unittest.TestCase):
    def test_a_repeated_showy_species_counts(self):
        cue = _cue(_project(plants=((1, 51.05, 4),)), cc.SHOWY_REPEAT)
        self.assertTrue(cue.present)
        self.assertIn("Wild Bergamot", cue.line)

    def test_below_the_threshold_does_not(self):
        p = _project(plants=((1, 51.05, cc.REPEAT_MIN - 1),))
        self.assertFalse(_cue(p, cc.SHOWY_REPEAT).present)

    def test_grasses_do_not_count_as_showy(self):
        """flower_colour buckets grasses, sedges and rushes as wind-pollinated
        and their swatch is the ABSENCE of a showy flower. Counting them would
        credit the design for a repeat nobody can see."""
        p = _project(plants=((3, 51.05, 8),))
        self.assertFalse(_cue(p, cc.SHOWY_REPEAT).present)

    def test_an_empty_design_has_no_opinion(self):
        self.assertIsNone(_cue(_project(), cc.SHOWY_REPEAT).present)


class TestTheSignIsAPromptNotACheck(unittest.TestCase):
    """Nothing in the app represents a sign, so inventing a geometric proxy for
    one would be a measurement of nothing wearing the costume of evidence."""

    def test_it_never_claims_present_or_absent(self):
        for project in (_project(), _project(shapes=("Garden Bed",))):
            self.assertIsNone(_cue(project, cc.SIGN).present)

    def test_it_still_says_something_useful(self):
        self.assertIn("sign", _cue(_project(), cc.SIGN).line.lower())


class TestTheFrontageAssumption(unittest.TestCase):
    """No road data exists anywhere in the app — osm_features fetches trees and
    buildings only. The sidewalk camera already assumes the south edge and says
    so in a comment; this makes the same assumption and states it."""

    def test_the_assumption_is_named_where_it_is_used(self):
        line = _cue(_project(), cc.MOWN_EDGE).line
        self.assertIn(cc.FRONTAGE_NOTE, line,
                      "the frontage assumption is used but not stated — an "
                      "assumption implied reads as a measurement")

    def test_only_the_mown_edge_depends_on_it(self):
        """The proof that a wrong guess costs one line rather than the feature:
        no other cue's line mentions the frontage at all."""
        for cue in cc.assess(_project(), get_plant=_GP):
            if cue.key == cc.MOWN_EDGE:
                continue
            with self.subTest(cue=cue.key):
                self.assertNotIn("frontage", (cue.line or "").lower())
                self.assertNotIn("south", (cue.line or "").lower())


class TestTheReadout(unittest.TestCase):
    def test_an_empty_design_produces_no_false_findings(self):
        """Three cues can be judged with nothing placed; the two that need
        plants must stay silent rather than reporting failure."""
        present, judged = cc.tally(_project(), get_plant=_GP)
        self.assertEqual(present, 0)
        self.assertEqual(judged, 3)

    def test_a_complete_design_scores_everything(self):
        from src.lawn_zones import ZONE_TYPES
        p = _project(
            shapes=("Lawn Area", "Garden Bed", "Pathway",
                    ZONE_TYPES["lawn_remaining"]["label"]),
            plants=((1, 51.0500, 4), (2, 51.0510, 3)))
        present, judged = cc.tally(p, get_plant=_GP)
        self.assertEqual((present, judged), (5, 5))
        self.assertEqual(cc.missing(p, get_plant=_GP), [])

    def test_lines_lead_with_absences(self):
        """A panel that recites what is already fine buries the one thing worth
        changing."""
        p = _project(shapes=("Lawn Area",))
        lines = cc.cue_lines(p, get_plant=_GP)
        self.assertTrue(lines)
        for line in lines:
            self.assertNotIn("There is a mown", line,
                             "a satisfied cue was listed among the findings")

    def test_the_sign_prompt_appears_when_there_is_room_for_it(self):
        p = _project(
            shapes=("Lawn Area", "Garden Bed", "Pathway"),
            plants=((1, 51.0500, 4), (2, 51.0510, 3)))
        self.assertTrue(any("sign" in ln.lower()
                            for ln in cc.cue_lines(p, get_plant=_GP)))

    def test_the_tally_excludes_what_it_could_not_judge(self):
        """Otherwise the ratio implies a verdict that was never reached."""
        _present, judged = cc.tally(_project(), get_plant=_GP)
        self.assertLess(judged, len(cc.assess(_project(), get_plant=_GP)))


if __name__ == "__main__":
    unittest.main()

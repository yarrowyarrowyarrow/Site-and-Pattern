"""
tests/test_try_another.py — Try another, front or back, about this plan
(PY-6, PY-7, PY-8; V3.29; docs/homeowner/07-plan-my-yard.md §4.3–§4.5).

The generator half plans the probe's 15 x 10 m yard five times (about forty
seconds); the controller half needs no database.
"""

import ast
import contextlib
import json
import os
import sys
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from src import plan_notes  # noqa: E402

try:
    import shapely  # noqa: F401
    _HAVE_SHAPELY = True
except ImportError:                                        # pragma: no cover
    _HAVE_SHAPELY = False


def _emitted_codes() -> set:
    """Every code ``llm_design`` can give a note, read from its source: the
    third argument or ``code=`` of each ``_add_warning`` call, the codes in
    the goal feedback's ``(message, code)`` pairs, and ``_water_code``'s."""
    with open(os.path.join(ROOT, "src", "llm_design.py"),
              encoding="utf-8") as fh:
        src = fh.read()
    tree = ast.parse(src)
    codes, uncoded = set(), []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name = getattr(node.func, "id", "")
        if name == "_add_warning" and node.lineno:
            arg = (node.args[2] if len(node.args) > 2 else next(
                (k.value for k in node.keywords if k.arg == "code"), None))
            if isinstance(arg, ast.Constant):
                codes.add(arg.value)
            elif arg is None:
                uncoded.append(node.lineno)
    for node in ast.walk(tree):
        if (isinstance(node, ast.Tuple) and len(node.elts) == 2
                and isinstance(node.elts[1], ast.Constant)
                and isinstance(node.elts[1].value, str)
                and node.elts[1].value in plan_notes.known_codes()
                | {"unbacked", "caveat", "no_goal_plant", "goal_pond",
                   "goal_water_only", "goal_added"}):
            codes.add(node.elts[1].value)
        if (isinstance(node, ast.IfExp)
                and isinstance(node.body, ast.Constant)
                and isinstance(node.orelse, ast.Constant)
                and isinstance(node.body.value, str)
                and node.body.value.startswith(("goal_", "no_pond"))):
            codes |= {node.body.value, node.orelse.value}
    return codes, uncoded


class TheNotesTable(unittest.TestCase):
    """PY-8: every code has simple words or is marked advanced-only."""

    def test_every_note_has_a_code(self):
        _codes, uncoded = _emitted_codes()
        # The definition's own ``code: str = ""`` is not a call; every call
        # names a code.
        self.assertEqual(uncoded, [], "a note with no code, at lines "
                                      f"{uncoded}")

    def test_every_code_is_in_the_table(self):
        codes, _ = _emitted_codes()
        self.assertTrue({"cover_short", "vine_alone", "repair",
                         "no_pond", "pond_full"} <= codes, codes)
        self.assertEqual(codes - plan_notes.known_codes(), set())

    def test_could_not_lines(self):
        lines = plan_notes.could_not([
            {"code": "vine_alone", "names": ["Wild Vetch", "Wild Vetch",
                                             "Wild Clematis"]},
            {"code": "repair"},
            {"code": "cover_short", "cover": 61, "target": 70,
             "reason": "no open ground left for the plants it uses"},
            {"code": "hard_to_find", "names": ["A", "B"]}])
        self.assertEqual(len(lines), plan_notes.MAX_COULD_NOT)
        self.assertIn("for Wild Vetch and Wild Clematis to climb yet, so "
                      "they lie", lines[0])
        self.assertTrue(lines[1].startswith("It covers about 61%"))

    def test_the_words_have_no_banned_word(self):
        for words in plan_notes.COULD_NOT.values():
            for bad in plan_notes.BANNED:
                self.assertNotIn(bad, words.lower())


@unittest.skipUnless(_HAVE_SHAPELY, "shapely not installed")
class TryAnotherAndFrontOrBack(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        sys.path.insert(0, os.path.join(ROOT, "scripts"))
        import probe_plan_my_yard as probe
        probe._db()
        cls.probe = probe
        from src.llm_design import generate_design_offline
        from src.onboarding import FIRST_RUN_GOALS

        def plan(**kw):
            return generate_design_offline(
                site_config=probe.SITE, boundary=probe.BOUNDARY,
                goals=list(FIRST_RUN_GOALS), cover=0.70, **kw).as_dict()
        cls.v0, cls.v0b, cls.v1 = plan(), plan(), plan(variant=1)
        cls.front, cls.back = plan(setting="front"), plan(setting="back")

    @staticmethod
    def _spots(project):
        return [(f["properties"]["plant_id"],
                 round(f["geometry"]["coordinates"][1], 7),
                 round(f["geometry"]["coordinates"][0], 7))
                for f in project["features"]
                if f["properties"].get("plant_id")]

    def _cover(self, project):
        from src import yard_overview
        return yard_overview.cover(project)["share"]

    # ── PY-6 ──
    def test_the_same_answers_give_the_same_plan(self):
        self.assertEqual(self._spots(self.v0), self._spots(self.v0b))

    def test_another_variant_is_another_plan_of_the_same_cover(self):
        a = {(la, ln) for _p, la, ln in self._spots(self.v0)}
        b = {(la, ln) for _p, la, ln in self._spots(self.v1)}
        self.assertLessEqual(len(a & b), 2 * len(a) / 3,
                             "less than a third of the positions moved")
        self.assertLess(abs(self._cover(self.v0) - self._cover(self.v1)),
                        0.05)

    # ── PY-7 ──
    def test_the_street_band_is_short_and_stays_put(self):
        from src import street_band
        from src.db.plants import get_plant
        band = street_band.Band(self.probe.BOUNDARY, "south")
        inside = [s for s in self._spots(self.front)
                  if band.contains(s[1], s[2])]
        self.assertTrue(inside, "nothing planted along the street")
        for pid, _la, _ln in inside:
            self.assertTrue(street_band.fits(get_plant(pid) or {}),
                            get_plant(pid)["common_name"])

    def test_a_front_yard_reads_as_cared_for(self):
        from src import cues_to_care
        self.assertGreaterEqual(cues_to_care.tally(self.front)[0],
                                cues_to_care.tally(self.v0)[0] + 1)

    def test_a_back_yard_may_add_a_brush_pile_and_no_more_than_two(self):
        made = [(f["properties"].get("struct_def") or {}).get("id")
                for f in self.back["features"]
                if f["properties"].get("element_type") == "structure"]
        self.assertIn("brush_pile", made)
        self.assertLessEqual(len(made), 2)
        self.assertNotIn("brush_pile", [
            (f["properties"].get("struct_def") or {}).get("id")
            for f in self.front["features"]
            if f["properties"].get("element_type") == "structure"])

    # ── PY-8 ──
    def test_about_this_plan(self):
        notes = self.v0["properties"].get("generation_notes") or []
        self.assertEqual(len(notes),
                         len(self.v0["properties"]["generation_warnings"]))
        s = plan_notes.summary(self.v0, notes, where="yard")
        self.assertTrue(s["heading"].startswith("Your plan: "))
        self.assertLessEqual(len(s["lines"]), plan_notes.MAX_LINES)
        self.assertLessEqual(len(s["could_not"]), plan_notes.MAX_COULD_NOT)
        text = plan_notes.as_text(s).lower()
        for bad in plan_notes.BANNED:
            self.assertNotIn(bad, text)
        self.assertLessEqual(len(text.splitlines()), 12)


class ThePersonsStreetSide(unittest.TestCase):
    """PY-7: the side the person said wins over the measured and assumed."""

    def test_told_wins(self):
        from src import frontage
        f = frontage.frontage_for_project(
            {"properties": {"site_config": {"street_side": "east"}},
             "features": []})
        self.assertEqual((f.side, f.told, f.known), ("east", True, True))
        self.assertIn("as you said", f.note)

    def test_no_answer_is_assumed(self):
        from src import frontage
        f = frontage.frontage_for_project({"features": []})
        self.assertFalse(f.known)


def _plant(pid, lat, lng, run=""):
    props = {"element_type": "plant", "plant_id": pid,
             "common_name": f"P{pid}", "feature_id": f"f{pid}{lat}"}
    if run:
        props["plan_run"] = run
    return {"type": "Feature", "properties": props,
            "geometry": {"type": "Point", "coordinates": [lng, lat]}}


class _Generated:
    def __init__(self, notes=()):
        self.notes = list(notes)

    def as_dict(self):
        return {"features": [_plant(11, 53.5, -113.5), _plant(12, 53.5001,
                                                              -113.5)],
                "properties": {"generation_warnings": ["English."],
                               "generation_notes": self.notes}}


class TheBarNotTheBox(unittest.TestCase):
    """PY-6, PY-8: after a plan, a line above the map; no modal box."""

    @classmethod
    def setUpClass(cls):
        try:
            import src.controllers.generation as gen
        except Exception as exc:  # noqa: BLE001
            raise unittest.SkipTest(f"needs PyQt6: {exc}")
        cls.gen = gen

    def setUp(self):
        from src.project_store import ProjectStore
        self.main = mock.MagicMock()
        self.main._project = {"type": "FeatureCollection", "properties": {},
                              "features": []}
        self.main._placed_plants = []
        self.main._store = ProjectStore(self.main._project,
                                        self.main._placed_plants)
        self.main._plant_info.return_value = (0.5, "wildflower", None)

        @contextlib.contextmanager
        def checkpoint(label=""):
            yield
        self.main._persistence.checkpoint = checkpoint
        self.ctl = self.gen.GenerationController(self.main)

    def test_no_modal_box_and_the_bar_names_the_plan(self):
        with mock.patch.object(self.gen, "QMessageBox") as box:
            self.ctl._render(_Generated([{"code": "repair"}]))
        box.information.assert_not_called()
        self.main.plan_bar.show_plan.assert_called_once()
        n, kinds, run = self.main.plan_bar.show_plan.call_args[0]
        self.assertEqual((n, kinds), (2, 2))
        self.assertTrue(run)
        props = self.main._project["properties"]
        self.assertEqual(props["generation_warnings"], ["English."])
        self.assertEqual(props["generation_notes"], [{"code": "repair"}])

    def test_try_another_is_the_next_variant_replacing_the_last(self):
        with mock.patch.object(self.gen, "QMessageBox"):
            self.ctl._render(_Generated())
        run = self.main._project["features"][0]["properties"]["plan_run"]
        self.ctl._answers = {"site_config": None, "boundary": None,
                             "goals": [], "variant": 0, "where": "yard",
                             "setting": "front", "street_side": "south"}
        with mock.patch.object(self.ctl, "_start") as start:
            self.ctl.try_another()
        kw = start.call_args.kwargs
        self.assertEqual(kw["variant"], 1)
        self.assertEqual(self.ctl._replacing, run)
        self.assertNotIn("where", kw)
        self.main.plan_bar.set_busy.assert_called_with(True)

    def test_try_another_before_any_plan_does_nothing(self):
        with mock.patch.object(self.ctl, "_start") as start:
            self.ctl.try_another()
        start.assert_not_called()


@unittest.skipUnless(os.environ.get("QT_QPA_PLATFORM"), "no Qt platform")
class TheWidgets(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        try:
            from PyQt6.QtWidgets import QApplication
        except Exception as exc:  # noqa: BLE001
            raise unittest.SkipTest(f"needs PyQt6: {exc}")
        cls.app = QApplication.instance() or QApplication(["try-another"])

    def test_the_bar_goes_with_its_plan(self):
        from src.plan_bar import PlanBar
        bar = PlanBar()
        bar.show_plan(95, 14, "run1")
        self.assertEqual(bar.label.text(), "Your plan: 95 plants of 14 kinds.")
        self.assertEqual([b.text() for b in bar.buttons],
                         ["Try another", "About this plan", "Undo"])
        bar.set_busy(True)
        self.assertEqual(bar.label.text(), "Planning another…")
        self.assertFalse(any(b.isEnabled() for b in bar.buttons))
        bar.set_busy(False)
        self.assertTrue(bar.label.text().startswith("Your plan"))
        bar.follow({"features": [_plant(1, 53.5, -113.5, run="run1")]})
        self.assertTrue(bar.isVisible())
        bar.follow({"features": []})
        self.assertFalse(bar.isVisible())
        bar.deleteLater()

    def test_about_is_not_modal(self):
        from src.plan_about import AboutPlan
        dlg = AboutPlan({"heading": "Your plan: 2 plants of 2 kinds",
                         "lines": ["2 plants of 2 kinds."],
                         "could_not": ["The pond had no room."]},
                        ["English note."])
        self.assertFalse(dlg.isModal())
        text = dlg.text()
        self.assertIn("What I could not do", text)
        self.assertIn("Design notes", text)
        dlg.deleteLater()

    def test_the_dialog_asks_front_or_back(self):
        from src.generate_design_dialog import GenerateDesignDialog
        dlg = GenerateDesignDialog(has_boundary=True, has_pin=True,
                                   areas={"yard_m2": 150.0},
                                   street_side="east")
        self.assertEqual(dlg.setting(), "front")
        self.assertEqual(dlg.street_side(), "east")
        dlg._yard["back"].setChecked(True)
        self.assertEqual(dlg.setting(), "back")
        self.assertFalse(dlg._street.isEnabled())
        dlg.deleteLater()


if __name__ == "__main__":
    unittest.main()

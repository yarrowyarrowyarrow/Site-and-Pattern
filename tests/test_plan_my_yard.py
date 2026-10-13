"""
tests/test_plan_my_yard.py — the planner keeps out what is drawn and replaces
its own last plan (V3.18, docs/homeowner/07-plan-my-yard.md).

PY-3: a drawn path, patio or building was kept out as one circle about its
centre reaching its farthest corner, so a 1 x 10 m path through a 15 x 10 m
yard took the plan from 42 plants to 18. ``docs/homeowner/prototypes/
plan_my_yard_probe.py`` measured it; the first test here is that probe's path
row, held.

PY-5: running the planner twice stacked a second identical plan on the first,
every plant on its own twin (the first-pass review's R2). Each run now stamps
its plants and structures with a ``plan_run``, and the next run removes that
run's features inside the same undo checkpoint it adds its own in.
"""

import contextlib
import json
import math
import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import src.db.plants as _plants_mod  # noqa: E402

_TMP = tempfile.mkdtemp(prefix="permadesign_plan_test_")


def _use_our_db():
    _plants_mod._DATA_DIR = _TMP
    _plants_mod._DB_PATH = os.path.join(_TMP, "t.db")
    _plants_mod.init_db()


from src.project_store import (  # noqa: E402
    ProjectStore, last_plan, without_plan,
)

# The probe's yard: 15 x 10 m in south Edmonton.
LAT0, LNG0 = 53.5232, -113.5263
KX = 111320 * math.cos(math.radians(LAT0))
KY = 111320.0
BOUNDARY = [[LAT0 + n / KY, LNG0 + e / KX]
            for e, n in ((0, 0), (15, 0), (15, 10), (0, 10))]
SITE = {"latitude": LAT0 + 5 / KY, "longitude": LNG0 + 7 / KX}


def _drawn(kind, x0, y0, x1, y1):
    ring = [[LNG0 + e / KX, LAT0 + n / KY]
            for e, n in ((x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0))]
    return {"type": "Feature",
            "geometry": {"type": "Polygon", "coordinates": [ring]},
            "properties": {"element_type": "custom_shape", "shape_type": kind}}


class TestAPathCostsOnlyItsOwnGround(unittest.TestCase):
    """The probe's path row: within 10% of the plan with nothing drawn, and
    nothing on the path."""

    @classmethod
    def setUpClass(cls):
        _use_our_db()

    def _plants(self, features):
        from src.llm_design import generate_design_offline
        from src.onboarding import FIRST_RUN_GOALS
        project = generate_design_offline(
            site_config=SITE, boundary=BOUNDARY, goals=list(FIRST_RUN_GOALS),
            density="balanced", existing_features=features).as_dict()
        out = []
        for f in project["features"]:
            if f["properties"].get("plant_id"):
                lng, lat = f["geometry"]["coordinates"]
                out.append(((lng - LNG0) * KX, (lat - LAT0) * KY))
        return out

    def test_a_one_metre_path_keeps_the_plan(self):
        open_yard = self._plants([])
        with_path = self._plants([_drawn("Pathway", 7, 0, 8, 10)])
        self.assertGreaterEqual(len(with_path), 0.9 * len(open_yard),
                                f"{len(with_path)} with the path, "
                                f"{len(open_yard)} without")
        on_path = [p for p in with_path if 7 <= p[0] <= 8]
        self.assertEqual(on_path, [])


# ── replace, not stack ──────────────────────────────────────────────────────

def _plant(pid, lat, lng, **props):
    p = {"element_type": "plant", "plant_id": pid, "common_name": f"P{pid}"}
    p.update(props)
    return {"type": "Feature",
            "geometry": {"type": "Point", "coordinates": [lng, lat]},
            "properties": p}


def _pond(lat, lng, **props):
    p = {"element_type": "structure", "struct_id": "pond", "size_m": 4.0,
         "struct_def": {"id": "pond", "size_m": 4.0}}
    p.update(props)
    return {"type": "Feature",
            "geometry": {"type": "Point", "coordinates": [lng, lat]},
            "properties": p}


class TestTheLastPlan(unittest.TestCase):

    def test_none_without_a_generated_plant(self):
        self.assertEqual(last_plan([_plant(1, 53.5, -113.5)]), ("", 0))
        self.assertEqual(last_plan([]), ("", 0))

    def test_the_most_recent_run_and_its_plants(self):
        feats = [_plant(1, 53.5, -113.5, plan_run="a"),
                 _plant(2, 53.5, -113.6, plan_run="b"),
                 _plant(3, 53.6, -113.5, plan_run="b"),
                 _pond(53.6, -113.6, plan_run="b"),
                 _plant(4, 53.7, -113.5)]                 # by hand, later
        self.assertEqual(last_plan(feats), ("b", 2))

    def test_a_plan_from_before_v3_18_is_known_by_its_group(self):
        feats = [_plant(1, 53.5, -113.5, pattern_kind="generated",
                        placement_group_id="g1"),
                 _plant(2, 53.5, -113.6, pattern_kind="generated",
                        placement_group_id="g2"),
                 _plant(3, 53.6, -113.5, pattern_kind="generated",
                        placement_group_id="g2"),
                 _plant(4, 53.7, -113.5, placement_group_id="g2")]
        self.assertEqual(last_plan(feats), ("legacy:g2", 2))
        kept = without_plan(feats, "legacy:g2")
        self.assertEqual([f["properties"]["plant_id"] for f in kept], [1, 4])

    def test_removing_a_plan_takes_its_structures_and_leaves_the_rest(self):
        project = {"features": [
            _plant(1, 53.5, -113.5, plan_run="a"),
            _pond(53.6, -113.6, plan_run="a"),
            _pond(53.6, -113.7),                           # placed by hand
            _plant(2, 53.7, -113.5)]}                      # placed by hand
        store = ProjectStore(project)
        self.assertEqual(store.remove_plan("a"), 2)
        self.assertEqual([f["properties"].get("plan_run")
                          for f in project["features"]], [None, None])
        self.assertEqual([r["plant_id"] for r in store.placed_plants], [2])
        self.assertEqual(store.check_consistency(), [])
        self.assertEqual(store.remove_plan(""), 0)

    def test_the_run_rides_on_the_plant_and_its_index_entry(self):
        store = ProjectStore({"features": []})
        rec = store.add_plant(7, "P7", 53.5, -113.5, plan_run="r1")
        self.assertEqual(rec["plan_run"], "r1")
        self.assertEqual(store.features[0]["properties"]["plan_run"], "r1")
        self.assertEqual(store.records_from_features()[0]["plan_run"], "r1")


class _Generated:
    """What the worker hands ``_render``: two plants and a pond."""

    def __init__(self, shift=0.0):
        self._feats = [_plant(11, 53.50 + shift, -113.50),
                       _plant(12, 53.50 + shift, -113.5001),
                       _pond(53.5002 + shift, -113.50)]

    def as_dict(self):
        return {"features": json.loads(json.dumps(self._feats)),
                "properties": {}}


class TestRunningItTwice(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        try:
            import src.controllers.generation as gen  # PyQt6 at import
        except Exception as exc:  # noqa: BLE001
            raise unittest.SkipTest(f"generation controller needs PyQt6: {exc}")
        cls.gen = gen

    def setUp(self):
        self.main = mock.MagicMock()
        self.main._project = {"type": "FeatureCollection", "properties": {},
                              "features": [_plant(99, 53.6, -113.6)]}
        self.main._placed_plants = []
        self.main._store = ProjectStore(self.main._project,
                                        self.main._placed_plants)
        self.main._store.rebuild_index()
        self.main._plant_info.return_value = (0.5, "wildflower", None)
        self.checkpoints = []

        @contextlib.contextmanager
        def checkpoint(label=""):
            before = json.dumps(self.main._project["features"], sort_keys=True)
            yield
            self.checkpoints.append(
                (before, json.dumps(self.main._project["features"],
                                    sort_keys=True)))

        self.main._persistence.checkpoint = checkpoint
        self.ctl = self.gen.GenerationController(self.main)

    def _run(self, shift, *, replace):
        self.ctl._replacing = (last_plan(self.main._project["features"])[0]
                               if replace else "")
        with mock.patch.object(self.gen, "QMessageBox"):
            self.ctl._render(_Generated(shift))
        self.ctl._finish_ui()

    def _kinds(self):
        out = {"generated": 0, "by_hand": 0, "ponds": 0}
        for f in self.main._project["features"]:
            p = f["properties"]
            if p["element_type"] == "structure":
                out["ponds"] += 1
            elif p.get("plan_run"):
                out["generated"] += 1
            else:
                out["by_hand"] += 1
        return out

    def test_twice_is_one_plan(self):
        self._run(0.0, replace=False)
        self._run(0.001, replace=True)
        self.assertEqual(self._kinds(),
                         {"generated": 2, "by_hand": 1, "ponds": 1})
        self.assertEqual(self.main._store.check_consistency(), [])
        self.main._persistence.redraw.assert_called_once()

    def test_add_to_it_instead_keeps_both(self):
        self._run(0.0, replace=False)
        self._run(0.001, replace=False)
        self.assertEqual(self._kinds(),
                         {"generated": 4, "by_hand": 1, "ponds": 2})

    def test_a_replace_is_one_undo_step_back_to_the_first_plan(self):
        self._run(0.0, replace=False)
        first = json.dumps(self.main._project["features"], sort_keys=True)
        self._run(0.001, replace=True)
        before, after = self.checkpoints[-1]
        self.assertEqual(before, first)       # undo restores exactly this
        self.assertNotEqual(after, first)

    def test_an_empty_result_replaces_nothing(self):
        self._run(0.0, replace=False)
        kept = json.dumps(self.main._project["features"], sort_keys=True)

        class _Empty:
            def as_dict(self):
                return {"features": [], "properties": {}}

        self.ctl._replacing = last_plan(self.main._project["features"])[0]
        with mock.patch.object(self.gen, "QMessageBox"):
            self.ctl._render(_Empty())
        self.assertEqual(json.dumps(self.main._project["features"],
                                    sort_keys=True), kept)


class TestTheDialogSaysSo(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        try:
            from PyQt6.QtWidgets import QApplication
        except Exception as exc:  # noqa: BLE001
            raise unittest.SkipTest(f"needs PyQt6: {exc}")
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        cls.app = QApplication.instance() or QApplication(["plan-tests"])

    def _dialog(self, last):
        from src.generate_design_dialog import GenerateDesignDialog
        return GenerateDesignDialog(has_boundary=True, has_pin=True,
                                    last_plan=last)

    def _ok_text(self, dlg):
        from PyQt6.QtWidgets import QDialogButtonBox
        box = dlg.findChild(QDialogButtonBox)
        return box.button(QDialogButtonBox.StandardButton.Ok).text()

    def test_a_first_plan_replaces_nothing(self):
        dlg = self._dialog(0)
        self.assertFalse(dlg.replace_last())
        self.assertEqual(self._ok_text(dlg), "Generate")

    def test_a_second_plan_says_it_replaces_the_first(self):
        from PyQt6.QtWidgets import QLabel
        dlg = self._dialog(42)
        self.assertTrue(dlg.replace_last())
        self.assertEqual(self._ok_text(dlg), "Replace my plan")
        words = " ".join(w.text() for w in dlg.findChildren(QLabel))
        self.assertIn("Your last plan (42 plants) will be replaced", words)
        self.assertIn("Plants you placed yourself stay", words)

    def test_add_to_it_instead(self):
        dlg = self._dialog(42)
        dlg._add_check.setChecked(True)
        self.assertFalse(dlg.replace_last())
        self.assertEqual(self._ok_text(dlg), "Add to my plan")


if __name__ == "__main__":
    unittest.main()

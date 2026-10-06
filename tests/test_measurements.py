"""
tests/test_measurements.py — a measurement is part of the design (F215,
V3.11), the selection box catches one, one Delete is one undo step, and a
boundary's corner handles can be switched off (F216).

The owner: "I noticed undo does not work for measurements, they also do not get
selected when I go to select an area. Also the dots on the corner points of a
boundary to move it around should be able to toggle on and off just like the
area and side length label."

Until V3.11 a measurement lived only in the map page: no bridge call, no
feature, so undo (a snapshot of the design's features) could not see one and
Ctrl+Z straight after measuring undid whatever came before it; nothing saved
one and nothing cleared one. Four layers here:

  * the feature and its loader, Qt-free (``src/measurements.py``,
    ``src/project.py``);
  * the handlers, with a fake window and a checkpoint that counts, Qt-free;
  * undo itself through the real ``PersistenceController``, when PyQt6 is
    installed;
  * the real map page in headless Chromium (``html/measure_probe.html``,
    the harness ``tests/test_boundary_press.py`` uses), when Chromium is.
"""

import json
import os
import pathlib
import re
import subprocess
import sys
import tempfile
import unittest
from contextlib import contextmanager
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import measurements as M                              # noqa: E402
from src.controllers.map_events import MapEventRouter, name_boundaries  # noqa: E402
from src.project import (load_project, new_project,             # noqa: E402
                         project_to_map_data, save_project)

_ROOT = pathlib.Path(__file__).resolve().parent.parent
A, B = [53.5461, -113.4938], [53.5463, -113.4930]


def _has_qt() -> bool:
    try:
        import PyQt6.QtWidgets  # noqa: F401
        return True
    except Exception:                                         # noqa: BLE001
        return False


def _boundary(bid, name=None, **props):
    p = {"element_type": "property_boundary", "boundary_id": bid,
         "color": "green", "show_lengths": True, "show_area": True}
    if name is not None:
        p["name"] = name
    p.update(props)
    ring = [[-113.494, 53.546], [-113.493, 53.546], [-113.493, 53.547],
            [-113.494, 53.546]]
    return {"type": "Feature", "geometry": {"type": "Polygon", "coordinates": [ring]},
            "properties": p}


class TestTheFeature(unittest.TestCase):

    def test_a_measurement_is_a_two_point_line_in_lng_lat(self):
        f = M.measurement_feature("m1", [A, B])
        self.assertEqual(f["geometry"], {"type": "LineString",
                                         "coordinates": [[A[1], A[0]], [B[1], B[0]]]})
        self.assertEqual(f["properties"], {"element_type": "measurement",
                                           "measurement_id": "m1"})

    def test_bad_input_adds_nothing(self):
        p = new_project()
        for coords in ([A], [A, B, A], [["x", 1], B], None, [[1], [2]]):
            with self.subTest(coords=coords):
                self.assertFalse(M.add_measurement(p, "m1", coords))
        self.assertFalse(M.add_measurement(p, "", [A, B]))
        self.assertEqual(p["features"], [])

    def test_the_same_id_twice_adds_one(self):
        p = new_project()
        self.assertTrue(M.add_measurement(p, "m1", [A, B]))
        self.assertFalse(M.add_measurement(p, "m1", [A, B]))
        self.assertEqual(len(p["features"]), 1)

    def test_removing_takes_only_those(self):
        p = new_project()
        p["features"].append(_boundary("b1"))
        for mid in ("m1", "m2", "m3"):
            M.add_measurement(p, mid, [A, B])
        self.assertEqual(M.remove_measurements(p, ["m1", "m3", "nope"]), 2)
        kinds = [(f["properties"]["element_type"],
                  f["properties"].get("measurement_id")) for f in p["features"]]
        self.assertEqual(kinds, [("property_boundary", None), ("measurement", "m2")])
        self.assertEqual(M.remove_measurements(p, ["m1"]), 0)

    def test_the_loader_hands_the_map_lat_lng(self):
        p = new_project()
        M.add_measurement(p, "m1", [A, B])
        self.assertEqual(project_to_map_data(p)["measurements"],
                         [{"id": "m1", "points": [A, B]}])

    def test_it_survives_save_and_reopen(self):
        p = new_project()
        M.add_measurement(p, "m1", [A, B])
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "t.perma.geojson")
            save_project(p, path)
            again = load_project(path)
        self.assertEqual(project_to_map_data(again)["measurements"],
                         [{"id": "m1", "points": [A, B]}])

    def test_a_boundarys_switch_and_name_reach_the_map(self):
        p = new_project()
        p["features"] += [_boundary("b1"),
                          _boundary("b2", name="Private lot", show_handles=False)]
        bds = project_to_map_data(p)["boundaries"]
        self.assertEqual([(b["showHandles"], b["name"]) for b in bds],
                         [(True, ""), (False, "Private lot")])


class _Persistence:
    """A checkpoint that counts the outermost entries, as the real one pushes
    one undo step per outermost checkpoint."""

    def __init__(self):
        self.depth, self.steps = 0, []

    @contextmanager
    def checkpoint(self, label=""):
        if self.depth == 0:
            self.steps.append(label)
        self.depth += 1
        try:
            yield
        finally:
            self.depth -= 1


class _Main:
    def __init__(self, features=()):
        self._project = {"features": list(features)}
        self._persistence = _Persistence()
        self.modified = 0
        self.names = []
        self.map_widget = mock.Mock()

    def _mark_modified(self):
        self.modified += 1

    def _set_mode_label(self, *_a):
        pass


class TestTheHandlers(unittest.TestCase):

    def test_added_and_removed_mark_the_design_modified(self):
        main = _Main()
        router = MapEventRouter(main)
        router._on_measurement_added("m1", [A, B])
        self.assertEqual(len(main._project["features"]), 1)
        router._on_measurements_removed(["m1"])
        self.assertEqual(main._project["features"], [])
        self.assertEqual(main.modified, 2)
        self.assertEqual(main._persistence.steps, ["measure", "remove measurement"])

    def test_one_delete_runs_each_kinds_handler_inside_one_checkpoint(self):
        shape = {"type": "Feature", "geometry": {"type": "Polygon", "coordinates": [[]]},
                 "properties": {"element_type": "custom_shape", "shape_id": "s1"}}
        struct = {"type": "Feature",
                  "geometry": {"type": "Point", "coordinates": [-113.49, 53.54]},
                  "properties": {"element_type": "structure", "struct_id": "pond"}}
        main = _Main([_boundary("b1"), _boundary("b2"), shape, struct,
                      M.measurement_feature("m1", [A, B])])
        router = MapEventRouter(main)
        plants = []
        router._on_plants_removed_batch = lambda j: plants.append(json.loads(j))
        router._on_measurement_added("m2", [A, B])
        main._persistence.steps.clear()
        router._on_selection_deleted(json.dumps({
            "plants": [{"plantId": 42, "lat": 53.5, "lng": -113.5}],
            "boundaries": ["b1"], "structures": [["sx", "pond", 53.54, -113.49]],
            "shapes": ["s1"], "measurements": ["m1", "m2"], "sunpath": True}))
        self.assertEqual(main._persistence.steps, ["delete selection"])
        self.assertEqual(plants, [[{"plantId": 42, "lat": 53.5, "lng": -113.5}]])
        left = [f["properties"].get("boundary_id") or f["properties"]["element_type"]
                for f in main._project["features"]]
        self.assertEqual(left, ["b2"])
        main.map_widget.clear_sun_path.assert_called_once()

    def test_a_payload_it_cannot_read_does_nothing(self):
        main = _Main([_boundary("b1")])
        router = MapEventRouter(main)
        for bad in ("", "nonsense", "[1, 2]"):
            router._on_selection_deleted(bad)
        self.assertEqual(len(main._project["features"]), 1)
        self.assertEqual(main.modified, 0)

    def test_corner_handles_are_saved_with_the_colour_and_labels(self):
        main = _Main([_boundary("b1")])
        MapEventRouter(main)._on_boundary_props_changed("b1", "blue", True, False, False)
        props = main._project["features"][0]["properties"]
        self.assertEqual((props["color"], props["show_area"], props["show_handles"]),
                         ("blue", False, False))

    def test_naming_sets_and_clears(self):
        p = {"features": [_boundary("b1"), _boundary("b2"), _boundary("b3", name="Old")]}
        self.assertTrue(name_boundaries(p, ["b1", "b2"], "Private lot"))
        self.assertFalse(name_boundaries(p, ["b1"], "Private lot"))   # no change
        self.assertTrue(name_boundaries(p, ["b3"], ""))
        names = [f["properties"].get("name") for f in p["features"]]
        self.assertEqual(names, ["Private lot", "Private lot", None])


class _Action:
    def setEnabled(self, *_a):
        pass


@unittest.skipUnless(_has_qt(), "PyQt6 not installed in this env")
class TestUndo(unittest.TestCase):
    """Through the real PersistenceController, with the map's redraw stubbed:
    the pattern of tests/test_snapshot_undo.py."""

    def setUp(self):
        from src.project_store import ProjectStore
        import src.controllers.persistence as pmod

        class Main:
            AUTOSAVE_INTERVAL_MS = 300000

            def __init__(self):
                self._store = ProjectStore()
                self._project = self._store.project
                self._modified = False
                self._undo_stack, self._redo_stack, self._max_undo = [], [], 50
                self._act_undo = self._act_redo = _Action()
                self.toolbar = None
                self.map_widget = mock.Mock()
                self.site_panel = mock.Mock()

            def statusBar(self):
                return mock.Mock()

            def setWindowTitle(self, *_a):
                pass

            def windowTitle(self):
                return "t"

            def _sync_planning_panel(self):
                pass

            def _set_mode_label(self, *_a):
                pass

        self.main = Main()
        ctl = pmod.PersistenceController(self.main)
        ctl.render_project_to_map = lambda **k: None
        ctl._apply_view_state = lambda v: None
        self.main._persistence = ctl
        self.main._mark_modified = ctl._mark_modified
        self.main._push_undo = ctl._push_undo
        self.ctl = ctl
        self.router = MapEventRouter(self.main)

    def _kinds(self):
        return [f["properties"]["element_type"] for f in self.main._project["features"]]

    def test_undo_takes_a_measurement_back_and_redo_returns_it(self):
        self.main._project["features"].append(_boundary("b1"))
        self.router._on_measurement_added("m1", [A, B])
        self.assertEqual(self._kinds(), ["property_boundary", "measurement"])
        self.ctl._do_undo()
        # The measurement goes, and only it: until V3.11 this Ctrl+Z undid
        # whatever came before the measurement.
        self.assertEqual(self._kinds(), ["property_boundary"])
        self.ctl._do_redo()
        self.assertEqual(self._kinds(), ["property_boundary", "measurement"])

    def test_one_delete_of_many_kinds_is_one_undo_step(self):
        feats = self.main._project["features"]
        feats += [_boundary("b1"), _boundary("b2")]
        self.router._on_measurement_added("m1", [A, B])
        depth = len(self.main._undo_stack)
        self.router._on_selection_deleted(json.dumps({
            "boundaries": ["b1", "b2"], "measurements": ["m1"]}))
        self.assertEqual(self._kinds(), [])
        self.assertEqual(len(self.main._undo_stack), depth + 1)
        self.ctl._do_undo()
        self.assertEqual(sorted(self._kinds()),
                         ["measurement", "property_boundary", "property_boundary"])

    def test_naming_is_one_step_and_a_cancel_is_none(self):
        from PyQt6.QtWidgets import QInputDialog
        self.main._project["features"] += [_boundary("b1"), _boundary("b2")]
        with mock.patch.object(QInputDialog, "getText", return_value=("", False)):
            self.router._on_boundary_name_requested(["b1", "b2"], "")
        self.assertEqual(self.main._undo_stack, [])
        with mock.patch.object(QInputDialog, "getText",
                               return_value=("  City   park land ", True)):
            self.router._on_boundary_name_requested(["b1", "b2"], "")
        self.assertEqual(len(self.main._undo_stack), 1)
        names = [f["properties"].get("name") for f in self.main._project["features"]]
        self.assertEqual(names, ["City park land", "City park land"])
        self.main.map_widget.set_boundary_names.assert_called_once_with(
            ["b1", "b2"], "City park land")


class TestTheRedrawAndANewDesign(unittest.TestCase):
    """Source guards: what open, undo and New must do now that measurements
    are the design's."""

    def test_the_redraw_clears_then_loads_them(self):
        src = (_ROOT / "src" / "controllers" / "persistence.py").read_text(encoding="utf-8")
        body = src[src.index("def render_project_to_map"):]
        body = body[:body.index("\n    def ", 10)]
        self.assertIn("clear_measure()", body)
        self.assertIn("load_measurement(", body)
        self.assertLess(body.index("clear_measure()"), body.index("load_measurement("))

    def test_a_new_design_clears_them_and_the_notes(self):
        src = (_ROOT / "src" / "app.py").read_text(encoding="utf-8")
        body = src[src.index("self._project      = project_io.new_project(name)"):]
        body = body[:body.index("self.setWindowTitle(")]
        self.assertIn("clear_measure()", body)
        self.assertIn("clear_annotations()", body)

    def test_the_page_tells_python_and_never_on_a_load(self):
        tools = (_ROOT / "html" / "map" / "04-tools.js").read_text(encoding="utf-8")
        click = tools[tools.index("function handleMeasureClick"):
                      tools.index("function _cancelMeasureStart")]
        self.assertIn("bridge.onMeasurementAdded", click)
        load = tools[tools.index("function loadMeasurement"):
                     tools.index("function _removeMeasureById")]
        self.assertNotIn("bridge.", load)


def _run_probe():
    from tests.test_boundary_press import _run_probe as run
    return run("measure_probe.html")


def _chromium():
    from tests.test_scene3d_render import _find_chromium
    return _find_chromium()


@unittest.skipIf(_chromium() is None, "no Chromium binary (set CHROME= to run this gate)")
class OnTheMap(unittest.TestCase):
    m = None

    @classmethod
    def setUpClass(cls):
        cls.m = _run_probe()

    def setUp(self):
        self.assertNotIn("error", self.m, self.m.get("error"))

    def test_a_measurement_tells_python_once_with_its_two_points(self):
        self.assertEqual(self.m["measure"]["sent"], 1)
        self.assertEqual(self.m["measure"]["points"], 2)
        self.assertEqual(self.m["measure"]["layers"], 1)

    def test_esc_after_one_click_leaves_nothing_behind(self):
        e = self.m["esc"]
        self.assertTrue(e["dot_after_first"])
        self.assertFalse(e["dot_after_esc"], "the first click's dot stayed")
        self.assertFalse(e["start_after_esc"])
        self.assertEqual(e["added_by_one_click"], 0,
                         "the next click finished a measurement from the old start")

    def test_the_selection_box_catches_it_and_shows_it(self):
        mq = self.m["marquee"]
        self.assertEqual(mq["selected"], 1)
        self.assertEqual((mq["weight"], mq["dashed"]), (4, False))
        self.assertEqual(mq["after_clear"], {"weight": 2, "dashed": True})
        self.assertEqual(mq["by_its_middle"], 1, "a box round its label missed it")
        self.assertEqual(mq["hidden"], 0, "a hidden measurement was selected")

    def test_shift_click_selects_it_and_presses_nothing_else(self):
        self.assertEqual(self.m["shift_click"], {"selected": 1, "boundary_edit": None})

    def test_one_delete_is_one_call_with_everything_in_it(self):
        d = self.m["delete"]
        self.assertEqual(d["kinds"], ["boundary", "measure", "plant"])
        self.assertEqual(d["calls"], ["onSelectionDeleted"])
        self.assertEqual(d["plants"], 1)
        self.assertEqual(d["boundaries"], ["b1"])
        self.assertEqual(d["measurements"], [self.m["measure"]["id"]])
        self.assertEqual(d["left"], {"layers": 0, "boundaries": 0, "plants": 0})

    def test_drawn_from_the_design_it_says_nothing(self):
        self.assertEqual(self.m["load"], {"layers": 1, "sent": 0})
        self.assertEqual(self.m["clear"], {"layers": 0, "sent": 0})

    def test_a_right_click_removes_just_it_and_says_so(self):
        self.assertEqual(self.m["right_click"], {"removed": [["m-saved"]], "layers": 0})

    def test_the_boundary_menu_has_the_switch_and_the_name(self):
        labels = [re.sub(r"^✓", "", t) for t in self.m["menu"]["labels"] if t]
        self.assertEqual(labels, ["Edge Labels", "Area Label", "Corner Handles",
                                  "Name…", "Remove Boundary", "Color:"])
        self.assertTrue(self.m["menu"]["swatches_follow_colour"],
                        "the colour swatches are not under their label")

    def test_corner_handles_off(self):
        off = self.m["handles_off"]
        self.assertEqual(off["sent"], [["b1", "green", True, True, False]])
        self.assertEqual(off["press"], {"edit": None, "handles": 0})
        self.assertFalse(off["pointer"], "the pointer still says it can be pressed")
        self.assertEqual(off["shift_selects"], 1)
        self.assertTrue(off["menu_still"], "no way back to switch them on")

    def test_corner_handles_on_show_now_and_on_a_press(self):
        on = self.m["handles_on"]
        self.assertEqual(on["sent"], [["b1", "green", True, True, True]])
        self.assertEqual((on["edit_now"], on["handles"], on["press"]), ("b1", 4, "b1"))

    def test_saved_off_it_loads_off(self):
        self.assertEqual(self.m["loaded_off"], {"edit": None, "flag": False})

    def test_name_asks_python_with_the_id_and_the_name_now(self):
        self.assertEqual(self.m["name"], {"asked": [[["b2"], "Private lot"]],
                                          "stored": "Private lot"})


if __name__ == "__main__":
    unittest.main()

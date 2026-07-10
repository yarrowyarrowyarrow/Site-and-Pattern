"""
tests/test_undo_redo.py — characterisation suite for the undo/redo engine
(V1.63, the tests the Chunk 5c extraction was waiting on).

Drives the REAL MainWindow (offscreen Qt + WebEngine) through every
undoable action type — boundary, structure, contour, hedgerow, custom
shape, plant place/move/group-move — then undoes and redoes each,
asserting the project features round-trip exactly (the redo engine
re-appends the very features undo stashed) and the ProjectStore stays
consistent throughout. Skips cleanly when Qt/WebEngine can't construct
a MainWindow in this environment (same policy as test_app_smoke).
"""

import copy
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
# Root-only CI containers need Chromium's sandbox off; harmless elsewhere
# and only effective if this module is the first to initialise WebEngine.
os.environ.setdefault("QTWEBENGINE_CHROMIUM_FLAGS",
                      "--no-sandbox --disable-gpu")

_TMP_DIR = tempfile.mkdtemp(prefix="permadesign_undo_test_")
try:
    import src.db.plants as _plants_mod
    _plants_mod._DATA_DIR = _TMP_DIR
    _plants_mod._DB_PATH = os.path.join(_TMP_DIR, "t.db")
    import src.settings as _settings_mod
    _settings_mod._CONFIG_PATH = os.path.join(_TMP_DIR, "config.json")
except Exception:  # pragma: no cover
    pass


def _make_window():
    from PyQt6.QtCore import Qt
    from PyQt6.QtWidgets import QApplication
    QApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts)
    import PyQt6.QtWebEngineWidgets  # noqa: F401
    app = QApplication.instance() or QApplication(["permadesign-tests"])
    from src.app import MainWindow
    return app, MainWindow()


try:
    _APP, _WIN_PROBE = _make_window()
    _WIN_PROBE.deleteLater()
    _HAVE_WINDOW = True
    _SKIP_REASON = ""
except Exception as exc:  # noqa: BLE001
    _HAVE_WINDOW = False
    _SKIP_REASON = f"MainWindow construction failed here: {exc}"


@unittest.skipUnless(_HAVE_WINDOW, _SKIP_REASON)
class TestUndoRedoRoundTrips(unittest.TestCase):
    """Each action: place → undo (feature gone) → redo (feature restored,
    byte-identical) → undo again (gone)."""

    def setUp(self):
        self._app, self.w = _make_window()

    def tearDown(self):
        # Tear the WebEngine pages down promptly and clear _modified first —
        # closeEvent otherwise blocks forever on its modal "unsaved changes"
        # QMessageBox under a headless run. (A Chromium teardown segfault at
        # interpreter exit can still occur in dbus-less containers; it
        # pre-exists for any QWebEngineView there — test_map3d_widget alone
        # reproduces it — and doesn't affect test results.)
        self.w._modified = False
        self.w.close()
        self.w.deleteLater()
        for _ in range(5):
            self._app.processEvents()

    # ── helpers ──────────────────────────────────────────────────────────

    def _features(self):
        # Strip the stash key — it's undo-stack bookkeeping, not state.
        return [f for f in self.w._project["features"]]

    def _round_trip(self, n_before, n_added=1):
        """After a placement: undo removes, redo restores identically."""
        snapshot = copy.deepcopy(self._features())
        self.assertEqual(len(snapshot), n_before + n_added)
        self.w._do_undo()
        self.assertEqual(len(self._features()), n_before)
        self.w._do_redo()
        self.assertEqual(self._features(), snapshot)
        self.w._do_undo()
        self.assertEqual(len(self._features()), n_before)
        self.assertEqual(self.w._store.check_consistency(), [])

    # ── placements ───────────────────────────────────────────────────────

    def test_boundary_round_trip(self):
        loads = []
        self.w.map_widget.load_boundary = lambda bd: loads.append(bd)
        n = len(self._features())
        self.w._map_events._on_boundary_complete(
            "b1", [[53.5, -113.5], [53.501, -113.5], [53.501, -113.499]],
            "green")
        snapshot = copy.deepcopy(self._features())
        self.w._do_undo()
        self.assertEqual(len(self._features()), n)
        self.w._do_redo()
        self.assertEqual(self._features(), snapshot)
        self.assertEqual(len(loads), 1)            # redo re-rendered it
        self.assertEqual(loads[0]["id"], "b1")

    def test_structure_round_trip(self):
        loads = []
        self.w.map_widget.load_structure = (
            lambda sd, lat, lng: loads.append((sd, lat, lng)))
        n = len(self._features())
        self.w._map_events._on_structure_placed(
            "bee_hotel", "Bee hotel", 53.5005, -113.4995, 0.5)
        self._round_trip(n)
        # The redo render used the feature's own struct_def.
        self.assertEqual(len(loads), 1)
        self.assertEqual(loads[0][0].get("id"), "bee_hotel")

    def test_existing_tree_round_trip(self):
        n = len(self._features())
        self.w._map_events._on_structure_placed(
            "existing_tree", "Existing tree", 53.5006, -113.4994, 8.0)
        self._round_trip(n)

    def test_contour_round_trip(self):
        n = len(self._features())
        self.w._map_events._on_contour_complete(
            json.dumps([[53.5, -113.5], [53.5002, -113.4998]]),
            660.0, "#795548")
        self._round_trip(n)

    def test_hedgerow_round_trip(self):
        n = len(self._features())
        self.w._map_events._on_hedgerow_complete(
            "h1", json.dumps([[53.5, -113.5], [53.5003, -113.5]]),
            "willow", "hedge", 30.0, 10)
        self._round_trip(n)

    def test_custom_shape_round_trip(self):
        n = len(self._features())
        self.w._map_events._on_shape_complete(
            "s1", json.dumps([[53.5, -113.5], [53.5002, -113.5],
                              [53.5002, -113.4998]]),
            "Bed", "Custom", "#4caf50", "#2e7d32", 0.25, "", 25.0, 0.0)
        self._round_trip(n)

    def test_plant_round_trip_keeps_group_id(self):
        n = len(self._features())
        self.w._on_plant_placed(1, "Saskatoon", 53.5, -113.5)
        group = self.w._placed_plants[-1]["placement_group_id"]
        self.assertTrue(group)
        self._round_trip(n)
        # Redo restored the group id (regression: the historical redo
        # dropped it).
        self.w._do_redo()
        self.assertEqual(self.w._placed_plants[-1]["placement_group_id"],
                         group)

    # ── moves ────────────────────────────────────────────────────────────

    def test_plant_move_round_trip(self):
        self.w._on_plant_placed(1, "Saskatoon", 53.5, -113.5)
        self.w._map_events._on_plant_moved("m1", 1, 53.5, -113.5,
                                           53.6, -113.6)
        self.assertEqual(self.w._placed_plants[-1]["lat"], 53.6)
        self.w._do_undo()
        self.assertEqual(self.w._placed_plants[-1]["lat"], 53.5)
        self.w._do_redo()
        self.assertEqual(self.w._placed_plants[-1]["lat"], 53.6)
        self.assertEqual(self.w._store.check_consistency(), [])

    def test_selection_move_round_trip(self):
        self.w._on_plant_placed(1, "A", 53.5, -113.5)
        self.w._on_plant_placed(2, "B", 53.51, -113.51)
        originals = [{"markerId": "m1", "plantId": 1,
                      "lat": 53.5, "lng": -113.5},
                     {"markerId": "m2", "plantId": 2,
                      "lat": 53.51, "lng": -113.51}]
        moved = [{"markerId": "m1", "lat": 53.52, "lng": -113.52},
                 {"markerId": "m2", "lat": 53.53, "lng": -113.53}]
        self.w._map_events._on_selection_moved(
            json.dumps(originals), json.dumps(moved))
        self.assertEqual(self.w._placed_plants[0]["lat"], 53.52)
        self.w._do_undo()
        self.assertEqual(self.w._placed_plants[0]["lat"], 53.5)
        self.assertEqual(self.w._placed_plants[1]["lat"], 53.51)
        self.w._do_redo()
        self.assertEqual(self.w._placed_plants[0]["lat"], 53.52)
        self.assertEqual(self.w._placed_plants[1]["lat"], 53.53)
        self.assertEqual(self.w._store.check_consistency(), [])

    # ── stack semantics ──────────────────────────────────────────────────

    def test_new_action_clears_redo(self):
        self.w._on_plant_placed(1, "A", 53.5, -113.5)
        self.w._do_undo()
        self.assertTrue(self.w._redo_stack)
        self.w._on_plant_placed(2, "B", 53.51, -113.51)
        self.assertFalse(self.w._redo_stack)
        self.assertFalse(self.w._act_redo.isEnabled())

    def test_undo_everything_then_redo_everything(self):
        self.w._on_plant_placed(1, "A", 53.5, -113.5)
        self.w._map_events._on_structure_placed(
            "bee_hotel", "Bee hotel", 53.5005, -113.4995, 0.5)
        self.w._map_events._on_hedgerow_complete(
            "h1", json.dumps([[53.5, -113.5], [53.5003, -113.5]]),
            "willow", "hedge", 30.0, 10)
        snapshot = copy.deepcopy(self.w._project["features"])
        for _ in range(3):
            self.w._do_undo()
        self.assertEqual(self.w._project["features"], [])
        for _ in range(3):
            self.w._do_redo()
        self.assertEqual(self.w._project["features"], snapshot)
        self.assertEqual(self.w._store.check_consistency(), [])


@unittest.skipUnless(_HAVE_WINDOW, _SKIP_REASON)
class TestSnapshotUndoExhaustive(unittest.TestCase):
    """V1.81: the snapshot catch-all that makes undo exhaustive. Each gap
    action (bulk placement, removal, edit, clear) records one "snapshot"
    undo step; undo reverses it and redo reapplies it, with the ProjectStore
    staying consistent throughout."""

    def setUp(self):
        self._app, self.w = _make_window()

    def tearDown(self):
        self.w._modified = False
        self.w.close()
        self.w.deleteLater()
        for _ in range(5):
            self._app.processEvents()

    # ── helpers ──────────────────────────────────────────────────────────

    def _features(self):
        return [f for f in self.w._project["features"]]

    def _assert_snapshot_top(self):
        self.assertTrue(self.w._undo_stack)
        self.assertEqual(self.w._undo_stack[-1]["action"], "snapshot")

    def _reversal_round_trip(self, n_before, n_after):
        """A decorated action took features n_before → n_after. Undo restores
        n_before; redo reapplies n_after; leave it undone + consistent."""
        self.assertEqual(len(self._features()), n_after)
        self._assert_snapshot_top()
        self.w._do_undo()
        self.assertEqual(len(self._features()), n_before)
        self.w._do_redo()
        self.assertEqual(len(self._features()), n_after)
        self.w._do_undo()
        self.assertEqual(len(self._features()), n_before)
        self.assertEqual(self.w._store.check_consistency(), [])

    def _place_plant_community(self):
        """Two plants tagged as one community instance (precondition for the
        polyculture-removal test) placed through the store, undo cleared."""
        from src.project_store import store_for
        s = store_for(self.w)
        for pid, name, lat in ((1, "A", 53.50), (2, "B", 53.501)):
            s.add_plant(pid, name, lat, -113.5, placement_group_id="pg1",
                        polyculture_name="Mound",
                        polyculture_center_lat=53.5,
                        polyculture_center_lng=-113.5)
        self.w._clear_undo()

    # ── bulk placement ───────────────────────────────────────────────────

    def test_pattern_placement_round_trip(self):
        n = len(self._features())
        self.w._map_events._on_pattern_placed(
            1, "Saskatoon", 1.0, "shrub", "",
            json.dumps([[53.5, -113.5], [53.501, -113.5], [53.502, -113.5]]),
            "row")
        self._assert_snapshot_top()
        self._reversal_round_trip(n, n + 3)

    def test_community_click_round_trip(self):
        # A single click in polyculture mode drops a whole community; undo must
        # remove ALL members, not just the central one (the reported bug).
        self.w._current_mode = 'polyculture'
        self.w._pending_polyculture = {
            "name": "Pollinator Mound",
            "members": [
                {"plant_id": 1, "common_name": "A", "offset_x": 0, "offset_y": 0},
                {"plant_id": 2, "common_name": "B", "offset_x": 2, "offset_y": 0},
                {"plant_id": 3, "common_name": "C", "offset_x": 0, "offset_y": 2},
            ],
        }
        n = len(self._features())
        self.w._map_events._on_polyculture_click(53.5, -113.5)
        self._assert_snapshot_top()
        self._reversal_round_trip(n, n + 3)

    # ── removals ─────────────────────────────────────────────────────────

    def test_plant_removal_round_trip(self):
        self.w._on_plant_placed(1, "Saskatoon", 53.5, -113.5)
        self.w._clear_undo()
        n = len(self._features())
        self.w._map_events._on_plant_removed("m1", 1, 53.5, -113.5)
        self._reversal_round_trip(n, n - 1)

    def test_batch_removal_round_trip(self):
        self.w._on_plant_placed(1, "A", 53.5, -113.5)
        self.w._on_plant_placed(2, "B", 53.51, -113.51)
        self.w._clear_undo()
        n = len(self._features())
        self.w._map_events._on_plants_removed_batch(json.dumps([
            {"plantId": 1, "lat": 53.5, "lng": -113.5},
            {"plantId": 2, "lat": 53.51, "lng": -113.51}]))
        self._reversal_round_trip(n, n - 2)

    def test_polyculture_removal_round_trip(self):
        self._place_plant_community()
        n = len(self._features())
        self.w._map_events._on_polyculture_removed("Mound", 53.5, -113.5)
        self._reversal_round_trip(n, n - 2)

    def test_structure_removal_round_trip(self):
        self.w._map_events._on_structure_placed(
            "bee_hotel", "Bee hotel", 53.5005, -113.4995, 0.5)
        self.w._clear_undo()
        n = len(self._features())
        self.w._map_events._on_structure_removed(
            "m1", "bee_hotel", 53.5005, -113.4995)
        self._reversal_round_trip(n, n - 1)

    def test_boundary_removal_round_trip(self):
        self.w.map_widget.load_boundary = lambda *a, **k: None
        self.w._map_events._on_boundary_complete(
            "b1", [[53.5, -113.5], [53.501, -113.5], [53.501, -113.499]],
            "green")
        self.w._clear_undo()
        n = len(self._features())
        self.w._map_events._on_boundary_removed("b1")
        self._reversal_round_trip(n, n - 1)

    def test_contour_removal_round_trip(self):
        pts = json.dumps([[53.5, -113.5], [53.5002, -113.4998]])
        self.w._map_events._on_contour_complete(pts, 660.0, "#795548")
        self.w._clear_undo()
        n = len(self._features())
        self.w._map_events._on_contour_removed(pts, 660.0, "#795548")
        self._reversal_round_trip(n, n - 1)

    def test_contour_clear_round_trip(self):
        self.w._map_events._on_contour_complete(
            json.dumps([[53.5, -113.5], [53.5002, -113.4998]]), 660.0,
            "#795548")
        self.w._map_events._on_contour_complete(
            json.dumps([[53.5, -113.4], [53.5002, -113.398]]), 661.0,
            "#795548")
        self.w._clear_undo()
        n = len(self._features())
        self.w._map_events._on_contour_cleared()
        self._reversal_round_trip(n, n - 2)

    def test_hedgerow_removal_round_trip(self):
        self.w._map_events._on_hedgerow_complete(
            "h1", json.dumps([[53.5, -113.5], [53.5003, -113.5]]),
            "willow", "hedge", 30.0, 10)
        self.w._clear_undo()
        n = len(self._features())
        self.w._map_events._on_hedgerow_removed(
            "h1", json.dumps([[53.5, -113.5], [53.5003, -113.5]]))
        self._reversal_round_trip(n, n - 1)

    def test_shape_removal_round_trip(self):
        self.w._map_events._on_shape_complete(
            "s1", json.dumps([[53.5, -113.5], [53.5002, -113.5],
                              [53.5002, -113.4998]]),
            "Bed", "Custom", "#4caf50", "#2e7d32", 0.25, "", 25.0, 0.0)
        self.w._clear_undo()
        n = len(self._features())
        self.w._map_events._on_shape_removed("s1")
        self._reversal_round_trip(n, n - 1)

    def test_auto_terrain_clear_round_trip(self):
        self.w._project["features"].append({
            "type": "Feature",
            "geometry": {"type": "MultiLineString",
                         "coordinates": [[[-113.5, 53.5], [-113.4, 53.5]]]},
            "properties": {"element_type": "auto_contour", "elevation_m": 675},
        })
        self.w._store.rebuild_index()
        self.w._clear_undo()
        n = len(self._features())
        self.w._map_events._on_auto_terrain_cleared()
        self._reversal_round_trip(n, n - 1)

    # ── edits (feature count unchanged; content changes) ─────────────────

    def test_boundary_props_edit_round_trip(self):
        self.w.map_widget.load_boundary = lambda *a, **k: None
        self.w._map_events._on_boundary_complete(
            "b1", [[53.5, -113.5], [53.501, -113.5], [53.501, -113.499]],
            "green")
        self.w._clear_undo()

        def _color():
            for f in self._features():
                if f["properties"].get("boundary_id") == "b1":
                    return f["properties"].get("color")
            return None
        self.assertEqual(_color(), "green")
        self.w._map_events._on_boundary_props_changed("b1", "blue", False, False)
        self.assertEqual(_color(), "blue")
        self._assert_snapshot_top()
        self.w._do_undo()
        self.assertEqual(_color(), "green")
        self.w._do_redo()
        self.assertEqual(_color(), "blue")
        self.w._do_undo()
        self.assertEqual(self.w._store.check_consistency(), [])

    def test_shape_height_edit_round_trip(self):
        self.w._map_events._on_shape_complete(
            "s1", json.dumps([[53.5, -113.5], [53.5002, -113.5],
                              [53.5002, -113.4998]]),
            "Bed", "Custom", "#4caf50", "#2e7d32", 0.25, "", 25.0, 0.0)
        self.w._clear_undo()

        def _etype():
            for f in self._features():
                if f["properties"].get("shape_id") == "s1":
                    return f["properties"].get("element_type")
            return None
        self.assertEqual(_etype(), "custom_shape")
        self.w._map_events._on_shape_height_changed("s1", 3.0)
        self.assertEqual(_etype(), "canopy_footprint")   # now casts shade
        self._assert_snapshot_top()
        self.w._do_undo()
        self.assertEqual(_etype(), "custom_shape")
        self.w._do_redo()
        self.assertEqual(_etype(), "canopy_footprint")
        self.w._do_undo()
        self.assertEqual(self.w._store.check_consistency(), [])

    # ── annotations ──────────────────────────────────────────────────────

    def test_annotation_add_round_trip(self):
        from PyQt6 import QtWidgets
        orig = QtWidgets.QInputDialog.getText
        QtWidgets.QInputDialog.getText = staticmethod(
            lambda *a, **k: ("Wet corner", True))
        try:
            n = len(self._features())
            self.w._map_events._on_annotate_requested(53.5, -113.5)
        finally:
            QtWidgets.QInputDialog.getText = orig
        self._reversal_round_trip(n, n + 1)

    def test_annotation_remove_round_trip(self):
        self.w._project["features"].append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [-113.5, 53.5]},
            "properties": {"element_type": "annotation",
                           "annotation_id": "ann_1", "text": "note"},
        })
        self.w._clear_undo()
        n = len(self._features())
        self.w._map_events._on_annotation_removed("ann_1")
        self._reversal_round_trip(n, n - 1)

    # ── analysis-overlay toggles (Part 3) ────────────────────────────────

    def test_wind_shadow_toggle_round_trip(self):
        self.w._clear_undo()
        self.assertFalse(getattr(self.w, "_wind_shadow_on", False))
        self.w._map_events._on_wind_shadow_toggled(True)
        self.assertTrue(self.w._wind_shadow_on)
        self._assert_snapshot_top()
        self.w._do_undo()
        self.assertFalse(self.w._wind_shadow_on)
        self.w._do_redo()
        self.assertTrue(self.w._wind_shadow_on)
        self.w._do_undo()
        self.assertFalse(self.w._wind_shadow_on)

    def test_sun_path_round_trip(self):
        self.w._clear_undo()
        self.w._pending_sun_config = {"date": "2026-06-21", "date_label": "Jun 21"}
        self.w._map_events._on_sun_anchor_placed(53.5, -113.5)
        self.assertIsNotNone(self.w._active_sun_state)
        self._assert_snapshot_top()
        self.w._do_undo()
        self.assertIsNone(self.w._active_sun_state)
        self.w._do_redo()
        self.assertIsNotNone(self.w._active_sun_state)

    def test_site_pin_round_trip(self):
        self.w._clear_undo()

        def _pin_lat():
            return (self.w._project["properties"]
                    .get("site_config", {}).get("latitude"))
        self.w._map_events._on_site_pin_placed(53.5, -113.5, "Home")
        self.assertEqual(_pin_lat(), 53.5)
        self._assert_snapshot_top()
        self.w._do_undo()
        self.assertIsNone(_pin_lat())
        self.w._do_redo()
        self.assertEqual(_pin_lat(), 53.5)

    def test_shade_toggle_round_trip(self):
        # Drive the worker's ready callback directly (no elevation fetch).
        self.w._clear_undo()
        self.w._shade_overlay_active = False
        self.w._persistence.begin_shade_undo()
        self.w._map_events._on_shade_ready(
            {"data_url": "data:image/png;base64,iVBORw0KGgo=",
             "bbox": {"north": 53.6, "south": 53.5,
                      "east": -113.4, "west": -113.5}})
        self.assertTrue(self.w._shade_overlay_active)
        self._assert_snapshot_top()
        self.w._do_undo()
        self.assertFalse(self.w._shade_overlay_active)
        self.w._do_redo()
        self.assertTrue(self.w._shade_overlay_active)

    def test_redo_toolbar_button_enabled_state(self):
        # The toolbar Redo button greys out unless the redo stack is non-empty.
        self.w._clear_undo()
        self.assertFalse(self.w.toolbar._act_redo.isEnabled())
        self.w._on_plant_placed(1, "Saskatoon", 53.5, -113.5)
        self.assertTrue(self.w.toolbar._act_undo.isEnabled())
        self.assertFalse(self.w.toolbar._act_redo.isEnabled())
        self.w._do_undo()
        self.assertTrue(self.w.toolbar._act_redo.isEnabled())
        self.w._do_redo()
        self.assertFalse(self.w.toolbar._act_redo.isEnabled())

    # ── engine semantics ─────────────────────────────────────────────────

    def test_checkpoint_noop_records_nothing(self):
        self.w._clear_undo()
        with self.w._persistence.checkpoint("nothing"):
            pass
        self.assertEqual(self.w._undo_stack, [])

    def test_checkpoint_reentrant_single_entry(self):
        self.w._clear_undo()
        p = self.w._persistence
        with p.checkpoint("outer"):
            with p.checkpoint("inner"):
                self.w._project["features"].append({
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": [-113.5, 53.5]},
                    "properties": {"element_type": "annotation",
                                   "annotation_id": "a", "text": "t"}})
        self.assertEqual(len(self.w._undo_stack), 1)
        self.assertEqual(self.w._undo_stack[-1]["action"], "snapshot")

    def test_snapshot_new_action_clears_redo(self):
        self.w._clear_undo()
        self.w._map_events._on_annotate_requested  # noqa: B018 (keep ref)
        with self.w._persistence.checkpoint("add a"):
            self.w._project["features"].append({
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [-113.5, 53.5]},
                "properties": {"element_type": "annotation",
                               "annotation_id": "a", "text": "t"}})
        self.w._do_undo()
        self.assertTrue(self.w._redo_stack)
        with self.w._persistence.checkpoint("add b"):
            self.w._project["features"].append({
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [-113.4, 53.6]},
                "properties": {"element_type": "annotation",
                               "annotation_id": "b", "text": "t"}})
        self.assertFalse(self.w._redo_stack)


if __name__ == "__main__":
    unittest.main()

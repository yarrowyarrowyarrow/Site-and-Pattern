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
        _app, self.w = _make_window()

    def tearDown(self):
        self.w.deleteLater()

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


if __name__ == "__main__":
    unittest.main()

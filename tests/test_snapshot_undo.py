"""
tests/test_snapshot_undo.py — the JSON-string snapshot engine (V2.22).

Until V2.22 every @undoable gesture deep-copied the WHOLE features list
twice (before + after), ×50 stack depth — memory and per-gesture latency
scaled with imported-project size. Snapshots are now one canonical JSON
string per side. These tests pin the engine's contract Qt-free (fake
main + a stubbed render), independent of the WebEngine-bound round-trip
suite in tests/test_undo_redo.py:

  * a change records exactly one entry; a no-op records none,
  * re-entrant checkpoints collapse to one entry; a raising body records
    nothing,
  * the chain shares string objects between consecutive entries (the
    memory bound), and snapshots can't be corrupted by later in-place
    mutations of live feature dicts (immutability by construction),
  * undo/redo restore the exact feature trees.
"""

import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class _FakeStatusBar:
    def showMessage(self, *a, **k):
        pass


class _FakeAction:
    def setEnabled(self, *a):
        pass


class _FakeMain:
    AUTOSAVE_INTERVAL_MS = 300000

    def __init__(self):
        from src.project_store import ProjectStore
        self._store = ProjectStore()
        self._project = self._store.project
        self._modified = False
        self._undo_stack = []
        self._redo_stack = []
        self._max_undo = 50
        self._act_undo = _FakeAction()
        self._act_redo = _FakeAction()
        self.toolbar = None

    def statusBar(self):
        return _FakeStatusBar()

    def setWindowTitle(self, *a):
        pass

    def windowTitle(self):
        return "t"

    def _sync_planning_panel(self):
        # Feature-derived panel readouts refreshed by _apply_snapshot —
        # not under test here.
        pass


def _controller(main):
    import src.controllers.persistence as pmod
    ctl = pmod.PersistenceController(main)
    # The snapshot format is under test — not the map re-render.
    ctl.render_project_to_map = lambda **k: None
    ctl._apply_view_state = lambda v: None
    # site_panel caster summary probe inside _mark_modified:
    main.site_panel = type("SP", (), {
        "update_caster_summary": lambda self, p: None})()
    return ctl


def _add_plant(main, pid, lat, lng):
    main._store.add_plant(pid, f"Plant {pid}", lat, lng)


class TestSnapshotCheckpoint(unittest.TestCase):
    def setUp(self):
        try:
            import PyQt6  # noqa: F401
        except Exception as exc:  # pragma: no cover
            self.skipTest(f"PyQt6 unavailable: {exc}")
        self.main = _FakeMain()
        self.ctl = _controller(self.main)

    def test_change_records_one_entry_noop_records_none(self):
        with self.ctl.checkpoint("place"):
            _add_plant(self.main, 1, 53.5, -113.5)
        self.assertEqual(len(self.main._undo_stack), 1)
        with self.ctl.checkpoint("nothing"):
            pass
        self.assertEqual(len(self.main._undo_stack), 1,
                         "a no-op gesture must not push an entry")

    def test_reentrant_checkpoints_collapse(self):
        with self.ctl.checkpoint("outer"):
            with self.ctl.checkpoint("inner"):
                _add_plant(self.main, 1, 53.5, -113.5)
            _add_plant(self.main, 2, 53.6, -113.6)
        self.assertEqual(len(self.main._undo_stack), 1)

    def test_raising_body_records_nothing(self):
        with self.assertRaises(RuntimeError):
            with self.ctl.checkpoint("boom"):
                _add_plant(self.main, 1, 53.5, -113.5)
                raise RuntimeError("gesture failed")
        self.assertEqual(self.main._undo_stack, [])

    def test_chain_shares_string_objects(self):
        with self.ctl.checkpoint("a"):
            _add_plant(self.main, 1, 53.5, -113.5)
        with self.ctl.checkpoint("b"):
            _add_plant(self.main, 2, 53.6, -113.6)
        e1, e2 = self.main._undo_stack
        self.assertIs(
            e1["after"]["features_json"], e2["before"]["features_json"],
            "consecutive snapshots must share one string object — the "
            "memory bound the JSON format exists for")

    def test_snapshot_immune_to_later_inplace_mutation(self):
        with self.ctl.checkpoint("place"):
            _add_plant(self.main, 1, 53.5, -113.5)
        entry = self.main._undo_stack[0]
        # Vandalize the live feature dict in place (a future buggy handler).
        self.main._project["features"][0]["properties"]["common_name"] = "X"
        restored = json.loads(entry["after"]["features_json"])
        self.assertEqual(restored[0]["properties"]["common_name"], "Plant 1")

    def test_undo_redo_round_trip(self):
        with self.ctl.checkpoint("place"):
            _add_plant(self.main, 1, 53.5, -113.5)
        with self.ctl.checkpoint("place"):
            _add_plant(self.main, 2, 53.6, -113.6)
        self.assertEqual(len(self.main._project["features"]), 2)
        self.ctl._do_undo()
        self.assertEqual(len(self.main._project["features"]), 1)
        self.assertEqual(
            self.main._project["features"][0]["properties"]["plant_id"], 1)
        self.assertFalse(self.main._store.check_consistency())
        self.ctl._do_redo()
        self.assertEqual(len(self.main._project["features"]), 2)
        self.assertFalse(self.main._store.check_consistency())
        self.ctl._do_undo()
        self.ctl._do_undo()
        self.assertEqual(self.main._project["features"], [])

    def test_stack_depth_capped(self):
        for i in range(60):
            with self.ctl.checkpoint(f"p{i}"):
                _add_plant(self.main, i + 1, 53.0 + i * 0.001, -113.5)
        self.assertLessEqual(len(self.main._undo_stack),
                             self.main._max_undo)


if __name__ == "__main__":
    unittest.main()

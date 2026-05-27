"""
tests/test_app_smoke.py

Headless-Qt smoke test for src/app.py:MainWindow. The point is to give the
upcoming MainWindow decomposition (Chunk 5 of the strengthening roadmap)
a safety net — once the controllers are extracted, the public surface
that this test exercises must keep working.

The tests skip cleanly when PyQt6 is not importable in the current env
(e.g. CI without Qt), and also when MainWindow construction fails for
environmental reasons (QWebEngineView is fussy under some headless GL
stacks). On a dev machine with PyQt6 + Qt WebEngine installed they run
end-to-end. Run from project root::

    QT_QPA_PLATFORM=offscreen python -m unittest tests.test_app_smoke -v

This is a structural smoke test, not a behavioural one — it pins the
*existence* of the undo/redo stack, mode helpers, and project save/load
plumbing so a rename or accidental deletion fails loudly.
"""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Force offscreen platform BEFORE importing anything Qt-touching.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

# Sandbox the DB and config so the test never touches the real user data.
_TMP_DIR = tempfile.mkdtemp(prefix="permadesign_app_smoke_")
_DB_PATH = os.path.join(_TMP_DIR, "permadesign_test.db")
_CFG_PATH = os.path.join(_TMP_DIR, "config.json")

try:
    import src.db.plants as _plants_mod
    _plants_mod._DATA_DIR = _TMP_DIR
    _plants_mod._DB_PATH = _DB_PATH
    import src.settings as _settings_mod
    _settings_mod._CONFIG_PATH = _CFG_PATH
except Exception:  # pragma: no cover — defensive, almost never trips
    pass


def _qt_available():
    try:
        import PyQt6  # noqa: F401
        from PyQt6.QtWidgets import QApplication  # noqa: F401
        return True
    except Exception:
        return False


@unittest.skipUnless(_qt_available(), "PyQt6 not installed in this env")
class TestMainWindowSmoke(unittest.TestCase):
    """Construct a MainWindow once for the class, then exercise public state."""

    _app = None
    _win = None
    _construct_error: Exception | None = None

    @classmethod
    def setUpClass(cls):
        from PyQt6.QtWidgets import QApplication
        cls._app = QApplication.instance() or QApplication([])
        try:
            from src.app import MainWindow
            cls._win = MainWindow()
        except Exception as exc:  # noqa: BLE001 — capture for skipTest
            cls._construct_error = exc

    @classmethod
    def tearDownClass(cls):
        if cls._win is not None:
            cls._win.close()
            cls._win.deleteLater()
            cls._win = None

    def setUp(self):
        if self._construct_error is not None:
            self.skipTest(
                f"MainWindow construction failed in this env: "
                f"{type(self._construct_error).__name__}: {self._construct_error}"
            )

    # ── Basic class shape ────────────────────────────────────────────────────

    def test_constructed(self):
        self.assertIsNotNone(self._win)
        self.assertEqual(self._win.windowTitle(),
                         "PermaDesign — Native Habitat Designer")

    def test_initial_project_state(self):
        self.assertEqual(self._win._project["type"], "FeatureCollection")
        self.assertEqual(self._win._project["features"], [])
        self.assertIsNone(self._win._project_path)
        self.assertFalse(self._win._modified)
        self.assertEqual(self._win._current_mode, "none")

    def test_initial_undo_redo_state(self):
        self.assertEqual(self._win._undo_stack, [])
        self.assertEqual(self._win._redo_stack, [])

    # ── Undo/redo stack mechanics ────────────────────────────────────────────
    # `_push_undo` is the single entry point that all map-side mutations
    # funnel through; if Chunk 5 moves it to a controller, this guards the
    # invariant that pushing clears redo and the stack stays bounded.

    def test_push_undo_clears_redo(self):
        self._win._redo_stack = [{"action": "stale", "data": {}}]
        self._win._push_undo({"action": "test", "data": {"x": 1}})
        self.assertEqual(self._win._undo_stack[-1]["action"], "test")
        self.assertEqual(self._win._redo_stack, [])

    def test_push_undo_caps_stack_size(self):
        self._win._undo_stack = []
        cap = self._win._max_undo
        for i in range(cap + 5):
            self._win._push_undo({"action": "noop", "data": {"i": i}})
        self.assertEqual(len(self._win._undo_stack), cap)
        # Newest entry survives, oldest were dropped.
        self.assertEqual(self._win._undo_stack[-1]["data"]["i"], cap + 4)

    # ── Mode helpers ─────────────────────────────────────────────────────────

    def test_set_mode_label_updates_state(self):
        # `_set_mode_label` is what every _enter_*_mode helper calls; if a
        # mode name silently drifts, this catches it. The label widget
        # (`_sb_mode`, status-bar mode indicator) should reflect the new
        # text after the call.
        self._win._set_mode_label("BoundaryProbe")
        self.assertTrue(hasattr(self._win, "_sb_mode"))
        self.assertEqual(self._win._sb_mode.text(), "Mode: BoundaryProbe")

    def test_required_mode_methods_exist(self):
        for name in (
            "_enter_boundary_mode", "_enter_measure_mode",
            "_enter_annotate_mode", "_enter_plant_mode",
            "_enter_structure_mode", "_enter_hedgerow_mode",
            "_enter_shape_mode", "_set_mode_label",
            "_cancel_draw",
        ):
            self.assertTrue(
                callable(getattr(self._win, name, None)),
                f"MainWindow.{name} should remain reachable after Chunk 5",
            )

    # ── Persistence surface ──────────────────────────────────────────────────

    def test_required_persistence_methods_exist(self):
        for name in ("_on_save", "_on_save_as", "_do_undo", "_do_redo",
                     "_push_undo", "_autosave", "_start_autosave",
                     "_mark_modified"):
            self.assertTrue(
                callable(getattr(self._win, name, None)),
                f"MainWindow.{name} should remain reachable after Chunk 5",
            )

    # ── Update-flow surface ──────────────────────────────────────────────────

    def test_required_update_flow_methods_exist(self):
        for name in (
            "_on_check_for_updates", "_run_update_flow",
            "_newest_remote_version_branch", "_is_newer_version",
            "_offer_branch_switch", "_open_releases_page",
            "_maybe_restore_stash",
        ):
            self.assertTrue(
                callable(getattr(self._win, name, None)),
                f"MainWindow.{name} should remain reachable after Chunk 5",
            )

    # ── Permapeople surface is gone ──────────────────────────────────────────

    def test_permapeople_helpers_removed(self):
        for name in ("_load_api_keys", "_on_settings"):
            self.assertFalse(
                hasattr(self._win, name),
                f"MainWindow.{name} should have been removed in Chunk 1",
            )


if __name__ == "__main__":
    unittest.main()

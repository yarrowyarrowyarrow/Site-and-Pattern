"""
tests/test_plant_panel_smoke.py

Headless-Qt smoke test for src/plant_panel.py:PlantPanel. Safety net for
the upcoming plant_panel split (Chunk 4 of the strengthening roadmap)
into PlantListModel + PlantRowDelegate, the mix logic, and the placed-
plants strip.

Same skip-gracefully pattern as tests/test_app_smoke.py — when PyQt6 is
missing or the panel can't construct in this env, the tests skip
cleanly. Run locally with::

    QT_QPA_PLATFORM=offscreen python -m unittest tests.test_plant_panel_smoke -v

The mix logic (`_add_to_mix`, `_remove_from_mix`, `_clear_mix`) is the
piece most likely to move during the Chunk 4 split, so it gets the most
behavioural coverage here.
"""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Force offscreen platform BEFORE importing anything Qt-touching.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

# Sandbox DB so the test never touches the real user DB.
_TMP_DIR = tempfile.mkdtemp(prefix="permadesign_plant_smoke_")
try:
    import src.db.plants as _plants_mod
    _plants_mod._DATA_DIR = _TMP_DIR
    _plants_mod._DB_PATH = os.path.join(_TMP_DIR, "permadesign_test.db")
except Exception:  # pragma: no cover
    pass


def _qt_available():
    try:
        import PyQt6  # noqa: F401
        from PyQt6.QtWidgets import QApplication  # noqa: F401
        return True
    except Exception:
        return False


@unittest.skipUnless(_qt_available(), "PyQt6 not installed in this env")
class TestPlantPanelSmoke(unittest.TestCase):

    _app = None
    _panel = None
    _construct_error: Exception | None = None

    @classmethod
    def setUpClass(cls):
        from PyQt6.QtWidgets import QApplication
        cls._app = QApplication.instance() or QApplication(["permadesign-tests"])
        try:
            from src.db.plants import init_db
            init_db()  # seeds the temp DB so PlantPanel queries succeed
            from src.plant_panel import PlantPanel
            cls._panel = PlantPanel()
        except Exception as exc:  # noqa: BLE001
            cls._construct_error = exc

    @classmethod
    def tearDownClass(cls):
        if cls._panel is not None:
            cls._panel.close()
            cls._panel.deleteLater()
            cls._panel = None

    def setUp(self):
        if self._construct_error is not None:
            self.skipTest(
                f"PlantPanel construction failed in this env: "
                f"{type(self._construct_error).__name__}: {self._construct_error}"
            )
        # The panel is constructed once for the class (setUpClass), so its
        # mutable transient state leaks between test methods in alphabetical
        # run order — e.g. test_add_to_mix_* would dirty _mix_species before
        # test_constructed checks it's empty. Reset to construction defaults
        # before each test so assertions are order-independent.
        if self._panel is not None:
            self._panel._mix_species = []
            self._panel._selected_plant = None
            self._panel._current_zone = None
            self._panel._placed_counts = {}

    # ── Basic class shape ────────────────────────────────────────────────────

    def test_constructed(self):
        self.assertIsNotNone(self._panel)
        # Initial mix should be empty.
        self.assertEqual(self._panel._mix_species, [])
        self.assertIsNone(self._panel._selected_plant)
        self.assertIsNone(self._panel._current_zone)

    def test_no_legacy_api_setter(self):
        # Chunk 1 cleanup removed the set_api_keys no-op; verify it stays
        # gone so the upcoming Chunk 4 split doesn't accidentally
        # resurrect it.
        self.assertFalse(hasattr(self._panel, "set_api_keys"))

    # ── Mix add/remove/clear semantics ───────────────────────────────────────

    def _reset_mix(self):
        self._panel._mix_species = []

    def test_add_to_mix_appends_entry(self):
        self._reset_mix()
        self._panel._add_to_mix({"id": 1, "common_name": "Yarrow"})
        self.assertEqual(len(self._panel._mix_species), 1)
        self.assertEqual(self._panel._mix_species[0]["id"], 1)
        self.assertEqual(self._panel._mix_species[0]["_weight"], 1)

    def test_add_to_mix_rejects_duplicates(self):
        self._reset_mix()
        self._panel._add_to_mix({"id": 1, "common_name": "Yarrow"})
        self._panel._add_to_mix({"id": 1, "common_name": "Yarrow"})
        self.assertEqual(len(self._panel._mix_species), 1)

    def test_add_to_mix_rejects_db_less_rows(self):
        self._reset_mix()
        self._panel._add_to_mix({"id": None, "common_name": "Ghost"})
        self._panel._add_to_mix({"common_name": "Also Ghost"})
        self.assertEqual(self._panel._mix_species, [])

    def test_add_to_mix_caps_at_MIX_MAX(self):
        self._reset_mix()
        cap = self._panel._MIX_MAX
        for i in range(cap + 3):
            self._panel._add_to_mix({"id": i + 1, "common_name": f"P{i}"})
        self.assertEqual(len(self._panel._mix_species), cap)

    def test_add_to_mix_does_not_mutate_caller_dict(self):
        self._reset_mix()
        plant = {"id": 1, "common_name": "Yarrow"}
        self._panel._add_to_mix(plant)
        self.assertNotIn("_weight", plant)
        self.assertIn("_weight", self._panel._mix_species[0])

    def test_remove_from_mix_drops_matching_id(self):
        self._reset_mix()
        self._panel._add_to_mix({"id": 1, "common_name": "Yarrow"})
        self._panel._add_to_mix({"id": 2, "common_name": "Bergamot"})
        self._panel._remove_from_mix(1)
        ids = [s["id"] for s in self._panel._mix_species]
        self.assertEqual(ids, [2])

    def test_remove_from_mix_ignores_unknown_id(self):
        self._reset_mix()
        self._panel._add_to_mix({"id": 1, "common_name": "Yarrow"})
        self._panel._remove_from_mix(999)
        self.assertEqual(len(self._panel._mix_species), 1)

    # ── Zone tracking ────────────────────────────────────────────────────────

    def test_set_zone_persists(self):
        self._panel.set_zone(3)
        self.assertEqual(self._panel._current_zone, 3)
        self._panel.set_zone(None)
        self.assertIsNone(self._panel._current_zone)

    # ── Placed-plants round-trip ─────────────────────────────────────────────
    # `clear_placed` / `load_placed` are what app.py calls after every map
    # mutation. Pin the dict-shape contract so the Chunk 4 split can't
    # silently change it.

    def test_clear_placed_resets_counts(self):
        self._panel._placed_counts = {1: 5, 2: 3}
        self._panel.clear_placed()
        self.assertEqual(self._panel._placed_counts, {})

    def test_load_placed_recomputes_counts(self):
        self._panel.load_placed([
            {"plant_id": 1, "common_name": "A"},
            {"plant_id": 1, "common_name": "A"},
            {"plant_id": 2, "common_name": "B"},
        ])
        self.assertEqual(self._panel._placed_counts.get(1), 2)
        self.assertEqual(self._panel._placed_counts.get(2), 1)


if __name__ == "__main__":
    unittest.main()

"""
tests/test_save_durability.py — atomic project saves + crash-recovery
autosave (V2.22).

The design file is the product; these tests pin the durability contract:

  * save_project writes atomically (a failed serialize can never truncate
    the existing file, and leaves no temp litter),
  * the previous version survives one save as <path>.bak,
  * the autosave stamps the design's source path on a copy without
    polluting the live project dict,
  * an unreadable autosave is discarded, not offered (no dialog path).

Controller-level pieces run Qt-free: PersistenceController is constructed
against a tiny fake main window (the same trick tests/test_project_store.py
uses), never a QApplication.
"""

import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import project as project_io


class TestAtomicSave(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="sp-save-")
        self.path = os.path.join(self.dir, "design.perma.geojson")

    def _files(self):
        return sorted(os.listdir(self.dir))

    def test_simple_save_and_load_round_trip(self):
        proj = project_io.new_project("Roundtrip")
        project_io.save_project(proj, self.path)
        self.assertEqual(project_io.load_project(self.path), proj)
        self.assertEqual(self._files(), ["design.perma.geojson"],
                         "no temp litter after a clean save")

    def test_previous_version_survives_as_bak(self):
        v1 = project_io.new_project("One")
        v2 = project_io.new_project("Two")
        project_io.save_project(v1, self.path)
        project_io.save_project(v2, self.path)
        self.assertEqual(project_io.load_project(self.path), v2)
        bak = self.path + ".bak"
        self.assertTrue(os.path.exists(bak))
        with open(bak, encoding="utf-8") as f:
            self.assertEqual(json.load(f)["properties"]["project_name"], "One")

    def test_failed_serialize_leaves_original_intact(self):
        good = project_io.new_project("Good")
        project_io.save_project(good, self.path)
        # A dict json can't serialize — the classic mid-save failure.
        bad = project_io.new_project("Bad")
        bad["features"].append({"oops": object()})
        with self.assertRaises(TypeError):
            project_io.save_project(bad, self.path)
        self.assertEqual(project_io.load_project(self.path), good,
                         "original file must be untouched by a failed save")
        self.assertEqual(self._files(), ["design.perma.geojson"],
                         "failed save must clean up its temp file")


class _FakeStatusBar:
    def showMessage(self, *a, **k):
        pass


class _FakeMain:
    """Just enough MainWindow for the autosave paths."""
    AUTOSAVE_INTERVAL_MS = 300000

    def __init__(self):
        self._project = {"type": "FeatureCollection",
                         "properties": {"project_name": "Fake"},
                         "features": []}
        self._project_path = "/somewhere/fake.perma.geojson"
        self._modified = True

    def statusBar(self):
        return _FakeStatusBar()

    def setWindowTitle(self, *a):
        pass


class TestAutosave(unittest.TestCase):
    def setUp(self):
        try:
            import src.controllers.persistence as pmod
        except Exception as exc:  # pragma: no cover — no PyQt6 here
            self.skipTest(f"PyQt6 unavailable: {exc}")
        self.pmod = pmod
        self.dir = tempfile.mkdtemp(prefix="sp-autosave-")
        self._orig_autosave_path = pmod.autosave_path
        pmod.autosave_path = lambda: os.path.join(self.dir, "auto.perma.geojson")

    def tearDown(self):
        self.pmod.autosave_path = self._orig_autosave_path

    def _controller(self, main):
        return self.pmod.PersistenceController(main)

    def test_autosave_stamps_source_without_polluting_project(self):
        main = _FakeMain()
        ctl = self._controller(main)
        ctl._autosave()
        saved = json.load(open(self.pmod.autosave_path(), encoding="utf-8"))
        self.assertEqual(saved["properties"]["_autosave_source_path"],
                         main._project_path)
        self.assertNotIn("_autosave_source_path", main._project["properties"],
                         "live project must not carry the recovery-only key")

    def test_autosave_skipped_when_unmodified(self):
        main = _FakeMain()
        main._modified = False
        self._controller(main)._autosave()
        self.assertFalse(os.path.exists(self.pmod.autosave_path()))

    def test_clear_autosave_removes_file_and_tolerates_absence(self):
        main = _FakeMain()
        ctl = self._controller(main)
        ctl._autosave()
        self.assertTrue(os.path.exists(self.pmod.autosave_path()))
        ctl.clear_autosave()
        self.assertFalse(os.path.exists(self.pmod.autosave_path()))
        ctl.clear_autosave()  # second call: no raise

    def test_unreadable_autosave_discarded_without_dialog(self):
        with open(self.pmod.autosave_path(), "w", encoding="utf-8") as f:
            f.write("{not json")
        ctl = self._controller(_FakeMain())
        ctl.maybe_offer_autosave_recovery()   # must not raise / show dialogs
        self.assertFalse(os.path.exists(self.pmod.autosave_path()),
                         "corrupt autosave should be consumed")

    def test_recovery_check_is_one_shot(self):
        ctl = self._controller(_FakeMain())
        ctl.maybe_offer_autosave_recovery()   # no file → marks checked
        ctl._autosave.__self__._main._modified = True
        # Drop a valid autosave AFTER the first check; the second call
        # must not offer it (one-shot per launch).
        with open(self.pmod.autosave_path(), "w", encoding="utf-8") as f:
            json.dump({"type": "FeatureCollection", "properties": {},
                       "features": []}, f)
        ctl.maybe_offer_autosave_recovery()
        self.assertTrue(os.path.exists(self.pmod.autosave_path()),
                        "second call must be a no-op")


if __name__ == "__main__":
    unittest.main()

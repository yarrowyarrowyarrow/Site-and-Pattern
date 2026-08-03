"""
tests/test_saves.py — a saves folder, a list, and no file dialog (F87, V2.39).

User feedback: *"Saving a file should be more simple and similar to how game
files are saved and loaded. There should be a folder that they automatically
save to. When loading a previously saved file they should be listed in the app
rather than opening the computer's file explorer."*

Before this, a design went wherever the OS dialog happened to be pointing and
finding it again meant remembering. These cover the Qt-free half: the folder,
the filename, and the one-line description that tells one yard from another.
"""

import json
import os
import shutil
import sys
import tempfile
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import saves                                       # noqa: E402


def _project(name="Untitled Design", plants=(), pin=""):
    feats = [{"type": "Feature",
              "properties": {"element_type": "plant", "common_name": c},
              "geometry": {"type": "Point", "coordinates": [0, 0]}}
             for c in plants]
    return {"type": "FeatureCollection",
            "properties": {"project_name": name,
                           "site_config": {"pin_label": pin}},
            "features": feats}


def _write(directory, filename, project):
    path = os.path.join(directory, filename)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(project, f)
    return path


class TestTheFilename(unittest.TestCase):
    """A person should be able to open the folder and see their designs."""

    def test_a_name_stays_readable(self):
        self.assertEqual(saves.slugify("Back Yard Meadow"), "Back Yard Meadow")

    def test_characters_no_filesystem_accepts_are_replaced(self):
        for bad in '<>:"/\\|?*':
            out = saves.slugify(f"Front{bad}Yard")
            self.assertNotIn(bad, out)
            self.assertIn("Front", out)

    def test_an_empty_name_still_produces_a_file(self):
        for empty in ("", "   ", None, "...", "///"):
            self.assertTrue(saves.slugify(empty))

    def test_windows_device_names_are_defused(self):
        """CON.perma.geojson cannot be created on Windows."""
        for reserved in ("CON", "con", "PRN", "NUL", "COM1", "lpt9"):
            self.assertNotIn(saves.slugify(reserved).upper(),
                             {"CON", "PRN", "NUL", "COM1", "LPT9"})

    def test_a_very_long_name_is_trimmed(self):
        self.assertLessEqual(len(saves.slugify("x" * 500)), 80)


class TestNotOverwriting(unittest.TestCase):
    """Two designs both called 'Untitled Design' are two designs."""

    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="sp_saves_")
        self.addCleanup(shutil.rmtree, self.dir, ignore_errors=True)

    def test_a_free_name_is_used_as_is(self):
        p = saves.unique_save_path("Meadow", self.dir)
        self.assertEqual(os.path.basename(p), "Meadow" + saves.SAVE_SUFFIX)

    def test_a_taken_name_gets_a_number_not_a_clobber(self):
        first = saves.unique_save_path("Meadow", self.dir)
        open(first, "w").close()
        second = saves.unique_save_path("Meadow", self.dir)
        self.assertNotEqual(first, second)
        self.assertTrue(os.path.exists(first), "the first save was destroyed")
        self.assertIn("Meadow 2", os.path.basename(second))

    def test_it_keeps_counting(self):
        made = []
        for _ in range(4):
            p = saves.unique_save_path("Meadow", self.dir)
            open(p, "w").close()
            made.append(p)
        self.assertEqual(len(set(made)), 4)


class TestDescribingASave(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="sp_saves_")
        self.addCleanup(shutil.rmtree, self.dir, ignore_errors=True)
        saves.clear_cache()

    def test_it_reads_the_name_and_the_counts(self):
        path = _write(self.dir, "a" + saves.SAVE_SUFFIX,
                      _project("Back Yard", ["Saskatoon Berry", "Wild Bergamot",
                                             "Saskatoon Berry"], pin="Edmonton"))
        d = saves.describe(path)
        self.assertEqual(d["name"], "Back Yard")
        self.assertEqual(d["plants"], 3)
        self.assertEqual(d["species"], 2)      # duplicates are one species
        self.assertEqual(d["site"], "Edmonton")
        self.assertEqual(d["error"], "")

    def test_an_unreadable_save_is_described_not_hidden(self):
        """A file vanishing from the list is how a user concludes their work
        is gone."""
        path = os.path.join(self.dir, "broken" + saves.SAVE_SUFFIX)
        with open(path, "w", encoding="utf-8") as f:
            f.write("{not json")
        d = saves.describe(path)
        self.assertTrue(d["error"])
        self.assertEqual(d["filename"], "broken" + saves.SAVE_SUFFIX)
        self.assertIn("Could not be read", saves.summary_line(d))

    def test_a_missing_file_is_not_an_exception(self):
        d = saves.describe(os.path.join(self.dir, "nope" + saves.SAVE_SUFFIX))
        self.assertTrue(d["error"])

    def test_a_json_file_that_is_not_a_project_is_caught(self):
        path = _write(self.dir, "list" + saves.SAVE_SUFFIX, [])
        self.assertTrue(saves.describe(path)["error"])

    def test_the_read_is_cached_until_the_file_changes(self):
        path = _write(self.dir, "a" + saves.SAVE_SUFFIX, _project("One"))
        self.assertEqual(saves.describe(path)["name"], "One")
        time.sleep(0.01)
        _write(self.dir, "a" + saves.SAVE_SUFFIX, _project("Two"))
        os.utime(path, (time.time() + 5, time.time() + 5))
        self.assertEqual(saves.describe(path)["name"], "Two",
                         "the cache did not notice the file changed")


class TestTheList(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="sp_saves_")
        self.addCleanup(shutil.rmtree, self.dir, ignore_errors=True)
        saves.clear_cache()

    def test_newest_first(self):
        old = _write(self.dir, "old" + saves.SAVE_SUFFIX, _project("Old"))
        new = _write(self.dir, "new" + saves.SAVE_SUFFIX, _project("New"))
        os.utime(old, (1_000_000, 1_000_000))
        os.utime(new, (2_000_000, 2_000_000))
        self.assertEqual([e["name"] for e in saves.list_saves(self.dir)],
                         ["New", "Old"])

    def test_non_saves_are_ignored(self):
        _write(self.dir, "real" + saves.SAVE_SUFFIX, _project("Real"))
        with open(os.path.join(self.dir, "notes.txt"), "w") as f:
            f.write("hello")
        self.assertEqual([e["name"] for e in saves.list_saves(self.dir)],
                         ["Real"])

    def test_a_missing_folder_is_an_empty_list_not_a_crash(self):
        self.assertEqual(saves.list_saves(os.path.join(self.dir, "nope")), [])

    def test_one_broken_file_does_not_lose_the_others(self):
        _write(self.dir, "good" + saves.SAVE_SUFFIX, _project("Good"))
        with open(os.path.join(self.dir, "bad" + saves.SAVE_SUFFIX), "w") as f:
            f.write("{")
        names = {e["name"] for e in saves.list_saves(self.dir)}
        self.assertIn("Good", names)
        self.assertEqual(len(saves.list_saves(self.dir)), 2)


class TestWhatTheListSays(unittest.TestCase):
    def test_a_design_with_no_plants_says_so(self):
        line = saves.summary_line({"plants": 0, "species": 0, "site": ""})
        self.assertIn("no plants yet", line)
        self.assertNotIn("0 species", line)

    def test_singulars(self):
        self.assertIn("1 plant ", saves.summary_line(
            {"plants": 1, "species": 1, "site": ""}) + " ")
        self.assertNotIn("1 plants", saves.summary_line(
            {"plants": 1, "species": 1, "site": ""}))

    def test_recency_reads_as_recency(self):
        now = 1_000_000.0
        self.assertEqual(saves.when({"modified": now - 10}, now), "just now")
        self.assertEqual(saves.when({"modified": now - 600}, now),
                         "10 minutes ago")
        self.assertEqual(saves.when({"modified": now - 7200}, now),
                         "2 hours ago")
        self.assertEqual(saves.when({"modified": now - 2 * 86400}, now),
                         "2 days ago")

    def test_something_old_gets_a_date(self):
        now = time.time()
        self.assertRegex(saves.when({"modified": now - 60 * 86400}, now),
                         r"\d{2} \w{3} \d{4}")

    def test_no_timestamp_says_nothing_rather_than_1970(self):
        self.assertEqual(saves.when({"modified": 0}), "")


class TestTheAutosaveMoved(unittest.TestCase):
    """It was a hidden dotfile in $HOME — nobody's mental model of where their
    work lives, and the one moment it matters is the moment a user is upset."""

    def test_it_lives_in_the_data_dir_now(self):
        from src.controllers.persistence import autosave_path
        from src.user_paths import user_data_dir
        self.assertTrue(autosave_path().startswith(user_data_dir()))

    def test_it_is_not_a_home_directory_dotfile(self):
        from src.controllers.persistence import autosave_path
        self.assertFalse(os.path.basename(autosave_path()).startswith("."))

    def test_the_migration_copies_verifies_then_unlinks(self):
        """Never a bare rename: a person hitting this is mid-recovery from a
        crash, and losing the file to a refactor is the worst possible moment
        for a clever one-liner."""
        import ast
        import pathlib
        src = (pathlib.Path(__file__).resolve().parent.parent / "src"
               / "controllers" / "persistence.py").read_text(encoding="utf-8")
        fn = next(n for n in ast.walk(ast.parse(src))
                  if isinstance(n, ast.FunctionDef)
                  and n.name == "migrate_legacy_autosave")
        dump = ast.dump(fn)
        self.assertIn("fsync", dump)
        self.assertIn("getsize", dump)
        self.assertNotIn("'rename'", dump)
        self.assertNotIn("'move'", dump)

    def test_recovery_migrates_before_it_looks(self):
        """Otherwise the one launch that most needs the file finds nothing."""
        import ast
        import pathlib
        src = (pathlib.Path(__file__).resolve().parent.parent / "src"
               / "controllers" / "persistence.py").read_text(encoding="utf-8")
        fn = next(n for n in ast.walk(ast.parse(src))
                  if isinstance(n, ast.FunctionDef)
                  and n.name == "maybe_offer_autosave_recovery")
        migrate = next((n.lineno for n in ast.walk(fn)
                        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                        and n.func.id == "migrate_legacy_autosave"), None)
        look = next((n.lineno for n in ast.walk(fn)
                     if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                     and n.func.id == "autosave_path"), None)
        self.assertIsNotNone(migrate, "the legacy autosave is never migrated")
        self.assertLess(migrate, look)


class TestSaveStopsAsking(unittest.TestCase):
    def test_save_with_no_path_goes_to_the_saves_folder(self):
        """AST-only — the controller needs a MainWindow to instantiate."""
        import ast
        import pathlib
        src = (pathlib.Path(__file__).resolve().parent.parent / "src"
               / "controllers" / "persistence.py").read_text(encoding="utf-8")
        fn = next(n for n in ast.walk(ast.parse(src))
                  if isinstance(n, ast.FunctionDef) and n.name == "_on_save")
        dump = ast.dump(fn)
        self.assertIn("unique_save_path", dump)
        self.assertIn("ensure_saves_dir", dump)

    def test_save_as_still_offers_the_dialog(self):
        """This adds a default; it does not take away the choice."""
        import ast
        import pathlib
        src = (pathlib.Path(__file__).resolve().parent.parent / "src"
               / "controllers" / "persistence.py").read_text(encoding="utf-8")
        fn = next(n for n in ast.walk(ast.parse(src))
                  if isinstance(n, ast.FunctionDef) and n.name == "_on_save_as")
        self.assertIn("getSaveFileName", ast.dump(fn))


if __name__ == "__main__":
    unittest.main()


try:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PyQt6.QtWidgets import QApplication
    _HAVE_QT = True
except Exception:                                          # noqa: BLE001
    _HAVE_QT = False


@unittest.skipUnless(_HAVE_QT, "PyQt6 not installed in this env")
class TestTheBrowser(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="sp_saves_")
        self.addCleanup(shutil.rmtree, self.dir, ignore_errors=True)
        saves.clear_cache()

    def _dialog(self):
        from src.saves_dialog import SavesDialog
        return SavesDialog(directory=self.dir)

    def test_it_lists_what_is_there_newest_first(self):
        old = _write(self.dir, "old" + saves.SAVE_SUFFIX, _project("Old"))
        new = _write(self.dir, "new" + saves.SAVE_SUFFIX, _project("New"))
        os.utime(old, (1_000_000, 1_000_000))
        os.utime(new, (2_000_000, 2_000_000))
        dlg = self._dialog()
        self.assertEqual(dlg._list.count(), 2)
        self.assertTrue(dlg._list.item(0).text().startswith("New"))

    def test_each_row_says_what_the_design_is(self):
        _write(self.dir, "a" + saves.SAVE_SUFFIX,
               _project("Back Yard", ["Saskatoon Berry", "Wild Bergamot"],
                        pin="Edmonton"))
        text = self._dialog()._list.item(0).text()
        self.assertIn("Back Yard", text)
        self.assertIn("2 plants", text)
        self.assertIn("2 species", text)
        self.assertIn("Edmonton", text)

    def test_an_empty_folder_says_so_rather_than_looking_broken(self):
        dlg = self._dialog()
        self.assertEqual(dlg._list.count(), 0)
        self.assertIn("No saved designs yet", dlg._blurb.text())
        self.assertFalse(dlg._btn_open.isEnabled())
        self.assertFalse(dlg._btn_delete.isEnabled())

    def test_an_unreadable_save_is_shown_and_marked(self):
        with open(os.path.join(self.dir, "bad" + saves.SAVE_SUFFIX), "w") as f:
            f.write("{")
        dlg = self._dialog()
        self.assertEqual(dlg._list.count(), 1)
        self.assertIn("Could not be read", dlg._list.item(0).text())

    def test_choosing_one_returns_its_path(self):
        path = _write(self.dir, "a" + saves.SAVE_SUFFIX, _project("Back Yard"))
        dlg = self._dialog()
        dlg._list.setCurrentRow(0)
        dlg._open()
        self.assertEqual(dlg.chosen(), path)

    def test_browse_is_a_distinct_answer_from_cancel(self):
        """The caller has to tell 'wants the OS dialog' from 'changed their
        mind' without a second round trip."""
        from src.saves_dialog import BROWSE
        from PyQt6.QtWidgets import QDialog
        self.assertNotIn(BROWSE, (QDialog.DialogCode.Accepted.value,
                                  QDialog.DialogCode.Rejected.value))

    def test_nothing_is_chosen_when_nothing_is_selected(self):
        self.assertEqual(self._dialog().chosen(), "")


@unittest.skipUnless(_HAVE_QT, "PyQt6 not installed in this env")
class TestOpenGoesThroughTheList(unittest.TestCase):
    def test_the_menu_opens_the_browser_not_the_os_dialog(self):
        import ast
        import pathlib
        src = (pathlib.Path(__file__).resolve().parent.parent
               / "src" / "app.py").read_text(encoding="utf-8")
        fn = next(n for n in ast.walk(ast.parse(src))
                  if isinstance(n, ast.FunctionDef) and n.name == "_on_open")
        dump = ast.dump(fn)
        self.assertIn("SavesDialog", dump)
        self.assertNotIn("getOpenFileName", dump,
                         "File → Open still opens the OS dialog directly")

    def test_the_os_dialog_is_still_reachable(self):
        """A design kept somewhere else is a real thing; this adds a default,
        it does not take the choice away."""
        import ast
        import pathlib
        src = (pathlib.Path(__file__).resolve().parent.parent
               / "src" / "app.py").read_text(encoding="utf-8")
        tree = ast.parse(src)
        fn = next(n for n in ast.walk(tree)
                  if isinstance(n, ast.FunctionDef)
                  and n.name == "_ask_for_design_file")
        self.assertIn("getOpenFileName", ast.dump(fn))
        opener = next(n for n in ast.walk(tree)
                      if isinstance(n, ast.FunctionDef) and n.name == "_on_open")
        self.assertIn("BROWSE", ast.dump(opener))

    def test_it_loads_through_the_shared_path(self):
        """A second, near-identical load path is how the panels and the title
        bar drift out of step — the worked example proved the shared one."""
        import ast
        import pathlib
        src = (pathlib.Path(__file__).resolve().parent.parent
               / "src" / "app.py").read_text(encoding="utf-8")
        fn = next(n for n in ast.walk(ast.parse(src))
                  if isinstance(n, ast.FunctionDef) and n.name == "_on_open")
        self.assertIn("_load_from_path", ast.dump(fn))

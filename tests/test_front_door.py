"""
tests/test_front_door.py — the front door, V3.23 (docs/homeowner/04-start-screen.md,
ST-4 to ST-9, and the owner's flowering line).

A design takes its name from its address (ST-5), one way starts a new yard
(ST-6), a design can be renamed (ST-7), unsaved work passed over on the start
screen is kept as its own design (ST-8), the example opens as a copy (ST-9),
and the screen's last line says what is in flower around Edmonton this month.
"""

import json
import os
import shutil
import sys
import tempfile
import time
import unittest
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import design_name, saves  # noqa: E402
from src.plant_directory_bloom import flowering_around, flowering_line  # noqa: E402

try:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PyQt6.QtWidgets import QApplication
    _HAVE_QT = True
except Exception:                                          # noqa: BLE001
    _HAVE_QT = False


class _TempSaves(unittest.TestCase):
    def setUp(self):
        import src.settings as settings_mod
        self.dir = tempfile.mkdtemp(prefix="sp_front_")
        self.addCleanup(shutil.rmtree, self.dir, ignore_errors=True)
        self.addCleanup(setattr, saves, "saves_dir", saves.saves_dir)
        saves.saves_dir = lambda: self.dir
        self.addCleanup(setattr, settings_mod, "_CONFIG_PATH",
                        settings_mod._CONFIG_PATH)
        settings_mod._CONFIG_PATH = os.path.join(self.dir, "config.json")
        saves.clear_cache()

    def write(self, name, project_name, *, mtime=None):
        path = os.path.join(self.dir, name)
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"type": "FeatureCollection",
                       "properties": {"project_name": project_name},
                       "features": []}, f)
        if mtime is not None:
            os.utime(path, (mtime, mtime))
        return path


class ADesignIsNamedFromItsAddress(unittest.TestCase):
    """ST-5 (§6): the rule, and that it only ever replaces a placeholder."""

    def test_house_address_point_of_interest_neighbourhood_coordinates(self):
        cases = {
            "10234, 82 Avenue NW, Strathcona, Edmonton, Alberta, T6E 1Z8, "
            "Canada": "10234 82 Avenue NW",
            "Muttart Conservatory, 9626, 96A Street NW, Edmonton":
                "Muttart Conservatory",
            "Ritchie, Edmonton, Alberta, Canada": "Ritchie",
            "53.54321, -113.49876": "",
            "": "",
            None: "",
        }
        for label, want in cases.items():
            self.assertEqual(design_name.from_address(label), want, label)

    def test_never_longer_than_sixty_characters(self):
        self.assertLessEqual(len(design_name.from_address("x" * 200)), 60)

    def test_only_a_placeholder_is_replaced(self):
        self.assertEqual(design_name.renamed("Untitled Design", "Ritchie, AB"),
                         "Ritchie")
        self.assertEqual(design_name.renamed("Back yard", "Ritchie, AB"), "")
        self.assertEqual(design_name.renamed("My yard", "Ritchie, AB"), "")
        self.assertEqual(design_name.renamed("Untitled Design", ""), "")

    def test_the_open_design_and_its_title_follow_the_pin(self):
        from src import start_flow
        titles = []
        main = SimpleNamespace(
            _project={"properties": {"project_name": "Untitled Design"}},
            setWindowTitle=titles.append)
        start_flow.name_from_pin(main, "10234, 82 Avenue NW, Edmonton")
        self.assertEqual(main._project["properties"]["project_name"],
                         "10234 82 Avenue NW")
        self.assertIn("10234 82 Avenue NW", titles[-1])
        # A dragged pin sends no label; a named design keeps its name.
        start_flow.name_from_pin(main, "")
        start_flow.name_from_pin(main, "Ritchie, Edmonton")
        self.assertEqual(main._project["properties"]["project_name"],
                         "10234 82 Avenue NW")

    def test_the_pin_handler_and_the_first_save_ask_it(self):
        import pathlib
        root = pathlib.Path(__file__).resolve().parent.parent / "src"
        events = (root / "controllers" / "map_events.py").read_text(encoding="utf-8")
        self.assertIn("start_flow.name_from_pin", events)
        persistence = (root / "controllers" / "persistence.py").read_text(encoding="utf-8")
        self.assertIn("ask_design_name", persistence)
        self.assertIn("is_placeholder", persistence)


class ADesignCanBeRenamed(_TempSaves):
    """ST-7: inside the file and on it, nothing overwritten."""

    def test_rename_changes_the_name_the_file_and_the_memory(self):
        old = self.write("Untitled Design.perma.geojson", "Untitled Design")
        saves.remember_last_design(old)
        new = saves.rename_save(old, "Back yard meadow")
        self.assertFalse(os.path.exists(old))
        self.assertEqual(os.path.basename(new),
                         "Back yard meadow.perma.geojson")
        with open(new, encoding="utf-8") as f:
            self.assertEqual(json.load(f)["properties"]["project_name"],
                             "Back yard meadow")
        self.assertEqual(os.path.abspath(saves.last_design()),
                         os.path.abspath(new))

    def test_a_rename_never_overwrites_another_design(self):
        self.write("Back yard.perma.geojson", "Back yard")
        old = self.write("Other.perma.geojson", "Other")
        new = saves.rename_save(old, "Back yard")
        self.assertEqual(os.path.basename(new), "Back yard 2.perma.geojson")
        self.assertTrue(os.path.exists(
            os.path.join(self.dir, "Back yard.perma.geojson")))

    def test_a_blank_name_is_refused(self):
        old = self.write("A.perma.geojson", "A")
        with self.assertRaises(ValueError):
            saves.rename_save(old, "   ")
        self.assertTrue(os.path.exists(old))

    def test_file_menu_and_the_saves_list_offer_it(self):
        import pathlib
        root = pathlib.Path(__file__).resolve().parent.parent / "src"
        self.assertIn("Rename Design", (root / "app.py").read_text(encoding="utf-8"))
        self.assertIn("Rename…", (root / "saves_dialog.py").read_text(encoding="utf-8"))


class UnsavedWorkIsKept(_TempSaves):
    """ST-8 (S13): passed over on the start screen, a crash's work becomes
    "<name> (unsaved changes from 12 Oct)" and the autosave goes."""

    def test_the_autosave_becomes_a_named_design(self):
        auto = os.path.join(self.dir, "autosave.perma.geojson")
        with open(auto, "w", encoding="utf-8") as f:
            json.dump({"properties": {"project_name": "Back yard"},
                       "features": [{"properties": {"element_type": "plant"}}]},
                      f)
        when = time.mktime((2026, 10, 12, 9, 0, 0, 0, 0, -1))
        kept = saves.keep_unsaved(auto, now=when, directory=self.dir)
        self.assertFalse(os.path.exists(auto))
        with open(kept, encoding="utf-8") as f:
            data = json.load(f)
        self.assertEqual(data["properties"]["project_name"],
                         "Back yard (unsaved changes from 12 Oct)")
        self.assertEqual(len(data["features"]), 1)

    def test_an_unreadable_autosave_is_left_alone(self):
        auto = os.path.join(self.dir, "autosave.perma.geojson")
        with open(auto, "w", encoding="utf-8") as f:
            f.write("{not json")
        self.assertEqual(saves.keep_unsaved(auto, directory=self.dir), "")
        self.assertTrue(os.path.exists(auto))

    def test_the_launch_keeps_it_when_another_row_is_chosen(self):
        import ast
        import pathlib
        src = (pathlib.Path(__file__).resolve().parent.parent / "src"
               / "onboarding_flow.py").read_text(encoding="utf-8")
        fn = next(n for n in ast.walk(ast.parse(src))
                  if isinstance(n, ast.FunctionDef)
                  and n.name == "choose_start_action")
        self.assertIn("keep_passed_autosave", ast.dump(fn))


class TheScreenListsYourDesigns(_TempSaves):
    def test_newest_first_with_the_last_design_from_elsewhere(self):
        from src import start_flow
        now = time.time()
        self.write("a.perma.geojson", "Old", mtime=now - 9 * 86400)
        self.write("b.perma.geojson", "New", mtime=now - 60)
        outside = tempfile.mkdtemp(prefix="sp_out_")
        self.addCleanup(shutil.rmtree, outside, ignore_errors=True)
        far = os.path.join(outside, "far.perma.geojson")
        with open(far, "w", encoding="utf-8") as f:
            json.dump({"properties": {"project_name": "Elsewhere"}}, f)
        os.utime(far, (now - 3600, now - 3600))
        saves.remember_last_design(far)
        rows, total = start_flow.screen_designs()
        self.assertEqual([r["name"] for r in rows], ["New", "Elsewhere", "Old"])
        self.assertEqual(total, 3)
        self.assertEqual(rows[0]["when"], "just now")

    def test_a_listed_design_travels_as_one_string(self):
        from src import start_flow, start_screen
        choice = start_flow.path_choice("/x/Back yard.perma.geojson")
        self.assertEqual(start_flow.split_choice(choice),
                         (start_screen.OPEN_PATH, "/x/Back yard.perma.geojson"))
        self.assertEqual(start_flow.split_choice("example"), ("example", ""))


class OneWayToStartANewYard(unittest.TestCase):
    """ST-6: the screen's row and File › New share start_new_yard, which asks
    no name and puts the cursor in the address search."""

    def test_it_resets_then_points_at_the_address(self):
        from src import start_flow
        seen = []
        main = SimpleNamespace(
            _on_new=lambda: seen.append("reset") or True,
            site_panel=SimpleNamespace(
                focus_address_search=lambda: seen.append("address")))
        start_flow.start_new_yard(main)
        self.assertEqual(seen, ["reset", "address"])

    def test_kept_work_leaves_the_cursor_alone(self):
        from src import start_flow
        seen = []
        main = SimpleNamespace(
            _on_new=lambda: False,
            site_panel=SimpleNamespace(
                focus_address_search=lambda: seen.append("address")))
        start_flow.start_new_yard(main)
        self.assertEqual(seen, [])

    def test_file_new_asks_no_name(self):
        import pathlib
        app = (pathlib.Path(__file__).resolve().parent.parent / "src"
               / "app.py").read_text(encoding="utf-8")
        self.assertNotIn('"Project name:"', app)
        self.assertIn("start_flow.start_new_yard(self)", app)


class TheExampleOpensAsACopy(unittest.TestCase):
    """ST-9: Save writes a new design; the example is never "your" last."""

    def test_open_example_lets_go_of_the_file(self):
        import ast
        import pathlib
        src = (pathlib.Path(__file__).resolve().parent.parent / "src"
               / "onboarding_flow.py").read_text(encoding="utf-8")
        fn = next(n for n in ast.walk(ast.parse(src))
                  if isinstance(n, ast.FunctionDef) and n.name == "open_example")
        dump = ast.dump(fn)
        self.assertIn("_project_path", dump)
        self.assertIn("remember_last_design", dump)


class WhatIsInFlower(unittest.TestCase):
    """The owner (V3.23): "a little line" of what is flowering this month."""

    @staticmethod
    def _fake(rows):
        def search(**kwargs):
            assert kwargs == {"bloom_months": ["7"], "native_near": "edmonton"}
            return rows
        return search

    def test_the_most_recorded_showy_plants_are_named_first(self):
        """V3.24, the owner: common natives, not Sneezeweed."""
        rows = [
            {"common_name": "Purple Oat Grass", "plant_type": "grass"},
            {"common_name": "Cattail", "plant_type": "aquatic"},
            {"common_name": "Zigadene", "plant_type": "wildflower",
             "availability_class": "rare"},
            {"common_name": "Wild Bergamot", "plant_type": "wildflower",
             "availability_class": "garden_centre"},
            {"common_name": "Harebell", "plant_type": "wildflower",
             "availability_class": "native_specialist"},
        ]
        seen = {"Wild Bergamot": 40, "Harebell": 300, "Zigadene": 2}
        summary = flowering_around(
            month=7, search_fn=self._fake(rows),
            seen_fn=lambda r: seen.get(r["common_name"], 0))
        self.assertEqual(summary["names"],
                         ["Harebell", "Wild Bergamot", "Zigadene"])
        self.assertEqual(flowering_line(summary),
                         "In flower around Edmonton in July: Harebell, "
                         "Wild Bergamot and 1 more.")

    def test_a_long_list_is_two_names_and_a_count(self):
        line = flowering_line({"month_name": "May", "place": "Edmonton",
                               "names": list("ABCDEFG")})
        self.assertEqual(line, "In flower around Edmonton in May: A, B and 5 more.")

    def test_two_names_and_one_and_none(self):
        self.assertEqual(flowering_line({"month_name": "October",
                                         "place": "Edmonton",
                                         "names": ["Smooth Aster",
                                                   "Willow Aster"]}),
                         "In flower around Edmonton in October: Smooth Aster "
                         "and Willow Aster.")
        self.assertEqual(flowering_line({"month_name": "October",
                                         "place": "Edmonton",
                                         "names": ["Smooth Aster"]}),
                         "In flower around Edmonton in October: Smooth Aster.")
        self.assertEqual(flowering_line({"month_name": "December",
                                         "names": []}), "")

    def test_a_failing_search_says_nothing(self):
        def broken(**_kw):
            raise RuntimeError("no database")
        self.assertEqual(flowering_around(month=7, search_fn=broken)["names"], [])


@unittest.skipUnless(_HAVE_QT, "PyQt6 not installed in this env")
class TheScreenCanBeRead(unittest.TestCase):
    """The visual floor in every state: 4.5 : 1 for the words on each kind of
    row and for the links and quiet lines on the screen's own ground."""

    @classmethod
    def setUpClass(cls):
        cls._app = QApplication.instance() or QApplication(["permadesign-tests"])

    def test_every_colour_pair_clears_four_and_a_half(self):
        from tests._visual import contrast
        from src import start_screen as s
        for row in (s._PLAIN, s._PRIMARY, s._AMBER):
            for part in ("head", "note"):
                self.assertGreaterEqual(contrast(row[part], row["bg"]), 4.5,
                                        (row, part))
                self.assertGreaterEqual(contrast(row[part], row["hover"]), 4.5,
                                        (row, part, "hover"))
        ground = "#1a2a1a"
        for colour in ("#8fc98f", "#a5c4a7", "#e8f5e9"):
            self.assertGreaterEqual(contrast(colour, ground), 4.5, colour)

    def test_no_text_under_twelve_pixels(self):
        import re
        import pathlib
        src = (pathlib.Path(__file__).resolve().parent.parent / "src"
               / "start_screen.py").read_text(encoding="utf-8")
        sizes = [int(n) for n in re.findall(r"font-size:\s*(\d+)px", src)]
        self.assertTrue(sizes)
        self.assertGreaterEqual(min(sizes), 12)


if __name__ == "__main__":
    unittest.main()

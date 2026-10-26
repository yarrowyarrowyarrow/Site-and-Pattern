"""
tests/test_choosing_a_design.py — choosing and naming a design, V3.37.

The owner, with screenshots of the start screen and the saves list: *"The
'Open a Design' button opens the whole app map page which it shouldn't until
the actual design has been selected. You should be able to rename the design
as well rather than have it just read all the addresses."* And: "mesic" is
not understandable to many.

Held here: the list and the file picker open over the start screen with no
window behind them, and Cancel comes back to it; each listed design has a
Rename; a kept design's name carries one date, not two; a name an address gave
follows the pin; the saves list says where a design is in a few words, never
the address search's whole line; a session's own recovery copy goes when the
window closes cleanly; and communities say "Medium moisture".
"""

import ast
import json
import os
import pathlib
import shutil
import sys
import tempfile
import time
import unittest
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import design_name, saves  # noqa: E402

try:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PyQt6.QtWidgets import QApplication, QMainWindow, QPushButton
    _HAVE_QT = True
except Exception:                                          # noqa: BLE001
    _HAVE_QT = False

_SRC = pathlib.Path(__file__).resolve().parent.parent / "src"
_RITCHIE = ("8103, 95A Street NW, Ritchie, Mill Creek South, Edmonton, "
            "Alberta, T6E 3Z1, Canada")
_GROVENOR = ("10173, 144 Street NW, Grovenor, Western Mature Area, Edmonton, "
             "Alberta, T5N 2V6, Canada")


class _TempSaves(unittest.TestCase):
    """A saves folder and a config file of the test's own."""

    def setUp(self):
        import src.settings as settings_mod
        self.dir = tempfile.mkdtemp(prefix="sp_choose_")
        self.addCleanup(shutil.rmtree, self.dir, ignore_errors=True)
        self.addCleanup(setattr, saves, "saves_dir", saves.saves_dir)
        saves.saves_dir = lambda: self.dir
        self.addCleanup(setattr, settings_mod, "_CONFIG_PATH",
                        settings_mod._CONFIG_PATH)
        settings_mod._CONFIG_PATH = os.path.join(self.dir, "config.json")
        saves.clear_cache()
        self.addCleanup(saves.clear_cache)

    def write(self, name, project_name, *, site="", plants=0, age=0,
              folder=None):
        path = os.path.join(folder or self.dir, name)
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"type": "FeatureCollection",
                       "properties": {"project_name": project_name,
                                      "site_config": {"pin_label": site}},
                       "features": [{"properties": {
                           "element_type": "plant", "common_name": "Aster"}}
                           for _ in range(plants)]}, f)
        stamp = time.time() - age
        os.utime(path, (stamp, stamp))
        return path


# ── Names ───────────────────────────────────────────────────────────────────

class AKeptDesignCarriesOneDate(_TempSaves):
    """"Yard (unsaved changes from 17 Oct) (unsaved changes from 24 Oct)" was
    on the owner's list."""

    def _keep(self, name, day):
        auto = os.path.join(self.dir, "autosave.json")
        with open(auto, "w", encoding="utf-8") as f:
            json.dump({"properties": {"project_name": name}, "features": []}, f)
        kept = saves.keep_unsaved(
            auto, now=time.mktime((2026, 10, day, 9, 0, 0, 0, 0, -1)),
            directory=self.dir)
        with open(kept, encoding="utf-8") as f:
            return json.load(f)["properties"]["project_name"]

    def test_keeping_a_kept_design_again_replaces_its_date(self):
        once = self._keep("8103 95A Street NW", 17)
        self.assertEqual(once, "8103 95A Street NW (unsaved changes from 17 Oct)")
        self.assertEqual(self._keep(once, 24),
                         "8103 95A Street NW (unsaved changes from 24 Oct)")

    def test_a_name_stacked_by_an_older_version_is_mended(self):
        self.assertEqual(
            self._keep("Yard (unsaved changes from 17 Oct) "
                       "(unsaved changes from 24 Oct)", 26),
            "Yard (unsaved changes from 26 Oct)")

    def test_only_the_date_at_the_end_is_taken(self):
        self.assertEqual(self._keep("Back (and side) yard", 3),
                         "Back (and side) yard (unsaved changes from 3 Oct)")
        self.assertEqual(self._keep("", 3),
                         "Untitled Design (unsaved changes from 3 Oct)")


class ANameTheAddressGaveFollowsThePin(unittest.TestCase):
    """The owner's list held "8103 95A Street NW" pinned at 10173 144 Street
    NW: the pin had moved, and the name the first address gave stayed."""

    def test_it_follows_while_it_is_the_address_name(self):
        self.assertEqual(design_name.renamed(
            "8103 95A Street NW", _GROVENOR, previous=_RITCHIE),
            "10173 144 Street NW")

    def test_a_name_the_person_gave_stays(self):
        self.assertEqual(design_name.renamed(
            "Grandma's front yard", _GROVENOR, previous=_RITCHIE), "")
        self.assertEqual(design_name.renamed(
            "8103 95A Street NW (unsaved changes from 17 Oct)", _GROVENOR,
            previous=_RITCHIE), "")

    def test_the_same_address_again_changes_nothing(self):
        """Undo re-places the pin with its own label (U3)."""
        self.assertEqual(design_name.renamed(
            "8103 95A Street NW", _RITCHIE, previous=_RITCHIE), "")

    def test_the_window_follows_and_the_handler_passes_the_old_label(self):
        from src import start_flow
        titles = []
        main = SimpleNamespace(
            _project={"properties": {"project_name": "8103 95A Street NW"}},
            setWindowTitle=titles.append)
        start_flow.name_from_pin(main, _GROVENOR, _RITCHIE)
        self.assertEqual(main._project["properties"]["project_name"],
                         "10173 144 Street NW")
        self.assertIn("10173 144 Street NW", titles[-1])
        events = (_SRC / "controllers" / "map_events.py").read_text(
            encoding="utf-8")
        self.assertIn("start_flow.name_from_pin(self._main, label, previous)",
                      events)


class TheListSaysWhereInAFewWords(unittest.TestCase):
    """The whole address search line ran off the list behind a sideways
    scroll bar."""

    def _entry(self, name, site):
        return {"name": name, "plants": 3, "species": 2, "site": site,
                "error": ""}

    def test_the_house_and_street_only(self):
        self.assertEqual(saves.summary_line(self._entry("Test", _GROVENOR)),
                         "3 plants · 2 species · 10173 144 Street NW")

    def test_nothing_when_the_name_already_says_it(self):
        self.assertEqual(
            saves.summary_line(self._entry("8103 95A Street NW", _RITCHIE)),
            "3 plants · 2 species")
        self.assertEqual(saves.short_place(self._entry("Yard", "")), "")


class OneListOfYourDesigns(_TempSaves):
    """The start screen said "All 4 designs…" and the list it opened said 5."""

    def test_a_design_kept_elsewhere_is_listed_and_marked(self):
        self.write("a.perma.geojson", "Here", age=60)
        outside = tempfile.mkdtemp(prefix="sp_out_")
        self.addCleanup(shutil.rmtree, outside, ignore_errors=True)
        far = self.write("far.perma.geojson", "Elsewhere", folder=outside)
        saves.remember_last_design(far)
        names = [(e["name"], bool(e.get("elsewhere")))
                 for e in saves.your_designs()]
        self.assertEqual(names, [("Elsewhere", True), ("Here", False)])
        self.assertEqual([e["name"] for e in
                          saves.your_designs(include_last=False)], ["Here"])
        from src import start_flow
        self.assertEqual(start_flow.screen_designs()[1], 2)


# ── The start screen ────────────────────────────────────────────────────────

@unittest.skipUnless(_HAVE_QT, "PyQt6 not installed in this env")
class EachDesignCanBeRenamedFromTheScreen(_TempSaves):

    @classmethod
    def setUpClass(cls):
        cls._app = QApplication.instance() or QApplication(["permadesign-tests"])

    def _screen(self):
        from src import start_flow, start_screen
        designs, total = start_flow.screen_designs()
        dlg = start_screen.StartScreen(designs=designs, total=total,
                                       rename=start_flow.rename_listed)
        self.addCleanup(dlg.deleteLater)
        return dlg

    def _renames(self, dlg):
        return [b for b in dlg.findChildren(QPushButton)
                if b.text() == "Rename" and not b.isHidden()]

    def _answer(self, name):
        from src import plain_messages
        self.addCleanup(setattr, plain_messages, "ask_design_name",
                        plain_messages.ask_design_name)
        plain_messages.ask_design_name = lambda *a, **k: name

    def test_every_listed_design_has_one_with_its_name(self):
        self.write("a.perma.geojson", "8103 95A Street NW", age=60)
        self.write("b.perma.geojson", "Test", age=3600)
        dlg = self._screen()
        self.assertEqual([b.accessibleName() for b in self._renames(dlg)],
                         ["Rename 8103 95A Street NW", "Rename Test"])

    def test_renaming_redraws_the_list_and_keeps_the_screen_open(self):
        old = self.write("a.perma.geojson", "8103 95A Street NW", age=60)
        self.write("b.perma.geojson", "Test", age=3600)
        self._answer("Grandma's front yard")
        dlg = self._screen()
        self._renames(dlg)[1].click()          # "Test"
        self._app.processEvents()
        self.assertEqual(dlg.choice(), "")
        self.assertTrue(os.path.exists(old))
        self.assertTrue(os.path.exists(os.path.join(
            self.dir, "Grandma's front yard.perma.geojson")))
        self.assertEqual([b.accessibleName() for b in self._renames(dlg)],
                         ["Rename Grandma's front yard",
                          "Rename 8103 95A Street NW"])
        # The new first row is the one Enter opens.
        self.assertEqual(dlg.primary_row().accessibleName(),
                         "Grandma's front yard")

    def test_backing_out_changes_nothing(self):
        path = self.write("a.perma.geojson", "Test")
        self._answer("")
        dlg = self._screen()
        self._renames(dlg)[0].click()
        self.assertTrue(os.path.exists(path))
        self.assertEqual(len(self._renames(dlg)), 1)

    def test_no_rename_without_the_callback_or_for_a_broken_file(self):
        from src import start_screen
        dlg = start_screen.StartScreen(designs=[
            {"path": "/x.perma.geojson", "name": "X", "when": "", "error": ""}])
        self.addCleanup(dlg.deleteLater)
        self.assertEqual(self._renames(dlg), [])
        broken = start_screen.StartScreen(rename=lambda *_a: None, designs=[
            {"path": "/x.perma.geojson", "name": "X", "when": "",
             "error": "bad"}])
        self.addCleanup(broken.deleteLater)
        self.assertEqual(self._renames(broken), [])

    def test_the_open_design_follows_a_rename(self):
        from PyQt6.QtWidgets import QWidget
        from src import start_flow
        path = self.write("a.perma.geojson", "Test")
        self._answer("Front")
        main = QWidget()
        self.addCleanup(main.deleteLater)
        main._project_path = path
        main._project = {"properties": {"project_name": "Test"}}
        child = QWidget(main)
        target = start_flow.rename_design(child, path)
        self.assertEqual(main._project_path, target)
        self.assertEqual(main._project["properties"]["project_name"], "Front")
        self.assertIn("Front", main.windowTitle())


@unittest.skipUnless(_HAVE_QT, "PyQt6 not installed in this env")
class TheListOpensBeforeTheMap(_TempSaves):
    """*All N designs…* and *Open a file…* are answered over the start
    screen; the map opens only once a design is picked."""

    @classmethod
    def setUpClass(cls):
        cls._app = QApplication.instance() or QApplication(["permadesign-tests"])

    def _scripted(self, screen_answers, picker_answers):
        """Run ``_menu_loop`` with the screen and the picker answering from
        lists; return its result and how often each was asked."""
        from src import onboarding_flow, start_flow
        asked = {"screen": 0, "picker": []}
        screen_answers, picker_answers = list(screen_answers), list(picker_answers)

        def screen(_parent, at_launch=False):
            asked["screen"] += 1
            return screen_answers.pop(0)

        def picker(_parent, *, listed):
            asked["picker"].append(listed)
            return picker_answers.pop(0)

        self.addCleanup(setattr, onboarding_flow, "_open_menu",
                        onboarding_flow._open_menu)
        self.addCleanup(setattr, start_flow, "choose_design",
                        start_flow.choose_design)
        onboarding_flow._open_menu = screen
        start_flow.choose_design = picker
        return onboarding_flow._menu_loop(None, at_launch=True), asked

    def test_a_design_picked_from_the_list_comes_back_as_that_design(self):
        from src import start_flow, start_screen
        choice, asked = self._scripted([start_screen.ALL_DESIGNS],
                                       ["/x/Yard.perma.geojson"])
        self.assertEqual(choice, start_flow.path_choice("/x/Yard.perma.geojson"))
        self.assertEqual(asked["picker"], [True])

    def test_cancel_goes_back_to_the_start_screen(self):
        from src import start_screen
        choice, asked = self._scripted(
            [start_screen.ALL_DESIGNS, start_screen.OPEN_FILE,
             start_screen.EXAMPLE], ["", ""])
        self.assertEqual(choice, start_screen.EXAMPLE)
        self.assertEqual(asked["screen"], 3)
        self.assertEqual(asked["picker"], [True, False])

    def test_end_to_end_no_window_until_a_design_is_opened(self):
        """A real start screen, a real click on "All 4 designs…", a real list
        over it, a real Open; and no main window anywhere."""
        from PyQt6.QtCore import QTimer
        from src import onboarding_flow, saves_dialog, start_flow, start_screen
        newest = self.write("a.perma.geojson", "Front", age=60)
        self.write("b.perma.geojson", "Back", age=3600)
        self.write("c.perma.geojson", "Side", age=7200)
        self.write("d.perma.geojson", "Old", age=86400)
        fake = SimpleNamespace(d={})
        fake.value = lambda k, default=None, type=None: fake.d.get(k, default)
        fake.setValue = lambda k, v: fake.d.__setitem__(k, v)
        for mod, name, value in (
                (onboarding_flow, "_settings", lambda: fake),
                (onboarding_flow, "_autosave_pending", lambda: False),
                (start_flow, "flowering", lambda month=None: ("", ""))):
            self.addCleanup(setattr, mod, name, getattr(mod, name))
            setattr(mod, name, value)
        seen = {}

        def _on_screen():
            dlg = QApplication.activeModalWidget()
            if not isinstance(dlg, start_screen.StartScreen):
                return _bail()
            link = next((b for b in dlg.findChildren(QPushButton)
                         if b.text() == "All 4 designs…"), None)
            if link is None:
                return _bail()
            QTimer.singleShot(0, _on_list)
            link.click()

        def _on_list():
            dlg = QApplication.activeModalWidget()
            seen["list"] = type(dlg).__name__
            seen["parent"] = dlg.parent() if dlg is not None else "none"
            seen["windows"] = [w for w in QApplication.topLevelWidgets()
                               if isinstance(w, QMainWindow) and w.isVisible()]
            if not isinstance(dlg, saves_dialog.SavesDialog):
                return _bail()
            seen["rows"] = dlg._list.count()
            seen["styled"] = bool(dlg.styleSheet())
            dlg._list.setCurrentRow(0)
            dlg._open()

        def _bail():
            dlg = QApplication.activeModalWidget()
            if dlg is not None:
                dlg.reject()

        QTimer.singleShot(0, _on_screen)
        for delay in (4000, 4500, 5000):
            QTimer.singleShot(delay, _bail)          # never hang the suite
        choice = onboarding_flow.choose_start_action()

        self.assertEqual(seen.get("list"), "SavesDialog")
        self.assertIsNone(seen["parent"])
        self.assertEqual(seen["windows"], [])
        self.assertEqual(seen["rows"], 4)      # what "All 4 designs…" said
        self.assertTrue(seen["styled"])
        self.assertEqual(choice, start_flow.path_choice(newest))


@unittest.skipUnless(_HAVE_QT, "PyQt6 not installed in this env")
class TheSavesList(_TempSaves):

    @classmethod
    def setUpClass(cls):
        cls._app = QApplication.instance() or QApplication(["permadesign-tests"])

    def test_no_sideways_scroll_bar_and_its_own_dark_stripe(self):
        from PyQt6.QtCore import Qt
        from src.saves_dialog import SavesDialog
        dlg = SavesDialog()
        self.addCleanup(dlg.deleteLater)
        self.assertEqual(dlg._list.horizontalScrollBarPolicy(),
                         Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.assertIn("alternate-background-color", dlg._list.styleSheet())

    def test_a_design_kept_elsewhere_cannot_be_deleted_from_here(self):
        self.write("a.perma.geojson", "Here", age=3600)
        outside = tempfile.mkdtemp(prefix="sp_out_")
        self.addCleanup(shutil.rmtree, outside, ignore_errors=True)
        far = self.write("far.perma.geojson", "Elsewhere", folder=outside)
        saves.remember_last_design(far)
        from src.saves_dialog import SavesDialog
        dlg = SavesDialog()
        self.addCleanup(dlg.deleteLater)
        self.assertEqual(dlg._list.count(), 2)
        self.assertNotIn("saves folder", dlg._blurb.text())
        dlg._list.setCurrentRow(0)             # Elsewhere, the newest
        self.assertFalse(dlg._btn_delete.isEnabled())
        self.assertTrue(dlg._btn_rename.isEnabled())
        dlg._list.setCurrentRow(1)
        self.assertTrue(dlg._btn_delete.isEnabled())


# ── The recovery copy ───────────────────────────────────────────────────────

class ASessionsOwnRecoveryCopyGoesOnACleanClose(unittest.TestCase):
    """The cycle behind the owner's "(unsaved changes from …)" designs: the
    recovery check stands aside while the start screen is up, passing over
    Restore left it unanswered all session, and a clean close then kept the
    session's own recovery copy for the next launch to offer."""

    def setUp(self):
        from src.controllers import persistence as pmod
        self.pmod = pmod
        self.dir = tempfile.mkdtemp(prefix="sp_auto_")
        self.addCleanup(shutil.rmtree, self.dir, ignore_errors=True)
        self.addCleanup(setattr, pmod, "autosave_path", pmod.autosave_path)
        pmod.autosave_path = lambda: os.path.join(self.dir, "auto.perma.geojson")

    def test_the_session_marks_its_own_copy_and_never_offers_it_back(self):
        from src import onboarding_flow
        self.addCleanup(setattr, onboarding_flow, "should_show_welcome",
                        onboarding_flow.should_show_welcome)
        onboarding_flow.should_show_welcome = lambda: True
        crash = self.pmod.autosave_path()
        with open(crash, "w", encoding="utf-8") as f:
            json.dump({"properties": {"project_name": "Yard"}, "features": []}, f)
        main = SimpleNamespace(_modified=True, _project_path=None,
                               _project={"properties": {"project_name": "New"},
                                         "features": []})
        p = self.pmod.PersistenceController(main)
        p.maybe_offer_autosave_recovery()       # the screen is up: aside
        self.assertFalse(getattr(p, "_recovery_checked", False))
        self.assertTrue(saves.keep_unsaved(crash, directory=self.dir))
        p._autosave()                           # this session's own copy
        self.assertTrue(p._wrote_autosave)
        p.maybe_offer_autosave_recovery()       # a late page load
        self.assertTrue(p._recovery_checked)
        self.assertTrue(os.path.exists(crash), "it offered or ate its own copy")

    def test_close_clears_it_whatever_became_of_the_check(self):
        tree = ast.parse((_SRC / "app.py").read_text(encoding="utf-8"))
        fn = next(n for n in ast.walk(tree)
                  if isinstance(n, ast.FunctionDef) and n.name == "closeEvent")
        guard = next(n for n in ast.walk(fn) if isinstance(n, ast.If)
                     and "clear_autosave" in ast.dump(n))
        self.assertIn("_wrote_autosave", ast.dump(guard.test))
        self.assertIn("_recovery_checked", ast.dump(guard.test))


# ── Words ───────────────────────────────────────────────────────────────────

class MoistureInPlainWords(unittest.TestCase):
    """The owner: "mesic" is not understandable to many."""

    def test_the_middle_of_the_scale_is_medium_moisture(self):
        from src.db import polycultures
        self.assertEqual(polycultures._community_moisture(
            [{"water": "medium"}, {"water": "moderate"}]), "Medium moisture")
        self.assertEqual(polycultures._community_moisture([{"water": "low"}]),
                         "Dry")

    def test_no_filter_choice_says_a_word_the_glossary_keeps_out(self):
        from src import vocabulary
        from src.db import polycultures
        self.assertIn("mesic", vocabulary.NEVER)
        choices = polycultures.facet_filter_choices()
        self.assertEqual(choices["moisture"], ["Dry", "Medium moisture", "Wet"])
        from tests.test_vocabulary import _pattern
        for facet, labels in choices.items():
            for label in labels:
                for word in vocabulary.NEVER:
                    self.assertIsNone(_pattern(word).search(label),
                                      (facet, label, word))


if __name__ == "__main__":
    unittest.main()

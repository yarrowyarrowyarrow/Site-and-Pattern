"""
tests/test_windows_update_flow.py

Check for Updates on an installed Windows copy, in one click (F228, V3.15).

Until V3.15 the app started the downloaded installer and stayed open, and the
installer stopped on "Error opening file for writing: ...SiteAndPattern.exe",
because Windows will not let a running program's files be opened for writing.
Now the app settles unsaved work, starts the installer in update mode with its
own folder, and closes every window; the installer waits for it, replaces the
program and reopens it (scripts/packaging/installer.nsi, pinned by
tests/test_installer_script.py).

Driven through UpdateFlowController with the dialogs, os.startfile and the
window replaced, so it runs on any OS. Needs PyQt6 to import the controller;
no QApplication and no widget is made.
"""

from __future__ import annotations

import ntpath
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from PyQt6.QtWidgets import QMessageBox
    from src.controllers import update_flow
    _HAVE_QT = True
except Exception:                                          # noqa: BLE001
    _HAVE_QT = False

_EXE = r"C:\Program Files (x86)\Site & Pattern\SiteAndPattern.exe"
_SETUP = r"C:\Users\friend\Downloads\SiteAndPattern-V3.15-Setup.exe"


class _Button:
    def __init__(self, text):
        self.text = text


class _Box:
    """Stands in for QMessageBox: records what was asked and clicks the
    button named in ``answer``."""
    Icon = QMessageBox.Icon if _HAVE_QT else None
    StandardButton = QMessageBox.StandardButton if _HAVE_QT else None
    ButtonRole = QMessageBox.ButtonRole if _HAVE_QT else None
    answer = None
    shown: list = []
    infos: list = []

    def __init__(self, icon, title, text, buttons=None, parent=None):
        self.title, self.text, self.buttons = title, text, []
        self._clicked = None
        _Box.shown.append(self)

    def addButton(self, text, role):
        b = _Button(text)
        self.buttons.append(b)
        return b

    def setDefaultButton(self, button):
        self.default = button

    def exec(self):
        self._clicked = next(
            (b for b in self.buttons if b.text == _Box.answer), None)

    def clickedButton(self):
        return self._clicked

    @staticmethod
    def information(parent, title, text, *a, **k):
        _Box.infos.append((title, text))

    @staticmethod
    def question(*a, **k):
        raise AssertionError("Windows asks with named buttons, not Yes/No")


class _Main:
    """The parts of MainWindow the hand-over touches."""

    def __init__(self, modified=False, save_works=True):
        self._modified = modified
        self.save_works = save_works
        self.saved = self.closed = False
        self.messages = []

    def _on_save(self):
        self.saved = True
        if self.save_works:
            self._modified = False

    def close(self):
        # closeEvent asks "Exit anyway?" while unsaved: the hand-over must
        # have settled that before it gets here, or the installer waits on a
        # question nobody was told about.
        assert not self._modified, "closed while still unsaved"
        self.closed = True
        return True

    def statusBar(self):
        return self

    def showMessage(self, text, *_):
        self.messages.append(text)


@unittest.skipUnless(_HAVE_QT, "PyQt6 not installed in this env")
class TestOneClickUpdateOnWindows(unittest.TestCase):

    def setUp(self):
        _Box.answer, _Box.shown, _Box.infos = None, [], []
        self.started = []
        self.qapp = mock.MagicMock()
        patches = [
            mock.patch.object(update_flow, "QMessageBox", _Box),
            mock.patch.object(update_flow, "QApplication", self.qapp,
                              create=True),
            mock.patch.object(update_flow.sys, "platform", "win32"),
            mock.patch.object(update_flow.sys, "executable", _EXE),
            # Windows path rules, so a C: path reads as the absolute path it is.
            mock.patch.object(update_flow.os, "path", ntpath),
            mock.patch.object(update_flow.os, "startfile", create=True,
                              side_effect=self._startfile),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)
        self.refuse = None

    def _startfile(self, path, operation=None, arguments=""):
        if self.refuse:
            raise self.refuse
        self.started.append((path, arguments))

    def _run(self, main):
        update_flow.UpdateFlowController(main)._open_installer(
            _SETUP, "release-V3.15")

    def test_a_saved_design_hands_over_and_closes(self):
        main = _Main()
        self._run(main)
        self.assertEqual(self.started, [(
            _SETUP,
            r"/UPDATE /D=C:\Program Files (x86)\Site & Pattern")])
        self.assertTrue(main.closed)
        # Any other window (a Learn window, the Field Guide) would keep the
        # process, and its files, alive.
        self.qapp.closeAllWindows.assert_called_once()
        self.assertEqual(_Box.shown, [], "a clean design needs no question")

    def test_unsaved_work_is_saved_first_by_default(self):
        main = _Main(modified=True)
        _Box.answer = "Save and update"
        self._run(main)
        (box,) = _Box.shown
        self.assertIs(box.default, box.buttons[0])
        self.assertEqual(box.buttons[0].text, "Save and update")
        self.assertIn("V3.15", box.text)
        self.assertNotIn("release-", box.text)
        self.assertTrue(main.saved)
        self.assertEqual(len(self.started), 1)
        self.assertTrue(main.closed)

    def test_a_failed_save_installs_nothing(self):
        main = _Main(modified=True, save_works=False)
        _Box.answer = "Save and update"
        self._run(main)
        self.assertEqual(self.started, [])
        self.assertFalse(main.closed)
        self.assertTrue(main._modified)

    def test_cancel_keeps_the_app_open_and_says_so(self):
        main = _Main(modified=True)
        _Box.answer = "Cancel"
        self._run(main)
        self.assertEqual(self.started, [])
        self.assertFalse(main.closed)
        self.assertTrue(main._modified)
        self.assertTrue(any("V3.15 was not installed" in m
                            for m in main.messages))

    def test_updating_without_saving_closes_without_asking_again(self):
        main = _Main(modified=True)
        _Box.answer = "Update without saving"
        self._run(main)
        self.assertFalse(main.saved)
        self.assertEqual(len(self.started), 1)
        self.assertTrue(main.closed)        # _Main.close asserts it was settled

    def test_no_to_the_windows_prompt_changes_nothing(self):
        main = _Main(modified=True)
        _Box.answer = "Update without saving"
        self.refuse = OSError(22, "The operation was canceled by the user")
        self._run(main)
        self.assertFalse(main.closed)
        self.assertTrue(main._modified, "the design is still unsaved, and "
                                        "the app must still say so on exit")
        ((title, text),) = _Box.infos
        self.assertEqual(title, "Update not installed")
        self.assertIn("nothing has changed", text)

    def test_the_offer_says_what_will_happen_before_it_happens(self):
        ctl = update_flow.UpdateFlowController(_Main())
        asset = mock.Mock(size=250 * 1024 * 1024)
        release = mock.Mock(tag="release-V3.15", body="")
        release.asset_for_extensions.return_value = asset
        with mock.patch.object(ctl, "_download_and_open") as download:
            _Box.answer = "Not now"
            ctl._offer_frozen_download(release, "V3.14")
            download.assert_not_called()
            _Box.answer = "Update now"
            ctl._offer_frozen_download(release, "V3.14")
            download.assert_called_once_with(asset, "release-V3.15")
        text = _Box.shown[-1].text
        self.assertIn("closes Site & Pattern, installs it and opens it again",
                      text)
        self.assertIn("choose Yes", text)
        self.assertIn("Latest:      V3.15", text)


if __name__ == "__main__":
    unittest.main()

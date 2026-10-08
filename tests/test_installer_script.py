"""
tests/test_installer_script.py

The Windows installer and the app that starts it agree (F228, V3.15).

A friend's update stopped on NSIS's "Error opening file for writing:
...\\SiteAndPattern.exe": the app started the installer and stayed open, and
Windows will not let a running program's files be opened for writing. From
V3.15 the app starts the installer in update mode and closes; the installer
waits for it, replaces the program and opens it again. That hand-over is a
contract between two files in two languages, and the release build is the
first thing that runs the installer, so it is pinned here: the switch spelled
the same on both sides, nothing copied before the app has closed, no Ignore
on a locked file, the app never reopened as administrator, an uninstaller that
exists and removes only what it installed. And, where NSIS is installed, that
the script compiles with warnings treated as errors, which is how V3.15 found
the uninstaller that had never been written.

Qt-free.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import github_releases as ghr  # noqa: E402

_NSI = (Path(__file__).resolve().parent.parent
        / "scripts" / "packaging" / "installer.nsi")


def _code_lines(text: str) -> list[str]:
    """The script's lines with comments and blank lines dropped. NSIS
    comments start a line with ``;`` or ``#``; this script has no trailing
    ones."""
    out = []
    for line in text.splitlines():
        s = line.strip()
        if s and not s.startswith((";", "#")):
            out.append(s)
    return out


def _main_section(lines: list[str]) -> list[str]:
    start = next(i for i, s in enumerate(lines)
                 if s.startswith('Section "Site & Pattern"'))
    end = next(i for i in range(start, len(lines)) if lines[i] == "SectionEnd")
    return lines[start:end]


class TestTheInstallerAndTheAppAgree(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.text = _NSI.read_text(encoding="utf-8")
        cls.lines = _code_lines(cls.text)

    def test_the_update_switch_is_spelled_the_same_in_both(self):
        read = re.findall(r'\$\{GetOptions\}\s+\$\w+\s+"([^"]+)"', self.text)
        self.assertEqual(
            read, [ghr.UPDATE_SWITCH],
            "installer.nsi must read the switch the app passes "
            "(github_releases.UPDATE_SWITCH); a mismatch leaves every update "
            "on the folder page with the app still open, which is V3.14")

    def test_the_folder_is_the_last_argument_and_bare(self):
        folder = r"C:\Program Files (x86)\Site & Pattern"
        args = ghr.installer_update_arguments(folder)
        self.assertTrue(args.startswith(ghr.UPDATE_SWITCH + " "), args)
        # NSIS reads /D= only last, takes the rest of the line, and does not
        # strip quotes: a quoted folder would be a folder named with quotes.
        self.assertTrue(args.endswith(" /D=" + folder), args)
        self.assertNotIn('"', args)

    def test_nothing_is_copied_before_the_app_has_closed(self):
        section = _main_section(self.lines)
        self.assertIn("Call WaitForAppToClose", section,
                      "the installer no longer waits for the app to close")
        wait = section.index("Call WaitForAppToClose")
        for step in ('RMDir /r "$INSTDIR\\_internal"',
                     'File /r "..\\..\\dist\\SiteAndPattern\\*.*"'):
            self.assertIn(step, section)
            self.assertLess(wait, section.index(step),
                            f"{step} runs before the installer has waited for "
                            "the app to let go of its files")

    def test_a_locked_file_is_never_skipped(self):
        # "Ignore" on a locked SiteAndPattern.exe kept the old program and
        # replaced the loose version.txt beside it: the old code reported the
        # new version, and Check for Updates called it up to date.
        self.assertIn("AllowSkipFiles off", self.lines)

    def test_the_app_is_never_started_as_administrator(self):
        launches = [s for s in self.lines
                    if s.startswith(("Exec ", "ExecWait ", "ExecShell "))]
        self.assertTrue(launches, "nothing opens the app after an update")
        for s in launches:
            self.assertIn("explorer.exe", s,
                          f"{s!r}: this installer runs as administrator, and "
                          "a program it starts directly runs as one too")
        # MUI's own Run checkbox Execs the file it names; it must call the
        # function instead, which goes through Explorer.
        self.assertIn("!define MUI_FINISHPAGE_RUN", self.lines)
        self.assertIn("!define MUI_FINISHPAGE_RUN_FUNCTION OpenAppAsUser",
                      self.lines)

    def test_update_mode_skips_the_pages_and_reopens_the_app(self):
        pre = [i for i, s in enumerate(self.lines)
               if s == "!define MUI_PAGE_CUSTOMFUNCTION_PRE SkipInUpdateMode"]
        pages = [i for i, s in enumerate(self.lines)
                 if s.startswith("!insertmacro MUI_PAGE_")]
        self.assertEqual(len(pre), 2, "the folder and finish pages are both "
                                      "skipped in update mode")
        skipped = {self.lines[min(p for p in pages if p > i)] for i in pre}
        self.assertEqual(skipped, {"!insertmacro MUI_PAGE_DIRECTORY",
                                   "!insertmacro MUI_PAGE_FINISH"})
        on_success = self.text.split("Function .onInstSuccess", 1)[1]
        self.assertIn("Call OpenAppAsUser",
                      on_success.split("FunctionEnd", 1)[0])

    def test_the_uninstaller_exists_and_takes_only_what_it_installed(self):
        self.assertIn('WriteUninstaller "$INSTDIR\\Uninstall.exe"', self.lines)
        # A folder typed on the folder page (C:\Tools) would go with all of
        # its contents under RMDir /r "$INSTDIR". Only an empty one may go.
        for s in self.lines:
            self.assertNotRegex(s, r'^RMDir\s+/r\s+"\$INSTDIR"$')
        self.assertIn('RMDir "$INSTDIR"', self.lines)


class TestTheInstallerCompiles(unittest.TestCase):
    """Built the way the release workflow builds it, against a stand-in
    bundle, with every warning an error. Skips where NSIS is not installed;
    CI installs it (tests.yml)."""

    @unittest.skipUnless(shutil.which("makensis"), "NSIS (makensis) not installed")
    def test_it_compiles_without_a_warning(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "scripts" / "packaging").mkdir(parents=True)
            shutil.copy(_NSI, root / "scripts" / "packaging" / "installer.nsi")
            bundle = root / "dist" / "SiteAndPattern"
            (bundle / "_internal").mkdir(parents=True)
            (bundle / "SiteAndPattern.exe").write_bytes(b"stand-in")
            (bundle / "_internal" / "version.txt").write_text("V0.0\n",
                                                              encoding="utf-8")
            # build_installer.bat writes it with echo: CRLF.
            (root / "version.txt").write_bytes(b"V0.0\r\n")
            run = subprocess.run(
                ["makensis", "-WX", "-V2", "installer.nsi"],
                cwd=root / "scripts" / "packaging",
                capture_output=True, text=True, encoding="utf-8",
                errors="replace", timeout=120)
            self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
            self.assertTrue((root / "SiteAndPattern-Installer.exe").exists())


if __name__ == "__main__":
    unittest.main()

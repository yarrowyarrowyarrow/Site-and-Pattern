"""
tests/test_app_version.py

The version in the title bar (F231, V3.16): ``branding.window_title`` and
``app_version.running_version``, which the title and the Help menu's
"About / Version" both read. Qt-free, so these run without PyQt6.

The title is the quickest check that an update arrived whole: the words come
from the program, the number from the ``version.txt`` installed beside it.
"""

import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import app_version  # noqa: E402
from src.app_version import checkout_branch, running_version  # noqa: E402
from src.branding import APP_TITLE, window_title  # noqa: E402
from src.version_branch import normalize_branch_ref  # noqa: E402

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class WindowTitleTest(unittest.TestCase):
    def test_a_copy_that_knows_no_version_reads_as_before(self):
        self.assertEqual(window_title(version=None), APP_TITLE)
        self.assertEqual(window_title("My Yard", version=None),
                         "Site & Pattern — My Yard")

    def test_the_version_follows_the_name(self):
        self.assertEqual(window_title(version="V3.16"),
                         "Site & Pattern V3.16 — Native Habitat Designer")
        self.assertEqual(window_title("My Yard", version="V3.16"),
                         "Site & Pattern V3.16 — My Yard")

    def test_a_design_with_no_name_shows_the_tagline(self):
        self.assertEqual(window_title("", version="V3.16"),
                         window_title(version="V3.16"))

    def test_the_version_cannot_be_left_out_by_accident(self):
        with self.assertRaises(TypeError):
            window_title("My Yard")


class CheckoutBranchTest(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="sp_head_")
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)

    def _head(self, text):
        os.makedirs(os.path.join(self.root, ".git"), exist_ok=True)
        with open(os.path.join(self.root, ".git", "HEAD"), "w",
                  encoding="utf-8") as f:
            f.write(text)

    def test_a_branch(self):
        self._head("ref: refs/heads/V3.16\n")
        self.assertEqual(checkout_branch(self.root), "V3.16")
        self._head("ref: refs/heads/main\n")
        self.assertEqual(checkout_branch(self.root), "main")

    def test_a_detached_head_names_no_branch(self):
        self._head("305e55e034416fd3bf3064439a50073107fb2163\n")
        self.assertIsNone(checkout_branch(self.root))

    def test_no_checkout(self):
        self.assertIsNone(checkout_branch(self.root))

    def test_a_worktree_is_not_read(self):
        # There .git is a file pointing elsewhere; update_flow._repo_path
        # does not treat it as a checkout either.
        with open(os.path.join(self.root, ".git"), "w", encoding="utf-8") as f:
            f.write("gitdir: /elsewhere\n")
        self.assertIsNone(checkout_branch(self.root))

    def test_it_agrees_with_git_on_this_checkout(self):
        if not os.path.isdir(os.path.join(_ROOT, ".git")):
            self.skipTest("not a plain git checkout")
        try:
            res = subprocess.run(
                ["git", "-C", _ROOT, "rev-parse", "--abbrev-ref", "HEAD"],
                capture_output=True, encoding="utf-8", errors="replace",
                timeout=10)
        except (OSError, subprocess.SubprocessError):
            self.skipTest("git is not available")
        if res.returncode != 0:
            self.skipTest("git could not read this checkout")
        said = normalize_branch_ref(res.stdout.strip())
        self.assertEqual(checkout_branch(),
                         None if said == "HEAD" else said)


class RunningVersionTest(unittest.TestCase):
    def setUp(self):
        running_version.cache_clear()
        self.addCleanup(running_version.cache_clear)

    def _patch(self, patcher):
        # TestCase.enterContext is 3.11+, and the app supports 3.10.
        started = patcher.start()
        self.addCleanup(patcher.stop)
        return started

    def _as(self, frozen):
        """Run as a frozen build (True) or a source checkout (False)."""
        if frozen:
            self._patch(mock.patch.object(sys, "frozen", True, create=True))
        elif hasattr(sys, "frozen"):
            self._patch(mock.patch.object(sys, "frozen", False))

    def _with(self, *, build, branch):
        self._patch(mock.patch.object(
            app_version, "build_version", return_value=build))
        return self._patch(mock.patch.object(
            app_version, "checkout_branch", return_value=branch))

    def test_an_installed_copy_names_its_version_txt(self):
        # End to end, through the bundle a frozen build reads, with the CRLF
        # build_installer.bat's `echo` writes.
        bundle = tempfile.mkdtemp(prefix="sp_meipass_")
        self.addCleanup(shutil.rmtree, bundle, ignore_errors=True)
        with open(os.path.join(bundle, "version.txt"), "w",
                  encoding="utf-8", newline="") as f:
            f.write("V3.16\r\n")
        self._as(frozen=True)
        self._patch(mock.patch.object(sys, "_MEIPASS", bundle, create=True))
        self.assertEqual(running_version(), "V3.16")

    def test_an_installed_copy_never_asks_git(self):
        self._as(frozen=True)
        branch = self._with(build=None, branch="V3.16")
        self.assertIsNone(running_version())
        branch.assert_not_called()

    def test_a_build_from_no_release_names_none(self):
        self._as(frozen=True)
        self._with(build="claude/some-branch", branch=None)
        self.assertIsNone(running_version())

    def test_a_source_checkout_names_its_release_branch(self):
        self._as(frozen=False)
        self._with(build=None, branch="V3.16")
        self.assertEqual(running_version(), "V3.16")

    def test_a_development_branch_names_none(self):
        for branch in ("main", "ccr-6889d8ee-wh9752", None):
            running_version.cache_clear()
            with self.subTest(branch=branch):
                self._as(frozen=False)
                self._with(build=None, branch=branch)
                self.assertIsNone(running_version())

    def test_it_is_read_once_per_run(self):
        # It names what is running: a source update switches the branch,
        # then offers a restart, and until then the old code runs.
        self._as(frozen=False)
        branch = self._with(build=None, branch="V3.16")
        self.assertEqual(running_version(), "V3.16")
        branch.return_value = "V3.17"
        self.assertEqual(running_version(), "V3.16")
        self.assertEqual(branch.call_count, 1)


if __name__ == "__main__":
    unittest.main()

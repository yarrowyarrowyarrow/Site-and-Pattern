"""
tests/test_version_branch.py

Verifies the V<major>.<minor> branch helpers introduced in V1.32 for the
"Check for Updates" auto-switch flow. The helpers live in
``src/version_branch.py`` as Qt-free pure functions so they can be tested
without PyQt6 in the environment.
"""

import os
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.version_branch import (  # noqa: E402
    parse_version_branch,
    is_newer_version,
    newest_remote_version_branch,
)


class TestParseVersionBranch(unittest.TestCase):

    def test_valid_versions(self):
        for name, expected in [
            ("V1.31", (1, 31)),
            ("V1.32", (1, 32)),
            ("V2.0",  (2, 0)),
            ("V10.5", (10, 5)),
            ("V0.1",  (0, 1)),
        ]:
            with self.subTest(name=name):
                self.assertEqual(parse_version_branch(name), expected)

    def test_invalid_versions(self):
        for name in [
            "main",
            "V1",
            "1.31",
            "v1.31",            # lowercase v — convention is strict
            "V1.31-beta",
            "feature/V1.31",
            "claude/wizardly-goldberg-Ntd5l",
            "",
            "V.1.31",
            None,
        ]:
            with self.subTest(name=repr(name)):
                self.assertIsNone(parse_version_branch(name))


class TestIsNewerVersion(unittest.TestCase):

    def test_strictly_higher_is_newer(self):
        self.assertTrue(is_newer_version("V1.32", "V1.31"))
        self.assertTrue(is_newer_version("V2.0", "V1.99"))
        self.assertTrue(is_newer_version("V1.100", "V1.31"))

    def test_equal_is_not_newer(self):
        self.assertFalse(is_newer_version("V1.31", "V1.31"))

    def test_lower_is_not_newer(self):
        self.assertFalse(is_newer_version("V1.30", "V1.31"))
        self.assertFalse(is_newer_version("V1.31", "V1.32"))

    def test_non_version_current_treats_any_v_as_newer(self):
        """If the user is on a dev/codename branch, any published V-branch
        counts as 'newer' — V-branches are the canonical release line."""
        self.assertTrue(is_newer_version("V1.31", "main"))
        self.assertTrue(is_newer_version("V1.31", "claude/wizardly-goldberg-Ntd5l"))
        self.assertTrue(is_newer_version("V1.31", "feature/foo"))

    def test_non_version_target_is_never_newer(self):
        """A non V-branch on the remote should never trigger a switch
        prompt — we only auto-switch to release-line branches."""
        self.assertFalse(is_newer_version("main", "V1.31"))
        self.assertFalse(is_newer_version("develop", "main"))
        self.assertFalse(is_newer_version("feature/foo", "V1.31"))


class TestNewestRemoteVersionBranch(unittest.TestCase):
    """Drive ``newest_remote_version_branch`` against an actual git repo on
    disk so we exercise the ``for-each-ref`` parser end-to-end."""

    def setUp(self):
        self._tmp = tempfile.mkdtemp(prefix="permadesign_branchtest_")
        self.addCleanup(lambda: shutil.rmtree(self._tmp, ignore_errors=True))
        self._init_repo()

    def _run_upstream(self, *args):
        return subprocess.run(
            ["git", "-C", self._upstream, *args],
            capture_output=True, text=True, check=False,
        )

    def _init_repo(self):
        # "Upstream" repo with an initial commit on main. We disable commit
        # signing locally in the temp repo — some CI / sandboxed shells
        # have signing enforced globally, which would break the test
        # infrastructure even though we're not producing real commits.
        self._upstream = os.path.join(self._tmp, "upstream")
        os.makedirs(self._upstream)
        subprocess.run(
            ["git", "init", "-q", "-b", "main", self._upstream], check=True
        )
        self._run_upstream("config", "user.email", "t@t")
        self._run_upstream("config", "user.name", "T")
        self._run_upstream("config", "commit.gpgsign", "false")
        self._run_upstream("config", "tag.gpgsign", "false")
        with open(os.path.join(self._upstream, "f"), "w") as f:
            f.write("hi\n")
        self._run_upstream("add", "f")
        self._run_upstream("commit", "-q", "-m", "init")

        # Clone — "downstream" is the running app's checkout.
        self._downstream = os.path.join(self._tmp, "downstream")
        subprocess.run(
            ["git", "clone", "-q", self._upstream, self._downstream], check=True
        )

    def _git_runner(self):
        """Match the closure shape used inside _on_check_for_updates."""
        def _git(*args, timeout=10):
            return subprocess.run(
                ["git", "-C", self._downstream, *args],
                capture_output=True, text=True, timeout=timeout, check=False,
            )
        return _git

    def _make_remote_branch(self, name):
        self._run_upstream("checkout", "-q", "-b", name)
        # Sanitize the branch name to a flat filename — slashes in branch
        # names (e.g. "feature/foo") would otherwise become subdirectories.
        safe = name.replace("/", "_")
        with open(os.path.join(self._upstream, safe + ".txt"), "w") as f:
            f.write(name)
        self._run_upstream("add", ".")
        self._run_upstream("commit", "-q", "-m", name)
        self._run_upstream("checkout", "-q", "main")

    # ── Tests ────────────────────────────────────────────────────────────

    def test_no_version_branches_returns_none(self):
        gr = self._git_runner()
        gr("fetch", "--quiet")
        self.assertIsNone(newest_remote_version_branch(gr))

    def test_finds_single_version_branch(self):
        self._make_remote_branch("V1.31")
        gr = self._git_runner()
        gr("fetch", "--quiet")
        self.assertEqual(newest_remote_version_branch(gr), "V1.31")

    def test_picks_highest_of_several(self):
        for name in ["V1.30", "V1.31", "V1.32", "V1.5", "main-dev"]:
            self._make_remote_branch(name)
        gr = self._git_runner()
        gr("fetch", "--quiet")
        self.assertEqual(newest_remote_version_branch(gr), "V1.32")

    def test_ignores_non_version_branches(self):
        for name in ["feature/foo", "develop", "release-1.31", "v1.31"]:
            self._make_remote_branch(name)
        gr = self._git_runner()
        gr("fetch", "--quiet")
        self.assertIsNone(newest_remote_version_branch(gr))

    def test_major_version_numeric_sort(self):
        """V2.0 > V1.99 (numeric sort, not lexical 'V1.99' > 'V2.0')."""
        self._make_remote_branch("V1.99")
        self._make_remote_branch("V2.0")
        gr = self._git_runner()
        gr("fetch", "--quiet")
        self.assertEqual(newest_remote_version_branch(gr), "V2.0")

    def test_minor_version_numeric_sort(self):
        """V1.100 > V1.99 (numeric sort)."""
        self._make_remote_branch("V1.99")
        self._make_remote_branch("V1.100")
        gr = self._git_runner()
        gr("fetch", "--quiet")
        self.assertEqual(newest_remote_version_branch(gr), "V1.100")


if __name__ == "__main__":
    unittest.main()

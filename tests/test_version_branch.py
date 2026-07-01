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
    next_version_branch,
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


class TestNextVersionBranch(unittest.TestCase):
    """``next_version_branch`` drives the branch-policy hook: it decides which
    V-branch a session should land on. Exercised against a real git repo so the
    ``for-each-ref`` parse + increment run end-to-end."""

    def setUp(self):
        self._tmp = tempfile.mkdtemp(prefix="permadesign_nextbranch_")
        self.addCleanup(lambda: shutil.rmtree(self._tmp, ignore_errors=True))
        self._upstream = os.path.join(self._tmp, "upstream")
        os.makedirs(self._upstream)
        subprocess.run(["git", "init", "-q", "-b", "main", self._upstream],
                       check=True)
        self._run_upstream("config", "user.email", "t@t")
        self._run_upstream("config", "user.name", "T")
        self._run_upstream("config", "commit.gpgsign", "false")
        with open(os.path.join(self._upstream, "f"), "w") as f:
            f.write("hi\n")
        self._run_upstream("add", "f")
        self._run_upstream("commit", "-q", "-m", "init")
        self._downstream = os.path.join(self._tmp, "downstream")
        subprocess.run(["git", "clone", "-q", self._upstream, self._downstream],
                       check=True)

    def _run_upstream(self, *args):
        return subprocess.run(["git", "-C", self._upstream, *args],
                              capture_output=True, text=True, check=False)

    def _git_runner(self):
        def _git(*args, timeout=10):
            return subprocess.run(
                ["git", "-C", self._downstream, *args],
                capture_output=True, text=True, timeout=timeout, check=False,
            )
        return _git

    def _make_remote_branch(self, name):
        self._run_upstream("checkout", "-q", "-b", name)
        safe = name.replace("/", "_")
        with open(os.path.join(self._upstream, safe + ".txt"), "w") as f:
            f.write(name)
        self._run_upstream("add", ".")
        self._run_upstream("commit", "-q", "-m", name)
        self._run_upstream("checkout", "-q", "main")

    def test_none_when_no_version_branches(self):
        gr = self._git_runner()
        gr("fetch", "--quiet")
        self.assertIsNone(next_version_branch(gr, current="claude/foo-bar"))

    def test_increments_newest_minor(self):
        self._make_remote_branch("V2.05")
        gr = self._git_runner()
        gr("fetch", "--quiet")
        self.assertEqual(next_version_branch(gr, current="claude/foo-bar"),
                         "V2.06")

    def test_increments_highest_of_several(self):
        for name in ["V2.03", "V2.05", "V2.04", "main-dev"]:
            self._make_remote_branch(name)
        gr = self._git_runner()
        gr("fetch", "--quiet")
        self.assertEqual(next_version_branch(gr, current="main"), "V2.06")

    def test_keeps_current_when_already_a_version_branch(self):
        # A continuation of an existing release branch must NOT bump.
        self._make_remote_branch("V2.05")
        gr = self._git_runner()
        gr("fetch", "--quiet")
        self.assertEqual(next_version_branch(gr, current="V3.1"), "V3.1")
        self.assertEqual(next_version_branch(gr, current="  V2.05 "), "V2.05")

    def test_major_rollover_only_bumps_minor(self):
        self._make_remote_branch("V2.99")
        gr = self._git_runner()
        gr("fetch", "--quiet")
        # By convention only the minor increments (V2.99 → V2.100).
        self.assertEqual(next_version_branch(gr, current="main"), "V2.100")


class TestVersionBranchSwitchCheckout(unittest.TestCase):
    """Regression for the V1.77 detached-HEAD switch bug.

    The release workflow publishes a git TAG with the same name as the
    V-branch (tag ``V1.77`` next to branch ``V1.77``). With that tag present
    and no local branch yet, a bare ``git checkout V1.77`` resolves to the TAG
    and lands in DETACHED HEAD — the follow-up ``git pull`` then fails with
    "you are not currently on a branch" and the switch only half-completes.
    The updater (``_offer_branch_switch``) must instead use
    ``git checkout -B <v> origin/<v>`` so it always attaches to a real,
    tracking branch. Pure git — no Qt."""

    def setUp(self):
        self._tmp = tempfile.mkdtemp(prefix="permadesign_switchtest_")
        self.addCleanup(lambda: shutil.rmtree(self._tmp, ignore_errors=True))
        self._upstream = os.path.join(self._tmp, "upstream")
        os.makedirs(self._upstream)
        self._u("init", "-q", "-b", "main")
        self._u("config", "user.email", "t@t")
        self._u("config", "user.name", "T")
        self._u("config", "commit.gpgsign", "false")
        self._u("config", "tag.gpgsign", "false")
        self._write_commit("f", "hi", "init")
        # A release V-branch plus a TAG of the same name at its tip — exactly
        # the collision the GitHub release workflow produces.
        self._u("checkout", "-q", "-b", "V1.77")
        self._write_commit("v177.txt", "V1.77", "V1.77 work")
        self._u("tag", "V1.77")
        self._u("checkout", "-q", "main")
        self._downstream = os.path.join(self._tmp, "downstream")
        subprocess.run(["git", "clone", "-q", self._upstream, self._downstream],
                       check=True)
        self._d("fetch", "--quiet", "--tags", "origin")
        # Reproduce the user's broken state: detached HEAD on the initial commit
        # (no local V1.77 branch — this is a first-time switch to the version).
        init_sha = self._d("rev-parse", "HEAD").stdout.strip()
        self._d("checkout", "-q", init_sha)
        self.assertNotEqual(self._symbolic_ref().returncode, 0,
                            "test setup should start from a detached HEAD")

    def _u(self, *args):
        return subprocess.run(["git", "-C", self._upstream, *args],
                              capture_output=True, text=True, check=False)

    def _d(self, *args):
        return subprocess.run(["git", "-C", self._downstream, *args],
                              capture_output=True, text=True, check=False)

    def _write_commit(self, name, body, msg):
        with open(os.path.join(self._upstream, name), "w") as f:
            f.write(body + "\n")
        self._u("add", ".")
        self._u("commit", "-q", "-m", msg)

    def _symbolic_ref(self):
        # rc 0 + "refs/heads/<branch>" when attached; rc != 0 when detached.
        return self._d("symbolic-ref", "-q", "HEAD")

    def test_checkout_dash_B_attaches_to_branch_despite_tag(self):
        # The fix: explicit origin/<target> start-point → real tracking branch.
        r = self._d("checkout", "-B", "V1.77", "origin/V1.77")
        self.assertEqual(r.returncode, 0, r.stderr)
        sym = self._symbolic_ref()
        self.assertEqual(sym.returncode, 0, "HEAD is detached after the switch")
        self.assertEqual(sym.stdout.strip(), "refs/heads/V1.77")
        # The symptom was the follow-up pull failing; now it's a clean no-op.
        pull = self._d("pull", "--ff-only")
        self.assertEqual(pull.returncode, 0, pull.stderr)

    def test_bare_checkout_detaches_because_of_same_named_tag(self):
        # Documents the bug the fix avoids: with the tag present and no local
        # branch, a bare checkout lands on the tag in detached HEAD.
        r = self._d("checkout", "V1.77")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertNotEqual(
            self._symbolic_ref().returncode, 0,
            "bare `git checkout V1.77` should detach onto the same-named tag")


if __name__ == "__main__":
    unittest.main()

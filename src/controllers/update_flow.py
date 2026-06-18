"""
src/controllers/update_flow.py — Help menu + Check-for-Updates controller.

Owns every method that touches git from inside the app: the About /
Switch-version dialogs, the Check-for-Updates flow itself, the
``V<major>.<minor>`` auto-switch handshake, and the small repo/branch
discovery helpers.

Extracted from ``src/app.py:MainWindow`` in Chunk 5 of the
strengthening roadmap as a *pure structural move*. Behaviour is
identical; the methods are now reachable as
``self._update_flow.<name>`` on MainWindow and via the historical
``self._<name>`` shims that delegate to this controller.

The controller still talks to Qt (QMessageBox, QInputDialog, status
bar) via the MainWindow it's bound to. Making it Qt-free is a follow-up
audit in Chunk 6 (E1 — "domain logic does not import Qt"); once the
dialog calls are abstracted, an MCP server or scripting agent will be
able to drive the same flow without a QApplication.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import threading
import time

from PyQt6.QtCore import Qt, QTimer, QUrl
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import QInputDialog, QMessageBox, QProgressDialog

from src.app_version import build_version
from src.branding import APP_NAME
from src.version_branch import (
    is_newer_version,
    newest_remote_version_branch,
    parse_version_branch,
)


_REPO_RELEASES_URL = "https://github.com/yarrowyarrowyarrow/PermaDesign/releases"


def _human_size(num_bytes) -> str:
    """Human-readable byte count, e.g. ``"243.1 MB"``."""
    size = float(num_bytes or 0)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024.0 or unit == "GB":
            return f"{int(size)} {unit}" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024.0
    return f"{size:.1f} GB"


class UpdateFlowController:
    """Owns the Help → About / Switch version / Check for Updates flow.

    Holds a reference to MainWindow (``self._main``) so it can parent
    QMessageBox / QInputDialog and write to ``statusBar()``. Every other
    method call is intra-controller (``self.<method>``).
    """

    # Kept as a class attribute so MainWindow's shim ``_REPO_RELEASES_URL``
    # can re-export the same constant.
    REPO_RELEASES_URL = _REPO_RELEASES_URL

    def __init__(self, main_window):
        self._main = main_window

    # ── Help → About / Version / Switch (V1.37) ──────────────────────────────

    def _repo_path(self):
        """Absolute path to the project root (where .git lives for
        source installs). Returns None if the running binary isn't
        inside a git repo (e.g. PyInstaller .exe)."""
        here = os.path.dirname(os.path.abspath(__file__))
        # src/controllers/update_flow.py → repo root is two levels up
        candidate = os.path.dirname(os.path.dirname(here))
        if os.path.isdir(os.path.join(candidate, ".git")):
            return candidate
        return None

    def _current_branch_name(self):
        """Return the current git branch name, or None for frozen /
        non-git installs. Cached only across the call site that built
        the menu label."""
        repo = self._repo_path()
        if not repo:
            return None
        try:
            res = subprocess.run(
                ["git", "-C", repo, "rev-parse", "--abbrev-ref", "HEAD"],
                capture_output=True, text=True, timeout=3,
            )
            if res.returncode == 0:
                return res.stdout.strip() or None
        except Exception:
            pass
        return None

    def _on_about(self):
        """Show a small About dialog: current V<major>.<minor>, git
        commit, schema version, and a link to the releases page."""
        repo = self._repo_path()
        # Frozen builds have no git; fall back to the version baked in at
        # build time (version.txt). Source checkouts use the live branch.
        branch = build_version() or self._current_branch_name() or "?"
        commit = "?"
        if repo:
            try:
                res = subprocess.run(
                    ["git", "-C", repo, "rev-parse", "--short", "HEAD"],
                    capture_output=True, text=True, timeout=3,
                )
                if res.returncode == 0:
                    commit = res.stdout.strip() or "?"
            except Exception:
                pass
        try:
            from src.db.plants import _SCHEMA_VERSION as schema_v
        except Exception:
            schema_v = "?"
        is_release = parse_version_branch(branch) is not None
        kind_note = "" if is_release else (
            "\n\nYou're on a development branch — the V*.* branch "
            "convention isn't being followed. Use Help → Switch to a "
            "specific version to move to a release branch."
        )
        QMessageBox.information(
            self._main, f"About {APP_NAME}",
            f"<b>{APP_NAME}</b><br>"
            f"Branch: <b>{branch}</b><br>"
            f"Commit: {commit}<br>"
            f"Schema version: v{schema_v}<br><br>"
            f"Native-plant landscape designer for Alberta and the "
            f"Canadian prairies."
            + kind_note
        )

    def _on_pick_version(self):
        """Let the user pick any published V<major>.<minor> branch and
        switch the checkout to it. Useful for rolling back to an older
        release or jumping ahead. Frozen installs download the chosen
        version's installer from GitHub Releases instead."""
        # Frozen / non-git install — there's no checkout to switch, so offer
        # the published installers (download + install) instead.
        if getattr(sys, "frozen", False):
            self._frozen_pick_version()
            return
        repo = self._repo_path()
        if not repo:
            QMessageBox.information(
                self._main, "Switch version",
                "This install isn't a git checkout — there's nothing to "
                "switch. Visit the releases page to download a specific "
                "installer."
            )
            self._open_releases_page()
            return

        def _git(*args, timeout=10):
            return subprocess.run(
                ["git", "-C", repo, *args],
                capture_output=True, text=True, timeout=timeout, check=False,
            )

        # Fetch so we see any branches published since launch.
        self._main.statusBar().showMessage("Fetching version list…", 2000)
        fetch = _git("fetch", "--prune", "--quiet")
        if fetch.returncode != 0:
            QMessageBox.warning(
                self._main, "Switch version",
                "Couldn't reach the git remote (check your network).\n\n"
                f"{fetch.stderr.strip()}"
            )
            return

        # Collect every V<major>.<minor> branch — remote + local — sorted
        # newest first.
        names: set[str] = set()
        for ref_glob in ("refs/remotes/origin/", "refs/heads/"):
            res = _git("for-each-ref", "--format=%(refname:short)", ref_glob)
            if res.returncode != 0:
                continue
            for line in res.stdout.splitlines():
                short = line.strip()
                name = short[len("origin/"):] if short.startswith("origin/") else short
                if parse_version_branch(name):
                    names.add(name)
        if not names:
            QMessageBox.information(
                self._main, "Switch version",
                "No V<major>.<minor> branches found on this remote."
            )
            return
        ordered = sorted(
            names,
            key=lambda n: parse_version_branch(n),
            reverse=True,
        )
        current = self._current_branch_name() or "?"

        # Build the list dialog. Pre-select the current branch if
        # present in the list.
        labels = [
            f"{n}  (current)" if n == current else n
            for n in ordered
        ]
        try:
            preselect = ordered.index(current)
        except ValueError:
            preselect = 0
        choice, ok = QInputDialog.getItem(
            self._main, "Switch to a specific version",
            "Pick a release branch. The app will check out the chosen "
            "branch and pull any new commits. You'll need to restart "
            "the app to load the new code.",
            labels, current=preselect, editable=False,
        )
        if not ok or not choice:
            return
        target = ordered[labels.index(choice)]
        if target == current:
            QMessageBox.information(
                self._main, "Switch version",
                f"You're already on {target}."
            )
            return

        # Reuse the existing dirty-tree handling + offer-branch-switch
        # path so behaviour matches Check for Updates exactly.
        status = _git("status", "--porcelain")
        stash_label = None
        if status.returncode == 0 and status.stdout.strip():
            choice2 = QMessageBox.question(
                self._main, "Uncommitted changes",
                "Your working tree has uncommitted changes. Stash them "
                f"before switching to {target}? They'll be restored on "
                f"the new branch via `git stash pop`.",
                QMessageBox.StandardButton.Yes
                | QMessageBox.StandardButton.No
                | QMessageBox.StandardButton.Cancel,
            )
            if choice2 == QMessageBox.StandardButton.Cancel:
                return
            if choice2 == QMessageBox.StandardButton.Yes:
                stash_label = f"PermaDesign auto-stash before switch to {target}"
                stash = _git("stash", "push", "-u", "-m", stash_label)
                if stash.returncode != 0:
                    QMessageBox.warning(
                        self._main, "Stash failed",
                        f"Couldn't stash local changes:\n\n{stash.stderr.strip()}"
                    )
                    return

        self._offer_branch_switch(
            _git,
            target=target,
            current=current,
            stash_to_restore=stash_label,
        )

    # ── Help → Check for Updates ──────────────────────────────────────────────
    #
    # Behaves differently depending on how the user is running the app:
    #
    #   * Source install (git checkout, `python main.py`) — runs
    #     `git fetch` + `git status` to detect upstream commits, then
    #     offers a fast-forward `git pull`. If the working tree is dirty,
    #     gives the user three options: stash & update (safe, recoverable
    #     via `git stash pop`), discard & update (destructive, with a
    #     second confirm), or cancel. Refuses to auto-merge on divergence.
    #
    #   * Frozen install (PyInstaller .exe used by friends) — git isn't
    #     available, so we open the GitHub releases page in the default
    #     browser and let the user download the next installer.

    def _on_check_for_updates(self):
        # Frozen build: no git — check GitHub Releases and offer to
        # download + install the newest published installer in-app.
        if getattr(sys, "frozen", False):
            self._frozen_check_for_updates()
            return

        # Detect git root by walking up from this file
        repo_root = self._repo_path()
        if not repo_root:
            QMessageBox.information(
                self._main, "Check for Updates",
                "Not a git checkout — opening the releases page in your browser "
                "so you can download the latest installer manually."
            )
            self._open_releases_page()
            return

        def _git(*args, timeout=30):
            return subprocess.run(
                ["git", "-C", repo_root, *args],
                capture_output=True, text=True, timeout=timeout, check=False,
            )

        status = _git("status", "--porcelain")
        if status.returncode != 0:
            QMessageBox.warning(
                self._main, "Check for Updates",
                "Couldn't run git. Make sure git is installed and on your PATH.\n\n"
                f"{status.stderr.strip() or status.stdout.strip()}"
            )
            return

        if status.stdout.strip():
            # Dirty working tree — give the user three explicit choices
            # instead of just refusing.
            dirty_files = [
                line[3:] for line in status.stdout.strip().splitlines()[:6]
            ]
            preview = "\n".join(f"  · {f}" for f in dirty_files)
            if len(status.stdout.strip().splitlines()) > 6:
                preview += f"\n  · …and more"

            box = QMessageBox(self._main)
            box.setIcon(QMessageBox.Icon.Warning)
            box.setWindowTitle("Local changes detected")
            box.setText(
                "You have uncommitted local changes — pulling now could "
                "clobber them. How would you like to proceed?"
            )
            box.setInformativeText(
                f"Changed files:\n{preview}\n\n"
                "• Stash & update — safest. Sets your changes aside in a "
                "git stash, pulls, then restores them. If the restore "
                "conflicts, the stash stays put so you can recover manually.\n\n"
                "• Discard & update — destructive. Throws away all "
                "uncommitted changes, then pulls. Requires a second confirm."
            )
            btn_stash   = box.addButton("Stash && update",
                                        QMessageBox.ButtonRole.AcceptRole)
            btn_discard = box.addButton("Discard && update",
                                        QMessageBox.ButtonRole.DestructiveRole)
            btn_cancel  = box.addButton(QMessageBox.StandardButton.Cancel)
            box.setDefaultButton(btn_stash)
            box.exec()

            choice = box.clickedButton()
            if choice is btn_cancel or choice is None:
                return
            if choice is btn_discard:
                confirm = QMessageBox.question(
                    self._main, "Discard all local changes?",
                    "This will permanently delete every uncommitted change "
                    "in your working tree (tracked-file edits will be "
                    "reset to the last commit). Untracked files are left "
                    "alone. Continue?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No,
                )
                if confirm != QMessageBox.StandardButton.Yes:
                    return
                reset = _git("reset", "--hard", "HEAD")
                if reset.returncode != 0:
                    QMessageBox.warning(
                        self._main, "Discard failed",
                        "git reset --hard HEAD failed:\n\n"
                        + (reset.stderr.strip() or reset.stdout.strip())
                    )
                    return
                self._run_update_flow(_git, stash_to_restore=None)
                return

            # Stash & update
            stash_label = f"permadesign-auto-{int(time.time())}"
            stash = _git("stash", "push", "--include-untracked",
                         "-m", stash_label)
            if stash.returncode != 0:
                QMessageBox.warning(
                    self._main, "Stash failed",
                    "git stash failed:\n\n"
                    + (stash.stderr.strip() or stash.stdout.strip())
                )
                return
            self._run_update_flow(_git, stash_to_restore=stash_label)
            return

        # Clean working tree — proceed straight to the update flow.
        self._run_update_flow(_git, stash_to_restore=None)

    def _run_update_flow(self, git_runner, *, stash_to_restore):
        """Shared update flow: fetch → ahead/behind check → pull → optional
        stash-pop → restart prompt. `git_runner` is the closure `_git` from
        the caller (already bound to the repo path). `stash_to_restore` is
        a stash message label (or None) — when set, we `git stash pop`
        after a successful pull and warn if the pop conflicts.

        Schema v1.32: after the fetch, also check whether origin carries a
        newer ``V<major>.<minor>`` branch than the one we're on. If so,
        prompt the user to switch to that branch instead of (or in addition
        to) updating the current one. Branch naming convention is the same
        one documented in CLAUDE.md."""
        self._main.statusBar().showMessage("Checking for updates…", 2000)
        # --prune drops references to branches the remote has deleted, so
        # _newest_remote_version_branch doesn't surface stale entries.
        fetch = git_runner("fetch", "--prune", "--quiet")
        if fetch.returncode != 0:
            self._maybe_restore_stash(git_runner, stash_to_restore)
            QMessageBox.warning(
                self._main, "Check for Updates",
                "Couldn't reach the git remote (check your network).\n\n"
                f"{fetch.stderr.strip()}"
            )
            return

        current_branch = (
            git_runner("rev-parse", "--abbrev-ref", "HEAD").stdout.strip() or "?"
        )

        # ── V<major>.<minor> auto-switch (V1.32) ──────────────────────────
        # If a newer release branch exists on origin than the one we're on,
        # offer the switch. Falls through to the standard fast-forward flow
        # when we're already on the highest V-branch or no V-branches exist.
        newest = self._newest_remote_version_branch(git_runner)
        if newest and self._is_newer_version(newest, current_branch):
            self._offer_branch_switch(
                git_runner,
                target=newest,
                current=current_branch,
                stash_to_restore=stash_to_restore,
            )
            return

        behind = git_runner("rev-list", "--count", "HEAD..@{u}")
        ahead  = git_runner("rev-list", "--count", "@{u}..HEAD")
        if behind.returncode != 0 or ahead.returncode != 0:
            self._maybe_restore_stash(git_runner, stash_to_restore)
            QMessageBox.information(
                self._main, "Check for Updates",
                "This branch has no configured upstream. Set one with "
                "`git branch --set-upstream-to=origin/<branch>` and try again."
            )
            return

        n_behind = int((behind.stdout or "0").strip() or 0)
        n_ahead  = int((ahead.stdout  or "0").strip() or 0)
        branch   = current_branch

        if n_behind == 0 and n_ahead == 0:
            self._maybe_restore_stash(git_runner, stash_to_restore)
            QMessageBox.information(
                self._main, "Check for Updates",
                f"You're up to date on branch '{branch}'."
            )
            return
        if n_behind == 0 and n_ahead > 0:
            self._maybe_restore_stash(git_runner, stash_to_restore)
            QMessageBox.information(
                self._main, "Check for Updates",
                f"You're {n_ahead} commit(s) ahead of the remote on '{branch}'. "
                "Nothing to pull."
            )
            return
        if n_ahead > 0 and n_behind > 0:
            self._maybe_restore_stash(git_runner, stash_to_restore)
            QMessageBox.warning(
                self._main, "Check for Updates",
                f"Branch '{branch}' has diverged from the remote "
                f"({n_ahead} ahead, {n_behind} behind). Resolve manually in a "
                "terminal — the app won't auto-merge."
            )
            return

        # Behind only — show recent incoming commits and offer the pull.
        log = git_runner("log", "--oneline", f"-{min(n_behind, 8)}", "HEAD..@{u}")
        recent = log.stdout.strip() or "(commit log unavailable)"
        prompt = QMessageBox.question(
            self._main, "Update available",
            f"Branch '{branch}' is {n_behind} commit(s) behind the remote.\n\n"
            f"Recent incoming changes:\n{recent}\n\n"
            "Pull and fast-forward now? You'll need to restart the app for "
            "code changes to take effect.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if prompt != QMessageBox.StandardButton.Yes:
            self._maybe_restore_stash(git_runner, stash_to_restore)
            return

        pull = git_runner("pull", "--ff-only")
        if pull.returncode != 0:
            self._maybe_restore_stash(git_runner, stash_to_restore)
            QMessageBox.warning(
                self._main, "Pull failed",
                "git pull --ff-only failed:\n\n"
                + (pull.stderr.strip() or pull.stdout.strip())
            )
            return

        # Pull succeeded. If we stashed, try to restore.
        stash_note = ""
        if stash_to_restore:
            pop = git_runner("stash", "pop")
            if pop.returncode == 0:
                stash_note = ("\n\nYour stashed local changes were restored "
                              "cleanly.")
            else:
                stash_note = (
                    "\n\nYour stash could NOT be auto-restored (likely a "
                    "merge conflict with the incoming changes). It's still "
                    f"saved as `{stash_to_restore}` — recover it with:\n"
                    "    git stash list\n"
                    "    git stash apply stash@{0}"
                )
        QMessageBox.information(
            self._main, "Updated",
            f"Pulled {n_behind} commit(s) from origin/{branch}.\n\n"
            "Close and relaunch the app to load the new code."
            + stash_note
        )

    def _maybe_restore_stash(self, git_runner, stash_label):
        """Best-effort stash pop on the abort/error paths so a user who hit
        Cancel mid-flow gets their working tree back. Silent on failure —
        the stash entry remains and we don't pile on additional dialogs."""
        if not stash_label:
            return
        git_runner("stash", "pop")

    # ── V<major>.<minor> branch auto-switch (V1.32) ───────────────────────────
    #
    # Convention (also documented in CLAUDE.md): release branches are named
    # ``V<major>.<minor>`` (e.g. V1.31, V1.32). Each branch contains a single
    # release's worth of work; "the latest version" is the numerically
    # highest such branch on origin. The updater treats these as the
    # authoritative release line.
    #
    # The parsing/comparison/listing helpers live in
    # ``src/version_branch.py`` (Qt-free, unit-testable). This controller's
    # responsibility here is only the user-facing switch dialog.

    def _newest_remote_version_branch(self, git_runner):
        return newest_remote_version_branch(git_runner)

    def _is_newer_version(self, target, current):
        return is_newer_version(target, current)

    def _offer_branch_switch(self, git_runner, *, target, current, stash_to_restore):
        """Prompt the user to switch from ``current`` to ``target`` (a remote
        V-branch). Reuses the stash carried in from
        ``_on_check_for_updates`` so a dirty-tree pre-stash still survives
        the switch."""
        # Show the recent commit log of the target branch as a preview.
        log = git_runner(
            "log", "--oneline", "-8",
            f"origin/{target}",
            "--not", "HEAD",
        )
        recent = (log.stdout or "").strip() or "(commit log unavailable)"

        prompt = QMessageBox.question(
            self._main, "New version available",
            f"A newer version of {APP_NAME} is on the server.\n\n"
            f"You're on:   {current}\n"
            f"Latest:      {target}\n\n"
            f"Recent changes in {target}:\n{recent}\n\n"
            f"Switch to {target} now? You'll need to restart the app "
            "afterward to load the new code.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if prompt != QMessageBox.StandardButton.Yes:
            self._maybe_restore_stash(git_runner, stash_to_restore)
            return

        # If a local branch with this name already exists, plain ``checkout``
        # it; otherwise create it tracking origin/<target>.
        rev_check = git_runner("rev-parse", "--verify", "--quiet", target)
        if rev_check.returncode == 0:
            checkout = git_runner("checkout", target)
        else:
            checkout = git_runner("checkout", "-b", target, f"origin/{target}")

        if checkout.returncode != 0:
            self._maybe_restore_stash(git_runner, stash_to_restore)
            QMessageBox.warning(
                self._main, "Switch failed",
                f"Couldn't switch to {target}.\n\n"
                + (checkout.stderr.strip() or checkout.stdout.strip())
            )
            return

        # Fast-forward in case the local branch already existed and was
        # behind origin/<target>. Non-fatal if it fails — we've already
        # switched, the user can re-run "Check for Updates" on the new
        # branch.
        pull = git_runner("pull", "--ff-only")
        pull_warning = ""
        if pull.returncode != 0:
            pull_warning = (
                "\n\nNote: couldn't fast-forward after the switch:\n"
                + (pull.stderr.strip() or pull.stdout.strip())
            )

        # Restore any stash we set aside on the source branch.
        stash_note = ""
        if stash_to_restore:
            pop = git_runner("stash", "pop")
            if pop.returncode == 0:
                stash_note = (
                    "\n\nYour stashed local changes were restored on "
                    f"{target}."
                )
            else:
                stash_note = (
                    "\n\nYour stashed local changes did NOT auto-restore "
                    "(likely conflicts on the new branch). It's still "
                    f"saved as `{stash_to_restore}` — recover it with:\n"
                    "    git stash list\n"
                    "    git stash apply stash@{0}"
                )

        QMessageBox.information(
            self._main, f"Switched to {target}",
            f"You're now on {target}.{pull_warning}{stash_note}\n\n"
            "Close and relaunch the app to load the new version."
        )

    # ── Frozen-build updater (GitHub Releases) ────────────────────────────────
    #
    # A packaged .dmg/.exe isn't a git checkout, so "update" means: ask the
    # GitHub Releases API which versions ship an installer, compare against the
    # version baked into this build (version.txt), and download + open the
    # matching installer. The release tag is the V<major>.<minor> branch name,
    # so the user sees the same version labels as a source install.
    #
    # The release artifacts are produced and published automatically by
    # .github/workflows/release-macos.yml on every push to a V* branch.

    def _frozen_fetch_releases(self):
        """Fetch the published releases (newest first), or show an error
        dialog and return ``None``. Synchronous — the releases JSON is tiny;
        only the installer download (below) is threaded."""
        from src import github_releases as ghr

        self._main.statusBar().showMessage("Checking GitHub for updates…", 2000)
        try:
            releases = ghr.list_releases()
        except Exception as exc:
            QMessageBox.warning(
                self._main, "Check for Updates",
                "Couldn't reach GitHub to check for updates — check your "
                "internet connection and try again.\n\n"
                f"{type(exc).__name__}: {exc}"
            )
            return None
        if not releases:
            QMessageBox.information(
                self._main, "Check for Updates",
                "No published versions were found on GitHub yet."
            )
            return None
        return releases

    def _frozen_check_for_updates(self):
        from src import github_releases as ghr

        releases = self._frozen_fetch_releases()
        if releases is None:
            return
        latest = releases[0]
        current = build_version()
        current_ver = ghr.parse_release_version(current) if current else None

        if current_ver is not None and latest.version <= current_ver:
            QMessageBox.information(
                self._main, "Check for Updates",
                f"You're up to date.\n\n"
                f"Installed: {current}\nLatest available: {latest.tag}"
            )
            return
        self._offer_frozen_download(latest, current)

    def _frozen_pick_version(self):
        releases = self._frozen_fetch_releases()
        if releases is None:
            return
        current = build_version()
        labels = [
            f"{r.tag}  (current)" if current and r.tag == current else r.tag
            for r in releases
        ]
        preselect = 0
        if current:
            for i, r in enumerate(releases):
                if r.tag == current:
                    preselect = i
                    break
        choice, ok = QInputDialog.getItem(
            self._main, "Switch to a specific version",
            "Pick a published version to download and install. The current "
            "version stays until you install the one you pick.",
            labels, current=preselect, editable=False,
        )
        if not ok or not choice:
            return
        chosen = releases[labels.index(choice)]
        if current and chosen.tag == current:
            QMessageBox.information(
                self._main, "Switch version",
                f"You're already on {chosen.tag}."
            )
            return
        self._offer_frozen_download(chosen, current)

    def _offer_frozen_download(self, release, current):
        """Confirm, then download + open the installer asset for this
        platform. Falls back to the release page if no matching asset is
        attached."""
        from src import github_releases as ghr

        asset = release.asset_for_extensions(ghr.platform_asset_extensions())
        if asset is None:
            QMessageBox.information(
                self._main, "Update available",
                f"Version {release.tag} is published, but it has no installer "
                f"for your system attached yet. Opening the download page so "
                f"you can grab it manually."
            )
            QDesktopServices.openUrl(QUrl(release.html_url or _REPO_RELEASES_URL))
            return

        notes = (release.body or "").strip()
        if len(notes) > 700:
            notes = notes[:700].rstrip() + "\n…"
        notes_block = f"\n\nWhat's new:\n{notes}" if notes else ""
        prompt = QMessageBox.question(
            self._main, "Update available",
            f"A newer version of {APP_NAME} is available.\n\n"
            f"Installed: {current or 'your current version'}\n"
            f"Latest:      {release.tag}   (~{_human_size(asset.size)})"
            f"{notes_block}\n\n"
            "Download and install it now?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if prompt != QMessageBox.StandardButton.Yes:
            return
        self._download_and_open(asset, release.tag)

    def _download_and_open(self, asset, tag):
        """Threaded download with a Qt progress dialog, then open the
        installer. Keeps the UI responsive during the ~200-300 MB download."""
        from src import github_releases as ghr

        downloads = os.path.join(os.path.expanduser("~"), "Downloads")
        if not os.path.isdir(downloads):
            downloads = tempfile.gettempdir()
        dest = os.path.join(downloads, asset.name or f"SiteAndPattern-{tag}")

        progress = QProgressDialog(
            f"Downloading {tag}…", "Cancel", 0, 100, self._main
        )
        progress.setWindowTitle("Downloading update")
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(0)
        progress.setAutoClose(False)
        progress.setAutoReset(False)
        progress.setValue(0)

        # The worker thread only mutates `state`; the GUI-thread QTimer reads
        # it. `progress.wasCanceled()` is the GUI→worker cancel signal.
        state = {"done": 0, "total": int(asset.size or 0),
                 "finished": False, "error": None, "cancelled": False}

        def _on_progress(done, total):
            state["done"], state["total"] = done, total
            return not state["cancelled"]

        def _worker():
            try:
                ghr.download_asset(asset, dest, progress=_on_progress)
            except ghr.DownloadCancelled:
                state["cancelled"] = True
            except Exception as exc:  # noqa: BLE001 — surfaced in the dialog
                state["error"] = f"{type(exc).__name__}: {exc}"
            finally:
                state["finished"] = True

        worker = threading.Thread(target=_worker, daemon=True)
        worker.start()

        timer = QTimer(self._main)

        def _tick():
            if progress.wasCanceled():
                state["cancelled"] = True
            total, done = state["total"], state["done"]
            if total > 0:
                progress.setValue(min(100, int(done * 100 / total)))
                progress.setLabelText(
                    f"Downloading {tag}…\n"
                    f"{_human_size(done)} of {_human_size(total)}"
                )
            if state["finished"]:
                timer.stop()
                progress.close()
                self._after_download(state, dest, tag)

        timer.timeout.connect(_tick)
        timer.start(120)

    def _after_download(self, state, dest, tag):
        if state.get("cancelled"):
            return
        if state.get("error"):
            QMessageBox.warning(
                self._main, "Download failed",
                "Couldn't download the update:\n\n"
                f"{state['error']}\n\n"
                "You can try again, or download it manually from the "
                "releases page."
            )
            return
        self._open_installer(dest, tag)

    def _open_installer(self, path, tag):
        """Open the downloaded installer with the OS handler and tell the
        user how to finish."""
        try:
            if sys.platform == "darwin":
                subprocess.Popen(["open", path])
                message = (
                    "The new version has been downloaded and its installer "
                    "window opened.\n\n"
                    "To finish:\n"
                    "  1. Drag Site & Pattern onto the Applications folder and "
                    "choose Replace.\n"
                    "  2. Quit this older copy, then open Site & Pattern again.\n\n"
                    "Because the app downloaded the update itself, macOS won't "
                    "show the usual “unverified developer” warning."
                )
            elif sys.platform.startswith("win"):
                os.startfile(path)  # type: ignore[attr-defined]
                message = (
                    "The installer has been downloaded and opened.\n\n"
                    "Click through it to update in place (your designs and "
                    "database are kept), then reopen Site & Pattern. You can "
                    "close this older copy now."
                )
            else:
                subprocess.Popen(["xdg-open", os.path.dirname(path) or "."])
                message = f"The update was downloaded to:\n{path}"
        except Exception as exc:  # noqa: BLE001
            message = (
                f"The update was downloaded to:\n{path}\n\n"
                f"(Couldn't open it automatically: {exc})"
            )
        QMessageBox.information(self._main, f"Update {tag} downloaded", message)

    def _open_releases_page(self):
        QDesktopServices.openUrl(QUrl(_REPO_RELEASES_URL))

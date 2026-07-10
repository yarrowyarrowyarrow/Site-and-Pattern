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
    fast_forward_upstream,
    is_newer_version,
    list_remote_version_branches,
    newest_remote_version_branch,
    normalize_branch_ref,
    parse_version_branch,
    update_to_branch,
    working_tree_dirty,
)

# git emits UTF-8 (commit subjects, branch names) regardless of the OS locale;
# decoding subprocess output with the locale default mojibakes commit messages
# on Windows (cp1252 renders "→" as "â†'" — seen live in the V2.25 update
# dialog). Every git call below decodes explicitly.
_GIT_TEXT = {"encoding": "utf-8", "errors": "replace"}


_REPO_RELEASES_URL = "https://github.com/yarrowyarrowyarrow/Site-and-Pattern/releases"


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
        the menu label. Normalized: once the release tag V2.NN exists,
        ``rev-parse --abbrev-ref`` disambiguates to ``heads/V2.NN`` — the
        plain branch name is what every caller wants."""
        repo = self._repo_path()
        if not repo:
            return None
        try:
            res = subprocess.run(
                ["git", "-C", repo, "rev-parse", "--abbrev-ref", "HEAD"],
                capture_output=True, timeout=3, **_GIT_TEXT,
            )
            if res.returncode == 0:
                return normalize_branch_ref(res.stdout.strip()) or None
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
                    capture_output=True, timeout=3, **_GIT_TEXT,
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
        """Version picker. Frozen installs download a published installer
        from GitHub Releases; source checkouts pick a published V-branch and
        the app switches to it in place (one-click, restored in V2.25 —
        same safe path as Check for Updates: stash-aware, no reset-hard)."""
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

        def _git(*args, timeout=30):
            return subprocess.run(
                ["git", "-C", repo, *args],
                capture_output=True, timeout=timeout, check=False, **_GIT_TEXT,
            )

        self._main.statusBar().showMessage("Fetching version list…", 2000)
        fetch = _git("fetch", "--prune", "--quiet")
        if fetch.returncode != 0:
            QMessageBox.warning(
                self._main, "Switch version",
                "Couldn't reach the git remote (check your network), or git "
                "isn't on your PATH.\n\n"
                f"{fetch.stderr.strip() or fetch.stdout.strip()}"
            )
            return
        branches = list_remote_version_branches(_git)
        if not branches:
            QMessageBox.information(
                self._main, "Switch version",
                "No published V<major>.<minor> versions found on the remote."
            )
            return
        current = self._current_branch_name() or "?"
        labels = [f"{b}  (current)" if b == current else b for b in branches]
        preselect = branches.index(current) if current in branches else 0
        choice, ok = QInputDialog.getItem(
            self._main, "Switch to a specific version",
            "Pick a published version. The app switches its checkout to it "
            "(local source edits are set aside safely first) and offers a "
            "restart.",
            labels, current=preselect, editable=False,
        )
        if not ok or not choice:
            return
        target = branches[labels.index(choice)]
        if target == current:
            QMessageBox.information(
                self._main, "Switch version",
                f"You're already on {target}.")
            return
        self._perform_source_update(_git, target)

    # ── Help → Check for Updates ──────────────────────────────────────────────
    #
    # Behaves differently depending on how the user is running the app:
    #
    #   * Frozen install (.dmg/.exe) — checks GitHub Releases and offers to
    #     download + install the newest published installer, all in-app
    #     (below, unchanged).
    #
    #   * Source install (git checkout, `python main.py`) — one-click
    #     update, restored in V2.25 by user request (most users won't open
    #     a terminal; V2.22 had made this path read-only). Only the SAFE
    #     subset returned: a stash-aware `git checkout -B <V> origin/<V>`
    #     for a newer release branch, or a pure `merge --ff-only` when
    #     merely behind upstream — then a restart prompt. The old
    #     "Discard & update" (destructive reset) path stays dead: local
    #     changes are set aside recoverably, never destroyed, and a
    #     diverged branch is reported, not auto-merged.
    #     (tests/test_architecture_guard.py pins this file free of the
    #     destructive git flags.)

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
                capture_output=True, timeout=timeout, check=False, **_GIT_TEXT,
            )

        self._main.statusBar().showMessage("Checking for updates…", 2000)
        # --prune drops references to branches the remote has deleted, so
        # _newest_remote_version_branch doesn't surface stale entries.
        fetch = _git("fetch", "--prune", "--quiet")
        if fetch.returncode != 0:
            QMessageBox.warning(
                self._main, "Check for Updates",
                "Couldn't reach the git remote (check your network), or git "
                "isn't on your PATH.\n\n"
                f"{fetch.stderr.strip() or fetch.stdout.strip()}"
            )
            return

        current = self._current_branch_name() or "?"

        # A newer V<major>.<minor> release branch on origin wins the offer.
        newest = self._newest_remote_version_branch(_git)
        if newest and self._is_newer_version(newest, current):
            log = _git("log", "--oneline", "-8", f"origin/{newest}",
                       "--not", "HEAD")
            recent = (log.stdout or "").strip() or "(commit log unavailable)"
            command = f"git checkout -B {newest} origin/{newest}"
            box = QMessageBox(
                QMessageBox.Icon.Information, "New version available",
                f"A newer version of {APP_NAME} is on the server.\n\n"
                f"You're on:   {current}\n"
                f"Latest:      {newest}\n\n"
                f"Recent changes in {newest}:\n{recent}\n\n"
                "Update now switches to it in place and offers a restart. "
                "(Any local source edits are set aside safely first — or do "
                f"it from a terminal: {command})",
                QMessageBox.StandardButton.NoButton, self._main,
            )
            update_btn = box.addButton(
                f"Update to {newest}", QMessageBox.ButtonRole.AcceptRole)
            copy_btn = box.addButton(
                "Copy command", QMessageBox.ButtonRole.ActionRole)
            box.addButton("Not now", QMessageBox.ButtonRole.RejectRole)
            box.setDefaultButton(update_btn)
            box.exec()
            clicked = box.clickedButton()
            if clicked is copy_btn:
                from PyQt6.QtWidgets import QApplication
                QApplication.clipboard().setText(command)
                self._main.statusBar().showMessage(
                    f"Copied to clipboard: {command}", 5000)
            elif clicked is update_btn:
                self._perform_source_update(_git, newest)
            return

        # Same branch as the newest release — check upstream drift.
        behind = _git("rev-list", "--count", "HEAD..@{u}")
        ahead = _git("rev-list", "--count", "@{u}..HEAD")
        if behind.returncode != 0 or ahead.returncode != 0:
            QMessageBox.information(
                self._main, "Check for Updates",
                f"You're on '{current}', which has no configured upstream — "
                "nothing to compare against. (Set one with `git branch "
                "--set-upstream-to=origin/<branch>` if you want drift "
                "reports here.)"
            )
            return
        n_behind = int((behind.stdout or "0").strip() or 0)
        n_ahead = int((ahead.stdout or "0").strip() or 0)
        if n_behind == 0:
            note = ("" if n_ahead == 0 else
                    f" (and {n_ahead} local commit(s) ahead of it)")
            QMessageBox.information(
                self._main, "Check for Updates",
                f"You're up to date on branch '{current}'{note}.")
            return
        if n_ahead:
            # Diverged — never auto-merge; report only.
            QMessageBox.information(
                self._main, "Update available",
                f"Branch '{current}' is {n_behind} commit(s) behind its "
                f"upstream and {n_ahead} ahead (diverged). The app won't "
                "auto-merge — resolve from a terminal:\n\n"
                "    git rebase @{u}    (or merge — your call)\n\n"
                "then relaunch the app."
            )
            return
        prompt = QMessageBox.question(
            self._main, "Update available",
            f"Branch '{current}' is {n_behind} commit(s) behind its "
            "upstream.\n\nUpdate now (fast-forward) and restart?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if prompt != QMessageBox.StandardButton.Yes:
            return
        ok, detail = fast_forward_upstream(_git)
        if not ok:
            QMessageBox.warning(
                self._main, "Update failed",
                detail + "\n\nYou can finish from a terminal instead:\n\n"
                "    git pull --ff-only")
            return
        self._offer_restart(f"the latest {current}")

    # ── One-click source update (V2.25) ───────────────────────────────────────

    def _perform_source_update(self, git_runner, target: str):
        """Switch the checkout to origin/<target> in-app. Local tracked
        changes are stashed (with consent) and restored after — the V2.22
        lesson kept: nothing here can destroy work, and there is no
        reset-hard path."""
        dirty = working_tree_dirty(git_runner)
        if dirty is None:
            QMessageBox.warning(
                self._main, "Update failed",
                "Couldn't inspect the working tree — is git on your PATH?")
            return
        stash_label = None
        if dirty:
            choice = QMessageBox.question(
                self._main, "Local changes detected",
                "Some of the app's source files have local modifications. "
                "Set them aside safely (git stash) and restore them after "
                f"the update to {target}?",
                QMessageBox.StandardButton.Yes
                | QMessageBox.StandardButton.Cancel,
            )
            if choice != QMessageBox.StandardButton.Yes:
                return
            stash_label = f"site-and-pattern auto-update {int(time.time())}"
        self._main.statusBar().showMessage(f"Updating to {target}…", 3000)
        ok, note = update_to_branch(git_runner, target,
                                    stash_label=stash_label)
        if not ok:
            QMessageBox.warning(
                self._main, "Update failed",
                note + "\n\nYou can finish from a terminal instead:\n\n"
                f"    git checkout -B {target} origin/{target}")
            return
        self._offer_restart(target, note)

    def _offer_restart(self, version: str, note: str = ""):
        """Post-update restart prompt. The new code only loads on relaunch
        (and a schema/seed bump only reseeds the DB on next start)."""
        extra = f"\n\n{note}" if note else ""
        prompt = QMessageBox.question(
            self._main, "Update complete",
            f"{APP_NAME} is now on {version}.{extra}\n\n"
            "Restart now to load it? (You'll be asked to save any unsaved "
            "changes first.)",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if prompt == QMessageBox.StandardButton.Yes:
            self._restart_app()
        else:
            self._main.statusBar().showMessage(
                f"Updated to {version} — it loads next time you start "
                "the app.", 8000)

    def _restart_app(self):
        """Close the window (which runs the normal unsaved-changes prompt),
        then spawn a fresh process on the updated code. Spawn only after the
        close actually happened — a cancelled save prompt must not leave two
        copies running."""
        argv = [sys.executable] + sys.argv
        if self._main.close():
            subprocess.Popen(argv)
        else:
            self._main.statusBar().showMessage(
                "Restart cancelled — the update loads next time you start "
                "the app.", 8000)

    # ── V<major>.<minor> release-line helpers ─────────────────────────────────
    # The parsing/comparison/listing logic lives in ``src/version_branch.py``
    # (Qt-free, unit-testable); these delegates exist so MainWindow shims and
    # tests can reach them through the controller.

    def _newest_remote_version_branch(self, git_runner):
        return newest_remote_version_branch(git_runner)

    def _is_newer_version(self, target, current):
        return is_newer_version(target, current)

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

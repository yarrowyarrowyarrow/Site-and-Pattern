"""
version_branch.py — Helpers for the V<major>.<minor> release-branch
convention used by the "Check for Updates" auto-switch flow.

Lives at the module level (not on MainWindow) so it can be unit-tested
without PyQt6 in the environment. The Qt-aware switch UI in
``src.app.MainWindow`` thinly wraps these helpers.

Convention (also documented in CLAUDE.md): release branches are named
``V<major>.<minor>`` (e.g. V1.31, V1.32). The numerically highest such
branch on ``origin`` is the canonical "latest version" — that's the
branch the updater offers to switch to.
"""

from __future__ import annotations

import re
from typing import Callable, Optional, Tuple


_VERSION_BRANCH_RE = re.compile(r"^V(\d+)\.(\d+)$")


def normalize_branch_ref(name: Optional[str]) -> Optional[str]:
    """Strip the ref-namespace prefix git prepends when a branch name is
    ambiguous with another ref: ``git rev-parse --abbrev-ref HEAD`` answers
    ``heads/V2.22`` instead of ``V2.22`` once the release *tag* V2.22 exists —
    and the release workflow publishes a tag for every V-branch, so on a real
    install this is the norm, not the exception. Without normalization the
    ugly name leaks into the updater dialogs and ``parse_version_branch``
    rejects it (the Help menu then mislabels the build as "dev")."""
    if not name:
        return name
    s = name.strip()
    for prefix in ("refs/heads/", "heads/"):
        if s.startswith(prefix):
            return s[len(prefix):]
    return s


def parse_version_branch(name: str) -> Optional[Tuple[int, int]]:
    """Return ``(major, minor)`` if ``name`` matches the convention, else
    ``None``. Comparison is strict — lowercase ``v``, suffixes, and
    feature-style prefixes are all rejected."""
    if not name:
        return None
    m = _VERSION_BRANCH_RE.match(name.strip())
    return (int(m.group(1)), int(m.group(2))) if m else None


def is_newer_version(target: str, current: str) -> bool:
    """``True`` when ``target`` is a V-branch *and* either:

      * ``current`` is not a V-branch (so any release is "newer"), or
      * ``current`` parses to a strictly lower ``(major, minor)``.

    Equal versions return ``False`` so the caller falls through to the
    standard fast-forward path."""
    t = parse_version_branch(target)
    if t is None:
        return False
    c = parse_version_branch(current)
    if c is None:
        return True
    return t > c


def list_remote_version_branches(
    git_runner: Callable[..., object],
) -> list[str]:
    """Every ``V<major>.<minor>`` branch present on ``origin``, as plain
    branch names (no ``origin/`` prefix), newest first. Empty when no
    V-branches are published yet, or when ``for-each-ref`` fails.

    ``git_runner`` is the same closure used elsewhere in the updater: it
    takes positional ``git`` arguments and returns an object with
    ``returncode`` (int) and ``stdout`` (str) attributes (e.g. a
    ``subprocess.CompletedProcess``)."""
    res = git_runner(
        "for-each-ref",
        "--format=%(refname:short)",
        "refs/remotes/origin/",
    )
    if getattr(res, "returncode", 1) != 0:
        return []
    candidates: list[tuple[Tuple[int, int], str]] = []
    for line in (getattr(res, "stdout", "") or "").splitlines():
        short = line.strip()
        if not short.startswith("origin/"):
            continue
        local_name = short[len("origin/"):]
        parsed = parse_version_branch(local_name)
        if parsed is not None:
            candidates.append((parsed, local_name))
    candidates.sort(reverse=True)
    return [name for _parsed, name in candidates]


def newest_remote_version_branch(
    git_runner: Callable[..., object],
) -> Optional[str]:
    """Return the highest ``V<major>.<minor>`` branch present on
    ``origin``, as a plain branch name (no ``origin/`` prefix). ``None``
    if no V-branches are published yet, or if ``for-each-ref`` fails."""
    branches = list_remote_version_branches(git_runner)
    return branches[0] if branches else None


# ── One-click source update (V2.25) ──────────────────────────────────────────
# The V2.22 cleanup made source checkouts read-only; the product owner asked
# for the one-click updater back — most users won't open a terminal. What
# returns is the SAFE subset: stash-aware branch switch and pure fast-forward.
# The old "Discard & update" (`git reset --hard`) path stays dead — local
# changes are set aside recoverably, never destroyed
# (tests/test_architecture_guard.py pins update_flow.py free of `--hard`).


def _run_detail(res) -> str:
    return ((getattr(res, "stderr", "") or "").strip()
            or (getattr(res, "stdout", "") or "").strip())


def working_tree_dirty(git_runner: Callable[..., object]) -> Optional[bool]:
    """``True``/``False`` per ``git status --porcelain``; ``None`` when git
    itself failed. Untracked files do NOT count — they never block a branch
    switch, and stashing them could sweep up a user's own files (e.g. a
    design saved into the app folder)."""
    res = git_runner("status", "--porcelain", "--untracked-files=no")
    if getattr(res, "returncode", 1) != 0:
        return None
    return bool((getattr(res, "stdout", "") or "").strip())


def update_to_branch(
    git_runner: Callable[..., object],
    branch: str,
    *,
    stash_label: Optional[str] = None,
) -> Tuple[bool, str]:
    """Move the checkout onto ``origin/<branch>`` — the one-click update.

    Uses ``git checkout -B <branch> origin/<branch>`` with the explicit
    start point: a bare ``git checkout V2.NN`` can detach onto the
    same-named release *tag* (see TestVersionBranchSwitchCheckout).

    When ``stash_label`` is given, tracked local modifications are stashed
    first and popped back after the switch. Returns ``(ok, detail)`` —
    ``detail`` is the failure text, or a warning note on success (e.g. the
    stash-pop conflicted and the changes stay safe in the stash)."""
    if stash_label:
        res = git_runner("stash", "push", "-m", stash_label)
        if getattr(res, "returncode", 1) != 0:
            return False, ("Couldn't set local changes aside "
                           "(git stash push):\n" + _run_detail(res))
    res = git_runner("checkout", "-B", branch, f"origin/{branch}")
    if getattr(res, "returncode", 1) != 0:
        msg = (f"git checkout -B {branch} origin/{branch} failed:\n"
               + _run_detail(res))
        if stash_label:
            pop = git_runner("stash", "pop")
            if getattr(pop, "returncode", 1) != 0:
                msg += ("\n\nYour local changes are still set aside — "
                        "restore them with: git stash pop")
        return False, msg
    if stash_label:
        pop = git_runner("stash", "pop")
        if getattr(pop, "returncode", 1) != 0:
            return True, ("Updated — but restoring your local changes hit a "
                          "conflict, so they were kept safe in the stash "
                          f"('{stash_label}'). Restore them with: "
                          "git stash pop")
    return True, ""


def fast_forward_upstream(
    git_runner: Callable[..., object],
) -> Tuple[bool, str]:
    """Fast-forward the current branch to its upstream
    (``git merge --ff-only @{u}``). Pure fast-forward — fails cleanly (no
    merge, no rebase) when the branches have diverged."""
    res = git_runner("merge", "--ff-only", "@{u}")
    if getattr(res, "returncode", 1) != 0:
        return False, "git merge --ff-only failed:\n" + _run_detail(res)
    return True, ""


def next_version_branch(
    git_runner: Callable[..., object],
    *,
    current: Optional[str] = None,
) -> Optional[str]:
    """The branch the current session should develop/push on, per the
    ``V<major>.<minor>`` convention.

    * If ``current`` is already a valid V-branch, keep it — this is a
      continuation of an existing release branch, so we must NOT bump.
    * Otherwise (a ``claude/*`` codename branch, ``main``, or detached HEAD),
      return the newest published V-branch with its minor incremented by one
      (e.g. newest ``V2.05`` → ``V2.06``).
    * ``None`` when no V-branches exist on ``origin`` yet, so the caller can
      leave the branch untouched rather than inventing a version.

    ``git_runner`` has the same shape as in ``newest_remote_version_branch``.
    """
    if parse_version_branch((current or "").strip()):
        return current.strip()
    newest = newest_remote_version_branch(git_runner)
    if newest is None:
        return None
    m = _VERSION_BRANCH_RE.match(newest)
    if m is None:  # defensive — newest_remote only returns valid V-branches
        return None
    major = int(m.group(1))
    minor_str = m.group(2)
    # Preserve the source minor's zero-padding width (the current release line
    # is padded, e.g. V2.05 → V2.06; an unpadded V1.31 → V1.32 is unchanged).
    width = len(minor_str)
    return f"V{major}.{int(minor_str) + 1:0{width}d}"

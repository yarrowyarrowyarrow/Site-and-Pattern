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


def newest_remote_version_branch(
    git_runner: Callable[..., object],
) -> Optional[str]:
    """Return the highest ``V<major>.<minor>`` branch present on
    ``origin``, as a plain branch name (no ``origin/`` prefix). ``None``
    if no V-branches are published yet, or if ``for-each-ref`` fails.

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
        return None
    candidates: list[tuple[Tuple[int, int], str]] = []
    for line in (getattr(res, "stdout", "") or "").splitlines():
        short = line.strip()
        if not short.startswith("origin/"):
            continue
        local_name = short[len("origin/"):]
        parsed = parse_version_branch(local_name)
        if parsed is not None:
            candidates.append((parsed, local_name))
    if not candidates:
        return None
    candidates.sort()
    return candidates[-1][1]

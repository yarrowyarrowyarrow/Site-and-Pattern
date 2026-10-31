"""
src/app_version.py — what version the running build identifies as.

Two cases:

* **Source checkout** (`python main.py`): there is no ``version.txt``;
  callers fall back to the live git branch (``UpdateFlowController.
  _current_branch_name``).
* **Frozen build** (`.dmg` / `.exe`): there is no git, so the build's
  version is read from ``version.txt`` — a one-line file written by
  ``scripts/packaging/build_installer.sh`` / ``…/build_installer.bat`` (or the
  GitHub Actions release workflow via ``APP_BUILD_VERSION``) and bundled by
  ``scripts/packaging/permadesign.spec``. It holds the ``V<major>.<minor>``
  branch/tag the bundle was built from.

``running_version`` answers for both, for the title bar (F231, V3.16).

Kept Qt-free so any layer can ask "what version am I".
"""

from __future__ import annotations

import functools
import os
import sys
from typing import Optional

from src.resources import resource_path
from src.version_branch import parse_version_branch


def build_version() -> Optional[str]:
    """The version baked into a frozen build (e.g. ``"V1.73"``), or ``None``
    when no ``version.txt`` is bundled (a normal source checkout)."""
    try:
        path = resource_path("version.txt")
        if os.path.isfile(path):
            with open(path, encoding="utf-8") as f:
                value = f.read().strip()
                return value or None
    except Exception:
        pass
    return None


def checkout_branch(root: Optional[str] = None) -> Optional[str]:
    """The branch a source checkout has out, read from ``.git/HEAD`` under
    ``root`` (the project root by default), or ``None`` on a detached HEAD or
    where there is no checkout.

    A file read rather than ``git rev-parse``, which is how ``update_flow``
    asks: this runs at every start, and a file needs neither git on the PATH
    nor a child process, which on Windows opens a console window when the app
    was started without one."""
    path = os.path.join(root or resource_path(), ".git", "HEAD")
    try:
        with open(path, encoding="utf-8") as f:
            head = f.read().strip()
    except OSError:
        return None
    prefix = "ref: refs/heads/"
    if not head.startswith(prefix):
        return None
    return head[len(prefix):] or None


@functools.lru_cache(maxsize=1)
def running_version() -> Optional[str]:
    """The release this copy is running, as the title bar names it (F231,
    V3.16): ``version.txt`` in a frozen build, else the checked-out branch,
    and ``None`` unless that is a ``V<major>.<minor>`` release. A development
    branch, a detached HEAD and a local build name no release.

    Read once per run because it names what is *running*. Updating a source
    checkout switches its branch and then offers a restart; until the restart
    the old code is still what runs."""
    found = build_version()
    if found is None and not getattr(sys, "frozen", False):
        found = checkout_branch()
    return found if found and parse_version_branch(found) else None

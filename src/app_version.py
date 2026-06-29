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

Kept Qt-free so any layer can ask "what version am I".
"""

from __future__ import annotations

import os
from typing import Optional

from src.resources import resource_path


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

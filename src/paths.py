"""
paths.py — Centralised path resolution for both dev and PyInstaller bundle.

When frozen (PyInstaller), resources live in sys._MEIPASS (temp extraction dir).
User-writable data (database, config) must live in the user's home directory
because the extraction dir is read-only.
"""

from __future__ import annotations
import os
import sys


def _project_root() -> str:
    """Return the project root (source tree root or PyInstaller bundle root)."""
    if getattr(sys, "frozen", False):
        return sys._MEIPASS  # type: ignore[attr-defined]
    # src/paths.py → go up two levels to reach project root
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def resource_path(relative: str) -> str:
    """Absolute path to a read-only resource (html, data files, schema)."""
    return os.path.join(_project_root(), relative)


def user_data_dir() -> str:
    """Absolute path to the user-writable data directory (~/.permadesign/)."""
    d = os.path.join(os.path.expanduser("~"), ".permadesign")
    os.makedirs(d, exist_ok=True)
    return d

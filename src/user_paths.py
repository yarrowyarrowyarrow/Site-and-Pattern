"""
src/user_paths.py — the single source of truth for the per-user data directory,
plus the one-time "PermaDesign → Site & Pattern" folder migration (V1.69).

Every persistent store (the design DB, the building/terrain packs, the soil
GeoTIFFs, the image cache) lives under one per-user app folder. Historically each
store re-derived that folder independently; this module is the one place that
computes it, and the one place that migrates a pre-rebrand ``PermaDesign`` folder
to the new ``Site & Pattern`` name so existing installs keep their database and
downloaded data packs.

Kept Qt-free and dependency-free so the DB layer, the offline stores and the
tests can all share one definition without importing PyQt.

Two access patterns, matching how the callers already work:

  * :func:`data_dir_path` is **pure** — it computes the path with no side effects,
    so module-level constants (``plants._DATA_DIR`` / ``_DB_PATH``) can be built at
    import time without creating or moving anything. ``plants._user_data_dir``
    delegates here, preserving the test monkeypatch point.
  * :func:`user_data_dir` **migrates + creates** the folder and returns it — for
    the offline stores that want a ready-to-use directory. It uses ``os.makedirs``
    (not ``Path.mkdir``) so the stores' existing ``os.makedirs``-stub tests keep
    suppressing real directory creation.

The actual migration must run **before** the new folder is created, otherwise the
"already migrated" guard (``target.exists()``) would skip it and strand the old
DB — see :func:`migrate_legacy_into` and its call in ``plants.init_db``.
"""

from __future__ import annotations

import os
import pathlib
import shutil
import sys

from src.branding import DATA_DIR_NAME, LEGACY_DATA_DIR_NAME


def _platform_base() -> str:
    """OS-conventional base directory the app folder sits inside (as a string).

    Treats Windows as ``os.name == "nt" or sys.platform == "win32"`` so it
    matches both the ``sys.platform`` checks the DB layer used and the ``os.name``
    checks the terrain/building/soil stores used. Kept on ``os.path`` strings
    (not ``pathlib``) so it's safe even when a test patches ``os.name`` to ``"nt"``
    on a POSIX host — ``pathlib.Path`` would try to build a ``WindowsPath`` and
    raise, but ``os.path`` does not."""
    if os.name == "nt" or sys.platform == "win32":
        return os.environ.get("APPDATA") or os.path.expanduser("~")
    if sys.platform == "darwin":
        return os.path.join(os.path.expanduser("~"), "Library", "Application Support")
    return os.environ.get("XDG_DATA_HOME") or os.path.join(
        os.path.expanduser("~"), ".local", "share")


def _data_dir_str() -> str:
    """The per-user data folder as a string — **pure**, no filesystem side effects."""
    return os.path.join(_platform_base(), DATA_DIR_NAME)


def data_dir_path() -> pathlib.Path:
    """The per-user data folder as a ``Path`` — **pure**, no filesystem side effects.

    Used by the DB layer (``plants._user_data_dir``) and the image cache, which
    want ``Path`` semantics. Built only on the real platform (never under an
    ``os.name`` patch), so the ``pathlib`` construction is safe here."""
    return pathlib.Path(_data_dir_str())


def migrate_legacy_into(target) -> None:
    """One-time rename of the legacy ``PermaDesign`` folder to ``target``.

    Moves ``<dirname(target)>/PermaDesign`` → ``target`` only when ``target`` does
    not yet exist and the legacy folder does. A no-op on fresh installs and on
    every launch after the first. Any failure is swallowed — callers fall back to
    whatever directory they can create, so user data is never stranded by a raised
    exception. Driving the move off ``target`` (rather than recomputing the base)
    means a test-overridden temp directory, which already exists, is a correct
    no-op. Uses ``os.path`` (not ``pathlib``) so it's safe under an ``os.name``
    patch."""
    target = os.fspath(target)
    legacy = os.path.join(os.path.dirname(target), LEGACY_DATA_DIR_NAME)
    if (os.path.exists(target)
            or os.path.abspath(legacy) == os.path.abspath(target)
            or not os.path.isdir(legacy)):
        return
    try:
        shutil.move(legacy, target)
    except (OSError, shutil.Error):
        # Leave the legacy folder in place; the caller still creates/uses a dir.
        pass


def user_data_dir() -> str:
    """Return the ready-to-use per-user data folder as a string (migrate + create).

    For the offline stores (terrain/building/soil), which join further filenames
    onto it. Returns a ``str`` (not ``Path``) and stays on ``os.path`` so it's safe
    even when a platform test patches ``os.name``. Uses ``os.makedirs`` so those
    stores' ``os.makedirs``-patching tests keep suppressing real dir creation."""
    target = _data_dir_str()
    migrate_legacy_into(target)
    os.makedirs(target, exist_ok=True)
    return target

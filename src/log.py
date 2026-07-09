"""
src/log.py — the app's one logging setup (V2.22).

The codebase's offline-first discipline swallows failures so the GUI keeps
working without a network — but historically it swallowed them *silently*
(``except Exception: pass``, ``return None``), so a frozen build in the
field left no trace of what went wrong. This module gives every swallow
point somewhere cheap to report to:

  * :func:`get_logger` — module loggers under the ``sitepattern`` root.
    Safe to call anywhere (Qt-free, no side effects); until
    :func:`init_logging` runs, records ≥ WARNING fall through to Python's
    last-resort stderr handler and everything else is dropped — so headless
    tests and the agent API stay quiet and never touch the filesystem.
  * :func:`init_logging` — called once from ``main.py``: attaches a small
    rotating file log at ``<user data dir>/logs/app.log`` (the same per-user
    folder as the DB, via ``src.user_paths``) plus a WARNING-level stderr
    echo for source checkouts. Never raises: a read-only disk or bad HOME
    must not stop the app from launching.

House rule for callers: an ``except Exception`` that degrades gracefully
should call ``log.warning(...)`` (or ``log.exception(...)`` when the
traceback matters) instead of passing silently. Offline-expected outcomes
(fetch failed, no network) log at INFO/DEBUG so a field log isn't all noise.
"""

from __future__ import annotations

import logging
import logging.handlers
import os

_ROOT_NAME = "sitepattern"
_initialized = False

# 1 MB × 3 files ≈ a few weeks of chatty INFO logging; small enough to
# attach whole to a bug report.
_MAX_BYTES = 1_000_000
_BACKUP_COUNT = 3


def get_logger(name: str = "") -> logging.Logger:
    """A logger namespaced under the app root.

    Pass ``__name__`` — ``src.foo`` becomes ``sitepattern.src.foo`` so one
    root-level configuration governs every module.
    """
    if not name or name == _ROOT_NAME:
        return logging.getLogger(_ROOT_NAME)
    return logging.getLogger(f"{_ROOT_NAME}.{name}")


def log_file_path() -> str:
    """Where :func:`init_logging` writes (the file may not exist yet)."""
    from src.user_paths import _data_dir_str
    return os.path.join(_data_dir_str(), "logs", "app.log")


def init_logging(level: int = logging.INFO) -> logging.Logger:
    """Attach the rotating file handler + stderr echo. Idempotent, never raises.

    Only the GUI entry point (``main.py``) calls this — tests and the
    headless scripting API deliberately don't, so they create no files.
    """
    global _initialized
    root = logging.getLogger(_ROOT_NAME)
    if _initialized:
        return root
    _initialized = True

    root.setLevel(level)
    root.propagate = False  # don't double-print through the global root

    stderr = logging.StreamHandler()
    stderr.setLevel(logging.WARNING)
    stderr.setFormatter(logging.Formatter("%(levelname)s %(name)s: %(message)s"))
    root.addHandler(stderr)

    try:
        path = log_file_path()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        fh = logging.handlers.RotatingFileHandler(
            path, maxBytes=_MAX_BYTES, backupCount=_BACKUP_COUNT,
            encoding="utf-8")
        fh.setLevel(level)
        fh.setFormatter(logging.Formatter(
            "%(asctime)s %(levelname)-7s %(name)s: %(message)s"))
        root.addHandler(fh)
        root.info("logging initialized → %s", path)
    except Exception:  # noqa: BLE001 — logging must never block launch
        root.warning("file logging unavailable; stderr only", exc_info=True)
    return root

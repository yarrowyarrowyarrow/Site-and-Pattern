"""
src/slot_errors.py — a button that fails says so, and the app carries on (V3.05).

PyQt6 treats an exception that escapes a slot as fatal: unless ``sys.excepthook``
has been replaced it calls ``qFatal`` and the process ends, with the design that
was open and every unsaved change in it. The traceback goes to stderr, which a
packaged build does not show, and not to the app's own log
(:func:`src.log.log_file_path`), so nothing is left to say what happened.

The V3.05 surface audit clicked every button in the window and found one that
did exactly this on every press (*Download Edmonton Data*, a moved constant).
That one is fixed; this is for the next one. :func:`install` replaces the hook
so an escaped exception is

* **logged**, with its traceback, to the app's log;
* **reported** in a message that names what went wrong and where the log is,
  without blocking the window (once per distinct fault per session, so a
  failing timer cannot bury the screen in boxes);
* **survived**: the event loop goes on and the design stays open.

Carrying on after an exception can leave one panel half-updated. That is the
trade every desktop app that does this makes (Anki and Calibre among them), and
it beats the alternative here, which is losing the session. The message says
to save, so the user decides.

The text and the throttle are Qt-free and tested without a display; only
:func:`_show` touches Qt. Installed from ``main.py``, never from tests, which
must keep seeing exceptions as failures.
"""

from __future__ import annotations

import sys
import time
import traceback

from src.log import get_logger, log_file_path

log = get_logger(__name__)

#: At most this many messages a minute, whatever the faults, so a slot that
#: fails on a timer cannot stack boxes faster than they can be closed.
MAX_PER_MINUTE = 3

_seen: set = set()
_shown_at: list = []


def fault_key(etype, tb) -> tuple:
    """What makes two faults the same one: the exception type and the line it
    was raised from. The message is left out on purpose, since it often holds
    a value that differs every time."""
    frames = traceback.extract_tb(tb) if tb is not None else []
    last = frames[-1] if frames else None
    where = (last.filename, last.lineno) if last else ("", 0)
    return (getattr(etype, "__name__", str(etype)),) + where


def describe(etype, value, tb) -> tuple[str, str]:
    """``(summary, details)``: one plain sentence for the message, and the
    traceback for whoever asks for it."""
    name = getattr(etype, "__name__", str(etype))
    text = str(value).strip()
    summary = f"{name}: {text}" if text else name
    if len(summary) > 160:
        summary = summary[:157] + "…"
    details = "".join(traceback.format_exception(etype, value, tb))
    return summary, details


def message_text(summary: str, log_path: str) -> str:
    """The words a person reads. Says what happened, that the design is still
    open, what to do, and where the record is; never asks them to diagnose."""
    return ("That action could not finish, and it was stopped. Your design is "
            "still open: save it before you go on.\n\n"
            f"What went wrong: {summary}\n\n"
            f"A full record is in the log:\n{log_path}\n\n"
            "Help → Send Feedback… tells the author.")


def should_show(key: tuple, now: float | None = None) -> bool:
    """True the first time a fault is seen this session, and only while fewer
    than :data:`MAX_PER_MINUTE` messages have been shown in the last minute."""
    now = time.monotonic() if now is None else now
    if key in _seen:
        return False
    recent = [t for t in _shown_at if now - t < 60.0]
    _shown_at[:] = recent
    if len(recent) >= MAX_PER_MINUTE:
        return False
    _seen.add(key)
    _shown_at.append(now)
    return True


def reset() -> None:
    """Forget what has been shown (tests)."""
    _seen.clear()
    _shown_at.clear()


def _hook(etype, value, tb) -> None:
    if issubclass(etype, (KeyboardInterrupt, SystemExit)):
        sys.__excepthook__(etype, value, tb)
        return
    summary, details = describe(etype, value, tb)
    try:
        log.error("Unhandled exception in the GUI: %s\n%s", summary, details)
    except Exception:                                      # noqa: BLE001
        pass
    sys.stderr.write(details)
    try:
        if should_show(fault_key(etype, tb)):
            _show(summary, details)
    except Exception:                                      # noqa: BLE001
        pass            # reporting a fault must never become a second one


def _show(summary: str, details: str) -> None:
    from PyQt6.QtCore import QThread, Qt
    from PyQt6.QtWidgets import QApplication, QMessageBox

    app = QApplication.instance()
    if app is None or QThread.currentThread() is not app.thread():
        return          # logged above; a box from a worker thread is unsafe
    try:
        path = log_file_path()
    except Exception:                                      # noqa: BLE001
        path = "(the app's data folder, logs/app.log)"
    box = QMessageBox(app.activeWindow())
    box.setIcon(QMessageBox.Icon.Warning)
    box.setWindowTitle("Something went wrong")
    box.setText(message_text(summary, path))
    box.setDetailedText(details)
    box.setStandardButtons(QMessageBox.StandardButton.Ok)
    box.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
    box.open()          # not exec(): the window behind keeps working


def install() -> None:
    """Replace ``sys.excepthook`` for the GUI process (main.py)."""
    sys.excepthook = _hook

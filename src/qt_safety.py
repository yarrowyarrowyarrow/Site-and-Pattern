"""
qt_safety.py — emitting from a worker thread without crashing the app (V2.37).

Several panels warm photos on `QThreadPool.globalInstance()` and signal the UI
when one lands. The fetch outlives the widget whenever the user closes a panel,
switches tabs, or quits while it is in flight — and a signal emitted on a
QObject whose C++ half has already been destroyed is a use-after-free, which
shows up as a segfault with no traceback rather than an exception anyone can
catch.

Python-side `try/except` is not enough on its own: it catches the RuntimeError
PyQt raises when the *wrapper* knows the object is gone, but not the case where
C++ ownership deleted the object without Python being told. `sip.isdeleted` is
the check that actually answers "is this still there?".

Kept tiny and Qt-import-lazy so it can be used from any of the workers without
dragging Qt into a Qt-free module.
"""

from __future__ import annotations


def is_alive(obj) -> bool:
    """True if ``obj``'s underlying C++ object still exists."""
    if obj is None:
        return False
    try:
        from PyQt6 import sip
    except ImportError:                      # pragma: no cover — no PyQt6
        return True
    try:
        return not sip.isdeleted(obj)
    except (TypeError, RuntimeError):
        # Not a sip-wrapped object, or already unusable — either way, do not
        # touch it.
        return False


def emit_if_alive(owner, signal_name: str, *args) -> bool:
    """Emit ``owner.<signal_name>(*args)`` only if ``owner`` still exists.

    Returns whether the emit happened. Never raises: this is called from worker
    threads, where an escaping exception is at best a silent thread death and at
    worst a crash.
    """
    if not is_alive(owner):
        return False
    try:
        getattr(owner, signal_name).emit(*args)
        return True
    except (RuntimeError, AttributeError, TypeError):
        # The object went away between the check and the emit, which is exactly
        # the race this exists for — losing the update is the correct outcome.
        return False


def stop_threads(owner, timeout_ms: int = 5000) -> list[str]:
    """Quit and join every ``QThread`` parented to ``owner``. Returns the names
    of any that would not stop.

    Qt's response to a ``QThread`` object being destroyed while its thread is
    still running is ``qFatal()`` — the process aborts. The window creates
    worker threads in ten places (terrain fetch, region download, shade, shade
    zones, generation, soil, buildings, wind, tree detection) and until V2.38
    stopped **none** of them on close, so quitting mid-fetch aborted instead of
    exiting. It showed up first as a test suite dying after its last test with
    "QThread: Destroyed while thread '' is still running", which is the same
    event: the window goes away, a worker is still going.

    **No ``terminate()``.** Killing a thread mid-statement can leave a SQLite
    write half-applied, and corrupting the user's catalogue to make an exit
    tidy is a bad trade. A worker that will not stop inside the timeout is
    reported and left alone.
    """
    if not is_alive(owner):
        return []
    try:
        from PyQt6.QtCore import QThread
    except ImportError:                      # pragma: no cover — no PyQt6
        return []
    stubborn: list[str] = []
    for thread in owner.findChildren(QThread):
        try:
            if not thread.isRunning():
                continue
            thread.quit()
            if not thread.wait(timeout_ms):
                stubborn.append(thread.objectName() or thread.__class__.__name__)
        except RuntimeError:
            # Already destroyed between findChildren and here — nothing to do.
            continue
    return stubborn

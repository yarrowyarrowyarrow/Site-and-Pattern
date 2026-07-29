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

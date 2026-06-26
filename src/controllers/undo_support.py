"""
src/controllers/undo_support.py — the @undoable decorator (V1.81).

Deliberately Qt-free: several controllers that this decorates
(``map_events``, ``area_fill_controller``) are importable without PyQt6, and
their unit tests rely on that. The decorator only reaches the Qt-bound
PersistenceController (where ``checkpoint`` lives) at *call* time, via
``self._main._persistence`` — so importing it pulls in no Qt.

See PersistenceController.checkpoint for the snapshot mechanism this drives.
"""

from __future__ import annotations

import functools
from contextlib import nullcontext


def undoable(label: str = ""):
    """Decorator for a controller method that mutates ``project["features"]``.

    Wraps the call in :meth:`PersistenceController.checkpoint`, so whatever the
    method does to the feature list becomes a single snapshot undo step. The
    decorated method must be a bound method whose object exposes ``self._main``
    (every controller and the scan-import dialog does). A call that changes
    nothing (a cancelled dialog, an empty selection) records no entry.

    This is the catch-all that makes undo exhaustive: bulk placements,
    removals, edits and imports all reverse through one mechanism, and a new
    feature type is covered for free once its handler is decorated.
    """
    def deco(method):
        @functools.wraps(method)
        def wrapper(self, *args, **kwargs):
            persistence = getattr(
                getattr(self, "_main", None), "_persistence", None)
            # No persistence controller wired (bare fake-main controller
            # tests) → run the body without a checkpoint. The real
            # MainWindow always has one by the time a gesture fires.
            cm = (persistence.checkpoint(label) if persistence is not None
                  else nullcontext())
            with cm:
                return method(self, *args, **kwargs)
        return wrapper
    return deco

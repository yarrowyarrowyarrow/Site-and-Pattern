"""
follow_design.py — the windows that show the design follow it (F89, V3.08).

Design principle P5 — see docs/DESIGN_PHILOSOPHY.md.

The 3D preview had a *Refresh from design* button, and Growth Snapshots a
*Refresh*: change the design on the map, look at either window, and it still
showed the old one until the button was pressed. The V3.05 surface audit called
the preview's "a manual sync, the 3D form of finding 1" (a read-out that does
not follow the design), and the owner said yes to the window following edits.
Split view has followed them since V2.44 (``src/controllers/split_view.py``),
and these windows follow by the same rule:

  * every edit ends in ``_mark_modified`` (the hook split view uses), and a
    design opened or undone ends in ``_sync_planning_panel``; both call
    :func:`request_sync`;
  * an open window rebuilds once the edits pause (a drag is one rebuild, not
    one per mouse move), and a closed one pays nothing: opening it rebuilds.
"""

from __future__ import annotations

from PyQt6.QtCore import QTimer

#: After the last edit, before a rebuild. The 3D scene walks every feature and
#: re-instances every mesh, so this is longer than split view's 220 ms; a drag
#: of a plant is still one rebuild, after the mouse lets go.
DELAY_MS = 400

#: ``(attribute on the main window, the method that rebuilds it)``.
WINDOWS = (("_scene3d_window", "follow_design"),
           ("_snapshot_window", "refresh"))


def request_sync(main) -> None:
    """The design changed: rebuild every open window once the edits pause."""
    for attr, method in WINDOWS:
        win = getattr(main, attr, None)
        if win is None:
            continue
        try:
            if not win.isVisible():
                continue
        except RuntimeError:                # deleted under us
            continue
        timer = getattr(win, "_follow_timer", None)
        if timer is None:
            timer = QTimer(win)
            timer.setSingleShot(True)
            timer.setInterval(DELAY_MS)
            timer.timeout.connect(
                lambda w=win, m=method: _rebuild(w, m))
            win._follow_timer = timer
        timer.start()


def settled(win) -> None:
    """``win`` rebuilt itself just now (an edit made in the 3D preview): drop
    the rebuild that edit queued."""
    timer = getattr(win, "_follow_timer", None)
    if timer is not None:
        timer.stop()


def _rebuild(win, method: str) -> None:
    """From a timer, so nothing may escape: an exception out of a Qt slot
    ends the process (the V2.38 and V2.40 aborts)."""
    from src.qt_safety import is_alive
    try:
        if is_alive(win) and win.isVisible():
            getattr(win, method)()
    except Exception:                                      # noqa: BLE001
        pass

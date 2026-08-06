"""
split_view.py — the map and the 3D scene, side by side (V2.44).

Design principle P5 (perception is constructed — make the invisible visible)
and P11 (the body and the site know things the screen does not; two views of one
place is the nearest a screen gets) — see docs/DESIGN_PHILOSOPHY.md.

Author's report: *"the split screen 3D and map mode so you can edit the design
in more ways than one."*

The two views answer different questions and always have. The map answers
*where* — spacing, boundaries, sun and wind, the plan a contractor works from.
The 3D answers *what it will be like* — height, mass, whether you can see the
neighbours' shed. Until now they were separate windows, so answering one
question meant losing sight of the other.

## What this actually is

A controller shim on ``MainWindow``, like ``persistence`` and ``map_events``,
so this costs **no MainWindow methods** (the architecture guard's ceiling is
126/140 and it is meaningful). ``app.py`` carries one lambda.

The left column of the existing ``QSplitter`` (``app.py``) becomes a *vertical*
splitter: map on top, ``Map3DWidget`` below. Nothing about the map or the side
panels moves.

## Two things that are load-bearing

**Lazy, and disposable.** A second ``QWebEngineView`` is real memory and a real
GPU context. It is built on the first toggle and destroyed when the split
closes, so a user who never opens it pays nothing.

**Debounced.** Both views read one ``main._project``; an edit in either has to
reach the other. Dragging a plant on the map fires a position update per mouse
move, and rebuilding the 3D scene per mouse-move would make the drag unusable —
``build_scene`` walks every feature and the viewer disposes and rebuilds every
instanced mesh. So map→3D is coalesced onto a short timer. 3D→map needs no
debounce: an edit there is a discrete click.

**Learn mode does not get this**, deliberately. A second view of the same place
is exactly the complexity the Learn door exists to remove, and the sandbox has
its own answer already — you are standing inside it.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import QSplitter

#: How long to wait after the last map change before rebuilding the 3D scene.
#: Long enough to swallow a drag's worth of updates, short enough that letting
#: go of the mouse feels like it took effect immediately.
_SYNC_DEBOUNCE_MS = 220


class SplitViewController:
    """Owns the second pane: building it, tearing it down, and keeping the two
    views showing the same project."""

    def __init__(self, main):
        self._main = main
        self.viewer = None
        self._splitter = None
        self._timer = None
        self._syncing = False

    # ── State ───────────────────────────────────────────────────────────────

    @property
    def active(self) -> bool:
        return self.viewer is not None

    # ── Toggling ────────────────────────────────────────────────────────────

    def toggle(self, on: bool) -> None:
        if bool(on) == self.active:
            return
        if on:
            self._open()
        else:
            self._close()

    def _open(self) -> None:
        """Build the 3D pane under the map."""
        from src.map3d_widget import Map3DWidget
        main = self._main

        # The map's own column, found through the widget rather than assumed:
        # app.py's layout has been restructured before and a hard-coded index
        # would break silently, showing an empty pane.
        holder = main.map_widget.parentWidget()
        layout = holder.layout() if holder is not None else None
        if layout is None:
            return

        self._splitter = QSplitter(Qt.Orientation.Vertical, holder)
        idx = layout.indexOf(main.map_widget)
        layout.removeWidget(main.map_widget)
        self._splitter.addWidget(main.map_widget)

        self.viewer = Map3DWidget(self._splitter)
        self._splitter.addWidget(self.viewer)
        self._splitter.setSizes([500, 340])
        self._splitter.setStretchFactor(0, 6)
        self._splitter.setStretchFactor(1, 4)
        layout.insertWidget(max(0, idx), self._splitter, 1)

        # Edits made *in* the 3D pane come back through the V2.43 bridge. The
        # design side has a single write path and an undo stack, so this hands
        # off to the map-events controller rather than mutating anything here.
        bridge = getattr(self.viewer, "bridge", None)
        if bridge is not None:
            bridge.species_inspected.connect(self._on_inspected)

        self._timer = QTimer(main)
        self._timer.setSingleShot(True)
        self._timer.setInterval(_SYNC_DEBOUNCE_MS)
        self._timer.timeout.connect(self._rebuild_scene)

        self.sync_from_project()

    def _close(self) -> None:
        """Take the pane down and give the map its column back."""
        main = self._main
        if self._timer is not None:
            self._timer.stop()
            self._timer = None
        if self._splitter is None:
            self.viewer = None
            return

        holder = self._splitter.parentWidget()
        layout = holder.layout() if holder is not None else None
        if layout is not None:
            idx = layout.indexOf(self._splitter)
            layout.removeWidget(self._splitter)
            # Reparent the map back into the column BEFORE the splitter is
            # deleted, or Qt takes the map down with its parent.
            main.map_widget.setParent(holder)
            layout.insertWidget(max(0, idx), main.map_widget, 1)
            main.map_widget.show()
        else:
            main.map_widget.setParent(None)

        if self.viewer is not None:
            # close() before deleteLater(), or closeEvent never runs and the
            # widget's workers are never stopped — the V2.40 "QThread destroyed
            # while still running" abort, which surfaces in an unrelated later
            # test rather than here.
            self.viewer.close()
            self.viewer.deleteLater()
        self.viewer = None
        self._splitter.deleteLater()
        self._splitter = None

    # ── Keeping the two in step ─────────────────────────────────────────────

    def request_sync(self) -> None:
        """Something changed on the map. Coalesce, then rebuild the 3D scene.

        Safe to call on every mouse-move of a drag: that is what it is for.
        """
        if not self.active or self._timer is None:
            return
        self._timer.start()

    def sync_from_project(self) -> None:
        """Rebuild now, without waiting — for a project load or an undo, where
        the change is discrete and the delay would just read as lag."""
        if not self.active:
            return
        if self._timer is not None:
            self._timer.stop()
        self._rebuild_scene()

    def _rebuild_scene(self) -> None:
        """Push the current project into the 3D pane.

        Everything from here down is wrapped, and that is not defensive
        padding. This runs from a ``QTimer`` slot, and a debounced rebuild can
        fire *after* the user closed the split — so the viewer may be a
        half-torn-down C++ object by the time we reach it. An exception
        escaping a Qt slot calls ``qFatal()``: a process abort with no
        traceback, surfacing in whatever ran next. The app has been bitten by
        exactly this twice (V2.38, V2.40).
        """
        if not self.active:
            return
        from src.qt_safety import is_alive
        from src.scene_contract import build_scene
        main = self._main
        if not is_alive(self.viewer):
            return
        try:
            scene = build_scene(getattr(main, "_project", None) or {})
        except Exception:                                  # noqa: BLE001
            return
        try:
            self.viewer.apply_scene(scene)
        except Exception:                                  # noqa: BLE001
            return
        try:
            from src.scene_wildlife import wildlife_for_scene, support_by_taxon
            pids = [p["plant_id"] for p in scene.get("plants", [])
                    if p.get("plant_id")]
            self.viewer.set_wildlife(wildlife_for_scene(scene),
                                     support_by_taxon(pids))
        except Exception:                                  # noqa: BLE001
            pass

    def _on_inspected(self, kind: str, key: str) -> None:
        """A click in the 3D pane. Records the discovery, so the ledger works
        the same on both sides of the app."""
        try:
            from src.db import progress
            from src.db.plants import get_plant
        except Exception:                                  # noqa: BLE001
            return
        if kind == "fauna":
            progress.record_seen(progress.FAUNA, key,
                                 how=progress.HOW_INSPECTED)
            return
        try:
            row = get_plant(int(key)) or {}
        except (TypeError, ValueError):
            return
        name = row.get("scientific_name") or ""
        if name:
            progress.record_seen(progress.PLANT, name,
                                 how=progress.HOW_INSPECTED)


# ── The flow-module entry points app.py calls ────────────────────────────────

def controller(main) -> SplitViewController:
    """The window's split-view controller, created on first use."""
    ctl = getattr(main, "_split_view", None)
    if ctl is None:
        ctl = SplitViewController(main)
        main._split_view = ctl
    return ctl


def toggle(main, on: bool) -> None:
    controller(main).toggle(bool(on))


def request_sync(main) -> None:
    """Called from the places that already know the design changed. A no-op
    when the split is closed, so callers never have to ask first."""
    ctl = getattr(main, "_split_view", None)
    if ctl is not None:
        ctl.request_sync()

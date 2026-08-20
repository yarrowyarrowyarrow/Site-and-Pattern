"""
src/sandbox_undo.py — undo for the wild-landscape sandbox (F104, V2.55).

Design principle P13 (a native planting has to be loved to survive) — see
docs/DESIGN_PHILOSOPHY.md.

The Learn side had no undo. Design mode has had a full undo/redo stack since
V1.81, and ``scene3d_edit_flow`` even carries a table comparing the two that
states it outright — the sandbox row reads ``undo: none``. So the half of the
app built for people who do not know what they are doing yet was the half where
every misclick was permanent, which is exactly backwards.

**Why not reuse ``controllers.undo_support.undoable``.** That decorator reaches
``self._main._persistence`` at call time, and the sandbox window is not
MainWindow — it is a standalone Learn-mode window that deliberately never brings
the design app up. The *mechanism* is reused instead, and it is the interesting
part: :meth:`PersistenceController._capture_state` snapshots features as **one
canonical JSON string** rather than a deepcopy tree, because features are JSON
by definition — they *are* the saved file. Same information, several times less
memory, immune to aliasing because strings are immutable, and comparing two
states is a string compare. The sandbox is literally a GeoJSON
``FeatureCollection`` on disk, so the trick transfers directly.

**Restores in place.** The window, the viewer bridge and the project store all
hold the same ``dict``; rebinding a new one would leave them pointing at the
old landscape. So :meth:`SandboxHistory.undo` clears and refills the dict the
caller already has.

**Reset is undoable too**, which is the point rather than a bonus: throwing away
every edit you have made is the single most destructive thing the window can do,
and it was one click with no way back.
"""

from __future__ import annotations

import json
from typing import Optional

#: How many steps back you can go. Bounded because a sandbox session can run
#: long and each entry holds a whole landscape; 30 is far past the point where
#: anyone is still undoing rather than pressing Reset.
DEFAULT_LIMIT = 30


def snapshot(project: dict) -> str:
    """A project as one canonical JSON string.

    ``sort_keys`` so two equal states always compare equal as text — without it
    a dict that merely reordered would register as a change and push a no-op
    entry onto the stack.
    """
    return json.dumps(project or {}, sort_keys=True, separators=(",", ":"))


class SandboxHistory:
    """A bounded stack of landscape snapshots, with a label per step."""

    def __init__(self, limit: int = DEFAULT_LIMIT):
        self._limit = max(1, int(limit))
        self._stack: list[tuple[str, str]] = []      # (label, snapshot)

    # ── recording ────────────────────────────────────────────────────────────

    def record(self, project: dict, label: str = "") -> None:
        """Push the state as it is **now**, before the caller mutates it.

        Called ahead of the change rather than after, so the stack holds the
        states to go *back* to. A snapshot identical to the one already on top
        is dropped: repeated identical pushes would otherwise make Undo look
        broken by requiring several presses to visibly do anything.
        """
        snap = snapshot(project)
        if self._stack and self._stack[-1][1] == snap:
            return
        self._stack.append((label, snap))
        if len(self._stack) > self._limit:
            del self._stack[0]

    # ── going back ───────────────────────────────────────────────────────────

    def can_undo(self) -> bool:
        return bool(self._stack)

    def next_label(self) -> str:
        """What the next Undo would reverse, for the button's tooltip."""
        return self._stack[-1][0] if self._stack else ""

    def undo(self, project: dict) -> bool:
        """Restore the most recent snapshot **into** ``project``. False if empty.

        Mutates in place — see the module docstring. A corrupt entry is dropped
        rather than raised: this is the button a confused beginner presses, and
        it must never be the thing that produces a traceback.
        """
        while self._stack:
            _label, snap = self._stack.pop()
            try:
                restored = json.loads(snap)
            except Exception:                              # noqa: BLE001
                continue
            if not isinstance(restored, dict):
                continue
            project.clear()
            project.update(restored)
            return True
        return False

    def clear(self) -> None:
        self._stack.clear()

    def __len__(self) -> int:
        return len(self._stack)


def history_for(win, limit: Optional[int] = None) -> SandboxHistory:
    """The window's history, created on first use.

    A helper rather than a constructor call at every site so the handlers in
    ``reference_edit_flow`` do not each have to remember to make one — a missing
    stack would silently mean "this particular verb is not undoable", which is
    the failure mode hardest to notice.
    """
    hist = getattr(win, "_history", None)
    if hist is None:
        hist = SandboxHistory(DEFAULT_LIMIT if limit is None else limit)
        win._history = hist
    return hist

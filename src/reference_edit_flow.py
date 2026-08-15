"""
reference_edit_flow.py — the sandbox's Qt-shaped edit handlers (V2.44).

Free functions taking ``win`` (the :class:`ReferenceEcosystemWindow`), the
flow-module pattern from ``src/wind_flow.py`` and ``src/learn_flow.py``: the
behaviour lives here rather than as window methods, so the window stays a
layout and the handlers stay readable on their own.

Split out of ``reference_ecosystem_window`` when the V2.44 toolbar and the net
took it past its 450-line ceiling. That guard's own comment named this seam in
advance — *"the split is the edit half — the bridge slots and the trowel"* — so
this is the extraction it asked for rather than a bigger number.

The decisions still live one layer down, in the Qt-free
:mod:`src.reference_edit`, which is the only thing allowed to touch the project
(through ``ProjectStore``, the single write path). This module is the glue: it
takes what the viewer's bridge reports, asks the core to do it, and puts the
answer on screen.

**Ordering note.** These run as the *completion callbacks* of the viewer's edit
animations (``html/scene3d/17-anim.js``), not on the click itself. That is why
a rebuild here is safe: by the time Python is told, the animation has finished
and the scene is already showing the result.
"""

from __future__ import annotations


def build_tools(win):
    """The palette bar: what to plant, the verbs, and the two ways out.

    Moved here from ``reference_ecosystem_window`` in V2.55. The window was at
    450 lines against a 450-line ceiling with nowhere to put an Undo button, and
    its guard comment's named seam had already been taken by the V2.44 split. So
    the seam this time is the obvious remaining one: **the module that owns what
    the buttons do now owns what they look like.**

    Qt is imported inside the function, like every other import in this file, so
    the module stays importable without PyQt6 — several tests read it as source
    and one imports it.
    """
    from PyQt6.QtWidgets import QComboBox, QHBoxLayout, QPushButton

    bar = QHBoxLayout()
    bar.setContentsMargins(8, 0, 8, 4)
    bar.addWidget(win._label("Plant:"))

    win._species = QComboBox()
    win._species.setMinimumWidth(220)
    win._species.setToolTip(
        "The species of this community. Deliberately not the whole "
        "catalogue — a wild community is a set of plants that belong "
        "together.")
    bar.addWidget(win._species)

    win._plant_btn = QPushButton("🌱 Plant")
    win._plant_btn.setCheckable(True)
    win._plant_btn.setToolTip("Click the ground to place the species above.")
    win._plant_btn.clicked.connect(lambda: win._set_mode("plant"))
    bar.addWidget(win._plant_btn)

    win._pull_btn = QPushButton("✖ Pull")
    win._pull_btn.setCheckable(True)
    win._pull_btn.setToolTip(
        "Click a plant to remove it — and see what loses support.")
    win._pull_btn.clicked.connect(lambda: win._set_mode("pull"))
    bar.addWidget(win._pull_btn)

    # The net (V2.44). Catch, look at, release — the creature is put back
    # when the animation finishes, which is both real field practice and
    # the only version of this that does not teach a child to take
    # pollinators out of a habitat (P11).
    win._net_btn = QPushButton("🥅 Net")
    win._net_btn.setCheckable(True)
    win._net_btn.setToolTip(
        "Walk up to a creature until a ring appears round it, then "
        "click anywhere to swing. Recorded in your field guide, then "
        "released — caught counts for more than seen.")
    win._net_btn.clicked.connect(lambda: win._set_mode("net"))
    # Hidden until walk mode — see _set_net_visible.
    win._net_btn.setVisible(False)
    bar.addWidget(win._net_btn)

    # Undo (F104, V2.55) sits beside Reset because Reset is the thing people
    # most need saving from. Disabled until there is something to reverse, so
    # it never offers an action that would do nothing.
    win._undo_btn = QPushButton("↶ Undo")
    win._undo_btn.setEnabled(False)
    win._undo_btn.setToolTip(
        "Step back through your changes to this landscape.")
    win._undo_btn.clicked.connect(lambda: on_undo(win))
    bar.addWidget(win._undo_btn)

    reset = QPushButton("↺ Reset")
    reset.setToolTip("Throw away your changes and restore the wild "
                     "community as it ships. Undo can bring them back.")
    reset.clicked.connect(lambda: on_reset(win))
    bar.addWidget(reset)

    bar.addStretch()

    # The way out (F104). Past the stretch, apart from the edit verbs, because
    # it is a different kind of act: it leaves Learn mode, which nothing else
    # on this bar does.
    from src.graduation_flow import on_graduate
    win._graduate_btn = QPushButton("🎓 Take into Design")
    win._graduate_btn.setToolTip(
        "Move this landscape to your own address and open it as a real "
        "design you can keep working on. Your sandbox stays as it is.")
    win._graduate_btn.clicked.connect(lambda: on_graduate(win))
    bar.addWidget(win._graduate_btn)
    return bar


def on_plant_requested(win, x: float, y: float,
                        plant_id: int, common_name: str):
    from src.reference_edit import plant_at, plant_consequence
    pick = win._current_pick()
    pid = int(plant_id) or int((pick or {}).get("plant_id") or 0)
    if not pid or not win._project:
        return
    name = common_name or (pick or {}).get("common_name") or "plant"
    _remember(win, f"planting the {name}")
    try:
        record = plant_at(win._project, pid, name, win._center, x, y,
                          planted_year=win._year)
    except Exception:      # noqa: BLE001
        return
    win._say.setText(plant_consequence(record))
    record_seen_plant(win, pid)
    save(win)
    win._render()
    _refresh_undo(win)


def on_pull_requested(win, x: float, y: float):
    from src.project_store import ProjectStore
    from src.reference_edit import nearest_plant, pull_at, pull_consequence
    if not win._project:
        return
    target = nearest_plant(win._project, win._center, x, y)
    if target is None:
        win._say.setText("Nothing there to pull — click closer to a plant.")
        return
    # The verdict has to be computed BEFORE the removal: pull_plant_impact
    # simulates the pull itself and returns None for a plant already gone.
    placed = ProjectStore(win._project).placed_plants
    line = pull_consequence(placed, target["plant_id"])
    _remember(win, f"pulling the {target.get('common_name', 'plant')}")
    removed = pull_at(win._project, target["plant_id"],
                      target["lat"], target["lng"],
                      feature_id=target.get("feature_id", ""))
    if removed is None:
        return
    win._say.setText(line or f"Pulled {target.get('common_name', 'it')}.")
    save(win)
    win._render()
    _refresh_undo(win)


def on_reset(win):
    from src.reference_edit import reset_sandbox
    # Reset is undoable, and that is the point rather than a nicety: throwing
    # away every edit you have made was one click with nothing behind it.
    _remember(win, "the reset")
    reset_sandbox(win._community)
    win._push(win._community)
    win._say.setText("Back to the community as it ships. Undo brings it back.")
    _refresh_undo(win)


# ── Undo (F104, V2.55) ───────────────────────────────────────────────────────
#
# The Learn side had none while Design had a full stack — the side built for
# people who do not know what they are doing yet was the side where every
# misclick was permanent. The stack itself is Qt-free in src/sandbox_undo.py;
# these are the three lines of glue around it.

def _remember(win, label: str = "") -> None:
    """Snapshot the landscape as it is now, before the caller changes it."""
    try:
        from src.sandbox_undo import history_for
        history_for(win).record(win._project, label)
    except Exception:      # noqa: BLE001
        pass               # never let bookkeeping break the edit itself


def _refresh_undo(win) -> None:
    """Enable/disable the Undo button and say what it would reverse."""
    btn = getattr(win, "_undo_btn", None)
    if btn is None:
        return
    from src.sandbox_undo import history_for
    hist = history_for(win)
    btn.setEnabled(hist.can_undo())
    nxt = hist.next_label()
    btn.setToolTip(f"Undo {nxt}." if nxt
                   else "Step back through your changes to this landscape.")


def on_undo(win):
    """Step one change back."""
    from src.sandbox_undo import history_for
    if not win._project:
        return
    hist = history_for(win)
    label = hist.next_label()
    if not hist.undo(win._project):
        win._say.setText("Nothing left to undo.")
        _refresh_undo(win)
        return
    save(win)
    win._render()
    win._say.setText(f"Undid {label}." if label else "Stepped back.")
    _refresh_undo(win)


def save(win):
    from src.reference_edit import save_sandbox
    try:
        save_sandbox(win._community, win._project)
    except Exception:      # noqa: BLE001
        pass


def on_inspected(win, kind: str, key: str):
    """Clicking a creature or a plant in the scene discovers it.

    Keyed by scientific name in the ledger, so a plant id has to be
    resolved first — ids are not stable across a reseed and a ledger of
    them would silently re-point after an upgrade.
    """
    try:
        from src.db import progress
    except Exception:      # noqa: BLE001
        return
    if kind == "fauna":
        progress.record_seen(progress.FAUNA, key,
                             how=progress.HOW_INSPECTED,
                             where=win._community)
        return
    try:
        record_seen_plant(win, int(key), how=progress.HOW_INSPECTED)
    except (TypeError, ValueError):
        pass


def on_caught(win, name: str):
    """A creature was netted. Record it as *caught* and say so.

    ``how='caught'`` rather than ``'inspected'`` is the whole point: it is
    the difference between having walked past something and having gone and
    looked at it, and it is what a later achievement can honestly reward.
    """
    try:
        from src.db import progress
        fresh = progress.record_seen(progress.FAUNA, name,
                                     how=progress.HOW_CAUGHT,
                                     where=win._community)
    except Exception:      # noqa: BLE001
        return
    if fresh:
        win._say.setText(f"Caught {name} — new to your field guide! "
                          f"Released back into the community.")
    else:
        win._say.setText(f"Caught {name} and let it go.")


def record_seen_plant(win, plant_id: int, how: str = ""):
    try:
        from src.db import progress
        from src.db.plants import get_plant
        row = get_plant(int(plant_id)) or {}
        name = row.get("scientific_name") or ""
        if name:
            progress.record_seen(
                progress.PLANT, name,
                how=how or progress.HOW_PLANTED, where=win._community)
    except Exception:      # noqa: BLE001
        pass



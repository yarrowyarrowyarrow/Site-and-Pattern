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


def on_plant_requested(win, x: float, y: float,
                        plant_id: int, common_name: str):
    from src.reference_edit import plant_at, plant_consequence
    pick = win._current_pick()
    pid = int(plant_id) or int((pick or {}).get("plant_id") or 0)
    if not pid or not win._project:
        return
    name = common_name or (pick or {}).get("common_name") or "plant"
    try:
        record = plant_at(win._project, pid, name, win._center, x, y,
                          planted_year=win._year)
    except Exception:      # noqa: BLE001
        return
    win._say.setText(plant_consequence(record))
    record_seen_plant(win, pid)
    save(win)
    win._render()


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
    removed = pull_at(win._project, target["plant_id"],
                      target["lat"], target["lng"],
                      feature_id=target.get("feature_id", ""))
    if removed is None:
        return
    win._say.setText(line or f"Pulled {target.get('common_name', 'it')}.")
    save(win)
    win._render()


def on_reset(win):
    from src.reference_edit import reset_sandbox
    reset_sandbox(win._community)
    win._push(win._community)
    win._say.setText("Back to the community as it ships.")


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



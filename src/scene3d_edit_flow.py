"""
scene3d_edit_flow.py — planting and pulling in the *design*, from inside it
(V2.46).

Design principle P11 (the body and the site know things the screen does not)
and P13 (a native planting has to be loved to survive) — see
docs/DESIGN_PHILOSOPHY.md.

    Author's report: *"I want the 3D view and the tour a reference ecosystem to
    have the same functionality. I want to be able to plant a plant or remove
    one, to catch a bug in a net the guy holds, to make it more like a game."*

V2.43 gave the *reference* windows a trowel; the 3D preview of your own design —
the one you actually spend time in — stayed read-only. The viewer never needed
changing for this: ``html/scene3d/16-editing.js`` reports a point in scene
metres and knows nothing about which window it is in. What was missing was a
Python side for the design, and the difference from the sandbox is the whole
reason this is a separate module rather than a second caller of
:mod:`src.reference_edit_flow`:

============  ==========================  ==============================
              reference sandbox           the design
============  ==========================  ==============================
state         a throwaway sandbox file    the user's real project
undo          none                        MainWindow's undo stack
other views   just the 3D window          the 2D map, the plant panel,
                                          the planning panel, the score
saving        ``save_sandbox`` each edit  the project's own dirty flag
============  ==========================  ==============================

So every verb here goes through **the same path a map click takes** —
``ProjectStore`` for the write, ``_push_undo`` before it, and the panel/map
re-syncs after — rather than a second, quieter way to modify a design. A plant
you put in from the 3D view is undoable, appears on the map, counts toward the
Habitat Value Score, and is saved with everything else, because it is not a
different kind of plant.

**Ordering note**, same as the sandbox: these run as the *completion callbacks*
of the viewer's edit animations (``html/scene3d/17-anim.js``), so by the time
Python is told, the animation has finished and a rebuild is safe.
"""

from __future__ import annotations

from typing import Optional

#: What to say when a swing finds nothing at all (V2.46c).
MISS_HINT = (
    "Nothing in reach — walk right up to a creature until a ring appears "
    "round it, then swing.")

#: The three verbs, and the attribute each button hangs off ``win``.
_TOOLS = (
    ("plant", "_plant_btn", "🌱 Plant",
     "Click the ground to plant the species selected in the Plants panel — "
     "at the year on the slider, so it grows in from nursery stock."),
    ("pull", "_pull_btn", "✖ Remove",
     "Click a plant to take it out — and see what loses support."),
    ("net", "_net_btn", "🥅 Net",
     "Walk up to a creature until a ring appears round it, then click "
     "anywhere to swing. Recorded in your field guide, then released — "
     "caught counts for more than seen."),
)


def build_tools(win):
    """The edit row for :class:`~src.scene3d_window.Scene3DWindow`.

    Built here rather than in the window for the reason every flow module
    exists: the window stays a layout, and one file owns this whole feature —
    the buttons, the mode, the bridge and the handlers — so none of them can be
    changed without the others being visible.
    """
    from PyQt6.QtWidgets import QHBoxLayout, QLabel, QPushButton

    bar = QHBoxLayout()
    lab = QLabel("Edit:")
    lab.setStyleSheet("color: #90a4ae; font-size: 11px;")
    bar.addWidget(lab)
    for mode, attr, text, tip in _TOOLS:
        btn = QPushButton(text)
        btn.setCheckable(True)
        btn.setToolTip(tip)
        btn.clicked.connect(lambda _c=False, m=mode: set_mode(win, m))
        setattr(win, attr, btn)
        bar.addWidget(btn)
    # Hidden until he is actually walking — see set_walking.
    win._net_btn.setVisible(False)
    win._edit_hint = QLabel("")
    win._edit_hint.setStyleSheet("color: #cfe8d2; font-size: 11px;")
    bar.addWidget(win._edit_hint)
    bar.addStretch(1)
    return bar


def set_walking(win, on: bool) -> None:
    """Show the net only while he is out there to hold it (V2.46d).

        *"The buttons for the human character should only be visible when you
        enter that character mode."*

    Right, and it was worse than clutter: the net is the WALKER's tool — it has
    a hand, an arm and a 3 m reach — so out of walk mode the button was offering
    a verb that could not work the way its own tooltip described. Plant and
    Remove stay visible, because clicking the ground from the overview is a
    perfectly good way to place a plant and has nothing to do with the avatar.
    """
    btn = getattr(win, "_net_btn", None)
    if btn is None:
        return
    btn.setVisible(bool(on))
    if not on and btn.isChecked():
        btn.setChecked(False)
        set_mode(win, "net")          # clears it, since the button is now off


def set_mode(win, mode: str) -> None:
    """Turn one verb on and the other two off (click again to turn it off).

    Checkable buttons in a plain row are not a QButtonGroup, so the exclusivity
    is explicit — and clicking the *active* verb clears it, which is what makes
    it possible to get back to plain looking without a fourth button.
    """
    want = mode if getattr(win, _button_attr(mode)).isChecked() else ""
    for m, attr, _t, _tip in _TOOLS:
        getattr(win, attr).setChecked(m == want)
    hint = ""
    if want == "plant":
        pick = win._current_plant_pick()
        hint = (f"Planting {pick['common_name']}."
                if pick else "Pick a species in the Plants panel first.")
    elif want == "pull":
        hint = "Click a plant to remove it."
    elif want == "net":
        hint = "Walk up to a creature until a ring appears, then swing."
    win._edit_hint.setText(hint)
    pick = win._current_plant_pick() if want == "plant" else None
    win.viewer.set_edit_mode(want, pick)


def _button_attr(mode: str) -> str:
    return next(a for m, a, _t, _tip in _TOOLS if m == mode)


def connect_bridge(win) -> bool:
    """Wire the viewer's JS→Python channel. False when there is none.

    There is none in the ``web3d/dist`` fork build, and none if the page failed
    to load. Editing then simply does nothing — the right failure, because the
    window still previews the design, which is what it did before V2.46.
    """
    bridge = getattr(win.viewer, "bridge", None)
    if bridge is None:
        for _m, attr, _t, _tip in _TOOLS:
            btn = getattr(win, attr, None)
            if btn is not None:
                btn.setEnabled(False)
                btn.setToolTip("Editing needs the built-in 3D viewer.")
        return False
    bridge.plant_requested.connect(
        lambda x, y, pid, nm: on_plant_requested(win, x, y, pid, nm))
    bridge.pull_requested.connect(
        lambda x, y: on_pull_requested(win, x, y))
    bridge.species_inspected.connect(
        lambda kind, key: on_inspected(win, kind, key))
    bridge.species_caught.connect(lambda name: on_caught(win, name))
    bridge.out_of_reach.connect(lambda name: on_out_of_reach(win, name))
    return True


def on_out_of_reach(win, name: str):
    """A swing that caught nothing. Always says something.

    An empty ``name`` means "nothing was in reach at all" rather than "that
    particular animal was too far" — the viewer sends both, because a click
    that silently does nothing is indistinguishable from a broken button, and
    that was half of *"catching the bugs is impossible"*.
    """
    _say(win, f"{name} is out of reach — walk closer and swing again."
         if name else MISS_HINT)


def scene_center(win) -> Optional[tuple]:
    """The (lat, lng) the viewer's scene metres are measured from.

    ``Scene3DWindow`` stashes ``build_scene``'s origin as ``_last_origin`` on
    every push. Without one there is no way to turn a click into a place, and
    every verb below declines rather than guessing.
    """
    o = getattr(win, "_last_origin", None) or {}
    try:
        return (float(o["lat"]), float(o["lng"]))
    except (KeyError, TypeError, ValueError):
        return None


def _say(win, text: str) -> None:
    """Put a line where the user is looking.

    The 3D window has no consequence row of its own, so this uses the main
    window's status bar — the surface every other design edit already reports
    through.
    """
    try:
        win._main.statusBar().showMessage(text, 6000)
    except Exception:      # noqa: BLE001
        pass


def on_plant_requested(win, x: float, y: float,
                       plant_id: int, common_name: str):
    """Place the picked species at a point given in scene-local metres."""
    from src.project_store import store_for
    # `offset_latlng` and `plant_consequence` are Qt-free and window-agnostic —
    # reference_edit owns the metres↔degrees maths for both windows so the
    # sandbox and the design cannot disagree about where a click landed.
    from src.reference_edit import offset_latlng, plant_consequence

    center = scene_center(win)
    pick = win._current_plant_pick()
    pid = int(plant_id or 0) or int((pick or {}).get("plant_id") or 0)
    if center is None or not pid:
        _say(win, "Pick a species to plant first.")
        return
    name = common_name or (pick or {}).get("common_name") or "plant"
    lat, lng = offset_latlng(center[0], center[1], float(x), float(y))

    main = win._main
    import src.project as project_io
    group_id = project_io.new_placement_group_id()
    # Undo BEFORE the write, exactly as map_events._on_plant_placed does — the
    # snapshot has to be of the state the user would be returned to.
    main._push_undo({
        "action": "place_plant",
        "plant_id": pid, "common_name": name,
        "lat": lat, "lng": lng,
        "placement_group_id": group_id,
    })
    record = store_for(main).add_plant(
        pid, name, lat, lng, placement_group_id=group_id,
        # The year on the slider is when this went in the ground, so it grows
        # from nursery stock rather than appearing as mature as its neighbours
        # (V2.44, src/scene3d.effective_age).
        planted_year=int(win._year.value()))
    _resync(win, main)
    _say(win, plant_consequence(record))
    _record_seen_plant(pid)


def on_pull_requested(win, x: float, y: float):
    """Remove the plant nearest a point given in scene-local metres."""
    from src.project_store import ProjectStore, store_for
    from src.reference_edit import nearest_plant, pull_consequence

    center = scene_center(win)
    if center is None:
        return
    main = win._main
    target = nearest_plant(main._project, center, float(x), float(y))
    if target is None:
        _say(win, "Nothing there to remove — click closer to a plant.")
        return
    # The verdict is computed BEFORE the removal: pull_plant_impact simulates
    # the pull itself and returns nothing for a plant already gone.
    line = pull_consequence(ProjectStore(main._project).placed_plants,
                            target["plant_id"])
    # A *snapshot* checkpoint, not a `_push_undo` entry: `_do_undo` dispatches
    # on `entry["action"]` through a registered handler table, and a removal has
    # no per-action handler — it reverses through the generic before/after
    # snapshot the `@undoable` decorator uses for exactly this case. Pushing a
    # made-up action name would have looked right and undone nothing.
    with _checkpoint(main, "remove plant"):
        removed = store_for(main).remove_plant(
            int(target["plant_id"]), float(target["lat"]),
            float(target["lng"]), feature_id=target.get("feature_id", ""),
            newest_first=True)
    if removed is None:
        return
    try:
        main.plant_panel.on_plant_removed(int(target["plant_id"]))
    except Exception:      # noqa: BLE001
        pass
    _resync(win, main)
    _say(win, line or f"Removed {target.get('common_name', 'it')}.")


def on_inspected(win, kind: str, key: str):
    """Clicking a creature or a plant in the design discovers it too.

    The ledger is keyed by *scientific name*, never by id — ids are not stable
    across a reseed and a ledger of them would silently re-point on upgrade.
    """
    try:
        from src.db import progress
    except Exception:      # noqa: BLE001
        return
    if kind == "fauna":
        progress.record_seen(progress.FAUNA, key,
                             how=progress.HOW_INSPECTED, where="design")
        return
    try:
        _record_seen_plant(int(key), how=progress.HOW_INSPECTED)
    except (TypeError, ValueError):
        pass


def on_caught(win, name: str):
    """A creature was netted in your own yard. Recorded, then released."""
    try:
        from src.db import progress
        fresh = progress.record_seen(progress.FAUNA, name,
                                     how=progress.HOW_CAUGHT, where="design")
    except Exception:      # noqa: BLE001
        return
    _say(win, f"Caught {name} — new to your field guide! Released."
         if fresh else f"Caught {name} and let it go.")


# ── Shared tail ──────────────────────────────────────────────────────────────


def _checkpoint(main, label: str):
    """``main._persistence.checkpoint(label)``, or a no-op when there is no
    persistence controller (the bare-fake-main pattern the controller tests
    use). Same degradation as ``controllers.undo_support.undoable``."""
    from contextlib import nullcontext
    persistence = getattr(main, "_persistence", None)
    return persistence.checkpoint(label) if persistence is not None \
        else nullcontext()


def _resync(win, main) -> None:
    """Everything that has to agree with the project after an edit.

    The 2D map is redrawn from the project rather than patched, because the
    edit did not come from the map and there is no marker to reconcile — the
    same call the split-view controller makes.
    """
    try:
        main._persistence.render_project_to_map()
    except Exception:      # noqa: BLE001
        pass
    for call in (lambda: main._mark_modified(),
                 lambda: main._sync_planning_panel()):
        try:
            call()
        except Exception:      # noqa: BLE001
            pass
    try:
        win._push_scene()
    except Exception:      # noqa: BLE001
        pass


def _record_seen_plant(plant_id: int, how: str = "") -> None:
    try:
        from src.db import progress
        from src.db.plants import get_plant
        name = (get_plant(int(plant_id)) or {}).get("scientific_name") or ""
        if name:
            progress.record_seen(progress.PLANT, name,
                                 how=how or progress.HOW_PLANTED,
                                 where="design")
    except Exception:      # noqa: BLE001
        pass

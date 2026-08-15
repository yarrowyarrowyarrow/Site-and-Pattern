"""
graduation_flow.py — the Qt glue for leaving Learn mode (F104, V2.55).

Design principle P13 (a native planting has to be loved to survive) — see
docs/DESIGN_PHILOSOPHY.md.

The core is Qt-free in :mod:`src.graduation`: centroid, re-centre, name, save.
This is the part that needs a window — read the property pin off the design,
call the core, and bring MainWindow up. Same core-plus-``_flow`` split as
``wind.py``/``wind_flow.py`` and ``soil_grid.py``/``soil_flow.py``.

**It crosses the mode split deliberately.** ``app_mode._LEARN_ONLY`` keeps the
Learn windows from ever raising MainWindow — its docstring calls that "the whole
mechanical content of the mode split: the beginner does not meet the map". This
module is the sanctioned exception, and it only ever runs from an explicit
press. Nothing here should be called on the app's own initiative.

Imports are function-local, matching ``reference_edit_flow``, so the module can
be read and reasoned about without PyQt6 present.
"""

from __future__ import annotations

from typing import Optional


def property_pin(main) -> Optional[tuple]:
    """``(lat, lng)`` of the property pin on the design, or ``None``.

    Read off ``site_config`` rather than the site panel's widgets, because in
    Learn mode the panel exists but has never been shown or filled.
    """
    try:
        sc = ((main._project.get("properties") or {}).get("site_config") or {})
        lat, lng = sc.get("latitude"), sc.get("longitude")
        if lat is None or lng is None:
            return None
        return (float(lat), float(lng))
    except Exception:      # noqa: BLE001
        return None


def site_config(main) -> dict:
    """The design's cached site data, so the graduated project keeps it.

    Without this the graduation would be a downgrade rather than a promotion:
    ``MainWindow._load_from_path`` replays this block to restore the pin and
    every Site Info reading, so a project arriving without it would open at the
    right address with the whole site panel blank — and would overwrite the
    site data the user already had.
    """
    try:
        return dict((main._project.get("properties") or {})
                    .get("site_config") or {})
    except Exception:      # noqa: BLE001
        return {}


def on_graduate(win):
    """Take the sandbox landscape into Design.

    MainWindow is already built and merely not shown — ``main.py`` constructs it
    behind the start screen precisely so that "stepping into Design later" is
    instant. So this is a transform, a save, and a ``show()``.
    """
    from src import graduation

    main = getattr(win, "_main", None)
    if main is None or not getattr(win, "_project", None):
        win._say.setText("Couldn't open the design app from here.")
        return
    if not graduation.plant_records(win._project):
        win._say.setText("Plant something first — there is nothing to take.")
        return

    target = property_pin(main)
    project = graduation.graduate(win._project, target,
                                  site_config=site_config(main))
    try:
        path = graduation.save_as_design(project)
    except Exception:      # noqa: BLE001
        win._say.setText("Couldn't save the design. Your landscape is safe.")
        return

    open_in_design(main, path)
    # With no pin the landscape arrives at its own coordinates and the app's
    # normal first-step prompt asks for an address. Refusing to graduate would
    # put a wall exactly where this feature is trying to open a door.
    win._say.setText(
        "Opened in Design at your property." if target else
        "Opened in Design — set your address to place it on your land.")


def open_in_design(main, path: str) -> None:
    """Load the graduated design and bring MainWindow up.

    ``_load_from_path`` is the app's own File → Open path, so the landscape
    arrives exactly the way any saved design does: features rendered, undo
    cleared, site data replayed, remembered as the last design. Going through it
    rather than assigning ``main._project`` is what makes a graduated landscape
    an ordinary design rather than a special case.
    """
    loader = getattr(main, "_load_from_path", None)
    if callable(loader):
        loader(path)
    try:
        main.show()
        main.raise_()
        main.activateWindow()
    except Exception:      # noqa: BLE001
        pass

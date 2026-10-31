"""
month_tasks.py — this month's jobs for the plants in this design (V3.19, QF-12).

Design principle P4 — see docs/DESIGN_PHILOSOPHY.md.

Before a single plant was placed, the status bar read *"October: Direct Sow:
Meadow Sedge, Yellow Rattle | Harvest: Bog Cranberry, Broad-leaved Arrowhead,
Broomweed +3"*: the first eight calendar rows of the whole catalogue, not the
design's (R26). For someone with no plants it was noise, and "harvest
Broad-leaved Arrowhead" was baffling. The line now names only the plants in
the open design, and says nothing at all when the design has none, or when
none of them has a job this month.

The jobs are the plant page's (``species_page._TASKS``; a test keeps the words
equal): start indoors, sow outdoors, plant out, prune, and harvest only of a
plant with edible parts, where it is a job rather than the fruiting season said
again. Prune only in spring (V3.20, OV-8): the care calendar says cut back in
spring, never in the autumn tidy-up (``maintenance_calendar.says_prune``).

Qt-free: :func:`refresh` only sets the status bar label's text. The window
calls it wherever the design's plants can change: every edit and undo
(``_mark_modified``), a design opened (``_sync_planning_panel``) and a new one.
"""

from __future__ import annotations

from datetime import date
from typing import Callable, Iterable, Optional

from src.log import get_logger
from src.maintenance_calendar import says_prune

_log = get_logger(__name__)

#: ``(planting-calendar status, the job in words)``, in the order the work
#: comes in a year.
JOBS: tuple = (("start_indoors", "start indoors"),
               ("direct_sow", "sow outdoors"),
               ("transplant", "plant out"),
               ("pruning", "prune"),
               ("harvest", "harvest"))

#: Plants named per job before "and N more": the status bar is one line.
SHOWN = 3

_MONTHS = ("January", "February", "March", "April", "May", "June", "July",
           "August", "September", "October", "November", "December")


def jobs_for(plant_ids: Iterable[int], month: int, *,
             fetch: Optional[Callable] = None) -> list:
    """``[(job in words, [plant names])]`` for ``month``, in :data:`JOBS`
    order, for these plants only. ``fetch(ids, month)`` returns calendar rows
    (``src.db.plants.get_month_tasks`` unless a test passes its own)."""
    ids = [i for i in (plant_ids or ()) if i is not None]
    if not ids:
        return []
    if fetch is None:
        from src.db.plants import get_month_tasks as fetch
    by_status: dict = {}
    for row in fetch(ids, int(month)) or []:
        status = row.get("status")
        if status == "harvest" and not (row.get("edible_parts") or "").strip():
            continue
        if status == "pruning" and not says_prune(month):
            continue
        name = (row.get("common_name") or "").strip()
        names = by_status.setdefault(status, [])
        if name and name not in names:
            names.append(name)
    return [(words, by_status[status]) for status, words in JOBS
            if by_status.get(status)]


def _names(names: list) -> str:
    """"A", "A and B", "A, B and C", "A, B, C and 2 more"."""
    shown = names[:SHOWN]
    more = len(names) - len(shown)
    if more:
        return f"{', '.join(shown)} and {more} more"
    if len(shown) == 1:
        return shown[0]
    return f"{', '.join(shown[:-1])} and {shown[-1]}"


def status_line(jobs: list, month: int) -> str:
    """``"To do in October: prune Saskatoon and Wild Rose · plant out Wild
    Bergamot"``, or ``""`` when there is nothing to do."""
    if not jobs:
        return ""
    parts = [f"{words} {_names(names)}" for words, names in jobs if names]
    if not parts:
        return ""
    return f"To do in {_MONTHS[int(month) - 1]}: " + " · ".join(parts)


def refresh(main, *, month: Optional[int] = None) -> None:
    """Set the status bar's line for the design open in ``main``. Cheap on
    every edit: the database is asked only when the set of plants, or the
    month, has changed since the last time (a drag changes neither)."""
    label = getattr(main, "_sb_tasks", None)
    if label is None:
        return
    month = int(month or date.today().month)
    ids = frozenset(p.get("plant_id")
                    for p in (getattr(main, "_placed_plants", None) or [])
                    if p.get("plant_id") is not None)
    key = (ids, month)
    if getattr(main, "_month_tasks_key", None) == key:
        return
    try:
        text = status_line(jobs_for(ids, month), month)
    except Exception:                                      # noqa: BLE001
        # A status line must never take an edit down with it.
        _log.warning("this month's jobs could not be read", exc_info=True)
        text = ""
    main._month_tasks_key = key
    label.setText(text)

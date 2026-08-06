"""
learn_flow.py — Qt-shaped wiring for Learn mode (V2.43).

Free functions taking ``main`` (the MainWindow), the flow-module pattern from
``src/wind_flow.py`` and ``src/onboarding_flow.py``. Everything user-visible is
decided in the Qt-free :mod:`src.app_mode` and :mod:`src.reference_edit`; this
does the Qt-shaped half — open the second screen, open the lessons over the
sandbox, and read the counts those screens display.

Split out of ``onboarding_flow`` when the Learn wiring took that module past
its 620-line ceiling. That guard says, in its own words, that the fix is
"extraction, never raising the number without a split plan" — and this is the
natural seam: the cold-start path and the Learn-mode path share only the start
screen, so a module boundary between them costs one import and keeps each
readable on its own.

The functions here are deliberately all failure-tolerant. Every one of them
feeds a screen that must open regardless: a menu that will not appear because a
species count could not be read is a much worse bug than a menu with a blank
note column.
"""

from __future__ import annotations

from PyQt6.QtWidgets import QDialog


def _safely(fn) -> None:
    """Run an action without letting it take the launch with it."""
    try:
        fn()
    except Exception:                                      # noqa: BLE001
        pass


def open_learn_menu(parent) -> str:
    """Show the Learn menu, built against what the learner has actually done."""
    from src.learn_menu import LearnMenu
    dlg = LearnMenu(parent, discovery_line=discovery_line(),
                    communities=community_count(),
                    sandbox=sandbox_name())
    if dlg.exec() != QDialog.DialogCode.Accepted:
        return ""
    return dlg.choice()


def open_studio(main) -> None:
    """Open the lessons over the sandbox — the landscape the user has been
    planting in, not an empty design.

    This is the point of the V2.43 sandbox: ``LearnPanel`` is design-aware and
    had nothing to talk about in Learn mode until the reference landscape
    became a real, editable, saved project. With no sandbox yet it still opens
    and still works — the quiz falls back to the catalogue — so a first-time
    learner is never shown a locked door.
    """
    from src.learn_menu import LearnStudioWindow

    def _go():
        plants, title = _sandbox_plants()
        win = getattr(main, "_learn_studio", None)
        if win is None:
            win = LearnStudioWindow(plants, title)
            main._learn_studio = win
        else:
            win.set_plants(plants)
        win.show()
        win.raise_()
        win.activateWindow()

    _safely(_go)


def sandbox_key() -> str:
    """Which reference community the learner was last in, or ``""``."""
    try:
        from src.db import progress
        return progress.get_state(progress.LAST_COMMUNITY, "")
    except Exception:                                      # noqa: BLE001
        return ""


def sandbox_name() -> str:
    """The human name of that community, for the Learn menu's note column."""
    key = sandbox_key()
    if not key:
        return ""
    try:
        from src.reference_ecosystem import reference_community
        return reference_community(key).get("name", "")
    except Exception:                                      # noqa: BLE001
        return ""


def sandbox_plants() -> tuple:
    """``(placed_plants, community_name)`` for the saved sandbox, or
    ``([], "")``. Never raises: the lessons must open either way."""
    key = sandbox_key()
    if not key:
        return ([], "")
    try:
        from src.project_store import ProjectStore
        from src.reference_edit import load_sandbox
        project = load_sandbox(key)
        if not project:
            return ([], sandbox_name())
        return (ProjectStore(project).placed_plants, sandbox_name())
    except Exception:                                      # noqa: BLE001
        return ([], sandbox_name())


def community_count() -> int:
    """How many wild communities there are to walk into."""
    try:
        from src.reference_ecosystem import community_keys
        return len(community_keys())
    except Exception:                                      # noqa: BLE001
        return 0


def discovery_line() -> str:
    """"37 of 581 species discovered" — the collection loop's one number, on
    the front door. ``""`` when the ledger cannot be read, which is the right
    answer for a start screen that must never fail to open over a count."""
    try:
        from src.db import progress
        return progress.coverage_line()
    except Exception:                                      # noqa: BLE001
        return ""

"""
learn_flow.py — Qt-shaped wiring for Learn mode (V2.43).

Free functions taking ``main`` (the MainWindow), the flow-module pattern from
``src/wind_flow.py`` and ``src/onboarding_flow.py``. Everything user-visible is
decided in the Qt-free :mod:`src.app_mode` and :mod:`src.reference_edit`; this
does the Qt-shaped half — open the lessons or the quizzes over the sandbox,
and read the count the start screen's walk door displays. (It opened the
Learn menu too, until V3.42 put the Learn doors on the start screen.)

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

from src.app_mode import LESSONS, QUIZZES


def _safely(fn, what: str) -> None:
    """Run an action without letting it take the launch with it.

    A failure is reported, not swallowed (V3.18, ST-3): until then this
    ``pass`` hid a NameError that left the Lessons door dead for a release,
    and ``main.py``'s safety net then showed the design window instead, which
    read as "Learn opens the regular app". ``what`` names the thing that could
    not open, in the words the message uses ("The Lessons").
    """
    try:
        fn()
    except Exception:                                      # noqa: BLE001
        from src import slot_errors
        slot_errors.report(what)


def open_studio(main, page: str = LESSONS) -> None:
    """Open the lessons or the quizzes (``page``) over the sandbox — the
    landscape the user has been planting in, not an empty design.

    This is the point of the V2.43 sandbox: ``LearnPanel`` is design-aware and
    had nothing to talk about in Learn mode until the reference landscape
    became a real, editable, saved project. With no sandbox yet it still opens
    and still works — the quiz falls back to the catalogue — so a first-time
    learner is never shown a locked door.

    One window per page, kept on ``main._learn_windows`` and raised again on
    a second click (V3.42: the start screen's Lessons and Quizzes are
    separate doors).
    """
    from src.learn_window import TITLES, LearnStudioWindow
    page = page if page in TITLES else LESSONS

    def _go():
        plants, title = sandbox_plants()
        windows = getattr(main, "_learn_windows", None)
        if windows is None:
            windows = main._learn_windows = {}
        win = windows.get(page)
        if win is None:
            win = windows[page] = LearnStudioWindow(plants, title, page=page)
        else:
            win.set_plants(plants)
        win.show()
        win.raise_()
        win.activateWindow()

    _safely(_go, "The Quizzes" if page == QUIZZES else "The Lessons")


def sandbox_key() -> str:
    """Which reference community the learner was last in, or ``""``."""
    try:
        from src.db import progress
        return progress.get_state(progress.LAST_COMMUNITY, "")
    except Exception:                                      # noqa: BLE001
        return ""


def sandbox_name() -> str:
    """The human name of that community, for the Learn windows' titles."""
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
    """How many wild communities there are to walk into: the start screen's
    "Seven native places, in 3D"."""
    try:
        from src.reference_ecosystem import community_keys
        return len(community_keys())
    except Exception:                                      # noqa: BLE001
        return 0

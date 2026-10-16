"""
start_flow.py — the glue behind "Your designs" (V3.23, ST-4 to ST-8;
docs/homeowner/04-start-screen.md).

``onboarding_flow.py`` had the start screen's glue and sat at 571 of its 620
lines, so the rebuilt screen's lives here: what the screen lists, the line of
what is in flower, one way to start a new yard (ST-6), renaming the open
design (ST-7), naming a design from its address (ST-5), and keeping a crash's
unsaved work when Restore is passed over (ST-8). Free functions taking
``main``, so MainWindow's method count does not grow.
"""

from __future__ import annotations

import os

from src import start_screen as screen

#: A listed design's choice carries its path after this separator, so the
#: launch sequence passes one string from the screen to the dispatch.
_SEP = "\0"


def path_choice(path: str) -> str:
    return f"{screen.OPEN_PATH}{_SEP}{path}"


def split_choice(choice: str) -> tuple[str, str]:
    """``(key, path)``; ``path`` is ``""`` for every choice but a design."""
    key, _, path = (choice or "").partition(_SEP)
    return key, path


# ── What the screen shows ───────────────────────────────────────────────────

def screen_designs(limit: int = screen.SHOWN, directory=None):
    """``(rows, total)``: the saves folder plus the last design when it lives
    elsewhere (the example, a file opened with Browse), newest first. A row
    is ``{path, name, when, summary, error}``. Never raises."""
    from src import saves
    try:
        entries = saves.list_saves(directory)
        last = saves.last_design()
        if last and not any(os.path.abspath(e["path"]) == os.path.abspath(last)
                            for e in entries):
            entries.append(saves.describe(last))
        entries.sort(key=lambda e: e.get("modified") or 0, reverse=True)
    except Exception:                                      # noqa: BLE001
        return [], 0
    rows = [{"path": e["path"], "name": e.get("name") or e.get("filename", ""),
             "when": saves.when(e), "summary": saves.summary_line(e),
             "error": e.get("error", "")} for e in entries[:limit]]
    return rows, len(entries)


def flowering(month=None) -> tuple[str, str]:
    """The start screen's last line and its tooltip (the owner, V3.23)."""
    try:
        from src.plant_directory_bloom import flowering_around, flowering_line
        summary = flowering_around(month=month)
    except Exception:                                      # noqa: BLE001
        return "", ""
    names = summary.get("names") or []
    tip = ", ".join(names[:12]) + (f" and {len(names) - 12} more"
                                   if len(names) > 12 else "")
    return flowering_line(summary), tip


def open_screen(parent, *, recover: str, version: str, hidden: bool) -> str:
    """Show the screen; return its choice (a listed design as
    :func:`path_choice`), or ``""`` if it was closed. Writes the skip
    preference on every close."""
    from src import saves
    designs, total = screen_designs()
    line, tip = flowering()
    dlg = screen.StartScreen(
        parent, recover=recover, designs=designs, total=total,
        show_skip=bool(saves.last_design()), hidden=hidden, version=version,
        flowering=line, flowering_tip=tip)
    accepted = bool(dlg.exec())
    from src.onboarding_flow import START_SCREEN_OFF_KEY, _settings
    _settings().setValue(START_SCREEN_OFF_KEY, dlg.suppressed())
    if not accepted:
        return ""
    if dlg.choice() == screen.OPEN_PATH:
        return path_choice(dlg.chosen_path())
    return dlg.choice()


def keep_passed_autosave() -> str:
    """ST-8: the screen offered Restore and another row was chosen, so the
    crash's work is kept as its own design rather than left for the next
    autosave to overwrite. Returns the kept path, or ``""``."""
    try:
        from src import saves
        from src.controllers.persistence import autosave_path
        path = autosave_path()
        if not os.path.exists(path):
            return ""
        kept = saves.keep_unsaved(path)
        saves.clear_cache()
        return kept
    except Exception:                                      # noqa: BLE001
        from src.log import get_logger
        get_logger("start_flow").exception("could not keep the unsaved work")
        return ""


# ── Acting on a choice ──────────────────────────────────────────────────────

def dispatch(main, choice: str) -> bool:
    """Carry out the choices this module owns; ``False`` for any other."""
    key, path = split_choice(choice)
    if key == screen.NEW_YARD:
        start_new_yard(main)
    elif key == screen.OPEN_PATH:
        _open(main, path)
    elif key == screen.ALL_DESIGNS:
        main._on_open()
    elif key == screen.OPEN_FILE:
        path = main._ask_for_design_file()
        if path:
            _open(main, path)
    else:
        return False
    return True


def _open(main, path: str) -> None:
    from src import plain_messages
    if path and main._modified and not plain_messages.ask_discard_for_new(
            main, main._project.get("properties", {}).get("project_name", "")):
        return
    try:
        main._load_from_path(path)
    except Exception:                                      # noqa: BLE001
        plain_messages.tell_open_failed(main, path)


def start_new_yard(main) -> None:
    """ST-6: the one way to start a yard (the start screen's *Plan a new
    yard*, File › New and Help › Start Screen). Asks before unsaved work is
    lost, never asks for a name (it comes from the address, ST-5), then puts
    the cursor in the address search."""
    if not main._on_new():        # it asks before unsaved work is lost
        return
    try:
        main.site_panel.focus_address_search()
    except Exception:                                      # noqa: BLE001
        pass


def name_from_pin(main, label: str) -> None:
    """ST-5: a placeholder-named design takes its address's name when the pin
    arrives with one, and the title follows. A named design, a dragged pin
    (``''``) and a bare coordinate change nothing."""
    from src import design_name
    props = main._project.setdefault("properties", {})
    name = design_name.renamed(props.get("project_name", ""), label)
    if not name:
        return
    props["project_name"] = name
    _retitle(main, name)


def rename_open_design(main) -> None:
    """ST-7: File › Rename Design…, for the design that is open."""
    from src import plain_messages, saves
    props = main._project.setdefault("properties", {})
    current = props.get("project_name", "")
    new = plain_messages.ask_design_name(
        main, title="Rename design", label="New name:", suggested=current)
    if not new or new == current:
        return
    props["project_name"] = new
    if not main._project_path:
        main._mark_modified()           # the name reaches the file at Save
    else:
        try:
            main._project_path = saves.rename_save(main._project_path, new)
            saves.remember_last_design(main._project_path)
        except Exception:                                  # noqa: BLE001
            from src import plain_messages
            plain_messages.tell_save_failed(main, main._project_path)
            return
    _retitle(main, new)


def _retitle(main, name: str) -> None:
    from src.app_version import running_version
    from src.branding import window_title
    main.setWindowTitle(window_title(name, version=running_version()))

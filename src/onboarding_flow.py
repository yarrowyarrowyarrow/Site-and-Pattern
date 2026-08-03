"""
onboarding_flow.py — wiring for the cold-start path (F44 / F45).

Free functions taking ``main`` (the MainWindow), following the flow-module
pattern in ``src/wind_flow.py``: the behaviour lives here rather than as new
MainWindow methods, so ``app.py`` only carries lambdas.

Everything user-visible is decided in the Qt-free :mod:`src.onboarding`; this
module does the Qt-shaped work — read the QSettings flag, show the dialog, write
the example to disk, keep the step bar and the Site panel in step with the
project.
"""

from __future__ import annotations

import os

try:                                   # keep importable Qt-free (headless API)
    from PyQt6.QtCore import QSettings, QTimer
    from PyQt6.QtWidgets import QDialog, QMessageBox
    _HAVE_QT = True
except ImportError:                    # pragma: no cover — headless
    _HAVE_QT = False

#: QSettings key. Namespaced under the legacy org/app name like every other
#: setting in this app (see src/branding.py on why that name stays).
SEEN_WELCOME_KEY = "onboarding/welcome_seen"
#: Separate key: hiding the strip is not the same decision as having seen the
#: welcome, and conflating them made the strip vanish for people who had only
#: dismissed the dialog.
HIDE_STEP_BAR_KEY = "onboarding/step_bar_hidden"


def _settings():
    return QSettings()


# ── The welcome ──────────────────────────────────────────────────────────────

def should_show_welcome() -> bool:
    """Whether the start menu opens on launch.

    Until V2.40 this meant "has never been seen", and the dialog was a
    first-run greeting. It is now a start menu — every launch, unless the user
    has explicitly turned it off — so the key means "asked not to see this
    again" rather than "has seen it once".
    """
    if not _HAVE_QT:
        return False
    return not bool(_settings().value(SEEN_WELCOME_KEY, False, type=bool))


#: Deferral before the welcome appears. Long enough for the main window to
#: paint — a modal dialog over an unpainted window reads as a crash — and short
#: enough not to feel like a lag. A zero-timer is NOT enough: it can fire ahead
#: of the paint events show() queued.
_WELCOME_DELAY_MS = 150


def maybe_show_welcome(main) -> None:
    """Open the start menu on launch, unless the user has turned it off.

    Crash recovery used to be a *second* modal, fired separately on map_ready,
    and this function returned early whenever one was pending purely to keep
    two dialogs from stacking. Since V2.40 recovery is the menu's top row, so
    the two no longer compete — but see ``PersistenceController.
    maybe_offer_autosave_recovery``: when the menu is turned off, the
    standalone prompt still fires. Unsaved work is not conditional on a
    preference about greetings.
    """
    if not should_show_welcome():
        return
    QTimer.singleShot(_WELCOME_DELAY_MS, lambda: _welcome_if_alive(main))


def _welcome_if_alive(main) -> None:
    """Open the welcome, unless the window went away in the meantime (V2.38).

    The 150 ms delay is a window in which the MainWindow can be destroyed —
    rare in normal use (quit within a sixth of a second of launch) but routine
    in the test suite, which builds a probe window and deletes it immediately.
    Constructing a dialog parented to a deleted C++ object raises RuntimeError
    *inside a Qt slot*, and an exception escaping a Qt slot calls ``qFatal()``:
    a process abort. On Windows that killed the test run before it could print
    its summary; on Linux it printed a traceback and carried on, which is worse
    in a way — the same latent bug reading as harmless noise.

    ``qt_safety.is_alive`` is the check that actually answers this. A plain
    try/except catches the case where PyQt's wrapper knows the object is gone,
    but not the one where C++ ownership deleted it without telling Python.
    """
    from src.qt_safety import is_alive
    if not is_alive(main):
        return
    # NOT mark_seen: this fires on every launch now, and marking it seen here
    # would suppress the start menu after the first one — the exact behaviour
    # V2.40 replaced. Only the checkbox turns it off.
    show_welcome(main)


def _pending_recovery_name(main) -> str:
    """The design name inside a surviving autosave, or ``""``.

    Read rather than assumed, so the row can say *which* design has unsaved
    work — "a previous session" is a worse question to answer than "your Back
    Yard design". An unreadable autosave offers no row: the standalone recovery
    path discards it with its own message, and a button that leads to that is
    just a longer way to the same place.
    """
    if not _autosave_pending():
        return ""
    try:
        from src.controllers.persistence import autosave_path
        from src.project import load_project
        props = (load_project(autosave_path()).get("properties") or {})
        return props.get("project_name") or "Untitled Design"
    except Exception:                                      # noqa: BLE001
        return ""


def _open_last_design(main) -> None:
    """Reopen the design from the last session, through the ordinary path."""
    from src import saves
    path = saves.last_design()
    if not path:
        return
    try:
        main._load_from_path(path)
    except Exception as exc:                               # noqa: BLE001
        from PyQt6.QtWidgets import QMessageBox
        QMessageBox.critical(main, "Open failed", str(exc))


def _autosave_pending() -> bool:
    try:
        from src.controllers.persistence import autosave_path
        return os.path.exists(autosave_path())
    except Exception:                                      # noqa: BLE001
        return False


def show_welcome(main, *, mark_seen: bool = False) -> None:
    """Open the start menu and act on the choice. Also the Help-menu entry
    point.

    ``mark_seen`` is a no-op kept for callers; **only the "don't show this
    again" checkbox** turns the menu off now. It used to be that dismissing the
    dialog counted as an answer — reasonable for a one-time greeting, wrong for
    a start menu, where closing it means "I will start from the blank map",
    not "never show me this again".
    """
    from src.welcome_dialog import (BLANK, CONTINUE, EXAMPLE, GENERATE, OPEN,
                                    RECOVER, WelcomeDialog)
    from src import saves

    last_path = saves.last_design()
    last_name = ""
    if last_path:
        entry = saves.describe(last_path)
        last_name = "" if entry.get("error") else entry["name"]

    recover_name = _pending_recovery_name(main)
    dlg = WelcomeDialog(main, last_design=last_name, recover=recover_name,
                        has_saves=bool(saves.list_saves()),
                        first_run=not last_name and not recover_name)
    result = dlg.exec()
    if dlg.suppressed():
        _settings().setValue(SEEN_WELCOME_KEY, True)
    if result != QDialog.DialogCode.Accepted:
        return

    choice = dlg.choice()
    if choice == RECOVER:
        # Tell the controller this is the menu asking, so its "the menu will
        # handle it" guard stands aside.
        main._persistence._recovery_from_menu = True
        main._persistence.maybe_offer_autosave_recovery()
    elif choice == CONTINUE:
        _open_last_design(main)
    elif choice == OPEN:
        main._on_open()
    elif choice == GENERATE:
        main._on_generate_design()
    elif choice == EXAMPLE:
        open_example(main)
    elif choice == BLANK:
        # Nothing to build — just point at step one and put the cursor where
        # the user has to act.
        try:
            main._side_tabs.setCurrentWidget(main.site_panel)
            main.site_panel.focus_address_search()
        except Exception:                                  # noqa: BLE001
            pass
    refresh(main)


# ── The worked example ───────────────────────────────────────────────────────

def example_path() -> str:
    """Where the example is written — the user's data dir, so it survives as a
    real file they can Save As, edit, or delete."""
    from src.onboarding import example_filename
    from src.user_paths import user_data_dir
    return os.path.join(user_data_dir(), example_filename())


def open_example(main) -> None:
    """Build the worked example and open it through the normal load path.

    Built fresh from the authored spec every time rather than shipped as a
    file, so it resolves against the catalogue the user actually has (see
    :mod:`src.onboarding`). Written to disk first so it opens through
    ``MainWindow._load_from_path`` — the same code path as File → Open, which
    means the panels, the title bar and the map restore exactly as they do for
    any other project rather than through a second, near-identical path that
    would rot.
    """
    from src.onboarding import build_example_project
    from src.project import save_project

    if not _confirm_discard(main, "Open Example"):
        return

    lat = lng = None
    try:
        coords = main.site_panel.current_coords()
        if coords:
            lat, lng = coords
    except Exception:                                      # noqa: BLE001
        pass

    try:
        project, missing = build_example_project(lat, lng)
        path = example_path()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        save_project(project, path)
        main._load_from_path(path)
    except Exception as exc:                               # noqa: BLE001
        QMessageBox.critical(main, "Example unavailable",
                             f"Could not build the example design:\n{exc}")
        return

    # The project is a fresh artifact, not the user's own work — but it IS
    # now on disk under its own name, so leave it unmodified and let Save
    # write back to it.
    note = ("Opened the example design — a front-yard lawn conversion. "
            "Everything in it is editable; Planning → Notes says what to try.")
    if missing:
        # Never quietly ship a thinner design than the one described (P9).
        note += (f"  ({len(missing)} species in the example aren't in this "
                 f"catalogue: {', '.join(missing[:3])}"
                 + ("…" if len(missing) > 3 else "") + ")")
    main.statusBar().showMessage(note, 15000)
    refresh(main)


def _confirm_discard(main, title: str) -> bool:
    """Guard the user's unsaved work before we replace the project."""
    if not getattr(main, "_modified", False):
        return True
    r = QMessageBox.question(
        main, title,
        "The current design has unsaved changes. Discard them and open the "
        "example?",
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel)
    return r == QMessageBox.StandardButton.Yes


# ── Keeping the guidance live ────────────────────────────────────────────────

def refresh(main) -> None:
    """Re-read the project and update the step bar + the Site panel line.

    Called after anything that could complete a step (pin, boundary, plant,
    project load, undo). Never raises — onboarding guidance must not be able
    to break the app it is trying to explain.
    """
    try:
        from src.onboarding import first_step, first_step_line, steps_progress
        project = main._project
        steps = steps_progress(project)
        current = first_step(project)
    except Exception:                                      # noqa: BLE001
        return

    bar = getattr(main, "first_step_bar", None)
    if bar is not None:
        try:
            bar.set_progress(steps, current)
            # The strip retires itself once the path is walked; an explicit
            # dismissal keeps it hidden regardless.
            bar.setVisible(not current["complete"] and not step_bar_hidden())
        except Exception:                                  # noqa: BLE001
            pass

    try:
        main.site_panel.set_first_step(first_step_line(project))
    except Exception:                                      # noqa: BLE001
        pass

    act = getattr(main, "_act_step_bar", None)
    if act is not None:
        try:
            act.setChecked(not step_bar_hidden())
        except Exception:                                  # noqa: BLE001
            pass


def step_bar_hidden() -> bool:
    if not _HAVE_QT:
        return False
    return bool(_settings().value(HIDE_STEP_BAR_KEY, False, type=bool))


def set_step_bar_hidden(main, hidden: bool) -> None:
    _settings().setValue(HIDE_STEP_BAR_KEY, bool(hidden))
    refresh(main)


def on_step_clicked(main, key: str) -> None:
    """A step chip was clicked — take the user to where that step happens.

    Guidance that only *describes* the next action is half a feature; these
    chips perform the navigation so the strip is a control, not a poster.
    """
    try:
        if key == "pin":
            main._side_tabs.setCurrentWidget(main.site_panel)
            main.site_panel.focus_address_search()
        elif key == "boundary":
            main.toolbar.activate_boundary_tool()
        elif key == "plants":
            main._side_tabs.setCurrentWidget(main._plant_poly_tab)
    except Exception:                                      # noqa: BLE001
        pass

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
    if not _HAVE_QT:
        return False
    return not bool(_settings().value(SEEN_WELCOME_KEY, False, type=bool))


#: Deferral before the welcome appears. Long enough for the main window to
#: paint — a modal dialog over an unpainted window reads as a crash — and short
#: enough not to feel like a lag. A zero-timer is NOT enough: it can fire ahead
#: of the paint events show() queued.
_WELCOME_DELAY_MS = 150


def maybe_show_welcome(main) -> None:
    """Show the welcome once, on the first launch."""
    if not should_show_welcome():
        return
    if _autosave_pending():
        # Crash recovery asks a more urgent question and fires on map_ready.
        # Two modal dialogs stacking on launch is worse than deferring the
        # welcome by one session. (Normally unreachable — an autosave implies
        # a previous session, which would have set the flag — but a wiped
        # QSettings over a surviving data dir gets here.)
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
    show_welcome(main, mark_seen=True)


def _autosave_pending() -> bool:
    try:
        from src.controllers.persistence import autosave_path
        return os.path.exists(autosave_path())
    except Exception:                                      # noqa: BLE001
        return False


def show_welcome(main, *, mark_seen: bool = False) -> None:
    """Open the welcome dialog and act on the choice. Also the Help-menu
    entry point, which is why ``mark_seen`` is opt-in: choosing to re-read the
    welcome should not change whether it appears next launch."""
    from src.welcome_dialog import BLANK, EXAMPLE, GENERATE, WelcomeDialog

    dlg = WelcomeDialog(main)
    result = dlg.exec()
    if mark_seen or dlg.suppressed():
        # Dismissing IS an answer: a user who closed the welcome does not want
        # it again next launch. The "don't show again" box additionally covers
        # the re-opened-from-Help case.
        _settings().setValue(SEEN_WELCOME_KEY, True)
    if result != QDialog.DialogCode.Accepted:
        return

    choice = dlg.choice()
    if choice == GENERATE:
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

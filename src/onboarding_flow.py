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
#:
#: **Dead since V2.41. Do not read it.** From V2.31 to V2.40 this meant "the
#: welcome has been shown once", and the auto-show path wrote it itself
#: (``show_welcome(main, mark_seen=True)``) the first time the dialog ever
#: appeared. V2.40 turned the welcome into a start menu and quietly redefined
#: the same key as "asked not to see this again". Both readings are reasonable;
#: the value on disk was written under the first one. So every install older
#: than V2.40 came up with the start screen already switched off, by a flag its
#: owner never set, and no control in the app could turn it back on.
SEEN_WELCOME_KEY = "onboarding/welcome_seen"

#: What actually decides it now. A **new key**, because the fix for a key whose
#: meaning changed is never to reinterpret the old value: nobody stored a
#: preference here, so nobody's preference is being discarded. Absent means
#: show, which is the right default for a screen that is the app's front door.
START_SCREEN_OFF_KEY = "onboarding/start_screen_off"
#: Separate key: hiding the strip is not the same decision as having seen the
#: welcome, and conflating them made the strip vanish for people who had only
#: dismissed the dialog.
HIDE_STEP_BAR_KEY = "onboarding/step_bar_hidden"


def _settings():
    return QSettings()


# ── The welcome ──────────────────────────────────────────────────────────────

def should_show_welcome() -> bool:
    """Whether the start screen opens on launch.

    Reads :data:`START_SCREEN_OFF_KEY` only. The old
    :data:`SEEN_WELCOME_KEY` is deliberately not consulted and not migrated:
    see its comment. Off by default means every install gets the front door
    back, including the ones that lost it to the V2.40 key reuse.
    """
    if not _HAVE_QT:
        return False
    return not bool(_settings().value(START_SCREEN_OFF_KEY, False, type=bool))


#: Fallback deferral for acting on a start-menu choice when there is no map
#: bridge to wait on. Long enough for the main window to paint — a modal over an
#: unpainted window reads as a crash — and short enough not to feel like a lag.
#: A zero-timer is NOT enough: it can fire ahead of the paint events show()
#: queued.
_WELCOME_DELAY_MS = 150


def choose_start_action() -> str:
    """Open the start menu **before the main window exists**, and return the
    choice (V2.40).

    The menu used to be a modal over an already-painted map: you saw the app,
    then a dialog on top of it, which is a greeting rather than a start screen.
    Running it first — with no parent, so it is a window of its own rather than
    a sheet over something — means the first thing you see is the choice, and
    the map appears already carrying it.

    Needs no MainWindow, which is what makes the ordering possible: everything
    on the menu is read from disk (the saves folder, the last-design path, a
    surviving autosave). Acting on the answer is :func:`act_on_start_choice`,
    once there is a window to act on.

    Returns ``""`` when the menu is turned off or dismissed.
    """
    if not _HAVE_QT or not should_show_welcome():
        return ""
    return _open_menu(None)


def _open_menu(parent) -> str:
    """Build the screen against what is on disk, show it, and return the row
    the user picked (``""`` if they closed it).

    One body for both entry points — the launch sequence and Help → Welcome —
    because *which rows exist* is the whole feature, and two copies of that
    decision would be two answers to it within a release or two.
    """
    from src.start_screen import StartScreen
    from src import saves

    last_path = saves.last_design()
    last_name = ""
    if last_path:
        entry = saves.describe(last_path)
        last_name = "" if entry.get("error") else entry["name"]
    recover_name = _pending_recovery_name()

    dlg = StartScreen(parent, last_design=last_name, recover=recover_name,
                      saves_count=len(saves.list_saves()),
                      species_count=_species_count(),
                      bloom_line=_bloom_line(), version=_version_line(),
                      hidden=not should_show_welcome())
    result = dlg.exec()
    # Written every time, not only when ticked. A checkbox that can be turned
    # on and never off is a trapdoor, and this app shipped one: the only way
    # back was hand-editing PermaDesign.conf. Closing the screen is still not
    # an answer to it — that means "I'll start from the blank map".
    _settings().setValue(START_SCREEN_OFF_KEY, dlg.suppressed())
    if result != QDialog.DialogCode.Accepted:
        return ""
    return dlg.choice()


#: Rows that put a project on the map, so they must wait until it can render.
#: Everything else — the directory, a reference ecosystem, the update check —
#: runs the moment the window exists. Kept as a set rather than an ``if`` chain
#: so a new row's author has to decide which it is.
_NEEDS_MAP = frozenset({"recover", "continue", "open", "example"})


def act_on_start_choice(main, choice: str) -> None:
    """Carry out a start-menu choice, once the map can render.

    Deferred to ``map_ready`` rather than run at once: opening a design calls
    ``render_project_to_map``, and a render into a WebEngine view that has not
    finished loading draws nothing. The crash-recovery prompt has been wired
    this way since it shipped, for the same reason.

    Two things the deferral costs, both paid for here:

    * **The window can be gone by then** — rare in normal use, routine in the
      test suite, which builds a probe window and deletes it immediately.
      Touching a deleted C++ object raises RuntimeError *inside a Qt slot*, and
      an exception escaping a Qt slot calls ``qFatal()``: a process abort. On
      Windows that killed a whole test run before it could print its summary
      (V2.38). ``qt_safety.is_alive`` is the check that actually answers it —
      a plain try/except misses the case where C++ ownership deleted the object
      without telling Python.
    * **``map_ready`` fires again on every page load.** Without the disconnect
      below, reloading the map would re-open the example, or re-open the last
      design over whatever the user had done since.

    Only the rows that *draw a project* wait. Opening the plant directory or a
    reference ecosystem touches no map, and making those sit through a Leaflet
    load would be a delay bought for nothing.
    """
    if not choice:
        return
    if choice not in _NEEDS_MAP:
        _dispatch(main, choice)
        return

    def _go():
        from src.qt_safety import is_alive
        try:
            main.map_widget.bridge.map_ready.disconnect(_go)
        except Exception:                                  # noqa: BLE001
            pass
        if is_alive(main):
            _dispatch(main, choice)

    try:
        main.map_widget.bridge.map_ready.connect(_go)
    except Exception:                                      # noqa: BLE001
        # No bridge to wait on (headless, or a test double). Fall back to the
        # timer rather than dropping the user's choice on the floor.
        QTimer.singleShot(_WELCOME_DELAY_MS, _go)


def _pending_recovery_name() -> str:
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
    """Whether a previous session left unsaved work behind.

    Runs the legacy-location migration first. Since V2.40 the start menu is the
    **first** thing in the process to ask this question — ahead of the
    MainWindow, which is where the migration used to be triggered — so asking it
    without migrating would mean a user upgrading from before V2.39 is offered
    no Recover row on precisely the launch that needs one. The migration is
    copy-verify-unlink and a no-op once done.
    """
    try:
        from src.controllers.persistence import (autosave_path,
                                                 migrate_legacy_autosave)
        migrate_legacy_autosave()
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
    _dispatch(main, _open_menu(main))


def _dispatch(main, choice: str) -> None:
    """Act on a start-screen choice. Shared by the Help menu and the launch
    sequence, so the two can never drift about what a row does."""
    if not choice:
        return
    from src.start_screen import (BLOOM, CONTINUE, DIRECTORY, EXAMPLE, NEW,
                                  OPEN, RECOVER, REFERENCE, UPDATE)
    if choice == RECOVER:
        # Tell the controller this is the screen asking, so its "the screen
        # will handle it" guard stands aside.
        main._persistence._recovery_from_menu = True
        main._persistence.maybe_offer_autosave_recovery()
    elif choice == CONTINUE:
        _open_last_design(main)
    elif choice == OPEN:
        main._on_open()
    elif choice == EXAMPLE:
        open_example(main)
    elif choice in (DIRECTORY, BLOOM):
        _open_directory(main, bloom=(choice == BLOOM))
    elif choice == REFERENCE:
        _open_reference(main)
    elif choice == UPDATE:
        _safely(lambda: main._on_check_for_updates())
    elif choice == NEW:
        # Nothing to build — just point at step one and put the cursor where
        # the user has to act.
        _safely(lambda: (main._side_tabs.setCurrentWidget(main.site_panel),
                         main.site_panel.focus_address_search()))
    refresh(main)


def _safely(fn) -> None:
    """Run a dispatch action without letting it take the launch with it. A row
    that fails should leave the user on a working blank map, not on a
    traceback."""
    try:
        fn()
    except Exception:                                      # noqa: BLE001
        pass


def _open_directory(main, *, bloom: bool = False) -> None:
    """Open the plant directory (F90), optionally already filtered to what is
    flowering this month — which is what the start screen's in-bloom line is a
    link to."""
    from src.plant_directory_window import open_plant_directory
    criteria = None
    if bloom:
        import datetime
        criteria = {"bloom_months": [str(datetime.date.today().month)]}
    _safely(lambda: open_plant_directory(main, criteria))


def _open_reference(main) -> None:
    from src.reference_ecosystem_window import open_reference_ecosystem
    _safely(lambda: open_reference_ecosystem(main))


def _species_count() -> int:
    """How big the catalogue is, for the directory row. Silent on failure: the
    row then reads "look up any native species", which is true either way."""
    try:
        from src.plant_directory import catalogue_size
        return catalogue_size()
    except Exception:                                      # noqa: BLE001
        return 0


def _bloom_line() -> str:
    """The footer's living number. Never raises and returns ``""`` when it has
    nothing to say — a start screen must not fail to open because a count
    could not be computed."""
    try:
        from src.plant_directory import bloom_line, in_bloom_now
        return bloom_line(in_bloom_now(ecoregion=_last_ecoregion()))
    except Exception:                                      # noqa: BLE001
        return ""


def _last_ecoregion() -> str:
    """The ecoregion of the design you were last in, if any.

    The start screen runs before any project is open, so this is the only
    location it can honestly claim. With nothing here the bloom line says
    "across the catalogue" rather than implying a regional count (P9).
    """
    try:
        from src import saves
        from src.project import load_project
        path = saves.last_design()
        if not path:
            return ""
        props = (load_project(path).get("properties") or {})
        regions = (props.get("site_config") or {}).get("ecoregion") or ""
        if isinstance(regions, (list, tuple)):
            return regions[0] if regions else ""
        return str(regions).split(",")[0].strip()
    except Exception:                                      # noqa: BLE001
        return ""


def _version_line() -> str:
    """What build this is.

    A frozen build knows from its stamped ``version.txt``. A source checkout's
    version *is* its V-branch, and the only thing that can answer that is git —
    ``UpdateFlowController._current_branch_name`` asks it the same way, but
    that is a controller method and this runs before any controller exists.
    So: one short, timed-out ``rev-parse``, only on the path where the stamp is
    absent, and blank rather than a guess if anything about it fails.
    """
    try:
        from src.app_version import build_version
        stamped = build_version()
        if stamped:
            return stamped
    except Exception:                                      # noqa: BLE001
        pass
    try:
        import subprocess
        repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        out = subprocess.run(
            ["git", "-C", repo, "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True, text=True, timeout=3)
        branch = (out.stdout or "").strip().split("/")[-1]
        return branch if branch.startswith("V") else ""
    except Exception:                                      # noqa: BLE001
        return ""


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

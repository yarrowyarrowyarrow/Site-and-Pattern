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
    from PyQt6.QtWidgets import QMessageBox
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


#: What closing the start screen at launch means (S7): quit. From Help ›
#: Start Screen, closing it only closes it.
QUIT = "quit"


def choose_start_action() -> str:
    """Open the start screen **before the main window exists**, and return the
    choice (V2.40).

    Running it first, with no parent, means the first thing seen is the
    choice, and the map appears already carrying it. It needs no MainWindow:
    everything on it is read from disk (the saves folder, the last-design
    path, a surviving autosave, the catalogue's flowering months). Acting on
    the answer is :func:`act_on_start_choice`, once there is a window.

    Since V3.23: closing it returns :data:`QUIT` (S7); a screen turned off
    opens the last design, or the blank map when there is none (S8); and
    unsaved work the screen offered to restore is kept as its own design
    when another row is chosen (ST-8, S13).
    """
    if not _HAVE_QT:
        return ""
    from src.start_screen import CONTINUE, RECOVER
    if not should_show_welcome():
        from src import saves
        return CONTINUE if saves.last_design() else ""
    offered = bool(_pending_recovery_name())
    choice = _menu_loop(None, at_launch=True)
    if offered and choice not in (RECOVER, QUIT, ""):
        from src import start_flow
        start_flow.keep_passed_autosave()
    return choice


def _menu_loop(parent, *, at_launch: bool = False) -> str:
    """The start screen, plus the Learn menu behind its first door (V2.43).

    A loop rather than two calls, because **Back has to go somewhere**. The
    Learn menu is a second screen, not a dead end: closing it or pressing Back
    returns to the start screen, so a person who opens the wrong door is not
    dropped into an app they did not choose. Without the loop the only way out
    of Learn would be to quit.

    Returns the choice to act on once there is a window — which may be a
    Learn-side key (see :func:`src.app_mode.opens_main_window`, which is what
    decides whether the MainWindow is shown at all).

    *All N designs…* and *Open a file…* are answered here too (V3.37), on the
    screen's side of the map: the list and the file picker open over the
    start screen, a design picked there comes back as that design, and
    Cancel comes back to the screen. Until V3.37 they were acted on once the
    window was shown, so the map opened first and the list sat over it (the
    owner: it "opens the whole app map page which it shouldn't until the
    actual design has been selected").
    """
    from src import app_mode, learn_flow, start_flow
    from src.start_screen import ALL_DESIGNS, OPEN_FILE
    while True:
        choice = _open_menu(parent, at_launch=at_launch)
        if choice in (ALL_DESIGNS, OPEN_FILE):
            path = start_flow.choose_design(parent,
                                            listed=choice == ALL_DESIGNS)
            if path:
                return start_flow.path_choice(path)
            continue            # Cancel: back to the start screen
        if choice != app_mode.LEARN:
            return choice
        sub = learn_flow.open_learn_menu(parent)
        if sub and sub != app_mode.BACK:
            return sub
        # Back, or closed. Round again to the start screen.


def _open_menu(parent, *, at_launch: bool = False) -> str:
    """Build the screen against what is on disk, show it, and return the
    choice: ``""`` when closed from Help, :data:`QUIT` when closed at launch.

    One body for both entry points, the launch and Help › Start Screen,
    because *which rows exist* is the whole feature. Restore is offered only
    at launch: later in a session the autosave is this session's own.
    """
    from src import start_flow
    choice = start_flow.open_screen(
        parent, recover=_pending_recovery_name() if at_launch else "",
        version=_version_line(), hidden=not should_show_welcome())
    if not choice and at_launch:
        return QUIT
    return choice


#: Rows that put a project on the map, so they must wait until it can render.
#: Everything else — a reference ecosystem, the update check —
#: runs the moment the window exists. Kept as a set rather than an ``if`` chain
#: so a new row's author has to decide which it is.
_NEEDS_MAP = frozenset({"recover", "continue", "example", "new_yard",
                        "open_path", "all_designs", "open_file"})


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
    if not choice or choice == QUIT:
        return
    from src.start_flow import split_choice
    if split_choice(choice)[0] not in _NEEDS_MAP:
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

    # The map has usually loaded already: the window is built behind the start
    # screen, and map_ready fires once per page load, while the screen is still
    # up. Waiting for it then waited forever, and Continue, Open a design, See
    # a finished design and Recover did nothing (F197, V3.04).
    if _map_is_ready(main):
        QTimer.singleShot(0, _go)
        return
    try:
        main.map_widget.bridge.map_ready.connect(_go)
    except Exception:                                      # noqa: BLE001
        # No bridge to wait on (headless, or a test double). Fall back to the
        # timer rather than dropping the user's choice on the floor.
        QTimer.singleShot(_WELCOME_DELAY_MS, _go)


def _map_is_ready(main) -> bool:
    """Whether the window's map has already said ``map_ready``. False for a
    window that is gone or has no map: asking a deleted widget for an attribute
    raises ``RuntimeError``, which ``getattr``'s default does not catch."""
    from src.qt_safety import is_alive
    if not is_alive(main):
        return False
    try:
        return bool(main.map_widget.is_ready)
    except Exception:                                      # noqa: BLE001
        return False


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
    except Exception:                                      # noqa: BLE001
        from src import plain_messages
        plain_messages.tell_open_failed(main, path)


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
    _dispatch(main, _menu_loop(main))


def _dispatch(main, choice: str) -> None:
    """Act on a start-screen choice. Shared by the Help menu and the launch
    sequence, so the two can never drift about what a row does."""
    if not choice or choice == QUIT:
        return
    from src import start_flow
    from src.app_mode import STUDIO
    from src.start_screen import CONTINUE, EXAMPLE, RECOVER, REFERENCE, UPDATE
    if start_flow.dispatch(main, choice):
        pass            # NEW_YARD, OPEN_PATH, ALL_DESIGNS, OPEN_FILE (V3.23)
    elif choice == RECOVER:
        # Tell the controller this is the screen asking, so its "the screen
        # will handle it" guard stands aside.
        main._persistence._recovery_from_menu = True
        main._persistence.maybe_offer_autosave_recovery()
    elif choice == CONTINUE:
        _open_last_design(main)
    elif choice == EXAMPLE:
        open_example(main)
    elif choice == REFERENCE:
        _open_reference(main)
    elif choice == STUDIO:
        from src import learn_flow
        learn_flow.open_studio(main)
    elif choice == UPDATE:
        _safely(lambda: main._on_check_for_updates(), "The update check")
    refresh(main)


def _safely(fn, what: str) -> None:
    """Run a dispatch action without letting it take the launch with it. A row
    that fails should leave the user on a working blank map, not on a
    traceback, and it says so (V3.18, ST-3: a bare ``pass`` here and in
    ``learn_flow`` hid a dead door for a release). ``what`` names the thing
    in the message's own words ("The address search")."""
    try:
        fn()
    except Exception:                                      # noqa: BLE001
        from src import slot_errors
        slot_errors.report(what)


def _open_reference(main) -> None:
    from src.reference_ecosystem_window import open_reference_ecosystem
    _safely(lambda: open_reference_ecosystem(main), "Walk a Wild Landscape")


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
            capture_output=True, text=True, timeout=3, encoding="utf-8")
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

    lat, lng = example_position(main)

    from src import saves
    previous = saves.last_design()
    try:
        project, missing = build_example_project(lat, lng)
        path = example_path()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        save_project(project, path)
        main._load_from_path(path)
        # A copy (V3.23, ST-9): Save writes a new design to the saves folder,
        # and the example is not "your" last design, so it never lists on the
        # start screen as one and opens pristine every time.
        main._project_path = None
        saves.remember_last_design(previous)
    except Exception as exc:                               # noqa: BLE001
        QMessageBox.critical(main, "Example unavailable",
                             f"Could not build the example design:\n{exc}")
        return

    # Unmodified until changed; a Save then goes to Your designs.
    note = ("Opened the example yard. Changes you save go to Your designs; "
            "Site › Notes says what to try.")
    if missing:
        # Never quietly ship a thinner design than the one described (P9).
        note += (f"  ({len(missing)} species in the example aren't in this "
                 f"catalogue: {', '.join(missing[:3])}"
                 + ("…" if len(missing) > 3 else "") + ")")
    main.statusBar().showMessage(note, 15000)
    refresh(main)


def example_position(main) -> tuple:
    """Where the example opens: ``(None, None)`` for its own place, else the
    person's pin. Its own place when the example was made from a real lot
    (V3.38, F254: its house and walk are that lot's), and when the pin is
    outside every pack, since its plants are the pack's and would otherwise
    be planted in Toronto (V3.25, ED-8)."""
    from src import region
    from src.onboarding import EXAMPLE_OWN_PLACE
    if EXAMPLE_OWN_PLACE:
        return None, None
    try:
        coords = main.site_panel.current_coords()
    except Exception:                                      # noqa: BLE001
        coords = None
    if not coords or region.at(*coords) is None:
        return None, None
    return coords


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
    """Re-read the project and update the step bar.

    Called after anything that could complete a step (pin, boundary, plant,
    project load, undo). Never raises — onboarding guidance must not be able
    to break the app it is trying to explain. Until V3.19 it also wrote the
    step into a box at the top of Site Info, under the strip saying the same
    thing (R26, QF-12); the strip is the one place it is said now.
    """
    try:
        from src.onboarding import first_step, steps_progress
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
            # Opens Site › Site Info whatever page is in front, then the box.
            main.site_panel.focus_address_search()
        elif key == "boundary":
            main.toolbar.activate_boundary_tool()
        elif key == "plants":
            from src.keyboard_help import show_panel
            show_panel(main.plant_panel)
    except Exception:                                      # noqa: BLE001
        pass

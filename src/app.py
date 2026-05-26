"""
app.py — Main application window for PermaDesign.

Layout
------
  ┌─────────────────────────────────────────┐
  │  Menu bar                               │
  │  Toolbar                                │
  ├──────────────────────┬──────────────────┤
  │                      │                  │
  │   MapWidget  (70%)   │  PlantPanel(30%) │
  │                      │                  │
  ├──────────────────────┴──────────────────┤
  │  Status bar  (coords · zone · mode)     │
  └─────────────────────────────────────────┘
"""

import json
import os
import sys
from datetime import datetime
from typing import Optional

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QSplitter,
    QStatusBar, QLabel, QMessageBox, QFileDialog, QSizePolicy,
    QInputDialog, QTabWidget,
)
from PyQt6.QtCore import Qt, QTimer, QThread, QEvent
from PyQt6.QtGui import QKeySequence, QShortcut

from src.map_widget       import MapWidget
from src.plant_panel      import PlantPanel, OnThisDesignPanel
from src.polyculture_panel      import PolyculturePanel
from src.structure_panel  import StructurePanel
from src.analysis_panel   import AnalysisPanel
from src.planning_panel   import PlanningPanel
from src.site_panel       import SitePanel
from src.toolbar          import MainToolbar
from src.climate          import get_zone, zone_label
from src.settings         import SettingsDialog, get_api_keys
from src.collapsible_panel import CollapsibleSidebar
import src.project as project_io


# Marker colour tables for plant-community members.
#
# Vegetation layer is the primary signal — when a member has a layer set
# we colour by that so the canopy structure reads at a glance on the
# map. Function colours are used only when a member has no layer (i.e.
# functional-only roles like "windbreak" or "nitrogen_fixer"). Legacy
# single-value `role` data falls through to either table.
_LAYER_COLORS = {
    'overstory':           '#1b5e20',
    'understory':          '#388e3c',
    'shrub_layer':         '#4a8b3a',
    'groundcover':         '#66bb6a',
    'herbaceous':          '#9ccc65',
    'vine':                '#7cb342',
    'root':                '#8d6e63',
}

_FUNCTION_COLORS = {
    'nitrogen_fixer':      '#43a047',
    'soil_builder':        '#2e7d32',
    'pest_deterrent':      '#7cb342',
    'pollinator':          '#aed581',
    'windbreak':           '#558b2f',
}

# Legacy aliases mapped through to the new tables so projects saved
# before the role rename still render.
_LEGACY_ROLE_ALIASES = {
    'canopy':              ('overstory',      'layer'),
    'dynamic_accumulator': ('soil_builder',   'function'),
    'pest_repellent':      ('pest_deterrent', 'function'),
}

_OTHER_COLOR = '#81c784'


def _member_color(member: dict) -> str:
    """Pick a marker colour for a polyculture member.

    Resolution order:
      1. Explicit `layer` → _LAYER_COLORS.
      2. First entry in `functions` → _FUNCTION_COLORS.
      3. Legacy single `role` (with alias mapping) → either table.
      4. Fallback to _OTHER_COLOR.
    """
    layer = (member.get('layer') or '').strip().lower()
    if layer in _LAYER_COLORS:
        return _LAYER_COLORS[layer]
    funcs = member.get('functions') or []
    if isinstance(funcs, list) and funcs:
        f0 = str(funcs[0]).strip().lower()
        if f0 in _FUNCTION_COLORS:
            return _FUNCTION_COLORS[f0]
    role = (member.get('role') or '').strip().lower()
    if role in _LEGACY_ROLE_ALIASES:
        canonical, kind = _LEGACY_ROLE_ALIASES[role]
        if kind == 'layer':
            return _LAYER_COLORS.get(canonical, _OTHER_COLOR)
        return _FUNCTION_COLORS.get(canonical, _OTHER_COLOR)
    if role in _LAYER_COLORS:
        return _LAYER_COLORS[role]
    if role in _FUNCTION_COLORS:
        return _FUNCTION_COLORS[role]
    return _OTHER_COLOR


# Back-compat shim — older code paths still reference _ROLE_COLORS by
# name. Kept as a flat lookup that covers the union of layer + function
# colours plus the legacy aliases.
_ROLE_COLORS = {
    **_LAYER_COLORS,
    **_FUNCTION_COLORS,
    'canopy':              _LAYER_COLORS['overstory'],
    'dynamic_accumulator': _FUNCTION_COLORS['soil_builder'],
    'pest_repellent':      _FUNCTION_COLORS['pest_deterrent'],
    'other':               _OTHER_COLOR,
}


def _init_database():
    """Bootstrap the plant database; show a warning on failure (don't crash)."""
    try:
        from src.db.plants import init_db
        init_db()
    except Exception as exc:
        from PyQt6.QtWidgets import QMessageBox
        QMessageBox.warning(
            None, "Database Warning",
            f"Could not initialise the plant database:\n{exc}\n\n"
            "The plant panel will be empty. "
            "Try running:  python -m src.db.seed_data"
        )


class MainWindow(QMainWindow):

    AUTOSAVE_INTERVAL_MS = 5 * 60 * 1000   # 5 minutes

    def __init__(self):
        super().__init__()
        _init_database()
        self.setWindowTitle("PermaDesign — Native Habitat Designer")
        self.resize(1400, 860)
        self.setMinimumSize(900, 600)

        # Project state
        self._project      = project_io.new_project()
        self._project_path = None        # path when saved to file
        self._modified     = False
        self._current_zone = None
        self._current_mode = 'none'

        # Placed plants list: [{plant_id, common_name, lat, lng}, ...]
        self._placed_plants = []

        # Undo/redo stacks
        self._undo_stack: list[dict] = []   # each entry: {action, data}
        self._redo_stack: list[dict] = []
        self._max_undo = 50

        # Pending anchor-mode configs (set when entering anchor mode, cleared after render)
        self._pending_sun_config:    dict | None = None
        self._pending_sun_anchor:    tuple | None = None
        self._pending_sector_config: dict | None = None
        # Community-pattern stash: when set, _on_pattern_placed expands
        # each anchor position into one full community (instead of one
        # plant). Set by _enter_polyculture_pattern_mode, cleared on
        # mode exit.
        self._pending_community_pattern: dict | None = None
        # Same idea for the community-mix case (Communities tab's ratio
        # mix of multiple plant communities).
        self._pending_community_pattern_mix: list[dict] | None = None

        # Edmonton offline download thread/worker (None when idle)
        self._dl_thread: Optional[QThread] = None
        self._dl_worker = None

        self._build_ui()
        self._connect_signals()
        self._start_autosave()
        self._load_api_keys()

    # ── UI construction ───────────────────────────────────────────────────────

    def _build_ui(self):
        # Toolbar — Draw row on top, Layers row stacked below it.
        # NOTE: the toolbars used to be attached to QMainWindow's toolbar
        # area (above the central widget). They now live inside the left
        # column of the central splitter so the right-hand side panel can
        # extend full-height from just below the menu bar to the status
        # bar — see _build_central_layout below.
        self.toolbar = MainToolbar(self)

        # Central area
        self.map_widget      = MapWidget(self)
        self.site_panel      = SitePanel(self)
        # Wire so the address finder can bias its Nominatim query
        # against the map's current view centre.
        self.site_panel.attach_map_widget(self.map_widget)
        self.plant_panel     = PlantPanel(self)
        self.polyculture_panel     = PolyculturePanel(self)
        # Third sibling inner tab — displays Plants / Communities / Stats
        # for the current design. Driven by _sync_planning_panel + a
        # placed_counts_changed signal from PlantPanel.
        self.on_this_design = OnThisDesignPanel()
        self.structure_panel = StructurePanel(self)
        self.analysis_panel  = AnalysisPanel(self)
        self.planning_panel  = PlanningPanel(self)

        # Tabbed side panel — five top-level tabs (Site, Plants, Structures,
        # Analysis, Planning). The Polyculture library lives under an inner
        # tab inside "Plants".
        self._plant_poly_tab = self._build_plants_polycultures_tab()

        self._side_tabs = QTabWidget()
        self._side_tabs.setDocumentMode(False)
        self._side_tabs.addTab(self.site_panel, "Site")
        self._side_tabs.addTab(self._plant_poly_tab, "Plants")
        self._side_tabs.addTab(self.structure_panel, "Structures")
        self._side_tabs.addTab(self.analysis_panel, "Analysis")
        self._side_tabs.addTab(self.planning_panel, "Planning")
        # Side panel needs to be wide enough that all five tab labels can
        # render in full ("Structures" is the widest at ~11px font). 260px
        # is the empirical minimum; below that the tab bar truncates to
        # "S..." even with elide off, because tabs share width equally
        # when setExpanding(True).
        self._side_tabs.setMinimumWidth(260)
        self._side_tabs.setMaximumWidth(480)
        # Show every label in full: turn off scroll-button fallback, turn
        # off ellipsis truncation, and let tabs grow to fit their content
        # instead of squeezing into an equal share.
        self._side_tabs.tabBar().setUsesScrollButtons(False)
        self._side_tabs.tabBar().setElideMode(Qt.TextElideMode.ElideNone)
        self._side_tabs.tabBar().setExpanding(False)
        # Tab styling — selected tab is a bright-green pill so the active
        # panel is unmistakable; padding/min-width are sized so all five
        # labels render fully without ellipsis at the panel's minimum
        # width.
        self._side_tabs.setStyleSheet(
            "QTabWidget::pane { border: 1px solid #2e4a2e; "
            "background: #1e2a1e; top: -1px; }"
            "QTabBar { qproperty-drawBase: 0; background: #122012; }"
            "QTabBar::tab { background: #1a2a1a; color: #90a4ae; "
            "padding: 5px 8px; margin-right: 1px; "
            "border: 1px solid #2e4a2e; border-bottom: none; "
            "border-top-left-radius: 4px; border-top-right-radius: 4px; "
            "font-size: 11px; min-width: 44px; }"
            "QTabBar::tab:hover { background: #284028; color: #c8e6c9; }"
            "QTabBar::tab:selected { background: #2e7d32; color: #ffffff; "
            "font-weight: bold; border: 1px solid #66bb6a; "
            "border-bottom: 2px solid #66bb6a; }"
            "QTabBar::tab:!selected { margin-top: 2px; }"
            "QWidget { background-color: #1e2a1e; color: #c8e6c9; }"
        )

        # Wrap in a CollapsibleSidebar so the entire side panel can be
        # collapsed to a thin chevron strip — replaces the long-standing
        # workaround of "minimize the Design panel" via the splitter.
        self._side_wrapper = CollapsibleSidebar(
            "Side Panel", panel_id="main_sidebar", expanded=True
        )
        self._side_wrapper.set_content(self._side_tabs)

        # Build the left column: Draw toolbar + View toolbar + map.
        # The toolbars used to live in QMainWindow's toolbar area above
        # the central widget; placing them inside the splitter's left
        # column instead lets the right-hand side panel span the full
        # vertical extent (just below the menu bar to just above the
        # status bar) — see Phase 1 of the panel refactor.
        left_col = QWidget(self)
        left_layout = QVBoxLayout(left_col)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(0)
        self.toolbar.attach_to_layout(left_layout)
        left_layout.addWidget(self.map_widget, 1)

        self._splitter = QSplitter(Qt.Orientation.Horizontal)
        self._splitter.addWidget(left_col)
        self._splitter.addWidget(self._side_wrapper)

        # 70 / 30 split
        self._splitter.setSizes([700, 300])
        self._splitter.setStretchFactor(0, 7)
        self._splitter.setStretchFactor(1, 3)

        self.setCentralWidget(self._splitter)

        # Status bar labels
        self._sb_coords  = QLabel("Lat: — , Lng: —")
        self._sb_zone    = QLabel("Zone: —")
        self._sb_mode    = QLabel("Mode: Ready")

        self._sb_coords.setMinimumWidth(220)
        self._sb_zone.setMinimumWidth(100)

        self._sb_tasks = QLabel("")
        self._sb_tasks.setStyleSheet("color: #a5d6a7; font-size: 11px;")
        self._load_seasonal_tasks()

        sb = QStatusBar(self)
        sb.addWidget(self._sb_coords)
        sb.addWidget(_vsep())
        sb.addWidget(self._sb_zone)
        sb.addWidget(_vsep())
        sb.addWidget(self._sb_tasks, 1)
        sb.addPermanentWidget(self._sb_mode)
        self.setStatusBar(sb)

        # Menu bar
        self._build_menu()

        # Recovery hatch: if the saved state restored the sidebar collapsed,
        # the chevron strip on the right edge can be missed entirely. Force
        # the panel open on every launch so users always boot with the panel
        # visible; they can collapse it again from the chevron if they want.
        self._side_wrapper.set_expanded(True, persist=False)
        self._act_show_sidebar.setChecked(True)
        self._side_wrapper.toggled.connect(self._act_show_sidebar.setChecked)

        # Window style
        self.setStyleSheet(_APP_STYLE)

    def _build_plants_polycultures_tab(self) -> QWidget:
        """Build the 'Plants' tab.

        Houses the plant browser/placer and the saved-polyculture library
        under a compact inner tab strip so users can move between the two
        without leaving this outer tab.

        The PlantPanel already owns the inline polyculture-mix builder
        used to place mixes on the map; the PolyculturePanel is for
        editing the saved library of multi-plant templates.
        """
        wrap = QWidget()
        v = QVBoxLayout(wrap)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)

        inner = QTabWidget(wrap)
        inner.setDocumentMode(True)
        inner.tabBar().setUsesScrollButtons(False)
        inner.tabBar().setExpanding(True)
        inner.setStyleSheet(
            "QTabWidget::pane { border: none; background: #1e2a1e; }"
            "QTabBar::tab { background: #15251a; color: #90a4ae; "
            "padding: 4px 10px; font-size: 11px; "
            "border-bottom: 2px solid transparent; }"
            "QTabBar::tab:selected { color: #a5d6a7; "
            "border-bottom: 2px solid #66bb6a; }"
            "QTabBar::tab:hover { color: #c8e6c9; }"
        )
        inner.addTab(self.plant_panel, "Plants")
        inner.addTab(self.polyculture_panel, "Plant Communities")
        inner.addTab(self.on_this_design, "On This Design")
        v.addWidget(inner)
        return wrap

    def _on_toggle_sidebar(self, checked: bool):
        """View → Show Side Panel (Ctrl+\\). Mirrors the chevron click."""
        self._side_wrapper.set_expanded(checked)
        if checked:
            # Make sure the splitter actually allocates room for the panel —
            # if it was collapsed via drag, re-expanding the wrapper alone
            # leaves zero width.
            sizes = self._splitter.sizes()
            if len(sizes) >= 2 and sizes[1] < 100:
                total = sum(sizes) or 1000
                self._splitter.setSizes([int(total * 0.7), int(total * 0.3)])

    # ── Help → About / Version / Switch (V1.37) ──────────────────────────────

    def _repo_path(self):
        """Absolute path to the project root (where .git lives for
        source installs). Returns None if the running binary isn't
        inside a git repo (e.g. PyInstaller .exe)."""
        import os
        here = os.path.dirname(os.path.abspath(__file__))
        # src/app.py → repo root is one level up
        candidate = os.path.dirname(here)
        if os.path.isdir(os.path.join(candidate, ".git")):
            return candidate
        return None

    def _current_branch_name(self):
        """Return the current git branch name, or None for frozen /
        non-git installs. Cached only across the call site that built
        the menu label."""
        repo = self._repo_path()
        if not repo:
            return None
        import subprocess
        try:
            res = subprocess.run(
                ["git", "-C", repo, "rev-parse", "--abbrev-ref", "HEAD"],
                capture_output=True, text=True, timeout=3,
            )
            if res.returncode == 0:
                return res.stdout.strip() or None
        except Exception:
            pass
        return None

    def _on_about(self):
        """Show a small About dialog: current V<major>.<minor>, git
        commit, schema version, and a link to the releases page."""
        repo = self._repo_path()
        branch = self._current_branch_name() or "?"
        commit = "?"
        if repo:
            import subprocess
            try:
                res = subprocess.run(
                    ["git", "-C", repo, "rev-parse", "--short", "HEAD"],
                    capture_output=True, text=True, timeout=3,
                )
                if res.returncode == 0:
                    commit = res.stdout.strip() or "?"
            except Exception:
                pass
        try:
            from src.db.plants import _SCHEMA_VERSION as schema_v
        except Exception:
            schema_v = "?"
        from src.version_branch import parse_version_branch
        is_release = parse_version_branch(branch) is not None
        kind_note = "" if is_release else (
            "\n\nYou're on a development branch — the V*.* branch "
            "convention isn't being followed. Use Help → Switch to a "
            "specific version to move to a release branch."
        )
        QMessageBox.information(
            self, "About PermaDesign",
            f"<b>PermaDesign</b><br>"
            f"Branch: <b>{branch}</b><br>"
            f"Commit: {commit}<br>"
            f"Schema version: v{schema_v}<br><br>"
            f"Native-plant landscape designer for Alberta and the "
            f"Canadian prairies."
            + kind_note
        )

    def _on_pick_version(self):
        """Let the user pick any published V<major>.<minor> branch and
        switch the checkout to it. Useful for rolling back to an older
        release or jumping ahead. Frozen installs get redirected to
        the releases page."""
        # Frozen / non-git install — no checkout to switch.
        if getattr(sys, "frozen", False):
            self._open_releases_page()
            return
        repo = self._repo_path()
        if not repo:
            QMessageBox.information(
                self, "Switch version",
                "This install isn't a git checkout — there's nothing to "
                "switch. Visit the releases page to download a specific "
                "installer."
            )
            self._open_releases_page()
            return

        import subprocess

        def _git(*args, timeout=10):
            return subprocess.run(
                ["git", "-C", repo, *args],
                capture_output=True, text=True, timeout=timeout, check=False,
            )

        # Fetch so we see any branches published since launch.
        self.statusBar().showMessage("Fetching version list…", 2000)
        fetch = _git("fetch", "--prune", "--quiet")
        if fetch.returncode != 0:
            QMessageBox.warning(
                self, "Switch version",
                "Couldn't reach the git remote (check your network).\n\n"
                f"{fetch.stderr.strip()}"
            )
            return

        # Collect every V<major>.<minor> branch — remote + local — sorted
        # newest first.
        from src.version_branch import parse_version_branch
        names: set[str] = set()
        for ref_glob in ("refs/remotes/origin/", "refs/heads/"):
            res = _git("for-each-ref", "--format=%(refname:short)", ref_glob)
            if res.returncode != 0:
                continue
            for line in res.stdout.splitlines():
                short = line.strip()
                name = short[len("origin/"):] if short.startswith("origin/") else short
                if parse_version_branch(name):
                    names.add(name)
        if not names:
            QMessageBox.information(
                self, "Switch version",
                "No V<major>.<minor> branches found on this remote."
            )
            return
        ordered = sorted(
            names,
            key=lambda n: parse_version_branch(n),
            reverse=True,
        )
        current = self._current_branch_name() or "?"

        # Build the list dialog. Pre-select the current branch if
        # present in the list.
        from PyQt6.QtWidgets import QInputDialog
        labels = [
            f"{n}  (current)" if n == current else n
            for n in ordered
        ]
        try:
            preselect = ordered.index(current)
        except ValueError:
            preselect = 0
        choice, ok = QInputDialog.getItem(
            self, "Switch to a specific version",
            "Pick a release branch. The app will check out the chosen "
            "branch and pull any new commits. You'll need to restart "
            "the app to load the new code.",
            labels, current=preselect, editable=False,
        )
        if not ok or not choice:
            return
        target = ordered[labels.index(choice)]
        if target == current:
            QMessageBox.information(
                self, "Switch version",
                f"You're already on {target}."
            )
            return

        # Reuse the existing dirty-tree handling + offer-branch-switch
        # path so behaviour matches Check for Updates exactly.
        status = _git("status", "--porcelain")
        stash_label = None
        if status.returncode == 0 and status.stdout.strip():
            choice2 = QMessageBox.question(
                self, "Uncommitted changes",
                "Your working tree has uncommitted changes. Stash them "
                f"before switching to {target}? They'll be restored on "
                f"the new branch via `git stash pop`.",
                QMessageBox.StandardButton.Yes
                | QMessageBox.StandardButton.No
                | QMessageBox.StandardButton.Cancel,
            )
            if choice2 == QMessageBox.StandardButton.Cancel:
                return
            if choice2 == QMessageBox.StandardButton.Yes:
                stash_label = f"PermaDesign auto-stash before switch to {target}"
                stash = _git("stash", "push", "-u", "-m", stash_label)
                if stash.returncode != 0:
                    QMessageBox.warning(
                        self, "Stash failed",
                        f"Couldn't stash local changes:\n\n{stash.stderr.strip()}"
                    )
                    return

        self._offer_branch_switch(
            _git,
            target=target,
            current=current,
            stash_to_restore=stash_label,
        )

    # ── Help → Check for Updates ──────────────────────────────────────────────
    #
    # Behaves differently depending on how the user is running the app:
    #
    #   * Source install (git checkout, `python main.py`) — runs
    #     `git fetch` + `git status` to detect upstream commits, then
    #     offers a fast-forward `git pull`. If the working tree is dirty,
    #     gives the user three options: stash & update (safe, recoverable
    #     via `git stash pop`), discard & update (destructive, with a
    #     second confirm), or cancel. Refuses to auto-merge on divergence.
    #
    #   * Frozen install (PyInstaller .exe used by friends) — git isn't
    #     available, so we open the GitHub releases page in the default
    #     browser and let the user download the next installer.

    _REPO_RELEASES_URL = "https://github.com/yarrowyarrowyarrow/PermaDesign/releases"

    def _on_check_for_updates(self):
        import os, subprocess, sys

        # Frozen build: no git, just open releases page.
        if getattr(sys, "frozen", False):
            self._open_releases_page()
            return

        # Detect git root by walking up from this file
        here = os.path.dirname(os.path.abspath(__file__))
        repo_root = os.path.dirname(here)
        if not os.path.isdir(os.path.join(repo_root, ".git")):
            QMessageBox.information(
                self, "Check for Updates",
                "Not a git checkout — opening the releases page in your browser "
                "so you can download the latest installer manually."
            )
            self._open_releases_page()
            return

        def _git(*args, timeout=30):
            return subprocess.run(
                ["git", "-C", repo_root, *args],
                capture_output=True, text=True, timeout=timeout, check=False,
            )

        status = _git("status", "--porcelain")
        if status.returncode != 0:
            QMessageBox.warning(
                self, "Check for Updates",
                "Couldn't run git. Make sure git is installed and on your PATH.\n\n"
                f"{status.stderr.strip() or status.stdout.strip()}"
            )
            return

        if status.stdout.strip():
            # Dirty working tree — give the user three explicit choices
            # instead of just refusing.
            dirty_files = [
                line[3:] for line in status.stdout.strip().splitlines()[:6]
            ]
            preview = "\n".join(f"  · {f}" for f in dirty_files)
            if len(status.stdout.strip().splitlines()) > 6:
                preview += f"\n  · …and more"

            box = QMessageBox(self)
            box.setIcon(QMessageBox.Icon.Warning)
            box.setWindowTitle("Local changes detected")
            box.setText(
                "You have uncommitted local changes — pulling now could "
                "clobber them. How would you like to proceed?"
            )
            box.setInformativeText(
                f"Changed files:\n{preview}\n\n"
                "• Stash & update — safest. Sets your changes aside in a "
                "git stash, pulls, then restores them. If the restore "
                "conflicts, the stash stays put so you can recover manually.\n\n"
                "• Discard & update — destructive. Throws away all "
                "uncommitted changes, then pulls. Requires a second confirm."
            )
            btn_stash   = box.addButton("Stash && update",
                                        QMessageBox.ButtonRole.AcceptRole)
            btn_discard = box.addButton("Discard && update",
                                        QMessageBox.ButtonRole.DestructiveRole)
            btn_cancel  = box.addButton(QMessageBox.StandardButton.Cancel)
            box.setDefaultButton(btn_stash)
            box.exec()

            choice = box.clickedButton()
            if choice is btn_cancel or choice is None:
                return
            if choice is btn_discard:
                confirm = QMessageBox.question(
                    self, "Discard all local changes?",
                    "This will permanently delete every uncommitted change "
                    "in your working tree (tracked-file edits will be "
                    "reset to the last commit). Untracked files are left "
                    "alone. Continue?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No,
                )
                if confirm != QMessageBox.StandardButton.Yes:
                    return
                reset = _git("reset", "--hard", "HEAD")
                if reset.returncode != 0:
                    QMessageBox.warning(
                        self, "Discard failed",
                        "git reset --hard HEAD failed:\n\n"
                        + (reset.stderr.strip() or reset.stdout.strip())
                    )
                    return
                self._run_update_flow(_git, stash_to_restore=None)
                return

            # Stash & update
            import time
            stash_label = f"permadesign-auto-{int(time.time())}"
            stash = _git("stash", "push", "--include-untracked",
                         "-m", stash_label)
            if stash.returncode != 0:
                QMessageBox.warning(
                    self, "Stash failed",
                    "git stash failed:\n\n"
                    + (stash.stderr.strip() or stash.stdout.strip())
                )
                return
            self._run_update_flow(_git, stash_to_restore=stash_label)
            return

        # Clean working tree — proceed straight to the update flow.
        self._run_update_flow(_git, stash_to_restore=None)

    def _run_update_flow(self, git_runner, *, stash_to_restore):
        """Shared update flow: fetch → ahead/behind check → pull → optional
        stash-pop → restart prompt. `git_runner` is the closure `_git` from
        the caller (already bound to the repo path). `stash_to_restore` is
        a stash message label (or None) — when set, we `git stash pop`
        after a successful pull and warn if the pop conflicts.

        Schema v1.32: after the fetch, also check whether origin carries a
        newer ``V<major>.<minor>`` branch than the one we're on. If so,
        prompt the user to switch to that branch instead of (or in addition
        to) updating the current one. Branch naming convention is the same
        one documented in CLAUDE.md."""
        self.statusBar().showMessage("Checking for updates…", 2000)
        # --prune drops references to branches the remote has deleted, so
        # _newest_remote_version_branch doesn't surface stale entries.
        fetch = git_runner("fetch", "--prune", "--quiet")
        if fetch.returncode != 0:
            self._maybe_restore_stash(git_runner, stash_to_restore)
            QMessageBox.warning(
                self, "Check for Updates",
                "Couldn't reach the git remote (check your network).\n\n"
                f"{fetch.stderr.strip()}"
            )
            return

        current_branch = (
            git_runner("rev-parse", "--abbrev-ref", "HEAD").stdout.strip() or "?"
        )

        # ── V<major>.<minor> auto-switch (V1.32) ──────────────────────────
        # If a newer release branch exists on origin than the one we're on,
        # offer the switch. Falls through to the standard fast-forward flow
        # when we're already on the highest V-branch or no V-branches exist.
        newest = self._newest_remote_version_branch(git_runner)
        if newest and self._is_newer_version(newest, current_branch):
            self._offer_branch_switch(
                git_runner,
                target=newest,
                current=current_branch,
                stash_to_restore=stash_to_restore,
            )
            return

        behind = git_runner("rev-list", "--count", "HEAD..@{u}")
        ahead  = git_runner("rev-list", "--count", "@{u}..HEAD")
        if behind.returncode != 0 or ahead.returncode != 0:
            self._maybe_restore_stash(git_runner, stash_to_restore)
            QMessageBox.information(
                self, "Check for Updates",
                "This branch has no configured upstream. Set one with "
                "`git branch --set-upstream-to=origin/<branch>` and try again."
            )
            return

        n_behind = int((behind.stdout or "0").strip() or 0)
        n_ahead  = int((ahead.stdout  or "0").strip() or 0)
        branch   = current_branch

        if n_behind == 0 and n_ahead == 0:
            self._maybe_restore_stash(git_runner, stash_to_restore)
            QMessageBox.information(
                self, "Check for Updates",
                f"You're up to date on branch '{branch}'."
            )
            return
        if n_behind == 0 and n_ahead > 0:
            self._maybe_restore_stash(git_runner, stash_to_restore)
            QMessageBox.information(
                self, "Check for Updates",
                f"You're {n_ahead} commit(s) ahead of the remote on '{branch}'. "
                "Nothing to pull."
            )
            return
        if n_ahead > 0 and n_behind > 0:
            self._maybe_restore_stash(git_runner, stash_to_restore)
            QMessageBox.warning(
                self, "Check for Updates",
                f"Branch '{branch}' has diverged from the remote "
                f"({n_ahead} ahead, {n_behind} behind). Resolve manually in a "
                "terminal — the app won't auto-merge."
            )
            return

        # Behind only — show recent incoming commits and offer the pull.
        log = git_runner("log", "--oneline", f"-{min(n_behind, 8)}", "HEAD..@{u}")
        recent = log.stdout.strip() or "(commit log unavailable)"
        prompt = QMessageBox.question(
            self, "Update available",
            f"Branch '{branch}' is {n_behind} commit(s) behind the remote.\n\n"
            f"Recent incoming changes:\n{recent}\n\n"
            "Pull and fast-forward now? You'll need to restart the app for "
            "code changes to take effect.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if prompt != QMessageBox.StandardButton.Yes:
            self._maybe_restore_stash(git_runner, stash_to_restore)
            return

        pull = git_runner("pull", "--ff-only")
        if pull.returncode != 0:
            self._maybe_restore_stash(git_runner, stash_to_restore)
            QMessageBox.warning(
                self, "Pull failed",
                "git pull --ff-only failed:\n\n"
                + (pull.stderr.strip() or pull.stdout.strip())
            )
            return

        # Pull succeeded. If we stashed, try to restore.
        stash_note = ""
        if stash_to_restore:
            pop = git_runner("stash", "pop")
            if pop.returncode == 0:
                stash_note = ("\n\nYour stashed local changes were restored "
                              "cleanly.")
            else:
                stash_note = (
                    "\n\nYour stash could NOT be auto-restored (likely a "
                    "merge conflict with the incoming changes). It's still "
                    f"saved as `{stash_to_restore}` — recover it with:\n"
                    "    git stash list\n"
                    "    git stash apply stash@{0}"
                )
        QMessageBox.information(
            self, "Updated",
            f"Pulled {n_behind} commit(s) from origin/{branch}.\n\n"
            "Close and relaunch the app to load the new code."
            + stash_note
        )

    def _maybe_restore_stash(self, git_runner, stash_label):
        """Best-effort stash pop on the abort/error paths so a user who hit
        Cancel mid-flow gets their working tree back. Silent on failure —
        the stash entry remains and we don't pile on additional dialogs."""
        if not stash_label:
            return
        git_runner("stash", "pop")

    # ── V<major>.<minor> branch auto-switch (V1.32) ───────────────────────────
    #
    # Convention (also documented in CLAUDE.md): release branches are named
    # ``V<major>.<minor>`` (e.g. V1.31, V1.32). Each branch contains a single
    # release's worth of work; "the latest version" is the numerically
    # highest such branch on origin. The updater treats these as the
    # authoritative release line.
    #
    # The parsing/comparison/listing helpers live in
    # ``src/version_branch.py`` (Qt-free, unit-testable). MainWindow's
    # responsibility here is only the user-facing switch dialog.

    def _newest_remote_version_branch(self, git_runner):
        from src.version_branch import newest_remote_version_branch
        return newest_remote_version_branch(git_runner)

    def _is_newer_version(self, target, current):
        from src.version_branch import is_newer_version
        return is_newer_version(target, current)

    def _offer_branch_switch(self, git_runner, *, target, current, stash_to_restore):
        """Prompt the user to switch from ``current`` to ``target`` (a remote
        V-branch). Reuses the stash carried in from
        ``_on_check_for_updates`` so a dirty-tree pre-stash still survives
        the switch."""
        # Show the recent commit log of the target branch as a preview.
        log = git_runner(
            "log", "--oneline", "-8",
            f"origin/{target}",
            "--not", "HEAD",
        )
        recent = (log.stdout or "").strip() or "(commit log unavailable)"

        prompt = QMessageBox.question(
            self, "New version available",
            f"A newer version of PermaDesign is on the server.\n\n"
            f"You're on:   {current}\n"
            f"Latest:      {target}\n\n"
            f"Recent changes in {target}:\n{recent}\n\n"
            f"Switch to {target} now? You'll need to restart the app "
            "afterward to load the new code.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if prompt != QMessageBox.StandardButton.Yes:
            self._maybe_restore_stash(git_runner, stash_to_restore)
            return

        # If a local branch with this name already exists, plain ``checkout``
        # it; otherwise create it tracking origin/<target>.
        rev_check = git_runner("rev-parse", "--verify", "--quiet", target)
        if rev_check.returncode == 0:
            checkout = git_runner("checkout", target)
        else:
            checkout = git_runner("checkout", "-b", target, f"origin/{target}")

        if checkout.returncode != 0:
            self._maybe_restore_stash(git_runner, stash_to_restore)
            QMessageBox.warning(
                self, "Switch failed",
                f"Couldn't switch to {target}.\n\n"
                + (checkout.stderr.strip() or checkout.stdout.strip())
            )
            return

        # Fast-forward in case the local branch already existed and was
        # behind origin/<target>. Non-fatal if it fails — we've already
        # switched, the user can re-run "Check for Updates" on the new
        # branch.
        pull = git_runner("pull", "--ff-only")
        pull_warning = ""
        if pull.returncode != 0:
            pull_warning = (
                "\n\nNote: couldn't fast-forward after the switch:\n"
                + (pull.stderr.strip() or pull.stdout.strip())
            )

        # Restore any stash we set aside on the source branch.
        stash_note = ""
        if stash_to_restore:
            pop = git_runner("stash", "pop")
            if pop.returncode == 0:
                stash_note = (
                    "\n\nYour stashed local changes were restored on "
                    f"{target}."
                )
            else:
                stash_note = (
                    "\n\nYour stashed local changes did NOT auto-restore "
                    "(likely conflicts on the new branch). It's still "
                    f"saved as `{stash_to_restore}` — recover it with:\n"
                    "    git stash list\n"
                    "    git stash apply stash@{0}"
                )

        QMessageBox.information(
            self, f"Switched to {target}",
            f"You're now on {target}.{pull_warning}{stash_note}\n\n"
            "Close and relaunch the app to load the new version."
        )

    def _open_releases_page(self):
        from PyQt6.QtCore import QUrl
        from PyQt6.QtGui import QDesktopServices
        QDesktopServices.openUrl(QUrl(self._REPO_RELEASES_URL))

    def _build_menu(self):
        mb = self.menuBar()

        # Edit menu
        edit_menu = mb.addMenu("&Edit")

        self._act_undo = edit_menu.addAction("&Undo")
        self._act_undo.setShortcut(QKeySequence.StandardKey.Undo)
        self._act_undo.setEnabled(False)
        self._act_undo.triggered.connect(self._do_undo)

        self._act_redo = edit_menu.addAction("&Redo")
        self._act_redo.setShortcut(QKeySequence.StandardKey.Redo)
        self._act_redo.setEnabled(False)
        self._act_redo.triggered.connect(self._do_redo)

        # File menu
        file_menu = mb.addMenu("&File")

        act_new  = file_menu.addAction("&New")
        act_new.setShortcut("Ctrl+N")
        act_new.triggered.connect(self._on_new)

        act_open = file_menu.addAction("&Open…")
        act_open.setShortcut("Ctrl+O")
        act_open.triggered.connect(self._on_open)

        file_menu.addSeparator()

        act_save = file_menu.addAction("&Save")
        act_save.setShortcut("Ctrl+S")
        act_save.triggered.connect(self._on_save)

        act_save_as = file_menu.addAction("Save &As…")
        act_save_as.setShortcut("Ctrl+Shift+S")
        act_save_as.triggered.connect(self._on_save_as)

        file_menu.addSeparator()

        act_shopping = file_menu.addAction("Export &Plant Order List…")
        act_shopping.setStatusTip("Export a plant order list grouped by Alberta nursery source")
        act_shopping.triggered.connect(self._on_export_shopping_list)

        act_pdf = file_menu.addAction("Export &PDF…")
        act_pdf.setStatusTip("Export design as a presentation-quality PDF")
        act_pdf.triggered.connect(self._on_export_pdf)

        file_menu.addSeparator()

        act_exit = file_menu.addAction("E&xit")
        act_exit.setShortcut("Alt+F4")
        act_exit.triggered.connect(self.close)

        # View menu — recovery hatch for users who accidentally collapse the
        # sidebar (the chevron strip on the right edge can be easy to miss).
        view_menu = mb.addMenu("&View")

        self._act_show_sidebar = view_menu.addAction("Show &Side Panel")
        self._act_show_sidebar.setCheckable(True)
        self._act_show_sidebar.setChecked(True)
        self._act_show_sidebar.setShortcut("Ctrl+\\")
        self._act_show_sidebar.setStatusTip(
            "Toggle the right-hand panel (Site / Plants / Analysis / …)"
        )
        self._act_show_sidebar.triggered.connect(self._on_toggle_sidebar)

        # Help menu
        help_menu = mb.addMenu("&Help")

        # Show the current V<major>.<minor> in the menu item label itself
        # so the user can read it without opening a dialog. The handler
        # opens an About dialog with more detail (commit hash, schema
        # version, etc).
        from src.version_branch import parse_version_branch
        current_branch = self._current_branch_name() or ""
        version_disp = current_branch if parse_version_branch(current_branch) else "dev"
        act_about = help_menu.addAction(f"&About / Version: {version_disp}")
        act_about.setStatusTip(
            "Show the current PermaDesign version, schema version, and "
            "git commit hash"
        )
        act_about.triggered.connect(self._on_about)

        act_update = help_menu.addAction("Check for &Updates…")
        act_update.setStatusTip("Pull the latest version from GitHub (source installs) "
                                "or open the releases page (.exe installs)")
        act_update.triggered.connect(self._on_check_for_updates)

        act_pick = help_menu.addAction("&Switch to a specific version…")
        act_pick.setStatusTip(
            "Pick any published V<major>.<minor> branch and switch the "
            "checkout to it. Handy for rolling back to an older release "
            "or jumping ahead to one the auto-detector doesn't surface."
        )
        act_pick.triggered.connect(self._on_pick_version)

    # ── Signal wiring ─────────────────────────────────────────────────────────

    def _connect_signals(self):
        b = self.map_widget.bridge

        # Map → status bar
        b.mouse_moved.connect(self._on_mouse_moved)

        # Map events → project state (boundary_complete re-connected below with new signature)
        b.plant_placed.connect(self._on_plant_placed)
        b.plant_moved.connect(self._on_plant_moved)
        b.plant_group_moved.connect(self._on_plant_group_moved)
        b.map_ready.connect(self._on_map_ready)

        # Toolbar → map
        self.toolbar.draw_boundary_requested.connect(self._enter_boundary_mode)
        self.toolbar.measure_requested.connect(self._enter_measure_mode)
        self.toolbar.annotate_requested.connect(self._enter_annotate_mode)
        self.toolbar.cancel_draw_requested.connect(self._cancel_draw)
        self.toolbar.undo_requested.connect(self._do_undo)

        self.toolbar.satellite_toggled.connect(self.map_widget.set_satellite_visible)
        self.toolbar.boundary_toggled.connect(self.map_widget.set_boundary_visible)
        self.toolbar.measurements_toggled.connect(
            self.map_widget.set_measurements_visible
        )
        self.toolbar.plants_toggled.connect(self.map_widget.set_plants_visible)
        self.toolbar.canopy_toggled.connect(self.map_widget.set_canopy_visible)
        self.toolbar.grid_settings_changed.connect(self._on_grid_settings_changed)

        # Plant panel → map (plant placement + colour). Pattern mode info
        # arrives in the 4th argument; legacy single-mode placements pass
        # {"kind": "single"}.
        self.plant_panel.place_plant_requested.connect(self._enter_plant_mode)
        self.plant_panel.color_changed.connect(self._on_plant_color_changed)

        # Map → remove plant marker
        b.plant_removed.connect(self._on_plant_removed)

        # Map → batch placement (Burst, Row, Grid, Circle)
        b.pattern_placed.connect(self._on_pattern_placed)

        # Map → annotations
        b.annotate_requested.connect(self._on_annotate_requested)
        b.annotation_removed.connect(self._on_annotation_removed)

        # Toolbar → settings
        self.toolbar.settings_requested.connect(self._on_settings)

        # Polyculture panel → map (polyculture placement)
        self.polyculture_panel.placePolycultureRequested.connect(self._enter_polyculture_mode)
        # Stack → community: refresh the Communities tree when the Plants
        # tab (or anywhere else) creates a brand-new plant community.
        self.plant_panel.communityCreated.connect(
            self.polyculture_panel._refresh_polyculture_list
        )
        self.polyculture_panel.communityCreated.connect(
            self.polyculture_panel._refresh_polyculture_list
        )
        # Mirror plant_panel's per-species counts into the sibling
        # On-This-Design tab's Plants sub-tab.
        self.plant_panel.placed_counts_changed.connect(
            lambda: self.on_this_design.set_plants_counts(
                self.plant_panel._placed_counts
            )
        )

        # Structure panel → map
        self.structure_panel.place_structure_requested.connect(self._enter_structure_mode)
        self.structure_panel.place_hedgerow_requested.connect(self._enter_hedgerow_mode)
        self.structure_panel.place_shape_requested.connect(self._enter_shape_mode)

        # Map → structures/hedgerows/shapes
        b.structure_placed.connect(self._on_structure_placed)
        b.structure_removed.connect(self._on_structure_removed)
        b.hedgerow_complete.connect(self._on_hedgerow_complete)
        b.hedgerow_removed.connect(self._on_hedgerow_removed)
        b.shape_complete.connect(self._on_shape_complete)
        b.shape_removed.connect(self._on_shape_removed)

        # Toolbar → structures layer toggle
        self.toolbar.structures_toggled.connect(self.map_widget.set_structures_visible)

        # Analysis panel → map (A1-A4)
        self.analysis_panel.sun_path_requested.connect(self._on_sun_path_requested)
        self.analysis_panel.sun_path_cleared.connect(self.map_widget.clear_sun_path)
        self.analysis_panel.sector_requested.connect(self._on_sector_requested)
        self.analysis_panel.sector_cleared.connect(self.map_widget.clear_sectors)
        # (Manual contour drawing moved to Site panel — wired below.)
        # Auto-terrain controls live on the Site panel now (alongside the
        # single-point Elevation/slope readout) — the request / clear /
        # opacity signals come from there.
        self.site_panel.auto_terrain_requested.connect(self._on_auto_terrain_requested)
        self.site_panel.auto_terrain_cleared.connect(self._on_auto_terrain_cleared)
        self.site_panel.auto_terrain_opacity.connect(self.map_widget.set_slope_overlay_opacity)
        b.terrain_bbox_ready.connect(self._on_terrain_bbox_ready)
        b.terrain_bbox_cancelled.connect(self._on_terrain_bbox_cancelled)
        self.site_panel.download_edmonton_requested.connect(
            self._on_download_edmonton_requested
        )
        self.analysis_panel.wind_requested.connect(self._on_wind_requested)
        self.analysis_panel.wind_cleared.connect(self.map_widget.clear_wind_overlay)
        self.analysis_panel.season_changed.connect(self._on_season_changed)

        # Map → polyculture removal
        b.polyculture_removed.connect(self._on_polyculture_removed)

        # Map → contour complete / removal
        b.contour_complete.connect(self._on_contour_complete)
        b.contour_removed.connect(self._on_contour_removed)

        # Map → multi-boundary events
        b.boundary_complete.connect(self._on_boundary_complete)
        b.boundary_geom_changed.connect(self._on_boundary_geom_changed)
        b.boundary_props_changed.connect(self._on_boundary_props_changed)
        b.boundary_removed.connect(self._on_boundary_removed)

        # Map → sun path / sector anchor & removal
        b.sun_anchor_placed.connect(self._on_sun_anchor_placed)
        b.sun_path_removed.connect(self._on_sun_path_removed)
        b.anchor_cancelled.connect(self._on_anchor_cancelled)
        b.sector_anchor_placed.connect(self._on_sector_anchor_placed)
        b.sector_group_removed.connect(self._on_sector_group_removed)
        b.sector_group_moved.connect(self._on_sector_group_moved)
        b.sector_group_rotated.connect(self._on_sector_group_rotated)
        b.sector_group_resized.connect(self._on_sector_group_resized)

        # Toolbar → zoom sensitivity
        self.toolbar.zoom_step_changed.connect(self.map_widget.set_zoom_sensitivity)

        # Planning panel → timeline / notes
        self.planning_panel.timeline_year_changed.connect(self._on_timeline_year_changed)
        self.planning_panel.notes_changed.connect(self._on_notes_changed)

        # Site panel ↔ map
        b.site_pin_placed.connect(self._on_site_pin_placed)
        b.site_pin_removed.connect(self._on_site_pin_removed)
        self.site_panel.pin_drop_requested.connect(self._enter_site_pin_mode)
        self.site_panel.pin_clear_requested.connect(self._on_site_pin_clear_clicked)
        self.site_panel.site_data_updated.connect(self._on_site_data_updated)
        # Address search → drop pin on map (the bridge then notifies us
        # back via site_pin_placed and the usual fetch flow runs).
        self.site_panel.address_resolved.connect(self._on_address_resolved)
        # Manual contour drawing controls live on the Site tab now.
        self.site_panel.contour_requested.connect(self._on_contour_requested)
        self.site_panel.contour_cleared.connect(self._on_contour_cleared)

    # ── Map-ready ─────────────────────────────────────────────────────────────

    def _on_map_ready(self):
        self._set_mode_label("Ready")

    # ── Settings ──────────────────────────────────────────────────────────────

    def _load_api_keys(self):
        """Push stored API keys into the plant panel on startup."""
        kid, ksec = get_api_keys()
        self.plant_panel.set_api_keys(kid, ksec)

    def _on_settings(self):
        dlg = SettingsDialog(self)
        if dlg.exec():
            self._load_api_keys()

    def _on_plant_color_changed(self, plant_id: int, hex_color: str):
        """Update all existing markers for this plant on the map."""
        self.map_widget.update_marker_color(plant_id, hex_color)

    # ── Status bar updates ────────────────────────────────────────────────────

    def _on_mouse_moved(self, lat: float, lng: float):
        self._sb_coords.setText(f"Lat: {lat:.5f} , Lng: {lng:.5f}")

    def _set_zone_display(self, zone):
        self._current_zone = zone
        self._sb_zone.setText(zone_label(zone))
        self._project["properties"]["hardiness_zone"] = zone
        self.plant_panel.set_zone(zone)

    def _on_grid_settings_changed(self, settings: dict):
        """Apply changes from the View bar's Grid menu — enabled/size/style."""
        try:
            self.map_widget.set_snap_enabled(
                bool(settings.get("enabled")),
                float(settings.get("size_m") or 1.0),
            )
        except Exception:
            pass
        color = settings.get("color")
        opacity = settings.get("opacity")
        if color is not None or opacity is not None:
            try:
                self.map_widget.set_grid_style(
                    str(color or "#4a7a4a"),
                    float(opacity if opacity is not None else 0.4),
                )
            except Exception:
                pass

    def _set_mode_label(self, text: str):
        self._sb_mode.setText(f"Mode: {text}")

    def _mark_modified(self):
        self._modified = True
        if not self.windowTitle().endswith(' *'):
            self.setWindowTitle(self.windowTitle() + ' *')

    # ── Seasonal tasks ────────────────────────────────────────────────────────

    def _load_seasonal_tasks(self):
        """Show current month's planting tasks in the status bar."""
        try:
            from src.db.plants import get_current_month_tasks
            from datetime import datetime
            month_name = datetime.now().strftime("%B")
            tasks = get_current_month_tasks()
            if tasks:
                # Group by status
                by_status = {}
                for t in tasks[:8]:  # Limit to avoid overflow
                    s = t["status"].replace("_", " ").title()
                    by_status.setdefault(s, []).append(t["common_name"])
                parts = []
                for status, names in by_status.items():
                    parts.append(f"{status}: {', '.join(names[:3])}")
                    if len(names) > 3:
                        parts[-1] += f" +{len(names)-3}"
                self._sb_tasks.setText(f"{month_name}: {' | '.join(parts)}")
            else:
                self._sb_tasks.setText(f"{month_name}: No active tasks")
        except Exception:
            pass

    # ── Drawing modes ─────────────────────────────────────────────────────────

    def _enter_boundary_mode(self):
        self._current_mode = 'boundary'
        self.map_widget.set_mode('boundary')
        self._set_mode_label("Drawing boundary — click to add points, double-click or click first point to close")

    def _enter_plant_mode(self, plant_id: int, common_name: str,
                          quantity: int = 1, pattern: dict | None = None):
        self._current_mode = 'plant'
        # Clear any stale community-pattern stash from a previous
        # community placement; _enter_polyculture_pattern_mode will
        # re-set it after this call returns if a community is being
        # placed, otherwise plant-only patterns get the plant branch.
        self._pending_community_pattern = None
        self._pending_community_pattern_mix = None
        spacing_m, plant_type, custom_color = self._plant_info(plant_id)

        # Polyculture override: when the panel built a mix recipe, use
        # the resolved effective spacing (default = max canopy width)
        # so the JS-side geometry generator lays out cells at a step
        # that fits the largest species in the mix.
        poly = ((pattern or {}).get("params") or {}).get("polyculture")
        if poly and poly.get("effective_spacing_m"):
            spacing_m = float(poly["effective_spacing_m"])

        try:
            from src.db.plants import get_plant
            _p = get_plant(plant_id)
            mature_canopy_m = (_p or {}).get("mature_canopy_m")
        except Exception:
            mature_canopy_m = None

        self.map_widget.set_mode('plant', plant_id, common_name, spacing_m,
                                 plant_type, quantity, custom_color,
                                 pattern=pattern,
                                 mature_canopy_m=mature_canopy_m)
        self.toolbar.enter_plant_mode()

        kind = (pattern or {}).get("kind", "single")
        species_n = len(poly["species"]) if poly else 0
        poly_tag = f" · Mix ({species_n} species)" if species_n else ""
        # When a polyculture is armed, the recipe persists until Esc, so
        # advertise that the user can drop multiple identical patterns.
        tail = " (Esc to finish)" if poly else " — Esc to cancel"
        if kind == "single":
            qty_str = f" ×{quantity}" if quantity > 1 else ""
            label = f"Placing: {common_name}{qty_str} — click map, press Esc to cancel"
        elif kind == "row":
            label = f"Row of {common_name}{poly_tag} — click start point, then end point{tail}"
        elif kind == "grid":
            label = f"Grid of {common_name}{poly_tag} — click two opposite corners{tail}"
        elif kind == "circle":
            label = f"Circle of {common_name}{poly_tag} — click centre, then radius point{tail}"
        else:
            label = f"Placing: {common_name}"
        self._set_mode_label(label)

    @staticmethod
    def _plant_info(plant_id: int) -> tuple[float, str, str]:
        """Return (spacing_meters, plant_type, marker_color) for a plant."""
        try:
            from src.db.plants import get_plant
            p = get_plant(plant_id)
            if p:
                return (
                    float(p.get("spacing_meters") or 1.0),
                    p.get("plant_type") or "herb",
                    p.get("marker_color") or "",
                )
        except Exception:
            pass
        return 1.0, "herb", ""

    def _enter_measure_mode(self):
        self._current_mode = 'measure'
        self.map_widget.set_mode('measure')
        self._set_mode_label("Measure — click two points to see distance")

    def _enter_annotate_mode(self):
        self._current_mode = 'annotate'
        self.map_widget.set_mode('annotate')
        self._set_mode_label("Annotate — click map to place a note")

    def _on_annotate_requested(self, lat: float, lng: float):
        text, ok = QInputDialog.getText(
            self, "Add Note", "Note text:", text=""
        )
        if not ok or not text.strip():
            return
        ann_id = f"ann_{int(lat*1e6)}_{int(lng*1e6)}_{id(self)}"
        self.map_widget.place_annotation(ann_id, lat, lng, text.strip())
        # Save to project
        self._project["features"].append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [lng, lat]},
            "properties": {
                "element_type": "annotation",
                "annotation_id": ann_id,
                "text": text.strip(),
            }
        })
        self._mark_modified()

    def _on_annotation_removed(self, ann_id: str):
        self._project["features"] = [
            f for f in self._project["features"]
            if f.get("properties", {}).get("annotation_id") != ann_id
        ]
        self._mark_modified()

    # ── Structure / Hedgerow / Shape modes ──────────────────────────────────

    def _enter_structure_mode(self, struct_def: dict):
        self._current_mode = 'structure'
        self.map_widget.set_structure_mode(struct_def)
        self.toolbar.reset_draw_buttons()
        self._set_mode_label(
            f"Placing: {struct_def.get('icon', '')} {struct_def.get('name', 'Structure')} — click map, Esc to cancel"
        )

    def _on_structure_placed(self, struct_id: str, name: str, lat: float, lng: float, size_m: float):
        from src.db.structures import get_structure
        struct_def = get_structure(struct_id)
        if struct_def:
            struct_def = dict(struct_def)
            struct_def["size_m"] = size_m
        else:
            struct_def = {"id": struct_id, "name": name, "size_m": size_m}

        self._project["features"].append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [lng, lat]},
            "properties": {
                "element_type": "structure",
                "struct_id": struct_id,
                "name": name,
                "size_m": size_m,
                "struct_def": struct_def,
            }
        })
        self._push_undo({
            "action": "place_structure",
            "struct_id": struct_id,
            "name": name,
            "lat": lat,
            "lng": lng,
            "size_m": size_m,
            "struct_def": struct_def,
        })
        self._mark_modified()
        self.statusBar().showMessage(f"Placed {name}", 2000)
        self._sync_planning_panel()

    def _on_structure_removed(self, marker_id: str, struct_id: str, lat: float, lng: float):
        kept = []
        removed = False
        for f in self._project["features"]:
            props = f.get("properties", {})
            coords = f.get("geometry", {}).get("coordinates", [])
            if (not removed
                    and props.get("element_type") == "structure"
                    and props.get("struct_id") == struct_id
                    and coords
                    and abs(coords[1] - lat) < 1e-7
                    and abs(coords[0] - lng) < 1e-7):
                removed = True
            else:
                kept.append(f)
        self._project["features"] = kept
        self._mark_modified()

    def _enter_hedgerow_mode(self, hedge_config: dict):
        self._current_mode = 'hedgerow'
        self.map_widget.set_hedgerow_mode(hedge_config)
        self.toolbar.reset_draw_buttons()
        self._set_mode_label(
            "Drawing hedgerow — click to add points, double-click to finish"
        )

    def _on_hedgerow_complete(self, hedge_id: str, points_json: str, species: str,
                               style: str, length_m: float, num_plants: int):
        import json as _json
        points = _json.loads(points_json)
        # Store as GeoJSON LineString (lng, lat order)
        coords = [[pt[1], pt[0]] for pt in points]
        self._project["features"].append({
            "type": "Feature",
            "geometry": {"type": "LineString", "coordinates": coords},
            "properties": {
                "element_type": "hedgerow",
                "hedge_id": hedge_id,
                "species": species,
                "style": style,
                "length_m": length_m,
                "num_plants": num_plants,
                "color": "#4caf50",
                "width_m": 1.5,
                "spacing_m": 1.0,
            }
        })
        self._push_undo({
            "action": "place_hedgerow",
            "hedge_id": hedge_id,
            "length_m": length_m,
        })
        self._mark_modified()
        self._set_mode_label("Ready")
        self.statusBar().showMessage(
            f"Hedgerow placed: {length_m:.1f}m, ~{num_plants} plants", 3000
        )

    def _on_hedgerow_removed(self, hedge_id: str, points_json: str):
        self._project["features"] = [
            f for f in self._project["features"]
            if f.get("properties", {}).get("hedge_id") != hedge_id
        ]
        self._mark_modified()

    def _enter_shape_mode(self, shape_config: dict):
        self._current_mode = 'shape'
        self.map_widget.set_shape_mode(shape_config)
        self.toolbar.reset_draw_buttons()
        self._set_mode_label(
            "Drawing shape — click points, double-click or click first point to close"
        )

    def _on_shape_complete(self, shape_id: str, points_json: str, label: str,
                            shape_type: str, fill_color: str, stroke_color: str,
                            fill_opacity: float, dash_array: str, area_m2: float):
        import json as _json
        points = _json.loads(points_json)
        # Store as GeoJSON Polygon (lng, lat; closed ring)
        ring = [[pt[1], pt[0]] for pt in points]
        ring.append(ring[0])  # close the ring
        self._project["features"].append({
            "type": "Feature",
            "geometry": {"type": "Polygon", "coordinates": [ring]},
            "properties": {
                "element_type": "custom_shape",
                "shape_id": shape_id,
                "label": label,
                "shape_type": shape_type,
                "fill_color": fill_color,
                "stroke_color": stroke_color,
                "fill_opacity": fill_opacity,
                "dash_array": dash_array,
                "area_m2": area_m2,
            }
        })
        self._push_undo({
            "action": "place_custom_shape",
            "shape_id": shape_id,
            "label": label,
            "shape_type": shape_type,
        })
        self._mark_modified()
        self._set_mode_label("Ready")
        area_str = f"{area_m2:.1f} m²" if area_m2 < 10000 else f"{area_m2/10000:.2f} ha"
        self.statusBar().showMessage(
            f"Shape placed: {label or shape_type} ({area_str})", 3000
        )

    def _on_shape_removed(self, shape_id: str):
        self._project["features"] = [
            f for f in self._project["features"]
            if f.get("properties", {}).get("shape_id") != shape_id
        ]
        self._mark_modified()

    # ── Analysis overlays (A1-A4) ──────────────────────────────────────────

    def _on_sun_path_requested(self, config: dict):
        """A1: Enter anchor-placement mode; render after user clicks the map."""
        self._pending_sun_config = config
        self._pending_sun_anchor = None
        self.map_widget.enter_sun_anchor_mode()
        self._set_mode_label("Click map to place sun path anchor — right-click to cancel")

    def _render_sun_path(self, config: dict, lat: float, lng: float):
        """Compute sun positions and send to JS with the clicked anchor."""
        from datetime import date as _date
        from src.solar import sun_path_for_date, sunrise_sunset

        d = _date.fromisoformat(config["date"])
        positions = sun_path_for_date(lat, lng, d, steps=72)
        sr, ss = sunrise_sunset(lat, lng, d)

        pos_data = [
            {"altitude": p.altitude, "azimuth": p.azimuth, "hour": p.hour}
            for p in positions
        ]

        payload = {
            "positions": pos_data,
            "date_label": config.get("date_label", d.isoformat()),
            "show_shadows": config.get("show_shadows", True),
            "show_shadow_length": config.get("show_shadow_length", False),
            "sunrise_hour": sr,
            "sunset_hour": ss,
        }
        if "arc_radius" in config:
            payload["arc_radius"] = config["arc_radius"]
        self.map_widget.draw_sun_path(payload, lat, lng)

        noon_alt = max((p.altitude for p in positions), default=0)
        daylight = ss - sr
        self.analysis_panel.set_sun_info(
            f"Sunrise: {_fmt_time(sr)} | Sunset: {_fmt_time(ss)}\n"
            f"Daylight: {daylight:.1f} hrs | Max altitude: {noon_alt:.1f}°"
        )
        self._set_mode_label(f"Sun path: {config.get('date_label', d.isoformat())}")
        self._pending_sun_config = None

    def _on_sector_requested(self, config: dict):
        """A2: Enter anchor-placement mode; draw after user clicks the map."""
        self._pending_sector_config = config
        self.map_widget.enter_sector_anchor_mode()
        self._set_mode_label("Click map to place sector anchor — right-click to cancel")

    def _on_contour_requested(self, config: dict):
        """A3: Enter contour drawing mode."""
        self._current_mode = 'contour'
        self.map_widget.set_contour_mode(config)
        self.toolbar.reset_draw_buttons()
        elev = config.get("elevation_m", 0)
        self._set_mode_label(
            f"Drawing contour at {elev:.1f}m — click points, double-click to finish"
        )

    def _on_contour_complete(self, points_json: str, elevation: float, color: str):
        """Save contour line to project."""
        import json as _json
        points = _json.loads(points_json)
        coords = [[pt[1], pt[0]] for pt in points]
        self._project["features"].append({
            "type": "Feature",
            "geometry": {"type": "LineString", "coordinates": coords},
            "properties": {
                "element_type": "contour_line",
                "elevation_m": elevation,
                "color": color,
            }
        })
        self._push_undo({
            "action": "place_contour",
            "points": list(points),
            "elevation_m": elevation,
            "color": color,
        })
        self._mark_modified()
        self._set_mode_label("Ready")
        self.statusBar().showMessage(
            f"Contour line at {elevation:.1f}m placed", 2000
        )

    def _on_contour_removed(self, points_json: str, elevation: float, color: str):
        """Remove a single contour line from project state."""
        kept = []
        removed = False
        for f in self._project["features"]:
            props = f.get("properties", {})
            if (not removed
                    and props.get("element_type") == "contour_line"
                    and abs(props.get("elevation_m", -1) - elevation) < 0.01):
                removed = True
            else:
                kept.append(f)
        self._project["features"] = kept
        self._mark_modified()
        self.statusBar().showMessage(
            f"Contour line at {elevation:.1f}m removed", 2000
        )

    def _on_contour_cleared(self):
        """Clear all contours from map and project."""
        self.map_widget.clear_contours()
        self._project["features"] = [
            f for f in self._project["features"]
            if f.get("properties", {}).get("element_type") != "contour_line"
        ]
        self._mark_modified()

    # ── Auto-generated terrain (slope contours + ramp overlay) ────────────────

    def _on_auto_terrain_requested(self, config: dict):
        """Stash config, then ask the JS map for the bbox to compute over."""
        self._pending_terrain_config = dict(config)
        area = config.get("area_source", "viewport")
        if area == "viewport":
            self.map_widget.request_terrain_viewport()
        elif area == "boundary":
            self.map_widget.request_terrain_boundary_bbox()
        elif area == "draw":
            self.map_widget.enter_terrain_draw_mode()
            self._set_mode_label(
                "Drag a rectangle on the map to set the slope-analysis area"
            )

    def _on_terrain_bbox_cancelled(self):
        self._pending_terrain_config = None
        self._set_mode_label("Ready")
        self.site_panel.set_auto_terrain_status("Cancelled.")

    def _on_terrain_bbox_ready(self, bbox: dict):
        """Enqueue a TerrainWorker job for the chosen bbox and start it
        if no other job is running. Multiple Generate clicks queue up
        rather than getting rejected.
        """
        cfg = getattr(self, "_pending_terrain_config", None)
        if not cfg:
            return
        self._pending_terrain_config = None

        options = {
            "interval_m":         cfg.get("interval_m", 0.5),
            "resolution_m":       cfg.get("resolution_m", 30.0),
            "want_contours":      cfg.get("want_contours", True),
            "want_slope_overlay": cfg.get("want_slope_overlay", True),
        }
        prefs = {
            "color":       cfg.get("color", "#5d4037"),
            "opacity":     cfg.get("opacity", 0.6),
            "show_labels": cfg.get("show_labels", True),
        }
        if not hasattr(self, "_terrain_queue"):
            self._terrain_queue = []
        self._terrain_queue.append({
            "bbox": bbox, "options": options, "prefs": prefs,
        })
        self._update_terrain_queue_status()
        self._maybe_start_next_terrain_job()

    def _maybe_start_next_terrain_job(self):
        """Pop the next queued job and run it, if nothing else is running."""
        if getattr(self, "_terrain_running", False):
            return
        queue = getattr(self, "_terrain_queue", None) or []
        if not queue:
            return
        job = queue.pop(0)
        bbox    = job["bbox"]
        options = job["options"]
        self._terrain_render_prefs = job["prefs"]

        from src.terrain import TerrainWorker, grid_dims
        self._terrain_running = True
        self._terrain_thread = QThread(self)
        self._terrain_worker = TerrainWorker(bbox, options)
        self._terrain_worker.moveToThread(self._terrain_thread)
        self._terrain_thread.started.connect(self._terrain_worker.run)
        self._terrain_worker.ready.connect(self._on_terrain_ready)
        self._terrain_worker.failed.connect(self._on_terrain_failed)
        self._terrain_worker.finished.connect(self._terrain_thread.quit)
        self._terrain_worker.finished.connect(self._terrain_worker.deleteLater)
        self._terrain_thread.finished.connect(self._on_terrain_thread_done)
        self._terrain_thread.start()

        self._set_mode_label("Generating slope contours…")
        cols, rows = grid_dims(bbox, options["resolution_m"])
        n_samples = cols * rows
        prefix = self._terrain_queue_prefix()
        if n_samples > 3000:
            # ~0.3 s pacing per batch + request time ≈ 0.5 s/batch end-to-end.
            est_seconds = max(5, int(round(n_samples / 100 * 0.6)))
            self.site_panel.set_auto_terrain_status(
                f"{prefix}Fetching elevation data for {cols}×{rows} samples "
                f"— ~{est_seconds} s for an area this size…"
            )
        else:
            self.site_panel.set_auto_terrain_status(
                f"{prefix}Fetching elevation data…"
            )

    def _terrain_queue_prefix(self) -> str:
        """Render '[3 queued] ' before status text when other jobs wait."""
        queued = len(getattr(self, "_terrain_queue", []) or [])
        return f"[{queued} more queued] " if queued else ""

    def _update_terrain_queue_status(self):
        """Update the status line when queue changes but no job started yet."""
        queue = getattr(self, "_terrain_queue", []) or []
        if not getattr(self, "_terrain_running", False) and queue:
            self.site_panel.set_auto_terrain_status(
                f"Queued {len(queue)} job(s); starting next…"
            )

    def _on_terrain_thread_done(self):
        """Clear stale references after a TerrainWorker run finishes, then
        start the next queued job (if any).

        Connected to QThread.finished. Drops the Python references *before*
        scheduling deleteLater on the thread, so the next Generate click
        can't observe a half-deleted wrapper.
        """
        thread = self._terrain_thread
        self._terrain_thread = None
        self._terrain_worker = None
        self._terrain_running = False
        if thread is not None:
            thread.deleteLater()
        # Defer the next start so deleteLater settles cleanly.
        QTimer.singleShot(0, self._maybe_start_next_terrain_job)

    # ── Edmonton offline dataset download ─────────────────────────────────────

    def _on_download_edmonton_requested(self):
        from src.terrain_downloader import EdmontonDownloadWorker
        self._dl_thread = QThread(self)
        self._dl_worker = EdmontonDownloadWorker()
        self._dl_worker.moveToThread(self._dl_thread)
        self._dl_thread.started.connect(self._dl_worker.run)
        self._dl_worker.progress.connect(self._on_edmonton_dl_progress)
        self._dl_worker.finished.connect(self._on_edmonton_dl_finished)
        self._dl_worker.error.connect(self._on_edmonton_dl_error)
        self._dl_worker.finished.connect(self._dl_thread.quit)
        self._dl_worker.error.connect(self._dl_thread.quit)
        self._dl_thread.finished.connect(self._on_dl_thread_done)
        # Wire the Cancel button to the worker's cancel() slot
        self.site_panel._terrain_cancel_btn.clicked.connect(self._dl_worker.cancel)
        self._dl_thread.start()

    def _on_edmonton_dl_progress(self, features_stored: int, page_num: int, text: str):
        self.site_panel.set_download_progress(features_stored, page_num, text)

    def _on_edmonton_dl_finished(self, total: int):
        self.site_panel.set_terrain_status()
        self.statusBar().showMessage(
            f"Edmonton terrain download complete — {total:,} features stored offline.",
            8000,
        )

    def _on_edmonton_dl_error(self, message: str):
        self.site_panel.set_terrain_status()
        self.statusBar().showMessage(f"Edmonton download failed: {message}", 10000)

    def _on_dl_thread_done(self):
        try:
            self.site_panel._terrain_cancel_btn.clicked.disconnect(self._dl_worker.cancel)
        except Exception:
            pass
        if hasattr(self, "_dl_worker") and self._dl_worker is not None:
            self._dl_worker.deleteLater()
            self._dl_worker = None
        if hasattr(self, "_dl_thread") and self._dl_thread is not None:
            self._dl_thread.deleteLater()
            self._dl_thread = None

    def _on_terrain_ready(self, result: dict):
        """Render the worker's output and persist features in the project."""
        prefs = getattr(self, "_terrain_render_prefs", {}) or {}
        contours = result.get("contours") or []
        png_bytes = result.get("slope_png_bytes")
        slope_bbox = result.get("slope_bbox")

        # Strip stale auto features before adding new ones.
        self._project["features"] = [
            f for f in self._project["features"]
            if f.get("properties", {}).get("element_type") not in
                ("auto_contour", "slope_overlay")
        ]
        self.map_widget.clear_auto_terrain()

        # Render contour lines.
        if contours:
            self.map_widget.draw_auto_contours(
                contours,
                color=prefs.get("color", "#5d4037"),
                show_labels=prefs.get("show_labels", True),
            )
            for c in contours:
                # Each contour may have multiple disjoint segments;
                # stored as a MultiLineString feature for round-tripping.
                lines = []
                for seg in c.get("segments", []):
                    if len(seg) >= 2:
                        # GeoJSON wants [lng, lat]
                        lines.append([[pt[1], pt[0]] for pt in seg])
                if not lines:
                    continue
                self._project["features"].append({
                    "type": "Feature",
                    "geometry": {
                        "type": "MultiLineString",
                        "coordinates": lines,
                    },
                    "properties": {
                        "element_type": "auto_contour",
                        "elevation_m":  c["elevation_m"],
                        "color":        prefs.get("color", "#5d4037"),
                        "source":       result.get("source", ""),
                    },
                })

        # Render slope ramp overlay.
        if png_bytes and slope_bbox:
            import base64
            data_url = "data:image/png;base64," + base64.b64encode(png_bytes).decode("ascii")
            self.map_widget.draw_slope_overlay(
                data_url, slope_bbox,
                opacity=prefs.get("opacity", 0.6),
            )
            # Persist a marker feature so projects re-open with overlay
            # information (the PNG itself is regenerated on demand).
            ring = [
                [slope_bbox["west"], slope_bbox["south"]],
                [slope_bbox["east"], slope_bbox["south"]],
                [slope_bbox["east"], slope_bbox["north"]],
                [slope_bbox["west"], slope_bbox["north"]],
                [slope_bbox["west"], slope_bbox["south"]],
            ]
            self._project["features"].append({
                "type": "Feature",
                "geometry": {"type": "Polygon", "coordinates": [ring]},
                "properties": {
                    "element_type": "slope_overlay",
                    "bbox":         slope_bbox,
                    "stats":        result.get("stats", {}),
                    "interval_m":   result.get("interval_m"),
                    "resolution_m": result.get("resolution_m"),
                    "source":       result.get("source", ""),
                },
            })

        self._mark_modified()
        self._set_mode_label("Ready")

        stats = result.get("stats", {})
        bits = [f"Source: {result.get('source', '')}"]
        if "max_slope_pct" in stats:
            bits.append(
                f"Max slope: {stats['max_slope_pct']:.1f}%, "
                f"mean: {stats.get('mean_slope_pct', 0):.1f}%"
            )
        if "dominant_aspect" in stats:
            share_pct = int(round(stats.get("dominant_aspect_share", 0) * 100))
            bits.append(
                f"Aspect: {stats['dominant_aspect']} ({share_pct}% of slope ≥2%)"
            )
        bits.append(f"{len(contours)} contour level(s)")
        for w in (result.get("warnings") or []):
            bits.append("⚠ " + w)
        self.site_panel.set_auto_terrain_status(" — ".join(bits))

    def _on_terrain_failed(self, message: str):
        self._set_mode_label("Ready")
        self.site_panel.set_auto_terrain_status(f"Failed: {message}")
        # Avoid stacking modal dialogs when more jobs are queued — show
        # one only when nothing else is pending. Queued failures still
        # surface in the status line.
        queued = len(getattr(self, "_terrain_queue", []) or [])
        if queued == 0:
            QMessageBox.warning(self, "Terrain Generation", message)

    def _on_auto_terrain_cleared(self):
        self.map_widget.clear_auto_terrain()
        self._project["features"] = [
            f for f in self._project["features"]
            if f.get("properties", {}).get("element_type") not in
                ("auto_contour", "slope_overlay")
        ]
        self._mark_modified()
        self.site_panel.set_auto_terrain_status("")

    def _on_wind_requested(self, config: dict):
        """A4: Draw wind overlay with shelter zones."""
        self.map_widget.draw_wind_overlay(config)
        self._set_mode_label(
            f"Wind from {config.get('direction_from', '?')}° ({config.get('speed_label', '')})"
        )

    def _on_season_changed(self, season: str):
        """Apply seasonal view to the map — adjusts plant visibility by type."""
        import json as _json
        from src.db.plants import get_plant

        # Seasonal opacity rules based on deciduous_evergreen field
        # Summer: everything full
        # Winter: deciduous → 0.15, herbaceous → 0.05, evergreen → 1.0
        # Spring/Fall: intermediate
        season_opacity = {
            "Summer":  {"deciduous": 1.0, "evergreen": 1.0, "herbaceous": 1.0},
            "Spring":  {"deciduous": 0.7, "evergreen": 1.0, "herbaceous": 0.6},
            "Fall":    {"deciduous": 0.5, "evergreen": 1.0, "herbaceous": 0.4},
            "Winter":  {"deciduous": 0.15, "evergreen": 1.0, "herbaceous": 0.05},
        }
        rules = season_opacity.get(season, season_opacity["Summer"])

        pid_vis = {}
        plant_cache = {}
        for p in self._placed_plants:
            pid = p["plant_id"]
            if pid not in plant_cache:
                plant = get_plant(pid)
                if plant:
                    de = (plant.get("deciduous_evergreen") or "").lower()
                    if de in ("evergreen",):
                        plant_cache[pid] = "evergreen"
                    elif de in ("deciduous",):
                        plant_cache[pid] = "deciduous"
                    else:
                        # Herbs, groundcover, etc. treated as herbaceous
                        ptype = plant.get("plant_type", "herb")
                        if ptype in ("tree", "shrub"):
                            plant_cache[pid] = "deciduous"
                        else:
                            plant_cache[pid] = "herbaceous"
                else:
                    plant_cache[pid] = "herbaceous"

            pid_vis[pid] = rules[plant_cache[pid]]

        js_data = _json.dumps(pid_vis)
        self.map_widget.run_js(f"setSeasonView('{season}', {js_data});")
        self._set_mode_label(f"Season: {season}")

    def _enter_polyculture_mode(self, polyculture_data: dict):
        """Place a polyculture on the map.

        Two modes:
          - "single" (no pattern, or pattern.kind == "single"): click once
            to drop the community at the clicked point. Each member is
            placed at its offset_x/offset_y from that centre.
          - "row" / "grid" / "circle": enter plant-pattern mode with a
            synthetic representative plant (so JS's preview ghost works),
            stash the full community, and let JS handle the 2-click
            gesture. The stashed community is expanded across the
            resulting anchor positions in _on_pattern_placed.
        """
        pattern = polyculture_data.get("pattern")
        kind = (pattern or {}).get("kind") or "single"
        if kind != "single" and polyculture_data.get("members"):
            self._enter_polyculture_pattern_mode(polyculture_data, pattern)
            return

        self._current_mode = 'polyculture'
        self._pending_polyculture = polyculture_data
        self.map_widget.run_js("map.getContainer().style.cursor = 'crosshair';")
        self._set_mode_label(
            f"Placing plant community: {polyculture_data.get('name', '?')} — click map to place centre"
        )
        try:
            self.map_widget.bridge.map_clicked.disconnect(self._on_polyculture_click)
        except TypeError:
            pass
        self.map_widget.bridge.map_clicked.connect(self._on_polyculture_click)

    def _enter_polyculture_pattern_mode(self, polyculture_data: dict, pattern: dict):
        """Set up row/grid/circle placement of a community as a unit.

        Reuses plant-pattern mode by picking the member closest to (0,0)
        as the synthetic preview plant. The full community is stashed
        in self._pending_community_pattern so _on_pattern_placed can
        expand each anchor position into one full community.
        """
        members = polyculture_data.get("members") or []
        # Pick the member nearest the community centre as the preview anchor.
        members_sorted = sorted(
            members,
            key=lambda m: (float(m.get("offset_x") or 0.0) ** 2
                           + float(m.get("offset_y") or 0.0) ** 2),
        )
        primary = members_sorted[0]
        primary_pid = int(primary["plant_id"])
        primary_name = primary.get("common_name") or polyculture_data.get("name", "")

        spacing_m = float(pattern.get("spacing_m") or 4.0)
        kind = pattern.get("kind") or "row"

        # Use the params dict the placement widget produced. Defaults
        # cover legacy callers that supplied only kind + spacing_m.
        params = dict(pattern.get("params") or {})
        params.setdefault("overlap", 0.0)
        params.setdefault("use_canopy", False)
        # Detect the community-mix case (Plants tab analogue: one stack
        # of multiple communities at ratios). Each anchor will become one
        # full community, picked according to the ratios.
        community_mix = params.pop("community_mix", None)
        # Carry the full community payload so _on_pattern_placed can
        # expand each anchor into the community's members.
        params["community"] = {
            "name": polyculture_data.get("name", ""),
            "spacing_m": spacing_m,
            "members": [dict(m) for m in members],
        }
        pattern_dict = {"kind": kind, "params": params}

        # Drop any stale plant-mix recipe so it doesn't get applied.
        try:
            self.plant_panel.clear_pending_polyculture()
        except Exception:
            pass
        self._enter_plant_mode(primary_pid, primary_name,
                               quantity=1, pattern=pattern_dict)
        # Stash AFTER _enter_plant_mode (which clears the previous stash
        # at its top) so this fresh community is the one expanded by
        # _on_pattern_placed. The mix stash takes precedence over the
        # single-community stash when present.
        self._pending_community_pattern = pattern_dict["params"]["community"]
        self._pending_community_pattern_mix = community_mix
        # Override the mode label so the user sees the community context.
        if community_mix:
            community_name = (
                f"{len(community_mix)}-community mix "
                f"({':'.join(str(c['weight']) for c in community_mix)})"
            )
        else:
            community_name = polyculture_data.get("name", "?")
        gesture = {
            "row":    "click start, then end",
            "grid":   "click two opposite corners",
            "circle": "click centre, then radius point",
        }.get(kind, "click")
        self._set_mode_label(
            f"Placing community '{community_name}' as {kind} — {gesture}. "
            "Esc to cancel."
        )

    def _on_polyculture_click(self, lat: float, lng: float):
        """Drop a polyculture by issuing one placePlantMarker per member.

        Mirrors the grid/row/burst loop in _on_pattern_placed: each member is
        rendered through the fast canvas-renderer path with a shared groupId,
        so the placement avoids the per-poly SVG renderer + temp L.layerGroup
        attach that caused O(N^2) browser paint cost. Mode stays armed after
        each placement (Esc / mode-switch cancels), matching row/burst/grid
        UX so a single "Place on Map" press lets the user drop many
        polycultures back to back.
        """
        if self._current_mode != 'polyculture' or not hasattr(self, '_pending_polyculture'):
            return
        import math

        polyculture = self._pending_polyculture
        members = polyculture.get("members", [])
        if not members:
            return

        poly_name = polyculture.get("name", "")
        group_id = project_io.new_placement_group_id()
        cos_lat = math.cos(lat * math.pi / 180) or 1e-9

        batch_placements: list[tuple[int, str]] = []
        for m in members:
            pid = m["plant_id"]
            name = m["common_name"]
            spacing_m, plant_type, _ = self._plant_info(pid)
            color = _member_color(m)

            mlat = lat + (m.get("offset_y", 0)) / 111320
            mlng = lng + (m.get("offset_x", 0)) / (111320 * cos_lat)

            self.map_widget.run_js(
                f"placePlantMarker({pid}, {repr(name)}, "
                f"{mlat}, {mlng}, {spacing_m}, {repr(plant_type)}, "
                f"{repr(color)}, {repr(group_id)});"
            )
            self._placed_plants.append({
                "plant_id": pid, "common_name": name,
                "lat": mlat, "lng": mlng,
                "polyculture_name": poly_name,
                "polyculture_center_lat": lat, "polyculture_center_lng": lng,
                "placement_group_id": group_id,
            })
            self._project["features"].append({
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [mlng, mlat]},
                "properties": {
                    "element_type": "plant",
                    "plant_id": pid,
                    "common_name": name,
                    "polyculture_name": poly_name,
                    "polyculture_center_lat": lat,
                    "polyculture_center_lng": lng,
                    "placement_group_id": group_id,
                    "quantity": 1
                }
            })
            batch_placements.append((pid, name))

        # One placed-list rebuild per polyculture click instead of N — see
        # PlantPanel.on_plants_placed_batch for the rationale.
        self.plant_panel.on_plants_placed_batch(batch_placements)
        self._mark_modified()
        self._sync_planning_panel()
        self._set_mode_label(
            f"Placed plant community '{poly_name}'. Click again for another, "
            f"or press Esc to finish."
        )
        self.statusBar().showMessage(
            f"Placed plant community '{poly_name}' with {len(members)} members", 2500
        )

    def _cancel_draw(self):
        self._current_mode = 'none'
        self.map_widget.cancel_draw()
        # Also bail out of an armed manual pin-drop, since Esc / Cancel
        # is the user's universal "back out" gesture.
        if getattr(self, "_site_pin_mode", False):
            self._site_pin_mode = False
            self.map_widget.set_site_pin_drop_mode(False)
            try:
                self.map_widget.bridge.map_clicked.disconnect(
                    self._on_site_pin_click
                )
            except (TypeError, RuntimeError):
                pass
        self._set_mode_label("Ready")
        self.toolbar.reset_draw_buttons()
        # Drop any in-flight polyculture recipe — the user explicitly
        # exited plant mode, so the next Place Mix click should re-stash
        # a fresh one.
        try:
            self.plant_panel.clear_pending_polyculture()
        except Exception:
            pass
        # Same idea for any community-pattern stash: dropping it on
        # cancel ensures the user starts fresh next time they hit Place.
        self._pending_community_pattern = None
        self._pending_community_pattern_mix = None

    # ── Map event handlers ────────────────────────────────────────────────────

    def _on_boundary_complete(self, bid: str, coords: list, color: str):
        """Multi-boundary: add a new boundary to the project."""
        ring = [[pt[1], pt[0]] for pt in coords] + [[coords[0][1], coords[0][0]]]
        self._project["features"].append({
            "type": "Feature",
            "geometry": {"type": "Polygon", "coordinates": [ring]},
            "properties": {
                "element_type": "property_boundary",
                "boundary_id": bid,
                "color": color,
                "show_lengths": True,
                "show_area": True,
            }
        })

        lats = [pt[0] for pt in coords]
        lngs = [pt[1] for pt in coords]
        self._set_zone_display(get_zone(sum(lats)/len(lats), sum(lngs)/len(lngs)))

        self._push_undo({
            "action": "place_boundary",
            "boundary_id": bid,
            "coords": list(coords),
            "color": color,
        })

        self._mark_modified()
        self.toolbar.reset_draw_buttons()
        self._set_mode_label(
            f"Boundary added ({color}) — " + zone_label(self._current_zone)
        )

    def _on_boundary_geom_changed(self, bid: str, coords: list):
        """Update geometry of an existing boundary after vertex/move/scale drag."""
        ring = [[pt[1], pt[0]] for pt in coords] + [[coords[0][1], coords[0][0]]]
        for f in self._project.get("features", []):
            if (f.get("properties", {}).get("element_type") == "property_boundary"
                    and f["properties"].get("boundary_id") == bid):
                f["geometry"]["coordinates"] = [ring]
                break
        self._mark_modified()

    def _on_boundary_props_changed(self, bid: str, color: str,
                                    show_lengths: bool, show_area: bool):
        """Update color/label toggles for an existing boundary."""
        for f in self._project.get("features", []):
            if (f.get("properties", {}).get("element_type") == "property_boundary"
                    and f["properties"].get("boundary_id") == bid):
                f["properties"]["color"] = color
                f["properties"]["show_lengths"] = show_lengths
                f["properties"]["show_area"] = show_area
                break
        self._mark_modified()

    def _on_boundary_removed(self, bid: str):
        """Remove a boundary from the project."""
        self._project["features"] = [
            f for f in self._project["features"]
            if not (f.get("properties", {}).get("element_type") == "property_boundary"
                    and f["properties"].get("boundary_id") == bid)
        ]
        self._mark_modified()

    def _on_plant_moved(self, marker_id: str, plant_id: int,
                        old_lat: float, old_lng: float,
                        new_lat: float, new_lng: float):
        """User dragged a singleton plant marker. Update project state
        and push a single-move undo entry so Ctrl+Z restores the
        previous position."""
        if abs(new_lat - old_lat) < 1e-9 and abs(new_lng - old_lng) < 1e-9:
            return
        # _placed_plants list
        for p in self._placed_plants:
            if (p["plant_id"] == plant_id
                    and abs(p["lat"] - old_lat) < 1e-7
                    and abs(p["lng"] - old_lng) < 1e-7):
                p["lat"] = new_lat
                p["lng"] = new_lng
                break
        # Project features
        for f in self._project["features"]:
            props = f.get("properties", {})
            coords = f.get("geometry", {}).get("coordinates", [])
            if (props.get("element_type") == "plant"
                    and props.get("plant_id") == plant_id
                    and coords
                    and abs(coords[1] - old_lat) < 1e-7
                    and abs(coords[0] - old_lng) < 1e-7):
                f["geometry"]["coordinates"] = [new_lng, new_lat]
                break
        self._push_undo({
            "action":   "move_plant",
            "plant_id": plant_id,
            "old_lat":  old_lat, "old_lng": old_lng,
            "new_lat":  new_lat, "new_lng": new_lng,
        })
        self._mark_modified()

    def _on_plant_group_moved(self, group_id: str,
                              originals_json: str, moved_json: str):
        """User dragged a polyculture (or other multi-plant) group as
        a cohesive unit. Apply the per-marker delta to project state
        and push a single group-move undo entry."""
        import json as _json
        try:
            originals = _json.loads(originals_json or "[]")
            moved     = _json.loads(moved_json or "[]")
        except Exception:
            return
        if not originals or len(originals) != len(moved):
            return
        # Pair by markerId so updates land on the right feature even if
        # the JSON arrays come back in a different order.
        moved_by_id = {m.get("markerId"): m for m in moved}
        any_change = False
        for orig in originals:
            mid = orig.get("markerId")
            new = moved_by_id.get(mid)
            if not new:
                continue
            old_lat = float(orig.get("lat") or 0.0)
            old_lng = float(orig.get("lng") or 0.0)
            new_lat = float(new.get("lat") or 0.0)
            new_lng = float(new.get("lng") or 0.0)
            if abs(new_lat - old_lat) < 1e-9 and abs(new_lng - old_lng) < 1e-9:
                continue
            any_change = True
            plant_id = orig.get("plantId")
            for p in self._placed_plants:
                if (p["plant_id"] == plant_id
                        and abs(p["lat"] - old_lat) < 1e-7
                        and abs(p["lng"] - old_lng) < 1e-7):
                    p["lat"] = new_lat
                    p["lng"] = new_lng
                    break
            for f in self._project["features"]:
                props = f.get("properties", {})
                coords = f.get("geometry", {}).get("coordinates", [])
                if (props.get("element_type") == "plant"
                        and props.get("plant_id") == plant_id
                        and props.get("placement_group_id") == group_id
                        and coords
                        and abs(coords[1] - old_lat) < 1e-7
                        and abs(coords[0] - old_lng) < 1e-7):
                    f["geometry"]["coordinates"] = [new_lng, new_lat]
                    break
        if not any_change:
            return
        self._push_undo({
            "action":    "move_plant_group",
            "group_id":  group_id,
            "originals": list(originals),
            "moved":     list(moved),
        })
        self._mark_modified()
        self.statusBar().showMessage(
            f"Moved polyculture group ({len(originals)} plants)", 2000
        )

    def _on_sun_anchor_placed(self, lat: float, lng: float):
        """User placed sun-path anchor; now compute and draw."""
        self._pending_sun_anchor = (lat, lng)
        if self._pending_sun_config:
            self._render_sun_path(self._pending_sun_config, lat, lng)

    def _on_sector_anchor_placed(self, lat: float, lng: float):
        """User placed sector anchor; now draw."""
        if self._pending_sector_config:
            self.map_widget.draw_sectors(self._pending_sector_config, lat, lng)
            names = [s["name"] for s in self._pending_sector_config.get("sectors", [])]
            self._set_mode_label(f"Sectors: {', '.join(names)}")
            self._pending_sector_config = None

    def _on_sun_path_removed(self):
        self._set_mode_label("Sun path removed")

    def _on_anchor_cancelled(self, mode: str):
        self.toolbar.reset_draw_buttons()
        self._set_mode_label("Ready")
        try:
            self.plant_panel.clear_pending_polyculture()
        except Exception:
            pass

    def _on_sector_group_removed(self, sid: str):
        self._set_mode_label("Sector group removed")

    def _on_sector_group_moved(self, sid: str, lat: float, lng: float):
        pass  # could persist if sectors were saved to project file

    def _on_sector_group_rotated(self, sid: str, rotation_deg: float):
        pass

    def _on_sector_group_resized(self, sid: str, radius_m: float):
        pass

    def _on_plant_placed(self, plant_id: int, common_name: str, lat: float, lng: float):
        # Single-click placement: each plant gets its own singleton group.
        group_id = project_io.new_placement_group_id()
        self._push_undo({
            "action": "place_plant",
            "plant_id": plant_id, "common_name": common_name,
            "lat": lat, "lng": lng,
            "placement_group_id": group_id,
        })
        self._placed_plants.append({
            "plant_id": plant_id, "common_name": common_name,
            "lat": lat, "lng": lng,
            "placement_group_id": group_id,
        })
        self._project["features"].append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [lng, lat]},
            "properties": {
                "element_type": "plant",
                "plant_id": plant_id,
                "common_name": common_name,
                "placement_group_id": group_id,
                "quantity": 1
            }
        })
        # Tell JS the marker's group id so right-click → "Delete group" works.
        self.map_widget.run_js(
            f"setPlantGroupForLatest({plant_id}, {lat}, {lng}, "
            f"{repr(group_id)});"
        )
        self.plant_panel.on_plant_placed(plant_id, common_name)
        self._mark_modified()
        self._sync_planning_panel()

    def _expand_communities_at_positions(self, positions, community: dict,
                                          pattern_kind: str):
        """Expand a Community across N anchor positions.

        ``community`` is the dict stashed in self._pending_community_pattern
        by _enter_polyculture_pattern_mode (or a single-community block).
        Currently always uses the same community at every anchor — the
        community-mix (ratio) variant can plug in here later by replacing
        the single dict with per-anchor assignments.

        Every placed marker across every anchor shares a single
        placement_group_id, so deleting any marker via "Delete group"
        removes the whole pattern. The per-anchor polyculture_name +
        polyculture_center_{lat,lng} are also written so
        _on_polyculture_removed can target one community at a time.
        """
        import math
        members = community.get("members") or []
        if not members or not positions:
            return

        poly_name = community.get("name") or ""
        group_id = project_io.new_placement_group_id()

        batch_placements: list[tuple[int, str]] = []
        for (lat, lng) in positions:
            cos_lat = math.cos(lat * math.pi / 180) or 1e-9
            for m in members:
                pid = m["plant_id"]
                name = m.get("common_name", "")
                spacing_m, plant_type, _ = self._plant_info(pid)
                color = _member_color(m)
                mlat = lat + float(m.get("offset_y", 0) or 0) / 111320
                mlng = lng + float(m.get("offset_x", 0) or 0) / (111320 * cos_lat)

                self.map_widget.run_js(
                    f"placePlantMarker({pid}, {repr(name)}, "
                    f"{mlat}, {mlng}, {spacing_m}, {repr(plant_type)}, "
                    f"{repr(color)}, {repr(group_id)});"
                )
                self._placed_plants.append({
                    "plant_id": pid, "common_name": name,
                    "lat": mlat, "lng": mlng,
                    "polyculture_name": poly_name,
                    "polyculture_center_lat": lat,
                    "polyculture_center_lng": lng,
                    "placement_group_id": group_id,
                })
                self._project["features"].append({
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": [mlng, mlat]},
                    "properties": {
                        "element_type": "plant",
                        "plant_id": pid,
                        "common_name": name,
                        "polyculture_name": poly_name,
                        "polyculture_center_lat": lat,
                        "polyculture_center_lng": lng,
                        "placement_group_id": group_id,
                        "pattern_kind": pattern_kind,
                        "quantity": 1,
                    }
                })
                batch_placements.append((pid, name))

        self.plant_panel.on_plants_placed_batch(batch_placements)
        self._mark_modified()
        self._sync_planning_panel()
        self._set_mode_label(
            f"Placed {len(positions)} × '{poly_name}' ({pattern_kind}). "
            "Click again for another, or press Esc to finish."
        )
        self.statusBar().showMessage(
            f"Placed {len(positions)} communities of '{poly_name}' "
            f"({len(members)} members each)",
            3000,
        )

    def _on_pattern_placed(self, plant_id: int, common_name: str, spacing_m: float,
                            plant_type: str, custom_color: str,
                            positions_json: str, pattern_kind: str):
        """Place N plants at once (Burst, Row, Grid, Circle).

        All plants share a single placement_group_id so they can be selected
        and deleted as a unit. The positions list is computed JS-side so the
        live preview and the committed placement use the same geometry.

        When the plant panel's polyculture mix had ≥2 species at the time
        Place was clicked, the panel stashed a recipe; we consume it here
        and assign one species per generated position. Each placed marker
        carries its own plant_id/common_name/colour, but the whole stand
        still shares one placement_group_id so it selects and deletes
        as a single polyculture.
        """
        import json as _json
        try:
            positions = _json.loads(positions_json)
        except Exception:
            return
        if not positions:
            return

        # ── Community-mix-as-pattern branch ────────────────────────────
        # When the Communities tab armed a Community Mix (≥2 communities
        # at ratios), each anchor becomes one full community picked by
        # ratio. assign_species takes generic {id, weight} items so the
        # communities pose as "species" here at zero algorithmic cost.
        community_mix = getattr(self, "_pending_community_pattern_mix", None)
        if community_mix:
            from src.polyculture import assign_species
            mix_items = [
                {
                    "id": int(c["id"]),
                    "common_name": c.get("name") or "",
                    "spacing_m": 1.0,
                    "plant_type": "community",
                    "color": "",
                    "weight": int(c.get("weight") or 1),
                }
                for c in community_mix
            ]
            try:
                assignments = assign_species(positions, mix_items, "even_split")
            except Exception:
                assignments = [mix_items[0]] * len(positions)
            poly_by_id = {int(c["id"]): c["polyculture"] for c in community_mix}
            # Per-anchor calls so each instance gets its own
            # placement_group_id — deleting one community doesn't take
            # out the rest of the row.
            for (lat, lng), assignment in zip(positions, assignments):
                community = poly_by_id.get(int(assignment["id"]))
                if not community:
                    continue
                community_payload = {
                    "name": community.get("name", ""),
                    "spacing_m": 1.0,
                    "members": [dict(m) for m in (community.get("members") or [])],
                }
                self._expand_communities_at_positions(
                    [(lat, lng)], community_payload, pattern_kind
                )
            return

        # ── Community-as-pattern branch ────────────────────────────────
        # If a Community was stashed at Place-click time, every anchor
        # position expands into one full community (all its members,
        # offset around the anchor). This sits above the plant-mix
        # branch because the two are mutually exclusive — selecting a
        # community for pattern placement clears any plant mix.
        community = getattr(self, "_pending_community_pattern", None)
        if community:
            self._expand_communities_at_positions(
                positions, community, pattern_kind
            )
            return

        # Peek (don't consume) the polyculture recipe stashed at
        # Place-click time. Keeping it alive lets the user drop multiple
        # back-to-back patterns without re-clicking Place Mix; it's
        # only cleared when plant mode is exited (Esc / cancel) or the
        # user clicks Place Mix again with a different mix.
        assignments: list[dict] | None = None
        poly = None
        try:
            poly = self.plant_panel.peek_pending_polyculture()
        except Exception:
            poly = None
        if poly and len(poly.get("species", [])) >= 2:
            from src.polyculture import assign_species, optimize_layout
            assignments = assign_species(
                positions, poly["species"], poly.get("strategy", "even_split")
            )
            # Now permute that ratio-correct assignment so same-species
            # plants are spread as far apart as the geometry allows.
            # The optimiser only swaps pairs, so per-species counts
            # (the user's ratios) are preserved exactly.
            try:
                assignments = optimize_layout(positions, assignments)
            except Exception:
                # Fall back to the un-optimised but ratio-correct list
                # if SA blows up; better to plant clumped than to crash.
                pass

        group_id = project_io.new_placement_group_id()
        for i, (lat, lng) in enumerate(positions):
            if assignments is not None:
                sp = assignments[i]
                pid       = sp["id"]
                name      = sp["common_name"]
                sp_space  = sp["spacing_m"]
                sp_type   = sp["plant_type"]
                sp_color  = sp["color"]
            else:
                pid, name           = plant_id, common_name
                sp_space, sp_type   = spacing_m, plant_type
                sp_color            = custom_color

            # Render the marker on the map.
            self.map_widget.run_js(
                f"placePlantMarker({pid}, {repr(name)}, "
                f"{lat}, {lng}, {sp_space}, {repr(sp_type)}, "
                f"{repr(sp_color) if sp_color else 'null'}, "
                f"{repr(group_id)});"
            )
            # Mirror in project state.
            self._placed_plants.append({
                "plant_id": pid, "common_name": name,
                "lat": lat, "lng": lng,
                "placement_group_id": group_id,
            })
            self._project["features"].append({
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [lng, lat]},
                "properties": {
                    "element_type": "plant",
                    "plant_id": pid,
                    "common_name": name,
                    "placement_group_id": group_id,
                    "pattern_kind": pattern_kind,
                    "quantity": 1
                }
            })
            self.plant_panel.on_plant_placed(pid, name)
        self._mark_modified()
        self._sync_planning_panel()
        if assignments is not None:
            n_species = len({s["id"] for s in poly["species"]})
            self.statusBar().showMessage(
                f"Placed {len(positions)} plants — "
                f"{n_species}-species plant community ({pattern_kind})", 3000
            )
            self._set_mode_label(
                f"Placed plant community ({pattern_kind}). Click again for another, "
                f"or press Esc to finish."
            )
        else:
            self.statusBar().showMessage(
                f"Placed {len(positions)} {common_name} ({pattern_kind})", 2500
            )

    def _on_plant_removed(self, marker_id: str, plant_id: int, lat: float, lng: float):
        # Remove matching entry from placed list (match by plant_id + coords)
        for i, p in enumerate(self._placed_plants):
            if (p["plant_id"] == plant_id
                    and abs(p["lat"] - lat) < 1e-7
                    and abs(p["lng"] - lng) < 1e-7):
                self._placed_plants.pop(i)
                break

        # Remove matching feature from project
        removed = False
        kept = []
        for f in self._project["features"]:
            props = f.get("properties", {})
            coords = f.get("geometry", {}).get("coordinates", [])
            if (not removed
                    and props.get("element_type") == "plant"
                    and props.get("plant_id") == plant_id
                    and coords
                    and abs(coords[1] - lat) < 1e-7
                    and abs(coords[0] - lng) < 1e-7):
                removed = True
            else:
                kept.append(f)
        self._project["features"] = kept

        self.plant_panel.on_plant_removed(plant_id)
        self._mark_modified()
        self._sync_planning_panel()

    def _on_polyculture_removed(self, polyculture_name: str, center_lat: float, center_lng: float):
        """Remove all polyculture member plant features from project state.

        Members are identified by the polyculture_center_{lat,lng} anchor they were
        tagged with at placement time — the previous approach of matching
        each plant's own coordinate against the center with a 0.001-degree
        (~111 m) tolerance both missed members farther than 100 m from the
        center and could match plants from adjacent polycultures with identical
        names.
        """
        # 1e-7 deg ≈ 1 cm — plenty tight while absorbing float round-trip noise.
        TOL = 1e-7

        def _anchors_match(anchor_lat, anchor_lng):
            if anchor_lat is None or anchor_lng is None:
                return False
            return (abs(anchor_lat - center_lat) < TOL
                    and abs(anchor_lng - center_lng) < TOL)

        kept_plants = []
        for p in self._placed_plants:
            if (p.get("polyculture_name") == polyculture_name
                    and _anchors_match(p.get("polyculture_center_lat"),
                                       p.get("polyculture_center_lng"))):
                continue  # drop this polyculture member
            kept_plants.append(p)
        removed_count = len(self._placed_plants) - len(kept_plants)
        self._placed_plants = kept_plants

        kept_features = []
        for f in self._project["features"]:
            props = f.get("properties", {})
            if (props.get("element_type") == "plant"
                    and props.get("polyculture_name") == polyculture_name
                    and _anchors_match(props.get("polyculture_center_lat"),
                                       props.get("polyculture_center_lng"))):
                continue  # drop this polyculture member
            kept_features.append(f)
        self._project["features"] = kept_features

        # Update plant panel counts
        for _ in range(removed_count):
            self.plant_panel.on_plant_removed(0)
        self._mark_modified()
        self._sync_planning_panel()

    # ── Site pin / property data ──────────────────────────────────────────────

    def _on_site_pin_placed(self, lat: float, lng: float, label: str):
        """User dropped a property pin (via search or manual click)."""
        self._site_pin_mode = False
        self.map_widget.set_site_pin_drop_mode(False)
        self.site_panel.set_pin(lat, lng, label)
        # Switch to the Site tab so results are visible.
        try:
            idx = self._side_tabs.indexOf(self.site_panel)
            if idx >= 0:
                self._side_tabs.setCurrentIndex(idx)
        except Exception:
            pass
        # Persist coordinates immediately; site data fills in when fetcher returns.
        sc = self._project["properties"].setdefault("site_config", {})
        sc["latitude"]  = lat
        sc["longitude"] = lng
        if label:
            sc["pin_label"] = label
        self._mark_modified()
        self._set_mode_label("Property pin set — fetching site data")

    def _on_site_pin_removed(self):
        self.site_panel.clear_pin()
        sc = self._project["properties"].setdefault("site_config", {})
        for key in ("latitude", "longitude", "pin_label",
                    "rainfall", "soil", "elevation", "hardiness",
                    "data_fetched_at"):
            sc.pop(key, None)
        self._mark_modified()
        self._set_mode_label("Property pin removed")

    def _on_site_pin_clear_clicked(self):
        self.map_widget.clear_site_pin()
        self._on_site_pin_removed()

    def _on_address_resolved(self, lat: float, lng: float, label: str):
        """SitePanel resolved an address — drop the pin and re-centre the map.

        The bridge will fire `site_pin_placed` back which runs the
        existing site-data fetch flow; we just have to place the pin
        and pan/zoom.
        """
        self.map_widget.place_site_pin(lat, lng, label or "")
        # Centre on the new pin at a reasonable property-scale zoom.
        self.map_widget.set_view(lat, lng, 17)

    def _enter_site_pin_mode(self):
        """Manual pin-drop: next map click places the pin."""
        self._site_pin_mode = True
        self._set_mode_label("Click the map to drop the property pin")
        # Visual affordance — switch the map cursor to a crosshair so the
        # user can see that the next click is going to drop a point.
        self.map_widget.set_site_pin_drop_mode(True)
        # One-shot connection to map_clicked
        try:
            self.map_widget.bridge.map_clicked.disconnect(self._on_site_pin_click)
        except Exception:
            pass
        self.map_widget.bridge.map_clicked.connect(self._on_site_pin_click)

    def _on_site_pin_click(self, lat: float, lng: float):
        if not getattr(self, "_site_pin_mode", False):
            return
        self._site_pin_mode = False
        self.map_widget.set_site_pin_drop_mode(False)
        try:
            self.map_widget.bridge.map_clicked.disconnect(self._on_site_pin_click)
        except Exception:
            pass
        # Drop the pin immediately with just coordinates so the user gets
        # instant feedback, then resolve the actual address in the
        # background and refresh the pin label once we have it.
        self.map_widget.place_site_pin(lat, lng, "")
        self._start_pin_reverse_geocode(lat, lng)

    def _start_pin_reverse_geocode(self, lat: float, lng: float):
        """Look up the actual address for a manually-dropped pin.

        Runs Nominatim's reverse geocode off the UI thread; if it
        succeeds we re-place the pin with the resolved label so the Site
        panel shows a real address instead of just lat/lng.
        """
        # Cancel any prior reverse-geocode worker first.
        prev_worker = getattr(self, "_revgeo_worker", None)
        prev_thread = getattr(self, "_revgeo_thread", None)
        self._revgeo_worker = None
        self._revgeo_thread = None
        if prev_worker is not None:
            try:
                prev_worker.results.disconnect()
            except (TypeError, RuntimeError):
                pass
        # Use the same safe-isRunning pattern as site_panel — calling
        # isRunning() on a QThread whose C++ side has been deleteLater'd
        # raises RuntimeError, which used to crash the app on rapid
        # consecutive pin actions.
        from src.site_panel import _safe_is_running as _safe_is_running_thread
        if _safe_is_running_thread(prev_thread):
            try:
                prev_thread.quit()
            except RuntimeError:
                pass

        from PyQt6.QtCore import QObject, QThread, pyqtSignal, pyqtSlot

        class _RevGeoWorker(QObject):
            results = pyqtSignal(float, float, str)  # lat, lng, label ("" on fail)

            def __init__(self, lat: float, lng: float):
                super().__init__()
                self._lat = lat
                self._lng = lng

            @pyqtSlot()
            def run(self):
                try:
                    from src.property_data import reverse_geocode
                    label = reverse_geocode(self._lat, self._lng) or ""
                except Exception:
                    label = ""
                self.results.emit(self._lat, self._lng, label)

        thread = QThread(self)
        worker = _RevGeoWorker(lat, lng)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.results.connect(self._on_pin_reverse_geocode_done)
        # Auto-teardown chain (same pattern as site_panel._start_fetch).
        worker.results.connect(thread.quit)
        worker.results.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        self._revgeo_worker = worker
        self._revgeo_thread = thread
        thread.start()

    def _on_pin_reverse_geocode_done(self, lat: float, lng: float, label: str):
        self._revgeo_worker = None
        self._revgeo_thread = None
        if not label:
            return
        # Re-place the pin with the resolved label so the marker tooltip
        # and the Site panel both show the actual address.
        self.map_widget.place_site_pin(lat, lng, label)

    def _on_site_data_updated(self, result: dict):
        """SitePanel finished fetching; persist results into project state."""
        from datetime import datetime
        sc = self._project["properties"].setdefault("site_config", {})
        for key in ("rainfall", "soil", "elevation", "hardiness"):
            if result.get(key) is not None:
                sc[key] = result[key]
        sc["data_fetched_at"] = datetime.utcnow().isoformat()

        # Mirror the auto-filled hardiness zone into the existing
        # top-level project field so the rest of the app picks it up.
        hard = result.get("hardiness") or {}
        zone = hard.get("zone")
        if zone is not None:
            self._set_zone_display(zone)

        self._mark_modified()
        self._set_mode_label("Site data ready")

    # ── File operations ───────────────────────────────────────────────────────

    def _on_new(self):
        if self._modified:
            r = QMessageBox.question(
                self, "New Design",
                "Current design has unsaved changes. Discard and start new?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel
            )
            if r != QMessageBox.StandardButton.Yes:
                return

        name, ok = QInputDialog.getText(
            self, "New Design", "Project name:", text="My Food Forest"
        )
        if not ok:
            return
        name = name.strip() or "Untitled Design"

        self._project      = project_io.new_project(name)
        self._project_path = None
        self._modified     = False
        self._placed_plants.clear()
        self._clear_undo()
        self._current_zone = None
        self._sb_zone.setText("Zone: —")
        self.map_widget.clear_all()
        self.map_widget.clear_site_pin()
        self.site_panel.clear_pin()
        self.plant_panel.clear_placed()
        self.plant_panel.set_zone(None)
        self.planning_panel.set_notes("")
        self.planning_panel.set_placed_plants([])
        self.planning_panel.set_structures([])
        self.analysis_panel.set_placed_plants([])
        self.analysis_panel.set_structures([])
        self.setWindowTitle(f"PermaDesign — {name}")
        self._set_mode_label("Ready")

    def _on_open(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Open Design", "",
            "PermaDesign Files (*.perma.geojson);;GeoJSON (*.geojson);;All files (*)"
        )
        if not path:
            return
        try:
            self._load_from_path(path)
        except Exception as exc:
            QMessageBox.critical(self, "Open failed", str(exc))

    def _load_from_path(self, path: str):
        proj = project_io.load_project(path)
        self._project      = proj
        self._project_path = path
        self._modified     = False
        self._placed_plants.clear()
        self._clear_undo()

        self.map_widget.clear_all()
        data = project_io.project_to_map_data(proj)

        for bd in data.get("boundaries", []):
            self.map_widget.load_boundary(bd)
        if data.get("boundaries"):
            first = data["boundaries"][0]
            lats = [p[0] for p in first["points"]]
            lngs = [p[1] for p in first["points"]]
            self._set_zone_display(
                get_zone(sum(lats)/len(lats), sum(lngs)/len(lngs))
            )

        # Backfill placement_group_id onto legacy project features so that a
        # subsequent save persists them. project_to_map_data already minted
        # singleton groups for any feature that lacked one.
        plant_idx = 0
        for f in proj.get("features", []):
            if f.get("properties", {}).get("element_type") == "plant":
                if not f["properties"].get("placement_group_id") and plant_idx < len(data["plants"]):
                    f["properties"]["placement_group_id"] = (
                        data["plants"][plant_idx]["placement_group_id"]
                    )
                plant_idx += 1

        for p in data["plants"]:
            spacing_m, plant_type, custom_color = self._plant_info(p["plant_id"])
            self.map_widget.load_plant_marker(
                p["plant_id"], p["common_name"], p["lat"], p["lng"],
                spacing_m, plant_type, custom_color,
                p.get("placement_group_id", "")
            )
            self._placed_plants.append(p)

        self.plant_panel.load_placed(data["plants"])

        for s in data.get("structures", []):
            self.map_widget.load_structure(s["struct_def"], s["lat"], s["lng"])

        for h in data.get("hedgerows", []):
            self.map_widget.load_hedgerow(h)

        for sh in data.get("shapes", []):
            self.map_widget.load_shape(sh)

        # Contour lines are loaded via JS (finishContour re-uses the drawing logic)
        # We redraw them directly as polylines
        for ctr in data.get("contours", []):
            import json as _json
            self.map_widget.run_js(
                f"(function() {{"
                f"  var d = JSON.parse({_json.dumps(_json.dumps(ctr))});"
                f"  contourPoints = d.points;"
                f"  currentContour = d;"
                f"  finishContour();"
                f"  contourPoints = [];"
                f"}})()"
            )

        # Auto-generated contours (MultiLineString features) are restored
        # directly as a single layer group. Slope ramp PNG isn't persisted —
        # the user re-runs Generate to recompute it on demand.
        auto_contours = data.get("auto_contours") or []
        if auto_contours:
            color = auto_contours[0].get("color", "#5d4037")
            self.map_widget.draw_auto_contours(
                [{"elevation_m": c["elevation_m"], "segments": c["segments"]}
                 for c in auto_contours],
                color=color,
                show_labels=True,
            )
        if data.get("slope_overlay"):
            self.site_panel.set_auto_terrain_status(
                "Slope ramp not loaded from file — click Generate to recompute."
            )

        # Restore property pin + cached site data, if any.
        sc = proj.get("properties", {}).get("site_config") or {}
        plat, plng = sc.get("latitude"), sc.get("longitude")
        if plat is not None and plng is not None:
            label = sc.get("pin_label", "")
            self.map_widget.place_site_pin(plat, plng, label)
            has_cache = any(sc.get(k) for k in
                            ("rainfall", "soil", "elevation", "hardiness"))
            self.site_panel.set_pin(plat, plng, label, fetch=not has_cache)
            # Replay any cached results without hitting the network again.
            for key, slot in (
                ("hardiness", self.site_panel._on_hardiness),
                ("elevation", self.site_panel._on_elevation),
                ("rainfall",  self.site_panel._on_rainfall),
                ("soil",      self.site_panel._on_soil),
            ):
                if sc.get(key):
                    slot(sc[key])

        # Load notes
        notes = proj.get("properties", {}).get("notes", "")
        self.planning_panel.set_notes(notes)

        name = proj.get("properties", {}).get("project_name", "Design")
        self.setWindowTitle(f"PermaDesign — {name}")

        self._sync_planning_panel()

    def _on_save(self):
        if self._project_path:
            self._save_to_path(self._project_path)
        else:
            self._on_save_as()

    def _on_save_as(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Design", "",
            "PermaDesign Files (*.perma.geojson);;GeoJSON (*.geojson)"
        )
        if not path:
            return
        if not path.endswith(".geojson"):
            path += ".perma.geojson"
        self._save_to_path(path)

    def _save_to_path(self, path: str):
        try:
            project_io.save_project(self._project, path)
            self._project_path = path
            self._modified     = False
            name = self._project["properties"].get("project_name", "Design")
            self.setWindowTitle(f"PermaDesign — {name}")
            self.statusBar().showMessage(f"Saved: {path}", 3000)
        except Exception as exc:
            QMessageBox.critical(self, "Save failed", str(exc))

    # ── Autosave ──────────────────────────────────────────────────────────────

    def _start_autosave(self):
        self._autosave_timer = QTimer(self)
        self._autosave_timer.setInterval(self.AUTOSAVE_INTERVAL_MS)
        self._autosave_timer.timeout.connect(self._autosave)
        self._autosave_timer.start()

    def _autosave(self):
        if not self._modified:
            return
        tmp = os.path.join(os.path.expanduser("~"), ".permadesign_autosave.perma.geojson")
        try:
            project_io.save_project(self._project, tmp)
        except Exception:
            pass

    # ── Plant order list export ──────────────────────────────────────────────

    # Form (seed / plug / container) inferred from plant_type. Native nurseries
    # commonly stock trees/shrubs as containers, herbaceous as plugs, and grasses
    # / forbs as seed for broadcast applications.
    _PLANT_FORM_BY_TYPE = {
        "tree":        "container",
        "shrub":       "container",
        "vine":        "container",
        "herb":        "plug or seed",
        "groundcover": "plug or seed",
        "root":        "bulb / tuber",
    }

    def _on_export_shopping_list(self):
        if not self._placed_plants:
            QMessageBox.information(self, "Plant Order List", "No plants placed yet.")
            return

        from collections import Counter
        counts: Counter = Counter()
        names: dict[int, str] = {}
        for p in self._placed_plants:
            pid = p["plant_id"]
            counts[pid] += 1
            names[pid] = p["common_name"]

        try:
            from src.db.plants import get_plant
        except Exception:
            get_plant = lambda pid: None

        # Bucket by sourcing channel:
        #   native_trees_shrubs → ALCLA / Bow Valley Habitat Development
        #   native_herbaceous   → ALCLA / Wild About Flowers / Bedrock Seed Bank
        #   cultivated          → local garden centres
        native_woody: list[tuple[str, str, str, int]] = []
        native_herb:  list[tuple[str, str, str, int]] = []
        cultivated:   list[tuple[str, str, str, int]] = []

        total = 0
        for pid, qty in counts.items():
            plant = get_plant(pid) or {}
            ptype = plant.get("plant_type", "other")
            sci   = plant.get("scientific_name", "")
            native = bool(plant.get("native_to_alberta"))
            form  = self._PLANT_FORM_BY_TYPE.get(ptype, "—")
            entry = (names[pid], sci, form, qty)
            if native and ptype in ("tree", "shrub", "vine"):
                native_woody.append(entry)
            elif native:
                native_herb.append(entry)
            else:
                cultivated.append(entry)
            total += qty

        def fmt_section(title: str, items: list[tuple[str, str, str, int]]) -> list[str]:
            if not items:
                return []
            out = [title, "-" * len(title)]
            for name, sci, form, qty in sorted(items, key=lambda x: x[0].lower()):
                line = f"  {name}"
                if sci:
                    line += f"  ({sci})"
                line += f"  ×{qty}  [{form}]"
                out.append(line)
            out.append("")
            return out

        lines = [
            "PermaDesign — Native Plant Order List",
            "=" * 44,
            "",
        ]
        lines += fmt_section(
            "NATIVE TREES & SHRUBS  (sources: ALCLA, Bow Valley Habitat)",
            native_woody,
        )
        lines += fmt_section(
            "NATIVE HERBACEOUS & GROUNDCOVER  "
            "(sources: ALCLA, Wild About Flowers, Bedrock Seed Bank)",
            native_herb,
        )
        lines += fmt_section(
            "CULTIVATED / NON-NATIVE  (sources: local garden centres)",
            cultivated,
        )

        lines.append("=" * 44)
        n_native = sum(qty for _, _, _, qty in native_woody + native_herb)
        n_cult   = sum(qty for _, _, _, qty in cultivated)
        lines.append(
            f"Total: {total} plants ({len(counts)} species)  "
            f"— {n_native} native, {n_cult} cultivated"
        )
        lines.append("")
        lines.append("Alberta native plant nurseries / seed sources:")
        lines.append("  • ALCLA Native Plants            https://alclanativeplants.com/")
        lines.append("  • Bow Valley Habitat Development https://bowvalleyhabitat.com/")
        lines.append("  • Wild About Flowers             https://wildaboutflowers.ca/")
        lines.append("  • Bedrock Seed Bank              https://bedrockseedbank.ca/")

        text = "\n".join(lines)

        path, _ = QFileDialog.getSaveFileName(
            self, "Export Plant Order List", "plant_order_list.txt",
            "Text Files (*.txt);;CSV (*.csv);;All Files (*)"
        )
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(text)
            self.statusBar().showMessage(f"Plant order list saved: {path}", 3000)
        except Exception as exc:
            QMessageBox.critical(self, "Export failed", str(exc))

    # ── Undo / Redo ────────────────────────────────────────────────────────

    # ── PDF export (V3) ────────────────────────────────────────────────────

    def _on_export_pdf(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Export PDF", "design.pdf",
            "PDF Files (*.pdf);;All Files (*)"
        )
        if not path:
            return
        if not path.endswith(".pdf"):
            path += ".pdf"

        try:
            from src.pdf_export import export_pdf

            # Enrich placed plants with type info for the PDF
            enriched = []
            for p in self._placed_plants:
                entry = dict(p)
                try:
                    from src.db.plants import get_plant
                    plant_data = get_plant(p["plant_id"])
                    if plant_data:
                        entry["plant_type"] = plant_data.get("plant_type", "herb")
                except Exception:
                    pass
                enriched.append(entry)

            # Capture map screenshot
            pixmap = self.map_widget.grab()

            # Gather structures from project
            structs = [
                f["properties"].get("struct_def", {})
                for f in self._project.get("features", [])
                if f.get("properties", {}).get("element_type") == "structure"
            ]

            notes = self.planning_panel.get_notes()

            export_pdf(path, self._project, enriched, structs, notes, pixmap)
            self.statusBar().showMessage(f"PDF exported: {path}", 3000)
        except Exception as exc:
            QMessageBox.critical(self, "PDF Export Failed", str(exc))

    # ── Design notes (V4) ────────────────────────────────────────────────

    def _on_notes_changed(self, text: str):
        self._project["properties"]["notes"] = text
        self._mark_modified()

    # ── Timeline / succession ──────────────────────────────────────────────

    def _on_timeline_year_changed(self, year: int):
        """Compute per-plant scale factors for the timeline year and send to JS."""
        import json as _json
        import math

        from src.db.plants import get_plant

        _DEFAULT_YTM = {"tree": 15, "shrub": 5, "herb": 2, "groundcover": 1, "vine": 2, "root": 2}

        scale_data = []
        # Build a mapping from markerId patterns to placed plants
        # MarkerIds follow pattern: {plantId}_{timestamp}_{random}
        # We need to iterate plantMarkers in JS, so we build scale data keyed by markerIds
        # Since we don't have JS markerIds in Python, we build per-plant-id scale factors
        # and let JS match by plantId
        plant_cache = {}  # plant_id -> (ytm, curve)
        summary_trees = 0
        summary_mature = 0
        summary_total = len(self._placed_plants)

        for p in self._placed_plants:
            pid = p["plant_id"]
            if pid not in plant_cache:
                plant = get_plant(pid)
                if plant:
                    ytm = plant.get("years_to_maturity") or _DEFAULT_YTM.get(
                        plant.get("plant_type", "herb"), 2)
                    curve = plant.get("growth_curve") or "steady"
                    ptype = plant.get("plant_type", "herb")
                else:
                    ytm = 2
                    curve = "steady"
                    ptype = "herb"
                plant_cache[pid] = (ytm, curve, ptype)

            ytm, curve, ptype = plant_cache[pid]

            if year == 0:
                factor = 1.0
            elif year >= ytm:
                factor = 1.0
            else:
                ratio = year / ytm
                if curve == "fast_early":
                    factor = math.sqrt(ratio)
                elif curve == "slow_start":
                    factor = ratio ** 1.5
                else:  # steady
                    factor = ratio
            factor = max(0.1, min(1.0, factor))

            if ptype == "tree":
                summary_trees += 1
            if factor >= 0.95:
                summary_mature += 1

        # Build summary text
        if year == 0:
            summary = "Planting day — all plants at initial size."
        else:
            pct_mature = int(summary_mature / max(1, summary_total) * 100)
            summary = (
                f"Year {year}: {summary_mature}/{summary_total} plants at maturity "
                f"({pct_mature}%)."
            )
            if summary_trees > 0:
                # Find avg tree scale
                tree_scales = []
                for p in self._placed_plants:
                    pid = p["plant_id"]
                    ytm, curve, ptype = plant_cache[pid]
                    if ptype == "tree":
                        ratio = min(1.0, year / ytm)
                        if curve == "fast_early":
                            tree_scales.append(math.sqrt(ratio))
                        elif curve == "slow_start":
                            tree_scales.append(ratio ** 1.5)
                        else:
                            tree_scales.append(ratio)
                avg_tree = sum(tree_scales) / len(tree_scales) if tree_scales else 0
                summary += f"\nTrees: ~{int(avg_tree * 100)}% of mature canopy."

        self.planning_panel.update_timeline_summary(summary)

        # Send scale data to JS — we use a per-plantId approach
        # JS will iterate plantMarkers and look up scaleFactor by plantId
        pid_factors = {}
        for pid, (ytm, curve, ptype) in plant_cache.items():
            if year == 0:
                factor = 1.0
            elif year >= ytm:
                factor = 1.0
            else:
                ratio = year / ytm
                if curve == "fast_early":
                    factor = math.sqrt(ratio)
                elif curve == "slow_start":
                    factor = ratio ** 1.5
                else:
                    factor = ratio
            pid_factors[pid] = max(0.1, min(1.0, factor))

        js_data = _json.dumps(pid_factors)
        self.map_widget.run_js(f"setTimelineYearByPlantId({year}, {js_data});")

    # ── Planning panel sync ──────────────────────────────────────────────

    def _sync_planning_panel(self):
        """Push current placed plants and structures to planning + analysis panels."""
        enriched = []
        for p in self._placed_plants:
            entry = dict(p)
            try:
                from src.db.plants import get_plant
                plant_data = get_plant(p["plant_id"])
                if plant_data:
                    entry["plant_type"] = plant_data.get("plant_type", "herb")
                    entry["water_needs"] = plant_data.get("water_needs", "medium")
                    entry["native_to_alberta"] = bool(plant_data.get("native_to_alberta"))
            except Exception:
                pass
            enriched.append(entry)
        self.planning_panel.set_placed_plants(enriched)

        structs = []
        for f in self._project.get("features", []):
            props = f.get("properties", {})
            if props.get("element_type") == "structure":
                sd = props.get("struct_def", {})
                structs.append(sd)
        self.planning_panel.set_structures(structs)

        # Habitat Value Score tab in the analysis panel uses the same data.
        self.analysis_panel.set_placed_plants(enriched)
        self.analysis_panel.set_structures(structs)

        # "On This Design" sibling inner tab. Push both: Communities + Stats
        # sub-tabs read from the enriched list; the Plants sub-tab reads
        # from `_placed_counts` (this catches load-project / new-project
        # paths where placed_counts_changed didn't fire one-for-one).
        try:
            self.on_this_design.set_plants_counts(self.plant_panel._placed_counts)
            self.on_this_design.set_design_data(enriched)
        except Exception:
            pass

    def _push_undo(self, entry: dict):
        self._undo_stack.append(entry)
        if len(self._undo_stack) > self._max_undo:
            self._undo_stack.pop(0)
        self._redo_stack.clear()
        self._act_undo.setEnabled(True)
        self._act_redo.setEnabled(False)

    def _do_undo(self):
        if not self._undo_stack:
            return
        entry = self._undo_stack.pop()
        action = entry["action"]

        if action == "place_plant":
            # Remove the most recent marker matching this plant + coords
            pid, lat, lng = entry["plant_id"], entry["lat"], entry["lng"]
            self.map_widget.run_js(
                f"(function() {{"
                f"  var keys = Object.keys(plantMarkers);"
                f"  for (var i = keys.length - 1; i >= 0; i--) {{"
                f"    var m = plantMarkers[keys[i]];"
                f"    if (m._pd && m._pd.plantId === {pid}"
                f"        && Math.abs(m._pd.lat - {lat}) < 1e-7"
                f"        && Math.abs(m._pd.lng - {lng}) < 1e-7) {{"
                f"      map.removeLayer(m);"
                f"      if (plantLabels[keys[i]]) {{ map.removeLayer(plantLabels[keys[i]]); delete plantLabels[keys[i]]; }}"
                f"      delete plantMarkers[keys[i]];"
                f"      break;"
                f"    }}"
                f"  }}"
                f"}})()"
            )
            # Remove from placed list
            for i in range(len(self._placed_plants) - 1, -1, -1):
                p = self._placed_plants[i]
                if (p["plant_id"] == pid
                        and abs(p["lat"] - lat) < 1e-7
                        and abs(p["lng"] - lng) < 1e-7):
                    self._placed_plants.pop(i)
                    break
            # Remove from project features
            kept = []
            removed = False
            for f in reversed(self._project["features"]):
                props = f.get("properties", {})
                coords = f.get("geometry", {}).get("coordinates", [])
                if (not removed
                        and props.get("element_type") == "plant"
                        and props.get("plant_id") == pid
                        and coords
                        and abs(coords[1] - lat) < 1e-7
                        and abs(coords[0] - lng) < 1e-7):
                    removed = True
                else:
                    kept.append(f)
            self._project["features"] = list(reversed(kept))
            self.plant_panel.on_plant_removed(pid)
            self._redo_stack.append(entry)
            self.statusBar().showMessage("Undo: removed plant", 2000)

        elif action == "place_structure":
            import json as _json
            sid = entry["struct_id"]
            lat = entry["lat"]
            lng = entry["lng"]
            self.map_widget.run_js(
                f"undoStructureAt({_json.dumps(sid)}, {lat}, {lng});"
            )
            kept = []
            removed = False
            for f in reversed(self._project["features"]):
                props = f.get("properties", {})
                coords = f.get("geometry", {}).get("coordinates", [])
                if (not removed
                        and props.get("element_type") == "structure"
                        and props.get("struct_id") == sid
                        and coords
                        and abs(coords[1] - lat) < 1e-7
                        and abs(coords[0] - lng) < 1e-7):
                    removed = True
                else:
                    kept.append(f)
            self._project["features"] = list(reversed(kept))
            self._redo_stack.append(entry)
            self.statusBar().showMessage(
                f"Undo: removed {entry.get('name', 'structure')}", 2000
            )
            self._sync_planning_panel()

        elif action == "place_boundary":
            import json as _json
            bid = entry["boundary_id"]
            self.map_widget.run_js(
                f"(function() {{"
                f"  if (typeof _removeBoundaryEntry === 'function') {{"
                f"    _removeBoundaryEntry({_json.dumps(bid)});"
                f"  }}"
                f"}})()"
            )
            self._project["features"] = [
                f for f in self._project["features"]
                if not (f.get("properties", {}).get("element_type")
                        == "property_boundary"
                        and f["properties"].get("boundary_id") == bid)
            ]
            self._redo_stack.append(entry)
            self.statusBar().showMessage("Undo: removed boundary", 2000)

        elif action == "place_contour":
            elev = float(entry.get("elevation_m") or 0.0)
            self.map_widget.run_js(f"undoLastContour({elev});")
            kept = []
            removed = False
            for f in reversed(self._project["features"]):
                props = f.get("properties", {})
                if (not removed
                        and props.get("element_type") == "contour_line"
                        and abs(float(props.get("elevation_m") or 0.0)
                                - elev) < 1e-3):
                    removed = True
                else:
                    kept.append(f)
            self._project["features"] = list(reversed(kept))
            self._redo_stack.append(entry)
            self.statusBar().showMessage(
                f"Undo: removed contour at {elev:.1f}m", 2000
            )

        elif action == "place_hedgerow":
            import json as _json
            hid = entry["hedge_id"]
            self.map_widget.run_js(
                f"undoHedgerowById({_json.dumps(hid)});"
            )
            self._project["features"] = [
                f for f in self._project["features"]
                if f.get("properties", {}).get("hedge_id") != hid
            ]
            self._redo_stack.append(entry)
            self.statusBar().showMessage("Undo: removed hedgerow", 2000)

        elif action == "place_custom_shape":
            import json as _json
            sid = entry["shape_id"]
            self.map_widget.run_js(
                f"undoCustomShapeById({_json.dumps(sid)});"
            )
            self._project["features"] = [
                f for f in self._project["features"]
                if f.get("properties", {}).get("shape_id") != sid
            ]
            self._redo_stack.append(entry)
            label = entry.get("label") or entry.get("shape_type") or "shape"
            self.statusBar().showMessage(f"Undo: removed {label}", 2000)

        elif action == "move_plant":
            # Reverse a singleton drag: snap the marker (and project
            # state) back to its old lat/lng.
            pid     = entry["plant_id"]
            old_lat = float(entry["old_lat"])
            old_lng = float(entry["old_lng"])
            new_lat = float(entry["new_lat"])
            new_lng = float(entry["new_lng"])
            self.map_widget.run_js(
                f"(function() {{"
                f"  var keys = Object.keys(plantMarkers);"
                f"  for (var i = keys.length - 1; i >= 0; i--) {{"
                f"    var m = plantMarkers[keys[i]];"
                f"    if (m._pd && m._pd.plantId === {pid}"
                f"        && Math.abs(m._pd.lat - {new_lat}) < 1e-7"
                f"        && Math.abs(m._pd.lng - {new_lng}) < 1e-7) {{"
                f"      m.setLatLng([{old_lat}, {old_lng}]);"
                f"      m._pd.lat = {old_lat}; m._pd.lng = {old_lng};"
                f"      var lbl = plantLabels[keys[i]];"
                f"      if (lbl) lbl.setLatLng([{old_lat}, {old_lng}]);"
                f"      break;"
                f"    }}"
                f"  }}"
                f"}})()"
            )
            for p in self._placed_plants:
                if (p["plant_id"] == pid
                        and abs(p["lat"] - new_lat) < 1e-7
                        and abs(p["lng"] - new_lng) < 1e-7):
                    p["lat"] = old_lat
                    p["lng"] = old_lng
                    break
            for f in self._project["features"]:
                props = f.get("properties", {})
                coords = f.get("geometry", {}).get("coordinates", [])
                if (props.get("element_type") == "plant"
                        and props.get("plant_id") == pid
                        and coords
                        and abs(coords[1] - new_lat) < 1e-7
                        and abs(coords[0] - new_lng) < 1e-7):
                    f["geometry"]["coordinates"] = [old_lng, old_lat]
                    break
            self._redo_stack.append(entry)
            self.statusBar().showMessage("Undo: plant move", 2000)

        elif action == "move_plant_group":
            import json as _json
            originals = entry.get("originals") or []
            moved     = entry.get("moved") or []
            moved_by_id = {m.get("markerId"): m for m in moved}
            # Reverse direction in JS: snap each marker back from its
            # moved position to its original.
            for orig in originals:
                mid = orig.get("markerId")
                new = moved_by_id.get(mid)
                if not new:
                    continue
                pid = int(orig.get("plantId") or 0)
                ol  = float(orig.get("lat") or 0.0)
                og  = float(orig.get("lng") or 0.0)
                nl  = float(new.get("lat") or 0.0)
                ng  = float(new.get("lng") or 0.0)
                self.map_widget.run_js(
                    f"(function() {{"
                    f"  var keys = Object.keys(plantMarkers);"
                    f"  for (var i = keys.length - 1; i >= 0; i--) {{"
                    f"    var m = plantMarkers[keys[i]];"
                    f"    if (m._pd && m._pd.plantId === {pid}"
                    f"        && Math.abs(m._pd.lat - {nl}) < 1e-7"
                    f"        && Math.abs(m._pd.lng - {ng}) < 1e-7) {{"
                    f"      m.setLatLng([{ol}, {og}]);"
                    f"      m._pd.lat = {ol}; m._pd.lng = {og};"
                    f"      var lbl = plantLabels[keys[i]];"
                    f"      if (lbl) lbl.setLatLng([{ol}, {og}]);"
                    f"      break;"
                    f"    }}"
                    f"  }}"
                    f"}})()"
                )
                for p in self._placed_plants:
                    if (p["plant_id"] == pid
                            and abs(p["lat"] - nl) < 1e-7
                            and abs(p["lng"] - ng) < 1e-7):
                        p["lat"] = ol
                        p["lng"] = og
                        break
                for f in self._project["features"]:
                    props = f.get("properties", {})
                    coords = f.get("geometry", {}).get("coordinates", [])
                    if (props.get("element_type") == "plant"
                            and props.get("plant_id") == pid
                            and coords
                            and abs(coords[1] - nl) < 1e-7
                            and abs(coords[0] - ng) < 1e-7):
                        f["geometry"]["coordinates"] = [og, ol]
                        break
            self._redo_stack.append(entry)
            self.statusBar().showMessage(
                f"Undo: polyculture move ({len(originals)} plants)", 2000
            )

        self._act_undo.setEnabled(bool(self._undo_stack))
        self._act_redo.setEnabled(bool(self._redo_stack))
        self._mark_modified()

    def _do_redo(self):
        if not self._redo_stack:
            return
        entry = self._redo_stack.pop()
        action = entry["action"]

        if action == "place_plant":
            pid = entry["plant_id"]
            name = entry["common_name"]
            lat, lng = entry["lat"], entry["lng"]
            spacing_m, plant_type, custom_color = self._plant_info(pid)
            self.map_widget.load_plant_marker(
                pid, name, lat, lng, spacing_m, plant_type, custom_color
            )
            self._placed_plants.append({
                "plant_id": pid, "common_name": name, "lat": lat, "lng": lng
            })
            self._project["features"].append({
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [lng, lat]},
                "properties": {
                    "element_type": "plant",
                    "plant_id": pid,
                    "common_name": name,
                    "quantity": 1
                }
            })
            self.plant_panel.on_plant_placed(pid, name)
            self._undo_stack.append(entry)
            self.statusBar().showMessage("Redo: placed plant", 2000)

        self._act_undo.setEnabled(bool(self._undo_stack))
        self._act_redo.setEnabled(bool(self._redo_stack))
        self._mark_modified()

    # ── Window close ─────────────────────────────────────────────────────────

    # ── LOAD-BEARING RESIZE HANDLERS ─────────────────────────────────────
    # Both event handlers below are critical infrastructure for the map
    # resize / maximise behaviour on Windows. See the matching block
    # comment in src/map_widget.py above MapWidget.invalidate_size for
    # the full story. Short version: the _dbg() file I/O inside these
    # handlers and the singleShot(0) invalidate in changeEvent together
    # give Chromium's renderer enough scheduling slack to commit its new
    # viewport before Leaflet measures the container. Don't trim them.
    # ─────────────────────────────────────────────────────────────────────

    def changeEvent(self, event):
        # Qt fires WindowStateChange on F11/maximise/restore. The embedded
        # QWebEngineView doesn't always get its own resizeEvent in the same
        # frame, so Leaflet's canvas renderer can cache a stale 0x0 size and
        # paint into nothing. Posting invalidate_size on the next event-loop
        # tick lets Qt finish the state transition first.
        if event.type() == QEvent.Type.WindowStateChange:
            try:
                # _dbg() is load-bearing here, not diagnostic: the file
                # write yields to the OS scheduler and lets Chromium
                # propagate the new viewport before invalidate_size runs.
                from src.map_widget import _dbg
                _dbg(f"[mainwindow] WindowStateChange state={int(self.windowState())} "
                     f"size={self.width()}x{self.height()}")
            except Exception:
                pass
            QTimer.singleShot(0, self.map_widget.invalidate_size)
        super().changeEvent(event)

    def resizeEvent(self, event):
        # The override exists for the same load-bearing reason as the
        # _dbg() call inside: the Python frame + file syscall together
        # introduce just enough scheduling delay for Chromium's IPC to
        # land between Qt's resize and super().resizeEvent propagating
        # the new size down to MapWidget. Removing the override (or just
        # the _dbg call) reintroduces the half-painted-map symptom on
        # Windows after a maximise with LiDAR contours visible.
        try:
            from src.map_widget import _dbg
            sz = event.size()
            _dbg(f"[mainwindow] resizeEvent w={sz.width()} h={sz.height()} "
                 f"state={int(self.windowState())}")
        except Exception:
            pass
        super().resizeEvent(event)

    def closeEvent(self, event):
        if self._modified:
            r = QMessageBox.question(
                self, "Exit",
                "You have unsaved changes. Exit anyway?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel
            )
            if r != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
        event.accept()

    # ── Keyboard shortcuts ────────────────────────────────────────────────────

    def keyPressEvent(self, event):
        key = event.key()
        if key == Qt.Key.Key_Escape:
            self._cancel_draw()
            self.map_widget.run_js("clearSelection();")
        elif key == Qt.Key.Key_Delete or key == Qt.Key.Key_Backspace:
            # Delete every currently-selected map item (across types).
            self.map_widget.run_js("deleteSelected();")
        elif key == Qt.Key.Key_B and not event.modifiers():
            self._enter_boundary_mode()
        elif key == Qt.Key.Key_P and not event.modifiers():
            # Switch to Plants tab
            self._side_tabs.setCurrentWidget(self.plant_panel)
        elif key == Qt.Key.Key_G and not event.modifiers():
            # Switch to Polycultures tab
            self._side_tabs.setCurrentWidget(self.polyculture_panel)
        elif key == Qt.Key.Key_S and not event.modifiers():
            # Switch to Structures tab
            self._side_tabs.setCurrentWidget(self.structure_panel)
        elif key == Qt.Key.Key_A and not event.modifiers():
            # Switch to Analysis tab
            self._side_tabs.setCurrentWidget(self.analysis_panel)
        elif key == Qt.Key.Key_T and not event.modifiers():
            # Switch to Planning tab
            self._side_tabs.setCurrentWidget(self.planning_panel)
        elif key == Qt.Key.Key_M and not event.modifiers():
            self._enter_measure_mode()
        elif key == Qt.Key.Key_N and not event.modifiers():
            self._enter_annotate_mode()
        elif key == Qt.Key.Key_L and not event.modifiers():
            # Toggle map legend
            self.map_widget.run_js("toggleLegend();")
        else:
            super().keyPressEvent(event)

    def _clear_undo(self):
        """Clear undo/redo stacks (e.g. on New/Open project)."""
        self._undo_stack.clear()
        self._redo_stack.clear()
        self._act_undo.setEnabled(False)
        self._act_redo.setEnabled(False)


# ── Helper widgets ────────────────────────────────────────────────────────────

def _fmt_time(decimal_hour: float) -> str:
    """Format a decimal hour (e.g. 6.5) as '6:30 AM'."""
    h = int(decimal_hour)
    m = int((decimal_hour - h) * 60)
    ampm = "AM" if h < 12 else "PM"
    h12 = h % 12 or 12
    return f"{h12}:{m:02d} {ampm}"


def _vsep() -> QWidget:
    """Thin vertical separator widget for the status bar."""
    w = QWidget()
    w.setFixedWidth(1)
    w.setStyleSheet("background: #37474f;")
    return w


# ── Application-wide stylesheet ───────────────────────────────────────────────

_APP_STYLE = """
QMainWindow, QWidget {
    background-color: #1a2a1a;
    color: #c8e6c9;
    font-family: 'Segoe UI', 'Arial', sans-serif;
    font-size: 13px;
}

QMenuBar {
    background-color: #1b2b1b;
    color: #c8e6c9;
    border-bottom: 1px solid #2e4a2e;
}
QMenuBar::item:selected {
    background-color: #2e4a2e;
}
QMenu {
    background-color: #1e2e1e;
    color: #c8e6c9;
    border: 1px solid #2e4a2e;
}
QMenu::item:selected {
    background-color: #2e4a2e;
}

QToolBar {
    background-color: #1b2b1b;
    border-bottom: 1px solid #2e4a2e;
    spacing: 4px;
    padding: 2px 4px;
}
QToolButton {
    color: #c8e6c9;
    background: transparent;
    border: 1px solid transparent;
    border-radius: 4px;
    padding: 3px 8px;
}
QToolButton:hover {
    background: #2e4a2e;
    border-color: #4a7a4a;
}
QToolButton:checked {
    background: #2e5a2e;
    border-color: #66bb6a;
    color: #a5d6a7;
}

QStatusBar {
    background-color: #152015;
    color: #78909c;
    border-top: 1px solid #2e4a2e;
    font-size: 12px;
}

QSplitter::handle {
    background-color: #2e4a2e;
    width: 2px;
}

QScrollBar:vertical {
    background: #1a2a1a;
    width: 10px;
}
QScrollBar::handle:vertical {
    background: #2e4a2e;
    border-radius: 5px;
}
"""

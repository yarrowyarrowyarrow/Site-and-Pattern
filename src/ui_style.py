"""
ui_style.py — shared Qt stylesheet snippets so panels look consistent.

Keeps the inner sub-tab strip (Plants → Plants/Plant Communities/On This Design,
Site → Site Information/Slope/Shade) identical across panels from one source,
and defines the three button tiers (V2.13):

  * BTN_PRIMARY   — filled green: the step the user came to this section for
                    (Find, Use Pin Drop, Generate, Show shade).
  * BTN_SECONDARY — quiet grey: supporting actions (Refresh, Clear, imports).
  * BTN_DOWNLOAD  — quiet grey outline: heavy offline-data downloads. These
                    used to share the primary fill, which made "fetch ~1 GB"
                    look like the routine next step; the hollow shape + a "⬇"
                    text prefix keep them discoverable without recommending
                    them or out-shouting the secondary buttons beside them.

Panels historically redefined their own copies; new/updated code should import
these instead (site_panel.py migrated in V2.13).
"""

from __future__ import annotations


# The app's base surface — dark green ground, pale text. It normally reaches a
# widget by inheritance from `APP_STYLE` below, which is set on the MainWindow.
# A window that opens *before* the MainWindow exists (the V2.40 start menu) has
# nothing to inherit from and lands on the platform's default light palette,
# where this app's pale-green text is close to invisible. Such a window carries
# this itself. Mirrors the first block of `APP_STYLE` — if that palette moves,
# move it here too.
BASE_SURFACE = (
    "QWidget { background-color: #1a2a1a; color: #c8e6c9; "
    "font-family: 'Segoe UI', 'Arial', sans-serif; font-size: 13px; }"
)

GROUP_STYLE = (
    "QGroupBox { border: 1px solid #2e4a2e; border-radius: 4px; "
    "margin-top: 10px; padding-top: 12px; }"
    "QGroupBox::title { color: #a5d6a7; subcontrol-origin: margin; left: 8px; }"
)

BTN_PRIMARY = (
    "QPushButton { background: #2e7d32; color: #e8f5e9; border: 1px solid #43a047;"
    " border-radius: 4px; padding: 6px; font-weight: bold; }"
    "QPushButton:hover { background: #388e3c; }"
)

BTN_SECONDARY = (
    "QPushButton { background: #37474f; color: #b0bec5; border: 1px solid #546e7a;"
    " border-radius: 4px; padding: 6px; }"
    "QPushButton:hover { background: #455a64; }"
)

# Outline only — deliberately the *quietest* tier. The first cut used a green
# outline, which out-shouted the grey secondary buttons around it; the ⬇ glyph
# and hollow shape carry the "big optional download" meaning on their own.
BTN_DOWNLOAD = (
    "QPushButton { background: transparent; color: #90a4ae; "
    "border: 1px solid #546e7a; border-radius: 4px; padding: 6px; }"
    "QPushButton:hover { background: rgba(84, 110, 122, 0.18); "
    "color: #b0bec5; border-color: #78909c; }"
    "QPushButton:disabled { color: #455a64; border-color: #37474f; }"
)



# ── Whole windows ────────────────────────────────────────────────────────────
# The main window's stylesheet (in app.py until V3.08, when the 3D preview and
# Growth Snapshots started wearing it too).
APP_STYLE = """
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
    color: #90a4ae;
    border-top: 1px solid #2e4a2e;
    font-size: 12px;
}

QSplitter::handle {
    background-color: #2e4a2e;
    width: 2px;
}

QScrollBar:vertical {
    background: #1a2a1a;
    width: 14px;
}
QScrollBar::handle:vertical {
    background: #5a8a5a;
    border-radius: 6px;
    min-height: 24px;
}
"""

# A window of its own (the 3D preview, Growth Snapshots) inherits nothing from
# the MainWindow: it is top-level, so until V3.08 it opened in the platform's
# light palette beside a dark app, and the 3D preview's pale-green edit hint
# (#cfe8d2) sat on near-white at about 1.2:1 (F209). Such a window sets this:
# the app's own surface, and buttons that show when they are on, because the
# preview's View row is checkable buttons.
WINDOW_STYLE = APP_STYLE + """
QPushButton {
    background: #24352b; color: #c8e6c9; border: 1px solid #3a5a3a;
    border-radius: 4px; padding: 4px 8px;
}
QPushButton:hover { border-color: #66bb6a; }
QPushButton:checked { background: #2e5a2e; color: #e8f5e9; border-color: #66bb6a; }
QPushButton:disabled { color: #6b8a72; border-color: #2e4a2e; }
QComboBox {
    background: #1e2e1e; color: #c8e6c9; border: 1px solid #3a5a3a;
    border-radius: 3px; padding: 2px 6px;
}
QComboBox QAbstractItemView {
    background: #1e2e1e; color: #c8e6c9; selection-background-color: #2e5a2e;
}
QLabel { background: transparent; }
"""

# ── The tab hierarchy ────────────────────────────────────────────────────────
# The side panel nests three deep — Plants → On This Design → Stats — and until
# V2.37 every level used `inner_tab_stylesheet()` verbatim, on the stated
# grounds that one look everywhere is consistent. A tester bounced off it: with
# identical size, weight, colour and underline at every level, three stacked
# strips read as three peer toolbars rather than as a path into the app. (The
# top bar was in fact the *tighter* of the two, which inverted the cue.)
#
# So the levels differ deliberately now, and differ by WEIGHT and GROUND rather
# than size: `FillTabWidget` spreads tabs edge-to-edge and the sidebar's
# empirical minimum is 300px at ~11px text, so making the six top-level labels
# bigger would just elide them.
#
#   L1 (top)  bold, on a darker ground, selected tab lifted into the pane colour
#   L2 (sub)  regular, green underline on select — unchanged
#   L3 (leaf) smaller and dimmer, underline only
#
# Don't re-unify these. The sameness was the bug.

def top_tab_stylesheet() -> str:
    """Stylesheet for the **top-level** side-panel tab bar (Site / Plants /
    Structures / Analysis / Planning / Learn).

    Reads as the primary navigation: bold, sitting on its own darker ground,
    with the selected tab lifted into the panel's background colour so it looks
    joined to the content below it rather than underlined like a sub-tab.

    Measured, not guessed. `FillTabWidget(allow_shrink=True)` gives every tab an
    EQUAL share when they'd overflow, so the binding constraint is the widest
    label, not the sum: full labels need `widest × 6`. At 11px that is 456px
    here, against 426px for the pre-V2.37 style — i.e. **the top strip has
    always elided at the sidebar's minimum width**, and the old comment claiming
    300px was sufficient was wrong. ElideRight makes that degrade gracefully and
    the 480px maximum shows everything.

    So the hierarchy is carried by things that cost no width — a darker ground,
    and the selected tab lifting into the pane colour instead of being
    underlined like a sub-tab — plus bold on the SELECTED tab only. Bolding all
    six, or going to 12px, would have pushed the threshold to 500px+.
    """
    return (
        "QTabWidget::pane { border: 1px solid #2e4a2e; background: #1e2a1e; "
        "top: -1px; }"
        "QTabBar { background: #0f1a10; }"
        "QTabBar::tab { background: #0f1a10; color: #8aa08d; "
        "padding: 7px 4px; font-size: 12px; "
        "border: 1px solid transparent; border-bottom: none; }"
        "QTabBar::tab:selected { background: #1e2a1e; color: #c8e6c9; "
        "font-weight: bold; "
        "border: 1px solid #2e4a2e; border-bottom: none; }"
        "QTabBar::tab:hover:!selected { color: #a5d6a7; background: #16241a; }"
    )


def inner_tab_stylesheet() -> str:
    """Stylesheet for a panel's inner ``QTabWidget`` sub-tab strip — the compact
    green underline-on-select look used by the Plants and Site panels."""
    return (
        "QTabWidget::pane { border: none; background: #1e2a1e; }"
        "QTabBar::tab { background: #15251a; color: #90a4ae; "
        "padding: 4px 10px; font-size: 12px; "
        "border-bottom: 2px solid transparent; }"
        "QTabBar::tab:selected { color: #a5d6a7; "
        "border-bottom: 2px solid #66bb6a; }"
        "QTabBar::tab:hover { color: #c8e6c9; }"
    )


def leaf_tab_stylesheet() -> str:
    """Stylesheet for a **third-level** tab strip (Plants → On This Design →
    Plants/Communities/Stats).

    Quieter and smaller than a sub-tab so a third strip reads as detail within
    the second, not as another peer. Replaces the boxed look
    `on_this_design_panel` had invented for itself, which made the deepest level
    the most visually prominent of the three.
    """
    return (
        "QTabWidget::pane { border: none; background: #1e2a1e; }"
        "QTabBar::tab { background: transparent; color: #90a4ae; "
        "padding: 4px 9px; font-size: 12px; "
        "border-bottom: 1px solid transparent; }"
        "QTabBar::tab:selected { color: #cfd8dc; "
        "border-bottom: 1px solid #4a7a4a; }"
        "QTabBar::tab:hover { color: #b0bec5; }"
    )

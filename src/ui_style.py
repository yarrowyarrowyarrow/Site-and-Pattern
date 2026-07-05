"""
ui_style.py — shared Qt stylesheet snippets so panels look consistent.

Keeps the inner sub-tab strip (Plants → Plants/Plant Communities/On This Design,
Site → Site Information/Slope/Shade) identical across panels from one source,
and defines the three button tiers (V2.13):

  * BTN_PRIMARY   — filled green: the step the user came to this section for
                    (Find, Use Pin Drop, Generate, Show shade).
  * BTN_SECONDARY — quiet grey: supporting actions (Refresh, Clear, imports).
  * BTN_DOWNLOAD  — green outline: heavy offline-data downloads. These used to
                    share the primary fill, which made "fetch ~1 GB" look like
                    the routine next step; the outline keeps them discoverable
                    without recommending them. Pair with a "⬇" text prefix.

Panels historically redefined their own copies; new/updated code should import
these instead (site_panel.py migrated in V2.13).
"""

from __future__ import annotations


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

BTN_DOWNLOAD = (
    "QPushButton { background: transparent; color: #81c784; "
    "border: 1px solid #2e7d32; border-radius: 4px; padding: 6px; }"
    "QPushButton:hover { background: rgba(46, 125, 50, 0.18); "
    "border-color: #43a047; }"
    "QPushButton:disabled { color: #546e7a; border-color: #37474f; }"
)


def inner_tab_stylesheet() -> str:
    """Stylesheet for a panel's inner ``QTabWidget`` sub-tab strip — the compact
    green underline-on-select look used by the Plants and Site panels."""
    return (
        "QTabWidget::pane { border: none; background: #1e2a1e; }"
        "QTabBar::tab { background: #15251a; color: #90a4ae; "
        "padding: 4px 10px; font-size: 11px; "
        "border-bottom: 2px solid transparent; }"
        "QTabBar::tab:selected { color: #a5d6a7; "
        "border-bottom: 2px solid #66bb6a; }"
        "QTabBar::tab:hover { color: #c8e6c9; }"
    )

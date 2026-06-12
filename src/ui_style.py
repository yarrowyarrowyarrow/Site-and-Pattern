"""
ui_style.py — shared Qt stylesheet snippets so panels look consistent.

Keeps the inner sub-tab strip (Plants → Plants/Plant Communities/On This Design,
Site → Site Information/Slope/Shade) identical across panels from one source.
"""

from __future__ import annotations


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

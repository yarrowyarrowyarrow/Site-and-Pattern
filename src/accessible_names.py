"""
accessible_names.py — names for the containers a screen reader passes through
(F195, V3.02).

A control's name belongs where it is built, and V3.02 named about forty there.
These are the containers no single panel builds: each panel's scroll area,
which takes a Tab stop so a keyboard user can page through text no control
leads to, and the tab widgets, which hand focus to their tab bars but stay in
the tree as the bars' parents. Both reached Orca as an unnamed "filler",
twice on every side tab. They are named after the tab they sit in, once the
window is built, so a new panel is covered without remembering to be.
"""

from __future__ import annotations

from typing import Optional

from PyQt6.QtWidgets import QScrollArea, QStackedWidget, QTabWidget, QWidget


def name_containers(window: QWidget) -> int:
    """Name each unnamed scroll area and tab widget after the tab it sits in;
    return how many.

    A panel's scroll area takes a Tab stop, which lets a keyboard user page
    through text no control leads to (Site Info's climate figures), and a
    screen reader announced it as an unnamed "filler" (V3.02). A tab widget
    hands its focus to its tab bar, but stays in the tree as the tab bar's
    unnamed parent, so a reader moving through the panel met a "filler" there
    too: the Plants tab's sections now read as "Plants"."""
    named = 0
    for tabs in window.findChildren(QTabWidget):
        for i in range(tabs.count()):
            page = tabs.widget(i)
            title = tabs.tabText(i).replace("&", "")
            inside = page.findChildren(QScrollArea) + page.findChildren(QTabWidget)
            for widget in ([page] if isinstance(page, (QScrollArea, QTabWidget))
                           else []) + inside:
                if widget.accessibleName() or _tab_owner(widget) is not tabs:
                    continue
                widget.setAccessibleName(title)
                named += 1
    return named


def _tab_owner(widget: QWidget) -> Optional[QTabWidget]:
    """The nearest tab widget ``widget`` is a page of, or inside a page of."""
    parent = widget.parentWidget()
    while parent is not None:
        grand = parent.parentWidget()
        if isinstance(parent, QStackedWidget) and isinstance(grand, QTabWidget):
            return grand
        parent = grand
    return None

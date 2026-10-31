"""
advanced_tools_flow.py — apply the Advanced tools switch to the window
(V3.21, MD-1; the registry and the reasons are in ``src/advanced_tools.py``).

``apply(main)`` walks the registry and shows or hides each surface: a page by
its tab (``QTabWidget.setTabVisible``, found by widget, never by index: the
rule of ``side_panel_layout``), a menu action by its object name, a toolbar
item by its action, a control by itself, and a hook by its
``set_advanced_tools``. Called once the window is built and again whenever
the switch changes. It touches nothing in the design or the undo stack.

Wired from ``MainWindow`` through lambdas (MainWindow is at its method
ceiling).
"""

from __future__ import annotations

from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QPushButton, QTabWidget, QToolBar, QWidget,
)

from src import advanced_tools
from src.side_panel_layout import tab_owner


def resolve(main, path: str):
    """The object at ``path`` (``"site_panel.slope_page"``) from ``main``,
    or ``None`` when any step is missing."""
    obj = main
    for part in path.split("."):
        obj = getattr(obj, part, None)
        if obj is None:
            return None
    return obj


def _toolbar_action(item):
    """The action a toolbar shows ``item`` by: the item itself if it is an
    action, else the action a toolbar made for the widget."""
    if isinstance(item, QAction):
        return item
    bar = item.parentWidget() if isinstance(item, QWidget) else None
    if isinstance(bar, QToolBar):
        for act in bar.actions():
            if bar.widgetForAction(act) is item:
                return act
    return None


def _show_page(page: QWidget, on: bool, strips: set) -> None:
    tabs = tab_owner(page)
    if tabs is None:
        return
    tabs.setTabVisible(tabs.indexOf(page), on)
    strips.add(tabs)


def _settle(tabs: QTabWidget) -> None:
    """A strip whose page went shows its first visible one, and a strip
    with no page left to show leaves its own tab, if it is one."""
    shown = [i for i in range(tabs.count()) if tabs.isTabVisible(i)]
    if shown and not tabs.isTabVisible(tabs.currentIndex()):
        tabs.setCurrentIndex(shown[0])
    outer = tab_owner(tabs)
    if outer is not None:
        outer.setTabVisible(outer.indexOf(tabs), bool(shown))
        _settle(outer)


def apply(main, on=None) -> None:
    """Show the advanced tools when ``on`` (default: the remembered switch),
    hide them otherwise."""
    on = advanced_tools.is_on() if on is None else bool(on)
    if not on:
        _disarm(main)
    strips: set = set()
    for path in advanced_tools.ADVANCED_PAGES:
        page = resolve(main, path)
        if isinstance(page, QWidget):
            _show_page(page, on, strips)
    for tabs in strips:
        _settle(tabs)
    for name in advanced_tools.ADVANCED_ACTIONS:
        act = main.findChild(QAction, name)
        if act is not None:
            act.setVisible(on)
    for path in advanced_tools.ADVANCED_TOOLBAR_ITEMS:
        act = _toolbar_action(resolve(main, path))
        if act is not None:
            act.setVisible(on)
    for path in advanced_tools.ADVANCED_CONTROLS:
        box = resolve(main, path)
        if isinstance(box, QWidget):
            box.setVisible(on)
    for path in advanced_tools.ADVANCED_HOOKS:
        target = resolve(main, path)
        if target is not None and hasattr(target, "set_advanced_tools"):
            target.set_advanced_tools(on)
    switch = getattr(main, "_act_advanced", None)
    if switch is not None and switch.isChecked() != on:
        blocked = switch.blockSignals(True)
        switch.setChecked(on)
        switch.blockSignals(blocked)
    refresh_bar(main)


def set_and_apply(main, on: bool) -> None:
    """The View menu's switch: remember it, then apply it."""
    advanced_tools.set_on(on)
    apply(main, on)


def _disarm(main) -> None:
    """A tool the switch is about to hide is not left armed: Measure or a
    map note in progress is cancelled, as Esc would."""
    bar = getattr(main, "toolbar", None)
    armed = [getattr(bar, name, None)
             for name in ("_act_measure", "_act_annotate")]
    if any(a is not None and a.isChecked() for a in armed):
        bar._on_cancel()


def install(main, view_menu) -> None:
    """Add View → Advanced tools. The window calls :func:`apply` once
    everything the registry names exists (the plant page comes last)."""
    act = view_menu.addAction(f"{advanced_tools.NAME}")
    act.setObjectName("view_advanced_tools")
    act.setCheckable(True)
    act.setStatusTip(
        "Show the tools for terrain, wind, habitat analysis, 3D and "
        "presentations. Your design is the same either way.")
    act.triggered.connect(lambda checked: set_and_apply(main, checked))
    main._act_advanced = act


# ── "This design uses advanced tools." (MD-3) ───────────────────────────────

class AdvancedBar(QFrame):
    """One line above the map, in simple mode only, when the open design
    holds something the advanced tools made: what it holds still draws,
    selects, prints and undoes; the bar says where its tools went."""

    def __init__(self, main):
        super().__init__(main)
        self.setObjectName("advancedBar")
        self.setAccessibleName("Advanced tools notice")
        self.setStyleSheet(
            "QFrame#advancedBar { background: #1e2e1e; "
            "border-bottom: 1px solid #2e4a2e; }"
            "QLabel { color: #c8e6c9; font-size: 13px; }")
        row = QHBoxLayout(self)
        row.setContentsMargins(10, 4, 10, 4)
        self.label = QLabel(advanced_tools.BAR_TEXT)
        row.addWidget(self.label, 1)
        self.show_btn = QPushButton("Show them")
        self.show_btn.setStyleSheet(
            "QPushButton { background: #2e4a2e; color: #e8f5e9; border: none; "
            "border-radius: 4px; padding: 3px 12px; font-size: 13px; }"
            "QPushButton:focus { border: 2px solid #ffe082; }")
        self.show_btn.clicked.connect(lambda: _show_them(main))
        row.addWidget(self.show_btn)
        self.found: list = []
        self.hide()


def make_bar(main) -> AdvancedBar:
    """The bar, for the map's column (beside the map, never inside it: the
    web view's accessible interface reports only the page)."""
    main.advanced_bar = AdvancedBar(main)
    return main.advanced_bar


def refresh_bar(main) -> None:
    """Show the bar when the design holds advanced work and the switch is
    off; hide it otherwise. Called on open, undo and every switch."""
    bar = getattr(main, "advanced_bar", None)
    if bar is None:
        return
    bar.found = advanced_tools.uses_advanced(getattr(main, "_project", None))
    bar.setToolTip("This design has " + ", ".join(bar.found) + "."
                   if bar.found else "")
    bar.setVisible(bool(bar.found) and not advanced_tools.is_on())


def _show_them(main) -> None:
    """Turn the switch on, and open the Slope page when the design has
    contours, which is the page that made them."""
    found = list(getattr(main.advanced_bar, "found", []))
    set_and_apply(main, True)
    if "contours or a slope map" in found:
        from src.keyboard_help import show_panel
        show_panel(main.site_panel.slope_page)

"""
keyboard_help.py — every key the app answers to, in one table (F195, V3.02).

The V2.98 review found nine single-letter shortcuts, and Delete, acting from
anywhere in the window and listed nowhere: with keyboard focus on a button in
the side panel, B started drawing a boundary and A switched tabs (measured
again on V3.01), and typing a plant's name into the wrong place did both. They
now act only while the map has focus, which is WCAG 2.1.4's "active only on
focus", and Help → Keyboard shortcuts lists them from :data:`MAP_LETTERS`, the
table the window's key handler reads, so the list cannot drift from the keys.

Two of them did nothing at all: P and G called ``setCurrentWidget`` on the
side tabs with a panel that sits inside the Plants tab (Placement since
V3.07), which Qt ignores. :func:`show_panel` opens every tab level a panel is
nested in.
"""

from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import QObject, Qt
from PyQt6.QtWidgets import (
    QApplication, QDialog, QDialogButtonBox, QLabel, QStackedWidget,
    QTabWidget, QVBoxLayout, QWidget,
)

#: Single keys the map answers to while it has focus: ``(key, action, words)``.
#: ``action`` names what the window does; the window maps it to a method.
MAP_LETTERS: tuple = (
    ("B", "boundary", "Draw the property boundary"),
    ("M", "measure", "Measure a distance"),
    ("N", "note", "Pin a note"),
    ("L", "legend", "Show or hide the map legend"),
    ("P", "plants", "Go to Placement: Plants"),
    ("G", "communities", "Go to Placement: Communities"),
    ("S", "structures", "Go to Placement: Structures"),
    # D since V3.07, when Analysis became Design (it was A).
    ("D", "design", "Go to Design"),
    ("T", "planning", "Go to Planning"),
)

#: The map's own keys (html/map/09-keyboard.js, Leaflet), and the two the
#: window answers only while the map has focus.
MAP_KEYS: tuple = (
    ("F6", "Move between the map and the side panel, back to where you were"),
    ("Tab", "Move to the map, and on through its controls"),
    ("Arrow keys", "Pan the map"),
    ("+  and  −", "Zoom in and out"),
    ("Enter", "With a tool chosen, act at the centre of the map: place, add a "
              "corner, measure, pin a note"),
    ("Shift+Enter", "Finish a boundary, hedgerow, shape, fill area or contour"),
    ("Esc", "Stop placing or drawing"),
    ("Delete, Backspace", "Delete what is selected on the map"),
)

#: Keys in the lists and pages.
LIST_KEYS: tuple = (
    ("Enter", "In a plant list: place the plant. In the community builder: "
              "add it to the community"),
    ("→", "In Browse: open the plant's page; Esc closes it"),
    ("Enter, Space", "In Design › Planted: frame the row on the map"),
    ("Delete", "In the builder's Members: remove the member"),
    ("Menu key, Shift+F10", "Open a row's menu"),
    ("↑, ↓, Space", "Open a filter's list; Space ticks a value in it"),
)


def letter_action(event) -> str:
    """The :data:`MAP_LETTERS` action for an unmodified key press, or ``""``."""
    if event.modifiers() not in (Qt.KeyboardModifier.NoModifier,
                                 Qt.KeyboardModifier.KeypadModifier):
        return ""
    for key, action, _words in MAP_LETTERS:
        if event.key() == getattr(Qt.Key, f"Key_{key}"):
            return action
    return ""


def map_has_focus(map_widget: QWidget) -> bool:
    """Whether a key press belongs to the map: it has focus, or nothing does
    (nothing to have typed into). A key that reached the window from a button,
    a list or a tab bar in a panel does not."""
    focus = QApplication.focusWidget()
    if focus is None:
        return True
    return focus is map_widget or map_widget.isAncestorOf(focus)


class PaneSwitch(QObject):
    """F6 and Shift+F6: between the map and the side panel.

    V3.02's keyboard walk took 18 presses of Tab to get from the plant list to
    the map while placing (the placement bar, both toolbars, then the map),
    which is the trip a keyboard user makes for every plant. F6 is the key
    that moves between the panes of a window on Windows and in browsers. It
    returns to the control you left in the panel, so list, map, list is two
    presses; from anywhere else it goes to the map."""

    def __init__(self, window: QWidget, map_widget: QWidget, panel: QWidget):
        from PyQt6.QtGui import QKeySequence, QShortcut
        super().__init__(window)
        self._map, self._panel = map_widget, panel
        self._last: Optional[QWidget] = None
        QApplication.instance().focusChanged.connect(self._remember)
        for key in ("F6", "Shift+F6"):
            QShortcut(QKeySequence(key), window).activated.connect(self.switch)

    def _remember(self, _old, new):
        if new is not None and self._panel.isAncestorOf(new):
            self._last = new

    def switch(self) -> None:
        if not map_has_focus(self._map) or QApplication.focusWidget() is None:
            self._map.focus_by_keyboard()
            return
        back = self._last
        if (back is None or _gone(back) or not back.isVisible()
                or not back.isEnabled()):
            back = self._panel.focusProxy() or self._panel
        back.setFocus(Qt.FocusReason.ShortcutFocusReason)


def _gone(widget: QWidget) -> bool:
    try:
        from PyQt6 import sip
    except ImportError:                                     # pragma: no cover
        import sip                                          # type: ignore
    return sip.isdeleted(widget)


def show_panel(widget: QWidget) -> None:
    """Bring ``widget`` to the front through every tab widget it sits in, from
    the outside in. ``setCurrentWidget`` on one tab widget ignores a widget
    that is a page of a tab widget inside it, which is how P and G did
    nothing."""
    chain = []
    child, parent = widget, widget.parentWidget()
    while parent is not None:
        tabs = parent.parentWidget()
        if isinstance(parent, QStackedWidget) and isinstance(tabs, QTabWidget):
            chain.append((tabs, child))
        child, parent = parent, parent.parentWidget()
    for tabs, page in reversed(chain):
        tabs.setCurrentWidget(page)


def distinct_keys(sequences) -> list:
    """``sequences`` with each key once, in order. Qt keeps a duplicate, calls
    the two ambiguous, and fires neither: Redo listed Ctrl+Shift+Z itself and
    again inside the platform's Redo keys, and the key did nothing."""
    from PyQt6.QtGui import QKeySequence
    out, seen = [], set()
    for seq in sequences:
        text = seq.toString(QKeySequence.SequenceFormat.PortableText)
        if text and text not in seen:
            seen.add(text)
            out.append(seq)
    return out


def menu_shortcuts(window: QWidget) -> list:
    """``[(keys, words)]`` for every menu action with a shortcut, read from the
    window, so the list says what the menus actually bind."""
    from PyQt6.QtGui import QAction, QKeySequence
    out, seen = [], set()
    for action in window.findChildren(QAction):
        keys = [s.toString(QKeySequence.SequenceFormat.NativeText)
                for s in distinct_keys(action.shortcuts())]
        words = action.text().replace("&", "").rstrip("…").strip()
        if keys and words and (words, tuple(keys)) not in seen:
            seen.add((words, tuple(keys)))
            out.append((", ".join(keys), words))
    return out


def _table(title: str, rows) -> str:
    cells = "".join(
        f"<tr><td style='padding: 2px 14px 2px 0; white-space: nowrap;'>"
        f"<b>{_esc(keys)}</b></td><td style='padding: 2px 0;'>{_esc(words)}</td></tr>"
        for keys, words in rows)
    return (f"<h3 style='margin: 10px 0 4px 0;'>{_esc(title)}</h3>"
            f"<table cellspacing='0'>{cells}</table>")


def _esc(text: str) -> str:
    import html
    return html.escape(str(text))


def help_html(window: Optional[QWidget] = None) -> str:
    """The Keyboard shortcuts page, as rich text."""
    parts = [
        _table("On the map, while it has focus",
               [(k, w) for k, w in MAP_KEYS]
               + [(k, w) for k, _a, w in MAP_LETTERS]),
        _table("In lists and pages", LIST_KEYS),
    ]
    if window is not None:
        menu = menu_shortcuts(window)
        if menu:
            parts.append(_table("Anywhere", menu))
    note = ("<p style='margin-top: 10px;'>The single letters act only while the "
            "map has focus, so typing in a panel never starts a tool. Tab moves "
            "between controls; the yellow ring shows where you are.</p>")
    return "".join(parts) + note


def show_shortcuts(window: QWidget) -> QDialog:
    """Help → Keyboard shortcuts."""
    from PyQt6.QtWidgets import QScrollArea
    dialog = QDialog(window)
    dialog.setWindowTitle("Keyboard shortcuts")
    dialog.setMinimumWidth(560)
    layout = QVBoxLayout(dialog)
    page = QLabel(help_html(window))
    page.setTextFormat(Qt.TextFormat.RichText)
    page.setWordWrap(True)
    page.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse
                                 | Qt.TextInteractionFlag.TextSelectableByKeyboard)
    page.setAccessibleName("Keyboard shortcuts")
    # Room for the focus ring, which is drawn just inside the scroll area's
    # edge and sat over the first letter of every line without it.
    page.setMargin(10)
    # It is 760 px tall at the default font: on a 768 px laptop screen, or
    # with larger text, it scrolls rather than losing its last rows.
    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QScrollArea.Shape.NoFrame)
    scroll.setWidget(page)
    scroll.setAccessibleName("Keyboard shortcuts")
    layout.addWidget(scroll)
    buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
    buttons.rejected.connect(dialog.reject)
    layout.addWidget(buttons)
    screen = window.screen() if window is not None else None
    if screen is not None:
        room = screen.availableGeometry()
        dialog.resize(max(560, min(640, room.width() - 40)),
                      min(page.sizeHint().height() + 80, room.height() - 60))
    dialog.show()
    return dialog

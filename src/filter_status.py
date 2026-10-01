"""
filter_status.py — what is narrowing a plant list, and why it came back empty
(F194, V3.01).

Design principle P9 — see docs/DESIGN_PHILOSOPHY.md.

Two widgets the plant picker (``src/plant_picker.py``) draws over its list.
Neither runs a search; the picker does that and hands them words.

  * :class:`FilterLine` — Filters ▸, then one chip per restriction that is on,
    each removing its own ("Type: Tree or Shrub ×"), then Clear all. Until V3.01
    the line was one string, "Type: Shrub · Native", which said what was on and
    let you take none of it off without reopening its dropdown.
  * :class:`WhyEmpty` — said instead of nothing when no plant passes: which
    restriction emptied the list, and what removing it would bring back. Until
    V3.01 an empty result read "No plants match" over a blank list.
"""

from __future__ import annotations

import html
from typing import Optional

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QLabel, QPushButton, QToolButton, QVBoxLayout, QWidget,
)

from src.flow_layout import FlowLayout

DIM = "color: #a8b8b0; font-size: 12px;"
SMALL_BUTTON = (
    "QToolButton, QPushButton { background: transparent; "
    "color: #c8e6c9; border: 1px solid #2e4a2e; border-radius: 3px; "
    "padding: 2px 8px; font-size: 12px; min-height: 20px; }"
    "QToolButton:checked { border-color: #66bb6a; }"
    "QToolButton:hover, QPushButton:hover { border-color: #4a7a4a; }"
    "QToolButton:focus, QPushButton:focus { border: 2px solid #ffe082; }")
# A filter that is on: the toggles' checked look, as a pill. #e8f5e9 on #2e5a2e
# is 7.1:1.
_ON_CHIP = (
    "QPushButton { background: #2e5a2e; color: #e8f5e9; "
    "border: 1px solid #66bb6a; border-radius: 10px; padding: 2px 8px; "
    "font-size: 12px; min-height: 18px; }"
    "QPushButton:hover { border-color: #a5d6a7; }"
    "QPushButton:focus { border: 2px solid #ffe082; }")
_OFFER = (
    "QPushButton { background: transparent; color: #c8e6c9; text-align: left; "
    "border: 1px solid #2e4a2e; border-radius: 3px; padding: 3px 8px; "
    "font-size: 12px; }"
    "QPushButton:hover { border-color: #66bb6a; }"
    "QPushButton:focus { border: 2px solid #ffe082; }")


def wrapped(tip: str) -> str:
    """A tooltip Qt will wrap. Qt word-wraps only rich text, so a plain
    sentence or three is drawn as one line: the soil pH's ran 1,340 px across
    a 1,366 px screen, over the map. A screen reader is given the plain text
    (``setAccessibleDescription``), not this."""
    return f"<p>{html.escape(tip)}</p>" if tip else tip


def _button(text: str, style: str) -> QPushButton:
    btn = QPushButton(text)
    btn.setStyleSheet(style)
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    return btn


class FilterLine(QWidget):
    """Filters ▸, a chip per restriction that is on, Clear all; wrapping at the
    width there is."""

    #: A chip's ×: carries the restriction's key ("type", "native_only", "soil").
    remove_requested = pyqtSignal(str)
    clear_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAccessibleName("Filters on")
        self._flow = FlowLayout(self, h_spacing=4, v_spacing=4)
        self._flow.setContentsMargins(0, 0, 0, 0)
        self._entries: list = []
        self._chips: list = []

        self.filters_button = QToolButton()
        self.filters_button.setCheckable(True)
        self.filters_button.setAccessibleName("Filters")
        self.filters_button.setToolTip("Show or hide the filters")
        self.filters_button.setStyleSheet(SMALL_BUTTON)
        self.filters_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self._flow.addWidget(self.filters_button)
        self.none_label = QLabel("None on")
        self.none_label.setAccessibleName("No filters on")
        self.none_label.setStyleSheet(DIM + " padding: 3px 2px;")
        self._flow.addWidget(self.none_label)
        self.clear_button = _button("Clear all", SMALL_BUTTON)
        self.clear_button.setAccessibleName("Clear all filters")
        self.clear_button.setToolTip(
            "Remove every filter, your soil's pH included")
        self.clear_button.clicked.connect(self.clear_requested)
        self._flow.addWidget(self.clear_button)
        self.clear_button.hide()

    def set_entries(self, entries: list, tips: Optional[dict] = None):
        """Show ``[(key, words), ...]`` as chips. Rebuilt only when that list
        changes, so a search typed while a chip has focus does not pull the
        chip out from under the keyboard."""
        entries = list(entries)
        if entries != self._entries:
            # The window's focus widget, not hasFocus(): that is true only
            # while the window is active, and the chip still owns the keyboard
            # in a window that is not.
            holder = self.window()
            focused = next((i for i, c in enumerate(self._chips)
                            if holder.focusWidget() is c), None)
            for chip in self._chips:
                self._flow.removeWidget(chip)
                chip.hide()
                chip.deleteLater()
            self._flow.removeWidget(self.clear_button)
            self._chips = []
            for key, words in entries:
                chip = _button(f"{words}  ×", _ON_CHIP)
                chip.setAccessibleName(f"Remove {words}")
                chip.clicked.connect(
                    lambda _c=False, k=key: self.remove_requested.emit(k))
                self._flow.addWidget(chip)
                self._chips.append(chip)
            self._flow.addWidget(self.clear_button)
            self._entries = entries
            # A widget made after its window joins the end of the tab chain,
            # which put the chips after the plant list. Tab follows the line.
            chain = [self.filters_button] + self._chips + [self.clear_button]
            for before, after in zip(chain, chain[1:]):
                QWidget.setTabOrder(before, after)
            if focused is not None:
                # The chip that had the keyboard took itself off: hand focus to
                # the one now in its place, or back to Filters, never to nothing.
                target = (self._chips[min(focused, len(self._chips) - 1)]
                          if self._chips else self.filters_button)
                target.setFocus(Qt.FocusReason.OtherFocusReason)
            self._flow.invalidate()
        tips = tips or {}
        for (key, _words), chip in zip(self._entries, self._chips):
            tip = tips.get(key, "Remove this filter")
            chip.setToolTip(wrapped(tip))
            chip.setAccessibleDescription(tip)
        self.none_label.setVisible(not entries)
        cleared = not entries and self.window().focusWidget() is self.clear_button
        self.clear_button.setVisible(bool(entries))
        if cleared:
            # Clear all hides itself once nothing is on; Qt would hand the
            # keyboard to the next control in the window, on the map's toolbar.
            self.filters_button.setFocus(Qt.FocusReason.OtherFocusReason)

    def texts(self) -> list:
        """The chips' words without their ×: what is on, as drawn."""
        return [words for _key, words in self._entries]

    def chips(self) -> list:
        return list(self._chips)


class WhyEmpty(QWidget):
    """What emptied a plant list, and an offer for each restriction whose
    removal would bring plants back. Hidden while the list has plants."""

    remove_requested = pyqtSignal(str)
    clear_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAccessibleName("Why nothing matches")
        col = QVBoxLayout(self)
        col.setContentsMargins(0, 2, 0, 4)
        col.setSpacing(4)
        self.label = QLabel("")
        self.label.setWordWrap(True)
        self.label.setStyleSheet(DIM)
        self.label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse)
        col.addWidget(self.label)
        self._offers: list = []
        self.hide()

    def explain(self, on: list, options: list, *, tab_between=None):
        """``on`` is every restriction that is on, ``[(key, words), ...]``;
        ``options`` those that would bring plants back if removed, as
        ``[(count, key, words), ...]``, most first. ``tab_between`` is the
        ``(before, after)`` pair the offers sit between on screen: made now,
        they would otherwise join the end of the tab chain, after the list."""
        self.dismiss()
        if len(on) == 1 and on[0][0] == "query":
            text = f"No plant’s name or role contains “{on[0][1]}”."
        elif len(on) == 1:
            text = f"No plant passes “{on[0][1]}”."
        elif options:
            text = "No plant passes all of these together. Remove one:"
        else:
            text = ("No plant passes all of these together, and removing any "
                    "one still leaves none: it is the combination.")
        self.label.setText(text)
        for n, key, words in options[:6]:
            plants = f"{n} plant{'s' if n != 1 else ''}"
            label = (f"Clear the search “{words}” ({plants})"
                     if key == "query" else
                     f"Remove “{words}” ({plants})")
            self._offer(label, lambda _c=False, k=key: self.remove_requested.emit(k))
        if not options:
            self._offer("Clear all filters", self.clear_requested)
        if tab_between:
            chain = [tab_between[0]] + self._offers + [tab_between[1]]
            for before, after in zip(chain, chain[1:]):
                QWidget.setTabOrder(before, after)
        self.show()

    def _offer(self, label: str, slot):
        btn = _button(label, _OFFER)
        btn.setAccessibleName(label)
        btn.clicked.connect(slot)
        self.layout().addWidget(btn)
        self._offers.append(btn)

    def dismiss(self):
        for btn in self._offers:
            btn.hide()
            btn.deleteLater()
        self._offers = []
        self.hide()

    def offers(self) -> list:
        """The offers, as drawn."""
        return [b.text() for b in self._offers]

    def buttons(self) -> list:
        return list(self._offers)

    def has_keyboard(self) -> bool:
        focus = self.window().focusWidget()
        return focus is not None and (focus is self or self.isAncestorOf(focus))

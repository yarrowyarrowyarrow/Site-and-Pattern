"""
place_action.py — looking at a list is not placing from it (F191, V2.99).

Both side panels list things to place: plants, and plant communities. From V2.37
until V2.99 *selecting* one armed the map, so every way of looking at one did: a
click on a name, on ▶ to read the card, an arrow key, even keyboard focus arriving
in the list (measured: it armed the first plant in the list, a pond plant). The
next click on the map planted it.

Now a list reports two things, and each panel decides what they mean:

* ``place``: an explicit Place, which is Enter or Return on the list, or a
  double-click. Enter is read as a key here rather than through ``activated``,
  which Qt also emits on a *single* click wherever the style activates items that
  way (KDE's default), so arming from it would come back on those machines alone.
* ``choose``: a finished choice, which is a click that ends on the row it began
  on, or an arrow key onto a row. While the map is placing, a panel switches the
  placement to what was chosen, which keeps the case V2.37 was for: you never
  place "the last thing" once you have chosen another. A press that turns into a
  drag (into the mix) is not a choice, and neither is focus arriving in the list,
  which makes the first row current without selecting it.

* ``read`` (V3.00, plant list only): → (Right arrow) on a row, which opens that
  plant's page and moves into it. Opt-in, because a tree uses → to open a group.

:class:`PlaceButton` is the Place button both panels show: an action named after
what it places, never a toggle. V2.37's toggled, so after Esc it took two clicks
to arm again.

Qt widgets only; no project imports, so both panels can use it without a cycle.
"""

from __future__ import annotations

from PyQt6.QtCore import QEvent, QModelIndex, QObject, Qt, pyqtSignal
from PyQt6.QtWidgets import QPushButton

# Keys that move the current row. A move made with one of them is a choice.
_MOVE_KEYS = frozenset({
    Qt.Key.Key_Up, Qt.Key.Key_Down, Qt.Key.Key_PageUp, Qt.Key.Key_PageDown,
    Qt.Key.Key_Home, Qt.Key.Key_End,
})
_PLACE_KEYS = frozenset({Qt.Key.Key_Return, Qt.Key.Key_Enter})


class ListGestures(QObject):
    """Turns a list or tree view's input into ``place`` and ``choose``.

    Create it after the view has its model: a ``QListView`` swaps its selection
    model in ``setModel``, and this listens to the one it has.
    """

    place = pyqtSignal(QModelIndex)
    choose = pyqtSignal(QModelIndex)
    read = pyqtSignal(QModelIndex)

    def __init__(self, view, *, read_key: bool = False):
        super().__init__(view)
        self._view = view
        self._keyed = False
        self._read_key = read_key
        view.installEventFilter(self)
        view.clicked.connect(self._on_clicked)
        view.doubleClicked.connect(self._on_double_clicked)
        view.selectionModel().currentChanged.connect(self._on_current_changed)

    def eventFilter(self, obj, event):
        kind = event.type()
        if kind == QEvent.Type.KeyPress:
            key = event.key()
            if key in _PLACE_KEYS:
                index = self._view.currentIndex()
                if index.isValid():
                    self.place.emit(index)
                    return True
            elif key in _MOVE_KEYS:
                self._keyed = True
            elif (key == Qt.Key.Key_Right and self._read_key
                    and not event.modifiers()):
                index = self._view.currentIndex()
                if index.isValid():
                    self.read.emit(index)
                    return True
        elif kind == QEvent.Type.KeyRelease:
            self._keyed = False
        return False

    def _on_current_changed(self, current, _previous):
        # Only a move the keyboard made; a mouse press changes the current row
        # too, and is judged on release (``clicked``), after any drag.
        if self._keyed and current.isValid():
            self._keyed = False
            self.choose.emit(current)

    def _on_clicked(self, index):
        # Qt emits ``clicked`` on a release over the row that was pressed, and
        # not after a drag. It does after a click the row's delegate took (Qt 5
        # did not), so a delegate that takes clicks for itself says so through
        # ``took_click()``; the plant list's ▶ did until V3.00.
        took = getattr(self._view.itemDelegate(), "took_click", None)
        if index.isValid() and not (took and took()):
            self.choose.emit(index)

    def _on_double_clicked(self, index):
        if index.isValid():
            self.place.emit(index)


# 13 px text, 4.5:1 and a visible focus ring, the review's baseline (F195), and
# the green this app uses for doing the thing (the bar's amber is for a state).
_STYLE = """
QPushButton#placeButton {
    background-color: #2e7d32; color: #ffffff;
    border: 1px solid #66bb6a; border-radius: 4px;
    padding: 3px 12px; font-size: 13px; font-weight: bold; min-height: 24px;
}
QPushButton#placeButton:hover { background-color: #388e3c; }
QPushButton#placeButton:focus { border: 2px solid #ffe082; }
QPushButton#placeButton:disabled {
    background-color: #1e2e1e; color: #a5b8a5; border-color: #3a4a3a;
    font-weight: normal;
}
"""


class PlaceButton(QPushButton):
    """"Place Wild Bergamot on the map": says what it places, or why it can't.

    Long names are elided to the button's width; the full sentence stays in the
    accessible name and the tooltip. ``compact`` buttons read just "Place on
    map" and carry the name only in those two, for a row that already shows it.
    """

    def __init__(self, noun: str, *, compact: bool = False, parent=None):
        super().__init__(parent)
        self.setObjectName("placeButton")
        self.setStyleSheet(_STYLE)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._noun = noun
        self._compact = compact
        self._what = ""
        if not compact:
            # Its width comes from the column, never from its text: the text is
            # elided to the width, and a width that followed the text would
            # chase it.
            from PyQt6.QtWidgets import QSizePolicy
            self.setSizePolicy(QSizePolicy.Policy.Ignored,
                               QSizePolicy.Policy.Fixed)
            self.setMinimumWidth(160)
        self.set_subject("")

    @property
    def subject(self) -> str:
        return self._what

    def set_subject(self, what: str) -> None:
        self._what = (what or "").strip()
        if self._what:
            sentence = f"Place {self._what} on the map"
            self.setAccessibleName(sentence)
            self.setToolTip(f"{sentence}. Or double-click it, or press Enter "
                            f"in the list.")
            self.setEnabled(True)
        else:
            self.setAccessibleName("Place on the map")
            self.setToolTip(f"Select a {self._noun} first.")
            self.setEnabled(False)
        self._fit_text()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._fit_text()

    def _fit_text(self) -> None:
        self.ensurePolished()        # measure in the style sheet's font
        if not self._what:
            self.setText(f"Select a {self._noun} to place it"
                         if not self._compact else "Place on map")
            return
        if self._compact:
            self.setText("Place on map")
            return
        metrics = self.fontMetrics()
        head, tail = "Place ", " on the map"
        room = self.width() - 28 - metrics.horizontalAdvance(head + tail)
        name = metrics.elidedText(self._what, Qt.TextElideMode.ElideRight,
                                  max(room, 40))
        self.setText(head + name + tail)

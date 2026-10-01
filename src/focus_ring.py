"""
focus_ring.py — one ring that follows keyboard focus in every window (F195,
V3.02).

The V2.98 review found no visible focus in the plant and community panels, and
V3.01's measurement found none anywhere outside Browse. The cause is the app's
look: almost every panel sets its controls' borders in its own stylesheet, a
widget's own stylesheet beats its window's whatever the specificity, and Qt's
native focus drawing goes with it. A window-wide ``:focus`` rule would lose the
same way, and adding one to each of a few hundred stylesheets would be a rule
nobody keeps.

So the ring is drawn by a ``QFocusFrame``, which sits around the focused control
rather than inside its stylesheet, and moves with focus from window to window.
It shows while the keyboard is in use and hides on a mouse press, the way a
browser's ``:focus-visible`` does: a ring around every clicked button is noise
to a mouse user, and no ring at all is the bug for a keyboard user.

**The ring is drawn over the control, just inside its edge.** Qt's own frame
(Fusion) sits *under* the control and shows only in a margin around it, so it
is clipped wherever a layout packs a control against its parent's edge: on
V3.02's first build a Tab walk measured the search field showing only its
bottom edge, the plant list only its top, and the side tab bars and scroll areas
nothing at all. :class:`_AboveStyle` puts the frame above the control in the
nearest window, toolbar or scroll viewport, which clips it exactly as the
control is clipped and no more. Two tones, so it shows on a light field as well
as a dark panel.

The map is not ringed here: focus inside it moves between the page's own
controls, which Qt cannot see, so the page draws its focus itself
(``html/map/09-keyboard.js``).
"""

from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import QEvent, QObject, QRectF, Qt
from PyQt6.QtGui import QColor, QPainter, QPen
from PyQt6.QtWidgets import (
    QApplication, QFocusFrame, QProxyStyle, QStyle, QWidget,
)

try:
    from PyQt6 import sip
except ImportError:                                         # pragma: no cover
    import sip                                              # type: ignore

#: The app's focus colour (the placement bar and the picker use it too).
#: #ffe082 on the darkest panel ground, #16241a, is 12.5:1.
RING_COLOUR = "#ffe082"
#: The line just inside it, so the ring holds 3:1 on a light field too
#: (#1a2a1a on white is 15:1), where yellow alone is about 1.3:1.
RING_EDGE = "#1a2a1a"


class _AboveStyle(QProxyStyle):
    """Puts the frame over the control, the size of the control, unmasked."""

    def styleHint(self, hint, option=None, widget=None, returnData=None):  # noqa: N802
        if hint == QStyle.StyleHint.SH_FocusFrame_AboveWidget:
            return 1
        if hint == QStyle.StyleHint.SH_FocusFrame_Mask:
            return 0
        return super().styleHint(hint, option, widget, returnData)

    def pixelMetric(self, metric, option=None, widget=None):  # noqa: N802
        if metric in (QStyle.PixelMetric.PM_FocusFrameHMargin,
                      QStyle.PixelMetric.PM_FocusFrameVMargin):
            return 0
        return super().pixelMetric(metric, option, widget)


class _Ring(QFocusFrame):
    """Two pixels of yellow at the control's edge and one dark one inside."""

    def __init__(self, parent: QWidget):
        super().__init__(parent)
        style = _AboveStyle()
        style.setParent(self)
        self.setStyle(style)

    def paintEvent(self, _event):  # noqa: N802 (Qt override)
        painter = QPainter(self)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        rect = QRectF(self.rect())
        painter.setPen(QPen(QColor(RING_COLOUR), 2))
        painter.drawRect(rect.adjusted(1, 1, -1, -1))
        painter.setPen(QPen(QColor(RING_EDGE), 1))
        painter.drawRect(rect.adjusted(2.5, 2.5, -2.5, -2.5))


class FocusRing(QObject):
    """Install with :func:`install`; nothing else needs to know it exists."""

    def __init__(self, app: QApplication):
        super().__init__(app)
        self._keyboard = False
        self._frame: Optional[QFocusFrame] = None
        app.installEventFilter(self)
        app.focusChanged.connect(self._on_focus_changed)

    # ── Keyboard or mouse ───────────────────────────────────────────────────

    def eventFilter(self, obj, event):  # noqa: N802 (Qt override)
        kind = event.type()
        if kind == QEvent.Type.KeyPress:
            if not self._keyboard:
                self._keyboard = True
                self._ring(QApplication.focusWidget())
        elif kind in (QEvent.Type.MouseButtonPress,
                      QEvent.Type.MouseButtonDblClick):
            if self._keyboard:
                self._keyboard = False
                self._ring(None)
        return False

    def _on_focus_changed(self, _old, new):
        self._ring(new if self._keyboard else None)

    def keyboard_in_use(self) -> bool:
        return self._keyboard

    # ── The frame ───────────────────────────────────────────────────────────

    def _ring(self, widget: Optional[QWidget]):
        if widget is not None and not _wants_ring(widget):
            widget = None
        frame = self._frame
        if frame is not None and sip.isdeleted(frame):
            # The frame lives beside the widget it rings; a closed window
            # takes it along.
            frame = self._frame = None
        if widget is None:
            if frame is not None:
                frame.setWidget(None)
                frame.hide()
            return
        if frame is None:
            frame = self._frame = _Ring(widget.window())
            frame.setObjectName("focusRing")
        frame.setWidget(widget)
        frame.show()
        frame.raise_()

    def ringed(self) -> Optional[QWidget]:
        """The widget the ring is around, or ``None`` (for tests)."""
        frame = self._frame
        if frame is None or sip.isdeleted(frame) or not frame.isVisible():
            return None
        return frame.widget()


def _wants_ring(widget: QWidget) -> bool:
    """Not inside a popup (a dropdown's list, a menu): those show their current
    row already, and a frame laid over a popup window is a frame on nothing.
    Not inside a web view: the page draws its own (see the module notes)."""
    if isinstance(widget, QFocusFrame) or widget.isWindow():
        return False
    if widget.window().windowType() in (Qt.WindowType.Popup,
                                        Qt.WindowType.ToolTip):
        return False
    ancestor = widget
    while ancestor is not None:
        if ancestor.inherits("QWebEngineView"):
            return False
        ancestor = ancestor.parentWidget()
    return True


_installed: Optional[FocusRing] = None


def install(app: Optional[QApplication] = None) -> FocusRing:
    """One ring per application; calling again returns the first."""
    global _installed
    if _installed is None or sip.isdeleted(_installed):
        app = app or QApplication.instance()
        _installed = FocusRing(app)
    return _installed

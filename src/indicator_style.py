"""
indicator_style.py — a checkbox's box you can see (F195, V3.03).

Measured on V3.03's own build, the example design open at 1366 × 768 under
Fusion (the style Linux and CI draw in): an unchecked checkbox's box edge was
1.11:1 against the panel it sits on, so until it was ticked nothing on screen
said there was a box at all. Fusion outlines the box in the widget's window
colour darkened by 40%, and on these dark panels the window colour *is* the
panel. WCAG 1.4.11 asks 3:1 of what identifies a control and its state.

So the application's style is wrapped in one that draws the two indicators
itself, the same on every platform: a light edge (6.3:1 on the panels), and
when ticked a green fill with a dark tick (a radio button: a green dot). On a
light ground, which a few system dialogs keep, the edge is dark instead.
Everything else is the platform's own style, untouched.

Installed once, like the focus ring and the 24 px floor, by ``main.py`` and by
the window.
"""

from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QColor, QPainter, QPainterPath, QPen
from PyQt6.QtWidgets import QApplication, QProxyStyle, QStyle, QStyleFactory

try:
    from PyQt6 import sip
except ImportError:                                         # pragma: no cover
    import sip                                              # type: ignore

#: The edge on a dark ground: 6.3:1 on the panels (#1e2a1e), 5.9:1 on the
#: darkest of them.
EDGE = "#b0bec5"
EDGE_HOVER = "#cfd8dc"
#: On a light ground (a system dialog that keeps its own palette).
EDGE_ON_LIGHT = "#455a64"
#: Disabled controls are exempt and meant to recede (WCAG 1.4.3, 1.4.11).
EDGE_DISABLED = "#546e7a"
ON = "#66bb6a"
ON_DISABLED = "#3a5a44"
MARK = "#0d1f0d"

_S = QStyle.StateFlag
_P = QStyle.PrimitiveElement


def _colours(option) -> tuple[QColor, QColor]:
    """(edge, fill when on) for this option's state and ground."""
    enabled = bool(option.state & _S.State_Enabled)
    dark_ground = option.palette.window().color().lightness() < 128
    if not enabled:
        return QColor(EDGE_DISABLED), QColor(ON_DISABLED)
    if not dark_ground:
        return QColor(EDGE_ON_LIGHT), QColor(ON)
    hover = bool(option.state & _S.State_MouseOver)
    return QColor(EDGE_HOVER if hover else EDGE), QColor(ON)


def draw_box(option, painter: QPainter) -> None:
    """A checkbox's box: edge, and a tick or a dash when it says so."""
    r = QRectF(option.rect).adjusted(0.5, 0.5, -0.5, -0.5)
    edge, on_fill = _colours(option)
    on = bool(option.state & _S.State_On)
    partial = bool(option.state & _S.State_NoChange)
    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setPen(QPen(edge, 1))
    painter.setBrush(on_fill if (on or partial) else Qt.BrushStyle.NoBrush)
    painter.drawRoundedRect(r, 2, 2)
    mark = QPen(QColor(MARK), max(1.5, r.width() / 7), Qt.PenStyle.SolidLine,
                Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
    painter.setPen(mark)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    w, h = r.width(), r.height()
    if on:
        tick = QPainterPath(QPointF(r.left() + 0.24 * w, r.top() + 0.52 * h))
        tick.lineTo(r.left() + 0.43 * w, r.top() + 0.71 * h)
        tick.lineTo(r.left() + 0.77 * w, r.top() + 0.31 * h)
        painter.drawPath(tick)
    elif partial:
        y = r.center().y()
        painter.drawLine(QPointF(r.left() + 0.27 * w, y), QPointF(r.right() - 0.27 * w, y))
    painter.restore()


def draw_ring(option, painter: QPainter) -> None:
    """A radio button's ring, and a dot when it is the one chosen."""
    r = QRectF(option.rect).adjusted(0.5, 0.5, -0.5, -0.5)
    edge, on_fill = _colours(option)
    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setPen(QPen(edge, 1))
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.drawEllipse(r)
    if option.state & _S.State_On:
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(on_fill)
        painter.drawEllipse(r.center(), r.width() * 0.3, r.height() * 0.3)
    painter.restore()


class IndicatorStyle(QProxyStyle):
    """The platform's style, with the two indicators drawn as above."""

    def drawPrimitive(self, element, option, painter, widget=None):  # noqa: N802
        if element == _P.PE_IndicatorCheckBox:
            draw_box(option, painter)
            return
        if element == _P.PE_IndicatorRadioButton:
            draw_ring(option, painter)
            return
        super().drawPrimitive(element, option, painter, widget)


_installed: Optional[IndicatorStyle] = None


def install(app: Optional[QApplication] = None) -> QStyle:
    """Wrap the application's style once; calling again changes nothing."""
    global _installed
    app = app or QApplication.instance()
    if _installed is not None and not sip.isdeleted(_installed) \
            and app.style() is _installed:
        return _installed
    # A fresh instance of the same style to wrap: the application owns, and
    # deletes, the one it is replacing.
    name = app.style().name()
    base = QStyleFactory.create(name) if name else None
    _installed = IndicatorStyle(base) if base is not None else IndicatorStyle()
    app.setStyle(_installed)
    return _installed

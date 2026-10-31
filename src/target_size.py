"""
target_size.py — every control at least 24 px across (F195, V3.03).

WCAG 2.5.8 asks 24 × 24 px of anything you click or tap. Measured on V3.02, at
1366 × 768 on the example design, every side tab had controls under it, one to
fifteen per tab: checkboxes 18-20 px tall, spin boxes 20, dropdowns 20-23, Plant
Communities' row of buttons 23 and "▸ Show variations" 16, the search boxes 23,
sliders 15. They are sized by a few hundred stylesheets, mostly by padding, and
a rule written into each would be a rule nobody keeps.

So it is one rule in one place, the way V3.02 did the focus ring: when a
control is polished, and again each time it is shown, a control that would
draw under 24 px high (a vertical slider: wide) is given a minimum of 24, and a
button one of 24 wide too (a checkbox or radio button only when it has no words
of its own). A control fixed smaller than that has its maximum raised to match.
Only raised, never lowered: see the note at ``_floor``.

Not counted: the parts of a control (the line edit inside a dropdown or a spin
box, a tab bar's scroll arrows, Qt's own ``qt_``-named helpers), which share
their owner's target.
"""

from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import QEvent, QObject, Qt
from PyQt6.QtWidgets import (
    QAbstractButton, QAbstractSpinBox, QApplication, QCheckBox, QComboBox,
    QLineEdit, QRadioButton, QSlider, QWidget,
)

try:
    from PyQt6 import sip
except ImportError:                                         # pragma: no cover
    import sip                                              # type: ignore

#: WCAG 2.5.8 (AA), in logical pixels: the operating system's display scaling
#: multiplies it like every other size here.
MIN_TARGET = 24

CONTROLS = (QAbstractButton, QComboBox, QAbstractSpinBox, QLineEdit, QSlider)


def counts(widget: QWidget) -> bool:
    """Whether ``widget`` is a target of its own (see the module notes)."""
    if not isinstance(widget, CONTROLS) or widget.isWindow():
        return False
    if widget.objectName().startswith("qt_"):
        return False
    parent = widget.parentWidget()
    if parent is None:
        return True
    if isinstance(widget, QLineEdit) and isinstance(parent, (QComboBox, QAbstractSpinBox)):
        return False
    return not parent.inherits("QTabBar")


def fit(widget: QWidget) -> None:
    """Give one control the minimum, or give it back. Safe to call again."""
    if not counts(widget):
        return
    vertical = (isinstance(widget, QSlider)
                and widget.orientation() == Qt.Orientation.Vertical)
    _floor(widget, "w" if vertical else "h")
    # A checkbox's or radio button's words are part of what you click; one
    # with no words (its question beside it, as in Field Notes) is its box.
    if isinstance(widget, QAbstractButton) and not (
            isinstance(widget, (QCheckBox, QRadioButton)) and widget.text()):
        _floor(widget, "w")


# Only ever raise a minimum. A minimum set on a widget REPLACES the one Qt
# works out from its text (minimumSizeHint) when a layout asks: the first
# build set 24 on every button, and the View toolbar, which had moved what did
# not fit into its » menu, shrank its buttons to 24 px instead and read
# "S…ite", "B…ary", "Mea…ement". So a minimum is set only where both the
# widget's and Qt's are under 24, and given back (re-checked each time the
# control is shown) once Qt's own reaches 24: a button made empty and given its
# text later would otherwise keep a 24 px floor its text has outgrown.
_MARK = {"h": "_targetSizeH", "w": "_targetSizeW"}


def _floor(widget: QWidget, dim: str) -> None:
    high = dim == "h"
    hint = widget.minimumSizeHint().height() if high else widget.minimumSizeHint().width()
    current = widget.minimumHeight() if high else widget.minimumWidth()
    maximum = widget.maximumHeight() if high else widget.maximumWidth()
    set_min = widget.setMinimumHeight if high else widget.setMinimumWidth
    set_max = widget.setMaximumHeight if high else widget.setMaximumWidth
    if (widget.property(_MARK[dim]) and current == MIN_TARGET
            and hint >= MIN_TARGET and maximum >= MIN_TARGET):
        set_min(0)                     # Qt's own minimum holds now
        widget.setProperty(_MARK[dim], False)
        return
    # What a layout uses: a minimum that has been set, else Qt's.
    effective = current if current > 0 else hint
    if effective >= MIN_TARGET and maximum >= MIN_TARGET:
        return
    if maximum < MIN_TARGET:
        set_max(MIN_TARGET)
    if effective < MIN_TARGET:
        set_min(MIN_TARGET)
        widget.setProperty(_MARK[dim], True)


class TargetSize(QObject):
    """Install with :func:`install`."""

    def eventFilter(self, obj, event):  # noqa: N802 (Qt override)
        if (event.type() in (QEvent.Type.Polish, QEvent.Type.Show)
                and isinstance(obj, CONTROLS)):
            fit(obj)
        return False


_installed: Optional[TargetSize] = None


def install(app: Optional[QApplication] = None) -> TargetSize:
    """One filter per application; calling again returns the first."""
    global _installed
    if _installed is None or sip.isdeleted(_installed):
        app = app or QApplication.instance()
        _installed = TargetSize(app)
        app.installEventFilter(_installed)
    return _installed

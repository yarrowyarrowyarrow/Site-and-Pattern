"""
tests/_visual.py — what is on screen, measured (F195, V3.03).

Shared by the tests that hold the visual baseline: the WCAG contrast of two
colours, the ground a widget is actually drawn on (read from a grab of its
window, so a stylesheet's intent is not taken on trust), the colours a piece of
text draws in, rich text included, and the smallest text it draws.

Not a test module: unittest's pattern does not match the leading underscore.
"""

from __future__ import annotations

import re
from collections import Counter

from PyQt6.QtCore import QRect
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QAbstractButton, QComboBox, QGroupBox, QLabel, QLineEdit, QTabWidget,
)

_SPAN = re.compile(r"<span[^>]*style\s*=\s*['\"][^'\"]*?color\s*:\s*"
                   r"(#[0-9a-fA-F]{3,8})[^'\"]*['\"][^>]*>(.*?)</span>",
                   re.I | re.S)
_INLINE_SIZE = re.compile(r"font-size\s*:\s*([0-9.]+)px", re.I)
_TAGS = re.compile(r"<[^>]+>")
# Text made only of these is a graphic (a swatch, a progress dot), held to
# WCAG 1.4.11's 3:1 rather than 1.4.3's 4.5:1.
_SYMBOLS = set("■□▪▫●○◆◇★☆•·–—▸▾▶◀✓✕×⬡ ")


def luminance(c: QColor) -> float:
    def ch(v):
        v /= 255
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    return 0.2126 * ch(c.red()) + 0.7152 * ch(c.green()) + 0.0722 * ch(c.blue())


def contrast(a, b) -> float:
    a, b = QColor(a), QColor(b)
    la, lb = sorted([luminance(a), luminance(b)], reverse=True)
    return (la + 0.05) / (lb + 0.05)


def text_of(w) -> str:
    if isinstance(w, (QLabel, QAbstractButton)):
        return w.text()
    if isinstance(w, QGroupBox):
        return w.title()
    if isinstance(w, QComboBox):
        return w.currentText()
    if isinstance(w, QLineEdit):
        return w.text() or w.placeholderText()
    return ""


def plain(text: str) -> str:
    return _TAGS.sub("", (text or "").replace("&nbsp;", " ")).strip()


def is_graphic(text: str) -> bool:
    t = plain(text)
    return bool(t) and set(t) <= _SYMBOLS


def font_px(w) -> int:
    f = w.font()
    if f.pixelSize() > 0:
        return f.pixelSize()
    return round(f.pointSizeF() * w.logicalDpiY() / 72)


def smallest_px(w) -> int:
    """The smallest text ``w`` draws: its font, or a size written into its
    rich text."""
    sizes = [int(float(v)) for v in _INLINE_SIZE.findall(text_of(w) or "")]
    return min(sizes) if sizes else font_px(w)


def colours(w):
    """``[(colour, is_graphic)]`` for each colour ``w``'s text is drawn in."""
    text = text_of(w)
    pal = w.palette()
    if isinstance(w, QLineEdit) and not w.text():
        out = [(pal.color(pal.ColorRole.PlaceholderText), False)]
    else:
        out = [(pal.color(w.foregroundRole()), is_graphic(text))]
    for colour, inner in _SPAN.findall(text or ""):
        c = QColor(colour)
        if c.isValid():
            out.append((c, is_graphic(inner)))
    return out


def ground(image, window, w):
    """The commonest pixel under the part of ``w`` that is on screen, in a
    grab of its window; ``None`` when none of it is."""
    seen_part = w.visibleRegion().boundingRect()
    if seen_part.isEmpty():
        return None
    rect = QRect(w.mapTo(window, seen_part.topLeft()), seen_part.size())
    seen = Counter()
    step = max(1, min(rect.width(), rect.height()) // 12)
    for x in range(rect.left(), rect.right() + 1, step):
        for y in range(rect.top(), rect.bottom() + 1, step):
            if 0 <= x < image.width() and 0 <= y < image.height():
                seen[image.pixel(x, y)] += 1
    return QColor(seen.most_common(1)[0][0]) if seen else None


def indicator(image, window, w):
    """``(edge, ground, inside)`` of a checkbox's box or a radio button's
    ring, read from a grab of ``window``: the pixel on the box's left edge at
    its middle, the ground three pixels left of it, and a pixel inside its
    lower right quarter, which a tick does not cross. ``None`` when the box is
    not wholly on screen (a control scrolled half out of its panel)."""
    from PyQt6.QtWidgets import QRadioButton, QStyle, QStyleOptionButton
    opt = QStyleOptionButton()
    w.initStyleOption(opt)
    element = (QStyle.SubElement.SE_RadioButtonIndicator
               if isinstance(w, QRadioButton)
               else QStyle.SubElement.SE_CheckBoxIndicator)
    r = w.style().subElementRect(element, opt, w)
    from PyQt6.QtGui import QRegion
    if w.visibleRegion().intersected(QRegion(r)) != QRegion(r):
        return None
    top_left = w.mapTo(window, r.topLeft())
    y = top_left.y() + r.height() // 2

    def px(x, yy):
        return QColor(image.pixel(max(0, x), yy))
    return (px(top_left.x(), y), px(top_left.x() - 3, y),
            px(top_left.x() + 3 * r.width() // 4, top_left.y() + 3 * r.height() // 4))


def every_tab(window, outer: QTabWidget):
    """Show each side tab and each of its sub-tabs in turn; yield a name."""
    from PyQt6.QtWidgets import QApplication
    for i in range(outer.count()):
        outer.setCurrentIndex(i)
        inner = outer.widget(i).findChildren(QTabWidget)
        pages = range(inner[0].count()) if inner else [None]
        for j in pages:
            if j is not None:
                inner[0].setCurrentIndex(j)
            QApplication.processEvents()
            name = outer.tabText(i).replace("&", "")
            if j is not None:
                name += " / " + inner[0].tabText(j).replace("&", "")
            yield name

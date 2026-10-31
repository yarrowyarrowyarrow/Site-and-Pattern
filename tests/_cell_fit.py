"""
tests/_cell_fit.py — does a list's text fit its cells, as Qt lays it out
(V3.19, QF-10)?

Shared by ``tests/test_community_names.py`` and the real window's check in
``tests/test_app_smoke.py``. It reads the text the delegate draws, split into
its lines, against the cell's own rectangle (``visualRect``), so it does not
repeat the delegate's arithmetic and works on any delegate: on Qt's own a name
too long for its cell is reported as too wide, since Qt elides only as it
paints.

Not a test module: unittest's pattern does not match the leading underscore.
It changes nothing at import, so a module that has pointed the database
somewhere can import it.
"""

from __future__ import annotations

#: Qt's line separator, as ``src/two_line_rows.py`` writes a fold.
LINE = chr(0x2028)


def cut_cells(tree, columns=(0,)) -> list:
    """Every shown cell in ``columns`` whose drawn text does not fit its
    rectangle: a line wider than the cell, a line elided, or more lines than
    the row is tall. ``"name: why"`` each."""
    from PyQt6.QtGui import QFontMetrics
    from PyQt6.QtWidgets import (
        QStyle, QStyleOptionViewItem, QTreeWidgetItemIterator,
    )
    margin = tree.style().pixelMetric(
        QStyle.PixelMetric.PM_FocusFrameHMargin, None, tree) + 1
    delegate = tree.itemDelegate()
    bad = []
    it = QTreeWidgetItemIterator(tree)
    while it.value() is not None:
        item = it.value()
        it += 1
        parent = item.parent()
        if parent is not None and not parent.isExpanded():
            continue
        for column in columns:
            index = tree.indexFromItem(item, column)
            if not item.text(column):
                continue
            option = QStyleOptionViewItem()
            option.initFrom(tree.viewport())
            try:
                delegate.initStyleOption(option, index)
                text, metrics = option.text, option.fontMetrics
            except RuntimeError:     # Qt's own delegate: its text as stored
                text = item.text(column)
                metrics = QFontMetrics(item.font(column))
            rect = tree.visualRect(index)
            room = rect.width() - 2 * margin
            lines = text.replace("\n", LINE).split(LINE)
            name = item.text(column)
            for line in lines:
                if "…" in line:
                    bad.append(f"{name}: elided as {line!r}")
                elif metrics.horizontalAdvance(line) > room:
                    bad.append(f"{name}: {line!r} needs "
                               f"{metrics.horizontalAdvance(line)} of {room} px")
            if rect.height() < len(lines) * metrics.height():
                bad.append(f"{name}: {len(lines)} lines in {rect.height()} px")
    return bad

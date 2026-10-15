"""
src/two_line_rows.py — a list's names on two lines before they are cut
(V3.19, QF-10).

The first review (R21): at 1366 px Placement › Communities cut every name to
about twelve characters, "Boreal Conifer…", "Boreal Peavin…", "Boreal Shade …",
"Boreal Woodl…", and several could not be told apart. The facts column (F196,
V3.05) took the width it needed first, 288 px of a 392 px list, and left the
names 104.

:class:`TwoLineRows` is the list's delegate. The facts take what they need on
one line up to :data:`FACTS_SHARE` of the row (never less than they need on
two), the names the rest, and each cell folds onto a second line before
anything is elided, by ``community_page.two_lines``, the rule the community
page's photographs have used since V3.09: names between words, facts between
their " · " parts. Narrower than that, the facts give way before a name does.
A row is two lines tall only when one of its cells needs it. The fold happens
as the row is measured and drawn; the item keeps its whole name, which is what
a screen reader, the tooltip and the context menu read.
"""

from __future__ import annotations

from PyQt6.QtCore import QEvent, QModelIndex, QTimer
from PyQt6.QtWidgets import (
    QHeaderView, QStyle, QStyledItemDelegate, QTreeWidget,
    QTreeWidgetItemIterator,
)

#: The most of the row the facts take when one line would need more. At
#: 1366 px that leaves every community's name whole: most on one line, the
#: longest (8 of 73 under Arial metrics, 17 under DejaVu) on two (V3.19).
FACTS_SHARE = 0.45

#: Where each column may break: names between words, facts between parts.
_BREAKS = (" ", " · ")

#: Qt's line separator: a hard break that QTextLayout honours, as "\n" in an
#: item's text is not guaranteed to be. An escape, because the character
#: itself cannot be seen in an editor.
LINE = "\u2028"


class TwoLineRows(QStyledItemDelegate):
    """Delegate for a two-column ``QTreeWidget`` (name, facts) whose cells
    fold onto a second line before they elide. Installs itself on ``tree``."""

    def __init__(self, tree: QTreeWidget, share: float = FACTS_SHARE):
        super().__init__(tree)
        self._tree, self._share = tree, share
        tree.setItemDelegate(self)
        header = tree.header()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        # A width change re-measures every row; a burst of them is one pass.
        self._relayout = QTimer(self)
        self._relayout.setSingleShot(True)
        self._relayout.setInterval(0)
        self._relayout.timeout.connect(tree.doItemsLayout)
        header.sectionResized.connect(lambda *_: self._relayout.start())
        self._refit = QTimer(self)
        self._refit.setSingleShot(True)
        self._refit.setInterval(0)
        self._refit.timeout.connect(self.fit)
        model = tree.model()
        for signal in (model.rowsInserted, model.rowsRemoved,
                       model.modelReset, model.dataChanged):
            signal.connect(lambda *_: self._refit.start())
        # Kept, not asked of the tree in eventFilter: the viewport still sends
        # events while the tree is being destroyed, when the tree's wrapper
        # already reads as deleted.
        self._viewport = tree.viewport()
        self._viewport.installEventFilter(self)

    # ── The columns ──────────────────────────────────────────────────────────

    def fit(self) -> None:
        """Give the facts what they need on one line, up to the share but
        never less than they need on two, and the names the rest. When the
        list is too narrow for both, the names keep their two lines and the
        facts give way, down to a third of the row: the name is what says
        which community a row is."""
        tree = self._tree
        metrics = tree.fontMetrics()
        one = two = names = 0
        it = QTreeWidgetItemIterator(tree)
        while it.value() is not None:
            item = it.value()
            facts = item.text(1)
            one = max(one, metrics.horizontalAdvance(facts))
            two = max(two, _folded_width(facts, metrics, _BREAKS[1]))
            depth, parent = 0, item.parent()
            while parent is not None:
                depth, parent = depth + 1, parent.parent()
            indent = tree.indentation() * (depth + int(tree.rootIsDecorated()))
            names = max(names, indent + _folded_width(
                item.text(0), metrics, _BREAKS[0]))
            it += 1
        pad = 2 * self._margin() + 2
        width = tree.viewport().width()
        facts = min(one + pad, max(two + pad, int(width * self._share)))
        tree.setColumnWidth(1, min(facts, max(width - names - pad, width // 3)))

    def room(self, index: QModelIndex) -> int:
        """The width a cell's text is drawn in, in px."""
        tree = self._tree
        room = tree.columnWidth(index.column()) - 2 * self._margin() - 1
        if index.column() == 0:
            depth, parent = 0, index.parent()
            while parent.isValid():
                depth, parent = depth + 1, parent.parent()
            room -= tree.indentation() * (depth + int(tree.rootIsDecorated()))
        return room

    def _margin(self) -> int:
        """The style's text margin, each side (as ``QCommonStyle`` draws)."""
        return self._tree.style().pixelMetric(
            QStyle.PixelMetric.PM_FocusFrameHMargin, None, self._tree) + 1

    # ── The fold ─────────────────────────────────────────────────────────────

    def initStyleOption(self, option, index) -> None:          # noqa: N802
        super().initStyleOption(option, index)
        if not option.text:
            return
        from src.community_page import two_lines
        sep = _BREAKS[min(index.column(), len(_BREAKS) - 1)]
        option.text = two_lines(option.text, option.fontMetrics,
                                self.room(index), sep).replace("\n", LINE)

    def eventFilter(self, obj, event) -> bool:                 # noqa: N802
        if obj is self._viewport:
            if event.type() == QEvent.Type.Resize:
                self._refit.start()
            return False
        return super().eventFilter(obj, event)


def _folded_width(text: str, metrics, sep: str) -> int:
    """The narrowest ``text`` gets on two lines broken at ``sep``: the widest
    line of its best break."""
    from src.community_page import fold_parts
    parts = fold_parts(text, sep)
    if len(parts) < 2:
        return metrics.horizontalAdvance(text)
    return min(max(metrics.horizontalAdvance(sep.join(parts[:k])),
                   metrics.horizontalAdvance(sep.join(parts[k:])))
               for k in range(1, len(parts)))

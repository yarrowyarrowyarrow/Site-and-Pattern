"""
share_panel.py — Share: what leaves the app (V3.08).

The V3.05 surface audit found the ways a design leaves the app in four places:
File's three exports, Learn › Present (the narrated tour), View › Growth
Snapshots, and the 3D preview's Presentation still and Before / after. The owner
moved Present out of Learn ("presenting a design is an output") and Where to buy
off Site Info, and said yes to the 3D preview's outputs going here too. Two
pages:

  * **Present** — the docent tour, built by ``learn_panel`` as before;
  * **Export** — the PDF, the planting plan, the order file, Growth Snapshots,
    the presentation still and before / after, and **Where to buy**, beside the
    buy list it serves.

The Export page only calls what the File menu and the 3D preview already do;
nothing here is a second way of exporting. The 3D outputs open the preview and
ask it, because that is where they render; the moment and the file are asked
for while its scene loads.
"""

from __future__ import annotations

from PyQt6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QPushButton, QScrollArea, QVBoxLayout,
    QWidget,
)

from src.ui_style import BTN_PRIMARY

#: The app's one primary colour (F209), the label at the left.
_PRIMARY = BTN_PRIMARY + "QPushButton { text-align: left; padding: 6px 10px; }"
_HEAD_STYLE = ("color: #a5d6a7; font-size: 13px; font-weight: bold; "
               "padding: 8px 0 2px 0;")
_NOTE_STYLE = "color: #90a4ae; font-size: 12px;"


def _open_still(main):
    from src.scene3d_window import open_3d_view
    open_3d_view(main)._on_presentation_still()


def _open_before_after(main):
    from src.scene3d_window import open_3d_view
    open_3d_view(main)._on_before_after()


def _open_snapshots(main):
    from src.snapshot_window import open_snapshot_view
    open_snapshot_view(main)


#: ``(section, [(button, what it gives, action(main))])``, in the order a
#: person needs them: the documents to take outside, then the pictures.
EXPORTS = (
    ("Take it outside", (
        ("Export PDF…", "the whole plan: prep, buy list, planting map, care",
         lambda main: main._on_export_pdf()),
        ("Planting plan…", "what to buy and where it goes, as text",
         lambda main: main._on_export_shopping_list()),
        ("Order file…", "the buy list as a spreadsheet, by supplier",
         lambda main: main._on_export_order_file()),
    )),
    ("Pictures", (
        ("Growth Snapshots…", "the design at 1, 5, 15 and 30 years",
         _open_snapshots),
        ("Presentation still…", "a 3D render at print size, for a proposal",
         _open_still),
        ("Before / after…", "the yard now beside the design grown",
         _open_before_after),
    )),
)


class SharePanel(QWidget):
    """The Share tab: a strip with Present and Export."""

    def __init__(self, main, parent=None):
        super().__init__(parent)
        from src.fill_tab_widget import FillTabWidget
        from src.ui_style import inner_tab_stylesheet
        self._main = main
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(0)
        self._tabs = FillTabWidget()
        self._tabs.setDocumentMode(True)
        self._tabs.tabBar().setUsesScrollButtons(False)
        self._tabs.tabBar().setExpanding(True)
        self._tabs.setStyleSheet(inner_tab_stylesheet())
        layout.addWidget(self._tabs)
        self.export_page = self._build_export()
        self._tabs.addTab(self.export_page, "Export")

    def _build_export(self) -> QScrollArea:
        page = QScrollArea()
        page.setWidgetResizable(True)
        page.setFrameShape(QFrame.Shape.NoFrame)
        body = QWidget()
        page.setWidget(body)
        lay = QVBoxLayout(body)
        lay.setContentsMargins(6, 6, 6, 6)
        lay.setSpacing(6)
        self.buttons: dict = {}
        for section, rows in EXPORTS:
            head = QLabel(section)
            head.setStyleSheet(_HEAD_STYLE)
            lay.addWidget(head)
            for words, gives, action in rows:
                row = QHBoxLayout()
                btn = QPushButton(words)
                btn.setStyleSheet(_PRIMARY)
                btn.setMinimumWidth(150)
                btn.clicked.connect(lambda _c=False, a=action: a(self._main))
                row.addWidget(btn)
                note = QLabel(gives)
                note.setWordWrap(True)
                note.setStyleSheet(_NOTE_STYLE)
                btn.setToolTip(gives[0].upper() + gives[1:])
                row.addWidget(note, 1)
                lay.addLayout(row)
                self.buttons[words] = btn
        # Where to buy arrives here from Site Info (src/side_panel_layout.py).
        self._export_layout = lay
        lay.addStretch()
        return page

    def add_to_export(self, widget: QWidget) -> None:
        """Put ``widget`` at the end of the Export page, above its stretch."""
        lay = self._export_layout
        lay.insertWidget(lay.count() - 1, widget)

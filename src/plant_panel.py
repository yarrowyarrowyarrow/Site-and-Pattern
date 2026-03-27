"""
plant_panel.py — Right-side plant browser panel (Step 2 implementation).

For Step 1 this is a minimal stub so the main window can import it without
crashing. A QLabel placeholder is shown.
"""

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PyQt6.QtCore import pyqtSignal, Qt


class PlantPanel(QWidget):
    """Right-hand panel for browsing, filtering and placing plants."""

    # Emitted when the user clicks "Place on Map" for a plant
    place_plant_requested = pyqtSignal(int, str)   # plant_id, common_name

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_stub()

    def _build_stub(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)

        lbl = QLabel(
            "<b style='color:#a5d6a7;'>Plant Panel</b><br><br>"
            "<span style='color:#78909c;'>Coming in Step 2:<br>"
            "• Search &amp; filter plants<br>"
            "• Browse the Alberta plant database<br>"
            "• Place plants on the map</span>"
        )
        lbl.setWordWrap(True)
        lbl.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(lbl)
        layout.addStretch()

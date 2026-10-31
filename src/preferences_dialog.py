"""
preferences_dialog.py — View › Map Settings…: an optional satellite token and
the scroll-wheel zoom step (moved here from the View row in V3.07; saved and
applied by ``src/map_settings_flow.py``).
"""

from __future__ import annotations

from PyQt6.QtWidgets import (
    QComboBox, QDialog, QDialogButtonBox, QFormLayout, QLabel,
    QLineEdit, QVBoxLayout, QWidget,
)
from PyQt6.QtCore import Qt


class MapPreferencesDialog(QDialog):
    """The map's two settings: a Mapbox token and how far one wheel step
    zooms."""

    def __init__(self, current_token: str = "", parent: QWidget | None = None,
                 *, zoom_level: str = "fine"):
        from src.map_settings_flow import ZOOM_LEVELS
        super().__init__(parent)
        self.setWindowTitle("Map Settings")
        self.setMinimumWidth(440)

        layout = QVBoxLayout(self)

        zoom_form = QFormLayout()
        self._zoom = QComboBox()
        self._zoom.setAccessibleName("Scroll-wheel zoom")
        for level, words in ZOOM_LEVELS:
            self._zoom.addItem(words, level)
        found = self._zoom.findData(zoom_level)
        self._zoom.setCurrentIndex(found if found >= 0 else 0)
        self._zoom.setToolTip("How far one step of the mouse wheel zooms the "
                              "map. Fine is the smoothest.")
        zoom_form.addRow("Scroll-wheel zoom:", self._zoom)
        layout.addLayout(zoom_form)

        info = QLabel(
            "<b>Mapbox Satellite (optional)</b><br>"
            "A free Mapbox access token enables high-resolution satellite imagery "
            "(zoom 22) globally — ideal for residential property detail.<br>"
            "Get a free token at <a href='https://account.mapbox.com/'>account.mapbox.com</a> "
            "(50 000 map loads/month free)."
        )
        info.setWordWrap(True)
        info.setOpenExternalLinks(True)
        layout.addWidget(info)

        form = QFormLayout()
        self._token_edit = QLineEdit(current_token)
        self._token_edit.setPlaceholderText("pk.eyJ1Ijoiexample…")
        self._token_edit.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow("Access token:", self._token_edit)
        layout.addLayout(form)

        show_btn = QLabel("<a href='#'>Show / hide</a>")
        show_btn.setAlignment(Qt.AlignmentFlag.AlignRight)
        show_btn.linkActivated.connect(self._toggle_echo)
        layout.addWidget(show_btn)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save |
            QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _toggle_echo(self):
        if self._token_edit.echoMode() == QLineEdit.EchoMode.Password:
            self._token_edit.setEchoMode(QLineEdit.EchoMode.Normal)
        else:
            self._token_edit.setEchoMode(QLineEdit.EchoMode.Password)

    def token(self) -> str:
        return self._token_edit.text().strip()

    def zoom_level(self) -> str:
        return self._zoom.currentData() or "fine"

"""
preferences_dialog.py — Map settings dialog for optional API tokens.
"""

from __future__ import annotations

from PyQt6.QtWidgets import (
    QDialog, QDialogButtonBox, QFormLayout, QLabel,
    QLineEdit, QVBoxLayout, QWidget,
)
from PyQt6.QtCore import Qt


class MapPreferencesDialog(QDialog):
    """Dialog for configuring optional map provider tokens."""

    def __init__(self, current_token: str = "", parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("Map Settings")
        self.setMinimumWidth(440)

        layout = QVBoxLayout(self)

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

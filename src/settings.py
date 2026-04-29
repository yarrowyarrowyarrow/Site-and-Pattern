"""
settings.py — Persistent configuration storage and Settings dialog.

API keys are stored in  ~/.permadesign_config.json  (never in the repo).
"""

from __future__ import annotations

import json
import os
from typing import Optional

from PyQt6.QtWidgets import (
    QDialog, QFormLayout, QLineEdit, QDialogButtonBox,
    QLabel, QVBoxLayout, QGroupBox,
)
from PyQt6.QtCore import Qt

_CONFIG_PATH = os.path.join(os.path.expanduser("~"), ".permadesign_config.json")


# ── Read / write ──────────────────────────────────────────────────────────────

def load_config() -> dict:
    """Return the full config dict (empty dict if file absent or corrupt)."""
    try:
        with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_config(config: dict) -> None:
    """Persist the full config dict to disk."""
    with open(_CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)


def get_api_keys() -> tuple[str, str]:
    """Return (key_id, key_secret) from config, or ('', '') if not set."""
    cfg = load_config()
    return cfg.get("permapeople_key_id", ""), cfg.get("permapeople_key_secret", "")


def save_api_keys(key_id: str, key_secret: str) -> None:
    cfg = load_config()
    cfg["permapeople_key_id"]     = key_id.strip()
    cfg["permapeople_key_secret"] = key_secret.strip()
    save_config(cfg)


def has_api_keys() -> bool:
    kid, ksec = get_api_keys()
    return bool(kid and ksec)


# ── Saved polyculture recipes ─────────────────────────────────────────────────

def get_polyculture_recipes() -> list[dict]:
    """Return the user's saved polyculture mixes, oldest-first.

    Each entry is `{"name": str, "species": [{...minimal plant fields,
    "weight": int}, ...]}`. The recipes are stored as plant_id +
    weight + cached display fields; the full plant record is rehydrated
    from the local DB at load time so changes to plant data flow
    through.
    """
    cfg = load_config()
    recipes = cfg.get("polyculture_recipes")
    if not isinstance(recipes, list):
        return []
    out = []
    for r in recipes:
        if isinstance(r, dict) and r.get("name") and isinstance(r.get("species"), list):
            out.append(r)
    return out


def save_polyculture_recipes(recipes: list[dict]) -> None:
    cfg = load_config()
    cfg["polyculture_recipes"] = list(recipes)
    save_config(cfg)


# ── Settings dialog ───────────────────────────────────────────────────────────

class SettingsDialog(QDialog):
    """Modal dialog for entering / updating Permapeople API credentials."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings — Permapeople API")
        self.setMinimumWidth(420)
        self.setModal(True)

        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # Info label
        info = QLabel(
            "Enter your Permapeople API credentials below.\n"
            "Get a free key at <b>permapeople.org</b> → Account → API Access.\n"
            "Keys are stored locally in your home folder and never shared."
        )
        info.setWordWrap(True)
        info.setTextFormat(Qt.TextFormat.RichText)
        info.setStyleSheet("color: #90a4ae; font-size: 12px;")
        layout.addWidget(info)

        # Credentials group
        group = QGroupBox("Permapeople API Credentials")
        form = QFormLayout(group)
        form.setSpacing(8)

        self._key_id_edit = QLineEdit()
        self._key_id_edit.setPlaceholderText("your-key-id")
        self._key_id_edit.setMinimumWidth(280)

        self._key_secret_edit = QLineEdit()
        self._key_secret_edit.setPlaceholderText("your-key-secret")
        self._key_secret_edit.setEchoMode(QLineEdit.EchoMode.Password)

        form.addRow("Key ID:", self._key_id_edit)
        form.addRow("Key Secret:", self._key_secret_edit)

        layout.addWidget(group)

        # Buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save |
            QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        # Pre-fill existing keys
        kid, ksec = get_api_keys()
        self._key_id_edit.setText(kid)
        self._key_secret_edit.setText(ksec)

    def _on_save(self):
        key_id     = self._key_id_edit.text().strip()
        key_secret = self._key_secret_edit.text().strip()
        if key_id and key_secret:
            save_api_keys(key_id, key_secret)
        self.accept()

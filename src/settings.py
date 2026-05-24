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


# ── Saved polyculture recipes (DEPRECATED shims) ──────────────────────────────
#
# Recipes now live in the SQLite database. These two functions are kept
# as thin shims so any code path that still calls them keeps working —
# they delegate to src.db.recipes. New code should import directly from
# src.db.recipes.

def get_polyculture_recipes() -> list[dict]:
    """DEPRECATED — use src.db.recipes.get_all_recipes().

    Returns the recipe list in the legacy QSettings shape
    (``[{"name": ..., "species": [...]}]``) so callers that haven't
    migrated keep working.
    """
    try:
        from src.db.recipes import get_all_recipes, get_recipe_by_id, recipe_to_species_list
    except Exception:
        return []
    out: list[dict] = []
    for r in get_all_recipes():
        try:
            full = get_recipe_by_id(r["id"]) or {}
            rec = recipe_to_species_list(full)
            out.append({
                "name": full.get("name") or "",
                "species": rec.get("species") or [],
            })
        except Exception:
            continue
    return out


def save_polyculture_recipes(recipes: list[dict]) -> None:
    """DEPRECATED — write recipes via src.db.recipes.create_recipe /
    replace_recipe_members instead. This shim treats the call as
    "replace all recipes" so the legacy plant_panel save flow still
    works in the transition window.
    """
    try:
        from src.db import recipes as recipes_db
    except Exception:
        return
    existing = {r["name"]: r["id"] for r in recipes_db.get_all_recipes()}
    seen: set[str] = set()
    for r in recipes or []:
        if not isinstance(r, dict):
            continue
        name = (r.get("name") or "").strip()
        if not name:
            continue
        seen.add(name)
        species = r.get("species") or []
        members = [
            {
                "plant_id": int(s["id"]),
                "weight": int(s.get("weight") or 1),
                "marker_color": s.get("color") or None,
            }
            for s in species if s.get("id")
        ]
        recipe_id = existing.get(name)
        if recipe_id is None:
            recipe_id = recipes_db.create_recipe(name)
        recipes_db.replace_recipe_members(recipe_id, members)
    # Drop recipes that disappeared from the legacy list.
    for name, rid in existing.items():
        if name not in seen:
            recipes_db.delete_recipe(rid)


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

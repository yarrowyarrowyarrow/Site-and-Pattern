"""
settings.py — Persistent configuration storage.

Lightweight JSON-backed config in ``~/.permadesign_config.json``. Used by
the collapsible-sidebar state and the polyculture-recipes migration shim.
The Permapeople API key UI lived here historically; it was removed once
the integration itself was retired.
"""

from __future__ import annotations

import json
import os

_CONFIG_PATH = os.path.join(os.path.expanduser("~"), ".permadesign_config.json")


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

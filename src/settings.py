"""
settings.py — Persistent configuration storage.

Lightweight JSON-backed config in ``~/.permadesign_config.json``. Used by
the collapsible-sidebar state and the polyculture-recipes migration shim.
A legacy plant-API key UI lived here historically; it was removed once
that integration itself was retired.
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


def get_mapbox_token() -> str | None:
    """Return the Mapbox access token from config or PERMADESIGN_MAPBOX_TOKEN env var."""
    cfg = load_config()
    return cfg.get("mapbox_token") or os.environ.get("PERMADESIGN_MAPBOX_TOKEN") or None


def set_mapbox_token(token: str) -> None:
    """Save the Mapbox access token to config. Pass empty string to clear."""
    cfg = load_config()
    if token.strip():
        cfg["mapbox_token"] = token.strip()
    else:
        cfg.pop("mapbox_token", None)
    save_config(cfg)

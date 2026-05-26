"""
bootstrap.py — Headless DB initialisation for CLI, MCP, and test contexts.

Call bootstrap_db() once before any DB use when running without Qt.
The Qt GUI path (src/app.py _init_database) delegates here too, so
there is a single canonical bootstrap entry point.
"""

from __future__ import annotations


def bootstrap_db() -> None:
    """Initialise the plant database without requiring Qt."""
    from src.db.plants import init_db
    init_db()

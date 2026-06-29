"""
tile_store.py — Shared primitives for the offline SQLite tile packs.

The building pack (``src/building_store.py``) and the terrain/contour pack
(``src/terrain_store.py``) follow the same "download once, then serve from
disk" model: a WAL SQLite file of zlib-compressed JSON blobs keyed by a
0.01° tile, deduplicated by a SHA1 of the geometry. This module holds the
pieces that were otherwise copy-pasted between the two stores — the
connection setup, the DDL applier, and the compress/hash helpers — so there
is exactly one definition of each. The on-disk format is unchanged (compact
JSON, zlib level 6), so existing packs stay readable.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import zlib
from typing import Any


def connect(db_path: str) -> sqlite3.Connection:
    """Open ``db_path`` in WAL mode (concurrent-read safe), 30 s busy timeout."""
    conn = sqlite3.connect(db_path, timeout=30)
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous = NORMAL")
    return conn


def ensure_schema(conn: sqlite3.Connection, ddl: str) -> None:
    """Apply a multi-statement ``ddl`` string (idempotent CREATE IF NOT EXISTS)."""
    for stmt in ddl.strip().split(";"):
        stmt = stmt.strip()
        if stmt:
            conn.execute(stmt)
    conn.commit()


def pack(obj: Any) -> bytes:
    """Serialize ``obj`` to compact JSON, zlib-compressed (the on-disk blob)."""
    return zlib.compress(json.dumps(obj, separators=(",", ":")).encode(), level=6)


def unpack(blob: bytes) -> Any:
    """Inverse of :func:`pack` — decompress + parse a stored blob."""
    return json.loads(zlib.decompress(blob))


def sha1_json(obj: Any) -> str:
    """Stable SHA1 of ``obj``'s compact JSON — the cross-tile dedupe identity."""
    return hashlib.sha1(
        json.dumps(obj, separators=(",", ":")).encode()).hexdigest()

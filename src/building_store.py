"""
building_store.py — SQLite-backed offline store for building footprints (V1.66).

The "download once, then work offline" half of the free building auto-import —
the exact model the Edmonton contour pack uses (``src/terrain_store.py``), but
for building footprints. A region's buildings are bulk-downloaded once (see
``src/building_downloader.py``) into 0.01°×0.01° tiles; any later design in that
area pulls its buildings straight from disk with no network, and feeds them
through the existing ``osm_features.add_features_to_project`` pipeline (so they
cast shade in 2D and extrude in 3D with zero new rendering code).

Stored items are the **OSM building item shape already used downstream**::

    {"kind": "building", "lat": .., "lng": .., "height_m": .., "radius_m": ..,
     "footprint": [[lng, lat], ...]}      # closed ring, GeoJSON order

so the store is source-agnostic: OSM today, NRCan/Microsoft footprints later
all reduce to the same dict.

Database location (separate from the design DB and the terrain cache, under the
shared per-user data folder, V1.69-renamed from ``PermaDesign`` to
``Site & Pattern`` — see ``src/user_paths.py``):
  Linux   : ~/.local/share/Site & Pattern/buildings.db
  macOS   : ~/Library/Application Support/Site & Pattern/buildings.db
  Windows : %APPDATA%\\Site & Pattern\\buildings.db
"""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import sys
import zlib

# Pure tile geometry is shared with the terrain pack — same 0.01° scheme.
from src.terrain_store import _tile_key, _tiles_for_bbox, _tiles_touched_by_line


def _db_path() -> str:
    from src import user_paths
    return os.path.join(str(user_paths.user_data_dir()), "buildings.db")


_DDL = """
PRAGMA journal_mode = WAL;
CREATE TABLE IF NOT EXISTS building_tiles (
    tile_key      TEXT PRIMARY KEY,
    data          BLOB NOT NULL,
    feature_count INTEGER
);
CREATE TABLE IF NOT EXISTS building_meta (
    key   TEXT PRIMARY KEY,
    value TEXT
);
"""


def _connect(path: str | None = None) -> sqlite3.Connection:
    conn = sqlite3.connect(path or _db_path(), timeout=30)
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous = NORMAL")
    return conn


def _ensure_schema(conn: sqlite3.Connection) -> None:
    for stmt in _DDL.strip().split(";"):
        stmt = stmt.strip()
        if stmt:
            conn.execute(stmt)
    conn.commit()


def _footprint_hash(item: dict) -> str:
    """Stable identity for a building, so the same footprint stored in two
    overlapping tiles (or fetched from two sub-bboxes) is counted once."""
    fp = item.get("footprint") or [[item.get("lng"), item.get("lat")]]
    return hashlib.sha1(
        json.dumps(fp, separators=(",", ":")).encode()).hexdigest()


def _tiles_for_item(item: dict) -> set:
    """Every tile key a building touches — its whole footprint, not just the
    centroid, so a building straddling a tile edge is found from either side."""
    fp = item.get("footprint")
    if fp and len(fp) >= 2:
        # footprint is [lng, lat]; the tiler wants [lat, lng].
        coords = [[p[1], p[0]] for p in fp if len(p) >= 2]
        if len(coords) >= 2:
            return _tiles_touched_by_line(coords)
    lat, lng = item.get("lat"), item.get("lng")
    if lat is None or lng is None:
        return set()
    return {_tile_key(lat, lng)}


class BuildingStore:
    """Short-lived connections per public method (WAL = concurrent-safe).
    Pass ``path`` to target a specific DB file (tests use a temp file)."""

    def __init__(self, path: str | None = None):
        self._path = path

    # ── query ────────────────────────────────────────────────────────────────

    def has_data(self) -> bool:
        try:
            with _connect(self._path) as conn:
                _ensure_schema(conn)
                row = conn.execute(
                    "SELECT value FROM building_meta WHERE key='complete'"
                ).fetchone()
                return row is not None and row[0] == "1"
        except Exception:  # noqa: BLE001 — a missing/corrupt cache means "no data"
            return False

    def feature_count(self) -> int:
        try:
            with _connect(self._path) as conn:
                _ensure_schema(conn)
                row = conn.execute(
                    "SELECT value FROM building_meta WHERE key='total_features'"
                ).fetchone()
                return int(row[0]) if row else 0
        except Exception:  # noqa: BLE001
            return 0

    def region(self) -> str:
        try:
            with _connect(self._path) as conn:
                _ensure_schema(conn)
                row = conn.execute(
                    "SELECT value FROM building_meta WHERE key='region'"
                ).fetchone()
                return row[0] if row else ""
        except Exception:  # noqa: BLE001
            return ""

    def buildings_in_bbox(self, bbox: dict) -> list:
        """Stored buildings overlapping ``bbox`` ({south,north,west,east}),
        deduped across tile boundaries by footprint identity. Returns the
        ready-to-import OSM item dicts (empty list on any failure)."""
        try:
            keys = _tiles_for_bbox(bbox["south"], bbox["north"],
                                   bbox["west"], bbox["east"])
            if not keys:
                return []
            seen: set[str] = set()
            out: list[dict] = []
            with _connect(self._path) as conn:
                _ensure_schema(conn)
                ph = ",".join("?" * len(keys))
                rows = conn.execute(
                    f"SELECT data FROM building_tiles WHERE tile_key IN ({ph})",
                    keys).fetchall()
            for (blob,) in rows:
                for item in json.loads(zlib.decompress(blob)):
                    h = _footprint_hash(item)
                    if h in seen:
                        continue
                    seen.add(h)
                    if _overlaps(item, bbox):
                        out.append(item)
            return out
        except Exception:  # noqa: BLE001
            return []

    # ── write ────────────────────────────────────────────────────────────────

    def add_buildings(self, items: list) -> int:
        """Merge ``items`` (OSM building dicts) into the tile store, deduping by
        footprint identity. Returns the number of *new* buildings stored (each
        counted once even though its footprint spans several tiles). Safe to
        call repeatedly as a region downloads."""
        # Unique input buildings, keyed by footprint identity.
        unique: dict[str, dict] = {}
        for item in items or []:
            if item.get("kind") != "building":
                continue
            unique.setdefault(_footprint_hash(item), item)
        if not unique:
            return 0
        # Every tile any of these buildings touches.
        tiles_for: dict[str, set] = {h: _tiles_for_item(it)
                                     for h, it in unique.items()}
        affected = set().union(*tiles_for.values()) if tiles_for else set()
        if not affected:
            return 0
        added = 0
        try:
            with _connect(self._path) as conn:
                _ensure_schema(conn)
                ph = ",".join("?" * len(affected))
                rows = conn.execute(
                    f"SELECT tile_key, data FROM building_tiles "
                    f"WHERE tile_key IN ({ph})", list(affected)).fetchall()
                tiles: dict[str, list] = {tk: json.loads(zlib.decompress(blob))
                                          for tk, blob in rows}
                present = {_footprint_hash(i)
                           for lst in tiles.values() for i in lst}
                for h, item in unique.items():
                    if h in present:
                        continue
                    present.add(h)
                    added += 1
                    for tk in tiles_for[h]:
                        tiles.setdefault(tk, []).append(item)
                if added:
                    conn.executemany(
                        "INSERT OR REPLACE INTO building_tiles "
                        "(tile_key, data, feature_count) VALUES (?,?,?)",
                        [(tk, zlib.compress(
                            json.dumps(lst, separators=(",", ":")).encode(),
                            level=6), len(lst))
                         for tk, lst in tiles.items()])
                    conn.commit()
        except Exception:  # noqa: BLE001
            return added
        return added

    def mark_complete(self, region: str, total: int) -> None:
        """Flag the pack ready so ``has_data`` returns True and the per-design
        import prefers the offline store over the live Overpass fetch."""
        try:
            with _connect(self._path) as conn:
                _ensure_schema(conn)
                conn.executemany(
                    "INSERT OR REPLACE INTO building_meta (key, value) "
                    "VALUES (?,?)",
                    [("complete", "1"), ("region", region),
                     ("total_features", str(int(total)))])
                conn.commit()
        except Exception:  # noqa: BLE001
            pass

    def clear(self) -> None:
        try:
            with _connect(self._path) as conn:
                _ensure_schema(conn)
                conn.execute("DELETE FROM building_tiles")
                conn.execute("DELETE FROM building_meta")
                conn.commit()
        except Exception:  # noqa: BLE001
            pass


def _overlaps(item: dict, bbox: dict) -> bool:
    """True when the building's footprint (or centroid) intersects ``bbox``.
    Tiles are ~1 km, so without this a corner tile could leak buildings a few
    hundred metres outside the requested area."""
    fp = item.get("footprint")
    pts = ([(p[1], p[0]) for p in fp if len(p) >= 2] if fp
           else [(item.get("lat"), item.get("lng"))])
    for la, ln in pts:
        if la is None or ln is None:
            continue
        if (bbox["south"] <= la <= bbox["north"]
                and bbox["west"] <= ln <= bbox["east"]):
            return True
    return False

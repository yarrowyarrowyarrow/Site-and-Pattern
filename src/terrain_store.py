"""
terrain_store.py — SQLite-backed store for offline terrain data.

Stores the full City of Edmonton 0.5 m LiDAR contour dataset in
0.01°×0.01° tiles so any bbox query is served instantly from disk.
Also stores Open-Meteo/Copernicus DEM grid responses for durability.

Database location (under the shared per-user data folder, V1.69-renamed from
``PermaDesign`` to ``Site & Pattern`` — see ``src/user_paths.py``):
  Linux   : ~/.local/share/Site & Pattern/terrain.db
  macOS   : ~/Library/Application Support/Site & Pattern/terrain.db
  Windows : %APPDATA%\\Site & Pattern\\terrain.db
"""

import math
import os
import sqlite3
from datetime import datetime, timezone
from typing import Optional

from src.tile_store import connect, ensure_schema, pack, sha1_json, unpack


# ── DB path ─────────────────────────────────────────────────────────────────

def _db_path() -> str:
    from src import user_paths
    return os.path.join(str(user_paths.user_data_dir()), "terrain.db")


# ── Tile key helpers ─────────────────────────────────────────────────────────

def _tile_key(lat: float, lng: float) -> str:
    """0.01° × 0.01° cell key, e.g. '5342_-11351'."""
    return f"{int(math.floor(lat * 100))}_{int(math.floor(lng * 100))}"


def _tiles_for_bbox(south: float, north: float, west: float, east: float) -> list[str]:
    """All tile keys whose cells overlap [south,north] × [west,east]."""
    lat0 = int(math.floor(south * 100))
    lat1 = int(math.floor(north * 100))
    lng0 = int(math.floor(west * 100))
    lng1 = int(math.floor(east * 100))
    keys = []
    for la in range(lat0, lat1 + 1):
        for lo in range(lng0, lng1 + 1):
            keys.append(f"{la}_{lo}")
    return keys


def _tiles_touched_by_line(coords: list) -> set:
    """
    Return all tile keys that a polyline (list of [lat, lng]) passes through.
    Steps at 0.005° (half-tile width) to avoid skipping tiles.
    """
    touched: set[str] = set()
    for i, (lat, lng) in enumerate(coords):
        touched.add(_tile_key(lat, lng))
        if i == 0:
            continue
        lat0, lng0 = coords[i - 1]
        steps = max(1, int(max(abs(lat - lat0), abs(lng - lng0)) / 0.005))
        for s in range(1, steps):
            t = s / steps
            touched.add(_tile_key(lat0 + t * (lat - lat0), lng0 + t * (lng - lng0)))
    return touched


# ── Schema ───────────────────────────────────────────────────────────────────

_DDL = """
PRAGMA journal_mode = WAL;
CREATE TABLE IF NOT EXISTS edmonton_tiles (
    tile_key      TEXT PRIMARY KEY,
    data          BLOB NOT NULL,
    elev_min      REAL,
    elev_max      REAL,
    feature_count INTEGER
);
CREATE TABLE IF NOT EXISTS edmonton_staging (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    tile_key TEXT NOT NULL,
    data     BLOB NOT NULL,
    elev_min REAL,
    elev_max REAL
);
CREATE INDEX IF NOT EXISTS edmonton_staging_tile ON edmonton_staging(tile_key);
CREATE TABLE IF NOT EXISTS srtm_grids (
    cache_key  TEXT PRIMARY KEY,
    data       BLOB NOT NULL,
    fetched_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS metadata (
    key   TEXT PRIMARY KEY,
    value TEXT
);
"""


def _connect() -> sqlite3.Connection:
    return connect(_db_path())


def _ensure_schema(conn: sqlite3.Connection) -> None:
    ensure_schema(conn, _DDL)


# ── TerrainStore ─────────────────────────────────────────────────────────────

class TerrainStore:
    """Short-lived connections per public method (WAL = safe for concurrent access)."""

    # ── Edmonton query ────────────────────────────────────────────────────

    def has_edmonton_data(self) -> bool:
        try:
            with _connect() as conn:
                _ensure_schema(conn)
                row = conn.execute(
                    "SELECT value FROM metadata WHERE key='edmonton_download_complete'"
                ).fetchone()
                return row is not None and row[0] == "1"
        except Exception:
            return False

    def get_edmonton_feature_count(self) -> int:
        try:
            with _connect() as conn:
                _ensure_schema(conn)
                row = conn.execute(
                    "SELECT value FROM metadata WHERE key='edmonton_total_features'"
                ).fetchone()
                return int(row[0]) if row else 0
        except Exception:
            return 0

    def get_edmonton_contours(self, bbox: dict, interval_m: float = 0.5) -> list:
        """
        Return contour features for bbox from the offline tile store.
        Deduplicates across tile boundaries by SHA1 of coord JSON.
        """
        try:
            south = bbox["south"]
            north = bbox["north"]
            west  = bbox["west"]
            east  = bbox["east"]
            keys  = _tiles_for_bbox(south, north, west, east)
            if not keys:
                return []

            seen_hashes: set[str] = set()
            results: list[dict] = []

            with _connect() as conn:
                _ensure_schema(conn)
                placeholders = ",".join("?" * len(keys))
                rows = conn.execute(
                    f"SELECT data FROM edmonton_tiles WHERE tile_key IN ({placeholders})",
                    keys
                ).fetchall()

            for (blob,) in rows:
                features = unpack(blob)
                for feat in features:
                    elev = feat.get("elevation_m", 0.0)
                    if interval_m > 0 and abs(round(elev / interval_m) * interval_m - elev) > 0.01:
                        continue
                    coords = feat.get("coords", [])
                    h = sha1_json(coords)
                    if h in seen_hashes:
                        continue
                    seen_hashes.add(h)
                    results.append(feat)

            return results
        except Exception:
            return []

    # ── Edmonton download helpers ─────────────────────────────────────────

    def store_edmonton_page(self, features: list) -> int:
        """
        Insert a page of converted features into the staging table.
        Each feature is: {"coords": [[lat, lng], ...], "elevation_m": float}
        Returns number of features stored.
        """
        if not features:
            return 0
        # Group by tile; a feature may belong to multiple tiles.
        tile_buckets: dict[str, list] = {}
        for feat in features:
            coords = feat.get("coords", [])
            if not coords:
                continue
            for tk in _tiles_touched_by_line(coords):
                tile_buckets.setdefault(tk, []).append(feat)

        try:
            with _connect() as conn:
                _ensure_schema(conn)
                rows = []
                for tk, feats in tile_buckets.items():
                    elevations = [f.get("elevation_m", 0.0) for f in feats]
                    blob = pack(feats)
                    rows.append((
                        tk,
                        blob,
                        min(elevations),
                        max(elevations),
                    ))
                conn.executemany(
                    "INSERT INTO edmonton_staging (tile_key, data, elev_min, elev_max) VALUES (?,?,?,?)",
                    rows
                )
                conn.commit()
        except Exception:
            pass

        return len(features)

    def mark_edmonton_complete(self, total: int) -> None:
        """
        Merge staging rows into the permanent edmonton_tiles table, then
        record completion metadata.  Runs inside one transaction.
        """
        try:
            with _connect() as conn:
                _ensure_schema(conn)
                # Collect all staging rows grouped by tile_key
                conn.execute("BEGIN EXCLUSIVE")
                rows = conn.execute(
                    "SELECT tile_key, data, elev_min, elev_max FROM edmonton_staging ORDER BY tile_key"
                ).fetchall()

                tile_data: dict[str, dict] = {}
                for tile_key, blob, elev_min, elev_max in rows:
                    page_feats = unpack(blob)
                    if tile_key not in tile_data:
                        tile_data[tile_key] = {
                            "features": [],
                            "elev_min": elev_min,
                            "elev_max": elev_max,
                        }
                    tile_data[tile_key]["features"].extend(page_feats)
                    tile_data[tile_key]["elev_min"] = min(tile_data[tile_key]["elev_min"], elev_min)
                    tile_data[tile_key]["elev_max"] = max(tile_data[tile_key]["elev_max"], elev_max)

                # Deduplicate within each tile by coord hash
                insert_rows = []
                for tk, td in tile_data.items():
                    seen: set[str] = set()
                    deduped = []
                    for feat in td["features"]:
                        h = sha1_json(feat.get("coords", []))
                        if h not in seen:
                            seen.add(h)
                            deduped.append(feat)
                    blob = pack(deduped)
                    insert_rows.append((tk, blob, td["elev_min"], td["elev_max"], len(deduped)))

                conn.execute("DELETE FROM edmonton_tiles")
                conn.executemany(
                    """INSERT OR REPLACE INTO edmonton_tiles
                       (tile_key, data, elev_min, elev_max, feature_count)
                       VALUES (?,?,?,?,?)""",
                    insert_rows
                )
                conn.execute("DELETE FROM edmonton_staging")
                now = datetime.now(timezone.utc).isoformat()
                conn.execute(
                    "INSERT OR REPLACE INTO metadata (key, value) VALUES (?,?)",
                    ("edmonton_download_complete", "1")
                )
                conn.execute(
                    "INSERT OR REPLACE INTO metadata (key, value) VALUES (?,?)",
                    ("edmonton_total_features", str(total))
                )
                conn.execute(
                    "INSERT OR REPLACE INTO metadata (key, value) VALUES (?,?)",
                    ("edmonton_downloaded_at", now)
                )
                conn.commit()
        except Exception as exc:
            raise RuntimeError(f"mark_edmonton_complete failed: {exc}") from exc

    def clear_edmonton(self) -> None:
        try:
            with _connect() as conn:
                _ensure_schema(conn)
                conn.execute("DELETE FROM edmonton_tiles")
                conn.execute("DELETE FROM edmonton_staging")
                conn.execute("DELETE FROM metadata WHERE key LIKE 'edmonton_%'")
                conn.commit()
        except Exception:
            pass

    # ── SRTM / Open-Meteo cache ───────────────────────────────────────────

    def get_srtm_grid(self, cache_key: str) -> Optional[dict]:
        try:
            with _connect() as conn:
                _ensure_schema(conn)
                row = conn.execute(
                    "SELECT data FROM srtm_grids WHERE cache_key=?", (cache_key,)
                ).fetchone()
                if row is None:
                    return None
                return unpack(row[0])
        except Exception:
            return None

    def store_srtm_grid(self, cache_key: str, data: dict) -> None:
        try:
            blob = pack(data)
            now  = datetime.now(timezone.utc).isoformat()
            with _connect() as conn:
                _ensure_schema(conn)
                conn.execute(
                    "INSERT OR REPLACE INTO srtm_grids (cache_key, data, fetched_at) VALUES (?,?,?)",
                    (cache_key, blob, now)
                )
                conn.commit()
        except Exception:
            pass

    # ── Storage info ──────────────────────────────────────────────────────

    def db_size_mb(self) -> float:
        try:
            return os.path.getsize(_db_path()) / (1024 * 1024)
        except Exception:
            return 0.0

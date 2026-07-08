---
name: offline-packs
description: Use when adding or changing a download-once offline data pack (SQLite tile store, GeoTIFF pack, or similar) — buildings, terrain/contours, soil — or wiring a bulk downloader + Qt worker + flow orchestration. Covers the shared tile_store primitives, user_paths as the single data-dir source, fetch-order conventions (pack → live → regional), the pure-loop-plus-Qt-worker split, and testing with stubbed downloads.
---

# Offline data packs (Site & Pattern)

## Purpose / when to use

The app is **offline-first**: expensive external data is downloaded **once** into
a per-user pack, then served from disk with no network on every later use. Three
packs exist today and share one architecture:

- **Buildings** (`buildings.db`) — OSM footprints in 0.01° tiles.
- **Terrain/contours** (`terrain.db`) — Edmonton 0.5 m LiDAR contours in 0.01°
  tiles + a SRTM/Open-Meteo grid cache.
- **Soil** (`soil/` GeoTIFFs) — Gridded Soil Landscapes of Canada, sampled by
  lat/lng.

Use this skill when adding a new pack, extending one, or changing the
download/serve/orchestration wiring. The two tile packs (buildings, terrain)
share `src/tile_store.py`; soil is a GeoTIFF pack that reuses the *pattern* but
not the tile store. Copy the closest existing pack rather than inventing a shape.

## The shared architecture (three layers)

Every pack is built from the same three-layer split. Keep them separate — the
pure core must stay Qt-free and headlessly testable.

1. **Store** (`*_store.py` / `soil_grid.py`) — the on-disk read/write API. Pure
   Python, no Qt, no network. Short-lived connections per public method (WAL =
   concurrent-read safe). Every method is failure-tolerant: a missing/corrupt
   pack returns `[]` / `None` / `False`, never raises.
2. **Downloader** (`*_downloader.py`) — a **pure `download_*` function** (the
   network fetch/opener is an injectable kwarg) *plus* a thin Qt
   `QObject`/`pyqtSignal` worker defined only when PyQt6 imports. The pure
   function is unit-tested headlessly; the worker just wraps it for a QThread.
3. **Flow** (`*_flow.py`) — free functions taking `main` (the MainWindow),
   kept **off** the controllers so they stay under their line ceilings. Wires
   the worker on a `QThread` with `progress`/`finished`/`error`/`cancel`, and
   provides the per-use "serve from pack if present" fast path.

### `src/tile_store.py` — the shared primitives (buildings + terrain)

Six functions, one definition each, so the two tile stores don't copy-paste:
- `connect(db_path)` — opens WAL mode, `synchronous=NORMAL`, 30 s busy timeout.
- `ensure_schema(conn, ddl)` — applies a multi-statement idempotent DDL string.
- `pack(obj)` / `unpack(blob)` — compact-JSON + zlib level 6 round-trip (the
  on-disk blob format; unchanged so existing packs stay readable).
- `sha1_json(obj)` — stable SHA1 of compact JSON = the **cross-tile dedupe
  identity** (a footprint stored in two overlapping tiles is counted once).

Tile geometry helpers live in `src/terrain_store.py` and are **imported by**
`building_store.py` (same 0.01° scheme — don't redefine them):
`_tile_key(lat,lng)` (`"5354_-11350"`, floor-based), `_tiles_for_bbox(...)`,
`_tiles_touched_by_line(coords)` (steps at 0.005° so it never skips a tile).

## How the three packs instantiate the pattern

| Concern | Buildings | Terrain | Soil |
|---|---|---|---|
| Store | `src/building_store.py` `BuildingStore` | `src/terrain_store.py` `TerrainStore` | `src/soil_grid.py` (module fns) |
| On-disk | `buildings.db` (tiles) | `terrain.db` (tiles + grid cache) | `soil/*.tif` GeoTIFFs |
| Downloader | `src/building_downloader.py` | `src/terrain_downloader.py` | `src/soil_downloader.py` |
| Flow | `src/building_flow.py` | (site-panel wiring) | `src/soil_flow.py` |
| "ready?" flag | `building_meta.complete='1'` | `metadata.edmonton_download_complete='1'` | `has_soil_pack()` (≥1 .tif present) |
| Pure download seam | `download_region(..., fetch_fn=)` | worker uses `terrain._http_get_json` | `download_soil_pack(..., opener=)` |

Note the **staging→commit** wrinkle in terrain: pages land in
`edmonton_staging`, then `mark_edmonton_complete` merges + dedupes them into
`edmonton_tiles` inside one `BEGIN EXCLUSIVE` transaction. Buildings merge
directly into `building_tiles` on each `add_buildings` call (dedupe by footprint
hash). Both mark the pack `complete` only when the run finished — a **cancel
leaves a partial cache that `has_data()` still reports `False` for**, so a
partial download is never mistaken for a finished one.

## `src/user_paths.py` — the single source of the data dir

Every pack DB/dir lives under one per-user folder computed **only** in
`src/user_paths.py`. Never re-derive the platform base yourself.

- `user_data_dir()` → `str`, **migrates the legacy `PermaDesign` folder + creates
  the dir** (uses `os.makedirs`, safe under `os.name` patching). The offline
  stores call this: `os.path.join(str(user_paths.user_data_dir()), "buildings.db")`.
- `data_dir_path()` → `Path`, **pure**, no side effects (the DB layer's
  import-time constants use this).
- `migrate_legacy_into(target)` — the one-time `PermaDesign → Site & Pattern`
  rename; must run *before* the new folder is created (its guard is
  `target.exists()`).

A new pack's `_db_path()` / `pack_dir()` **must** join onto
`user_paths.user_data_dir()` — do not hardcode a path or read `_DATA_DIR` from
`plants.py`. `tests/test_polycultures.py` asserts nothing lands in the source
tree.

## Fetch-order conventions (pack → live → regional)

Consumers try the offline pack **first**, then a live source, then a bundled
regional approximation — and every result carries a `source` string so the UI
labels it honestly (P9 — never present an approximation as a point measurement).

- **Soil** (`property_data.fetch_soil`): `soil_grid.sample_soil` (offline pack,
  instant, real) → SoilGrids v2.0 (online, often paused) →
  `_prairie_soil_fallback` (`data/soil_fallback_prairie.json`, nearest centroid).
- **Buildings** (`building_flow.import_buildings_offline`): if
  `BuildingStore().has_data()` and the bbox has buildings, place them from disk
  and return `True` so the caller **skips** the live Overpass fetch; else return
  `False` to fall through to the online import.
- **Terrain elevation** (`property_data.fetch_elevation`): Open-Meteo Copernicus
  DEM → Edmonton LiDAR pack (`terrain.lookup_point_elevation_edmonton`) for
  higher resolution / river-valley null fill.

When you add a pack, insert it at the **front** of the relevant fetch chain and
set a distinctive `source` (e.g. `"… (offline pack)"`). Return `None` cleanly
when the pack is absent so the chain continues.

## Adding a NEW pack, step by step

1. **Decide store shape.** Tiled geo blobs → reuse `src/tile_store.py`
   (`connect`/`ensure_schema`/`pack`/`sha1_json`) and terrain's tile helpers,
   copying `building_store.py`. Raster/point files → copy `soil_grid.py`.
2. **Write the store** (`src/<thing>_store.py` or module fns). `_db_path()` /
   `pack_dir()` joins onto `user_paths.user_data_dir()`. Wrap every public method
   in `try/except → safe empty` so a missing/corrupt pack degrades. Provide a
   `has_data()`/`has_*_pack()` readiness check and a `clear()`.
3. **Write the downloader** (`src/<thing>_downloader.py`): a pure
   `download_*(..., fetch_fn|opener=None, on_progress=None, should_cancel=None)`
   loop (default the fetcher lazily inside so tests inject a stub), then the
   `if _HAVE_QT:` worker mirroring `BuildingDownloadWorker`
   (`progress`/`finished`/`error` signals, `cancel()`). Mark complete only if
   the loop ran to the end (respect `should_cancel`).
4. **Write the flow** (`src/<thing>_flow.py`): a `start_<thing>_download(main)`
   that wires the worker on a `QThread` (copy `soil_flow.start_soil_download` /
   `building_flow.start_building_download` signal wiring verbatim — thread/worker
   state on `main._<thing>_dl_thread`/`_worker`, disconnect the cancel button in
   the `finished`-thread cleanup), and a per-use "serve from pack" helper.
5. **Insert into the fetch chain** at the front, with an honest `source`.
6. **Test headlessly** (next section).
7. If the pack is a **seeded/derived DB table** (not a standalone file), it also
   needs a schema-version bump + reseed-wipe entry — see the `schema-change`
   skill. Standalone pack files (`buildings.db`, `soil/`) do **not** touch the
   design DB or `_SCHEMA_VERSION`.

## Testing with stubbed downloads

The whole point of the pure-core split is headless tests with **no network and
no Qt**. Patterns from the existing tests:

- **Store round-trip against a temp file** (`tests/test_building_store.py`):
  `BuildingStore(os.path.join(tempfile.mkdtemp(), "buildings.db"))` — pass an
  explicit `path` so the real user pack is never touched. Assert add→query
  round-trip, cross-tile dedup, far-bbox empty, `has_data()`/`clear()` lifecycle,
  non-matching items ignored.
- **Temp-`_db_path` monkeypatch** (`tests/test_terrain_store.py`):
  `mock.patch.object(ts, "_db_path", return_value=self._db)` for a store whose
  path isn't injectable. Also unit-tests the **pure tile geometry** with no DB at
  all.
- **Injected opener/sampler** (`tests/test_soil_downloader.py`,
  `tests/test_soil_grid.py`): pass `opener=lambda url: fake_zip_bytes` to
  `download_soil_pack`; write tiny synthetic GeoTIFFs into a temp pack dir for
  `sample_soil` (guarded by `@unittest.skipUnless(_HAVE_RASTERIO, ...)` since
  `rasterio`/`pyproj` are optional deps — your pack must degrade to `None` when
  they're absent, and the fetch chain must continue).
- **Fetch-order test** (`tests/test_soil_grid.py::TestFetchSoilOrdering`):
  monkeypatch both `soil_grid.sample_soil` and `property_data._http_get_json` to
  prove pack-first, then regional-fallback ordering. Restore in `tearDown`.
- **Pure download loop** (`tests/test_building_downloader.py`): call
  `download_region(bbox, store, fetch_fn=fake, pace_s=0)` (set `pace_s=0` so the
  politeness `time.sleep` doesn't slow the test) and assert stored counts +
  `should_cancel` short-circuit behaviour.

## Key files

| Path | Role |
|---|---|
| `src/tile_store.py` | Shared connect / ensure_schema / pack / unpack / sha1_json for tile packs. |
| `src/user_paths.py` | Single source of the per-user data dir + legacy-folder migration. |
| `src/building_store.py` | `BuildingStore` — footprint tiles, footprint-hash dedupe, bbox query. |
| `src/building_downloader.py` | Pure `download_region` + `BuildingDownloadWorker`. |
| `src/building_flow.py` | `import_buildings_offline` (fast path) + `start_building_download`. |
| `src/terrain_store.py` | `TerrainStore` (staging→commit contours + SRTM cache) + tile geometry helpers. |
| `src/terrain_downloader.py` | Edmonton LiDAR bulk downloader (Socrata + bundled-seed fallback). |
| `src/soil_grid.py` | GeoTIFF pack sampler (`sample_soil`, `has_soil_pack`, `soil_pack_dir`). |
| `src/soil_downloader.py` | Pure `download_soil_pack(opener=)` + `SoilDownloadWorker`. |
| `src/soil_flow.py` | `apply_soil_site_fields` + `start_soil_download`. |
| `src/property_data.py` | `fetch_soil`/`fetch_elevation` — the pack→live→regional chains. |
| `tests/test_building_store.py` / `test_soil_grid.py` / `test_terrain_store.py` / `test_soil_downloader.py` / `test_building_downloader.py` / `test_building_flow.py` | The headless test patterns to copy. |

## Pitfalls & gotchas

- **Never touch the real user pack in a test.** Pass an explicit `path=` (store
  supports it) or monkeypatch `_db_path`/`pack_dir`. The building/soil stores
  take a temp file; terrain patches `_db_path`.
- **Cancel must not leave a "ready" pack.** `mark_complete`/`mark_edmonton_complete`
  is the *only* thing that flips the ready flag, and the loops skip it on
  `should_cancel`. If you add a new pack, replicate this or a cancelled partial
  download will be served as complete.
- **Optional deps degrade, don't crash.** `soil_grid`/`hrdem` import
  `rasterio`/`pyproj` lazily inside functions and return `None` on `ImportError`.
  Frozen macOS/Windows builds ship them as *optional* (see the latest commit
  moving rasterio/pyproj to optional reqs) — a pack that hard-imports them at
  module top would break those builds.
- **Dedupe identity is content-based.** Buildings dedupe by `sha1_json` of the
  footprint ring across tiles; a building on a 0.01° boundary lands in multiple
  tiles and must still return once (`test_dedup_across_tiles`). Keep dedupe in
  the store, not the caller.
- **Politeness pacing** — the region downloaders `time.sleep(pace_s)` between
  Overpass calls (`_PACE_S = 1.0`). Pass `pace_s=0` in tests; keep it in prod
  (the public Overpass instance rate-limits hard).
- **Store methods swallow exceptions by design** (`except Exception: return
  <empty>`). That's correct for graceful degradation but means a real bug hides
  as "no data" — assert positively (round-trip a known value) in tests rather
  than trusting an empty return.
- **Keep the store Qt-free.** Only the worker class imports PyQt6, guarded by
  `try/except ImportError: _HAVE_QT = False`. The store and pure download loop
  must import headlessly.

## Validation (run these)

From the repo root:

```bash
# The offline-pack test spine (soil tests skip cleanly if rasterio is absent):
python -m unittest tests.test_building_store tests.test_soil_grid tests.test_terrain_store \
    tests.test_soil_downloader tests.test_building_downloader tests.test_building_flow -v

# Full suite before done (stdlib unittest only — no pytest):
python -m unittest discover -s tests
```

The `unittest` command above was run in this session and passes (`OK`, with the
rasterio-dependent soil cases auto-skipped when the lib is missing).

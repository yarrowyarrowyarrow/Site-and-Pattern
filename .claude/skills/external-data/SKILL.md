---
name: external-data
description: Use when adding or changing a networked data source (Open-Meteo, SoilGrids, Nominatim, Overpass/OSM, NRCan, iNaturalist images) or its cache/fallback — anything calling http_utils.http_get_json or urllib. Covers the offline-first discipline (graceful degradation, DB-cached results, regional fallback JSONs), the fetch-order chains in property_data.py, SSL bootstrap for frozen builds, timeout discipline, and testing network code without a network.
---

# Networked data sources (Site & Pattern)

## Purpose / when to use

The app pulls climate, soil, elevation, wind, hardiness, addresses, OSM
features, and open-licensed photos from free public APIs — but it must remain
**fully usable offline**. Every fetcher degrades gracefully: on any failure it
returns `None`/`[]`/`False` so the UI shows "unavailable" instead of crashing,
and results are cached (DB or file) so a second use needs no network. Use this
skill when adding a new external source or touching an existing fetch/cache/
fallback path.

## The offline-first philosophy (non-negotiable)

Three layers of resilience, in priority order:

1. **Cache first.** A previously-fetched result (DB table or file cache) is
   served with no network. Wind and climate cache in SQLite (`wind_cache`,
   `climate_cache`); photos cache under the user-data dir (`image_cache.py`).
2. **Live fetch, graceful.** On a cache miss, fetch — but **every network call
   returns `None` on any error** (`http_utils.http_get_json` wraps the whole
   thing in `except Exception: return None`). Callers must handle `None`.
3. **Bundled regional fallback.** When there's nothing cached and the network is
   down, a bundled nearest-centroid approximation keeps the UI useful:
   `data/rainfall_fallback_prairie.json`, `data/soil_fallback_prairie.json`,
   `data/wind_fallback_prairie.json`, `data/hardiness_zones.json`. These are
   **labelled honestly** via the result's `source` string (P9 — an approximation
   is never presented as a point measurement).

## `src/http_utils.py` — the one HTTP helper

All JSON-over-HTTP goes through `http_get_json(url, timeout=20.0)`: sets the
`User-Agent`, applies the timeout, returns parsed JSON or `None`. **Do not
hand-roll `urllib` for JSON** — use this. Each fetcher module keeps a thin
module-local `_http_get_json` wrapper (with its own default timeout) *purely so
tests can monkeypatch `<module>._http_get_json`* — the real logic stays in one
place. Mirror that: add a `_http_get_json` alias in your module and call it, so
your tests have a seam.

The User-Agent deliberately keeps the pre-rebrand string
(`"PermaDesign/1.0 ..."`) — see CLAUDE.md; don't "fix" it to Site & Pattern.

### Timeout discipline

Defaults exist for a reason — match the endpoint's cost:
- `property_data._TIMEOUT = 8.0` for quick point queries (soil, elevation,
  geocode); the multi-year archive rainfall call overrides to `20.0` and
  hardiness stays at the 8 s default.
- `wind.fetch_current_wind` uses `12.0`; the hourly archive fetch uses the 20 s
  default (it's ~17k rows).
- `osm_features._TIMEOUT = 25.0`, `hrdem._TIMEOUT = 25.0`,
  `soil_downloader` opener `120.0` (a large one-time download).
Pick a timeout proportional to the payload; a too-short timeout on a big archive
call silently degrades to the fallback on slow connections.

## Fetch-order chains in `property_data.py`

`property_data.py` is the aggregator (`fetch_all` calls each). Learn the chains —
they encode the offline-first priority and are the model for any new source:

- **`fetch_rainfall`**: bundled EC climate normal within `_NORMAL_MAX_KM` (150
  km) → live Open-Meteo ERA5-Land (10-yr mean, labelled *not a normal*) →
  nearest EC normal regardless of distance (last-resort offline).
- **`fetch_soil`**: offline Gridded-SLC pack (`soil_grid.sample_soil`) →
  SoilGrids v2.0 (ISRIC, often paused) → `_prairie_soil_fallback` (bundled
  regional). See the `offline-packs` skill for the pack side.
- **`fetch_elevation`**: Open-Meteo Copernicus DEM → Edmonton LiDAR pack
  (`terrain.lookup_point_elevation_edmonton`) for resolution / river-null fill;
  returns partial (elevation-only) rather than nothing when neighbours are over
  water.
- **`fetch_hardiness`**: local `data/hardiness_zones.json` (`climate.get_zone`,
  bbox lookup) → derive USDA zone from ERA5-Land extreme-min temp.
- **`geocode_address` / `reverse_geocode`**: OSM Nominatim, prairie viewbox
  (AB+SK), client-side re-ranking; `[]`/`None` on failure.

A new source slots into the front of the relevant chain, returns the **same dict
shape** as its siblings (so the display/cache need no special case — see how
`soil_grid.sample_soil` matches `_parse_soilgrids` output), and sets a
distinctive `source`.

## DB-cached fetchers (wind, climate)

`wind.get_wind_summary` is the reference for a DB-cached fetch:
```
if use_cache: cached = get_cached_wind(lat, lng)   # → wind_cache table
              if cached: return {**cached, "cached": True}
rows = _fetcher(lat, lng)          # injectable seam for tests
if not rows: return None
rose = compute_wind_rose(rows)     # PURE aggregation, unit-testable
store_cached_wind(lat, lng, rose)  # best-effort; cache failure never blocks result
```
Key points to replicate: the cache is keyed on lat/lng **quantized to 0.01°**
(`_quantize_latlng` in `plants.py`, ~1 km — nearby pins reuse a fetch); the
storage helpers live in `src/db/plants.py` (`get_cached_*`/`store_cached_*`);
the aggregation is a **pure function** separate from the fetch so it's tested
without network; the fetcher is an injectable kwarg (`_fetcher=`). These cache
tables are **wiped on reseed** (they're per-location user data, not seeded) — if
you add one, add it to the reseed wipe list (see the `schema-change` skill).

## Off-thread fetching (the Qt worker pattern)

Network fetches must not block the UI thread. `src/wind_flow.py` is the canonical
`main`-taking flow: build a `QThread` + a `_WindFetchWorker(QObject)` with a
`done = pyqtSignal(object)`, `moveToThread`, connect `started→run`,
`done→apply`, `done→quit`, `finished→cleanup`, `start()`. The worker's `run`
wraps each fetch in `try/except → None` and, when the live fetch yields nothing,
falls back to the bundled regional approximation (`wind_flow._fallback_rose`
reads `data/wind_fallback_prairie.json` by nearest centroid). Keep worker/thread
state on `main` (`main._wind_thread`/`_wind_worker`) so it isn't GC'd. The flow
lives **off** the controllers (line-ceiling discipline). Copy this for any new
off-thread source.

## `src/ssl_bootstrap.py` — HTTPS for frozen builds

macOS OpenSSL Pythons and PyInstaller-frozen builds may have **no usable CA
bundle**, so every `https urlopen()` fails with `CERTIFICATE_VERIFY_FAILED` —
*silently*, because the fetchers degrade to offline fallbacks. The symptom is
"photos, elevation, OSM, address search all just don't work" while the base map
(QtWebEngine, own root store) keeps working.

`ensure_ca_bundle()` fixes this: it points `SSL_CERT_FILE` at certifi's Mozilla
bundle **always on macOS** (a merely-present OpenSSL bundle proved
untrustworthy — stale Homebrew cert.pem), and elsewhere only when the default
context loads **zero** CA certs (checked functionally via `cert_store_stats`,
not by path existence). It's idempotent, respects an existing
`SSL_CERT_FILE`/`SSL_CERT_DIR`, and **must run before the first https request**
(called once at startup). If you add a network feature and it "works in dev but
not in the packaged app", this is the first suspect. Don't disable TLS
verification to work around it.

## Image fetching (`src/image_cache.py`)

Open-licensed flora/fauna photos: `get_cached_image(url)` is **cache-only, never
blocks** — safe on the paint path; `resolve_image`/`fetch_and_cache_image` do the
network fetch **off** the paint path. Downloads cache under the user-data dir with
a JSON sidecar carrying attribution + license (so the citation always travels
with the file). A local file path is returned as-is; failures return `None`. Note
the descriptive User-Agent — some hosts (iNaturalist) reject the default urllib
agent with HTTP 403. Licence compliance for bee photos (CC0/CC-BY only) is gated
in `data_quality.validate_fauna_images` (see the `seed-data` skill).

## Adding a new external source correctly

1. Fetch via a module-local `_http_get_json` alias over
   `http_utils.http_get_json`; pick a timeout proportional to payload size.
2. **Return `None`/`[]` on any failure** — never let an exception escape.
3. Return the **same dict shape** as the sibling source it slots beside, with a
   distinctive `source` string. Insert at the front of the relevant
   `property_data` chain (or add a new `fetch_*` + wire into `fetch_all`).
4. If results are worth reusing, add a **cache** (DB table via `plants.py`
   `get_cached_*`/`store_cached_*`, quantized key; or a file cache like
   `image_cache`). Cache tables get wiped on reseed → add to the wipe list.
5. If a fully-offline experience matters, add a **bundled regional fallback**
   JSON in `data/` and a nearest-centroid reader (copy
   `_prairie_soil_fallback` / `wind_flow._fallback_rose`).
6. If it's slow, run it **off-thread** in a `*_flow.py` worker (copy
   `wind_flow`).
7. Keep the pure parsing/aggregation in a **separate pure function** so it's
   unit-testable without network.

## Testing network code without a network

Every test in this repo runs offline. Patterns:
- **Monkeypatch the module-local `_http_get_json`** to return canned JSON (or
  `None` to force the fallback). `tests/test_property_data.py` and
  `tests/test_wind.py` do exactly this; `test_soil_grid.py::TestFetchSoilOrdering`
  patches both `soil_grid.sample_soil` and `property_data._http_get_json` to
  prove chain ordering. Restore in `tearDown`.
- **Inject the fetcher seam.** `wind.get_wind_summary(_fetcher=fake)` and the
  downloader `opener=`/`fetch_fn=` kwargs let you drive the pure loop with no
  network.
- **Parse captured fixtures.** `osm_features` / `hrdem` tests feed captured
  Overpass / STAC JSON to the pure parsers — the live API is never hit in CI.
- **Temp DB for cache tests.** Cache-table tests redirect the DB to a
  `tempfile.mkdtemp` dir before importing `src.db.plants` (see the temp-DB
  pattern in the `schema-change` skill).

## Key files

| Path | Role |
|---|---|
| `src/http_utils.py` | The one `http_get_json` helper (UA, timeout, `None` on failure). |
| `src/ssl_bootstrap.py` | `ensure_ca_bundle()` — HTTPS for macOS/frozen builds; run once at startup. |
| `src/property_data.py` | Aggregator + the pack→live→regional fetch chains (rainfall/soil/elevation/hardiness/geocode). |
| `src/climate.py` | Hardiness bbox lookup + GDD/frost (DB-cached in `climate_cache`). |
| `src/wind.py` | Wind rose fetch + pure aggregation + `wind_cache` DB cache. |
| `src/wind_flow.py` | Off-thread wind fetch worker + regional fallback (`wind_fallback_prairie.json`). |
| `src/osm_features.py` | Overpass buildings/trees import (retry + mirror; graceful `[]`). |
| `src/hrdem.py` | NRCan HRDEM elevation (STAC + COG windowed reads; injectable seams). |
| `src/image_cache.py` | Open-licensed photo cache + attribution sidecar. |
| `data/rainfall_fallback_prairie.json` / `soil_fallback_prairie.json` / `wind_fallback_prairie.json` / `hardiness_zones.json` | Bundled regional fallbacks / lookups. |
| `tests/test_property_data.py` / `test_wind.py` / `test_climate.py` / `test_climate_cache.py` / `test_image_cache.py` / `test_ssl_bootstrap.py` / `test_osm_features.py` / `test_hrdem.py` | The offline test patterns to copy. |

## Pitfalls & gotchas

- **Silent degradation hides bugs.** Because failures return `None` and fall
  back, a broken URL or a too-short timeout looks like "offline". Test the
  *happy path* with a canned-JSON stub, not just the fallback.
- **Patch the module-local alias, not `http_utils`.** Fetchers call
  `<module>._http_get_json`; monkeypatching `http_utils.http_get_json` directly
  won't intercept them.
- **Cache key is quantized to 0.01°.** Two pins within ~1 km share a cached
  fetch (`_quantize_latlng`). That's intended; don't add per-decimal keys.
- **`source` strings are load-bearing** — the UI labels reanalysis vs normal vs
  regional approximation from them (P9). Set a truthful one; don't reuse a
  sibling's.
- **Reseed wipes cache tables.** `climate_cache`/`wind_cache`/`shade_zone_cache`
  are wiped on every reseed (they're derived/per-location, not seeded). A new
  cache table must be added to the wipe list or it accumulates stale rows.
- **Frozen-build TLS.** If a feature works in dev but not the packaged app,
  suspect the CA bundle (`ssl_bootstrap`), and follow the proxy README rather
  than disabling verification.
- **Politeness.** Public Overpass/Nominatim rate-limit hard; `osm_features`
  retries once + tries a mirror. Don't hammer them in a loop without pacing.
- **P12.** External sources can carry Indigenous plant-use / traditional-knowledge
  content in their metadata. Do **not** ingest or operationalize it into the data
  model, recommendations, or UI without free, prior, and informed consent — stop
  and raise it with the user.

## Validation (run these)

From the repo root:

```bash
# The networked-source test spine (all real unittest.TestCase modules; run fully offline):
python -m unittest tests.test_wind tests.test_climate_cache tests.test_image_cache \
    tests.test_ssl_bootstrap tests.test_osm_features tests.test_hrdem -v

# Full suite before done (stdlib unittest only — no pytest):
python -m unittest discover -s tests
```

The `unittest` command above was run in this session and passes (`OK`, one
rasterio-dependent case skipped). **Gotcha:** `tests/test_property_data.py` and
`tests/test_climate.py` are written as **bare pytest-style `def test_*`
functions with no `unittest.TestCase` class**, so `python -m unittest
tests.test_property_data` collects **0 tests** (it exits `OK` but runs nothing),
and `unittest discover` does not execute their assertions either. There is no
pytest configured in this repo, so those modules' assertions currently don't run
in the standard gate — if you rely on them, add a `unittest.TestCase` wrapper or
run them under pytest explicitly. Prefer the TestCase-based modules above for a
signal that actually executes.

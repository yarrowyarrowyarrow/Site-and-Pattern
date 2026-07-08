---
name: debugging
description: Use when chasing a runtime bug — empty panels or "no such table", stale seed data after editing data/*.json, FK constraint failures, a blank/white map, dead network features, or frozen-build-only crashes. Symptom→cause→fix playbook plus where the real user DB lives per-OS, how to inspect it, where Qt warnings and JS console output go, and the SSL/resource-path traps specific to this app.
---

# Debugging playbook

Start from the symptom. Each row links to the detail section below.

| Symptom | Most likely cause | Fix |
|---|---|---|
| Empty panels / `sqlite3 ... no such table` | DB not initialised, or a bundled data file not found in a frozen build | Reinit DB; confirm `resource_path` + `.spec` `datas` (§1) |
| Edited `data/*.json` but the app shows old data | `_SCHEMA_VERSION` not bumped → no reseed on existing installs | Bump the version (§2) |
| `FOREIGN KEY constraint failed` | Insert order / stale row vs FKs-on-at-runtime | §3 |
| DB seems to be in the "wrong" place, or edits don't take | Looking at the source tree, not the per-user data dir | §4 (per-OS paths) |
| Blank / white map area | Web assets not found, or WebEngine can't render | §5 |
| No plant photos / no elevation / OSM import empty | Missing CA certs (SSL) or offline with no fallback | §6 |
| Works from source, crashes only when installed | Frozen-build resource resolution / missing hidden import | §7 |

---

## 1. Empty panels / "no such table"

Two distinct causes:

- **Source checkout:** the DB was never seeded. `init_db()`
  (`src/db/plants.py`) is idempotent and runs on first GUI launch and on
  the first facade call. Force it: `python3 -c "from src.db.plants import
  init_db; init_db()"`. Then inspect (§4).
- **Frozen build:** a bundled data/schema file isn't found. The file must
  be (a) listed in `scripts/packaging/permadesign.spec` under `datas`, and
  (b) read via `src/resources.py` `resource_path(...)`, never a
  `__file__`-relative join. This exact bug once produced "No such file:
  schema.sql" on installed builds; `tests/test_resource_path.py` guards it.

## 2. Stale seed data after editing `data/*.json`

`init_db()` only reseeds when it decides `needs_reseed` — which is
`count < 100` **or** `current_version < _SCHEMA_VERSION`. So editing seed
JSON without bumping `_SCHEMA_VERSION` (`src/db/plants.py`, currently 45)
means existing installs keep the old rows: the version check is the *only*
trigger that fires the reseed on a populated DB. This is the #1 "my data
change didn't show up" cause. See the `schema-change` and `seed-data`
skills. To force it locally, bump the version, or just delete the user DB
(§4) so the next launch reseeds from scratch.

## 3. FK constraint failures

FK enforcement is **ON at runtime** (`get_connection` sets
`PRAGMA foreign_keys = ON`) but **temporarily OFF during the bulk reseed**.
This matters because Python 3.14 enforces FKs at statement time rather than
at transaction commit, so seeding a child row before its parent would fail
mid-reseed; the reseed path disables FKs for the duration and re-enables
after. If you hit a FK error:

- In normal operation: you're inserting a child (e.g. a `plant_uses` /
  `plant_fauna` row) whose parent id doesn't exist. Insert the parent first,
  or fix the id.
- During a reseed you wrote: make sure your new seed step runs inside the
  FK-off window in `init_db`, following the existing `_seed_*` helpers.
- If you added a dependent table, it must also be added to the reseed
  **wipe list** in `init_db` or it accumulates stale rows across reseeds
  (see `schema-change`).

## 4. Where the real user DB lives (per-OS) + inspecting it

The single source of truth is `src/user_paths.py`. The per-user data folder
is `<base>/Site & Pattern/`, where `<base>` is:

| OS | Base | Full DB path |
|---|---|---|
| Linux | `$XDG_DATA_HOME` or `~/.local/share` | `~/.local/share/Site & Pattern/permadesign.db` |
| macOS | `~/Library/Application Support` | `~/Library/Application Support/Site & Pattern/permadesign.db` |
| Windows | `%APPDATA%` | `%APPDATA%\Site & Pattern\permadesign.db` |

Notes:
- The **filename stays `permadesign.db`** (internal legacy name — deliberate).
- The **folder** was `PermaDesign` before V1.69 and is renamed once, in
  place, on first launch (`user_paths.migrate_legacy_into`). If a migration
  half-happened, you may see both folders; the code no-ops if the target
  already exists.
- **Never** put the DB in the source tree — `tests/test_polycultures.py`
  asserts against it.

Inspect it (Linux example):

```bash
sqlite3 "$HOME/.local/share/Site & Pattern/permadesign.db" \
  ".tables" "SELECT COUNT(*) FROM plants;" "PRAGMA user_version;"
```

`PRAGMA user_version` is where the schema version is stored
(`_get_schema_version` / `_set_schema_version`); compare it to
`_SCHEMA_VERSION` in `src/db/plants.py` to see whether a reseed is pending.

**Reset to clean state (destroys the user's designs in that DB):** delete
the `permadesign.db` file (or the whole `Site & Pattern` folder) — the next
launch recreates and reseeds it. Warn the user first; saved
`.perma.geojson` project files elsewhere are unaffected.

## 5. Blank / white map

The map is Leaflet inside `QWebEngineView` (`src/map_widget.py`), loading
`html/map.html` + the six `html/map/*.js` files. Causes:

- Web assets not resolved in a frozen build — same `resource_path` / `.spec`
  `datas` issue as §1, but for `html/`.
- WebEngine can't initialise (missing system libs / sandbox). Run from a
  terminal (§7) to see the Chromium error.
- A JS error broke page init. See "seeing JS output" below.

**Seeing JS console output / renderer errors:** `src/map_widget.py` routes
the embedded page's `console.*` messages into Python
(`javaScriptConsoleMessage` on the page). Run the app from a terminal and
watch stdout/stderr. See the `map-frontend` skill for the bridge and console
routing detail.

## 6. Network features dead (photos / elevation / OSM / climate)

Offline-first is by design — the app must degrade gracefully — so a dead
feature is usually **certs**, not logic:

- macOS Pythons and frozen builds ship **no root certificates**, so every
  HTTPS fetch fails silently while the Leaflet map (Chromium, own cert
  store) keeps working. `src/ssl_bootstrap.py` (`ensure_ca_bundle`) wires
  `certifi`'s CA bundle at startup; if it's missing, `pip install -r
  requirements.txt` so `certifi` is present, then rebuild if packaging.
- Genuinely offline: fetches fall back to DB-cached results and the
  `data/*_fallback_prairie.json` regional defaults. See `external-data`.
- In this sandbox, outbound HTTPS goes through a proxy — a fetch that hangs
  is usually waiting on that, not broken code.

## 7. Frozen build differs from source

- Run the installed binary from a terminal to see the traceback:
  - Windows: `"C:\Program Files\Site & Pattern\SiteAndPattern.exe"`
  - macOS: `dist/SiteAndPattern.app/Contents/MacOS/SiteAndPattern`
  - Linux: `./dist/SiteAndPattern/SiteAndPattern`
- "Missing module": add it to `hiddenimports` in
  `scripts/packaging/permadesign.spec`.
- Missing data/html: add to `datas` in the same spec and read via
  `resource_path`.
- See the `release-packaging` skill and `docs/BUILD.md` troubleshooting.

## Diagnostics quick reference

- **Qt warnings** are filtered by a message handler installed in `main.py`
  (keeps the console readable); if you're missing an expected Qt warning,
  that filter is why. Loosen it temporarily while debugging.
- **Typed errors:** the facade/domain raise `src/errors.py` exceptions
  (`ProjectError`, `AnalysisError`, …) rather than popping Qt dialogs — good
  places to breakpoint.
- **Reproduce headlessly** whenever possible via the facade (see
  `agent-api`) — it isolates domain bugs from Qt.

## Key files

| Path | What |
|---|---|
| `src/user_paths.py` | Per-OS data dir + legacy folder migration (source of truth). |
| `src/db/plants.py` | `init_db`, reseed decision, FK pragma, `_SCHEMA_VERSION`. |
| `src/resources.py` | `resource_path` — frozen-build-safe bundled-file resolution. |
| `src/ssl_bootstrap.py` | CA-bundle wiring for headless/frozen HTTPS. |
| `src/http_utils.py` | Shared fetch helpers + timeouts. |
| `main.py` | Qt warning-message filter; app entry. |
| `src/map_widget.py` | Map view; JS console-message routing. |
| `src/errors.py` | Typed exception hierarchy. |
| `docs/BUILD.md` | Troubleshooting section for installed builds. |

## Validation

Reproduce the suspected path headlessly, then confirm the fix with the
relevant test module (see `testing`), e.g. after a DB/reseed fix:

```bash
python3 -c "from src.db.plants import init_db; init_db(); print('ok')"
python3 -m unittest tests.test_polycultures -v
```

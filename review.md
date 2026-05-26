# review.md — Reference for deep-dive code reviews

This file is for Claude to read at the start of a deep-dive review pass.
The goal is to ground feedback in this project's actual priorities and
historical decisions, not generic best-practice advice. Three sections:

  1. **Convention checklist** — invariants every change should respect
  2. **Open items + decision log** — known data debt, deferred work,
     and decisions worth remembering across sessions
  3. **Per-area review prompts** — focused checklists for reviewing
     specific subsystems (data, UI, network, geospatial, etc.)

CLAUDE.md is the long-running project intro; this is the review rubric.
Both should be loaded for any deep-dive task.

---

## 1. Convention checklist

Each item is a hard rule unless explicitly negotiated. Cite a violation
with the source-of-truth pointer in parentheses; that's how Claude can
flag drift without having to re-derive the rule.

### Branching + versioning
- **Release branches are `V<major>.<minor>`** (V1.31, V1.32, …). The
  next branch increments the minor by 1. Never push to `claude/*-Ntd5l`
  codename branches — even if the harness suggests one as default.
  (See `CLAUDE.md` → "Branch naming convention".)
- **`Help → Check for Updates` auto-detects the highest `V*.*` on
  origin** and offers a switch. Breaking the convention silently
  breaks that feature. (`src/version_branch.py`.)
- **Schema version bumps come with seed-data or schema.sql changes**,
  always. The schema version is at `src/db/plants.py:_SCHEMA_VERSION`;
  bumping it triggers a one-time reseed on the user's next launch.
  Without it, existing installs don't pick up new tables or new rows.
- **New dependent tables get added to the reseed wipe list** in
  `src/db/plants.py:init_db` → "needs_reseed" block. Forgetting this
  lets stale rows accumulate across reseeds.

### Vocabulary + content
- **No Indigenous-knowledge claims in seeded text without explicit
  consent** from source communities. This applies to plant notes,
  polyculture names + descriptions, calendar entries, and any other
  shipped data. V1.37 removed 133 such references; the rule prevents
  reintroduction. Specific patterns to flag:
    * Named-community attributions ("used by First Nations / Blackfoot /
      Cree / Stoney Nakoda / Métis").
    * Sacred / ceremonial / smudging / spiritual framings.
    * Appropriative folk names ("Indian ice cream", "Indian Chocolate").
    * "Plant X is sacred to Y" / "X has ceremonial significance for Y".
  Acceptable: "historically used as a spring green", "traditional
  respiratory remedy" — generic ethnobotany verbs without named-
  community attribution.
- **No "permaculture-flavored" vocabulary in use tags or seeded
  descriptions.** Reframe toward "native habitat" + "functional
  landscape design". Specifically banned tag keys:
  `biomass`, `pest_deterrent`, `food_forest`, `edible_landscape`.
  (`src/db/plants.py:_USE_DEFINITIONS` is the source of truth.)
- **No "pioneer / colonizer" framing**. Use `early_successional` /
  "Early Successional", never `pioneer_species` / "Pioneer Species".
  This was reverted in V1.37 round 3 — flag if it creeps back.
- **Labels use full names, not acronyms**, when the audience may not
  know the term. Example: "Growing-degree days", not "GDD₅" (in the
  label — the acronym is fine in the value text like "1881 (3-yr avg)").

### Data invariants
- **`scripts/check_plant_data.py` must exit with zero errors.** Warnings
  are allowed — they're the known data-debt backlog. Adding new
  warnings is fine; failing a previously-passing field isn't.
  (`src/data_quality.py` is the validator module; the script is a
  thin CLI shim.)
- **Canonical enums** for plant data are listed in `src/data_quality.py`
  (`SUN_REQUIREMENTS`, `WATER_NEEDS`, `PLANT_TYPES`, `LIFE_CYCLES`,
  `DECIDUOUSNESS`, `GROWTH_RATES`). Adding a value means updating that
  module first, not just the data.
- **Canonical use tags** are in `src/db/plants.py:_USE_DEFINITIONS`.
  Mirroring `_USE_LABELS` in `src/plant_panel.py` must stay in sync.
- **Canonical ecoregion keys** are in `src/plant_panel.py:_AB_ECOREGION_CHOICES`;
  the validator reads them via AST parse (no PyQt6 dep at script time).
  Polygons live in `data/ecoregions_canada.geojson`. Adding a polygon
  whose `key` isn't in the canonical list will silently fail the
  filter pre-populate.

### Code patterns
- **Tests are stdlib `unittest`**, run via
  `python -m unittest discover -s tests`. Some legacy tests use their
  own custom runner (`test_terrain.py`, `test_climate.py`,
  `test_property_data.py`); those are pytest-style functions and
  `unittest discover` skips them.
- **Tests redirect the DB to `tempfile.mkdtemp`** before importing
  anything that opens a connection. See `test_uses_junction.py` for
  the canonical pattern. Never touch `~/.local/share/PermaDesign/`.
- **Network fetches use `property_data._http_get_json`** (or the
  equivalent pattern). User-Agent set, timeout default 20s, returns
  None on any failure. Don't introduce raw `urllib.request.urlopen`
  without graceful-degradation handling.
- **Site-panel fetches run in parallel** via
  `ThreadPoolExecutor` for the fast batch, then climate runs as a
  tail step so the "Site data ready" status flips ASAP. Don't
  re-serialize this.
- **Pure Python preferred over heavy deps**. `shapely` / `pyproj` /
  `fiona` are dev-time-only (used in `scripts/prepare_ecoregions.py`).
  Don't add them to `requirements.txt` unless a runtime feature
  genuinely needs polygon overlay / union / projection — point-in-
  polygon ray casting is enough for the current use case.
- **`map_widget` only stores (lat, lon).** Distance/area math uses an
  ad-hoc cosLat projection (~1% error at <2 km). Document any new
  geometry helper that introduces a different convention.
- **PyQt6 model/view delegates**: `sizeHint` MUST match the actual
  painted height. The plant detail row layout uses
  `N * lineSpacing()`; the calendar block adds `_CAL_BLOCK_H` only
  when calendar data is present. Sentence-wrapped rows count as 2
  lineSpacing units (V1.37 lesson — the wrap-on-overflow was a real
  user complaint).

---

## 2. Open items + decision log

Things that happened, things that didn't, and why.

### Known data debt
- **8 validator warnings** as of V1.37:
    * Goodland Apple / Norland Apple / Evans Cherry: `growth_curve='moderate'`
      (canonical set is `{slow_start, steady, fast_early}`; "moderate" is
      a likely typo confusing growth_rate with growth_curve)
    * Nanking Cherry / Bee Balm: `growth_curve='fast_start'`
      (typo for `fast_early`)
    * Cream-Coloured Peavine: `fruit_period='August?'`
      (uncertainty marker — intentional, not a typo)
    * Geum triflorum: 2 records share the scientific name
      (Old Man's Whiskers + Prairie Smoke — known duplicate, flagged
      in the record's own notes)
    * Valeriana sitchensis: 2 records share the scientific name
      (Sitka Valerian + Valerian — `FLAG:` marker in the record's
      own notes says the second one is misnamed; should be
      V. officinalis or similar)
- **Manual contour-drawing UI removed in V1.37**. Signal definitions
  (`contour_requested`, `contour_cleared`) + stub methods
  (`_pick_contour_color`, `_on_draw_contour`) preserved so re-enabling
  is one block of UI code.
- **5 → 3 year GDD fetch window**. Reduced for snappiness; continental
  climates are stable enough across 3-year windows. If the user wants
  multi-decadal climate averages later, parameter exists.
- **`permaculture_uses` SQL column name** is unchanged despite the
  vocabulary refocus. Renaming the column would require migration; for
  now, treat the name as historical and ignore. The user-facing label
  in the UI is "Uses".
- **"Red Indian Paintbrush" common_name** (Castilleja species) was
  NOT renamed in the V1.37 Indigenous-knowledge cleanup. It's the
  established horticultural common name; renaming would affect
  lookups and polyculture references. Flagged for an explicit
  user decision.

### Deferred work
- **Pyproj / UTM projection** for accurate distance / area math.
  Current cosLat approximation is ~1% off at the parcel scale, fine for
  the current map use cases. Step up when a feature needs the
  precision.
- **Shapely / fiona** for the ecoregion lookup. The starter
  `data/ecoregions_canada.geojson` is hand-drawn rectangles, and the
  prep script `scripts/prepare_ecoregions.py` describes the path to
  fidelity polygons from the CEC Level III dataset. Run it when
  someone genuinely wants accurate boundaries.
- **Plant-specific GDD bases**. Right now we report a single GDD₅;
  per-plant warnings ("apricot needs ~2000, you have 1300") need a
  `gdd_base_c` + `gdd_required` column on the plants table.
- **`medicinal` use tag** — kept in V1.37 since it isn't strictly
  permaculture (it's a human-use category). If the user later wants
  to drop it, removing 110 records would be a straightforward
  follow-up.
- **140 plant notes ethnobotanical references** were cleaned to
  130 in V1.37 round 3. About 7 records retained generic
  "historically used as food" phrasing where the named attribution
  was the only Indigenous-knowledge reference. If the user wants
  even those generic phrasings gone, a follow-up pass would just
  strip the verb clauses entirely.

### Decisions worth remembering across sessions
- **"Pioneer Species" → "Early Successional"**: the user explicitly
  rejected pioneer/colonizer framing. Reapplied to `_USE_DEFINITIONS`,
  `_USE_LABELS`, data file. Don't reintroduce.
- **"First Nations Medicine Wheel"**: renamed to "Native Prairie
  Aromatics" with horticultural-only framing. Don't reintroduce the
  ceremonial / spiritual framing.
- **Vocabulary refresh**: drop tags that explicitly invoke permaculture
  (`biomass`, `pest_deterrent`, `food_forest`, `edible_landscape`).
  Keep tags that describe ecological function (`nitrogen_fixer`,
  `soil_builder`, `early_successional`) or landscape design
  (`canopy_layer`, `windbreak`, etc).
- **Validator philosophy**: ERROR for things that silently mis-parse;
  WARNING for known drift the app already handles. Don't promote
  warnings to errors without also cleaning the underlying data in
  the same commit. (`src/data_quality.py` has the rationale.)
- **Edmonton offline pack: ~1 GB** unpacked. The earlier 50-300 MB
  estimate was wrong — corrected in V1.37.
- **Site-panel parallel fetches**: the V1.37 refactor took perceived
  pin-drop latency from sum-of-fetches (~5 s) to max-of-fetches
  (~1-2 s). Don't undo this by re-serializing.
- **Help menu version label**: includes the current `V<major>.<minor>`
  in the action title itself so the user can read it without opening
  the dialog. (V1.37.)

---

## 3. Per-area review prompts

When the user says "review the data layer" or "review the UI", load
the matching prompt instead of doing a generic pass.

### Plant data (`data/plants_master.json`, `data/garden_plants.json`)
1. Run `python scripts/check_plant_data.py` — must exit 0.
2. Any new `permaculture_uses` tags not in `_USE_DEFINITIONS`? Either
   promote to canonical or remove.
3. Any new Indigenous-knowledge references? Specific community names,
   sacred/ceremonial framings, appropriative folk names — flag every
   one, citing § Vocabulary + content.
4. Calendar status enums match the schema CHECK constraint
   (`dormant`, `start_indoors`, `direct_sow`, `transplant`, `growing`,
   `harvest`, `pruning`)?
5. Numeric fields: any soil_ph inversion, hardiness zone inversion,
   negative spacing/height?
6. New scientific names — do they look like binomials? Do they
   duplicate an existing record?

### Database layer (`src/db/`)
1. Was `_SCHEMA_VERSION` bumped if `schema.sql` or seeded data
   changed?
2. Any new dependent table — is it in the reseed wipe list in
   `init_db`?
3. New queries: parameterized, no SQL injection?
4. Foreign-key constraints honored? (`PRAGMA foreign_keys=ON` is on
   at runtime per `plants.py:get_connection`.)
5. New seed data — is it shipped from a JSON file rather than
   hard-coded in Python? `_seed_*` helpers are the pattern.

### UI (`src/site_panel.py`, `src/plant_panel.py`, `src/polyculture_panel.py`, etc.)
1. Acronyms in user-facing labels — spell them out (per V1.37 GDD
   feedback).
2. Long lists in the plant detail rows — do they wrap (`max_lines=2`)
   or clip? (Companions / Uses / Wildlife are the V1.37 wrap rows.)
3. `sizeHint` matches the painted layout? Adding a row means bumping
   the lineSpacing count.
4. Calendar legend dots — do they wrap to a second line on narrow
   panels, or `break` and disappear? (V1.37 fixed the break-on-overflow.)
5. Tooltips on technical fields? Compass direction, GDD, frost
   window — anything jargon-y needs a tooltip with concrete intuition.
6. Worker threads (`_SiteFetchWorker`, `TerrainWorker`): tear-down
   chain through `finished` → `quit` → `deleteLater`. Don't introduce
   blocking calls between signal emission and teardown.

### Network calls
1. Use `_http_get_json` (or equivalent) — User-Agent + timeout + None-
   on-failure.
2. Open-Meteo endpoints: `archive-api.open-meteo.com` for historical;
   `api.open-meteo.com` for live elevation / forecast.
3. Graceful fallback: if the API fails, do we have a local fallback
   (`data/rainfall_fallback_alberta.json`, Edmonton LiDAR pack, etc)?
   Source label reflects which path served the data?
4. Parallelizable I/O — using `ThreadPoolExecutor` for independent
   fetches, not serializing them?
5. Rate limits / weight — Open-Meteo has a free-tier daily quota
   (~10k calls). Don't introduce new calls per-pin-move; reuse the
   site-panel worker.

### Geospatial code (`src/terrain.py`, `src/ecoregion.py`, `src/climate.py`)
1. Pure Python OK for the operation? (Ray-casting for point-in-polygon
   is enough; don't add shapely speculatively.)
2. cosLat projection for short distances; document the ~1% error if
   you add a new helper that uses it.
3. Coordinate convention: GeoJSON is `[lng, lat]` but the in-app
   bbox dicts are `{south, north, west, east}`. Don't mix.
4. Grid convention: `grid[0]` is the NORTH row, `grid[-1]` is the
   SOUTH row (matches the existing slope code's `rN = r-1`,
   `rS = r+1`).
5. DEM gaps over water — `_parse_elevation` degrades gracefully. New
   spatial helpers should too.

### Update / version-switching flow (`src/app.py:_run_update_flow`)
1. Detect highest `V*.*` on origin and offer switch (V1.32 logic).
2. Dirty-tree handling: stash / discard / cancel before switching.
3. Stash auto-restore on the new branch; warning if pop conflicts.
4. Frozen installs (`getattr(sys, "frozen", False)`) redirect to
   releases page; don't try git operations.
5. Help menu has `About / Version`, `Check for Updates`, and `Switch
   to a specific version` — three actions, not collapsed into one.

### Tests
1. New test module — does it use the temp-DB pattern? (Required.
   See `test_uses_junction.py`.)
2. Pure-logic helpers go in their own module so tests can import
   without PyQt6 (e.g. `src/version_branch.py`).
3. Custom runners (`test_terrain.py`, `test_climate.py`,
   `test_property_data.py`) use pytest-style functions and are NOT
   picked up by `unittest discover`. Don't assume the discover count
   covers them.
4. New canonical constants (use keys, enum values) — does a test
   assert they don't drift?

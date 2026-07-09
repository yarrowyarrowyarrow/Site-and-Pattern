---
name: placed-plants
description: Use when touching placed-plant state — placing, removing, moving, or dragging plants; polyculture/community placement; undo/redo; area fill; generated designs; or anything that reads/writes the project's plant features. Covers the single-write-path rule (src/project_store.py), the two synced structures, the only allowed mutators, the plant-feature dict shape, how undo/redo snapshots interact, and the source-tree grep guard that fails the build on any hand-rolled mutation.
---

# Placed-plant state — the single write path

## The rule (do not violate it)

Placed plants live in **two structures that must stay in sync**:

1. `project["features"]` — the canonical GeoJSON `FeatureCollection`. One
   `Point` feature per plant. This is what save/load, the habitat score,
   exclusion zones, and the generator read.
2. `_placed_plants` — a denormalized plants-only index (a plain `list` of
   dicts). The planning/analysis panels and plant-count badges scan this
   because filtering the mixed-type feature list on every UI refresh is
   expensive.

A missed update to *either* silently desyncs the map, the saved file, and
the analytics. So **all mutations go through `src/project_store.py`**
(`ProjectStore`, introduced V1.62). Never `.append(...)` to
`_placed_plants` or to `features` by hand in a placement/removal path.
`tests/test_project_store.py` greps the whole `src/` tree and fails the
build the moment a new direct-mutation call site appears.

If you find yourself writing `self._placed_plants.append(...)` or
`features.append(<a plant feature>)`, stop — route it through the store.

## The only supported mutators

All on `ProjectStore` in `src/project_store.py`:

| Method | Use for |
|---|---|
| `add_plant(plant_id, common_name, lat, lng, *, placement_group_id="", polyculture_name="", polyculture_center_lat=None, polyculture_center_lng=None, pattern_kind="", quantity=1)` | Placing one plant. Returns the index record. |
| `remove_plant(plant_id, lat, lng, *, newest_first=False, feature_id="")` | Remove ONE match. Pass `feature_id` (V2.22) for an exact match that disambiguates duplicate-position plants; else id+coords, `newest_first=True` = undo semantics (remove most-recent), default = oldest (right-click-delete semantics). Returns the removed record or `None`. |
| `remove_plants_batch(keys)` | Remove many in one pass. `keys` = iterable of `(plant_id, lat, lng)`; duplicate keys remove duplicate-position plants once each (multiset). |
| `remove_polyculture(polyculture_name, center_lat, center_lng)` | Remove every member of one placed community instance (matched by the polyculture-center anchor). Returns count removed. |
| `move_plant(plant_id, old_lat, old_lng, new_lat, new_lng, *, group_id=None, feature_id="")` | Move one plant (drag). `feature_id` (V2.22) makes the match exact; else `group_id` constrains the feature match so identically-positioned plants in other groups stay put. Returns `True` if moved. |

Whole-state replacement (New / Open / undo restore):

| Method | Use for |
|---|---|
| `set_project(project)` | File → New / Open: adopt a new project dict and rebuild the index. |
| `rebuild_index()` | After undo/redo swaps the whole `features` list at once — brings `_placed_plants` back into agreement. |
| `replace_placed_plants(records)` | Load paths that build richer index records (minting group ids) than a bare feature rebuild gives. |

## The converter pair (never hand-roll a plant feature)

`plant_feature(record, *, pattern_kind="", quantity=1)` and its inverse
`plant_record_from_feature(feature)` are the **one** record↔feature
converter pair — so the two shapes can't drift. Use them; do not build a
plant `Feature` dict inline.

The canonical plant feature shape (what `plant_feature` writes):

```json
{
  "type": "Feature",
  "geometry": { "type": "Point", "coordinates": [lng, lat] },
  "properties": {
    "element_type": "plant",
    "plant_id": 42,
    "common_name": "Wild Bergamot",
    "quantity": 1
  }
}
```

Critical details, mined from `plant_feature` / `plant_record_from_feature`:

- **GeoJSON coordinate order is `[lng, lat]`** — longitude first. The index
  record uses named `lat` / `lng` keys, so the converters are where the
  order flips. Get this wrong and plants teleport. (See the `geo-projection`
  skill for the broader ordering trap.)
- `element_type == "plant"` is the discriminator that separates plant
  features from boundary/structure/overlay features. `plant_record_from_feature`
  returns `None` for anything that isn't a `Point` with `element_type == "plant"`.
- Optional fields (`polyculture_name`, `polyculture_center_lat`,
  `polyculture_center_lng`, `placement_group_id`) are **omitted when
  empty**, not written as `""`/`None`. This keeps saved files byte-stable
  against the old hand-written call sites. Don't "helpfully" add empty keys.
- `pattern_kind` and `quantity` are feature-only metadata (how it was
  placed; how many a generated placement represents) — they live in the
  feature, not the index record.

## Matching tolerance

Position matches use `COORD_TOL_DEG = 1e-7` degrees (≈ 1 cm) via the
`_close()` / `_same_spot()` helpers — tight enough to distinguish
neighbours, loose enough to absorb float noise from the JS round-trip
(Leaflet hands coordinates back through JSON). Every matcher, including
batch removal, uses the same tolerance (the old rounded `_key` was deleted
in V2.22 — it disagreed with `_close` at rounding boundaries). If you add
a matcher, reuse `_same_spot`; don't invent a new tolerance.

Since V2.22 every plant feature is minted a stable `feature_id`
(`pf_<hex>`, written into both the feature and the index record by
`plant_feature`). **Prefer matching by `feature_id`** — coordinates remain
only as the legacy-file fallback.

## `store_for(main)` — getting the store

`store_for(main)` returns (and caches on `main._store`) the `ProjectStore`
for a `MainWindow`. It also works for the lightweight fake mains the
controller tests build: it wraps the fake's own `_project` /
`_placed_plants` references, mutating them in place so the fake's
attributes observe every change. Use `store_for(self)` in controller code
rather than constructing a `ProjectStore` yourself.

## How undo/redo interacts

Undo/redo (`src/controllers/undo_support.py`, `src/controllers/persistence.py`)
snapshots and restores the **whole** `features` list at once — it bypasses
the per-plant mutators by design. After such a swap, the index is stale, so
the restore path calls `store.rebuild_index()` to bring `_placed_plants`
back into agreement. The `@undoable` decorator in
`src/controllers/undo_support.py` wraps map-event handlers in
`src/controllers/map_events.py` so each feature edit pushes an undo
snapshot. When you add a new placement gesture, wire it through the store
*and* make sure it's captured by the undo machinery (follow an existing
`@undoable` handler in `map_events.py` as the pattern).

## Checking your work

`store.check_consistency()` rebuilds the index from the features and
returns a list of human-readable mismatches — **empty means the two agree**.
`tests/test_project_store.py` asserts it stays empty through a scripted
editing session (place → pattern → community → drag → undo → redo → remove),
plus a tamper test proving the checker actually detects drift.

## Procedure for a new placement/removal path

1. Get the store: `store = store_for(self)` (or the store you already hold).
2. Call the matching mutator (`add_plant` / `remove_plant` / … above).
   Never touch `_placed_plants` or `features` directly.
3. Do the Qt/map side effects (draw the marker, refresh the panel) at the
   call site — the store is deliberately Qt-free and only guarantees the
   two data structures agree.
4. If the gesture should be undoable, ensure it's inside an `@undoable`
   handler (see `map_events.py`).
5. Add/extend a scripted step in `tests/test_project_store.py` and assert
   `check_consistency()` stays empty.

## Pitfalls

- **The grep guard is source-wide.** Even a `_placed_plants.append` in a
  helper module trips `tests/test_project_store.py`. Route everything
  through the store.
- **`remove_plant` default removes the OLDEST match.** For undo you almost
  always want `newest_first=True`. Picking the wrong one removes the wrong
  duplicate and desyncs nothing structurally but corrupts the design.
- **Don't build plant features inline** for the map or for save — use
  `plant_feature`. The optional-field-omission behaviour matters for
  file stability.
- **`move_plant` without `group_id`** will move the first id+coords match
  it finds; pass `group_id` for group/community drags so co-located plants
  in other groups don't get dragged along.
- The store is Qt-free on purpose — don't import PyQt into it, and don't
  put map redraws inside it.

## Key files

| Path | What |
|---|---|
| `src/project_store.py` | The store: `ProjectStore`, `plant_feature`, `plant_record_from_feature`, `store_for`, `COORD_TOL_DEG`. |
| `tests/test_project_store.py` | Unit tests per mutator + scripted-session consistency + the source-tree grep guard. |
| `src/controllers/map_events.py` | Map-event handlers; `@undoable` placement/removal/drag gestures that call the store. |
| `src/controllers/undo_support.py` | The `@undoable` decorator + snapshot machinery. |
| `src/controllers/persistence.py` | Save/load/undo-restore; calls `rebuild_index()` after whole-list swaps. |
| `src/project.py` | `load_project` / `save_project` / `project_to_map_data` — the project dict shape the store wraps. |

## Validation

```bash
python3 -m unittest tests.test_project_store -v
```

Run the whole guard set when you touch this area:

```bash
python3 -m unittest tests.test_project_store tests.test_undo_redo tests.test_map_events_drag -v
```

---
name: geo-projection
description: Use when writing any coordinate, distance, area, bearing, or polygon math — lat/lng↔metres conversions, shapely geometry, shade/wind-shadow footprints, GeoJSON handling. Covers THE RULE (store only lat/lon; metric math goes through src/projection.py), the cosLat default vs optional UTM backend, the use_utm_projection flag's real status, shadow_geometry as the shared shapely engine, and the lat/lng-vs-lng/lat ordering traps.
---

# Coordinates, distance/area math, and geometry

## THE RULE

**The map and the project file store only `(lat, lon)` in WGS-84. Every
distance, area, offset, or bearing computation converts to local metres
through `src/projection.py` — never with inline `111320`-style arithmetic in
new code.** The constant exists once as `projection.M_PER_DEG_LAT`; modules
that need it (`src/shade.py`, `src/property_data.py`) import it from there.

Why: an inline formula silently disagrees with the UTM upgrade path, can't be
switched per-project, and is where degree-vs-metre bugs breed.

## The two backends

`src/projection.py` centralises the math behind `class Projector`:

- **`"coslat"` (DEFAULT)** — the legacy equirectangular approximation:
  1° lat ≈ 111,320 m; 1° lng ≈ 111,320·cos(lat) m. Accurate to ~1% for spans
  under ~2 km at Alberta latitudes — fine for a property, loose beyond. It
  reproduces the pre-refactor numbers byte-for-byte
  (`tests/test_projection.py:TestCosLatBackendMatchesLegacy` pins this).
- **`"utm"` (optional)** — pyproj geodetic transform, zone auto-selected from
  the origin (`utm_epsg_for` → EPSG 326xx/327xx; Alberta = 32611/32612).
  If pyproj isn't installed the request **silently falls back to coslat**
  (`set_default_backend("utm")` returns the backend actually in effect —
  check the return value, don't assume).

### The `use_utm_projection` flag — real status (code wins over CLAUDE.md)

`projection.project_uses_utm(project)` reads
`project["properties"]["use_utm_projection"]` (documented in
`docs/PROJECT_FILE_FORMAT.md`), but as of V2.19 **nothing in `src/` calls it**
— no call site wires the flag to `set_default_backend` or passes
`backend="utm"`. The flag is a prepared hook, not live plumbing. Judgment:

- Don't build a second flag or your own backend-switching mechanism; if a task
  needs per-project UTM, wire `project_uses_utm` → `set_default_backend` at
  project-load time (one place), and say so in the change description.
- For new metric code, just use `Projector(...)` with the default backend; it
  inherits UTM automatically if/when the flag gets wired.
- `pyproj` is an **optional** dependency (`requirements-optional.txt`) — never
  import it unconditionally; go through `projection.pyproj_available()`.

## The conversion toolkit (actual names)

| Need | Use |
|------|-----|
| lat/lng → metres east/north of an origin | `Projector(lat0, lng0).to_xy(lat, lng)` → `(x, y)` |
| metres → lat/lng | `Projector.to_latlng(x, y)` → `(lat, lng)` |
| origin at a point set's centroid | `Projector.for_positions([(lat, lng), …])` |
| distance between two lat/lng points | `Projector.distance_m(lat1, lng1, lat2, lng2)` |
| project a whole list | `Projector.project_many([(lat, lng), …])` |
| metres-per-degree at a latitude | `projection.metres_per_deg(lat)` → `(m_per_deg_lat, m_per_deg_lng)` |
| centroid-relative local frame for a cluster | `projection.to_local_xy(positions)` (the polyculture optimiser path) |
| UTM zone / EPSG for a location | `projection.utm_zone_for(lng)`, `projection.utm_epsg_for(lat, lng)` |

Notes with teeth:

- `Projector.to_xy` takes **`(lat, lng)`**. The shadow engine's
  `_MetricOrigin.to_xy` (below) takes **`(lng, lat)`** — the single most
  bite-prone inconsistency in this codebase. Check the signature every time.
- coslat `to_xy` maps the origin to `(0, 0)`; the UTM backend returns real UTM
  eastings/northings (large absolute numbers). Only **relative** distances are
  comparable across backends — never persist or compare raw `x, y` across
  frames with different origins.
- `cos(lat)` is clamped to `1e-9` near the poles in both `Projector` and
  `metres_per_deg` — copy the clamp if you ever must write a local formula.

## The shapely engine: `src/shadow_geometry.py`

This is the shared metric-polygon engine for **both** sun shade and wind
shadow. shapely is optional: every entry point checks `_HAVE_SHAPELY` and
returns `None`/`[]` so callers can fall back (`src/shade.py` reverts to its
circle model; headless CI keeps working). Match that pattern in new geometry
code — guard, degrade, never crash on a missing optional dep.

Core pieces:

- `_MetricOrigin(lat0, lng0)` — tiny cosLat frame; **`to_xy(lng, lat)`** /
  `to_lnglat(x, y)` (GeoJSON argument order, unlike `Projector`).
  `origin_for_bbox(bbox)` anchors one at a grid bbox's SW corner.
- `footprint_to_metric(coords_lnglat, origin)` — GeoJSON ring → metric shapely
  `Polygon`, with `buffer(0)` self-touching-ring repair.
- `cast_shadow(polygon, height_m, azimuth, altitude)` — exact Minkowski-sum
  sweep of the footprint down-sun by `height/tan(altitude)`; convex footprints
  take the cheap hull path, concave ones keep their notches (`_swept_region`).
  Sun below `_MIN_SUN_ALT` (5°) → `None`; length clamped to `_MAX_SHADOW_M`
  (60 m). Azimuth convention: **degrees clockwise from north**; down-sun
  decomposes as east = sin, north = cos.
- `cast_tree_shadow(center_xy, radius_m, height_m, az, alt)` — trunk streak +
  tapering canopy teardrop (a tree is not a column).
- `union_shadows`, `union_geometries` — merge casters / sun moments.
- `latlng_rings(geom, origin)` — metric (Multi)Polygon → nested
  **`[lat, lng]`** rings (exterior + holes) exactly as `L.polygon` accepts.
  This is the standard way geometry returns to the Leaflet layer.
- `rasterize_to_grid(shadow_geom, elev, origin)` — onto the elevation grid
  (`[[fraction]]`, **row 0 = north**) using `shapely.prepared.prep` for fast
  repeated point-in-polygon. Keep `prep()` when rasterizing — the naive loop
  is an order of magnitude slower.

`src/wind_shadow.py` (V1.68) reuses `_MetricOrigin` + `latlng_rings` +
shapely `unary_union` for porosity-banded shelter trapezoids
(`merged_shelter`, `casters_from_project`). Its band math is intentionally
mirrored in JS (`html/map/06-overlays.js` `_windWedges`) for the live ghost —
if you change reach/band constants in one, change the other.

## Pure-Python polygon tests: `src/geometry.py`

Ray-casting point-in-polygon, no deps, no projection (containment is
projection-invariant):

- `point_in_ring(lat, lng, ring)` / `point_in_polygon(lat, lng, polygon)` /
  `ring_bbox(ring)`.
- Rings follow the **GeoJSON convention: `[lng, lat]` pairs**; the public
  functions take `(lat, lng)` scalars and swap internally. Used by ecoregion
  lookup and the design generator's boundary clipping (`src/llm_design.py`).

## Ordering cheat sheet — memorise this table

| Surface | Order |
|---------|-------|
| GeoJSON geometry on disk (project file) | `[lng, lat]` (spec order — see `docs/PROJECT_FILE_FORMAT.md`) |
| Internal map model / scripting API / bridge signals | `(lat, lng)` — `src/project.py:project_to_map_data` does the swap |
| Leaflet `L.latLng`, `L.polygon`, marker positions | `[lat, lng]` |
| `Projector.to_xy(...)` | args `(lat, lng)` |
| `_MetricOrigin.to_xy(...)` (shadow_geometry) | args `(lng, lat)` |
| `shadow_geometry.latlng_rings` output | `[lat, lng]` rings (Leaflet-ready) |
| `geometry.point_in_ring` ring arg | `[lng, lat]` (GeoJSON), scalars `(lat, lng)` |
| pyproj `Transformer` (built with `always_xy=True`) | `(lng, lat)` in, `(easting, northing)` out |

When a feature "lands in the ocean off Ghana" (≈ `[0, 0]`) or appears mirrored
across the diagonal, it's this table. Check the boundary handler
(`src/controllers/map_events.py:_on_boundary_complete`) for the canonical
swap-when-writing-GeoJSON example: `[[pt[1], pt[0]] for pt in coords]`.

## Pitfalls & gotchas (real ones)

- **Area on raw degrees is wrong twice**: a degree of longitude at Edmonton is
  ~0.59× a degree of latitude, and both are ~111 km. Project to metres first
  (`Projector`/`to_local_xy`), then shoelace — see the reference
  implementation in `tests/test_map_features.py:shoelace_area_m2`.
- **Degree/metre unit mixing**: grid cell sizes cross the bridge in degrees
  (`d_lat`/`d_lng` in `map_js.draw_shade_zones`) but geometry math wants
  metres. Name variables with units (`half_m`, `d_lat_deg`) and convert at the
  edge, once.
- **Don't compare absolute projected coords across origins.** Two cosLat
  frames differ by a constant offset — `src/scene_contract.py` re-frames scan
  points between origins via `metres_per_deg`; copy that, don't re-project.
- shapely `Polygon` validity: user-drawn rings self-touch. Always follow the
  engine's pattern — `if not poly.is_valid: poly = poly.buffer(0)` — before
  union/rasterize, or `unary_union` throws deep in a paint path.
- The `1e-7` lat/lng tolerance in JS marker matching (`src/map_js.py`
  `undo_place_plant`) ≈ 1 cm; rounding coordinates below 7 decimals anywhere
  in the pipeline breaks undo matching.
- `metres_per_deg(lat, backend="utm")` measures local scale by projecting a
  0.001° step — it's a *measurement*, not a constant; don't cache it across
  latitudes.
- Tests that must run without pyproj/shapely: gate with
  `@unittest.skipUnless(pyproj_available(), ...)` /
  `@unittest.skipUnless(sg._HAVE_SHAPELY, ...)` exactly as
  `tests/test_projection.py` and `tests/test_shadow_geometry.py` do, and never
  leak a changed default backend (`TestDefaultBackend.tearDown` restores it).

## Validation

```bash
python -m unittest tests.test_projection tests.test_shadow_geometry tests.test_wind_shadow -v
python tests/test_map_features.py          # JS-mirror haversine/shoelace/sector math (script-style)
python -m unittest tests.test_shade        # circle-model fallback when touching shadow_geometry
python -m unittest discover -s tests       # full suite before finishing
```

All pass headlessly; shapely/pyproj-gated cases self-skip when those optional
deps are absent (they were absent in the environment this skill was verified
in — the suites still pass with skips). If your change is UTM-specific,
install pyproj so the `TestUtmAgreesWithCosLat` cases actually execute.

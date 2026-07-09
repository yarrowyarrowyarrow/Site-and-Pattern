# Site & Pattern Project File Format

A Site & Pattern project is a single JSON file, conventionally named
`*.perma.geojson`. It is a [GeoJSON](https://geojson.org/)
`FeatureCollection` with Site & Pattern-specific properties on the
collection and on each feature.

Files written by the GUI, the scripting API
([`src/permadesign_api.py`](../src/permadesign_api.py)), and the CLI are
all the same format and open interchangeably.

The authoritative reader/writer is [`src/project.py`](../src/project.py)
(`new_project`, `save_project`, `load_project`, `project_to_map_data`).

---

## Top-level structure

```jsonc
{
  "type": "FeatureCollection",
  "properties": {
    "schema_version": "1.6",          // project-file format version (see below)
    "project_name": "My Yard",
    "created": "2026-05-28T12:00:00",  // naive UTC ISO-8601
    "hardiness_zone": 3,               // or null
    "notes": "",
    "site_config": {
      "latitude": 53.5461,             // or null
      "longitude": -113.4938,          // or null
      "area_m2": null,
      "hardiness_zone": null,
      "soil_type": null,
      "sun_exposure": null,
      "wind_exposure": null,
      "priorities": []
    }
    // "use_utm_projection" (V1.41–V2.21) is obsolete: the UTM backend was
    // never reachable and was deleted in V2.22. Old files carrying the key
    // are fine — readers ignore unknown properties.
  },
  "features": [ /* see element types below */ ]
}
```

`schema_version` here is the **project-file** version (`"1.6"`,
`src.project.SCHEMA_VERSION`). It is unrelated to the **database**
schema version (`17`) documented in
[`DATABASE_SCHEMA.md`](DATABASE_SCHEMA.md).

`site_config` additionally accumulates fetched data at runtime:
`rainfall`, `soil`, `elevation`, `hardiness`, `pin_label`,
`data_fetched_at`.

---

## Coordinate convention

**GeoJSON geometry stores `[longitude, latitude]`** (X, Y order) — the
spec's order, and the order on disk. Site & Pattern's internal map model and
the scripting API use `[latitude, longitude]`; `project_to_map_data`
does the swap. When hand-writing geometry, use `[lng, lat]`.

---

## Feature types

Every feature is a GeoJSON `Feature` whose `properties.element_type`
selects the kind. Below: the geometry type and the properties each kind
carries.

### `property_boundary` — Polygon
```jsonc
{
  "type": "Feature",
  "geometry": { "type": "Polygon", "coordinates": [[[lng, lat], ...]] },
  "properties": {
    "element_type": "property_boundary",
    "boundary_id": "b_api_1a2b3c4d",
    "color": "green",
    "show_lengths": true,
    "show_area": true
  }
}
```
Multiple boundaries are allowed; each needs a unique `boundary_id`.

### `plant` — Point
```jsonc
{
  "geometry": { "type": "Point", "coordinates": [lng, lat] },
  "properties": {
    "element_type": "plant",
    "plant_id": 42,                       // FK into the plant database
    "common_name": "Yarrow",
    "placement_group_id": "pg_abcdef0123",// shared by one placement gesture
    "quantity": 1,
    // present only for community members:
    "polyculture_name": "Apple Tree Community",
    "polyculture_center_lat": 53.546,
    "polyculture_center_lng": -113.496
  }
}
```
`placement_group_id` ties plants placed by one gesture (single, row,
grid, circle, community) together so they select/delete as a unit.
Legacy projects with no group id get a fresh singleton id assigned on
load.

### `structure` — Point
```jsonc
{
  "geometry": { "type": "Point", "coordinates": [lng, lat] },
  "properties": {
    "element_type": "structure",
    "struct_id": "bee_hotel",
    "name": "Bee Hotel",
    "size_m": 1.0,
    "struct_def": { "id": "bee_hotel", "name": "Bee Hotel", ... }
  }
}
```
`struct_def` is the full definition from
[`src/db/structures.py`](../src/db/structures.py); habitat scoring reads
`struct_def.id`.

### `hedgerow` — LineString
```jsonc
{
  "geometry": { "type": "LineString", "coordinates": [[lng, lat], ...] },
  "properties": {
    "element_type": "hedgerow",
    "hedge_id": "...", "species": "Saskatoon", "style": "hedge",
    "length_m": 12.4, "num_plants": 9,
    "color": "#4caf50", "width_m": 1.5, "spacing_m": 1.0
  }
}
```

### `custom_shape` — Polygon
```jsonc
{
  "geometry": { "type": "Polygon", "coordinates": [[[lng, lat], ...]] },
  "properties": {
    "element_type": "custom_shape",
    "shape_id": "...", "label": "Goldfish pond", "shape_type": "Pond",
    "fill_color": "#4caf50", "stroke_color": "#2e7d32",
    "fill_opacity": 0.25, "dash_array": "", "area_m2": 18.0
  }
}
```

### `canopy_footprint` — Polygon (shade caster)
A footprint with a `height_m > 0` that casts a true-shape shadow (a drawn
building/canopy perimeter, an imported nDSM footprint, or — V1.58 — a building
imported from OpenStreetMap, which keeps its real outline instead of collapsing
to a point + radius). `source` records the origin (`"osm"`, `"extract"`, or
absent for hand-drawn). OSM buildings also stamp the centroid (`lat`/`lng`) and
`canopy_radius_m` so the generator's keep-out (`src/exclusion.py`) still avoids
them. The outline is editable on the map (drag its vertices), which rewrites the
ring and re-derives `canopy_radius_m`.
```jsonc
{
  "geometry": { "type": "Polygon", "coordinates": [[[lng, lat], ...]] },
  "properties": {
    "element_type": "canopy_footprint",
    "shape_id": "shape_osm_0", "label": "Building (OSM)",
    "height_m": 6.0, "cast_shade": true, "canopy_radius_m": 7.1,
    "lat": 53.5, "lng": -113.5, "source": "osm",
    "fill_color": "#8d6e63", "stroke_color": "#5d4037", "fill_opacity": 0.3
  }
}
```

### `contour_line` — LineString
```jsonc
{
  "geometry": { "type": "LineString", "coordinates": [[lng, lat], ...] },
  "properties": { "element_type": "contour_line", "elevation_m": 670, "color": "#795548" }
}
```

### `auto_contour` — MultiLineString
Generated slope contours (the auto-terrain pipeline).
```jsonc
{
  "geometry": { "type": "MultiLineString", "coordinates": [[[lng, lat], ...], ...] },
  "properties": { "element_type": "auto_contour", "elevation_m": 675, "color": "#5d4037", "source": "lidar" }
}
```

### `slope_overlay` — Polygon (metadata marker)
The slope-ramp PNG is regenerated on demand; the project stores only its
bounds + stats so a re-open knows an overlay existed.
```jsonc
{
  "geometry": { "type": "Polygon", "coordinates": [[[lng, lat], ...]] },
  "properties": {
    "element_type": "slope_overlay",
    "bbox": { "north": 53.6, "south": 53.5, "east": -113.4, "west": -113.5 },
    "stats": { "mean_slope_pct": 4.2 },
    "interval_m": 0.5, "resolution_m": 1.0, "source": "lidar"
  }
}
```

### `annotation` — Point
```jsonc
{
  "geometry": { "type": "Point", "coordinates": [lng, lat] },
  "properties": { "element_type": "annotation", "annotation_id": "ann_...", "text": "north bed" }
}
```

---

## Evolution rules

- **Add, don't repurpose.** New element kinds get a new `element_type`;
  new per-feature data gets a new property key. Readers ignore unknown
  keys, so additions are backward-compatible.
- **Default missing values.** `project_to_map_data` supplies defaults for
  absent properties (e.g. boundary `color` → `"green"`), so older files
  keep loading. Preserve that when adding fields.
- **Bump `SCHEMA_VERSION`** in `src/project.py` only for a change that
  older code couldn't load safely, and add a migration path in
  `project_to_map_data`. Day-to-day additive fields don't need a bump.
- Round-trip fidelity is covered by
  [`tests/test_project.py`](../tests/test_project.py); add a case there
  for any new element type.

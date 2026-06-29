CREATE TABLE IF NOT EXISTS plants (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    common_name TEXT NOT NULL,
    scientific_name TEXT,
    plant_type TEXT NOT NULL,       -- tree, shrub, herb, groundcover, vine, root
    hardiness_zone_min INTEGER,
    hardiness_zone_max INTEGER,
    sun_requirement TEXT,           -- full_sun, partial_shade, full_shade
    water_needs TEXT,               -- low, medium, high
    native_region TEXT,
    -- permaculture_uses dropped in schema v37: the normalized plant_uses
    -- junction (below) is the single source of truth. Read-side consumers get
    -- a derived comma-joined `permaculture_uses` synthesized in get_plant /
    -- search_plants / get_all_plants.
    spacing_meters REAL,
    mature_height_meters REAL,
    mature_canopy_m REAL,           -- horizontal spread at maturity (NULL ⇒ heuristic in get_plant)
    notes TEXT,
    -- Extended fields (schema v2)
    bloom_period TEXT,              -- e.g. "May–June"
    fruit_period TEXT,              -- e.g. "August–September"
    native_to_alberta INTEGER DEFAULT 0,  -- 1 = native to Alberta
    edible_parts TEXT,              -- comma-separated e.g. "fruit,leaves,flowers"
    deciduous_evergreen TEXT,       -- deciduous | evergreen | herbaceous
    soil_ph_min REAL,
    soil_ph_max REAL,
    perennial_or_annual TEXT,       -- perennial | annual | biennial
    marker_color TEXT,              -- custom hex colour for map markers (e.g. '#ff5722')
    -- Growth data (schema v5) for succession/timeline planning
    growth_rate TEXT,               -- slow | moderate | fast
    years_to_maturity INTEGER,      -- estimated years to reach mature size
    growth_curve TEXT,              -- fast_early | steady | slow_start
    -- Schema v11
    ab_ecoregion TEXT,              -- comma-separated AB ecoregion tags
                                    -- (aspen_parkland, mixedgrass_prairie,
                                    --  fescue_foothills, boreal_mixedwood,
                                    --  riparian, wet_meadow, subalpine_montane)
    -- Safety + spread (schema v18, V1.44 chunk 2). Empty string = UNASSESSED,
    -- which is deliberately NOT the same as 'none' — the safety filters use a
    -- denylist (exclude only known-toxic), so unassessed plants are surfaced
    -- with an honest "no known toxicity, not a guarantee" caveat.
    toxicity_pets TEXT DEFAULT '',      -- '' (unassessed) | none | low | high
    toxicity_humans TEXT DEFAULT '',    -- '' (unassessed) | none | low | high
    has_thorns INTEGER DEFAULT 0,       -- 1 = thorns / spines / prickles
    spread_habit TEXT DEFAULT '',       -- '' | clumping | slow_spreader | aggressive_rhizomatous | self_seeding
    safety_source TEXT DEFAULT '',      -- provenance note for the safety classification
    -- Sourcing + cost (schema v19, V1.45). ESTIMATES ONLY — Alberta retail
    -- ranges per single nursery plant; region/year-dependent, surfaced with an
    -- "estimate" disclaimer. Empty / NULL = unpriced (a plant_type default is
    -- used at estimate time, see src/sourcing.py).
    price_low_cad REAL,                 -- est. low retail price, one nursery plant (CAD)
    price_high_cad REAL,                -- est. high retail price (CAD)
    availability_class TEXT DEFAULT '', -- '' | big_box | garden_centre | native_specialist | seed_or_plug | rare
    sourcing_notes TEXT DEFAULT '',     -- form sold / example AB nurseries / as-of year
    -- Flower colour + form (schema v31, V1.90) — drives real-coloured flowers in
    -- the 3D viewer, shown when in bloom. Empty / 'none' = no showy flower.
    flower_color TEXT DEFAULT '',       -- hex like '#f2c11e' or '' (no showy flower)
    flower_form TEXT DEFAULT 'none',    -- daisy | spike | umbel | cluster | bell | none
    fruit_color TEXT DEFAULT '',        -- berry hex (v35, V2.0); '' = dry/non-fruiting
    -- Imagery (schema v24, V1.60). An OPENLY-licensed photo + its citation;
    -- NULL/empty until the dataset workflow fills them. The app caches the URL
    -- locally and shows the attribution beside the photo (src/image_cache.py).
    image_url TEXT DEFAULT '',          -- http(s) URL or local path to an open-licensed photo
    image_attribution TEXT DEFAULT '',  -- e.g. "© Photographer, CC BY-SA 4.0 (via Wikimedia)"
    image_license TEXT DEFAULT ''       -- e.g. CC0 / CC BY / CC BY-SA / public domain
);

CREATE TABLE IF NOT EXISTS companion_friends (
    plant_id_a INTEGER NOT NULL REFERENCES plants(id) ON DELETE CASCADE,
    plant_id_b INTEGER NOT NULL REFERENCES plants(id) ON DELETE CASCADE,
    PRIMARY KEY (plant_id_a, plant_id_b)
);

CREATE TABLE IF NOT EXISTS companion_enemies (
    plant_id_a INTEGER NOT NULL REFERENCES plants(id) ON DELETE CASCADE,
    plant_id_b INTEGER NOT NULL REFERENCES plants(id) ON DELETE CASCADE,
    PRIMARY KEY (plant_id_a, plant_id_b)
);

CREATE TABLE IF NOT EXISTS planting_calendar (
    plant_id INTEGER NOT NULL REFERENCES plants(id) ON DELETE CASCADE,
    month    INTEGER NOT NULL CHECK (month BETWEEN 1 AND 12),
    status   TEXT NOT NULL CHECK (status IN (
        'dormant', 'start_indoors', 'direct_sow', 'transplant',
        'growing', 'harvest', 'pruning'
    )),
    notes    TEXT,
    PRIMARY KEY (plant_id, month)
);

CREATE TABLE IF NOT EXISTS polycultures (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT,
    center_plant_id INTEGER REFERENCES plants(id),
    parent_id INTEGER REFERENCES polycultures(id) ON DELETE SET NULL,
    -- Alexander pattern-language framing (schema v27, F4). Authored editorial
    -- text; `description` stays as the short summary / fallback. The data-derived
    -- parts of the pattern (site envelope, ecological forces, related patterns)
    -- are computed at display time in src/pattern_language.py, not stored.
    problem TEXT,                   -- the need / conflict the community resolves
    context TEXT,                   -- where & when to use it (the larger situation)
    forces TEXT,                    -- the competing considerations it balances
    solution TEXT,                  -- the instruction ("Therefore: …")
    created TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    modified TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS polyculture_members (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    polyculture_id INTEGER NOT NULL REFERENCES polycultures(id) ON DELETE CASCADE,
    plant_id INTEGER NOT NULL REFERENCES plants(id) ON DELETE CASCADE,
    role TEXT,                      -- legacy single-value role (kept for back-compat)
    layer TEXT,                     -- vegetation layer (overstory/understory/...)
    functions TEXT,                 -- JSON array of ecological functions (pollinator, etc.)
    offset_x REAL DEFAULT 0,
    offset_y REAL DEFAULT 0,
    notes TEXT
);

-- Polyculture Recipes — persistent ratio-only mixes (no spatial layout).
-- Unlike polycultures, recipes carry per-member weights instead of x/y offsets;
-- they drive ratio assignment for row/grid/circle placements and can be
-- "populated" into a polyculture's circle via the builder.
CREATE TABLE IF NOT EXISTS polyculture_recipes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    description TEXT,
    strategy TEXT DEFAULT 'even_split',
    spacing_strategy TEXT DEFAULT 'max',
    created TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    modified TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS polyculture_recipe_members (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    recipe_id INTEGER NOT NULL REFERENCES polyculture_recipes(id) ON DELETE CASCADE,
    plant_id INTEGER NOT NULL REFERENCES plants(id) ON DELETE CASCADE,
    weight INTEGER NOT NULL DEFAULT 1,
    marker_color TEXT,
    sort_order INTEGER DEFAULT 0
);

-- Permaculture-uses lookup + plant ↔ use junction (schema v13).
-- Replaces the comma-delimited plants.permaculture_uses blob for filter
-- queries; the legacy column is still populated during seed for one
-- release cycle as a safety net.
CREATE TABLE IF NOT EXISTS uses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    key TEXT NOT NULL UNIQUE,           -- e.g. 'keystone_species', 'host_plant'
    label TEXT NOT NULL,                -- display label, e.g. 'Keystone Species'
    category TEXT NOT NULL,             -- 'wildlife' | 'function' | 'utility'
    sort_order INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS plant_uses (
    plant_id INTEGER NOT NULL REFERENCES plants(id) ON DELETE CASCADE,
    use_id   INTEGER NOT NULL REFERENCES uses(id) ON DELETE CASCADE,
    PRIMARY KEY (plant_id, use_id)
);

-- Fauna registry + plant ↔ fauna relationship junction (schema v13).
-- Records which native lepidoptera, birds, and bees each plant supports,
-- and via which biological relationship (larval host, nectar, fruit, etc.).
CREATE TABLE IF NOT EXISTS fauna (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scientific_name TEXT NOT NULL UNIQUE,
    common_name TEXT NOT NULL,
    taxon TEXT NOT NULL CHECK (taxon IN
        ('lepidoptera', 'bird', 'bee', 'other_insect', 'mammal')),
    ab_native INTEGER NOT NULL DEFAULT 1,
    range_notes TEXT,
    icon TEXT,
    description TEXT,
    -- Imagery (schema v24, V1.60) — see the plants table note.
    image_url TEXT DEFAULT '',
    image_attribution TEXT DEFAULT '',
    image_license TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS plant_fauna (
    plant_id INTEGER NOT NULL REFERENCES plants(id) ON DELETE CASCADE,
    fauna_id INTEGER NOT NULL REFERENCES fauna(id) ON DELETE CASCADE,
    relationship TEXT NOT NULL CHECK (relationship IN (
        'larval_host', 'nectar', 'pollen', 'seed_food',
        'fruit_food', 'nesting', 'cover'
    )),
    specificity TEXT CHECK (specificity IN ('specialist', 'generalist')),
    source TEXT,
    notes TEXT,
    PRIMARY KEY (plant_id, fauna_id, relationship)
);

-- Climate cache (schema v14, V1.35). One row per ~1 km^2 location;
-- stores derived growing-degree-day and frost-window stats from the
-- Open-Meteo Historical Weather endpoint. Lat/lng are quantized to
-- 0.01 deg so close-by property pins reuse the same cached fetch
-- (an Open-Meteo archive call costs ~3-5 s, worth avoiding on every
-- pin move). The cache never auto-expires — ERA5 is historical and
-- doesn't change. A schema bump or an explicit refresh button is the
-- way to invalidate.
CREATE TABLE IF NOT EXISTS climate_cache (
    lat_q INTEGER NOT NULL,                    -- lat * 100, rounded
    lng_q INTEGER NOT NULL,                    -- lng * 100, rounded
    gdd5_mean REAL,                            -- mean annual GDD base 5C
    last_spring_frost_doy INTEGER,             -- 1-365, average across years
    first_fall_frost_doy  INTEGER,
    frost_free_days       INTEGER,             -- first_fall - last_spring
    years_used  INTEGER,
    source      TEXT,
    cached_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (lat_q, lng_q)
);

-- Per-location seasonal wind rose (schema v26, V1.67). The rose is a nested
-- dict (annual + seasonal blocks), so it's stored as a JSON blob rather than
-- one-column-per-field. Per-location user cache, wiped on reseed like
-- climate_cache (re-fetched on demand from Open-Meteo).
CREATE TABLE IF NOT EXISTS wind_cache (
    lat_q INTEGER NOT NULL,                    -- lat * 100, rounded
    lng_q INTEGER NOT NULL,                    -- lng * 100, rounded
    rose_json TEXT NOT NULL,                   -- compute_wind_rose() output
    source    TEXT,
    cached_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (lat_q, lng_q)
);

-- Shade-zone tag cache (schema v21, V1.53). DERIVED output only: caches the
-- resulting shade classification (full_sun / partial_shade / full_shade) per
-- planting zone, keyed by project + zone id, so the placement UI / analysis
-- panel can query without recomputing the cast-shade grid. Footprint geometry
-- and heights remain the project .perma.geojson file's responsibility (per
-- CLAUDE.md, project geometry never lives in the global DB); this table is a
-- fast index of the OUTPUT and is safe to wipe/recompute. project_key is a
-- stable id derived from the project file path (NOT geometry).
CREATE TABLE IF NOT EXISTS shade_zone_cache (
    project_key   TEXT NOT NULL,
    zone_id       TEXT NOT NULL,         -- e.g. "r{row}c{col}" grid cell or named zone
    shade_tag     TEXT NOT NULL CHECK (shade_tag IN
                    ('full_sun', 'partial_shade', 'full_shade')),
    shade_frac    REAL,                  -- season-avg fraction it was derived from
    centroid_lat  REAL,
    centroid_lng  REAL,
    computed_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (project_key, zone_id)
);
CREATE INDEX IF NOT EXISTS idx_shade_zone_project ON shade_zone_cache(project_key);

CREATE INDEX IF NOT EXISTS idx_plants_type    ON plants(plant_type);
CREATE INDEX IF NOT EXISTS idx_plants_zone    ON plants(hardiness_zone_min, hardiness_zone_max);
CREATE INDEX IF NOT EXISTS idx_plants_native  ON plants(native_to_alberta);
CREATE INDEX IF NOT EXISTS idx_calendar_plant ON planting_calendar(plant_id);
CREATE INDEX IF NOT EXISTS idx_polyculture_members  ON polyculture_members(polyculture_id);
CREATE INDEX IF NOT EXISTS idx_recipe_members ON polyculture_recipe_members(recipe_id);
CREATE INDEX IF NOT EXISTS idx_plant_uses_use       ON plant_uses(use_id);
CREATE INDEX IF NOT EXISTS idx_plant_fauna_plant    ON plant_fauna(plant_id);
CREATE INDEX IF NOT EXISTS idx_plant_fauna_fauna    ON plant_fauna(fauna_id);
CREATE INDEX IF NOT EXISTS idx_plant_fauna_rel      ON plant_fauna(relationship);

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
    permaculture_uses TEXT,         -- comma-separated tags
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
    growth_curve TEXT               -- fast_early | steady | slow_start
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
    created TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    modified TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS polyculture_members (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    polyculture_id INTEGER NOT NULL REFERENCES polycultures(id) ON DELETE CASCADE,
    plant_id INTEGER NOT NULL REFERENCES plants(id) ON DELETE CASCADE,
    role TEXT,
    offset_x REAL DEFAULT 0,
    offset_y REAL DEFAULT 0,
    notes TEXT
);

CREATE INDEX IF NOT EXISTS idx_plants_type    ON plants(plant_type);
CREATE INDEX IF NOT EXISTS idx_plants_zone    ON plants(hardiness_zone_min, hardiness_zone_max);
CREATE INDEX IF NOT EXISTS idx_plants_native  ON plants(native_to_alberta);
CREATE INDEX IF NOT EXISTS idx_calendar_plant ON planting_calendar(plant_id);
CREATE INDEX IF NOT EXISTS idx_polyculture_members  ON polyculture_members(polyculture_id);

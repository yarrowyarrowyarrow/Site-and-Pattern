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
    notes TEXT,
    -- Extended fields (schema v2)
    bloom_period TEXT,              -- e.g. "May–June"
    fruit_period TEXT,              -- e.g. "August–September"
    native_to_alberta INTEGER DEFAULT 0,  -- 1 = native to Alberta
    edible_parts TEXT,              -- comma-separated e.g. "fruit,leaves,flowers"
    deciduous_evergreen TEXT,       -- deciduous | evergreen | herbaceous
    soil_ph_min REAL,
    soil_ph_max REAL,
    perennial_or_annual TEXT        -- perennial | annual | biennial
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

CREATE INDEX IF NOT EXISTS idx_plants_type    ON plants(plant_type);
CREATE INDEX IF NOT EXISTS idx_plants_zone    ON plants(hardiness_zone_min, hardiness_zone_max);
CREATE INDEX IF NOT EXISTS idx_plants_native  ON plants(native_to_alberta);

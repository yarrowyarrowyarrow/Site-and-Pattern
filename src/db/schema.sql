CREATE TABLE IF NOT EXISTS plants (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    common_name TEXT NOT NULL,
    scientific_name TEXT,
    plant_type TEXT NOT NULL,
    hardiness_zone_min INTEGER,
    hardiness_zone_max INTEGER,
    sun_requirement TEXT,
    water_needs TEXT,
    native_region TEXT,
    permaculture_uses TEXT,
    spacing_meters REAL,
    mature_height_meters REAL,
    bloom_period TEXT,
    fruit_period TEXT,
    edible_parts TEXT,
    deciduous_evergreen TEXT,
    soil_ph_min REAL,
    soil_ph_max REAL,
    perennial_annual TEXT,
    notes TEXT
);

CREATE TABLE IF NOT EXISTS guilds (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT,
    center_plant_id INTEGER REFERENCES plants(id),
    created TEXT DEFAULT (datetime('now')),
    modified TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS guild_members (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id INTEGER NOT NULL REFERENCES guilds(id) ON DELETE CASCADE,
    plant_id INTEGER NOT NULL REFERENCES plants(id),
    role TEXT,
    offset_x REAL DEFAULT 0,
    offset_y REAL DEFAULT 0,
    notes TEXT
);

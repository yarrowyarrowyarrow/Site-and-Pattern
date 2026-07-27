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
    native_to_alberta INTEGER DEFAULT 0,  -- 1 = native to Alberta (back-compat
                                    -- flag; derived from native_provinces on seed)
    native_provinces TEXT,          -- comma-separated province codes the plant is
                                    -- native to (v42), e.g. "AB,SK". The
                                    -- province-neutral generalization of
                                    -- native_to_alberta.
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
    -- Schema v11; renamed ab_ecoregion -> ecoregion in v42 (province-neutral,
    -- Saskatchewan expansion). Ecoregion keys are shared across provinces where
    -- the ecoregion is the same — nature does not respect borders (P1/P2).
    ecoregion TEXT,                 -- comma-separated ecoregion tags
                                    -- (aspen_parkland, mixedgrass_prairie,
                                    --  moist_mixedgrass, fescue_foothills,
                                    --  boreal_mixedwood, riparian, wet_meadow,
                                    --  subalpine_montane)
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
    -- Fruit SHAPE (v49, V2.29) — the companion to fruit_color. Every fleshy
    -- fruit used to draw as the same sphere sprite, which made a strawberry, a
    -- rose hip and a chokecherry raceme all "red dot".
    fruit_form TEXT DEFAULT '',         -- berry | strig | raceme | cherry | pome | hip | strawberry | aggregate | flat_cluster | ''
    -- Imagery (schema v24, V1.60). An OPENLY-licensed photo + its citation;
    -- NULL/empty until the dataset workflow fills them. The app caches the URL
    -- locally and shows the attribution beside the photo (src/image_cache.py).
    image_url TEXT DEFAULT '',          -- http(s) URL or local path to an open-licensed photo
    image_attribution TEXT DEFAULT '',  -- e.g. "© Photographer, CC BY-SA 4.0 (via Wikimedia)"
    image_license TEXT DEFAULT '',      -- e.g. CC0 / CC BY / CC BY-SA / public domain
    -- Botanical morphology (schema v47, V2.29). What a species LOOKS like, so
    -- the 3D archetypes can read as themselves instead of as a generic member
    -- of their growth form. Authored for the woody species in
    -- scripts/seed_woody_morphology.py (which documents the fields and their
    -- sourcing); empty/NULL everywhere else, and every consumer falls back to
    -- the old behaviour, so this is additive.
    leaf_shape TEXT DEFAULT '',         -- needle|awl|scale|linear|lanceolate|elliptic|
                                        -- ovate|obovate|orbicular|cordate|lobed|
                                        -- trifoliate|compound_pinnate|compound_palmate
    leaf_size_cm REAL,                  -- typical mature blade (or needle) length, cm.
                                        -- Sets 3D foliage-mass grain in REAL metres:
                                        -- a 20 cm bur oak leaf reads coarse, a 2 cm
                                        -- dwarf-birch leaf fine, at the same crown size.
    leaf_arrangement TEXT DEFAULT '',   -- alternate|opposite|whorled|fascicled|basal
    bark_color TEXT DEFAULT '',         -- hex; the trunk/stem colour (red-osier dogwood
                                        -- red, aspen chalky green-white)
    fall_color TEXT DEFAULT '',         -- hex autumn foliage; '' = evergreen or no
                                        -- colouring (an honest empty, not a guess)
    branching TEXT DEFAULT '',          -- excurrent|decurrent|multi_stem|suckering|
                                        -- arching|prostrate|rosette (woody habit)
    -- Herbaceous habit (schema v48, V2.29). The SOURCE OF TRUTH for which 3D
    -- archetype a non-woody plant gets: the viewer's hardcoded genus table
    -- (03-herbs.js _HPROF) named only 65 genera, so 64 of the 211 wildflowers
    -- had their form guessed from flower shape and aspect — and two thirds of
    -- those collapsed onto one generic bush. Authored in
    -- scripts/seed_non_woody_morphology.py; empty for woody plants, which use
    -- `branching` instead.
    growth_form TEXT DEFAULT '',        -- erect|ferny|rosette|clump|grassy|mat|fern|
                                        -- vining|tussock|emergent|floating|cushion|
                                        -- succulent|sprawling
    -- Surface character (schema v52, V2.33). What a species' bark and foliage
    -- LOOK like close up, so the 3D viewer can draw a papery birch, a furrowed
    -- oak and a glaucous sage instead of one grain for every plant in the
    -- catalogue. Authored in scripts/seed_surface_morphology.py; empty
    -- everywhere the character isn't known, and the viewer falls back to a
    -- per-genus default (P9 — an honest empty, never an invented measurement).
    bark_texture TEXT DEFAULT '',       -- smooth|furrowed|papery|shaggy|scaly
    leaf_surface TEXT DEFAULT '',       -- matte|glossy|pubescent|glaucous
    -- The graminoid field mark (schema v52, V2.33). 79 grass/sedge/rush species
    -- all carried flower_form='plume' and drew the same generic spray, while an
    -- inflorescence is most of how a grass is identified in the field — a big
    -- bluestem is NAMED for its turkey-foot. Separate from flower_form on
    -- purpose: that column feeds pollinator logic (bee_habitat.tongue_form_fit,
    -- forage_calendar) where a grass is wind-pollinated and must stay 'plume'.
    inflorescence_form TEXT DEFAULT '', -- turkey_foot|open_panicle|contracted_spike|
                                        -- nodding_raceme|one_sided_raceme|bristly|
                                        -- sedge_cluster|rush_umbel|cattail_spike
    -- The bloom, as something to BUILD (schema v53, V2.34). Until now a flower
    -- was one 64x64 image per `flower_form` — fifteen pictures for 228
    -- wildflowers, unlit, seven quads in a disc at 90% of height. A forb in
    -- bloom is 60-80% flower to the eye, so that single fact was most of why a
    -- planting read as a cheap video game while its leaves were modelled at
    -- 1,200 triangles.
    --
    -- Separate from flower_form on exactly the grounds inflorescence_form took
    -- in v52: flower_form is a POLLINATOR-ACCESS statement (it feeds
    -- bee_habitat.tongue_form_fit and forage_calendar) and is not widened here.
    -- These columns are the picture.
    --
    -- Authored in scripts/seed_flower_morphology.py, family-first. Empty
    -- everywhere the character isn't known and the viewer falls back to the
    -- billboard it drew before, so partial coverage is never a broken plant
    -- (P9 — ranges and honest gaps, never false precision).
    flower_arch TEXT DEFAULT '',        -- solitary|raceme|spike|panicle|corymb|
                                        -- umbel|head|cyme|whorl
    flower_symmetry TEXT DEFAULT '',    -- radial|bilateral
    petal_shape TEXT DEFAULT '',        -- narrow|oval|notched|tubular|lipped
    petal_count INTEGER,                -- rays/petals per floret (5, 8, 21...)
    florets_per_head INTEGER,           -- florets on one head/spike/umbel
    flower_diameter_cm REAL,            -- ONE floret across. The most valuable
                                        -- missing number: bloom size is
                                        -- currently derived from canopy, so a
                                        -- pasqueflower and a sunflower scale
                                        -- with the plant instead of the flower.
    flower_center_color TEXT DEFAULT '',-- the disc/eye. A black-eyed Susan IS
                                        -- its dark disc; it was a yellow blob.
    flower_height_frac REAL,            -- how far the bloom is held above the
                                        -- foliage, as a fraction of height
    stem_branching TEXT DEFAULT '',     -- unbranched|branched_above|
                                        -- branched_throughout
    basal_rosette INTEGER DEFAULT 0,    -- 0/1
    -- How many inflorescences a MATURE plant carries (schema v54, V2.35). The
    -- 3D viewer sized its bloom display off the plant's canopy, which is a
    -- proxy for spread and not for flowering: a pasqueflower holds two flowers
    -- and a mature bergamot thirty, and "in full bloom" is mostly that number.
    -- No flora records it — it is one of the four things worth going out and
    -- counting (see docs/SPRITE_AUDIT.md), so these are genus-level estimates
    -- meant to be corrected with scripts/tune_morphology.py. Empty falls back
    -- to a count derived from stem_branching + stature, which is at least a
    -- structural consequence rather than a guess.
    flowering_stems INTEGER,
    -- WHERE each flower number came from (schema v55, V2.35). The catalogue
    -- describes 307 of 311 flowering species and has VERIFIED almost none of
    -- them: the seeder's values are genus-level botanical judgement, which is a
    -- reasonable starting point and is not the same thing as a measurement.
    -- Reporting those two as one number is exactly what P9 forbids, so the
    -- distinction is recorded rather than assumed.
    --   measured  — someone put a ruler on the plant
    --   flora     — read from a published description (FNA, Budd's, …)
    --   photo     — counted or judged off a photograph
    --   estimated — the family-first seeder's default
    -- Set in scripts/tune_morphology.py as the catalogue is worked through.
    flower_data_source TEXT DEFAULT ''
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
    -- Row provenance (schema v46): 'seed' = shipped example (wiped + re-seeded
    -- on every schema bump); 'user' = authored in the builder — NEVER wiped by
    -- the reseed. Default 'user' so anything the seeder didn't explicitly
    -- stamp is treated as the user's work.
    origin TEXT NOT NULL DEFAULT 'user',
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
    native_provinces TEXT,          -- comma-separated province codes (v42),
                                    -- e.g. "AB,SK"; province-neutral companion
                                    -- to ab_native.
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

-- Bee attributes (schema v39, F37 "see what a bee sees"). One row per fauna row
-- with taxon='bee'. Kept in a narrow table keyed on fauna_id rather than as extra
-- columns on the 5-taxon `fauna` table so the bee-only enums (tongue length,
-- nesting habit) and sparse fields don't add perpetually-NULL columns to birds /
-- lepidoptera / mammals. Data honesty (P8/P9): tongue_length is populated ONLY for
-- Bombus; 'unknown' / NULL means "not characterised", never a silent default.
-- floral_host_genera and flight_season are deliberately coarse free-text ranges.
CREATE TABLE IF NOT EXISTS bee_attributes (
    fauna_id INTEGER PRIMARY KEY REFERENCES fauna(id) ON DELETE CASCADE,
    genus TEXT,                    -- denormalised for genus-level grouping / selection
    nesting_habit TEXT CHECK (nesting_habit IN (
        'ground',         -- soil / underground excavators (Anthophora, Melissodes, many Bombus)
        'cavity',         -- pre-formed holes / reed tubes / drilled wood (mason, leafcutter)
        'pithy_stem',     -- excavate soft / pithy stems
        'social_ground',  -- social colonies in ground cavities, tussocks, old rodent nests (Bombus)
        'cleptoparasite', -- cuckoo bees: no nest, develop in a host bee's nest
        'unknown'
    )),
    host_genus TEXT,               -- cleptoparasites: host bee genus ('Bombus', 'Melissodes', …)
    tongue_length TEXT CHECK (tongue_length IN (
        'short', 'medium', 'long', 'unknown'
    )),
    flight_season TEXT,            -- free-text month range ("April–September"); parsed downstream
    floral_host_genera TEXT,       -- comma-separated plant genera ("Salix,Rosa,Solidago") | NULL
    pollen_specialist INTEGER,     -- 1 oligolectic, 0 polylectic, NULL unknown
    conservation_status TEXT,      -- free text ("Secure", "At Risk", "Data Deficient")
    source TEXT,
    notes TEXT
);
CREATE INDEX IF NOT EXISTS idx_bee_attr_genus   ON bee_attributes(genus);
CREATE INDEX IF NOT EXISTS idx_bee_attr_nesting ON bee_attributes(nesting_habit);

-- Lepidoptera attributes (schema v40, V2.12 "fly as a butterfly"). One row per
-- fauna row with taxon='lepidoptera'. Parallels bee_attributes: a narrow table
-- keyed on fauna_id so the lep-only fields (flight season, overwintering stage,
-- adult nectar genera) don't add perpetually-NULL columns to the 5-taxon fauna
-- table. Larval host plants stay in plant_fauna (relationship='larval_host').
-- Data honesty (P9): giant silk moths and some sphinxes DO NOT feed as adults —
-- nectar_flower_genera is NULL for them, never a silent generalist default.
CREATE TABLE IF NOT EXISTS lepidoptera_attributes (
    fauna_id INTEGER PRIMARY KEY REFERENCES fauna(id) ON DELETE CASCADE,
    kind TEXT CHECK (kind IN ('butterfly', 'moth', 'skipper')),
    activity TEXT CHECK (activity IN ('day', 'night', 'day_dusk', 'unknown')),
    flight_season TEXT,             -- free-text month range ("May-August"); parsed downstream
    overwintering_stage TEXT CHECK (overwintering_stage IN
        ('egg', 'larva', 'pupa', 'adult', 'migrant', 'unknown')),
    voltinism TEXT,                 -- free text ("one brood", "multiple broods")
    nectar_flower_genera TEXT,      -- comma-separated adult-nectar genera | NULL (non-feeding)
    larval_host_note TEXT,          -- plain-language summary (edges live in plant_fauna)
    conservation_status TEXT,
    source TEXT,
    notes TEXT
);
CREATE INDEX IF NOT EXISTS idx_lep_attr_kind ON lepidoptera_attributes(kind);

-- Native-plant nurseries / seed houses / societies (schema v44, V2.18).
-- Seeded from data/nurseries_master.json; feeds the site panel's "Where to buy
-- near you" section (src/db/nurseries.py). ``sells`` mirrors the plants
-- availability_class enum so a supplier can be matched to a plant's sourcing
-- tier. ``lat``/``lng`` are approximate (community-level), used only to sort
-- suppliers by rough distance from the property pin.
CREATE TABLE IF NOT EXISTS nurseries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    kind TEXT,                      -- native_nursery | seed_house | garden_centre | society
    province TEXT,                  -- AB, SK, ...
    city TEXT,
    lat REAL,
    lng REAL,
    url TEXT,
    sells TEXT,                     -- availability_class channel: native_specialist,
                                    -- seed_or_plug, garden_centre, big_box, rare
    ships INTEGER DEFAULT 0,        -- 1 = mail-order / ships province-wide
    notes TEXT
);
CREATE INDEX IF NOT EXISTS idx_nurseries_province ON nurseries(province);

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

-- ── The unified relationship-edges layer (schema v51, F7) ────────────────────
-- Design principle P3 (relationships matter more than components) and P10
-- (plants are nodes in a network) — see docs/DESIGN_PHILOSOPHY.md.
--
-- The app's ecology has always been stored as edges, but in four unrelated
-- shapes: plant_fauna carries trophic/shelter relationships, companion_friends
-- and companion_enemies carry horticultural affinity, and shared membership in
-- a polyculture carries "these grow together". Every consumer that wanted to
-- ask "what is connected to this plant?" had to know all four and join them by
-- hand. This VIEW is the single queryable answer, read by src/db/relationships.py.
--
-- Deliberately a VIEW, not a table: the per-relationship tables remain the
-- single source of truth and the seeders stay untouched, so there is no second
-- copy to drift and nothing extra for the reseed to wipe. Only DOCUMENTED edges
-- appear here — derived/second-order edges (two plants that feed the same
-- animal) are computed in Python and carry evidence='derived', so a caller can
-- always tell a record from an inference (P9).
--
-- `kind` is the vocabulary in src/db/relationships.py:EDGE_KINDS. `directed`
-- marks plant→fauna edges, which read one way ("nectar for"); plant↔plant edges
-- are symmetric and stored once per unordered pair.
DROP VIEW IF EXISTS relationship_edges;
CREATE VIEW relationship_edges AS
    SELECT pf.relationship            AS kind,
           'plant'                    AS a_type,
           pf.plant_id                AS a_id,
           'fauna'                    AS b_type,
           pf.fauna_id                AS b_id,
           1                          AS directed,
           COALESCE(pf.specificity, '') AS detail,
           COALESCE(pf.source, '')      AS source
      FROM plant_fauna pf
    UNION ALL
    SELECT 'companion_friend', 'plant', cf.plant_id_a, 'plant', cf.plant_id_b,
           0, '', ''
      FROM companion_friends cf
    UNION ALL
    SELECT 'companion_enemy', 'plant', ce.plant_id_a, 'plant', ce.plant_id_b,
           0, '', ''
      FROM companion_enemies ce
    UNION ALL
    -- Co-membership in an authored plant community. m2.plant_id > m1.plant_id
    -- keeps one row per unordered pair and drops self-pairs; DISTINCT collapses
    -- a pair that appears in several communities into one edge (the community
    -- names are re-gathered by the query API when a caller wants them).
    SELECT DISTINCT 'co_planted', 'plant', m1.plant_id, 'plant', m2.plant_id,
           0, '', 'polyculture'
      FROM polyculture_members m1
      JOIN polyculture_members m2
        ON m2.polyculture_id = m1.polyculture_id
       AND m2.plant_id > m1.plant_id;

-- ── Photo sets (schema v55, V2.35 — F70) ────────────────────────────────────
--
-- `plants.image_url` is ONE slot, and that single fact is most of what is wrong
-- with the app's photography. iNaturalist's leading photo is nearly always a
-- macro of a flower — the frame that identifies a plant to a botanist and the
-- least useful one for deciding whether you want it in your yard, or for finding
-- it there in May. With one column, improving the photo means LOSING the other.
-- 111 of 434 plants have no photo at all, and there was no path for the user's
-- own.
--
-- So: many photos per species, each in a NAMED SLOT, and `image_url` is
-- synthesized on read from the best available one (src/db/plants.py
-- _attach_photos) — exactly the way `permaculture_uses` has been synthesized
-- from the plant_uses junction since v37. Every existing consumer (the plant
-- browser, the 3D dossier, the bee/lep panels, photo_warm) keeps working and
-- gains better photos without a line of change.
--
-- KEYED BY NAME, NOT BY plant_id. Plant ids are not stable across a reseed
-- (AUTOINCREMENT, never reset) — a photo table keyed by id would silently
-- re-point photos at the wrong species on some future schema bump and nobody
-- would notice for months. The worked example (F44) and the reference
-- communities (F50) are authored as names for the same reason.
-- >>> plant_photos  (lifted verbatim by src/db/plants.py:_photo_ddl so the
-- v55 migration can create the table on a DB that predates it. Keep the
-- markers.)
CREATE TABLE IF NOT EXISTS plant_photos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scientific_name TEXT NOT NULL,
    slot TEXT NOT NULL,             -- habit|flower|leaf|fruit|bark_stem|winter|seedling
    url TEXT NOT NULL,              -- http(s) URL, or a path to a local file
    attribution TEXT DEFAULT '',    -- photographer + licence credit, shown beside the photo
    license TEXT DEFAULT '',        -- cc0 | cc-by | cc-by-sa | …
    source TEXT DEFAULT '',         -- inaturalist | owner | user | wikimedia
    -- Row provenance, the polycultures v46 pattern: 'seed' = shipped (wiped and
    -- re-seeded on every schema bump); 'user' = the person's own photograph,
    -- NEVER wiped. That one distinction is the whole of F72 — anything written
    -- into the seed-backed columns is destroyed on the next reseed, which is the
    -- trap this table exists to avoid.
    origin TEXT NOT NULL DEFAULT 'seed',
    -- When the photo was taken, ISO date, where it is known. Nothing reads it
    -- yet; it is here so F73 ("in my yard, on this date") is a UI change rather
    -- than another schema bump.
    taken_on TEXT DEFAULT '',
    rank INTEGER DEFAULT 0,         -- ordering within a slot; lowest wins
    notes TEXT DEFAULT ''           -- P12: the botanical/visual record ONLY
);

CREATE INDEX IF NOT EXISTS idx_plant_photos_name ON plant_photos(scientific_name);
CREATE INDEX IF NOT EXISTS idx_plant_photos_slot ON plant_photos(scientific_name, slot);
-- <<< plant_photos

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

import json
from .plants import get_connection


def _get_plant_by_name(common_name):
    """Look up a plant by common_name (case-insensitive)."""
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM plants WHERE LOWER(common_name) = LOWER(?)",
            (common_name,)
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_all_guilds(top_level_only=True):
    conn = get_connection()
    sql = ("SELECT g.*, p.common_name AS center_plant_name "
           "FROM guilds g LEFT JOIN plants p ON g.center_plant_id = p.id ")
    if top_level_only:
        sql += "WHERE g.parent_id IS NULL "
    sql += "ORDER BY g.name"
    rows = conn.execute(sql).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_guild_by_id(guild_id):
    conn = get_connection()
    row = conn.execute(
        "SELECT g.*, p.common_name AS center_plant_name "
        "FROM guilds g LEFT JOIN plants p ON g.center_plant_id = p.id "
        "WHERE g.id = ?",
        (guild_id,),
    ).fetchone()
    if not row:
        conn.close()
        return None
    guild = dict(row)
    members = conn.execute(
        "SELECT gm.*, p.common_name, p.plant_type "
        "FROM guild_members gm JOIN plants p ON gm.plant_id = p.id "
        "WHERE gm.guild_id = ? ORDER BY gm.id",
        (guild_id,),
    ).fetchall()
    guild["members"] = [dict(m) for m in members]
    conn.close()
    return guild


def create_guild(name, description, center_plant_id, parent_id=None):
    conn = get_connection()
    cur = conn.execute(
        "INSERT INTO guilds (name, description, center_plant_id, parent_id) VALUES (?, ?, ?, ?)",
        (name, description, center_plant_id, parent_id),
    )
    guild_id = cur.lastrowid
    conn.commit()
    conn.close()
    return guild_id


def get_guild_children(parent_id):
    """Get all variation guilds under a parent guild."""
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT g.*, p.common_name AS center_plant_name "
            "FROM guilds g LEFT JOIN plants p ON g.center_plant_id = p.id "
            "WHERE g.parent_id = ? ORDER BY g.name",
            (parent_id,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def add_guild_member(guild_id, plant_id, role, offset_x, offset_y, notes=""):
    conn = get_connection()
    conn.execute(
        "INSERT INTO guild_members (guild_id, plant_id, role, offset_x, offset_y, notes) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (guild_id, plant_id, role, offset_x, offset_y, notes),
    )
    conn.execute(
        "UPDATE guilds SET modified = datetime('now') WHERE id = ?", (guild_id,)
    )
    conn.commit()
    conn.close()


def remove_guild_member(member_id):
    conn = get_connection()
    row = conn.execute(
        "SELECT guild_id FROM guild_members WHERE id = ?", (member_id,)
    ).fetchone()
    conn.execute("DELETE FROM guild_members WHERE id = ?", (member_id,))
    if row:
        conn.execute(
            "UPDATE guilds SET modified = datetime('now') WHERE id = ?",
            (row["guild_id"],),
        )
    conn.commit()
    conn.close()


def delete_guild(guild_id):
    conn = get_connection()
    conn.execute("DELETE FROM guild_members WHERE guild_id = ?", (guild_id,))
    conn.execute("DELETE FROM guilds WHERE id = ?", (guild_id,))
    conn.commit()
    conn.close()


def update_guild(guild_id, name=None, description=None):
    conn = get_connection()
    if name is not None:
        conn.execute("UPDATE guilds SET name = ? WHERE id = ?", (name, guild_id))
    if description is not None:
        conn.execute(
            "UPDATE guilds SET description = ? WHERE id = ?", (description, guild_id)
        )
    conn.execute(
        "UPDATE guilds SET modified = datetime('now') WHERE id = ?", (guild_id,)
    )
    conn.commit()
    conn.close()


def duplicate_guild(guild_id, as_variation=False):
    """Duplicate a guild. If as_variation=True, create it as a child variation.

    The guild row and all member rows are written in a single transaction so
    a mid-operation failure cannot leave behind a half-populated guild.
    """
    guild = get_guild_by_id(guild_id)
    if not guild:
        return None

    if as_variation:
        children = get_guild_children(guild_id)
        var_num = len(children) + 1
        new_name = f"Variation {var_num}"
        parent_id = guild_id
    else:
        new_name = f"{guild['name']} (copy)"
        parent_id = guild.get("parent_id")

    members = guild.get("members", [])
    conn = get_connection()
    try:
        cur = conn.execute(
            "INSERT INTO guilds (name, description, center_plant_id, parent_id) "
            "VALUES (?, ?, ?, ?)",
            (new_name, guild["description"], guild["center_plant_id"], parent_id),
        )
        new_id = cur.lastrowid
        for m in members:
            conn.execute(
                "INSERT INTO guild_members "
                "(guild_id, plant_id, role, offset_x, offset_y, notes) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (new_id, m["plant_id"], m["role"],
                 m["offset_x"], m["offset_y"], m.get("notes", "")),
            )
        conn.commit()
        return new_id
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def export_guild(guild_id):
    guild = get_guild_by_id(guild_id)
    if not guild:
        return None
    data = {
        "name": guild["name"],
        "description": guild["description"] or "",
        "members": [],
    }
    for m in guild.get("members", []):
        data["members"].append(
            {
                "common_name": m["common_name"],
                "role": m["role"] or "",
                "offset_x": m["offset_x"],
                "offset_y": m["offset_y"],
            }
        )
    return data


def import_guild(data):
    warnings = []
    center_plant_id = None

    # Find center plant (offset 0,0 or first member)
    for m in data.get("members", []):
        if m.get("offset_x", 0) == 0 and m.get("offset_y", 0) == 0:
            plant = _get_plant_by_name(m["common_name"])
            if plant:
                center_plant_id = plant["id"]
            break

    guild_id = create_guild(
        data.get("name", "Imported Guild"),
        data.get("description", ""),
        center_plant_id,
    )

    for m in data.get("members", []):
        plant = _get_plant_by_name(m["common_name"])
        if plant:
            add_guild_member(
                guild_id,
                plant["id"],
                m.get("role", ""),
                m.get("offset_x", 0),
                m.get("offset_y", 0),
            )
        else:
            warnings.append(f"Plant not found: {m['common_name']}")

    return guild_id, warnings


# ── Example guild presets ────────────────────────────────────────────────────

EXAMPLE_GUILDS = [
    {
        "name": "Apple Tree Guild",
        "description": "Classic permaculture fruit tree guild for Zone 3-4. "
                       "Apple at centre with support plants filling understory and ground layer.",
        "members": [
            # (common_name, role, offset_x, offset_y)
            ("Goodland Apple",    "canopy",              0,    0),
            ("Comfrey",           "dynamic_accumulator", 1.5,  0.8),
            ("Chives",            "pest_repellent",     -1.2,  1.0),
            ("White Clover",      "nitrogen_fixer",      0,    1.5),
            ("Yarrow",            "pollinator",          1.0, -1.2),
            ("Wild Strawberry",   "groundcover",        -0.8, -1.0),
        ],
        "variations": [
            {
                "name": "Shade-Tolerant",
                "description": "Apple guild variant using shade-tolerant understory plants. "
                               "Better for north-facing or partially shaded sites.",
                "members": [
                    ("Goodland Apple",  "canopy",              0,    0),
                    ("Comfrey",         "dynamic_accumulator", 1.5,  0.8),
                    ("Wild Mint",       "pest_repellent",     -1.2,  1.0),
                    ("White Clover",    "nitrogen_fixer",      0,    1.5),
                    ("Gooseberry",      "understory",          1.0, -1.2),
                    ("Kinnikinnick (Bearberry)", "groundcover",-0.8, -1.0),
                ],
            },
        ],
    },
    {
        "name": "Saskatoon Berry Guild",
        "description": "Prairie-adapted shrub guild built around Saskatoon berry. "
                       "Great for Zone 2-4 food forests with native plants.",
        "members": [
            ("Saskatoon Berry",   "canopy",              0,    0),
            ("Wild Lupine",       "nitrogen_fixer",      1.0,  0.5),
            ("Yarrow",            "dynamic_accumulator",-0.8,  0.8),
            ("Wild Strawberry",   "groundcover",         0.5, -0.8),
            ("Chives",            "pest_repellent",     -0.5, -0.6),
            ("Bee Balm (Wild Bergamot)", "pollinator",   0.8, -0.5),
        ],
        "variations": [
            {
                "name": "Berry Focus",
                "description": "Saskatoon guild variant emphasizing fruit production. "
                               "Adds more berry-producing understory shrubs.",
                "members": [
                    ("Saskatoon Berry",  "canopy",             0,    0),
                    ("Wild Lupine",      "nitrogen_fixer",     1.0,  0.5),
                    ("Gooseberry",       "understory",        -0.8,  0.8),
                    ("Wild Strawberry",  "groundcover",        0.5, -0.8),
                    ("Red Currant",      "understory",        -0.5, -0.6),
                    ("Yarrow",           "pollinator",         0.8, -0.5),
                ],
            },
        ],
    },
    # ── Edmonton-specific guilds designed for Zone 3-4 ──────────────────────
    {
        "name": "Evans Cherry Guild",
        "description": "Fruit tree guild centred on Evans Cherry, a hardy sour cherry bred for "
                       "prairie climates. Comfrey mines deep nutrients and provides chop-and-drop "
                       "mulch. Chives and garlic repel aphids and borers common on cherries. "
                       "White clover fixes nitrogen as a living mulch, while bee balm attracts "
                       "native pollinators for improved fruit set. Wild strawberry suppresses "
                       "weeds and yields an additional ground-level harvest.",
        "members": [
            ("Evans Cherry",              "canopy",              0,    0),
            ("Comfrey",                   "dynamic_accumulator", 1.8,  0),
            ("Chives",                    "pest_repellent",     -1.0,  1.2),
            ("White Clover",              "nitrogen_fixer",      0,    2.0),
            ("Bee Balm (Wild Bergamot)",  "pollinator",         -1.5, -1.0),
            ("Wild Strawberry",           "groundcover",         1.0, -1.5),
            ("Garlic",                    "pest_repellent",      0,   -1.3),
        ],
        "variations": [
            {
                "name": "Native Understory",
                "description": "Evans Cherry guild variant using exclusively native prairie plants. "
                               "Replaces comfrey and garlic with native dynamic accumulators and "
                               "pest repellents. Yarrow is a native nutrient accumulator and "
                               "pollinator attractor; nodding onion replaces chives as a native "
                               "allium pest deterrent.",
                "members": [
                    ("Evans Cherry",              "canopy",              0,    0),
                    ("Yarrow",                    "dynamic_accumulator", 1.8,  0),
                    ("Nodding Onion",             "pest_repellent",     -1.0,  1.2),
                    ("Alfalfa",                   "nitrogen_fixer",      0,    2.0),
                    ("Bee Balm (Wild Bergamot)",  "pollinator",         -1.5, -1.0),
                    ("Wild Strawberry",           "groundcover",         1.0, -1.5),
                    ("Purple Coneflower",         "pollinator",          0,   -1.3),
                ],
            },
        ],
    },
    {
        "name": "Bur Oak Guild",
        "description": "Large shade-tree guild modelled on natural oak savanna ecosystems of the "
                       "aspen parkland. Bur oak provides a long-lived canopy with edible acorns. "
                       "Beaked hazelnut is a native understory shrub that naturally co-occurs with "
                       "oak and produces edible nuts. Wild lupine and white prairie clover fix "
                       "nitrogen in the dappled light. Comfrey accumulates nutrients from deep "
                       "soil layers. Dotted blazingstar is a premier pollinator magnet for native "
                       "bumble bees. Kinnikinnick forms an evergreen groundcover that suppresses "
                       "weeds under the spreading canopy.",
        "members": [
            ("Bur Oak",                   "canopy",              0,    0),
            ("Beaked Hazelnut",           "understory",          3.0,  1.5),
            ("Wild Lupine",               "nitrogen_fixer",     -2.0,  2.5),
            ("Comfrey",                   "dynamic_accumulator", 2.5, -1.5),
            ("Dotted Blazingstar",        "pollinator",         -2.5, -2.0),
            ("Kinnikinnick (Bearberry)",  "groundcover",         1.5, -2.5),
            ("White Prairie Clover",      "nitrogen_fixer",     -1.0,  3.0),
        ],
        "variations": [
            {
                "name": "Edible Savanna",
                "description": "Bur oak guild variant emphasizing food production. Saskatoon berry "
                               "and gooseberry replace hazelnut for more fruit. Canada goldenrod "
                               "provides late-season pollinator support.",
                "members": [
                    ("Bur Oak",                   "canopy",              0,    0),
                    ("Saskatoon Berry",           "understory",          3.0,  1.5),
                    ("Gooseberry",                "understory",         -2.5,  1.0),
                    ("Alfalfa",                   "nitrogen_fixer",     -2.0,  2.5),
                    ("Yarrow",                    "dynamic_accumulator", 2.5, -1.5),
                    ("Canada Goldenrod",          "pollinator",         -2.5, -2.0),
                    ("Wild Strawberry",           "groundcover",         1.5, -2.5),
                ],
            },
        ],
    },
    {
        "name": "Prairie Pollinator Garden",
        "description": "Native wildflower grouping designed to provide continuous bloom from "
                       "spring through fall for Edmonton-area pollinators. Based on aspen parkland "
                       "ecoregion recommendations. Prairie crocus blooms first in spring, followed "
                       "by wild bergamot and blanketflower in summer, with goldenrod and smooth "
                       "aster extending into late fall. Purple prairie clover is a critical native "
                       "bumble bee food source. Rough fescue provides overwintering habitat for "
                       "native bees. Group plants in clumps of 3-8 as recommended by pollinator "
                       "habitat guides.",
        "members": [
            ("Bee Balm (Wild Bergamot)",  "pollinator",          0,    0),
            ("Blanketflower",             "pollinator",          0.8,  0.5),
            ("Purple Prairie Clover",     "nitrogen_fixer",     -0.7,  0.6),
            ("Canada Goldenrod",          "pollinator",          0.5, -0.8),
            ("Smooth Aster",              "pollinator",         -0.8, -0.5),
            ("Prairie Crocus",            "pollinator",          0,    0.9),
            ("Rough Fescue",              "other",              -0.5, -0.9),
        ],
        "variations": [
            {
                "name": "Tall Prairie Meadow",
                "description": "Taller prairie pollinator variant featuring sunflowers and "
                               "penstemons. Giant sunflower anchors the centre, providing seeds "
                               "for birds. Maximilian sunflower, black-eyed Susan, and smooth "
                               "blue beardtongue create a dramatic mid-to-late summer display. "
                               "Wild blue flax adds early blue blooms that attract mason bees.",
                "members": [
                    ("Giant Sunflower",           "pollinator",          0,    0),
                    ("Maximilian Sunflower",      "pollinator",          0.8,  0.5),
                    ("Black-eyed Susan",          "pollinator",         -0.7,  0.6),
                    ("Smooth Blue Beardtongue",   "pollinator",          0.5, -0.8),
                    ("Wild Blue Flax",            "pollinator",         -0.8, -0.5),
                    ("Purple Prairie Clover",     "nitrogen_fixer",      0,    0.9),
                    ("Switchgrass",               "other",              -0.5, -0.9),
                ],
            },
        ],
    },
    {
        "name": "Boreal Shade Guild",
        "description": "Understory guild for shaded or north-facing areas beneath existing "
                       "spruce, poplar, or birch canopy. Modelled on natural boreal forest floor "
                       "communities. Wild sarsaparilla, bunchberry, and twinflower are classic "
                       "boreal companions found growing together in Alberta woodlands. Highbush "
                       "cranberry is a shade-tolerant native shrub that produces edible fruit. "
                       "Star-flowered Solomon's seal thrives in dappled woodland light. All "
                       "species tolerate the acidic soils typical under conifer canopy.",
        "members": [
            ("White Spruce",                    "canopy",              0,    0),
            ("Highbush Cranberry",              "understory",          2.5,  1.0),
            ("Wild Sarsaparilla",               "other",              -1.5,  1.5),
            ("Bunchberry",                      "groundcover",         1.0, -1.5),
            ("Twinflower",                      "groundcover",        -1.0, -1.8),
            ("Star-flowered Solomon's Seal",    "other",               1.8,  1.8),
            ("Wild Lily-of-the-valley",         "groundcover",        -2.0, -0.5),
        ],
        "variations": [
            {
                "name": "Edible Boreal Understory",
                "description": "Boreal shade guild variant emphasizing edible plants. Low-bush "
                               "cranberry and Labrador tea replace ornamental groundcovers. Wild "
                               "mint fills the ground layer with a useful aromatic herb that "
                               "thrives in moist shade. Red osier dogwood provides winter colour "
                               "and bird habitat.",
                "members": [
                    ("White Spruce",              "canopy",              0,    0),
                    ("Low-bush Cranberry",        "understory",          2.5,  1.0),
                    ("Red Osier Dogwood",         "understory",         -2.0,  1.5),
                    ("Labrador Tea",              "other",               1.0, -1.5),
                    ("Wild Mint",                 "groundcover",        -1.0, -1.8),
                    ("Wild Sarsaparilla",         "other",               1.8,  1.8),
                    ("Bog Cranberry",             "groundcover",        -2.0, -0.5),
                ],
            },
        ],
    },
    {
        "name": "Medicinal Herb Circle",
        "description": "Traditional medicinal plant guild arranged in a circle garden. Centred on "
                       "purple coneflower (Echinacea), North America's most popular herbal immune "
                       "support. Yarrow is used by First Nations for wound care and fever. Wild "
                       "mint and giant hyssop provide digestive and respiratory remedies. "
                       "Valerian is a traditional sleep aid. Self-heal (Prunella vulgaris) is "
                       "a widely used wound herb. All species are hardy perennials proven in "
                       "Zone 3 Alberta gardens.",
        "members": [
            ("Purple Coneflower",         "pollinator",          0,    0),
            ("Yarrow",                    "dynamic_accumulator", 0.8,  0.5),
            ("Wild Mint",                 "pest_repellent",     -0.7,  0.7),
            ("Giant Hyssop",              "pollinator",          0.5, -0.8),
            ("Valerian",                  "other",              -0.8, -0.3),
            ("Self-heal",                 "other",               0.3,  0.9),
            ("Bee Balm (Wild Bergamot)",  "pollinator",         -0.4, -0.8),
        ],
        "variations": [
            {
                "name": "First Nations Medicine Wheel",
                "description": "Medicinal herb circle variant drawing on traditional Indigenous "
                               "prairie plant uses. Sweetgrass is a sacred ceremonial plant. Rat "
                               "root (Acorus calamus) is used for throat and stomach ailments. "
                               "Seneca snakeroot is a traditional respiratory remedy. Prairie sage "
                               "provides smudging material. Wild licorice root was used as a "
                               "general tonic.",
                "members": [
                    ("Purple Coneflower",         "pollinator",          0,    0),
                    ("Sweetgrass",                "other",               0.8,  0.5),
                    ("Prairie Sage",              "pest_repellent",     -0.7,  0.7),
                    ("Rat Root",                  "other",               0.5, -0.8),
                    ("Wild Licorice",             "other",              -0.8, -0.3),
                    ("Seneca Snakeroot",          "other",               0.3,  0.9),
                    ("Yarrow",                    "dynamic_accumulator",-0.4, -0.8),
                ],
            },
        ],
    },
    {
        "name": "Native Berry Hedge",
        "description": "Linear guild for property edges and windbreaks, arranged as a layered "
                       "hedgerow. Combines native berry-producing shrubs with nitrogen fixers and "
                       "pollinator plants to create a productive living fence. Saskatoon berry and "
                       "chokecherry form the tall backbone spaced 2-3m apart. Haskap fills the "
                       "mid layer at 1m spacing. Wild rose and raspberry provide thorny security "
                       "at the base. Alfalfa fixes nitrogen between shrubs. Use offset_y as "
                       "distance along the hedge line.",
        "members": [
            ("Saskatoon Berry",           "canopy",              0,    0),
            ("Chokecherry",               "understory",          0,    3.0),
            ("Haskap (Blue Honeysuckle)", "understory",          0,    1.5),
            ("Raspberry",                 "understory",          0.8,  0.8),
            ("Prickly Rose",              "other",               0.8,  2.2),
            ("Alfalfa",                   "nitrogen_fixer",      0.5,  3.8),
            ("Canada Goldenrod",          "pollinator",         -0.5,  1.0),
        ],
        "variations": [
            {
                "name": "Wildlife Corridor Hedge",
                "description": "Native berry hedge variant optimized for bird and pollinator "
                               "habitat. Highbush cranberry and elderberry provide fall and winter "
                               "bird food. Snowberry adds winter interest and food for waxwings. "
                               "Buffalo berry fixes nitrogen while producing tart edible fruit. "
                               "Wolf willow provides silver-leaved windbreak at the base.",
                "members": [
                    ("Highbush Cranberry",        "canopy",              0,    0),
                    ("Elderberry",                "understory",          0,    3.0),
                    ("Buffalo Berry",             "nitrogen_fixer",      0,    1.5),
                    ("Snowberry",                 "understory",          0.8,  0.8),
                    ("Wolf Willow",               "windbreak",           0.8,  2.2),
                    ("Nanking Cherry",            "understory",         -0.5,  3.8),
                    ("Bee Balm (Wild Bergamot)",  "pollinator",         -0.5,  1.0),
                ],
            },
        ],
    },
]


def seed_example_guilds():
    """Create example guilds if none exist yet. Safe to call multiple times."""
    conn = get_connection()
    try:
        count = conn.execute("SELECT COUNT(*) FROM guilds").fetchone()[0]
        if count > 0:
            return  # Already have guilds, don't re-seed
    finally:
        conn.close()

    for guild_def in EXAMPLE_GUILDS:
        # Find center plant
        center_name = guild_def["members"][0][0]
        center_plant = _get_plant_by_name(center_name)
        center_id = center_plant["id"] if center_plant else None

        guild_id = create_guild(
            guild_def["name"], guild_def["description"], center_id
        )

        for common_name, role, ox, oy in guild_def["members"]:
            plant = _get_plant_by_name(common_name)
            if plant:
                add_guild_member(guild_id, plant["id"], role, ox, oy)

        # Create variations as child guilds
        for var_def in guild_def.get("variations", []):
            var_center_name = var_def["members"][0][0]
            var_center = _get_plant_by_name(var_center_name)
            var_center_id = var_center["id"] if var_center else None

            var_id = create_guild(
                var_def["name"], var_def["description"],
                var_center_id, parent_id=guild_id
            )

            for common_name, role, ox, oy in var_def["members"]:
                plant = _get_plant_by_name(common_name)
                if plant:
                    add_guild_member(var_id, plant["id"], role, ox, oy)

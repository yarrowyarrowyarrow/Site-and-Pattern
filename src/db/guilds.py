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
    """Duplicate a guild. If as_variation=True, create it as a child variation."""
    guild = get_guild_by_id(guild_id)
    if not guild:
        return None

    if as_variation:
        # Count existing variations to auto-name
        children = get_guild_children(guild_id)
        var_num = len(children) + 1
        new_name = f"Variation {var_num}"
        parent_id = guild_id
    else:
        new_name = f"{guild['name']} (copy)"
        parent_id = guild.get("parent_id")

    new_id = create_guild(
        new_name, guild["description"], guild["center_plant_id"], parent_id
    )
    for m in guild.get("members", []):
        add_guild_member(new_id, m["plant_id"], m["role"], m["offset_x"], m["offset_y"])
    return new_id


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

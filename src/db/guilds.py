import json
from .plants import get_connection, get_plant_by_name


def get_all_guilds():
    conn = get_connection()
    rows = conn.execute(
        "SELECT g.*, p.common_name AS center_plant_name "
        "FROM guilds g LEFT JOIN plants p ON g.center_plant_id = p.id "
        "ORDER BY g.name"
    ).fetchall()
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


def create_guild(name, description, center_plant_id):
    conn = get_connection()
    cur = conn.execute(
        "INSERT INTO guilds (name, description, center_plant_id) VALUES (?, ?, ?)",
        (name, description, center_plant_id),
    )
    guild_id = cur.lastrowid
    conn.commit()
    conn.close()
    return guild_id


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


def duplicate_guild(guild_id):
    guild = get_guild_by_id(guild_id)
    if not guild:
        return None
    new_id = create_guild(
        f"{guild['name']} (copy)", guild["description"], guild["center_plant_id"]
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
            plant = get_plant_by_name(m["common_name"])
            if plant:
                center_plant_id = plant["id"]
            break

    guild_id = create_guild(
        data.get("name", "Imported Guild"),
        data.get("description", ""),
        center_plant_id,
    )

    for m in data.get("members", []):
        plant = get_plant_by_name(m["common_name"])
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

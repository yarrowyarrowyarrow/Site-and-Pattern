import json
import math
from .plants import get_connection, _role_to_layer_functions

# Legacy role names → current ones. Keeps plant communities saved before the
# Native Habitat Designer rename rendering with the new vegetation-layer
# language without forcing a DB migration.
_LEGACY_ROLE_ALIASES = {
    "canopy":              "overstory",
    "dynamic_accumulator": "soil_builder",
    "pest_repellent":      "pest_deterrent",
}


def _normalize_role(role):
    if role and role in _LEGACY_ROLE_ALIASES:
        return _LEGACY_ROLE_ALIASES[role]
    return role


def _parse_functions(raw):
    """Decode the JSON-text `functions` column into a list of strings."""
    if not raw:
        return []
    if isinstance(raw, list):
        return [str(x) for x in raw if x]
    try:
        v = json.loads(raw)
    except (TypeError, ValueError):
        return []
    if isinstance(v, list):
        return [str(x) for x in v if x]
    return []


def _resolve_layer_functions(member_dict):
    """Return (layer, functions_list) for a member dict from any source.

    Accepts a row dict that may have:
      - explicit `layer` and `functions` (preferred),
      - only legacy `role` (derived via _role_to_layer_functions),
      - or no role info at all (returns (None, [])).
    """
    layer = (member_dict.get("layer") or "").strip() or None
    functions = _parse_functions(member_dict.get("functions"))
    if layer is None and not functions:
        # Fall back to the legacy single role.
        role = _normalize_role(member_dict.get("role"))
        layer, functions = _role_to_layer_functions(role)
    return layer, functions


def _derive_role(layer, functions):
    """Pick the legacy single `role` value to persist for back-compat.

    Layer wins over function (overstory > pollinator); falls back to the
    first function, then to "other".
    """
    if layer:
        return layer
    if functions:
        return functions[0]
    return "other"


def community_natural_radius(polyculture) -> float:
    """Return the natural radius of a community in metres.

    Defined as max(sqrt(ox² + oy²)) across members, with a 1 m floor so
    single-member or co-located communities still have a non-zero
    footprint for spacing-as-unit calculations. Used by the row/grid/
    circle "place as unit" path to pre-fill cell spacing.
    """
    members = (polyculture or {}).get("members") or []
    best = 0.0
    for m in members:
        ox = float(m.get("offset_x") or 0.0)
        oy = float(m.get("offset_y") or 0.0)
        r = math.sqrt(ox * ox + oy * oy)
        if r > best:
            best = r
    return max(1.0, best)


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


def get_all_polycultures(top_level_only=True):
    conn = get_connection()
    try:
        sql = ("SELECT g.*, p.common_name AS center_plant_name "
               "FROM polycultures g LEFT JOIN plants p ON g.center_plant_id = p.id ")
        if top_level_only:
            sql += "WHERE g.parent_id IS NULL "
        sql += "ORDER BY g.name"
        rows = conn.execute(sql).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_polyculture_by_id(polyculture_id):
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT g.*, p.common_name AS center_plant_name "
            "FROM polycultures g LEFT JOIN plants p ON g.center_plant_id = p.id "
            "WHERE g.id = ?",
            (polyculture_id,),
        ).fetchone()
        if not row:
            return None
        polyculture = dict(row)
        members = conn.execute(
            "SELECT gm.*, p.common_name, p.plant_type "
            "FROM polyculture_members gm JOIN plants p ON gm.plant_id = p.id "
            "WHERE gm.polyculture_id = ? ORDER BY gm.id",
            (polyculture_id,),
        ).fetchall()
        member_dicts = []
        for m in members:
            md = dict(m)
            md["role"] = _normalize_role(md.get("role"))
            layer, functions = _resolve_layer_functions(md)
            md["layer"] = layer
            md["functions"] = functions
            member_dicts.append(md)
        polyculture["members"] = member_dicts
        return polyculture
    finally:
        conn.close()


def create_polyculture(name, description, center_plant_id, parent_id=None):
    conn = get_connection()
    try:
        cur = conn.execute(
            "INSERT INTO polycultures (name, description, center_plant_id, parent_id) VALUES (?, ?, ?, ?)",
            (name, description, center_plant_id, parent_id),
        )
        polyculture_id = cur.lastrowid
        conn.commit()
        return polyculture_id
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def get_polyculture_children(parent_id):
    """Get all variation polycultures under a parent polyculture."""
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT g.*, p.common_name AS center_plant_name "
            "FROM polycultures g LEFT JOIN plants p ON g.center_plant_id = p.id "
            "WHERE g.parent_id = ? ORDER BY g.name",
            (parent_id,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def add_polyculture_member(polyculture_id, plant_id, role, offset_x, offset_y,
                            notes="", layer=None, functions=None):
    if plant_id is None:
        raise ValueError("plant_id must not be None")
    # If caller supplied only `role`, derive layer/functions from it so the
    # new columns aren't left blank for newly-seeded data.
    if layer is None and functions is None:
        layer, functions = _role_to_layer_functions(_normalize_role(role))
    functions = functions or []
    # Keep `role` populated for back-compat readers.
    role = role or _derive_role(layer, functions)
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO polyculture_members "
            "(polyculture_id, plant_id, role, layer, functions, offset_x, offset_y, notes) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (polyculture_id, plant_id, role, layer,
             json.dumps(list(functions)), offset_x, offset_y, notes),
        )
        conn.execute(
            "UPDATE polycultures SET modified = datetime('now') WHERE id = ?", (polyculture_id,)
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def replace_polyculture_members(polyculture_id, members):
    """Atomically swap the member set of a polyculture.

    ``members`` is a list of dicts with keys ``plant_id``, ``offset_x``,
    ``offset_y``, optional ``layer`` (single vegetation layer) and
    optional ``functions`` (list of ecological-function tags). Legacy
    callers that pass only ``role`` are still supported — the layer and
    functions are derived from the role on the fly.
    """
    conn = get_connection()
    try:
        conn.execute(
            "DELETE FROM polyculture_members WHERE polyculture_id = ?",
            (polyculture_id,),
        )
        for m in members or []:
            plant_id = m.get("plant_id")
            if plant_id is None:
                continue
            layer = m.get("layer")
            functions = m.get("functions")
            if layer is None and functions is None:
                layer, functions = _role_to_layer_functions(
                    _normalize_role(m.get("role"))
                )
            functions = list(functions or [])
            role = m.get("role") or _derive_role(layer, functions)
            conn.execute(
                "INSERT INTO polyculture_members "
                "(polyculture_id, plant_id, role, layer, functions, "
                " offset_x, offset_y, notes) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    polyculture_id,
                    plant_id,
                    role,
                    layer,
                    json.dumps(functions),
                    float(m.get("offset_x") or 0.0),
                    float(m.get("offset_y") or 0.0),
                    m.get("notes", "") or "",
                ),
            )
        conn.execute(
            "UPDATE polycultures SET modified = datetime('now') WHERE id = ?",
            (polyculture_id,),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def remove_polyculture_member(member_id):
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT polyculture_id FROM polyculture_members WHERE id = ?", (member_id,)
        ).fetchone()
        conn.execute("DELETE FROM polyculture_members WHERE id = ?", (member_id,))
        if row:
            conn.execute(
                "UPDATE polycultures SET modified = datetime('now') WHERE id = ?",
                (row["polyculture_id"],),
            )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def delete_polyculture(polyculture_id):
    conn = get_connection()
    try:
        conn.execute("DELETE FROM polyculture_members WHERE polyculture_id = ?", (polyculture_id,))
        conn.execute("DELETE FROM polycultures WHERE id = ?", (polyculture_id,))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def update_polyculture(polyculture_id, name=None, description=None):
    conn = get_connection()
    try:
        if name is not None:
            conn.execute("UPDATE polycultures SET name = ? WHERE id = ?", (name, polyculture_id))
        if description is not None:
            conn.execute(
                "UPDATE polycultures SET description = ? WHERE id = ?", (description, polyculture_id)
            )
        conn.execute(
            "UPDATE polycultures SET modified = datetime('now') WHERE id = ?", (polyculture_id,)
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def duplicate_polyculture(polyculture_id, as_variation=False):
    """Duplicate a polyculture. If as_variation=True, create it as a child variation.

    The polyculture row and all member rows are written in a single transaction so
    a mid-operation failure cannot leave behind a half-populated polyculture.
    """
    polyculture = get_polyculture_by_id(polyculture_id)
    if not polyculture:
        return None

    if as_variation:
        children = get_polyculture_children(polyculture_id)
        var_num = len(children) + 1
        new_name = f"Variation {var_num}"
        parent_id = polyculture_id
    else:
        new_name = f"{polyculture['name']} (copy)"
        parent_id = polyculture.get("parent_id")

    members = polyculture.get("members", [])
    conn = get_connection()
    try:
        cur = conn.execute(
            "INSERT INTO polycultures (name, description, center_plant_id, parent_id) "
            "VALUES (?, ?, ?, ?)",
            (new_name, polyculture["description"], polyculture["center_plant_id"], parent_id),
        )
        new_id = cur.lastrowid
        for m in members:
            layer = m.get("layer")
            functions = m.get("functions")
            if layer is None and functions is None:
                layer, functions = _role_to_layer_functions(
                    _normalize_role(m.get("role"))
                )
            functions = list(functions or [])
            role = m.get("role") or _derive_role(layer, functions)
            conn.execute(
                "INSERT INTO polyculture_members "
                "(polyculture_id, plant_id, role, layer, functions, "
                " offset_x, offset_y, notes) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (new_id, m["plant_id"], role, layer,
                 json.dumps(functions),
                 m["offset_x"], m["offset_y"], m.get("notes", "")),
            )
        conn.commit()
        return new_id
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def export_polyculture(polyculture_id):
    polyculture = get_polyculture_by_id(polyculture_id)
    if not polyculture:
        return None
    data = {
        "name": polyculture["name"],
        "description": polyculture["description"] or "",
        "members": [],
    }
    for m in polyculture.get("members", []):
        data["members"].append(
            {
                "common_name": m["common_name"],
                "role": m["role"] or "",
                "layer": m.get("layer") or "",
                "functions": list(m.get("functions") or []),
                "offset_x": m["offset_x"],
                "offset_y": m["offset_y"],
            }
        )
    return data


def import_polyculture(data):
    warnings = []
    center_plant_id = None

    # Find center plant (offset 0,0 or first member)
    for m in data.get("members", []):
        if m.get("offset_x", 0) == 0 and m.get("offset_y", 0) == 0:
            plant = _get_plant_by_name(m["common_name"])
            if plant:
                center_plant_id = plant["id"]
            break

    polyculture_id = create_polyculture(
        data.get("name", "Imported Polyculture"),
        data.get("description", ""),
        center_plant_id,
    )

    for m in data.get("members", []):
        plant = _get_plant_by_name(m["common_name"])
        if plant:
            layer = m.get("layer") or None
            functions = m.get("functions")
            if isinstance(functions, str):
                functions = _parse_functions(functions)
            add_polyculture_member(
                polyculture_id,
                plant["id"],
                m.get("role", ""),
                m.get("offset_x", 0),
                m.get("offset_y", 0),
                layer=layer,
                functions=functions,
            )
        else:
            warnings.append(f"Plant not found: {m['common_name']}")

    return polyculture_id, warnings


# ── Example polyculture presets ────────────────────────────────────────────────────

EXAMPLE_POLYCULTURES = [
    {
        "name": "Apple Tree Community",
        "description": "Classic native habitat fruit tree community for Zone 3-4. "
                       "Apple at centre with support plants filling understory and ground layer.",
        "members": [
            # (common_name, role, offset_x, offset_y)
            ("Goodland Apple",        "overstory",       0,    0),
            ("Stinging Nettle",       "soil_builder",    1.5,  0.8),
            ("Wild Chives",           "pest_deterrent", -1.2,  1.0),
            ("Purple Prairie Clover", "nitrogen_fixer",  0,    1.5),
            ("Yarrow",                "pollinator",      1.0, -1.2),
            ("Wild Strawberry",       "groundcover",    -0.8, -1.0),
        ],
        "variations": [
            {
                "name": "Shade-Tolerant",
                "description": "Apple community variant using shade-tolerant understory plants. "
                               "Better for north-facing or partially shaded sites.",
                "members": [
                    ("Goodland Apple",           "overstory",       0,    0),
                    ("Stinging Nettle",          "soil_builder",    1.5,  0.8),
                    ("Wild Mint",                "pest_deterrent", -1.2,  1.0),
                    ("Canada Milk Vetch",        "nitrogen_fixer",  0,    1.5),
                    ("Wild Gooseberry",          "understory",      1.0, -1.2),
                    ("Kinnikinnick (Bearberry)", "groundcover",    -0.8, -1.0),
                ],
            },
        ],
    },
    {
        "name": "Saskatoon Berry Community",
        "description": "Prairie-adapted shrub polyculture built around Saskatoon berry. "
                       "Great for Zone 2-4 native habitat plantings.",
        "members": [
            ("Saskatoon Berry",          "overstory",       0,    0),
            ("Silvery Lupine",           "nitrogen_fixer",  1.0,  0.5),
            ("Yarrow",                   "soil_builder",   -0.8,  0.8),
            ("Wild Strawberry",          "groundcover",     0.5, -0.8),
            ("Wild Chives",              "pest_deterrent", -0.5, -0.6),
            ("Bee Balm (Wild Bergamot)", "pollinator",      0.8, -0.5),
        ],
        "variations": [
            {
                "name": "Berry Focus",
                "description": "Saskatoon community variant emphasizing fruit production. "
                               "Adds more berry-producing understory shrubs.",
                "members": [
                    ("Saskatoon Berry",   "overstory",       0,    0),
                    ("Silvery Lupine",    "nitrogen_fixer",  1.0,  0.5),
                    ("Wild Gooseberry",   "understory",     -0.8,  0.8),
                    ("Wild Strawberry",   "groundcover",     0.5, -0.8),
                    ("Wild Red Currant",  "understory",     -0.5, -0.6),
                    ("Yarrow",            "pollinator",      0.8, -0.5),
                ],
            },
        ],
    },
    # ── Edmonton-specific polycultures designed for Zone 3-4 ──────────────────────
    {
        "name": "Evans Cherry Community",
        "description": "Fruit tree polyculture centred on Evans Cherry, a hardy sour cherry bred for "
                       "prairie climates. Stinging nettle accumulates deep nutrients and provides "
                       "chop-and-drop mulch. Wild chives and prairie sage repel aphids and borers "
                       "common on cherries. Purple prairie clover fixes nitrogen as a native ground "
                       "layer, while bee balm attracts native pollinators for improved fruit set. "
                       "Wild strawberry suppresses weeds and yields an additional ground-level harvest.",
        "members": [
            ("Evans Cherry",              "overstory",       0,    0),
            ("Stinging Nettle",           "soil_builder",    1.8,  0),
            ("Wild Chives",               "pest_deterrent", -1.0,  1.2),
            ("Purple Prairie Clover",     "nitrogen_fixer",  0,    2.0),
            ("Bee Balm (Wild Bergamot)",  "pollinator",     -1.5, -1.0),
            ("Wild Strawberry",           "groundcover",     1.0, -1.5),
            ("Prairie Sage",              "pest_deterrent",  0,   -1.3),
        ],
        "variations": [
            {
                "name": "Native Understory",
                "description": "Evans Cherry community variant using exclusively native prairie plants. "
                               "Yarrow is a native nutrient accumulator and pollinator attractor; "
                               "nodding onion provides allium-family pest deterrence; silvery lupine "
                               "fixes nitrogen in dappled light; wild bergamot draws native bumble bees.",
                "members": [
                    ("Evans Cherry",              "overstory",       0,    0),
                    ("Yarrow",                    "soil_builder",    1.8,  0),
                    ("Nodding Onion",             "pest_deterrent", -1.0,  1.2),
                    ("Silvery Lupine",            "nitrogen_fixer",  0,    2.0),
                    ("Bee Balm (Wild Bergamot)",  "pollinator",     -1.5, -1.0),
                    ("Wild Strawberry",           "groundcover",     1.0, -1.5),
                    ("Wild Bergamot",             "pollinator",      0,   -1.3),
                ],
            },
        ],
    },
    {
        "name": "Bur Oak Community",
        "description": "Large shade-tree polyculture modelled on natural oak savanna ecosystems of the "
                       "aspen parkland. Bur oak provides a long-lived canopy with edible acorns. "
                       "Beaked hazelnut is a native understory shrub that naturally co-occurs with "
                       "oak and produces edible nuts. Silvery lupine and white prairie clover fix "
                       "nitrogen in the dappled light. Stinging nettle accumulates nutrients from "
                       "deep soil layers. Dotted blazingstar is a premier pollinator magnet for "
                       "native bumble bees. Kinnikinnick forms an evergreen groundcover that "
                       "suppresses weeds under the spreading canopy.",
        "members": [
            ("Bur Oak",                   "overstory",       0,    0),
            ("Beaked Hazelnut",           "understory",      3.0,  1.5),
            ("Silvery Lupine",            "nitrogen_fixer", -2.0,  2.5),
            ("Stinging Nettle",           "soil_builder",    2.5, -1.5),
            ("Dotted Blazingstar",        "pollinator",     -2.5, -2.0),
            ("Kinnikinnick (Bearberry)",  "groundcover",     1.5, -2.5),
            ("White Prairie Clover",      "nitrogen_fixer", -1.0,  3.0),
        ],
        "variations": [
            {
                "name": "Edible Savanna",
                "description": "Bur oak community variant emphasizing food production. Saskatoon berry "
                               "and wild gooseberry replace hazelnut for more fruit. Canada goldenrod "
                               "provides late-season pollinator support.",
                "members": [
                    ("Bur Oak",                   "overstory",       0,    0),
                    ("Saskatoon Berry",           "understory",      3.0,  1.5),
                    ("Wild Gooseberry",           "understory",     -2.5,  1.0),
                    ("Silvery Lupine",            "nitrogen_fixer", -2.0,  2.5),
                    ("Yarrow",                    "soil_builder",    2.5, -1.5),
                    ("Canada Goldenrod",          "pollinator",     -2.5, -2.0),
                    ("Wild Strawberry",           "groundcover",     1.5, -2.5),
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
        "name": "Boreal Shade Community",
        "description": "Understory polyculture for shaded or north-facing areas beneath existing "
                       "spruce, poplar, or birch canopy. Modelled on natural boreal forest floor "
                       "communities. Wild sarsaparilla, bunchberry, and twinflower are classic "
                       "boreal companions found growing together in Alberta woodlands. Highbush "
                       "cranberry is a shade-tolerant native shrub that produces edible fruit. "
                       "Star-flowered Solomon's seal thrives in dappled woodland light. All "
                       "species tolerate the acidic soils typical under conifer canopy.",
        "members": [
            ("White Spruce",                    "overstory",              0,    0),
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
                "description": "Boreal shade community variant emphasizing edible plants. Low-bush "
                               "cranberry and Labrador tea replace ornamental groundcovers. Wild "
                               "mint fills the ground layer with a useful aromatic herb that "
                               "thrives in moist shade. Red osier dogwood provides winter colour "
                               "and bird habitat.",
                "members": [
                    ("White Spruce",              "overstory",              0,    0),
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
        "description": "Traditional native medicinal plant polyculture arranged in a circle garden. "
                       "Centred on wild bergamot, an aromatic native mint used by First Nations for "
                       "respiratory and digestive remedies and a favourite of native bumble bees. "
                       "Yarrow is used by First Nations for wound care and fever. Wild mint and "
                       "giant hyssop provide digestive and respiratory remedies. Valerian is a "
                       "traditional sleep aid. Self-heal (Prunella vulgaris) is a widely used wound "
                       "herb. All species are hardy native perennials proven in Zone 3 Alberta gardens.",
        "members": [
            ("Wild Bergamot",             "pollinator",      0,    0),
            ("Yarrow",                    "soil_builder",    0.8,  0.5),
            ("Wild Mint",                 "pest_deterrent", -0.7,  0.7),
            ("Giant Hyssop",              "pollinator",      0.5, -0.8),
            ("Valerian",                  "other",          -0.8, -0.3),
            ("Self-heal",                 "other",           0.3,  0.9),
            ("Bee Balm (Wild Bergamot)",  "pollinator",     -0.4, -0.8),
        ],
        "variations": [
            {
                "name": "First Nations Medicine Wheel",
                "description": "Medicinal herb circle variant drawing on traditional Indigenous "
                               "prairie plant uses. Sweetgrass is a sacred ceremonial plant. Rat "
                               "root (Acorus calamus) is used for throat and stomach ailments. "
                               "Seneca snakeroot is a traditional respiratory remedy. Prairie sage "
                               "provides smudging material. Wild licorice root was used as a "
                               "general tonic. Wild bergamot anchors the circle as a native "
                               "pollinator and traditional medicinal mint.",
                "members": [
                    ("Wild Bergamot",             "pollinator",      0,    0),
                    ("Sweetgrass",                "other",           0.8,  0.5),
                    ("Prairie Sage",              "pest_deterrent", -0.7,  0.7),
                    ("Rat Root",                  "other",           0.5, -0.8),
                    ("Wild Licorice",             "other",          -0.8, -0.3),
                    ("Seneca Snakeroot",          "other",           0.3,  0.9),
                    ("Yarrow",                    "soil_builder",   -0.4, -0.8),
                ],
            },
        ],
    },
    {
        "name": "Native Berry Hedge",
        "description": "Linear polyculture for property edges and windbreaks, arranged as a layered "
                       "hedgerow. Combines native berry-producing shrubs with nitrogen fixers and "
                       "pollinator plants to create a productive living fence. Saskatoon berry and "
                       "chokecherry form the tall backbone spaced 2-3m apart. Haskap fills the "
                       "mid layer at 1m spacing. Prickly wild rose and wild raspberry provide thorny "
                       "security at the base. Silvery lupine fixes nitrogen between shrubs. Use "
                       "offset_y as distance along the hedge line.",
        "members": [
            ("Saskatoon Berry",           "overstory",       0,    0),
            ("Chokecherry",               "understory",      0,    3.0),
            ("Haskap (Blue Honeysuckle)", "understory",      0,    1.5),
            ("Wild Raspberry",            "understory",      0.8,  0.8),
            ("Prickly Wild Rose",         "other",           0.8,  2.2),
            ("Silvery Lupine",            "nitrogen_fixer",  0.5,  3.8),
            ("Canada Goldenrod",          "pollinator",     -0.5,  1.0),
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
                    ("Highbush Cranberry",        "overstory",              0,    0),
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
    # ── Habitat-focused communities (designed around Habitat Value Score + forage) ───
    {
        "name": "Keystone Pollinator Mound",
        "description": "Maximises the Habitat Value 'keystone species' score. Built almost entirely "
                       "from Tallamy-style Alberta keystone species — willows and aspens that host "
                       "the most caterpillar diversity, and goldenrods / asters that anchor "
                       "late-season pollinator and bird-food webs. Expect significant lifts to the "
                       "keystone, host-plant, and bird-food categories from a single placement.",
        "members": [
            ("Trembling Aspen",            "overstory",       0,     0),
            ("Pussy Willow",               "shrub_layer",     2.5,   1.2),
            ("Sandbar Willow",             "shrub_layer",    -2.2,   1.5),
            ("Pin Cherry",                 "understory",      2.0,  -2.0),
            ("Canada Goldenrod",           "herbaceous",     -1.5,  -1.8),
            ("Smooth Aster",               "herbaceous",      1.0,  -1.0),
            ("Maximilian Sunflower",       "pollinator",      0.0,  -2.5),
        ],
    },
    {
        "name": "Caterpillar Host Garden",
        "description": "Built for the Habitat Value 'host plants' category. Each member is a "
                       "documented host for specialist Alberta butterfly or moth caterpillars — "
                       "willows host mourning cloak and swallowtails; milkweeds host monarch; "
                       "violets host fritillaries; columbine hosts columbine duskywing. This is the "
                       "single highest-impact community for caterpillar biodiversity, which feeds "
                       "almost all songbird nestlings.",
        "members": [
            ("Pussy Willow",               "shrub_layer",     0,     0),
            ("Sandbar Willow",             "shrub_layer",     2.5,   1.5),
            ("Showy Milkweed",             "herbaceous",     -2.0,   1.0),
            ("Green Milkweed",             "herbaceous",      1.5,  -1.5),
            ("Smooth Aster",               "herbaceous",     -1.5,  -1.0),
            ("Eastern Red Columbine",      "herbaceous",      1.0,   1.8),
            ("Early Blue Violet",          "groundcover",    -1.0,  -2.0),
        ],
    },
    {
        "name": "Songbird Berry Patch",
        "description": "Designed for the Habitat Value 'bird food' category and to stagger fruit "
                       "across the Wildlife Forage calendar from early summer into winter. "
                       "Strawberry (June) → saskatoon (July) → raspberry (July-Aug) → chokecherry "
                       "(Aug-Sep) → highbush cranberry & snowberry & wild rose hips (winter persistent). "
                       "Plants also appear on Human Forage tab.",
        "members": [
            ("Saskatoon Berry",            "shrub_layer",     0,     0),
            ("Chokecherry",                "understory",      2.5,   1.5),
            ("Wild Raspberry",             "shrub_layer",    -2.0,   1.5),
            ("Highbush Cranberry",         "shrub_layer",     2.0,  -2.0),
            ("Common Snowberry",           "shrub_layer",    -2.0,  -1.5),
            ("Prickly Wild Rose",          "shrub_layer",     1.0,  -2.5),
            ("Silver Buffaloberry",        "nitrogen_fixer", -1.5,   2.0),
            ("Wild Strawberry",            "groundcover",     0.5,  -1.0),
        ],
    },
    {
        "name": "Continuous Bloom Pollinator Strip",
        "description": "Closes nectar gaps across the entire Apr–Oct growing season — pussy willow "
                       "and prairie crocus carry early spring, golden bean and wild strawberry "
                       "cover May–June, wild bergamot anchors July, blazingstar carries late summer, "
                       "and goldenrod + smooth aster extend into the first frost. Drop this anywhere "
                       "the Wildlife Forage tab shows nectar gaps and the gap warning typically "
                       "clears in one placement.",
        "members": [
            ("Pussy Willow",               "shrub_layer",     0,     0),
            ("Prairie Crocus",             "herbaceous",      1.5,   1.0),
            ("Wild Strawberry",            "groundcover",    -1.0,   1.2),
            ("Golden Bean",                "nitrogen_fixer",  1.8,  -1.0),
            ("Bee Balm (Wild Bergamot)",   "pollinator",     -1.5,  -0.5),
            ("Dotted Blazingstar",         "pollinator",      0.5,  -1.8),
            ("Canada Goldenrod",           "pollinator",     -2.0,   0.5),
            ("Smooth Aster",               "pollinator",      2.0,   1.8),
        ],
    },
    {
        "name": "Native Edible Garden",
        "description": "Tuned for the Human Forage calendar. Every member has documented edible parts "
                       "and the harvest windows are staggered: wild strawberry (Jun-Jul), saskatoon "
                       "(Jul), wild raspberry (Jul-Aug), pin cherry (Aug), chokecherry (Aug-Sep), "
                       "highbush cranberry (Sep-Oct), beaked hazelnut (Sep-Oct). Most members are "
                       "also tagged as bird food, so they boost wildlife forage and habitat value too.",
        "members": [
            ("Saskatoon Berry",            "shrub_layer",     0,     0),
            ("Chokecherry",                "understory",      2.5,   1.2),
            ("Pin Cherry",                 "understory",     -2.0,   1.5),
            ("Wild Raspberry",             "shrub_layer",     1.5,  -1.5),
            ("Highbush Cranberry",         "shrub_layer",    -1.8,  -1.5),
            ("Beaked Hazelnut",            "shrub_layer",     2.5,  -0.5),
            ("Wild Strawberry",            "groundcover",     0.0,  -2.2),
        ],
    },
    {
        "name": "Aspen Parkland Edge",
        "description": "Maximises the Habitat Value 'vegetation layers' score — every canonical "
                       "layer is represented (overstory aspen, understory chokecherry, shrub layer "
                       "saskatoon, herbaceous goldenrod, groundcover strawberry). Mirrors the natural "
                       "edge structure of central Alberta's aspen parkland, the most species-rich "
                       "ecoregion in the province. Strong all-round lift to habitat value.",
        "members": [
            ("Trembling Aspen",            "overstory",       0,     0),
            ("Chokecherry",                "understory",      3.0,   1.5),
            ("Saskatoon Berry",            "shrub_layer",    -2.5,   1.5),
            ("Beaked Hazelnut",            "shrub_layer",     2.0,  -2.0),
            ("Canada Goldenrod",           "herbaceous",     -2.0,  -1.5),
            ("Smooth Aster",               "herbaceous",      1.0,  -2.5),
            ("Wild Strawberry",            "groundcover",     0.0,   2.5),
        ],
    },
    {
        "name": "Mixedgrass Prairie Patch",
        "description": "Pairs native bunchgrasses (nesting material for ground-nesting bees and "
                       "songbirds) with prairie forbs that bloom in succession from spring crocus "
                       "to late-summer blazingstar. Designed for dry, open sites in southern and "
                       "central Alberta. Boosts the Habitat Value layers score (grasses → "
                       "herbaceous), bloom continuity, and the nesting-material structural metric.",
        "members": [
            ("Rough Fescue",               "herbaceous",      0,     0),
            ("June Grass",                 "herbaceous",      1.5,   1.0),
            ("Little Bluestem",            "herbaceous",     -1.5,   1.2),
            ("Prairie Crocus",             "herbaceous",      0.8,  -1.0),
            ("Dotted Blazingstar",         "pollinator",     -1.0,  -1.2),
            ("Purple Prairie Clover",      "nitrogen_fixer",  1.2,  -1.8),
            ("Yarrow",                     "soil_builder",   -1.5,  -0.5),
        ],
    },
    {
        "name": "Boreal Woodland Floor",
        "description": "Shade-tolerant community for north-facing sites or established conifer / "
                       "aspen understory. Bunchberry, twinflower, and wild lily-of-the-valley form "
                       "a classic boreal-floor mosaic; beaked hazelnut, bog cranberry, and wild "
                       "strawberry add bird food and edible berries. Most members are bird_food-tagged, "
                       "boosting that Habitat Value category in the hardest-to-plant niche.",
        "members": [
            ("White Spruce",               "overstory",       0,     0),
            ("Beaked Hazelnut",            "shrub_layer",     2.5,   1.5),
            ("Bunchberry",                 "groundcover",    -1.5,   1.2),
            ("Twinflower",                 "groundcover",     1.5,  -1.0),
            ("Bog Cranberry",              "groundcover",    -1.0,  -1.5),
            ("Wild Strawberry",            "groundcover",     0.5,   2.0),
            ("Wild Lily-of-the-valley",    "groundcover",    -2.0,  -0.5),
        ],
    },
    {
        "name": "Late-Season Pollinator Refuge",
        "description": "Targets the Aug–Oct nectar-gap months that the Wildlife Forage calendar "
                       "most often flags as red. All members bloom late-summer through first frost "
                       "and most are keystone species (goldenrods, asters, sunflowers), so this "
                       "community lifts both bloom-continuity and keystone-species scores at once. "
                       "Critical fuel for migrating monarchs and hibernating queen bumble bees.",
        "members": [
            ("Canada Goldenrod",           "pollinator",      0,     0),
            ("Smooth Aster",               "pollinator",      1.5,   1.0),
            ("Dotted Blazingstar",         "pollinator",     -1.5,   1.2),
            ("Meadow Blazingstar",         "pollinator",      1.2,  -1.5),
            ("Maximilian Sunflower",       "pollinator",     -1.0,  -1.8),
            ("Fireweed",                   "pollinator",      2.0,  -0.5),
            ("Showy Milkweed",             "herbaceous",     -2.0,  -0.5),
        ],
    },
    {
        "name": "Riparian Willow Thicket",
        "description": "Streamside / wet-edge community built around the willow guild — pussy willow "
                       "and sandbar willow are both Tallamy keystones AND host plants AND bird food, "
                       "so this single community lifts all three categories at once. Red osier dogwood "
                       "adds winter colour and bird food. Showy milkweed and fireweed bring "
                       "summer-long bloom and additional caterpillar hosting.",
        "members": [
            ("Pussy Willow",               "overstory",       0,     0),
            ("Sandbar Willow",             "shrub_layer",     2.5,   1.5),
            ("Red Osier Dogwood",          "shrub_layer",    -2.0,   1.5),
            ("Highbush Cranberry",         "shrub_layer",     2.0,  -2.0),
            ("Showy Milkweed",             "herbaceous",     -1.5,  -1.5),
            ("Fireweed",                   "herbaceous",      1.0,  -1.0),
            ("Wild Strawberry",            "groundcover",     0.0,   2.5),
        ],
    },
]


def seed_example_polycultures():
    """Create example polycultures if none exist yet. Safe to call multiple times."""
    conn = get_connection()
    try:
        count = conn.execute("SELECT COUNT(*) FROM polycultures").fetchone()[0]
        if count > 0:
            return  # Already have polycultures, don't re-seed
    finally:
        conn.close()

    for polyculture_def in EXAMPLE_POLYCULTURES:
        # Find center plant
        center_name = polyculture_def["members"][0][0]
        center_plant = _get_plant_by_name(center_name)
        center_id = center_plant["id"] if center_plant else None

        polyculture_id = create_polyculture(
            polyculture_def["name"], polyculture_def["description"], center_id
        )

        for common_name, role, ox, oy in polyculture_def["members"]:
            plant = _get_plant_by_name(common_name)
            if plant:
                add_polyculture_member(polyculture_id, plant["id"], role, ox, oy)

        # Create variations as child polycultures
        for var_def in polyculture_def.get("variations", []):
            var_center_name = var_def["members"][0][0]
            var_center = _get_plant_by_name(var_center_name)
            var_center_id = var_center["id"] if var_center else None

            var_id = create_polyculture(
                var_def["name"], var_def["description"],
                var_center_id, parent_id=polyculture_id
            )

            for common_name, role, ox, oy in var_def["members"]:
                plant = _get_plant_by_name(common_name)
                if plant:
                    add_polyculture_member(var_id, plant["id"], role, ox, oy)

# Design principle P1 (a generative pattern language — communities as reusable,
# site-responsive patterns) and P3 (relationships matter more than components) —
# see docs/DESIGN_PHILOSOPHY.md.
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


def get_polyculture_by_name(name: str):
    """Look up a top-level or variation polyculture by exact name. Returns
    the raw row dict (no members) or ``None`` if no match. Used by the
    Plants-tab Save-as-Community flow to detect name collisions before
    creating a new community."""
    if not name:
        return None
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM polycultures WHERE name = ? LIMIT 1",
            (name,),
        ).fetchone()
        return dict(row) if row else None
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


def create_polyculture(name, description, center_plant_id, parent_id=None, *,
                        problem=None, context=None, forces=None, solution=None):
    """Create a polyculture row.

    ``problem`` / ``context`` / ``forces`` / ``solution`` are the authored
    Alexander pattern-language fields (schema v27, F4); they are optional so
    user-created communities (which only fill name + description) keep working.
    """
    conn = get_connection()
    try:
        cur = conn.execute(
            "INSERT INTO polycultures "
            "(name, description, center_plant_id, parent_id, "
            " problem, context, forces, solution) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (name, description, center_plant_id, parent_id,
             problem, context, forces, solution),
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


def update_polyculture(polyculture_id, name=None, description=None, *,
                       problem=None, context=None, forces=None, solution=None):
    """Update editable polyculture fields. Any argument left ``None`` is
    untouched; pass the pattern-language fields (problem/context/forces/
    solution) to edit the authored Alexander framing (schema v27, F4)."""
    conn = get_connection()
    try:
        updates = {
            "name": name, "description": description,
            "problem": problem, "context": context,
            "forces": forces, "solution": solution,
        }
        for col, val in updates.items():
            if val is not None:
                conn.execute(
                    f"UPDATE polycultures SET {col} = ? WHERE id = ?",
                    (val, polyculture_id),
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
        # Authored pattern-language fields (schema v27, F4) — round-tripped so a
        # shared community keeps its problem/context/forces/solution framing.
        "problem": polyculture.get("problem") or "",
        "context": polyculture.get("context") or "",
        "forces": polyculture.get("forces") or "",
        "solution": polyculture.get("solution") or "",
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
        problem=data.get("problem") or None,
        context=data.get("context") or None,
        forces=data.get("forces") or None,
        solution=data.get("solution") or None,
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


# ── Alexander pattern-language text (F4) ────────────────────────────────────────────
# Authored problem / context / forces / solution for each seeded community, keyed by
# name. Kept separate from the spatial member layout in EXAMPLE_POLYCULTURES so the
# editorial voice is easy to read and edit. The *measured* parts of each pattern
# (site envelope, ecological forces, related patterns) are NOT stored here — they are
# derived live from member data in src/pattern_language.py and appended at display
# time, so they never drift as the catalogue grows.
#
#   problem  — the need / conflict the community resolves (Alexander's bold headline)
#   context  — where & when to reach for it (the larger situation it serves)
#   forces   — the competing considerations it balances
#   solution — the instruction ("Therefore: …")
_PATTERN_TEXT = {
    # ── Fruit & nut tree guilds ──────────────────────────────────────────────
    "Apple Tree Community": {
        "problem": "A lone fruit tree on mown grass competes with turf for water "
                   "and nutrients, feeds little wildlife, and leans on you for "
                   "fertiliser and pest control.",
        "context": "A sunny spot with room for a small tree, where you want fruit "
                   "for the kitchen and a self-supporting guild rather than a "
                   "specimen in a lawn.",
        "forces": "The tree wants nutrients, pollination, and fewer pests; you want "
                  "low maintenance and a harvest. Bare ground under a tree invites "
                  "weeds, while the right companions feed the soil and the bees "
                  "instead.",
        "solution": "Therefore: plant the apple at the centre and ring it with a "
                    "working guild — a nutrient accumulator and nitrogen fixer to "
                    "feed the soil, alliums and aromatic herbs to deter pests, a "
                    "pollinator magnet for fruit set, and a living groundcover to "
                    "hold moisture and shade out weeds.",
    },
    "Shade-Tolerant": {
        "problem": "North-facing or partly shaded yards still want a fruit guild, "
                   "but sun-loving prairie companions sulk and fail there.",
        "context": "The same apple guild, sited where buildings, fences, or taller "
                   "trees cast shade for part of the day.",
        "forces": "Fruit trees tolerate some shade, but most understory companions "
                  "need full sun; choosing shade-adapted natives keeps the guild "
                  "functioning where light is limited.",
        "solution": "Therefore: keep the apple but swap the understory for "
                    "shade-tolerant natives — woodland-edge shrubs, shade-happy mint, "
                    "and a creeping evergreen groundcover that thrives out of full sun.",
    },
    "Saskatoon Berry Community": {
        "problem": "Saskatoon is the prairie's most reliable berry, but planted "
                   "alone it asks for weeding and watering and gives nothing back to "
                   "the soil.",
        "context": "An open, prairie-adapted yard (Zone 2–4) where you want a tough, "
                   "fruiting shrub guild that shrugs off cold and drought.",
        "forces": "The shrub wants pollinators and fertile soil; you want fruit with "
                  "little fuss. Prairie companions can fix nitrogen and draw bees "
                  "without needing pampering.",
        "solution": "Therefore: anchor with saskatoon and surround it with a "
                    "nitrogen-fixing lupine, a nutrient-accumulating yarrow, an "
                    "allium pest-deterrent, a pollinator forb, and a strawberry "
                    "groundcover for a second, ground-level harvest.",
    },
    "Berry Focus": {
        "problem": "When the goal is a serious berry harvest, ornamental companions "
                   "earn their space only if they also produce.",
        "context": "A saskatoon guild on a productive site where you are willing to "
                   "trade a little pollinator flash for more fruit.",
        "forces": "Every slot in a small guild is a choice; replacing flowers with "
                  "fruiting shrubs raises yield but must not starve the bees that "
                  "set that fruit.",
        "solution": "Therefore: keep the nitrogen fixer and one pollinator, but fill "
                    "the rest with extra berry shrubs (gooseberry, currant) for a "
                    "layered, fruit-forward planting.",
    },
    "Evans Cherry Community": {
        "problem": "Sour cherries set heavily on the prairies but draw aphids and "
                   "borers, and a cherry in turf competes for everything it needs.",
        "context": "A Zone 3–4 yard with room for a small fruit tree, where you want "
                   "pie cherries and a guild that manages its own pests.",
        "forces": "The tree needs pollination and protection; you want fruit without "
                  "spraying. Aromatic and allium companions confuse pests while "
                  "natives feed the soil and the bees.",
        "solution": "Therefore: centre the cherry and ring it with chop-and-drop "
                    "nettle, aphid-deterring chives and sage, a nitrogen-fixing "
                    "clover, a bee-balm pollinator, and a weed-suppressing strawberry "
                    "groundcover.",
    },
    "Native Understory": {
        "problem": "Gardeners who want a strictly native planting need a cherry guild "
                   "with no introduced companions.",
        "context": "An Evans cherry guild for purists restoring local biodiversity, "
                   "or sites where only Alberta natives are wanted.",
        "forces": "Native-only narrows the palette, but Alberta's prairie flora "
                  "covers every guild role — nutrient accumulation, pest deterrence, "
                  "nitrogen fixing, and pollination.",
        "solution": "Therefore: keep the cherry and fill every support role with "
                    "natives — yarrow, nodding onion, silvery lupine, and wild "
                    "bergamot — for a guild that is functional and fully local.",
    },
    "Bur Oak Community": {
        "problem": "A big shade tree planted into lawn is decades of slow growth over "
                   "sterile turf, when it could be the spine of a whole habitat.",
        "context": "A large yard or acreage with space for a long-lived canopy tree, "
                   "modelled on the aspen parkland's natural oak savanna.",
        "forces": "An oak is a 200-year investment and a keystone for caterpillars "
                  "and acorn-eaters; the dappled light beneath it can grow a rich, "
                  "layered community instead of grass.",
        "solution": "Therefore: plant bur oak as the canopy and build the savanna "
                    "beneath it — a nut-bearing hazelnut understory, nitrogen-fixing "
                    "clovers in the dappled light, a nutrient accumulator, a "
                    "blazingstar pollinator, and an evergreen groundcover under the "
                    "spread.",
    },
    "Edible Savanna": {
        "problem": "An oak guild can lean harder into food if the understory is chosen "
                   "for the kitchen as well as for wildlife.",
        "context": "A bur oak savanna on a site where you want acorns plus berries "
                   "and a long pollinator season.",
        "forces": "Food production and habitat value usually reinforce each other — "
                  "native fruit shrubs feed both people and birds — so the trade-off "
                  "is gentle.",
        "solution": "Therefore: keep the oak and nitrogen fixer but swap in saskatoon "
                    "and gooseberry for fruit and a late goldenrod for end-of-season "
                    "nectar.",
    },
    # ── Pollinator & wildflower communities ──────────────────────────────────
    "Prairie Pollinator Garden": {
        "problem": "A flowerbed that blooms all at once leaves pollinators hungry for "
                   "the rest of the season.",
        "context": "A sunny bed or border where you want colour and a continuous "
                   "nectar supply built on aspen-parkland wildflowers.",
        "forces": "Different bees and butterflies fly at different times; bloom has to "
                  "be spread across spring, summer, and fall, and bees need bare ground "
                  "and grass stems to overwinter, not bare mulch.",
        "solution": "Therefore: choose species that hand the baton along the season — "
                    "crocus first, bergamot and blanketflower in summer, goldenrod and "
                    "aster into fall — add a nitrogen-fixing clover, and leave a "
                    "bunchgrass for nesting. Plant in clumps of 3–8.",
    },
    "Tall Prairie Meadow": {
        "problem": "Short pollinator beds can read as tidy plantings; sometimes you "
                   "want the drama and bird-seed of a tall-grass prairie.",
        "context": "An open, sunny area with room for waist-to-shoulder-high forbs and "
                   "grasses that won't shade out a path.",
        "forces": "Height brings presence and seed for birds but can flop or crowd "
                  "neighbours; sunflowers and tall grasses need full sun and space.",
        "solution": "Therefore: anchor with a giant sunflower for birds, layer in "
                    "Maximilian sunflower, black-eyed Susan, and beardtongue for a "
                    "mid-to-late display, add early flax for mason bees, and let a tall "
                    "grass hold it together.",
    },
    "Aromatic Herb Circle": {
        "problem": "Herb gardens are often a tidy row of single plants that do little "
                   "for wildlife and need replanting each year.",
        "context": "A sunny, well-drained spot near the kitchen or path where scent, "
                   "tea, and bees are all welcome.",
        "forces": "You want fragrance and useful leaves; pollinators want nectar. "
                  "Hardy native perennials give both and come back every year, "
                  "tolerating dry summers once rooted.",
        "solution": "Therefore: ring a wild-bergamot centre with yarrow, mint, hyssop, "
                    "valerian, and self-heal — a circle of aromatic Zone-3 perennials "
                    "that feeds bees and the teapot alike.",
    },
    "Native Prairie Aromatics": {
        "problem": "An all-native aromatic planting needs species that are fragrant, "
                   "bee-friendly, and genuinely local — not garden-centre herbs.",
        "context": "A sunny prairie-restoration bed where strong scent and a long "
                   "bloom window are wanted from Alberta natives only.",
        "forces": "The native aromatic palette is narrower but drought-tough; chosen "
                  "well it covers June into September with nectar and scent.",
        "solution": "Therefore: combine wild bergamot, sweetgrass, prairie sage, rat "
                    "root, wild licorice, seneca snakeroot, and yarrow for a fragrant, "
                    "fully native, low-water circle.",
    },
    "Keystone Pollinator Mound": {
        "problem": "Most plantings spread effort across many average species when a "
                   "few keystone plants would do far more ecological work.",
        "context": "Any sunny spot where you want the biggest habitat return from a "
                   "single placement — the 80/20 of native gardening.",
        "forces": "A handful of Tallamy keystone genera (willow, aspen, goldenrod, "
                  "aster) host the lion's share of caterpillars and anchor the food "
                  "web; concentrating on them beats scattering generalists.",
        "solution": "Therefore: build the planting almost entirely from keystones — an "
                    "aspen and willows for caterpillar diversity, goldenrods, asters, "
                    "and sunflower for late pollen and bird seed.",
    },
    "Caterpillar Host Garden": {
        "problem": "Nectar gardens feed adult butterflies but starve their "
                   "caterpillars — and without caterpillars there are almost no baby "
                   "birds.",
        "context": "A sunny bed for gardeners who want to breed butterflies and feed "
                   "nesting songbirds, not just host visiting adults.",
        "forces": "Specialist caterpillars can only eat specific host plants "
                  "(monarchs need milkweed, fritillaries need violets); a real "
                  "butterfly garden has to grow the leaves, not only the flowers.",
        "solution": "Therefore: plant documented Alberta host plants together — "
                    "willows, milkweeds, violets, columbine, and aster — so the whole "
                    "life cycle, caterpillar to bird, has what it needs.",
    },
    "Songbird Berry Patch": {
        "problem": "Birds need fruit across many months, but a single berry shrub "
                   "gives one short glut and then nothing.",
        "context": "A yard corner or border where you want to feed songbirds from "
                   "early summer straight through winter.",
        "forces": "Fruiting windows are short and species-specific; staggering "
                  "early, mid, and winter-persistent berries keeps the buffet open, "
                  "and a nitrogen fixer keeps the shrubs productive.",
        "solution": "Therefore: stack the harvest — strawberry and saskatoon for early "
                    "summer, raspberry and chokecherry for late summer, and "
                    "cranberry, snowberry, and rose hips that cling through winter, "
                    "with a buffaloberry to feed the soil.",
    },
    "Continuous Bloom Pollinator Strip": {
        "problem": "The Wildlife Forage calendar keeps flagging nectar gaps — weeks "
                   "in the season when nothing in the yard is flowering.",
        "context": "Any sunny strip dropped in specifically to close bloom gaps the "
                   "analysis shows across the Apr–Oct growing season.",
        "forces": "Pollinators need uninterrupted nectar; one missing month can break "
                  "the chain. The fix is deliberate bloom hand-off, not more of the "
                  "same flower.",
        "solution": "Therefore: line up bloom from first to last frost — pussy willow "
                    "and crocus in early spring, golden bean and strawberry into June, "
                    "bergamot in July, blazingstar in late summer, goldenrod and aster "
                    "to frost.",
    },
    "Late-Season Pollinator Refuge": {
        "problem": "Late summer and fall are when nectar runs out, right when migrating "
                   "monarchs and queen bumble bees need fuel the most.",
        "context": "A sunny area added to cover the Aug–Oct gap the forage calendar "
                   "most often shows red.",
        "forces": "Most gardens peak in midsummer and fade; the insects that overwinter "
                  "or migrate depend on the last flowers standing, many of which are "
                  "also keystones.",
        "solution": "Therefore: mass late bloomers — goldenrods, asters, blazingstars, "
                    "Maximilian sunflower, fireweed, and a late milkweed — for a fall "
                    "refuelling station that doubles your keystone count.",
    },
    # ── Habitat-structure & ecoregion communities ────────────────────────────
    "Aspen Parkland Edge": {
        "problem": "Single-layer plantings (just shrubs, or just flowers) leave most "
                   "wildlife niches empty.",
        "context": "A yard edge or open bed with room for a small tree, mirroring the "
                   "layered structure of central Alberta's richest ecoregion.",
        "forces": "Birds and insects nest and feed at every height; a design that fills "
                  "canopy, understory, shrub, herb, and ground layers offers far more "
                  "homes than any single layer.",
        "solution": "Therefore: stack every canonical layer — aspen overstory, "
                    "chokecherry understory, saskatoon shrub layer, goldenrod and aster "
                    "herbs, and a strawberry groundcover.",
    },
    "Mixedgrass Prairie Patch": {
        "problem": "Dry, open, sun-baked ground defeats most ornamental plantings and "
                   "bakes lawns brown by July.",
        "context": "A hot, dry, low-water site in southern or central Alberta where "
                   "you want resilient native cover and habitat.",
        "forces": "These sites punish thirsty plants; native bunchgrasses and prairie "
                  "forbs thrive on neglect, hold soil, and give ground-nesting bees "
                  "and birds the stems and bare earth they need.",
        "solution": "Therefore: weave native bunchgrasses (fescue, June grass, little "
                    "bluestem) through succession-blooming forbs from crocus to "
                    "blazingstar, with a clover for nitrogen and yarrow to bind it.",
    },
    "Boreal Shade Community": {
        "problem": "The ground beneath existing spruce, poplar, or birch is dry, "
                   "shaded, acidic, and usually written off as a dead zone.",
        "context": "Under or north of an established conifer or aspen canopy, modelled "
                   "on the natural boreal forest floor.",
        "forces": "Sun-loving plants fail in deep shade and acid soil, but a specific "
                  "boreal-floor community evolved for exactly these conditions and "
                  "knits together where little else will grow.",
        "solution": "Therefore: plant the classic boreal companions — sarsaparilla, "
                    "bunchberry, twinflower, and a shade-tolerant highbush cranberry — "
                    "that naturally grow together in Alberta woodlands.",
    },
    "Edible Boreal Understory": {
        "problem": "A shady forest-floor planting can do more than look natural — it "
                   "can also feed you.",
        "context": "The same boreal understory, on a site where edible and useful "
                   "plants are preferred.",
        "forces": "Shade limits the edible palette, but several boreal natives "
                  "(cranberries, Labrador tea, mint) are both shade-tolerant and "
                  "useful.",
        "solution": "Therefore: keep the spruce frame and swap in low-bush and bog "
                    "cranberry, Labrador tea, and moisture-loving mint for an edible, "
                    "aromatic shade carpet.",
    },
    "Boreal Woodland Floor": {
        "problem": "Shaded northern yards are the hardest niche to plant for bird "
                   "food, so they usually offer none.",
        "context": "A north-facing site or established conifer/aspen understory where "
                   "you still want to feed wildlife.",
        "forces": "Few fruiting plants tolerate deep shade; the boreal-floor mosaic is "
                  "one of the only communities that delivers berries and groundcover "
                  "in low light.",
        "solution": "Therefore: combine a bunchberry–twinflower–lily-of-the-valley "
                    "mosaic with hazelnut, bog cranberry, and strawberry so even the "
                    "shadiest corner feeds birds.",
    },
    "Riparian Willow Thicket": {
        "problem": "Wet, low, or streamside ground waterlogs ordinary plants and is "
                   "often left as a soggy, weedy gap.",
        "context": "A pond edge, swale, ditch, or any spot that stays damp, where you "
                   "want a thicket that thrives on wet feet.",
        "forces": "Most plants drown in saturated soil, but the willow guild loves it — "
                  "and willows happen to be keystone, host, and bird-food plants all "
                  "at once, so a wet problem becomes a habitat jackpot.",
        "solution": "Therefore: build a willow thicket on the wet edge — pussy and "
                    "sandbar willow with red osier dogwood and highbush cranberry, "
                    "underplanted with milkweed and fireweed for summer bloom.",
    },
    # ── Lawn-to-habitat starter communities ──────────────────────────────────
    "Native Berry Hedge": {
        "problem": "A bare property line or fence does nothing but mark a boundary, "
                   "while a living hedge could screen, shelter, and feed you.",
        "context": "A property edge or windbreak line where you want a productive, "
                   "layered living fence instead of cedar boards or chain-link.",
        "forces": "A hedge must screen and shelter, but a single-species row is "
                  "vulnerable and dull; mixing berry shrubs, a nitrogen fixer, and "
                  "thorny security builds a resilient, productive barrier.",
        "solution": "Therefore: plant a layered line — saskatoon and chokecherry for "
                    "the tall backbone, haskap in the mid layer, thorny rose and "
                    "raspberry at the base, and lupine to feed the soil between.",
    },
    "Wildlife Corridor Hedge": {
        "problem": "When a hedge's job is habitat connection rather than the kitchen, "
                   "its species should be chosen for birds first.",
        "context": "A boundary planting meant to link your yard to nearby green space "
                   "as a wildlife corridor.",
        "forces": "Bird and pollinator value rises with winter-persistent fruit and "
                  "dense cover; choosing for wildlife slightly lowers the human "
                  "harvest but raises the habitat payoff.",
        "solution": "Therefore: build the hedge from highbush cranberry, elderberry, "
                    "snowberry, and buffaloberry for fall-and-winter bird food, with a "
                    "silver-leaved wolf willow windbreak at the base.",
    },
    "Boulevard Pollinator Strip": {
        "problem": "A sun-baked boulevard or hellstrip is the hardest scrap of a "
                   "yard: salt, drought, and mowing leave it a sterile green "
                   "rectangle that feeds nothing.",
        "context": "A narrow curb strip, hellstrip, or boulevard in full sun where "
                   "plants must stay low for sightlines and shrug off salt and "
                   "drought.",
        "forces": "The strip has to look kept and keep sightlines open, yet survive "
                  "with no watering and feed pollinators — which rules out tall or "
                  "thirsty plants and rules in a tough, low native matrix.",
        "solution": "Therefore: lay a fine warm-season grass matrix (blue grama) and "
                    "scatter drought-tough forbs through it — blanketflower, "
                    "black-eyed Susan, and bergamot for summer, prairie clover for "
                    "nitrogen, prairie goldenrod for fall nectar. Mow once in spring; "
                    "never water once established.",
    },
    "Backyard Meadow Patch": {
        "problem": "A back corner of mown lawn is weekly work for zero habitat and a "
                   "monoculture of grass.",
        "context": "A sunny residential-scale corner you're ready to convert from turf "
                   "to a low-care native meadow.",
        "forces": "A meadow must read as intentional, not neglected; a grass matrix "
                  "with scattered forbs gives structure and bloom while cutting mowing "
                  "to once a year.",
        "solution": "Therefore: set a fine fescue and little-bluestem matrix and weave "
                    "in coneflower, blanketflower, and bergamot for layered bloom, a "
                    "lupine for nitrogen, and a strawberry to knit the ground.",
    },
    "Hedgerow Shelterbelt": {
        "problem": "An exposed property edge offers no shelter from prairie wind and "
                   "no habitat — just a line on a map.",
        "context": "A windward property edge or acreage boundary where you want a "
                   "fast, layered native windbreak that also feeds birds.",
        "forces": "A shelterbelt needs quick height and density to break wind, but "
                  "should earn its space with fruit and habitat rather than being a "
                  "single-species screen.",
        "solution": "Therefore: plant a row that climbs in layers — aspen for fast "
                    "height, chokecherry and saskatoon for fruit, buffaloberry to fix "
                    "nitrogen and feed waxwings, cranberry for winter fruit, and "
                    "snowberry filling the low layer.",
    },
    "Native Edible Garden": {
        "problem": "A vegetable patch is annual work and bare soil; a native food "
                   "garden could feed you and the wildlife with perennials that "
                   "return on their own.",
        "context": "A sunny bed for gardeners who want a staggered, low-input harvest "
                   "of native fruits and nuts.",
        "forces": "Harvest windows are short and species-specific; spreading them "
                  "across the season keeps fresh food coming, and most native fruit "
                  "doubles as bird food and habitat.",
        "solution": "Therefore: stagger the harvest from June to October — strawberry, "
                    "saskatoon, raspberry, pin and chokecherry, highbush cranberry, "
                    "and hazelnut — most of which feed birds too.",
    },
}


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
        "name": "Aromatic Herb Circle",
        "description": "A circle of seven hardy native perennials with strong aromatics and "
                       "pollinator value. Wild bergamot anchors the centre as a magnet for native "
                       "bumble bees; yarrow, wild mint, giant hyssop, valerian, and self-heal fill "
                       "the surround. All species are Zone 3 proven in Alberta gardens and tolerate "
                       "dry summers once established.",
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
                # Renamed from "First Nations Medicine Wheel" (V1.37).
                # The original name and description framed the design as
                # Indigenous traditional knowledge, which it isn't ours
                # to claim or distribute. The plant list is unchanged —
                # these are real native prairie species hardy in Zone 3 —
                # but the framing is now strictly horticultural.
                "name": "Native Prairie Aromatics",
                "description": "Seven Alberta-native prairie perennials chosen for strong aromatics, "
                               "pollinator support, and Zone 3 cold tolerance: wild bergamot, "
                               "sweetgrass, prairie sage, rat root, wild licorice, seneca snakeroot, "
                               "and yarrow. The species mix favours drought-tolerant plants once "
                               "established and provides a long bloom window from June into "
                               "September.",
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
    # ── Lawn-to-habitat starter communities (P1) ──────────────────────────────
    # Ready-to-place AB starters for the three most common conversions; named to
    # match how people describe the project ("a boulevard strip", "a meadow
    # patch", "a shelterbelt"). All members are confirmed native catalogue rows.
    {
        "name": "Boulevard Pollinator Strip",
        "description": "A tough, low-growing nectar strip for hellstrips and "
                       "boulevards — sun-baked, salt- and drought-tolerant natives "
                       "kept short for sightlines. Blue grama forms a fine "
                       "warm-season matrix; blanketflower, black-eyed Susan and wild "
                       "bergamot carry summer bloom; purple prairie clover fixes "
                       "nitrogen and prairie goldenrod extends nectar into fall.",
        "members": [
            ("Wild Bergamot",          "pollinator",      0,    0),
            ("Blanketflower",          "pollinator",      1.0,  0.6),
            ("Black-eyed Susan",       "pollinator",     -1.0,  0.6),
            ("Purple Prairie Clover",  "nitrogen_fixer",  0.0, -0.8),
            ("Blue Grama Grass",       "groundcover",     1.2, -0.6),
            ("Prairie Goldenrod",      "pollinator",     -1.2, -0.5),
        ],
    },
    {
        "name": "Backyard Meadow Patch",
        "description": "A residential-scale sunny meadow for a back corner. Little "
                       "bluestem and sheep fescue form the grass matrix; prairie "
                       "coneflower, blanketflower and wild bergamot bring layered "
                       "bloom; silvery lupine fixes nitrogen and wild strawberry "
                       "knits the ground layer.",
        "members": [
            ("Little Bluestem",    "matrix_grass",    0,    0),
            ("Sheep Fescue",       "matrix_grass",    1.2,  0.8),
            ("Prairie Coneflower", "pollinator",     -1.0,  0.8),
            ("Blanketflower",      "pollinator",      1.0, -0.8),
            ("Silvery Lupine",     "nitrogen_fixer", -1.1, -0.7),
            ("Wild Strawberry",    "groundcover",     0.2,  1.3),
        ],
    },
    {
        "name": "Hedgerow Shelterbelt",
        "description": "A layered native windbreak and bird hedge for a property "
                       "edge. Trembling aspen gives quick height and shelter; "
                       "chokecherry and saskatoon supply fruit; buffaloberry fixes "
                       "nitrogen and feeds waxwings; highbush cranberry holds winter "
                       "fruit; snowberry fills the low layer. Plant in a row along "
                       "the boundary you want to screen.",
        "members": [
            ("Trembling Aspen",     "overstory",       0,    0),
            ("Chokecherry",         "shrub_layer",     2.5,  0.4),
            ("Saskatoon Berry",     "shrub_layer",    -2.5,  0.4),
            ("Canada Buffaloberry", "nitrogen_fixer",  4.5, -0.4),
            ("Highbush Cranberry",  "shrub_layer",    -4.5, -0.4),
            ("Common Snowberry",    "groundcover",     0.0, -1.2),
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

    def _seed_one(poly_def, parent_id=None):
        center_name = poly_def["members"][0][0]
        center_plant = _get_plant_by_name(center_name)
        center_id = center_plant["id"] if center_plant else None
        # Authored Alexander pattern text lives in _PATTERN_TEXT keyed by name
        # (kept separate from the spatial member layout above); an inline key on
        # the community dict, if present, wins.
        text = _PATTERN_TEXT.get(poly_def["name"], {})
        poly_id = create_polyculture(
            poly_def["name"], poly_def["description"], center_id,
            parent_id=parent_id,
            problem=poly_def.get("problem") or text.get("problem"),
            context=poly_def.get("context") or text.get("context"),
            forces=poly_def.get("forces") or text.get("forces"),
            solution=poly_def.get("solution") or text.get("solution"),
        )
        for common_name, role, ox, oy in poly_def["members"]:
            plant = _get_plant_by_name(common_name)
            if plant:
                add_polyculture_member(poly_id, plant["id"], role, ox, oy)
        return poly_id

    for polyculture_def in EXAMPLE_POLYCULTURES:
        polyculture_id = _seed_one(polyculture_def)
        # Create variations as child polycultures
        for var_def in polyculture_def.get("variations", []):
            _seed_one(var_def, parent_id=polyculture_id)

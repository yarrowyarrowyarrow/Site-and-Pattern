"""Polyculture Recipe persistence.

A Recipe is a ratio-only mix of plants (no spatial layout). It is the
DB-backed home for what used to live in QSettings as
``polyculture_recipes``. Recipes drive ratio assignment for row/grid/
circle placements and can be "populated" into a Plant Community's
circle by the builder.

A Recipe row carries name + description + distribution strategy; its
members carry plant_id + weight + an optional per-mix marker_color
override. This mirrors the in-memory dict shape that the placement code
already consumes (``PlantPanel.active_polyculture()`` returned the same
shape today), so callers can switch over without restructuring.
"""

import json
from typing import Optional

from .plants import get_connection


def _row_to_dict(row) -> dict:
    return dict(row) if row is not None else {}


def _member_row_to_dict(row) -> dict:
    d = dict(row)
    # Hydrate the cached plant fields so callers don't have to
    # re-fetch each plant individually.
    return d


def get_all_recipes() -> list[dict]:
    """Return all saved recipes (without their members)."""
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM polyculture_recipes ORDER BY name"
        ).fetchall()
        return [_row_to_dict(r) for r in rows]
    finally:
        conn.close()


def get_recipe_by_id(recipe_id: int) -> Optional[dict]:
    """Return one recipe with its members hydrated.

    Each member dict carries ``id`` (member-row id), ``recipe_id``,
    ``plant_id``, ``weight``, ``marker_color``, ``sort_order``, plus
    cached plant fields ``common_name``, ``plant_type``,
    ``spacing_meters`` so callers can render the row without a
    second DB hit.
    """
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM polyculture_recipes WHERE id = ?",
            (recipe_id,),
        ).fetchone()
        if not row:
            return None
        recipe = dict(row)
        members = conn.execute(
            "SELECT rm.*, p.common_name, p.plant_type, p.spacing_meters, "
            "       p.marker_color AS plant_marker_color "
            "FROM polyculture_recipe_members rm "
            "JOIN plants p ON rm.plant_id = p.id "
            "WHERE rm.recipe_id = ? "
            "ORDER BY rm.sort_order, rm.id",
            (recipe_id,),
        ).fetchall()
        recipe["members"] = [_member_row_to_dict(m) for m in members]
        return recipe
    finally:
        conn.close()


def get_recipe_by_name(name: str) -> Optional[dict]:
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT id FROM polyculture_recipes WHERE name = ?", (name,)
        ).fetchone()
    finally:
        conn.close()
    return get_recipe_by_id(row["id"]) if row else None


def create_recipe(name: str, description: str = "",
                  strategy: str = "even_split",
                  spacing_strategy: str = "max") -> int:
    conn = get_connection()
    try:
        cur = conn.execute(
            "INSERT INTO polyculture_recipes "
            "(name, description, strategy, spacing_strategy) "
            "VALUES (?, ?, ?, ?)",
            (name, description, strategy, spacing_strategy),
        )
        recipe_id = cur.lastrowid
        conn.commit()
        return recipe_id
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def update_recipe(recipe_id: int, *, name=None, description=None,
                  strategy=None, spacing_strategy=None) -> None:
    fields = []
    values = []
    if name is not None:
        fields.append("name = ?")
        values.append(name)
    if description is not None:
        fields.append("description = ?")
        values.append(description)
    if strategy is not None:
        fields.append("strategy = ?")
        values.append(strategy)
    if spacing_strategy is not None:
        fields.append("spacing_strategy = ?")
        values.append(spacing_strategy)
    if not fields:
        return
    fields.append("modified = datetime('now')")
    values.append(recipe_id)
    conn = get_connection()
    try:
        conn.execute(
            f"UPDATE polyculture_recipes SET {', '.join(fields)} WHERE id = ?",
            values,
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def replace_recipe_members(recipe_id: int, members: list[dict]) -> None:
    """Atomically swap the member set of a recipe.

    Each member dict needs ``plant_id`` and ``weight`` (default 1).
    Optional: ``marker_color`` (per-mix override), ``sort_order``.
    """
    conn = get_connection()
    try:
        conn.execute(
            "DELETE FROM polyculture_recipe_members WHERE recipe_id = ?",
            (recipe_id,),
        )
        for i, m in enumerate(members or []):
            plant_id = m.get("plant_id") or m.get("id")
            if plant_id is None:
                continue
            weight = int(m.get("weight") or m.get("_weight") or 1)
            if weight < 1:
                weight = 1
            sort_order = int(m.get("sort_order", i))
            marker_color = m.get("marker_color") or m.get("color") or None
            conn.execute(
                "INSERT INTO polyculture_recipe_members "
                "(recipe_id, plant_id, weight, marker_color, sort_order) "
                "VALUES (?, ?, ?, ?, ?)",
                (recipe_id, plant_id, weight, marker_color, sort_order),
            )
        conn.execute(
            "UPDATE polyculture_recipes SET modified = datetime('now') WHERE id = ?",
            (recipe_id,),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def delete_recipe(recipe_id: int) -> None:
    conn = get_connection()
    try:
        conn.execute(
            "DELETE FROM polyculture_recipe_members WHERE recipe_id = ?",
            (recipe_id,),
        )
        conn.execute(
            "DELETE FROM polyculture_recipes WHERE id = ?", (recipe_id,)
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def duplicate_recipe(recipe_id: int) -> Optional[int]:
    rec = get_recipe_by_id(recipe_id)
    if not rec:
        return None
    base_name = f"{rec['name']} (copy)"
    new_name = base_name
    # Avoid UNIQUE-constraint collisions by suffixing if needed.
    suffix = 2
    while get_recipe_by_name(new_name) is not None:
        new_name = f"{base_name} {suffix}"
        suffix += 1
    new_id = create_recipe(
        new_name, rec.get("description") or "",
        rec.get("strategy") or "even_split",
        rec.get("spacing_strategy") or "max",
    )
    replace_recipe_members(new_id, rec.get("members") or [])
    return new_id


def recipe_to_species_list(recipe: dict) -> dict:
    """Return the recipe in the dict shape PlantPanel.active_polyculture()
    used to produce, so existing placement code (in app.py) can consume
    it unchanged.
    """
    from src.polyculture import resolve_spacing
    species = []
    for m in recipe.get("members") or []:
        species.append({
            "id": int(m["plant_id"]),
            "common_name": m.get("common_name") or "",
            "spacing_m": float(m.get("spacing_meters") or 1.0),
            "plant_type": m.get("plant_type") or "herb",
            "color": m.get("marker_color") or m.get("plant_marker_color") or "",
            "weight": float(m.get("weight") or 1),
        })
    eff = resolve_spacing(species, recipe.get("spacing_strategy") or "max")
    return {
        "species": species,
        "strategy": recipe.get("strategy") or "even_split",
        "spacing_strategy": recipe.get("spacing_strategy") or "max",
        "effective_spacing_m": eff,
        "name": recipe.get("name") or "",
    }


def migrate_qsettings_recipes() -> int:
    """One-time import of recipes that used to live in ~/.permadesign_config.json.

    Returns the number of recipes imported. Idempotent: once the marker
    flag ``polyculture_recipes_migrated`` is set in the config file we
    skip further imports.
    """
    try:
        from src.settings import load_config, save_config
    except Exception:
        return 0
    cfg = load_config()
    if cfg.get("polyculture_recipes_migrated"):
        return 0
    legacy = cfg.get("polyculture_recipes") or []
    if not isinstance(legacy, list):
        cfg["polyculture_recipes_migrated"] = True
        save_config(cfg)
        return 0

    imported = 0
    for r in legacy:
        if not isinstance(r, dict):
            continue
        name = (r.get("name") or "").strip()
        if not name:
            continue
        if get_recipe_by_name(name) is not None:
            continue
        species = r.get("species") or []
        if not species:
            continue
        try:
            new_id = create_recipe(name, r.get("description") or "")
        except Exception:
            continue
        members = []
        for s in species:
            pid = s.get("id")
            if not pid:
                continue
            members.append({
                "plant_id": int(pid),
                "weight": int(s.get("weight") or 1),
                "marker_color": s.get("color") or None,
            })
        if members:
            replace_recipe_members(new_id, members)
            imported += 1
    cfg["polyculture_recipes_migrated"] = True
    save_config(cfg)
    return imported

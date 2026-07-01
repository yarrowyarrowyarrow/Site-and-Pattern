"""
src/ecological_role.py — "why it matters" ecological-role badges for a plant (F1).

Design principle P6 (conventional value metrics miss ecological value — make the
ecological role legible where the user already looks) and P10 (design for
relationships, not objects) — see docs/DESIGN_PHILOSOPHY.md.

Qt-free so the plant-browser delegate, the scripting layer and the tests share
one definition of a plant's ecological "why". It reuses the same use-tag
membership the Habitat Value Score keys off (keystone / host / bird-food /
pollinator / nitrogen-fixer, from the ``permaculture_uses`` blob synthesised by
``db.plants``) and the plant↔fauna junction (``fauna.fauna_for_plant``) for the
relationship-backed badges — how many caterpillars it hosts, and whether it feeds
a specialist that depends on it.

The badges are short, highest-value first, so they read as a one-line answer to
"why does this plant matter?" at the point the user is already looking — the
expanded row in the plant browser — rather than only in the Habitat tab.
"""

from __future__ import annotations


def _use_tags(plant) -> set[str]:
    """The plant's ``permaculture_uses`` comma-blob as a set of tag keys."""
    raw = (plant or {}).get("permaculture_uses") or ""
    return {t.strip() for t in raw.split(",") if t.strip()}


def ecological_role_summary(plant, *, fauna_rows=None) -> list[str]:
    """Return short ecological-role badge strings for a plant, highest-value first.

    Badges, in priority order:
      * ``"Keystone"``              — the ``keystone_species`` tag (Tallamy's
                                      high-value genera that anchor the food web).
      * ``"Hosts N caterpillars"``  — distinct larval-host lepidoptera in the
                                      plant↔fauna junction; falls back to
                                      ``"Larval host"`` when only the tag is known.
      * ``"Specialist host"``       — the plant feeds at least one specialist
                                      species that depends on it (e.g. monarch↔milkweed).
      * ``"Bird food"``             — the ``bird_food`` tag or a documented bird
                                      relationship.
      * ``"Pollinator plant"``      — the ``pollinator`` tag or a nectar/pollen
                                      relationship.
      * ``"Nitrogen fixer"``        — the ``nitrogen_fixer`` tag.

    ``fauna_rows`` is the ``fauna.fauna_for_plant(plant_id)`` result, injectable
    for tests; when ``None`` and the plant carries an ``id`` it is fetched lazily
    (any DB error degrades to tag-only badges). A plant with no recognised role
    returns ``[]`` — the caller renders nothing.
    """
    tags = _use_tags(plant)

    if fauna_rows is None:
        pid = (plant or {}).get("id")
        fauna_rows = []
        if pid is not None:
            try:
                from src.db.fauna import fauna_for_plant
                fauna_rows = fauna_for_plant(int(pid))
            except Exception:  # noqa: BLE001 — badges are a read nicety, never fatal
                fauna_rows = []

    # Relationship-backed signals from the junction.
    caterpillars = {
        r.get("common_name") for r in fauna_rows
        if r.get("relationship") == "larval_host"
        and r.get("taxon") == "lepidoptera"
        and r.get("common_name")
    }
    has_specialist = any(r.get("specificity") == "specialist" for r in fauna_rows)
    has_bird_rel = any(r.get("taxon") == "bird" for r in fauna_rows)
    has_pollinator_rel = any(
        r.get("relationship") in ("nectar", "pollen") for r in fauna_rows
    )

    badges: list[str] = []
    if "keystone_species" in tags:
        badges.append("Keystone")

    n_cat = len(caterpillars)
    if n_cat == 1:
        badges.append("Hosts 1 caterpillar")
    elif n_cat > 1:
        badges.append(f"Hosts {n_cat} caterpillars")
    elif "host_plant" in tags:
        badges.append("Larval host")

    if has_specialist:
        badges.append("Specialist host")
    if "bird_food" in tags or has_bird_rel:
        badges.append("Bird food")
    if "pollinator" in tags or has_pollinator_rel:
        badges.append("Pollinator plant")
    if "nitrogen_fixer" in tags:
        badges.append("Nitrogen fixer")

    return badges

"""
plant_filters.py — the one filter vocabulary every plant picker reads (F192,
V3.00).

Design principle P9 — see docs/DESIGN_PHILOSOPHY.md.

Until V3.00 the catalogue had three pickers and three vocabularies. Browse
(``plant_panel.py``) wired nine dropdowns and four toggles by hand; the Plant
Directory looped two tables of its own, seven dropdowns and thirteen toggles;
the community builder had a checkbox and four single-choice dropdowns that
filtered ``get_all_plants()`` in Python. Each lacked filters another had, and
five of the Directory's toggles were Browse's "Use" values under other names:
``keystone_only``, ``host_plant_only``, ``bird_food_only``, ``pollinator_only``
and ``nfixer_only`` each run ``search_plants``' ``_use_filter`` on exactly the
tag ``perm_use`` does.

This module is the union less those five, held once and Qt-free:

  * :data:`FACETS` — nine multi-select dimensions, each saying how the values
    you tick combine (``any`` or ``all``), so a picker can say so in words.
  * :data:`QUALITIES` — nine on/off restrictions.
  * :data:`ORDERS` — how a result can be ordered.

and what every picker needs from them: criteria to ``search_plants`` keyword
arguments (:func:`criteria_to_kwargs`), the order (:func:`order_plants`) and a
short account of what is switched on (:func:`summary`).

**"Recorded near this site" ranks; it never filters.** It reads
:func:`src.site_fit.locality` the way the design generator does: species
recorded near the pin first, then the next ring out, then everything else level,
because records follow collectors and an empty grid square is unsurveyed as
often as it is unoccupied. Plants that need standing water
(:func:`src.zoning.needs_standing_water`, 23 species) go last rather than away:
results had been ordered by plant type, and "aquatic" sorts first, so a front
yard's list opened on Arrowhead, Water-plantain, Buckbean and Cattail.
"""

from __future__ import annotations

from typing import Callable, NamedTuple, Optional

from src.flower_colour import COLOUR_LABELS as _COLOUR_LABELS
from src.plant_facets import _MONTH_LABELS, _TYPE_LABELS


class Facet(NamedTuple):
    """One multi-select dimension. ``values`` is ``{key: label}``, or ``None``
    for the ecoregion tree, which a picker builds with
    :func:`src.filter_widgets.build_ecoregion_tree`."""
    key: str
    label: str
    param: str
    values: Optional[dict]
    combine: str            # "any": a plant needs one ticked value; "all": every one
    placeholder: str
    tip: str


class Quality(NamedTuple):
    """One on/off restriction: when on, ``param=value`` goes to the search."""
    key: str
    label: str
    param: str
    tip: str
    value: object = True


SUN_LABELS: dict = {
    "full_sun": "Full Sun", "partial_shade": "Partial Shade",
    "full_shade": "Full Shade",
}
WATER_LABELS: dict = {"low": "Low", "medium": "Medium", "high": "High"}
#: The use tags, as the Role facet and the species page both name them.
ROLE_LABELS: dict = {
    "keystone_species": "Keystone Species", "host_plant": "Larval Host",
    "pollinator": "Pollinator Support", "bird_food": "Bird Food",
    "nesting_material": "Nesting Material",
    "wildlife_habitat": "Wildlife Habitat",
    "nitrogen_fixer": "Nitrogen Fixer", "soil_builder": "Soil Builder",
    "early_successional": "Early Successional",
    "canopy_layer": "Canopy Layer", "windbreak": "Windbreak", "hedge": "Hedge",
    "groundcover": "Groundcover", "erosion_control": "Erosion Control",
    "riparian_filter": "Riparian Filter", "ornamental": "Ornamental",
    "aquatic": "Aquatic", "medicinal": "Medicinal",
}
AVAILABILITY_LABELS: dict = {
    "big_box": "Big-box store", "garden_centre": "Garden centre",
    "native_specialist": "Native nursery",
    "seed_or_plug": "Seed / plug only", "rare": "Rare / hard to find",
}

FACETS: tuple = (
    Facet("type", "Type", "plant_type", dict(_TYPE_LABELS), "any", "Any type",
          "Plants of any of the types you tick. The colour beside each is the "
          "dot the list and the map use for it."),
    Facet("sun", "Sun", "sun_req", SUN_LABELS, "any", "Any sun",
          "Plants that grow in any of the light you tick."),
    Facet("water", "Water", "water_needs", WATER_LABELS, "any", "Any water",
          "Plants suited to any of the water levels you tick."),
    Facet("use", "Role", "perm_use", ROLE_LABELS, "all", "Any role",
          "Only plants listed for every role you tick."),
    Facet("availability", "Where to buy", "availability_in",
          AVAILABILITY_LABELS, "any", "Anywhere to buy",
          "Only plants sold by one of the kinds of seller you tick."),
    Facet("ecoregion", "Restoring toward", "ecoregion", None, "any",
          "Restoring toward…",
          "Plants recorded in any of the regions you tick. Ticking a system "
          "includes everything inside it. A pin you drop on the map ticks its "
          "own region here."),
    Facet("bloom_months", "Blooms in", "bloom_months", dict(_MONTH_LABELS),
          "any", "Blooms in…",
          "Plants flowering in any of the months you tick: the direct way to "
          "fill a gap in nectar. A plant with no recorded bloom window is left "
          "out rather than guessed at."),
    Facet("fruit_months", "Fruits in", "fruit_months", dict(_MONTH_LABELS),
          "any", "Fruits in…",
          "Plants fruiting in any of the months you tick, for bird food or a "
          "harvest across the season."),
    Facet("colour", "Flower colour", "flower_colours", dict(_COLOUR_LABELS),
          "any", "Any flower colour",
          "Plants flowering in any of the colours you tick. Grasses, sedges "
          "and rushes are a group of their own: they are wind-pollinated, so "
          "what you see is a seed head, not a bloom."),
)

QUALITIES: tuple = (
    # Read from the province list VASCAN supplies (V2.80), not from the
    # native_to_alberta flag: five species still carry the seed's "1?" there
    # (False Box, Flat-topped White Aster, Round-leaved Alumroot, Stiff
    # Sunflower, Tall Anemone), which the flag's filter dropped although VASCAN
    # records every one in Alberta and the list's AB badge said so.
    Quality("native_only", "Native", "native_province",
            "Native to Alberta, as VASCAN records it.", "AB"),
    Quality("perennial_only", "Perennial", "perennial_only",
            "Comes back every year."),
    Quality("supports_specialist", "Feeds a specialist", "supports_specialist",
            "Supports at least one animal that has nowhere else to go."),
    Quality("edible_only", "Edible", "edible_only",
            "Has parts recorded as edible for people."),
    Quality("pet_safe_only", "Pet safe", "pet_safe_only",
            "No recorded toxicity to pets. Silence is not a guarantee: an "
            "unassessed plant passes this filter."),
    Quality("kid_safe_only", "Child safe", "kid_safe_only",
            "No recorded toxicity to people and no thorns. Same caveat."),
    Quality("well_behaved_only", "Well behaved", "well_behaved_only",
            "Does not spread aggressively."),
    Quality("common_only", "Easy to find", "common_only",
            "Stocked somewhere other than a specialist grower."),
    Quality("has_image_only", "Has a photo", "has_image_only",
            "Only species this catalogue can show you."),
)

#: ``(key, label, tooltip)``. "suits" is offered only where there is a site.
ORDERS: tuple = (
    # Named for what it knows. The review asked for "suits this site", but
    # nothing here knows the yard's sun or soil: it knows where a species has
    # been recorded and the zone, and a salt-flat grass recorded near
    # Edmonton is "near this site" without suiting a front yard (P9).
    ("suits", "Recorded near this site",
     "Species recorded near your pin first, then those hardy in your zone. "
     "Plants that need standing water come last. Nothing is hidden: records "
     "follow collectors, so a plant with none nearby may still grow there, "
     "and a record nearby says nothing about your yard's sun or soil."),
    ("name", "Name", "A to Z by common name."),
    ("type", "Type", "Trees, shrubs and so on, then by name."),
    ("wildlife", "Animals supported",
     "Most documented animals first. Undocumented is not unused."),
    ("height", "Height", "Tallest at maturity first."),
)


def facet(key: str) -> Optional[Facet]:
    return next((f for f in FACETS if f.key == key), None)


def facet_params() -> set:
    """Every ``search_plants`` parameter this vocabulary drives. A test checks
    them against the real signature: a typo here is a filter that silently
    does nothing."""
    return ({f.param for f in FACETS} | {q.param for q in QUALITIES}
            | {"query"})


# ── Criteria ─────────────────────────────────────────────────────────────────

def criteria_to_kwargs(criteria: Optional[dict]) -> dict:
    """Turn ``{facet_key: [values], quality_key: True, "query": "..."}`` into
    ``search_plants`` keyword arguments.

    Empty selections are dropped rather than passed as empty lists: "no
    restriction" and "match nothing" are one typo apart downstream.
    """
    criteria = criteria or {}
    kwargs: dict = {}
    query = (criteria.get("query") or "").strip()
    if query:
        kwargs["query"] = query
    for f in FACETS:
        chosen = criteria.get(f.key) or []
        if isinstance(chosen, str):
            chosen = [chosen]
        if not chosen:
            continue
        if f.param.endswith("_months"):
            # Month keys travel as strings (combo keys always do); the search
            # layer wants ints.
            kwargs[f.param] = [int(v) for v in chosen if str(v).isdigit()]
        elif f.key == "ecoregion":
            # Along the lineage both ways: a ticked ecozone matches plants
            # tagged with any region inside it, and a ticked region matches
            # plants only ever tagged at its ecozone (src/ecoregion_tree.py).
            from src.ecoregion_tree import expand_for_filter   # noqa: PLC0415
            kwargs[f.param] = expand_for_filter(list(chosen))
        else:
            kwargs[f.param] = list(chosen)
    for q in QUALITIES:
        if criteria.get(q.key):
            kwargs[q.param] = q.value
    return kwargs


def active(criteria: Optional[dict]) -> bool:
    """Whether any facet or quality is on (the search text aside)."""
    criteria = criteria or {}
    return (any(criteria.get(f.key) for f in FACETS)
            or any(criteria.get(q.key) for q in QUALITIES))


def summary(criteria: Optional[dict], *, most: int = 2) -> list:
    """What is switched on, one short phrase each, in the order the filters are
    drawn: ``["Restoring toward Aspen Parkland", "Type: Shrub or Tree",
    "Native"]``. The combine rule is in the words ("or" for any, "and" for
    all), which is the one thing a dropdown's face never says."""
    criteria = criteria or {}
    out = []
    for f in FACETS:
        chosen = criteria.get(f.key) or []
        if isinstance(chosen, str):
            chosen = [chosen]
        names = _value_names(f, list(chosen))
        if not names:
            continue
        shown = names[:most]
        joiner = " and " if f.combine == "all" else " or "
        text = (", ".join(shown[:-1]) + joiner + shown[-1]
                if len(shown) > 1 else shown[0])
        if len(names) > most:
            text = ", ".join(shown) + f" +{len(names) - most}"
        out.append(f"{f.label} {text}" if f.key == "ecoregion"
                   else f"{f.label}: {text}")
    out += [q.label for q in QUALITIES if criteria.get(q.key)]
    return out


def _value_names(f: Facet, keys: list) -> list:
    if f.key == "ecoregion":
        return [_ecoregion_name(k) for k in _outermost(keys)]
    labels = f.values or {}
    return [labels.get(str(k), str(k)) for k in keys]


def _outermost(keys: list) -> list:
    """Ticking an ecozone ticks everything inside it; name the ecozone once."""
    try:
        from src.ecoregion_tree import ancestors_of             # noqa: PLC0415
    except Exception:                                           # noqa: BLE001
        return list(keys)
    chosen = set(keys)
    return [k for k in keys if not (ancestors_of(k) & chosen)]


def _ecoregion_name(key: str) -> str:
    try:
        from src.ecoregion import MOISTURE_NICHES                # noqa: PLC0415
        from src.ecoregion_tree import _index                     # noqa: PLC0415
        index = _index()
    except Exception:                                           # noqa: BLE001
        return key
    if key in index["zones"]:
        return index["zones"][key]
    if key in index["regions"]:
        return index["regions"][key][0]
    if key in index["subs"]:
        return index["subs"][key][0]
    for niche_key, name, _where in MOISTURE_NICHES:
        if niche_key == key:
            return name
    return key


# ── Order ────────────────────────────────────────────────────────────────────

def order_plants(rows, key: str = "name", *, site=None,
                 zone: Optional[float] = None,
                 wildlife_counts: Optional[dict] = None,
                 hint: Optional[Callable] = None) -> list:
    """Order a result set.

    ``site`` is ``(lat, lng)`` or ``None``; ``zone`` the site's hardiness zone.
    ``hint(row)``, when given, lifts the rows it is true for to the top whatever
    the order: the community builder's "matches the layer you chose".
    Unknown keys fall back to name rather than raising: a list drawn in the
    wrong order beats one that refuses to draw.
    """
    rows = list(rows or [])

    def name(r):
        return (r.get("common_name") or "").lower()

    if key == "suits":
        from src.site_fit import locality_rank                   # noqa: PLC0415
        from src.zoning import needs_standing_water              # noqa: PLC0415
        lat, lng = site if site else (None, None)

        def main_key(r):
            return (needs_standing_water(r),
                    -locality_rank(r.get("scientific_name") or "", lat, lng),
                    not hardy_at(r, zone), name(r))
    elif key == "type":
        def main_key(r):
            return ((r.get("plant_type") or "~"), name(r))
    elif key == "height":
        def main_key(r):
            return (-_number(r.get("mature_height_meters")), name(r))
    elif key == "wildlife":
        counts = (wildlife_counts if wildlife_counts is not None
                  else animals_per_plant())

        def main_key(r):
            return (-int(counts.get(r.get("id"), 0)), name(r))
    else:
        main_key = name

    if hint is None:
        return sorted(rows, key=main_key)
    return sorted(rows, key=lambda r: (not hint(r), main_key(r)))


def hardy_at(row: dict, zone) -> bool:
    """Whether a plant is recorded hardy at ``zone``. Unrecorded counts as
    hardy: absent is not estimated (src/confidence.py), and a missing zone must
    not push a plant down a list."""
    if zone is None:
        return True
    lowest = _number(row.get("hardiness_zone_min"), default=None)
    try:
        return lowest is None or lowest <= float(zone)
    except (TypeError, ValueError):
        return True


def _number(value, default=0.0):
    """A numeric field, tolerating the hedges the data carries ('4?')."""
    if value is None or value == "":
        return default
    try:
        return float(str(value).strip().rstrip("?"))
    except ValueError:
        return default


def animals_per_plant() -> dict:
    """``{plant_id: distinct animals documented}``, for the "Animals supported"
    order. Distinct animals, not relationship rows: Boreal Yarrow has 334 rows
    and 296 animals, because one bee can take nectar and pollen."""
    try:
        from src.db.plants import get_connection                 # noqa: PLC0415
        conn = get_connection()
    except Exception:                                           # noqa: BLE001
        return {}
    try:
        return {int(pid): int(n) for pid, n in conn.execute(
            "SELECT plant_id, COUNT(DISTINCT fauna_id) FROM plant_fauna "
            "GROUP BY plant_id")}
    except Exception:                                           # noqa: BLE001
        return {}
    finally:
        conn.close()

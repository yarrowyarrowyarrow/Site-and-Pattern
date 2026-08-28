"""
plant_directory.py — the catalogue as a reference work (F90, V2.41).

Design principle P5 — see docs/DESIGN_PHILOSOPHY.md.

User feedback: *"explore the plant directory (which we have not built yet but I
think would be an excellent feature of a native plant education app and we have
all the data)."*

That last clause is the whole argument. The catalogue holds 434 species with
~70 fields each, their documented animals, their sourced ranges, their twelve
month calendars — and until now the only way to see any of it was to open a
design and use the browser that sits beside the map. The browser is a *picker*:
its job is to get a plant onto the ground, and every affordance in it points
that way. A reference work has a different job, so it gets a different surface.

This module is the Qt-free half:

  * :data:`FACETS` / :data:`TOGGLES` — the filter vocabulary as data, so the
    window builds its strip from a table rather than from 200 lines of wiring,
    and so a test can assert every facet names a real ``search_plants``
    parameter.
  * :func:`search` — criteria in, species out.
  * :func:`species_entry` — one species page as a plain dict.
  * :func:`in_bloom_now` — what is flowering this week, for the start screen.

**Nothing here is new knowledge.** Every field it surfaces already existed;
what did not exist was a room to read them in. Where a fact is uncertain it is
carried with its evidence (P9) — a range seen three times is not the same claim
as one seen three hundred times, and :func:`species_entry` keeps the counts.

**P12:** this surfaces only what the data model already holds — horticultural
and permaculture use tags, edible parts, documented ecological relationships.
No ethnobotanical content is added and no field is relabelled to imply any.
"""

from __future__ import annotations

import datetime
from typing import Callable, Optional

from src.flower_colour import COLOUR_LABELS as _COLOUR_LABELS
from src.nativity import SOURCE_FIELD
# Re-exported: the start-screen trio moved out in V2.80 when this
# file hit its line ceiling. Callers import them from here.
from src.plant_directory_bloom import (  # noqa: F401
    bloom_line, catalogue_size, in_bloom_now)

# ── The filter vocabulary ────────────────────────────────────────────────────
#
# `search_plants` takes thirty parameters. The design-side browser wires
# fourteen. The other sixteen have worked the whole time with nothing to press:
# keystone, larval host, bird food, pollinator, nitrogen fixer, specialist
# support, pet/kid safety, spread habit, price, commonness, province, moisture
# and three fauna-keyed lookups. A reference work is exactly where they belong —
# "show me the keystone species that feed a specialist and are safe around a
# dog" is a research question, not a placement one.
#
# Held as data so the window is a loop, and so `tests/test_plant_directory.py`
# can check every `param` against the real signature.

#: ``(key, label, search_plants parameter, {value: label})`` — multi-select.
FACETS: tuple = (
    ("type", "Type", "plant_type", {
        "tree": "Tree", "shrub": "Shrub", "vine": "Vine",
        "wildflower": "Wildflower", "herb": "Herb / Foliage",
        "groundcover": "Groundcover", "grass": "Grass", "sedge": "Sedge",
        "rush": "Rush", "fern": "Fern", "aquatic": "Aquatic / Wetland",
    }),
    ("sun", "Sun", "sun_req", {
        "full_sun": "Full Sun", "partial_shade": "Partial Shade",
        "full_shade": "Full Shade",
    }),
    ("water", "Water", "water_needs", {
        "low": "Low", "medium": "Medium", "high": "High",
    }),
    ("use", "Role", "perm_use", {
        "keystone_species": "Keystone Species", "host_plant": "Larval Host",
        "pollinator": "Pollinator Support", "bird_food": "Bird Food",
        "nesting_material": "Nesting Material",
        "wildlife_habitat": "Wildlife Habitat",
        "nitrogen_fixer": "Nitrogen Fixer", "soil_builder": "Soil Builder",
        "early_successional": "Pioneer Species", "canopy_layer": "Canopy Layer",
        "windbreak": "Windbreak", "hedge": "Hedge",
        "groundcover": "Groundcover",
    }),
    ("availability", "Where to buy", "availability_in", {
        "big_box": "Big-box store", "garden_centre": "Garden centre",
        "native_specialist": "Native nursery",
        "seed_or_plug": "Seed / plug only", "rare": "Rare / hard to find",
    }),
    ("bloom_months", "Blooms in", "bloom_months", {
        str(m): name for m, name in enumerate(
            ("January", "February", "March", "April", "May", "June", "July",
             "August", "September", "October", "November", "December"), 1)
    }),
    # V2.47. `flower_color` has held a hex since schema v31 and nothing could
    # filter on it — the one axis a person uses when they are choosing a plant
    # because they want to look at it (P13). The vocabulary is imported rather
    # than restated so the desktop facet, the search layer and the static site's
    # colour pages cannot drift; see `src.flower_colour` for why the grasses get
    # a bucket of their own instead of being filed as yellow.
    ("colour", "Flower colour", "flower_colours", dict(_COLOUR_LABELS)),
)

#: ``(key, label, search_plants parameter, tooltip)`` — on/off chips.
TOGGLES: tuple = (
    ("native_only", "Native", "native_only",
     "Native to Alberta."),
    ("keystone_only", "Keystone", "keystone_only",
     "Tallamy's high-value genera — the plants that anchor a food web."),
    ("host_plant_only", "Larval host", "host_plant_only",
     "Feeds caterpillars, which is what feeds nestling birds."),
    ("supports_specialist", "Feeds a specialist", "supports_specialist",
     "Supports at least one animal that has nowhere else to go."),
    ("bird_food_only", "Bird food", "bird_food_only",
     "Documented seed or fruit food for birds."),
    ("pollinator_only", "Pollinator", "pollinator_only",
     "Documented nectar or pollen source."),
    ("nfixer_only", "Nitrogen fixer", "nfixer_only",
     "Feeds the soil rather than needing it fed."),
    ("edible_only", "Edible", "edible_only",
     "Has parts recorded as edible for people."),
    ("pet_safe_only", "Pet safe", "pet_safe_only",
     "No recorded toxicity to pets. Silence is not a guarantee — an "
     "unassessed plant passes this filter."),
    ("kid_safe_only", "Child safe", "kid_safe_only",
     "No recorded toxicity to people and no thorns. Same caveat."),
    ("well_behaved_only", "Well behaved", "well_behaved_only",
     "Does not spread aggressively."),
    ("common_only", "Easy to find", "common_only",
     "Stocked somewhere other than a specialist grower."),
    ("has_image_only", "Has a photo", "has_image_only",
     "Only species this catalogue can show you."),
)

#: How the list can be ordered. ``name`` is the default because a reference
#: work is something you look things up in.
SORT_KEYS: tuple = (
    ("name", "Name"),
    ("type", "Type"),
    ("height", "Mature height"),
    ("wildlife", "Animals supported"),
)


def facet_params() -> set:
    """Every ``search_plants`` parameter this module drives. The test that
    checks them against the real signature reads this."""
    return ({f[2] for f in FACETS} | {t[2] for t in TOGGLES}
            | {"query", "ecoregion"})


# ── Searching ────────────────────────────────────────────────────────────────

def criteria_to_kwargs(criteria: Optional[dict]) -> dict:
    """Turn ``{facet_key: [values], toggle_key: True, "query": "..."}`` into
    ``search_plants`` keyword arguments.

    Empty selections are dropped rather than passed as empty lists, because
    ``search_plants`` reads "no restriction" from an empty value and passing
    ``[]`` for a list parameter would otherwise read as "match nothing" to a
    future maintainer even though it currently does not.
    """
    criteria = criteria or {}
    kwargs: dict = {}

    query = (criteria.get("query") or "").strip()
    if query:
        kwargs["query"] = query
    region = criteria.get("ecoregion") or ""
    if region:
        kwargs["ecoregion"] = (",".join(region) if isinstance(region, list)
                               else region)

    for key, _label, param, _values in FACETS:
        chosen = criteria.get(key) or []
        if not chosen:
            continue
        if param.endswith("_months"):
            # Month keys travel as strings (CheckableComboBox keys always do);
            # the search layer wants ints.
            kwargs[param] = [int(v) for v in chosen if str(v).isdigit()]
        else:
            kwargs[param] = list(chosen)

    for key, _label, param, _tip in TOGGLES:
        if criteria.get(key):
            kwargs[param] = True
    return kwargs


def search(criteria: Optional[dict] = None, *,
           search_fn: Optional[Callable] = None,
           sort_key: str = "name") -> list[dict]:
    """The species matching ``criteria``, ordered by ``sort_key``.

    ``search_fn`` is injectable so the whole query path is testable without a
    database.
    """
    if search_fn is None:
        from src.db.plants import search_plants as search_fn  # noqa: PLC0415
    rows = search_fn(**criteria_to_kwargs(criteria))
    return sort_species(rows, sort_key)


def sort_species(rows: list, key: str = "name") -> list:
    """Order a result set. Unknown keys fall back to name rather than raising —
    a directory that refuses to draw because a sort key was misspelt is worse
    than one that draws in the wrong order."""
    rows = list(rows or [])
    if key == "type":
        return sorted(rows, key=lambda r: ((r.get("plant_type") or "~"),
                                           (r.get("common_name") or "")))
    if key == "height":
        return sorted(rows, key=lambda r: (-_float(r.get("mature_height_meters")),
                                           (r.get("common_name") or "")))
    if key == "wildlife":
        return sorted(rows, key=lambda r: (-int(r.get("_wildlife_count") or 0),
                                           (r.get("common_name") or "")))
    return sorted(rows, key=lambda r: (r.get("common_name") or "").lower())


def _float(value) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


# ── One species, as a page ───────────────────────────────────────────────────

def species_entry(plant_id: int, *,
                  get_plant: Optional[Callable] = None,
                  fauna_for_plant: Optional[Callable] = None,
                  neighbourhood: Optional[Callable] = None,
                  ranges_for: Optional[Callable] = None,
                  calendar_for: Optional[Callable] = None,
                  photos_for: Optional[Callable] = None) -> dict:
    """Everything a species page shows, as a plain dict.

    The catalogue-wide sibling of ``scene_dossier._plant_entry``, which builds
    almost this and cannot be reused directly: it is scene-scoped (it needs a
    year for the growth timeline and computes "the only thing feeding this
    animal" against the plants in *your design*). The shared parts — safety
    wording, sourcing, morphology in plain English, the ecological-role badges —
    are imported from it rather than restated, so the 3D inspect card and this
    page can never disagree about the same plant.

    Every collaborator is injectable; with all of them supplied this runs with
    no database at all.
    """
    if get_plant is None:
        from src.db.plants import get_plant                    # noqa: PLC0415
    plant = get_plant(plant_id)
    if not plant:
        return {}

    from src.ecological_role import ecological_role_summary    # noqa: PLC0415
    from src.scene_dossier import (_bloom_pair, _fruit_pair,   # noqa: PLC0415
                                   _month_span, _morphology,
                                   _safety_notes, _sourcing)

    if fauna_for_plant is None:
        from src.db.fauna import fauna_for_plant               # noqa: PLC0415
    edges = _safely(lambda: fauna_for_plant(plant_id), [])

    entry = {
        "id": plant_id,
        "name": plant.get("common_name") or "",
        "scientific_name": plant.get("scientific_name") or "",
        "plant_type": plant.get("plant_type") or "",
        "badges": ecological_role_summary(plant, fauna_rows=edges),
        "native": (plant.get("native_provinces")
                   or plant.get("native_region") or ""),
        # Carried, not dropped. `nativity.provenance` reads exactly this key
        # to decide whether the claim is published, and V2.80 got the seed
        # file, the column, the migration and a reseed test all right while
        # every built page still said "not checked" -- because this dict never
        # copied it across. Same trap `nativity.py` documents for `native`.
        SOURCE_FIELD: plant.get(SOURCE_FIELD) or "",
        "native_to_alberta": bool(plant.get("native_to_alberta")),
        "sun": (plant.get("sun_requirement") or "").replace("_", " "),
        "water": plant.get("water_needs") or "",
        "soil_ph": _ph_range(plant),
        "zones": _zone_range(plant),
        "spacing_m": plant.get("spacing_meters"),
        "mature_height_m": plant.get("mature_height_meters"),
        "mature_canopy_m": plant.get("mature_canopy_m"),
        "years_to_maturity": plant.get("years_to_maturity"),
        "bloom": _month_span(*_bloom_pair(plant)),
        "bloom_color": plant.get("flower_color") or "",
        # The colour as a WORD, plus whether anyone checked it (V2.48). The hex
        # drives the 3D bloom and is meaningless on a page, so this page used to
        # print nothing at all for flower colour. Both halves are assembled here
        # rather than in either surface, so the desktop page and the website say
        # the same thing about the same plant.
        **_bloom_colour(plant),
        "fruit": _month_span(*_fruit_pair(plant)),
        "fruit_color": plant.get("fruit_color") or "",
        "morphology": _morphology(plant),
        "safety": _safety_notes(plant),
        "sourcing": _sourcing(plant),
        "edible_parts": plant.get("edible_parts") or "",
        "notes": plant.get("notes") or "",
        "image_url": plant.get("image_url") or "",
        "image_attribution": plant.get("image_attribution") or "",
        "image_license": plant.get("image_license") or "",
        "wildlife": _wildlife(edges),
        "ranges": _ranges(plant_id, plant, ranges_for),
        "calendar": _calendar(plant_id, calendar_for),
        "photos": _photos(plant, photos_for),
        "provenance": _provenance(plant),
    }
    entry["relationships"] = _relationships(plant_id, neighbourhood)
    return entry


def _safely(fn: Callable, fallback):
    """A species page must render even when one of its sources is unavailable.
    A missing section is a gap; a traceback is a dead feature."""
    try:
        return fn()
    except Exception:                                    # noqa: BLE001
        return fallback


def _wildlife(edges: list) -> dict:
    """The documented animals, grouped by what they get, specialists flagged.

    ``{"total": n, "specialists": n, "groups": [{how, items:[{name, taxon,
    specialist}]}]}``. Specialists are counted separately because that is the
    single most consequential thing on the page: a generalist losing this plant
    finds another, and a specialist does not (P3).
    """
    from src.scene_dossier import _REL_FROM_PLANT, _TAXON_LABEL  # noqa: PLC0415
    groups: dict = {}
    specialists = 0
    for row in edges or []:
        how = _REL_FROM_PLANT.get(row.get("relationship") or "", "used by")
        specialist = row.get("specificity") == "specialist"
        specialists += 1 if specialist else 0
        groups.setdefault(how, []).append({
            "name": row.get("common_name") or "",
            "scientific_name": row.get("scientific_name") or "",
            "taxon": row.get("taxon") or "",
            "taxon_label": _TAXON_LABEL.get(row.get("taxon"), ""),
            "specialist": specialist,
            "source": row.get("source") or "",
        })
    out = [{"how": how, "items": sorted(items, key=lambda i: i["name"])}
           for how, items in sorted(groups.items(),
                                    key=lambda kv: -len(kv[1]))]
    return {"total": len(edges or []), "specialists": specialists,
            "groups": out}


def _relationships(plant_id: int, neighbourhood: Optional[Callable]) -> dict:
    if neighbourhood is None:
        from src.db.relationships import neighbourhood         # noqa: PLC0415
    return _safely(lambda: neighbourhood(plant_id),
                   {"plant_id": plant_id, "total": 0, "groups": []})


def _ranges(plant_id: int, plant: dict,
            ranges_for: Optional[Callable]) -> list[dict]:
    """Where this species has actually been recorded, **with the evidence**.

    ``[{key, name, occurrences, confidence, source}]``. The count and the
    confidence band travel with the region because they are the difference
    between a range and a guess (P9). Falls back to the heuristic
    ``plants.ecoregion`` column when nothing has been derived, and says so by
    carrying ``occurrences = 0``.
    """
    if ranges_for is None:
        from src.db.plants import ecoregion_ranges_for_ids     # noqa: PLC0415
        ranges_for = lambda ids: ecoregion_ranges_for_ids(ids)  # noqa: E731

    from src.ecoregion import ecoregion_display                # noqa: PLC0415
    rows = _safely(lambda: (ranges_for([plant_id]) or {}).get(plant_id, []), [])
    if rows:
        out = []
        for r in rows:
            key = r.get("ecoregion") or ""
            name, where = ecoregion_display(key)
            out.append({"key": key, "name": name, "where": where,
                        "occurrences": int(r.get("occurrences") or 0),
                        "confidence": r.get("confidence") or "",
                        "source": r.get("source") or ""})
        return sorted(out, key=lambda r: -r["occurrences"])

    out = []
    for key in [t.strip() for t in (plant.get("ecoregion") or "").split(",")]:
        if not key:
            continue
        name, where = ecoregion_display(key)
        out.append({"key": key, "name": name, "where": where,
                    "occurrences": 0, "confidence": "", "source": ""})
    return out


def _calendar(plant_id: int, calendar_for: Optional[Callable]) -> list[dict]:
    if calendar_for is None:
        from src.db.plants import get_calendar as calendar_for  # noqa: PLC0415
    return _safely(lambda: calendar_for(plant_id), [])


def _photos(plant: dict, photos_for: Optional[Callable]) -> list[dict]:
    """The named-slot photo set, newest machinery first, falling back to the
    single ``image_url`` every row has carried since schema v24.

    Only 323 of 434 species have any photograph at all and the slot table ships
    empty, so this returns a short list or none — and the page says which,
    rather than drawing an empty frame.
    """
    name = plant.get("scientific_name") or ""
    if photos_for is None:
        try:
            from src.db.photos import photos_for               # noqa: PLC0415
        except Exception:                                      # noqa: BLE001
            photos_for = None
    rows = _safely(lambda: photos_for(name), []) if photos_for and name else []
    if rows:
        return list(rows)
    if plant.get("image_url"):
        return [{"slot": "", "url": plant["image_url"],
                 "attribution": plant.get("image_attribution") or "",
                 "license": plant.get("image_license") or ""}]
    return []


def _provenance(plant: dict) -> list[str]:
    """Where the measured morphology came from. A directory that shows petal
    counts should be able to say who counted them (P9, and the V2.38 bench
    refuses a correction that cannot).

    V2.53: the raw seed word (``estimated``, ``flora``) is rendered through
    :func:`src.confidence.mark`, so this page, the website and the 3D dossier
    all say the same thing about the same value. It used to print the database
    token, which is honest and unreadable — "Flower detail: estimated" does not
    tell a reader that nobody has ever looked at that number.
    """
    from src.confidence import mark                          # noqa: PLC0415
    out = []
    for src_field, cite_field, what in (
            ("flower_data_source", "flower_data_citation", "Flower"),
            ("leaf_data_source", "leaf_data_citation", "Leaf")):
        source = (plant.get(src_field) or "").strip()
        if not source:
            continue
        cite = (plant.get(cite_field) or "").strip()
        m = mark(source)
        # An unrecognised seed word still shows itself rather than vanishing
        # behind "not recorded" — the value IS there, we just have no wording.
        word = m.label if m.recorded else source
        out.append(f"{what} detail: {word}" + (f" — {cite}" if cite else ""))
    return out


def _bloom_colour(plant: dict) -> dict:
    """``{bloom_colour, bloom_colour_label, bloom_colour_note}``.

    Empty strings where the catalogue records nothing, so a caller can print the
    block or skip it without testing for a sentinel.
    """
    from src.flower_colour import (                            # noqa: PLC0415
        COLOUR_LABELS, classify, colours,
    )
    key = classify(plant)
    if not key:
        return {"bloom_colour": "", "bloom_colour_label": "",
                "bloom_colour_note": "", "bloom_colours": ()}
    if key == "straw":
        # A grass is not an unverified purple. Its bucket comes from the family
        # being wind-pollinated, which is a botanical fact rather than a guess
        # somebody has yet to check, so the provenance wording does not apply.
        return {"bloom_colour": key,
                "bloom_colour_label": "Straw or green seed heads",
                "bloom_colour_note": "wind-pollinated, so no showy flower",
                "bloom_colours": (key,)}
    from src.confidence import mark                          # noqa: PLC0415
    source = (plant.get("flower_colour_source") or "").strip()
    m = mark(source)
    keys = colours(plant) or (key,)
    # A flora writes "white to pinkish", and printing only the first of those
    # throws away the half of the answer that explains why the photograph
    # above it looks wrong. Two colours read as a range because that is what
    # the book means; three or more are listed, because "yellow to pinkish
    # orange" is a range and "white, pink and purple" is a set.
    if len(keys) == 1:
        label = COLOUR_LABELS.get(keys[0], keys[0])
    elif len(keys) == 2:
        label = (f"{COLOUR_LABELS.get(keys[0], keys[0])} to "
                 f"{COLOUR_LABELS.get(keys[1], keys[1]).lower()}")
    else:
        named = [COLOUR_LABELS.get(k, k) for k in keys]
        label = ", ".join(named[:-1]) + " and " + named[-1].lower()
    return {
        "bloom_colour": key,
        "bloom_colours": keys,
        "bloom_colour_label": label,
        # No mark on a value somebody checked, and nothing at all when the
        # column is empty — the shared rule from src.confidence.annotate.
        "bloom_colour_note": m.label if (m.recorded and source) else "",
    }


def _ph_range(plant: dict) -> str:
    lo = _number(plant.get("soil_ph_min"))
    hi = _number(plant.get("soil_ph_max"))
    if lo and hi:
        return f"pH {lo}–{hi}"
    if lo or hi:
        return f"pH {lo or hi}"
    return ""


def _zone_range(plant: dict) -> str:
    """The hardiness band, **keeping any uncertainty marker the data carries**.

    ``hardiness_zone_min`` is not reliably numeric: one row ships ``'4?'``,
    which is a botanist's "about 4, not verified" and is exactly the kind of
    hedge P9 asks us to preserve rather than round off. It also used to crash
    this function — ``int('4?')`` raised ``ValueError`` and took the whole
    species page down with it, which is why False Box could not be opened in the
    directory at all (found V2.47, while building the static site over the same
    call). Rendering the mark is both the honest answer and the safe one.
    """
    lo = _number(plant.get("hardiness_zone_min"))
    hi = _number(plant.get("hardiness_zone_max"))
    if lo and hi and lo.rstrip("?") != hi.rstrip("?"):
        return f"zone {lo}–{hi}"
    if lo or hi:
        return f"zone {lo or hi}"
    return ""


def _number(value) -> str:
    """A numeric field as display text, tolerating the hedges the data carries.

    ``4.0`` → ``"4"``, ``"4?"`` → ``"4?"``, ``""``/``None``/unparseable →
    ``""``. Never raises: a reference work that refuses to draw a page because
    one field of seventy is oddly formatted is worse than one that draws the
    other sixty-nine.
    """
    if value is None or value == "":
        return ""
    if isinstance(value, (int, float)):
        return f"{float(value):g}"
    text = str(value).strip()
    try:
        return f"{float(text):g}"
    except ValueError:
        pass
    mark = "?" if text.endswith("?") else ""
    try:
        return f"{float(text.rstrip('?').strip()):g}{mark}"
    except ValueError:
        return text


# ── What is flowering now ────────────────────────────────────────────────────

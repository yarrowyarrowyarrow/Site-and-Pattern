"""
src/scene_dossier.py — the learning content behind a click in the 3D preview
(V2.29).

Design principle P5 (perception is constructed — make the invisible ecology
visible where the user is already looking) and P3/P10 (relationships are the
unit of value: a plant's entry is mostly the *edges* it carries) — see
docs/DESIGN_PHILOSOPHY.md.

Until now the 3D view answered exactly one question — "what is that?" — with a
hover tooltip carrying a common name, while the app held sourced ecology for
every species in it: 362 documented plant↔fauna edges, bee nesting habits and
tongue lengths, lepidoptera flight seasons and overwintering stages, keystone
and specialist status, bloom and fruit windows, toxicity and thorns, sourcing
estimates. None of it reached the place where you can *see* the plant.

:func:`build_dossier` assembles that into one plain dict, keyed by the ids the
scene already carries, so the viewer can render a card entirely client-side.
The 3D bridge is one-directional by design (no QWebChannel — see
docs/scene-3d), which makes pushing the content alongside the scene the natural
shape: no round trip, works in walk/fly/bee modes, and testable as a pure
function.

Honesty rules it inherits (P9):
  * Only *documented* edges appear — nothing is inferred from "plants like this
    usually…".
  * An unassessed toxicity is reported as unassessed, never as safe: the
    seed data deliberately distinguishes '' from 'none'.
  * Prices are stated as estimates, with their year and region caveat.
  * "Only source here" is computed from the design in front of you, so it
    changes as the design changes — that is the point.

Qt-free, DB-injectable, JSON-serialisable.
"""

from __future__ import annotations

from typing import Callable, Optional

from src.nativity import SOURCE_FIELD as _NATIVITY_SOURCE

# Relationship → how it reads on the card, from the plant's side and the
# animal's side. Same vocabulary as the hover tooltip (01-core.js _REL_WORDS)
# and src/scene_wildlife.py.
_REL_FROM_PLANT = {
    "nectar": "nectar for",
    "pollen": "pollen for",
    "larval_host": "caterpillar host for",
    "fruit_food": "fruit for",
    "seed_food": "seed for",
    "nesting": "nest site for",
    "cover": "cover for",
}
_REL_FROM_ANIMAL = {
    "nectar": "sips nectar at",
    "pollen": "gathers pollen at",
    "larval_host": "lays eggs on",
    "fruit_food": "eats fruit of",
    "seed_food": "eats seed of",
    "nesting": "nests in",
    "cover": "shelters in",
}

_TAXON_LABEL = {
    "bee": "native bee", "lepidoptera": "butterfly / moth", "bird": "bird",
    "other_insect": "insect", "mammal": "mammal",
}

_MONTH_ABBR = ["", "Jan", "Feb", "Mar", "Apr", "May", "Jun",
               "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

# Growth-timeline years the card charts. Chosen to answer "when does this stop
# looking like a twig?" — the question the year slider exists for (P4).
TIMELINE_YEARS = (1, 5, 15, 25)

_NESTING_LABEL = {
    "ground": "nests in bare ground",
    "cavity": "nests in cavities (bee hotels, hollow stems)",
    "pithy_stem": "excavates pithy stems",
    "social_ground": "social colonies in ground cavities",
    "cleptoparasite": "cuckoo bee — lays in another bee's nest",
}
_TONGUE_LABEL = {
    "short": "short tongue — needs open, shallow flowers",
    "medium": "medium tongue",
    "long": "long tongue — reaches deep tubular flowers",
}
_OVERWINTER_LABEL = {
    "egg": "overwinters as an egg",
    "larva": "overwinters as a caterpillar",
    "pupa": "overwinters as a chrysalis / cocoon",
    "adult": "overwinters as an adult",
    "migrant": "migrates — does not overwinter here",
}


def _month_span(start, end) -> str:
    """'May–Jul' from a (start, end) month pair; '' when unknown."""
    try:
        s, e = int(start or 0), int(end or 0)
    except (TypeError, ValueError):
        return ""
    if not s:
        return ""
    if not e or e == s:
        return _MONTH_ABBR[s]
    return f"{_MONTH_ABBR[s]}–{_MONTH_ABBR[e]}"


def _safety_notes(plant: dict) -> list[str]:
    """Toxicity / thorn warnings, honest about what has not been assessed.

    The seed data keeps '' (unassessed) distinct from 'none' on purpose, and the
    safety filters are a denylist — so silence here means "nobody checked",
    which is exactly what the card must say rather than implying safety.
    """
    out = []
    for field, who in (("toxicity_pets", "pets"), ("toxicity_humans", "people")):
        level = (plant.get(field) or "").strip()
        if level in ("low", "high"):
            out.append(f"{level.capitalize()} toxicity to {who}")
    if plant.get("has_thorns"):
        out.append("Has thorns or prickles")
    if not (plant.get("toxicity_pets") or plant.get("toxicity_humans")):
        out.append("Toxicity not assessed — absence of a warning is not a "
                   "guarantee of safety")
    return out


def _sourcing(plant: dict) -> dict:
    """Where to get it and roughly what it costs — flagged as an estimate."""
    lo, hi = plant.get("price_low_cad"), plant.get("price_high_cad")
    price = ""
    if lo and hi:
        price = f"about ${float(lo):.0f}–${float(hi):.0f} per plant"
    elif lo or hi:
        price = f"about ${float(lo or hi):.0f} per plant"
    out = {}
    if price:
        out["price"] = price + " (estimate)"
    if plant.get("availability_class"):
        out["availability"] = str(plant["availability_class"]).replace("_", " ")
    if plant.get("sourcing_notes"):
        out["notes"] = plant["sourcing_notes"]
    return out


def _timeline(plant: dict, scene_year: int, plant_3d_state=None) -> list[dict]:
    """Height and spread at TIMELINE_YEARS, straight from the module the growth
    slider and the 2D timeline use — so the card can never disagree with the
    thing on screen next to it."""
    if plant_3d_state is None:
        from src.scene3d import plant_3d_state          # noqa: PLC0415
    out = []
    for year in TIMELINE_YEARS:
        try:
            st = plant_3d_state(plant, 0.0, 0.0, year)
        except Exception:                                # noqa: BLE001
            continue
        out.append({"year": year,
                    "height_m": round(float(st["height_m"]), 2),
                    "canopy_m": round(float(st["canopy_m"]), 2),
                    "now": year == scene_year})
    return out


def _photo(row: dict) -> Optional[dict]:
    """``{key, credit}`` for a row's photo, or ``None``.

    Cache-only on purpose: this runs while building a push, so it must never
    block on the network. A photo the warmer hasn't reached yet is simply absent
    and appears on the next push.

    ``key`` is an opaque cache handle, not the URL — the viewer fetches it from
    the loopback server's ``/__image`` route, which resolves keys inside the
    cache directory and nowhere else. ``credit`` is never empty when ``key`` is
    present: showing an open-licensed photo obliges us to say whose it is, so an
    entry that cannot name its source carries no photo at all.
    """
    url = (row.get("image_url") or "").strip()
    if not url:
        return None
    try:
        from src.image_cache import (cache_key, credit_line,   # noqa: PLC0415
                                     get_cached_image)
        if not get_cached_image(url):
            return None
        credit = credit_line(row.get("image_attribution") or "",
                             row.get("image_license") or "")
        if not credit:
            return None
        return {"key": cache_key(url), "credit": credit}
    except Exception:                              # noqa: BLE001 — graceful
        return None


def _plant_entry(plant: dict, edges: list, only_source: list,
                 scene_year: int, plant_3d_state=None) -> dict:
    """One plant's card. ``edges`` are its documented fauna rows; ``only_source``
    the names of animals this plant alone supports in the current design."""
    from src.ecological_role import ecological_role_summary   # noqa: PLC0415

    from src.citations import (                              # noqa: PLC0415
        format_sources, is_placeholder)

    users = _users(edges, format_sources, is_placeholder)

    entry = {
        "kind": "plant",
        "name": plant.get("common_name") or "",
        "scientific_name": plant.get("scientific_name") or "",
        "plant_type": plant.get("plant_type") or "",
        "badges": ecological_role_summary(plant, fauna_rows=edges),
        "native": plant.get("native_provinces") or plant.get("native_region") or "",
        # Same reason as `plant_directory.species_entry`: this dict is
        # what the inspect card renders, and dropping the key here makes
        # every plant read "not checked against a published flora"
        # however well sourced the row behind it is.
        _NATIVITY_SOURCE: plant.get(_NATIVITY_SOURCE) or "",
        "ecoregion": plant.get("ecoregion") or "",
        "sun": (plant.get("sun_requirement") or "").replace("_", " "),
        "water": plant.get("water_needs") or "",
        "bloom": _month_span(*_bloom_pair(plant)),
        "bloom_color": plant.get("flower_color") or "",
        "fruit": _month_span(*_fruit_pair(plant)),
        "fruit_color": plant.get("fruit_color") or "",
        # What it looks like (schema v47) — the same fields that shape the 3D
        # model, said in words, so the card explains the thing on screen.
        "morphology": _morphology(plant),
        "mature_height_m": plant.get("mature_height_meters"),
        "mature_canopy_m": plant.get("mature_canopy_m"),
        "years_to_maturity": plant.get("years_to_maturity"),
        "timeline": _timeline(plant, scene_year, plant_3d_state),
        # What it is food for, in sentences (V3.39): the card's first lines.
        "does": _does(users),
        "users": users,
        "only_source": sorted(only_source),
        "safety": _safety_notes(plant),
        "sourcing": _sourcing(plant),
        # No free-text notes (V3.38): the plant page dropped them in V3.26
        # (L8, P12), because about 43 seeded notes describe traditional plant
        # use, and the card is shown in the Learn walk too now.
        "edible_parts": plant.get("edible_parts") or "",
        # The works behind the wildlife rows above, deduped and in full (F12).
        "sources": _source_block(edges),
    }
    photo = _photo(plant)
    if photo:
        entry["photo"] = photo
    return entry


def _users(edges: list, format_sources, is_placeholder) -> list:
    """One row per animal recorded with this plant. Until V3.39 a row per
    record, so an animal at the nectar and the pollen of one plant was two
    rows; the card now lists animals, each with every way it uses the plant.
    Ordered to put first the animals a person can get to know: an English
    name, then a specialist (it has nowhere else to go), then by group and
    name. The viewer adds a photograph and being out now (25-cards.js)."""
    from src.what_it_feeds import GROUPS, kind_words          # noqa: PLC0415
    from src.yard_overview_items import english_name           # noqa: PLC0415
    by: dict = {}
    for r in edges:
        name = r.get("common_name") or ""
        if not name:
            continue
        u = by.setdefault(name, {
            "name": name,
            "scientific_name": r.get("scientific_name") or "",
            "taxon": r.get("taxon") or "",
            "taxon_label": _TAXON_LABEL.get(r.get("taxon"), ""),
            "kinds": [], "specialist": False, "sources": [],
            "english": bool(english_name(r)),
        })
        rel = r.get("relationship") or ""
        if rel and rel not in u["kinds"]:
            u["kinds"].append(rel)
        # A specialist has nowhere else to go — the single most important
        # thing the card can tell you about an edge (P3).
        u["specialist"] = u["specialist"] or r.get("specificity") == "specialist"
        # F12 (V2.53). Every one of these edges has carried a cited source
        # since it was written; the short form ("Acorn & Sheldon 2006") rides
        # on the row, the full references go in `sources`, once each.
        cite = _short_source(r.get("source"), format_sources, is_placeholder)
        if cite and cite not in u["sources"]:
            u["sources"].append(cite)
    order = [t for t, _one, _plural in GROUPS]
    out = []
    for u in by.values():
        u["how"] = " and ".join(
            _REL_FROM_PLANT.get(k, "used by").removesuffix(" for")
            for k in u["kinds"]) + " for"
        u["words"] = " and ".join(kind_words(k, u["taxon"]) for k in u["kinds"])
        u["source"] = "; ".join(u.pop("sources"))
        out.append(u)
    out.sort(key=lambda u: (not u["english"], not u["specialist"],
                            order.index(u["taxon"]) if u["taxon"] in order
                            else len(order), u["name"].lower()))
    return out


#: The card's sentences, by the part of the plant an animal is recorded
#: eating or using. "Recorded as food for", never "feeds" (V3.20, OV-5): the
#: records say an animal was seen at it somewhere in two provinces.
_DOES = (
    ("flowers", "Its flowers are recorded as food for {}."),
    ("leaves", "Its leaves are recorded as food for the caterpillars of {}."),
    ("young", "It is recorded as a host for the young of {}."),
    ("fruit", "Its fruit is recorded as food for {}."),
    ("seed", "Its seeds are recorded as food for {}."),
    ("nest", "It is recorded as a nest site for {}."),
    ("cover", "It is recorded as cover for {}."),
)


def _part(kind: str, taxon: str) -> str:
    """Which part of the plant a record is about. A bee's host record is its
    flowers (GloBI's *hostOf*, ``what_it_feeds.kind_words``); a butterfly's or
    moth's is its leaves."""
    if kind in ("nectar", "pollen") or (kind == "larval_host"
                                        and taxon == "bee"):
        return "flowers"
    if kind == "larval_host":
        return "leaves" if taxon == "lepidoptera" else "young"
    return {"fruit_food": "fruit", "seed_food": "seed", "nesting": "nest",
            "cover": "cover"}.get(kind, "")


def _does(users: list) -> list[str]:
    """'Its flowers are recorded as food for 22 kinds: 18 bees, 4 butterflies
    and moths.' One sentence per part, each animal counted once in it."""
    from src.what_it_feeds import GROUPS, group_words          # noqa: PLC0415
    counts: dict = {}
    for u in users:
        for part in {_part(k, u["taxon"]) for k in u["kinds"]} - {""}:
            by = counts.setdefault(part, {})
            by[u["taxon"]] = by.get(u["taxon"], 0) + 1
    out = []
    for part, sentence in _DOES:
        by = counts.get(part)
        if not by:
            continue
        groups = [group_words(t, by[t]) for t, _o, _p in GROUPS if by.get(t)]
        groups += [group_words(t, n) for t, n in sorted(by.items())
                   if t not in {g for g, _o, _p in GROUPS}]
        total = sum(by.values())
        words = groups[0] if len(groups) == 1 else (
            f"{total} kinds: " + ", ".join(groups))
        out.append(sentence.format(words))
    return out


def _short_source(source, format_sources, is_placeholder) -> str:
    """Author-year for one edge, or ``""`` when nothing is attributable.

    A placeholder names no work, and printing it as a citation is the precise
    failure `src.citations` exists to prevent — so it yields an empty string
    here and the row simply carries no citation, which is honest.
    """
    keys = [k.strip() for k in (source or "").split(",") if k.strip()]
    real = [k for k in keys if not is_placeholder(k)]
    return format_sources(",".join(real), short=True) if real else ""


def _source_block(edges: list) -> dict:
    """``{works: [full citations], unattributed: n}`` for one plant's edges.

    Mirrors ``plant_directory_window._citation_block`` deliberately: the desktop
    directory, the 3D card and the website should not each invent their own way
    of saying where an edge came from. The unattributed count is reported rather
    than hidden, because "we do not know who says this" is itself information.
    """
    from src.citations import format_citation, is_placeholder  # noqa: PLC0415
    works: list[str] = []
    unattributed = 0
    for r in edges or []:
        for key in (k.strip() for k in (r.get("source") or "").split(",")):
            if not key:
                continue
            if is_placeholder(key):
                unattributed += 1
                continue
            text = format_citation(key)
            if text and text not in works:
                works.append(text)
    return {"works": works, "unattributed": unattributed}


_LEAF_SHAPE_LABEL = {
    "needle": "needles", "awl": "sharp awl-shaped leaves",
    "scale": "scale-like leaves", "linear": "narrow linear leaves",
    "lanceolate": "lance-shaped leaves", "elliptic": "elliptic leaves",
    "ovate": "egg-shaped leaves", "obovate": "spoon-shaped leaves",
    "orbicular": "round leaves", "cordate": "heart-shaped leaves",
    "lobed": "lobed leaves", "trifoliate": "leaves in threes",
    "compound_pinnate": "feather-compound leaves",
    "compound_palmate": "hand-compound leaves",
}
_BRANCHING_LABEL = {
    "excurrent": "a single straight leader",
    "decurrent": "a spreading, branching crown",
    "multi_stem": "several stems from the base",
    "suckering": "spreads by suckers into a colony",
    "arching": "arching canes",
    "prostrate": "low and ground-hugging",
    "rosette": "a basal rosette of stiff leaves",
}


def _morphology(plant: dict) -> list[str]:
    """Plain-language description of the species' form — the same fields the 3D
    archetype is shaped by, so the card explains what you are looking at."""
    out = []
    shape = _LEAF_SHAPE_LABEL.get(plant.get("leaf_shape") or "")
    size = plant.get("leaf_size_cm")
    if shape and size:
        arrangement = plant.get("leaf_arrangement") or ""
        pair = " in opposite pairs" if arrangement == "opposite" else (
            " in bundles" if arrangement == "fascicled" else "")
        out.append(f"{shape} about {float(size):g} cm long{pair}")
    elif shape:
        out.append(shape)
    branch = _BRANCHING_LABEL.get(plant.get("branching") or "")
    if branch:
        out.append(branch)
    return out


def _bloom_pair(plant: dict):
    from src.scene_contract import _bloom_months            # noqa: PLC0415
    return _bloom_months(plant.get("bloom_period"))


def _fruit_pair(plant: dict):
    from src.scene_contract import _bloom_months            # noqa: PLC0415
    return _bloom_months(plant.get("fruit_period"))


#: The order an animal's uses of one plant are said in: what its young eat
#: first, the plant it relies on (V3.39).
_USE_ORDER = ("larval_host", "nectar", "pollen", "fruit_food", "seed_food",
              "nesting", "cover")


def _uses_words(kinds) -> str:
    """'lays eggs on it and sips nectar at it': every way an animal uses one
    plant, from the animal's side."""
    ordered = sorted({k for k in kinds if k},
                     key=lambda k: _USE_ORDER.index(k) if k in _USE_ORDER
                     else len(_USE_ORDER))
    return " and ".join(f"{_REL_FROM_ANIMAL.get(k, 'uses')} it"
                        for k in ordered) or "uses it"


def _fauna_entry(row: dict, uses: list, attrs: dict) -> dict:
    """One animal's card: who it is, how it lives, and which of YOUR plants it
    uses. ``uses`` are ``{plant, how}`` for the present design only."""
    taxon = row.get("taxon") or ""
    facts = []
    if taxon == "bee":
        nest = _NESTING_LABEL.get(attrs.get("nesting_habit") or "")
        if nest:
            facts.append(nest)
        tongue = _TONGUE_LABEL.get(attrs.get("tongue_length") or "")
        if tongue:
            facts.append(tongue)
        if attrs.get("pollen_specialist"):
            facts.append("pollen specialist — depends on a narrow set of plants")
        if attrs.get("host_genus"):
            facts.append(f"host: {attrs['host_genus']} bees")
    elif taxon == "lepidoptera":
        ow = _OVERWINTER_LABEL.get(attrs.get("overwintering_stage") or "")
        if ow:
            facts.append(ow)
        if attrs.get("voltinism"):
            facts.append(str(attrs["voltinism"]))
        if attrs.get("larval_host_note"):
            facts.append(str(attrs["larval_host_note"]))
        if attrs.get("nectar_flower_genera") is None and attrs:
            facts.append("does not feed as an adult")

    from src.yard_overview_items import english_name           # noqa: PLC0415
    entry = {
        "kind": "fauna",
        "english": bool(english_name(row)),
        "name": row.get("common_name") or "",
        "scientific_name": row.get("scientific_name") or "",
        "taxon": taxon,
        "taxon_label": _TAXON_LABEL.get(taxon, ""),
        "description": row.get("description") or "",
        "season": attrs.get("flight_season") or "",
        "status": attrs.get("conservation_status") or "",
        "facts": facts,
        "uses": uses,
        "range_notes": row.get("range_notes") or "",
    }
    photo = _photo(row)
    if photo:
        entry["photo"] = photo
    return entry


def build_dossier(scene: dict, *,
                  get_plant: Optional[Callable] = None,
                  fauna_edges: Optional[Callable] = None,
                  fauna_attrs: Optional[Callable] = None,
                  plant_3d_state: Optional[Callable] = None,
                  animal_plans: Optional[Callable] = None,
                  plantable: tuple = (),
                  province: str = "") -> dict:
    """Learning content for everything in ``scene``, ready to push to the viewer.

    Returns ``{"plants": {plant_id: entry}, "fauna": {name: entry}, "reach":
    {taxon: n}}`` — keyed by the identifiers the scene and the wildlife list
    already carry, so the viewer can look an entry up from a click with nothing
    else in hand. ``reach`` counts the animals the scene's plants are recorded
    as food for, each once (``what_it_feeds.food_counts``' rule).

    ``animal_plans`` (``what_it_feeds.animal_plans``; V3.39) adds to each
    animal the catalogue's plants it uses that are not in the scene, native to
    ``province`` when one is given, ``plantable`` ones (the walk's own) first
    after food; each says whether it is ``plantable``. Opt-in: without it no
    entry is looked up beyond the scene, which keeps this a pure function for
    the tests.

    Every collaborator is injectable for tests; each is called **once for the
    whole design**, not once per plant, so a 119-plant yard costs one edge query
    rather than 119. The "only source here" set falls out of that same query as
    a set operation — no habitat-score recomputation per plant.
    """
    plants = [p for p in (scene.get("plants") or []) if p.get("plant_id")]
    if not plants:
        return {"plants": {}, "fauna": {}}
    if get_plant is None:
        from src.db.plants import get_plant as _gp           # noqa: PLC0415
        get_plant = _gp
    if fauna_edges is None:
        from src.db.fauna import fauna_for_plants as fauna_edges   # noqa: PLC0415

    pids = sorted({int(p["plant_id"]) for p in plants})
    names = {int(p["plant_id"]): p.get("common_name") or "" for p in plants}
    year = int(scene.get("year") or 0)

    try:
        rows = list(fauna_edges(pids))
    except Exception:                                        # noqa: BLE001
        rows = []

    # Group edges by plant, and count how many DISTINCT present plants support
    # each animal — an animal supported by exactly one is the "pull this and it
    # is gone" case the card leads with (P3: the edge is the unit of value).
    by_plant: dict = {}
    supporters: dict = {}
    fauna_rows: dict = {}
    for r in rows:
        pid = r.get("plant_id")
        fid = r.get("id")
        if pid is None or fid is None:
            continue
        by_plant.setdefault(int(pid), []).append(r)
        supporters.setdefault(fid, set()).add(int(pid))
        fauna_rows.setdefault(fid, r)

    plant_entries = {}
    for pid in pids:
        plant = get_plant(pid) or {}
        if not plant:
            continue
        edges = by_plant.get(pid, [])
        only = [r.get("common_name") or "" for r in edges
                if len(supporters.get(r.get("id"), ())) == 1]
        plant_entries[str(pid)] = _plant_entry(
            plant, edges, only, year, plant_3d_state)

    # Fauna are keyed by common name: that is what the scene's wildlife records
    # carry (src/scene_wildlife.py), and it is what a click has to work from.
    plans = {}
    if animal_plans is not None and fauna_rows:
        try:
            plans = animal_plans(sorted(fauna_rows), pids, elsewhere=6,
                                 prefer=tuple(plantable),
                                 province=province) or {}
        except Exception:                                    # noqa: BLE001
            plans = {}
    can_plant = {int(p) for p in plantable}
    # Each animal's facts in two queries for the whole scene, not a connection
    # per animal: a walk's cards cover 450 animals and are rebuilt on every
    # edit, and the per-animal lookups were half the build (V3.41).
    preloaded = (_attrs_for(fauna_rows) if fauna_attrs is None else {})
    rels: dict = {}
    for r in rows:
        if r.get("id") is not None and r.get("plant_id") is not None:
            rels.setdefault((r["id"], int(r["plant_id"])), []).append(
                r.get("relationship") or "")
    fauna_entries = {}
    for fid, row in fauna_rows.items():
        if fauna_attrs is not None:
            attrs = fauna_attrs(fid, row.get("taxon")) or {}
        else:
            attrs = preloaded.get(fid, {})
        uses = [{"plant": names.get(pid, ""), "plant_id": pid,
                 "how": _REL_FROM_ANIMAL.get(
                     (rels.get((fid, pid)) or [""])[0], "uses"),
                 "does": _uses_words(rels.get((fid, pid)) or [])}
                for pid in sorted(supporters.get(fid, ()))]
        name = row.get("common_name") or ""
        if name:
            entry = _fauna_entry(row, uses, attrs)
            plan = plans.get(fid)
            if plan:
                entry["elsewhere"] = [
                    {"plant_id": e["plant_id"], "name": e["name"],
                     "does": _uses_words(e["kinds"]),
                     "plantable": e["plant_id"] in can_plant}
                    for e in plan.get("elsewhere") or []]
                entry["elsewhere_total"] = plan.get("elsewhere_total", 0)
            fauna_entries[name] = entry

    out = {"plants": plant_entries, "fauna": fauna_entries,
           "reach": _reach(rows)}
    if can_plant:
        out["plantable"] = sorted(can_plant)
    return out


def _reach(rows: list) -> dict:
    """``{taxon: n}``: the animals the scene's plants are recorded as food
    for, each once; shelter alone does not count (V3.20, OV-5)."""
    from src.what_it_feeds import FOOD_KINDS                   # noqa: PLC0415
    taxon_of: dict = {}
    for r in rows:
        if (r.get("relationship") in FOOD_KINDS and r.get("id") is not None):
            taxon_of[r["id"]] = r.get("taxon") or ""
    out: dict = {}
    for taxon in taxon_of.values():
        out[taxon] = out.get(taxon, 0) + 1
    return out


def _attrs_for(fauna_rows: dict) -> dict:
    """``{fauna_id: attribute row}`` for every bee and butterfly or moth among
    ``fauna_rows`` (``{fauna_id: row}``), from the two narrow tables in one
    connection. Best-effort: an empty dict when they cannot be read."""
    tables = {"bee": "bee_attributes", "lepidoptera": "lepidoptera_attributes"}
    out: dict = {}
    try:
        from src.db.plants import get_connection           # noqa: PLC0415
        conn = get_connection()
    except Exception:                                        # noqa: BLE001
        return out
    try:
        for taxon, table in tables.items():
            ids = sorted(fid for fid, r in fauna_rows.items()
                         if r.get("taxon") == taxon)
            if not ids:
                continue
            marks = ",".join("?" * len(ids))
            for r in conn.execute(f"SELECT * FROM {table} "
                                  f"WHERE fauna_id IN ({marks})", ids):
                out[r["fauna_id"]] = dict(r)
    except Exception:                                        # noqa: BLE001
        pass
    finally:
        conn.close()
    return out


def _default_attrs(fauna_id: int, taxon: str) -> dict:
    """Taxon-specific attribute row, best-effort — the card degrades to the
    shared fauna fields when the narrow table has nothing."""
    try:
        if taxon == "bee":
            from src.db.fauna import bee_attributes_for      # noqa: PLC0415
            return bee_attributes_for(int(fauna_id)) or {}
        if taxon == "lepidoptera":
            from src.db.fauna import lep_attributes_for      # noqa: PLC0415
            return lep_attributes_for(int(fauna_id)) or {}
    except Exception:                                        # noqa: BLE001
        pass
    return {}

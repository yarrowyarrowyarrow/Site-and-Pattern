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


def _plant_entry(plant: dict, edges: list, only_source: list,
                 scene_year: int, plant_3d_state=None) -> dict:
    """One plant's card. ``edges`` are its documented fauna rows; ``only_source``
    the names of animals this plant alone supports in the current design."""
    from src.ecological_role import ecological_role_summary   # noqa: PLC0415

    users = []
    for r in sorted(edges, key=lambda r: (r.get("taxon") or "",
                                          r.get("common_name") or "")):
        rel = r.get("relationship") or ""
        users.append({
            "name": r.get("common_name") or "",
            "scientific_name": r.get("scientific_name") or "",
            "taxon": r.get("taxon") or "",
            "taxon_label": _TAXON_LABEL.get(r.get("taxon"), ""),
            "how": _REL_FROM_PLANT.get(rel, "used by"),
            # A specialist has nowhere else to go — the single most important
            # thing the card can tell you about an edge (P3).
            "specialist": r.get("specificity") == "specialist",
        })

    entry = {
        "kind": "plant",
        "name": plant.get("common_name") or "",
        "scientific_name": plant.get("scientific_name") or "",
        "plant_type": plant.get("plant_type") or "",
        "badges": ecological_role_summary(plant, fauna_rows=edges),
        "native": plant.get("native_provinces") or plant.get("native_region") or "",
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
        "users": users,
        "only_source": sorted(only_source),
        "safety": _safety_notes(plant),
        "sourcing": _sourcing(plant),
        "notes": plant.get("notes") or "",
        "edible_parts": plant.get("edible_parts") or "",
    }
    return entry


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

    return {
        "kind": "fauna",
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


def build_dossier(scene: dict, *,
                  get_plant: Optional[Callable] = None,
                  fauna_edges: Optional[Callable] = None,
                  fauna_attrs: Optional[Callable] = None,
                  plant_3d_state: Optional[Callable] = None) -> dict:
    """Learning content for everything in ``scene``, ready to push to the viewer.

    Returns ``{"plants": {plant_id: entry}, "fauna": {name: entry}}`` — keyed by
    the identifiers the scene and the wildlife list already carry, so the viewer
    can look an entry up from a click with nothing else in hand.

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
    fauna_entries = {}
    for fid, row in fauna_rows.items():
        attrs = {}
        if fauna_attrs is not None:
            attrs = fauna_attrs(fid, row.get("taxon")) or {}
        else:
            attrs = _default_attrs(fid, row.get("taxon"))
        uses = [{"plant": names.get(pid, ""),
                 "how": _REL_FROM_ANIMAL.get(
                     next((e.get("relationship") for e in by_plant.get(pid, [])
                           if e.get("id") == fid), ""), "uses")}
                for pid in sorted(supporters.get(fid, ()))]
        name = row.get("common_name") or ""
        if name:
            fauna_entries[name] = _fauna_entry(row, uses, attrs)

    return {"plants": plant_entries, "fauna": fauna_entries}


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

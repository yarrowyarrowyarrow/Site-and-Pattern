"""
plant_priority.py — which plants to lead with (PR-1, V3.26;
docs/homeowner/05-plants-that-lead.md).

Design principle P6 — see docs/DESIGN_PHILOSOPHY.md.

The owner: the plants "should focus on and lead with those making the greatest
impact ecologically and most feasibly to plant". Until V3.26 every list a
beginner saw first was A to Z. The owner's answers to part 05 shaped this
module:

* **Impact only, feasibility as words** (L1). The order is Impact, 0 to 11,
  from records the app already trusts: caterpillars (with a keystone floor),
  a specialist, birds, bees and the thin ends of the season (§4.1). Whether a
  beginner can buy it, plant it and keep it is said in words, the cautions,
  never added up. Within one Impact, a plant on a local seller's list comes
  first (``local_stock``), then the name.
* **Bands are cut on Impact**: *Top pick* holds about the top 40 Edmonton
  natives, *Good pick* the rest that feed something on record, *Little
  recorded* the ones nothing much is recorded on yet. A plant that needs
  standing water goes to *For a pond*, and a pin's plant not on its local list
  to *Not native around …*, both after the rest, because each is a fact about
  the yard rather than a score. A restoration plant no seller lists is at most
  a *Good pick* (the owner, V3.25).
* **No size words without an outline** (L3): a plant is "too big for this
  yard" only against a measured area.
* **Nothing about spreading until it is checked** (L5): a blank
  ``spread_habit`` says nothing.
* Chokecherry may lead, with its cautions shown (L4); moist-site plants keep
  their band with "Wants moist soil" (L6).

It **ranks and never filters** (P9): ``rank`` returns the same rows. A plant
with nothing recorded says "Little is recorded yet about what it feeds",
never "low". The words come from structured fields and edges only; the
free-text notes never reach them (P12). The habitat score does not read this
module and does not move. Qt-free.
"""

from __future__ import annotations

import functools
from dataclasses import dataclass, field
from typing import Iterable, Mapping, Optional

#: Every weight in one place, so a correction is one line.
CATERPILLAR_STEPS = ((13, 4), (6, 3), (3, 2), (1, 1))
WOODY_KEYSTONE = frozenset({"Quercus", "Prunus", "Salix", "Betula", "Populus"})
KEYSTONE_FLOOR = {"woody": 4, "herb": 3}
BEE_STEPS = ((40, 3), (15, 2), (5, 1))
BIRDS_MANY = 5
SHOULDER_MONTHS = frozenset({4, 5, 9})
WIND_POLLINATED = frozenset({"grass", "sedge", "rush"})
#: Wind-pollinated wetland genera filed under other types (cattails,
#: bur-reeds, bulrushes, spikerushes, reeds).
WIND_GENERA = frozenset({"Typha", "Sparganium", "Schoenoplectus", "Scirpus",
                         "Eleocharis", "Phragmites"})
#: Impact at or above which a plant is a Top pick (about the top 40 of the
#: 250 Edmonton natives on the shipped data), and a Good pick.
TOP_PICK = 5
GOOD_PICK = 3

TOP, GOOD, LITTLE, POND, AWAY = ("Top pick", "Good pick", "Little recorded",
                                 "For a pond", "Not native here")
BANDS = (TOP, GOOD, LITTLE, POND, AWAY)

#: The keystone genera's sentences (reason words, §4.5).
_KEYSTONE_WORDS = {
    "Prunus": "Cherries", "Salix": "Willows", "Populus": "Poplars and aspens",
    "Betula": "Birches", "Quercus": "Oaks", "Solidago": "Goldenrods",
    "Symphyotrichum": "Asters", "Aster": "Asters", "Helianthus": "Sunflowers",
}
#: A buying caution for one plant (decision L9).
_BUY_CAUTION = {
    "Viburnum opulus": "Often sold as the European variety: ask for the "
                       "native one (var. americanum).",
}


@dataclass
class Assessment:
    impact: int
    band: str
    parts: dict = field(default_factory=dict)
    reasons: list = field(default_factory=list)
    cautions: list = field(default_factory=list)
    buy: str = ""             # the local_stock tier, "" outside the region
    tie: int = 0              # within one Impact, higher first


@dataclass
class Record:
    lep: set = field(default_factory=set)
    bees: set = field(default_factory=set)
    birds: set = field(default_factory=set)          # fruit or seed
    nectar_birds: set = field(default_factory=set)   # hummingbirds
    shelter_birds: set = field(default_factory=set)  # cover or a nest
    specialist: list = field(default_factory=list)


def load_records(conn=None) -> dict:
    """``{plant_id: Record}`` from documented edges to animals recorded in
    Alberta (no derived, companion or shared-fauna edges), read once."""
    own = conn is None
    if own:
        from src.db.plants import get_connection             # noqa: PLC0415
        conn = get_connection()
    out: dict = {}
    try:
        rows = conn.execute(
            "SELECT pf.plant_id, pf.relationship, f.taxon, f.id, "
            "pf.specificity, f.common_name FROM plant_fauna pf "
            "JOIN fauna f ON f.id = pf.fauna_id WHERE f.ab_native = 1")
        for pid, rel, taxon, fid, spec, fname in rows:
            r = out.setdefault(int(pid), Record())
            if rel == "larval_host" and taxon == "lepidoptera":
                r.lep.add(fid)
            if rel in ("nectar", "pollen") and taxon == "bee":
                r.bees.add(fid)
            if taxon == "bird":
                {"nectar": r.nectar_birds, "pollen": r.nectar_birds,
                 "cover": r.shelter_birds, "nesting": r.shelter_birds}.get(
                    rel, r.birds).add(fid)
            if spec == "specialist" and fname:
                r.specialist.append(fname)
    except Exception:                                      # noqa: BLE001
        return {}
    finally:
        if own:
            conn.close()
    return out


@functools.lru_cache(maxsize=1)
def _shared_records() -> dict:
    return load_records()


def clear_cache() -> None:
    _shared_records.cache_clear()
    impact_by_id.cache_clear()


def _steps(n: int, steps) -> int:
    return next((pts for at_least, pts in steps if n >= at_least), 0)


def _months(plant: Mapping) -> set:
    from src.habitat_score import parse_month_range          # noqa: PLC0415
    return set(parse_month_range(plant.get("bloom_period") or ""))


def _tokens(value) -> set:
    return {t.strip() for t in str(value or "").split(",") if t.strip()}


def _kinds(n: int, one: str, many: str) -> str:
    return one if n == 1 else many.format(n=n)


def assess(plant: Mapping, records: Optional[dict] = None, *,
           area_m2: Optional[float] = None, place: str = "") -> Assessment:
    """One plant's Impact, band and words. ``area_m2`` is a measured yard (no
    size words without one); ``place`` a region with a local list (its plants
    off the list go last)."""
    records = _shared_records() if records is None else records
    rec = records.get(int(plant.get("id") or 0)) or Record()
    sci = (plant.get("scientific_name") or "").strip()
    genus = sci.split()[0] if sci else ""
    ptype = (plant.get("plant_type") or "").strip()
    tags = _tokens(plant.get("permaculture_uses"))

    floor = 0
    if genus in _KEYSTONE_WORDS:
        floor = KEYSTONE_FLOOR["woody" if genus in WOODY_KEYSTONE else "herb"]
    n_lep, n_bees = len(rec.lep), len(rec.bees)
    n_birds = len(rec.birds | rec.shelter_birds)
    any_bird = n_birds or rec.nectar_birds or "bird_food" in tags
    parts = {
        "caterpillars": max(_steps(n_lep, CATERPILLAR_STEPS), floor),
        "specialist": 1 if rec.specialist else 0,
        "birds": 2 if n_birds >= BIRDS_MANY else 1 if any_bird else 0,
        "bees": _steps(n_bees, BEE_STEPS),
        "season": 1 if (_months(plant) & SHOULDER_MONTHS
                        and ptype not in WIND_POLLINATED
                        and genus not in WIND_GENERA) else 0,
    }
    impact = sum(parts.values())

    reasons = []
    if n_lep:
        reasons.append(_kinds(n_lep, "Caterpillar food for one kind of moth "
                              "or butterfly", "Caterpillar food for {n} kinds "
                              "of moth and butterfly"))
    if floor and n_lep < 6:
        reasons.append(f"{_KEYSTONE_WORDS[genus]} feed more kinds of "
                       "caterpillar than almost any other plant")
    if rec.specialist:
        reasons.append("Food that " + _join(sorted(set(rec.specialist))[:2])
                       + " depend on")
    if rec.birds:
        reasons.append(_kinds(len(rec.birds), "Berries or seed for one kind "
                              "of bird", "Berries or seed for {n} kinds of "
                              "bird"))
    elif "bird_food" in tags:
        reasons.append("Seed or berries for birds")
    if rec.shelter_birds:
        reasons.append(_kinds(len(rec.shelter_birds), "Shelter or a nest site "
                              "for one kind of bird", "Shelter or a nest site "
                              "for {n} kinds of bird"))
    if rec.nectar_birds:
        reasons.append("Nectar for hummingbirds")
    if n_bees >= 5:
        reasons.append(f"Visited by {n_bees} kinds of native bee")
    if parts["season"]:
        months = _months(plant)
        reasons.append("Flowers in April or May, when early bees need it"
                       if months & {4, 5} else
                       "Flowers into September, when little else does")
    if not reasons:
        reasons.append("Little is recorded yet about what it feeds")

    from src import local_stock, zoning                      # noqa: PLC0415
    wet = zoning.needs_standing_water(dict(plant))
    buy = local_stock.tier(sci, place) if place else local_stock.tier(sci)
    cautions = _cautions(plant, wet, area_m2, buy)

    band = TOP if impact >= TOP_PICK else GOOD if impact >= GOOD_PICK else LITTLE
    if band == TOP and buy == "hard":
        band = GOOD
    if wet:
        band = POND
    if place and not _native_around(sci, place):
        band = AWAY
    return Assessment(impact=impact, band=band, parts=parts, reasons=reasons,
                      cautions=cautions, buy=buy,
                      tie={"available": 2, "seed": 1}.get(buy, 0))


def _cautions(plant, wet, area_m2, buy) -> list:
    out = []
    water = _tokens(plant.get("water_needs"))
    if wet:
        out.append("Needs a pond or standing water")
    elif "high" in water and "low" not in water:
        out.append("Wants moist soil: a low spot, or water in dry spells")
    if area_m2:
        from src.llm_design import _too_big_for              # noqa: PLC0415
        if _too_big_for(dict(plant), float(area_m2)):
            h = plant.get("mature_height_meters")
            out.append(f"Grows to {float(h):g} m tall: too big for a yard this "
                       "size" if h else "Too big for a yard this size")
    spread = (plant.get("spread_habit") or "").strip()
    if spread == "aggressive_rhizomatous":
        out.append("Spreads by runners or suckers: give it room or an edge")
    elif spread == "self_seeding" or (plant.get("branching") or "") == "suckering":
        out.append("Suckers or self-seeds a little")
    if buy == "hard":
        out.append("Hard to find for sale")
    elif buy == "seed":
        out.append("Sold as seed, not as plants")
    if (plant.get("perennial_or_annual") or "") in ("annual", "biennial"):
        out.append("Lives one or two years and comes back from seed")
    if (plant.get("toxicity_pets") or "") == "high":
        out.append("Poisonous to pets if eaten")
    if (plant.get("toxicity_humans") or "") == "high":
        out.append("Poisonous to people if eaten")
    sci = (plant.get("scientific_name") or "").strip()
    if sci in _BUY_CAUTION:
        out.append(_BUY_CAUTION[sci])
    return out


def _native_around(sci: str, place: str) -> bool:
    from src import native_here                              # noqa: PLC0415
    try:
        return sci in native_here.native_names(place)
    except ValueError:
        return True


def _join(names) -> str:
    names = list(names)
    return " and ".join(names) if len(names) <= 2 else (
        ", ".join(names[:-1]) + " and " + names[-1])


def sort_key(a: Assessment, name: str = "") -> tuple:
    """Band, then Impact, then local stock, then the name."""
    return (BANDS.index(a.band), -a.impact, -a.tie, name.lower())


def rank(rows: Iterable[Mapping], *, records: Optional[dict] = None,
         area_m2: Optional[float] = None, place: str = "") -> list:
    """The same rows, best picks first. Never drops one."""
    rows = list(rows)
    records = _shared_records() if records is None else records
    keyed = [(sort_key(assess(r, records, area_m2=area_m2, place=place),
                       r.get("common_name") or ""), i, r)
             for i, r in enumerate(rows)]
    keyed.sort(key=lambda k: (k[0], k[1]))
    return [r for _k, _i, r in keyed]


#: The simple list's first screen (PR-3, §5): per ten rows four flowers,
#: three shrubs or trees, two grasses or sedges and one groundcover or vine,
#: each layer in rank order, so the first rows look like a garden.
_PATTERN = "FWFGWFCWFG"
_LAYER = {"wildflower": "F", "herb": "F", "fern": "F", "shrub": "W",
          "tree": "W", "grass": "G", "sedge": "G", "rush": "G",
          "groundcover": "C", "vine": "C"}


def interleave(ranked: Iterable[Mapping], *, rows: int = 20,
               place: str = "") -> list:
    """``ranked`` with its first ``rows`` drawn layer by layer; never drops
    or repeats one. A pond plant or one off the local list is never pulled
    forward, and a layer that runs out leaves its slot to the next."""
    ranked, records = list(ranked), _shared_records()
    pattern = (_PATTERN * (rows // len(_PATTERN) + 1))[:rows]
    want = {k: pattern.count(k) for k in "FWGC"}
    queues: dict = {k: [] for k in "FWGC"}
    for r in ranked:
        if all(len(queues[k]) >= want[k] for k in want):
            break
        layer = _LAYER.get(r.get("plant_type") or "")
        if (layer and len(queues[layer]) < want[layer]
                and assess(r, records, place=place).band not in (POND, AWAY)):
            queues[layer].append(r)
    first = [queues[k].pop(0) for k in pattern if queues[k]]
    taken = {id(r) for r in first}
    return first + [r for r in ranked if id(r) not in taken]


@functools.lru_cache(maxsize=1)
def impact_by_id() -> dict:
    """``{plant_id: Impact}`` for the whole catalogue, for sorts that rank a
    group of plants (the community library, PR-9)."""
    from src.db.plants import get_all_plants                 # noqa: PLC0415
    records = _shared_records()
    return {int(p["id"]): assess(p, records).impact for p in get_all_plants()}


def animals_per_plant() -> dict:
    """``{plant_id: distinct animals documented}``, for the "Animals supported"
    order (moved from ``plant_filters``, V3.26). Distinct animals, not
    relationship rows: one bee can take nectar and pollen."""
    try:
        from src.db.plants import get_connection             # noqa: PLC0415
        conn = get_connection()
    except Exception:                                      # noqa: BLE001
        return {}
    try:
        return {int(pid): int(n) for pid, n in conn.execute(
            "SELECT plant_id, COUNT(DISTINCT fauna_id) FROM plant_fauna "
            "GROUP BY plant_id")}
    except Exception:                                      # noqa: BLE001
        return {}
    finally:
        conn.close()


def band_counts(rows, **kw) -> dict:
    out = {b: 0 for b in BANDS}
    for r in rows:
        out[assess(r, **kw).band] += 1
    return out

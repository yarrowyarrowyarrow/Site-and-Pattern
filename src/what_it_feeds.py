"""
what_it_feeds.py — who a design feeds, when, and what people can harvest from
it (V3.08).

Design principle P3 — see docs/DESIGN_PHILOSOPHY.md.

The owner's answer to the V3.05 surface audit merged three pages into one
"what it feeds" page: Analysis › Bees ("I do want a per species analysis but
not one limited to just bees") and Planning's Wildlife and Harvest calendars
("in such a way that it is clear and distinct what is human forage and what is
animal forage"). This module is the page's arithmetic, Qt-free:

  * :func:`animals_fed` — every animal the design's plants feed or shelter,
    from the edges layer (``src/db/relationships.py``), most plants first;
  * :func:`animal_plan` — one animal, any animal: which of the design's plants
    serve it and how, which others in the catalogue would, and the months it
    finds food here;
  * :func:`month_by_month` — the year in three groups a month, for pollinators,
    for birds and **for people**, kept apart because a harvest is not forage;
  * :func:`eaters_line` — one line for a planted species: what eats it, and
    when ("feeds 12: 5 bees, 4 butterflies and moths, 3 birds · flowers
    Jul–Aug · fruit Sep"), the owner's "what eats this when", from
    :func:`plant_food` (one plant) or :func:`together` (a community, each
    animal once).

**When an animal eats** is read off the plant, because the catalogue records the
plant's season and not the animal's: nectar and pollen when it flowers, fruit
and seed when it fruits, a larval host while it is in leaf (May to September
here), except a bee's host plant, which is a flower record. Shelter (a nest
site, cover) is not food and adds no months.
Nothing is inferred from taxonomy that the edges layer does not already say.
"""

from __future__ import annotations

from typing import Callable, Iterable, Optional

from src.habitat_score import GROWING_SEASON_MONTHS, parse_month_range

#: Edge kinds that are food, in the order a row names them.
FOOD_KINDS = ("nectar", "pollen", "larval_host", "fruit_food", "seed_food")
#: Edge kinds that are shelter.
SHELTER_KINDS = ("nesting", "cover")

#: How each kind reads after a plant's name ("Wild Bergamot: nectar, pollen").
#: ``larval_host`` depends on the animal: :func:`kind_words`.
KIND_WORDS = {
    "nectar": "nectar", "pollen": "pollen", "larval_host": "larval host",
    "fruit_food": "fruit", "seed_food": "seed", "nesting": "nest site",
    "cover": "cover",
}

#: ``larval_host`` for the groups where it means something narrower. A bee's
#: is a host record (GloBI's *hostOf*, from a specimen's label), the flowers it
#: was collected from, not a plant its young eat the leaves of.
_LARVAL_WORDS = {"lepidoptera": "caterpillar host", "bee": "host plant"}

#: The catalogue's animal groups, in the order the page lists them.
GROUPS = (
    ("bee", "bee", "bees"),
    ("lepidoptera", "butterfly or moth", "butterflies and moths"),
    ("bird", "bird", "birds"),
    ("other_insect", "other insect", "other insects"),
    ("mammal", "mammal", "mammals"),
)
_PLURAL = {taxon: plural for taxon, _one, plural in GROUPS}
_ONE = {taxon: one for taxon, one, _plural in GROUPS}

#: A caterpillar eats leaves: the months a host here is in leaf.
LEAF_MONTHS = (5, 6, 7, 8, 9)

MONTH_ABBR = ("Jan", "Feb", "Mar", "Apr", "May", "Jun",
              "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")


def _connect(connect: Optional[Callable]):
    if connect is not None:
        return connect()
    from src.db.plants import get_connection
    return get_connection()


def group_words(taxon: str, n: int) -> str:
    """'1 bee', '3 butterflies and moths'."""
    if n == 1:
        return f"1 {_ONE.get(taxon, 'animal')}"
    return f"{n} {_PLURAL.get(taxon, 'animals')}"


def span(months: Iterable[int]) -> str:
    """'Jul–Aug', 'May', 'Apr–May, Aug' — runs of months, in order."""
    ms = sorted({int(m) for m in months if 1 <= int(m) <= 12})
    if not ms:
        return ""
    runs, start, prev = [], ms[0], ms[0]
    for m in ms[1:]:
        if m != prev + 1:
            runs.append((start, prev))
            start = m
        prev = m
    runs.append((start, prev))
    return ", ".join(MONTH_ABBR[a - 1] if a == b
                     else f"{MONTH_ABBR[a - 1]}–{MONTH_ABBR[b - 1]}"
                     for a, b in runs)


def kind_words(kind: str, taxon: str = "") -> str:
    """How an edge reads for this animal: a butterfly's larval host is a
    caterpillar host, a bee's is a host plant, a beetle's or a fly's is a
    larval host."""
    if kind == "larval_host":
        return _LARVAL_WORDS.get(taxon, KIND_WORDS[kind])
    return KIND_WORDS.get(kind, kind)


def months_for(kind: str, bloom: Iterable[int], fruit: Iterable[int],
               taxon: str = "") -> set:
    """The months a plant is food of this ``kind``: its bloom for nectar and
    pollen (and for a bee's host plant, which is its flowers), its fruit for
    fruit and seed, its leaves for larvae that eat the plant; none for
    shelter, which is not food."""
    if kind in ("nectar", "pollen") or (kind == "larval_host"
                                        and taxon == "bee"):
        return set(bloom)
    if kind in ("fruit_food", "seed_food"):
        return set(fruit)
    if kind == "larval_host":
        return set(LEAF_MONTHS)
    return set()


def _plant_rows(plant_ids, connect) -> dict:
    ids = sorted({int(p) for p in plant_ids})
    if not ids:
        return {}
    conn = _connect(connect)
    try:
        ph = ",".join("?" * len(ids))
        rows = conn.execute(
            f"SELECT id, common_name, plant_type, flower_form, bloom_period, "
            f"fruit_period, edible_parts FROM plants WHERE id IN ({ph})",
            ids).fetchall()
        return {r["id"]: dict(r) for r in rows}
    finally:
        conn.close()


def _fauna_rows(fauna_ids, connect) -> dict:
    ids = sorted({int(f) for f in fauna_ids})
    if not ids:
        return {}
    conn = _connect(connect)
    try:
        ph = ",".join("?" * len(ids))
        rows = conn.execute(
            f"SELECT id, common_name, scientific_name, taxon, icon "
            f"FROM fauna WHERE id IN ({ph})", ids).fetchall()
        return {r["id"]: dict(r) for r in rows}
    finally:
        conn.close()


def _animal_edges(plant_ids, connect) -> list:
    from src.db import relationships
    return [e for e in relationships.edges_among(
                plant_ids, kinds=FOOD_KINDS + SHELTER_KINDS,
                include_derived=False, connect=connect)
            if e.b_type == "fauna"]


def animals_fed(plant_ids: Iterable[int], *,
                connect: Optional[Callable] = None) -> list[dict]:
    """Every animal the plants feed or shelter: ``[{fauna_id, name,
    scientific_name, taxon, icon, plants: {plant_id: [kinds]}, food: bool}]``,
    most plants first, then by name. ``food`` is False for an animal the design
    only shelters."""
    by_animal: dict = {}
    for e in _animal_edges(plant_ids, connect):
        kinds = by_animal.setdefault(e.b_id, {}).setdefault(e.a_id, [])
        if e.kind not in kinds:
            kinds.append(e.kind)
    fauna = _fauna_rows(by_animal, connect)
    out = []
    for fid, plants in by_animal.items():
        row = fauna.get(fid)
        if row is None:
            continue
        out.append({
            "fauna_id": fid, "name": row["common_name"],
            "scientific_name": row["scientific_name"], "taxon": row["taxon"],
            "icon": row.get("icon") or "",
            "plants": plants,
            "food": any(k in FOOD_KINDS for ks in plants.values() for k in ks),
        })
    out.sort(key=lambda a: (-len(a["plants"]), a["name"].lower()))
    return out


def animal_plan(fauna_id: int, plant_ids: Iterable[int], *,
                elsewhere: int = 8,
                connect: Optional[Callable] = None) -> dict:
    """One animal against one design.

    ``{fauna: row, here: [{plant_id, name, kinds}], elsewhere: [...],
    months_here: [m…], gaps: [m…], no_host: bool}``: the design's plants that
    serve it and how, up to ``elsewhere`` catalogue plants that would (food
    first, documented records before derived ones), the months it finds food
    here, the growing-season months it does not, and, for a butterfly or moth,
    whether the design lacks the caterpillar host it needs while the catalogue
    has one."""
    present = {int(p) for p in plant_ids}
    conn = _connect(connect)
    try:
        frow = conn.execute(
            "SELECT id, common_name, scientific_name, taxon, icon, description "
            "FROM fauna WHERE id = ?", (int(fauna_id),)).fetchone()
        kinds = FOOD_KINDS + SHELTER_KINDS
        ph = ",".join("?" * len(kinds))
        rows = conn.execute(
            f"SELECT kind, a_id, evidence FROM relationship_edges "
            f"WHERE b_type = 'fauna' AND b_id = ? AND kind IN ({ph})",
            [int(fauna_id), *kinds]).fetchall()
    finally:
        conn.close()
    if frow is None:
        return {}
    by_plant: dict = {}
    documented: set = set()
    for r in rows:
        ks = by_plant.setdefault(r["a_id"], [])
        if r["kind"] not in ks:
            ks.append(r["kind"])
        if (r["evidence"] or "") != "derived":
            documented.add(r["a_id"])
    plants = _plant_rows(by_plant, connect)

    def entry(pid):
        p = plants.get(pid) or {}
        order = {k: i for i, k in enumerate(kinds)}
        return {"plant_id": pid, "name": p.get("common_name", f"#{pid}"),
                "kinds": sorted(by_plant[pid], key=order.get)}

    here = sorted((entry(pid) for pid in by_plant if pid in present),
                  key=lambda e: e["name"].lower())
    others = [entry(pid) for pid in by_plant if pid not in present]
    others.sort(key=lambda e: (not any(k in FOOD_KINDS for k in e["kinds"]),
                               e["plant_id"] not in documented,
                               e["name"].lower()))
    months: set = set()
    for e in here:
        p = plants.get(e["plant_id"]) or {}
        bloom = parse_month_range(p.get("bloom_period") or "")
        fruit = parse_month_range(p.get("fruit_period") or "")
        for k in e["kinds"]:
            months |= months_for(k, bloom, fruit, frow["taxon"])
    gaps = [m for m in GROWING_SEASON_MONTHS if m not in months] if here else []
    hosts_here = any("larval_host" in e["kinds"] for e in here)
    hosts_known = any("larval_host" in ks for ks in by_plant.values())
    return {
        "fauna": dict(frow), "here": here, "elsewhere": others[:elsewhere],
        "elsewhere_total": len(others), "months_here": sorted(months),
        "gaps": gaps,
        "no_host": (frow["taxon"] == "lepidoptera" and hosts_known
                    and not hosts_here),
    }


def month_by_month(plant_ids: Iterable[int], *,
                   connect: Optional[Callable] = None) -> dict:
    """The year for one design, each month in three groups kept apart:
    ``{"months": [{month, pollinators: [names], birds: [names],
    people: [(name, part)]}], "gaps": [m…]}``.

    *Pollinators* are the plants in flower whose flowers are forage (a grass,
    sedge or rush flowers for the wind, ``forage_calendar.is_pollinator_forage``);
    *birds* the plants in fruit; *people* the plants with an edible part
    recorded, in their harvest months (the planting calendar's where it has
    them, else the fruit period). ``gaps`` are the growing-season months with
    no pollinator bloom."""
    from src.forage_calendar import is_pollinator_forage
    plants = _plant_rows(plant_ids, connect)
    harvest: dict = {}
    if plants:
        conn = _connect(connect)
        try:
            ph = ",".join("?" * len(plants))
            for r in conn.execute(
                    f"SELECT plant_id, month FROM planting_calendar "
                    f"WHERE status = 'harvest' AND plant_id IN ({ph})",
                    sorted(plants)):
                harvest.setdefault(r["plant_id"], set()).add(r["month"])
        except Exception:                                  # noqa: BLE001
            harvest = {}
        finally:
            conn.close()
    months = [{"month": m, "pollinators": [], "birds": [], "people": []}
              for m in range(1, 13)]
    for pid, p in plants.items():
        name = p["common_name"]
        bloom = parse_month_range(p.get("bloom_period") or "")
        fruit = parse_month_range(p.get("fruit_period") or "")
        if bloom and is_pollinator_forage(p):
            for m in bloom:
                months[m - 1]["pollinators"].append(name)
        for m in fruit:
            months[m - 1]["birds"].append(name)
        part = (p.get("edible_parts") or "").strip()
        if part:
            for m in sorted(harvest.get(pid) or fruit):
                months[m - 1]["people"].append((name, part))
    for month in months:
        month["pollinators"] = sorted(set(month["pollinators"]), key=str.lower)
        month["birds"] = sorted(set(month["birds"]), key=str.lower)
        month["people"] = sorted(set(month["people"]),
                                 key=lambda np: np[0].lower())
    gaps = [m for m in GROWING_SEASON_MONTHS
            if not months[m - 1]["pollinators"]]
    return {"months": months, "gaps": gaps}


def plant_food(plant_ids: Iterable[int], *,
               connect: Optional[Callable] = None) -> dict:
    """``{plant_id: {"animals": {taxon: n}, "bloom": [m…], "fruit": [m…]}}``:
    for each plant, how many animals of each group it feeds (food edges only),
    and when it flowers and fruits."""
    plants = _plant_rows(plant_ids, connect)
    out = {pid: {"animals": {}, "bloom": parse_month_range(
                     p.get("bloom_period") or ""),
                 "fruit": parse_month_range(p.get("fruit_period") or "")}
           for pid, p in plants.items()}
    fed: dict = {}
    for e in _animal_edges(plants, connect):
        if e.kind in FOOD_KINDS:
            fed.setdefault(e.a_id, set()).add(e.b_id)
    fauna = _fauna_rows({f for fs in fed.values() for f in fs}, connect)
    for pid, fids in fed.items():
        if pid not in out:
            continue
        counts: dict = {}
        for fid in fids:
            taxon = (fauna.get(fid) or {}).get("taxon")
            if taxon:
                counts[taxon] = counts.get(taxon, 0) + 1
        out[pid]["animals"] = counts
    return out


def together(plant_ids: Iterable[int], *,
             connect: Optional[Callable] = None) -> dict:
    """What a group of plants feeds between them, in :func:`plant_food`'s
    shape: each animal counted once however many members feed it, and the
    months any member flowers or fruits. A community's line on Planted."""
    plants = _plant_rows(plant_ids, connect)
    bloom: set = set()
    fruit: set = set()
    for p in plants.values():
        bloom.update(parse_month_range(p.get("bloom_period") or ""))
        fruit.update(parse_month_range(p.get("fruit_period") or ""))
    fed = {e.b_id for e in _animal_edges(plants, connect)
           if e.kind in FOOD_KINDS}
    counts: dict = {}
    for row in _fauna_rows(fed, connect).values():
        taxon = row.get("taxon")
        if taxon:
            counts[taxon] = counts.get(taxon, 0) + 1
    return {"animals": counts, "bloom": sorted(bloom), "fruit": sorted(fruit)}


def eaters_line(food: dict) -> str:
    """'feeds 12: 5 bees, 4 butterflies and moths, 3 birds · flowers Jul–Aug ·
    fruit Sep'. A plant with nothing recorded says so ("no animal recorded"),
    which is a gap in the data more often than a fact about the plant (P9)."""
    counts = food.get("animals") or {}
    total = sum(counts.values())
    parts = []
    if total:
        groups = ", ".join(group_words(t, counts[t])
                           for t, _one, _plural in GROUPS if counts.get(t))
        parts.append(f"feeds {total}: {groups}")
    else:
        parts.append("no animal recorded")
    if food.get("bloom"):
        parts.append(f"flowers {span(food['bloom'])}")
    if food.get("fruit"):
        parts.append(f"fruit {span(food['fruit'])}")
    return " · ".join(parts)

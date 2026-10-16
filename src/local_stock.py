"""
local_stock.py — whether a native plant can be bought around a region, from
the region's own nurseries' stock (V3.25; levels redrawn V3.26).

Design principle P9 — see docs/DESIGN_PHILOSOPHY.md.

The owner, V3.25: the levels must be "based on actual stock that is available
at these local retailers", and a restoration plant one would have trouble
finding even as seed is never in the top level. Then V3.26, with three of
Arnica Wildflowers' 2026 market lists in hand: "There are so few native plant
retailers in Edmonton … These ones at Arnica should be listed as 'available'
rather than common." With one or two retailers, "common" claimed more than any
list can say, so the levels say only what the lists say:

* ``available``: on a region nursery's plant list (or the owner says so);
* ``seed``: on a list only as seed;
* ``hard``: a restoration plant no list carries (the catalogue's ``rare``,
  each with its reason in ``sourcing_notes``), or the owner says so;
* ``unlisted``: on none of the lists on file. **Not the same as hard to find**
  (P9): a nursery may grow it to order, and the lists are one nursery's.

The evidence lives in the pack, ``data/regions/<key>/stock.json``: ``lists``
(what a supplier listed, when, and as plants or seed, by scientific name; the
transcriptions behind them are in ``tools/stock_review/lists/``) and
``rulings`` (the owner's answer for a species, which wins). Until V3.25 the
tiers were ``availability_class``, the author's V3.14 guess at what Alberta
garden centres carried; a plant no list covers keeps that guess for the
generator's ranking only, and never as high as a plant a list shows.

Only the region's own natives are ranked: a Calgary nursery's list counts for
Edmonton, but only for the plants on Edmonton's list (the owner: not
"recommending plants outside of the Edmonton region"). Anything else has no
tier here (``""``).

Read from file, not seeded: a new list or answer needs no schema bump. Qt-free.
"""

from __future__ import annotations

import functools
import json
import os
from typing import Mapping, Optional

TIERS = ("available", "seed", "hard", "unlisted")
LABELS = {
    "available": "Available",
    "seed": "Seed only",
    "hard": "Hard to find",
    "unlisted": "Not on a local list",
}
TIPS = {
    "available": "On a list of plants a native-plant nursery near you sells.",
    "seed": "Sold as seed, not as grown plants.",
    "hard": "A restoration plant few nurseries grow.",
    "unlisted": "On none of the nursery lists on file. It may still be sold "
                "or grown to order: ask.",
}
#: What an answer written before V3.26 means now.
_OLD_TIERS = {"common": "available", "sometimes": "available",
              "unchecked": "unlisted"}
FORMS = ("plants", "seed")
SCHEMA = 1

_document: Optional[dict] = None


def path(key: str) -> str:
    from src.resources import resource_path                  # noqa: PLC0415
    return os.path.join(resource_path("data"), "regions", key, "stock.json")


def set_document(key: Optional[str], doc: Optional[dict] = None) -> None:
    """Tests: use ``doc`` as region ``key``'s stock; ``set_document(None)``
    goes back to the files."""
    global _document
    _document = None if key is None else {**(_document or {}), key: doc}
    _load.cache_clear()
    tiers.cache_clear()


@functools.lru_cache(maxsize=8)
def _load(key: str) -> dict:
    if _document is not None and key in _document:
        return _document[key] or {}
    try:
        with open(path(key), encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {}


def validate(doc: Mapping, suppliers=(), catalogue=None) -> list:
    """Problems with a stock document: unknown fields, a supplier the pack does
    not name, a form or tier outside the vocabulary, a name not in the
    catalogue (``catalogue``, a set of scientific names, when given)."""
    errs = []
    extra = set(doc) - {"schema", "key", "about", "lists", "rulings"}
    if extra:
        errs.append(f"unknown fields: {sorted(extra)}")
    for i, lst in enumerate(doc.get("lists") or []):
        extra = set(lst) - {"supplier", "seen", "form", "source", "species"}
        if extra:
            errs.append(f"list {i}: unknown fields {sorted(extra)}")
        if suppliers and lst.get("supplier") not in suppliers:
            errs.append(f"list {i}: supplier {lst.get('supplier')!r} is not "
                        "one of the pack's nurseries")
        if lst.get("form", "plants") not in FORMS:
            errs.append(f"list {i}: form {lst.get('form')!r}")
        if not str(lst.get("seen") or "").strip():
            errs.append(f"list {i}: no date seen")
        for name in lst.get("species") or []:
            if catalogue is not None and name not in catalogue:
                errs.append(f"list {i}: {name!r} is not in the catalogue")
    for name, r in (doc.get("rulings") or {}).items():
        if _OLD_TIERS.get((r or {}).get("tier"), (r or {}).get("tier")) \
                not in TIERS[:-1]:
            errs.append(f"ruling {name!r}: tier {(r or {}).get('tier')!r}")
        if set(r or {}) - {"tier", "on"}:
            errs.append(f"ruling {name!r}: only a tier and a date are kept")
        if catalogue is not None and name not in catalogue:
            errs.append(f"ruling {name!r} is not in the catalogue")
    return errs


def restoration_plant(row: Mapping) -> bool:
    """A plant few grow: the catalogue ranks it ``rare``, with its reason in
    ``sourcing_notes``."""
    return ((row or {}).get("availability_class") or "").strip() == "rare"


def derive(doc: Mapping, natives, restoration=frozenset()) -> dict:
    """``{scientific name: tier}`` for every name in ``natives`` (the region's
    list), from a stock document. ``restoration`` names the plants that are
    hard to find when no list carries them."""
    lists = list(doc.get("lists") or [])
    on_plants = {n for l in lists if l.get("form", "plants") == "plants"
                 for n in (l.get("species") or ())}
    on_seed = {n for l in lists if l.get("form") == "seed"
               for n in (l.get("species") or ())}
    rulings = doc.get("rulings") or {}
    out = {}
    for name in natives:
        if name in on_plants:
            tier = "available"
        elif name in on_seed:
            tier = "seed"
        elif name in restoration:
            tier = "hard"
        else:
            tier = "unlisted"
        ruled = (rulings.get(name) or {}).get("tier")
        ruled = _OLD_TIERS.get(ruled, ruled)
        if ruled in TIERS:
            tier = ruled
        out[name] = tier
    return out


@functools.lru_cache(maxsize=8)
def tiers(key: str = "") -> dict:
    """``{scientific name: tier}`` for region ``key`` (the default pack when
    empty), every native on its list ranked."""
    from src import native_here, region                      # noqa: PLC0415
    key = key or region.default().key
    try:
        natives = native_here.native_names(key)
    except ValueError:
        return {}
    return derive(_load(key), natives, _restoration_names())


@functools.lru_cache(maxsize=1)
def _restoration_names() -> frozenset:
    try:
        from src.db.plants import get_all_plants             # noqa: PLC0415
        return frozenset((p.get("scientific_name") or "").strip()
                         for p in get_all_plants() if restoration_plant(p))
    except Exception:                                      # noqa: BLE001
        return frozenset()


def tier(plant, key: str = "") -> str:
    """A plant's tier around region ``key``, ``""`` when it is not one of the
    region's natives."""
    name = plant if isinstance(plant, str) else (
        (plant or {}).get("scientific_name") or "")
    return tiers(key).get(name.strip(), "")


def listings(plant, key: str = "") -> dict:
    """``{supplier: [(seen, form), …]}``, oldest list first: every list that
    carries the plant."""
    from src import region                                   # noqa: PLC0415
    name = plant_name(plant)
    lists = _load(key or region.default().key).get("lists") or []
    out: dict = {}
    for l in sorted(lists, key=lambda l: str(l.get("seen") or "")):
        if name in (l.get("species") or ()) and l.get("supplier"):
            out.setdefault(l["supplier"], []).append(
                (str(l.get("seen") or ""), l.get("form", "plants")))
    return out


def suppliers(plant, key: str = "") -> list:
    """``(supplier, newest seen, form)`` for each supplier whose lists carry
    the plant, newest first."""
    rows = [(s, seen[-1][0], seen[-1][1])
            for s, seen in listings(plant, key).items()]
    return sorted(rows, key=lambda r: r[1], reverse=True)


#: The old tier's ease (``sourcing.ease``) for a plant no list covers, capped:
#: only a list shows a plant can be bought.
_OLD_EASE = {"big_box": 2, "garden_centre": 2, "native_specialist": 1,
             "seed_or_plug": 1, "rare": 0}
_EASE = {"available": 2, "seed": 1, "hard": 0}


def ease(row: Mapping, key: str = "") -> int:
    """2 on a nursery's list, 1 sold as seed, 0 hard to find. A plant no list
    covers keeps its old tier's ease, at most 1."""
    t = tier(row, key)
    if t in _EASE:
        return _EASE[t]
    old = _OLD_EASE.get(((row or {}).get("availability_class") or "").strip(), 1)
    return min(old, 1)


def easy_to_find(row: Mapping, key: str = "") -> bool:
    """What *Easy to find* and the budget goal keep: on a nursery's plant
    list, or, where no list covers it, not known to be seed-only or rare."""
    t = tier(row, key)
    if t == "available":
        return True
    if t in ("seed", "hard"):
        return False
    return ((row or {}).get("availability_class") or "").strip() not in (
        "seed_or_plug", "rare")


_MONTHS = ("January", "February", "March", "April", "May", "June", "July",
           "August", "September", "October", "November", "December")


def _when(seen: list) -> str:
    """"its May, June and August 2026 lists" from the dates seen."""
    months, years = [], []
    for date, _form in seen:
        parts = date.split("-")
        if len(parts) >= 2 and parts[1].isdigit():
            m = _MONTHS[int(parts[1]) - 1]
            if m not in months:
                months.append(m)
        if parts and parts[0] not in years:
            years.append(parts[0])
    if not months:
        return ""
    word = "list" if len(seen) == 1 else "lists"
    return f"its {_join(months)} {_join(years)} {word}"


def clause(plant, key: str = "") -> str:
    """What a plant page says about buying it around the region, ``""`` when
    the plant is not one of the region's natives."""
    from src import region                                   # noqa: PLC0415
    r = region.regions().get(key) if key else region.default()
    r = r or region.default()
    t = tier(plant, r.key)
    lists = listings(plant, r.key)
    plants = {s: [x for x in v if x[1] == "plants"] for s, v in lists.items()}
    plants = {s: v for s, v in plants.items() if v}
    if t == "available":
        if not plants:
            return f"Available from {r.short} native-plant nurseries."
        return "Available: " + "; ".join(
            f"{s} (on {_when(v)})" if _when(v) else s
            for s, v in plants.items()) + "."
    if t == "seed":
        seeds = [s for s, v in lists.items() if any(f == "seed" for _d, f in v)]
        return "Sold as seed" + (f" ({_join(seeds)})" if seeds else "") + "."
    if t == "hard":
        if not lists and plant_name(plant) in _restoration_names():
            return "Hard to find: a restoration plant few nurseries grow."
        return f"Hard to find at {r.short} native-plant nurseries."
    if t == "unlisted":
        return (f"Not on any {r.short} native-plant nursery list on file. It "
                "may still be sold or grown to order: ask.")
    return ""


def plant_name(plant) -> str:
    return (plant if isinstance(plant, str) else (
        (plant or {}).get("scientific_name") or "")).strip()


def _join(names) -> str:
    names = list(names)
    if len(names) <= 2:
        return " and ".join(names)
    return ", ".join(names[:-1]) + " and " + names[-1]


def counts(key: str = "") -> dict:
    """How many of the region's natives are in each tier."""
    out = {t: 0 for t in TIERS}
    for t in tiers(key).values():
        out[t] = out.get(t, 0) + 1
    return out

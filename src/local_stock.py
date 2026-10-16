"""
local_stock.py — how easy a native plant is to buy around a region, from the
region's own nurseries' stock (V3.25).

Design principle P9 — see docs/DESIGN_PHILOSOPHY.md.

The owner, V3.25: the levels must be "based on actual stock that is available
at these local retailers". Yarrow, prairie crocus, wild bergamot and giant
hyssop are common; harebell and prairie sage are sold, but only now and then;
and "plants that are edge restoration cases and whom one would have trouble
finding seed let alone grown plants should not be included in the most common
tier." Until V3.25 the tiers were ``availability_class``, the author's V3.14
judgment of what Alberta garden centres carried, made without any catalogue.

The evidence lives in the pack, ``data/regions/<key>/stock.json``:

* ``lists``: what a supplier listed, when, and in what form (``plants`` or
  ``seed``), by scientific name. One supplier may have many lists (a spring
  and an autumn list, this year and last), which is what tells *always* from
  *once in a while*.
* ``rulings``: the owner's answer for a species, which wins.

Every species gets one tier, easiest first:

* ``common``: listed as plants by at least two of the region's suppliers, in
  at least half of their lists, or the owner says so;
* ``sometimes``: listed as plants by one supplier, or only some of the time;
* ``seed``: listed only as seed;
* ``hard``: on no list while lists from :data:`LISTS_TO_SAY_ABSENT` suppliers
  are on file, or a restoration plant (below);
* ``unchecked``: no list and no answer covers it yet.

**A restoration plant is never** ``common`` (the owner's rule): a species the
catalogue already ranks ``rare``, each for a reason written into its
``sourcing_notes`` (orchids, hemiparasites, bog plants, mountain or far-north
ranges, few records). **Unchecked is not hard to find** (P9): with no list on
file the app says it has not checked, and ranks the plant by its old tier but
never as high as a plant the stock shows is common.

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

TIERS = ("common", "sometimes", "seed", "hard", "unchecked")
LABELS = {
    "common": "Common",
    "sometimes": "Sometimes available",
    "seed": "Seed only",
    "hard": "Hard to find",
    "unchecked": "Not checked yet",
}
TIPS = {
    "common": "Carried as plants by most of the region's native-plant "
              "nurseries, most years.",
    "sometimes": "Carried by one nursery, or only some years.",
    "seed": "Sold as seed, not as grown plants.",
    "hard": "On none of the nursery lists checked, or a restoration plant few "
            "grow.",
    "unchecked": "No nursery list or answer covers it yet.",
}
FORMS = ("plants", "seed")
#: How many suppliers' lists must be on file before a plant missing from all
#: of them is called hard to find rather than unchecked.
LISTS_TO_SAY_ABSENT = 3
#: The share of a supplier's lists a plant must be on to count as regular.
REGULAR_SHARE = 0.5
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
        if (r or {}).get("tier") not in TIERS[:-1]:
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
    list), from a stock document. ``restoration`` names the plants that may
    never be ``common``."""
    lists = [l for l in (doc.get("lists") or [])]
    by_supplier: dict = {}
    for l in lists:
        by_supplier.setdefault(l.get("supplier") or "", []).append(l)
    rulings = doc.get("rulings") or {}
    out = {}
    for name in natives:
        tier = _from_lists(name, by_supplier)
        ruled = (rulings.get(name) or {}).get("tier")
        if ruled in TIERS:
            tier = ruled
        elif tier == "unchecked" and name in restoration:
            tier = "hard"
        if tier == "common" and name in restoration:
            tier = "sometimes"
        out[name] = tier
    return out


def _from_lists(name: str, by_supplier: Mapping) -> str:
    plants_regular = plants_any = seed_any = 0
    for supplier, lists in by_supplier.items():
        plants = [l for l in lists if l.get("form", "plants") == "plants"]
        named = [l for l in plants if name in (l.get("species") or ())]
        if named:
            plants_any += 1
            if len(named) / len(plants) >= REGULAR_SHARE:
                plants_regular += 1
        if any(name in (l.get("species") or ()) for l in lists
               if l.get("form") == "seed"):
            seed_any += 1
    if plants_regular >= 2:
        return "common"
    if plants_any:
        return "sometimes"
    if seed_any:
        return "seed"
    if len([s for s in by_supplier if s]) >= LISTS_TO_SAY_ABSENT:
        return "hard"
    return "unchecked"


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


def suppliers(plant, key: str = "") -> list:
    """The suppliers whose lists carry the plant, newest list first, as
    ``(supplier, seen, form)``."""
    from src import region                                   # noqa: PLC0415
    name = plant if isinstance(plant, str) else (
        (plant or {}).get("scientific_name") or "")
    lists = _load(key or region.default().key).get("lists") or []
    seen: dict = {}
    for l in sorted(lists, key=lambda l: str(l.get("seen") or ""),
                    reverse=True):
        if name.strip() in (l.get("species") or ()):
            seen.setdefault(l.get("supplier") or "",
                            (l.get("supplier") or "", str(l.get("seen") or ""),
                             l.get("form", "plants")))
    return [v for k, v in seen.items() if k]


#: The old tier's ease (``sourcing.ease``) for a plant the stock does not
#: cover, capped: only stock shows a plant is common.
_OLD_EASE = {"big_box": 2, "garden_centre": 2, "native_specialist": 1,
             "seed_or_plug": 1, "rare": 0}
_EASE = {"common": 2, "sometimes": 1, "seed": 1, "hard": 0}


def ease(row: Mapping, key: str = "") -> int:
    """2 common, 1 sold now and then or as seed, 0 hard to find. A plant the
    stock does not cover keeps its old tier's ease, at most 1."""
    t = tier(row, key)
    if t in _EASE:
        return _EASE[t]
    old = _OLD_EASE.get(((row or {}).get("availability_class") or "").strip(), 1)
    return min(old, 1)


def easy_to_find(row: Mapping, key: str = "") -> bool:
    """What *Easy to find* and the budget goal keep: sold as plants (common or
    sometimes), or, where the stock is silent, not known to be seed-only or
    rare."""
    t = tier(row, key)
    if t in ("common", "sometimes"):
        return True
    if t in ("seed", "hard"):
        return False
    return ((row or {}).get("availability_class") or "").strip() not in (
        "seed_or_plug", "rare")


def clause(plant, key: str = "") -> str:
    """What a plant page says about buying it around the region, ``""`` when
    the stock does not cover it."""
    from src import region                                   # noqa: PLC0415
    r = region.regions().get(key) if key else region.default()
    r = r or region.default()
    t = tier(plant, r.key)
    who = suppliers(plant, r.key)
    names = [s for s, _seen, form in who if form == "plants"]
    if t == "common":
        return (f"Common at {r.short} native-plant nurseries"
                + (f" ({_join(names)})" if names else "") + ".")
    if t == "sometimes":
        return ("Sold now and then" + (f", by {_join(names)}" if names else
                                       f" by {r.short} native-plant nurseries")
                + ": check before you go.")
    if t == "seed":
        seeds = [s for s, _seen, form in who if form == "seed"]
        return "Sold as seed" + (f" ({_join(seeds)})" if seeds else "") + "."
    if t == "hard":
        if not who and plant_name(plant) in _restoration_names():
            return "Hard to find: a restoration plant few nurseries grow."
        return f"Hard to find at {r.short} native-plant nurseries."
    if t == "unchecked":
        return (f"Not yet checked against {r.short} nurseries' stock.")
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

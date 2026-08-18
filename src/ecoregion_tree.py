"""ecoregion_tree.py — the vocabulary has three levels, not one.

Design principle P2 (the best designs disappear into their context) and P9
(ship confidence, never false precision) — see docs/DESIGN_PHILOSOPHY.md.

WHY THIS EXISTS
-------------------------------------------------------------------------------
V2.67 replaced six hand-traced regions with twenty-four surveyed ones, and
twenty-four is too many to put in one list. The author's answer was the right
one: *"tabs, subtabs and subsubtabs to account for the 3 levels. This way we
don't have one overwhelming menu with 24 items."*

The three levels are not an interface invention. They are what the
classification already is, and the polygon file has carried all three since the
day it was adopted:

    ecozone      6   the physiographic system      Boreal Plains
    ecoregion   24   the unit inside it            Mid-Boreal Uplands
    subregion   21   Alberta's own finer split     Central Mixedwood

So the first choice is six-way instead of twenty-four-way, and the Alberta
subregions — Dry Mixedgrass, Northern Fescue, Upper Foothills — become
reachable for the first time. They were already in the data and nothing had
ever offered them.

THE ONE RULE WORTH ARGUING ABOUT: MATCHING RUNS ALONG A LINEAGE
-------------------------------------------------------------------------------
Filtering for Mid-Boreal Uplands also shows plants tagged only "Boreal Plains",
and filtering for Boreal Plains shows plants tagged with any region inside it.
Both directions, deliberately.

Downward is uncontroversial: a plant recorded in Mid-Boreal Uplands is in the
Boreal Plains, definitionally.

Upward is the judgement call. A plant tagged only at the ecozone is a plant
whose evidence was never finer than that; whether it grows in *this* ecoregion
is unknown, not no. Hiding it would silently drop a probably-suitable native
from somebody's search, and the whole point of the filter is to find natives.
Showing it risks a plant that turns out not to belong. For a planting
recommendation that is the better error, and it is the direction P9 points:
absence of evidence is not evidence of absence.

The alternative — only matching exactly — would have made the migrated
heuristic tags useless the moment they were written, since most of them are
ecozone-level by construction (see ``scripts/migrate_ecoregion_tags.py``).
"""

from __future__ import annotations

import json
from functools import lru_cache

from src.resources import resource_path

__all__ = ["ECOZONE", "ECOREGION", "SUBREGION", "descendants_of", "level_of",
           "lineage_keys", "subregions_in", "tree", "ecozones", "regions_in"]

#: The three levels, coarsest first. Strings rather than an enum because they
#: end up in a widget's item data and a test's assertion message.
ECOZONE = "ecozone"
ECOREGION = "ecoregion"
SUBREGION = "subregion"

LEVELS = (ECOZONE, ECOREGION, SUBREGION)

#: Key prefixes, and the reason they exist.
#:
#: **"Athabasca Plain" is an ELC ecoregion on the Boreal Shield in Saskatchewan
#: AND an Alberta natural subregion, and they are different ground.** The
#: rebuild brief warned about exactly this pair and the pipeline was careful to
#: join the two frameworks spatially rather than by name — and then the first
#: version of this module slugged both to ``athabasca_plain`` and collided them
#: anyway, one namespace further along. The symptom was that asking for the
#: lineage of Mid-Boreal Uplands returned a Boreal Shield region, because
#: walking down to the *subregion* Athabasca Plain and back up reached the
#: *ecoregion* of the same name.
#:
#: Ecoregion keys keep their bare form: they are already written into the
#: shipped polygon file, into every species tag and into the website's URLs.
#: The two levels that are derived here get a prefix, so the collision is not
#: available to make.
_ZONE_PREFIX = "zone_"
_SUB_PREFIX = "sub_"


def zone_key(name: str) -> str:
    """Namespaced key for an ecozone."""
    return _ZONE_PREFIX + slug(name) if name else ""


def subregion_key(name: str) -> str:
    """Namespaced key for an Alberta natural subregion."""
    return _SUB_PREFIX + slug(name) if name else ""


def slug(name: str) -> str:
    """``"Mid-Boreal Uplands"`` -> ``"mid_boreal_uplands"``.

    The same transform ``tools/ecoregions/adopt.py`` uses when it writes the
    polygon file, so an ecozone or subregion key is derivable here rather than
    needing to be stored a second time.
    """
    out, last = [], True
    for char in (name or "").lower():
        if char.isalnum():
            out.append(char)
            last = False
        elif not last:
            out.append("_")
            last = True
    return "".join(out).strip("_")


@lru_cache(maxsize=1)
def _index() -> dict:
    """Everything the tree needs, read once from the polygon file.

    Returns ``{"zones": {key: name}, "regions": {key: (name, zone_key)},
    "subs": {key: (name, region_keys)}, "children": {...}}``.

    Built from the file rather than declared beside it, for the reason
    ``src/ecoregion.py`` gives at length: the polygon file *is* the vocabulary,
    and a second copy is a second thing to keep in step. The hand-typed copy
    that did exist was already wrong about one region's ecozone.
    """
    zones: dict = {}
    regions: dict = {}
    subs: dict = {}
    shares: dict = {}
    try:
        with open(resource_path("data", "ecoregions_canada.geojson"),
                  encoding="utf-8") as handle:
            features = (json.load(handle) or {}).get("features") or []
    except Exception:                                             # noqa: BLE001
        features = []

    for feature in features:
        props = feature.get("properties") or {}
        region_key = (props.get("key") or "").strip()
        region_name = (props.get("name") or "").strip()
        zone_name = (props.get("ecozone") or "").strip()
        sub_name = (props.get("ab_subregion") or "").strip()
        if not region_key:
            continue
        zkey = zone_key(zone_name)
        if zkey:
            zones.setdefault(zkey, zone_name)
        regions.setdefault(region_key, (region_name or region_key, zkey))
        if sub_name:
            key = subregion_key(sub_name)
            name, parents = subs.get(key, (sub_name, []))
            if region_key not in parents:
                parents = parents + [region_key]
            subs[key] = (name, parents)
            try:
                share = float(props.get("sub_share") or 0.0)
            except (TypeError, ValueError):
                share = 0.0
            shares.setdefault(key, {})
            shares[key][region_key] = shares[key].get(region_key, 0.0) + share
    return {"zones": zones, "regions": regions, "subs": subs, "shares": shares}


#: A subregion accounted for at least this much by one ecoregion is treated as
#: sitting inside it. Same two thirds as ``scripts/migrate_ecoregion_tags.py``,
#: and for the same reason: at a half, a 51/49 split gets reported as a fact.
DOMINANT_SHARE = 0.66


def subregion_parents(key: str) -> list:
    """``[(ecoregion key, share), ...]`` for one subregion, largest first.

    **The Alberta subregions are not a third tier of the ELC tree**, and this
    is the function that stops the site pretending they are. Measured from the
    shipped polygons: 12 of the 21 sit ≥90% inside a single ecoregion, but
    Montane is 42% Northern Continental Divide, Central Mixedwood is 31% of
    Mid-Boreal Uplands spread across *nine* ecoregions, and Athabasca Plain is
    46% of its own namesake. Two classifications of the same ground, agreeing
    in most places and crossing in the mountains and the mid-boreal.

    The first cut of the website's third level filed a subregion under
    whichever parent sorted first alphabetically, which put **Montane inside
    Aspen Parkland** — 6% of it — on a public page. Shares come from
    ``sub_share`` in the polygon file, written by ``tools/ecoregions/adopt.py``
    where an equal-area projection is available.
    """
    rows = (_index()["shares"].get(key) or {}).items()
    return sorted(rows, key=lambda kv: (-kv[1], kv[0]))


def dominant_parent(key: str) -> str:
    """The one ecoregion that accounts for a subregion, or ``""`` when none
    does. Empty is a real answer: it means the subregion genuinely spans
    several, and the page should say so rather than name one."""
    rows = subregion_parents(key)
    return rows[0][0] if rows and rows[0][1] >= DOMINANT_SHARE else ""


def ecozones() -> list:
    """``(key, name)`` per ecozone, in the polygon file's display order."""
    index = _index()
    seen, out = set(), []
    # `zkey` rather than `zone_key`: that name is a function in this module and
    # shadowing it inside a loop is the kind of thing that works until someone
    # adds a call three lines down.
    for _region_key, (_name, zkey) in _ordered_regions():
        if zkey and zkey not in seen:
            seen.add(zkey)
            out.append((zkey, index["zones"][zkey]))
    return out


def _ordered_regions() -> list:
    """Regions in the order :mod:`src.ecoregion` offers them, which is the
    polygon file's ``sort`` — grouped by ecozone already."""
    from src.ecoregion import geographic_ecoregions                # noqa: PLC0415

    index = _index()
    out = []
    for key, _name, _where in geographic_ecoregions():
        if key in index["regions"]:
            out.append((key, index["regions"][key]))
    return out


def regions_in(zone: str) -> list:
    """``(key, name)`` per ecoregion inside one ecozone."""
    return [(key, name) for key, (name, zkey) in _ordered_regions()
            if zkey == zone]


def subregions_in(region_key: str) -> list:
    """``(key, name)`` per Alberta natural subregion inside one ecoregion.

    Empty for every Saskatchewan region, and that asymmetry is honest rather
    than a gap to fill: Alberta publishes a subregion layer and Saskatchewan
    does not, so inventing one would be inventing data.
    """
    return sorted(
        ((key, name) for key, (name, parents) in _index()["subs"].items()
         if region_key in parents),
        key=lambda pair: pair[1])


def tree() -> list:
    """The whole vocabulary as nested ``(key, name, level, children)``."""
    return [
        (zone_key, zone_name, ECOZONE, [
            (region_key, region_name, ECOREGION, [
                (sub_key, sub_name, SUBREGION, [])
                for sub_key, sub_name in subregions_in(region_key)
            ])
            for region_key, region_name in regions_in(zone_key)
        ])
        for zone_key, zone_name in ecozones()
    ]


def level_of(key: str) -> str:
    """Which level a key belongs to, or ``""`` when it is not in the tree."""
    index = _index()
    if key in index["regions"]:
        return ECOREGION
    if key in index["zones"]:
        return ECOZONE
    if key in index["subs"]:
        return SUBREGION
    return ""


def descendants_of(key: str) -> set:
    """Every key below ``key``, not including it."""
    index = _index()
    out: set = set()
    if key in index["zones"]:
        for region_key, _name in regions_in(key):
            out.add(region_key)
            out |= {sub for sub, _n in subregions_in(region_key)}
    elif key in index["regions"]:
        out |= {sub for sub, _n in subregions_in(key)}
    return out


def ancestors_of(key: str) -> set:
    """Every key above ``key``, not including it."""
    index = _index()
    out: set = set()
    if key in index["regions"]:
        zone = index["regions"][key][1]
        if zone:
            out.add(zone)
    elif key in index["subs"]:
        for region_key in index["subs"][key][1]:
            out.add(region_key)
            zone = index["regions"].get(region_key, ("", ""))[1]
            if zone:
                out.add(zone)
    return out


def lineage_keys(key: str) -> list:
    """``key`` plus everything above and below it, for matching.

    See the module docstring for why both directions. Returns a sorted list so
    the SQL it feeds is stable between runs and a query plan can be compared.
    """
    if not key or not level_of(key):
        return [key] if key else []
    return sorted({key} | ancestors_of(key) | descendants_of(key))


def expand_for_filter(keys) -> list:
    """Expand a user's chosen keys into everything that should match them.

    Moisture niches and anything else unknown to the tree pass through
    untouched: ``riparian`` is a condition rather than a place and has no
    lineage to walk.
    """
    out: list = []
    for key in keys or []:
        for expanded in (lineage_keys(key) or [key]):
            if expanded not in out:
                out.append(expanded)
    return out

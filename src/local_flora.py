"""
local_flora.py — which of the catalogue's plants are native around a place,
and on what evidence (F220, V3.12).

Design principle P9 — see docs/DESIGN_PHILOSOPHY.md.

The question VASCAN cannot answer
---------------------------------
Since V2.80 every row says which provinces VASCAN records it native in, and
"native to Alberta" is 415 of 424 species: Glacier Lily and Moss Campion from
the mountains, Ball Cactus and the sagebrushes from the dry south, all of them
"native" to an Edmonton yard. The owner asked for the narrower list, "Edmonton
specific native plants", for people planting there.

The records cannot answer it on their own either, which is the trap this module
is built around. Within 50 km of downtown the GBIF cache holds **119
observations of Bur Oak** and **three herbarium specimens of it**, 1935-1952;
VASCAN records Bur Oak *introduced* in Alberta. A city is full of planted trees,
and somebody presses a specimen of one now and then. So:

* **VASCAN's Alberta list is a gate in front of everything.** A species it does
  not record native in Alberta is never native around an Alberta place, whatever
  the records say and whatever a review says.
* **Only herbarium specimens count as evidence.** A sheet can be re-examined; an
  observation's "wild" is a checkbox. Observations are carried as context and
  never counted.
* **At least three distinct collections**, the floor
  :data:`src.ecoregion_ranges.MIN_RECORDS` already argues for ("two is a
  coincidence"). One gathering split between herbaria is one collection: sheets
  sharing a 0.01-degree spot and a year count once.
* **A record counts only if its whole uncertainty circle is inside the place.**
  A sheet labelled "Edmonton" and georeferenced to the city with a coarse
  radius is good evidence for a 50 km question; the range map's 10 km cut threw
  out pin cherry's only Edmonton specimen.

Below the floor a species is *not settled*, never "not native" (P9): pin cherry
has one collection and 189 observations, and is about as Edmonton as a shrub
gets. Settling those is a person's job, so the owner's rulings
(``data/local_flora_rulings.json``) are merged in, each with its reason, and a
re-derivation keeps them. A ruling can move a species either way except across
the VASCAN gate.

What a tier claims
------------------
``documented``  three or more collections inside the place.
``thin``        one or two: not enough to say either way.
``observed``    seen inside the place, never collected there.
``unrecorded``  nothing inside, although recorded elsewhere.
``no_data``     nothing anywhere in the cache.
``not_in_province``  VASCAN does not record it native in the province.

The list itself is derived offline by ``scripts/derive_local_flora.py`` into
``data/local_flora.json``; :mod:`src.native_here` is the read side every
surface asks. This module is the rule and the file format, so a test can run
the rule on a synthetic cache.
"""

from __future__ import annotations

import json
import math
from typing import Iterable, Mapping, Optional

from src.ecoregion_ranges import MIN_RECORDS
from src.projection import metres_per_deg

#: The places with a list. The centre is the point the basemap's Edmonton dot
#: and the worked example already use (a test keeps them equal); the radius is
#: the owner's choice, between 30-40 km (fewer species with enough specimens)
#: and 80 km (the boreal edge as well as the city).
PLACES: dict = {
    "edmonton": {
        "name": "Edmonton region",
        "short": "Edmonton",
        "province": "AB",
        "centre": (53.5461, -113.4938),
        "radius_km": 50.0,
    },
}

#: Distinct collections inside the place before it is documented there.
MIN_COLLECTIONS = MIN_RECORDS

SPECIMEN = "PRESERVED_SPECIMEN"

TIERS = ("documented", "thin", "observed", "unrecorded", "no_data",
         "not_in_province")

#: What an owner's ruling can say.
RULINGS = ("native", "not_native")


def distance_km(a, b) -> float:
    """Ground distance between two ``(lat, lng)`` points, by the app's metric
    (:mod:`src.projection`), which is good to well under a kilometre at 50 km."""
    lat_m, lng_m = metres_per_deg((a[0] + b[0]) / 2.0)
    return math.hypot((b[0] - a[0]) * lat_m, (b[1] - a[1]) * lng_m) / 1000.0


def inside(lat: float, lng: float, uncertainty_m, place: Mapping) -> bool:
    """Whether a record's whole uncertainty circle lies within ``place``."""
    reach = distance_km(place["centre"], (lat, lng)) + (uncertainty_m or 0) / 1000.0
    return reach <= float(place["radius_km"])


def tally(points: Iterable, basis: list, place: Mapping) -> dict:
    """The evidence one species' cached records give for ``place``.

    ``points`` are the cache's rows, ``[lat, lng, uncertainty_m, year,
    basis_index, dataset_index]``; ``basis`` its list of basis names. Returns
    ``collections`` (distinct specimen gatherings inside), ``first``/``last``
    (their years, ``None`` when unknown), ``observations`` (everything else
    inside) and ``nearest_km`` (the nearest record not inside, ``None`` when
    every record is inside or there are none).
    """
    gatherings, years, observations = set(), [], 0
    nearest: Optional[float] = None
    for row in points or ():
        lat, lng, unc, year, b = row[0], row[1], row[2], row[3], row[4]
        if inside(lat, lng, unc, place):
            if basis[b] == SPECIMEN:
                key = (round(lat, 2), round(lng, 2), year)
                if key not in gatherings:
                    gatherings.add(key)
                    if year:
                        years.append(int(year))
            else:
                observations += 1
            continue
        d = distance_km(place["centre"], (lat, lng))
        nearest = d if nearest is None else min(nearest, d)
    return {
        "collections": len(gatherings),
        "first": min(years) if years else None,
        "last": max(years) if years else None,
        "observations": observations,
        "nearest_km": None if nearest is None else int(round(nearest)),
    }


def tier_for(in_province: bool, has_records: bool, collections: int,
             observations: int) -> str:
    """The tier a species' evidence puts it in (see the module docstring)."""
    if not in_province:
        return "not_in_province"
    if not has_records:
        return "no_data"
    if collections >= MIN_COLLECTIONS:
        return "documented"
    if collections:
        return "thin"
    if observations:
        return "observed"
    return "unrecorded"


def is_native(entry: Mapping) -> bool:
    """Whether a list entry counts as native around its place: documented and
    not ruled out, or ruled in. Never across the VASCAN gate."""
    if not entry or entry.get("tier") == "not_in_province":
        return False
    ruling = entry.get("ruling")
    if ruling in RULINGS:
        return ruling == "native"
    return entry.get("tier") == "documented"


def parse_rulings(doc: Optional[Mapping], species: Mapping) -> dict:
    """``{place: {scientific name: ruling}}`` from the rulings file, checked.

    ``species`` maps every catalogue scientific name to its row. Raises
    ``ValueError`` naming the problem: an unknown place, a species not in the
    catalogue (a rename must carry its ruling along), a ruling outside
    :data:`RULINGS`, no reason, or a "native" ruling on a species VASCAN does
    not record in the place's province.
    """
    out: dict = {}
    for place_key, rows in ((doc or {}).get("places") or {}).items():
        if place_key not in PLACES:
            raise ValueError(f"rulings name an unknown place: {place_key!r}")
        province = PLACES[place_key]["province"]
        kept = {}
        for name, ruling in (rows or {}).items():
            if name not in species:
                raise ValueError(f"{place_key}: ruling for {name!r}, which is "
                                 "not in the catalogue")
            if (ruling or {}).get("ruling") not in RULINGS:
                raise ValueError(f"{place_key}: {name}: ruling must be one of "
                                 f"{RULINGS}")
            if not str(ruling.get("reason") or "").strip():
                raise ValueError(f"{place_key}: {name}: a ruling needs a reason")
            if (ruling["ruling"] == "native"
                    and province not in _provinces(species[name])):
                raise ValueError(f"{place_key}: {name}: VASCAN does not record "
                                 f"it native in {province}; a review cannot "
                                 "make it native here")
            kept[name] = {k: ruling[k] for k in ("ruling", "reason", "on")
                          if ruling.get(k)}
        out[place_key] = kept
    return out


def derive(catalogue: Iterable[Mapping], cache: Mapping,
           rulings: Optional[Mapping] = None) -> dict:
    """The whole shipped document, from the catalogue rows, the occurrence
    cache and the parsed rulings. Deterministic: ``generated`` is the cache's
    date, so a re-run over the same inputs writes the same bytes."""
    rows = {r["scientific_name"]: r for r in catalogue
            if r.get("scientific_name")}
    basis = list(cache.get("basis") or [])
    points = cache.get("species") or {}
    rulings = rulings or {}
    places = {}
    for key, place in PLACES.items():
        entries = {}
        for name in sorted(rows):
            ev = tally(points.get(name) or [], basis, place)
            entry = {"tier": tier_for(
                place["province"] in _provinces(rows[name]),
                bool(points.get(name)), ev["collections"],
                ev["observations"])}
            entry.update({k: v for k, v in ev.items() if v not in (None, 0)})
            entry.update((rulings.get(key) or {}).get(name) or {})
            entries[name] = entry
        places[key] = {"name": place["name"], "short": place["short"],
                       "province": place["province"],
                       "centre": list(place["centre"]),
                       "radius_km": place["radius_km"],
                       "min_collections": MIN_COLLECTIONS,
                       "species": entries}
    return {
        "version": 1,
        "generated": cache.get("generated") or "",
        "source": ("derived from data/fetched/plant_occurrences.json ("
                   + (cache.get("source") or "GBIF") + ") and the province "
                   "lists VASCAN gives every row of data/plants_master.json, "
                   "with the owner's rulings from data/local_flora_rulings.json"),
        "comment": ("Which species are native around each place, with the "
                    "evidence. A species is native there when VASCAN records "
                    "it native in the province AND at least min_collections "
                    "distinct herbarium collections lie wholly within "
                    "radius_km of the centre, or the owner ruled it native. "
                    "Observations are context and never counted: a city's "
                    "records include its planted trees. Below the floor a "
                    "species is not settled, which is not the same as not "
                    "native. Regenerate with scripts/derive_local_flora.py; "
                    "never edit by hand."),
        "places": places,
    }


def parse_document(doc: Optional[Mapping]) -> dict:
    """``{place: {"name", "short", "province", "centre", "radius_km",
    "species": {name: entry}}}`` from a shipped document, or ``{}`` for one
    that is missing or of a version this code does not read."""
    if not isinstance(doc, Mapping) or doc.get("version") != 1:
        return {}
    out = {}
    for key, place in (doc.get("places") or {}).items():
        if not isinstance(place, Mapping) or "species" not in place:
            continue
        out[key] = dict(place)
        out[key]["centre"] = tuple(place.get("centre") or ())
    return out


def dumps(doc: Mapping) -> str:
    """The document as text, one species per line, so a review's diff reads as
    the rulings it made rather than as a reflowed file."""
    head = {k: v for k, v in doc.items() if k != "places"}
    lines = ["{"]
    lines += [f"  {json.dumps(k)}: {json.dumps(v, ensure_ascii=False)},"
              for k, v in head.items()]
    lines.append('  "places": {')
    places = list((doc.get("places") or {}).items())
    for i, (key, place) in enumerate(places):
        lines.append(f"    {json.dumps(key)}: {{")
        for k, v in place.items():
            if k != "species":
                lines.append(f"      {json.dumps(k)}: {json.dumps(v)},")
        lines.append('      "species": {')
        species = list(place["species"].items())
        for j, (name, entry) in enumerate(species):
            comma = "," if j < len(species) - 1 else ""
            lines.append(f"        {json.dumps(name)}: "
                         f"{json.dumps(entry, ensure_ascii=False, sort_keys=True)}"
                         f"{comma}")
        lines.append("      }")
        lines.append("    }" + ("," if i < len(places) - 1 else ""))
    lines += ["  }", "}", ""]
    return "\n".join(lines)


def _provinces(row: Mapping) -> list:
    return [p.strip().upper() for p in str(row.get("native_provinces") or "")
            .split(",") if p.strip()]

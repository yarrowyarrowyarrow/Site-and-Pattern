"""
native_here.py — is this plant native here? At the province, and around the
place where the catalogue has a list for it (F220, V3.12).

Design principle P9 — see docs/DESIGN_PHILOSOPHY.md.

One read side, so the surfaces cannot disagree. They have before: the
ecoregion filter and the species card (V2.38), the website's species entry and
its nativity note (V2.80), the generator's Alberta flag and the pin's province
(V2.85), the picker's flag and VASCAN (V3.00). The plant picker, the species
page on both the desktop and the website, the community list, the generator and
the website's filter all ask the questions below and nothing else.

* **The province** (VASCAN, since V2.80): :func:`native_in`, :func:`native_tip`
  and :func:`province_words`, moved here from ``plant_filters`` in V3.12, which
  re-exports them.
* **Around a place** (``data/local_flora.json``, derived by
  ``scripts/derive_local_flora.py`` under the rule in :mod:`src.local_flora`):
  :func:`native_around`, :func:`native_names` and :func:`around`, whose
  ``words`` are the sentence a page prints. Below the evidence floor a species
  is *not settled*, and the words say that rather than "not native".
"""

from __future__ import annotations

import functools
import json
from typing import Mapping, Optional

from src.local_flora import MIN_COLLECTIONS, is_native, parse_document

#: The provinces a pin can be in, by the code VASCAN's lists use (F200).
PROVINCE_NAMES: dict = {"AB": "Alberta", "SK": "Saskatchewan"}

#: The only place with a list so far, and the one every caller means by default.
EDMONTON = "edmonton"


def native_in(plant: dict, province: str = "AB") -> bool:
    """Whether VASCAN records ``plant`` native in ``province``, read off its
    ``native_provinces`` (every row's since V2.80); a row without them falls
    back to the Alberta flag, and to nothing elsewhere."""
    provs = (plant or {}).get("native_provinces")
    if provs:
        return (province or "AB") in {p.strip() for p in str(provs).split(",")}
    return (province or "AB") == "AB" and bool(
        (plant or {}).get("native_to_alberta"))


def native_tip(province: str = "AB") -> str:
    """The Native filter's tooltip, naming the province it filters to."""
    name = PROVINCE_NAMES.get(province or "AB", "Alberta")
    return f"Native to {name}, as VASCAN records it."


def province_words(plant: Mapping) -> str:
    """Where VASCAN records ``plant`` native, as a sentence, naming the
    catalogue province it is *not* native to: the line the desktop species page
    lacked until V3.12, which is how Eastern Red Columbine read as Albertan.
    Accepts a catalogue row or a ``species_entry`` (``native``)."""
    from src.nativity import WITHHELD_NOTE, provinces, publishable
    if not publishable(plant):
        return WITHHELD_NOTE
    codes = provinces(plant.get("native_provinces") or plant.get("native"))
    named = [PROVINCE_NAMES[c] for c in PROVINCE_NAMES if c in codes]
    missing = [PROVINCE_NAMES[c] for c in PROVINCE_NAMES if c not in codes]
    if not named:
        return ("Not native to " + " or ".join(missing)
                + ", as VASCAN records it.")
    text = " and ".join(named) + ", as VASCAN records it."
    return text + (f" Not native to {' or '.join(missing)}." if missing else "")


# ── Around a place ───────────────────────────────────────────────────────────

def around_tip(place: str = EDMONTON) -> str:
    """The filter's tooltip, from the rule's own constants (no file read), so
    the numbers it states are the ones the list was derived with."""
    from src.local_flora import PLACES                       # noqa: PLC0415
    p = PLACES[place]
    return (f"Native around {p['short']}: native to "
            f"{PROVINCE_NAMES[p['province']]} as VASCAN records it, and "
            f"collected at least {MIN_COLLECTIONS} times within "
            f"{p['radius_km']:g} km of downtown, or confirmed on review. Plants "
            "of the mountains and the dry south drop out. A plant's page shows "
            "the evidence.")


_document: Optional[dict] = None


def set_document(doc: Optional[dict]) -> None:
    """Use ``doc`` (a parsed :func:`src.local_flora.derive` result) instead of
    the shipped file; ``None`` goes back to the file. For tests."""
    global _document
    _document = None if doc is None else parse_document(doc)
    _shipped.cache_clear()
    native_names.cache_clear()


@functools.lru_cache(maxsize=1)
def _shipped() -> dict:
    from src.resources import resource_path                  # noqa: PLC0415
    try:
        with open(resource_path("data", "local_flora.json"),
                  encoding="utf-8") as fh:
            return parse_document(json.load(fh))
    except (OSError, ValueError):
        return {}


def _places() -> dict:
    return _document if _document is not None else _shipped()


def places() -> dict:
    """``{key: {"name", "short", "province", "centre", "radius_km"}}`` for
    every place with a list, as the list was derived."""
    return {k: {f: v for f, v in p.items() if f != "species"}
            for k, p in _places().items()}


def place_at(lat, lng) -> str:
    """The place whose circle holds ``(lat, lng)``, or ``""``."""
    from src.local_flora import distance_km                  # noqa: PLC0415
    try:
        point = (float(lat), float(lng))
    except (TypeError, ValueError):
        return ""
    for key, p in _places().items():
        if distance_km(p["centre"], point) <= float(p["radius_km"]):
            return key
    return ""


def entry(scientific_name: str, place: str = EDMONTON) -> dict:
    """The list's entry for a species, ``{}`` when it has none."""
    p = _places().get(place) or {}
    return dict((p.get("species") or {}).get((scientific_name or "").strip())
                or {})


@functools.lru_cache(maxsize=8)
def native_names(place: str = EDMONTON) -> frozenset:
    """Scientific names native around ``place``. Raises ``ValueError`` for a
    place with no list: an unknown key filtering to nothing would read as
    "no natives here", which is a claim."""
    p = _places().get(place)
    if p is None:
        raise ValueError(f"no local list for {place!r}; "
                         f"known: {sorted(_places())}")
    return frozenset(n for n, e in p["species"].items() if is_native(e))


def native_around(plant, place: str = EDMONTON) -> bool:
    """Whether a plant (a row, an entry or a scientific name) is native around
    ``place``."""
    name = plant if isinstance(plant, str) else (
        (plant or {}).get("scientific_name") or "")
    return name.strip() in native_names(place)


def around(plant, place: str = EDMONTON) -> dict:
    """What a page says about a plant around ``place``: ``native``, the
    ``tier`` and ``ruling`` behind it, and ``words``, the sentence to print
    under a heading like "Around Edmonton". ``{}`` when there is no list."""
    p = _places().get(place)
    if not p:
        return {}
    name = plant if isinstance(plant, str) else (
        (plant or {}).get("scientific_name") or "")
    e = entry(name, place)
    if not e:
        return {}
    return {"place": place, "name": p["name"], "short": p["short"],
            "native": is_native(e), "tier": e.get("tier", ""),
            "ruling": e.get("ruling", ""), "words": _words(e, p)}


def _words(e: Mapping, p: Mapping) -> str:
    radius = f"{float(p['radius_km']):g} km"
    tier = e.get("tier")
    if tier == "not_in_province":
        name = PROVINCE_NAMES.get(p.get("province"), p.get("province"))
        return f"Not native. VASCAN does not record it native to {name}."
    evidence = _evidence(e, radius)
    if e.get("ruling") in ("native", "not_native"):
        verdict = ("Native, on review" if e["ruling"] == "native"
                   else "Not native here, on review")
        return f"{verdict}: {_sentence(e.get('reason'))} {evidence}".strip()
    if tier == "documented":
        return f"Native. {evidence}"
    if tier == "thin":
        return (f"Not settled. {evidence[:-1]}; the list needs "
                f"{MIN_COLLECTIONS} collections or a review.")
    if tier == "observed":
        return (f"Not settled. {evidence[:-1]}, and planted ones are seen "
                "too.")
    if tier == "unrecorded":
        near = e.get("nearest_km")
        return (f"Not recorded within {radius}."
                + (f" The nearest record is {near} km from {p['short']}."
                   if near else ""))
    return "Not known. This catalogue holds no occurrence records for it."


def _evidence(e: Mapping, radius: str) -> str:
    """"Collected 10 times within 50 km, 1966 to 2017." or the observations."""
    n = int(e.get("collections") or 0)
    if n:
        first, last = e.get("first"), e.get("last")
        when = ("" if not first else f", in {first}" if first == last
                else f", {first} to {last}")
        return f"Collected {_times(n)} within {radius}{when}."
    seen = int(e.get("observations") or 0)
    if seen:
        return f"Seen {_times(seen)} within {radius} but never collected there."
    return ""


def _times(n: int) -> str:
    return {1: "once", 2: "twice"}.get(n, f"{n} times")


def _sentence(text) -> str:
    text = str(text or "").strip()
    return text if not text or text[-1] in ".!?" else text + "."

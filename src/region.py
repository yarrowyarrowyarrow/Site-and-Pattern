"""
region.py — everything true of one place, read from its pack (V3.24, ED-1;
docs/homeowner/08-edmonton-edition.md §4).

Design principle P2 — see docs/DESIGN_PHILOSOPHY.md.

The app was local to Edmonton by literals scattered through the code: a
50 km circle in ``local_flora``, "Edmonton native" in the picker, two nursery
lists that disagreed, "Edmonton, Alberta" under every PDF's title whatever
the pin. A **region pack** (``data/regions/<key>/``) holds what is true of one
place, its manifest ``region.json`` and the reviewed list of its native plants,
and this module is the only code that opens ``data/regions/`` or
``data/edition.json``. The pin chooses the pack; a pin outside every pack is
told so plainly (``coverage`` and ``message``) rather than given borrowed
numbers. Calgary is then a second folder, a derivation run and a person's
review, with no code (§5).

There is deliberately no field for plant uses, cultural knowledge or land
management (P12): the validation rejects unknown fields, so one cannot be
added in passing.

Qt-free.
"""

from __future__ import annotations

import functools
import json
import os
import re
from dataclasses import dataclass, field
from typing import Mapping, Optional

#: The manifest's fields: required, then optional (§4.2).
REQUIRED = ("schema", "key", "name", "short", "province", "area",
            "local_flora", "ecoregion", "map", "address_search", "climate",
            "nurseries", "nursery_note", "example", "defaults")
OPTIONAL = ("communities", "overview", "elevation")
SCHEMA = 1
_KEY = re.compile(r"^[a-z_]+$")

#: Kinds of :class:`Coverage`.
REGION, PROVINCE, OUTSIDE, NO_PIN = "region", "province", "outside", "no_pin"


@dataclass(frozen=True)
class Region:
    """One pack's manifest. Nested blocks are plain dicts, as written."""
    key: str
    name: str
    short: str
    province: str
    centre: tuple
    radius_km: float
    min_collections: int
    ecoregion: str
    map: dict = field(default_factory=dict)
    address_search: dict = field(default_factory=dict)
    climate: dict = field(default_factory=dict)
    nurseries: tuple = ()
    nursery_note: str = ""
    example: dict = field(default_factory=dict)
    defaults: dict = field(default_factory=dict)
    communities: dict = field(default_factory=dict)
    overview: dict = field(default_factory=dict)
    elevation: dict = field(default_factory=dict)
    folder: str = ""

    def place(self) -> dict:
        """The place as :mod:`src.local_flora` derives a list for it."""
        return {"name": self.name, "short": self.short,
                "province": self.province, "centre": tuple(self.centre),
                "radius_km": float(self.radius_km)}


@dataclass(frozen=True)
class Coverage:
    kind: str                       # REGION | PROVINCE | OUTSIDE | NO_PIN
    region: Optional[Region]        # the pack holding the pin (REGION only)
    province: str                   # "AB" | "SK" | ""
    nearest: Region                 # the nearest pack, for messages
    distance_km: Optional[float]    # to the nearest pack's centre


def validate(doc: Mapping, folder_key: str) -> list[str]:
    """What is wrong with a manifest, as sentences; ``[]`` when nothing is."""
    errs = []
    if not isinstance(doc, Mapping):
        return ["the manifest is not an object"]
    missing = [k for k in REQUIRED if k not in doc]
    unknown = sorted(set(doc) - set(REQUIRED) - set(OPTIONAL))
    if missing:
        errs.append(f"missing {', '.join(missing)}")
    if unknown:
        errs.append(f"unknown fields {', '.join(unknown)} (P12: a pack "
                    "carries no field this module does not name)")
    if doc.get("schema") != SCHEMA:
        errs.append(f"schema must be {SCHEMA}")
    key = doc.get("key", "")
    if not _KEY.match(str(key)) or key != folder_key:
        errs.append(f"key {key!r} must be [a-z_]+ and equal the folder name "
                    f"{folder_key!r}")
    if doc.get("province") not in ("AB", "SK"):
        errs.append("province must be AB or SK")
    area = doc.get("area") or {}
    if len(area.get("centre") or ()) != 2:
        errs.append("area.centre must be [lat, lng]")
    if not 10 <= float(area.get("radius_km") or 0) <= 150:
        errs.append("area.radius_km must be 10 to 150")
    precip = (doc.get("climate") or {}).get("monthly_precip_mm") or []
    if len(precip) != 12:
        errs.append("climate.monthly_precip_mm needs 12 values")
    for k in ("last_spring_frost", "first_fall_frost"):
        if not re.match(r"^\d\d-\d\d$",
                        str((doc.get("climate") or {}).get(k) or "")):
            errs.append(f"climate.{k} must be MM-DD")
    return errs


def _from_doc(doc: Mapping, folder: str) -> Region:
    area = doc["area"]
    return Region(
        key=doc["key"], name=doc["name"], short=doc["short"],
        province=doc["province"], centre=tuple(area["centre"]),
        radius_km=float(area["radius_km"]),
        min_collections=int(doc["local_flora"]["min_collections"]),
        ecoregion=doc["ecoregion"], map=dict(doc["map"]),
        address_search=dict(doc["address_search"]),
        climate=dict(doc["climate"]), nurseries=tuple(doc["nurseries"]),
        nursery_note=doc["nursery_note"], example=dict(doc["example"]),
        defaults=dict(doc["defaults"]),
        communities=dict(doc.get("communities") or {}),
        overview=dict(doc.get("overview") or {}),
        elevation=dict(doc.get("elevation") or {}), folder=folder)


def _data_dir() -> str:
    from src.resources import resource_path                  # noqa: PLC0415
    return resource_path("data")


_override: Optional[dict] = None
_default_override: Optional[str] = None


@functools.lru_cache(maxsize=1)
def _shipped() -> dict:
    root = os.path.join(_data_dir(), "regions")
    out = {}
    try:
        names = sorted(os.listdir(root))
    except OSError:
        return {}
    for name in names:
        folder = os.path.join(root, name)
        path = os.path.join(folder, "region.json")
        if not os.path.isfile(path):
            continue
        with open(path, encoding="utf-8") as fh:
            doc = json.load(fh)
        errs = validate(doc, name)
        if errs:
            raise ValueError(f"data/regions/{name}/region.json: "
                             + "; ".join(errs))
        out[name] = _from_doc(doc, folder)
    return out


def regions() -> dict:
    """Every pack, validated, by key."""
    return dict(_override) if _override is not None else _shipped()


@functools.lru_cache(maxsize=1)
def _edition() -> dict:
    try:
        with open(os.path.join(_data_dir(), "edition.json"),
                  encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {}


def feedback_address() -> str:
    """The address *Send Feedback* shows (FN-8, V3.31): ``data/edition.json``'s
    ``feedback_email``, a mailbox kept for the app and never a person's own.
    ``""`` until the owner names one, and the dialog then offers GitHub and
    the copied message only."""
    address = str(_edition().get("feedback_email") or "").strip()
    return address if "@" in address and " " not in address else ""


def default() -> Region:
    """The pack the app uses before a pin exists (``data/edition.json``)."""
    packs = regions()
    key = _default_override or _edition().get("default_region") or ""
    if key in packs:
        return packs[key]
    return packs[sorted(packs)[0]]


def set_regions(packs: Optional[dict], default_key: Optional[str] = None) -> None:
    """Tests: use ``packs`` (``{key: Region}``) instead of the shipped ones;
    ``None`` goes back to the files."""
    global _override, _default_override
    _override = None if packs is None else dict(packs)
    _default_override = default_key
    try:
        from src import native_here                          # noqa: PLC0415
        native_here.set_document(None)
    except Exception:                                      # noqa: BLE001
        pass


def from_doc(doc: Mapping, folder: str = "") -> Region:
    """A :class:`Region` from a manifest dict, validated (tests and tools)."""
    errs = validate(doc, doc.get("key", ""))
    if errs:
        raise ValueError("; ".join(errs))
    return _from_doc(doc, folder)


def flora_path(key: str) -> str:
    """The pack's derived list of native plants."""
    return os.path.join(_data_dir(), "regions", key, "local_flora.json")


def rulings_path(key: str) -> str:
    """The owner's yes/no rulings for the pack's list."""
    return os.path.join(_data_dir(), "regions", key, "local_flora_rulings.json")


def animal_records_path(key: str) -> str:
    """How often each animal is recorded near the pack's place and across its
    province (``src.fauna_fit``, V3.37)."""
    return os.path.join(_data_dir(), "regions", key, "animal_records.json")


def _distance(a, b) -> float:
    from src.local_flora import distance_km                  # noqa: PLC0415
    return distance_km(a, b)


def at(lat, lng) -> Optional[Region]:
    """The pack whose circle holds the point, or ``None``."""
    try:
        point = (float(lat), float(lng))
    except (TypeError, ValueError):
        return None
    for r in regions().values():
        if _distance(r.centre, point) <= r.radius_km:
            return r
    return None


def coverage(lat=None, lng=None) -> Coverage:
    """Where a pin is, as far as the app's knowledge goes (§4.5)."""
    try:
        point = (float(lat), float(lng))
    except (TypeError, ValueError):
        return Coverage(NO_PIN, None, "", default(), None)
    from src.site_fit import province_at                     # noqa: PLC0415
    nearest = min(regions().values(),
                  key=lambda r: _distance(r.centre, point))
    km = _distance(nearest.centre, point)
    province = province_at(*point)
    if km <= nearest.radius_km:
        return Coverage(REGION, nearest, province, nearest, km)
    return Coverage(PROVINCE if province else OUTSIDE, None, province,
                    nearest, km)


def for_site(site_config: Optional[Mapping]) -> Region:
    """The pack for a design: the one holding its pin, else the default."""
    sc = site_config or {}
    return at(sc.get("latitude"), sc.get("longitude")) or default()


_PROVINCE_NAMES = {"AB": "Alberta", "SK": "Saskatchewan"}


def message(cov: Coverage) -> str:
    """What Site Info and Plan My Yard say about where the pin is (§4.5)."""
    from src.branding import APP_NAME                        # noqa: PLC0415
    if cov.kind == NO_PIN:
        return ""
    if cov.kind == REGION:
        return f"{cov.region.name}."
    near = cov.nearest
    if cov.kind == PROVINCE:
        prov = _PROVINCE_NAMES.get(cov.province, cov.province)
        return (f"This pin is {round(cov.distance_km):d} km from "
                f"{near.short}, outside the area {APP_NAME} is set up for. "
                f"You can still plan here, but plants are chosen from "
                f"everything native to {prov}, and the nurseries and "
                f"planting dates are {near.short}'s.")
    return (f"This pin is outside Alberta and Saskatchewan. {APP_NAME} knows "
            f"the plants, climate and nurseries of the {near.name} only, so "
            "it can't suggest plants for this yard.")


def place_line(lat=None, lng=None) -> str:
    """What an export prints under its title for where the yard is (ED-5,
    EDF-2): the region's name inside a pack, the coordinates outside one,
    nothing with no pin. It had printed "Edmonton, Alberta" whatever the pin."""
    cov = coverage(lat, lng)
    if cov.kind == NO_PIN:
        return ""
    if cov.kind == REGION:
        prov = _PROVINCE_NAMES.get(cov.region.province, cov.region.province)
        return f"{cov.region.name}, {prov}"
    return f"{float(lat):.4f}, {float(lng):.4f}"

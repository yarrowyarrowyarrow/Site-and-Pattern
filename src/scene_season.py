"""
scene_season.py — what season the 3D preview draws (V3.46, F263; 3D-4 of
docs/plans/V3.43-the-3d-preview-reviewed.md).

Design principle P4 (time is the most undervalued design variable) and P9
(ranges and confidence, never false precision) — see docs/DESIGN_PHILOSOPHY.md.

The V3.43 review's finding 7: seasons were half drawn. One function in the
viewer tinted a plant by the month's number and nothing else about a plant
changed, so a perennial stood at its July height on 21 April and was green in
January's snow, a shrub kept its leaves all winter while the tree beside it
dropped them, and the months themselves (leaves April to October, snow November
to March) were typed into five of the viewer's chunks while the app has held
the region's frost dates in its pack since V3.25.

This module decides the season once, for the viewer and the animals alike
(the V2.88 lesson of the floating flowers), and ``build_scene`` puts it in the
scene: additive fields, no ``SCENE_VERSION`` bump. A scene without them is
drawn by the viewer's old month rules.

* ``scene["season"]``: whether snow lies, what the unplanted ground is doing,
  the general state of leaves and herbs, and where the dates came from.
* ``plant["season"]``, on every plant that is not evergreen: ``look`` (one of
  :data:`LOOKS`), ``t`` (how far through ``young`` or ``turning``, 0 to 1) and
  ``up`` (the share of this year's height a herb stands at while it comes up).

**The dates are the pack's frost dates plus the offsets below, and every
offset is an estimate nobody recorded.** They are a typical year in the
region, not this year's weather, and :func:`basis_words` says so for the
window to show. A warm-season grass comes up later than a cool-season one, an
oak holds brown leaves into winter, and none of that is in the catalogue: one
calendar for all, moved only by what a plant's own record says (its months in
flower, its foliage).

Qt-free, and it reads nothing but the region pack's file, which is read once:
``build_scene`` runs on the main thread on every slider tick.
"""

from __future__ import annotations

import datetime as _dt
from typing import Mapping, Optional

#: How a plant is drawn. ``dry``: last year's stems, standing. ``young``:
#: coming up, or leaves opening. ``green``: summer. ``turning``: autumn colour.
#: ``bare``: a woody plant with its leaves down. ``held``: a semi-evergreen's
#: bronzed winter leaves. html/scene3d/01d-season.js draws each; a test keeps
#: the two lists equal.
LOOKS = ("dry", "young", "green", "turning", "bare", "held")

#: What the ground is doing where nothing is planted.
GROUNDS = ("snow", "dormant", "waking", "green", "turning")

# ── the offsets: estimates, in days, from the pack's two frost dates ─────────
#: Herbs start to show this long before the last spring frost…
HERB_START_BEFORE = 30
#: …and no plant starts earlier than this, however early it flowers.
THAW_BEFORE = 45
#: Herbs are at their full height this long after the last spring frost,
HERB_FULL_AFTER = 35
#: or this far into the plant's first month in flower, if that is sooner,
BLOOM_FULL_DAYS = 14
#: having taken at most this long to come up.
HERB_RISE_DAYS = 65
#: Buds break this long before the last spring frost; leaves are full after.
LEAF_START_BEFORE = 7
LEAF_FULL_AFTER = 21
#: Leaves and herbs begin to turn before the first fall frost, are at full
#: colour a week after it, and are down (or dry) four weeks after it.
TURN_BEFORE = 14
COLOUR_AFTER = 7
DOWN_AFTER = 28
#: Snow lies in these months: the viewer's own rule since V2.24. The pack
#: records no snow dates, so this is not derived from anything.
SNOW_MONTHS = (11, 12, 1, 2, 3)

#: A herb just showing stands at this share of its height.
UP_MIN = 0.12
#: A plant in flower stands at least this tall, and has turned at most this far.
UP_IN_FLOWER = 0.75
TURN_IN_FLOWER = 0.6
#: Below this share of the spring rise the unplanted ground is still waking.
WAKING_BELOW = 0.4

_WOODY = ("tree", "shrub", "vine")
#: Bodies src/succulent_habit.py and src/pond_habit.py decide that do not die
#: back or come up with the herbs: a cactus keeps its pads, and a floating or
#: submerged plant's height is stem under water.
_KEEPS_ITS_BODY = ("pads", "ball", "swords", "fleshy")
_ON_WATER = ("floating", "submerged")


def _doy(month: int, day: int) -> int:
    return _dt.date(2025, int(month), int(day)).timetuple().tm_yday


def _smooth(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return t * t * (3.0 - 2.0 * t)


_CALENDARS: dict = {}


def calendar(site_config: Optional[Mapping] = None) -> dict:
    """The year's turning points as days of the year, with where they came
    from. ``known`` is False for a pin outside every province a pack covers:
    the default pack's dates still draw the picture, and nothing claims they
    are that place's."""
    from src import region, region_climate                   # noqa: PLC0415
    sc = site_config or {}
    key = (sc.get("latitude"), sc.get("longitude"))
    held = _CALENDARS.get(key)
    if held is not None and held[0] is region.regions():
        return held[1]
    frost = region_climate.frost_dates(sc)
    pack = region_climate.pack_for(sc)
    known = frost is not None and pack is not None
    if not known:
        pack = region.default()
        frost = region_climate.frost_dates({})
    last, first = _doy(*frost["last"]), _doy(*frost["first"])
    cal = {
        "known": known,
        "place": pack.name if known else "",
        "last_frost": region_climate.date_words(frost["last"]),
        "first_frost": region_climate.date_words(frost["first"]),
        "source": frost["label"] if known else "",
        "thaw": last - THAW_BEFORE,
        "herb_start": last - HERB_START_BEFORE,
        "herb_full": last + HERB_FULL_AFTER,
        "leaf_start": last - LEAF_START_BEFORE,
        "leaf_full": last + LEAF_FULL_AFTER,
        "turn_start": first - TURN_BEFORE,
        "colour": first + COLOUR_AFTER,
        "down": first + DOWN_AFTER,
    }
    _CALENDARS.clear()                # one design at a time; never grows
    _CALENDARS[key] = (region.regions(), cal)
    return cal


def basis_words(cal: Mapping) -> str:
    """What the seasons are drawn from, for the window to say."""
    if not cal.get("known"):
        return ("The seasons are drawn as a typical prairie year. No frost "
                "dates are known for this place.")
    return (f"The seasons are drawn as typical for the {cal['place']}: last "
            f"spring frost {cal['last_frost']}, first fall frost "
            f"{cal['first_frost']}. A typical year, not this year's weather.")


# ── one plant ────────────────────────────────────────────────────────────────

def _in_flower(plant: Mapping, month: int) -> bool:
    start, end = plant.get("bloom_start") or 0, plant.get("bloom_end") or 0
    return bool(start) and start <= month <= end


def _woody(day: int, cal: Mapping) -> dict:
    if day < cal["leaf_start"] or day >= cal["down"]:
        return {"look": "bare"}
    if day < cal["leaf_full"]:
        return {"look": "young", "t": round(
            (day - cal["leaf_start"]) / (cal["leaf_full"] - cal["leaf_start"]), 2)}
    if day < cal["turn_start"]:
        return {"look": "green"}
    return {"look": "turning", "t": round(min(1.0, (
        day - cal["turn_start"]) / (cal["colour"] - cal["turn_start"])), 2)}


def herb_rise(cal: Mapping, bloom_start: int = 0) -> tuple:
    """``(first day showing, first day at full height)`` for a herb whose
    first month in flower is ``bloom_start`` (0 = not recorded)."""
    full = cal["herb_full"]
    if bloom_start:
        full = min(full, max(cal["thaw"] + BLOOM_FULL_DAYS,
                             _doy(bloom_start, 1) + BLOOM_FULL_DAYS))
    start = max(cal["thaw"], min(cal["herb_start"], full - BLOOM_FULL_DAYS),
                full - HERB_RISE_DAYS)
    return start, full


def _herb(day: int, month: int, cal: Mapping, plant: Mapping) -> dict:
    start, full = herb_rise(cal, plant.get("bloom_start") or 0)
    flowering = _in_flower(plant, month)
    if day < start or day >= cal["down"]:
        if not flowering:
            return {"look": "dry"}
        # In flower by its own record: up, and not last year's stems.
        if day < start:
            return {"look": "young", "t": 0.5, "up": UP_IN_FLOWER}
        return {"look": "turning", "t": TURN_IN_FLOWER}
    if day < full:
        t = _smooth((day - start) / (full - start))
        up = UP_MIN + (1.0 - UP_MIN) * t
        if flowering:
            up = max(up, UP_IN_FLOWER)
        return {"look": "young", "t": round(t, 2), "up": round(up, 2)}
    if day < cal["turn_start"]:
        return {"look": "green"}
    t = (day - cal["turn_start"]) / (cal["down"] - cal["turn_start"])
    if flowering:
        t = min(t, TURN_IN_FLOWER)
    return {"look": "turning", "t": round(t, 2)}


def _held(day: int, cal: Mapping) -> dict:
    """A semi-evergreen keeps its leaves: green while the others are in leaf,
    bronzed while they are bare."""
    warm = cal["leaf_start"] <= day < cal["down"]
    return {"look": "green" if warm else "held"}


def plant_season(plant: Mapping, when: _dt.datetime, cal: Mapping) -> Optional[dict]:
    """The ``season`` block for one of the scene's plants, or ``None`` for an
    evergreen (drawn as it always was) and for a body that keeps itself."""
    foliage = (plant.get("foliage_type") or "herbaceous").lower()
    if foliage == "evergreen":
        return None
    body = (plant.get("drawn") or {}).get("body") or ""
    if body in _KEEPS_ITS_BODY:
        return None
    day = when.timetuple().tm_yday
    kind = (plant.get("plant_type") or "herb").lower()
    if foliage == "semi-evergreen":
        return _held(day, cal)
    if kind in _WOODY or foliage == "deciduous":
        return _woody(day, cal)
    season = _herb(day, when.month, cal, plant)
    if body in _ON_WATER:
        season.pop("up", None)        # stem under water, not stature
    return season


# ── the whole scene ──────────────────────────────────────────────────────────

def _ground(day: int, month: int, cal: Mapping) -> str:
    if month in SNOW_MONTHS:
        return "snow"
    start, full = herb_rise(cal)
    if day < start or day >= cal["down"]:
        return "dormant"
    if day < full:
        return ("waking" if _smooth((day - start) / (full - start)) < WAKING_BELOW
                else "green")
    return "green" if day < cal["turn_start"] else "turning"


def apply_seasons(plants: list, when: _dt.datetime,
                  site_config: Optional[Mapping] = None) -> dict:
    """Write ``season`` onto each plant that has one, and return the scene's
    own ``season`` block. Called by ``build_scene`` after every plant's body
    is settled (the vines, the pond, the succulents), because a body decides
    whether a season applies to it."""
    cal = calendar(site_config)
    for plant in plants:
        season = plant_season(plant, when, cal)
        if season is not None:
            plant["season"] = season
    day = when.timetuple().tm_yday
    return {
        "snow": when.month in SNOW_MONTHS,
        "ground": _ground(day, when.month, cal),
        "leaves": _woody(day, cal)["look"],
        "herbs": _herb(day, when.month, cal, {})["look"],
        "known": bool(cal["known"]),
        "basis": basis_words(cal),
    }


def up(plant: Mapping) -> float:
    """The share of its height a plant is drawn at this season (1 = all of
    it). ``scene_wildlife`` perches by it, as the viewer's ``bodyHeightOf``
    draws by it."""
    return float((plant.get("season") or {}).get("up") or 1.0)

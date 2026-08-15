"""
src/cues_to_care.py — will the neighbours read it as cared for? (F75, V2.56).

Design principle P13 (a native planting has to be loved to survive) and P2 (the
best designs disappear into their context) — see docs/DESIGN_PHILOSOPHY.md.

The app critiques a design *ecologically* — bloom gaps, keystones, host plants,
layers. It has never critiqued whether the planting survives **socially**, which
is the thing that actually decides whether it is still there in three years. A
native yard is not usually removed because it failed ecologically. It is removed
because it read as neglect.

Joan Nassauer's "cues to care" is the framework: a wild-looking planting is
accepted when it carries visible signs of human intention around it. A mown
strip, a crisp edge, a path, a repeated showy plant, a sign. The planting can be
as messy as the ecology wants **inside** a frame that says somebody meant this.

**Six cues, and one of them is honestly a prompt rather than a check.** Nothing
in this app represents a sign, so :data:`SIGN` cannot be measured — and inventing
a geometric proxy for it ("is there a 40 cm gap near the frontage") would be a
measurement of nothing wearing the costume of evidence (P9). It is reported as
a suggestion, and says so.

**The frontage problem.** *Which edge faces the street* is not knowable here:
``osm_features`` fetches trees and buildings and no roads, and nothing else in
the app records a frontage. The 3D viewer's ``sidewalk`` camera already hit this
and answered it in a comment — it uses the south edge, "because that is the
street side of a north-facing prairie lot far more often than not". This module
makes the **same** assumption, so the two cannot disagree, and **names it in the
line it affects**, because an assumption stated is a different object from a
measurement implied. Only :data:`MOWN_EDGE` depends on it; the other five are
frontage-free, so a wrong guess costs one line rather than the feature.

Qt-free, and the catalogue is reached through an injected ``get_plant``, so this
is testable with no database and no display.
"""

from __future__ import annotations

from typing import Callable, NamedTuple, Optional

# Cue keys.
MOWN_EDGE = "mown_edge"
CRISP_BORDER = "crisp_border"
HEIGHT_GRADED = "height_graded"
VISIBLE_PATH = "visible_path"
SHOWY_REPEAT = "showy_repeat"
SIGN = "sign"

#: How many of one species reads as a deliberate repeat rather than as three
#: plants that happen to match. Below this it is a coincidence; at it, a rhythm.
REPEAT_MIN = 3

#: Mean height-gradient above which the planting reads as graded, and below
#: which it reads as inverted — tall things at the front, screening the rest.
#: Either side of the dead band is a finding; the middle is genuinely "no
#: opinion", which is not the same as "fine".
GRADED_HIGH = 0.55
GRADED_LOW = 0.45

#: Shapes and structures that ARE a cue, by the vocabulary the drawer already
#: uses (src/structure_panel.py presets + src/lawn_zones.py labels). Restated
#: nowhere: the zone labels are imported so the drawer and this cannot drift.
_LAWN_SHAPES = ("Lawn Area",)
_BED_SHAPES = ("Garden Bed", "Mulch Area")
_PATH_SHAPES = ("Pathway", "Patio / Deck")
_LAWN_STRUCTURES = ("native_lawn_patch",)
_BORDER_STRUCTURES = ("fence",)


class Cue(NamedTuple):
    """One cue: whether it is present, and what to say about it.

    ``present`` is ``None`` for :data:`SIGN` and for anything that cannot be
    judged — a design with no plants has no opinion about height grading, and
    saying "not graded" about it would be a finding invented from absence.
    """
    key: str
    present: Optional[bool]
    line: str


# ── Reading the project ──────────────────────────────────────────────────────

def _features(project: dict) -> list:
    return (project or {}).get("features") or []


def _shape_types(project: dict) -> set:
    out = set()
    for f in _features(project):
        props = f.get("properties") or {}
        if props.get("element_type") in ("custom_shape", "canopy_footprint"):
            st = props.get("shape_type")
            if st:
                out.add(st)
    return out


def _structure_ids(project: dict) -> set:
    out = set()
    for f in _features(project):
        props = f.get("properties") or {}
        if props.get("element_type") != "structure":
            continue
        sid = props.get("structure_id") or (props.get("struct_def") or {}).get("id")
        if sid:
            out.add(sid)
    return out


def _has_boundary(project: dict) -> bool:
    return any((f.get("properties") or {}).get("element_type")
               == "property_boundary" for f in _features(project))


def _placed(project: dict) -> list:
    from src.project_store import ProjectStore
    return list(ProjectStore(project).placed_plants)


def _lawn_zone_labels() -> set:
    from src.lawn_zones import ZONE_TYPES
    return {ZONE_TYPES["lawn_remaining"]["label"]}


# ── The frontage assumption ──────────────────────────────────────────────────

#: Said out loud wherever the assumption is used. See the module docstring.
FRONTAGE_NOTE = ("assuming the street is on the south side, as the "
                 "sidewalk view does")


def frontage_is_assumed() -> bool:
    """Always true today. A function rather than a constant so the day a real
    frontage exists — declared by the user or read from road data — there is one
    place to change and the callers already ask."""
    return True


# ── The six cues ─────────────────────────────────────────────────────────────

def _cue_mown_edge(project: dict) -> Cue:
    """A mown or deliberately managed strip. The single strongest cue there is:
    it is what tells a passer-by the meadow behind it is on purpose."""
    shapes = _shape_types(project)
    has = bool(shapes & set(_LAWN_SHAPES)
               or shapes & _lawn_zone_labels()
               or _structure_ids(project) & set(_LAWN_STRUCTURES))
    if has:
        return Cue(MOWN_EDGE, True,
                   "There is a mown or managed strip — the strongest single "
                   "signal that the planting behind it is intended.")
    return Cue(MOWN_EDGE, False,
               f"No mown or managed strip along the frontage ({FRONTAGE_NOTE}). "
               f"A mown metre at the front is the cheapest way to make "
               f"everything behind it read as deliberate.")


def _cue_crisp_border(project: dict) -> Cue:
    """A hard edge around the planting — a drawn bed, a boundary, or a fence."""
    shapes = _shape_types(project)
    has = bool(shapes & set(_BED_SHAPES)
               or _has_boundary(project)
               or _structure_ids(project) & set(_BORDER_STRUCTURES))
    if has:
        return Cue(CRISP_BORDER, True,
                   "The planting has a defined edge — a bed line, boundary or "
                   "fence gives the eye somewhere to stop.")
    return Cue(CRISP_BORDER, False,
               "No defined edge around the planting. An edge — a bed line, a "
               "low fence, even a cut margin — is what separates 'wild' from "
               "'abandoned' to someone walking past.")


def _cue_height_graded(project: dict,
                       get_plant: Optional[Callable] = None) -> Cue:
    """Tall at the back, low at the front.

    Reuses ``placement_score._height_gradient`` rather than restating the
    thresholds, so the critique and the generator's own aesthetic scoring agree
    about what "graded" means.
    """
    from src.placement_score import _height_gradient

    plants = _placed(project)
    if len(plants) < 3:
        return Cue(HEIGHT_GRADED, None, "")
    lats = [p.get("lat") for p in plants if p.get("lat") is not None]
    if not lats:
        return Cue(HEIGHT_GRADED, None, "")
    lo, hi = min(lats), max(lats)
    span = hi - lo
    if span <= 0:
        return Cue(HEIGHT_GRADED, None, "")

    if get_plant is None:
        from src.db.plants import get_plant as _gp
        get_plant = _gp

    cache: dict = {}
    scores = []
    for p in plants:
        pid = p.get("plant_id")
        if pid not in cache:
            try:
                cache[pid] = get_plant(pid) or {}
            except Exception:                              # noqa: BLE001
                cache[pid] = {}
        row = cache[pid]
        try:
            height = float(row.get("mature_height_meters") or 0.0)
        except (TypeError, ValueError):
            height = 0.0
        if height <= 0:
            continue                    # unknown height votes on nothing
        north_frac = (float(p["lat"]) - lo) / span
        scores.append(_height_gradient(height, north_frac))
    if not scores:
        return Cue(HEIGHT_GRADED, None, "")

    mean = sum(scores) / len(scores)
    if mean >= GRADED_HIGH:
        return Cue(HEIGHT_GRADED, True,
                   "Heights step up toward the back, so the whole planting is "
                   "visible from the front.")
    if mean <= GRADED_LOW:
        return Cue(HEIGHT_GRADED, False,
                   "The tallest plants are toward the front, which screens "
                   "everything behind them — from the street this reads as a "
                   "thicket rather than as a planting.")
    return Cue(HEIGHT_GRADED, None, "")


def _cue_visible_path(project: dict) -> Cue:
    """A path or entry. Access is a cue: it says a person comes in here."""
    if _shape_types(project) & set(_PATH_SHAPES):
        return Cue(VISIBLE_PATH, True,
                   "There is a path or hard surface — a way in tells people "
                   "the space is used, not just left.")
    return Cue(VISIBLE_PATH, False,
               "No path or entry drawn. Even a short mown or gravel way in "
               "signals that somebody tends this.")


def _cue_showy_repeat(project: dict,
                      get_plant: Optional[Callable] = None) -> Cue:
    """One conspicuous plant, repeated enough to read as a decision.

    Grasses, sedges and rushes are excluded deliberately: ``flower_colour``
    buckets them as wind-pollinated and their swatch is the *absence* of a showy
    flower, so counting them here would credit the design for a repeat nobody
    can see.
    """
    from src.flower_colour import WIND_POLLINATED_TYPES, classify

    plants = _placed(project)
    if not plants:
        return Cue(SHOWY_REPEAT, None, "")

    if get_plant is None:
        from src.db.plants import get_plant as _gp
        get_plant = _gp

    counts: dict = {}
    for p in plants:
        pid = p.get("plant_id")
        counts[pid] = counts.get(pid, 0) + 1

    best_name, best_n = "", 0
    for pid, n in counts.items():
        if n < REPEAT_MIN:
            continue
        try:
            row = get_plant(pid) or {}
        except Exception:                                  # noqa: BLE001
            continue
        if (row.get("plant_type") or "").lower() in WIND_POLLINATED_TYPES:
            continue
        try:
            bucket = classify(row)
        except Exception:                                  # noqa: BLE001
            bucket = ""
        if not bucket or bucket in ("", "none", "grass"):
            continue
        if n > best_n:
            best_name, best_n = (row.get("common_name")
                                 or p.get("common_name") or "one species"), n
    if best_n:
        return Cue(SHOWY_REPEAT, True,
                   f"{best_name} repeats {best_n} times — a repeated showy "
                   f"plant is what makes a mixed planting read as composed "
                   f"rather than accidental.")
    return Cue(SHOWY_REPEAT, False,
               f"No showy species is repeated {REPEAT_MIN}+ times. One "
               f"conspicuous plant, used again and again, does more for how "
               f"this is received than any other single change.")


def _cue_sign() -> Cue:
    """Not a check. Nothing in this app represents a sign, so this is offered as
    a suggestion — and saying otherwise would be a measurement of nothing."""
    return Cue(SIGN, None,
               "Consider room for a small sign. Naming the planting — "
               "\"pollinator garden\", a habitat certification — converts it "
               "from something odd into something explained, and it is the "
               "cheapest cue to care there is.")


# ── The public API ───────────────────────────────────────────────────────────

def assess(project: dict, *, get_plant: Optional[Callable] = None) -> list:
    """Every cue, in the order they matter to a passer-by."""
    return [
        _cue_mown_edge(project),
        _cue_crisp_border(project),
        _cue_height_graded(project, get_plant=get_plant),
        _cue_visible_path(project),
        _cue_showy_repeat(project, get_plant=get_plant),
        _cue_sign(),
    ]


def missing(project: dict, *, get_plant: Optional[Callable] = None) -> list:
    """Only the cues that are absent — what to act on."""
    return [c for c in assess(project, get_plant=get_plant)
            if c.present is False]


def cue_lines(project: dict, *, get_plant: Optional[Callable] = None,
              limit: int = 4) -> list:
    """Lines to show, absences first, then the sign prompt.

    Present cues are not listed: a panel that recites what is already fine
    buries the one thing worth changing. The count is available separately for
    callers that want to say "4 of 5".
    """
    cues = assess(project, get_plant=get_plant)
    out = [c.line for c in cues if c.present is False]
    if len(out) < limit:
        out += [c.line for c in cues if c.present is None and c.line]
    return out[:limit]


def tally(project: dict, *, get_plant: Optional[Callable] = None) -> tuple:
    """``(present, judged)`` — how many cues are there, out of how many could be
    judged at all. The sign prompt and anything indeterminate are excluded from
    both, so the ratio never implies a verdict that was not reached."""
    cues = assess(project, get_plant=get_plant)
    judged = [c for c in cues if c.present is not None]
    return (sum(1 for c in judged if c.present), len(judged))

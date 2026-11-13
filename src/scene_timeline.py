"""
scene_timeline.py — what the years did to a plan, said where and which
(V3.46, F263; 3D-4 of docs/plans/V3.43-the-3d-preview-reviewed.md, decision D4).

Design principle P5 (make invisible ecology visible) and P9 (confidence, never
false precision) — see docs/DESIGN_PHILOSOPHY.md.

The V3.43 review's finding 6: the preview quietly kills the plan. On the review
lot the shade model takes 37% of a fresh plan by the fifth summer, and until
V3.43 nothing said so at all. Since then the line over the picture has counted
them ("136 lost to shade"), which says how many and nothing a person can act
on: not where, not which plants, not what shades them. A thin bed could be a
plan that failed or a preview that is wrong, and the picture did not say which.

:func:`notes` is ``scene["timeline_notes"]``, decided here once and shown by
the viewer's chip (``html/scene3d/25b-timeline.js``):

* one note per **place** plants were lost to shade: the drawn area they are in
  (a bed, a lawn), else the rest of the yard, with how many of how many, what
  shades most of them, and the kinds;
* one for the short-lived kinds that have lived out their years, which is how
  those kinds grow and is said as that;
* one for the gaps the plan's own plants have since seeded into.

**What shades them is the shade model's own answer**
(``SuccessionEngine.main_shader``), named the way the scene knows the thing: a
tree already here, the house, a building next door, a tree the plan planted.
Nothing here re-derives shade.

**Front and back are said only where the street's side is known** (told by the
person or measured from the road lines, V3.45's rule for drawing the street);
otherwise the compass.

It is the model's estimate, and ``about`` says so in the words the chip shows.
Qt-free. Its strings are the simple app's (``tests/test_vocabulary.py``).
"""

from __future__ import annotations

import math
from collections import Counter
from typing import Mapping, Optional

#: What a drawn area is called in a sentence, by the scene's surface kind
#: (``scene_site.KINDS``; a test keeps every kind worded).
PLACE_WORDS = {
    "bed": "garden bed", "mulch": "mulched area", "lawn": "lawn",
    "meadow": "meadow", "young_meadow": "young meadow",
    "seeded": "seeded area", "water": "water", "path": "path",
    "patio": "paving", "custom": "drawn area",
}
#: Plants in no drawn area.
ELSEWHERE = "the rest of the yard"
WHOLE_YARD = "the yard"

#: How far from the yard's middle (as a share of its half-size) still reads as
#: the middle, and as neither front nor back.
_MIDDLE = 0.2
#: A cause is named when it accounts for at least this share of a place's losses.
_MOSTLY = 0.5
#: Kinds listed per note before "and N other kinds".
_KINDS_SHOWN = 5

ABOUT = ("This is the app's estimate of shade over the years, from the plants "
         "as they grow, the trees and buildings on the map and how much sun "
         "each plant needs. A guide, not a forecast. Plants that take more "
         "shade would last in these spots: on the map, click one and choose "
         "Swap.")


# ── geometry ─────────────────────────────────────────────────────────────────

def _in_ring(x: float, y: float, ring: list) -> bool:
    inside = False
    j = len(ring) - 1
    for i in range(len(ring)):
        ax, ay = ring[j][0], ring[j][1]
        bx, by = ring[i][0], ring[i][1]
        if (ay > y) != (by > y) and x < (bx - ax) * (y - ay) / (by - ay) + ax:
            inside = not inside
        j = i
    return inside


def _centre(ring: list) -> tuple:
    return (sum(p[0] for p in ring) / len(ring),
            sum(p[1] for p in ring) / len(ring))


def _box(ring: list) -> dict:
    xs, ys = [p[0] for p in ring], [p[1] for p in ring]
    return {"min_x": min(xs), "max_x": max(xs), "min_y": min(ys), "max_y": max(ys)}


_COMPASS = ("north", "north-east", "east", "south-east",
            "south", "south-west", "west", "north-west")


def _compass(dx: float, dy: float) -> str:
    bearing = math.degrees(math.atan2(dx, dy)) % 360.0
    return _COMPASS[int((bearing + 22.5) // 45.0) % 8]


def position_words(x: float, y: float, box: Optional[Mapping],
                   street_bearing: Optional[float] = None) -> str:
    """Where a spot is in the yard: "at the front", "at the back", "on the
    east side", "in the north-west corner", "in the middle of the yard".

    ``street_bearing`` (degrees from north, toward the street) only when the
    street's side is known; without it the compass speaks."""
    if not box:
        return ""
    mx, my = (box["min_x"] + box["max_x"]) / 2, (box["min_y"] + box["max_y"]) / 2
    hw = max(1.0, (box["max_x"] - box["min_x"]) / 2)
    hh = max(1.0, (box["max_y"] - box["min_y"]) / 2)
    dx, dy = x - mx, y - my
    if abs(dx) < _MIDDLE * hw and abs(dy) < _MIDDLE * hh:
        return "in the middle of the yard"
    if street_bearing is not None:
        b = math.radians(street_bearing)
        toward = dx * math.sin(b) + dy * math.cos(b)
        depth = hw * abs(math.sin(b)) + hh * abs(math.cos(b))
        if toward > _MIDDLE * depth:
            return "at the front"
        if toward < -_MIDDLE * depth:
            return "at the back"
        # Beside the house: say which side by the compass.
        across = dx * math.cos(b) - dy * math.sin(b)
        side = (street_bearing + (90.0 if across > 0 else -90.0)) % 360.0
        return f"on the {_COMPASS[int((side + 22.5) // 45.0) % 8]} side"
    name = _compass(dx / hw, dy / hh)
    return f"in the {name} corner" if "-" in name else f"on the {name} side"


# ── naming ───────────────────────────────────────────────────────────────────

def _own_label(surface: Mapping) -> str:
    """The person's own name for a drawn area, or "" when the label is only
    the area's type."""
    label = str(surface.get("label") or "").strip()
    if not label:
        return ""
    from src.scene_site import SURFACE_KINDS                 # noqa: PLC0415
    plain = {k.lower() for k in SURFACE_KINDS} | set(PLACE_WORDS.values())
    return "" if label.lower() in plain else label


def place_of(x: float, y: float, surfaces: list) -> Optional[int]:
    """The index of the drawn area a spot is in (the topmost, as the scene
    piles them), or ``None``: the outline's own lawn is not a drawn area."""
    found = None
    for i, s in enumerate(surfaces or []):
        if s.get("base") or len(s.get("ring") or []) < 3:
            continue
        if _in_ring(x, y, s["ring"]):
            found = i
    return found


def place_words(index: Optional[int], surfaces: list, box: Optional[Mapping],
                street_bearing: Optional[float], any_drawn: bool) -> str:
    if index is None:
        return ELSEWHERE if any_drawn else WHOLE_YARD
    s = surfaces[index]
    words = PLACE_WORDS.get(s.get("kind"), PLACE_WORDS["custom"])
    own = _own_label(s)
    if own:
        return f"the {words} “{own}”"
    where = position_words(*_centre(s["ring"]), box, street_bearing)
    return f"the {words} {where}".strip()


def _tell_apart(wheres: dict, surfaces: list) -> dict:
    """Two beds at the back are both "the garden bed at the back": say which
    by the compass, from the middle of the ones that share the words ("… (the
    north-west one)")."""
    shared: dict = {}
    for place, words in wheres.items():
        shared.setdefault(words, []).append(place)
    out = dict(wheres)
    for words, places in shared.items():
        places = [p for p in places if p is not None]
        if len(places) < 2:
            continue
        centres = {p: _centre(surfaces[p]["ring"]) for p in places}
        mx = sum(c[0] for c in centres.values()) / len(centres)
        my = sum(c[1] for c in centres.values()) / len(centres)
        for p, (cx, cy) in centres.items():
            out[p] = f"{words} (the {_compass(cx - mx, cy - my)} one)"
    return out


def shader_words(shader: Optional[Mapping], plants: list, buildings: list,
                 boundary: Optional[list], house: Optional[list]) -> str:
    """What a caster is called: "the evergreen tree already here", "the
    house", "the building next door", "the Paper Birch in this plan"."""
    if not shader:
        return ""
    if shader.get("kind") == "plant":
        name = shader.get("common_name") or "a tree"
        return f"the {name} in this plan"
    x, y = float(shader["x"]), float(shader["y"])
    for b in buildings or []:
        ring = b.get("ring") or []
        if len(ring) < 3:
            continue
        cx, cy = _centre(ring)
        if not (_in_ring(x, y, ring) or math.hypot(cx - x, cy - y) < 1.0):
            continue
        if b.get("kind") == "canopy":
            return "the tree drawn on the map"
        if house and math.hypot(*(a - c for a, c in
                                  zip(_centre(house), (cx, cy)))) < 0.5:
            return "the house"
        if boundary and _in_ring(cx, cy, boundary):
            return "a building in the yard"
        return "the building next door"
    if shader.get("is_tree"):
        near = min((p for p in plants or [] if p.get("existing")),
                   key=lambda p: math.hypot(p["x"] - x, p["y"] - y),
                   default=None)
        evergreen = ((near or {}).get("foliage_type") == "evergreen"
                     if near and math.hypot(near["x"] - x, near["y"] - y) < 1.0
                     else shader.get("foliage") == "evergreen")
        return ("the evergreen tree already here" if evergreen
                else "the tree already here")
    return "a building"


def _kinds(plants: list) -> list:
    """``[[name, how many], …]``, most first, then by name."""
    counts = Counter(p.get("common_name") or "A plant" for p in plants)
    return [[name, n] for name, n in
            sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))]


def kinds_words(kinds: list) -> str:
    """"Wild Strawberry (20), Smooth Aster (12) and 3 other kinds"."""
    shown = [f"{name} ({n})" if n > 1 else name
             for name, n in kinds[:_KINDS_SHOWN]]
    rest = len(kinds) - len(shown)
    if rest > 0:
        shown.append(f"{rest} other {'kind' if rest == 1 else 'kinds'}")
    if len(shown) <= 1:
        return "".join(shown)
    return ", ".join(shown[:-1]) + " and " + shown[-1]


def _count(n: int, total: int) -> str:
    if total == 1:
        return "The one plant"
    if n == total:
        return f"All {total} plants"
    return f"{n} of the {total} plants"


# ── the notes ────────────────────────────────────────────────────────────────

def notes(*, year: int, when_words: str, engine, placed: Mapping,
          plants: list, surfaces: list, buildings: list,
          boundary: Optional[list], focus: Optional[Mapping],
          street_bearing: Optional[float] = None,
          house: Optional[list] = None) -> Optional[dict]:
    """``scene["timeline_notes"]``: ``{"when", "notes": [...], "about"}``, or
    ``None`` when the years have taken nothing (and at year 0, the design
    fully grown, where nothing is lost).

    ``placed`` maps the shade model's plant index to that plant's scene
    record. A note is ``{"kind": "shade" | "short_lived" | "self_seeded",
    "text", "plants": [[name, n], …], "kinds": those in words, "spots":
    [[x, y], …]}``; a shade note
    also carries ``where``, ``lost``, ``of``, ``struggling`` and ``by``."""
    if int(year) <= 0 or not placed:
        return None
    box = _box(boundary) if boundary else focus
    any_drawn = any(not s.get("base") for s in surfaces or [])
    by_place: dict = {}
    for index, p in placed.items():
        place = place_of(p["x"], p["y"], surfaces)
        row = by_place.setdefault(place, {"all": [], "lost": [], "weak": [],
                                          "by": Counter()})
        row["all"].append(p)
        if p.get("gone") == "shade":
            row["lost"].append(p)
            shader = None
            if engine is not None:
                died = engine.death_year(index, int(year)) or int(year)
                shader = engine.main_shader(index, died)
            row["by"][shader_words(shader, plants, buildings, boundary,
                                   house)] += 1
        elif p.get("health_state") == "declining" and not p.get("gone"):
            row["weak"].append(p)

    wheres = _tell_apart({
        place: place_words(place, surfaces, box, street_bearing, any_drawn)
        for place, row in by_place.items() if row["lost"]}, surfaces)
    out = []
    for place, row in by_place.items():
        lost, total = len(row["lost"]), len(row["all"])
        if not lost:
            continue
        where = wheres[place]
        cause, n = (row["by"].most_common(1) or [("", 0)])[0]
        text = (f"{_count(lost, total)} in {where} "
                f"{'is' if total == 1 or lost == 1 else 'are'} shaded out by "
                f"{when_words}")
        if cause and n >= _MOSTLY * lost:
            text += (f", by {cause}" if n == lost
                     else f", most of them by {cause}")
        elif len([c for c in row["by"] if c]) > 1:
            text += ", by more than one tree or building"
        text += "."
        weak = len(row["weak"])
        if weak:
            text += (f" {weak} more {'is' if weak == 1 else 'are'} struggling "
                     "in the shade.")
        out.append({"kind": "shade", "where": where, "lost": lost, "of": total,
                    "struggling": weak, "by": cause, "text": text,
                    "plants": _kinds(row["lost"]),
                    "kinds": kinds_words(_kinds(row["lost"])),
                    "spots": [[p["x"], p["y"]] for p in row["lost"]]})
    out.sort(key=lambda note: (-note["lost"], note["where"]))

    lived = [p for p in placed.values() if p.get("gone") == "short_lived"]
    if lived:
        n = len(lived)
        out.append({
            "kind": "short_lived", "lost": n,
            "text": (f"{n} {'plant' if n == 1 else 'plants'} of kinds that "
                     f"fill in first and then give way "
                     f"{'has' if n == 1 else 'have'} lived out "
                     f"{'its' if n == 1 else 'their'} years by {when_words}. "
                     "That is how those kinds grow, not a fault in the plan."),
            "plants": _kinds(lived), "kinds": kinds_words(_kinds(lived)),
            "spots": [[p["x"], p["y"]] for p in lived]})

    seeded = [p for p in plants or [] if p.get("recruit")]
    if seeded:
        n = len(seeded)
        out.append({
            "kind": "self_seeded", "count": n,
            "text": (f"{n} of the gaps {'has' if n == 1 else 'have'} been "
                     "taken by plants already in the plan, seeding or "
                     "creeping in from beside them."),
            "plants": _kinds(seeded), "kinds": kinds_words(_kinds(seeded)),
            "spots": [[p["x"], p["y"]] for p in seeded]})

    if not out:
        return None
    return {"when": when_words, "notes": out, "about": ABOUT}

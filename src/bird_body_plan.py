"""
bird_body_plan.py — which body a bird is drawn with, and where it stands (F174,
V2.97).

Design principle P5 — see docs/DESIGN_PHILOSOPHY.md. The 3D scene drew every
bird as one of three builds picked by words in its common name, and perched
every one inside the crown of a plant it is tied to. So a Sandhill Crane sat
0.74 m up an arrowhead as a three-metre songbird, a Snow Goose among the stems
of a saltgrass, a Red-tailed Hawk inside a poplar's leaves, and a Ruffed Grouse
in a bearberry mat 15 cm tall. Over 400 random designs those birds were in 45%
of them. Seeing where an animal lives is the point of drawing it; drawing it
where it could not be teaches the opposite.

Two things here, both decided once, in Python, for the viewer to draw:

* **the body** — the build in ``html/assets/models/fauna_bird.glb``, from the
  bird's GENUS (:data:`PLAN_BY_GENUS`), a recorded field, where the name words
  could only ever find woodpeckers and hummingbirds;
* **where it stands** — :func:`place`, by the build's stance: perched in a crown
  (the songbirds, as before), on the top of a real tree (hawks, owls), on the
  ground beside its plant (grouse, cranes), or on a pond's water (ducks, geese).

The builds are authored in ``scripts/blender/assetlib/bird_builds.py`` with
their wings at their birds' real span, so the model's width is its wingspan;
this module mirrors the three numbers the placement needs from there
(:data:`PERCH_PITCH`, :data:`WATERLINE`, :data:`PERCH_FOOT`) and
``tests/test_bird_body_plan.py`` keeps the copies equal. The colours are the table ``scene_wildlife`` carried,
moved unchanged: bird colours are F172's, and need a source.

Qt-free and DB-free.
"""

from __future__ import annotations

import math
from typing import Callable, Optional

from src.pond_habit import POND_WATER_RX, POND_WATER_RY, WATER_SURFACE_M

# ── The body ──────────────────────────────────────────────────────────────────

#: Genus → build. The catalogue's genera, and the ones next to them in the same
#: families a prairie list is likely to add.
PLAN_BY_GENUS = {
    # hawks and falcons
    "falco": "raptor", "buteo": "raptor", "accipiter": "raptor",
    "circus": "raptor",
    # owls
    "bubo": "owl", "strix": "owl", "asio": "owl", "aegolius": "owl",
    "athene": "owl", "megascops": "owl", "glaucidium": "owl",
    # grouse and ptarmigan
    "bonasa": "grouse", "lagopus": "grouse", "dendragapus": "grouse",
    "canachites": "grouse", "tympanuchus": "grouse", "centrocercus": "grouse",
    # ducks, geese, cranes
    "anas": "duck", "spatula": "duck", "mareca": "duck", "aythya": "duck",
    "bucephala": "duck", "anser": "goose", "branta": "goose", "chen": "goose",
    "grus": "crane", "antigone": "crane",
    # woodpeckers and hummingbirds (what the name words used to find)
    "dryobates": "woodpecker", "picoides": "woodpecker", "colaptes": "woodpecker",
    "sphyrapicus": "woodpecker", "melanerpes": "woodpecker",
    "dryocopus": "woodpecker",
    "archilochus": "hummer", "selasphorus": "hummer", "calypte": "hummer",
}

#: For a bird with no scientific name only: the words the name table used.
_NAME_WORDS = (("woodpecker", "woodpecker"), ("sapsucker", "woodpecker"),
               ("flicker", "woodpecker"), ("hummingbird", "hummer"))

#: Where each build stands.
STANCE = {"passerine": "crown", "woodpecker": "crown", "hummer": "crown",
          "raptor": "tree", "owl": "tree", "grouse": "ground",
          "crane": "ground", "duck": "water", "goose": "water"}

#: How far a build is tipped nose-up on a perch, radians; the songbirds use the
#: viewer's own 0.45. Mirrors assetlib/bird_builds.BIRD_PERCH_PITCH: the hawk
#: and owl are built level, as they fly, with their heads turned down by about
#: as much, so upright on the branch they look ahead.
PERCH_PITCH = {"raptor": 1.0, "owl": 1.2}

#: How high above its feet a swimming build floats, per metre of wingspan
#: (assetlib/bird_builds.waterline).
WATERLINE = {"duck": 0.1062, "goose": 0.118}

#: How far below its centre a tree build's body reaches on the perch, per metre
#: of wingspan (assetlib/bird_builds.perch_foot): its centre sits this high over
#: the top it grips.
PERCH_FOOT = {"raptor": 0.1052, "owl": 0.1367}

#: A hawk or owl perches only on a tree drawn at least this tall, on its top.
TREE_MIN_M = 3.0
#: A ground bird stands IN a plant this low (a mat, a sedge), BESIDE a taller one.
LOW_PLANT_M = 0.4
#: A hawk with no tree to sit in circles this high over the design.
SOAR_M = 25.0
_SOAR_R = (8.0, 18.0)


def plan_for(scientific_name: str, common_name: str = "") -> str:
    """The build a bird is drawn with."""
    genus = (scientific_name or "").strip().split(" ")[0].lower()
    if genus in PLAN_BY_GENUS:
        return PLAN_BY_GENUS[genus]
    if not genus:
        n = (common_name or "").lower()
        for word, plan in _NAME_WORDS:
            if word in n:
                return plan
    return "passerine"


def appearance(name: str, scientific_name: str = "") -> dict:
    """The appearance bag the viewer draws a bird from.

    The colours are ``scene_wildlife``'s name table, unchanged (V2.97 moved it
    here): the look of a species nobody has described, which F172 will correct
    against a source. The build, whether it hovers, and how it sits come from
    :func:`plan_for`."""
    n = (name or "").lower()
    plan = plan_for(scientific_name, name)

    def spec(body, belly, wing, size=1.0):
        out = {"kind": "bird", "body": body, "belly": belly, "wing": wing,
               "size": size, "hummer": plan == "hummer", "build": plan,
               "anim": "hover" if plan == "hummer" else "perch"}
        if plan in PERCH_PITCH:
            out["perch_pitch"] = PERCH_PITCH[plan]
        return out
    if "hummingbird" in n:          return spec("#2f7d4f", "#d8cbb0", "#3a2a20", 0.5)
    if "goldfinch" in n:            return spec("#e8c72e", "#f0e6b0", "#1c1c14", 0.7)
    if "waxwing" in n:              return spec("#b79a72", "#d8c8a0", "#3a2c22", 0.85)
    if "robin" in n:               return spec("#4a4038", "#b5502e", "#2a241e", 1.0)
    if "blue jay" in n:            return spec("#3f6fb0", "#eef2f5", "#20304a", 1.0)
    if "jay" in n:                 return spec("#6a7480", "#d8dde0", "#3a4048", 1.0)
    if "magpie" in n:              return spec("#1c1e22", "#eef2f5", "#20304a", 1.1)
    if "chickadee" in n:           return spec("#8a8f92", "#e8eef0", "#2a2c2e", 0.55)
    if "nuthatch" in n:            return spec("#5a6a80", "#c88a5a", "#2a3140", 0.55)
    if "warbler" in n:             return spec("#e0d24a", "#e7e0a0", "#6a6a2e", 0.55)
    if "woodpecker" in n or "flicker" in n: return spec("#c8b48a", "#e0d6b8", "#2a241e", 0.8)
    if "sparrow" in n or "junco" in n or "siskin" in n or "redpoll" in n:
        return spec("#8a7a60", "#d8cbb0", "#3a3026", 0.6)
    if "grosbeak" in n:            return spec("#b5482e", "#d8a0a0", "#3a2620", 0.75)
    if "hawk" in n or "kestrel" in n or "merlin" in n: return spec("#7a5a3a", "#e0d2b0", "#3a2a1e", 1.2)
    if "owl" in n:                 return spec("#6a5a44", "#c8b48a", "#3a3020", 1.2)
    if "grouse" in n:              return spec("#7a6a4a", "#c0a878", "#3a3020", 1.1)
    return spec("#8a7a60", "#cbbb90", "#3a3026", 0.7)


# ── Where it stands ───────────────────────────────────────────────────────────

def place(creature: dict, anchor: dict, plants: list, scene: dict,
          food: list, drawn_height: Callable[[dict], float],
          taken: Optional[set] = None, rels: Optional[dict] = None) -> bool:
    """Put a bird ``creature`` (a ``wildlife_for_scene`` record) where its build
    stands, rewriting its position, ``h``, ``route`` and ``app["anim"]``.

    ``anchor`` is the plant it was given, ``plants`` every plant as drawn,
    ``food`` every plant in the design this species is tied to, by any
    relationship, and ``rels`` that relationship per plant id, for the label
    when the bird sits on another of them. ``drawn_height`` is how tall the
    viewer draws a plant. ``taken`` holds the tree tops already sat on in this
    scene, so two hawks do not share one; the caller keeps it. False means the
    bird has nowhere to be here and is not drawn: an owl with no tree."""
    app = creature.get("app") or {}
    plan = app.get("build") or "passerine"
    stance = STANCE.get(plan, "crown")
    if stance == "crown":
        return True
    seed = int(creature.get("seed") or 0)
    if stance == "tree":
        taken = set() if taken is None else taken
        trees = [p for p in plants
                 if p.get("plant_type") == "tree"
                 and p.get("health_state") != "dead"
                 and drawn_height(p) >= TREE_MIN_M]
        # It sits on a tree it is tied to: its own, else another of its trees
        # in the design, nearest first; never on a top another bird holds.
        mine = sorted((t for t in trees
                       if (t is anchor or any(t is f for f in food))
                       and _top_key(t) not in taken),
                      key=lambda t: (t is not anchor, _d2(t, anchor)))
        if not mine:
            if plan == "owl":
                return False
            _soar(creature, plants, seed)
            return True
        home = mine[0]
        taken.add(_top_key(home))
        if home is not anchor:          # the label names the tree it is on
            creature["on"] = home.get("common_name", creature.get("on", ""))
            creature["on_id"] = home.get("plant_id", creature.get("on_id"))
            creature["rel"] = (rels or {}).get(home.get("plant_id"),
                                               creature.get("rel", ""))
        span = float((creature.get("size") or {}).get("m") or 0.5)
        # Then between its tree and the nearest other tall ones, top to top.
        others = sorted((t for t in trees if t is not home),
                        key=lambda t: _d2(t, home))[:3]
        route = [_tree_top(t, span, plan, drawn_height) for t in [home] + others]
        _set(creature, route, home["x"], home["y"], "perch")
        return True
    if stance == "water":
        pond = _nearest_pond(scene, anchor)
        if pond is not None:
            _on_the_water(creature, pond, plan, seed)
            return True
    _on_the_ground(creature, anchor, plants, food, seed, drawn_height)
    return True


def _set(creature, route, ax, ay, anim):
    creature["x"], creature["y"], creature["h"] = route[0]
    creature["route"] = [list(w) for w in route]
    creature["_ax"], creature["_ay"] = ax, ay
    creature["_fixed"] = True               # spacing leaves a stance alone
    creature["app"]["anim"] = anim


def _d2(a, b):
    return (a["x"] - b["x"]) ** 2 + (a["y"] - b["y"]) ** 2


def _angle(seed: int) -> float:
    return (seed % 360) * math.pi / 180.0


def _top_key(t):
    return (round(float(t["x"]), 2), round(float(t["y"]), 2))


def _tree_top(t, span, plan, drawn_height):
    """On the tree's top, feet on the tip: where hawks, falcons and owls sit to
    watch, and the one point every crown the viewer draws has. Partway out and
    partway up is inside a poplar's leaves and in the air beside a spruce, which
    has narrowed to a spire by then."""
    return (round(t["x"], 2), round(t["y"], 2),
            round(drawn_height(t) + PERCH_FOOT.get(plan, 0.1) * span, 2))


def _soar(creature, plants, seed):
    """No tree to sit in (a young design): circle over the yard, wings spread."""
    xs = [p["x"] for p in plants] or [0.0]
    ys = [p["y"] for p in plants] or [0.0]
    cx, cy = sum(xs) / len(xs), sum(ys) / len(ys)
    spread = max(max(xs) - min(xs), max(ys) - min(ys)) / 2.0
    r = min(_SOAR_R[1], max(_SOAR_R[0], spread))
    start = _angle(seed)
    route = [(round(cx + math.cos(start + k * math.pi / 4) * r, 2),
              round(cy + math.sin(start + k * math.pi / 4) * r, 2), SOAR_M)
             for k in range(8)]
    _set(creature, route, cx, cy, "soar")


def _ground_spot(p, seed, drawn_height):
    """In the patch of a low plant, at the crown's edge of a taller one: a grouse
    eats bearberry standing in it, and nothing stands inside a shrub."""
    a = _angle(seed * 11 + 5)
    c = max(0.3, float(p.get("canopy_m") or 0.5))
    r = c * 0.3 if drawn_height(p) <= LOW_PLANT_M else c / 2.0 + 0.25
    return (round(p["x"] + math.cos(a) * r, 2), round(p["y"] + math.sin(a) * r, 2), 0.0)


def _on_the_ground(creature, anchor, plants, food, seed, drawn_height):
    """Stand at its plant and walk between its plants, and a couple of others
    near, pausing to feed. Feet on the ground: a ground build's origin is its
    feet (assetlib/bird_builds.GROUND_BUILDS)."""
    stops = [anchor] + [q for q in food if q is not anchor][:3]
    near = sorted((q for q in plants if all(q is not s for s in stops)),
                  key=lambda q: _d2(q, anchor))
    stops += [q for q in near if _d2(q, anchor) <= 12.0 ** 2][:2]
    route = [_ground_spot(q, seed + i, drawn_height) for i, q in enumerate(stops)]
    _set(creature, route, anchor["x"], anchor["y"], "walk")


def _nearest_pond(scene, anchor) -> Optional[dict]:
    ponds = [s for s in (scene.get("structures") or [])
             if s.get("struct_id") == "pond" and float(s.get("size_m") or 0) > 0]
    if not ponds:
        return None
    return min(ponds, key=lambda s: _d2(s, anchor))


def _on_the_water(creature, pond, plan, seed):
    """Afloat on the water the viewer draws (pond_habit), sunk to its waterline,
    drifting between points on the same pond."""
    size = float(pond["size_m"])
    rx, ry = POND_WATER_RX * size, POND_WATER_RY * size
    span = float((creature.get("size") or {}).get("m") or 0.5)
    h = round(WATER_SURFACE_M - WATERLINE.get(plan, 0.11) * span, 3)
    start = _angle(seed)
    route = []
    for k in range(4):
        a = start + k * math.pi / 2 + ((seed >> (3 * k)) % 5) * 0.12
        f = 0.35 + 0.25 * (((seed >> (2 * k)) % 4) / 3.0)
        route.append((round(pond["x"] + math.cos(a) * rx * f, 2),
                      round(pond["y"] + math.sin(a) * ry * f, 2), h))
    _set(creature, route, pond["x"], pond["y"], "walk")

"""
scene_wildlife.py — populate a 3D scene with the animals the design's plants
actually support (V2.12). Given the built scene's plants, it reads the
documented plant↔fauna edges and returns a capped, deterministic list of ambient
creatures — bees, butterflies, moths, birds, flower flies / dragonflies, beetles
and small mammals — each placed on or near a plant it uses, and each carrying a
compact *appearance* spec so the viewer can draw it looking like its real
species (a green metallic sweat bee ≠ a fuzzy bumble bee ≠ a leafcutter).

This is the data behind "walk the garden and meet its wildlife": the plant→animal
edge is made visible and literal (P3, P10 — relationships are the unit of value;
P5 — start from what the design already supports; P8 — the habitat you built,
inhabited). Honest per P9: only creatures with a *documented* edge to a present
plant are placed — nothing is invented.

Qt-free — the 3D window computes this from the DB and pushes it to the viewer via
``permaSetWildlife``. See docs/DESIGN_PHILOSOPHY.md.
"""

from __future__ import annotations

import math
from typing import Callable, Optional

# Per-taxon caps so a diverse yard shows a balanced community, not 40 bees.
_TAXON_CAP = {"bee": 8, "lepidoptera": 7, "bird": 6, "other_insect": 5, "mammal": 3}
_TOTAL_CAP = 26

# Relationships that make sense to *stand an animal on*, best-first per taxon —
# a bird on a fruiting shrub, a bee on a nectar flower, a mammal by cover.
_REL_PRIORITY = {
    "bee": ("nectar", "pollen"),
    "lepidoptera": ("nectar", "larval_host"),
    "bird": ("fruit_food", "nectar", "seed_food", "cover", "nesting"),
    "other_insect": ("nectar", "pollen", "cover"),
    "mammal": ("seed_food", "cover"),
}

_GOLDEN = math.pi * (3 - math.sqrt(5))


def _hash(*parts) -> int:
    h = 0
    for p in parts:
        for ch in str(p):
            h = (h * 31 + ord(ch)) & 0x7FFFFFFF
    return h


# ── Appearance ────────────────────────────────────────────────────────────────
# Each returns a compact dict the viewer turns into low-poly geometry. Colours
# encode the real look; the viewer never hard-codes a species.

def _bee_appearance(genus: str, name: str) -> dict:
    """Bee look by genus — the field marks that separate our native bees."""
    g = (genus or "").lower()
    # (fuzz, dark, bands, shape, size, metallic)
    table = {
        "bombus":      ("#f2c12e", "#26211c", 2, "round",   1.0,  False),  # bumble
        "anthophora":  ("#c9a06a", "#3a2c1e", 1, "stout",   0.8,  False),  # digger
        "andrena":     ("#8a7a63", "#2a2520", 2, "slender", 0.7,  False),  # mining
        "osmia":       ("#3a6b63", "#1d2b33", 0, "stout",   0.6,  True),   # mason (blue-green)
        "megachile":   ("#d8cbb0", "#2a2620", 3, "stout",   0.75, False),  # leafcutter
        "halictus":    ("#9a8f7a", "#2a2622", 3, "slender", 0.55, False),  # sweat
        "lasioglossum":("#7d7568", "#26231e", 2, "slender", 0.5,  False),  # tiny sweat
        "agapostemon": ("#3fae5a", "#2c6b3a", 1, "slender", 0.6,  True),   # green sweat
        "melissodes":  ("#c2a274", "#3a2c1e", 2, "round",   0.75, False),  # long-horned
        "eucera":      ("#c2a274", "#3a2c1e", 2, "round",   0.75, False),
        "colletes":    ("#caa878", "#3a2c20", 2, "stout",   0.7,  False),  # plasterer
        "diadasia":    ("#c9a877", "#3a2c1e", 1, "stout",   0.7,  False),
    }
    cuckoo = {"nomada", "triepeolus", "epeolus", "melecta", "xeromelecta", "zacosmia"}
    if g in cuckoo:
        return {"kind": "bee", "fuzz": "#b5462e", "dark": "#241a16", "bands": 2,
                "shape": "slender", "size": 0.6, "metallic": False, "cuckoo": True}
    fuzz, dark, bands, shape, size, metallic = table.get(
        g, ("#e0a92a", "#2a231c", 2, "round", 0.7, False))       # generic bee
    return {"kind": "bee", "fuzz": fuzz, "dark": dark, "bands": bands,
            "shape": shape, "size": size, "metallic": metallic}


def _lep_appearance(name: str, sci: str, kind: str) -> dict:
    """Butterfly/moth wing colourway keyed off the well-known species."""
    n = (name or "").lower()
    def spec(fore, hind, edge, size=1.0):
        return {"kind": kind, "fore": fore, "hind": hind, "edge": edge, "size": size}
    if "monarch" in n:                 return spec("#e2711d", "#e2711d", "#1c140e", 1.2)
    if "swallowtail" in n:             return spec("#f2d64b", "#f2d64b", "#1c140e", 1.25)
    if "mourning cloak" in n:          return spec("#5a3420", "#5a3420", "#e8d18a", 1.1)
    if "tortoiseshell" in n:           return spec("#c9531f", "#3a2414", "#e0b25a", 0.95)
    if "painted lady" in n:            return spec("#d98a3d", "#caa06a", "#2a1c12", 0.95)
    if "red admiral" in n:             return spec("#2a1c14", "#2a1c14", "#c8352a", 0.95)
    if "white admiral" in n:           return spec("#20242a", "#20242a", "#eef2f5", 1.05)
    if "fritillary" in n:              return spec("#d07b2c", "#b06a28", "#2a1c10", 1.0)
    if "wood-nymph" in n or "ringlet" in n: return spec("#6a5638", "#6a5638", "#c9a45a", 0.85)
    if "azure" in n or "blue" in n:    return spec("#7fa6e0", "#9fc0ea", "#2a2c34", 0.6)
    if "sulphur" in n:                 return spec("#eddc4b", "#e6d24a", "#3a3a1e", 0.75)
    if "crescent" in n:                return spec("#d0782c", "#a85f24", "#2a1c10", 0.7)
    if "skipper" in n:                 return spec("#c08a3a", "#7a5228", "#2a1c10", 0.7)
    if "clearwing" in n or "hummingbird" in n: return spec("#5a7a3a", "#8a5a3a", "#2a1c12", 0.85)
    if "sphinx" in n or "hawk" in n or "white-lined" in n: return spec("#7a6a4a", "#b06a4a", "#2a1c12", 1.1)
    if kind == "moth":                 return spec("#8a7a5a", "#6a5a44", "#3a3020", 1.0)
    return spec("#c88a3a", "#a8702c", "#2a1c10", 0.9)


def _bird_appearance(name: str) -> dict:
    n = (name or "").lower()
    def spec(body, belly, wing, size=1.0, hummer=False):
        return {"kind": "bird", "body": body, "belly": belly, "wing": wing,
                "size": size, "hummer": hummer}
    if "hummingbird" in n:          return spec("#2f7d4f", "#d8cbb0", "#3a2a20", 0.5, True)
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


def _insect_appearance(name: str) -> dict:
    n = (name or "").lower()
    if "lady beetle" in n or "ladybug" in n:
        return {"kind": "beetle", "body": "#cc2a22", "spots": True, "size": 0.5}
    if "beetle" in n:
        return {"kind": "beetle", "body": "#3a3a2a", "spots": False, "size": 0.6}
    if "lacewing" in n:
        return {"kind": "fly", "body": "#8fd07a", "elongate": False, "wing": "#e8f5e0", "size": 0.6}
    if "darner" in n or "skimmer" in n or "meadowhawk" in n or "damselfly" in n or "dragon" in n:
        col = "#c0432e" if "meadowhawk" in n else ("#3f7d8a" if "damsel" in n else "#3f8a6a")
        return {"kind": "fly", "body": col, "elongate": True, "wing": "#eef4f8", "size": 0.9}
    # flower flies / hover flies — bee-mimic yellow & black
    return {"kind": "fly", "body": "#e0b53a", "elongate": False, "wing": "#eef4f8", "size": 0.55}


def _mammal_appearance(name: str) -> dict:
    n = (name or "").lower()
    if "bat" in n:
        return {"kind": "mammal", "body": "#3a2f28", "form": "bat", "size": 0.6}
    return {"kind": "mammal", "body": "#8a6f52", "form": "mouse", "size": 0.5}


def appearance_for_fauna(fauna_id: int) -> Optional[dict]:
    """The per-species appearance spec for one fauna id — reused by the
    fly-through so the flown avatar looks like the chosen species (a green sweat
    bee, a leafcutter, a mining bee…). Returns None for taxa without a look."""
    from src.db.fauna import get_fauna
    row = get_fauna(fauna_id)
    return _appearance_for(row) if row else None


def _appearance_for(row: dict) -> Optional[dict]:
    taxon = row.get("taxon")
    name = row.get("common_name", "")
    sci = row.get("scientific_name", "")
    if taxon == "bee":
        genus = sci.split(" ")[0] if sci else ""
        return _bee_appearance(genus, name)
    if taxon == "lepidoptera":
        kind = "moth" if "moth" in name.lower() or "sphinx" in name.lower() \
            or "clearwing" in name.lower() else "butterfly"
        return _lep_appearance(name, sci, kind)
    if taxon == "bird":
        return _bird_appearance(name)
    if taxon == "other_insect":
        return _insect_appearance(name)
    if taxon == "mammal":
        app = _mammal_appearance(name)
        return None if app.get("form") == "bat" else app   # bats are nocturnal — skip by day
    return None


# ── Placement height above the anchor plant's base (metres) ───────────────────

def _perch_height(kind: str, height_m: float, rel: str) -> float:
    h = max(0.1, height_m)
    if kind == "bird":
        return h * (0.72 if h > 1.0 else 1.05)      # in the crown, or just above a herb
    if kind == "beetle":
        return h * 0.45
    if kind == "mammal":
        return 0.06                                  # on the ground
    if kind in ("bee", "fly"):
        return h * 0.9 + 0.15                         # hovering at the flowers
    # butterfly / moth
    return h * 0.92 + 0.1


# ── Main ──────────────────────────────────────────────────────────────────────

def wildlife_for_scene(scene: dict, *,
                       fauna_edges: Optional[Callable] = None,
                       max_creatures: int = _TOTAL_CAP) -> list[dict]:
    """Return ambient creatures for ``scene`` (a ``build_scene`` result).

    ``fauna_edges`` resolves ``plant_ids -> list of fauna+relationship rows``
    (defaults to ``src.db.fauna.fauna_for_plants``; injectable for tests). Each
    returned creature: ``{kind, x, y, h, name, on, rel, seed, app}``.
    """
    plants = [p for p in (scene.get("plants") or []) if p.get("plant_id")]
    if not plants:
        return []
    by_id = {p["plant_id"]: p for p in plants}
    if fauna_edges is None:
        from src.db.fauna import fauna_for_plants as fauna_edges

    rows = fauna_edges(list(by_id.keys()))
    if not rows:
        return []

    # Collapse to one best (plant, relationship) per fauna species, preferring
    # the taxon's most placement-appropriate relationship and a present plant.
    best: dict = {}    # fauna_id -> row (with plant_id)
    for r in rows:
        fid = r.get("id")
        pid = r.get("plant_id")
        if fid is None or pid not in by_id:
            continue
        prio = _REL_PRIORITY.get(r.get("taxon"), ())
        rank = prio.index(r["relationship"]) if r.get("relationship") in prio else len(prio)
        cur = best.get(fid)
        if cur is None or rank < cur["_rank"]:
            best[fid] = {**r, "_rank": rank}

    # Order deterministically, then apply per-taxon caps + a global cap.
    chosen = sorted(best.values(),
                    key=lambda r: (r.get("taxon", ""), r.get("common_name", "")))
    per_taxon: dict = {}
    creatures: list[dict] = []
    for r in chosen:
        taxon = r.get("taxon")
        cap = _TAXON_CAP.get(taxon, 3)
        if per_taxon.get(taxon, 0) >= cap:
            continue
        app = _appearance_for(r)
        if app is None:
            continue
        p = by_id[r["plant_id"]]
        seed = _hash(r.get("id"), r.get("plant_id"))
        # A deterministic offset in a ring around the plant (golden-angle spread),
        # scaled to the plant's canopy so small herbs get tight placement.
        canopy = max(0.3, float(p.get("canopy_m") or 0.5))
        ang = (seed % 360) * math.pi / 180.0
        rad = canopy * (0.35 + 0.4 * ((seed >> 4) % 100) / 100.0)
        dx = math.cos(ang) * rad
        dy = math.sin(ang) * rad
        h = _perch_height(app["kind"], float(p.get("height_m") or 0.5), r.get("relationship", ""))
        creatures.append({
            "kind": app["kind"],
            "x": round(p["x"] + dx, 2),
            "y": round(p["y"] + dy, 2),
            "h": round(h, 2),
            "name": r.get("common_name", ""),
            "on": p.get("common_name", ""),
            "rel": r.get("relationship", ""),
            "seed": seed % 100000,
            "app": app,
        })
        per_taxon[taxon] = per_taxon.get(taxon, 0) + 1
        if len(creatures) >= max_creatures:
            break
    return creatures

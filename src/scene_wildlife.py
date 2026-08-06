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

# Home-range patrol (V2.24). Ranging fliers forage over the whole yard, so they
# get scene-wide route waypoints and stop clumping in the one bed their anchor
# plant happens to sit in (the reported "insects cluster on one part of the map").
# Movement only — the documented host and identity stay put (P9). Ground / crawling
# critters keep to their patch.
_RANGING = frozenset({"bee", "fly", "butterfly", "moth", "bird"})
_PATROL_MIN_M = 3.0      # only patrol to plants at least this far from the anchor
_PATROL_WAYPOINTS = 2    # extra scene-wide legs added to a ranger's route

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

# Which BODY PLAN a genus is modelled with (F67). `shape` was already a
# round/stout/slender word but nothing baked it — every bee was one mesh in a
# different colour. It is the mesh now (assetlib/fauna_variants.BEE_VARIANTS),
# and this is the one place a genus needs a build that is not just its shape:
# a leafcutter's broad head and flat scopa-bearing abdomen is the build a
# non-specialist actually notices, and "stout" does not say it.
_BEE_BUILD = {"megachile": "leafcutter"}


def _bee_appearance(genus: str, name: str, morph: dict = None) -> dict:
    """Bee look — the species' OWN record first, this genus table as the
    fallback (schema v58).

    The table below is what the catalogue had before v58, and it is kept rather
    than deleted for the same reason `03-herbs.js` keeps its genus profile
    behind `growth_form`: it is the honest answer for a species nobody has
    described yet, and 69 bees minus the ones anybody gets round to is a large
    number for a long time. What changed is that a recorded value now WINS,
    where before there was no way to record one.
    """
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
        # Cuckoo bees are nearly hairless and wasp-like — narrow, and the one
        # group where "not furry" is itself the field mark.
        out = {"kind": "bee", "fuzz": "#b5462e", "dark": "#241a16", "bands": 2,
               "shape": "slender", "build": "slender", "size": 0.6,
               "metallic": False, "cuckoo": True}
    else:
        fuzz, dark, bands, shape, size, metallic = table.get(
            g, ("#e0a92a", "#2a231c", 2, "round", 0.7, False))   # generic bee
        out = {"kind": "bee", "fuzz": fuzz, "dark": dark, "bands": bands,
               "shape": shape, "build": _BEE_BUILD.get(g, shape), "size": size,
               "metallic": metallic}
    return _apply_bee_morph(out, morph)


def _apply_bee_morph(out: dict, morph: dict) -> dict:
    """Overlay a species' recorded morphology onto the genus fallback."""
    if not morph:
        return out
    if morph.get("hair_colour"):
        out["fuzz"] = morph["hair_colour"]
    if morph.get("integument_colour"):
        out["dark"] = morph["integument_colour"]
    if morph.get("build"):
        out["build"] = morph["build"]
        # `shape` is the abdomen rescale and `build` the mesh; a leafcutter has
        # its own mesh but a stout abdomen, so they are not the same field.
        out["shape"] = "stout" if morph["build"] == "leafcutter" else morph["build"]
    if morph.get("metallic") is not None:
        out["metallic"] = bool(morph["metallic"])
    if morph.get("scopa_position"):
        out["scopa"] = morph["scopa_position"]
        # No pollen brush at all IS the cuckoo mark — see docs/FAUNA_FIELD_GUIDE.
        out["cuckoo"] = morph["scopa_position"] == "none"
    if morph.get("wing_tint"):
        out["wing_tint"] = morph["wing_tint"]
    if morph.get("band_pattern"):
        # Thorax + T1..T6, resolved to HEX here rather than sent as tokens.
        # The viewer then needs no colour vocabulary at all — the same contract
        # `fore`/`hind`/`edge` already follow — and BAND_COLOUR_HEX stays the
        # one definition instead of being mirrored into JS.
        from src.data_quality import (BAND_COLOUR_HEX,  # noqa: PLC0415
                                      band_pattern_tokens)
        toks = band_pattern_tokens(morph["band_pattern"])
        cols = [BAND_COLOUR_HEX.get(t) for t in toks]
        if cols and cols[0]:
            out["fuzz"] = cols[0]                    # thorax drives the pile
        # An unknown token would be None; drop it rather than paint it black,
        # so a typo shows as a missing segment instead of a plausible bee.
        out["band_colours"] = [c for c in cols[1:] if c]
        # How many of T1..T6 are a contrasting (non-black) colour — the number
        # a person means by "a two-banded bee", and what the GLB's Band0/1/2
        # toggles still key off.
        out["bands"] = min(3, sum(1 for t in toks[1:] if t != "black"))
    if morph.get("body_length_mm"):
        # Real millimetres, compressed. A linear map would make a 6 mm
        # Lasioglossum four pixels beside a 22 mm Bombus; the square root keeps
        # the ORDER honest and every animal visible, which is the trade P9
        # asks for when precision would be useless rather than wrong.
        mm = float(morph["body_length_mm"])
        out["size"] = round(min(1.6, max(0.35, (mm / 13.0) ** 0.5)), 3)
        out["body_length_mm"] = mm
    return out


def _lep_appearance(name: str, sci: str, kind: str, morph: dict = None) -> dict:
    """Butterfly/moth look — the species' OWN record first (schema v58), with
    the name-keyed table below as the fallback.

    That table is seventeen substring tests on a COMMON NAME, which collapsed 31
    species into 16 appearances and matched `"blue" in name` for anything with
    blue in it. It stays as the fallback for an undescribed species and is no
    longer the only answer available.
    """
    n = (name or "").lower()

    def spec(fore, hind, edge, size=1.0, build=None):
        # `build` is the silhouette (assetlib/fauna_variants.LEP_VARIANTS);
        # `kind` stays the day/night behaviour the roster and the flight code
        # already use. A skipper flies by day like a butterfly and looks
        # nothing like one, which is exactly why they are two fields.
        #
        # The recorded morphology is overlaid HERE rather than at each of the
        # seventeen `return spec(...)` branches below, so a species' own record
        # wins on every path without restructuring the table.
        return _apply_lep_morph(
            {"kind": kind, "fore": fore, "hind": hind, "edge": edge,
             "size": size,
             "build": build or ("moth" if kind == "moth" else "butterfly")},
            morph)
    if "monarch" in n:                 return spec("#e2711d", "#e2711d", "#1c140e", 1.2)
    if "swallowtail" in n:             return spec("#f2d64b", "#f2d64b", "#1c140e", 1.25, "swallowtail")
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
    if "skipper" in n:                 return spec("#c08a3a", "#7a5228", "#2a1c10", 0.7, "skipper")
    if "clearwing" in n or "hummingbird" in n: return spec("#5a7a3a", "#8a5a3a", "#2a1c12", 0.85)
    if "sphinx" in n or "hawk" in n or "white-lined" in n: return spec("#7a6a4a", "#b06a4a", "#2a1c12", 1.1)
    if kind == "moth":                 return spec("#8a7a5a", "#6a5a44", "#3a3020", 1.0)
    return spec("#c88a3a", "#a8702c", "#2a1c10", 0.9)


def _apply_lep_morph(out: dict, morph: dict) -> dict:
    """Overlay a lepidopteran's recorded morphology onto the name-keyed
    fallback (schema v58)."""
    if not morph:
        return out
    for src, dst in (("forewing_colour", "fore"), ("hindwing_colour", "hind"),
                     ("margin_colour", "edge")):
        if morph.get(src):
            out[dst] = morph[src]
    if morph.get("wing_shape"):
        out["wing_shape"] = morph["wing_shape"]
        # A tailed hind wing is the one shape with its own baked silhouette.
        if morph["wing_shape"] == "tailed":
            out["build"] = "swallowtail"
    for key in ("wing_pattern", "resting_posture", "flight_style"):
        if morph.get(key):
            out[key] = morph[key]
    if morph.get("eyespot_count") is not None:
        out["eyespots"] = int(morph["eyespot_count"])
    lo, hi = morph.get("wingspan_min_mm"), morph.get("wingspan_max_mm")
    if lo and hi:
        # The catalogue keeps the published RANGE; the viewer has to draw one
        # animal, so it takes the mid — the single place that collapse happens,
        # and it is a rendering decision rather than a data one.
        mm = (float(lo) + float(hi)) / 2.0
        out["wingspan_mm"] = mm
        # Compressed like the bees': true ratio would put a 22 mm azure at a
        # sixth of a 140 mm Cecropia and lose it entirely. Square root keeps
        # the order right and everything visible.
        out["size"] = round(min(1.8, max(0.4, (mm / 55.0) ** 0.5)), 3)
    return out


# Body plan by name (assetlib/fauna_variants.BIRD_VARIANTS). A woodpecker
# propped on a trunk by its stiff tail and a chickadee on a twig are not the
# same bird, and the roster routinely holds both.
_BIRD_BUILD_WORDS = (("woodpecker", "woodpecker"), ("sapsucker", "woodpecker"),
                     ("flicker", "woodpecker"), ("hummingbird", "hummer"))


def _bird_appearance(name: str) -> dict:
    n = (name or "").lower()
    def spec(body, belly, wing, size=1.0, hummer=False):
        build = "passerine"
        for word, plan in _BIRD_BUILD_WORDS:
            if word in n:
                build = plan
                break
        return {"kind": "bird", "body": body, "belly": belly, "wing": wing,
                "size": size, "hummer": hummer, "build": build}
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


def _flight_for(row: dict, bee_m: dict = None, lep_m: dict = None,
                bird_m: dict = None) -> dict:
    """Flight parameters for one creature, in the shape the viewer wants.

    Thin: :mod:`src.flight_model` owns every number and every band; this only
    picks which morphology row to hand it. Never raises — a creature with no
    morphology still flies, just on a wider band, and a scene must not fail to
    render because an allometry could not be evaluated.
    """
    try:
        from src.flight_model import animation_hz, flight_for
    except Exception:      # noqa: BLE001
        return {}
    taxon = (row.get("taxon") or "").strip().lower()
    sci = row.get("scientific_name") or ""
    name = (row.get("common_name") or "").lower()
    try:
        if taxon == "lepidoptera":
            lo = (lep_m or {}).get("wingspan_min_mm") or 0
            hi = (lep_m or {}).get("wingspan_max_mm") or 0
            span = (float(lo) + float(hi)) / 2.0 if (lo or hi) else 0
            kind = ("moth" if ("moth" in name or "sphinx" in name
                               or "clearwing" in name) else "butterfly")
            f = flight_for("lepidoptera", scientific_name=sci,
                           wingspan_mm=span or None, kind=kind,
                           flight_style=(lep_m or {}).get("flight_style") or "")
        elif taxon == "bee":
            f = flight_for("bee", scientific_name=sci,
                           body_length_mm=(bee_m or {}).get("body_length_mm"))
        elif taxon == "bird":
            bm = bird_m or {}
            f = flight_for("bird", scientific_name=sci,
                           mass_g=bm.get("mass_g"),
                           span_mm=bm.get("wingspan_mm"),
                           wing_area_cm2=bm.get("wing_area_cm2"),
                           style=bm.get("flight_style") or "")
        else:
            f = flight_for(taxon, scientific_name=sci)
    except Exception:      # noqa: BLE001
        return {}
    hz = (f.get("hz") or {}).get("mid") or 0
    return {
        # What to animate at — never above Nyquist, so a wing is either drawn
        # truthfully or drawn as the blur a human actually sees.
        "hz": round(animation_hz(hz), 2),
        "true_hz": round(hz, 1),
        "render": f.get("render", "discrete"),
        "style": f.get("style", ""),
        "basis": f.get("basis", ""),
        "burst": int((f.get("burst_beats") or {}).get("mid") or 0),
        "pause_s": round((f.get("pause_s") or {}).get("mid") or 0.0, 2),
        "dip_m": round((f.get("bound_dip_m") or {}).get("mid") or 0.0, 3),
    }


def support_by_taxon(plant_ids: list) -> dict:
    """``{taxon: distinct-species-count}`` of native fauna the given plants
    support — the design's total ecological reach, shown as the 3D roster's
    headline so the Habitat Value Score's wildlife tally is legible where you
    see the animals. Uses the same documented edges as the score (P6). Empty on
    error / no plants."""
    ids = [int(p) for p in (plant_ids or [])]
    if not ids:
        return {}
    try:
        from src.db.fauna import fauna_supported_by_plants
    except Exception:      # noqa: BLE001
        return {}
    out: dict = {}
    for taxon in ("bee", "lepidoptera", "bird", "other_insect", "mammal"):
        try:
            n = len(fauna_supported_by_plants(ids, taxon=taxon))
        except Exception:      # noqa: BLE001
            n = 0
        if n:
            out[taxon] = n
    return out


def appearance_for_fauna(fauna_id: int) -> Optional[dict]:
    """The per-species appearance spec for one fauna id — reused by the
    fly-through so the flown avatar looks like the chosen species (a green sweat
    bee, a leafcutter, a mining bee…). Returns None for taxa without a look."""
    from src.db.fauna import bee_morphology, get_fauna, lep_morphology
    row = get_fauna(fauna_id)
    if not row:
        return None
    # One creature, so fetch only the table it needs.
    if row.get("taxon") == "bee":
        morph = bee_morphology().get(fauna_id)
    elif row.get("taxon") == "lepidoptera":
        morph = lep_morphology().get(fauna_id)
    else:
        morph = None
    return _appearance_for(row, morph)


def _appearance_for(row: dict, morph: dict = None) -> Optional[dict]:
    """`morph` is this species' schema-v58 morphology row, or None. When it is
    None every branch falls back to the pre-v58 name tables, which is what an
    undescribed species — or a pre-v58 database — gets."""
    taxon = row.get("taxon")
    name = row.get("common_name", "")
    sci = row.get("scientific_name", "")
    if taxon == "bee":
        genus = sci.split(" ")[0] if sci else ""
        return _bee_appearance(genus, name, morph)
    if taxon == "lepidoptera":
        kind = "moth" if "moth" in name.lower() or "sphinx" in name.lower() \
            or "clearwing" in name.lower() else "butterfly"
        return _lep_appearance(name, sci, kind, morph)
    if taxon == "bird":
        return _bird_appearance(name)
    if taxon == "other_insect":
        return _insect_appearance(name)
    if taxon == "mammal":
        return _mammal_appearance(name)      # bats included; the diel filter gates them
    return None


# ── Season + day/night activity (V2.12) ───────────────────────────────────────
# When each animal is out. Documented flight seasons gate the bees & leps by
# month; birds/mammals are treated as year-round, insects as a warm-season
# default (a coarse, honest heuristic — not per-species precision, P9). Diel:
# bees + most birds + flower/dragonflies are day; owls, moths, bats are night;
# hawkmoths/hummingbird clearwings ("day_dusk") and small mammals are both.
_WARM_MONTHS = frozenset({4, 5, 6, 7, 8, 9, 10})   # insects / bats default season


def _diel(taxon: str, name: str, lep_activity: Optional[str]) -> str:
    """'day' | 'night' | 'both' — when this creature is active."""
    n = name.lower()
    if taxon == "bee":
        return "day"
    if taxon == "lepidoptera":
        return {"day": "day", "night": "night", "day_dusk": "both"}.get(
            lep_activity or "day", "day")
    if taxon == "bird":
        return "night" if "owl" in n else "day"
    if taxon == "other_insect":
        return "both" if "lacewing" in n else "day"
    if taxon == "mammal":
        return "night"                       # bats + nocturnal small mammals
    return "day"


def _season_months(taxon: str, fid: int,
                   bee_seasons: dict, lep_seasons: dict) -> frozenset:
    """The months (1-12) this creature is out; empty = no seasonal gate."""
    from src.habitat_score import parse_month_range
    if taxon == "bee":
        return frozenset(parse_month_range(bee_seasons.get(fid) or ""))
    if taxon == "lepidoptera":
        _act, season = lep_seasons.get(fid, (None, None))
        return frozenset(parse_month_range(season or ""))
    if taxon in ("other_insect", "mammal"):
        return _WARM_MONTHS
    return frozenset()                        # birds: year-round


def _active_now(taxon: str, name: str, fid: int, month: int, is_night: bool,
                bee_seasons: dict, lep_seasons: dict) -> bool:
    diel = _diel(taxon, name,
                 (lep_seasons.get(fid, (None, None))[0]) if taxon == "lepidoptera" else None)
    if is_night and diel == "day":
        return False
    if (not is_night) and diel == "night":
        return False
    months = _season_months(taxon, fid, bee_seasons, lep_seasons)
    if month and months and month not in months:
        return False
    return True


# ── Placement height above the anchor plant's base (metres) ───────────────────

def _perch_height(kind: str, height_m: float, rel: str) -> float:
    """Where on the plant this kind sits, in metres above the plant's base.

    The plant's rendered top is exactly ``ground + height_m`` (the archetypes are
    normalised to height 1 and scaled by it), so anything returned here that is
    ``>= height_m`` puts the animal in open air ABOVE the plant. That is what the
    old formulas did for small plants — bird ``h * 1.05`` and bee ``h * 0.9 +
    0.15`` both exceed ``h`` under ~1.5 m — and it is why a user saw creatures
    hovering well clear of the flowers they are supposed to be using.

    Everything is now clamped strictly inside the plant.
    """
    h = max(0.1, height_m)
    if kind == "bird":
        # Perched IN the crown: the upper-middle of a tree, and low enough on a
        # herb that the bird is among the stems rather than balanced on the tip.
        return h * (0.72 if h > 1.0 else 0.80)
    if kind == "beetle":
        return h * 0.45
    if kind == "mammal":
        return 0.06                                  # on the ground
    # Flower visitors sit AT the bloom, which is the top of the plant — just
    # inside it, never floating over it.
    if kind in ("bee", "fly"):
        return min(h * 0.95, h - 0.02)
    # butterfly / moth
    return min(h * 0.93, h - 0.02)


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
    # Every plant position in the design — a ranger's home-range patrol samples
    # these so it forages across the whole yard, not just its anchor's bed.
    # The whole plant record, not just its position: a patrol waypoint's HEIGHT
    # has to come from the plant it is over. Keeping only (x, y) here is what
    # made a bird anchored on a 5 m saskatoon rest 3.6 m above a 0.4 m
    # coneflower — it carried its anchor's perch height to every waypoint.
    all_pl = list(plants)
    if fauna_edges is None:
        from src.db.fauna import fauna_for_plants as fauna_edges

    rows = fauna_edges(list(by_id.keys()))
    if not rows:
        return []

    # Season + day/night truth (V2.12): only show a creature when it is actually
    # out. Attribute maps are best-effort — if unavailable, nothing is gated.
    month = int(scene.get("month") or 0)
    is_night = bool(scene.get("is_night"))
    try:
        from src.db.fauna import (bee_flight_seasons, bee_morphology,
                                  lep_activity_seasons, lep_morphology)
        bee_seasons = bee_flight_seasons()
        lep_seasons = lep_activity_seasons()
        # Two queries for the whole roster (schema v58) rather than one per
        # creature — the same shape as the season lookups above.
        bee_morph = bee_morphology()
        lep_morph = lep_morphology()
        # V2.45: mass + wingspan + flight style, the input to flight_model.
        from src.db.fauna import bird_morphology
        bird_morph = bird_morphology()
    except Exception:      # noqa: BLE001
        bee_seasons, lep_seasons = {}, {}
        bee_morph, lep_morph, bird_morph = {}, {}, {}

    # Per species, keep ALL its best-rank (plant, relationship) candidates, so a
    # species that uses several present plants can be spread across them rather
    # than piling every animal onto one keystone shrub (the old clumping bug).
    cand: dict = {}    # fauna_id -> {"best_rank", "row", "plants": [pid,...]}
    for r in rows:
        fid = r.get("id")
        pid = r.get("plant_id")
        if fid is None or pid not in by_id:
            continue
        # Season + day/night: skip creatures that aren't out right now.
        if not _active_now(r.get("taxon"), r.get("common_name", ""), fid,
                           month, is_night, bee_seasons, lep_seasons):
            continue
        prio = _REL_PRIORITY.get(r.get("taxon"), ())
        rank = prio.index(r["relationship"]) if r.get("relationship") in prio else len(prio)
        c = cand.get(fid)
        if c is None or rank < c["best_rank"]:
            cand[fid] = {"best_rank": rank, "row": {**r}, "plants": [pid]}
        elif rank == c["best_rank"] and pid not in c["plants"]:
            c["plants"].append(pid)

    chosen = sorted(cand.values(),
                    key=lambda c: (c["row"].get("taxon", ""),
                                   c["row"].get("common_name", "")))
    # Round-robin how many animals each plant already carries, so shared plants
    # don't stack: a species prefers a candidate plant with the fewest so far.
    load: dict = {}
    per_taxon: dict = {}
    creatures: list[dict] = []
    for c in chosen:
        r = c["row"]
        taxon = r.get("taxon")
        cap = _TAXON_CAP.get(taxon, 3)
        if per_taxon.get(taxon, 0) >= cap:
            continue
        _fid = r.get("id")
        app = _appearance_for(
            r, bee_morph.get(_fid) if taxon == "bee"
            else lep_morph.get(_fid) if taxon == "lepidoptera" else None)
        if app is None:
            continue
        seed = _hash(r.get("id"), r.get("plant_id"))
        # Pick the least-loaded candidate plant (ties broken deterministically).
        pid = min(sorted(c["plants"]),
                  key=lambda q: (load.get(q, 0), (seed + q) % 7))
        load[pid] = load.get(pid, 0) + 1
        p = by_id[pid]
        canopy = max(0.3, float(p.get("canopy_m") or 0.5))
        ang = (seed % 360) * math.pi / 180.0
        # A ring INSIDE the crown, so an animal sits among the foliage it is
        # there to use. `canopy_m` is the full width, so the old `canopy * 0.55`
        # was 1.1x the crown RADIUS — always just outside the leaves — and its
        # flat 0.7 m floor put a bee that far from a 0.3 m aster. The k-th
        # animal on one plant still steps outward so they don't stack.
        k = load[pid] - 1
        rad = max(0.15, canopy * 0.30) + 0.35 * k
        def _ph(pl):
            bh = _perch_height(app["kind"], float(pl.get("height_m") or 0.5),
                               r.get("relationship", ""))
            if app.get("form") == "bat":
                bh = max(2.5, float(pl.get("height_m") or 1.0) + 1.5)
            return bh
        base_h = _ph(p)
        # A route of the plants this species uses (present ones), nearest first —
        # the viewer moves the animal between them so it visits its plants instead
        # of orbiting one (V2.13). Cap at 4 waypoints; a single-plant species just
        # wanders locally.
        others = [q for q in c["plants"] if q != pid and q in by_id]
        others.sort(key=lambda q: (by_id[q]["x"] - p["x"]) ** 2
                    + (by_id[q]["y"] - p["y"]) ** 2)
        route = [[p["x"], p["y"], round(base_h, 2)]]
        for q in others[:3]:
            pq = by_id[q]
            route.append([pq["x"], pq["y"], round(_ph(pq), 2)])
        # Home-range patrol: a ranging flier (bee/fly/butterfly/moth/bird) also
        # visits spread-out plants across the design so it roams the whole yard
        # instead of orbiting its anchor — the fix for wildlife clumping in one
        # bed. Walk the plant list at a seed-dependent stride so different
        # creatures head to different corners rather than all to the same plant.
        if app["kind"] in _RANGING and len(all_pl) > 2:
            stride = 1 + (seed % (len(all_pl) - 1))
            j = seed % len(all_pl)
            added = 0
            for _ in range(len(all_pl)):
                pq = all_pl[j]
                qx, qy = pq["x"], pq["y"]
                j = (j + stride) % len(all_pl)
                if (qx - p["x"]) ** 2 + (qy - p["y"]) ** 2 >= _PATROL_MIN_M ** 2:
                    # _ph of the plant being VISITED — same as the host loop
                    # above. Using base_h (the anchor's) here was the bug.
                    route.append([round(qx, 2), round(qy, 2), round(_ph(pq), 2)])
                    added += 1
                    if added >= _PATROL_WAYPOINTS:
                        break
        creatures.append({
            "kind": app["kind"],
            "x": round(p["x"] + math.cos(ang) * rad, 2),
            "y": round(p["y"] + math.sin(ang) * rad, 2),
            # Small per-animal height jitter separates same-plant, same-band
            # animals — but only DOWNWARD. A symmetric ±10% put a bee 1.03 m up
            # a 1.0 m cinquefoil, undoing the clamp _perch_height just applied;
            # there is room below a perch and never any above it.
            "h": round(base_h * (1.0 - ((seed >> 6) % 20) / 100.0), 2),
            "name": r.get("common_name", ""),
            "on": p.get("common_name", ""),
            # The anchor plant's id as well as its name: the 3D inspector draws
            # food-web threads from a clicked plant to the animals that use it,
            # and matching on a display name would tie two plantings of the same
            # species together (V2.29).
            "on_id": pid,
            "rel": r.get("relationship", ""),
            "seed": seed % 100000,
            "app": app,
            # How this species' wings actually move (V2.45). Real hertz from
            # published allometry, the bout structure they beat in, and whether
            # the beat is renderable at all — see src/flight_model.py. The
            # viewer had hardcoded per-taxon constants before this.
            "flight": _flight_for(r, bee_morph.get(_fid),
                                  lep_morph.get(_fid), bird_morph.get(_fid)),
            "route": route,
            "_ax": p["x"], "_ay": p["y"],
        })
        per_taxon[taxon] = per_taxon.get(taxon, 0) + 1
        if len(creatures) >= max_creatures:
            break

    _relax_spacing(creatures)
    for c in creatures:
        c.pop("_ax", None); c.pop("_ay", None)
    return creatures


def _relax_spacing(creatures: list, min_sep: float = 0.85, tries: int = 12) -> None:
    """Nudge overlapping creatures apart in the ground plane so a rich scene
    reads as individuals, not a blob. Each creature is pushed radially outward
    from its anchor plant until it clears its neighbours (deterministic)."""
    placed: list = []
    for c in creatures:
        ax, ay = c.get("_ax", c["x"]), c.get("_ay", c["y"])
        vx, vy = c["x"] - ax, c["y"] - ay
        r = math.hypot(vx, vy) or 0.01
        ux, uy = vx / r, vy / r
        step = 0
        while step < tries:
            clash = any((c["x"] - q[0]) ** 2 + (c["y"] - q[1]) ** 2 < min_sep ** 2
                        for q in placed)
            if not clash:
                break
            # Spiral out: grow the radius and rotate a little each try.
            step += 1
            r += 0.35
            ang = math.atan2(uy, ux) + step * 0.7
            c["x"] = round(ax + math.cos(ang) * r, 2)
            c["y"] = round(ay + math.sin(ang) * r, 2)
        placed.append((c["x"], c["y"]))

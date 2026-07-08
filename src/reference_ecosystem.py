"""
reference_ecosystem.py — the walkable reference-ecosystem library (F50).

Every design deserves a *target*: the natural community it is reaching toward.
This module holds a small, curated reference community for each Alberta
ecoregion — the characteristic canopy / shrub / forb / grass genera and their
rough layer balance — and turns it into a `scene_contract`-shaped project the
existing 3D viewer can **walk**. "Walk your design, then walk the reference."

The communities are authored as *genera + layer ratios*, not fixed species
lists, and resolved against whatever the live plant database actually holds
(via `fauna.plants_in_genera`), so the reference can never name a plant the app
doesn't know, and it improves for free as the seed data grows.

Design principle P2 (the best designs disappear into their context — show the
"grown, not designed" endpoint to aim at) and P6 (make ecological value legible
— a reference community is the value target made walkable). See
docs/DESIGN_PHILOSOPHY.md.

Qt-free: the core builds the project + scene; a thin viewer window renders it.
Data access is injectable for tests; by default it reads the DB.
"""

from __future__ import annotations

import math
import random
from typing import Callable, Optional

# Per-layer plant-type preference used to keep a genus in its structural role
# (a Cornus can be a groundcover or a shrub; the layer decides which we want).
_LAYER_TYPES = {
    "canopy": {"tree"},
    "shrub": {"shrub"},
    "grass": {"grass", "graminoid", "sedge"},
    "forb": {"wildflower", "forb", "herb", "groundcover", "vine"},
}
# Rough mature height per layer (metres) — only used as a fallback when a
# resolved plant has no recorded height, so the 3D layers still stack sensibly.
_LAYER_FALLBACK_H = {"canopy": 9.0, "shrub": 2.0, "forb": 0.4, "grass": 0.6}


# ── the curated communities (genera per layer + how many to place) ────────────
# Genera are matched case-insensitively against scientific-name first tokens.
REFERENCE_COMMUNITIES: dict[str, dict] = {
    "aspen_parkland": {
        "name": "Aspen Parkland grove",
        "description": ("Clumps of trembling aspen over a saskatoon–rose–"
                        "snowberry shrub ring, with a goldenrod-and-aster forb "
                        "matrix in fescue grassland — the classic parkland mosaic."),
        "layers": {
            "canopy": {"genera": ["Populus", "Betula"], "count": 4},
            "shrub": {"genera": ["Amelanchier", "Cornus", "Rosa",
                                 "Symphoricarpos", "Prunus"], "count": 7},
            "forb": {"genera": ["Solidago", "Symphyotrichum", "Monarda",
                                "Gaillardia", "Geum", "Astragalus"], "count": 12},
            "grass": {"genera": ["Festuca", "Elymus", "Koeleria"], "count": 9},
        },
    },
    "mixedgrass_prairie": {
        "name": "Mixedgrass Prairie",
        "description": ("A near-treeless sea of grama and needlegrass, threaded "
                        "with blanketflower, blazingstar, milkvetch and sage — "
                        "the driest, most open native community."),
        "layers": {
            "canopy": {"genera": [], "count": 0},
            "shrub": {"genera": ["Rosa", "Artemisia", "Symphoricarpos"], "count": 4},
            "forb": {"genera": ["Gaillardia", "Liatris", "Astragalus",
                                "Solidago", "Artemisia"], "count": 12},
            "grass": {"genera": ["Bouteloua", "Nassella", "Koeleria",
                                 "Andropogon", "Elymus"], "count": 16},
        },
    },
    "fescue_foothills": {
        "name": "Foothills Rough Fescue grassland",
        "description": ("Dense rough-fescue bunchgrass with shrubby cinquefoil "
                        "and a rich avens–cinquefoil–aster forb layer, aspen "
                        "groves gathering in the coulees."),
        "layers": {
            "canopy": {"genera": ["Populus"], "count": 2},
            "shrub": {"genera": ["Dasiphora", "Rosa", "Symphoricarpos"], "count": 5},
            "forb": {"genera": ["Geum", "Potentilla", "Solidago",
                                "Symphyotrichum", "Anemone"], "count": 12},
            "grass": {"genera": ["Festuca", "Koeleria", "Elymus"], "count": 12},
        },
    },
    "boreal_mixedwood": {
        "name": "Boreal Mixedwood",
        "description": ("White spruce and aspen over an alder–viburnum–rose "
                        "understory, with a bunchberry–twinflower–lily forb "
                        "carpet — the northern forest."),
        "layers": {
            "canopy": {"genera": ["Picea", "Populus", "Betula", "Pinus"], "count": 6},
            "shrub": {"genera": ["Alnus", "Viburnum", "Rosa", "Cornus"], "count": 6},
            "forb": {"genera": ["Cornus", "Linnaea", "Maianthemum",
                                "Geum"], "count": 10},
            "grass": {"genera": ["Calamagrostis", "Carex"], "count": 6},
        },
    },
    "riparian": {
        "name": "Riparian streamside",
        "description": ("Balsam poplar and willow thickets over red-osier "
                        "dogwood and alder, with a lush moist-ground forb layer — "
                        "the wettest, most productive edge."),
        "layers": {
            "canopy": {"genera": ["Populus", "Betula"], "count": 3},
            "shrub": {"genera": ["Salix", "Cornus", "Alnus", "Viburnum"], "count": 8},
            "forb": {"genera": ["Mertensia", "Symphyotrichum", "Geum",
                                "Solidago"], "count": 9},
            "grass": {"genera": ["Calamagrostis", "Glyceria", "Carex"], "count": 8},
        },
    },
    "wet_meadow": {
        "name": "Wet Meadow / Marsh",
        "description": ("Sedge meadow and manna grass with willow and bog birch "
                        "at the margins, marsh-marigold and blue iris in the wet "
                        "hollows — standing-water habitat."),
        "layers": {
            "canopy": {"genera": [], "count": 0},
            "shrub": {"genera": ["Salix", "Betula"], "count": 5},
            "forb": {"genera": ["Caltha", "Iris", "Mertensia",
                                "Symphyotrichum"], "count": 8},
            "grass": {"genera": ["Carex", "Glyceria", "Calamagrostis"], "count": 16},
        },
    },
    "subalpine_montane": {
        "name": "Subalpine / Montane",
        "description": ("Engelmann spruce, fir and pine over juniper and "
                        "blueberry, with mountain avens and anemone in the "
                        "openings — the high-country community."),
        "layers": {
            "canopy": {"genera": ["Picea", "Abies", "Pinus", "Pseudotsuga",
                                  "Larix"], "count": 6},
            "shrub": {"genera": ["Vaccinium", "Juniperus", "Salix"], "count": 6},
            "forb": {"genera": ["Dryas", "Anemone", "Geum", "Potentilla"], "count": 9},
            "grass": {"genera": ["Festuca", "Poa"], "count": 6},
        },
    },
}

_DEFAULT_KEY = "aspen_parkland"


def community_keys() -> list[str]:
    """Ecoregion keys that have a curated reference community."""
    return list(REFERENCE_COMMUNITIES.keys())


def reference_community(ecoregion: Optional[str]) -> dict:
    """The curated community spec for ``ecoregion`` (falls back to a
    representative parkland community for an unknown/empty key)."""
    return REFERENCE_COMMUNITIES.get(ecoregion or "",
                                     REFERENCE_COMMUNITIES[_DEFAULT_KEY])


def _default_resolver(genera: list[str]) -> list[dict]:
    if not genera:
        return []
    from src.db.fauna import plants_in_genera
    return plants_in_genera(genera)


def _matches_layer(layer: str, row: dict) -> bool:
    want = _LAYER_TYPES.get(layer, set())
    return (row.get("plant_type") or "").lower() in want


def resolve_reference_community(ecoregion: Optional[str], *,
                                resolve_genus: Optional[Callable] = None) -> dict:
    """Resolve the community's genera against the live DB into real species per
    layer. Returns ``{key, name, description, layers: {layer: [names]},
    n_species}`` — the data behind the walkable scene, and a headless summary."""
    if resolve_genus is None:
        resolve_genus = _default_resolver
    spec = reference_community(ecoregion)
    layers: dict[str, list[str]] = {}
    seen: set[int] = set()
    total = 0
    for layer, lspec in spec["layers"].items():
        rows = resolve_genus(lspec.get("genera", []))
        pref = [r for r in rows if _matches_layer(layer, r)] or rows
        names = []
        for r in pref:
            rid = r.get("id")
            if rid in seen:
                continue
            seen.add(rid)
            names.append(r.get("common_name") or r.get("scientific_name") or "plant")
        layers[layer] = names
        total += len(names)
    return {
        "key": ecoregion or _DEFAULT_KEY,
        "name": spec["name"],
        "description": spec["description"],
        "layers": layers,
        "n_species": total,
    }


def _offset_latlng(lat: float, lng: float, dx: float, dy: float) -> tuple:
    """Shift (lat, lng) by (dx east, dy north) metres — the app's cosLat metric."""
    dlat = dy / 111320.0
    dlng = dx / ((111320.0 * math.cos(math.radians(lat))) or 1.0)
    return lat + dlat, lng + dlng


def build_reference_project(ecoregion: Optional[str], *,
                            center_lat: float = 51.05,
                            center_lng: float = -114.07,
                            size_m: float = 20.0,
                            seed: int = 7,
                            resolve_genus: Optional[Callable] = None) -> dict:
    """Build a `scene_contract`-shaped project placing the reference community's
    species in a naturalistic scatter within a ``size_m`` square around
    (``center_lat``, ``center_lng``). Feeds straight into
    ``scene_contract.build_scene``. Unresolved genera are simply skipped."""
    if resolve_genus is None:
        resolve_genus = _default_resolver
    from src.project_store import plant_feature

    spec = reference_community(ecoregion)
    rng = random.Random(seed)
    half = size_m / 2.0
    features: list[dict] = []

    for layer, lspec in spec["layers"].items():
        rows = resolve_genus(lspec.get("genera", []))
        pref = [r for r in rows if _matches_layer(layer, r)] or rows
        if not pref:
            continue
        count = int(lspec.get("count", 0))
        for i in range(count):
            row = pref[i % len(pref)]
            dx = rng.uniform(-half, half)
            dy = rng.uniform(-half, half)
            lat, lng = _offset_latlng(center_lat, center_lng, dx, dy)
            rec = {
                "plant_id": row.get("id"),
                "common_name": row.get("common_name") or "plant",
                "lat": lat, "lng": lng,
            }
            features.append(plant_feature(rec, pattern_kind="reference"))

    return {
        "type": "FeatureCollection",
        "features": features,
        "properties": {
            "name": f"Reference — {spec['name']}",
            "reference_ecoregion": ecoregion or _DEFAULT_KEY,
        },
    }


def build_reference_scene(ecoregion: Optional[str], *,
                          center_lat: float = 51.05,
                          center_lng: float = -114.07,
                          size_m: float = 20.0,
                          resolve_genus: Optional[Callable] = None,
                          get_plant: Optional[Callable] = None) -> dict:
    """Convenience: build the reference project and run it through
    ``scene_contract.build_scene`` at maturity (year 12) so the viewer sees the
    community grown in. Returns the Scene JSON."""
    from src.scene_contract import build_scene
    project = build_reference_project(
        ecoregion, center_lat=center_lat, center_lng=center_lng,
        size_m=size_m, resolve_genus=resolve_genus)
    return build_scene(project, year=12, get_plant=get_plant)

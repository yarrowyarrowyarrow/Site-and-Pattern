"""
reference_ecosystem.py — the walkable reference-ecosystem library (F50).

Every design deserves a *target*: the natural community it is reaching toward.
This module holds a small, curated reference community for each Alberta
ecoregion — the characteristic canopy / shrub / forb / grass genera and their
rough layer balance — and turns it into a `scene_contract`-shaped project the
existing 3D viewer can **walk**. "Walk your design, then walk the reference."

Each layer is authored as its **lead species** (the dominant and
characteristic plants, by catalogue name) and the genera that fill it out,
resolved against whatever the live plant database actually holds, so the
reference can never name a plant the app doesn't know. Where the plants stand
is decided by rules in `src.reference_layout` (trees in clumps, shrubs in
thickets at the grove's edge, wildflowers in drifts, grasses as the matrix,
light deciding who stands under a crown), not by coordinates (V3.39).

Design principle P2 (the best designs disappear into their context — show the
"grown, not designed" endpoint to aim at) and P6 (make ecological value legible
— a reference community is the value target made walkable). See
docs/DESIGN_PHILOSOPHY.md.

Qt-free: the core builds the project + scene; a thin viewer window renders it.
Data access is injectable for tests; by default it reads the DB.
"""

from __future__ import annotations

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


# ── the curated communities ───────────────────────────────────────────────────
# Each layer names its LEAD species first, by catalogue common name, then the
# genera that fill in after them (V3.39). Until V3.39 a layer was genera alone
# and took the first N species in alphabetical order, so the Aspen Parkland
# grove had no aspen (Balsam Poplar, two cottonwoods and Paper Birch sort
# first) and the Boreal Mixedwood no white spruce or aspen. A canopy lead is
# ``(name, stems)``; ``form`` says how the layer is planted (see _layout).
# The leads are the dominant and characteristic species of each community as
# the Natural Regions Committee (2006) describes Alberta's natural subregions,
# drafted from that description and not checked line by line in a session
# (the V3.39 plan's D7). The catalogue has no Engelmann spruce or subalpine
# fir, so the subalpine walk leans montane.
REFERENCE_COMMUNITIES: dict[str, dict] = {
    "aspen_parkland": {
        "name": "Aspen Parkland grove",
        "description": ("Clumps of trembling aspen over a saskatoon–rose–"
                        "snowberry shrub ring, with a goldenrod-and-aster forb "
                        "matrix in fescue grassland — the classic parkland mosaic."),
        "layers": {
            "canopy": {"lead": [("Trembling Aspen", 6), ("Balsam Poplar", 1)],
                       "genera": ["Populus", "Betula"], "count": 7,
                       "form": "clump"},
            "shrub": {"lead": ["Saskatoon Berry", "Prickly Wild Rose",
                               "Western Snowberry", "Chokecherry",
                               "Red Osier Dogwood"],
                      "genera": ["Amelanchier", "Cornus", "Rosa",
                                 "Symphoricarpos", "Prunus"], "count": 12,
                      "form": "edge"},
            "forb": {"lead": ["Lindley's Aster", "Smooth Aster",
                              "Three Flowered Avens (Prairie Smoke, Old Man's Whiskers)",
                              "Northern Bedstraw", "Wild Bergamot",
                              "Prairie Crocus"],
                     "genera": ["Solidago", "Symphyotrichum", "Monarda",
                                "Gaillardia", "Geum", "Astragalus"], "count": 28,
                     "form": "drift"},
            "grass": {"lead": ["Rough Fescue", "Western Porcupine Grass",
                               "June Grass"],
                      "genera": ["Festuca", "Elymus", "Koeleria"], "count": 50,
                      "form": "matrix"},
        },
    },
    "mixedgrass_prairie": {
        "name": "Mixedgrass Prairie",
        "description": ("A near-treeless sea of grama and needlegrass, threaded "
                        "with blanketflower, blazingstar, milkvetch and sage — "
                        "the driest, most open native community."),
        "layers": {
            "canopy": {"genera": [], "count": 0},
            "shrub": {"lead": ["Western Snowberry", "Prickly Wild Rose",
                               "Silverberry"],
                      "genera": ["Rosa", "Artemisia", "Symphoricarpos"],
                      "count": 6, "form": "edge"},
            "forb": {"lead": ["Prairie Sagewort", "Scarlet Globemallow",
                              "Dotted Blazingstar", "Blanketflower",
                              "Prairie Crocus", "Golden Bean"],
                     "genera": ["Gaillardia", "Liatris", "Astragalus",
                                "Solidago", "Artemisia"], "count": 34,
                     "form": "drift"},
            "grass": {"lead": ["Needle and Thread Grass", "Blue Grama Grass",
                               "Western Wheatgrass", "June Grass"],
                      "genera": ["Bouteloua", "Nassella", "Koeleria",
                                 "Andropogon", "Elymus"], "count": 90,
                      "form": "matrix"},
        },
    },
    "fescue_foothills": {
        "name": "Foothills Rough Fescue grassland",
        "description": ("Dense rough-fescue bunchgrass with shrubby cinquefoil "
                        "and a rich avens–cinquefoil–aster forb layer, aspen "
                        "groves gathering in the coulees."),
        "layers": {
            "canopy": {"lead": [("Trembling Aspen", 5)],
                       "genera": ["Populus"], "count": 5, "form": "clump"},
            "shrub": {"lead": ["Shrubby Cinquefoil", "Prickly Wild Rose",
                               "Western Snowberry", "Silverberry"],
                      "genera": ["Dasiphora", "Rosa", "Symphoricarpos"],
                      "count": 9, "form": "edge"},
            "forb": {"lead": ["Three Flowered Avens (Prairie Smoke, Old Man's Whiskers)",
                              "Prairie Crocus", "Northern Bedstraw",
                              "Golden Bean"],
                     "genera": ["Geum", "Potentilla", "Solidago",
                                "Symphyotrichum", "Anemone"], "count": 28,
                     "form": "drift"},
            "grass": {"lead": ["Foothills Rough Fescue", "Bluebunch Fescue",
                               "June Grass"],
                      "genera": ["Festuca", "Koeleria", "Elymus"], "count": 80,
                      "form": "matrix"},
        },
    },
    "boreal_mixedwood": {
        "name": "Boreal Mixedwood",
        "description": ("White spruce and aspen over an alder–viburnum–rose "
                        "understory, with a bunchberry–twinflower–lily forb "
                        "carpet — the northern forest."),
        "layers": {
            "canopy": {"lead": [("White Spruce", 4), ("Trembling Aspen", 5),
                                ("Balsam Poplar", 1), ("Paper Birch", 1)],
                       "genera": ["Picea", "Populus", "Betula", "Pinus"],
                       "count": 11, "form": "clump"},
            "shrub": {"lead": ["Low-bush Cranberry", "Prickly Wild Rose",
                               "Green Alder", "Beaked Hazelnut",
                               "Canada Buffaloberry"],
                      "genera": ["Alnus", "Viburnum", "Rosa", "Cornus"],
                      "count": 12, "form": "edge"},
            "forb": {"lead": ["Bunchberry", "Twinflower",
                              "Wild Lily-of-the-valley", "Wild Sarsaparilla",
                              "Fireweed", "Dewberry"],
                     "genera": ["Cornus", "Linnaea", "Maianthemum", "Geum"],
                     "count": 26, "form": "drift"},
            "grass": {"lead": ["Bluejoint Reed Grass", "Hairy Wild Rye"],
                      "genera": ["Calamagrostis", "Carex"], "count": 14,
                      "form": "matrix"},
        },
    },
    "riparian": {
        "name": "Riparian streamside",
        "description": ("Balsam poplar and willow thickets over red-osier "
                        "dogwood and alder, with a lush moist-ground forb layer — "
                        "the wettest, most productive edge."),
        "layers": {
            "canopy": {"lead": [("Balsam Poplar", 4)],
                       "genera": ["Populus", "Betula"], "count": 4,
                       "form": "clump"},
            "shrub": {"lead": ["Sandbar Willow", "Bebb's Willow",
                               "Red Osier Dogwood", "Thinleaf Alder",
                               "Pussy Willow"],
                      "genera": ["Salix", "Cornus", "Alnus", "Viburnum"],
                      "count": 14, "form": "edge"},
            "forb": {"lead": ["Tall Lungwort (Blue Bells)", "Smooth Aster",
                              "Fireweed"],
                     "genera": ["Mertensia", "Symphyotrichum", "Geum",
                                "Solidago"], "count": 18, "form": "drift"},
            "grass": {"lead": ["Bluejoint Reed Grass", "Water Sedge",
                               "Fowl Manna Grass"],
                      "genera": ["Calamagrostis", "Glyceria", "Carex"],
                      "count": 30, "form": "matrix"},
        },
    },
    "wet_meadow": {
        "name": "Wet Meadow / Marsh",
        "description": ("Sedge meadow and manna grass with willow and bog birch "
                        "at the margins, marsh-marigold and blue iris in the wet "
                        "hollows — standing-water habitat."),
        "layers": {
            "canopy": {"genera": [], "count": 0},
            "shrub": {"lead": ["Dwarf Birch", "Pussy Willow", "Sandbar Willow"],
                      "genera": ["Salix", "Betula"], "count": 7,
                      "form": "edge"},
            "forb": {"lead": ["Marsh Marigold", "Tall Lungwort (Blue Bells)"],
                     "genera": ["Caltha", "Iris", "Mertensia",
                                "Symphyotrichum"], "count": 16, "form": "drift"},
            "grass": {"lead": ["Beaked Sedge", "Water Sedge", "Awned Sedge",
                               "Bluejoint Reed Grass", "Common Tall Manna Grass"],
                      "genera": ["Carex", "Glyceria", "Calamagrostis"],
                      "count": 70, "form": "matrix"},
        },
    },
    "subalpine_montane": {
        "name": "Subalpine / Montane",
        "description": ("Lodgepole pine, spruce and Douglas fir over buffaloberry "
                        "and juniper, with mountain avens and arnica in the "
                        "openings — the high country, montane-leaning (the "
                        "catalogue has no Engelmann spruce or subalpine fir)."),
        "layers": {
            "canopy": {"lead": [("Lodgepole Pine", 4), ("White Spruce", 3),
                                ("Douglas Fir", 2)],
                       "genera": ["Picea", "Abies", "Pinus", "Pseudotsuga",
                                  "Larix"], "count": 9, "form": "clump"},
            "shrub": {"lead": ["Canada Buffaloberry", "Common Juniper",
                               "Velvet-leaf Blueberry", "Shrubby Cinquefoil"],
                      "genera": ["Vaccinium", "Juniperus", "Salix"], "count": 10,
                      "form": "edge"},
            "forb": {"lead": ["Bearberry", "Yellow Mountain Avens",
                              "Heart-leaved Arnica"],
                     "genera": ["Dryas", "Anemone", "Geum", "Potentilla"],
                     "count": 22, "form": "drift"},
            "grass": {"genera": ["Festuca", "Poa"], "count": 24,
                      "form": "matrix"},
        },
    },
}

#: The version of the communities above, recorded in every walk built from
#: them. A walk saved from an older version is rebuilt around the person's own
#: plants (src.reference_edit.open_sandbox), or it would keep its old trees
#: for good: a saved walk is never built again. Bump it with any change to the
#: lists, the counts or the layout.
COMMUNITY_VERSION = 2

#: The side of the square a walk is planted in, in metres. 20 until V3.39;
#: the grove needs the room.
SIZE_M = 26.0

#: The province whose plants fill a walk out after its leads: the communities
#: are Alberta's natural subregions.
PROVINCE = "AB"

_DEFAULT_KEY = "aspen_parkland"


def community_keys() -> list[str]:
    """Ecoregion keys that have a curated reference community."""
    return list(REFERENCE_COMMUNITIES.keys())


def reference_community(ecoregion: Optional[str]) -> dict:
    """The curated community spec for ``ecoregion`` (falls back to a
    representative parkland community for an unknown/empty key)."""
    return REFERENCE_COMMUNITIES.get(ecoregion or "",
                                     REFERENCE_COMMUNITIES[_DEFAULT_KEY])


def lead_entries(lspec: dict) -> list[tuple]:
    """A layer's leads as ``(name, stems)``; stems is 0 outside the canopy."""
    out = []
    for lead in (lspec or {}).get("lead") or []:
        if isinstance(lead, (tuple, list)):
            out.append((str(lead[0]), int(lead[1])))
        else:
            out.append((str(lead), 0))
    return out


def lead_names(ecoregion: Optional[str]) -> list[str]:
    """Every lead species of a community by catalogue name, trees first."""
    spec = reference_community(ecoregion)
    return [name for lspec in spec["layers"].values()
            for name, _stems in lead_entries(lspec)]


def _default_resolver(genera: list[str]) -> list[dict]:
    if not genera:
        return []
    from src.db.fauna import plants_in_genera
    return plants_in_genera(genera)


def _default_name_resolver(names: list[str]) -> list[dict]:
    """Catalogue rows for exact common names."""
    if not names:
        return []
    from src.db.plants import get_connection
    conn = get_connection()
    try:
        qmarks = ",".join("?" * len(names))
        rows = conn.execute(
            f"SELECT * FROM plants WHERE common_name IN ({qmarks})",
            list(names)).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def _resolvers(resolve_genus, resolve_names) -> tuple:
    """The two lookups. A caller that injects only the genus lookup (the
    older tests) gets no leads rather than a database read it did not ask
    for."""
    if resolve_names is None:
        resolve_names = (_default_name_resolver if resolve_genus is None
                         else (lambda _names: []))
    return resolve_genus or _default_resolver, resolve_names


def _matches_layer(layer: str, row: dict) -> bool:
    want = _LAYER_TYPES.get(layer, set())
    return (row.get("plant_type") or "").lower() in want


def _resolved_layers(spec: dict, resolve_genus, resolve_names) -> dict:
    """Per layer, ``{"leads": [(row, stems)], "others": [rows]}``: the leads
    that are in the catalogue in their authored order, then the layer's genera
    in name order, each species in one layer only (its first)."""
    wanted = [name for lspec in spec["layers"].values()
              for name, _s in lead_entries(lspec)]
    by_name = {r.get("common_name"): r for r in (resolve_names(wanted) or [])}
    seen: set = set()
    out: dict = {}
    for layer, lspec in spec["layers"].items():
        leads = []
        for name, stems in lead_entries(lspec):
            row = by_name.get(name)
            if row is not None and row.get("id") not in seen:
                seen.add(row.get("id"))
                leads.append((row, stems))
        rows = resolve_genus(lspec.get("genera", [])) or []
        pref = [r for r in rows if _matches_layer(layer, r)] or rows
        others = []
        for row in pref:
            if row.get("id") not in seen:
                seen.add(row.get("id"))
                others.append(row)
        out[layer] = {"leads": leads, "others": others}
    return out


def _name(row: dict) -> str:
    return row.get("common_name") or row.get("scientific_name") or "plant"


def resolve_reference_community(ecoregion: Optional[str], *,
                                resolve_genus: Optional[Callable] = None,
                                resolve_names: Optional[Callable] = None
                                ) -> dict:
    """Resolve the community against the live DB into real species per layer.
    Returns ``{key, name, description, layers: {layer: [names]}, leads:
    {layer: [names]}, n_species}``: the data behind the walkable scene, and a
    headless summary.

    ``layers`` is the genera's species, what the fidelity band and the habitat
    score's layer component are scored against (F13, F129). ``leads`` (V3.39)
    is kept apart on purpose: listed in ``layers``, the leads would raise the
    presence bar in eight of the communities' layers (measured), and a design's
    habitat score would move because the Learn side's walks changed."""
    resolve_genus, resolve_names = _resolvers(resolve_genus, resolve_names)
    spec = reference_community(ecoregion)
    genera = _resolved_layers(spec, resolve_genus, lambda _names: [])
    led = _resolved_layers(spec, lambda _genera: [], resolve_names)
    layers = {layer: [_name(r) for r in got["others"]]
              for layer, got in genera.items()}
    return {
        "key": ecoregion or _DEFAULT_KEY,
        "name": spec["name"],
        "description": spec["description"],
        "layers": layers,
        "leads": {layer: [_name(r) for r, _s in got["leads"]]
                  for layer, got in led.items()},
        "n_species": sum(len(names) for names in layers.values()),
    }


_WATER_LEVEL = {"low": 1, "medium": 2, "high": 3}


def _water_range(row: dict) -> Optional[tuple]:
    """The driest and wettest ground a plant takes, as 1 to 3, or None."""
    levels = [_WATER_LEVEL[w.strip()] for w in
              str(row.get("water_needs") or "").split(",")
              if w.strip() in _WATER_LEVEL]
    return (min(levels), max(levels)) if levels else None


def _typical_water(rows: list) -> Optional[tuple]:
    """The community's ground, from its leads: the middle of their driest
    and the middle of their wettest."""
    ranges = sorted(r for r in (_water_range(row) for row in rows) if r)
    if not ranges:
        return None
    lows = sorted(lo for lo, _hi in ranges)
    highs = sorted(hi for _lo, hi in ranges)
    return lows[len(lows) // 2], highs[len(highs) // 2]


def _fits_place(row: dict, typical: Optional[tuple]) -> bool:
    """Whether a species of the genera may fill a walk out: native to the
    province, and taking the community's typical ground: no drier-only plant
    in a wetland, no wet-ground plant in dry grassland (the marsh aster in
    the fescue). A row that does not say passes; nothing is left out for want
    of a field (P9)."""
    provinces = row.get("native_provinces")
    if provinces and PROVINCE not in str(provinces).split(","):
        return False
    water = _water_range(row)
    if typical is None or water is None:
        return True
    return water[0] <= typical[0] and water[1] >= typical[1]


def _fill(key: str, layer: str, others: list,
          typical: Optional[tuple]) -> list:
    """The genera's other species that fill a layer out, in a shuffled order
    that is the same every time for this community and layer."""
    rows = [r for r in others if _fits_place(r, typical)]
    random.Random(f"{key}:{layer}").shuffle(rows)
    return rows


def layer_plan(ecoregion: Optional[str], *,
               resolve_genus: Optional[Callable] = None,
               resolve_names: Optional[Callable] = None) -> list[dict]:
    """What :func:`src.reference_layout.lay_out` plants, layer by layer:
    ``{"layer", "form", "count", "leads": [(row, stems)], "fill": [rows]}``."""
    resolve_genus, resolve_names = _resolvers(resolve_genus, resolve_names)
    key = ecoregion if ecoregion in REFERENCE_COMMUNITIES else _DEFAULT_KEY
    spec = REFERENCE_COMMUNITIES[key]
    resolved = _resolved_layers(spec, resolve_genus, resolve_names)
    typical = _typical_water([row for got in resolved.values()
                              for row, _s in got["leads"]])
    plan = []
    for layer, lspec in spec["layers"].items():
        got = resolved[layer]
        plan.append({
            "layer": layer,
            "form": lspec.get("form") or "",
            "count": int(lspec.get("count", 0)),
            "leads": got["leads"],
            "fill": _fill(key, layer, got["others"], typical),
        })
    return plan


def plantable_ids(ecoregion: Optional[str], *,
                  plants: Optional[list] = None,
                  resolve_genus: Optional[Callable] = None,
                  resolve_names: Optional[Callable] = None) -> set:
    """The plants a walk lets you plant (V3.41): any plant of its four layers
    native to the province and taking the community's typical ground, the
    rule its own fill passes (:func:`_fits_place`). The planting list starts
    with the community's own species; *Plant one* on an animal's card can add
    any of these, because the plants an animal relies on that are not in the
    walk are, almost by definition, not among its own."""
    plan = layer_plan(ecoregion, resolve_genus=resolve_genus,
                      resolve_names=resolve_names)
    typical = _typical_water([row for spec in plan
                              for row, _s in spec["leads"]])
    if plants is None:
        from src.db.plants import get_all_plants
        plants = get_all_plants()
    kinds = set().union(*_LAYER_TYPES.values())
    return {r["id"] for r in plants
            if r.get("id") is not None
            and (r.get("plant_type") or "").lower() in kinds
            and _fits_place(r, typical)}


def _latlng(center_lat: float, center_lng: float, dx: float, dy: float):
    """(lat, lng) ``dx`` metres east and ``dy`` north of the centre, by the
    app's own metric (src.projection), as the sandbox converts clicks."""
    from src.projection import metres_per_deg
    m_lat, m_lng = metres_per_deg(center_lat)
    return center_lat + dy / (m_lat or 1.0), center_lng + dx / (m_lng or 1.0)


def build_reference_project(ecoregion: Optional[str], *,
                            center_lat: float = 51.05,
                            center_lng: float = -114.07,
                            size_m: float = SIZE_M,
                            seed: int = 7,
                            resolve_genus: Optional[Callable] = None,
                            resolve_names: Optional[Callable] = None) -> dict:
    """Build a `scene_contract`-shaped project planting the reference
    community within a ``size_m`` square around (``center_lat``,
    ``center_lng``), by the rules in :mod:`src.reference_layout`. Feeds
    straight into ``scene_contract.build_scene``. A species the catalogue does
    not hold is skipped, and the layer's others take its place."""
    from src.project_store import plant_feature
    from src.reference_layout import lay_out

    spec = reference_community(ecoregion)
    plan = layer_plan(ecoregion, resolve_genus=resolve_genus,
                      resolve_names=resolve_names)
    features: list[dict] = []
    for row, dx, dy in lay_out(plan, size_m=size_m, seed=seed):
        lat, lng = _latlng(center_lat, center_lng, dx, dy)
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
            "reference_version": COMMUNITY_VERSION,
            "reference_center": [center_lat, center_lng],
        },
    }


def build_reference_scene(ecoregion: Optional[str], *,
                          center_lat: float = 51.05,
                          center_lng: float = -114.07,
                          size_m: float = SIZE_M,
                          resolve_genus: Optional[Callable] = None,
                          resolve_names: Optional[Callable] = None,
                          get_plant: Optional[Callable] = None) -> dict:
    """Convenience: build the reference project and run it through
    ``scene_contract.build_scene`` at maturity (year 12) so the viewer sees the
    community grown in. Returns the Scene JSON."""
    from src.scene_contract import build_scene
    project = build_reference_project(
        ecoregion, center_lat=center_lat, center_lng=center_lng,
        size_m=size_m, resolve_genus=resolve_genus,
        resolve_names=resolve_names)
    return build_scene(project, year=12, get_plant=get_plant)

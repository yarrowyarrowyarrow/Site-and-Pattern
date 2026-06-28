"""
sprite_gallery.py — specimen scenes for the 3D sprite gallery (V1.93–94).

`gallery_scenes()` returns an ordered ``{key: {name, desc, example, scene}}`` map,
one specimen per plant-body archetype (now genus-specific: spruce vs pine vs fir,
white-barked aspen/birch, red-stemmed dogwood…) and one per flower form, each
built through the *real* :func:`src.scene_contract.build_scene` so it matches the
contract the viewer reads. Consumed by:

  * ``src/sprite_gallery_window.py`` — the in-app gallery (drives the real viewer
    via ``Map3DWidget.apply_scene``), and
  * ``scripts/make_gallery_scene.py`` — writes ``html/sprite_gallery_scenes.json``
    for the standalone ``html/sprite_gallery.html``.

Qt-free. ``year=0`` is the mature-design reference (full size, full presence, no
colony scatter); ``when = July noon`` → ``month 7`` so summer flowers are open.
Each single-specimen scene is framed tightly to the plant (build_scene floors
bounds to ±25 m, which would leave a small flower a speck) and given a unique
origin so the viewer reframes the camera on every menu switch.
"""

from __future__ import annotations

import datetime
import json
import math
from pathlib import Path

from src.scene_contract import build_scene
from src.project_store import plant_feature

_ROOT = Path(__file__).resolve().parent.parent
WHEN = datetime.datetime(2024, 7, 15, 12, 0)        # July noon → month 7
LAT0, LNG0 = 51.05, -114.07
_M_PER_DEG_LAT = 111320.0
_DULL = {"#f2f2ea", "#ffffff", "#ece6c8", "#eeeee0"}
_PREFERRED = {"cattail": "Typha"}                   # iconic exemplar per form


def _offset(lat, lng, dx_m, dy_m):
    return (lat + dy_m / _M_PER_DEG_LAT,
            lng + dx_m / (_M_PER_DEG_LAT * math.cos(math.radians(lat))))


def _boundary(lat, lng, half_m):
    s_lat, w_lng = _offset(lat, lng, -half_m, -half_m)
    n_lat, e_lng = _offset(lat, lng, half_m, half_m)
    ring = [[w_lng, s_lat], [e_lng, s_lat], [e_lng, n_lat],
            [w_lng, n_lat], [w_lng, s_lat]]
    return {"type": "Feature",
            "geometry": {"type": "Polygon", "coordinates": [ring]},
            "properties": {"element_type": "property_boundary",
                           "boundary_id": "gallery"}}


def _fc(features):
    return {"type": "FeatureCollection", "properties": {"site_config": {}},
            "features": list(features)}


def _tree(sci, h, c, *, evergreen=False, name=""):
    """A synthetic woody specimen — genus (from scientific_name) drives the
    viewer's species geometry; flowers suppressed so the body reads cleanly."""
    return {"plant_type": "tree", "scientific_name": sci,
            "deciduous_evergreen": "evergreen" if evergreen else "deciduous",
            "mature_height_meters": h, "mature_canopy_m": c,
            "growth_curve": "steady", "spread_habit": "clumping",
            "years_to_maturity": 3, "flower_color": "", "flower_form": "none",
            "bloom_period": "", "common_name": name}


def _shrub(sci, h, c, name=""):
    return {"plant_type": "shrub", "scientific_name": sci,
            "deciduous_evergreen": "deciduous",
            "mature_height_meters": h, "mature_canopy_m": c,
            "growth_curve": "steady", "spread_habit": "clumping",
            "years_to_maturity": 3, "flower_color": "", "flower_form": "none",
            "bloom_period": "", "common_name": name}


def _plain(ptype, sci, h, c, name=""):
    return {"plant_type": ptype, "scientific_name": sci,
            "deciduous_evergreen": "herbaceous",
            "mature_height_meters": h, "mature_canopy_m": c,
            "growth_curve": "steady", "spread_habit": "clumping",
            "years_to_maturity": 3, "flower_color": "", "flower_form": "none",
            "bloom_period": "", "common_name": name}


# Geometry specimens — genus chosen so the viewer's species profiles are exercised
# (spruce/pine/fir distinct, aspen/birch pale bark, oak broad, dogwood red stems).
GEOMETRY = [
    ("conifer_spruce", "Spruce", "Dense narrow bluish spire, branches upturned (Picea).",
     "White Spruce",      _tree("Picea glauca", 18, 6, evergreen=True, name="White Spruce")),
    ("conifer_pine",   "Pine", "Open, scraggly; clear trunk + tufted upper crown, yellow-green (Pinus).",
     "Jack Pine",         _tree("Pinus banksiana", 16, 6, evergreen=True, name="Jack Pine")),
    ("conifer_fir",    "Fir", "Narrow dark conic with a sharp thin summit, very dense (Abies).",
     "Balsam Fir",        _tree("Abies balsamea", 16, 5.5, evergreen=True, name="Balsam Fir")),
    ("conifer_larch",  "Larch / Tamarack", "Soft sparse cone; a deciduous conifer (golden, then bare) (Larix).",
     "Tamarack",          _tree("Larix laricina", 16, 5, name="Tamarack")),
    ("tree_aspen",     "Aspen / Poplar", "Slender, pale bark, open round crown (Populus).",
     "Trembling Aspen",   _tree("Populus tremuloides", 18, 6, name="Trembling Aspen")),
    ("tree_birch",     "Birch", "White bark, finer pendulous twigs (Betula).",
     "Paper Birch",       _tree("Betula papyrifera", 16, 8, name="Paper Birch")),
    ("tree_oak",       "Oak", "Broad gnarled spreading crown, dark, deep bark (Quercus).",
     "Bur Oak",           _tree("Quercus macrocarpa", 14, 14, name="Bur Oak")),
    ("tree_willow",    "Willow (tree)", "Pale grey bark, weeping fringe (Salix).",
     "Bebb's Willow",     _tree("Salix bebbiana", 7, 5, name="Bebb's Willow")),
    ("tree_cherry",    "Cherry", "Balanced oval crown (Prunus).",
     "Pin Cherry",        _tree("Prunus pensylvanica", 7, 4, name="Pin Cherry")),
    ("shrub_dogwood",  "Dogwood (red-osier)", "Bushy dome with bare RED stems (Cornus).",
     "Red-osier Dogwood", _shrub("Cornus sericea", 2, 2, name="Red-osier Dogwood")),
    ("shrub_willow",   "Willow (shrub)", "Pale upright multi-stem clump (Salix).",
     "Pussy Willow",      _shrub("Salix discolor", 3, 2.5, name="Pussy Willow")),
    ("shrub_saskatoon", "Saskatoon", "Upright fine-twigged shrub (Amelanchier).",
     "Saskatoon Berry",   _shrub("Amelanchier alnifolia", 3, 2, name="Saskatoon Berry")),
    ("shrub_rose",     "Shrub (generic)", "The bushy dome unknown genera fall back to.",
     "Wild Rose",         _shrub("Rosa acicularis", 1, 1, name="Wild Rose")),
    ("perennial",      "Perennial / herb clump", "Stems + leaf rosettes over a mound (wildflower/herb/fern).",
     "Canada Anemone",    _plain("wildflower", "Anemone canadensis", 0.5, 0.5, "Canada Anemone")),
    ("fern",           "Fern", "Shares the perennial-clump geometry.",
     "Ostrich Fern",      _plain("fern", "Matteuccia struthiopteris", 1.2, 0.9, "Ostrich Fern")),
    ("grass",          "Grass / sedge / rush tuft", "Dense fan of flat arching blades.",
     "Big Bluestem",      _plain("grass", "Andropogon gerardii", 1.6, 0.5, "Big Bluestem")),
    ("aquatic",        "Aquatic / emergent clump", "Tall erect strap leaves; cattails add the brown spike.",
     "Great Bulrush",     _plain("aquatic", "Schoenoplectus acutus", 1.8, 0.6, "Great Bulrush")),
    ("groundcover",    "Groundcover mat", "Low scatter of textured domes.",
     "Bearberry",         _plain("groundcover", "Arctostaphylos uva-ursi", 0.15, 0.7, "Bearberry")),
    ("vine",           "Vine", "A slim swaying cone.",
     "Blue Clematis",     _plain("vine", "Clematis occidentalis", 2.0, 1.2, "Blue Clematis")),
]

FORMS = ["daisy", "rays", "spike", "plume", "umbel", "globe",
         "cluster", "bell", "trumpet", "cattail", "pea", "whorl"]


def _seed_rows():
    rows = json.loads((_ROOT / "data" / "plants_master.json").read_text())
    rows += json.loads((_ROOT / "data" / "garden_plants.json").read_text())
    return rows


def _pick_flower(form, rows):
    cands = [p for p in rows if (p.get("flower_form") == form)
             and p.get("flower_color") and p.get("bloom_period")]
    if not cands:
        return None
    pref = _PREFERRED.get(form, "")
    cands.sort(key=lambda p: (
        not (pref and (p.get("scientific_name") or "").startswith(pref)),
        (p.get("flower_color", "").lower() in _DULL),
        float(p.get("mature_height_m") or 0) > 1.0))
    return cands[0]


def _flower_specimen(p):
    def f(v, d):
        try:
            return float(v)
        except (TypeError, ValueError):
            return d
    return {
        "plant_type": p.get("plant_type") or "wildflower",
        "scientific_name": p.get("scientific_name") or "",
        "deciduous_evergreen": p.get("deciduous_evergreen") or "herbaceous",
        "mature_height_meters": max(0.4, f(p.get("mature_height_m"), 0.5)),
        "mature_canopy_m": max(0.4, f(p.get("mature_canopy_m"), 0.45)),
        "growth_curve": "steady", "spread_habit": "clumping",
        "years_to_maturity": 3,
        "flower_color": p.get("flower_color") or "",
        "flower_form": p.get("flower_form") or "none",
        "bloom_period": p.get("bloom_period") or "",
        "common_name": p.get("common_name") or "",
    }


def _scene_for(plant, pid, name, i):
    feat = plant_feature({"plant_id": pid, "common_name": name,
                          "lat": LAT0, "lng": LNG0})
    proj = _fc([_boundary(LAT0, LNG0, 8.0), feat])
    sc = build_scene(proj, year=0, when=WHEN, get_plant=lambda _id: plant)
    p0 = sc["plants"][0] if sc["plants"] else {}
    h = float(p0.get("height_m") or 1.0)
    c = float(p0.get("canopy_m") or 0.5)
    half = round(max(1.0 * h, 1.2 * c, 0.7), 2)
    sc["bounds"] = {"min_x": -half, "max_x": half, "min_y": -half, "max_y": half}
    sc["origin"] = {"lat": LAT0 + i * 0.001, "lng": LNG0}   # unique → reframe on switch
    sc["boundary"] = []
    return sc


def _specimens():
    rows = _seed_rows()
    out = []
    for key, name, desc, example, plant in GEOMETRY:
        out.append((key, name, desc, example, plant))
    for form in FORMS:
        p = _pick_flower(form, rows)
        if not p:
            continue
        out.append((f"flower_{form}", f"Flower — {form}",
                    f"The '{form}' flower sprite, in its real colour, atop the plant's body.",
                    p.get("common_name", ""), _flower_specimen(p)))
    return out


def gallery_scenes() -> dict:
    """Ordered ``{key: {name, desc, example, scene}}`` — geometry specimens, then
    flower-form specimens, then an "all" grid. Built with the real build_scene."""
    specs = _specimens()
    out: dict = {}
    for i, (key, name, desc, example, plant) in enumerate(specs, start=1):
        out[key] = {"name": name, "desc": desc, "example": example,
                    "scene": _scene_for(plant, i, example or name, i)}

    # "All" — every specimen on a grid (natural bounds; trees dominate, small
    # plants are accents — use the menu to frame each individually).
    cols = 6
    spacing = 6.0
    feats = [_boundary(*_offset(LAT0, LNG0, (cols - 1) * spacing / 2,
                                -((len(specs) // cols) * spacing) / 2),
                       max(40.0, cols * spacing))]
    plant_by_id = {}
    for i, (key, name, desc, example, plant) in enumerate(specs):
        r, c = divmod(i, cols)
        lat, lng = _offset(LAT0, LNG0, c * spacing, -r * spacing)
        feats.append(plant_feature({"plant_id": 1000 + i,
                                    "common_name": example or name,
                                    "lat": lat, "lng": lng}))
        plant_by_id[1000 + i] = plant
    all_scene = build_scene(_fc(feats), year=0, when=WHEN,
                            get_plant=lambda pid: plant_by_id.get(pid, {}))
    out["all"] = {"name": "All sprites (grid)",
                  "desc": "One of every archetype + flower form, on a grid.",
                  "example": "", "scene": all_scene}
    return out

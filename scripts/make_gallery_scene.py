#!/usr/bin/env python3
"""
make_gallery_scene.py — generate the 3D sprite-gallery scenes.

Writes ``html/sprite_gallery_scenes.json``, consumed by
``html/sprite_gallery.html``. Each entry is a Scene-JSON dict built by the
*real* ``src.scene_contract.build_scene`` (so every field matches the contract
the viewer reads), plus a name / description / example-plant caption.

Two kinds of entries:
  * geometry archetypes — one specimen per plant-body builder, with tree
    aspect ratios chosen to exercise the slender / oval / spreading crown forms
    and the conifer-vs-deciduous split. Flowers are suppressed so the body
    geometry reads cleanly.
  * flower forms — one specimen per ``flower_form`` in the shipped data, using a
    real species (and its real flower colour + bloom window) auto-picked from
    ``data/plants_master.json`` so the sprite shows exactly as it does in the app.

``year = 0`` is the "mature-design reference": growth_scale_factor → 1.0 (full
size), presence_factor → 1.0 (fully visible), spread → none (no colony scatter).
``when = July noon`` → ``scene.month = 7`` so summer-blooming flowers are open.

Run:  python scripts/make_gallery_scene.py
"""

from __future__ import annotations

import datetime
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
import sys
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.scene_contract import build_scene          # noqa: E402
from src.project_store import plant_feature         # noqa: E402

OUT = ROOT / "html" / "sprite_gallery_scenes.json"
WHEN = datetime.datetime(2024, 7, 15, 12, 0)        # July noon → month 7, flowers open

LAT0, LNG0 = 51.05, -114.07                          # Calgary-ish anchor
_M_PER_DEG_LAT = 111320.0


def _offset(lat, lng, dx_m, dy_m):
    """Shift a lat/lng by (dx, dy) metres (east, north)."""
    dlat = dy_m / _M_PER_DEG_LAT
    dlng = dx_m / (_M_PER_DEG_LAT * math.cos(math.radians(lat)))
    return lat + dlat, lng + dlng


def _boundary(lat, lng, half_m):
    """A square property_boundary feature centred on (lat, lng)."""
    s_lat, w_lng = _offset(lat, lng, -half_m, -half_m)
    n_lat, e_lng = _offset(lat, lng, half_m, half_m)
    ring = [[w_lng, s_lat], [e_lng, s_lat], [e_lng, n_lat],
            [w_lng, n_lat], [w_lng, s_lat]]
    return {"type": "Feature",
            "geometry": {"type": "Polygon", "coordinates": [ring]},
            "properties": {"element_type": "property_boundary",
                           "boundary_id": "gallery"}}


def _fc(features):
    return {"type": "FeatureCollection",
            "properties": {"site_config": {}},
            "features": list(features)}


# ── Curated geometry specimens — control tree aspect (height/canopy) so the
#    viewer's formOf() picks the intended crown form. flower_form 'none' keeps
#    the body geometry uncluttered by sprites. ───────────────────────────────
def _g(ptype, sci, h, c, *, evergreen=False, name="", form_desc=""):
    return {"plant_type": ptype,
            "scientific_name": sci,
            "deciduous_evergreen": "evergreen" if evergreen else "deciduous",
            "mature_height_meters": h, "mature_canopy_m": c,
            "growth_curve": "steady", "spread_habit": "clumping",
            "years_to_maturity": 3,
            "flower_color": "", "flower_form": "none", "bloom_period": "",
            "common_name": name}


GEOMETRY = [
    ("conifer_spire",   "Conifer tree — spire",     "Stacked drooping cones (evergreen). Slender spire crown.",
     "White Spruce",     _g("tree", "Picea glauca",      20, 6.5, evergreen=True, name="White Spruce")),
    ("conifer_broad",   "Conifer tree — broad",     "Stacked cones, broad open form (h≈canopy).",
     "Balsam Fir",       _g("tree", "Abies balsamea",    13, 12,  evergreen=True, name="Balsam Fir")),
    ("tree_slender",    "Deciduous tree — slender", "Da Vinci branch crown, narrow upright (aspen/poplar/birch).",
     "Trembling Aspen",  _g("tree", "Populus tremuloides", 20, 6,  name="Trembling Aspen")),
    ("tree_oval",       "Deciduous tree — oval",    "Da Vinci branch crown, balanced upright.",
     "Paper Birch",      _g("tree", "Betula papyrifera", 18, 11, name="Paper Birch")),
    ("tree_spreading",  "Deciduous tree — spreading", "Da Vinci branch crown, broad and rounded (oak/maple).",
     "Bur Oak",          _g("tree", "Quercus macrocarpa", 15, 15, name="Bur Oak")),
    ("shrub",           "Shrub",                    "Bushy cluster of merged domes.",
     "Beaked Hazelnut",  _g("shrub", "Corylus cornuta",  3, 2.5, name="Beaked Hazelnut")),
    ("perennial",       "Perennial / herb clump",   "Thin stems with leaf rosettes over a basal mound. Fallback for wildflower / herb.",
     "Canada Anemone",   _g("wildflower", "Anemone canadensis", 0.5, 0.5, name="Canada Anemone")),
    ("fern",            "Fern",                     "Shares the perennial-clump geometry (herb bucket).",
     "Ostrich Fern",     _g("fern", "Matteuccia struthiopteris", 1.2, 0.9, name="Ostrich Fern")),
    ("grass",           "Grass / sedge / rush tuft", "Dense fan of flat arching blades (V1.92). Sedge & rush share it.",
     "Big Bluestem",     _g("grass", "Andropogon gerardii", 1.6, 0.5, name="Big Bluestem")),
    ("aquatic",         "Aquatic / emergent clump", "Tall erect strap leaves (V1.92). Cattails add the brown spike.",
     "Great Bulrush",    _g("aquatic", "Schoenoplectus acutus", 1.8, 0.6, name="Great Bulrush")),
    ("groundcover",     "Groundcover mat",          "Low scatter of textured domes — a plant carpet.",
     "Bearberry",        _g("groundcover", "Arctostaphylos uva-ursi", 0.15, 0.7, name="Bearberry")),
    ("vine",            "Vine",                     "A slim swaying cone.",
     "Blue Clematis",    _g("vine", "Clematis occidentalis", 2.0, 1.2, name="Blue Clematis")),
]

FORMS = ["daisy", "rays", "spike", "plume", "umbel", "globe",
         "cluster", "bell", "trumpet", "cattail"]
_DULL = {"#f2f2ea", "#ffffff", "#ece6c8", "#eeeee0"}   # de-prioritise near-white


def _seed_rows():
    rows = json.loads((ROOT / "data" / "plants_master.json").read_text())
    rows += json.loads((ROOT / "data" / "garden_plants.json").read_text())
    return rows


# A few forms have an iconic exemplar worth pinning (genus prefix on scientific
# name) so the gallery shows the species users expect.
_PREFERRED = {"cattail": "Typha"}


def _pick_flower(form, rows):
    """Best real example for a flower_form: has colour + bloom, an iconic genus
    preferred, then vivid colour, then shorter plants (the flower reads above a
    small clump)."""
    cands = [p for p in rows
             if (p.get("flower_form") == form)
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
    """Synthetic plant dict for a flower specimen — real flower fields, with a
    gentle height/canopy floor so the bloom sits on a visible clump."""
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
    """A single-specimen scene, the plant centred at the anchor and the camera
    framed tightly to it (build_scene floors bounds to ±25 m, which would leave a
    small flower a speck). A unique origin per specimen makes the viewer re-frame
    the camera on every menu switch; the boundary outline is dropped for a clean
    stage."""
    feat = plant_feature({"plant_id": pid, "common_name": name,
                          "lat": LAT0, "lng": LNG0})
    proj = _fc([_boundary(LAT0, LNG0, 8.0), feat])
    sc = build_scene(proj, year=0, when=WHEN, get_plant=lambda _id: plant)
    p0 = sc["plants"][0] if sc["plants"] else {}
    h = float(p0.get("height_m") or 1.0)
    c = float(p0.get("canopy_m") or 0.5)
    half = round(max(1.0 * h, 1.2 * c, 0.7), 2)
    sc["bounds"] = {"min_x": -half, "max_x": half, "min_y": -half, "max_y": half}
    sc["origin"] = {"lat": LAT0 + i * 0.001, "lng": LNG0}   # unique → re-frame on switch
    sc["boundary"] = []                                      # no outline square
    return sc


def main():
    rows = _seed_rows()

    specimens = []   # (key, name, desc, example, plant)
    for key, name, desc, example, plant in GEOMETRY:
        specimens.append((key, name, desc, example, plant))
    for form in FORMS:
        p = _pick_flower(form, rows)
        if not p:
            print(f"  ! no seed example for flower form {form!r}")
            continue
        specimens.append((f"flower_{form}",
                          f"Flower — {form}",
                          f"The '{form}' flower sprite, in its real colour, atop the plant's body.",
                          p.get("common_name", ""),
                          _flower_specimen(p)))

    out = {}

    # Per-specimen scenes (one plant centred) for the menu.
    for i, (key, name, desc, example, plant) in enumerate(specimens, start=1):
        scene = _scene_for(plant, i, example or name, i)
        out[key] = {"name": name, "desc": desc, "example": example,
                    "scene": scene}

    # "All" — every specimen laid out on a grid.
    cols = 6
    spacing = 6.0
    feats = [_boundary(*_offset(LAT0, LNG0, (cols - 1) * spacing / 2,
                                -((len(specimens) // cols) * spacing) / 2),
                       max(40.0, cols * spacing))]
    plant_by_id = {}
    for i, (key, name, desc, example, plant) in enumerate(specimens):
        r, c = divmod(i, cols)
        lat, lng = _offset(LAT0, LNG0, c * spacing, -r * spacing)
        feats.append(plant_feature({"plant_id": 1000 + i,
                                    "common_name": example or name,
                                    "lat": lat, "lng": lng}))
        plant_by_id[1000 + i] = plant
    all_scene = build_scene(_fc(feats), year=0, when=WHEN,
                            get_plant=lambda pid: plant_by_id.get(pid, {}))
    out["all"] = {"name": "All sprites (grid)",
                  "desc": "One of every archetype + flower form, laid out on a grid.",
                  "example": "", "scene": all_scene}

    OUT.write_text(json.dumps(out, separators=(",", ":")))
    n_geo = len(GEOMETRY)
    n_flw = len(specimens) - n_geo
    print(f"Wrote {OUT.relative_to(ROOT)}: {len(out)} entries "
          f"({n_geo} geometry + {n_flw} flower forms + 1 grid).")
    print("Keys:", ", ".join(sorted(out)))


if __name__ == "__main__":
    main()

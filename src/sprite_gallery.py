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
import re
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
    viewer's species geometry."""
    return {"plant_type": "tree", "scientific_name": sci,
            "deciduous_evergreen": "evergreen" if evergreen else "deciduous",
            "mature_height_meters": h, "mature_canopy_m": c,
            "growth_curve": "steady", "spread_habit": "clumping",
            "years_to_maturity": 3, "flower_color": "", "flower_form": "none",
            "bloom_period": "", "common_name": name}


def _shrub(sci, h, c, name="", fruit="", fruit_period=""):
    return {"plant_type": "shrub", "scientific_name": sci,
            "deciduous_evergreen": "deciduous",
            "mature_height_meters": h, "mature_canopy_m": c,
            "growth_curve": "steady", "spread_habit": "clumping",
            "years_to_maturity": 3, "flower_color": "", "flower_form": "none",
            "bloom_period": "", "fruit_color": fruit, "fruit_period": fruit_period,
            "common_name": name}


def _plain(ptype, sci, h, c, name=""):
    return {"plant_type": ptype, "scientific_name": sci,
            "deciduous_evergreen": "herbaceous",
            "mature_height_meters": h, "mature_canopy_m": c,
            "growth_curve": "steady", "spread_habit": "clumping",
            "years_to_maturity": 3, "flower_color": "", "flower_form": "none",
            "bloom_period": "", "common_name": name}


# Fields the archetype specimens borrow from their real species so the body is
# shown WEARING its flower and fruit. They were suppressed originally, on the
# reasoning that a bare body reads more cleanly as a geometry reference — but
# what a user sees is a menu entry called "Fireweed" with no fireweed flowers on
# it, which reads as a bug, not as a decision. A sprite in this app is a body
# plus a bloom, and hiding half of it hides half of what there is to judge.
_BLOOM_FIELDS = ("flower_color", "flower_form", "inflorescence_form",
                 "bloom_period",
                 "fruit_color", "fruit_form", "fruit_period")


def _with_bloom(plant, by_sci):
    """Restore the species' real flower/fruit onto a hand-written specimen."""
    row = by_sci.get((plant.get("scientific_name") or "").lower())
    if not row:
        return plant
    merged = dict(plant)
    for field in _BLOOM_FIELDS:
        value = row.get(field)
        if value in (None, "", "none"):
            continue
        if not merged.get(field) or merged.get(field) == "none":
            merged[field] = value
    return merged


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
    ("shrub_dogwood",  "Dogwood (spreading)", "Broad low spreading clump with bare RED stems (Cornus).",
     "Red-osier Dogwood", _shrub("Cornus sericea", 2, 2.4, name="Red-osier Dogwood")),
    ("shrub_willow",   "Willow (vase)", "Pale upright multi-stem vase (Salix).",
     "Pussy Willow",      _shrub("Salix discolor", 3, 2.2, name="Pussy Willow")),
    ("shrub_saskatoon", "Saskatoon (vase)", "Upright multi-stem vase, fine twigs; purple berries in July (Amelanchier).",
     "Saskatoon Berry",   _shrub("Amelanchier alnifolia", 3, 2, name="Saskatoon Berry",
                                  fruit="#46295e", fruit_period="July–August")),
    ("shrub_rose",     "Rose (mound)", "Low dense rounded thicket to the ground (Rosa).",
     "Wild Rose",         _shrub("Rosa acicularis", 1, 1.1, name="Wild Rose")),
    ("shrub_currant",  "Currant (thicket)", "Many fine arching canes; red berries in summer (Ribes).",
     "Wild Red Currant", _shrub("Ribes triste", 1.4, 1.2, name="Wild Red Currant",
                                fruit="#9a1f1f", fruit_period="July–August")),
    ("shrub_sage",     "Sagebrush (irregular)", "Sparse asymmetric silvery woody form (Artemisia).",
     "Prairie Sagewort", _shrub("Artemisia frigida", 0.5, 0.6, name="Prairie Sagewort")),
    ("herb_fireweed",  "Fireweed (erect)", "Tall erect leafy stem, lance leaves spiralling up (Chamaenerion).",
     "Fireweed",          _plain("wildflower", "Chamaenerion angustifolium", 1.4, 0.4, "Fireweed")),
    ("herb_yarrow",    "Yarrow (ferny)", "Low mound of fine feathery foliage under flat flower stalks (Achillea).",
     "Boreal Yarrow",            _plain("wildflower", "Achillea borealis", 0.5, 0.45, "Boreal Yarrow")),
    ("herb_fleabane",  "Fleabane (rosette)", "Basal leaf rosette under a few wiry flower stalks (Erigeron).",
     "Philadelphia Fleabane", _plain("wildflower", "Erigeron philadelphicus", 0.5, 0.4, "Philadelphia Fleabane")),
    ("herb_aster",     "Aster (clump)", "Bushy upright leafy clump (Symphyotrichum).",
     "Smooth Aster",      _plain("wildflower", "Symphyotrichum laeve", 0.8, 0.6, "Smooth Aster")),
    ("herb_onion",     "Onion (grassy)", "Upright strap/linear basal leaves (Allium).",
     "Nodding Onion",     _plain("wildflower", "Allium cernuum", 0.4, 0.3, "Nodding Onion")),
    ("herb_pussytoes", "Pussytoes (mat)", "Low cushion of spoon-shaped basal leaves (Antennaria).",
     "Rosy Pussytoes",    _plain("wildflower", "Antennaria rosea", 0.2, 0.4, "Rosy Pussytoes")),
    # A second specimen for five herb forms, chosen so the form is HELD CONSTANT
    # and only the leaf character changes. That is what the V2.29 variant work
    # actually does — 46 baked archetypes across the 211 wildflowers, keyed by
    # (blade class x grain class) with the arrangement stamped in — and with one
    # example per form the gallery could not show any of it. Pair each of these
    # with the entry above it: same silhouette, different leaf.
    ("herb_lupine",    "Lupine (erect · palmate compound)",
     "Same erect form as fireweed, but whorls of leaflets fanning from one point (Lupinus).",
     "Silky Lupine",      _plain("wildflower", "Lupinus sericeus", 0.6, 0.4, "Silky Lupine")),
    ("herb_bergamot",  "Bergamot (clump · OPPOSITE leaves)",
     "Same clump form and lance leaf as the aster — but paired at each node, not spiralled (Monarda).",
     "Wild Bergamot",     _plain("wildflower", "Monarda fistulosa", 0.8, 0.5, "Wild Bergamot")),
    ("herb_crocus",    "Prairie Crocus (rosette · deeply cut)",
     "A rosette of finely dissected leaves, and one of the smallest plants here (Pulsatilla).",
     "Prairie Crocus",    _plain("wildflower", "Pulsatilla nuttalliana", 0.2, 0.25, "Prairie Crocus")),
    ("herb_bedstraw",  "Bedstraw (mat · WHORLED leaves)",
     "Same low mat as pussytoes, with narrow leaves in rings of three (Galium).",
     "Northern Bedstraw", _plain("wildflower", "Galium boreale", 0.5, 0.5, "Northern Bedstraw")),
    ("herb_columbine", "Columbine (ferny · pinnate compound)",
     "Same ferny mound as yarrow, built from leaflets rather than dissected blades (Aquilegia).",
     "Blue Columbine",    _plain("wildflower", "Aquilegia brevistyla", 0.5, 0.35, "Blue Columbine")),
    ("fern",           "Fern", "Arching divided fronds from a crown.",
     "Ostrich Fern",      _plain("fern", "Matteuccia struthiopteris", 1.2, 0.9, "Ostrich Fern")),
    ("grass",          "Grass / sedge / rush tuft", "Dense fan of flat arching blades.",
     "Big Bluestem",      _plain("grass", "Andropogon gerardii", 1.6, 0.5, "Big Bluestem")),
    ("aquatic",        "Aquatic / emergent clump", "Tall erect strap leaves; cattails add the brown spike.",
     "Great Bulrush",     _plain("aquatic", "Schoenoplectus acutus", 1.8, 0.6, "Great Bulrush")),
    ("groundcover",    "Groundcover mat", "Low scatter of textured domes.",
     "Bearberry",         _plain("groundcover", "Arctostaphylos uva-ursi", 0.15, 0.7, "Bearberry")),
    ("vine",           "Vine", "Sprawling/twining leafy stems (clematis, vetch, peavine).",
     "Blue Clematis",     _plain("vine", "Clematis occidentalis", 2.0, 1.2, "Blue Clematis")),
]

FORMS = ["daisy", "rays", "spike", "plume", "umbel", "globe",
         "cluster", "bell", "trumpet", "cattail", "pea", "whorl"]


def _seed_rows():
    # encoding="utf-8" is required: the seed JSON has en-dashes / accented names,
    # and read_text() defaults to the locale codec (cp1252 on Windows → crash).
    rows = json.loads((_ROOT / "data" / "plants_master.json").read_text(encoding="utf-8"))
    rows += json.loads((_ROOT / "data" / "garden_plants.json").read_text(encoding="utf-8"))
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
    # Frame the box on the SPECIMEN, so every sprite fills the same ~43% of the
    # view whether it is a 20 m aspen or a 20 cm pussytoes (the viewer's
    # frameCamera derives its distance from these bounds). The floor used to be
    # 0.7 m, which only ever bit plants shorter and narrower than that — i.e. most
    # wildflowers — and pulled the camera back to frame a 1.4 m box around a 20 cm
    # plant: pussytoes filled 12% of the frame and yarrow 31% while everything
    # else filled 43%. The gallery exists to show the sprite, so it was worst at
    # exactly the species this page is most needed for. The remaining floor only
    # guards against a degenerate box for a 5 cm plant.
    half = round(max(1.0 * h, 1.2 * c, 0.30), 2)
    sc["bounds"] = {"min_x": -half, "max_x": half, "min_y": -half, "max_y": half}
    sc["origin"] = {"lat": LAT0 + i * 0.001, "lng": LNG0}   # unique → reframe on switch
    sc["boundary"] = []
    return sc


# Fields the specimens borrow from the real seed row for their scientific name.
# Since V2.29 a plant's leaf characters SELECT its geometry (blade class × grain
# class pick one of the baked archetype variants), so a gallery specimen without
# them would show the neutral fallback and quietly stop being a catalogue of what
# the app renders. The synthetic dicts stay hand-written for the dimensions the
# gallery frames on; only the recorded morphology is borrowed.
_MORPH_FIELDS = ("leaf_shape", "leaf_size_cm", "leaf_arrangement",
                 "bark_texture", "leaf_surface",
                 "growth_form", "bark_color", "fall_color")


def _with_morphology(plant, by_sci):
    row = by_sci.get((plant.get("scientific_name") or "").lower())
    if not row:
        return plant
    merged = dict(plant)
    for field in _MORPH_FIELDS:
        if row.get(field) not in (None, "") and not merged.get(field):
            merged[field] = row[field]
    return merged


def _specimens():
    rows = _seed_rows()
    # A species can appear in BOTH seed files — Monarda fistulosa is "Wild
    # Bergamot" in plants_master and "Bee Balm" in garden_plants — and only one of
    # the two rows carries the morphology. Last-one-wins silently handed the
    # gallery the empty row, so a specimen lost its leaves for no visible reason.
    # Prefer whichever row actually describes its leaves.
    by_sci = {}
    for r in rows:
        key = (r.get("scientific_name") or "").lower()
        if not key:
            continue
        if key not in by_sci or (r.get("leaf_shape")
                                 and not by_sci[key].get("leaf_shape")):
            by_sci[key] = r
    out = []
    for key, name, desc, example, plant in GEOMETRY:
        out.append((key, name, desc, example,
                    _with_bloom(_with_morphology(plant, by_sci), by_sci)))
    for form in FORMS:
        p = _pick_flower(form, rows)
        if not p:
            continue
        out.append((f"flower_{form}", f"Flower — {form}",
                    f"The '{form}' flower sprite, in its real colour, atop the plant's body.",
                    p.get("common_name", ""),
                    _with_morphology(_flower_specimen(p), by_sci)))
    return out


# Display order and headings for the sidebar. Every entry carries its `group`, so
# a consumer inserts a heading whenever the group changes and never has to sniff
# key prefixes — which stopped scaling the moment "every species" was 435 entries.
GROUP_GEOMETRY = "Plant-body geometry"
GROUP_FLOWER = "Flower sprites"
GROUP_COMBO = "Body × flower combos"
# One heading per plant_type inside the species list, in the order the layers
# stack: canopy down to ground.
SPECIES_GROUP_ORDER = ["tree", "shrub", "wildflower", "herb", "fern", "grass",
                       "sedge", "rush", "vine", "groundcover", "aquatic"]


def _species_group(ptype: str) -> str:
    return "Species · " + (ptype or "other").replace("_", " ")


def _species_specimen(row: dict) -> dict:
    """A seed row as a renderable specimen.

    Keeps the whole row (build_scene reads everything with ``.get``, so the real
    flower form, bloom window, morphology, bark and autumn colour all come along)
    and adds the two fields the 3D state layer names differently. Canopy is
    derived the way ``db.plants`` derives it — 1.5x the planting spacing — so a
    species with no measured spread is as wide here as it is in a real design.

    Deliberately reads the shipped JSON, not the database: this module is Qt-free
    and DB-free so ``scripts/make_gallery_scene.py`` can build the standalone page
    offline and deterministically. The one visible cost is berries, whose
    ``fruit_color`` is curated in the DB rather than the seed files, so only the
    hand-authored specimens above fruit.
    """
    spacing = row.get("spacing_m")
    canopy = float(spacing) * 1.5 if spacing else None
    return dict(row,
                mature_height_meters=row.get("mature_height_m"),
                mature_canopy_m=canopy)


def _combo_specs():
    """One specimen per (growth form × flower form) pair the catalogue actually
    uses — 75 of them across 435 species.

    A sprite in this app is a **combination**: a plant body from one small set
    of growth forms, wearing a flower head from another small set. Neither list
    on its own tells you what the app looks like, and the full species list is
    435 entries of mostly-repeats. This is the real vocabulary, deduplicated:
    if two combos look the same here, every species built from them looks the
    same in a design, which is exactly the kind of thing that is invisible until
    you put them side by side.

    The exemplar for each pair is the species with the least dull flower colour
    (a white-on-green sprite shows nothing), tie-broken by name for stability.
    """
    rows = _seed_rows()
    seen, uniq = set(), []
    for r in rows:
        sci = (r.get("scientific_name") or "").strip().lower()
        if sci and sci not in seen and r.get("common_name"):
            seen.add(sci)
            uniq.append(r)
    by_pair: dict = {}
    for r in uniq:
        gf = (r.get("growth_form") or r.get("plant_type") or "other").strip()
        ff = (r.get("flower_form") or "none").strip()
        by_pair.setdefault((gf, ff), []).append(r)
    out = []
    for (gf, ff) in sorted(by_pair, key=lambda k: (k[0], k[1])):
        cands = sorted(by_pair[(gf, ff)], key=lambda p: (
            (p.get("flower_color", "") or "").lower() in _DULL,
            not (p.get("flower_color") or ""),
            (p.get("common_name") or "").lower()))
        p = cands[0]
        n = len(by_pair[(gf, ff)])
        out.append((
            f"combo_{gf}_{ff}",
            f"{gf} × {ff}",
            f"{n} species share this body-and-bloom combination"
            + (f" — e.g. {p.get('common_name')}" if n > 1 else ""),
            p.get("scientific_name") or "",
            _species_specimen(p)))
    return out


def _species_specs():
    """``(key, name, desc, example, plant)`` for every seeded species, grouped by
    plant_type and alphabetical within each group."""
    seen, rows = set(), []
    for row in _seed_rows():
        sci = (row.get("scientific_name") or "").strip()
        name = (row.get("common_name") or "").strip()
        if not sci or not name or sci.lower() in seen:
            continue
        seen.add(sci.lower())
        rows.append(row)
    order = {t: i for i, t in enumerate(SPECIES_GROUP_ORDER)}
    rows.sort(key=lambda r: (order.get(r.get("plant_type"), 99),
                             (r.get("common_name") or "").lower()))
    out = []
    for row in rows:
        slug = re.sub(r"[^a-z0-9]+", "_",
                      (row.get("scientific_name") or "").lower()).strip("_")
        bits = [row.get("plant_type") or "plant"]
        if row.get("mature_height_m"):
            bits.append(f"{row['mature_height_m']} m")
        if row.get("leaf_shape"):
            bits.append(str(row["leaf_shape"]).replace("_", " "))
        if row.get("leaf_arrangement"):
            bits.append(str(row["leaf_arrangement"]))
        if row.get("bloom_period"):
            bits.append(f"blooms {row['bloom_period']}")
        out.append((f"species_{slug}", row["common_name"], " · ".join(bits),
                    row.get("scientific_name") or "",
                    _species_specimen(row)))
    return out


def gallery_scenes(include_species: bool = True) -> dict:
    """Ordered ``{key: {name, desc, example, group, scene}}`` — geometry
    specimens, flower-form specimens, an "all" grid, then EVERY seeded species.

    Built with the real build_scene, so a species entry renders exactly the sprite
    a design containing that plant would. ``include_species=False`` returns only
    the archetype specimens (a fast path for callers that just want those).
    """
    specs = _specimens()
    out: dict = {}
    for i, (key, name, desc, example, plant) in enumerate(specs, start=1):
        out[key] = {"name": name, "desc": desc, "example": example,
                    "group": (GROUP_FLOWER if key.startswith("flower_")
                              else GROUP_GEOMETRY),
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
                  "example": "", "group": GROUP_GEOMETRY, "scene": all_scene}

    # The real sprite vocabulary: every body × bloom pair the catalogue uses,
    # once each, so repeats across 435 species collapse to the ~75 things that
    # are actually distinguishable.
    cbase = len(out) + 1
    for j, (key, name, desc, example, plant) in enumerate(_combo_specs()):
        out[key] = {"name": name, "desc": desc, "example": example,
                    "group": GROUP_COMBO,
                    "scene": _scene_for(plant, cbase + j, name, cbase + j)}

    if include_species:
        # Every seeded species, so a user can look up the plant they are about to
        # place rather than inferring it from an archetype. The archetype
        # specimens above stay: they are the labelled reference for what the
        # builder can draw, and they are what the docs point at.
        base = len(out) + 1
        for j, (key, name, desc, example, plant) in enumerate(_species_specs()):
            out[key] = {"name": name, "desc": desc, "example": example,
                        "group": _species_group(plant.get("plant_type")),
                        "scene": _scene_for(plant, base + j, name, base + j)}
    return out

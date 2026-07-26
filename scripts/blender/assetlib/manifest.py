"""ASSET_TABLE — the single source of truth for what exists — and the
manifest writer. The JSON shape is exactly what html/scene3d/09-models.js
consumes; tests/test_model_assets.py cross-checks the written manifest
against the files and against the viewer's own archetype vocabularies.
"""

import json

from . import conventions as C
from .fauna_variants import BEE_VARIANTS, BIRD_VARIANTS, LEP_VARIANTS
from .flora_herbs import HERB_FORMS, LAYER_KINDS, VARIANT_LAYERS
from .flora_shrubs import SHRUB_FORMS
from .flora_trees import TREE_ARCHETYPES
from .structures import STRUCTURE_SPECS

MANIFEST_NAME = "manifest.json"

# Which (blade class, grain class) archetype variants the herb and shrub families
# need. Read from the shipped catalogue rather than generated as a full cross
# product: of the 84 possible herb combinations only 49 occur, and of the 60
# shrub ones only 29 — so building the product would nearly double the asset
# payload with archetypes no plant in the app can ever select.
_CATALOGUE = None


def _catalogue():
    """data/plants_master.json, or [] if unavailable (the generator still
    builds a sensible default set without it)."""
    global _CATALOGUE
    if _CATALOGUE is None:
        import json
        import os
        # assetlib → blender → scripts → repo root.
        root = os.path.abspath(__file__)
        for _ in range(4):
            root = os.path.dirname(root)
        path = os.path.join(root, "data", "plants_master.json")
        try:
            with open(path, encoding="utf-8") as fh:
                _CATALOGUE = json.load(fh)
        except (OSError, ValueError):
            _CATALOGUE = []
    return _CATALOGUE


def _variants_for(kind_forms, family):
    """{form: [variant_key, ...]} for every combination the catalogue uses.

    Which plant_types a family covers and how a record maps to a form both live
    in conventions.FAMILY_FORMS, so the viewer, the generator and the guard tests
    all read one definition.
    """
    plant_types, form_of, _prefix = C.FAMILY_FORMS[family]
    out = {form: set() for form in kind_forms}
    for rec in _catalogue():
        if rec.get("plant_type") not in plant_types:
            continue
        form = form_of(rec)
        if form not in out:
            continue
        blade = C.blade_class(rec.get("leaf_shape"))
        grain = C.grain_class(rec.get("leaf_size_cm"),
                              rec.get("mature_height_m"), family)
        # Herbs carry a third axis (V2.34): a species' own height ÷ canopy. Only
        # the triples the catalogue USES are baked, which is what keeps a third
        # axis from tripling the payload — 52 units to 96 rather than to 156.
        if family == "herb" and form in C.ASPECT_HERB_FORMS:
            out[form].add(C.herb_variant_key(
                blade, grain,
                C.herb_aspect_class(form, rec.get("mature_height_m"),
                                    _canopy_m(rec))))
        else:
            out[form].add(C.variant_key(blade, grain))
    # Always include the neutral variant so there is a guaranteed fallback.
    for form in out:
        out[form].add(C.herb_variant_key("broad", 1, 1)
                      if (family == "herb" and form in C.ASPECT_HERB_FORMS)
                      else C.variant_key("broad", 1))
    return {form: sorted(keys) for form, keys in out.items()}


def _canopy_m(rec):
    """Mature canopy, defaulting to 1.5 x spacing exactly as db.plants does."""
    for key, mul in (("mature_canopy_m", 1.0), ("spacing_m", 1.5)):
        try:
            v = float(rec.get(key) or 0)
        except (TypeError, ValueError):
            v = 0.0
        if v > 0:
            return v * mul
    return 0.0


def herb_variants():
    return _variants_for(HERB_FORMS, "herb")


def shrub_variants():
    return _variants_for(SHRUB_FORMS, "shrub")


def groundcover_variants():
    """Variant keys for the groundcover mat — one form, many leaf outlines."""
    return _variants_for(["groundcover"], "groundcover")["groundcover"]

# Fauna: manifest key → (nodes documented for the loader, materials used).
FAUNA_TABLE = {
    # bee / lep / bird ship several BUILDS in one file (V2.33, F67), the
    # multi-variant layout the fly established: the declared node names are the
    # variant ROOTS, and each root's parts are prefixed with it
    # ('round_WingL'), because Blender object names are unique per file.
    "bee":    {"file": "fauna_bee.glb",
               "nodes": list(BEE_VARIANTS),
               "materials": [C.MAT_FUZZ, C.MAT_DARK, C.MAT_WING]},
    "lep":    {"file": "fauna_lep.glb",
               "nodes": list(LEP_VARIANTS),
               "materials": [C.MAT_FORE, C.MAT_HIND, C.MAT_EDGE, C.MAT_DARK]},
    "bird":   {"file": "fauna_bird.glb",
               "nodes": list(BIRD_VARIANTS),
               "materials": [C.MAT_BODY, C.MAT_BELLY, C.MAT_WING, C.MAT_DARK]},
    "fly":    {"file": "fauna_fly.glb",
               "nodes": ["hover", "darner"],
               "materials": [C.MAT_BODY, C.MAT_DARK, C.MAT_WING]},
    "beetle": {"file": "fauna_beetle.glb",
               "nodes": ["Body", "Head", "Spots"],
               "materials": [C.MAT_BODY, C.MAT_DARK]},
    "bat":    {"file": "fauna_bat.glb",
               "nodes": ["Body", "Head", "EarL", "EarR", "WingL", "WingR"],
               "materials": [C.MAT_FUR, C.MAT_MEMBRANE]},
    "mammal": {"file": "fauna_mammal.glb",
               "nodes": ["Body", "Head", "Tail", "EarL", "EarR"],
               "materials": [C.MAT_FUR, C.MAT_DARK]},
}


def asset_table():
    """key → spec for every asset the batch build produces."""
    table = {}
    for arch in TREE_ARCHETYPES:
        table[f"tree.{arch}"] = {
            "kind": "tree", "file": f"tree_{arch}.glb", "tiers": [0, 1, 2],
            "parts": [C.PART_BARK, C.PART_FOLIAGE]}
    shrub_vars = shrub_variants()
    for form in SHRUB_FORMS:
        table[f"shrub.{form}"] = {
            "kind": "shrub", "file": f"shrub_{form}.glb",
            "variant_keys": shrub_vars[form],
            "parts": [C.PART_BARK, C.PART_FOLIAGE]}
    herb_vars = herb_variants()
    for form in HERB_FORMS:
        table[f"herb.{form}"] = {
            "kind": "herb", "file": f"herb_{form}.glb",
            "variant_keys": herb_vars[form], "parts": [C.PART_FOLIAGE]}
    for kind, variants in LAYER_KINDS.items():
        spec = {"kind": "layer", "file": f"layer_{kind}.glb",
                "parts": [C.PART_FOLIAGE]}
        if kind in C.ASPECT_LAYERS:
            # One unit per ASPECT class (F65) — the species' own height ÷ canopy
            # picks it, instead of the three units being random draws of one
            # shape chosen by a plant-id hash.
            spec["variant_keys"] = {C.aspect_variant_key(i): i
                                    for i in range(len(C.LAYER_ASPECT_CLASSES[kind]))}
        elif kind in VARIANT_LAYERS:
            # Morphology-keyed like herbs and shrubs: this layer bakes one unit
            # per (blade class × grain class) its species actually use.
            spec["variant_keys"] = groundcover_variants()
        else:
            spec["variants"] = variants
        table[f"layer.{kind}"] = spec
    for key, spec in FAUNA_TABLE.items():
        table[f"fauna.{key}"] = dict(spec, kind="fauna")
    for sid, (size_m, height_m, scale_mode) in STRUCTURE_SPECS.items():
        table[f"structure.{sid}"] = {
            "kind": "structure", "file": f"struct_{sid}.glb",
            "size_m": size_m, "height_m": height_m, "scale_mode": scale_mode}
    return table


def manifest_dict(generator="", half_widths=None):
    """The manifest as a dict. ``half_widths`` is ``{key: {unit: half_width}}``
    measured by ``mesh_ops.unit_frame`` during the build — each flora unit's
    authored horizontal half-extent at height 1. The viewer re-measures the same
    number off the loaded geometry (it is the geometry's own property); the
    manifest carries it so ``tests/test_model_assets.py`` can check the shipped
    files really were authored at their species' aspect."""
    half_widths = half_widths or {}
    plants, fauna, structures = {}, {}, {}
    for key, spec in asset_table().items():
        if spec["kind"] == "fauna":
            fauna[key.split(".", 1)[1]] = {
                "file": spec["file"], "nodes": spec["nodes"],
                "materials": spec["materials"],
                "nominal_size": C.FAUNA_NOMINAL_SIZE}
        elif spec["kind"] == "structure":
            structures[key.split(".", 1)[1]] = {
                "file": spec["file"], "size_m": spec["size_m"],
                "height_m": spec["height_m"], "scale_mode": spec["scale_mode"]}
        else:
            entry = {"file": spec["file"], "parts": spec["parts"]}
            if "tiers" in spec:
                entry["tiers"] = spec["tiers"]
            if "variants" in spec:
                entry["variants"] = spec["variants"]
            if "variant_keys" in spec:
                # {"broad_1": 0, "narrow_2": 1, …} — the viewer looks a plant's
                # (blade class, grain class) up here to pick its archetype.
                entry["variant_keys"] = {k: i for i, k
                                         in enumerate(spec["variant_keys"])}
            if key in half_widths:
                entry["half_width"] = half_widths[key]
            plants[key] = entry
    return {
        "version": 1,
        "generator": generator,
        "unit_frame": ("base y=0, height 1, scaled UNIFORMLY so the authored "
                       "aspect survives; each unit's half_width is published "
                       "below and re-measured on load"),
        "plants": plants,
        "fauna": fauna,
        "structures": structures,
    }


def write_manifest(out_dir, generator="", half_widths=None):
    """Write manifest.json and verify every referenced file exists."""
    import os
    mf = manifest_dict(generator, half_widths)
    missing = []
    for section in ("plants", "fauna", "structures"):
        for key, entry in mf[section].items():
            if not os.path.isfile(os.path.join(str(out_dir), entry["file"])):
                missing.append(f"{section}.{key} -> {entry['file']}")
    if missing:
        raise FileNotFoundError(
            "manifest references missing GLBs:\n  " + "\n  ".join(missing))
    path = os.path.join(str(out_dir), MANIFEST_NAME)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(mf, fh, indent=1, sort_keys=True)
        fh.write("\n")
    return path

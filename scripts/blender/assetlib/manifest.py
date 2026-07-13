"""ASSET_TABLE — the single source of truth for what exists — and the
manifest writer. The JSON shape is exactly what html/scene3d/09-models.js
consumes; tests/test_model_assets.py cross-checks the written manifest
against the files and against the viewer's own archetype vocabularies.
"""

import json

from . import conventions as C
from .flora_herbs import HERB_FORMS, LAYER_KINDS
from .flora_shrubs import SHRUB_FORMS
from .flora_trees import TREE_ARCHETYPES
from .structures import STRUCTURE_SPECS

MANIFEST_NAME = "manifest.json"

# Fauna: manifest key → (nodes documented for the loader, materials used).
FAUNA_TABLE = {
    "bee":    {"file": "fauna_bee.glb",
               "nodes": ["Body", "Head", "Abdomen", "WingL", "WingR",
                         "Band0", "Band1", "Band2"],
               "materials": [C.MAT_FUZZ, C.MAT_DARK, C.MAT_WING]},
    "lep":    {"file": "fauna_lep.glb",
               "nodes": ["Body", "Head", "Abdomen", "WingL", "WingR"],
               "materials": [C.MAT_FORE, C.MAT_HIND, C.MAT_EDGE, C.MAT_DARK]},
    "bird":   {"file": "fauna_bird.glb",
               "nodes": ["Body", "Head", "Beak", "Tail", "WingL", "WingR"],
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
    for form in SHRUB_FORMS:
        table[f"shrub.{form}"] = {
            "kind": "shrub", "file": f"shrub_{form}.glb",
            "parts": [C.PART_BARK, C.PART_FOLIAGE]}
    for form in HERB_FORMS:
        table[f"herb.{form}"] = {
            "kind": "herb", "file": f"herb_{form}.glb",
            "parts": [C.PART_FOLIAGE]}
    for kind, variants in LAYER_KINDS.items():
        table[f"layer.{kind}"] = {
            "kind": "layer", "file": f"layer_{kind}.glb",
            "variants": variants, "parts": [C.PART_FOLIAGE]}
    for key, spec in FAUNA_TABLE.items():
        table[f"fauna.{key}"] = dict(spec, kind="fauna")
    for sid, (size_m, height_m, scale_mode) in STRUCTURE_SPECS.items():
        table[f"structure.{sid}"] = {
            "kind": "structure", "file": f"struct_{sid}.glb",
            "size_m": size_m, "height_m": height_m, "scale_mode": scale_mode}
    return table


def manifest_dict(generator=""):
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
            plants[key] = entry
    return {
        "version": 1,
        "generator": generator,
        "unit_frame": "base y=0, height 1, half-width 0.5 (re-normalised on load)",
        "plants": plants,
        "fauna": fauna,
        "structures": structures,
    }


def write_manifest(out_dir, generator=""):
    """Write manifest.json and verify every referenced file exists."""
    import os
    mf = manifest_dict(generator)
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

"""Batch build orchestrator — the ONE code path both workflows share.

The Blender-MCP session and the headless CLI both call build_all(), so what
you approved in the viewport is byte-for-byte what gets exported. Each asset
is built into its own wiped-and-recreated collection (idempotent — safe to
re-run in a live session), normalised to the unit frame, AO-baked, budget-
checked (raises on violation), and exported to one GLB.
"""

import random

import bpy

from . import conventions as C
from .ao_bake import bake_ao
from .export_glb import export_glb
from .fauna import build_critter
from .flora_herbs import build_herb, build_layer
from .flora_shrubs import build_shrub
from .flora_trees import build_tree
from .manifest import asset_table, write_manifest
from .mesh_ops import decimate_to_budget, get_collection, make_empty, \
    tri_count, unit_frame, wipe_collection

# Grid spacing when building many assets in one scene (MCP inspection).
_GRID = 2.5


def _budget_for(spec, tier=None):
    if spec["kind"] == "tree":
        return C.TRI_BUDGETS[f"tree_tier{tier}"]
    return C.TRI_BUDGETS[spec["kind"]]


def _check_budget(key, objs, budget):
    n = sum(tri_count(o) for o in objs if o.type == "MESH")
    if n > budget:
        raise ValueError(f"{key}: {n} tris > budget {budget} — simplify the "
                         f"builder or lower its counts (conventions.TRI_BUDGETS)")
    return n


def build_asset(key, spec=None, seed_salt=""):
    """(Re)build one asset into collection `key`; returns {unit: tris}.

    Wipes EVERY generated collection first: Blender object names are global
    to the .blend, and the viewer looks parts/nodes up by exact name — a
    second asset using 'Body' or 'tier0_bark' would get renamed 'Body.001'
    and silently fail to load. One asset is resident at a time.
    """
    table = asset_table()
    spec = spec or table[key]
    for k in table:
        wipe_collection(k)
    coll = get_collection(key, wipe=False)
    rng = random.Random(C.seed_for(key + seed_salt))
    tris = {}

    if spec["kind"] == "tree":
        arch = key.split(".", 1)[1]
        for t in spec["tiers"]:
            prefix = f"tier{t}"
            root = make_empty(prefix, coll)
            parts = build_tree(arch, t, rng, coll, name_prefix=prefix)
            objs = list(parts.values())
            unit_frame(objs)
            budget = _budget_for(spec, t)
            for o in objs:
                decimate_to_budget(o, budget)
            bake_ao([parts[C.PART_BARK]], gradient=False, strength=0.7,
                    seed_key=key + prefix + "bark")
            bake_ao([parts[C.PART_FOLIAGE]], gradient=True, strength=0.85,
                    seed_key=key + prefix)
            tris[prefix] = _check_budget(f"{key}/{prefix}", objs, budget)
            for o in objs:
                o.parent = root
            root.location.x = t * _GRID          # side by side for inspection
    elif spec["kind"] == "shrub":
        parts = build_shrub(key.split(".", 1)[1], rng, coll)
        objs = list(parts.values())
        unit_frame(objs)
        for o in objs:
            decimate_to_budget(o, _budget_for(spec))
        bake_ao([parts[C.PART_BARK]], gradient=False, strength=0.7,
                seed_key=key + "bark")
        bake_ao([parts[C.PART_FOLIAGE]], gradient=True, strength=0.85,
                seed_key=key)
        tris["unit"] = _check_budget(key, objs, _budget_for(spec))
    elif spec["kind"] == "herb":
        parts = build_herb(key.split(".", 1)[1], rng, coll)
        objs = list(parts.values())
        unit_frame(objs)
        for o in objs:
            decimate_to_budget(o, _budget_for(spec))
        bake_ao(objs, gradient=True, strength=0.7, seed_key=key)
        tris["unit"] = _check_budget(key, objs, _budget_for(spec))
    elif spec["kind"] == "layer":
        kind = key.split(".", 1)[1]
        for v in range(spec["variants"]):
            prefix = f"{C.VARIANT_PREFIX}{v}"
            root = make_empty(prefix, coll)
            parts = build_layer(kind, rng, coll, name_prefix=prefix)
            objs = list(parts.values())
            unit_frame(objs)
            for o in objs:
                decimate_to_budget(o, _budget_for(spec))
            bake_ao(objs, gradient=True, strength=0.6, seed_key=key + prefix)
            tris[prefix] = _check_budget(f"{key}/{prefix}", objs,
                                         _budget_for(spec))
            for o in objs:
                o.parent = root
            root.location.x = v * _GRID
    elif spec["kind"] == "fauna":
        kind = key.split(".", 1)[1]
        objs = build_critter(kind, rng, coll)
        tris["unit"] = _check_budget(
            key, objs, C.TRI_BUDGETS["fauna"])          # no AO (tinted flat)
    else:
        raise KeyError(f"unknown asset kind for {key}")
    return tris


def _match(key, only):
    if not only:
        return True
    return any(key == o or key.startswith(o.rstrip("*")) for o in only)


def build_all(out_dir=None, only=None, check_only=False):
    """Build every (matching) asset; export + manifest when out_dir given.

    only  : iterable of keys / 'prefix*' patterns (e.g. ['tree.spruce',
            'fauna*']). None = everything.
    Returns {key: {unit: tris}}.
    """
    import os
    table = asset_table()
    summary = {}
    for key, spec in table.items():
        if not _match(key, only):
            continue
        summary[key] = build_asset(key, spec)
        if out_dir and not check_only:
            os.makedirs(str(out_dir), exist_ok=True)
            coll = bpy.data.collections[key]
            # Export empties + meshes of this asset only. Empties are the
            # tier/variant grid — zero their offset for the export frame.
            roots = [o for o in coll.objects if o.parent is None]
            saved = [(o, o.location.x) for o in roots]
            for o, _x in saved:
                o.location.x = 0.0
            bpy.context.view_layer.update()
            export_glb(list(coll.objects),
                       os.path.join(str(out_dir), spec["file"]))
            for o, x in saved:
                o.location.x = x
    if out_dir and not check_only and not only:
        gen = "assetlib %s / Blender %s" % (
            _asset_version(), ".".join(map(str, bpy.app.version)))
        write_manifest(out_dir, generator=gen)
    return summary


def _asset_version():
    from . import ASSET_VERSION
    return ASSET_VERSION

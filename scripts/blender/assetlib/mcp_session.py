"""Blender-MCP ergonomics: every function here is ONE short, idempotent call
sized for a single `execute_blender_code` invocation.

Session loop (see scripts/blender/README.md for the bootstrap cell):

    S.build("tree.spruce"); S.frame("tree.spruce")
    → get_viewport_screenshot → judge → edit assetlib on disk →
    re-run the bootstrap (reload) → S.build(...) again → …
    S.export_all("<abs repo>/html/assets/models")   # when happy

All state lives in the .blend scene (named collections), never in module
globals — a reload never strands anything.
"""

import bpy

from .build_all import build_all, build_asset
from .manifest import asset_table
from .mesh_ops import tri_count, wipe_collection


def status():
    """{asset key: triangle count} for what is currently built. Note that
    build() keeps ONE asset resident at a time (object names are global to
    the .blend and the viewer looks nodes up by exact name)."""
    table = asset_table()
    out = {}
    for key in table:
        coll = bpy.data.collections.get(key)
        if coll:
            out[key] = sum(tri_count(o) for o in coll.objects
                           if o.type == "MESH")
    return out


def keys(prefix=""):
    """List buildable asset keys (optionally filtered by prefix)."""
    return [k for k in asset_table() if k.startswith(prefix)]


def reset():
    """Wipe every generated collection; keeps the session alive."""
    for key in asset_table():
        wipe_collection(key)
    return "reset"


def build(key):
    """(Re)build one asset in place; returns its per-unit triangle counts."""
    return build_asset(key)


def frame(key):
    """Point every 3D viewport at the asset so a screenshot shows it."""
    coll = bpy.data.collections.get(key)
    if not coll:
        return f"{key} not built"
    for obj in bpy.context.view_layer.objects:
        obj.select_set(obj.name in {o.name for o in coll.objects})
    for window in bpy.context.window_manager.windows:
        for area in window.screen.areas:
            if area.type == "VIEW_3D":
                region = next((r for r in area.regions if r.type == "WINDOW"),
                              None)
                if region:
                    with bpy.context.temp_override(window=window, area=area,
                                                   region=region):
                        bpy.ops.view3d.view_selected()
    return f"framed {key}"


def preview_tint(hex_color="#5a8f4e"):
    """Tint the shared flora preview material (screenshot judgement only —
    COLOR_0 stays grayscale AO; the app applies the real per-plant tints)."""
    from .materials import preview_material
    mat = preview_material()
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    h = hex_color.lstrip("#")
    rgb = tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
    bsdf.inputs["Base Color"].default_value = (*rgb, 1.0)
    return f"preview tinted {hex_color}"


def export_all(out_dir, only=None):
    """Rebuild + export everything (or `only=[...]`) and write the manifest."""
    return build_all(out_dir=out_dir, only=only)

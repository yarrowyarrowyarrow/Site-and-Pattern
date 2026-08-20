"""Preview materials.

Flora: ONE shared preview material whose Base Color reads the 'Color'
vertex-color attribute. Its real job is (a) making the exporter emit COLOR_0
and (b) letting a Blender-MCP viewport screenshot approximate the in-app
shading — the viewer discards imported materials and uses its own.

Fauna: named placeholder materials (conventions.MAT_*). Only the NAME
crosses the contract; the viewer rebuilds each from the appearance bag.
"""

import bpy

from . import conventions as C


def _new_principled(name, rgba, roughness=0.9, metallic=0.0):
    mat = bpy.data.materials.get(name)
    if mat:
        return mat
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = rgba
    bsdf.inputs["Roughness"].default_value = roughness
    bsdf.inputs["Metallic"].default_value = metallic
    return mat


def preview_material():
    """The shared flora material: Color attribute → Base Color."""
    name = "AssetPreview"
    mat = bpy.data.materials.get(name)
    if mat:
        return mat
    mat = _new_principled(name, (0.5, 0.6, 0.4, 1.0))
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    attr = nodes.new("ShaderNodeVertexColor")
    attr.layer_name = "Color"
    links.new(attr.outputs["Color"],
              nodes.get("Principled BSDF").inputs["Base Color"])
    return mat


# Neutral defaults that echo the procedural critters, so MCP screenshots
# read right; the viewer overrides all of these by material NAME.
_FAUNA_DEFAULTS = {
    C.MAT_FUZZ: ((0.85, 0.61, 0.15, 1.0), 0.9, 0.0),
    C.MAT_DARK: ((0.13, 0.10, 0.08, 1.0), 0.85, 0.0),
    C.MAT_BODY: ((0.36, 0.40, 0.46, 1.0), 0.8, 0.0),
    C.MAT_BELLY: ((0.91, 0.89, 0.83, 1.0), 0.85, 0.0),
    C.MAT_WING: ((0.93, 0.96, 0.98, 1.0), 0.3, 0.0),
    C.MAT_FORE: ((0.90, 0.57, 0.18, 1.0), 0.7, 0.0),
    C.MAT_HIND: ((0.85, 0.44, 0.12, 1.0), 0.7, 0.0),
    C.MAT_EDGE: ((0.16, 0.11, 0.06, 1.0), 0.7, 0.0),
    C.MAT_FUR: ((0.23, 0.18, 0.16, 1.0), 0.9, 0.0),
    C.MAT_MEMBRANE: ((0.16, 0.14, 0.19, 1.0), 0.9, 0.0),
}


def fauna_material(name):
    rgba, rough, metal = _FAUNA_DEFAULTS.get(
        name, ((0.5, 0.5, 0.5, 1.0), 0.8, 0.0))
    mat = _new_principled(name, rgba, rough, metal)
    if name == C.MAT_WING:
        mat.blend_method = "BLEND"
        bsdf = mat.node_tree.nodes.get("Principled BSDF")
        if "Alpha" in bsdf.inputs:
            bsdf.inputs["Alpha"].default_value = 0.3
    return mat


# Structure materials are KEPT by the viewer (structures have fixed real-world
# colours — wood, stone, water — with no seasonal tinting), so unlike flora
# these colours ship. Values are sRGB (converted to linear at material build);
# baked COLOR_0 AO multiplies through in three.js.
_STRUCTURE_PALETTE = {
    "MatWood":     ((0.42, 0.32, 0.21, 1.0), 0.85, 0.0),
    "MatWoodDark": ((0.28, 0.21, 0.14, 1.0), 0.9, 0.0),
    "MatStone":    ((0.53, 0.52, 0.49, 1.0), 0.95, 0.0),
    "MatGravel":   ((0.42, 0.39, 0.33, 1.0), 1.0, 0.0),
    "MatWater":    ((0.20, 0.42, 0.53, 1.0), 0.25, 0.0),
    "MatSoil":     ((0.27, 0.20, 0.13, 1.0), 1.0, 0.0),
    "MatTurf":     ((0.30, 0.42, 0.23, 1.0), 1.0, 0.0),
    "MatMetal":    ((0.42, 0.45, 0.47, 1.0), 0.45, 0.6),
    "MatAsh":      ((0.21, 0.20, 0.19, 1.0), 1.0, 0.0),
    "MatHole":     ((0.12, 0.09, 0.07, 1.0), 1.0, 0.0),
    "MatBark":     ((0.33, 0.26, 0.18, 1.0), 0.95, 0.0),
}


def _srgb_to_linear(c):
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def structure_material(name):
    # The palette above is authored in sRGB (what the eye expects); glTF
    # baseColorFactor is LINEAR — without this conversion everything ships
    # ~1.5 stops too bright and washes out under the viewer's ACES pass.
    rgba, rough, metal = _STRUCTURE_PALETTE.get(
        name, ((0.5, 0.5, 0.5, 1.0), 0.9, 0.0))
    lin = tuple(_srgb_to_linear(c) for c in rgba[:3]) + (rgba[3],)
    return _new_principled(name, lin, rough, metal)

"""GLB export — the ONLY place exporter kwargs live.

Blender's glTF exporter kwargs drift across versions (the vertex-color
switch alone: export_colors → always-on → export_vertex_color). Instead of
guessing per version, the want-dict is filtered against the operator's
actual RNA properties, so unknown kwargs are dropped rather than raising.

Pin: Blender 4.2 LTS or newer (recorded per-build in manifest.generator).
"""

import bpy


def _filter_kwargs(want):
    props = bpy.ops.export_scene.gltf.get_rna_type().properties.keys()
    return {k: v for k, v in want.items() if k in props}


def export_glb(objects, filepath):
    """Export exactly `objects` (plus their empties/parents) to a GLB."""
    for obj in bpy.context.view_layer.objects:
        obj.select_set(False)
    roots = set()
    for obj in objects:
        o = obj
        obj.select_set(True)
        while o.parent is not None:
            o = o.parent
            o.select_set(True)
        roots.add(o)
    bpy.context.view_layer.objects.active = next(iter(roots), None)

    want = dict(
        filepath=str(filepath),
        export_format="GLB",
        use_selection=True,
        export_yup=True,                 # viewer frame (three.js) is Y-up
        export_apply=True,               # bake modifiers
        export_animations=False,
        export_skins=False,
        export_morph=False,
        export_cameras=False,
        export_lights=False,
        export_materials="EXPORT",       # names carry the fauna tint contract
        export_image_format="NONE",      # no textures, ever (tint-ability)
        export_vertex_color="ACTIVE",    # COLOR_0 = the baked AO attribute
        export_attributes=False,
        export_extras=False,
        export_normals=True,
        export_texcoords=False,
    )
    bpy.ops.export_scene.gltf(**_filter_kwargs(want))

"""assetlib — Blender generators for Site & Pattern's 3D GLB assets.

Runs ONLY inside Blender (4.2 LTS+): `import bpy` everywhere. Nothing in
the app, its tests, or requirements*.txt may import this package — the
committed GLB output under html/assets/models/ is what ships (the same
regenerate-and-commit pattern as scripts/render_flower_sprites.py).

Two drivers, one code path (build_all):
  headless : blender --background --python scripts/blender/build_assets.py \
                 -- --out html/assets/models
  MCP      : the bootstrap cell in scripts/blender/README.md, then
             `from assetlib import mcp_session as S; S.build("tree.spruce")`
"""

ASSET_VERSION = 1

_SUBMODULES = (
    # dependency order — reload_all() walks this list
    "conventions",
    "materials",
    "mesh_ops",
    "ao_bake",
    "flora_trees",
    "flora_shrubs",
    "flora_herbs",
    "fauna",
    "export_glb",
    "manifest",
    "build_all",
    "mcp_session",
)


def reload_all():
    """Reload every submodule in dependency order — one call picks up disk
    edits mid-MCP-session. Module state is design-stateless (all build state
    lives in the .blend scene), so reloading never strands anything."""
    import importlib
    import sys
    for name in _SUBMODULES:
        mod = sys.modules.get(__name__ + "." + name)
        if mod is not None:
            importlib.reload(mod)

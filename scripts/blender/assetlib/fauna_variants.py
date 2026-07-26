"""The fauna BUILD vocabularies, in a bpy-free module (V2.33, F67).

A bumblebee is not a honeybee, and until now every bee in the roster was one
model in different colours. The identification problem this fixes is specific
and severe: **62 of the catalogue's 69 native bees have no photograph** and,
under the licence policy, will not get one — so where there is no photo, the
model is the only thing carrying the identification.

These live apart from :mod:`fauna` (which imports ``bpy`` at module scope) for
the same reason ``conventions`` does: the manifest writer, the viewer-parity
guard in ``tests/test_model_assets.py`` and anything else that needs to know
*what exists* must be able to read it without Blender installed.

Each name is both the Blender variant-root object name inside the file and the
``app.build`` value the viewer selects on (``src/scene_wildlife.py``), so the
two ends cannot drift apart without a test noticing.
"""

# Bombus · the medium generalists · the small narrow bees · Megachile.
BEE_VARIANTS = ("round", "stout", "slender", "leafcutter")

# lepidoptera_attributes.kind records butterfly / moth / skipper; swallowtails
# are the one further silhouette worth naming, because the tail is unmistakable.
LEP_VARIANTS = ("butterfly", "moth", "skipper", "swallowtail")

# A chickadee on a twig, a woodpecker propped against a trunk, a hummingbird.
BIRD_VARIANTS = ("passerine", "woodpecker", "hummer")

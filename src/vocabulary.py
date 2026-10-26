"""
vocabulary.py — one name for each thing (V3.21, WD-1; the owner's W1:
docs/homeowner/09-words.md §2).

Design principle P5 — see docs/DESIGN_PHILOSOPHY.md.

The first review found the app calling one thing by three names and speaking
to a homeowner in an ecologist's words: *polyculture* beside *community*,
*boundary* beside *outline*, *species* where a person says *plant*. The
glossary is the contract for the simple app, and this module holds it as data
so a test can hold the code to it (``tests/test_vocabulary.py``), the way the
visual floors hold contrast.

  * :data:`NEVER`: words no user-facing text uses, simple or advanced.
  * :data:`ADVANCED_ONLY`: words the simple app does not use; the advanced
    pages may (``Advanced may also say``).

The rewrites themselves are WD-2 to WD-6, increment by increment; until then
the test carries today's counts and fails on any new use.
"""

from __future__ import annotations

#: ``(thing, the simple app says, advanced may also say, never)``, as
#: 09-words.md §2 writes it.
GLOSSARY: tuple = (
    ("The file you work on", "design", (), ("project", ".perma.geojson")),
    ("What Plan My Yard makes, and the printout", "plan",
     ("generated design",), ("spec",)),
    ("The pin on the map", "your yard's pin", ("property pin", "site"), ()),
    ("The outline of the yard", "yard outline", ("boundary",),
     ("property boundary",)),
    ("A drawn planting area", "bed", ("planting area",),
     ("fill zone", "fill region")),
    ("A kind of plant", "plant", ("species",), ("taxon",)),
    ("A ready-made planting", "community", ("plant community", "mix"),
     ("polyculture", "guild")),
    ("A wildflower", "wildflower", ("forb",), ()),
    ("The grasses between the flowers", "grasses", ("matrix grasses",), ()),
    ("The plants that feed the most caterpillars",
     "plants that feed the most caterpillars", ("keystone",), ()),
    ("A plant a caterpillar must eat", "caterpillar food plant",
     ("larval host",), ()),
    ("Animals with one food", "depends on this plant", ("specialist",), ()),
    ("Native within 50 km of downtown", "native around Edmonton",
     ("Edmonton list",), ()),
    ("Native in the province (VASCAN)", "native to Alberta", (),
     ("Alberta native",)),
    ("How far apart to plant", "plant about 60 cm apart", ("spacing",), ()),
    ("How wide it grows", "grows about 1 m wide", ("canopy", "spread"), ()),
    ("Spreads by roots or seed", "spreads",
     ("rhizomatous", "self-seeding"), ("well behaved",)),
    ("Poisonous", "poisonous to pets", ("toxicity",),
     ("pet friendly", "pet safe")),
    ("The first two years", "the first two summers", ("establishment",), ()),
    ("Early plants that fade", "fills in first, then gives way",
     ("early successional",), ("pioneer", "colonizer")),
    ("The habitat score", "", ("habitat score",), ("Habitat Value Score",)),
    ("A natural region", "the Edmonton region",
     ("ecoregion", "natural subregion"), ()),
    ("The middle of the moisture scale", "medium moisture", (), ("mesic",)),
    ("Prices", "about $X–$Y at Edmonton native nurseries",
     ("estimated retail price",), ("AB retail estimate",)),
)

#: Words no user-facing text says. "property boundary" and "Habitat Value
#: Score" are §2's "in simple text": they are ADVANCED_ONLY below.
NEVER: tuple = tuple(sorted({
    word for _t, _s, _a, never in GLOSSARY for word in never
    if word not in ("property boundary", "Habitat Value Score")}))

#: Words the simple app does not say. "site" and "mix" are left out: both
#: are ordinary English the simple app uses in their plain sense ("this
#: site", "a mix of grasses").
ADVANCED_ONLY: tuple = tuple(sorted({
    word for _t, _s, advanced, _n in GLOSSARY for word in advanced
    if word not in ("site", "mix")} | {"property boundary",
                                       "Habitat Value Score"}))

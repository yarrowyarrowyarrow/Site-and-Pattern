#!/usr/bin/env python3
"""Author the FLOWER MORPHOLOGY fields in data/plants_master.json
(V2.34, schema v53). Idempotent — re-running rewrites the same values, so this
file is both the tool and the provenance record.

    python scripts/seed_flower_morphology.py [--check]

WHY THESE FIELDS EXIST
A wildflower in bloom is 60–80% flower to the eye. Until now the app drew that
flower as **one 64 × 64 image per `flower_form`** — fifteen pictures for 228
wildflowers — on an unlit material, seven copies scattered in a disc at 90% of
the plant's height. Meanwhile the body underneath grew real leaves of the
species' own outline and size at ~1,200 triangles.

That mismatch is the whole problem, and it is not a resolution problem. A
faceted low-poly plant reads fine because it is a *confident abstraction*; a
realistically-leaved body wearing a cartoon bloom invites a comparison with a
real plant and then loses it. The measured state before this pass:

    228 wildflowers · 51 distinct (growth_form × flower_form) looks
    31 of them sharing "erect × spike" · 154 in a bucket of 5+ identical looks
    19 distinct flower colours in the entire catalogue

So the bloom becomes geometry, and geometry needs characters. These ten fields
are the ones a generator actually needs and that no single flora records
together.

WHY NOT JUST EXTEND ``flower_form``
Because ``flower_form`` is a POLLINATOR-ACCESS statement: ``bee_habitat.
tongue_form_fit`` and ``forage_calendar`` read it to decide which bees can work
a flower. It is not a picture, it must not become one, and it is untouched here.
Exactly the separation ``inflorescence_form`` took in v52 and ``fruit_form`` in
v49.

THE FIELDS
  flower_arch          Where the florets sit in space — most of a forb's
                       silhouette. A goldenrod's plume, a yarrow's flat corymb
                       and a lupine's spike are three ARCHITECTURES, not three
                       textures. solitary · raceme · spike · panicle · corymb ·
                       umbel · head · cyme · whorl
  flower_symmetry      radial (a daisy) or bilateral (a pea, a penstemon, an
                       orchid). Not the same flower and never were.
  petal_shape          narrow · oval · notched · tubular · lipped
  petal_count          Rays or petals on ONE floret. The first thing anyone
                       counts, and the difference between a buttercup and an
                       anemone.
  florets_per_head     How many florets the DRAWN unit carries: 40 on a
                       daisy's head, 12 up a spike, and — for the rayless
                       composites whose drawn unit is the whole spray — the
                       hundreds of tiny heads in a goldenrod plume.
  flower_diameter_cm   ONE floret across. The most valuable missing number in
                       the catalogue: bloom size is currently derived from
                       CANOPY, so a pasqueflower and a sunflower scale with the
                       plant rather than with the flower.
  flower_center_color  The disc/eye. A black-eyed Susan *is* its dark disc, and
                       it was being drawn as a yellow blob.
  flower_height_frac   How far the bloom is held above the foliage.
  stem_branching       unbranched · branched_above · branched_throughout —
                       the fix for every forb stem being one straight rod.
  basal_rosette        0/1.

SOURCING (P9)
Assignment is BY GENUS, from the standard floral formulae and inflorescence
types that every flora of the prairie provinces and boreal Canada keys on (see
docs/REFERENCES.md) — Asteraceae heads, Fabaceae papilionaceous flowers,
Apiaceae umbels, Lamiaceae whorls of bilabiate flowers, Rosaceae five-petalled
cymes, Brassicaceae crosses, Liliaceae six-tepalled stars. Diameters are TYPICAL
for the genus as it occurs here, and the counts are typical, not invariant —
Asteraceae ray counts in particular vary within a head.

Where a genus is not one flower, SPECIES_OVERRIDE records the split. Where a
genus is not covered, the record stays EMPTY and the viewer draws exactly the
billboard it drew before — partial coverage degrades to today, never to a hole.

This encodes no traditional, cultural or Indigenous knowledge of these plants —
only the botanical description of the flower (P12).
"""

from __future__ import annotations

import argparse
import json
import os

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_MASTER = os.path.join(_ROOT, "data", "plants_master.json")

ARCHITECTURES = ("solitary", "raceme", "spike", "panicle", "corymb", "umbel",
                 "head", "cyme", "whorl")
SYMMETRIES = ("radial", "bilateral")
PETAL_SHAPES = ("narrow", "oval", "notched", "tubular", "lipped")
BRANCHINGS = ("unbranched", "branched_above", "branched_throughout")

FIELDS = ("flower_arch", "flower_symmetry", "petal_shape", "petal_count",
          "florets_per_head", "flower_diameter_cm", "flower_center_color",
          "flower_height_frac", "stem_branching", "basal_rosette")


def F(arch, sym, shape, petals, florets, dia, centre,
      height_frac=1.0, branching="branched_above", rosette=0):
    """One flower description. Positional in the order the eye reads it."""
    return {"flower_arch": arch, "flower_symmetry": sym, "petal_shape": shape,
            "petal_count": petals, "florets_per_head": florets,
            "flower_diameter_cm": dia, "flower_center_color": centre,
            "flower_height_frac": height_frac, "stem_branching": branching,
            "basal_rosette": rosette}


# ── Asteraceae ──────────────────────────────────────────────────────────────
# A "flower" here is a HEAD of many florets, and the disc is half the picture.
_DAISY_WHITE = F("head", "radial", "narrow", 21, 40, 3.0, "#f2c94c",
                 branching="branched_above", rosette=1)
_DAISY_YELLOW = F("head", "radial", "oval", 13, 60, 5.0, "#8a5a1e")

GENUS = {
    # — Asteraceae, ray + disc —
    "Echinacea":     F("head", "radial", "narrow", 15, 90, 8.0, "#a4622a",
                       branching="unbranched", rosette=1),
    "Rudbeckia":     F("head", "radial", "oval", 12, 70, 7.0, "#3b2412",
                       branching="branched_above", rosette=1),
    "Ratibida":      F("head", "radial", "narrow", 6, 60, 5.0, "#6b4a20",
                       branching="branched_above"),
    "Gaillardia":    F("head", "radial", "notched", 12, 80, 6.0, "#7d2b1c",
                       branching="branched_above", rosette=1),
    "Helianthus":    F("head", "radial", "oval", 18, 120, 8.0, "#6d4a1c",
                       branching="branched_throughout"),
    "Heliopsis":     F("head", "radial", "oval", 12, 60, 6.0, "#c58b2a"),
    "Balsamorhiza":  F("head", "radial", "narrow", 14, 80, 8.0, "#c58b2a",
                       branching="unbranched", rosette=1),
    "Arnica":        F("head", "radial", "oval", 12, 50, 5.0, "#d9a63a",
                       branching="unbranched", rosette=1),
    "Erigeron":      F("head", "radial", "narrow", 60, 90, 2.5, "#e5c65a",
                       branching="branched_above", rosette=1),
    "Symphyotrichum": F("head", "radial", "narrow", 25, 45, 2.5, "#e8b93a",
                        branching="branched_throughout"),
    "Aster":         F("head", "radial", "narrow", 25, 45, 2.5, "#e8b93a",
                       branching="branched_throughout"),
    "Eurybia":       F("head", "radial", "narrow", 15, 40, 3.0, "#e8b93a",
                       branching="branched_above"),
    "Canadanthus":   F("head", "radial", "narrow", 25, 45, 2.5, "#e8b93a",
                       branching="branched_throughout"),
    "Doellingeria":  F("head", "radial", "narrow", 8, 35, 1.6, "#e8d76a",
                       branching="branched_above"),
    "Dieteria":      F("head", "radial", "narrow", 22, 45, 3.0, "#e8b93a",
                       branching="branched_throughout"),
    "Townsendia":    F("head", "radial", "narrow", 30, 60, 3.0, "#e5c65a",
                       branching="unbranched", rosette=1),
    "Heterotheca":   F("head", "radial", "narrow", 18, 45, 2.5, "#d9a63a",
                       branching="branched_throughout"),
    "Grindelia":     F("head", "radial", "narrow", 26, 100, 3.5, "#d9a63a",
                       branching="branched_above"),
    "Helenium":      F("head", "radial", "notched", 13, 90, 4.0, "#8a6a22"),
    "Coreopsis":     F("head", "radial", "notched", 8, 50, 5.0, "#7d4a1c"),
    "Packera":       F("head", "radial", "narrow", 10, 40, 2.2, "#e8b93a",
                       branching="branched_above", rosette=1),
    "Agoseris":      F("head", "radial", "narrow", 40, 40, 3.0, "#e8c552",
                       branching="unbranched", rosette=1),
    "Hieracium":     F("head", "radial", "narrow", 40, 40, 2.2, "#e8c552",
                       branching="branched_above", rosette=1),
    # — Asteraceae, disc-only or rayless: no ray petals to draw —
    "Solidago":      F("panicle", "radial", "narrow", 10, 160, 0.6, "#e8c552",
                       branching="branched_above"),
    "Oligoneuron":   F("corymb", "radial", "narrow", 10, 130, 0.6, "#e8c552",
                       branching="branched_above"),
    "Euthamia":      F("corymb", "radial", "narrow", 12, 130, 0.5, "#e8c552",
                       branching="branched_above"),
    "Ericameria":    F("panicle", "radial", "narrow", 5, 90, 0.7, "#e8c552",
                       branching="branched_throughout"),
    "Gutierrezia":   F("panicle", "radial", "narrow", 6, 90, 0.6, "#e8c552",
                       branching="branched_throughout"),
    "Liatris":       F("spike", "radial", "narrow", 8, 30, 1.4, "#7b3f98",
                       branching="unbranched"),
    "Cirsium":       F("head", "radial", "tubular", 0, 120, 3.5, "#a05aa8",
                       branching="branched_above", rosette=1),
    "Antennaria":    F("corymb", "radial", "tubular", 0, 30, 0.7, "#efe6d8",
                       branching="unbranched", rosette=1),
    "Anaphalis":     F("corymb", "radial", "tubular", 0, 40, 0.8, "#e8c552",
                       branching="branched_above"),
    "Artemisia":     F("panicle", "radial", "tubular", 0, 70, 0.3, "#b7bc86",
                       branching="branched_throughout"),
    "Eutrochium":    F("corymb", "radial", "tubular", 0, 60, 0.6, "#c9a0c9",
                       branching="branched_above"),

    # — Fabaceae: the pea flower, bilateral, on a raceme —
    "Lupinus":       F("raceme", "bilateral", "lipped", 5, 40, 1.6, "",
                       branching="unbranched"),
    "Astragalus":    F("raceme", "bilateral", "lipped", 5, 18, 1.4, "",
                       branching="branched_above"),
    "Oxytropis":     F("raceme", "bilateral", "lipped", 5, 20, 1.6, "",
                       branching="unbranched", rosette=1),
    "Hedysarum":     F("raceme", "bilateral", "lipped", 5, 30, 1.6, "",
                       branching="branched_above"),
    "Dalea":         F("spike", "bilateral", "lipped", 5, 50, 0.7, "#e8a63a",
                       branching="branched_above"),
    "Vicia":         F("raceme", "bilateral", "lipped", 5, 14, 1.5, "",
                       branching="branched_throughout"),
    "Lathyrus":      F("raceme", "bilateral", "lipped", 5, 8, 2.0, "",
                       branching="branched_throughout"),
    "Thermopsis":    F("raceme", "bilateral", "lipped", 5, 25, 2.2, "",
                       branching="unbranched"),
    "Glycyrrhiza":   F("raceme", "bilateral", "lipped", 5, 40, 1.2, "",
                       branching="branched_above"),
    "Pediomelum":    F("raceme", "bilateral", "lipped", 5, 25, 1.2, "",
                       branching="branched_above"),

    # — Lamiaceae: whorls of two-lipped flowers up a square stem —
    "Monarda":       F("head", "bilateral", "lipped", 5, 30, 3.0, "#b06a9a",
                       branching="branched_above"),
    "Agastache":     F("spike", "bilateral", "lipped", 5, 60, 1.0, "",
                       branching="branched_above"),
    "Stachys":       F("whorl", "bilateral", "lipped", 5, 20, 1.2, "",
                       branching="unbranched"),
    "Prunella":      F("spike", "bilateral", "lipped", 5, 25, 1.2, "",
                       branching="branched_above"),
    "Scutellaria":   F("raceme", "bilateral", "lipped", 5, 12, 1.8, "",
                       branching="branched_above"),
    "Mentha":        F("whorl", "bilateral", "lipped", 4, 30, 0.5, "",
                       branching="branched_throughout"),
    "Physostegia":   F("spike", "bilateral", "lipped", 5, 24, 2.5, "",
                       branching="unbranched"),

    # — Apiaceae: the compound umbel —
    "Zizia":         F("umbel", "radial", "oval", 5, 100, 0.3, "",
                       branching="branched_above"),
    "Angelica":      F("umbel", "radial", "oval", 5, 200, 0.3, "",
                       branching="branched_above"),
    "Osmorhiza":     F("umbel", "radial", "oval", 5, 40, 0.3, "",
                       branching="branched_above"),
    "Sium":          F("umbel", "radial", "oval", 5, 120, 0.3, "",
                       branching="branched_above"),

    # — Rosaceae: five broad petals, many stamens, in a cyme —
    "Potentilla":    F("cyme", "radial", "oval", 5, 12, 2.0, "#d8b83a",
                       branching="branched_throughout"),
    "Drymocallis":   F("cyme", "radial", "oval", 5, 14, 1.8, "#d8b83a",
                       branching="branched_above"),
    "Dasiphora":     F("cyme", "radial", "oval", 5, 10, 3.0, "#d8b83a",
                       branching="branched_throughout"),
    "Comarum":       F("cyme", "radial", "oval", 5, 6, 2.0, "#7d2b3a",
                       branching="branched_above"),
    "Sibbaldia":     F("cyme", "radial", "narrow", 5, 8, 0.6, "#d8b83a",
                       branching="branched_above", rosette=1),
    "Geum":          F("cyme", "radial", "oval", 5, 6, 1.6, "#d8b83a",
                       branching="branched_above", rosette=1),
    "Fragaria":      F("cyme", "radial", "oval", 5, 6, 1.8, "#e8d76a",
                       branching="branched_above", rosette=1),
    "Dryas":         F("solitary", "radial", "oval", 8, 1, 3.0, "#e8c552",
                       branching="unbranched", rosette=1),
    "Rosa":          F("solitary", "radial", "notched", 5, 3, 5.0, "#e8c552",
                       branching="branched_throughout"),
    "Rubus":         F("cyme", "radial", "oval", 5, 8, 2.5, "#e8e0c0",
                       branching="branched_throughout"),
    "Spiraea":       F("corymb", "radial", "oval", 5, 120, 0.5, "",
                       branching="branched_above"),
    "Amelanchier":   F("raceme", "radial", "narrow", 5, 12, 2.5, "#e8e0c0",
                       branching="branched_throughout"),
    "Prunus":        F("raceme", "radial", "oval", 5, 30, 1.2, "#e8e0c0",
                       branching="branched_throughout"),
    "Crataegus":     F("corymb", "radial", "oval", 5, 20, 1.6, "#d8b8a0",
                       branching="branched_throughout"),
    "Sorbus":        F("corymb", "radial", "oval", 5, 150, 0.8, "#e8e0c0",
                       branching="branched_throughout"),
    "Agrimonia":     F("spike", "radial", "oval", 5, 40, 0.7, "#d8b83a",
                       branching="unbranched"),

    # — Ranunculaceae —
    "Anemone":       F("solitary", "radial", "oval", 5, 2, 3.0, "#e8d76a",
                       branching="branched_above", rosette=1),
    "Anemonastrum":  F("umbel", "radial", "oval", 5, 4, 2.5, "#e8d76a",
                       branching="unbranched", rosette=1),
    "Pulsatilla":    F("solitary", "radial", "oval", 6, 1, 6.0, "#e8c552",
                       branching="unbranched", rosette=1),
    "Aquilegia":     F("solitary", "radial", "tubular", 5, 3, 4.0, "#e8d76a",
                       branching="branched_above"),
    "Delphinium":    F("raceme", "bilateral", "oval", 5, 20, 2.5, "#e8e8f0",
                       branching="unbranched"),
    "Thalictrum":    F("panicle", "radial", "narrow", 0, 80, 0.5, "#e8e0c0",
                       branching="branched_throughout"),
    "Ranunculus":    F("cyme", "radial", "oval", 5, 6, 2.0, "#d8b83a",
                       branching="branched_above"),
    "Caltha":        F("cyme", "radial", "oval", 6, 4, 3.0, "#d8b83a",
                       branching="branched_above", rosette=1),
    "Actaea":        F("raceme", "radial", "narrow", 4, 60, 0.5, "#e8e0c0",
                       branching="branched_above"),
    "Clematis":      F("solitary", "radial", "oval", 4, 3, 3.0, "#e8d76a",
                       branching="branched_throughout"),

    # — Liliaceae and allies: six tepals —
    "Lilium":        F("solitary", "radial", "oval", 6, 2, 7.0, "#8a5a1e",
                       branching="unbranched"),
    "Fritillaria":   F("solitary", "radial", "oval", 6, 2, 2.5, "#8a7a3a",
                       branching="unbranched"),
    "Erythronium":   F("solitary", "radial", "narrow", 6, 1, 4.0, "#d8b83a",
                       branching="unbranched", rosette=1),
    "Allium":        F("umbel", "radial", "oval", 6, 30, 0.8, "",
                       branching="unbranched", rosette=1),
    "Anticlea":      F("panicle", "radial", "oval", 6, 40, 1.2, "#c8d86a",
                       branching="branched_above", rosette=1),
    "Maianthemum":   F("raceme", "radial", "narrow", 6, 60, 0.5, "",
                       branching="unbranched"),
    "Iris":          F("solitary", "bilateral", "oval", 6, 2, 8.0, "#e8c552",
                       branching="unbranched"),
    "Sisyrinchium":  F("umbel", "radial", "notched", 6, 4, 1.6, "#e8d76a",
                       branching="unbranched"),
    "Yucca":         F("panicle", "radial", "oval", 6, 40, 5.0, "",
                       branching="unbranched", rosette=1),
    "Cypripedium":   F("solitary", "bilateral", "lipped", 3, 1, 5.0, "",
                       branching="unbranched"),
    "Spiranthes":    F("spike", "bilateral", "lipped", 3, 40, 0.8, "",
                       branching="unbranched", rosette=1),

    # — Onagraceae —
    "Chamaenerion":  F("raceme", "radial", "oval", 4, 40, 3.0, "#c86a9a",
                       branching="unbranched"),
    "Oenothera":     F("spike", "radial", "notched", 4, 20, 5.0, "#d8b83a",
                       branching="unbranched", rosette=1),

    # — Brassicaceae: the four-petalled cross —
    "Draba":         F("raceme", "radial", "notched", 4, 20, 0.6, "#d8d86a",
                       branching="branched_above", rosette=1),
    "Physaria":      F("raceme", "radial", "oval", 4, 20, 1.0, "#d8b83a",
                       branching="branched_above", rosette=1),
    "Peritoma":      F("raceme", "bilateral", "narrow", 4, 40, 1.5, "",
                       branching="branched_above"),

    # — Scrophulariaceae / Orobanchaceae / Plantaginaceae: bilateral tubes —
    "Penstemon":     F("raceme", "bilateral", "tubular", 5, 24, 2.5, "",
                       branching="unbranched"),
    "Castilleja":    F("spike", "bilateral", "lipped", 5, 30, 2.0, "",
                       branching="unbranched"),
    "Pedicularis":   F("spike", "bilateral", "lipped", 5, 25, 1.6, "",
                       branching="unbranched", rosette=1),
    "Rhinanthus":    F("raceme", "bilateral", "lipped", 5, 16, 1.5, "",
                       branching="unbranched"),
    "Orthocarpus":   F("spike", "bilateral", "lipped", 5, 30, 1.2, "",
                       branching="unbranched"),
    "Erythranthe":   F("raceme", "bilateral", "lipped", 5, 12, 2.5, "#c8a03a",
                       branching="branched_above"),
    "Mimulus":       F("raceme", "bilateral", "lipped", 5, 12, 2.5, "#c8a03a",
                       branching="branched_above"),
    "Linaria":       F("raceme", "bilateral", "lipped", 5, 30, 2.0, "#e8c552",
                       branching="unbranched"),

    # — Campanulaceae / Gentianaceae: bells —
    "Campanula":     F("raceme", "radial", "oval", 5, 8, 2.0, "",
                       branching="branched_above"),
    "Gentiana":      F("cyme", "radial", "oval", 5, 6, 3.5, "",
                       branching="unbranched"),
    "Gentianella":   F("cyme", "radial", "oval", 4, 10, 2.0, "",
                       branching="branched_above"),
    "Menyanthes":    F("raceme", "radial", "narrow", 5, 12, 1.5, "#e8e0c0",
                       branching="unbranched", rosette=1),

    # — Polemoniaceae / Boraginaceae / Hydrophyllaceae —
    "Phlox":         F("cyme", "radial", "notched", 5, 8, 2.0, "#e8e0c0",
                       branching="branched_throughout", rosette=1),
    "Polemonium":    F("cyme", "radial", "oval", 5, 20, 1.6, "#e8d76a",
                       branching="branched_above", rosette=1),
    "Mertensia":     F("cyme", "radial", "tubular", 5, 20, 1.4, "",
                       branching="branched_above"),
    "Myosotis":      F("cyme", "radial", "notched", 5, 25, 0.7, "#e8d76a",
                       branching="branched_above"),
    "Lithospermum":  F("cyme", "radial", "tubular", 5, 15, 1.6, "",
                       branching="branched_above"),
    "Phacelia":      F("cyme", "radial", "oval", 5, 40, 0.8, "",
                       branching="branched_above"),

    # — Saxifragaceae —
    "Heuchera":      F("panicle", "radial", "narrow", 5, 80, 0.5, "",
                       branching="unbranched", rosette=1),
    "Mitella":       F("raceme", "radial", "narrow", 5, 20, 0.4, "",
                       branching="unbranched", rosette=1),

    # — the rest, by genus —
    "Achillea":      F("corymb", "radial", "oval", 5, 200, 0.5, "#e8e0c0",
                       branching="branched_above"),
    "Asclepias":     F("umbel", "radial", "oval", 5, 60, 1.0, "",
                       branching="branched_above"),
    "Apocynum":      F("cyme", "radial", "oval", 5, 30, 0.6, "",
                       branching="branched_throughout"),
    "Viola":         F("solitary", "bilateral", "oval", 5, 4, 2.0, "#e8d76a",
                       branching="unbranched", rosette=1),
    "Geranium":      F("cyme", "radial", "notched", 5, 6, 3.0, "#e8e0c0",
                       branching="branched_throughout"),
    "Linum":         F("cyme", "radial", "oval", 5, 8, 2.5, "#e8d76a",
                       branching="branched_above"),
    "Sphaeralcea":   F("raceme", "radial", "notched", 5, 20, 2.5, "",
                       branching="branched_above"),
    "Iliamna":       F("raceme", "radial", "notched", 5, 20, 5.0, "",
                       branching="branched_above"),
    "Eriogonum":     F("umbel", "radial", "narrow", 6, 40, 0.4, "",
                       branching="unbranched", rosette=1),
    "Persicaria":    F("spike", "radial", "narrow", 5, 60, 0.4, "",
                       branching="branched_above"),
    "Silene":        F("cyme", "radial", "notched", 5, 6, 1.6, "",
                       branching="branched_above", rosette=1),
    "Cerastium":     F("cyme", "radial", "notched", 5, 10, 1.2, "#e8d76a",
                       branching="branched_above"),
    "Androsace":     F("umbel", "radial", "oval", 5, 12, 0.4, "#e8d76a",
                       branching="unbranched", rosette=1),
    "Primula":       F("umbel", "radial", "notched", 5, 10, 1.6, "#e8c552",
                       branching="unbranched", rosette=1),
    "Dodecatheon":   F("umbel", "bilateral", "narrow", 5, 10, 2.0, "#8a5a1e",
                       branching="unbranched", rosette=1),
    "Lysimachia":    F("raceme", "radial", "oval", 5, 30, 1.2, "#c86a3a",
                       branching="branched_above"),
    "Galium":        F("panicle", "radial", "narrow", 4, 60, 0.3, "",
                       branching="branched_throughout"),
    "Valeriana":     F("corymb", "radial", "oval", 5, 80, 0.4, "",
                       branching="branched_above", rosette=1),
    "Comandra":      F("cyme", "radial", "narrow", 5, 20, 0.5, "",
                       branching="branched_above"),
    "Sedum":         F("cyme", "radial", "narrow", 5, 30, 1.0, "",
                       branching="branched_above"),
    "Rhodiola":      F("corymb", "radial", "narrow", 4, 40, 0.5, "",
                       branching="unbranched"),
    "Escobaria":     F("solitary", "radial", "narrow", 20, 2, 3.0, "#e8d76a",
                       branching="unbranched"),
    "Opuntia":       F("solitary", "radial", "oval", 10, 3, 6.0, "#e8d76a",
                       branching="unbranched"),
    "Capnoides":     F("raceme", "bilateral", "tubular", 4, 20, 1.2, "",
                       branching="branched_above"),
    "Pyrola":        F("raceme", "radial", "oval", 5, 12, 1.2, "#c8c86a",
                       branching="unbranched", rosette=1),
    "Ledum":         F("corymb", "radial", "oval", 5, 30, 1.2, "",
                       branching="branched_throughout"),
    "Vaccinium":     F("raceme", "radial", "oval", 5, 8, 0.6, "",
                       branching="branched_throughout"),
    "Arctostaphylos": F("raceme", "radial", "oval", 5, 10, 0.5, "",
                        branching="branched_throughout"),
    "Ribes":         F("raceme", "radial", "oval", 5, 12, 0.8, "",
                       branching="branched_throughout"),
    "Symphoricarpos": F("raceme", "radial", "oval", 5, 8, 0.5, "",
                        branching="branched_throughout"),
    "Lonicera":      F("cyme", "bilateral", "tubular", 5, 4, 1.6, "",
                       branching="branched_throughout"),
    "Linnaea":       F("solitary", "radial", "tubular", 5, 2, 1.0, "",
                       branching="unbranched"),
    "Viburnum":      F("corymb", "radial", "oval", 5, 120, 0.6, "",
                       branching="branched_throughout"),
    "Cornus":        F("cyme", "radial", "narrow", 4, 60, 0.6, "",
                       branching="branched_throughout"),
    "Mahonia":       F("raceme", "radial", "oval", 6, 30, 0.8, "",
                       branching="branched_throughout"),
    "Paxistima":     F("cyme", "radial", "narrow", 4, 6, 0.3, "",
                       branching="branched_throughout"),
    "Salix":         F("spike", "radial", "narrow", 0, 80, 0.3, "",
                       branching="branched_throughout"),
    "Sagittaria":    F("whorl", "radial", "oval", 3, 9, 2.5, "#e8d76a",
                       branching="unbranched"),
    "Alisma":        F("panicle", "radial", "oval", 3, 60, 0.8, "#e8d76a",
                       branching="branched_throughout"),
    "Nuphar":        F("solitary", "radial", "oval", 6, 1, 6.0, "#c8a03a",
                       branching="unbranched"),
    "Calla":         F("spike", "radial", "oval", 1, 40, 5.0, "#e8e0c0",
                       branching="unbranched", rosette=1),
    "Acorus":        F("spike", "radial", "narrow", 0, 100, 0.2, "",
                       branching="unbranched"),
    "Hippuris":      F("whorl", "radial", "narrow", 0, 8, 0.2, "",
                       branching="unbranched"),
    "Myriophyllum":  F("spike", "radial", "narrow", 4, 30, 0.2, "",
                       branching="unbranched"),
    "Utricularia":   F("raceme", "bilateral", "lipped", 5, 8, 1.0, "",
                       branching="unbranched"),
    "Sparganium":    F("head", "radial", "narrow", 0, 40, 1.5, "",
                       branching="branched_above"),
    "Elodea":        F("solitary", "radial", "narrow", 3, 1, 0.8, "",
                       branching="unbranched"),
    "Lemna":         F("solitary", "radial", "narrow", 0, 1, 0.1, "",
                       branching="unbranched"),
    "Stuckenia":     F("spike", "radial", "narrow", 0, 20, 0.2, "",
                       branching="unbranched"),
}

# Where one genus is not one flower.
SPECIES_OVERRIDE = {
    # Pussytoes are dioecious mats; the pearly everlasting is a tall branched
    # plant with a much bigger corymb.
    "Anaphalis margaritacea": F("corymb", "radial", "tubular", 0, 60, 0.9,
                                "#e8c552", branching="branched_above"),
    # Prairie sage is grown for its foliage: the heads are nodding and green,
    # and drawing them as a bloom over-sells a plant nobody plants for flowers.
    "Artemisia ludoviciana": F("panicle", "radial", "tubular", 0, 10, 0.25,
                               "#b7bc86", branching="unbranched"),
    # The sunflowers split hard on architecture: the annual holds ONE big head,
    # Maximilian's and the Jerusalem artichoke carry many up a branched stem.
    "Helianthus annuus": F("solitary", "radial", "oval", 22, 200, 14.0,
                           "#5a3a12", branching="unbranched"),
    # Wild bergamot's head is the classic ragged crown; horsemint is denser.
    "Monarda fistulosa": F("head", "bilateral", "lipped", 5, 28, 3.2, "#b06a9a",
                           branching="branched_above"),
    # Three-flowered avens is famous for its NODDING trio of closed bells, not
    # for an open five-petalled rose flower.
    "Geum triflorum": F("cyme", "radial", "oval", 5, 3, 1.4, "#a05a4a",
                        branching="unbranched", rosette=1),
    # Prairie crocus opens before its leaves, held alone on a hairy scape.
    "Pulsatilla nuttalliana": F("solitary", "radial", "oval", 6, 1, 6.5,
                                "#e8c552", branching="unbranched", rosette=1),
    # Nodding onion is the one that nods; the others hold their umbels up.
    "Allium cernuum": F("umbel", "radial", "oval", 6, 40, 0.7, "",
                        branching="unbranched", rosette=1),
    # Blanketflower's rays are three-lobed at the tip and banded — the notch is
    # the field mark, and it is a much bigger head than the genus default.
    "Gaillardia aristata": F("head", "radial", "notched", 13, 90, 7.0,
                             "#7d2b1c", branching="branched_above", rosette=1),
}


def flower_for(rec):
    """The recorded flower for one catalogue record, or None."""
    sci = (rec.get("scientific_name") or "").strip()
    if sci in SPECIES_OVERRIDE:
        return SPECIES_OVERRIDE[sci]
    return GENUS.get(sci.split(" ")[0])


# Species with no flower to draw at all. Graminoids have their own field
# (inflorescence_form, v52) and conifers do not flower; both are skipped rather
# than described, because inventing a bloom is worse than drawing none.
_SKIP_TYPES = ("grass", "sedge", "rush")


def _flowers(rec):
    if rec.get("plant_type") in _SKIP_TYPES:
        return False
    # A species with a seed head already has its own drawing (v52), and the
    # viewer prefers it over flower_form. Five graminoids are filed under
    # `aquatic` rather than `sedge`/`rush` in the catalogue, so the plant_type
    # test above does not catch them — this does.
    if rec.get("inflorescence_form"):
        return False
    return (rec.get("flower_form") or "none") != "none"


def apply(records, check=False):
    applied, uncovered = 0, []
    for rec in records:
        if not _flowers(rec):
            continue
        flower = flower_for(rec)
        if flower is None:
            uncovered.append(rec.get("scientific_name") or rec.get("common_name"))
            continue
        if not check:
            rec.update(flower)
        applied += 1
    return applied, uncovered


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true",
                    help="report coverage without writing")
    args = ap.parse_args()

    bad = []
    for key, f in list(GENUS.items()) + list(SPECIES_OVERRIDE.items()):
        if f["flower_arch"] not in ARCHITECTURES:
            bad.append((key, "arch", f["flower_arch"]))
        if f["flower_symmetry"] not in SYMMETRIES:
            bad.append((key, "symmetry", f["flower_symmetry"]))
        if f["petal_shape"] not in PETAL_SHAPES:
            bad.append((key, "petal_shape", f["petal_shape"]))
        if f["stem_branching"] not in BRANCHINGS:
            bad.append((key, "branching", f["stem_branching"]))
    if bad:
        print("values outside the vocabulary:", bad)
        return 1

    with open(_MASTER, encoding="utf-8") as fh:
        records = json.load(fh)
    total = sum(1 for r in records if _flowers(r))
    applied, uncovered = apply(records, check=args.check)

    if uncovered:
        print(f"flowering species still without a described flower "
              f"({len(uncovered)}) — these keep the billboard:")
        for name in sorted(uncovered):
            print("   ", name)

    pct = 100.0 * applied / max(1, total)
    if args.check:
        print(f"check: {applied} of {total} flowering species covered ({pct:.0f}%)")
        return 0

    with open(_MASTER, "w", encoding="utf-8") as fh:
        json.dump(records, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    print(f"wrote {_MASTER}: {applied} of {total} flowering species "
          f"({pct:.0f}%) have a described flower")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

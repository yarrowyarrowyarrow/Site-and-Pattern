"""Author the botanical-morphology fields for the NON-WOODY species in
data/plants_master.json (V2.29, schema v48). Idempotent — re-running rewrites
the same values, so this file is both the tool and the provenance record.

    python scripts/seed_non_woody_morphology.py [--check]

Companion to scripts/seed_woody_morphology.py, which covers the 69 trees and
shrubs. Between them every one of the catalogue's 434 species has morphology.

WHY THIS EXISTS
211 of the 434 species are wildflowers — the app's main subject — and until now
every one of them had `leaf_shape` and `leaf_size_cm` empty. Their entire
geometric identity in 3D was one of seven archetype forms, chosen by a hardcoded
genus table in the viewer (`_HPROF`, html/scene3d/03-herbs.js). That table names
65 genera and covers 147 of the 211; the other **64 fell through to a guess based
on flower shape and aspect ratio**, and two thirds of those collapsed onto one
generic bushy `clump`. Prairie Crocus and Shooting Star (basal rosettes), Glacier
Lily and Yellowbells (strap-leaved), Prairie Sagewort (a fine silver mound) and
Yellow Lady's Slipper were all drawn as the same bush.

FIELDS
  leaf_shape        blade outline; drives the leaf profile the builders stamp.
  leaf_size_cm      typical mature blade length. The renderer converts it to the
                    unit frame against the plant's height, so a 30 cm balsamroot
                    leaf and a 1 cm moss-campion leaf differ on screen in the
                    same ratio they do in a meadow.
  leaf_arrangement  alternate / opposite / whorled / basal — where leaves sit on
                    the stem, which the builders use to place them in pairs,
                    rings, spirals or a ground rosette.
  growth_form       the plant's habit, and now the SOURCE OF TRUTH for which 3D
                    archetype it gets. `_HPROF` becomes a fallback for anything
                    this file does not name.

`bark_color`, `fall_color` and `branching` are left empty on purpose: they are
woody characters, and an honest empty beats an invented value (the V2.29
precedent — an empty `fall_color` already means "evergreen or does not colour up",
never "unknown, so guess brown").

AUTHORED PER GENUS
These characters are genus-consistent in descriptive botany, which is why floras
key them at that level, so the table below is keyed by genus with a small
SPECIES_OVERRIDE for the species that genuinely depart from their relatives.
201 genera cover all 365 non-woody rows. Claiming per-species precision for 365
rows would be a false claim to a resolution the sources do not carry (P9).

SOURCING
As with the woody set: standard, non-controversial descriptive characters for
well-described regional species, recorded as TYPICAL values, mid-range where
sources give a range. The reference frame is the general botanical literature for
the prairie provinces and boreal Canada catalogued in docs/REFERENCES.md.

NOTHING HERE IS INDIGENOUS KNOWLEDGE (P12). Morphological descriptors only — no
traditional use, name, management practice or relationship is encoded. Several
species in this list carry such knowledge; none of it appears here.
"""

import argparse
import json
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_MASTER = os.path.join(_ROOT, "data", "plants_master.json")

NON_WOODY_TYPES = ("wildflower", "herb", "fern", "grass", "sedge", "rush",
                   "aquatic", "groundcover", "vine")

# genus -> (leaf_shape, leaf_size_cm, leaf_arrangement, growth_form)
GENUS = {
    # ── forbs: ferny / finely divided ────────────────────────────────────────
    "Achillea":       ("bipinnate", 8.0, "alternate", "ferny"),
    "Anemone":        ("lobed", 8.0, "whorled", "ferny"),
    "Aquilegia":      ("compound_pinnate", 6.0, "basal", "ferny"),
    "Capnoides":      ("compound_pinnate", 10.0, "alternate", "ferny"),
    "Osmorhiza":      ("compound_pinnate", 15.0, "alternate", "ferny"),
    "Polemonium":     ("compound_pinnate", 12.0, "alternate", "ferny"),
    "Thalictrum":     ("compound_pinnate", 5.0, "alternate", "ferny"),
    "Artemisia":      ("pinnatifid", 5.0, "alternate", "ferny"),

    # ── forbs: basal rosettes ───────────────────────────────────────────────
    "Agoseris":       ("lanceolate", 15.0, "basal", "rosette"),
    "Androsace":      ("spatulate", 1.5, "basal", "rosette"),
    "Arnica":         ("ovate", 10.0, "opposite", "rosette"),
    "Aster":          ("spatulate", 5.0, "alternate", "rosette"),
    "Balsamorhiza":   ("sagittate", 30.0, "basal", "rosette"),
    "Bistorta":       ("lanceolate", 10.0, "basal", "rosette"),
    "Caltha":         ("reniform", 10.0, "basal", "rosette"),
    "Cirsium":        ("pinnatifid", 20.0, "alternate", "rosette"),
    "Dodecatheon":    ("spatulate", 15.0, "basal", "rosette"),
    "Draba":          ("spatulate", 2.0, "basal", "rosette"),
    "Drosera":        ("orbicular", 1.0, "basal", "rosette"),
    "Echinacea":      ("lanceolate", 15.0, "alternate", "rosette"),
    "Erigeron":       ("spatulate", 8.0, "basal", "rosette"),
    "Gaillardia":     ("lanceolate", 10.0, "alternate", "rosette"),
    "Geum":           ("compound_pinnate", 15.0, "basal", "rosette"),
    "Heuchera":       ("lobed", 8.0, "basal", "rosette"),
    "Hieracium":      ("lanceolate", 10.0, "alternate", "rosette"),
    "Mitella":        ("cordate", 5.0, "basal", "rosette"),
    "Oenothera":      ("lanceolate", 12.0, "basal", "rosette"),
    "Oxytropis":      ("compound_pinnate", 10.0, "basal", "rosette"),
    "Packera":        ("spatulate", 6.0, "basal", "rosette"),
    "Petasites":      ("lobed", 20.0, "basal", "rosette"),
    "Physaria":       ("spatulate", 4.0, "basal", "rosette"),
    "Primula":        ("spatulate", 12.0, "basal", "rosette"),
    "Pulsatilla":     ("pinnatifid", 8.0, "basal", "rosette"),
    "Pyrola":         ("orbicular", 4.0, "basal", "rosette"),
    "Ranunculus":     ("lobed", 5.0, "basal", "rosette"),
    "Townsendia":     ("spatulate", 3.0, "basal", "rosette"),
    "Viola":          ("reniform", 5.0, "basal", "rosette"),

    # ── forbs: tall leafy stems ─────────────────────────────────────────────
    "Agastache":      ("ovate", 7.0, "opposite", "erect"),
    "Agrimonia":      ("compound_pinnate", 12.0, "alternate", "erect"),
    "Anaphalis":      ("lanceolate", 8.0, "alternate", "erect"),
    "Angelica":       ("compound_pinnate", 30.0, "alternate", "erect"),
    "Apocynum":       ("ovate", 8.0, "opposite", "erect"),
    "Astragalus":     ("compound_pinnate", 10.0, "alternate", "erect"),
    "Blitum":         ("sagittate", 8.0, "alternate", "erect"),
    "Castilleja":     ("linear", 6.0, "alternate", "erect"),
    "Chamaenerion":   ("lanceolate", 15.0, "alternate", "erect"),
    "Comandra":       ("lanceolate", 3.0, "alternate", "erect"),
    "Comarum":        ("compound_pinnate", 12.0, "alternate", "erect"),
    "Coreopsis":      ("lanceolate", 8.0, "opposite", "erect"),
    "Dalea":          ("compound_pinnate", 4.0, "alternate", "erect"),
    "Delphinium":     ("lobed", 12.0, "alternate", "erect"),
    "Euthamia":       ("linear", 8.0, "alternate", "erect"),
    "Eutrochium":     ("lanceolate", 20.0, "whorled", "erect"),
    "Gentiana":       ("ovate", 4.0, "opposite", "erect"),
    "Gentianella":    ("lanceolate", 3.0, "opposite", "erect"),
    "Glycyrrhiza":    ("compound_pinnate", 15.0, "alternate", "erect"),
    "Hedysarum":      ("compound_pinnate", 12.0, "alternate", "erect"),
    "Helenium":       ("lanceolate", 10.0, "alternate", "erect"),
    "Iliamna":        ("lobed", 15.0, "alternate", "erect"),
    "Liatris":        ("linear", 20.0, "alternate", "erect"),
    "Linum":          ("linear", 2.5, "alternate", "erect"),
    "Lithospermum":   ("lanceolate", 6.0, "alternate", "erect"),
    "Lupinus":        ("compound_palmate", 10.0, "alternate", "erect"),
    "Lysimachia":     ("lanceolate", 10.0, "opposite", "erect"),
    "Maianthemum":    ("ovate", 12.0, "alternate", "erect"),
    "Mentha":         ("ovate", 5.0, "opposite", "erect"),
    "Oligoneuron":    ("elliptic", 12.0, "alternate", "erect"),
    "Orthocarpus":    ("linear", 4.0, "alternate", "erect"),
    "Pedicularis":    ("pinnatifid", 10.0, "alternate", "erect"),
    "Pediomelum":     ("compound_palmate", 6.0, "alternate", "erect"),
    "Penstemon":      ("lanceolate", 8.0, "opposite", "erect"),
    "Peritoma":       ("compound_palmate", 6.0, "alternate", "erect"),
    "Persicaria":     ("lanceolate", 12.0, "alternate", "erect"),
    "Physostegia":    ("lanceolate", 10.0, "opposite", "erect"),
    "Polygala":       ("lanceolate", 4.0, "alternate", "erect"),
    "Ratibida":       ("pinnatifid", 12.0, "alternate", "erect"),
    "Rhinanthus":     ("lanceolate", 4.0, "opposite", "erect"),
    "Scutellaria":    ("lanceolate", 4.0, "opposite", "erect"),
    "Solidago":       ("lanceolate", 10.0, "alternate", "erect"),
    "Spiranthes":     ("linear", 12.0, "basal", "grassy"),
    "Stachys":        ("lanceolate", 8.0, "opposite", "erect"),
    "Thermopsis":     ("trifoliate", 6.0, "alternate", "erect"),
    "Urtica":         ("ovate", 12.0, "opposite", "erect"),
    "Zizia":          ("compound_pinnate", 12.0, "alternate", "erect"),

    # ── forbs: bushy leafy clumps ───────────────────────────────────────────
    "Actaea":         ("compound_pinnate", 25.0, "alternate", "clump"),
    "Anemonastrum":   ("lobed", 8.0, "whorled", "clump"),
    "Aralia":         ("compound_pinnate", 30.0, "basal", "clump"),
    "Asclepias":      ("elliptic", 15.0, "opposite", "clump"),
    "Canadanthus":    ("lanceolate", 10.0, "alternate", "clump"),
    "Cypripedium":    ("elliptic", 15.0, "alternate", "clump"),
    "Dieteria":       ("lanceolate", 6.0, "alternate", "clump"),
    "Doellingeria":   ("lanceolate", 10.0, "alternate", "clump"),
    "Drymocallis":    ("compound_pinnate", 12.0, "alternate", "clump"),
    "Erythranthe":    ("ovate", 5.0, "opposite", "clump"),
    "Eurybia":        ("ovate", 12.0, "alternate", "clump"),
    "Geranium":       ("lobed", 10.0, "opposite", "clump"),
    "Grindelia":      ("lanceolate", 5.0, "alternate", "clump"),
    "Helianthus":     ("ovate", 20.0, "opposite", "clump"),
    "Heterotheca":    ("lanceolate", 5.0, "alternate", "clump"),
    "Mertensia":      ("ovate", 12.0, "alternate", "clump"),
    "Mimulus":        ("ovate", 7.0, "opposite", "clump"),
    "Monarda":        ("lanceolate", 8.0, "opposite", "clump"),
    "Phacelia":       ("pinnatifid", 8.0, "alternate", "clump"),
    "Prosartes":      ("ovate", 8.0, "alternate", "clump"),
    "Rudbeckia":      ("lanceolate", 12.0, "alternate", "clump"),
    "Sphaeralcea":    ("lobed", 5.0, "alternate", "clump"),
    "Symphyotrichum": ("lanceolate", 8.0, "alternate", "clump"),
    "Valeriana":      ("compound_pinnate", 15.0, "opposite", "clump"),

    # ── forbs: strap / grass-like basal leaves ──────────────────────────────
    "Allium":         ("linear", 25.0, "basal", "grassy"),
    "Anticlea":       ("linear", 30.0, "basal", "grassy"),
    "Calla":          ("cordate", 12.0, "basal", "emergent"),
    "Campanula":      ("linear", 4.0, "alternate", "grassy"),
    "Claytonia":      ("linear", 8.0, "opposite", "grassy"),
    "Erythronium":    ("lanceolate", 20.0, "basal", "grassy"),
    "Fritillaria":    ("linear", 12.0, "alternate", "grassy"),
    "Iris":           ("linear", 45.0, "basal", "grassy"),
    "Lilium":         ("lanceolate", 8.0, "whorled", "grassy"),
    "Sisyrinchium":   ("linear", 20.0, "basal", "grassy"),

    # ── forbs: mats, cushions and succulents ────────────────────────────────
    "Antennaria":     ("spatulate", 3.0, "basal", "mat"),
    "Cerastium":      ("lanceolate", 2.0, "opposite", "mat"),
    "Eriogonum":      ("spatulate", 3.0, "basal", "mat"),
    "Myosotis":       ("spatulate", 3.0, "alternate", "mat"),
    "Prunella":       ("ovate", 5.0, "opposite", "mat"),
    "Silene":         ("linear", 1.0, "opposite", "cushion"),
    "Phlox":          ("linear", 1.5, "opposite", "cushion"),
    "Escobaria":      ("scale", 0.5, "alternate", "succulent"),
    "Opuntia":        ("scale", 0.3, "alternate", "succulent"),
    "Rhodiola":       ("spatulate", 3.0, "alternate", "succulent"),
    "Sedum":          ("lanceolate", 2.0, "alternate", "succulent"),

    # ── groundcovers ────────────────────────────────────────────────────────
    "Arctostaphylos": ("obovate", 2.0, "alternate", "mat"),
    "Cornus":         ("ovate", 5.0, "whorled", "mat"),
    "Dryas":          ("elliptic", 2.0, "alternate", "mat"),
    "Fragaria":       ("trifoliate", 4.0, "basal", "mat"),
    "Galium":         ("linear", 3.0, "whorled", "sprawling"),
    "Juniperus":      ("awl", 0.8, "whorled", "mat"),
    "Linnaea":        ("orbicular", 1.5, "opposite", "mat"),
    "Potentilla":     ("compound_pinnate", 8.0, "alternate", "clump"),
    "Rubus":          ("trifoliate", 6.0, "alternate", "sprawling"),
    "Sibbaldia":      ("trifoliate", 2.0, "basal", "mat"),
    "Solanum":        ("lobed", 8.0, "alternate", "sprawling"),
    "Vaccinium":      ("elliptic", 1.0, "alternate", "mat"),
    "Veronica":       ("ovate", 5.0, "opposite", "sprawling"),

    # ── vines ───────────────────────────────────────────────────────────────
    "Clematis":       ("compound_pinnate", 8.0, "opposite", "vining"),
    "Lathyrus":       ("compound_pinnate", 10.0, "alternate", "vining"),
    "Lonicera":       ("elliptic", 8.0, "opposite", "vining"),
    "Vicia":          ("compound_pinnate", 8.0, "alternate", "vining"),

    # ── fern ────────────────────────────────────────────────────────────────
    "Matteuccia":     ("compound_pinnate", 90.0, "basal", "fern"),

    # ── aquatics / emergents / floating ─────────────────────────────────────
    "Acorus":         ("linear", 60.0, "basal", "emergent"),
    "Alisma":         ("ovate", 15.0, "basal", "emergent"),
    "Elodea":         ("linear", 1.5, "whorled", "floating"),
    "Equisetum":      ("scale", 1.0, "whorled", "emergent"),
    "Hippuris":       ("linear", 3.0, "whorled", "emergent"),
    "Lemna":          ("orbicular", 0.5, "basal", "floating"),
    "Menyanthes":     ("trifoliate", 8.0, "basal", "emergent"),
    "Myriophyllum":   ("pinnatifid", 3.0, "whorled", "floating"),
    "Nuphar":         ("cordate", 30.0, "basal", "floating"),
    "Sagittaria":     ("sagittate", 20.0, "basal", "emergent"),
    "Sium":           ("compound_pinnate", 20.0, "alternate", "emergent"),
    "Sparganium":     ("linear", 60.0, "alternate", "emergent"),
    "Stuckenia":      ("linear", 10.0, "alternate", "floating"),
    "Typha":          ("linear", 100.0, "basal", "emergent"),
    "Utricularia":    ("linear", 2.0, "alternate", "floating"),

    # ── graminoids: grasses, sedges, rushes ─────────────────────────────────
    # All linear-bladed basal tussocks; only blade length distinguishes them at
    # this scale, and that is exactly what the 3D tuft reads.
    "Agrostis":       ("linear", 15.0, "basal", "tussock"),
    "Andropogon":     ("linear", 40.0, "basal", "tussock"),
    "Anthoxanthum":   ("linear", 25.0, "basal", "tussock"),
    "Avenula":        ("linear", 20.0, "basal", "tussock"),
    "Beckmannia":     ("linear", 25.0, "basal", "tussock"),
    "Bolboschoenus":  ("linear", 60.0, "basal", "emergent"),
    "Bouteloua":      ("linear", 12.0, "basal", "tussock"),
    "Bromus":         ("linear", 25.0, "basal", "tussock"),
    "Calamagrostis":  ("linear", 30.0, "basal", "tussock"),
    "Calamovilfa":    ("linear", 30.0, "basal", "tussock"),
    "Carex":          ("linear", 30.0, "basal", "tussock"),
    "Cinna":          ("linear", 30.0, "basal", "tussock"),
    "Danthonia":      ("linear", 15.0, "basal", "tussock"),
    "Deschampsia":    ("linear", 20.0, "basal", "tussock"),
    "Distichlis":     ("linear", 10.0, "basal", "tussock"),
    "Eleocharis":     ("scale", 1.0, "basal", "tussock"),
    "Elymus":         ("linear", 25.0, "basal", "tussock"),
    "Eriocoma":       ("linear", 20.0, "basal", "tussock"),
    "Eriophorum":     ("linear", 25.0, "basal", "tussock"),
    "Festuca":        ("linear", 20.0, "basal", "tussock"),
    "Glyceria":       ("linear", 30.0, "basal", "tussock"),
    "Hesperostipa":   ("linear", 25.0, "basal", "tussock"),
    "Juncus":         ("linear", 30.0, "basal", "tussock"),
    "Koeleria":       ("linear", 15.0, "basal", "tussock"),
    "Leymus":         ("linear", 35.0, "basal", "tussock"),
    "Muhlenbergia":   ("linear", 15.0, "basal", "tussock"),
    "Nassella":       ("linear", 25.0, "basal", "tussock"),
    "Oryzopsis":      ("linear", 15.0, "basal", "tussock"),
    "Panicum":        ("linear", 40.0, "basal", "tussock"),
    "Pascopyrum":     ("linear", 20.0, "basal", "tussock"),
    "Piptatherum":    ("linear", 25.0, "basal", "tussock"),
    "Poa":            ("linear", 12.0, "basal", "tussock"),
    "Schizachne":     ("linear", 20.0, "basal", "tussock"),
    "Schizachyrium":  ("linear", 20.0, "basal", "tussock"),
    "Schoenoplectus": ("linear", 60.0, "basal", "emergent"),
    "Scirpus":        ("linear", 40.0, "basal", "tussock"),
    "Spartina":       ("linear", 40.0, "basal", "tussock"),
    "Sphenopholis":   ("linear", 20.0, "basal", "tussock"),
    "Sporobolus":     ("linear", 25.0, "basal", "tussock"),
}

# Species that genuinely depart from their genus's typical form.
SPECIES_OVERRIDE = {
    # A shrubby cactus-like succulent, not the mat its relatives make.
    "Escobaria vivipara":     ("scale", 0.5, "alternate", "succulent"),
    # Floating-leaved, unlike the marsh-marigold rosette.
    "Caltha natans":          ("reniform", 5.0, "basal", "floating"),
    # A creeping stoloniferous mat, unlike the upright cinquefoils.
    "Potentilla anserina":    ("compound_pinnate", 15.0, "basal", "mat"),
    # Leafless flowering scapes over a shallow rhizome.
    "Equisetum scirpoides":   ("scale", 0.5, "whorled", "mat"),
    # The tall shrubby wormwoods among otherwise low silver mounds.
    "Artemisia ludoviciana":  ("lanceolate", 8.0, "alternate", "erect"),
    # A climbing vine, unlike the bush honeysuckles.
    "Lonicera dioica":        ("elliptic", 8.0, "opposite", "vining"),
    # Rhizomatous colony former with broad basal blades.
    "Maianthemum canadense":  ("ovate", 8.0, "alternate", "mat"),
}

FIELDS = ("leaf_shape", "leaf_size_cm", "leaf_arrangement", "growth_form")


def apply(records, check=False):
    """Write morphology onto matching non-woody records.
    Returns (applied, uncovered_genera)."""
    applied, uncovered = 0, {}
    for rec in records:
        if rec.get("plant_type") not in NON_WOODY_TYPES:
            continue
        sci = (rec.get("scientific_name") or "").strip()
        row = SPECIES_OVERRIDE.get(sci) or GENUS.get(sci.split(" ")[0])
        if row is None:
            uncovered.setdefault(sci.split(" ")[0], []).append(rec["common_name"])
            continue
        if not check:
            for field, value in zip(FIELDS, row):
                rec[field] = value
        applied += 1
    return applied, uncovered


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true",
                    help="report coverage without writing")
    args = ap.parse_args()

    with open(_MASTER, encoding="utf-8") as fh:
        records = json.load(fh)
    total = sum(1 for r in records if r.get("plant_type") in NON_WOODY_TYPES)
    applied, uncovered = apply(records, check=args.check)

    if uncovered:
        print(f"genera with no morphology ({len(uncovered)}):")
        for genus, names in sorted(uncovered.items()):
            print(f"    {genus}: {', '.join(names[:3])}")
    stale = sorted(set(GENUS) - {(r.get("scientific_name") or "").split(" ")[0]
                                 for r in records})
    if stale:
        print(f"table rows matching no species (renamed?): {', '.join(stale)}")

    if args.check:
        print(f"check: {applied}/{total} non-woody species covered")
        return 1 if (uncovered or stale) else 0

    with open(_MASTER, "w", encoding="utf-8") as fh:
        json.dump(records, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    print(f"wrote {_MASTER}: {applied}/{total} non-woody species")
    return 0


if __name__ == "__main__":
    sys.exit(main())

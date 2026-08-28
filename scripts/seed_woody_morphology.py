"""Author the botanical-morphology fields for the woody species in
data/plants_master.json (V2.29). Idempotent — re-running rewrites the same
values, so this file is both the tool and the provenance record for them.

    python scripts/seed_woody_morphology.py [--check]

WHY THESE FIELDS EXIST
The 3D archetypes are keyed by archetype, never by species (P9), with species
identity carried by per-instance parameters. That was fine until the ask became
"make the models faithfully represent the native species" — at which point the
binding constraint turned out to be *data*, not art: the seed file recorded a
plant's height, spread, flower and fruit, and nothing whatsoever about what it
looks like. There was no honest way to draw a bur oak's coarse foliage
differently from an aspen's fine one, because nothing said their leaves are
20 cm and 6 cm.

Each field is here because a renderer consumes it:

  leaf_size_cm      typical mature blade length (needle length for conifers).
                    Sets foliage-mass granularity in REAL METRES, so a bur oak
                    reads coarse and a dwarf birch fine at the same crown size.
  leaf_shape        the blade outline. Drives foliage-mass proportions — a
                    compound or linear-leaved shrub carries open airy masses, a
                    cordate or lobed one dense round ones.
  leaf_arrangement  alternate / opposite / whorled / fascicled / basal. Drives
                    how masses sit on a twig (paired vs staggered).
  bark_color        the trunk and stem colour, replacing a hard-coded per-genus
                    table in the viewer. This is why red-osier dogwood is red
                    and aspen is chalky green-white.
  fall_color        autumn foliage. Empty for evergreens and for the greys that
                    do not coloUr up — an honest empty, not a guessed brown.
  branching         excurrent (one leader) / decurrent (spreading crown) /
                    multi_stem / suckering / arching / prostrate / rosette.
                    The silhouette character above and beyond the aspect ratio.

SOURCING (P9)
These are standard, non-controversial descriptive characters for well-described
regional species — the kind of thing every flora of the northern Great Plains
and boreal forest agrees on. They are recorded as TYPICAL values for the
species, not measurements of any individual, and the app presents them that way.
The reference frame is the general botanical literature for the prairie
provinces and boreal Canada catalogued in docs/REFERENCES.md; where sources give
a range (leaf length especially), the value here is the mid-range figure.
Colours are representative renderings of the described bark and autumn colour,
chosen for the 3D palette — they are an interpretation, and are deliberately
kept out of anything that scores or recommends.

NOTHING HERE IS INDIGENOUS KNOWLEDGE (P12). These are morphological descriptors
only: no traditional use, name, management practice or relationship is encoded.
"""

import argparse
import json
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_MASTER = os.path.join(_ROOT, "data", "plants_master.json")

# scientific_name -> (leaf_shape, leaf_size_cm, leaf_arrangement,
#                     bark_color, fall_color, branching)
MORPHOLOGY = {
    # ── trees ────────────────────────────────────────────────────────────────
    "Abies balsamea":        ("needle", 2.0, "alternate", "#8a8d86", "", "excurrent"),
    "Betula occidentalis":   ("ovate", 4.0, "alternate", "#6b4230", "#e8c34a", "multi_stem"),
    "Betula papyrifera":     ("ovate", 8.0, "alternate", "#e8e4d8", "#edc84e", "excurrent"),
    "Larix laricina":        ("needle", 2.5, "fascicled", "#7a5238", "#d9a72e", "excurrent"),
    "Picea glauca":          ("needle", 1.8, "alternate", "#7b7268", "", "excurrent"),
    "Picea mariana":         ("needle", 1.2, "alternate", "#6b6258", "", "excurrent"),
    "Pinus banksiana":       ("needle", 3.0, "fascicled", "#6f6154", "", "decurrent"),
    "Pinus contorta":        ("needle", 5.0, "fascicled", "#8a6a4a", "", "excurrent"),
    "Populus balsamifera":   ("ovate", 10.0, "alternate", "#7d7a70", "#d8b83e", "excurrent"),
    "Populus tremuloides":   ("orbicular", 6.0, "alternate", "#cfd2c4", "#e8c33a", "excurrent"),
    "Prunus pensylvanica":   ("lanceolate", 8.0, "alternate", "#7a4630", "#d9622e", "decurrent"),
    "Pseudotsuga menziesii": ("needle", 2.5, "alternate", "#6a4a34", "", "excurrent"),
    "Quercus macrocarpa":    ("lobed", 20.0, "alternate", "#5f584c", "#a8823a", "decurrent"),
    "Salix bebbiana":        ("elliptic", 6.0, "alternate", "#7a7264", "#d3c04a", "multi_stem"),

    # ── shrubs ───────────────────────────────────────────────────────────────
    "Acer glabrum":            ("lobed", 8.0, "opposite", "#6e6258", "#d1502e", "multi_stem"),
    "Alnus alnobetula":        ("ovate", 8.0, "alternate", "#6f6a60", "#9a8a3e", "multi_stem"),
    "Alnus incana":            ("ovate", 9.0, "alternate", "#6f6a60", "#9a8a3e", "multi_stem"),
    "Amelanchier alnifolia":   ("obovate", 5.0, "alternate", "#7d7a72", "#d1762e", "multi_stem"),
    "Artemisia cana":          ("linear", 4.0, "alternate", "#7a7060", "", "decurrent"),
    "Artemisia tridentata":    ("lobed", 3.0, "alternate", "#7a7060", "", "decurrent"),
    "Betula glandulosa":       ("orbicular", 2.0, "alternate", "#5f4a3a", "#d8a83c", "multi_stem"),
    "Cornus sericea":          ("ovate", 9.0, "opposite", "#b5402e", "#a83c2e", "multi_stem"),
    "Corylus cornuta":         ("ovate", 9.0, "alternate", "#786a58", "#d0a83c", "multi_stem"),
    "Crataegus douglasii":     ("obovate", 6.0, "alternate", "#6f665a", "#c07a34", "multi_stem"),
    "Dasiphora fruticosa":     ("compound_pinnate", 2.0, "alternate", "#8a6a52", "#c8b04a", "decurrent"),
    "Elaeagnus commutata":     ("elliptic", 5.0, "alternate", "#7a5a42", "#b7ab7c", "suckering"),
    "Endotropis alnifolia":    ("elliptic", 7.0, "alternate", "#6e6458", "#c8a842", "decurrent"),
    "Ericameria nauseosa":     ("linear", 5.0, "alternate", "#9aa08c", "", "decurrent"),
    "Gutierrezia sarothrae":   ("linear", 3.0, "alternate", "#7a6a52", "", "decurrent"),
    "Juniperus communis":      ("awl", 1.2, "whorled", "#7a5a44", "", "prostrate"),
    "Krascheninnikovia lanata": ("linear", 3.0, "alternate", "#a8a290", "", "decurrent"),
    "Ledum groenlandicum":     ("elliptic", 4.0, "alternate", "#6e5a44", "", "decurrent"),
    "Lonicera involucrata":    ("ovate", 10.0, "opposite", "#75695a", "#cbb44a", "multi_stem"),
    "Mahonia repens":          ("compound_pinnate", 8.0, "alternate", "#6a5a48", "#a8402e", "prostrate"),
    "Paxistima myrsinites":    ("elliptic", 2.0, "opposite", "#6a5a48", "", "prostrate"),
    "Prunus virginiana":       ("obovate", 8.0, "alternate", "#6f6252", "#d0932e", "multi_stem"),
    "Rhus aromatica":          ("trifoliate", 6.0, "alternate", "#6e5c46", "#c5442a", "decurrent"),
    "Ribes americanum":        ("lobed", 7.0, "alternate", "#6e6254", "#c8703a", "multi_stem"),
    "Ribes aureum":            ("lobed", 5.0, "alternate", "#7a5a42", "#c8503a", "multi_stem"),
    "Ribes glandulosum":       ("lobed", 5.0, "alternate", "#6a5c4a", "#c07a3a", "arching"),
    "Ribes hudsonianum":       ("lobed", 8.0, "alternate", "#6e6254", "#c8853a", "multi_stem"),
    "Ribes lacustre":          ("lobed", 4.0, "alternate", "#6a5644", "#b8703a", "multi_stem"),
    "Ribes oxyacanthoides":    ("lobed", 4.0, "alternate", "#75695c", "#c08a3a", "arching"),
    "Ribes triste":            ("lobed", 6.0, "alternate", "#6a5c4a", "#c05a3a", "arching"),
    "Rosa acicularis":         ("compound_pinnate", 8.0, "alternate", "#8a5442", "#c07a3a", "multi_stem"),
    "Rosa arkansana":          ("compound_pinnate", 7.0, "alternate", "#8a5442", "#c07a3a", "multi_stem"),
    "Rosa woodsii":            ("compound_pinnate", 7.0, "alternate", "#85604a", "#c07a3a", "suckering"),
    "Rubus idaeus":            ("compound_pinnate", 8.0, "alternate", "#9a8a72", "#c08a3a", "arching"),
    "Rubus parviflorus":       ("lobed", 15.0, "alternate", "#9a8a72", "#c8a03a", "arching"),
    "Salix brachycarpa":       ("elliptic", 3.0, "alternate", "#7d7466", "#cbbb50", "multi_stem"),
    "Salix discolor":          ("elliptic", 8.0, "alternate", "#75695c", "#cbbb50", "multi_stem"),
    "Salix exigua":            ("linear", 10.0, "alternate", "#7d7466", "#cbbb50", "suckering"),
    "Salix interior":          ("linear", 12.0, "alternate", "#7d7466", "#cbbb50", "suckering"),
    "Salix petiolaris":        ("lanceolate", 7.0, "alternate", "#7d7466", "#cbbb50", "multi_stem"),
    "Shepherdia argentea":     ("elliptic", 4.0, "opposite", "#8a8578", "#b0aa8c", "multi_stem"),
    "Shepherdia canadensis":   ("ovate", 4.0, "opposite", "#7a7264", "#a89e80", "decurrent"),
    "Sorbus scopulina":        ("compound_pinnate", 18.0, "alternate", "#7d7a72", "#d05a2e", "multi_stem"),
    "Spiraea alba":            ("lanceolate", 6.0, "alternate", "#6e5f4c", "#c8a03a", "multi_stem"),
    "Spiraea alba var. latifolia": ("lanceolate", 6.0, "alternate", "#6e5f4c", "#c8a03a", "multi_stem"),
    "Spiraea betulifolia":     ("ovate", 4.0, "alternate", "#6e5f4c", "#c8703a", "multi_stem"),
    "Symphoricarpos albus":    ("ovate", 4.0, "opposite", "#75695c", "#b8a860", "multi_stem"),
    "Symphoricarpos occidentalis": ("ovate", 5.0, "opposite", "#75695c", "#b8a860", "suckering"),
    "Vaccinium myrtilloides":  ("elliptic", 3.0, "alternate", "#6a5a48", "#b5402e", "decurrent"),
    "Vaccinium myrtillus":     ("ovate", 2.0, "alternate", "#6e6a4a", "#b5402e", "decurrent"),
    "Vaccinium uliginosum":    ("obovate", 2.5, "alternate", "#6a5a48", "#b0402e", "decurrent"),
    "Viburnum edule":          ("lobed", 8.0, "opposite", "#75695c", "#c04a2e", "multi_stem"),
    "Viburnum opulus":         ("lobed", 10.0, "opposite", "#75695c", "#b8402e", "multi_stem"),
    "Yucca glauca":            ("linear", 50.0, "basal", "#8a8570", "", "rosette"),
}

FIELDS = ("leaf_shape", "leaf_size_cm", "leaf_arrangement",
          "bark_color", "fall_color", "branching")


def apply(records, check=False):
    """Write the morphology onto matching records; return (applied, missing)."""
    applied, seen = 0, set()
    for rec in records:
        sci = (rec.get("scientific_name") or "").strip()
        row = MORPHOLOGY.get(sci)
        if row is None:
            continue
        seen.add(sci)
        if not check:
            for field, value in zip(FIELDS, row):
                rec[field] = value
        applied += 1
    missing = sorted(set(MORPHOLOGY) - seen)
    return applied, missing


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true",
                    help="report coverage without writing")
    args = ap.parse_args()

    with open(_MASTER, encoding="utf-8") as fh:
        records = json.load(fh)
    woody = [r for r in records if r.get("plant_type") in ("tree", "shrub")]
    applied, missing = apply(records, check=args.check)

    if missing:
        print("morphology rows with no matching species (renamed?):")
        for name in missing:
            print("   ", name)
    uncovered = [r["common_name"] for r in woody
                 if (r.get("scientific_name") or "").strip() not in MORPHOLOGY]
    if uncovered:
        print(f"woody species still without morphology ({len(uncovered)}):")
        for name in uncovered:
            print("   ", name)

    if args.check:
        print(f"check: {applied}/{len(woody)} woody species covered")
        return 1 if (missing or uncovered) else 0

    with open(_MASTER, "w", encoding="utf-8") as fh:
        json.dump(records, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    print(f"wrote {_MASTER}: {applied}/{len(woody)} woody species")
    return 0


if __name__ == "__main__":
    sys.exit(main())

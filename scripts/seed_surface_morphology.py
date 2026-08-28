"""Author the ``bark_texture`` and ``leaf_surface`` fields in
data/plants_master.json (V2.33, schema v52). Idempotent — re-running rewrites
the same values, so this file is both the tool and the provenance record.

    python scripts/seed_surface_morphology.py [--check]

WHY THESE FIELDS EXIST
Every surface in the 3D viewer was one of two procedural patterns: a generic
vertical bark fissure and a generic foliage mottle. So a paper birch and a bur
oak had the same bark, and a glossy red-osier dogwood, a silvery wolf-willow and
a waxy blue bog blueberry had the same leaf. Bark and leaf surface are among the
first things a person actually uses to identify a woody plant in winter or out
of flower — a birch is *recognised by its bark* — so drawing one grain for all
of them is the same class of false-sameness the fruit sprites had before v49
(P5: make the invisible visible; P9: no false precision, but no false SAMENESS
either).

They are data fields rather than genus tables in the viewer for the same reason
``flower_form`` and ``fruit_form`` are: the renderer should read the catalogue,
not re-encode botany in JavaScript. Where a species is not listed here the
viewer falls back to a per-genus default and then to a neutral grain, which is
an honest empty rather than an invented measurement.

THE BARK CLASSES — what you can name at ten paces, which is the granularity a
legible stylised model can carry and the seed data can honestly support.
  smooth    Unbroken or nearly so, its character in lenticels and branch scars:
            aspen, young cherry, saskatoon, alder, willow whips, dogwood canes.
  furrowed  Deep vertical fissures with ridges between: bur oak, mature balsam
            poplar, Douglas-fir, old Bebb's willow.
  papery    Horizontal peeling bands with dark lenticel dashes — paper birch,
            and in this catalogue only paper birch. Note that dwarf birch and
            water birch do NOT peel, which is exactly the kind of within-genus
            difference a genus table cannot express.
  shaggy    Fibrous strips lifting away from the stem: juniper, silverberry,
            sagebrush, shrubby cinquefoil, currant and raspberry canes,
            snowberry, honeysuckle.
  scaly     Irregular plates with dark gaps: spruce, pine, tamarack, hawthorn.

THE LEAF SURFACES
  matte      The default; no entry needed.
  glossy     Shining upper surface: Oregon-grape, red-osier dogwood, false box,
            bearberry, wintergreen, marsh marigold.
  pubescent  Hairy, downy or woolly, which reads as PALER and softer: wolf-
            willow, buffaloberry, sagebrush, pussytoes, pearly everlasting,
            velvet-leaf blueberry, woolly cinquefoil, silky lupine.
  glaucous   A waxy blue-white bloom: sandbar and narrow-leaf willow, bog
            blueberry, soapweed yucca (glauca is the epithet), white spruce,
            meadow-rue, columbine, stonecrop.

SOURCING (P9)
These are standard descriptive characters for well-described regional species —
bark type and leaf indumentum are among the least contested things in a flora,
and several species are *named* for the character recorded here (Elaeagnus
commutata "silverberry", Vaccinium myrtilloides "velvet-leaf", Yucca glauca,
Artemisia cana, Lupinus sericeus, Shepherdia argentea). Values are TYPICAL for a
mature plant, not measurements of an individual, and the reference frame is the
general botanical literature for the prairie provinces and boreal Canada
catalogued in docs/REFERENCES.md. Bark changes with age on several species —
balsam poplar and Bebb's willow are smooth when young and furrowed when old —
and the value recorded is the mature one, because that is what the archetype
draws.

This encodes no traditional, cultural or Indigenous knowledge of these plants —
only the botanical description of their surfaces (P12).
"""

from __future__ import annotations

import argparse
import json
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_MASTER = os.path.join(_ROOT, "data", "plants_master.json")

BARK_CLASSES = ("smooth", "furrowed", "papery", "shaggy", "scaly")
LEAF_SURFACES = ("matte", "glossy", "pubescent", "glaucous")

# scientific_name -> bark_texture. Woody species only; a yucca has no bark.
BARK_TEXTURE = {
    # conifers — plated, except the smooth resin-blistered firs
    "Abies balsamea": "smooth",
    "Picea glauca": "scaly",
    "Picea mariana": "scaly",
    "Pinus banksiana": "scaly",
    "Pinus contorta": "scaly",
    "Larix laricina": "scaly",
    "Pseudotsuga menziesii": "furrowed",
    "Juniperus communis": "shaggy",
    # broadleaf trees
    "Populus tremuloides": "smooth",       # chalky green-white, black scars
    "Populus balsamifera": "furrowed",     # mature; smooth only when young
    "Betula papyrifera": "papery",
    "Betula occidentalis": "smooth",       # reddish-brown, does NOT peel
    "Betula glandulosa": "smooth",
    "Quercus macrocarpa": "furrowed",
    "Salix bebbiana": "furrowed",          # mature; the shrub willows stay smooth
    "Prunus pensylvanica": "smooth",       # lenticel bands on red-brown
    "Prunus virginiana": "smooth",
    "Acer glabrum": "smooth",
    "Sorbus scopulina": "smooth",
    "Crataegus douglasii": "scaly",
    "Alnus alnobetula": "smooth",
    "Alnus incana": "smooth",
    "Corylus cornuta": "smooth",
    # shrubs
    "Amelanchier alnifolia": "smooth",     # grey with pale vertical striping
    "Cornus sericea": "smooth",            # the red cane is the whole point
    "Endotropis alnifolia": "smooth",
    "Mahonia repens": "smooth",
    "Paxistima myrsinites": "smooth",
    "Rhus aromatica": "smooth",
    "Shepherdia canadensis": "smooth",
    "Viburnum edule": "smooth",
    "Viburnum opulus": "smooth",
    "Vaccinium myrtilloides": "smooth",
    "Vaccinium myrtillus": "smooth",
    "Vaccinium uliginosum": "smooth",
    "Salix brachycarpa": "smooth",
    "Salix discolor": "smooth",
    "Salix exigua": "smooth",
    "Salix interior": "smooth",
    "Salix petiolaris": "smooth",
    "Rosa acicularis": "smooth",
    "Rosa arkansana": "smooth",
    "Rosa woodsii": "smooth",
    "Ribes glandulosum": "smooth",
    "Artemisia cana": "shaggy",
    "Artemisia tridentata": "shaggy",
    "Dasiphora fruticosa": "shaggy",       # shredding tan strips
    "Elaeagnus commutata": "shaggy",
    "Ericameria nauseosa": "shaggy",
    "Gutierrezia sarothrae": "shaggy",
    "Krascheninnikovia lanata": "shaggy",
    "Ledum groenlandicum": "shaggy",
    "Lonicera involucrata": "shaggy",
    "Ribes americanum": "shaggy",
    "Ribes aureum": "shaggy",
    "Ribes hudsonianum": "shaggy",
    "Ribes lacustre": "shaggy",
    "Ribes oxyacanthoides": "shaggy",
    "Ribes triste": "shaggy",
    "Rubus idaeus": "shaggy",              # peeling second-year canes
    "Rubus parviflorus": "shaggy",
    "Shepherdia argentea": "shaggy",
    "Spiraea alba": "shaggy",
    "Spiraea alba var. latifolia": "shaggy",
    "Spiraea betulifolia": "shaggy",
    "Symphoricarpos albus": "shaggy",
    "Symphoricarpos occidentalis": "shaggy",
}

# Catalogued as woody but carrying no bark to draw — recorded explicitly so the
# coverage check can tell a considered exclusion from a gap.
NO_BARK = {
    "Yucca glauca": "a basal rosette of stiff leaves on a caudex, not a stem",
}

# scientific_name -> leaf_surface. ONLY where the character is distinctive
# enough to be worth drawing; everything unlisted is matte, which is both the
# common case and the honest default.
LEAF_SURFACE = {
    # glossy
    "Mahonia repens": "glossy",
    "Paxistima myrsinites": "glossy",
    "Cornus sericea": "glossy",
    "Arctostaphylos uva-ursi": "glossy",
    "Vaccinium myrtillus": "glossy",
    "Rhus aromatica": "glossy",
    "Caltha palustris": "glossy",
    "Caltha natans": "glossy",
    "Pyrola asarifolia": "glossy",
    "Maianthemum canadense": "glossy",
    "Maianthemum stellatum": "glossy",
    "Maianthemum racemosum": "glossy",
    "Zizia aptera": "glossy",
    "Menyanthes trifoliata": "glossy",
    "Nuphar variegata": "glossy",
    "Sagittaria latifolia": "glossy",
    "Sagittaria cuneata": "glossy",
    "Linnaea borealis": "glossy",
    "Mitella nuda": "glossy",
    "Prosartes trachycarpa": "glossy",
    # pubescent — hairy, downy, woolly, scurfy; reads paler and softer
    "Elaeagnus commutata": "pubescent",
    "Shepherdia argentea": "pubescent",
    "Shepherdia canadensis": "pubescent",
    "Artemisia cana": "pubescent",
    "Artemisia tridentata": "pubescent",
    "Artemisia frigida": "pubescent",
    "Artemisia ludoviciana": "pubescent",
    "Artemisia campestris": "pubescent",
    "Krascheninnikovia lanata": "pubescent",
    "Ledum groenlandicum": "pubescent",
    "Vaccinium myrtilloides": "pubescent",
    "Ericameria nauseosa": "pubescent",
    "Anaphalis margaritacea": "pubescent",
    "Antennaria neglecta": "pubescent",
    "Antennaria parvifolia": "pubescent",
    "Antennaria rosea": "pubescent",
    "Antennaria microphylla": "pubescent",
    "Antennaria pulcherrima": "pubescent",
    "Potentilla hippiana": "pubescent",
    "Heterotheca villosa": "pubescent",
    "Eriogonum flavum": "pubescent",
    "Eriogonum androsaceum": "pubescent",
    "Oxytropis sericea": "pubescent",
    "Oxytropis splendens": "pubescent",
    "Lupinus sericeus": "pubescent",
    "Lupinus argenteus": "pubescent",
    "Phacelia sericea": "pubescent",
    "Physaria didymocarpa": "pubescent",
    "Androsace chamaejasme": "pubescent",
    "Dryas drummondii": "pubescent",
    "Dryas hookeriana": "pubescent",
    "Asclepias speciosa": "pubescent",
    "Asclepias ovalifolia": "pubescent",
    "Packera cana": "pubescent",
    "Pulsatilla nuttalliana": "pubescent",
    "Townsendia exscapa": "pubescent",
    "Townsendia parryi": "pubescent",
    "Erigeron caespitosus": "pubescent",
    "Silene acaulis": "pubescent",
    "Petasites frigidus": "pubescent",
    "Urtica dioica": "pubescent",
    "Urtica gracilis": "pubescent",
    # glaucous — a waxy blue-white bloom
    "Salix exigua": "glaucous",
    "Salix interior": "glaucous",
    "Salix brachycarpa": "glaucous",
    "Vaccinium uliginosum": "glaucous",
    "Yucca glauca": "glaucous",
    "Picea glauca": "glaucous",
    "Pseudotsuga menziesii": "glaucous",
    "Thalictrum dasycarpum": "glaucous",
    "Thalictrum venulosum": "glaucous",
    "Thalictrum occidentale": "glaucous",
    "Aquilegia brevistyla": "glaucous",
    "Aquilegia canadensis": "glaucous",
    "Aquilegia flavescens": "glaucous",
    "Aquilegia formosa": "glaucous",
    "Sedum lanceolatum": "glaucous",
    "Rhodiola integrifolia": "glaucous",
    "Comandra umbellata": "glaucous",
    "Agoseris glauca": "glaucous",
    "Dieteria canescens": "glaucous",
    "Stuckenia pectinata": "glaucous",
}


def apply(records, check=False):
    """Write both fields onto matching records. Returns (n_bark, n_leaf, missing)."""
    n_bark = n_leaf = 0
    seen_bark, seen_leaf = set(), set()
    for rec in records:
        sci = (rec.get("scientific_name") or "").strip()
        bark = BARK_TEXTURE.get(sci)
        if bark:
            seen_bark.add(sci)
            if not check:
                rec["bark_texture"] = bark
            n_bark += 1
        surf = LEAF_SURFACE.get(sci)
        if surf:
            seen_leaf.add(sci)
            if not check:
                rec["leaf_surface"] = surf
            n_leaf += 1
    missing = sorted((set(BARK_TEXTURE) - seen_bark)
                     | (set(LEAF_SURFACE) - seen_leaf))
    return n_bark, n_leaf, missing


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true",
                    help="report coverage without writing")
    args = ap.parse_args()

    bad = [k for k, v in BARK_TEXTURE.items() if v not in BARK_CLASSES]
    bad += [k for k, v in LEAF_SURFACE.items() if v not in LEAF_SURFACES]
    if bad:
        print("values outside the vocabulary:", bad)
        return 1

    with open(_MASTER, encoding="utf-8") as fh:
        records = json.load(fh)
    woody = [r for r in records if r.get("plant_type") in ("tree", "shrub")]
    n_bark, n_leaf, missing = apply(records, check=args.check)

    if missing:
        print("entries with no matching species (renamed?):")
        for name in missing:
            print("   ", name)
    uncovered = [r["common_name"] for r in woody
                 if (r.get("scientific_name") or "").strip() not in BARK_TEXTURE
                 and (r.get("scientific_name") or "").strip() not in NO_BARK]
    if uncovered:
        print(f"woody species still without a bark_texture ({len(uncovered)}):")
        for name in uncovered:
            print("   ", name)

    if args.check:
        print(f"check: {n_bark}/{len(woody)} woody species have bark, "
              f"{n_leaf} species have a distinctive leaf surface")
        return 1 if (missing or uncovered) else 0

    with open(_MASTER, "w", encoding="utf-8") as fh:
        json.dump(records, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    print(f"wrote {_MASTER}: {n_bark}/{len(woody)} woody species with a bark "
          f"texture, {n_leaf} species with a distinctive leaf surface")
    return 0


if __name__ == "__main__":
    sys.exit(main())

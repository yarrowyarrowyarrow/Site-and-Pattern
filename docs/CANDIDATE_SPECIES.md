# Candidate species: native plants the catalogue does not carry yet

*Compiled in V2.87 at the author's request ("give me a list, do not do it in
the app, store those for later"). Nothing here is in the catalogue or the
pending file. It is a worklist, backlog row **F168**.*

## How to use this list

Every province column is an **expectation**, written from regional floras in
a session that could not reach VASCAN. A `?` means genuinely unsure. **None of
it is a claim the catalogue makes.** Since V2.80 a species ships only with its
nativity read from a flora, so the route in is the one V2.86 built and V2.87
proved on seven trees:

1. Write each chosen species as a complete row in
   `data/plants_pending_flora.json` (see `src/pending_species.py`). The data
   gate holds pending rows to the catalogue's rules.
2. The author runs `scripts/fetch_flora_nativity.py --from-archive <zip>`,
   then `scripts/ingest_flora_nativity.py` (report), then `--apply`, which
   promotes each species VASCAN plainly confirms **with VASCAN's provinces**.
   In V2.87 VASCAN widened two of the seven.
3. The author runs the GBIF seeders (`seed_ecoregion_ranges.py --resume
   --species ...`, then `seed_species_ranges.py` and
   `seed_occurrence_points.py` with no `--species`) for range maps and
   locality ranking.

## 1. The app's own data says these are missing

Bees and Lepidoptera already in the catalogue name them as hosts
(`validate_host_genus_coverage` lists the genera on every gate run).

| Plant | Scientific name | Expected | Why |
|---|---|---|---|
| Green Milkweed | *Asclepias viridiflora* | AB, SK | The real one; see correction 1 below. Monarch host |
| Ten-petal Blazingstar | *Mentzelia decapetala* | AB, SK | A catalogued bee's host genus; showy badlands night-bloomer |
| Thrift Mock Goldenweed | *Stenotus armerioides* | AB, SK | Three bees cite *Haplopappus*; none of its segregates is carried |
| Arrow-leaved Groundsel | *Senecio triangularis* | AB (SK?) | Three bees cite *Senecio*; only *Packera cana* is carried |
| Pink Mountain-heather | *Phyllodoce empetriformis* | AB | Two bees cite it; mountain yards |

## 2. Lawn replacement (the app's core use)

| Plant | Scientific name | Expected | Why |
|---|---|---|---|
| Sun Sedge | *Carex inops* subsp. *heliophila* | AB, SK | Low, drought-tolerant, walkable; the best native lawn substitute here |
| Needle-leaved Sedge | *Carex duriuscula* | AB, SK | Short dry-prairie sedge |
| Thread-leaved Sedge | *Carex filifolia* | AB, SK | A dominant of dry mixed-grass prairie |
| Sand Dropseed | *Sporobolus cryptandrus* | AB, SK | Tough bunchgrass for sandy yards |
| Buffalograss | *Bouteloua dactyloides* | SK? | The classic native turf grass, at its northern edge |

## 3. Butterfly and moth hosts the catalogue cannot supply

| Plant | Scientific name | Expected | Why |
|---|---|---|---|
| Yellow Prairie Violet | *Viola nuttallii* | AB, SK | Fritillary host (two catalogued Lepidoptera need violets) |
| Fern-leaved Biscuitroot | *Lomatium foeniculaceum* | AB, SK | Anise swallowtail host |
| Fern-leaved Desert-parsley | *Lomatium dissectum* | AB | Same |
| Cow Parsnip | *Heracleum maximum* | AB, SK | Swallowtail host; pollinator magnet. Phototoxic sap: the row must say so |
| Wild Tarragon | *Artemisia dracunculus* | AB, SK | Prairie Old World swallowtail host |
| Wild Hops | *Humulus lupulus* var. *lupuloides* | SK (AB?) | Question Mark and Comma host; a native vine |
| Swamp Milkweed | *Asclepias incarnata* | SK? | Monarch host for wet ground |
| Western Sand Cherry | *Prunus pumila* | SK (AB?) | Keystone genus in a yard-sized shrub |
| Shining Willow | *Salix lucida* / *lasiandra* | AB, SK | Keystone small tree; VASCAN decides the accepted name |
| Flat-leaved Willow | *Salix planifolia* | AB, SK | Keystone shrub for wet sites |
| Western Wallflower | *Erysimum asperum* | AB, SK | Native mustard: white and orange-tip hosts; early nectar |
| Silver-leaf Scurf-pea | *Pediomelum argophyllum* | AB, SK | Prairie legume; blues |
| Field Milkvetch | *Astragalus agrestis* | AB, SK | Same |

## 4. Shade (the catalogue carries one fern)

| Plant | Scientific name | Expected |
|---|---|---|
| Lady Fern | *Athyrium filix-femina* | AB, SK |
| Spinulose Wood Fern | *Dryopteris carthusiana* | AB, SK |
| Oak Fern | *Gymnocarpium dryopteris* | AB, SK |
| Fragile Fern | *Cystopteris fragilis* | AB, SK |
| Oregon Woodsia | *Woodsia oregana* | AB, SK |
| Starflower | *Lysimachia borealis* | AB, SK |
| Goldthread | *Coptis trifolia* | AB, SK |
| Queen's Cup | *Clintonia uniflora* | AB |
| Bluebead Lily | *Clintonia borealis* | SK |

## 5. Shrubs and boreal edibles

| Plant | Scientific name | Expected | Why |
|---|---|---|---|
| Red Elderberry | *Sambucus racemosa* | AB, SK | Common bird-food shrub, oddly absent |
| Lingonberry | *Vaccinium vitis-idaea* | AB, SK | The commonest boreal edible groundcover |
| Black Huckleberry | *Vaccinium membranaceum* | AB | Mountain edible |
| Crowberry | *Empetrum nigrum* | AB, SK | Evergreen groundcover |
| Mountain Maple | *Acer spicatum* | SK | Boreal understorey small tree |
| Showy Mountain-ash | *Sorbus decora* | SK (AB?) | Fruit for waxwings and thrushes |
| Mallow Ninebark | *Physocarpus malvaceus* | AB | Southwest Alberta shrub |

## 6. Prairie, parkland and wet-meadow forbs

| Plant | Scientific name | Expected |
|---|---|---|
| Fringed Puccoon | *Lithospermum incisum* | AB, SK |
| White Beardtongue | *Penstemon albidus* | AB, SK |
| Soft Goldenrod | *Solidago mollis* | AB, SK |
| Upland White Goldenrod | *Solidago ptarmicoides* | AB, SK |
| Prairie Sunflower | *Helianthus petiolaris* | SK (AB?) |
| Wavy-leaved Thistle (native) | *Cirsium undulatum* | AB, SK |
| Kalm's Lobelia | *Lobelia kalmii* | AB, SK |
| Blue Flag | *Iris versicolor* | SK |
| Grass-of-Parnassus | *Parnassia palustris* | AB, SK |
| Western Anemone | *Pulsatilla occidentalis* | AB |
| Beargrass | *Xerophyllum tenax* | AB (southwest) |

## Corrections found while compiling this (not additions)

1. **"Green Milkweed" is two species in one row.** Filed as *Asclepias
   ovalifolia* (oval-leaved milkweed), with a common name, a green flower
   colour and a dry-upland description that fit *A. viridiflora*. The common
   name is the edge key: fix with `scripts/rename_common_name.py`, review the
   colour and notes, then add the real Green Milkweed from list 1.
2. **37 rows VASCAN records in SK that the catalogue calls AB-only** (June
   Grass, Bluebunch Fescue, Green Needle Grass, Butte Primrose...). The ingest
   files "VASCAN records more" under *confirm*. Since V2.85 the designer
   follows the province, so a Saskatchewan yard never gets them. A **widen**
   bucket, reported before applied, is waiting on the author's yes.
3. **"Crocus", cited by one bee, is prairie crocus**, *Pulsatilla nuttalliana*,
   already carried. The fix is a `GENUS_SYNONYMS` entry, not a plant.

## Deliberately left off

- **Introduced hosts the bee records cite:** *Trifolium*, *Melilotus*,
  *Medicago*, *Taraxacum*, *Lythrum*, *Linaria*, *Centaurea*. Correctly absent.
- **Not native here:** *Monardella*, *Salvia*.
- **Rare, listed, or usually wild-dug:** western spiderwort (federally listed),
  native orchids beyond the one carried, pitcher plant, limber and whitebark
  pine.
- **Toxic look-alikes:** water hemlock, death camas relatives, monkshood.
- **Green Ash:** emerald ash borer (V2.86's call, the author's to reverse).

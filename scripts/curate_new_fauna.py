#!/usr/bin/env python3
"""
scripts/curate_new_fauna.py — the 200 animals that carry most of the edges.

**Dev-time, offline.** Run it to read the table; the ingest gate imports
:func:`verdicts`.

    python3 scripts/curate_new_fauna.py            # the table
    python3 scripts/curate_new_fauna.py --apply    # write the fauna rows

Why this exists
---------------
The AB/SK occurrence gate (V2.61) and the introduced review (V2.62) took the
held queue from 2,898 animals to 1,252. Checking the top of that list before
writing 1,252 rows found it was still wrong at the very top:

| species | AB | SK | edges | |
|---|---|---|---|---|
| *Apis mellifera* | 3,671 | 451 | **133** | the honeybee, straight through |
| *Bombus impatiens* | 55 | 5 | 89 | eastern; shipped for greenhouses |
| *Bombus vosnesenskii* | 11 | 0 | 73 | Pacific coast |
| *Bombus prshewalskyi* | 4 | **1,125** | 57 | **Central Asian** |
| *Bombus bimaculatus* | 0 | 406 | 54 | eastern North America |

The honeybee is the clearest failure and the most instructive: V2.62's review
only saw the 24 species GBIF *flagged*, and after the strict Canada filter
*Apis mellifera* came back `unstated`, so it was never a candidate. It would
have entered as a native Alberta bee with 133 relationships.

**Occurrence counts cannot separate "native here" from "GBIF holds records
here for some reason."** A Central Asian bumblebee with 1,125 Saskatchewan
records is a data error, not a range. That is the fourth automated nativity
signal to fail, against two hand reviews that worked.

Why the top 200
---------------
The edges are concentrated, so review is bounded:

    top  100 species → 2,693 of 6,664 edges (40%)
    top  200 species → 3,864 (57%)
    all 1,252        → 6,664

200 covers well over half the value for an afternoon's reading. **The
1,052-species tail is held, not admitted** — its animals are real and its
edges are probably fine, but "probably fine" is not what this catalogue
claims about a documented edge.

Genus defaults, species overrides
---------------------------------
**Because that is the shape of the knowledge.** For *Syrphus* or *Hylaeus* I
can say with confidence that the genus is well represented across the prairies
and cannot place every species; for *Bombus* I can place most species
individually. Writing 200 independent calls would imply a uniform confidence
that does not exist. A genus rule that is wrong is wrong visibly, in one line,
for every species under it.

Every verdict is unsourced, like the 142 fauna rows already shipped and the
two reviews before this one. **`hold` is used freely** — it costs edges and
claims nothing.
"""

from __future__ import annotations

import argparse
import collections
import json
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)
_DATA = os.path.join(_ROOT, "data")
_FETCHED = os.path.join(_DATA, "fetched")

#: The exact 200 species this review covered, pinned.
#:
#: **Recomputing the shortlist is unstable and it bit immediately.** The list
#: was "top 200 by edge count among animals not yet in the catalogue" — so the
#: moment 159 of them were written, the window slid down and pulled in 42
#: species nobody had read, including *Megachile rotundata* and *Vespula
#: germanica*, both introduced. A review has to name what it reviewed.
REVIEWED = (
    "Apis mellifera",
    "Bombus impatiens",
    "Bombus vosnesenskii",
    "Halictus ligatus",
    "Halictus confusus",
    "Bombus prshewalskyi",
    "Bombus bimaculatus",
    "Strymon melinus",
    "Phyciodes tharos",
    "Toxomerus geminatus",
    "Agapostemon texanus",
    "Halictus tripartitus",
    "Vanessa virginiensis",
    "Polistes fuscatus",
    "Colias eurytheme",
    "Eristalis dimidiata",
    "Coenonympha california",
    "Andrena prunorum",
    "Syritta pipiens",
    "Cisseps fulvicollis",
    "Eristalis arbustorum",
    "Polistes dominula",
    "Polites peckius",
    "Speyeria cybele",
    "Cupido comyntas",
    "Lasioglossum albipenne",
    "Ochlodes sylvanoides",
    "Bombus auricomus",
    "Bombus vandykei",
    "Limenitis archippus",
    "Sphex ichneumoneus",
    "Celastrina lucia",
    "Dolichovespula arenaria",
    "Dolichovespula maculata",
    "Lycaena hypophlaeas",
    "Andrena vicina",
    "Euptoieta claudia",
    "Papilio glaucus",
    "Andrena crataegi",
    "Andrena milwaukeensis",
    "Eupeodes americanus",
    "Ancyloxypha numitor",
    "Apallates coxendix",
    "Ceratina calcarata",
    "Argynnis aphrodite",
    "Bombus vancouverensis nearcticus",
    "Megachile latimanus",
    "Melissodes bimaculatus",
    "Speyeria atlantis",
    "Sphaerophoria contigua",
    "Bombylius major",
    "Diabrotica undecimpunctata",
    "Eristalis stipator",
    "Halictus farinosus",
    "Lasioglossum cressonii",
    "Lon hobomok",
    "Megachile perihirta",
    "Augochlorella aurata",
    "Burnsius communis",
    "Callophrys gryneus",
    "Euodynerus foraminatus",
    "Helophilus fasciatus",
    "Hesperia comma colorado",
    "Hylaeus modestus",
    "Megachile melanophaea",
    "Osmia albolateralis",
    "Bombus vancouverensis",
    "Callophrys niphon",
    "Eristalis flavipes",
    "Lasioglossum nevadense",
    "Osmia juxta",
    "Osmia tristella",
    "Papilio polyxenes asterius",
    "Satyrium titus",
    "Alypia octomaculata",
    "Bombus hypnorum",
    "Eupeodes volucris",
    "Hylaeus annulatus",
    "Lasioglossum marinense",
    "Lasioglossum sisymbrii",
    "Vespula maculifrons",
    "Andrena carlini",
    "Euphyes vestris",
    "Feltia jaculifera",
    "Lasioglossum incompletum",
    "Limenitis arthemis arthemis",
    "Megachile pugnata",
    "Melissodes trinodis",
    "Osmia pusilla",
    "Philanthus gibbosus",
    "Trichodes ornatus",
    "Andrena nigrocaerulea",
    "Ashmeadiella bucconis",
    "Boloria bellona",
    "Heriades carinata",
    "Heriades cressoni",
    "Lucilia sericata",
    "Melissodes microstictus",
    "Pieris oleracea",
    "Ancistrocerus adiabatus",
    "Andrena miranda",
    "Andrena nivalis",
    "Colletes kincaidii",
    "Gnophaela vermiculata",
    "Hoplitis albifrons argentifrons",
    "Hylaeus basalis",
    "Lasioglossum knereri",
    "Papilio polyxenes",
    "Polites themistocles",
    "Pontia protodice",
    "Andrena miserabilis",
    "Bombus sandersoni",
    "Colletes fulgidus",
    "Melissodes druriellus",
    "Osmia californica",
    "Syrphus opinator",
    "Andrena amphibola",
    "Andrena hirticincta",
    "Boloria chariclea",
    "Bombus californicus",
    "Ctenucha virginica",
    "Dolichovespula arctica",
    "Eucera edwardsii",
    "Euphydryas anicia",
    "Feltia herilis",
    "Hoplitis hypocrita",
    "Icaricia acmon",
    "Icaricia icarioides",
    "Lasioglossum nigroviride",
    "Lasioglossum pruinosum",
    "Osmia trevoris",
    "Papilio zelicaon",
    "Physocephala tibialis",
    "Pontia occidentalis",
    "Pyrausta orphisalis",
    "Tharsalea hyllus",
    "Thyris maculata",
    "Agapostemon splendens",
    "Anagrapha falcifera",
    "Anatrytone logan",
    "Andrena lupinorum",
    "Autographa precationis",
    "Danaus plexippus plexippus",
    "Evodinus monticola",
    "Hesperia leonardus",
    "Hoplitis fulgida",
    "Lasioglossum ruidosense",
    "Osmia bucephala",
    "Osmia coloradensis",
    "Osmia montana",
    "Trichiotinus assimilis",
    "Vespula consobrina",
    "Andrena pallidifovea",
    "Anthidium manicatum",
    "Anthonomus elongatus",
    "Bembix americana",
    "Carterocephalus mandan",
    "Hoplitis albifrons",
    "Hylaeus mesillae",
    "Icaricia saepiolus",
    "Lycomorpha pholus",
    "Megachile onobrychidis",
    "Phyciodes mylitta",
    "Physocephala furcillata",
    "Polygonia comma",
    "Syrphus rectus",
    "Tharsalea helloides",
    "Vanessa atalanta rubria",
    "Andrena salicifloris",
    "Andrena scurra",
    "Andrena thaspii",
    "Anoplodera pubera",
    "Batyle suturalis",
    "Bombus kirbiellus",
    "Epalpus signifer",
    "Epistrophe emarginata",
    "Eristalis hirta",
    "Helicoverpa zea",
    "Helophilus latifrons",
    "Lasioglossum inconditum",
    "Lygus lineolaris",
    "Megachile frigida",
    "Osmia densa",
    "Osmia pentstemonis",
    "Papilio eurymedon",
    "Philanthus ventilabris",
    "Schinia arcigera",
    "Syrphus torvus",
    "Ancistrocerus catskill",
    "Andrena angustitarsata",
    "Andrena candida",
    "Anthrenus museorum",
    "Bibio albipennis",
    "Calypte anna",
    "Celastrina neglecta",
    "Coelioxys rufitarsis",
    "Colias interior",
    "Dianthidium subparvum",
    "Epistrophe grossulariae",
    "Hoplitis producta",
)


#: genus → (verdict, reason). The default for every species in that genus.
GENUS: dict[str, tuple] = {
    # ── Native bees. Alberta and Saskatchewan have a rich solitary-bee
    # fauna and these genera are all well represented in it. ─────────────
    "Andrena": ("include", "Mining bees. One of the largest bee genera in the "
                "prairies; dozens of species across AB and SK."),
    "Lasioglossum": ("include", "Sweat bees. Abundant and diverse here."),
    "Halictus": ("include", "Sweat bees, widespread across the prairies."),
    "Osmia": ("include", "Mason bees. Well represented in AB, especially the "
              "foothills."),
    "Megachile": ("include", "Leafcutter bees, native and common."),
    "Melissodes": ("include", "Long-horned bees, late-summer composite "
                   "specialists across the grasslands."),
    "Hylaeus": ("include", "Masked bees, small and widespread."),
    "Hoplitis": ("include", "Small mason bees, western and northern."),
    "Agapostemon": ("include", "Metallic green sweat bees, prairie-typical."),
    "Colletes": ("include", "Cellophane bees, widespread."),
    "Heriades": ("include", "Resin bees, small and widespread."),
    "Ceratina": ("include", "Small carpenter bees, common in stem nests."),
    "Augochlorella": ("include", "Metallic green sweat bees reaching the "
                      "prairies."),
    "Coelioxys": ("include", "Cuckoo bees of Megachile — present wherever "
                  "their hosts are."),
    "Dianthidium": ("include", "Pebble bees, western and dry-country."),
    "Eucera": ("include", "Long-horned bees, widespread."),
    "Bombus": ("hold", "Bumblebees, and the genus most in need of "
               "species-level calls — several in this list are eastern, "
               "Pacific-coast or Central Asian. Everything is decided below."),
    "Ashmeadiella": ("hold", "Mostly a southwestern genus; I cannot place the "
                     "species in this list against the prairies."),

    # ── Wasps ────────────────────────────────────────────────────────────
    "Dolichovespula": ("include", "Aerial yellowjackets, native and "
                       "conspicuous across the prairies."),
    "Vespula": ("include", "Ground yellowjackets, native."),
    "Ancistrocerus": ("include", "Potter wasps, widespread."),
    "Euodynerus": ("include", "Mason wasps, widespread."),
    "Philanthus": ("include", "Beewolves, sand-country natives."),
    "Sphex": ("include", "Digger wasps. S. ichneumoneus was already reviewed "
              "as native in curate_introduced."),
    "Bembix": ("include", "Sand wasps, native to prairie sand country."),
    "Polistes": ("include", "Paper wasps. P. fuscatus is the native northern "
                 "one; the European P. dominula is refused below."),

    # ── Flies. Syrphids are strongly Holarctic and well represented. ─────
    "Eupeodes": ("include", "Hoverflies, Holarctic and common."),
    "Syrphus": ("include", "Hoverflies, Holarctic and common."),
    "Helophilus": ("include", "Marsh hoverflies, wetland-typical here."),
    "Sphaerophoria": ("include", "Hoverflies, widespread."),
    "Epistrophe": ("include", "Hoverflies, Holarctic."),
    "Physocephala": ("include", "Thick-headed flies, native parasitoids of "
                     "bees."),
    "Bombylius": ("include", "Bee flies. B. major is Holarctic and native "
                  "here as well as in Europe."),
    "Epalpus": ("include", "Tachinid flies, native."),
    "Bibio": ("include", "March flies, widespread."),
    "Toxomerus": ("include", "Hoverflies. Eastern-centred but reaching the "
                  "prairies and expanding."),
    "Eristalis": ("include", "Drone flies. Mostly Holarctic natives — but see "
                  "E. arbustorum below, and E. tenax is already flagged "
                  "introduced in the catalogue."),
    "Apallates": ("hold", "A chloropid fly genus I cannot place with any "
                  "confidence at species level."),

    # ── Beetles ──────────────────────────────────────────────────────────
    "Trichodes": ("include", "Checkered beetles, western and native."),
    "Evodinus": ("include", "Flower longhorns, boreal and montane."),
    "Trichiotinus": ("include", "Flower scarabs, widespread."),
    "Batyle": ("include", "Flower longhorns, western."),
    "Diabrotica": ("include", "Cucumber beetles. Native to North America, "
                   "though the species here is an agricultural pest as well "
                   "as a flower visitor."),
    "Anoplodera": ("hold", "Flower longhorns; the species listed is eastern "
                   "and I cannot place it here."),
    "Anthonomus": ("hold", "Weevils. Too large and too poorly known to me at "
                   "species level."),

    # ── Bugs ─────────────────────────────────────────────────────────────
    "Lygus": ("include", "Plant bugs, native and abundant in prairie "
              "vegetation."),
}

#: species → (verdict, reason). Overrides the genus rule.
SPECIES: dict[str, tuple] = {
    # ── The honeybee, and the reason this review exists ──────────────────
    "Apis mellifera": (
        "reject",
        "Western Honey Bee. European, kept and feral, and the single most "
        "obviously introduced insect in the country. It reached the top of "
        "the surviving list with 133 edges because V2.62's review only saw "
        "species GBIF FLAGGED, and the strict Canada filter had left this one "
        "`unstated`. That is why this file exists."),

    # ── Bumblebees, one at a time ────────────────────────────────────────
    "Bombus kirbiellus": (
        "include", "High-alpine bumblebee of the Rockies; a genuine Alberta "
        "species above treeline."),
    "Bombus vancouverensis": (
        "include", "Western bumblebee of the mountains and foothills, "
        "reaching Alberta."),
    "Bombus sandersoni": (
        "hold", "Eastern boreal. It may reach northern Alberta and I cannot "
        "confirm it."),
    "Bombus californicus": (
        "hold", "Southern interior and Pacific slope; marginal at best here."),
    "Bombus auricomus": (
        "reject", "Black-and-gold Bumblebee — eastern and central North "
        "America, not the Canadian prairies."),
    "Bombus bimaculatus": (
        "reject", "Two-spotted Bumblebee — eastern North America. Zero "
        "Alberta records against 406 in the Saskatchewan box, which is itself "
        "a reason to distrust the box rather than the species."),
    "Bombus impatiens": (
        "reject", "Common Eastern Bumblebee. Native to eastern North America "
        "AND shipped commercially for greenhouse pollination, so western "
        "records are escapes. Recommending plants for it would be "
        "recommending plants for an agricultural escapee."),
    "Bombus vosnesenskii": (
        "reject", "Yellow-faced Bumblebee — Pacific coast, California to "
        "southern BC."),
    "Bombus vandykei": (
        "reject", "Van Dyke's Bumblebee — California and Oregon."),
    "Bombus hypnorum": (
        "reject", "Tree Bumblebee — Palaearctic. Not a North American "
        "species."),
    "Bombus prshewalskyi": (
        "reject", "A Central Asian bumblebee of the Tibetan plateau. Its "
        "1,125 records inside the Saskatchewan box are a GBIF data error, and "
        "they are the clearest evidence in this whole exercise that an "
        "occurrence count is not a range."),

    # ── Introduced, of the genera otherwise included ─────────────────────
    "Anthidium manicatum": (
        "reject", "European Wool Carder Bee. Introduced to North America and "
        "aggressive toward native bees at flowers."),
    "Polistes dominula": (
        "reject", "European Paper Wasp. Introduced and displacing native "
        "Polistes."),
    "Syritta pipiens": (
        "reject", "Thick-legged Hoverfly. European, introduced, now "
        "cosmopolitan."),
    "Anthrenus museorum": (
        "reject", "Museum Beetle. European, introduced, and a pest of "
        "collections rather than a garden visitor."),
    "Eristalis arbustorum": (
        "hold", "Holarctic, and the literature is not agreed on whether North "
        "American populations are native or introduced. Held rather than "
        "guessed."),
    "Lucilia sericata": (
        "reject", "Common Green Bottle Fly — already reviewed as introduced "
        "in curate_introduced."),
    "Calypte anna": (
        "reject", "Anna's Hummingbird — already rejected on range in "
        "curate_birds."),

    # ── Trinomials. The catalogue keys fauna on binomials. ───────────────
    "Bombus vancouverensis nearcticus": (
        "reject", "A subspecies trinomial; the catalogue keys on binomials "
        "and B. vancouverensis is included above."),
    "Papilio polyxenes asterius": (
        "reject", "Subspecies trinomial; the species is included above."),
    "Vanessa atalanta rubria": (
        "reject", "Subspecies trinomial. Red Admiral is a real Alberta "
        "migrant, but not under this key."),
    "Limenitis arthemis arthemis": (
        "reject", "Subspecies trinomial."),
    "Hesperia comma colorado": (
        "reject", "Subspecies trinomial."),
    "Danaus plexippus plexippus": (
        "reject", "Subspecies trinomial, and Monarch is already in the "
        "catalogue as Danaus plexippus."),
    "Hoplitis albifrons argentifrons": (
        "reject", "Subspecies trinomial; H. albifrons is included."),

    # ── Butterflies and moths, decided individually ──────────────────────
    "Papilio eurymedon": ("include", "Pale Swallowtail — western, reaching "
                          "the Alberta foothills."),
    "Papilio zelicaon": ("include", "Anise Swallowtail — western, present in "
                         "southern Alberta."),
    "Papilio polyxenes": ("include", "Black Swallowtail — reaches the "
                          "prairies; larvae on native umbellifers."),
    "Papilio glaucus": ("reject", "Eastern Tiger Swallowtail. The Alberta "
                        "tiger swallowtail is P. canadensis, already in the "
                        "catalogue."),
    "Phyciodes tharos": ("include", "Pearl Crescent — widespread, aster "
                         "specialist."),
    "Phyciodes mylitta": ("include", "Mylitta Crescent — western, thistle "
                          "feeder."),
    "Strymon melinus": ("include", "Gray Hairstreak — one of the most "
                        "widespread butterflies in North America."),
    "Vanessa virginiensis": ("include", "American Lady — a regular migrant to "
                             "the prairies, breeding on pussytoes."),
    "Speyeria atlantis": ("include", "Atlantis Fritillary — boreal and "
                          "montane, common in Alberta."),
    "Speyeria cybele": ("include", "Great Spangled Fritillary — widespread, "
                        "violet feeder."),
    "Argynnis aphrodite": ("include", "Aphrodite Fritillary — prairie and "
                           "parkland."),
    "Boloria bellona": ("include", "Meadow Fritillary — widespread in damp "
                        "meadows."),
    "Boloria chariclea": ("include", "Arctic Fritillary — northern and "
                          "alpine."),
    "Polites peckius": ("include", "Peck's Skipper — grassland, widespread."),
    "Polites themistocles": ("include", "Tawny-edged Skipper — grassland."),
    "Ochlodes sylvanoides": ("include", "Woodland Skipper — western."),
    "Carterocephalus mandan": ("include", "Arctic Skipper — boreal, present "
                               "across northern Alberta."),
    "Burnsius communis": ("include", "Common Checkered-Skipper — reaches the "
                          "southern prairies."),
    "Lon hobomok": ("include", "Hobomok Skipper — boreal and parkland."),
    "Ancyloxypha numitor": ("hold", "Least Skipper — eastern and central; I "
                            "cannot confirm it on the Alberta side."),
    "Euphyes vestris": ("hold", "Dun Skipper — eastern-centred; marginal "
                        "here."),
    "Anatrytone logan": ("reject", "Delaware Skipper — eastern North "
                         "America."),
    "Limenitis archippus": ("include", "Viceroy — willow feeder, common in "
                            "prairie riparian."),
    "Colias eurytheme": ("include", "Orange Sulphur — abundant across the "
                         "prairies."),
    "Colias interior": ("include", "Pink-edged Sulphur — boreal, blueberry "
                        "feeder."),
    "Pontia occidentalis": ("include", "Western White — montane and prairie."),
    "Pontia protodice": ("include", "Checkered White — southern prairies."),
    "Pieris oleracea": ("include", "Mustard White — a NATIVE Pieris, not to "
                        "be confused with the introduced P. rapae."),
    "Cupido comyntas": ("include", "Eastern Tailed-Blue — reaches the "
                        "prairies."),
    "Celastrina lucia": ("include", "Northern Azure — boreal and parkland."),
    "Celastrina neglecta": ("include", "Summer Azure — widespread."),
    "Icaricia icarioides": ("include", "Boisduval's Blue — western, lupine "
                            "feeder."),
    "Icaricia saepiolus": ("include", "Greenish Blue — western, clover "
                           "feeder."),
    "Icaricia acmon": ("hold", "Acmon Blue — southwestern; I cannot place it "
                       "on the Canadian prairies."),
    "Callophrys niphon": ("include", "Eastern Pine Elfin — boreal pine."),
    "Callophrys gryneus": ("hold", "Juniper Hairstreak — its Canadian range "
                           "is patchy and I cannot confirm the prairies."),
    "Satyrium titus": ("include", "Coral Hairstreak — chokecherry and plum "
                       "thickets."),
    "Tharsalea helloides": ("include", "Purplish Copper — common in damp "
                            "prairie."),
    "Tharsalea hyllus": ("include", "Bronze Copper — wetland margins."),
    "Lycaena hypophlaeas": ("hold", "American Copper — its status on the "
                            "prairies is unclear to me."),
    "Euptoieta claudia": ("include", "Variegated Fritillary — a regular "
                          "southern migrant."),
    "Euphydryas anicia": ("include", "Anicia Checkerspot — western montane."),
    "Coenonympha california": ("hold", "Ringlet taxonomy has been rearranged "
                               "and I cannot tell whether this key covers the "
                               "Alberta ringlet or the Californian one."),
    "Hesperia leonardus": ("hold", "Leonard's Skipper — eastern-centred."),
    "Polygonia comma": ("reject", "Eastern Comma. Alberta's commas are "
                        "P. faunus, P. gracilis and P. satyrus."),
    "Cisseps fulvicollis": ("include", "Yellow-collared Scape Moth — "
                            "widespread day-flying moth."),
    "Ctenucha virginica": ("include", "Virginia Ctenucha — grassland "
                           "day-flier."),
    "Lycomorpha pholus": ("include", "Black-and-yellow Lichen Moth."),
    "Alypia octomaculata": ("include", "Eight-spotted Forester — day-flying, "
                            "on wild grape and fireweed."),
    "Gnophaela vermiculata": ("include", "Police Car Moth — a western "
                              "day-flier, conspicuous in Alberta foothills."),
    "Feltia herilis": ("include", "A native cutworm moth; adults nectar."),
    "Feltia jaculifera": ("include", "Dingy Cutworm — native, adults nectar "
                          "heavily on late composites."),
    "Anagrapha falcifera": ("include", "Celery Looper — native and "
                            "widespread."),
    "Autographa precationis": ("include", "Common Looper — native."),
    "Schinia arcigera": ("include", "Arcigera Flower Moth — aster "
                         "specialist."),
    "Pyrausta orphisalis": ("include", "A native pyralid of mints."),
    "Thyris maculata": ("hold", "Spotted Thyris — eastern; I cannot place "
                        "it here."),
    "Helicoverpa zea": ("hold", "Corn Earworm. Native to the Americas, but a "
                        "migratory crop pest rather than something to plant "
                        "for, and it does not overwinter here."),
}

_ICON = {"bee": "🐝", "lepidoptera": "🦋", "bird": "🐦",
         "other_insect": "🪲", "mammal": "🦌"}


def _rows(path):
    with open(path, "r", encoding="utf-8") as fh:
        blob = json.load(fh)
    return blob if isinstance(blob, list) else next(
        v for v in blob.values() if isinstance(v, list))


def _shortlist() -> list:
    """The top 200 surviving animals by edge count, richest first."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "ingest_fauna_edges",
        os.path.join(_ROOT, "scripts", "ingest_fauna_edges.py"))
    ing = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ing)
    refuse, corrected = ing._reviewed_origin()

    cands = _rows(os.path.join(_FETCHED, "fauna_edges_candidates.json"))
    held = {h["scientific_name"]: h for h in
            _rows(os.path.join(_FETCHED, "fauna_new_species.json"))}
    with open(os.path.join(_FETCHED, "fauna_nativity.json"),
              encoding="utf-8") as fh:
        nat = json.load(fh)
    have = {r["scientific_name"] for r in
            _rows(os.path.join(_DATA, "fauna_master.json"))
            if isinstance(r, dict) and r.get("scientific_name")}

    n = collections.Counter(c["fauna"] for c in cands if c.get("fauna"))
    ok = [a for a in held if a not in have
          and ing.nativity_verdict(nat.get(a), a, refuse, corrected)[0]]
    ok.sort(key=lambda a: (-n[a], a))
    # Pinned, not sliced. `ok` is recomputed from the current catalogue, so
    # slicing it would review a different 200 every time rows are written.
    surviving = set(ok)
    return [(a, held.get(a, {}).get("taxon", ""), n[a], nat.get(a, {}))
            for a in REVIEWED if a in surviving or a in have]


def verdict_for(name: str) -> tuple:
    """``(verdict, reason)`` — species override first, then the genus rule."""
    if name in SPECIES:
        return SPECIES[name]
    genus = name.split()[0] if name else ""
    if genus in GENUS:
        return GENUS[genus]
    return ("hold", "not reviewed — outside the top 200")


def verdicts() -> dict:
    """``scientific_name → row`` for every animal cleared to be written.

    Consumed by the ingest gate. A name absent from this map is held, and
    holding is the default for everything outside the reviewed shortlist.
    """
    out = {}
    for name, taxon, _edges, nat in _shortlist():
        v, reason = verdict_for(name)
        if v != "include":
            continue
        provinces = nat.get("provinces", "")
        out[name] = {
            "scientific_name": name,
            # Scientific name as the common name where there is no accepted
            # English one — the author's call, and the honest one. For a
            # solitary bee the binomial IS the name; entomologists use it as
            # such, and inventing "Milwaukee Mining Bee" would be writing a
            # name nobody wrote.
            "common_name": COMMON_NAMES.get(name, name),
            "taxon": taxon,
            "ab_native": 1 if "AB" in provinces.split(",") else 0,
            "native_provinces": provinces,
            "range_notes": reason,
            "icon": _ICON.get(taxon, "🐛"),
            "description": reason,
        }
    return out


#: genus → (kind, activity) for the Lepidoptera this review admits.
#:
#: **Not optional.** `lepidoptera_attributes.kind` is what the 3D scene and
#: the habitat panel read to tell a butterfly from a moth; a new lep without
#: one arrives as `None` and sorts nowhere. Three tests caught that the moment
#: the 159 rows landed — the app had simply never met a lepidopteran it had no
#: attributes for.
#:
#: `flight_season` is deliberately left EMPTY rather than invented. Since
#: V2.63 an unrecorded season falls back to the warm months in
#: `scene_wildlife._season_months`, which is the honest default; writing
#: "June-August" for a moth nobody has phenology for would be a measurement
#: that never happened.
LEP_KIND: dict[str, tuple] = {
    # Butterflies
    "Papilio": ("butterfly", "day"), "Phyciodes": ("butterfly", "day"),
    "Strymon": ("butterfly", "day"), "Vanessa": ("butterfly", "day"),
    "Speyeria": ("butterfly", "day"), "Argynnis": ("butterfly", "day"),
    "Boloria": ("butterfly", "day"), "Limenitis": ("butterfly", "day"),
    "Colias": ("butterfly", "day"), "Pontia": ("butterfly", "day"),
    "Pieris": ("butterfly", "day"), "Cupido": ("butterfly", "day"),
    "Celastrina": ("butterfly", "day"), "Icaricia": ("butterfly", "day"),
    "Callophrys": ("butterfly", "day"), "Satyrium": ("butterfly", "day"),
    "Tharsalea": ("butterfly", "day"), "Lycaena": ("butterfly", "day"),
    "Euptoieta": ("butterfly", "day"), "Euphydryas": ("butterfly", "day"),
    "Coenonympha": ("butterfly", "day"), "Polygonia": ("butterfly", "day"),
    "Danaus": ("butterfly", "day"),
    # Skippers — their own kind in this vocabulary, not butterflies.
    "Polites": ("skipper", "day"), "Ochlodes": ("skipper", "day"),
    "Carterocephalus": ("skipper", "day"), "Burnsius": ("skipper", "day"),
    "Lon": ("skipper", "day"), "Ancyloxypha": ("skipper", "day"),
    "Euphyes": ("skipper", "day"), "Anatrytone": ("skipper", "day"),
    "Hesperia": ("skipper", "day"),
    # Day-flying moths. The reason `activity` is separate from `kind`:
    # a Police Car Moth is out in full sun and a Dingy Cutworm is not.
    "Cisseps": ("moth", "day"), "Ctenucha": ("moth", "day"),
    "Lycomorpha": ("moth", "day"), "Alypia": ("moth", "day"),
    "Gnophaela": ("moth", "day"),
    # Night-flying moths
    "Feltia": ("moth", "night"), "Anagrapha": ("moth", "night"),
    "Autographa": ("moth", "night"), "Schinia": ("moth", "night"),
    "Pyrausta": ("moth", "night"), "Thyris": ("moth", "day"),
    "Helicoverpa": ("moth", "night"),
}


def lep_attributes() -> list:
    """Minimal `lepidoptera_attributes` rows for the leps this review admits."""
    out = []
    for name, row in sorted(verdicts().items()):
        if row["taxon"] != "lepidoptera":
            continue
        kind, activity = LEP_KIND.get(name.split()[0], ("butterfly", "day"))
        out.append({
            "scientific_name": name,
            "kind": kind,
            "activity": activity,
            # "unknown", not a made-up range and not an empty string. The
            # file already accepts "unknown" for `overwintering_stage`, so
            # this uses the word the data model already has for the thing it
            # already admits. `parse_month_range` yields nothing for it, and
            # `scene_wildlife` then falls back to the warm months.
            "flight_season": "unknown",
            "overwintering_stage": "unknown",
            "source": "globi",
            "notes": ("Kind and activity assigned by family in "
                      "scripts/curate_new_fauna.py. Flight season and "
                      "overwintering stage are not recorded for this species "
                      "and are not guessed; the scene falls back to the "
                      "warm-season default."),
        })
    return out


#: The species that genuinely have an accepted English name in common use.
#: Everything else keeps its binomial, which for most solitary bees and
#: micromoths is the only name there is.
COMMON_NAMES: dict[str, str] = {
    "Strymon melinus": "Gray Hairstreak",
    "Vanessa virginiensis": "American Lady",
    "Speyeria atlantis": "Atlantis Fritillary",
    "Speyeria cybele": "Great Spangled Fritillary",
    "Argynnis aphrodite": "Aphrodite Fritillary",
    "Boloria bellona": "Meadow Fritillary",
    "Boloria chariclea": "Arctic Fritillary",
    "Phyciodes tharos": "Pearl Crescent",
    "Phyciodes mylitta": "Mylitta Crescent",
    "Limenitis archippus": "Viceroy",
    "Colias eurytheme": "Orange Sulphur",
    "Colias interior": "Pink-edged Sulphur",
    "Pontia occidentalis": "Western White",
    "Pontia protodice": "Checkered White",
    "Pieris oleracea": "Mustard White",
    "Cupido comyntas": "Eastern Tailed-Blue",
    "Celastrina lucia": "Northern Azure",
    "Celastrina neglecta": "Summer Azure",
    "Icaricia icarioides": "Boisduval's Blue",
    "Icaricia saepiolus": "Greenish Blue",
    "Callophrys niphon": "Eastern Pine Elfin",
    "Satyrium titus": "Coral Hairstreak",
    "Tharsalea helloides": "Purplish Copper",
    "Tharsalea hyllus": "Bronze Copper",
    "Euptoieta claudia": "Variegated Fritillary",
    "Euphydryas anicia": "Anicia Checkerspot",
    "Papilio eurymedon": "Pale Swallowtail",
    "Papilio zelicaon": "Anise Swallowtail",
    "Papilio polyxenes": "Black Swallowtail",
    "Polites peckius": "Peck's Skipper",
    "Polites themistocles": "Tawny-edged Skipper",
    "Ochlodes sylvanoides": "Woodland Skipper",
    "Carterocephalus mandan": "Arctic Skipper",
    "Burnsius communis": "Common Checkered-Skipper",
    "Lon hobomok": "Hobomok Skipper",
    "Cisseps fulvicollis": "Yellow-collared Scape Moth",
    "Ctenucha virginica": "Virginia Ctenucha",
    "Lycomorpha pholus": "Black-and-yellow Lichen Moth",
    "Alypia octomaculata": "Eight-spotted Forester",
    "Gnophaela vermiculata": "Police Car Moth",
    "Feltia jaculifera": "Dingy Cutworm",
    "Anagrapha falcifera": "Celery Looper",
    "Schinia arcigera": "Arcigera Flower Moth",
    "Bombylius major": "Large Bee Fly",
    "Bombus kirbiellus": "High Country Bumble Bee",
    "Bombus vancouverensis": "Vancouver Bumble Bee",
    "Lygus lineolaris": "Tarnished Plant Bug",
    "Diabrotica undecimpunctata": "Spotted Cucumber Beetle",
    "Trichodes ornatus": "Ornate Checkered Beetle",
    "Dolichovespula arenaria": "Aerial Yellowjacket",
    "Dolichovespula maculata": "Bald-faced Hornet",
    "Dolichovespula arctica": "Arctic Yellowjacket",
    "Polistes fuscatus": "Northern Paper Wasp",
    "Sphex ichneumoneus": "Great Golden Digger Wasp",
    "Bembix americana": "American Sand Wasp",
    "Toxomerus geminatus": "Eastern Calligrapher",
    "Eristalis dimidiata": "Black-shouldered Drone Fly",
}


def report() -> dict:
    short = _shortlist()
    by = collections.defaultdict(list)
    for name, taxon, edges, nat in short:
        v, reason = verdict_for(name)
        by[v].append((name, taxon, edges, reason))
    return {"shortlist": short, "by": by}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true",
                    help="write the included animals into fauna_master.json")
    args = ap.parse_args()

    r = report()
    for v in ("include", "hold", "reject"):
        rows = sorted(r["by"].get(v, []), key=lambda t: -t[2])
        edges = sum(t[2] for t in rows)
        print(f"\n{v.upper()}  {len(rows)} species, {edges} candidate edges")
        for name, taxon, n, reason in rows[:40]:
            print(f"  {n:4d}  {taxon:13s} {name}")
        if len(rows) > 40:
            print(f"        … and {len(rows) - 40} more")

    named = verdicts()
    with_common = sum(1 for k in named if k in COMMON_NAMES)
    print("\n" + "=" * 64)
    print(f"  {len(named)} animals would be written")
    print(f"    {with_common} have an accepted English name")
    print(f"    {len(named) - with_common} keep their binomial, which for a "
          f"solitary bee is the name")
    print("=" * 64)

    if args.apply:
        path = os.path.join(_DATA, "fauna_master.json")
        rows = _rows(path)
        have = {r["scientific_name"] for r in rows
                if isinstance(r, dict) and r.get("scientific_name")}
        new = [row for name, row in sorted(named.items()) if name not in have]
        if new:
            rows.extend(new)
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(rows, fh, indent=1, ensure_ascii=False)
            print(f"\nwrote {len(new)} fauna rows into "
                  f"{os.path.relpath(path, _ROOT)}")
        else:
            print("\nevery included animal is already in fauna_master.json.")
        # NOT under the `if new` — returning early here skipped the attribute
        # rows entirely on a second run, which is exactly when they were added.
        # Lepidoptera need a `kind` or the scene cannot tell a butterfly from
        # a moth — three tests caught that within a minute of the first apply.
        lp = os.path.join(_DATA, "lepidoptera_attributes_master.json")
        lrows = _rows(lp)
        lhave = {r.get("scientific_name") for r in lrows}
        lnew = [r for r in lep_attributes()
                if r["scientific_name"] not in lhave]
        if lnew:
            lrows.extend(lnew)
            with open(lp, "w", encoding="utf-8") as fh:
                json.dump(lrows, fh, indent=1, ensure_ascii=False)
            print(f"wrote {len(lnew)} lepidoptera_attributes rows")
        print("NEXT: python3 scripts/ingest_fauna_edges.py --apply, then bump "
              "_SCHEMA_VERSION.")
    else:
        print("\n(report only — re-run with --apply to write)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""
scripts/curate_new_fauna.py — the held animals, read by hand.

Two passes. **V2.63** read the top 200 by edge count (`REVIEWED`); **V2.64**
read the 980 that remained (`REVIEWED_TAIL`). One set of tables serves both,
because a genus rule written while looking at the top of the list is the same
rule at the bottom of it.

**Dev-time, offline.** Run it to read the table. It writes the fauna rows;
`ingest_fauna_edges.py` then writes the edges, and the two meet in
:func:`writable`, which asks the real gates which animals will actually get
one. (Unlike `curate_birds.py`, this file is *not* imported by the ingest
gate — an animal it holds is refused by simply never being written, and the
edge has nowhere to attach.)

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

Why the top 200 first
---------------------
The edges are concentrated, so the first pass could be bounded:

    top  100 species → 2,693 of 6,664 edges (40%)
    top  200 species → 3,864 (57%)
    all 1,252        → 6,664

200 covered well over half the value for an afternoon's reading, and the tail
was held rather than admitted, because "probably fine" is not what this
catalogue claims about a documented edge.

And the tail (V2.64)
--------------------
1,052 species, 2,800 edges — and a **different problem**, not more of the
same. The median tail species carries two edges and 457 carry exactly one, so
there is no shortlist to take: it is read whole or not at all. 572 of its 609
genera had no rule.

What changes with it is the *kind* of relationship. In the top 200, `nectar`
outnumbers `larval_host` ten to one. In the tail, host records are nearly a
quarter of the edges and the animals behind them are leaf miners, gall
formers, seedhead flies, aphids and sap feeders rather than pollinators. That
is the food web underneath the flowers, and it is worth having — but it makes
the question per animal a second one. Not only *is it native*, but *is this a
relationship where the plant gives something*, which for an ambush bug, a crab
spider or a darner it is not.

Two structural exclusions fall out of it, both in `REVIEWED_TAIL`'s note:
**birds** belong to `curate_birds.py` and **trinomials** cannot be rows.

Genus defaults, species overrides
---------------------------------
**Because that is the shape of the knowledge.** For *Syrphus* or *Hylaeus* I
can say with confidence that the genus is well represented across the prairies
and cannot place every species; for *Bombus* I can place most species
individually. Writing 200 independent calls would imply a uniform confidence
that does not exist. A genus rule that is wrong is wrong visibly, in one line,
for every species under it.

The tail made that the only workable shape: 580 genus rules and 98 species
overrides decide 1,180 animals, and reading the rules is a job of an hour.

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
#: The exact 980 species the V2.64 tail review covered, pinned.
#:
#: `REVIEWED` above is a *slice* — top 200 by edge count — and pinning it
#: stopped the window sliding. This one is not a slice: it is everything that
#: survived the gates and was not already read. It still gets pinned, for a
#: different reason. A re-fetch adds species, and an unpinned list would let
#: them arrive already marked as reviewed, inheriting a genus rule written
#: while looking at some other animal.
#:
#: **Two things are deliberately NOT in here.**
#:
#: *Birds*, because `scripts/curate_birds.py` decides birds and the ingest
#: gate reads that table, not this one. All 30 birds in the tail were already
#: in it — 13 included, 6 held, 11 rejected — and the included ones have no
#: row only because every one of their records failed the diet routing. Two
#: tables that can disagree about the same animal is worse than one.
#:
#: *Trinomials* — 42 of them — because the catalogue keys fauna on binomials,
#: so a subspecies row resolves against nothing. `verdict_for` refuses them
#: structurally rather than one line at a time.
REVIEWED_TAIL = (
    "Acalymma vittatum",
    "Acanthoscelidius acephalus",
    "Aceria dispar",
    "Aceria kiefferi",
    "Acleris celiana",
    "Acleris cornana",
    "Acmaeodera pulchella",
    "Acraspis quercushirta",
    "Acronicta fragilis",
    "Acronicta hasta",
    "Acronicta impleta",
    "Acronicta impressa",
    "Acronicta insita",
    "Acronicta oblinita",
    "Acronicta radcliffei",
    "Acronicta vulpina",
    "Aculus tetanothrix",
    "Acyrthosiphon macrosiphum",
    "Adalia bipunctata",
    "Adejeania vexatrix",
    "Adela septentrionella",
    "Adelges cooleyi",
    "Adelges lariciatus",
    "Adelphocoris lineolatus",
    "Adelphocoris rapidus",
    "Aeshna umbrosa",
    "Agalliopsis ancistra",
    "Agapostemon femoratus",
    "Ageniella accepta",
    "Agriades aquilo",
    "Agrilus anxius",
    "Agrilus cyanescens",
    "Agriphila ruricolellus",
    "Agromyza pseudoreptans",
    "Agromyza vockerothi",
    "Agrotis ipsilon",
    "Agrotis venerabilis",
    "Albuna pyramidalis",
    "Allograpta obliqua",
    "Alydus pilosulus",
    "Amblyptilia pica",
    "Amblyscirtes vialis",
    "Ammophila aberti",
    "Ammophila procera",
    "Amphigonalia gothica",
    "Amphipoea americana",
    "Anania funebris",
    "Anania tertialis",
    "Anarta nigrolunata",
    "Anasimyia bilinearis",
    "Anastoechus barbatus",
    "Anastrangalia laetifica",
    "Andrena astragali",
    "Andrena auricoma",
    "Andrena birtwelli",
    "Andrena caerulea",
    "Andrena canadensis",
    "Andrena carolina",
    "Andrena clarkella",
    "Andrena columbiana",
    "Andrena cressonii",
    "Andrena cyanophila",
    "Andrena erythrogaster",
    "Andrena forbesii",
    "Andrena frigida",
    "Andrena helianthi",
    "Andrena hippotes",
    "Andrena knuthiana",
    "Andrena lawrencei",
    "Andrena mariae",
    "Andrena medionitens",
    "Andrena melanochroa",
    "Andrena merriami",
    "Andrena microchlora",
    "Andrena nigrihirta",
    "Andrena persimulata",
    "Andrena porterae",
    "Andrena quintiliformis",
    "Andrena robervalensis",
    "Andrena rufosignata",
    "Andrena salictaria",
    "Andrena schuhi",
    "Andrena sigmundi",
    "Andrena sladeni",
    "Andrena sola",
    "Andrena subtilis",
    "Andrena surda",
    "Andrena topazana",
    "Andrena transnigra",
    "Andrena trevoris",
    "Andrena w-scripta",
    "Andrena wheeleri",
    "Androloma maccullochii",
    "Anisosticta bitriangularis",
    "Anoplius virginiensis",
    "Anthaxia inornata",
    "Antherophagus ochraceus",
    "Anthidiellum robertsoni",
    "Anthidium atrifrons",
    "Anthidium mormonum",
    "Anthidium tenuiflorae",
    "Anthidium utahense",
    "Anthocharis julia",
    "Anthocharis sara",
    "Anthonomus quadrigibbus",
    "Anthonomus signatus",
    "Anthophora pacifica",
    "Anthophora urbana",
    "Anthophora walshii",
    "Anthrax irroratus",
    "Anthrenus lepidus",
    "Anthrenus scrophulariae",
    "Anthrenus verbasci",
    "Apamea inordinata",
    "Apamea unanimis",
    "Aphilanthops frigidus",
    "Aphis nerii",
    "Apiomerus spissipes",
    "Archips cerasivorana",
    "Argynnis hydaspe",
    "Argynnis idalia",
    "Argynnis mormonia",
    "Asemosyrphus polygrammus",
    "Ashmeadiella cactorum",
    "Ashmeadiella californica",
    "Asteromyia carbonifera",
    "Asteromyia modesta",
    "Atalopedes campestris",
    "Atrichopogon fusculus",
    "Atrytonopsis hianna",
    "Aulagromyza cornigera",
    "Autographa californica",
    "Baccha cognata",
    "Bassettia flavipes",
    "Batyle ignicollis",
    "Bellamira scalaris",
    "Bembix amoena",
    "Bicyrtes ventralis",
    "Blaesodiplosis crataegifolia",
    "Blaesoxipha hunteri",
    "Blennogeneris spissipes",
    "Blepharida rhois",
    "Blera confusa",
    "Blera nigra",
    "Boisea trivittata",
    "Boloria astarte",
    "Boloria epithore",
    "Boloria freija",
    "Boloria frigga",
    "Bombus ashtoni",
    "Bombus fernaldae",
    "Bombus jonellus",
    "Bombylius pulchellus",
    "Bombylius pygmaeus",
    "Botanophila fugax",
    "Brachiacantha ursina",
    "Brachymelecta californica",
    "Brachymyrmex obscurior",
    "Brachyopa notata",
    "Brachypera zoilus",
    "Brachysomida nigripennis",
    "Bracon atrator",
    "Bradysiopsis vittigera",
    "Bromius obscurus",
    "Buprestis nutalli",
    "Burnsius oileus",
    "Byturus unicolor",
    "Caenurgina crassiuscula",
    "Caenurgina erechtea",
    "Calliopsis andreniformis",
    "Calliopsis coloradensis",
    "Calliphora vomitoria",
    "Callophrys affinis",
    "Callophrys augustinus",
    "Callophrys dumetorum",
    "Callophrys eryphon",
    "Callophrys polios",
    "Callophrys sheridanii",
    "Callophrys spinetorum",
    "Calvia quatuordecimguttata",
    "Campiglossa albiceps",
    "Campiglossa picciola",
    "Camponotus novaeboracensis",
    "Carterocephalus skada",
    "Catocala concumbens",
    "Ceratina acantha",
    "Ceratomia undulosa",
    "Cerceris deserta",
    "Cerceris nigrescens",
    "Cerceris sexta",
    "Cercyonis oetus",
    "Cercyonis sthenele",
    "Chaitophorus populicola",
    "Chaitophorus populifolii",
    "Chalcosyrphus curvaria",
    "Chalcosyrphus nemorum",
    "Chalcosyrphus piger",
    "Chalcosyrphus vecors",
    "Charadra deridens",
    "Cheilosia latrans",
    "Chionaspis pinifoliae",
    "Chionodes viduella",
    "Chirosia betuleti",
    "Chlorochlamys chloroleucaria",
    "Chlosyne acastus",
    "Chlosyne gorgone",
    "Chlosyne harrisii",
    "Chlosyne palla",
    "Choreutis diana",
    "Choreutis pariana",
    "Choristoneura fumiferana",
    "Choristoneura pinus",
    "Choristoneura rosaceana",
    "Chrysis iris",
    "Chrysochus auratus",
    "Chrysochus cobaltinus",
    "Chrysopa oculata",
    "Chrysops sackeni",
    "Chrysoteuchia topiarius",
    "Cimbex americana",
    "Cingilia catenaria",
    "Cladara limitaria",
    "Clastoptera proteus",
    "Clemensia albata",
    "Climaciella brunnea",
    "Clusia lateralis",
    "Clytus ruricola",
    "Coccinella transversoguttata",
    "Coccinella trifasciata",
    "Coelioxys edita",
    "Coelioxys funerarius",
    "Coelioxys grindeliae",
    "Coelioxys octodentatus",
    "Coelioxys porterae",
    "Coelioxys sodalis",
    "Coenophila opacifrons",
    "Colias alexandra",
    "Colias christina",
    "Colias hecla",
    "Colias nastes",
    "Colias palaeno",
    "Colletes compactus",
    "Colletes consors",
    "Colletes gypsicolens",
    "Colletes phaceliae",
    "Colletes simulans",
    "Conocephalus saltans",
    "Conophorus columbiensis",
    "Conophorus sackenii",
    "Contarinia virginianiae",
    "Conura torvina",
    "Copestylum comstocki",
    "Copestylum satur",
    "Copestylum vittatum",
    "Corimelaena pulicaria",
    "Coriomeris humilis",
    "Cortodera longicornis",
    "Cortodera subpilosa",
    "Corythucha cydoniae",
    "Corythucha morrilli",
    "Cosmopepla lintneriana",
    "Cosmosalia chrysocoma",
    "Crambodes talidiformis",
    "Crambus girardellus",
    "Crambus unistriatellus",
    "Criorhina nigriventris",
    "Crossidius coralinus",
    "Crossidius discoideus",
    "Crossidius pulchellus",
    "Cucullia convexipennis",
    "Cuerna alpina",
    "Cycnia tenera",
    "Cynomya cadaverina",
    "Cyrtophorus verrucosus",
    "Danaus gilippus",
    "Dargida diffusa",
    "Dasineura epilobii",
    "Dasineura folliculi",
    "Dasysyrphus venustus",
    "Datana perspicua",
    "Dejongia lobidactylus",
    "Desmia funeralis",
    "Diabrotica virgifera",
    "Diachrysia aereoides",
    "Diacme adipaloides",
    "Dianthidium curvatum",
    "Dianthidium pudicum",
    "Dianthidium ulkei",
    "Diastrophus turgidus",
    "Dicerca divaricata",
    "Dicerca tenebrica",
    "Dicerca tenebrosa",
    "Dichelonyx backii",
    "Dioxyna picciola",
    "Diplolepis bassetti",
    "Diplolepis bicolor",
    "Diplolepis spinosa",
    "Diploschizia impigritella",
    "Dolerus aprilis",
    "Dolichovespula albida",
    "Dolichovespula norvegicoides",
    "Drasteria adumbrata",
    "Drasteria hudsonica",
    "Drasteria petricola",
    "Druon ignotum",
    "Dufourea marginata",
    "Dufourea trochantera",
    "Dysstroma citrata",
    "Ectemnius arcuatus",
    "Ectemnius continuus",
    "Ectemnius dilectus",
    "Ectemnius lapidarius",
    "Ectemnius maculosus",
    "Ectemnius ruficornis",
    "Ectemnius rufifemur",
    "Ectemnius spiniferus",
    "Ectoedemia populella",
    "Ectropis crepuscularia",
    "Elachiptera costata",
    "Ellychnia corrusca",
    "Elophila icciusalis",
    "Emmelina monodactyla",
    "Enallagma civile",
    "Enargia fausta",
    "Enchenopa latipes",
    "Eosphoropteryx thyatyroides",
    "Epeoloides pilosulus",
    "Epeolus olympiellus",
    "Epiblema scudderiana",
    "Epicauta ferruginea",
    "Epicauta pensylvanica",
    "Epicauta puncticollis",
    "Epicauta sericans",
    "Epirrhoe alternata",
    "Epistrophe xanthostoma",
    "Epistrophella emarginata",
    "Epuraea aestiva",
    "Epuraea truncatella",
    "Erebia discoidalis",
    "Erebia epipsodea",
    "Erebia vidleri",
    "Eriophyes emarginatae",
    "Eristalinus aeneus",
    "Eristalis anthophorina",
    "Eristalis obscura",
    "Erynnis afranius",
    "Erynnis brizo",
    "Erynnis icelus",
    "Erynnis juvenalis",
    "Erynnis pacuvius",
    "Erynnis persius",
    "Erynnis propertius",
    "Estigmene acrea",
    "Etorofus obliteratus",
    "Euaresta aequalis",
    "Eucera acerba",
    "Eucera atriventris",
    "Eucera douglasiana",
    "Eucera frater",
    "Eucera hamata",
    "Eucerceris cressoni",
    "Euchlaena marginaria",
    "Euchloe ausonides",
    "Euchloe creusa",
    "Euchloe olympia",
    "Eucirroedia pampina",
    "Euclidia ardita",
    "Euclidia cuspidea",
    "Eudasyphora cyanicolor",
    "Euhexomyza schineri",
    "Eumea caesar",
    "Eumenes crucifera",
    "Eumerus strigatus",
    "Euodynerus annulatus",
    "Euodynerus hidalgo",
    "Euodynerus pratensis",
    "Eupeodes fumipennis",
    "Eupeodes latifasciatus",
    "Eupeodes perplexus",
    "Eupeodes snowi",
    "Euphilotes battoides",
    "Euphydryas chalcedona",
    "Euphydryas colon",
    "Euphydryas editha",
    "Euphydryas gillettii",
    "Euphyia intermediata",
    "Euplexia benesimilis",
    "Eupsilia tristigmata",
    "Eurimyia stipatus",
    "Eurosta solidaginis",
    "Eurytides marcellus",
    "Eusarca confusaria",
    "Eusphalerum pothos",
    "Eutreta diana",
    "Euxoa auxiliaris",
    "Euxoa catenula",
    "Euxoa detersa",
    "Evagetes parvus",
    "Evergestis pallidata",
    "Exoprosopa decora",
    "Exoprosopa dorcadion",
    "Exoprosopa doris",
    "Exoprosopa eremita",
    "Exoprosopa fascipennis",
    "Exorista mella",
    "Fannia ungulata",
    "Feniseca tarquinius",
    "Feralia comstocki",
    "Formica fusca",
    "Formica obscuripes",
    "Formica obtusopilosa",
    "Frankliniella tritici",
    "Fumibotys fumalis",
    "Geina tenuidactylus",
    "Gesneria centuriella",
    "Gillmeria pallidactyla",
    "Glaucopsyche piasus",
    "Gnathacmaeops pratensis",
    "Gnophaela clappiana",
    "Gnophaela latipennis",
    "Gnorimoschema octomaculella",
    "Gorytes simillimus",
    "Grammoptera subargentata",
    "Graphiphora augur",
    "Graphocephala coccinea",
    "Habropoda cineraria",
    "Halictus virgatellus",
    "Halysidota tessellaris",
    "Hammerschmidtia rufa",
    "Haploa confusa",
    "Haploa lecontei",
    "Harmostes reflexulus",
    "Hedriodiscus binotatus",
    "Helina evecta",
    "Heliothis phloxiphaga",
    "Helophilus hybridus",
    "Helophilus lapponicus",
    "Hemadas nubilipennis",
    "Hemaris gracilis",
    "Hemaris thetis",
    "Hemileuca nevadensis",
    "Hemipenthes morioides",
    "Heriades variolosa",
    "Herpetogramma abdominalis",
    "Herpetogramma aquilonalis",
    "Herpetogramma pertextalis",
    "Herpetogramma thestealis",
    "Hesperia dacotae",
    "Hesperia juba",
    "Hesperia uncas",
    "Heterogaster behrensii",
    "Hippodamia parenthesis",
    "Holcopasites calliopsidis",
    "Holopyga ventralis",
    "Homoeosoma electella",
    "Hoplitis grinnelli",
    "Hoplitis pilosifrons",
    "Hoplitis robusta",
    "Hoplitis sambuci",
    "Hoplitis spoliata",
    "Hoplitis truncata",
    "Hydria undulata",
    "Hylaeus affinis",
    "Hylaeus leptocephalus",
    "Hylaeus verticalis",
    "Hyles gallii",
    "Hypena humuli",
    "Hypena scabra",
    "Hyperaspis undulata",
    "Hyphantria cunea",
    "Hypocritanus fascipennis",
    "Hystricia abrupta",
    "Icaricia lupini",
    "Idaea dimidiata",
    "Ischnura verticalis",
    "Ischnus inquisitorius",
    "Isodontia elegans",
    "Isodontia mexicana",
    "Isophrictis similiella",
    "Janus abbreviatus",
    "Judolia instabilis",
    "Judolia montivagans",
    "Lacinipolia olivacea",
    "Lacinipolia renigera",
    "Lampronia russatella",
    "Laphria fernaldi",
    "Lapposyrphus aberrantis",
    "Lapposyrphus lapponicus",
    "Larinus obtusus",
    "Lasioglossum acuminatum",
    "Lasioglossum aff.nevadense",
    "Lasioglossum albohirtum",
    "Lasioglossum anhypops",
    "Lasioglossum athabascense",
    "Lasioglossum brunneiventre",
    "Lasioglossum buccale",
    "Lasioglossum colatum",
    "Lasioglossum cooleyi",
    "Lasioglossum coriaceum",
    "Lasioglossum dashwoodi",
    "Lasioglossum egregium",
    "Lasioglossum glabriventre",
    "Lasioglossum kincaidii",
    "Lasioglossum laevissimum",
    "Lasioglossum lineatulum",
    "Lasioglossum macroprosopum",
    "Lasioglossum mellipes",
    "Lasioglossum novascotiae",
    "Lasioglossum nr.pavoninum",
    "Lasioglossum obnubilum",
    "Lasioglossum occidentale",
    "Lasioglossum ovaliceps",
    "Lasioglossum pacatum",
    "Lasioglossum paraforbesii",
    "Lasioglossum pectorale",
    "Lasioglossum pilosum",
    "Lasioglossum prasinogaster",
    "Lasioglossum punctatoventre",
    "Lasioglossum quebecense",
    "Lasioglossum sandhousiellum",
    "Lasioglossum sedi",
    "Lasioglossum semicaeruleum",
    "Lasioglossum succinipenne",
    "Lasioglossum trizonatum",
    "Lasioglossum versans",
    "Lasioglossum zephyrum",
    "Lasius neoniger",
    "Lebia viridis",
    "Lepidosaphes ulmi",
    "Leptinotarsa decemlineata",
    "Leptometopa latipes",
    "Lepturobosca chrysocoma",
    "Lestes congener",
    "Lethe anthedon",
    "Lethe eurydice",
    "Leucoptera pachystimella",
    "Leucospis affinis",
    "Leucozona americana",
    "Limenitis lorquini",
    "Limnophora narona",
    "Limochores sonora",
    "Lindenius columbianus",
    "Liriomyza eupatorii",
    "Liriomyza galiivora",
    "Liris argentatus",
    "Lispe uliginosa",
    "Listronotus appendiculatus",
    "Lithophane bethunei",
    "Lithophane fagina",
    "Lobophora nivigerata",
    "Lomographa semiclarata",
    "Lomographa vestaliata",
    "Lopidea instabilis",
    "Lucidota atra",
    "Lucilia illustris",
    "Lucilia silvarum",
    "Lycaena cupreus",
    "Lycaena heteronea",
    "Lycaena snowi",
    "Lygaeus kalmii",
    "Lygus rufidorsus",
    "Lyroda subita",
    "Macaria truncataria",
    "Macropis nuda",
    "Macrosiphum albifrons",
    "Malachius aeneus",
    "Malacosoma americana",
    "Malacosoma californica",
    "Malacosoma disstria",
    "Mallota bautias",
    "Mallota posticata",
    "Marmara oregonensis",
    "Mecaphesa asperata",
    "Mecaphesa celer",
    "Megachile angelarum",
    "Megachile apicalis",
    "Megachile brevis",
    "Megachile centuncularis",
    "Megachile fidelis",
    "Megachile gemula",
    "Megachile inermis",
    "Megachile lapponica",
    "Megachile montivaga",
    "Megachile nivalis",
    "Megachile parallela",
    "Megachile rotundata",
    "Megachile subnigra",
    "Megachile texana",
    "Megachile wheeleri",
    "Megacyllene robiniae",
    "Megasyrphus laxus",
    "Megisto cymela",
    "Melanchra assimilis",
    "Melangyna lasiophthalma",
    "Melanoplus bivittatus",
    "Melanoplus femurrubrum",
    "Melanoplus infantilis",
    "Melanostoma mellina",
    "Melecta thoracica",
    "Meliscaeva cinctella",
    "Melissodes agilis",
    "Melissodes bimatris",
    "Melissodes communis",
    "Melissodes lupinus",
    "Melissodes menuachus",
    "Melissodes pallidisignatus",
    "Melissodes rivalis",
    "Melissodes subagilis",
    "Melissodes utahensis",
    "Merodon equestris",
    "Mesembrina latreillii",
    "Mesoleuca gratulata",
    "Mesoleuca ruficillata",
    "Metallus capitalis",
    "Microdon cothurnatus",
    "Microrhopala vittata",
    "Misumena vatia",
    "Mitoura gryneus",
    "Molorchus bimaculatus",
    "Mompha raschkiella",
    "Mompha unifasciella",
    "Mordellina pustulata",
    "Mordellistena cervicalis",
    "Mordellistena ornata",
    "Mordwilkoja vagabunda",
    "Morellia micans",
    "Muscina stabulans",
    "Myopa clausa",
    "Myospila meditabunda",
    "Mythimna unipuncta",
    "Neokolla hieroglyphica",
    "Neomyia cornicina",
    "Neoneides muticus",
    "Neophasia menapia",
    "Neorhynchocephalus sackenii",
    "Neoscona arabesca",
    "Nephelodes minians",
    "Nephrotoma ferruginea",
    "Neurocolpus nubilus",
    "Nitops pallipennis",
    "Nomada crotchii",
    "Nomada cuneata",
    "Nomada texana",
    "Nomia melanderi",
    "Nomophila nearctica",
    "Notodonta torva",
    "Nycteola cinereana",
    "Nymphalis californica",
    "Nysson plagiatus",
    "Oarisma garita",
    "Odynerus dilectus",
    "Oecanthus californicus",
    "Oecanthus nigricornis",
    "Oeneis chryxus",
    "Oeneis melissa",
    "Oeneis uhleri",
    "Oiceoptoma noveboracense",
    "Okanagana bella",
    "Olcella trigramma",
    "Orchestes mixtus",
    "Oreana unicolorella",
    "Orgyia leucostigma",
    "Orphilus subnitidus",
    "Orsodacne atra",
    "Orthocladius oblidens",
    "Orthonevra pulchella",
    "Orthosia hibisci",
    "Osmia aff.paradisica",
    "Osmia atriventris",
    "Osmia atrocyanea",
    "Osmia bella",
    "Osmia brevis",
    "Osmia bruneri",
    "Osmia calla",
    "Osmia cyanella",
    "Osmia exigua",
    "Osmia inermis",
    "Osmia integra",
    "Osmia kincaidii",
    "Osmia longula",
    "Osmia malina",
    "Osmia marginipennis",
    "Osmia nanula",
    "Osmia nigriventris",
    "Osmia odontogaster",
    "Osmia paradisica",
    "Osmia proxima",
    "Osmia simillima",
    "Osmia subaustralis",
    "Osmia tersula",
    "Otiorhynchus ovatus",
    "Otiorhynchus raucus",
    "Oxybelus emarginatus",
    "Oxybelus uniglumis",
    "Pachydiplax longipennis",
    "Pachypappa sacculi",
    "Palpada meigenii",
    "Palthis angulalis",
    "Panurginus atriceps",
    "Panurginus ineptus",
    "Paonias excaecata",
    "Paonias myops",
    "Papilio multicaudata",
    "Paraclemensia acerifoliella",
    "Paragus haemorrhous",
    "Paraleucoptera albella",
    "Paramyia nitens",
    "Paranthrene robiniae",
    "Parasyrphus relictus",
    "Paravilla separata",
    "Parhelophilus laetus",
    "Parhelophilus obsoletus",
    "Parhelophilus rex",
    "Parnassius clodius",
    "Parnassius smintheus",
    "Pelegrina galathea",
    "Peleteria anaxias",
    "Pemphredon inornata",
    "Pennisetia marginatum",
    "Pentaria trifasciata",
    "Perdita albipennis",
    "Perdita fallax",
    "Perdita nevadensis",
    "Perdita octomaculata",
    "Perdita perpallida",
    "Perdita swenki",
    "Peridroma saucia",
    "Phaeolita pyramusalis",
    "Phalaenophana pyramusalis",
    "Phalangium opilio",
    "Phaonia serva",
    "Phasia robertsonii",
    "Phidippus audax",
    "Phidippus johnsoni",
    "Philaenus spumarius",
    "Philanthus bilunatus",
    "Philanthus crabroniformis",
    "Philanthus multimaculatus",
    "Philanthus politus",
    "Philanthus sanbornii",
    "Philanthus solivagus",
    "Pholisora catullus",
    "Phormia regina",
    "Phyciodes batesii",
    "Phyciodes pulchella",
    "Phyllobius oblongus",
    "Phyllocnistis populiella",
    "Phyllonorycter anderidae",
    "Phyllonorycter apparella",
    "Phyllonorycter ledella",
    "Phyllonorycter nipigon",
    "Phymata americana",
    "Physiphora alceae",
    "Physocephala burgessi",
    "Physocephala texana",
    "Physoconops obscuripennis",
    "Phytomyza agromyzina",
    "Pidonia scripta",
    "Pieris angelika",
    "Pieris marginalis",
    "Pieris napi",
    "Pimpla pedalis",
    "Pipiza femoralis",
    "Pipiza quadrimaculata",
    "Plagiognathus obscurus",
    "Plateumaris nitida",
    "Plateumaris shoemakeri",
    "Platycheirus rosarum",
    "Platycheirus stegnus",
    "Plebejus anna",
    "Plebejus idas",
    "Plebejus saepiolus",
    "Plutella xylostella",
    "Podalonia robusta",
    "Podisus maculiventris",
    "Podosesia syringae",
    "Poecilanthrax tegminipennis",
    "Poecilognathus sulphureus",
    "Polia purpurissata",
    "Polistes aurifer",
    "Polites sabuleti",
    "Pollenia pediculata",
    "Pollenia rudis",
    "Polydontomyia curvipes",
    "Polydrusus formosus",
    "Polygonia faunus",
    "Polygonia gracilis",
    "Polygonia interrogationis",
    "Polygonia progne",
    "Polygonia satyrus",
    "Polygonia zephyrus",
    "Ponana pectoralis",
    "Ponometia candefacta",
    "Pontia beckerii",
    "Prionyx atratus",
    "Prionyx canadensis",
    "Pristiphora appendiculata",
    "Prochoerodes lineola",
    "Prociphilus tessellatus",
    "Proserpinus clarkiae",
    "Protandrena albitarsis",
    "Pseudanarta crocea",
    "Pseudanarta flava",
    "Pseudepipona aldrichi",
    "Pseudochrysis neglecta",
    "Pseudodynerus quadrisectus",
    "Pseudogaurotina cressoni",
    "Pseudohermonassa bicarnea",
    "Pseudomasaris vespoides",
    "Pseudopanurgus albitarsis",
    "Pseudopanurgus parvus",
    "Pseudothyris sepulchralis",
    "Psilocorsis reflexella",
    "Pterocheilus quinquefasciatus",
    "Pterocomma salicis",
    "Purpuricenus humeralis",
    "Pyrausta subsequalis",
    "Pyrgus centaureae",
    "Pyrgus ruralis",
    "Pyrisitia lisa",
    "Pyrophaena rosarum",
    "Rabdophaga rigidae",
    "Rabdophaga salicisbrassicoides",
    "Rabdophaga strobiloides",
    "Renia flavipunctalis",
    "Rheumaptera hastata",
    "Rhingia nasica",
    "Rhopalomyia capitata",
    "Rhopalomyia chrysothamni",
    "Rhopalomyia medusa",
    "Rhopalomyia medusirrasa",
    "Rhopalomyia obovata",
    "Rhopalomyia pomum",
    "Rhopalomyia utahensis",
    "Rhopalosiphum padi",
    "Rhyparochromus vulgaris",
    "Rivula propinqualis",
    "Saperda populnea",
    "Sarcophaga nearctica",
    "Sarcophaga sinuata",
    "Satyrium acadica",
    "Satyrium behrii",
    "Satyrium calanus",
    "Satyrium californica",
    "Satyrium edwardsii",
    "Satyrium favonius",
    "Satyrium fuliginosa",
    "Satyrium liparops",
    "Satyrium saepium",
    "Satyrium sylvinus",
    "Saucrobotys futilalis",
    "Scaeva affinis",
    "Scathophaga furcata",
    "Scathophaga stercoraria",
    "Sceliphron caementarium",
    "Scelolyperus varipes",
    "Schinia florida",
    "Schinia gaurae",
    "Schinia persimilis",
    "Schinia walsinghami",
    "Schizura concinna",
    "Scoliopteryx libatrix",
    "Scopula junctaria",
    "Scudderia furcata",
    "Scythris trivinctella",
    "Semioscopis inornata",
    "Senotainia trilineata",
    "Sericomyia chalcopyga",
    "Sericomyia lata",
    "Sericomyia militaris",
    "Sericomyia transversa",
    "Sitona hispidulus",
    "Speyeria adiaste",
    "Speyeria callippe",
    "Speyeria edwardsii",
    "Speyeria hesperis",
    "Speyeria zerene",
    "Sphaerophoria sulphuripes",
    "Sphecodes pecosensis",
    "Sphecomyia pattonii",
    "Sphecomyia vittata",
    "Sphenometopa tergata",
    "Sphex lucae",
    "Spilomyia sayi",
    "Spilosoma virginica",
    "Stamoderes lanei",
    "Stelis aff.permaculata",
    "Stelis calliphorina",
    "Stelis coarctatus",
    "Stelis foederalis",
    "Stelis lateralis",
    "Stelis monticola",
    "Stelis permaculata",
    "Stictoleptura canadensis",
    "Stigmella populetorum",
    "Stizoides renicinctus",
    "Stomoxys calcitrans",
    "Stratiomys badia",
    "Stratiomys normula",
    "Strongygaster triangulifera",
    "Strymon saepium",
    "Strymon sylvinus",
    "Sunira bicolorago",
    "Symmorphus albomarginatus",
    "Symmorphus canadensis",
    "Symmorphus cristatus",
    "Sympetrum vicinum",
    "Sympistis augustus",
    "Synanthedon albicornis",
    "Synanthedon bibionipennis",
    "Synanthedon exitiosa",
    "Synanthedon pictipes",
    "Synanthedon polygoni",
    "Synchlora aerata",
    "Syngrapha epigaea",
    "Syrphus vitripennis",
    "Systoechus oreas",
    "Systoechus vulgaris",
    "Tabanus punctifer",
    "Tachytes sayi",
    "Tamalia coweni",
    "Tapinoma sessile",
    "Temnostoma alternans",
    "Temnostoma venustum",
    "Tenodera sinensis",
    "Terellia occidentalis",
    "Tetracis cachexiata",
    "Tetragnatha extensa",
    "Thamnotettix confinis",
    "Tharsalea dione",
    "Tharsalea dorcas",
    "Tharsalea editha",
    "Tharsalea heteronea",
    "Tharsalea mariposa",
    "Tharsalea nivalis",
    "Tharsalea rubidus",
    "Thaumatomyia glabra",
    "Thecabius populimonilis",
    "Themira putris",
    "Tibellus chamberlini",
    "Toxomerus occidentalis",
    "Trachysida aspera",
    "Trachysida mutabilis",
    "Tremex columba",
    "Trichodezia albovittata",
    "Trichoplusia ni",
    "Trichopsomyia apisaon",
    "Triepeolus micropygius",
    "Triepeolus obliteratus",
    "Tritoxa flexa",
    "Tropidia quadrata",
    "Udea rubigalis",
    "Urocerus flavicornis",
    "Urophora quadrifasciata",
    "Vanessa annabella",
    "Vespula acadica",
    "Vespula alascensis",
    "Vespula atropilosa",
    "Vespula flavopilosa",
    "Vespula germanica",
    "Vespula pensylvanica",
    "Villa alternata",
    "Villa fulviana",
    "Villa hypomelas",
    "Villa lateralis",
    "Volucella bombylans",
    "Volucella facialis",
    "Xestia c-nigrum",
    "Xestia normaniana",
    "Xestia smithii",
    "Xestoleptura crassipes",
    "Xestoleptura tibialis",
    "Xylena curvimacula",
    "Xylota flavitibia",
    "Xysticus punctatus",
    "Zaira georgiae",
    "Zale minerea",
    "Zanclognatha jacchusalis",
    "Zelleria haimbachi",
    "Zonitis sayi",
)

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

    # ══════════════════════════════════════════════════════════════════
    # V2.64 — the tail. 1,052 species across 609 genera, 2,800 edges.
    #
    # A different problem from the top 200 and it needs saying: the median
    # tail species carries TWO edges and 457 carry exactly one, so this is a
    # long tail of singletons rather than a shortlist. 572 of the genera had
    # no rule at all. Everything below is a genus I can actually place;
    # everything I cannot is left out, and left out means held.
    # ══════════════════════════════════════════════════════════════════

    # ── Bees and apoid wasps ─────────────────────────────────────────────
    "Stelis": ("include", "Cuckoo bees of Osmia and Megachile — present "
               "wherever their hosts are, and their hosts are included."),
    "Nomada": ("include", "Cuckoo bees of Andrena; the same reasoning."),
    "Melecta": ("include", "Cuckoo bees of Anthophora."),
    "Holcopasites": ("include", "Cuckoo bees of Calliopsis and Pseudopanurgus."),
    "Anthophora": ("include", "Digger bees, native and widespread."),
    "Habropoda": ("include", "Digger bees, western."),
    "Perdita": ("include", "Tiny ground-nesting bees, strongly western and "
                "dry-country — prairie-typical."),
    "Panurginus": ("include", "Small andrenid bees, western."),
    "Pseudopanurgus": ("include", "Small andrenid bees, composite "
                       "specialists."),
    "Calliopsis": ("include", "Andrenid bees of open sandy ground."),
    "Dufourea": ("include", "Short-season halictid specialists, northern."),
    "Macropis": ("include", "Oil-collecting bees on Lysimachia — a genuine "
                 "wetland specialist here."),
    "Anthidium": ("include", "Wool carder bees. The native species are "
                  "prairie-typical; the European A. manicatum is refused."),
    "Ectemnius": ("include", "Crabronid wasps, native wood-nesters."),
    "Cerceris": ("include", "Weevil wasps, sand-country natives."),
    "Ammophila": ("include", "Thread-waisted wasps, native and conspicuous."),
    "Prionyx": ("include", "Grasshopper-hunting wasps, prairie natives."),
    "Oxybelus": ("include", "Fly-hunting crabronids, sand country."),
    "Bicyrtes": ("include", "Sand wasps, native."),
    "Aphilanthops": ("include", "Ant-hunting wasps, native."),
    "Lyroda": ("include", "Small crabronid wasps."),
    "Nysson": ("include", "Cuckoo wasps of other crabronids."),
    "Liris": ("include", "Cricket-hunting wasps."),
    "Sceliphron": ("include", "Mud daubers. S. caementarium is native to "
                   "North America despite being cosmopolitan now."),
    "Isodontia": ("include", "Grass-carrying wasps, native — see also the "
                  "V2.62 review, which corrected GBIF on this genus."),
    "Brachymelecta": ("hold", "A rare cleptoparasite genus whose North "
                      "American taxonomy has been rearranged; I cannot place "
                      "the species here."),

    # ── Butterflies ──────────────────────────────────────────────────────
    "Satyrium": ("include", "Hairstreaks — shrub-thicket butterflies, well "
                 "represented across the prairies and parkland."),
    "Callophrys": ("include", "Elfins and greens — early-spring butterflies "
                   "of bog, pine and shrubland."),
    "Tharsalea": ("include", "Coppers, wet-meadow and prairie."),
    "Erynnis": ("include", "Duskywings — legume and oak feeders; several "
                "prairie species."),
    "Polygonia": ("include", "Anglewings. Alberta's are faunus, gracilis and "
                  "satyrus; the eastern P. comma is refused."),
    "Euphydryas": ("include", "Checkerspots, montane and prairie."),
    "Speyeria": ("include", "Greater fritillaries, violet feeders."),
    "Argynnis": ("include", "Fritillaries, prairie and parkland."),
    "Boloria": ("include", "Lesser fritillaries, boreal and alpine."),
    "Chlosyne": ("include", "Checkerspots and patches, composite feeders."),
    "Parnassius": ("include", "Apollos — alpine and montane, on stonecrop "
                   "and bleeding heart."),
    "Plebejus": ("include", "Blues, legume feeders across the grasslands."),
    "Euphilotes": ("include", "Buckwheat blues, dry western."),
    "Agriades": ("include", "Arctic and alpine blues."),
    "Celastrina": ("include", "Azures."),
    "Cercyonis": ("include", "Wood-nymphs, grass feeders."),
    "Erebia": ("include", "Alpines — boreal and mountain satyrs, a "
               "characteristic Alberta group."),
    "Colias": ("include", "Sulphurs, legume feeders and abundant here."),
    "Pieris": ("include", "Whites. The native ones; the European P. rapae "
               "is refused."),
    "Neophasia": ("include", "Pine White — a conifer feeder of the "
                  "foothills."),
    "Limenitis": ("include", "Admirals, willow and poplar feeders."),
    "Danaus": ("include", "Monarch, already in the catalogue at species "
               "rank."),
    "Hesperia": ("include", "Branded skippers, grassland."),
    "Pyrgus": ("include", "Checkered skippers, dry open ground."),
    "Pholisora": ("include", "Sootywings."),
    "Carterocephalus": ("include", "Arctic Skipper."),
    "Amblyscirtes": ("hold", "Roadside skippers — mostly southern; I cannot "
                     "place the species here."),
    "Atalopedes": ("hold", "Sachem — a southern skipper, at best a stray."),
    "Pyrisitia": ("reject", "Little yellows — subtropical."),

    # ── Moths ────────────────────────────────────────────────────────────
    "Acronicta": ("include", "Dagger moths — native woody-plant feeders, "
                  "well represented in the boreal and parkland."),
    "Xestia": ("include", "Native noctuids, boreal."),
    "Lacinipolia": ("include", "Native noctuids of grassland and meadow."),
    "Agrotis": ("include", "Cutworm moths, native adults that nectar "
                "heavily."),
    "Drasteria": ("include", "Native dry-country noctuids."),
    "Caenurgina": ("include", "Native forage-looper moths of grassland."),
    "Synanthedon": ("include", "Clearwing borer moths — day-flying, native, "
                    "and genuine flower visitors."),
    "Albuna": ("include", "Clearwing moths, native."),
    "Hemaris": ("include", "Hummingbird clearwings — day-flying sphinxes, "
                "conspicuous nectar feeders here."),
    "Hyles": ("include", "Sphinx moths; H. lineata is already in the "
              "catalogue."),
    "Anania": ("include", "Native pyraloid moths."),
    "Lomographa": ("include", "Native geometrids of shrubland."),
    "Trichodezia": ("include", "Native geometrid, day-flying."),
    "Adela": ("include", "Fairy moths — day-flying, on flowers, native."),
    "Autographa": ("include", "Native looper moths."),
    "Dejongia": ("include", "Plume moths."),

    # ── Flies ────────────────────────────────────────────────────────────
    "Villa": ("include", "Bee flies, native and abundant on prairie "
              "flowers."),
    "Exoprosopa": ("include", "Bee flies, dry-country natives."),
    "Poecilanthrax": ("include", "Bee flies, western."),
    "Systoechus": ("include", "Bee flies, grassland."),
    "Conophorus": ("include", "Bee flies."),
    "Hemipenthes": ("include", "Bee flies."),
    "Sericomyia": ("include", "Large hoverflies of bog and fen — northern "
                   "and characteristic."),
    "Chalcosyrphus": ("include", "Hoverflies, boreal deadwood breeders."),
    "Mallota": ("include", "Hoverflies, tree-hole breeders."),
    "Lapposyrphus": ("include", "Hoverflies, Holarctic."),
    "Volucella": ("include", "Hoverflies, nest inquilines."),
    "Meliscaeva": ("include", "Hoverflies, Holarctic."),
    "Allograpta": ("include", "Hoverflies, widespread."),
    "Scaeva": ("include", "Hoverflies, migratory and Holarctic."),
    "Rhingia": ("include", "Snout hoverflies, Holarctic."),
    "Merodon": ("reject", "Narcissus Bulb Fly. European, introduced with "
                "ornamental bulbs, and a pest of them."),
    "Cynomya": ("include", "Blow flies, native and genuine flower "
                "visitors."),
    "Phormia": ("include", "Black Blow Fly, native."),
    "Sarcophaga": ("include", "Flesh flies — unglamorous and real "
                   "pollinators."),
    "Morellia": ("include", "Muscid flies, flower visitors."),
    "Myospila": ("include", "Muscid flies."),
    "Themira": ("hold", "Sepsid flies — dung breeders whose flower records "
                "I cannot interpret."),

    # ── Beetles and other insects ────────────────────────────────────────
    "Epicauta": ("include", "Blister beetles — native, and serious flower "
                 "feeders on prairie composites."),
    "Melanoplus": ("include", "Spur-throated grasshoppers, native and the "
                   "defining prairie orthopterans."),
    "Cortodera": ("include", "Flower longhorns, native."),
    "Megacyllene": ("include", "Longhorn beetles; the goldenrod-visiting "
                    "species are native."),
    "Grammoptera": ("include", "Flower longhorns."),
    "Judolia": ("include", "Flower longhorns."),
    "Leucospis": ("include", "Leucospid wasps, parasitoids of solitary bees "
                  "and native — corrected on GBIF's origin in V2.62."),
    "Cosmopepla": ("include", "Native stink bugs."),
    "Lygaeus": ("include", "Native seed bugs, milkweed-associated."),
    "Formica": ("include", "Wood and field ants. Native, and they do take "
                "floral nectar."),
    "Tapinoma": ("include", "Odorous house ants, native."),
    "Malachius": ("reject", "M. aeneus, the Scarlet Malachite Beetle — "
                  "European, introduced to North America."),

    # ── Gall-formers. Real relationships, unglamorous ones. ──────────────
    "Rhopalomyia": ("include", "Gall midges of Artemisia and composites. "
                    "Their `hostOf` records are genuine larval-host edges — "
                    "the gall IS the relationship — and the genus is native."),
    "Asteromyia": ("include", "Gall midges of asters and goldenrods, "
                   "native."),
    "Rabdophaga": ("include", "Willow gall midges, native."),

    # ── Predators standing on flowers. A visit is not a reward. ──────────
    #
    # The sparrow problem again (V2.60). GloBI files `flowersVisitedBy` for
    # an ambush bug or a crab spider, which is a true observation of where
    # the animal was and a false statement about what the plant gave it —
    # they are there to eat the pollinators. Held rather than admitted with
    # a `nectar` edge that misdescribes them.
    "Phymata": ("hold", "Ambush bugs sit ON flowers to eat the visitors. "
                "The flower-visit record is true and the `nectar` "
                "relationship it becomes is not."),
    "Misumena": ("hold", "Goldenrod Crab Spider — same reasoning as Phymata. "
                 "Native, and a predator rather than a beneficiary."),

    # ── The rest of the bees and apoid wasps. 14 genera, 21 edges. ───────
    "Pemphredon": ("include", "Aphid wasps, native stem-nesters."),
    "Epeolus": ("include", "Cuckoo bees of Colletes, which is included."),
    "Triepeolus": ("include", "Cuckoo bees of Melissodes and Svastra."),
    "Eucerceris": ("include", "Weevil wasps, western and dry-country."),
    "Anthidiellum": ("include", "Rotund resin bees, native."),
    "Gorytes": ("include", "Crabronid wasps, native."),
    "Lindenius": ("include", "Small crabronid wasps, native."),
    "Nomia": ("include", "Alkali bees. N. melanderi nests in the saline flats "
              "of the dry southern prairies — a genuinely local specialist."),
    "Podalonia": ("include", "Thread-waisted wasps, native."),
    "Protandrena": ("include", "Small andrenid bees."),
    "Sphecodes": ("include", "Blood bees — cuckoos of the halictids, and "
                  "widespread wherever those are."),
    "Tachytes": ("include", "Sand-loving crabronid wasps, native."),
    "Stizoides": ("hold", "A cuckoo wasp of Bembix; S. renicinctus is "
                  "southwestern and I cannot place it on the prairies."),
    "Epeoloides": ("hold", "E. pilosulus is one of the rarest bees in Canada "
                   "and its records are eastern. A prairie row on one "
                   "interaction record would be a claim, not a record."),

    # ── Butterflies, the remainder ───────────────────────────────────────
    "Euchloe": ("include", "Marbles — early-spring mustard feeders; olympia, "
                "ausonides and creusa are all Alberta butterflies."),
    "Anthocharis": ("include", "Orangetips of the foothills and parkland."),
    "Oeneis": ("include", "Arctics. Grassland and alpine satyrs, and about "
               "as characteristic of Alberta as a butterfly gets."),
    "Phyciodes": ("include", "Crescents. Aster feeders; pulchella and batesii "
                  "are both prairie species."),
    "Glaucopsyche": ("include", "Arrowhead and Silvery Blues, legume "
                     "feeders of the southern grasslands."),
    "Oarisma": ("include", "Skipperlings. O. garita is a true prairie "
                "grassland skipper."),
    "Hemileuca": ("include", "Buckmoths. H. nevadensis is a willow feeder of "
                  "the southern prairies — a day-flying saturniid."),
    "Nymphalis": ("hold", "Tortoiseshells. N. californica is irruptive and "
                  "reaches Alberta in flight years; a resident row would "
                  "overstate it."),
    "Lethe": ("hold", "Eyed browns and pearly-eyes — eastern satyrs reaching "
              "Manitoba at best."),
    "Megisto": ("reject", "Little Wood-Satyr — eastern, west to Manitoba."),
    "Eurytides": ("reject", "Zebra Swallowtail. A pawpaw specialist of the "
                  "southeast; the nearest pawpaw is two thousand kilometres "
                  "away."),
    "Strymon": ("hold", "Hairstreaks. S. melinus is decided above and is the "
                "Alberta one; sylvinus and saepium are western US and BC."),
    "Mitoura": ("hold", "A superseded genus — these animals are Callophrys "
                "now. Writing a Mitoura row would put a name nobody uses "
                "beside a Callophrys row for the same insect."),
    "Atrytonopsis": ("hold", "Dusted Skipper — central and eastern; I cannot "
                     "place it here."),
    "Limochores": ("hold", "Sonora Skipper — Rockies and Pacific slope; "
                   "another recently split genus I cannot place."),
    "Feniseca": ("hold", "The Harvester, whose caterpillar eats aphids rather "
                 "than plants. The plant in this record is where the aphids "
                 "were, which is not the relationship the edge would claim."),

    # ── Moths, macro. Overwhelmingly native Nearctic or Holarctic. ───────
    "Euxoa": ("include", "Dart moths — the largest native noctuid genus on "
              "the prairies, and heavy nectar feeders as adults."),
    "Schinia": ("include", "Flower moths. Composite specialists that rest, "
                "feed and breed on the flower head."),
    "Ponometia": ("include", "Small native noctuids of ragweed and other "
                  "composites."),
    "Amphipoea": ("include", "Native noctuids of wet meadow."),
    "Apamea": ("include", "Native noctuids, grass and sedge feeders."),
    "Orthosia": ("include", "Spring noctuids, native and among the earliest "
                 "moths at willow catkins."),
    "Lithophane": ("include", "Pinions — native, and out in cold weather at "
                   "both ends of the season."),
    "Eupsilia": ("include", "Sallows, native and overwintering as adults."),
    "Sunira": ("include", "Sallows, native."),
    "Eucirroedia": ("include", "Scalloped Sallow, native."),
    "Xylena": ("include", "Swordgrass moths, native."),
    "Catocala": ("include", "Underwings — native, on willow, poplar and "
                 "rose-family shrubs."),
    "Zale": ("include", "Native noctuids of woody plants."),
    "Hypena": ("include", "Snout moths, native."),
    "Palthis": ("include", "Native litter moths."),
    "Renia": ("include", "Native litter moths."),
    "Zanclognatha": ("include", "Native litter moths."),
    "Rivula": ("include", "Spotted Grass Moth, native."),
    "Phalaenophana": ("include", "Dark-banded Owlet, native."),
    "Nephelodes": ("include", "Bronzed Cutworm, native."),
    "Melanchra": ("include", "Native noctuids."),
    "Polia": ("include", "Native noctuids."),
    "Coenophila": ("include", "Native noctuids, boreal."),
    "Graphiphora": ("include", "Holarctic noctuid, native here."),
    "Pseudohermonassa": ("include", "Native noctuids."),
    "Anarta": ("include", "Arctic and alpine noctuids, native."),
    "Sympistis": ("include", "Native noctuids of the dry and alpine west."),
    "Dargida": ("include", "Native grass-feeding noctuids."),
    "Pseudanarta": ("include", "Native western noctuids."),
    "Heliothis": ("include", "H. phloxiphaga is a native western flower moth "
                  "— not to be confused with the migratory Helicoverpa held "
                  "in the review above."),
    "Cucullia": ("include", "Hooded owlets, native composite feeders."),
    "Crambodes": ("include", "Native noctuid."),
    "Charadra": ("include", "The Laugher, native."),
    "Feralia": ("include", "Native early-spring conifer noctuids."),
    "Enargia": ("include", "Native poplar-feeding noctuids."),
    "Euplexia": ("include", "Native noctuid."),
    "Nycteola": ("include", "Native willow-feeding noctuid."),
    "Diachrysia": ("include", "Native looper moths."),
    "Eosphoropteryx": ("include", "Pink-patched Looper, native."),
    "Syngrapha": ("include", "Native looper moths, boreal and alpine."),
    "Cycnia": ("include", "Dogbane tiger moths — native, and one of the few "
               "things that eats Apocynum."),
    "Spilosoma": ("include", "Native tiger moths."),
    "Estigmene": ("include", "Salt Marsh Moth, native."),
    "Halysidota": ("include", "Banded tussock moths, native."),
    "Clemensia": ("include", "Little White Lichen Moth, native."),
    "Orgyia": ("include", "Tussock moths, native."),
    "Datana": ("include", "Native prominents, gregarious on shrubs."),
    "Schizura": ("include", "Native prominents."),
    "Paonias": ("include", "Eyed sphinxes, native on willow and poplar."),
    "Ceratomia": ("include", "Waved Sphinx, native on ash."),
    "Paranthrene": ("include", "Western Poplar Clearwing, native."),
    "Podosesia": ("include", "Ash borers, native clearwings."),
    "Pennisetia": ("include", "Raspberry Crown Borer, native."),
    "Prochoerodes": ("include", "Native geometrids."),
    "Eusarca": ("include", "Native geometrids."),
    "Tetracis": ("include", "Native geometrids."),
    "Euchlaena": ("include", "Native geometrids."),
    "Macaria": ("include", "Native geometrids of conifer and shrub."),
    "Cingilia": ("include", "Chain-dotted Geometer, native."),
    "Ectropis": ("include", "Saddleback Looper, native."),
    "Cladara": ("include", "Native geometrids."),
    "Synchlora": ("include", "Wavy-lined Emerald — the caterpillar decorates "
                  "itself with the flower it is eating."),
    "Chlorochlamys": ("include", "Native emerald geometrids."),
    "Scopula": ("include", "Native waves."),
    "Dysstroma": ("include", "Holarctic carpet moths, native here."),
    "Hydria": ("include", "Scallop Shell, Holarctic and native here."),
    "Rheumaptera": ("include", "Spear-marked Black Moth — Holarctic, native, "
                    "and a birch defoliator of the boreal."),
    "Epirrhoe": ("include", "Holarctic carpet moths, native here."),
    "Mesoleuca": ("include", "Native carpet moths."),
    "Euphyia": ("include", "Native carpet moths."),
    "Lobophora": ("include", "Native geometrids."),
    "Euclidia": ("include", "Native day-flying noctuids of grassland."),
    "Androloma": ("include", "A. maccullochii, a native day-flying noctuid "
                  "of the mountains."),
    "Geina": ("include", "Plume moths, native."),
    "Emmelina": ("include", "Plume moths — Holarctic and native here."),
    "Amblyptilia": ("include", "Plume moths, native."),
    "Gillmeria": ("include", "Yarrow Plume Moth, Holarctic and native here."),
    "Hyphantria": ("include", "Fall Webworm — native to North America, "
                   "however much of a nuisance it is."),
    "Malacosoma": ("include", "Tent caterpillars. californica and disstria "
                   "are Alberta's; the eastern americana is refused below."),
    "Archips": ("include", "Uglynest Caterpillar and relatives — native "
                "chokecherry feeders."),
    "Choristoneura": ("include", "Budworms, native and defining insects of "
                      "the boreal forest."),
    "Acleris": ("include", "Native leafrollers."),
    "Epiblema": ("include", "Goldenrod gall moths — the gall IS the "
                 "relationship, and it is native."),
    "Nomophila": ("include", "Lucerne Moth, native."),
    "Udea": ("include", "Native pyraloids."),
    "Herpetogramma": ("include", "Native pyraloids."),
    "Saucrobotys": ("include", "Dogbane pyralid, native."),
    "Fumibotys": ("include", "Mint Root Borer, native."),
    "Evergestis": ("include", "Holarctic crucifer pyraloids, native here."),
    "Elophila": ("include", "Aquatic pyraloids whose caterpillars live on "
                 "floating leaves — a genuine pond-plant relationship."),
    "Crambus": ("include", "Native grass-veneer moths."),
    "Agriphila": ("include", "Native grass-veneer moths."),
    "Chrysoteuchia": ("include", "Cranberry Girdler, native."),
    "Gesneria": ("include", "Holarctic alpine pyralid, native here."),
    "Homoeosoma": ("include", "Sunflower Moth, native."),
    "Scoliopteryx": ("include", "The Herald — Holarctic, native, and one of "
                     "the moths that overwinters as an adult in a shed."),
    "Choreutis": ("include", "Metalmark moths. C. diana is native; the "
                  "European C. pariana is refused below."),
    "Semioscopis": ("include", "Native early-spring moths."),
    "Idaea": ("hold", "I. dimidiata is European and its North American "
              "records read as adventive."),
    "Notodonta": ("hold", "N. torva is Palaearctic. A prairie record under "
                  "that name is more likely a misapplied name than a moth."),
    "Phaeolita": ("hold", "A superseded combination of the same owlet as "
                  "Phalaenophana above — one animal, two names, and only one "
                  "of them should become a row."),
    "Peridroma": ("hold", "Variegated Cutworm — cosmopolitan and migratory, "
                  "with a genuinely unsettled origin."),
    "Mythimna": ("hold", "True Armyworm — a migrant that does not overwinter "
                 "here. Same reasoning as Helicoverpa above."),
    "Trichoplusia": ("hold", "Cabbage Looper — the same migrant-pest case."),
    "Desmia": ("hold", "Grape Leaffolder — eastern and southern."),
    "Diacme": ("hold", "Eastern and southern pyraloids."),
    "Haploa": ("hold", "Eastern and central tiger moths; I cannot place "
               "confusa or lecontei on the prairies."),
    "Pseudothyris": ("hold", "Mournful Thyris — eastern, and the same call "
                     "as Thyris maculata above."),
    "Oreana": ("hold", "An obscure pyralid I cannot place."),
    "Psilocorsis": ("hold", "Dead-leaf rollers — eastern; I cannot place "
                    "them."),
    "Lampronia": ("hold", "An obscure incurvariid I cannot place."),
    "Scythris": ("hold", "An obscure flower moth I cannot place."),
    "Proserpinus": ("hold", "P. clarkiae is Pacific-slope; Alberta's day "
                    "sphinx is P. flavofasciata."),
    "Plutella": ("reject", "Diamondback Moth — a cosmopolitan crucifer pest "
                 "carried around the world with the crop."),

    # ── Leaf miners and micromoths. Their host records are `hostOf`. ─────
    #
    # The mine, the gall or the case IS the relationship, and it is recorded
    # by finding it ON the plant — which makes these among the better-
    # evidenced edges in the whole set, not the worst. Included at genus
    # rank because the genera are broadly Holarctic and well represented in
    # the Canadian fauna, and the species are not something I can place.
    "Phyllonorycter": ("include", "Leaf-mining moths, speciose and native."),
    "Stigmella": ("include", "Pygmy leaf miners, native."),
    "Ectoedemia": ("include", "Pygmy leaf miners, native."),
    "Phyllocnistis": ("include", "P. populiella, the Aspen Leaf Miner — the "
                      "silver serpentine trails on half the aspen in the "
                      "province."),
    "Marmara": ("include", "Bark and leaf miners, native."),
    "Leucoptera": ("include", "Native leaf-mining moths."),
    "Paraleucoptera": ("include", "Native poplar leaf miners."),
    "Zelleria": ("include", "Pine Needle Sheathminer, native."),
    "Paraclemensia": ("include", "Maple Leafcutter, native."),
    "Chionodes": ("include", "Native twirler moths."),
    "Gnorimoschema": ("include", "Goldenrod gall moths — native, and the "
                      "spindle gall is unmistakable."),
    "Isophrictis": ("include", "Native composite seedhead moths."),
    "Mompha": ("include", "Momphid moths — Epilobium and Chamerion "
               "specialists, which matters in a fireweed province."),
    "Diploschizia": ("include", "Sedge-mining moths, native."),

    # ── Hoverflies. The single richest family in this tail. ──────────────
    "Melanostoma": ("include", "Hoverflies, Holarctic."),
    "Paragus": ("include", "Small hoverflies, Holarctic."),
    "Platycheirus": ("include", "Hoverflies, strongly northern and speciose "
                     "here."),
    "Parhelophilus": ("include", "Marsh hoverflies, native."),
    "Anasimyia": ("include", "Marsh hoverflies, native."),
    "Sphecomyia": ("include", "Large wasp-mimicking hoverflies of the boreal."),
    "Temnostoma": ("include", "Wasp-mimicking hoverflies, deadwood breeders."),
    "Tropidia": ("include", "Hoverflies, native."),
    "Eurimyia": ("include", "Hoverflies, native."),
    "Blera": ("include", "Hoverflies, boreal deadwood breeders."),
    "Copestylum": ("include", "Hoverflies, native."),
    "Hammerschmidtia": ("include", "H. rufa breeds in aspen sap runs — a "
                        "boreal specialist tied to a tree this catalogue "
                        "holds."),
    "Orthonevra": ("include", "Small hoverflies of seepage and fen."),
    "Pipiza": ("include", "Aphid-eating hoverflies, native."),
    "Spilomyia": ("include", "Hornet-mimicking hoverflies, native."),
    "Asemosyrphus": ("include", "Hoverflies, northern."),
    "Epistrophella": ("include", "Hoverflies, Holarctic."),
    "Megasyrphus": ("include", "Hoverflies, boreal."),
    "Melangyna": ("include", "Hoverflies, early-spring and Holarctic."),
    "Parasyrphus": ("include", "Hoverflies, boreal."),
    "Dasysyrphus": ("include", "Hoverflies, boreal."),
    "Polydontomyia": ("include", "Hoverflies, native."),
    "Trichopsomyia": ("include", "Hoverflies, native."),
    "Baccha": ("include", "Slender hoverflies, native."),
    "Brachyopa": ("include", "Sap-run hoverflies, native."),
    "Cheilosia": ("include", "Hoverflies, Holarctic and speciose here."),
    "Criorhina": ("include", "Bumblebee-mimicking hoverflies, native."),
    "Leucozona": ("include", "Hoverflies, Holarctic."),
    "Microdon": ("include", "Ant-nest hoverflies — native, and a genuinely "
                 "strange life history."),
    "Xylota": ("include", "Hoverflies, deadwood breeders."),
    "Palpada": ("hold", "A largely Neotropical genus; P. meigenii is not "
                "something I can place on the prairies."),
    "Eristalinus": ("hold", "E. aeneus is widely treated as adventive in "
                    "North America and the literature does not agree — the "
                    "same call as Eristalis arbustorum above."),
    "Blennogeneris": ("hold", "A Pacific-slope syrphid I cannot place."),
    "Pyrophaena": ("reject", "A superseded combination of Platycheirus "
                   "rosarum, which is admitted above. Writing both makes two "
                   "rows for one fly."),
    "Eumerus": ("reject", "Lesser bulb flies — European, introduced with "
                "ornamental bulbs. Same as Merodon above."),

    # ── The other flies ──────────────────────────────────────────────────
    "Scathophaga": ("include", "Dung flies — Holarctic, native, and genuine "
                    "flower visitors as adults."),
    "Limnophora": ("include", "Muscid flies of wet ground, native."),
    "Helina": ("include", "Muscid flies, native."),
    "Phaonia": ("include", "Muscid flies, native."),
    "Mesembrina": ("include", "Large Holarctic muscids, native here."),
    "Lispe": ("include", "Shore-loving muscids, native."),
    "Botanophila": ("include", "Anthomyiid flies — flower visitors and, in "
                    "some species, seed feeders."),
    "Chirosia": ("include", "Fern gall flies, native."),
    "Lucilia": ("include", "Green bottle flies — native, and unglamorous "
                "pollinators of umbels and composites."),
    "Calliphora": ("include", "Blow flies, Holarctic and native here."),
    "Adejeania": ("include", "A large native tachinid, conspicuous on "
                  "composites."),
    "Exorista": ("include", "Tachinid parasitoids, native, nectar feeders."),
    "Hystricia": ("include", "Native tachinids."),
    "Eumea": ("include", "Native tachinids."),
    "Peleteria": ("include", "Native tachinids."),
    "Strongygaster": ("include", "Native tachinids."),
    "Zaira": ("include", "Native tachinids."),
    "Phasia": ("include", "Native tachinids, parasitoids of true bugs."),
    "Blaesoxipha": ("include", "Flesh flies that parasitise grasshoppers — "
                    "native, and part of what keeps a prairie in balance."),
    "Senotainia": ("include", "Satellite flies of solitary bees, native."),
    "Sphenometopa": ("include", "Flesh flies, native."),
    "Agromyza": ("include", "Leaf-mining flies. Same argument as the "
                 "leaf-mining moths: the mine is the record."),
    "Liriomyza": ("include", "Leaf-mining flies, native."),
    "Phytomyza": ("include", "Leaf-mining flies, native and speciose."),
    "Aulagromyza": ("include", "Leaf-mining flies, native."),
    "Euhexomyza": ("include", "Willow gall agromyzids, native."),
    "Eurosta": ("include", "E. solidaginis, the Goldenrod Gall Fly — the "
                "textbook one, and native."),
    "Eutreta": ("include", "Native gall-forming fruit flies of composites."),
    "Euaresta": ("include", "Native ragweed seedhead flies."),
    "Campiglossa": ("include", "Native composite seedhead flies."),
    "Dioxyna": ("include", "Native composite seedhead flies."),
    "Terellia": ("include", "Native thistle seedhead flies."),
    "Tritoxa": ("include", "Native onion flies."),
    "Anthrax": ("include", "Bee flies, native parasitoids of solitary bees."),
    "Anastoechus": ("include", "Bee flies, native."),
    "Paravilla": ("include", "Bee flies, native."),
    "Poecilognathus": ("include", "Bee flies, native."),
    "Neorhynchocephalus": ("include", "Tangle-veined flies — native "
                           "grasshopper parasitoids, and heavy nectar "
                           "feeders."),
    "Physoconops": ("include", "Thick-headed flies, native bee parasitoids."),
    "Myopa": ("include", "Thick-headed flies, native."),
    "Stratiomys": ("include", "Soldier flies, native flower visitors."),
    "Hedriodiscus": ("include", "Soldier flies, native."),
    "Atrichopogon": ("include", "Biting midges — tiny, and genuine "
                     "pollinators of small flowers."),
    "Nephrotoma": ("include", "Crane flies, native."),
    "Chrysops": ("include", "Deer flies. The blood meal is the female's; "
                 "both sexes take nectar."),
    "Tabanus": ("include", "Horse flies, on the same reasoning."),
    "Clusia": ("include", "Native druid flies of deadwood."),
    "Pollenia": ("reject", "Cluster flies — European, and introduced to "
                 "North America along with the earthworms they parasitise."),
    "Stomoxys": ("reject", "Stable Fly — Old World, introduced with "
                 "livestock."),
    "Muscina": ("reject", "A cosmopolitan synanthrope introduced with "
                "European settlement."),
    "Neomyia": ("reject", "Palaearctic muscid, adventive in North America."),
    "Eudasyphora": ("hold", "Palaearctic muscid whose North American records "
                    "read as adventive."),
    "Fannia": ("hold", "A mixed genus of natives and introduced "
               "synanthropes; I cannot tell which this is."),
    "Physiphora": ("hold", "A cosmopolitan picture-winged fly of uncertain "
                   "origin here."),
    "Orthocladius": ("hold", "A chironomid midge. Its flower record is a "
                     "midge resting on a flower, not feeding at one."),
    "Bradysiopsis": ("hold", "A fungus gnat; the flower record is not a "
                     "relationship I can name."),
    "Elachiptera": ("hold", "Small acalyptrate flies I cannot place."),
    "Olcella": ("hold", "Small acalyptrate flies I cannot place."),
    "Thaumatomyia": ("hold", "Small acalyptrate flies I cannot place."),
    "Leptometopa": ("hold", "Small acalyptrate flies I cannot place."),
    "Paramyia": ("hold", "Small acalyptrate flies I cannot place."),

    # ── Beetles ──────────────────────────────────────────────────────────
    "Lepturobosca": ("include", "Golden-haired Flower Longhorn — abundant on "
                     "prairie umbels and composites."),
    "Gnathacmaeops": ("include", "Flower longhorns, boreal."),
    "Trachysida": ("include", "Flower longhorns, native."),
    "Anastrangalia": ("include", "Flower longhorns, native."),
    "Brachysomida": ("include", "Flower longhorns, native."),
    "Stictoleptura": ("include", "Flower longhorns, native."),
    "Xestoleptura": ("include", "Flower longhorns, native."),
    "Etorofus": ("include", "Flower longhorns, native."),
    "Bellamira": ("include", "Flower longhorns, native."),
    "Pidonia": ("include", "Flower longhorns, native."),
    "Pseudogaurotina": ("include", "Flower longhorns, native and montane."),
    "Molorchus": ("include", "Small longhorns, native."),
    "Cyrtophorus": ("include", "Ant-mimicking longhorns, native."),
    "Clytus": ("include", "Banded longhorns, native."),
    "Saperda": ("include", "Poplar and willow borers — S. populnea is "
                "Holarctic and native here."),
    "Anthaxia": ("include", "Native jewel beetles, flower visitors."),
    "Buprestis": ("include", "Native jewel beetles."),
    "Dicerca": ("include", "Native jewel beetles."),
    "Adalia": ("include", "Two-spotted Lady Beetle — Holarctic and native to "
               "North America, unlike the Asian Harmonia."),
    "Coccinella": ("include", "Native lady beetles — trifasciata is "
                   "Alberta's commonest. The European C. septempunctata is "
                   "refused below."),
    "Hippodamia": ("include", "Native lady beetles of grassland."),
    "Calvia": ("include", "Holarctic lady beetles, native here."),
    "Brachiacantha": ("include", "Native lady beetles."),
    "Anisosticta": ("include", "Native marsh lady beetles."),
    "Hyperaspis": ("include", "Native lady beetles."),
    "Epuraea": ("include", "Sap beetles — native, and pollen feeders on "
                "early flowers."),
    "Antherophagus": ("include", "Beetles that ride bumblebees to their "
                      "nests. A real relationship and an odd one."),
    "Byturus": ("include", "Raspberry fruitworms, native."),
    "Orsodacne": ("include", "Holarctic flower-feeding leaf beetles."),
    "Chrysochus": ("include", "Dogbane and Cobalt Milkweed Beetles — native, "
                   "and among the most striking insects on the prairie."),
    "Blepharida": ("include", "Sumac Flea Beetle, native."),
    "Bromius": ("include", "Holarctic leaf beetle, native here on Epilobium."),
    "Microrhopala": ("include", "Goldenrod leaf-mining beetles, native."),
    "Scelolyperus": ("include", "Native leaf beetles."),
    "Plateumaris": ("include", "Reed beetles of marsh and fen, native."),
    "Dichelonyx": ("include", "Native scarabs, foliage and flower feeders."),
    "Zonitis": ("include", "Blister beetles whose larvae develop in solitary "
                "bee nests — native."),
    "Mordellistena": ("include", "Tumbling flower beetles, native."),
    "Mordellina": ("include", "Tumbling flower beetles, native."),
    "Pentaria": ("include", "Tumbling flower beetles, native."),
    "Lebia": ("include", "Native ground beetles that visit flowers as "
              "adults."),
    "Ellychnia": ("include", "Winter Firefly — native, diurnal, and a real "
                  "flower visitor."),
    "Lucidota": ("include", "Black Firefly, native."),
    "Oiceoptoma": ("include", "Margined Carrion Beetle — native, and it does "
                   "genuinely visit flowers."),
    "Eusphalerum": ("include", "Flower-feeding rove beetles, native."),
    "Anthrenus": ("reject", "Carpet beetles — Palaearctic and introduced. "
                  "The same call as Anthrenus museorum above; the adults do "
                  "visit flowers, and they are still not from here."),
    "Otiorhynchus": ("reject", "European root weevils, introduced."),
    "Sitona": ("reject", "European legume weevils, introduced with clover "
               "and alfalfa."),
    "Phyllobius": ("reject", "European leaf weevil, introduced."),
    "Polydrusus": ("reject", "European leaf weevil, introduced."),
    "Brachypera": ("reject", "Clover Leaf Weevil — European, introduced."),
    "Larinus": ("reject", "Released deliberately as a knapweed biocontrol "
                "agent. A native-plant catalogue should not file a "
                "biocontrol introduction as prairie wildlife."),
    "Acmaeodera": ("hold", "A. pulchella is a Great Plains species reaching "
                   "well south of here; I cannot place it."),
    "Acalymma": ("hold", "Striped Cucumber Beetle — native to the continent, "
                 "but tied to wild Cucurbita, which Alberta does not have."),
    "Leptinotarsa": ("hold", "Colorado Potato Beetle. Native to the "
                     "continent; its prairie presence is an agricultural "
                     "range expansion off its wild Solanum host."),
    "Purpuricenus": ("hold", "Eastern longhorn; I cannot place it here."),
    "Listronotus": ("hold", "A genus of both natives and introduced pests."),
    "Stamoderes": ("hold", "An obscure weevil I cannot place."),
    "Acanthoscelidius": ("hold", "An obscure weevil I cannot place."),
    "Orchestes": ("hold", "Flea weevils — the genus holds both native leaf "
                  "miners and introduced ones."),
    "Nitops": ("hold", "An obscure short-winged flower beetle."),
    "Orphilus": ("hold", "An obscure dermestid."),

    # ── Wasps, sawflies and ants ─────────────────────────────────────────
    "Symmorphus": ("include", "Mason wasps, native."),
    "Eumenes": ("include", "Potter wasps, native."),
    "Pterocheilus": ("include", "Western potter wasps, native."),
    "Odynerus": ("include", "Mason wasps, native."),
    "Pseudepipona": ("include", "Potter wasps, native."),
    "Pseudomasaris": ("include", "Pollen wasps — a vespid that provisions "
                      "with pollen rather than prey, and a genuine "
                      "Penstemon pollinator in the dry west."),
    "Ageniella": ("include", "Spider wasps, native."),
    "Anoplius": ("include", "Spider wasps, native."),
    "Evagetes": ("include", "Spider wasps, native."),
    "Chrysis": ("include", "Cuckoo wasps — native, and nectar feeders as "
                "adults."),
    "Holopyga": ("include", "Cuckoo wasps, native."),
    "Conura": ("include", "Chalcid parasitoids, native."),
    "Pimpla": ("include", "Ichneumon parasitoids, native."),
    "Bracon": ("include", "Braconid parasitoids, native."),
    "Diplolepis": ("include", "Rose gall wasps — native, and the mossy rose "
                   "gall is one of the most visible insect signs on a "
                   "prairie rose."),
    "Diastrophus": ("include", "Stem gall wasps of rose and rubus, native."),
    "Hemadas": ("include", "Blueberry Stem Gall Wasp, native."),
    "Tremex": ("include", "Pigeon Horntail, native."),
    "Urocerus": ("include", "Horntails, native."),
    "Cimbex": ("include", "Elm Sawfly, native."),
    "Dolerus": ("include", "Native sawflies of wet meadow."),
    "Metallus": ("include", "Native leaf-mining sawflies of rubus."),
    "Janus": ("include", "Willow shoot sawflies, native."),
    "Lasius": ("include", "Field ants — native, abundant, and takes floral "
               "and extrafloral nectar."),
    "Camponotus": ("include", "Carpenter ants, native."),
    "Pseudochrysis": ("hold", "A Palaearctic cuckoo-wasp genus; I cannot "
                      "place this species here."),
    "Ischnus": ("hold", "A Palaearctic ichneumonid I cannot place."),
    "Hypocritanus": ("hold", "An obscure ichneumonid I cannot place."),
    "Pseudodynerus": ("hold", "Eastern and southern potter wasps."),
    "Pristiphora": ("hold", "A genus holding both native sawflies and two "
                    "well-known European introductions; this species is one "
                    "of the introductions and is refused below."),
    "Acraspis": ("hold", "An oak gall wasp. Bur oak barely reaches the "
                 "eastern prairies and this is not a relationship I can "
                 "claim for an Alberta yard."),
    "Bassettia": ("hold", "Oak gall wasp — the same reasoning."),
    "Druon": ("hold", "Oak gall wasp — the same reasoning."),
    "Brachymyrmex": ("reject", "A tropical ant genus; B. obscurior is "
                     "introduced wherever it turns up in the north."),

    # ── True bugs, hoppers and their relatives ───────────────────────────
    "Boisea": ("include", "Boxelder Bug — native, and tied to a tree this "
               "catalogue holds."),
    "Corimelaena": ("include", "Ebony bugs, native."),
    "Corythucha": ("include", "Lace bugs, native and host-specific."),
    "Harmostes": ("include", "Scentless plant bugs, native."),
    "Lopidea": ("include", "Native plant bugs."),
    "Neurocolpus": ("include", "Native plant bugs."),
    "Plagiognathus": ("include", "Native plant bugs."),
    "Alydus": ("include", "Broad-headed bugs, native."),
    "Heterogaster": ("include", "Native seed bugs."),
    "Neoneides": ("include", "Native stilt bugs."),
    "Graphocephala": ("include", "Sharpshooter leafhoppers, native."),
    "Cuerna": ("include", "Native leafhoppers of grassland."),
    "Ponana": ("include", "Native leafhoppers."),
    "Thamnotettix": ("include", "Native leafhoppers."),
    "Agalliopsis": ("include", "Native leafhoppers."),
    "Amphigonalia": ("include", "Native leafhoppers."),
    "Enchenopa": ("include", "Treehoppers, native and host-specific."),
    "Clastoptera": ("include", "Native spittlebugs."),
    "Okanagana": ("include", "Native prairie and foothill cicadas."),
    "Philaenus": ("reject", "Meadow Spittlebug — European, introduced, and "
                  "now the commonest spittlebug in North America."),
    "Rhyparochromus": ("reject", "A European seed bug established in North "
                       "America within the last twenty years."),
    "Coriomeris": ("reject", "A Palaearctic genus with no native North "
                   "American species."),
    "Neokolla": ("hold", "A superseded combination; this animal is a "
                 "Graphocephala. One insect should not become two rows."),
    "Apiomerus": ("hold", "Bee assassin — a predator sitting on a flower to "
                  "take the visitors. The Phymata call."),
    "Podisus": ("hold", "Spined Soldier Bug — predatory; the same call."),
    "Climaciella": ("hold", "A mantidfly, and a predator; the same call."),

    # ── Aphids, adelgids, scales and gall midges ─────────────────────────
    #
    # Host records, and host-specific ones. Unglamorous, and the layer of the
    # food web that everything insectivorous in the yard is actually eating.
    "Chaitophorus": ("include", "Native poplar and willow aphids."),
    "Prociphilus": ("include", "Woolly Alder Aphid, native."),
    "Pachypappa": ("include", "Native poplar gall aphids."),
    "Thecabius": ("include", "Native poplar gall aphids."),
    "Mordwilkoja": ("include", "Poplar Vagabond Gall Aphid, native."),
    "Tamalia": ("include", "Native Arctostaphylos gall aphids."),
    "Macrosiphum": ("include", "M. albifrons, the Lupine Aphid — native to "
                    "western North America."),
    "Adelges": ("include", "Cooley and larch spruce gall adelgids — native "
                "to western North America, and the pineapple gall on a "
                "spruce is unmistakable."),
    "Chionaspis": ("include", "Pine Needle Scale, native."),
    "Dasineura": ("include", "Gall midges, native and host-specific."),
    "Contarinia": ("include", "Gall midges, native."),
    "Blaesodiplosis": ("include", "Hawthorn gall midges, native."),
    "Aphis": ("reject", "A. nerii, the Oleander Aphid — a tropical species "
              "moved around the world on ornamental milkweeds, and now the "
              "thing found on garden Asclepias."),
    "Rhopalosiphum": ("reject", "Bird Cherry-Oat Aphid — Palaearctic, "
                      "introduced with cereals."),
    "Lepidosaphes": ("reject", "Oystershell Scale — European, introduced."),
    "Acyrthosiphon": ("hold", "A genus of both natives and the introduced "
                      "Pea Aphid; I cannot tell which this is."),
    "Pterocomma": ("hold", "Holarctic willow aphids of uncertain origin "
                   "here."),

    # ── Crickets, katydids, lacewings, thrips ────────────────────────────
    "Oecanthus": ("include", "Tree crickets — native, and they feed on "
                  "pollen and flower parts as well as singing from them."),
    "Scudderia": ("include", "Bush katydids, native flower and foliage "
                  "feeders."),
    "Conocephalus": ("include", "Meadow katydids, native seed feeders."),
    "Chrysopa": ("include", "Green lacewings. The larva is a predator and "
                 "the adult feeds on pollen and nectar, so the flower record "
                 "is a reward — unlike the ambush bugs above."),
    "Frankliniella": ("include", "Flower thrips — native, tiny, and genuine "
                      "pollen feeders."),

    # ── Dragonflies and damselflies. A perch is not a relationship. ──────
    #
    # Same reasoning as the ambush bugs, one step further: an odonate takes
    # nothing from a plant at all, at any life stage. Every flower record
    # here is an insect that landed.
    "Sympetrum": ("hold", "Meadowhawks. Native, and they take nothing from a "
                  "flower."),
    "Aeshna": ("hold", "Darners — the same."),
    "Ischnura": ("hold", "Forktail damselflies — the same."),
    "Enallagma": ("hold", "Bluet damselflies — the same."),
    "Lestes": ("hold", "Spreadwing damselflies — the same."),
    "Pachydiplax": ("hold", "Blue Dasher — the same."),

    # ── Arachnids. Two reasons, either of which is enough. ───────────────
    #
    # They are predators standing on flowers (the Misumena call), AND the
    # catalogue's taxon vocabulary has no word for them — the fetch files
    # them as `other_insect`, which is a false statement in a field the app
    # displays next to the animal's name.
    "Phidippus": ("hold", "Jumping spiders. Predators, and not insects."),
    "Pelegrina": ("hold", "Jumping spiders — the same."),
    "Neoscona": ("hold", "Orb weavers — the same."),
    "Xysticus": ("hold", "Crab spiders — the same."),
    "Mecaphesa": ("hold", "Crab spiders — the same."),
    "Tibellus": ("hold", "Running crab spiders — the same."),
    "Tetragnatha": ("hold", "Long-jawed orb weavers — the same."),
    "Phalangium": ("hold", "A harvestman, and a European one at that."),
    "Aceria": ("hold", "Eriophyid gall mites. The gall is a real "
               "relationship; `other_insect` is still the wrong word for a "
               "mite, and this catalogue has no right one yet."),
    "Aculus": ("hold", "Eriophyid gall mites — the same."),
    "Eriophyes": ("hold", "Eriophyid gall mites — the same."),

    "Crossidius": ("include", "Goldenrod flower longhorns — western, and "
                   "late-summer composite specialists as adults."),
    "Gnophaela": ("include", "Police car moths — day-flying, native, and on "
                  "bluebells."),
    "Pyrausta": ("include", "Native pyraloids, many of them mint feeders."),
    "Laphria": ("hold", "Bee-mimicking robber flies. Predators waiting on "
                "flowers for the pollinators — the Phymata call again, in a "
                "family that is very good at it."),
    "Tenodera": ("reject", "Chinese Mantis — introduced to North America, "
                 "sold as a garden 'beneficial', and a predator of "
                 "pollinators including hummingbirds."),

    # ── Four more genera that only make sense read with the overrides ────
    "Lycaena": ("include", "Coppers. cupreus and heteronea reach southern "
                "Alberta; the southern-Rockies snowi is held below."),
    "Agrilus": ("include", "Jewel beetles. A. anxius, the Bronze Birch "
                "Borer, is native; the European A. cyanescens is refused "
                "below."),
    "Cosmosalia": ("reject", "A superseded combination of Lepturobosca "
                   "chrysocoma, admitted above under its current name."),
    "Urophora": ("reject", "Released deliberately as a knapweed biocontrol "
                 "agent, like Larinus. Established, effective, and not "
                 "prairie wildlife."),
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

    # ══════════════════════════════════════════════════════════════════
    # V2.64 — the tail. Where a genus rule is right for most of its
    # species and wrong for one, the one is written down here.
    # ══════════════════════════════════════════════════════════════════

    # ── Out of range, inside an included genus ───────────────────────────
    "Icaricia lupini": ("hold", "Lupine Blue — Great Basin and the Pacific "
                        "Northwest. Alberta's blues in this genus are "
                        "icarioides and saepiolus, both admitted above."),
    "Lycaena snowi": ("hold", "Snow's Copper — a southern-Rockies alpine "
                      "endemic."),
    "Polites sabuleti": ("reject", "Sandhill Skipper — Great Basin and "
                         "California."),
    "Vanessa annabella": ("hold", "West Coast Lady. Reaches Alberta as an "
                          "occasional stray, which is not a resident."),
    "Papilio multicaudata": ("hold", "Two-tailed Swallowtail — southern BC "
                             "and the American southwest."),
    "Pontia beckerii": ("hold", "Becker's White — Great Basin and the dry "
                        "interior of BC."),
    "Burnsius oileus": ("reject", "Tropical Checkered-Skipper — subtropical, "
                        "and nowhere near here."),
    "Malacosoma americana": ("hold", "Eastern Tent Caterpillar. Alberta's "
                             "tent caterpillars are californica and "
                             "disstria, both admitted."),

    # ── Introduced, inside a genus that is otherwise native ──────────────
    "Choreutis pariana": ("reject", "Apple-and-Thorn Skeletonizer — "
                          "European, introduced with orchard stock."),
    "Agrilus cyanescens": ("reject", "A European jewel beetle introduced to "
                           "North America on honeysuckle."),
    "Pristiphora appendiculata": ("reject", "Gooseberry Sawfly — European, "
                                  "introduced with currants."),
    "Adelphocoris lineolatus": ("reject", "Alfalfa Plant Bug — European, "
                                "introduced with the forage crop."),
    "Adelphocoris rapidus": ("include", "Rapid Plant Bug — native to North "
                             "America, and the reason its genus gets no "
                             "blanket rule."),
    # Not in this tail, and written down anyway. It is the most likely
    # single mistake in the whole lady-beetle genus, and a rule that only
    # holds because the wrong species happens to be absent is not a rule.
    "Coccinella septempunctata": ("reject", "Seven-spotted Lady Beetle — "
                                  "European, released as a biocontrol agent "
                                  "and now displacing the native "
                                  "Coccinella across the prairies."),
}

_ICON = {"bee": "🐝", "lepidoptera": "🦋", "bird": "🐦",
         "other_insect": "🪲", "mammal": "🦌"}


def _rows(path):
    with open(path, "r", encoding="utf-8") as fh:
        blob = json.load(fh)
    return blob if isinstance(blob, list) else next(
        v for v in blob.values() if isinstance(v, list))


def _shortlist() -> list:
    """Every animal either review covered, richest first.

    ``REVIEWED`` (the V2.63 top 200) plus ``REVIEWED_TAIL`` (the V2.64
    remainder). Both are pinned name lists, so this walks them rather than
    recomputing a window; the only thing it computes is whether each name is
    *still* surviving the gates, because a name that stopped surviving should
    stop appearing in the report.
    """
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
    # Pinned, not sliced. `ok` is recomputed from the current catalogue, so
    # slicing it would review a different 200 every time rows are written.
    surviving = set(ok)
    reviewed = [a for a in REVIEWED] + [a for a in REVIEWED_TAIL]
    out = [(a, held.get(a, {}).get("taxon", ""), n[a], nat.get(a, {}))
           for a in reviewed if a in surviving or a in have]
    out.sort(key=lambda t: (-t[2], t[0]))
    return out


def verdict_for(name: str) -> tuple:
    """``(verdict, reason)`` — species override, then rank, then the genus.

    The middle step is structural rather than taxonomic: **the catalogue keys
    fauna on binomials**, so a trinomial row resolves against nothing and
    lands beside the species row for the same animal. V2.63 wrote seven of
    those out by hand and V2.64's tail brought 42 more, at which point one
    rule is more honest than forty-nine lines saying the same thing. It sits
    ABOVE the genus lookup on purpose — most of these subspecies belong to
    genera the review admits, so a genus rule would wave them straight in.
    """
    if name in SPECIES:
        return SPECIES[name]
    if len(name.split()) > 2:
        return ("reject", "a trinomial. The catalogue keys fauna on "
                "binomials, so a subspecies row resolves against nothing "
                "and duplicates the species it belongs to.")
    genus = name.split()[0] if name else ""
    if genus in GENUS:
        return GENUS[genus]
    return ("hold", "not reviewed — no rule for this genus")


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


def writable() -> tuple:
    """``(connected, orphans)`` — admitted animals that will actually get an
    edge, and the ones that will not.

    **A row for an animal with no edge is an animal connected to nothing.**
    `curate_birds.py` learned this in V2.60 and reported it; this file did
    not, and the first tail apply wrote 20 such rows — animals whose every
    candidate record was then dropped downstream by a gate this review does
    not run. `tests/test_derived_edges` caught them as orphans in the seeded
    DB, which is the right place to notice and the wrong place to fix.

    So the gates are asked, rather than guessed at: the real
    ``ingest_fauna_edges.review`` runs over the same candidate file and the
    answer is which animals survive it. An animal that **already** carries a
    seeded edge counts as connected — on a second run its candidates are all
    dropped as "already seeded", and that is not the same thing as an orphan.
    """
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "ingest_fauna_edges",
        os.path.join(_ROOT, "scripts", "ingest_fauna_edges.py"))
    ing = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ing)
    cands = _rows(os.path.join(_FETCHED, "fauna_edges_candidates.json"))
    kept = {e["fauna"] for e in ing.review(cands)["kept"]}
    seeded = {(r.get("fauna") or "").strip()
              for r in _rows(os.path.join(_DATA, "plant_fauna_master.json"))
              if isinstance(r, dict) and r.get("fauna")}
    admitted = set(verdicts())
    connected = admitted & (kept | seeded)
    return sorted(connected), sorted(admitted - connected)


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
    # ══════════════════════════════════════════════════════════════════
    # V2.64 — the tail. 143 more genera needed a kind.
    #
    # `activity` follows the FAMILY NORM and departs from it only where the
    # species is a documented day-flier — the clearwings, the buckmoths, the
    # arctic and alpine noctuids that fly in sunshine, Orgyia males, the
    # Spear-marked Black Moth. Stating the rule matters more than any single
    # call: it is the difference between a default and forty guesses.
    # ══════════════════════════════════════════════════════════════════

    # Butterflies
    "Agriades": ("butterfly", "day"), "Anthocharis": ("butterfly", "day"),
    "Cercyonis": ("butterfly", "day"), "Chlosyne": ("butterfly", "day"),
    "Erebia": ("butterfly", "day"), "Euchloe": ("butterfly", "day"),
    "Euphilotes": ("butterfly", "day"), "Glaucopsyche": ("butterfly", "day"),
    "Neophasia": ("butterfly", "day"), "Oeneis": ("butterfly", "day"),
    "Parnassius": ("butterfly", "day"), "Plebejus": ("butterfly", "day"),
    # Skippers
    "Erynnis": ("skipper", "day"), "Oarisma": ("skipper", "day"),
    "Pholisora": ("skipper", "day"), "Pyrgus": ("skipper", "day"),
    # Day-flying moths
    "Adela": ("moth", "day"), "Albuna": ("moth", "day"),
    "Androloma": ("moth", "day"), "Caenurgina": ("moth", "day"),
    "Choreutis": ("moth", "day"), "Diploschizia": ("moth", "day"),
    "Drasteria": ("moth", "day"), "Euclidia": ("moth", "day"),
    "Hemaris": ("moth", "day"), "Hemileuca": ("moth", "day"),
    "Orgyia": ("moth", "day"), "Paraclemensia": ("moth", "day"),
    "Paranthrene": ("moth", "day"), "Pennisetia": ("moth", "day"),
    "Podosesia": ("moth", "day"), "Rheumaptera": ("moth", "day"),
    "Synanthedon": ("moth", "day"), "Trichodezia": ("moth", "day"),
    # Noctuoids
    "Acronicta": ("moth", "night"), "Agrotis": ("moth", "night"),
    "Amphipoea": ("moth", "night"), "Anarta": ("moth", "night"),
    "Apamea": ("moth", "night"), "Catocala": ("moth", "night"),
    "Charadra": ("moth", "night"), "Coenophila": ("moth", "night"),
    "Crambodes": ("moth", "night"), "Cucullia": ("moth", "night"),
    "Dargida": ("moth", "night"), "Diachrysia": ("moth", "night"),
    "Enargia": ("moth", "night"), "Eosphoropteryx": ("moth", "night"),
    "Eucirroedia": ("moth", "night"), "Euplexia": ("moth", "night"),
    "Eupsilia": ("moth", "night"), "Euxoa": ("moth", "night"),
    "Feralia": ("moth", "night"), "Graphiphora": ("moth", "night"),
    "Heliothis": ("moth", "night"), "Hypena": ("moth", "night"),
    "Lacinipolia": ("moth", "night"), "Lithophane": ("moth", "night"),
    "Melanchra": ("moth", "night"), "Nephelodes": ("moth", "night"),
    "Nycteola": ("moth", "night"), "Palthis": ("moth", "night"),
    "Phalaenophana": ("moth", "night"), "Polia": ("moth", "night"),
    "Ponometia": ("moth", "night"), "Pseudanarta": ("moth", "night"),
    "Pseudohermonassa": ("moth", "night"), "Renia": ("moth", "night"),
    "Rivula": ("moth", "night"), "Scoliopteryx": ("moth", "night"),
    "Sunira": ("moth", "night"), "Sympistis": ("moth", "night"),
    "Syngrapha": ("moth", "night"), "Xestia": ("moth", "night"),
    "Xylena": ("moth", "night"), "Zale": ("moth", "night"),
    "Zanclognatha": ("moth", "night"),
    # Tiger moths, prominents, tussocks, tent caterpillars, sphinxes
    "Clemensia": ("moth", "night"), "Cycnia": ("moth", "night"),
    "Estigmene": ("moth", "night"), "Halysidota": ("moth", "night"),
    "Spilosoma": ("moth", "night"), "Datana": ("moth", "night"),
    "Schizura": ("moth", "night"), "Hyphantria": ("moth", "night"),
    "Malacosoma": ("moth", "night"), "Ceratomia": ("moth", "night"),
    "Paonias": ("moth", "night"), "Hyles": ("moth", "night"),
    # Geometrids
    "Chlorochlamys": ("moth", "night"), "Cingilia": ("moth", "night"),
    "Cladara": ("moth", "night"), "Dysstroma": ("moth", "night"),
    "Ectropis": ("moth", "night"), "Epirrhoe": ("moth", "night"),
    "Euchlaena": ("moth", "night"), "Euphyia": ("moth", "night"),
    "Eusarca": ("moth", "night"), "Hydria": ("moth", "night"),
    "Lobophora": ("moth", "night"), "Lomographa": ("moth", "night"),
    "Macaria": ("moth", "night"), "Mesoleuca": ("moth", "night"),
    "Prochoerodes": ("moth", "night"), "Scopula": ("moth", "night"),
    "Synchlora": ("moth", "night"), "Tetracis": ("moth", "night"),
    # Tortricids and pyraloids
    "Acleris": ("moth", "night"), "Anania": ("moth", "night"),
    "Agriphila": ("moth", "night"), "Archips": ("moth", "night"),
    "Choristoneura": ("moth", "night"), "Chrysoteuchia": ("moth", "night"),
    "Crambus": ("moth", "night"), "Elophila": ("moth", "night"),
    "Epiblema": ("moth", "night"), "Evergestis": ("moth", "night"),
    "Fumibotys": ("moth", "night"), "Gesneria": ("moth", "night"),
    "Herpetogramma": ("moth", "night"), "Homoeosoma": ("moth", "night"),
    "Nomophila": ("moth", "night"), "Saucrobotys": ("moth", "night"),
    "Udea": ("moth", "night"), "Orthosia": ("moth", "night"),
    # Plume moths
    "Amblyptilia": ("moth", "night"), "Dejongia": ("moth", "night"),
    "Emmelina": ("moth", "night"), "Geina": ("moth", "night"),
    "Gillmeria": ("moth", "night"),
    # Leaf miners and other micros
    "Chionodes": ("moth", "night"), "Ectoedemia": ("moth", "night"),
    "Gnorimoschema": ("moth", "night"), "Isophrictis": ("moth", "night"),
    "Leucoptera": ("moth", "night"), "Marmara": ("moth", "night"),
    "Mompha": ("moth", "night"), "Paraleucoptera": ("moth", "night"),
    "Phyllocnistis": ("moth", "night"), "Phyllonorycter": ("moth", "night"),
    "Semioscopis": ("moth", "night"), "Stigmella": ("moth", "night"),
    "Zelleria": ("moth", "night"),
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

    # ── V2.64, the tail. Same rule: a name somebody actually uses, or the
    # binomial. 941 of the 998 admitted animals keep their binomial, which
    # is not a shortfall — it is what most of these insects are called.
    # Butterflies
    "Euchloe olympia": "Olympia Marble",
    "Euchloe ausonides": "Large Marble",
    "Euchloe creusa": "Northern Marble",
    "Anthocharis julia": "Julia Orangetip",
    "Anthocharis sara": "Sara Orangetip",
    "Oeneis chryxus": "Chryxus Arctic",
    "Oeneis melissa": "Melissa Arctic",
    "Oeneis uhleri": "Uhler's Arctic",
    "Phyciodes pulchella": "Field Crescent",
    "Phyciodes batesii": "Tawny Crescent",
    "Glaucopsyche piasus": "Arrowhead Blue",
    "Lycaena cupreus": "Lustrous Copper",
    "Lycaena heteronea": "Blue Copper",
    "Oarisma garita": "Garita Skipperling",
    # Moths
    "Hemileuca nevadensis": "Nevada Buckmoth",
    "Hyphantria cunea": "Fall Webworm",
    "Malacosoma californica": "Western Tent Caterpillar",
    "Malacosoma disstria": "Forest Tent Caterpillar",
    "Choristoneura fumiferana": "Spruce Budworm",
    "Choristoneura rosaceana": "Oblique-banded Leafroller",
    "Choristoneura pinus": "Jack Pine Budworm",
    "Archips cerasivorana": "Uglynest Caterpillar",
    "Orgyia leucostigma": "White-marked Tussock Moth",
    "Halysidota tessellaris": "Banded Tussock Moth",
    "Estigmene acrea": "Salt Marsh Moth",
    "Spilosoma virginica": "Virginia Tiger Moth",
    "Cycnia tenera": "Delicate Cycnia",
    "Clemensia albata": "Little White Lichen Moth",
    "Nephelodes minians": "Bronzed Cutworm",
    "Orthosia hibisci": "Speckled Green Fruitworm",
    "Scoliopteryx libatrix": "Herald Moth",
    "Catocala concumbens": "Sweetheart Underwing",
    "Charadra deridens": "The Laugher",
    "Feralia comstocki": "Comstock's Sallow",
    "Eucirroedia pampina": "Scalloped Sallow",
    "Sunira bicolorago": "Broad-lined Sallow",
    "Xylena curvimacula": "Dot-and-dash Swordgrass Moth",
    "Eosphoropteryx thyatyroides": "Pink-patched Looper",
    "Zale minerea": "Colourful Zale",
    "Ceratomia undulosa": "Waved Sphinx",
    "Schizura concinna": "Red-humped Caterpillar",
    "Homoeosoma electella": "Sunflower Moth",
    "Nomophila nearctica": "Lucerne Moth",
    "Fumibotys fumalis": "Mint Root Borer",
    "Chrysoteuchia topiarius": "Cranberry Girdler",
    "Evergestis pallidata": "Purple-backed Cabbageworm",
    "Gillmeria pallidactyla": "Yarrow Plume Moth",
    "Emmelina monodactyla": "Morning-glory Plume Moth",
    "Geina tenuidactylus": "Himmelman's Plume Moth",
    "Rheumaptera hastata": "Spear-marked Black Moth",
    "Hydria undulata": "Scallop Shell",
    "Cingilia catenaria": "Chain-dotted Geometer",
    "Ectropis crepuscularia": "Saddleback Looper",
    "Synchlora aerata": "Wavy-lined Emerald",
    "Eusarca confusaria": "Confused Eusarca",
    "Epirrhoe alternata": "White-banded Toothed Carpet",
    "Epiblema scudderiana": "Goldenrod Gall Moth",
    "Phyllocnistis populiella": "Aspen Leaf Miner",
    "Paraclemensia acerifoliella": "Maple Leafcutter",
    "Zelleria haimbachi": "Pine Needle Sheathminer",
    "Pennisetia marginatum": "Raspberry Crown Borer",
    "Podosesia syringae": "Lilac Borer",
    "Paranthrene robiniae": "Western Poplar Clearwing",
    # Beetles
    "Lepturobosca chrysocoma": "Golden-haired Flower Longhorn",
    "Stictoleptura canadensis": "Red-shouldered Pine Borer",
    "Adalia bipunctata": "Two-spotted Lady Beetle",
    "Coccinella trifasciata": "Three-banded Lady Beetle",
    "Coccinella transversoguttata": "Transverse Lady Beetle",
    "Calvia quatuordecimguttata": "Cream-spotted Lady Beetle",
    "Hippodamia parenthesis": "Parenthesis Lady Beetle",
    "Byturus unicolor": "Raspberry Fruitworm",
    "Chrysochus cobaltinus": "Cobalt Milkweed Beetle",
    "Chrysochus auratus": "Dogbane Beetle",
    "Blepharida rhois": "Sumac Flea Beetle",
    "Microrhopala vittata": "Goldenrod Leaf Miner",
    "Ellychnia corrusca": "Winter Firefly",
    "Lucidota atra": "Black Firefly",
    "Oiceoptoma noveboracense": "Margined Carrion Beetle",
    "Saperda populnea": "Poplar Gall Borer",
    "Agrilus anxius": "Bronze Birch Borer",
    # Wasps, bees, ants
    "Nomia melanderi": "Alkali Bee",
    "Tremex columba": "Pigeon Horntail",
    "Cimbex americana": "Elm Sawfly",
    "Diplolepis spinosa": "Spiny Rose Gall Wasp",
    "Hemadas nubilipennis": "Blueberry Stem Gall Wasp",
    "Lasius neoniger": "Labour Day Ant",
    "Camponotus novaeboracensis": "New York Carpenter Ant",
    # Flies and the rest
    "Eurosta solidaginis": "Goldenrod Gall Fly",
    "Scathophaga stercoraria": "Yellow Dung Fly",
    "Tabanus punctifer": "Western Horse Fly",
    "Chrysopa oculata": "Golden-eyed Lacewing",
    "Boisea trivittata": "Boxelder Bug",
    "Graphocephala coccinea": "Candy-striped Leafhopper",
    "Prociphilus tessellatus": "Woolly Alder Aphid",
    "Mordwilkoja vagabunda": "Poplar Vagabond Gall Aphid",
    "Adelges cooleyi": "Cooley Spruce Gall Adelgid",
    "Adelges lariciatus": "Larch Spruce Gall Adelgid",
    "Chionaspis pinifoliae": "Pine Needle Scale",
    "Macrosiphum albifrons": "Lupine Aphid",
    "Oecanthus nigricornis": "Black-horned Tree Cricket",
    "Scudderia furcata": "Fork-tailed Bush Katydid",
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
    have = {r["scientific_name"] for r in
            _rows(os.path.join(_DATA, "fauna_master.json"))
            if isinstance(r, dict) and r.get("scientific_name")}
    new = {k: v for k, v in named.items() if k not in have}
    with_common = sum(1 for k in new if k in COMMON_NAMES)
    print("\n" + "=" * 64)
    print(f"  {len(named)} animals admitted, {len(named) - len(new)} of them "
          f"already in fauna_master.json")
    print(f"  {len(new)} would be written now")
    print(f"    {with_common} have an accepted English name")
    print(f"    {len(new) - with_common} keep their binomial, which for a "
          f"solitary bee is the name")
    print("=" * 64)

    if args.apply:
        connected, orphans = writable()
        if orphans:
            print(f"\n{len(orphans)} admitted animals get NO edge — every "
                  f"candidate record is dropped downstream, so a row here "
                  f"would be an animal connected to nothing. Not written:")
            for name in orphans[:20]:
                print(f"  {name}")
            if len(orphans) > 20:
                print(f"  … and {len(orphans) - 20} more")
        keep = set(connected)
        path = os.path.join(_DATA, "fauna_master.json")
        rows = _rows(path)
        have = {r["scientific_name"] for r in rows
                if isinstance(r, dict) and r.get("scientific_name")}
        new = [row for name, row in sorted(named.items())
               if name not in have and name in keep]
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
                if r["scientific_name"] not in lhave
                and r["scientific_name"] in keep]
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

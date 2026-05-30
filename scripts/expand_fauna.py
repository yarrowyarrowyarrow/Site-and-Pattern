#!/usr/bin/env python3
"""
scripts/expand_fauna.py — 2–3× the native fauna registry (V1.46).

Adds species-level bees, more birds, and the first `other_insect` and `mammal`
records (both already allowed by the `fauna.taxon` CHECK, so no schema change),
plus more lepidoptera — and the plant↔fauna links that connect them. Mirrors the
re-runnable, sourced pattern of scripts/apply_safety_tags.py: idempotent
(dedupes fauna by scientific_name and links by (plant, fauna, relationship)), so
re-running reproduces the same data.

Every `plant` below is an EXACT common_name already in data/plants_master.json /
garden_plants.json (links to unknown plants are skipped quietly at seed time,
but we keep the authored set clean). Relationships and specificity reflect
well-documented associations; `source` cites the reference class used.

Sources: Acorn & Sheldon 2006 (Butterflies of Alberta); Pohl et al. 2018
(Moths of Alberta); Packer, Bees of Canada; Cornell Birds of the World; Acorn,
Bugs of Alberta; Pattie & Fisher, Mammals of Alberta.

Run from the project root:  python scripts/expand_fauna.py
"""

from __future__ import annotations

import json
import os

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_FAUNA = os.path.join(_ROOT, "data", "fauna_master.json")
_LINKS = os.path.join(_ROOT, "data", "plant_fauna_master.json")

_BEE = "Packer, Bees of Canada"
_BFLY = "Acorn & Sheldon 2006"
_MOTH = "Pohl et al. 2018 (Moths of Alberta)"
_BIRD = "Cornell Birds of the World"
_BUG = "Acorn, Bugs of Alberta"
_MAM = "Pattie & Fisher, Mammals of Alberta"


def F(sci, common, taxon, icon, desc, native=1, rng=""):
    return {"scientific_name": sci, "common_name": common, "taxon": taxon,
            "ab_native": native, "range_notes": rng, "icon": icon,
            "description": desc}


NEW_FAUNA = [
    # ── Bees (species-level; genus groups already seeded) ────────────────────
    F("Bombus huntii", "Hunt's Bumble Bee", "bee", "🐝",
      "Common prairie/parkland bumble bee; long colony season makes it a key "
      "generalist pollinator of asters, clovers and mints.", rng="Throughout AB."),
    F("Bombus ternarius", "Tricoloured Bumble Bee", "bee", "🐝",
      "Orange-banded bumble bee of boreal and parkland edges; forages willow, "
      "blueberry, goldenrod.", rng="Central & northern AB."),
    F("Bombus rufocinctus", "Red-belted Bumble Bee", "bee", "🐝",
      "Highly variable short-tongued bumble bee common in gardens and grassland.",
      rng="Throughout AB."),
    F("Bombus borealis", "Northern Amber Bumble Bee", "bee", "🐝",
      "Long-tongued bumble bee favouring deep flowers (legumes, mints).",
      rng="Aspen parkland & boreal."),
    F("Osmia lignaria", "Blue Orchard Mason Bee", "bee", "🐝",
      "Spring solitary bee; superb fruit-tree and willow pollinator that nests "
      "in cavities (and bee hotels).", rng="Throughout AB."),
    F("Megachile relativa", "A Leafcutter Bee", "bee", "🐝",
      "Solitary cavity-nester that cuts leaf discs (often from rose) to line "
      "its nest cells; strong summer pollinator of legumes and asters.",
      rng="Throughout AB."),
    F("Agapostemon virescens", "Bicoloured Sweat Bee", "bee", "🐝",
      "Metallic-green communal ground-nesting bee; generalist on open flowers.",
      rng="Prairie & parkland."),
    F("Lasioglossum spp.", "Small Sweat Bees", "bee", "🐝",
      "Hugely diverse genus of tiny ground-nesting generalist pollinators — "
      "among the most abundant bees in any Alberta garden.", rng="Throughout AB."),
    F("Colletes inaequalis", "Spring Cellophane Bee", "bee", "🐝",
      "Early ground-nesting bee that lines burrows with a cellophane-like "
      "secretion; vital willow and early-spring pollinator.", rng="Throughout AB."),
    F("Halictus rubicundus", "Orange-legged Furrow Bee", "bee", "🐝",
      "Social sweat bee nesting in bare soil; generalist on composites.",
      rng="Throughout AB."),
    F("Anthophora terminalis", "A Digger Bee", "bee", "🐝",
      "Fast-flying solitary digger bee; long tongue suits penstemons and mints.",
      rng="Parkland & foothills."),

    # ── Birds ────────────────────────────────────────────────────────────────
    F("Buteo jamaicensis", "Red-tailed Hawk", "bird", "🦅",
      "Open-country raptor that nests in tall poplars and spruce and hunts "
      "small mammals over meadows.", rng="Throughout AB."),
    F("Bubo virginianus", "Great Horned Owl", "bird", "🦉",
      "Alberta's provincial bird; nests in poplar/spruce, controls rodents.",
      rng="Throughout AB."),
    F("Falco columbarius", "Merlin", "bird", "🦅",
      "Small falcon that reuses old crow/magpie nests in spruce; hunts small "
      "birds in towns and parkland.", rng="Throughout AB."),
    F("Falco sparverius", "American Kestrel", "bird", "🦅",
      "Cavity-nesting little falcon of open country; eats grasshoppers, voles.",
      rng="Throughout AB."),
    F("Dryobates pubescens", "Downy Woodpecker", "bird", "🐦",
      "Smallest woodpecker; forages insects on shrubs and trees and excavates "
      "nest cavities in soft dead wood (poplar, birch).", rng="Throughout AB."),
    F("Colaptes auratus", "Northern Flicker", "bird", "🐦",
      "Ground-foraging woodpecker that eats ants and autumn fruit; nests in "
      "aspen/poplar snags.", rng="Throughout AB."),
    F("Cyanocitta cristata", "Blue Jay", "bird", "🐦",
      "Bold parkland corvid; caches acorns and conifer seeds and takes fruit.",
      rng="Central & southern AB."),
    F("Pica hudsonia", "Black-billed Magpie", "bird", "🐦",
      "Ubiquitous corvid; omnivore whose bulky thorny nests shelter other "
      "species after use.", rng="Throughout AB."),
    F("Perisoreus canadensis", "Canada Jay", "bird", "🐦",
      "Boreal/foothills jay that caches food in spruce; year-round resident.",
      rng="Boreal & foothills."),
    F("Sitta canadensis", "Red-breasted Nuthatch", "bird", "🐦",
      "Conifer specialist that eats spruce/pine seeds and bark insects; nests "
      "in cavities.", rng="Throughout AB."),
    F("Melospiza melodia", "Song Sparrow", "bird", "🐦",
      "Shrub-and-edge sparrow; eats grass and forb seeds and nests low in "
      "dense cover.", rng="Throughout AB."),
    F("Junco hyemalis", "Dark-eyed Junco", "bird", "🐦",
      "Ground-feeding sparrow of forest edges; winters on fallen weed seeds.",
      rng="Throughout AB."),
    F("Pinicola enucleator", "Pine Grosbeak", "bird", "🐦",
      "Large winter finch that feeds on mountain-ash and other persistent "
      "fruit plus conifer and birch seeds.", rng="Boreal; winters south."),
    F("Bombycilla garrulus", "Bohemian Waxwing", "bird", "🐦",
      "Winter-flocking frugivore that strips berries from saskatoon, "
      "highbush-cranberry, hawthorn and rose.", rng="Winters throughout AB."),
    F("Bonasa umbellus", "Ruffed Grouse", "bird", "🐦",
      "Aspen-woodland grouse that eats poplar/willow buds, catkins and shrub "
      "fruit; broods need insect-rich understory.", rng="Throughout AB."),

    # ── Other insects (beneficials / pollinators / aquatic predators) ────────
    F("Eristalis tenax", "Drone Fly", "other_insect", "🪰",
      "Honey-bee-mimicking hover fly (introduced from Europe, now widespread); "
      "adults are major generalist pollinators of composites and umbels.",
      native=0, rng="Throughout AB."),
    F("Syrphus ribesii", "A Flower Fly", "other_insect", "🪰",
      "Hover fly whose aphid-eating larvae are valuable biocontrol; adults "
      "take pollen and nectar.", rng="Throughout AB."),
    F("Toxomerus marginatus", "Calligrapher Fly", "other_insect", "🪰",
      "Tiny hover fly; aphid-predator larvae, pollinator adults.",
      rng="Throughout AB."),
    F("Hippodamia convergens", "Convergent Lady Beetle", "other_insect", "🐞",
      "Native lady beetle; both adults and larvae eat aphids, adults also "
      "take pollen and nectar.", rng="Throughout AB."),
    F("Coccinella novemnotata", "Nine-spotted Lady Beetle", "other_insect", "🐞",
      "Declining native lady beetle; aphid predator of grassland and gardens.",
      rng="Prairie & parkland."),
    F("Chrysoperla carnea", "Green Lacewing", "other_insect", "🦗",
      "'Aphid lions' as larvae; adults sip nectar and honeydew. Key garden "
      "biocontrol.", rng="Throughout AB."),
    F("Pterostichus spp.", "Woodland Ground Beetles", "other_insect", "🪲",
      "Night-active predators of slugs, cutworms and weed seeds; shelter in "
      "leaf litter and groundcover.", rng="Throughout AB."),
    F("Chauliognathus pensylvanicus", "Goldenrod Soldier Beetle", "other_insect", "🪲",
      "Pollen- and nectar-feeding beetle of late-summer goldenrod; larvae are "
      "soil predators.", rng="Prairie & parkland."),
    F("Anax junius", "Common Green Darner", "other_insect", "🪰",
      "Large migratory dragonfly; aerial predator of mosquitoes and flies, "
      "needs ponds with emergent sedges.", rng="Throughout AB."),
    F("Libellula quadrimaculata", "Four-spotted Skimmer", "other_insect", "🪰",
      "Pond dragonfly of marsh edges; voracious insect predator.",
      rng="Throughout AB."),
    F("Sympetrum internum", "Cherry-faced Meadowhawk", "other_insect", "🪰",
      "Late-season red dragonfly of wet meadows and pond margins.",
      rng="Throughout AB."),
    F("Enallagma cyathigerum", "Common Blue Damselfly", "other_insect", "🪰",
      "Slender damselfly of vegetated still water; larvae and adults prey on "
      "small insects.", rng="Throughout AB."),

    # ── Mammals ──────────────────────────────────────────────────────────────
    F("Myotis lucifugus", "Little Brown Bat", "mammal", "🦇",
      "Insectivorous bat eating thousands of mosquitoes nightly; roosts under "
      "bark and in tree cavities. SARA-listed (Endangered).", rng="Throughout AB."),
    F("Eptesicus fuscus", "Big Brown Bat", "mammal", "🦇",
      "Hardy urban-tolerant bat; forages beetles and moths over meadows and "
      "water.", rng="Throughout AB."),
    F("Lasionycteris noctivagans", "Silver-haired Bat", "mammal", "🦇",
      "Migratory tree bat roosting under bark of poplar and spruce.",
      rng="Throughout AB."),
    F("Peromyscus maniculatus", "Deer Mouse", "mammal", "🐭",
      "Abundant native seed-eater and key prey for owls, hawks and foxes; "
      "disperses seeds and fungi.", rng="Throughout AB."),
    F("Microtus pennsylvanicus", "Meadow Vole", "mammal", "🐭",
      "Grassland herbivore whose runways shape meadows; cornerstone prey for "
      "raptors and weasels.", rng="Throughout AB."),
    F("Sorex cinereus", "Masked Shrew", "mammal", "🐭",
      "Tiny voracious insectivore of moist litter; eats insects, slugs and "
      "larvae.", rng="Throughout AB."),

    # ── Lepidoptera (more sphinx/tiger moths, skippers, satyrs, blues) ───────
    F("Hyles lineata", "White-lined Sphinx", "lepidoptera", "🦋",
      "Day-and-dusk hawkmoth; a hummingbird-like nectar pollinator of tubular "
      "flowers; larvae feed on flax and evening-primrose family plants.",
      rng="Throughout AB."),
    F("Pachysphinx modesta", "Big Poplar Sphinx", "lepidoptera", "🦋",
      "Large hawkmoth whose caterpillars feed on poplar and willow foliage.",
      rng="Throughout AB."),
    F("Smerinthus jamaicensis", "Twin-spotted Sphinx", "lepidoptera", "🦋",
      "Eyed hawkmoth; larvae host on willow, birch and cherry.",
      rng="Throughout AB."),
    F("Pyrrharctia isabella", "Isabella Tiger Moth", "lepidoptera", "🦋",
      "The 'woolly bear' caterpillar; a generalist on asters, goldenrods and "
      "many forbs that overwinters as a larva.", rng="Throughout AB."),
    F("Lophocampa maculata", "Spotted Tussock Moth", "lepidoptera", "🦋",
      "Tussock caterpillar feeding on willow, poplar, alder and birch.",
      rng="Throughout AB."),
    F("Epargyreus clarus", "Silver-spotted Skipper", "lepidoptera", "🦋",
      "Large skipper; caterpillars host on native legumes (milkvetch, vetch).",
      rng="Southern & central AB."),
    F("Coenonympha tullia", "Common Ringlet", "lepidoptera", "🦋",
      "Abundant grassland butterfly; caterpillars feed on native grasses.",
      rng="Throughout AB."),
    F("Colias philodice", "Clouded Sulphur", "lepidoptera", "🦋",
      "Ubiquitous yellow butterfly; caterpillars host on legumes (vetch, "
      "milkvetch, lupine).", rng="Throughout AB."),
    F("Plebejus melissa", "Melissa Blue", "lepidoptera", "🦋",
      "Prairie blue whose caterpillars feed on legumes and are tended by ants.",
      rng="Prairie & parkland."),
    F("Phyciodes cocyta", "Northern Crescent", "lepidoptera", "🦋",
      "Small orange-and-black butterfly; caterpillars host on native asters.",
      rng="Throughout AB."),
]


def L(plant, fauna, rel, spec, source, notes=""):
    d = {"plant": plant, "fauna": fauna, "relationship": rel,
         "specificity": spec, "source": source}
    if notes:
        d["notes"] = notes
    return d


NEW_LINKS = [
    # Bees — pollen/nectar generalists on the prairie staples (+ early willow)
    L("Pussy Willow", "Colletes inaequalis", "pollen", "generalist", _BEE,
      "Critical early-spring pollen for emerging solitary bees."),
    L("Pussy Willow", "Osmia lignaria", "pollen", "generalist", _BEE),
    L("Sandbar Willow", "Bombus ternarius", "pollen", "generalist", _BEE),
    L("Saskatoon Berry", "Osmia lignaria", "nectar", "generalist", _BEE,
      "Mason bees are key spring fruit-tree pollinators."),
    L("Chokecherry", "Osmia lignaria", "nectar", "generalist", _BEE),
    L("Wild Bergamot", "Bombus borealis", "nectar", "generalist", _BEE),
    L("Wild Bergamot", "Anthophora terminalis", "nectar", "generalist", _BEE),
    L("Smooth Blue Beardtongue", "Anthophora terminalis", "nectar", "generalist", _BEE),
    L("Canada Goldenrod", "Bombus rufocinctus", "pollen", "generalist", _BEE),
    L("Canada Goldenrod", "Agapostemon virescens", "pollen", "generalist", _BEE),
    L("Canada Goldenrod", "Halictus rubicundus", "pollen", "generalist", _BEE),
    L("Late Goldenrod", "Lasioglossum spp.", "pollen", "generalist", _BEE),
    L("Smooth Aster", "Bombus huntii", "nectar", "generalist", _BEE),
    L("Smooth Aster", "Lasioglossum spp.", "pollen", "generalist", _BEE),
    L("Smooth Aster", "Megachile relativa", "pollen", "generalist", _BEE),
    L("Maximilian Sunflower", "Agapostemon virescens", "pollen", "generalist", _BEE),
    L("Maximilian Sunflower", "Halictus rubicundus", "pollen", "generalist", _BEE),
    L("Blanketflower", "Megachile relativa", "pollen", "generalist", _BEE),
    L("Prickly Wild Rose", "Megachile relativa", "nectar", "generalist", _BEE,
      "Leafcutters cut discs from rose foliage to line nest cells."),
    L("Silky Lupine", "Bombus borealis", "pollen", "generalist", _BEE),
    L("Shrubby Cinquefoil", "Bombus huntii", "nectar", "generalist", _BEE),
    L("Wild Blue Flax", "Lasioglossum spp.", "pollen", "generalist", _BEE),

    # Bumble/solitary bees also use milkweed, blazingstar, fireweed-type nectar
    L("Showy Milkweed", "Bombus huntii", "nectar", "generalist", _BEE),
    L("Dotted Blazingstar", "Bombus huntii", "nectar", "generalist", _BEE),
    L("Dotted Blazingstar", "Bombus rufocinctus", "nectar", "generalist", _BEE),

    # Birds — fruit (frugivores)
    L("Saskatoon Berry", "Bombycilla garrulus", "fruit_food", "generalist", _BIRD),
    L("Saskatoon Berry", "Pinicola enucleator", "fruit_food", "generalist", _BIRD),
    L("Saskatoon Berry", "Bonasa umbellus", "fruit_food", "generalist", _BIRD),
    L("Highbush Cranberry", "Bombycilla garrulus", "fruit_food", "generalist", _BIRD),
    L("Highbush Cranberry", "Pinicola enucleator", "fruit_food", "generalist", _BIRD),
    L("Highbush Cranberry", "Bonasa umbellus", "fruit_food", "generalist", _BIRD),
    L("Black Hawthorn", "Bombycilla garrulus", "fruit_food", "generalist", _BIRD),
    L("Chokecherry", "Bombycilla garrulus", "fruit_food", "generalist", _BIRD),
    L("Chokecherry", "Cyanocitta cristata", "fruit_food", "generalist", _BIRD),
    L("Red Osier Dogwood", "Cyanocitta cristata", "fruit_food", "generalist", _BIRD),
    L("Prickly Wild Rose", "Bombycilla garrulus", "fruit_food", "generalist", _BIRD,
      "Rose hips persist into winter for waxwings and grosbeaks."),
    L("Canada Buffaloberry", "Bonasa umbellus", "fruit_food", "generalist", _BIRD),

    # Birds — seeds
    L("Maximilian Sunflower", "Junco hyemalis", "seed_food", "generalist", _BIRD),
    L("Maximilian Sunflower", "Melospiza melodia", "seed_food", "generalist", _BIRD),
    L("Common Sunflower", "Cyanocitta cristata", "seed_food", "generalist", _BIRD),
    L("Canada Goldenrod", "Junco hyemalis", "seed_food", "generalist", _BIRD),
    L("White Spruce", "Sitta canadensis", "seed_food", "generalist", _BIRD),
    L("White Spruce", "Pinicola enucleator", "seed_food", "generalist", _BIRD),
    L("Lodgepole Pine", "Sitta canadensis", "seed_food", "generalist", _BIRD),
    L("Bur Oak", "Cyanocitta cristata", "seed_food", "generalist", _BIRD,
      "Blue Jays cache acorns, aiding oak dispersal."),
    L("Paper Birch", "Pinicola enucleator", "seed_food", "generalist", _BIRD),
    L("Paper Birch", "Bonasa umbellus", "seed_food", "generalist", _BIRD,
      "Grouse eat birch catkins and buds in winter."),

    # Birds — cover / nesting (raptors, woodpeckers, corvids in trees)
    L("Trembling Aspen", "Bubo virginianus", "nesting", "generalist", _BIRD),
    L("Trembling Aspen", "Colaptes auratus", "nesting", "generalist", _BIRD,
      "Flickers excavate cavities in aspen snags later used by many species."),
    L("Trembling Aspen", "Dryobates pubescens", "nesting", "generalist", _BIRD),
    L("Trembling Aspen", "Bonasa umbellus", "cover", "generalist", _BIRD),
    L("Balsam Poplar", "Buteo jamaicensis", "nesting", "generalist", _BIRD),
    L("White Spruce", "Bubo virginianus", "cover", "generalist", _BIRD),
    L("White Spruce", "Falco columbarius", "nesting", "generalist", _BIRD,
      "Merlins reuse old corvid nests in spruce."),
    L("White Spruce", "Perisoreus canadensis", "cover", "generalist", _BIRD),
    L("Paper Birch", "Dryobates pubescens", "nesting", "generalist", _BIRD),
    L("Prickly Wild Rose", "Melospiza melodia", "nesting", "generalist", _BIRD,
      "Dense thorny shrubs shelter low nests."),
    L("Western Snowberry", "Melospiza melodia", "cover", "generalist", _BIRD),

    # Other insects — hover flies / lady beetles / lacewings on open flowers
    L("Yarrow", "Eristalis tenax", "nectar", "generalist", _BUG),
    L("Yarrow", "Syrphus ribesii", "nectar", "generalist", _BUG),
    L("Yarrow", "Chrysoperla carnea", "nectar", "generalist", _BUG),
    L("Yarrow", "Hippodamia convergens", "nectar", "generalist", _BUG),
    L("Canada Goldenrod", "Chauliognathus pensylvanicus", "pollen", "generalist", _BUG),
    L("Canada Goldenrod", "Eristalis tenax", "nectar", "generalist", _BUG),
    L("Late Goldenrod", "Hippodamia convergens", "nectar", "generalist", _BUG),
    L("Smooth Aster", "Toxomerus marginatus", "nectar", "generalist", _BUG),
    L("Philadelphia Fleabane", "Syrphus ribesii", "nectar", "generalist", _BUG),
    L("Blanketflower", "Coccinella novemnotata", "nectar", "generalist", _BUG),
    L("Wild Strawberry", "Pterostichus spp.", "cover", "generalist", _BUG,
      "Groundcover and litter shelter predatory ground beetles."),
    L("Bunchberry", "Pterostichus spp.", "cover", "generalist", _BUG),

    # Other insects — aquatic predators need emergent wetland vegetation
    L("Water Sedge", "Anax junius", "cover", "generalist", _BUG,
      "Dragonfly larvae develop among submerged/emergent sedge stems."),
    L("Beaked Sedge", "Libellula quadrimaculata", "cover", "generalist", _BUG),
    L("Water Sedge", "Enallagma cyathigerum", "cover", "generalist", _BUG),
    L("Beaked Sedge", "Sympetrum internum", "cover", "generalist", _BUG),

    # Mammals — bats roost in trees; small mammals eat seeds / use cover
    L("Trembling Aspen", "Lasionycteris noctivagans", "cover", "generalist", _MAM,
      "Silver-haired bats roost under loose bark."),
    L("Balsam Poplar", "Myotis lucifugus", "cover", "generalist", _MAM),
    L("Maximilian Sunflower", "Peromyscus maniculatus", "seed_food", "generalist", _MAM),
    L("Rough Fescue", "Microtus pennsylvanicus", "seed_food", "generalist", _MAM,
      "Bunchgrass provides voles food and runway cover."),
    L("Blue Grama Grass", "Peromyscus maniculatus", "seed_food", "generalist", _MAM),
    L("Wild Strawberry", "Sorex cinereus", "cover", "generalist", _MAM),

    # Lepidoptera — larval hosts (the high-value habitat links)
    L("Balsam Poplar", "Pachysphinx modesta", "larval_host", "generalist", _MOTH),
    L("Trembling Aspen", "Pachysphinx modesta", "larval_host", "generalist", _MOTH),
    L("Pussy Willow", "Pachysphinx modesta", "larval_host", "generalist", _MOTH),
    L("Pussy Willow", "Smerinthus jamaicensis", "larval_host", "generalist", _MOTH),
    L("Paper Birch", "Smerinthus jamaicensis", "larval_host", "generalist", _MOTH),
    L("Pin Cherry", "Smerinthus jamaicensis", "larval_host", "generalist", _MOTH),
    L("Sandbar Willow", "Lophocampa maculata", "larval_host", "generalist", _MOTH),
    L("Trembling Aspen", "Lophocampa maculata", "larval_host", "generalist", _MOTH),
    L("Green Alder", "Lophocampa maculata", "larval_host", "generalist", _MOTH),
    L("Canada Goldenrod", "Pyrrharctia isabella", "larval_host", "generalist", _MOTH),
    L("Smooth Aster", "Pyrrharctia isabella", "larval_host", "generalist", _MOTH),
    L("Wild Blue Flax", "Hyles lineata", "larval_host", "generalist", _MOTH),
    L("Dotted Blazingstar", "Hyles lineata", "nectar", "generalist", _MOTH),
    L("Wild Bergamot", "Hyles lineata", "nectar", "generalist", _MOTH),
    L("Canada Milk Vetch", "Epargyreus clarus", "larval_host", "generalist", _BFLY),
    L("Wild Vetch", "Epargyreus clarus", "larval_host", "generalist", _BFLY),
    L("Rough Fescue", "Coenonympha tullia", "larval_host", "generalist", _BFLY),
    L("Foothills Rough Fescue", "Coenonympha tullia", "larval_host", "generalist", _BFLY),
    L("Wild Vetch", "Colias philodice", "larval_host", "generalist", _BFLY),
    L("Silky Lupine", "Colias philodice", "larval_host", "generalist", _BFLY),
    L("Ascending Milkvetch", "Colias philodice", "larval_host", "generalist", _BFLY),
    L("Silvery Lupine", "Plebejus melissa", "larval_host", "generalist", _BFLY),
    L("Canada Milk Vetch", "Plebejus melissa", "larval_host", "generalist", _BFLY),
    L("Smooth Aster", "Phyciodes cocyta", "larval_host", "generalist", _BFLY),
    L("Lindley's Aster", "Phyciodes cocyta", "larval_host", "generalist", _BFLY),

    # A few adult-nectar links for the new butterflies/moths
    L("Wild Bergamot", "Epargyreus clarus", "nectar", "generalist", _BFLY),
    L("Dotted Blazingstar", "Colias philodice", "nectar", "generalist", _BFLY),
    L("Canada Goldenrod", "Phyciodes cocyta", "nectar", "generalist", _BFLY),
]


def _load(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _save(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")


def main() -> int:
    fauna = _load(_FAUNA)
    have_f = {r.get("scientific_name") for r in fauna}
    added_f = 0
    for rec in NEW_FAUNA:
        if rec["scientific_name"] not in have_f:
            fauna.append(rec)
            have_f.add(rec["scientific_name"])
            added_f += 1

    links = _load(_LINKS)
    have_l = {(r.get("plant"), r.get("fauna"), r.get("relationship"))
              for r in links}
    added_l = 0
    for rec in NEW_LINKS:
        key = (rec["plant"], rec["fauna"], rec["relationship"])
        if key not in have_l:
            links.append(rec)
            have_l.add(key)
            added_l += 1

    _save(_FAUNA, fauna)
    _save(_LINKS, links)
    print(f"fauna: +{added_f} (now {len(fauna)}) | "
          f"links: +{added_l} (now {len(links)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

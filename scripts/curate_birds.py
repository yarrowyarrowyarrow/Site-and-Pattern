#!/usr/bin/env python3
"""
scripts/curate_birds.py — the 67 birds GloBI turned up, decided one by one (F127a).

**Dev-time, run-once, commit the result.** Users never run this.

    python3 scripts/curate_birds.py            # report only, changes nothing
    python3 scripts/curate_birds.py --apply    # write into data/fauna_master.json

Why a script and not a spreadsheet
----------------------------------
F125's sourcing left 10,937 edges blocked on 2,872 animals the catalogue does
not hold. A ``fauna`` row needs a common name, a taxon and a nativity call, and
an interaction record supplies none of them. The birds are the tractable slice:
67 species, all of which have common names, and **81 of their 115 edges are
``fruit_food``** — the bird-forage relationship the V2.59 food-web chain now
depends on.

Every verdict below is **my call from knowledge, with no source behind it** —
the same footing as the 142 fauna rows already shipped, which carry no `source`
field either. That is why it is a diffable table with the reason on every row
rather than 67 silent decisions: an Albertan reading this list can disagree
with a specific line.

The three verdicts
------------------
``include``  regular in Alberta or the prairie provinces — breeding, resident
             or reliably migrant.
``hold``     real but marginal here: edge-of-range, or regular in Manitoba and
             a vagrant in Alberta. Not added; named, so the call is visible.
``reject``   out of range, or introduced. A Gambel's Quail eating something in
             Arizona says nothing about an Alberta yard, and the GloBI query's
             bounding box was North America, not the prairies.

Why every row also carries ``feeds``
------------------------------------
**GloBI's ``eatenBy`` is not ``fruit_food``, and the fetcher assumed it was.**
Of the 33 plants carrying a bird ``fruit_food`` edge, **10 bear no fruit at
all** — Lodgepole Pine, White Spruce, Tamarack, Paper Birch, Trembling Aspen,
Balsam Poplar, Canada Goldenrod, Cut-leaved Anemone, Philadelphia Fleabane,
Showy Milkweed. A White-winged Crossbill on a tamarack is eating **seeds**; a
sapsucker on a birch is drinking **sap**, which the schema cannot express at
all; a hummingbird does not eat fruit in any season.

And in the other direction, GloBI filed three ``flowersVisitedBy`` records for
a **White-crowned Sparrow** — on sagebrush, goldenrod and rabbitbrush. Sparrows
do not nectar. The bird was at the flower gleaning insects.

This is the Monarch bug again: an unspecific verb mapped to a specific claim.
The fix is the same shape as the wind-pollinated nectar gate — refuse what the
record cannot support — except that the deciding fact is about the *animal*, so
it has to live here, beside the nativity call, rather than in the ingester.

``feeds`` lists only what the bird takes **from a plant**:

    fruit   berries and drupes          seeds   seeds, grain, cones
    nectar  floral nectar               buds    buds, catkins, shoots
    sap     drilled sap                 insects (takes nothing from the plant)

Routing, applied by ``scripts/ingest_fauna_edges.py``:

* ``eatenBy`` + ``fruit`` + the plant has fruit data  → ``fruit_food``
* ``eatenBy`` + ``seeds``                             → ``seed_food``
* ``nectar``/``pollen`` + ``nectar``                  → kept
* anything else                                       → **dropped**

Dropped rather than guessed, exactly as mammal browse was. The sapsucker edges
are a real loss and they are recoverable: F128's ``includeObservations=true``
re-fetch carries the body part eaten.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)
_DATA = os.path.join(_ROOT, "data")

#: scientific_name → (verdict, common_name, provinces, feeds, range_notes)
#:
#: `provinces` is the schema-v42 `native_provinces` field: the prairie
#: provinces this species is regular in. `ab_native` is derived from whether AB
#: appears in it, so the two can never disagree.
BIRDS: dict[str, tuple] = {
    # ── Include: regular in Alberta ──────────────────────────────────────
    "Setophaga coronata": (
        "include", "Yellow-rumped Warbler", "AB,SK,MB", "fruit,insects",
        "Abundant breeder in every wooded part of the province."),
    "Lagopus lagopus": (
        "include", "Willow Ptarmigan", "AB,SK,MB", "buds,fruit",
        "Northern boreal and alpine; winters on willow buds."),
    "Lagopus muta": (
        "include", "Rock Ptarmigan", "AB", "buds,fruit",
        "Alpine, above treeline in the Rockies."),
    "Lagopus leucura": (
        "include", "White-tailed Ptarmigan", "AB", "buds,fruit",
        "Alpine specialist of the Rockies; the smallest ptarmigan."),
    "Zonotrichia leucophrys": (
        "include", "White-crowned Sparrow", "AB,SK,MB", "seeds",
        "Breeds in the mountains and the north; a familiar spring migrant "
        "everywhere else."),
    "Zonotrichia albicollis": (
        "include", "White-throated Sparrow", "AB,SK,MB", "seeds,fruit",
        "Boreal and parkland breeder; the clear whistled song of the north."),
    "Agelaius phoeniceus": (
        "include", "Red-winged Blackbird", "AB,SK,MB", "seeds",
        "In every cattail slough on the prairies."),
    "Anser caerulescens": (
        "include", "Snow Goose", "AB,SK,MB", "seeds,buds",
        "Migrates through in enormous flocks; grazes shoots, rhizomes and "
        "seeds of wetland plants."),
    "Anas clypeata": (
        "include", "Northern Shoveler", "AB,SK,MB", "seeds",
        "Abundant prairie-pothole breeder; filters seeds and invertebrates."),
    "Grus canadensis": (
        "include", "Sandhill Crane", "AB,SK,MB", "seeds",
        "Breeds in northern muskeg, stages on the prairies in thousands."),
    "Corthylio calendula": (
        "include", "Ruby-crowned Kinglet", "AB,SK,MB", "insects",
        "Boreal breeder. Takes almost nothing from plants directly."),
    "Loxia leucoptera": (
        "include", "White-winged Crossbill", "AB,SK,MB", "seeds",
        "Boreal resident; crossed bill is a tool for prising conifer cones."),
    "Loxia curvirostra": (
        "include", "Red Crossbill", "AB,SK,MB", "seeds",
        "Nomadic conifer-seed specialist; breeds whenever the cone crop is "
        "good, including midwinter."),
    "Selasphorus calliope": (
        "include", "Calliope Hummingbird", "AB", "nectar",
        "Breeds in the southwestern foothills and mountains — the smallest "
        "bird in Canada."),
    "Sitta carolinensis": (
        "include", "White-breasted Nuthatch", "AB,SK,MB", "seeds",
        "Resident of aspen parkland and river-valley woods."),
    "Sphyrapicus varius": (
        "include", "Yellow-bellied Sapsucker", "AB,SK,MB", "sap",
        "Breeds throughout the aspen belt. Drills sap wells that dozens of "
        "other species then feed at."),
    "Sphyrapicus nuchalis": (
        "include", "Red-naped Sapsucker", "AB", "sap",
        "The southwestern foothills counterpart of the Yellow-bellied."),
    "Tyrannus tyrannus": (
        "include", "Eastern Kingbird", "AB,SK,MB", "fruit,insects",
        "Open-country breeder; switches to fruit in late summer."),
    "Dryocopus pileatus": (
        "include", "Pileated Woodpecker", "AB,SK,MB", "fruit,insects",
        "Resident of mature mixedwood; the crow-sized woodpecker."),
    "Leuconotopicus villosus": (
        "include", "Hairy Woodpecker", "AB,SK,MB", "seeds,insects",
        "Year-round resident. Now placed in Dryobates by most authorities; "
        "the name here is the one GloBI keys on."),
    # NOTE: `Picoides pubescens` is NOT here. It is the Downy Woodpecker under
    # its old genus, and the catalogue already holds it as `Dryobates
    # pubescens`. See SYNONYMS — adding it would have created a second Downy
    # Woodpecker keyed on a name nothing else uses.
    "Dumetella carolinensis": (
        "include", "Gray Catbird", "AB,SK,MB", "fruit",
        "Breeds in dense shrubbery and thickets; heavily frugivorous."),
    "Toxostoma rufum": (
        "include", "Brown Thrasher", "AB,SK,MB", "fruit",
        "Southern and eastern shrublands and shelterbelts."),
    "Empidonax alnorum": (
        "include", "Alder Flycatcher", "AB,SK,MB", "insects",
        "Breeds in wet willow and alder thickets."),
    "Geothlypis trichas": (
        "include", "Common Yellowthroat", "AB,SK,MB", "insects",
        "Cattail marshes and wet shrubbery across the prairies."),
    "Setophaga magnolia": (
        "include", "Magnolia Warbler", "AB,SK,MB", "insects",
        "Boreal spruce-fir breeder."),
    "Leiothlypis celata": (
        "include", "Orange-crowned Warbler", "AB,SK,MB", "insects,nectar",
        "Widespread shrubland breeder; takes nectar and sap more than most "
        "warblers."),
    "Vireo gilvus": (
        "include", "Warbling Vireo", "AB,SK,MB", "insects,fruit",
        "Aspen and poplar canopy; one of the commonest songs of a prairie "
        "river valley."),
    "Vireo olivaceus": (
        "include", "Red-eyed Vireo", "AB,SK,MB", "fruit,insects",
        "Deciduous canopy breeder; largely frugivorous before migration."),
    "Piranga ludoviciana": (
        "include", "Western Tanager", "AB,SK,MB", "fruit,insects",
        "Breeds in the foothills and boreal mixedwood."),
    "Icterus galbula": (
        "include", "Baltimore Oriole", "AB,SK,MB", "fruit,nectar",
        "Breeds in mature deciduous trees, mostly central and eastern."),
    "Pheucticus melanocephalus": (
        "include", "Black-headed Grosbeak", "AB", "seeds,fruit",
        "Breeds in the southern river valleys and foothills."),
    "Pipilo maculatus": (
        "include", "Spotted Towhee", "AB,SK", "seeds,fruit",
        "Dry southern shrublands and coulees."),
    "Quiscalus quiscula": (
        "include", "Common Grackle", "AB,SK,MB", "seeds,fruit",
        "Widespread breeder in towns, shelterbelts and marsh edges."),
    "Sayornis phoebe": (
        "include", "Eastern Phoebe", "AB,SK,MB", "insects,fruit",
        "Nests on bridges and cutbanks near water."),
    "Haemorhous purpureus": (
        "include", "Purple Finch", "AB,SK,MB", "seeds,fruit",
        "Boreal and parkland breeder."),
    "Haemorhous mexicanus": (
        "include", "House Finch", "AB,SK,MB", "seeds,fruit",
        "Native to western North America and a recent colonist of prairie "
        "cities — established, but not a species that was here historically."),
    "Zenaida macroura": (
        "include", "Mourning Dove", "AB,SK,MB", "seeds",
        "Open country and towns across the settled prairies."),

    # ── Hold: real, but marginal here ────────────────────────────────────
    "Melanerpes carolinus": (
        "hold", "Red-bellied Woodpecker", "MB", "fruit,seeds",
        "Eastern species, expanding north-west; regular only in southern "
        "Manitoba and a rarity in Alberta."),
    "Cardinalis cardinalis": (
        "hold", "Northern Cardinal", "MB", "seeds,fruit",
        "Established in southeastern Manitoba; a vagrant in Alberta."),
    "Mimus polyglottos": (
        "hold", "Northern Mockingbird", "", "fruit",
        "Rare but near-annual visitor to the southern prairies; has bred, "
        "but is not a species to plant for here."),
    "Myiarchus crinitus": (
        "hold", "Great Crested Flycatcher", "MB,SK", "fruit,insects",
        "Eastern deciduous species; regular east of Alberta, rare within it."),
    "Piranga olivacea": (
        "hold", "Scarlet Tanager", "MB", "fruit,insects",
        "Eastern; regular in Manitoba, a vagrant further west."),

    # ── Reject: out of range ─────────────────────────────────────────────
    "Calypte anna": (
        "reject", "Anna's Hummingbird", "", "nectar",
        "Pacific coast resident. A rare vagrant inland — the 9 edges it "
        "carries are the largest single loss in this table, and they are "
        "records of a California and coastal-BC bird."),
    "Selasphorus platycercus": (
        "reject", "Broad-tailed Hummingbird", "", "nectar",
        "Southern Rocky Mountains; does not reach Canada."),
    "Selasphorus sasin": (
        "reject", "Allen's Hummingbird", "", "nectar",
        "Coastal California."),
    "Spinus psaltria": (
        "reject", "Lesser Goldfinch", "", "seeds",
        "Southwestern US and Mexico."),
    "Baeolophus bicolor": (
        "reject", "Tufted Titmouse", "", "seeds,fruit",
        "Eastern United States."),
    "Anas fulvigula": (
        "reject", "Mottled Duck", "", "seeds",
        "Gulf coast resident."),
    "Ardea alba": (
        "reject", "Great Egret", "", "insects",
        "A fish-and-frog hunter that eats no plant material — the record is "
        "a food-web artifact, not a feeding observation. Also barely reaches "
        "the prairies."),
    "Callipepla gambelii": (
        "reject", "Gambel's Quail", "", "seeds",
        "Sonoran and Mojave desert."),
    "Colinus virginianus": (
        "reject", "Northern Bobwhite", "", "seeds",
        "Eastern North America; the Canadian populations are introduced."),
    "Columbina passerina": (
        "reject", "Common Ground Dove", "", "seeds",
        "Southern United States and the tropics."),
    "Corvus ossifragus": (
        "reject", "Fish Crow", "", "fruit,seeds",
        "Southeastern United States."),
    "Hylocichla mustelina": (
        "reject", "Wood Thrush", "", "fruit",
        "Eastern deciduous forest; does not reach the prairie provinces."),
    "Melozone crissalis": (
        "reject", "California Towhee", "", "seeds",
        "California and Baja."),
    "Piranga rubra": (
        "reject", "Summer Tanager", "", "fruit,insects",
        "Southern United States."),
    "Polioptila caerulea": (
        "reject", "Blue-gray Gnatcatcher", "", "insects",
        "Southern and central United States."),
    "Sitta pygmaea": (
        "reject", "Pygmy Nuthatch", "", "seeds",
        "Ponderosa pine of the southern Rockies and interior BC."),
    "Sphyrapicus ruber": (
        "reject", "Red-breasted Sapsucker", "", "sap",
        "Coastal British Columbia and the Pacific states."),
    "Poecile rufescens": (
        "reject", "Chestnut-backed Chickadee", "", "seeds,insects",
        "Coastal and interior British Columbia; barely touches Alberta."),
    "Toxostoma curvirostre": (
        "reject", "Curve-billed Thrasher", "", "fruit,seeds",
        "Chihuahuan and Sonoran desert."),
    "Vireo griseus": (
        "reject", "White-eyed Vireo", "", "fruit,insects",
        "Southeastern United States."),

    # ── Reject: introduced, or not a species key ─────────────────────────
    "Sturnus vulgaris": (
        "reject", "European Starling", "", "fruit,seeds",
        "INTRODUCED and invasive across North America. It genuinely eats "
        "chokecherry, which is exactly why this must not become a row: this "
        "app recommends plants FOR the animals it lists, and no part of it "
        "should read as a reason to feed starlings."),
    "Myiopsitta monachus": (
        "reject", "Monk Parakeet", "", "seeds,fruit",
        "Introduced South American parakeet; feral in a few US cities."),
    "Turdus philomelos": (
        "reject", "Song Thrush", "", "fruit",
        "A European bird. Its presence in the results is a reminder that "
        "GloBI is global and the bounding box only narrows it."),
    "Picoides dorsalis bacatus": (
        "reject", "American Three-toed Woodpecker (eastern race)", "", "seeds",
        "A trinomial. The species IS an Alberta resident, but the catalogue "
        "keys fauna on binomials, so a subspecies row would not resolve "
        "against anything. Re-fetching at species rank would recover it."),
}

#: GloBI's name → the name this catalogue already keys on.
#:
#: The woodpecker genera were split and re-merged over the last two decades and
#: GloBI carries the older names. Without this, `Picoides pubescens` would have
#: been written as a **second Downy Woodpecker**, keyed on a name nothing else
#: in the app uses, and its edges would have pointed at the wrong row.
SYNONYMS: dict[str, str] = {
    "Picoides pubescens": "Dryobates pubescens",
}

#: Feeding guilds for the birds the catalogue ALREADY held before F127a.
#:
#: The routing gate has to be total or it silently drops what it does not
#: recognise — which is exactly what the first run did, binning 62 edges
#: belonging to these 24 hand-curated species. Nativity is not restated here:
#: it was decided when the rows were authored. Only the diet is, because only
#: the diet is what `route_bird` asks about.
#:
#: An **empty set is meaningful**: a Red-tailed Hawk takes nothing from a
#: plant, so every plant record for one is a food-web artifact and drops. That
#: is different from a bird nobody has assessed, and the two report separately.
SEEDED_FEEDS: dict[str, str] = {
    "Bombycilla cedrorum":   "fruit",
    "Bombycilla garrulus":   "fruit",
    "Turdus migratorius":    "fruit,insects",
    "Spinus tristis":        "seeds",
    "Spinus pinus":          "seeds",
    "Acanthis flammea":      "seeds",
    "Junco hyemalis":        "seeds",
    "Sitta canadensis":      "seeds",
    "Melospiza melodia":     "seeds,fruit",
    "Cyanocitta cristata":   "seeds,fruit",
    "Pica hudsonia":         "fruit,seeds",
    "Perisoreus canadensis": "fruit,seeds",
    "Pinicola enucleator":   "seeds,fruit,buds",
    "Bonasa umbellus":       "buds,fruit,seeds",
    "Colaptes auratus":      "fruit,seeds,insects",
    "Dryobates pubescens":   "seeds,insects",
    "Poecile atricapillus":  "seeds,insects",
    "Archilochus colubris":  "nectar",
    "Selasphorus rufus":     "nectar",
    "Setophaga petechia":    "insects",
    # Raptors and owls. Nothing from a plant, ever.
    "Buteo jamaicensis":     "",
    "Bubo virginianus":      "",
    "Falco columbarius":     "",
    "Falco sparverius":      "",
}

_ICON = "🐦"


def _rows(path):
    with open(path, "r", encoding="utf-8") as fh:
        blob = json.load(fh)
    return blob if isinstance(blob, list) else next(
        v for v in blob.values() if isinstance(v, list))


import collections


def curate() -> dict:
    """The decision table as records, plus what each verdict costs in edges."""
    cands = _rows(os.path.join(_DATA, "fetched",
                               "fauna_edges_candidates.json"))
    held = {h["scientific_name"] for h in _rows(
        os.path.join(_DATA, "fetched", "fauna_new_species.json"))
        if h.get("taxon") == "bird"}
    edge_n = collections.Counter(
        (c.get("fauna") or "").strip() for c in cands
        if (c.get("fauna") or "").strip() in held)

    missing = sorted(held - set(BIRDS) - set(SYNONYMS))

    # How many of a bird's candidate edges actually SURVIVE the diet routing —
    # not how many GloBI offered. The difference decides whether the row is
    # worth writing at all: a Yellow-bellied Sapsucker's every record is a sap
    # record, and the schema has no word for sap, so adding the species would
    # put an animal in the catalogue connected to nothing. The repo has fought
    # orphan fauna before (V2.42 took them 56 → 3) and a test holds the line.
    fruiting = set()
    for name in ("plants_master.json", "garden_plants.json"):
        for p in _rows(os.path.join(_DATA, name)):
            if p.get("common_name") and (
                    (p.get("fruit_period") or "").strip()
                    or (p.get("fruit_form") or "").strip()):
                fruiting.add(p["common_name"].strip().lower())
    routable: collections.Counter = collections.Counter()
    for c in cands:
        animal = (c.get("fauna") or "").strip()
        row = BIRDS.get(animal)
        if not row or row[0] != "include":
            continue
        if _route(c.get("relationship") or "",
                  {f for f in row[3].split(",") if f},
                  (c.get("plant") or "").strip().lower() in fruiting):
            routable[animal] += 1

    out = {"include": [], "hold": [], "reject": [], "missing": missing,
           "edges": {}, "orphans": []}
    for name, (verdict, common, provinces, feeds, notes) in BIRDS.items():
        out[verdict].append({
            "scientific_name": name,
            "common_name": common,
            "taxon": "bird",
            "ab_native": 1 if "AB" in provinces.split(",") else 0,
            "native_provinces": provinces,
            "range_notes": notes,
            "icon": _ICON,
            "description": notes,
            "_feeds": feeds,
            "_edges": edge_n.get(name, 0),
            "_routable": routable.get(name, 0),
        })
    for v in ("include", "hold", "reject"):
        out[v].sort(key=lambda r: -r["_edges"])
        out["edges"][v] = sum(r["_edges"] for r in out[v])
    out["orphans"] = [r for r in out["include"] if not r["_routable"]]
    out["writable"] = [r for r in out["include"] if r["_routable"]]
    return out


def _route(rel: str, feeds: set, plant_has_fruit: bool) -> str:
    """Local copy of ``ingest_fauna_edges.route_bird``'s decision.

    Duplicated on purpose and pinned by a test that runs both over the same
    inputs: importing the ingester here would make the two scripts import each
    other, since the ingester already imports this one for the feeds map.
    """
    if not feeds:
        return ""
    if rel in ("nectar", "pollen"):
        return rel if "nectar" in feeds else ""
    if rel == "fruit_food":
        if "fruit" in feeds and plant_has_fruit:
            return "fruit_food"
        return "seed_food" if "seeds" in feeds else ""
    return rel


def feeds_map() -> dict:
    """``scientific_name → set(feeds)`` for every bird the gate must judge.

    Consumed by ``ingest_fauna_edges.py``. A bird **absent** from this map has
    no edge written, which is the point: an animal nobody has decided about
    must not arrive through a relationship record. A bird **present with an
    empty set** is a decision too — a hawk takes nothing from a plant — and the
    two report separately.

    Covers the 38 newly included birds *and* the 24 the catalogue already held.
    Leaving the latter out is not neutral: the first run of this gate binned 62
    of their existing edges for being "uncurated".
    """
    out = {name: {f for f in row[3].split(",") if f}
           for name, row in BIRDS.items() if row[0] == "include"}
    out.update({name: {f for f in feeds.split(",") if f}
                for name, feeds in SEEDED_FEEDS.items()})
    return out


def _report(c: dict) -> None:
    print("=" * 66)
    for v in ("include", "hold", "reject"):
        print(f"  {v:8s} {len(c[v]):3d} species   {c['edges'][v]:4d} candidate "
              f"edges")
    print(f"  writable {len(c['writable']):3d} species   "
          f"{sum(r['_routable'] for r in c['writable']):4d} edges survive the "
          f"diet routing")
    print("=" * 66)
    if c["orphans"]:
        print(f"\nincluded but NOT written — every record drops, so a row here "
              f"would be an animal connected to nothing:")
        for r in c["orphans"]:
            print(f"  {r['_edges']:3d} candidate  {r['common_name']:34s} "
                  f"{r['_feeds']}")
    if c["missing"]:
        print(f"\n!! {len(c['missing'])} held birds are not in this table — the "
              f"candidate file has changed:")
        for m in c["missing"]:
            print(f"     {m}")
    for v in ("include", "hold", "reject"):
        print(f"\n{v.upper()}")
        for r in c[v]:
            print(f"  {r['_edges']:3d}  {r['common_name']:38s} "
                  f"{r['native_provinces'] or '—':9s} {r['_feeds']}")


def _apply(c: dict) -> None:
    path = os.path.join(_DATA, "fauna_master.json")
    rows = _rows(path)
    have = {(r.get("scientific_name") or "").strip() for r in rows
            if isinstance(r, dict)}
    new = [{k: v for k, v in r.items() if not k.startswith("_")}
           for r in c["writable"] if r["scientific_name"] not in have]
    if not new:
        print("every included bird is already in fauna_master.json.")
        return
    rows.extend(new)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(rows, fh, indent=1, ensure_ascii=False)
    print(f"wrote {len(new)} bird rows into "
          f"{os.path.relpath(path, _ROOT)}")
    print("\nNEXT: python3 scripts/ingest_fauna_edges.py --apply, then bump "
          "_SCHEMA_VERSION.")


def main() -> int:
    ap = argparse.ArgumentParser(description="Curate the GloBI birds (F127a).")
    ap.add_argument("--apply", action="store_true",
                    help="write the included birds into data/fauna_master.json")
    args = ap.parse_args()
    c = curate()
    _report(c)
    if args.apply:
        print()
        _apply(c)
    else:
        print("\n(report only — re-run with --apply to write)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

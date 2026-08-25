# Where the data came from, and what we owe for it

Every fact and every photograph this app ships, with its source and its licence.
Written so that the question *"are you allowed to have that?"* has an answer that
can be checked rather than asserted.

The app itself is [PolyForm Noncommercial 1.0.0](../LICENSE). That matters here:
several of the terms below are easier to satisfy for a noncommercial project than
they would be for a product, and a few of the choices only make sense in that
light.

> **This document is now reachable from inside the app** (V2.42) —
> **Help → "Where This Data Came From…"**, built by `src/data_sources_flow.py`
> from the live database and `data/sources_master.json`, so its numbers cannot
> go stale. It had been referenced only from code comments, which meant the
> careful answer below was invisible to the people it was written for: a user
> could not tell a sourced record from an invention, and well-sourced data that
> nobody can check is worth nothing to them.
>
> The machine-readable bibliography is
> [`data/sources_master.json`](../data/sources_master.json) — every `source`
> field in the biological seed data resolves to a key there, enforced by
> `src/data_quality.py:validate_plant_fauna`. Coverage and gap numbers are in
> [`DATA_AUDIT.md`](DATA_AUDIT.md).

---

## The short version

| | |
|---|---|
| Photographs | **Sound.** Every one is CC0 / CC BY / CC BY-SA, credited per photo, and a test fails the build if a credit goes missing. |
| Ecoregion range per species | **Sourced, and V2.75 found two things wrong with how.** The tags were once generated heuristically and never sourced; schema v59 replaced them with counts derived from GBIF occurrence records, each row carrying its evidence. Then an outside review asked where in the ecoregion those records were, and checking turned up a **5 km proximity buffer** reaching the derivation from site detection (16.4% of points inside the layer are credited to two or more regions) and a spatial join running against the display-simplified polygons. **Both are fixed and the data is re-derived (V2.76).** Re-fetched from GBIF on 2026-08-21 and derived by containment: 489,546 attributed records became **361,447**, and 493 of 4,218 region claims proved to have almost no records inside them. The error was **concentrated, not scattered** — `western_continental_ranges` is a BC region clipped to a hairline inside Alberta (0.02% of the layer), so a five-kilometre apron many times its own area was sweeping in every montane record near the border. It went from **135 species to 15**. `/method/` states this to readers rather than restating the numbers quietly. |
| Nativity per province | **The weakest claim in the catalogue, and it is being replaced.** `native_provinces` was *generated* from a hand-authored `native_to_alberta` boolean plus the plant's ecoregion tags — no plant record carries a citation of any kind. V2.75 retired the generator (it had gone stale against a vocabulary replaced two releases earlier) and shipped the machinery to source it from VASCAN. Until that fetch runs, treat "native to AB, SK" as the catalogue's assertion, not a sourced fact. |
| Flower morphology | **Was a gap, now recorded.** The numbers are genus-level botanical judgement. Until V2.36 nothing said so per species; now `flower_data_source` and `flower_data_citation` do. |
| Everything else | Named below. Nothing is scraped, and nothing is copied out of a copyrighted flora. |

---


## Occurrence coordinates (V2.80)

**Source:** GBIF, cached by `scripts/seed_ecoregion_ranges.py`, filtered and
shipped by `scripts/seed_occurrence_points.py` as
`data/plant_occurrence_points.json`. 171,896 marks over 426 species, drawn on
every species page.

**A coordinate is held to a different licence bar than a photograph, and that
is a deliberate decision the author made in V2.79.**

| | photographs | occurrence coordinates |
|---|---|---|
| constant | `fetch_inaturalist_images.ACCEPT_LICENSES` / `PUBLISHABLE` | `PUBLISHABLE_COORDINATES` |
| CC0, CC BY | published | published |
| **CC BY-NC** | **withheld** | **published** |
| unknown / unspecified | withheld | withheld |

The reasoning: *a photograph is redistributed as a work; a coordinate is a fact
about a place.* Where a plant was recorded is not authored, and a dot on a
distribution map is not a republication of the observer's creative work, so the
NonCommercial term — which governs commercial reuse of the work — does not
reach it. The photograph rule is untouched and a test asserts the coordinate
set is a strict superset of it.

The split is not academic. Of 365,092 records that are inside Alberta or
Saskatchewan and precise enough to draw, **329,267 are CC BY-NC observations**:
the entire iNaturalist layer. Holding coordinates to the photograph bar
published a map that was 94% herbarium specimens and called it the observation
record.

**Three filters, all disclosed on `/method/`:** coordinate uncertainty over
10 km is refused, records outside the two provinces are dropped (F142), and a
dataset absent from the licence table is dropped rather than assumed
permissive. Records closer together than 0.01° are drawn once, which is under
half a pixel at the size the maps are shown.

**Not shipped:** `data/fetched/plant_occurrences.json`, the raw cache. It is a
dev artefact holding 559,502 unfiltered records including the ones no licence
permits redrawing.


## Photographs

**Source:** iNaturalist, via `scripts/fetch_inaturalist_images.py`.

The script queries the taxa endpoint by scientific name, requires an **exact**
name match (so a photo is never attached to the wrong species), and takes the
first photo whose licence is in a redistributable whitelist:

```
ACCEPT_LICENSES     = {cc0, cc-by, cc-by-sa}          # plants and most fauna
BEE_ACCEPT_LICENSES = {cc0, cc-by}                    # stricter, no ShareAlike
```

NonCommercial, NoDerivatives and all-rights-reserved photos are **skipped**, not
downgraded or used anyway.

**What we owe:** attribution. CC BY and CC BY-SA both require the photographer be
credited wherever the photo appears. Every photo carries an `attribution` string
verbatim from iNaturalist, and it is rendered by one shared formatter —
`src/image_cache.py:credit_line` — at every call site
(`plant_list_view.py`, `analysis_panel.py`, `scene_dossier.py`). The formatter
exists precisely because three call sites once built that string separately and
one of them dropped the licence.

**Enforced, not just intended:** `src/data_quality.py` fails validation if any
non-CC0 photo has an empty attribution — for plant photos
(`validate_plant_images`), for fauna photos with the stricter CC0/CC-BY bar on
bees (`validate_fauna_images`), and for the `plant_photos` table
(`validate_photo_coverage`). It is a build error, not a warning.

> **Corrected in V2.42.** This paragraph previously credited
> `validate_fauna_images` with covering `plants.image_url`. It does not — that
> function filters `taxon != "bee"` over `fauna_master.json` and never opens the
> plant catalogues. Plant photo credits were unenforced for as long as the claim
> stood, and were clean only because whoever added them was careful: 323 of 323
> attributed and licensed. `validate_plant_images` is the check the sentence
> described, written in V2.42 to make the claim true.

**On ShareAlike.** CC BY-SA obliges you to license *adaptations* under the same
terms. The photos are shown alongside the app, not modified into it — a mere
aggregation — so the obligation does not reach the source code. Photos are
downscaled for caching, which is not an adaptation in the licence's sense;
if that ever becomes a concern the CC0/CC-BY subset alone would still cover most
of the catalogue.

**Why 62 of 69 bees have no photograph.** Not an oversight. Bee photos are held
to the stricter CC0/CC-BY bar and most iNaturalist bee photos are NonCommercial.
The V2.33 procedural bee models exist because of that decision.

### Your own photographs

`src/photo_import.py` strips EXIF from every imported image, **unconditionally
and with the standard library** so it cannot be skipped by Pillow being absent.
A photo of your own yard carries your home's GPS coordinates and the natural next
step for a photo you like is to commit it somewhere public. That is a privacy
property of this project, not a feature of the importer.

Photos imported as `origin='user'` stay on the user's machine and are never
shipped. Photos you choose to ship go in `data/photos/` with `source: "owner"`
and whatever licence you set (default CC BY-SA 4.0) — they are yours to license.

---

## Flower and plant morphology

**Source:** the seven `scripts/seed_*_morphology.py` files. Assignment is **by
genus**, from the standard floral formulae and inflorescence types that every
flora of the prairie provinces and boreal Canada keys on — Asteraceae heads,
Fabaceae papilionaceous flowers, Apiaceae umbels, Lamiaceae bilabiate whorls,
Rosaceae five-petalled cymes, Brassicaceae crosses, Liliaceae six-tepalled stars.
The bibliography is [`REFERENCES.md`](REFERENCES.md).

Nothing was copied from any flora. These are the conventions of the family, which
is why the values are *typical* rather than authoritative — and why the catalogue
now says so per species:

| column | records | added |
|---|---|---|
| `flower_data_source` | what KIND of source: `estimated` / `photo` / `flora` / `measured` | v55 |
| `flower_data_citation` | WHICH source: `FNA vol. 21`, `Budd's 442`, `my yard 2026-07-12` | v56 |

Today essentially every flowering species reads `estimated` with a blank
citation, and that is the honest state. The seeder deliberately writes **no**
citation rather than naming a flora, because naming a book nobody opened for that
species would be a worse lie than an empty field.

`scripts/tune_morphology.py` is where those get raised as species are actually
checked.

---

## Reading numbers out of a published flora

The precise numbers — ray counts, head diameters, laminae lengths — are published,
principally in **Flora of North America**. They are free to read and they are not
free to bulk-copy. Since somebody is eventually going to want to fill 300 species
from published descriptions, here is the position this project takes.

**Facts are not copyrightable; the sentences around them are.** *CCH Canadian Ltd
v Law Society of Upper Canada*, 2004 SCC 13 (Canada) and *Feist Publications v
Rural Telephone*, 499 U.S. 340 (1991) (US) both hold that facts and
sweat-of-the-brow compilation are outside copyright. A person reading "ray florets
8–21" and typing 8 and 21 into a database is recording facts.

**Three things that does not settle:**

1. **A compilation can be protected where its selection and arrangement are
   original.** Extracting the same four fields from all 400+ species and building
   a database out of them resembles copying the compilation more than noting a
   fact. "We only took numbers" is not a complete answer to this.
2. **A flora's range is a judgement, not an observation.** It is a botanist's
   synthesis of what is typical across many specimens — nearer to authorship than
   a boiling point is.
3. **Copyright is not the only constraint.** A site's Terms of Use are a contract
   and can forbid automated access whatever copyright allows. `robots.txt` is a
   convention rather than law, but disregarding it is what gets a project blocked
   and publicly criticised.

**Who holds what.** eFloras.org hosts *Flora of North America*, © **Flora of North
America Association**, with the site operated by **Missouri Botanical Garden** and
**Harvard University Herbaria**; the volumes are published by Oxford University
Press. At least three parties could object.

### What this project does about it

**Use the freer sources first.** Most of the characters the 3D generator needs do
not require a flora at all — petal count, symmetry, petal shape, inflorescence
architecture, disc colour, basal rosette and branching are all readable off a
photograph the app already holds a licence to, and flowering-stem count and bloom
height come off a habit shot. **Only flower diameter in centimetres genuinely
needs a ruler or a published description.** That is one field, not four.

In rough order of how freely the numbers may be reused:

| Source | Terms | Has the numbers? |
|---|---|---|
| **A photograph the app already ships** | already licensed | everything except diameter |
| **Budd's *Flora of the Canadian Prairie Provinces*** (Agriculture Canada pub. 1662) | Government of Canada publication; non-commercial reproduction terms are permissive | yes, **and it is the right region** |
| **Wikipedia / Wikispecies** | CC BY-SA — reuse permitted with credit | often |
| **USDA PLANTS** | public domain | stops at bloom period and colour |
| **Flora of North America** (eFloras) | © FNAA — free to read, not to copy | yes, and most precisely |
| **TRY / BIEN** | data request; mostly not redistributable | leaf/seed/height, little floral |

**A reading aid, built so it cannot become a scrape.** `src/flora_read.py` will
read the four numbers off *one* page, and the constraints are structural rather
than promised:

- **off unless `scripts/tune_morphology.py --flora-fetch`** — turning it on is a
  decision made at a command line by someone who has read the site's terms;
- **`robots.txt` checked before every request**, fail-closed (an unreachable
  robots.txt means no), and the UI cannot override it;
- **one species per click.** There is no function that takes a list and none that
  iterates the catalogue. Adding one would be the whole change and would show in
  a diff;
- **only the numbers.** The prose is never stored, never written to the catalogue
  and never cached — the module has no cache;
- **nothing saves itself.** The result is a proposal in the bench's sliders that a
  person approves against the render;
- **the citation is filled in automatically** on that path, so a number read from
  a description always says where it was read.

**The better move is to ask.** A short letter to the Flora of North America
Association — a noncommercial native-plant app, ~400 species, four numbers each,
cited per species — costs a day and, answered yes, removes the question entirely.
A draft is in [`FNA_PERMISSION_LETTER.md`](FNA_PERMISSION_LETTER.md).

---

## Everything else

| Data | Source | Terms |
|---|---|---|
| Species list, habitat and culture data | Native-plant references for Alberta and the prairie provinces (see [`REFERENCES.md`](REFERENCES.md)); compiled for this project | ours |
| Toxicity / pet-and-child safety | `scripts/apply_safety_tags.py`, each record carrying its own `safety_source` string | ours, sourced per record |
| Hardiness zones | Natural Resources Canada plant hardiness data | Government of Canada |
| Soil | Gridded Soil Landscapes of Canada (AAFC); SoilGrids v2.0 (ISRIC, `rest.isric.org`) | GoC open data; ISRIC CC BY 4.0 |
| Elevation / terrain | Open-Meteo elevation API (Copernicus DEM 30 m) | Copernicus free and open |
| Building footprints & existing trees | OpenStreetMap via Overpass (`src/osm_features.py`, `src/building_downloader.py`) | **ODbL — share-alike applies to the data**, credited on the map |
| Geocoding | Nominatim (OpenStreetMap) | ODbL; usage policy requires a descriptive User-Agent |
| Climate and wind | [Open-Meteo](https://open-meteo.com/) (ERA5-Land archive + forecast) | free for non-commercial use, CC BY 4.0 |
| Map tiles | OpenStreetMap + CARTO; Esri and Mapbox satellite layers | attributed in the Leaflet control (`html/map/01-core.js`, `05-features.js`) |
| Fauna records and plant↔fauna links | Compiled for this project from published host-plant and pollinator literature | ours |
| **Ecoregion polygons** | Rectangular approximations drawn for this project (V1.36), to be replaced by **CEC Level III Ecoregions of North America** via `scripts/prepare_ecoregions.py` — *check the CEC's terms before committing that output* | ours today; CEC terms apply once regenerated |
| **Per-species ecoregion range** (schema v59) | [GBIF](https://www.gbif.org/) occurrence search — georeferenced records intersected with the polygons above by `scripts/seed_ecoregion_ranges.py`. **Only the derived counts are published to the website**: each row is "N georeferenced records fall inside this region", which is a number we computed. Every row ships its count, a confidence band and the retrieval date. **Counts are inflated by about 0.8%** where two simplified polygons overlap at a shared border and one record satisfies both (V2.78, mostly Calgary); left in place and disclosed on `/method/` rather than resolved by guessing a side. **The raw points are cached in `data/fetched/plant_occurrences.json`** (V2.75) so a re-derivation costs no network — the app never reads it and the website never publishes it, but it IS committed to a public repository, so this row said "not redistributed" for one increment while it was. **Corrected in V2.77**, and the licences were then looked up rather than assumed: `scripts/fetch_dataset_licences.py` asked GBIF per dataset (224 of them) and got **61 CC0, 82 CC-BY, 81 CC-BY-NC**. All three permit redistribution; CC-BY and CC-BY-NC require attribution, which the cache file carries per record as `dataset_key`, and CC-BY-NC restricts commercial use, which this repository's own PolyForm Noncommercial licence already does. Drawing the points on a public page is a further step and has not been taken — see the "Publish the occurrence points" backlog entry | GBIF's search API is open and the derived counts are ours. The cached points are GBIF's records, redistributed here under the publishers' own CC licences with `dataset_key` attribution; per-dataset licence tokens are in `data/fetched/dataset_licences.json` |
| **Nativity and accepted names** (V2.75, machinery only) | [VASCAN](https://data.canadensys.net/vascan/), the Database of Vascular Plants of Canada, via `scripts/fetch_flora_nativity.py`. One request per species returns `establishmentMeans` **per province** and the accepted name with synonym status — the two things this catalogue has never had. Only the derived verdict is stored, per species: which provinces VASCAN calls it native in, whether the name is superseded, and `unstated` where VASCAN says nothing. **The fetch had not been run when this was written**; the container's egress policy answers 403 to `data.canadensys.net` | VASCAN is published under CC BY 4.0 by the Canadensys network; attribution is owed and is given here and on the website |
| **Botanical diagrams** — the 33 leaf shapes, inflorescence architectures and leaf arrangements | Drawn as code in [`html/botany/diagrams.js`](../html/botany/diagrams.js) from the botanical definitions. **Not traced from any published figure**, which matters because good ones exist and are copyrighted: a raceme is a raceme, the term is nobody's property, and the drawing is ours. Committed to `docs/img/botany/` by `scripts/render_botany_diagrams.js` | ours |
| **Fauna diagrams** — wing shapes, wing patterns, resting postures, flight styles, bee builds, scopa positions | As above, in [`html/botany/fauna.js`](../html/botany/fauna.js) → `docs/img/fauna/` | ours |
| **Fauna morphology** (schema v58) — bumblebee band patterns, wingspans, wing colours and shapes, flight styles | Genus-level and field-mark-level judgement in `scripts/seed_fauna_morphology.py`, carrying forward what `src/scene_wildlife.py` already asserted. **Every record ships `morph_data_source: estimated` with a blank citation.** Nothing is copied from a key or a plate; a band pattern here is what a species is generally described as, not a transcription. Raised to `photo`/`flora`/`measured` in `scripts/tune_fauna.py` as somebody checks it — at which point the citation becomes mandatory. The position on reading facts out of a copyrighted guide is the same one argued above for floras: **"T2 orange" is a fact, and facts are nobody's property** | ours, per-record provenance |

### What is deliberately absent

**No Indigenous ecological knowledge, land-management practice, plant-use
tradition or design framework is encoded anywhere in this app** — not in the seed
data, not in recommendations, not in the UI. This is Principle 12: such knowledge
is honoured through relationship, not extraction, and incorporating it requires
free, prior and informed consent from the communities it belongs to. Until that
consent exists, references in [`REFERENCES.md`](REFERENCES.md) are *directional
only*. The `plant_photos.notes` field and the morphology seeders both carry this
constraint in their own comments, because that is where somebody would be tempted
to put it.

---

## If you think we have got something wrong

Open an issue. If a photograph of yours is here and you would rather it were not,
or the credit is wrong, say so and it will be removed or fixed — that is a same-day
job, not a negotiation.

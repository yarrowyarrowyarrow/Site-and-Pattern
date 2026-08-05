# Biological data audit — V2.42

*What we ship, where it came from, and where the holes are.*

This is a provenance audit of the shipped biological seed data: the plant
catalogue, the fauna registry, the plant↔fauna relationships, the morphology
attribute files, and the photographs. It answers two questions a user is
entitled to ask — **"is this real?"** and **"is this yours to give me?"** — and
records honestly where the answer is currently "we can't show you".

Counts are as of V2.42 and were computed from `data/*.json` directly, not
carried over from earlier docs. Companion docs: `docs/DATA_SOURCES.md` (the
licence and copyright position), `docs/DATA_GAPS.md` (the morphology debt),
`docs/REFERENCES.md` (the bibliography).

---

## The short version

**The flora↔fauna relationships are better sourced than they look.** All 361
of them carry a real bibliographic citation naming a real work — Acorn &
Sheldon, Pohl et al., Cornell's *Birds of the World*, Wilson & Carril, Packer,
Pattie & Fisher. Not one is a bare `"literature"` filler, and every plant and
animal name in the file resolves against the catalogues.

**But a user cannot see a single one of them.** `plant_fauna.source` survives
the database, the edges layer and the view model, and is then dropped by every
widget that renders a relationship. The only citations the app shows on screen
are photo credits and weather/soil source strings. *The ecology itself is
uncited in the UI* — so a user has no route to the conclusion the data would
support.

**The doc chain that would let them check is broken at both ends.** None of the
six works actually cited in `data/*.json` appears in `docs/REFERENCES.md` or
`docs/DATA_SOURCES.md`. `DATA_SOURCES.md` tells the reader to see
`REFERENCES.md` for species data, and `REFERENCES.md` is design-philosophy
books with no floras and no entomology.

So the problem is not missing sources. It is that **the sourcing is unverifiable
from outside the JSON**, and **nothing enforces that it stays true**.

---

## 1 · Plant ↔ fauna relationships

`data/plant_fauna_master.json` — 362 records = 1 metadata header + **361 edges**.

### Citation coverage

| Measure | Value |
|---|---|
| Edges with a non-empty `source` | **361 / 361 (100%)** |
| Distinct source strings | 11 |
| Distinct *works* those strings name | **6** |
| Edges with a URL, DOI or page number | **0 / 361** |
| Edges with a 4-digit year in the source | 216 / 361 (60%) |
| Edges with a `notes` explanation | 73 / 361 (20%) |
| Plant / fauna names that fail to resolve | **0** |

### The eleven strings, and the six works behind them

```
 74  Acorn & Sheldon 2006                                    ┐
 51  Acorn & Sheldon 2006, Butterflies of Alberta            ├ one book, 3 spellings, 141 edges
 16  Prairie-composite pollination literature; Acorn & …     ┘
 65  Birds of the World                                      ┐ one source, 2 spellings, 98 edges
 33  Cornell Birds of the World                              ┘
 33  Pohl et al. 2018                                        ┐ one work, 2 spellings, 47 edges
 14  Pohl et al. 2018 (Moths of Alberta)                     ┘
 28  Wilson & Carril 2015
 25  Packer, Bees of Canada
 16  Acorn, Bugs of Alberta
  6  Pattie & Fisher, Mammals of Alberta
```

Three findings from this table:

1. **Citation is at *work* level, never at page level.** A source names a book;
   it never says where in the book. Nothing here is checkable without reading a
   whole flora.
2. **The file's own manifest is incomplete.** The header `_sources` block
   declares four works. Six are actually used — **Packer (*Bees of Canada*),
   Pattie & Fisher (*Mammals of Alberta*) and Acorn (*Bugs of Alberta*) are
   cited on 47 edges but declared nowhere.**
3. **One string is not a citation.** `"Prairie-composite pollination
   literature; Acorn & Sheldon 2006"` (16 edges) — the first half names no
   work. It is the only genuine non-citation in the file.

### `notes` coverage is a fingerprint of two authoring passes

| Edges | With notes | Source string |
|---:|---:|---|
| 51 | **51 (100%)** | Acorn & Sheldon 2006, Butterflies of Alberta |
| 74 | 2 (3%) | Acorn & Sheldon 2006 |
| 65 | 1 (2%) | Birds of the World |
| 33 | 0 (0%) | Pohl et al. 2018 |
| 14 | 0 (0%) | Pohl et al. 2018 (Moths of Alberta) |

One pass wrote a human explanation for every edge it added. The others added
edges in bulk. The 51-edge block is the quality bar the rest should be held to.

### Coverage — the number that matters most

| | |
|---|---|
| Plants with **any** fauna edge | **99 / 439 (22.6%)** — 340 plants have none |
| Fauna with any plant edge | 86 / 142 |
| **Orphan fauna** (in the registry, connected to nothing) | **56 — of which 53 are bees** |
| Edge kinds | nectar 119 · larval_host 116 · pollen 37 · seed_food 33 · fruit_food 26 · cover 19 · nesting 11 |
| Specialist vs generalist | 31 specialist / 330 generalist |

**22.6% is the denominator under every relationship feature in the app** — the
Habitat Value Score, the "hosts 7 caterpillars" labels, the food-web score, the
specialist spotlight, the relationship-web overlay (P3, P10). Three-quarters of
the catalogue reads as ecologically inert because nobody has written its edges
yet, not because it is.

The 53 orphan bees are the sharpest instance: they carry `floral_host_genera`
in `bee_attributes_master.json`, and `src/bee_habitat.py` already infers hosts
from that field at runtime for one panel — but those inferences are never
promoted to edges, so the graph does not know about them.

---

## 2 · Morphology attributes

| File | Records | `*_data_source` | Citations |
|---|---:|---|---:|
| `plants_master.json` — flower | 434 | `estimated` ×307, **absent ×127** | **0** |
| `plants_master.json` — leaf | 434 | **absent on all 434** | **0** |
| `bee_attributes_master.json` | 69 | `estimated` ×69 | **0** |
| `lepidoptera_attributes_master.json` | 31 | `estimated` ×31 | **0** |

Every morphology value in the app is the seeder's estimate. This is already
disclosed honestly in `docs/DATA_GAPS.md` and warned about by the data-quality
gate, and the tuning benches exist to fix it species by species. Two notes:

- **`leaf_data_source` is referenced by `src/db/schema.sql` and
  `src/data_quality.py` but appears in zero records.** `DATA_GAPS.md` states
  every record reads `estimated`; in fact the field is absent, so a reseed
  writes the schema default `''`. The validator's error branch can therefore
  never fire — it is a tripwire wired to nothing.
- The attribute files *do* carry good work-level `source` strings even though
  their per-field citations are blank — the bee file credits the Alberta Native
  Bee Council, Sheffield et al. 2014 and Wilson & Carril 2015; the lep file
  splits across Acorn & Sheldon 2006, Pohl et al. 2010 and Bird et al. 1995.
  That provenance is real and is currently invisible for the same reason the
  edge sources are.

---

## 3 · Photographs — the part that is already right

| | Plants | Fauna |
|---|---:|---:|
| Records with an image | 323 / 434 | 58 / 142 |
| **Unattributed** | **0** | **0** |
| **Unlicensed** | **0** | **0** |
| Licences | cc-by 183 · cc-by-sa 97 · cc0 43 | cc-by 38 · cc-by-sa 13 · cc0 7 |

Every photograph carries `image_attribution` and `image_license`, every licence
is inside the CC whitelist, and the 7 bee photos are all CC0/CC-BY — the
stricter bar `src/data_quality.py` holds bees to. One shared `credit_line`
formatter renders them (`src/image_cache.py:199`), the 3D inspector asserts the
credit is not optional, and the build fails on an uncredited non-CC0 photo.

**This is the model.** The photo pipeline answers "is this yours to give me?"
rigorously and mechanically. The ecological data does not, yet.

Safety data is the other bright spot: **49 / 49** toxicity-tagged plants carry a
`safety_source`. Nothing enforces it — it is simply done.

---

## 4 · What is not enforced

`scripts/check_plant_data.py` today: **0 errors, 20 warnings.**

- **The gate never opens `plant_fauna_master.json`.** `validate_all()`
  (`src/data_quality.py:580`) checks the plant catalogues, bee attributes, fauna
  images, morphology provenance and photo coverage — never the relationships.
  That 361/361 edges are sourced is an accident of authorship, not an invariant.
  A future unsourced edge would ship silently.
- **The seeder drops unresolvable edges without a word.**
  `src/db/plants.py:1137` — `if pid is None or fid is None: continue`. Today all
  361 resolve, so this is a latent risk rather than a live bug; a typo in a
  plant name would delete an edge with no error and no count.
- **`evidence` does not mean what it says.**
  `src/db/relationships.py:180` hardcodes `evidence="documented"` for everything
  out of the SQL view. A cited Monarch↔milkweed record and an **uncited
  companion-planting folk pairing read identically as `documented`.** The
  companion tables (`schema.sql:200-210`) have no sourcing columns at all, and
  the `relationship_edges` view hardcodes `''` for them — companion planting is
  the most folklore-prone data in the app and the least attributed.
- **`validate_plant_images()` does not exist**, though `DATA_SOURCES.md:49-52`
  says the gate enforces plant photo credits via `validate_fauna_images` — that
  function filters `taxon != "bee"` on `fauna_master.json` and never touches
  plants. The plant photos happen to be clean; nothing checks them.
- **The fauna bench has no provenance guard.** `scripts/tune_morphology.py:190`
  refuses a correction that the next seeder run would overwrite;
  `scripts/tune_fauna.py` has the `PROVENANCE` tuple but no equivalent check, so
  it accepts corrections that will be silently deleted.

---

## 5 · Ranked gaps

| # | Gap | Why it ranks here |
|---|---|---|
| 1 | **Sources invisible in the UI** | The data is defensible and the user cannot tell. Directly blocks "know that it's legitimate". Cheapest fix on the list — the strings are already at the call site. |
| 2 | **77% of plants have no fauna edge** | Silently weakens every P3/P10 feature and the Habitat Value Score. |
| 3 | **No enforcement on relationship sourcing** | Today's 100% is luck. Without a gate it decays on the next bulk add. |
| 4 | **`evidence` conflates cited and uncited** | The app makes a provenance claim it cannot support, on its folklore-prone data. |
| 5 | **11 strings for 6 works; 2 of 6 undeclared** | Blocks any citation rendering or cross-reference until normalized. |
| 6 | **No page/DOI-level citation** | The ceiling on verifiability. Expensive — needs the books. |
| 7 | **`leaf_data_source` absent everywhere** | A validator branch wired to nothing, plus an inaccurate line in `DATA_GAPS.md`. |
| 8 | **`notes` on 20% of edges** | The 51-edge block shows what good looks like. |

---

## 6 · What this audit could not verify

The **contents of the six cited works**. Everything above is a reading of the
citation *strings* and their internal consistency, not a check that Acorn &
Sheldon actually record a given butterfly on a given host. Confirming that means
opening the books, and it is the one thing that cannot be done from the
repository. If any edge's claim is factually wrong, nothing in this audit or in
the enforcement it proposes would catch it — the goal is to make each claim
*checkable by someone holding the book*, not to certify it.

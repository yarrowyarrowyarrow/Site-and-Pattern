# 8 · Local to Edmonton, built as a template for Calgary and Regina

*Part of the [homeowner-path plan](README.md). Work items **ED-1 to ED-16**;
defects found here **EDF-1 to EDF-7**; owner decisions **E1 to E9**
([12-decisions.md](12-decisions.md)). The Advanced switch this part leans on is
MD-1 ([02-two-ways-to-use-it.md](02-two-ways-to-use-it.md)); the overview's
regional sentences are OV-13 ([06-yard-overview.md](06-yard-overview.md)).*

> **The owner's answers (13 October 2026):** **no rules block** (E6): ED-14 is
> cancelled and the manifest carries no `rules` field and no 24-month check.
> **"Native" in the score counts the Edmonton list** in the Edmonton region (E5):
> new item ED-17, a deliberate headline change. **No website work for now** (G5):
> ED-12 is deferred. The other E answers took the recommendation.

The owner asked *"what it would mean for this app to be local to just Edmonton
[which could be used as a template to build out the Calgary or Regina apps]"*.

Sources: the code at V3.17, the shipped data, the first-pass review
([`../SALE_READINESS_REVIEW.md`](../SALE_READINESS_REVIEW.md) §7 and R4, R14,
R30, R32), and offline derivations run against the repository's own occurrence
cache. **Nothing here reopens** the decisions in V2.79's *Handing this over*
or the V3.12 rules for the Edmonton list (the VASCAN gate, specimens only,
three collections, the owner's rulings with no reasons).

## In one paragraph

Make the app local to Edmonton with **data, not git branches**: one folder,
`data/regions/edmonton/`, holds everything that is true of one place (the area,
the plant list, the climate normals, the nurseries, the local rules, the worked
example), and one module, `src/region.py`, is the only code that reads it. The
pin picks the region; a pin outside it is told so plainly instead of being given
borrowed numbers. Calgary is then a second folder, a derivation run and a
person's review (about one developer-week plus the reviewer); Regina is not
ready until its herbarium records reach GBIF. The audit found **seven defects**
that this fixes on the way, the worst being an export that prints **two
different nursery lists** in one PDF.

---

## 1. What "local to Edmonton" means

The app is local to Edmonton when **every place-specific answer comes from one
Edmonton region pack, chosen by the pin**, and a pin outside it is told so.

| Dimension | Edmonton edition | Today (V3.17) |
|---|---|---|
| **Area** | 50 km circle around downtown (53.5461, −113.4938): St. Albert 13 km, Sherwood Park 13 km, Beaumont 22 km, Devon 26 km, Fort Saskatchewan 26 km, Spruce Grove 27 km, Morinville 30 km, Leduc 32 km, Stony Plain 34 km, Elk Island 44 km. The same circle the Edmonton list was derived for (the owner's V3.12 choice) | No area. The pin is compared with nothing except the AB/SK outline (`site_fit.province_at`, `src/site_fit.py:62-76`) |
| **Plants** | The 250-species Edmonton list is the default wherever a plant is chosen: picker, Directory, Communities, Generate, the example, the overview's nudges. The other 174 stay in the catalogue, behind Advanced ("All Alberta natives") and on the website | The list exists and is **off by default everywhere** (R30). Generate's "Edmonton natives only" goal applies it by name wherever the pin is (EDF-3) |
| **Communities** | The 27 top-level communities (plus 2 variations) whose every member is on the list | 73 top-level communities shown |
| **Climate** | One station, one period, one set of frost dates, with the source printed: Edmonton City Centre A, 1981–2010 | Three frost dates and two rainfall tables in the code (EDF-4) |
| **Nurseries** | One list, used by Site Info, the order file, the plan and the PDF | Two lists that disagree, both printed in one export (EDF-1) |
| **Map and address** | Opens on Edmonton; search bounded to the circle plus a margin; *"Search an address in the Edmonton region"* | Opens on Edmonton from a literal (`html/map/01-core.js:497`); *"Search an Alberta address"* |
| **Local rules** | A short, sourced, dated list: the long-grass bylaw, noxious weeds, call before you dig, neighbouring towns' naturalized-yard rules | Missing |
| **Out of area** | A plain message; no borrowed climate, soil or nurseries | A Toronto pin gets Regina's rainfall and *"Site data ready."* (R32) |

---

## 2. Audit: every regional assumption in the code

**Method.** Every `.py`, `.js`, `.html`, `.css` and `.sql` file under `src/`,
`html/` and `main.py` was searched for *Edmonton, Alberta, Saskatchewan,
prairie, Calgary, Regina, Saskatoon* (not the berry), *Lethbridge, Red Deer,
Medicine Hat, Manitoba, Winnipeg, Grande Prairie, Fort McMurray*, `AB`, `SK`,
`53.54`, `-113.49` and "zone 3/4". Python files were tokenized so comments and
docstrings could be told apart from strings and names. 1,085 raw hits; 80
plant names ("Prairie Crocus", "Saskatoon Berry") removed. The classification
is heuristic; counts are within a few lines.

| Class | Meaning | Lines | Files |
|---|---|---|---|
| (a) Region data | A value true of one place (a list, a station, a supplier, a dataset) | 268 | 12 |
| (b) Region default | A choice made because the user is assumed to be in Edmonton | 41 | 14 |
| (c) Province logic | An Alberta, or Alberta and Saskatchewan, rule or word | 143 | 34 |
| (d) Website only | The static site, which keeps its AB + SK scope | 66 | 14 |
| (e) Incidental text | Comments, docstrings, history | 465 | 108 |
| — | False positives (three.js, Spark, a variable named `sk`) | 22 | 5 |

Counted another way: **188 string-or-code lines in 26 files name Edmonton**
(comments and docstrings excluded). About 100 of them can keep the name (§4.8);
the other ~88, in ~20 files, move to the pack.

**The distinct assumptions.** "Elsewhere" says what a pin outside Edmonton gets
today.

| # | Where | Class | What it assumes | Elsewhere | Work item |
|---|---|---|---|---|---|
| 1 | `src/local_flora.py:72-80` `PLACES` | a | The only place, written in code | — | ED-2 |
| 2 | `data/local_flora.json`, `data/local_flora_rulings.json` | a | Already keyed `places → edmonton` | — | Move into the pack folder (ED-2) |
| 3 | `src/native_here.py:36` `EDMONTON`, and the defaults that use it | b | Every caller means Edmonton | — | Default = the pin's region (ED-2) |
| 4 | `src/native_here.py` `place_at` | b | Pin → place exists, unused | — | Becomes `region.at` (ED-1) |
| 5 | `src/design_goals.py:64-81`, goal `edmonton_native` | b | Edmonton list, label, community hint "Edmonton", caveat "50 km of downtown" | Regina and Calgary designs restricted to the Edmonton list | Goal built from the region (ED-3) |
| 6 | `src/plant_filters.py` and `src/filter_area.py`, the "Edmonton native" quality | b | — | Offered in Calgary | From the region (ED-3) |
| 7 | `src/polyculture_panel.py`, the "Edmonton natives only" switch, QSettings value `"edmonton"` | b | — | Offered in Calgary | From the region (ED-3) |
| 8 | `src/community_page.py`, `place="edmonton"` | b | — | — | From the region (ED-3) |
| 9 | `src/static_site_species.py`, fallback "Edmonton" | d | — | — | Read `places()` (ED-12) |
| 10 | `html/map/01-core.js:497`, centre and zoom 12 | b | Opens on Edmonton | — | Python sends the pack's view on load (ED-7) |
| 11 | `src/onboarding.py:160-193`, the example's centre and species | a/b | Edmonton species; lands at the user's pin if there is one, so in Toronto too | Edmonton plants in Toronto | Example in the pack; open at the pack centre when the pin is out of area (ED-1, ED-8) |
| 12 | `src/pdf_export.py:313`, "Edmonton, Alberta" | b | Every PDF is in Edmonton | Wrong place printed | From coverage (ED-5) |
| 13 | `src/planting_plan.py:51-63`; `src/pdf_export.py` nursery block | a | Four Calgary-area suppliers, two of them not in the directory | Same list everywhere | One list from the pack (ED-4) |
| 14 | `src/site_panel.py:786-788`, "From the Native Plant Society of Saskatchewan's list" | a | A Saskatchewan source under Edmonton suppliers | — | The pack's note (ED-4) |
| 15 | `data/nurseries_master.json` (13: 8 SK, 5 AB) via `src/db/nurseries.py` | a | Shared directory sorted by distance | Toronto: Saskatchewan suppliers "ship to you"; Calgary: the Edmonton Native Plant Group as its society | The pack names its suppliers (ED-4) |
| 16 | `src/planning_panel.py:44-47, 512` | a | Fixed Edmonton rainfall (427 mm) | Every pin gets Edmonton's rain (R4) | Site's rainfall, else the pack's normals (ED-6) |
| 17 | `src/solar.py:143-160` | a | `EDMONTON_LAT/LNG`; last frost "~May 7", first "~Sep 23" | — | Pack frost dates; keep the test fixture (ED-6) |
| 18 | `src/db/calendar_data.py:1-8` | a | "Edmonton Zone 3b", last frost ~May 20 | Month-level; probably fine across the three cities | Shared calendar; frost text from the pack (ED-6) |
| 19 | `data/rainfall_fallback_prairie.json` (12 stations), `soil_fallback_prairie.json` (11), `wind_fallback_prairie.json` (8), read by `src/property_data.py` and `src/wind_flow.py` | a | Nearest prairie value **at any distance** | Toronto gets Regina | Distance-limited (ED-6, R32) |
| 20 | `data/hardiness_zones.json`, "Edmonton Metropolitan Area" zone 3 | a | Bounding boxes, western Canada | Toronto: zone 5 by latitude band | Shared; a pack may override with a sourced zone (ED-6) |
| 21 | The City of Edmonton 0.5 m contour dataset: `src/terrain.py`, `src/terrain_store.py`, `src/terrain_downloader.py`, `src/controllers/map_events.py`, `src/app.py`, `src/site_panel.py` | a | An Edmonton-only download (an Advanced tool) | HRDEM or 30 m Copernicus | The pack declares it; the button shows only in that pack (ED-7). Identifiers stay: users' `terrain.db` has an `edmonton_tiles` table |
| 22 | `src/db/polycultures.py`, 7 "Edmonton …" communities and 5 "Easy …" ones built from the Edmonton list | a | Shown everywhere | — | Stay as data; the pack names its featured hint (ED-3; decision E9) |
| 23 | `src/reference_ecosystem.py:141`, `_DEFAULT_KEY = "aspen_parkland"` | b | Parkland when the ecoregion is unknown | — | The pack's ecoregion (ED-1) |
| 24 | `src/site_panel.py:476` and the address search in `src/property_data.py` | b/c | "Search an Alberta address"; AB + SK filter and viewbox | — | The pack's bounds and wording (ED-7) |
| 25 | `src/onboarding.py:45`, `FIRST_RUN_GOALS` | b | The local list is not among them | — | From the pack (ED-10) |
| 26 | `src/site_fit.py:47-76`, `province_at` (the 110th meridian) | c | AB/SK only | `""` outside | Keep; the region layer calls it (ED-1) |
| 27 | `src/subject_area.py` | c | AB + SK geometry | — | Keep |
| 28 | `src/native_here.py`, `PROVINCE_NAMES`, `native_in(province="AB")` | c | — | — | Keep; pass the pin's province (ED-9) |
| 29 | `native_to_alberta` read in 12 modules: `habitat_score.py`, `analysis_panel.py`, `on_this_design_panel.py`, `planting_plan.py`, `maintenance_calendar.py`, `pattern_language.py`, `substitution.py`, `planning_panel.py`, `db/polycultures.py`, `app.py`, `plant_directory.py`, `cli.py` | c | Alberta, whatever the pin | Regina: 9 Saskatchewan-only natives scored non-native, 98 non-Saskatchewan natives scored native | `native_in(plant, province)` (ED-9) |
| 30 | The words "Alberta native" and "AB retail estimate" in about 20 places (`analysis_panel.py`, `habitat_score.py`, `design_critic.py`, `on_this_design_panel.py`, `pattern_language.py`, `polyculture_panel.py`, `llm_design.py`, `design_goals.py`, `order_file.py`, `planting_plan.py`, `pdf_export.py`, `app.py`, `controllers/update_flow.py`) | c | — | Wrong in Regina; off-message in Edmonton, where the default is the Edmonton list | Region words (ED-9; [09-words.md](09-words.md)) |
| 31 | `src/climate.py`, zone descriptions that name cities | e | — | — | Leave |
| 32 | `src/site_facets.py`, `src/site_facet_values.py`, `src/static_site_method.py`, `src/static_site_around.py` | d | One hard-coded "Native area" value | — | Values from `places()`; AB + SK unchanged (ED-12) |
| 33 | `src/ecoregion_basemap.py` `CITIES`; `src/static_site_about.py` ("I'm Marci, and I'm in Edmonton"); `src/static_site_points.py` | d | Map labels, the author's note, method text | — | Leave (allowlisted) |
| 34 | `tools/local_flora_review/build.py` and `reads.py` | a | `PLACE = "edmonton"`, Edmonton ecoregion names, Edmonton reads | — | A `--place` argument (ED-2) |
| 35 | `html/*_probe.html` (boundary, legend, measure) | b | Test fixtures at Edmonton | — | Leave (fixtures) |

---

## 3. Defects this audit found

| ID | Severity | What happens | Where | Evidence |
|---|---|---|---|---|
| **EDF-1** | High | **Two nursery lists in one export.** The PDF and planting plan print ALCLA, Bow Valley Habitat Development, Wild About Flowers and Bedrock Seed Bank (Calgary area; the last two are not in the directory). The order file, built from the directory, prints Arnica Wildflowers, the Edmonton Native Plant Group and TreeTime.ca. The plan's section headings name the Calgary set too | `src/planting_plan.py:51-63`; `src/pdf_export.py` nursery block | A full export of one design: the PDF's text, `planting-plan.txt` and `order.csv` |
| **EDF-2** | Medium | Every PDF is subtitled "Edmonton, Alberta", whatever the pin | `src/pdf_export.py:313` | Code |
| **EDF-3** | Medium | "Edmonton natives only" restricts a Regina or Calgary design to the Edmonton list (0 off-list species in both runs) | `src/design_goals.py:64-81`; `src/llm_design.py` | Offline generator runs at Regina and Calgary |
| **EDF-4** | Medium | Edmonton's climate is stated three ways: last frost May 7 (`src/solar.py:158`), ~May 20 (`src/db/calendar_data.py:5`), and an ECCC-normals-based source gives May 15. Rainfall 427 mm (`src/planning_panel.py:44-47`) against the shipped normal's 455.7 mm | As cited | Code; data file |
| **EDF-5** | Low | Site Info credits the Native Plant Society of Saskatchewan's list under Edmonton suppliers; a Calgary pin's "province-wide society" is the Edmonton Native Plant Group | `src/site_panel.py:786-788`; `src/db/nurseries.py` | `native_sources_near` for Calgary |
| **EDF-6** | Medium | Nativity scoring and wording use the Alberta flag in 12 modules, whatever the pin | Row 29 above | grep |
| **EDF-7** | Medium | Offline fallbacks (rain, soil, wind) answer from any distance; a Toronto pin reads *"Site data ready."* (extends R32) | `src/property_data.py`; `src/wind_flow.py` | A Toronto pin, offline |

**R14, found in the first pass, belongs here too.** The worked example contains
**Canada Goldenrod** (not native to Alberta per VASCAN, and marked aggressive)
and **Showy Milkweed** (ruled *not native here* in the owner's Edmonton review).
Proposed replacements, both on the Edmonton list as *documented*: **Stiff
Goldenrod** (*Solidago rigida*, 14 collections, nearest 49 km, a clump-former)
and **Oval-leaf Milkweed** (*Asclepias ovalifolia*, 10 collections, nearest
28 km; the catalogue called it "Green Milkweed", which is *A. viridiflora*,
until V3.18 renamed it on L9's check). The example's notes, which tell the
reader to experiment with the milkweed, are reworded to name it. Every other species in the
example is on the list. This fix does not wait for the pack: it is quick fix
**QF-4** in [11-work-plan.md](11-work-plan.md), and ED-1's pack test then
keeps it fixed.

---

## 4. The region pack

### 4.1 Folder layout

```
data/
  edition.json                     # which pack is the default before a pin exists
  regions/
    edmonton/
      region.json                  # the manifest (§4.2)
      local_flora.json             # derived; moved from data/local_flora.json
      local_flora_rulings.json     # the owner's yes/no rulings; moved from data/
      README.md                    # who reviewed what, when; how to rebuild
```

`data/` already ships whole (`scripts/packaging/permadesign.spec:21`), so a new
folder needs no packaging change. The nursery directory stays one shared file
(`data/nurseries_master.json`, seeded into the database); a pack **names**
which entries are its own, so no supplier is entered twice and a pack change
needs no schema bump.

### 4.2 The manifest (`region.json`, schema 1)

| Field | Type | Required | Edmonton value | Read by |
|---|---|---|---|---|
| `schema` | int | yes | 1 | loader |
| `key` | str, equal to the folder name, `[a-z_]+` | yes | `edmonton` | everything |
| `name` / `short` | str | yes | "Edmonton region" / "Edmonton" | headings, labels ("Edmonton natives only") |
| `province` | `AB` or `SK` | yes | `AB` | the VASCAN gate, `native_in` |
| `area.centre` / `area.radius_km` | [lat, lng] / 10–150 | yes | [53.5461, −113.4938] / 50 | coverage, the local-flora derivation |
| `local_flora.min_collections` | int | yes | 3 | derivation |
| `ecoregion` | ecoregion key | yes | `aspen_parkland` | the reference-community default |
| `map.centre` / `map.zoom` | [lat, lng] / 3–18 | yes | same / 12 | the map on load |
| `address_search.placeholder` | str | yes | "Search an address in the Edmonton region" | Site Info |
| `address_search.margin_km` | number | yes | 20 | geocode viewbox = circle + margin |
| `climate.station`, `period`, `source`, `url` | str | yes | "Edmonton City Centre A", "1981–2010", "Environment and Climate Change Canada, Canadian Climate Normals" | Site Info, the Water page |
| `climate.monthly_precip_mm` | 12 numbers | yes | 22.5, 13.8, 16.1, 26.5, 49.3, 87.1, 91.7, 69.0, 43.4, 21.0, 16.8, 14.5 (455.7 mm, the shipped normal) | Water page, offline Site Info |
| `climate.last_spring_frost` / `first_fall_frost` | `MM-DD` | yes | `05-15` / `09-16` (to verify, §8) | Site Info offline, the plan, the solar presets |
| `climate.hardiness_zone`, `zone_source` | str | yes | "3" from the app's own table, or NRCan's current value once checked | Site Info, PDF |
| `nurseries` | names in `nurseries_master.json` | yes | Arnica Wildflowers, TreeTime.ca, Edmonton Native Plant Group, ALCLA Native Plants, Wild About Flowers | Site Info, order file, plan, PDF |
| `nursery_note` | str | yes | "Native-plant growers and societies for the Edmonton region. Stock is seasonal and often grown to order: check before you go." | Site Info |
| `communities.hint` | str | no | "Edmonton" | the generator's community preference |
| `example` | `{centre, name, planting: [[[names…], [east_m, north_m]], …]}` | yes | from `src/onboarding.py:160-193`, after R14's fix | onboarding |
| ~~`rules[]`~~ | dropped by the owner's answer E6 | — | — | — |
| `overview.price_note` | str | no | "at Edmonton native nurseries" (the street-rule keys are dropped: O5) | the yard overview (OV-13) |
| `defaults.local_natives_only` | bool | yes | true | picker, Directory, Communities, Generate |
| `defaults.first_run_goals` | goal keys | yes | `local_native`, `pollinator`, `well_behaved`, `low_cost` | onboarding |
| `elevation.municipal_contours` | str or null | no | `edmonton_open_data` | the slope tools (Advanced) |

There is deliberately **no field for plant uses, cultural knowledge or
traditional land management** (P12). `rules` holds municipal and provincial
regulation only, and the validation test rejects unknown fields so one cannot
be added in passing.

`data/edition.json`:

```json
{"schema": 1, "default_region": "edmonton", "province_options": "advanced"}
```

`province_options` says where "All Alberta natives" and the province chips
appear: `"advanced"` (only with the Advanced switch on, MD-1) or `"always"`.

### 4.3 The read side: `src/region.py`

One module, Qt-free, and **the only place that opens `data/regions/` and
`data/edition.json`**. Everything else asks it.

```python
@dataclass(frozen=True)
class Region:      # fields as in §4.2; nested blocks as plain dicts
    key: str; name: str; short: str; province: str
    centre: tuple; radius_km: float; ...

@dataclass(frozen=True)
class Coverage:
    kind: str            # "region" | "province" | "outside" | "no_pin"
    region: Region|None  # the pack holding the pin ("region"), else None
    province: str        # "AB" | "SK" | "" (from site_fit.province_at)
    nearest: Region      # the nearest pack, for messages
    distance_km: float|None

def regions() -> dict[str, Region]     # every pack, validated, cached
def default() -> Region                # edition.json's default_region
def at(lat, lng) -> Region | None      # the pack whose circle holds the point
def coverage(lat, lng) -> Coverage
def for_site(site_config) -> Region    # at(pin), else default()
def message(cov: Coverage) -> str      # the wording in §4.5
def set_regions(packs) -> None         # tests: swap in synthetic packs
```

`local_flora.PLACES` becomes `local_flora.places()`, built from `regions()`
(key, name, short, province, centre, radius_km, min_collections).
`native_here.place_at` delegates to `region.at`. Distance uses
`local_flora.distance_km`, as today.

### 4.4 Which callers change

| Caller | Today | After |
|---|---|---|
| `design_goals.GOALS` (a static list) | the `edmonton_native` goal | `local_goal(region)`, built per site: key `local_native`, label `f"{r.short} natives only"`, filter `native_near=r.key`, hint `r.communities["hint"]`. `filters_for_goals` maps the old key `edmonton_native` to it, so saved designs' `priorities` keep working. Not offered when the pin is outside every pack |
| `plant_filters.QUALITIES` | `Quality("edmonton_native", "Edmonton native", …, "edmonton")` | `local_native`, label `f"{r.short} native"`, value from the picker's site (the picker already holds the site) |
| `polyculture_panel.py` | checkbox "Edmonton natives only", QSettings `"edmonton"` | label from the region; QSettings stores `"1"`/`""`, reading an old `"edmonton"` as on |
| `native_here` defaults | `EDMONTON` | `region.default().key` |
| `onboarding.EXAMPLE_*` | constants | `region.for_site(...).example` |
| `pdf_export.py:313` | "Edmonton, Alberta" | `r.name` when in a region; the coordinates ("53.5461, −113.4938") when outside; nothing with no pin |
| `planting_plan.NURSERIES`, `SOURCE_SECTIONS` | hard-coded | deleted; `region_nurseries(lat, lng)` = the directory rows the pack names, nearest first, each with `nurseries.access_label` |
| `planning_panel.py:512` | a fixed table | the site's monthly rainfall (Site Info already fetched it), else the pack's normals, labelled with the station |
| `property_data.fetch_rainfall` step 3, `_prairie_soil_fallback`, `wind_flow._fallback_rose` | any distance | only within 150 km of a fallback point (`_NORMAL_MAX_KM` already exists, `src/property_data.py:52`); otherwise `None`, shown as *"Not available for this location offline"* |
| `html/map/01-core.js:497` | a literal | stays as the cold-load fallback; Python sends `set_view(*r.map["centre"], r.map["zoom"])` on every map load when the design has no pin (the `map_furniture_flow` pattern) |
| `site_panel.py:476` and the address search | "Alberta" | the pack's wording and bounds |

### 4.5 Choosing the active region, and what an out-of-area pin sees

1. **No pin:** `default()`. The map view, the example, the address bias and the
   Generate defaults are Edmonton's.
2. **Pin inside a pack's circle:** that pack. Its defaults switch on (R30); its
   list, nurseries, climate and rules apply. Site Info's first line:
   **"Edmonton region."**
3. **Pin in Alberta or Saskatchewan, outside every pack:** the province's
   natives (VASCAN), no local list, the nearest pack's nurseries shown as
   "ships to you" only where they ship. Site Info, and the first line of the
   Plan My Yard dialog:
   > **"This pin is 281 km from Edmonton, outside the area Site & Pattern is set
   > up for. You can still plan here, but plants are chosen from everything
   > native to Alberta, and the nurseries and planting dates are Edmonton's."**
4. **Pin outside Alberta and Saskatchewan:**
   > **"This pin is outside Alberta and Saskatchewan. Site & Pattern knows the
   > plants, climate and nurseries of the Edmonton region only, so it can't
   > suggest plants for this yard."**

   Climate, soil and wind fall back only within their distance limits; Plan My
   Yard is disabled with the tooltip *"Plan My Yard needs a pin in Alberta or
   Saskatchewan."* (whether to block is decision E3).

The example opens at the pack's `example.centre` when the pin is outside every
pack, rather than planting Edmonton species in Toronto.

### 4.6 The Edmonton rules block (draft wording; every line to be checked against its source before it ships)

| Title | Text | Applies to | Source |
|---|---|---|---|
| Long grass | "Edmonton's Community Standards Bylaw asks that grass and weeds on private property stay under 10 cm. A planted bed is not a lawn, but an untidy one can still draw a complaint. Keep a mown strip along the sidewalk and put up a small sign saying it is a native planting." | City of Edmonton | Community Standards Bylaw 14600; edmonton.ca |
| Noxious weeds | "Alberta's Weed Control Act requires every landowner to destroy prohibited noxious weeds and control noxious weeds. A native bed is not exempt, so learn to recognise the common ones before your first summer." | Alberta | Weed Control Act and Weed Control Regulation |
| Before you dig | "Before you plant a tree or shrub, request a free locate of buried lines through Utility Safety Partners (Alberta One-Call)." | Alberta | utilitysafety.ca |
| Neighbouring towns | "Some towns in the region have their own rules. Spruce Grove allows naturalized yards of plants native to the area. If you live outside Edmonton, check your town's community standards bylaw." | Spruce Grove and others | sprucegrove.org, "Naturalized yards" |

Each entry carries `checked` (an ISO date). They are shown in the Site tab
under **Before you dig** and as a box on the PDF's site-prep page. The pack test
fails when any `checked` date is more than 24 months old, which forces a
re-check rather than a silent drift. **The app must never tell anyone a bed is
legally exempt**; the wording above says what the rule is and what helps, not
what the law allows.

### 4.7 The Edmonton-only build

One codebase and one installer. "Edmonton-only" is a property of the data and
the defaults, not of the build:

- `data/regions/` holds one pack, `edmonton`; `data/edition.json` names it the
  default.
- In the simple app (the default, [02](02-two-ways-to-use-it.md)): the plant
  picker, Directory, Communities and Plan My Yard show only the Edmonton list;
  the province "Native" chip, the "Native only" goal and the "Native to" facets
  are hidden; plant pages still say where VASCAN records the plant as native
  (that is information, not a choice).
- With Advanced tools on: "All Alberta natives" beside "Edmonton natives", the
  province chips, and the City of Edmonton contour download.
- **Remove `data/fetched/` from the installer** (a `datas` filter at
  `scripts/packaging/permadesign.spec:21`): 32 MB the app never reads at
  runtime, including CC BY-NC records it has no business redistributing.

When Calgary is added, the same installer carries both packs and the pin
chooses. A separate Calgary installer would be `edition.json` with
`default_region: "calgary"` in the build workflow, and nothing else.

### 4.8 What stays shared

- **The catalogue, all 424 species.** The 174 not on the Edmonton list break
  down as 116 with no record within 50 km, 49 ruled not native on review, and 9
  not native to Alberta per VASCAN. 26 of the 174 are documented around Calgary
  by the same rule (Foothills Rough Fescue, Missouri Milkvetch, Yellow
  Buckwheat, Prairie Onion, Woolly Cinquefoil and others). Nothing is removed.
- **The website** keeps its Alberta and Saskatchewan scope: `SUBJECT_PROVINCES`
  (`src/site_facet_values.py`), the province facet and every species page are
  unchanged. Its "Native area" facet and hub pages list every pack, read from
  `native_here.places()`, so a Calgary pack adds `/plants/native-area/calgary/`
  with no website code.
- **Province logic** (`site_fit.province_at`, `subject_area`, the VASCAN lists),
  the ecoregion layer, the prairie fallbacks, the hardiness table and the
  month-level planting calendar.
- **Names that stay** (the guard's allowlist): `terrain.py`, `terrain_store.py`,
  `terrain_downloader.py` (the City of Edmonton dataset, and the
  `edmonton_tiles` table in users' `terrain.db`); `db/polycultures.py` (seeded
  community names, pending E9); `ecoregion_basemap.py` `CITIES`,
  `static_site_about.py`, `static_site_points.py` (website text);
  `html/*_probe.html` fixtures; tests.

### 4.9 Guard tests

`tests/test_region_guard.py`:

1. **No module outside the region layer names a pack's place.** Tokenize every
   `src/**/*.py`; for name tokens and string tokens that are not docstrings,
   fail on `\b{short}\b` (case-insensitive) for every pack in
   `region.regions()`, so the guard grows with each pack. Allowlist (path →
   reason) as in §4.8. Today it would fail on 188 lines in 26 files; after
   ED-2 to ED-9, on none.
2. **No pack coordinates in code.** Fail on a numeric literal within 0.01° of
   any pack's `area.centre` or `map.centre` in `src/**/*.py`, and in
   `html/map/*.js` with comments stripped, except `html/map/01-core.js` (the
   cold-load fallback, kept equal to `default().map.centre` by an assertion),
   `ecoregion_basemap.py` and the probe pages.
3. **No literal `native_near` value.** Fail on `native_near` assigned or
   compared to a string literal anywhere in `src/`.

`tests/test_region_packs.py`, per pack:

- the manifest validates (required fields, no unknown fields, `key` equals the
  folder name);
- `site_fit.province_at(*area.centre) == province`;
- `derive_local_flora.py --check` is clean;
- every `nurseries` name exists in the directory;
- every example species resolves and `native_around(name, key)` is true (this
  would have caught R14);
- `monthly_precip_mm` has 12 values; the frost dates parse;
- no ruling carries a `reason`.

---

## 5. How to build the Calgary (or Regina) edition

### 5.1 What the existing tooling already predicts

The occurrence cache is in the repository, so the V3.12 rule can be run for any
centre today. At 50 km:

| City | Documented (native without review) | Thin + observed (needs review) | Unrecorded | Not native in the province | Documented at 80 km / 100 km |
|---|---|---|---|---|---|
| Edmonton (shipped) | 193 | 103 | 116 | 9 | 228 / 234 |
| Calgary | 98 | 231 | 83 | 9 | 179 / 218 |
| Saskatoon | 35 | 216 | 73 | 98 | 43 / 59 |
| Regina | 5 | 185 | 134 | 98 | 16 / 25 |

The floor favours Edmonton because the University of Alberta herbarium (ALTA) is
there: 2,009 of the 2,420 specimen records within 50 km of Edmonton are ALTA's.
Within 50 km of Regina the cache holds 138 specimen records in all. **Calgary is
a data and review job; Regina is not ready** until its herbarium records reach
GBIF (the University of Regina's newsletter says 2026; unverified) and the
catalogue gains the Saskatchewan grassland species it lacks.

### 5.2 The Calgary checklist (after ED-1 to ED-14)

| Step | What | Command or file | Effort | Who |
|---|---|---|---|---|
| 1 | **Draw the circle.** Centre at Calgary City Hall (51.0447, −114.0719, the website's map dot). At 50 km it takes in Chestermere 18 km, Airdrie 28 km, Cochrane 32 km, Okotoks 36 km and Bragg Creek 36 km, so its west edge is foothills: alpine and montane plants (Alpine Aster, Alpine Bistort) come out "documented" and need review too | `data/regions/calgary/region.json` | 1 h | Owner, with the reviewer |
| 2 | **Derive the list.** Expect about 98 documented and 231 to review | `python scripts/derive_local_flora.py --place calgary` (report), then `--write` | 1 h | Developer |
| 3 | Optional: fetch the specimens the 6,000-record cap cut, then re-derive with no network | `python scripts/seed_ecoregion_ranges.py --specimen-pass`, then `--from-cache`, then step 2 | half a day; needs GBIF access | Developer |
| 4 | **Build the review page for Calgary**; write a read for each species to review (labelled as opinion, as `reads.py` is) | `python -m tools.local_flora_review.build --place calgary`; `tools/local_flora_review/reads_calgary.py` | 2–3 days for ~230 reads | Developer or Claude |
| 5 | **Review**: a yes or a no where confident, no reasons, the same rules as V3.12 | the review page | about twice Edmonton's 108-species review | **A person who knows Calgary's native flora** (a native-plant grower or a field naturalists' club member), unless the owner does it |
| 6 | Fold in | `python scripts/derive_local_flora.py --merge <rows dir>` | 1 h | Developer |
| 7 | **Nurseries**: Wild About Flowers (41 km) and ALCLA (58 km) are already in the directory; check whether Bow Valley Habitat Development and Bedrock Seed Bank still trade and add them; list the pack's names | `data/nurseries_master.json` (schema bump), `region.json` | 1 day | Developer; a phone call or two |
| 8 | **Climate**: the Calgary normal is already shipped (418.8 mm); add frost dates and the zone from ECCC and NRCan | `region.json` | 2 h | Developer |
| 9 | **Rules**: Calgary's grass page says 15 cm for grasses and herbaceous plants, not affecting cultivated gardens or xeriscaping (verify); the provincial Weed Control Act and locate-before-you-dig rows are Alberta-wide and can be shared | `region.json` `rules` | half a day | Developer; the owner checks the wording |
| 10 | **Example yard** from the Calgary list | `region.json` `example` | half a day | Developer, checked by the reviewer |
| 11 | **Communities**: see which pass (`filter_library(index, native_near="calgary")`); optionally author Calgary ones as F221 did for Edmonton | `src/db/polycultures.py` (schema bump) | 1–3 days | Developer + reviewer |
| 12 | Tests: the pack test runs automatically; the guard picks up "Calgary" | — | — | — |

Total: **about one developer-week plus the reviewer's time.**

**Regina** adds a catalogue job first: species native to Saskatchewan's
grasslands go through `data/plants_pending_flora.json` and VASCAN
(`fetch_flora_nativity.py`, `ingest_flora_nativity.py --apply`), then a
specimen re-harvest once the University of Regina herbarium publishes, then a
review of 185 or more species. Several weeks, and not before the herbarium
data exists.

---

## 6. Work items

Effort: S = up to a day, M = two to four days, L = a week or more.

| ID | Item | Effort | Depends on |
|---|---|---|---|
| **ED-1** | **The region layer and the Edmonton pack.** `src/region.py` (§4.3, Qt-free, line ceiling 250); `data/regions/edmonton/region.json` filled from §4.2; `data/edition.json`; `reference_ecosystem` default from the pack. **Tests:** `tests/test_region_packs.py` (§4.9); `coverage()` for downtown (`region`), Red Deer (`province`, ~150 km), Toronto (`outside`) and no pin. *Accept:* `python3 -c "from src import region; print(region.coverage(53.52,-113.52).kind)"` prints `region` | M | — |
| **ED-2** | **The local flora read from packs.** Move `data/local_flora*.json` into the pack; `local_flora.places()` from `region.regions()`; `native_here` defaults to `region.default().key`; `derive_local_flora.py` and `tools/local_flora_review/` take `--place`. **Tests:** the existing local-flora tests pass unchanged; `derive_local_flora.py --check` is clean. *Accept:* the Edmonton list is byte-identical after the move | M | ED-1 |
| **ED-3** | **Labels and goals from the region.** `design_goals.local_goal(region)` (old key `edmonton_native` still read); the picker's quality, the communities switch and the community page read the region. **Tests:** a synthetic "testville" pack relabels all three; a saved design with `edmonton_native` opens with the goal on. *Accept:* in a Calgary test pack the switch reads "Calgary natives only" | M | ED-1, ED-2 |
| **ED-4** | **One nursery list** (fixes EDF-1, EDF-5). Delete `planting_plan.NURSERIES` and `SOURCE_SECTIONS`; `region_nurseries(lat, lng)` feeds Site Info, the plan, the PDF and the order file. **Tests:** one export of the example has the same supplier names in all three outputs. *Accept:* no export names Bow Valley or Bedrock unless the pack does | S | ED-1 |
| **ED-5** | **The place line on exports** (EDF-2). From `coverage()`; nothing with no pin. **Tests:** a Regina pin's PDF text does not contain "Edmonton". | S | ED-1 |
| **ED-6** | **Climate from the region; fallbacks limited by distance** (EDF-4, EDF-7, R4). The Water page uses the site's monthly rainfall, else the pack's normals with the station named; one frost date pair everywhere; fallbacks only within 150 km. **Tests:** a Toronto pin offline gets no rainfall and no "Site data ready"; the Water page's growing-season rain equals the pack's May–Sep sum. *Accept:* frost dates in Site Info, the plan and the calendar agree | M | ED-1 |
| **ED-7** | **Map view and address search from the region** (R6's wording too). Python sends the pack's view on map load; the placeholder and viewbox come from the pack; offline search says *"Address search needs an internet connection. You can drop the pin on the map instead."* rather than "No Alberta results". The Edmonton contour download shows only when the pack names it. *Accept:* offline, typing an address gives that sentence | S | ED-1 |
| **ED-8** | **Coverage messages and out-of-area behaviour** (R32). §4.5's messages on Site Info and in Plan My Yard; the example opens at the pack centre for an out-of-area pin. **Tests:** `region.message()` for the four cases matches §4.5's text. *Accept:* a Toronto pin shows the "outside Alberta and Saskatchewan" sentence and no "Site data ready" | M | ED-1, ED-6 |
| **ED-9** | **Nativity by the pin's province** (EDF-6). Replace the 12 `native_to_alberta` reads with `native_here.native_in(plant, province)`; the words come from the region ([09](09-words.md)). **Tests:** a Regina design scores a Saskatchewan-only native as native. Changes a headline score for Saskatchewan designs only (decision E5) | M | ED-1 |
| **ED-10** | **The region's defaults on** (R30). `defaults.local_natives_only` turns on the local list in the picker, Directory, Communities and Plan My Yard in the simple app; `first_run_goals` from the pack. *Accept:* a cold start's plant list has 250 species, not 424 | S | ED-3, MD-1 |
| **ED-11** | **Guard tests** (§4.9). *Accept:* the guards pass, and fail when "Edmonton" is typed into a new module | S | ED-2 to ED-9 |
| **ED-12** | **The website reads every pack.** The "Native area" facet and hub pages from `places()`. *Accept:* a test pack adds a hub page with no website code | S | ED-2 |
| **ED-13** | **The edition file and the installer's contents.** `edition.json`; drop `data/fetched/` from the spec's `datas`. **Tests:** a spec-reading test asserts `fetched` is excluded. *Accept:* the Windows installer shrinks by about 32 MB uncompressed | S | ED-1 |
| **ED-14** | **The Edmonton rules content** (§4.6). Owner reads each source and approves each line (decision E6); shown under Site › Before you dig and on the PDF. *Accept:* each rule carries a URL and a `checked` date | S, plus the owner's reading | ED-1, E6 |
| **ED-17** | **Native counts by the Edmonton list in the score** (owner's answer E5). In the Edmonton region the habitat score's native term (`src/habitat_score.py`, 20 points, `native_species / n_species`) counts plants on the Edmonton list; elsewhere, natives of the pin's province (ED-9). **A deliberate headline change** (the generate-design skill's stability rule): `tests/test_habitat_score.py` is updated on purpose, the increment's plan records how far the worked example and three generated designs move, and the critic's adopt-if-better comparison is re-checked. The nudge text (`habitat_score.py:331`, "aren't Alberta-native") follows the region's words. *Accept:* a design in Edmonton with Canada Goldenrod loses that plant's native credit; the worked example after QF-4 keeps full credit | M | ED-3, ED-9 |
| **ED-15** | **The Calgary pack** (§5.2). | L | ED-1 to ED-14; a reviewer (E8) |
| **ED-16** | **The Regina pack** (§5.1). | L | ED-15; the herbarium data |

**The Edmonton template (ED-1 to ED-14): about three to four developer-weeks.**
ED-15 and ED-16 are **not** part of finishing the app ([10-finishing.md](10-finishing.md)
§1); they are what someone else could pick up from a finished template.

---

## 7. Decisions for the owner

- **E1.** Is the Edmonton area the V3.12 50 km circle (recommended), or
  something else (a larger circle, or a list of municipalities)?
- **E2.** A pin in Alberta or Saskatchewan but outside the area: allow
  planning with province natives and a warning (recommended), or refuse?
- **E3.** A pin outside the two provinces: disable Plan My Yard (recommended),
  or allow it with a warning?
- **E4.** One installer with every pack, the pin choosing (recommended), or
  one installer per city?
- **E5.** Should the simple app's score and wording count "native" by the
  Edmonton list rather than by province? This changes the habitat score's
  native term, a headline that is the owner's call. Recommended: **not now**;
  the overview's "Right plants for here" item ([06](06-yard-overview.md))
  already speaks in the Edmonton list's terms without moving the score.
- **E6.** The rules block: include it at all (it changes, and it is a
  liability surface), how often to re-check (recommended: every 24 months,
  enforced by the test), and whether to name neighbouring towns.
- **E7.** Edmonton's frost dates and hardiness zone: which station and which
  map edition to print (§8).
- **E8.** Calgary and Regina reviews: who answers, and do their rulings follow
  the same "yes or no, no reasons" rule (recommended: yes)?
- **E9.** Keep "Edmonton" in the seven community names, or rename them by
  habitat so a Calgary pack can share the ones that pass there? Recommended:
  rename by habitat ("Aspen woodland edge", not "Edmonton woodland edge"),
  since the region switch already says where they are from.

---

## 8. What could not be verified

- **The bylaw wording.** edmonton.ca, calgary.ca and sprucegrove.org could not
  be opened from this environment; the summaries in §4.6 come from search
  results.
- **Edmonton's frost dates and NRCan zone.** Sources disagree (May 15 / Sep 16
  from an almanac citing ECCC 1981–2010; Edmonton listed as 3a, 3b and 4a on
  different sites). Check ECCC's normals and planthardiness.gc.ca.
- Whether **Bow Valley Habitat Development** and **Bedrock Seed Bank** still
  trade.
- Whether the University of Regina herbarium is on GBIF yet, and how much of
  the University of Saskatchewan's collection is.
- Which Saskatchewan species the catalogue lacks (needs VASCAN access).
- **The online path**: address search, live climate and the coverage messages
  were reasoned from code, not run with a network.

# Ecoregion Map Rebuild — Context

This is the brief the rebuild was built from, as written, followed by a record
of where the work diverged from it and why. The brief is kept verbatim because
most of the pipeline's apparent fussiness is a specific defect it names, and a
future session that reads only the code will file half of it as over-engineering.

---

## 1. What we're building

A harmonized ecoregion layer for Alberta and Saskatchewan, rendered as a
publication-quality map, and exported as a spatial file the app can query.

Two prior attempts exist. Both are wrong in the same underlying way, and the
fix is not "try harder at drawing" — it's "stop drawing and load real data."

---

## 2. Why both prior attempts fail

### Attempt A — the basic version

Five or six units, blobby polygons, no basemap, no legend, no scale.

Specific problems:
- Only ~5 classes for two provinces spanning roughly 12 degrees of latitude
- No Canadian Shield, no Cypress Hills, no Peace River Parkland, no Foothills
- Moist Mixed Grassland placed as a southeast block; it is actually a
  west–east arc sitting directly below the parkland across both provinces
- Appears unprojected (flat top and bottom edges). At 49–60°N, plate carrée
  inflates east–west distance badly — areas are not comparable
- AB/BC boundary drawn as a straight line. South of about 54°N it follows the
  continental divide, which is a ragged line, not a meridian
- No rivers, no lakes, no scale bar, no north arrow, no legend, no sources

### Attempt B — the detailed-looking version

Better cartography, same fabricated geometry. It looks more trustworthy, which
makes it more dangerous.

Errors, roughly in order of area affected:

1. **No Canadian Shield.** Northern Saskatchewan (Boreal Shield and Taiga
   Shield — Churchill River Upland, Athabasca Plain, Selwyn Lake Upland) and
   Alberta's northeast corner (Kazan Upland) are shown as undifferentiated
   boreal plain. Precambrian bedrock, thin soils, jack pine and lichen — an
   entirely different system from the mixedwood around Fort McMurray. Largest
   single error on the map.

2. **"Foothills Grasslands" is not a real unit.** Alberta's Foothills Natural
   Region is *forest* (Upper and Lower Foothills — lodgepole pine, white
   spruce, aspen) and is the province's second-largest natural region.
   Foothills Fescue and Foothills Parkland are separate, much smaller
   grassland units confined to the southwest.

3. **Grasslands under-split, and the split that exists is misplaced.** Missing
   Dry Mixedgrass (Brooks–Medicine Hat–Suffield, the driest ground in Canada)
   and Northern Fescue (east-central AB into west-central SK). The orange
   Moist Mixed Grassland should be a narrow arc immediately below the
   parkland; instead it covers Calgary to Lethbridge, which is arid. Regina
   also belongs in Moist Mixed Grassland, not the yellow unit.

4. **Parkland pushed too far north in Saskatchewan.** Prince Albert is in
   Boreal Transition, not Aspen Parkland.

5. **Legend colours appear swapped.** Peace River Parkland renders olive on
   the map but light green in the legend, and the reverse for Aspen Parkland.

6. **Rocky Mountain region incomplete.** No Alpine subregion. The purple band
   also sits slightly east of the actual relief in the hillshade.

7. **Two of Alberta's largest rivers are missing** — the Peace and the
   Athabasca.

### The framework problem, common to both

The legends mix Alberta's Natural Regions/Subregions vocabulary with
Saskatchewan's national ELC ecoregion vocabulary, plus invented terms. That is
not harmonization. Harmonization means picking one framework and publishing an
explicit crosswalk for the other's names.

---

## 3. Target

**Correctness:** every boundary traceable to a published dataset.
**Appearance:** at least the polish of Attempt B — shaded relief basemap,
neighbouring provinces in grey for context, rivers and lakes, city points,
legend with swatches, title, conic projection.
**Output:** a spatial file the app can query, not just a picture.

---

## 4. Data sources

Portal paths change constantly. Find the current download link from each
landing page. **If a source can't be reached, stop and report it — do not
substitute a different dataset or digitise a boundary by hand.**

Classification: the National Ecological Framework for Canada
(ecozones/ecoregions/ecodistricts; Ecological Stratification Working Group
1995, AAFC) as the base, with the Natural Regions and Subregions of Alberta
(Natural Regions Committee 2006) for finer detail inside Alberta. The CEC North
American Environmental Atlas Level I/II/III is an alternative whose advantage is
continuity into Montana and the Dakotas.

Basemap: Natural Earth 1:10m vectors for provinces/states, rivers, lakes and
populated places, and the Natural Earth **shaded relief raster** (`SR_HR` or
`GRAY_HR_SR_OB_DR`). The relief is what gives Attempt B its credibility.

Libraries: `geopandas` (1.x, pyogrio-backed), `rasterio`, `matplotlib`,
`pyproj`, `requests`. If pip fails on Windows, use
`conda install -c conda-forge geopandas`. Don't fight pip.

---

## 5. Pipeline

Six stages. Each writes an intermediate to disk so the run is resumable and
each stage independently inspectable.

**1 — Fetch.** Download sources to `data/`. Cache by filename; skip if present.
On any non-200, exit with the URL and the landing page. No fallbacks.

**2 — Inspect schema.** Print actual column names and the unique values in
each classification field. **Do not assume field names.** Alberta's may arrive
as a File Geodatabase rather than a shapefile — list layers first if so.

**3 — Harmonize.** ELC ecoregion is the base geometry because it is national
and already spans both provinces. Alberta subregions ride along as an
*attribute*, joined spatially, not as competing geometry. Produce a crosswalk
table (Alberta subregion → ELC ecozone/ecoregion) with a confidence column,
derived from the actual spatial overlap rather than from name matching.

**4 — Validate.** See §6. Fails are blocking.

**5 — Render.** Hillshade raster → neighbouring land in grey → ecoregion
polygons → lakes → rivers → cities → labels → legend → furniture.
Projection: Canada Albers Equal Area Conic (`ESRI:102001`).
Palette must vary in **lightness as well as hue**. Cypress Upland gets a hatch
as well as a colour. Include scale bar, north arrow, full source citations with
edition years, and a projection note.

**6 — Export.** GeoPackage (`.gpkg`) as primary. Also export a simplified
GeoJSON in WGS84 for app use; keep the unsimplified version as source of truth.

---

## 6. Validation

Turn every correction into a test. A city is cheap unambiguous ground truth.

### Point probes

Prince Albert → Boreal Transition · Fort McMurray → Mid-Boreal Uplands ·
Stony Rapids → Selwyn Lake Upland · Uranium City → Athabasca Plain ·
La Ronge → Churchill River Upland · Hinton → Western Alberta Upland ·
Grande Prairie → Peace Lowland · Edmonton → Aspen Parkland ·
Saskatoon → Moist Mixed Grassland · Regina → Moist Mixed Grassland ·
Medicine Hat → Mixed Grassland (AB subregion Dry Mixedgrass) ·
Lethbridge → Mixed Grassland · Maple Creek → Cypress Upland · Banff → mountains

Verify these expected values against the real attribute tables in stage 2. If a
probe fails because *my* expected value is wrong rather than the data, say so
and show the evidence — don't silently edit the expectation to make it pass.

### Structural checks

- **No gaps or overlaps.** Union ≈ AB area + SK area within tolerance.
- **No self-intersection.** A point in two ecoregions is a topology defect.
- **Never join Alberta subregions to ELC ecoregions on name.** "Athabasca
  Plain" exists in both frameworks and refers to *different polygons*.
- No polygon may carry the label "Foothills Grasslands".
- Alberta must resolve to at least four distinct grassland subregions.
- Legend swatch colours must be generated from the same dict used for polygon
  fills, so the Attempt B colour swap is structurally impossible.

---

## 7. Repo integration

- Location: `tools/ecoregions/`.
- `tools/ecoregions/data/` and `*.geojson` gitignored before the first run.
- `README.md` recording exact source URLs, download date, and edition.
- **Do not push to GitHub. Do not create tags, branches, or version numbers.
  When work is ready, ask which version name to use and wait for an answer.
  Never auto-increment.**
- Scope boundary for the first run: do not touch the plant database, its
  schema, or the PyQt6 app. Wiring ecoregions into species records is a
  separate task and the layer should be reviewed first.

---

## 8. One caveat about downstream use

If this eventually feeds seed sourcing, ecoregions are the wrong unit.
Ecoregions are drawn on vegetation and physiography; seed transfer zones are
drawn on climate and genecology. Ecoregions are the right unit for *habitat
description* and species range context.

---

## 9. Hard rules

1. Never fabricate, hand-digitise, approximate, or simplify-then-substitute
   any boundary geometry. If an authoritative source can't be reached, **stop
   and report it.**
2. Never assume field names. Inspect and report first.
3. Never join classification frameworks on name. Spatial join only.
4. Validation failures are blocking. Fix the data, don't relax the test.
5. No pushes, no version numbers, no tags without explicit instruction.

---
---

# Findings — where the work diverged from the brief

Added during the rebuild. The brief above is unchanged.

### The typo diagnosis was wrong; the conclusion it supported was right

The brief reads the labels "Moedgrass" and "Grade Palis" off Attempt A and
concludes the polygons must have been drawn from memory, since text from a
shapefile attribute table does not come out misspelled. Those strings are not in
the code. They are a low-resolution screenshot of "Mixedgrass" and "Grande
Prairie" being read at small size.

The conclusion holds anyway, on much better evidence: the modules say so
themselves. `scripts/draw_ecoregions.py` opens by explaining that it replaced
"ten five-vertex rectangles" with outlines hand-traced against the geography,
and `src/ecoregion_map.py` carries a `CAVEAT` constant, printed under every
drawing, that begins "Approximate extents, not surveyed boundaries". The layer
has been honest about being a diagram the entire time. What was missing was the
data to replace it, not the awareness that it needed replacing.

### Attempt A is not a discarded draft; it is what the site serves today

Both screenshots in the brief were treated as prior attempts at a new map.
Attempt A is `src/ecoregion_map.map_svg(reference=True)` — live, on the
published site, and reused at 420px on every species page as a range map. That
made the render upgrade worth doing immediately rather than after the
classification data lands, and it is why the palette and basemap work shipped
ahead of the pipeline.

### Two defects the brief attributes to the drawing are in the data

- The Alberta/British Columbia border was straight because
  `data/provinces_prairie.geojson` held Alberta as a 15-vertex polygon and
  Saskatchewan and Manitoba as five-vertex rectangles. Fixed by replacing that
  file with Natural Earth 1:10m; Alberta is now 187 vertices and the divide is
  ragged because the real one is.
- The missing Peace and Athabasca are not a styling omission. There was no water
  layer at all — no rivers, no lakes, in any of the maps.

Neither is a classification question, so neither had to wait for the blocked
downloads.

### The current shipped polygons are topologically invalid

Not noted in the brief, found while computing region adjacency: the
`moist_mixedgrass` and `mixedgrass_prairie` placeholders self-intersect at
(-108.546, 52.184). Shapely refuses to intersect them without repair. This is
the brief's own "no self-intersection" structural check failing against the
layer in production right now, which is a further argument for the replacement.

### The palette required a rule the brief did not anticipate

The brief asks for a palette varying in lightness as well as hue, and for a
hatch on Cypress Upland as an outlier plateau. Running the six shipped colours
through a colour-vision validator showed the problem is worse and more
structural than that: the old palette failed every check, with the boreal teal
and the foothills olive only ΔE 7.7 apart for a reader with *full* colour
vision.

Re-stepping fixed most of it, but one pair cannot be fixed by colour. Aspen
Parkland is yellow-green and the Moist Mixed Grassland it borders for eight
hundred kilometres is amber; green against orange is the red-green confusion
axis, and under deuteranopia they collapse to ΔE 4.3 regardless of how the
lightness is arranged. Searching the space with the conventional hues held fixed
found no solution; abandoning the convention produced a cyan boreal and a
magenta Rockies, which is not the map anybody asked for.

So the hatch became a general rule rather than a one-off for Cypress Upland:
**every pair of ecoregions that shares a border must reach CVD ΔE 8, or one of
the two must be hatched.** `tests/test_ecoregion.py` computes the adjacency graph
from whatever polygons are shipped and enforces it, so when the ELC regions land
the test names the pairs that need attention. It also fails if a region is
hatched *without* needing it, since a hatch is visual noise that has to be
earned.

Adjacency, rather than all pairs, is the right constraint for a map: Boreal
Mixedwood and Mixedgrass Prairie are never seen edge to edge, so a shared colour
budget spent separating them is wasted. Of the 15 possible pairs, 11 actually
touch.

### The re-centred projection

The brief specifies `ESRI:102001` for the render. Canada Albers puts its central
meridian at 96°W to keep the whole country upright; 14° west of that, the cone
has turned far enough that Alberta and Saskatchewan arrive visibly rotated — the
first render came out tilted about twelve degrees clockwise. Both renders use the
same Albers family re-centred on this window (standard parallels 50°N and 58°N,
central meridian 110.5°W). Still equal-area, so areas still compare. The exported
GeoPackage keeps `ESRI:102001`, because that is the number other tools expect.

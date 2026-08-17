# tools/ecoregions

A harmonized ecoregion layer for Alberta and Saskatchewan: rendered as a
publication-quality map, exported as a spatial file the app can query.

Dev-time only. Nothing here ships to users, and nothing under `src/` imports it.

The brief this was built from is [`CONTEXT.md`](CONTEXT.md). Read it before
changing anything — most of what looks arbitrary here is a specific defect in
one of the two earlier attempts, and the reasoning is recorded there.

---

## Status

| | |
|---|---|
| Basemap (provinces, water, relief) | **Done.** Downloaded, clipped, shipped as `data/basemap_prairie.geojson`. |
| Ecoregion classification | **Blocked on two downloads.** See below. |
| Pipeline stages 1-6 | Written. 1, 2, 5 exercised end to end; 3, 4, 6 need the classification data to run against. |
| App's `data/ecoregions_canada.geojson` | **Untouched.** Still the hand-traced placeholder. Adopting the real layer is a separate reviewed change; `python -m tools.ecoregions.export --adopt` prints what it involves. |

### What is blocking

The two classification datasets are behind hosts the development session's
egress proxy refuses (403 to CONNECT for everything except GitHub and PyPI).
They are ordinary public open-data downloads from any normal connection.

```bash
python -m tools.ecoregions.fetch      # prints exact URLs and target filenames
```

Put the files in `tools/ecoregions/data/raw/` and run it again.

---

## Running it

```bash
pip install geopandas rasterio matplotlib pyproj shapely pyogrio
# On Windows, if pip fights you:
#   conda install -c conda-forge geopandas rasterio matplotlib

python -m tools.ecoregions.run            # all six stages
python -m tools.ecoregions.run --from 3   # resume at harmonize
```

Or one stage at a time:

| Stage | Command | Writes |
|---|---|---|
| 1 Fetch | `python -m tools.ecoregions.fetch` | `data/raw/` |
| 2 Inspect | `python -m tools.ecoregions.inspect_schema` | stdout: the **real** field names |
| 3 Harmonize | `python -m tools.ecoregions.harmonize` | `out/ecoregions.gpkg`, `out/crosswalk.csv` |
| 4 Validate | `python -m tools.ecoregions.validate` | stdout; **non-zero exit blocks** |
| 5 Render | `python -m tools.ecoregions.render` | `out/ecoregions.png`, `.svg` |
| 6 Export | `python -m tools.ecoregions.export` | `out/ecoregions_ab_sk.gpkg`, two GeoJSONs |

Plus one stage that is not part of the six, because it does not depend on the
classification data and fixes things that were wrong today:

```bash
python -m tools.ecoregions.basemap --report   # writes data/basemap_prairie.geojson
```

**Stage 2 is not optional.** Fill the real column names into `FIELDS` in
`harmonize.py` from its output. `harmonize` refuses to run against a column it
was not told about rather than guessing — the brief's guesses (`NSRNAME`,
`ECOREGION_NAME`) and this repo's earlier ones (`NA_L3NAME`, `L3_KEY`) were
never checked against a real file.

### Before the classification data arrives

```bash
python -m tools.ecoregions.render --from-shipped
```

Draws the app's placeholder polygons through the whole cartographic pipeline, so
the projection, relief, water, legend and furniture are all exercised. The
output stamps `[PLACEHOLDER GEOMETRY]` into its own title and caption.

---

## Sources

Recorded in `sources.py`, which is the machine-readable version of this table.
Downloaded 2026-08-17.

| Dataset | Publisher | Edition | Licence | Reachable here |
|---|---|---|---|---|
| Provinces/states 1:10m | Natural Earth | 5.1.2 | Public domain | yes, via the project's GitHub repo |
| River centrelines 1:10m | Natural Earth | 5.1.2 | Public domain | yes |
| Lakes 1:10m (+ North America supplement) | Natural Earth | 5.1.2 | Public domain | yes |
| Shaded relief `SR_HR` | Natural Earth | 2.0 | Public domain | yes (233 MB) |
| Terrestrial Ecoregions of Canada | AAFC / Ecological Stratification Working Group | National Ecological Framework v2.2 (1995 framework) | Open Government Licence - Canada | **no** |
| Terrestrial Ecozones of Canada | AAFC / Ecological Stratification Working Group | v2.2 | Open Government Licence - Canada | **no** |
| Natural Regions and Subregions of Alberta | Alberta Environment and Protected Areas (Natural Regions Committee 2006) | 2005 Final, 1:250 000 | Open Government Licence - Alberta | **no** |

Natural Earth is fetched from `github.com/nvkelso/natural-earth-vector` and
`.../natural-earth-raster`, which are the upstream project's own repositories
rather than a third-party mirror.

`data/` and `out/` are gitignored. The sources are 50-150 MB and a
full-resolution GeoJSON export can exceed 100 MB.

---

## The decisions worth knowing

**ELC is the geometry; Alberta subregions are an attribute.** Harmonising means
picking one vocabulary and publishing a crosswalk for the other. ELC wins
because it is national, so the provincial border stops being a seam in the
legend. `out/crosswalk.csv` carries the mapping with an overlap fraction as its
confidence.

**The join is spatial, never by name.** "Athabasca Plain" exists in both
frameworks and refers to different polygons. A name join would silently corrupt
the northeast, and it would corrupt it into a file that still looked valid.

**Validation failures are blocking, and expectations are not edited to pass.**
Every probe in `probes.py` traces to a named defect in one of the earlier
attempts. When a probe fails, stage 4 reports which polygon the point actually
landed in and stops. The expectation may well be the thing that is wrong; that
is a human's call with the evidence in front of them.

**Nothing is ever substituted for a source that cannot be reached.** Stage 1
stops and reports. A boundary that came from somewhere other than the source
named here is worse than no boundary, because the map does not look any less
confident for being wrong.

**Colours come from the app.** `render.py` imports `src.ecoregion_palette`, so
the printed map and the website cannot drift, and the legend swatches are
generated from the same dict as the polygon fills. The second attempt shipped a
legend with two of its colours swapped, which is only reachable when the fills
and the key are two lists kept in step by hand.

---

## What this changed in the app, and what it did not

Changed, because none of it is a classification question:

- `data/basemap_prairie.geojson` is new: real provincial and state outlines,
  major lakes, major rivers, from Natural Earth. It replaces
  `data/provinces_prairie.geojson`, in which Saskatchewan and Manitoba were
  five-vertex rectangles and the Alberta/British Columbia border was a straight
  line where the real one follows the continental divide. Alberta went from 15
  vertices to 187. There was no water at all before; the Peace and the Athabasca
  were missing.
- `src/ecoregion_map.py` projects with an Albers equal-area conic instead of a
  single cosine factor, and draws the new basemap.
- `src/ecoregion_palette.py` varies in lightness as well as hue, and carries a
  hatch for the one bordering pair that colour cannot separate under
  deuteranopia.

Not changed: `data/ecoregions_canada.geojson`, the plant database, the schema,
and the PyQt6 app. The ecoregion polygons are still the hand-traced placeholder
and every drawing of them still carries `CAVEAT`.

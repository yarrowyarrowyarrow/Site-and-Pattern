# Site & Pattern — Philosophy-Driven Feature Roadmap

A catalogue of what the design philosophy ([`DESIGN_PHILOSOPHY.md`](DESIGN_PHILOSOPHY.md))
makes *possible*, grounded in what the codebase already does — and **ranked by impact** so
the next move can be chosen deliberately. Each entry states **Impact / Effort / Risk**,
the principle(s) it serves, and a concrete **how I'd build it** (the actual functions and
files it would lean on).

**Relationship to the other backlogs.** [`archive/FEATURE_BRAINSTORM.md`](archive/FEATURE_BRAINSTORM.md)
is the engineering backlog (what's shipped, effort-tiered); [`../ROADMAP.md`](../ROADMAP.md)
is the feature ledger. This is the *philosophical* lens over both, and is meant to be
amended alongside them. Feature IDs (F1, F2, …) are stable handles — say "let's do F5".

**Rating legend.**
- **Impact** — overall value (philosophical alignment × user value × conservation outcome):
  **High / Med / Low**.
- **Effort** — **S** (hours–a day), **M** (a few days), **L** (a week+ / multi-step),
  **XL** (a foundational program of work).
- **Risk** — chance of breakage / scope-creep / hard dependencies: **Low / Med / High**.
  Common risk flags: *schema bump* (`_SCHEMA_VERSION` + reseed, see `CLAUDE.md`),
  *guard ceiling* (a file near a `tests/test_architecture_guard.py` line limit — esp.
  `plant_panel.py` and the `html/map/*.js` files), *new UI surface*, *external data*.

---

## The funnel lens — ranking for *ecosystems created*

The ratings above weigh philosophical alignment × user value × conservation outcome. But the
ultimate goal is **more native ecosystems actually in the ground**, and that is gated by an
adoption funnel: a person has to *get started* (activation), *build a design*, *trust it enough
to act* (confidence), and then *actually buy and plant it* (action). Sorting F1–F39 by the funnel
stage each primarily serves is sobering:

| Funnel stage | # of features | Verdict |
|---|---|---|
| DESIGN (build/improve the design) | 18 | overweight |
| LEGIBILITY / EDUCATE (make ecology visible) | 13 | overweight |
| DECIDE / CONFIDENCE (trust it enough to act) | 7 | moderate |
| **ACT / OUTPUT (design → plants in the ground)** | **5** | **critical deficit** |
| **ONBOARD / ACTIVATE (cold start → first design)** | **1** | **severe deficit** |
| MAINTAIN (after planting) | 2 | minor |

The roadmap is a superb toolkit for an *already-engaged* user, and comparatively silent on the
two stages that actually move the conservation needle. Encouragingly, those two stages map onto
the philosophy's own **under-served principles** — P8 (repair/conversion), P9 (uncertainty/
confidence), P11 (the body & the site). Serving them is not a departure from the philosophy; it
strengthens its weakest spots. So the working rule for what comes next:

> **Lead with ACTION and ACTIVATION; keep (but defer) the DEPTH.** Optimize the funnel for the
> novice lawn-to-habitat converter — the long tail of yards where conversions create the most
> ecosystems — without losing the depth features that reward users who go further.

The new entries below (**F40–F45**) fill the ACT/OUTPUT and ONBOARD gaps; the **Defer** tier
parks the high-effort power-user-depth items until activation/action prove out.

---

## Shipped since this roadmap was written

These started life as entries below and have since landed — the State markers in
[`DESIGN_PHILOSOPHY.md`](DESIGN_PHILOSOPHY.md) reflect the lift. The detail entries are kept
(marked **✅ Shipped**) as the historical record of how they were built.

| ID | Feature | Lives in | Advances |
|----|---------|----------|----------|
| F1 | "Why it matters" ecological-role labels in the plant browser | `src/ecological_role.py`, surfaced in `src/plant_list_view.py` | P6, P10 |
| F2 | Year 1 / 5 / 15 / 30 snapshot view | `src/snapshot_timeline.py`, `src/snapshot_window.py` | P4 |
| F3 | Food-web completeness score | `src/habitat_score.py` (`food_web`), `src/design_critic.py` | P3, P6 |
| F4 | Pattern-language framing for communities | `src/pattern_language.py`, `src/polyculture_panel.py` | P1, P7 |
| F6 | Site-walk field notes | `src/field_notes.py`, surfaced in `src/site_panel.py` (Field Notes tab) | P11 |
| F9 | Specialist-host spotlight | `src/habitat_score.py` + `src/db/fauna.py` specificity | P3, P6 |
| F10 | Lawn-equivalent counterfactual | `src/lawn_zones.py` (`lawn_counterfactual`), surfaced in `src/analysis_panel.py` | P6, P8 |
| F16 | Seasonal view toggle | `src/analysis_panel.py`, `src/map_js.py`, `src/scene_contract.py` | P4, P5 |
| F17 | Phased conversion plan (year-by-year) | `src/conversion_plan.py`, surfaced in `src/planning_panel.py` + `src/app.py` + `src/pdf_export.py` | P8, P4 |
| F22 / F35 | Naturalistic drift placement + spread-aware spacing | `src/layout.py`, `src/planting_spacing.py` | P1, P2, P4 |
| F24 | Site photo overlay + markup | `src/site_photo.py` + `src/site_photo_flow.py`, surfaced in `src/site_panel.py` + `html/map/06-overlays.js` | P11, P5 |
| F37 (part) | "Design for a bee" habitat builder + Alberta native-bee data spine | `src/bee_habitat.py`, `data/bee_attributes_master.json` (+ Apidae roster in `data/fauna_master.json`), `src/db/fauna.py`, surfaced in `src/analysis_panel.py` (Bees tab) | P8, P3, P10, P5, P9 |
| F40 | Planting Plan — buy-it / plant-it sheet (quantities, form, spacing, planting window, phased schedule) | `src/planting_plan.py`, surfaced in `src/app.py` + `src/pdf_export.py` | P8, P4, P11, P6, P9 |
| F11 | Value-vs-price framing — the habitat value a design's spend *creates*, read together with its cost | `src/habitat_score.py` (`habitat_nudges`), surfaced in `src/on_this_design_panel.py` (Stats: habitat value → "where to grow next" → cost → "what your spend creates") | P6 |
| F7 | Relationship-first data model — one queryable edges layer over all four edge shapes | `src/db/relationships.py` + the schema-v51 `relationship_edges` view | P3, P10 |
| F5 | Relationship graph overlay — the design drawn as a living network on the map | `src/relationship_graph.py` + `html/map/07-network.js`, surfaced in Analysis → Habitat | P3, P5, P10 |
| F44 | First-run activation pack — welcome, three-step strip, worked example, Generate on the toolbar | `src/onboarding.py` + `src/onboarding_flow.py` + `src/welcome_dialog.py` + `src/first_step_bar.py` | P1, P9 |
| F45 | In-context guidance — first-step line, dead-end copy that names the way through, tooltips | `src/site_panel.py`, `src/plant_panel.py`, `src/analysis_panel.py`, `src/toolbar.py` | P5 |
| F41 | Numbered plant-by-numbers map — a scale plan drawing, keyed to the buy list | `src/planting_map.py`, drawn in `src/pdf_export.py` | P5, P11 |
| F42 | Design-specific maintenance calendar — the work falling year by year | `src/maintenance_calendar.py` | P4, P9 |
| F43 | Site-prep & soil-amendment sheet — decompact, don't enrich | `src/site_prep.py` | P8, P11, P9 |
| — | **The planting document assembled in job order** — prep → buy → dig → phase → maintain, in the text export and the PDF | `src/planting_plan_export.py` | P8, P11 |
| — | **Temporal succession engine** — the growing overstory shades the understory year by year, so sun-lovers over-topped past their tolerance decline and die and the year-N scene shows the *climax community* (survivors), not every plant frozen healthy | `src/succession_engine.py` (Qt-free growth-matrix + point-sampled dynamic shade + cumulative-stress survival evaluator), folded into `src/scene_contract.py` (health/opacity) and `html/scene3d.html` (withered render) | P4, P3, P9 |
| — | **Succession honesty + regeneration pass (V2.24)** — leaf-off-aware mortality (a deciduous crown shades only its leaf-on season, so part-shade plants survive under it), canopy trees *suppressed* not culled, and **gap recruitment** (self-seeding natives recolonise the openings the closing canopy leaves — the design self-heals). Also: woody plants no longer scatter clonal colonies in the scene, and ambient wildlife forages the whole yard instead of clumping in one bed | `src/succession_engine.py` (`recruits`, leaf weighting, tree floor), `src/scene3d.py` (woody spread gate), `src/scene_wildlife.py` (home-range patrol), `src/scene_contract.py` | P4, P1, P8, P9 |
| — | **3D viewer split + winter atmosphere (V2.24)** — the ~4,200-line `scene3d.html` monolith is split into an HTML shell + a bootstrap module + eight ordered `html/scene3d/*.js` classic chunks (shared-global, like the 2D map), unblocking further viewer work; plus **seasonal ground** (winter snow cover + straw/waking shoulder tints) and **falling snow** in winter. Snow, not invented rain (P9). Verified with a headless-Chromium render harness | `html/scene3d.html` + `html/scene3d/*.js`, guards in `tests/test_architecture_guard.py` / `test_bridge_contract.py` / `test_scene3d_assets.py` | P5, P4 |
| — | **Blender-authored 3D assets for flora & fauna (V2.27)** — the 3D viewer's plants and wildlife upgrade from procedural cone-stacks/sphere-critters to **low-poly GLB archetypes generated by a Blender package** (`scripts/blender/assetlib`, driveable headless *or* live over the Blender MCP with a screenshot-iterate loop; both share one build path with deterministic seeds). Assets are keyed by exactly the buckets the viewer already dispatches on — 14 tree kinds × 3 growth tiers, 5 shrub silhouettes, 7 herb forms, 4 layer kinds, 7 critter kinds — never per species (P9): species identity stays per-instance tints + profile params. Geometry-only adoption (imported materials discarded, `COLOR_0` = grayscale AO) keeps every seasonal/withering/presence tint, the year slider's tier switching, and winter bareness working unchanged — a deciduous GLB's bark part is a complete winter silhouette (P4, P5, P2). The **procedural geometry stays as the permanent per-archetype fallback**: no models dir, a bad file, or a bad archetype renders exactly as before. The **15 habitat structures** followed in the same increment — pond/swale/rain-garden/bee-hotel/brush-pile/snag/shed/fence/etc. as real-metre GLBs with kept (sRGB-authored) materials, cloned per placement and footprint-scaled, replacing the plain extruded boxes. Verified end-to-end with the headless-Chromium smoke probe (`html/model_probe.html`): summer lineup + all structures, January bare skeletons w/ foliated spruce + needle-dropping larch, tinted critter clones on the live animation loop | `scripts/blender/assetlib` + `scripts/blender/build_assets.py` + `scripts/blender/README.md` (MCP workflow), `html/assets/models/*.glb` + `manifest.json`, `html/scene3d/09-models.js` + vendored `GLTFLoader`, GLB-first hooks in `04-quality.js`/`07-wildlife.js`, guards in `tests/test_model_assets.py`; docs in `docs/3D_ASSETS.md` | P2, P4, P5, P9 |
| — | **3D realism + click-to-learn (V2.29)** — two problems, one root. (1) Every flora asset was normalised into a 1×1×1 box and then instanced by `(canopy_m, height_m, canopy_m)`, two different factors whenever a species isn't as wide as it is tall — and prairie trees run 1.2 (bur oak) to 4.2 (lodgepole pine). Every sub-feature was stretched by that ratio, so a poplar's foliage clump rendered as a mass ~6 m wide and 13 m tall: the "giant leaves on a pole" look. Archetypes are now **authored at their species' real aspect** (medians over `data/plants_master.json`), normalisation is **uniform** so that authoring survives, and instancing divides by the published `half_width` — median aspect error across the 65 flora units is 4%, down from 170–320% deformation. Builders shape to the target by moving *anchor points* only (`shape_to_aspect`, solving `max(d·k + r) = target` exactly), never by scaling finished geometry; flat-leaf families finish on an exact measured correction instead. Foliage granularity follows the same logic — clump radius is a fraction of the crown, shrinking with size class while the count grows — and **tiers become SIZE classes, not growth stages**, which is what stopped a young spruce drawing as a bare mast. (2) The viewer had **no click handler at all** and its pick arrays stored only names, while the app held 362 sourced plant↔fauna edges, bee nesting habits and tongue lengths, lep flight seasons and overwintering stages, keystone/specialist status, bloom and fruit windows, toxicity and sourcing — none of which reached the place where you can see the plant. `src/scene_dossier.py` assembles all of it per scene and `10-inspect.js` renders it as a card, with **food-web threads** drawn from the selection to every creature that uses it (P3/P10 literal), a season strip marking the current month and a growth strip marking the current year (the sliders become teaching instruments). "Pull this plant and N species lose their only support here" falls out of the same single edge query, relative to the design on screen. Pushed with the scene via `permaSetDossier`, so the one-directional bridge stands and the card works in walk/fly/bee modes. Also **schema v47**: six botanical-morphology columns authored for all 69 woody species (`scripts/seed_woody_morphology.py` is both the tool and the provenance record) driving foliage grain from real leaf length, per-species bark colour, and per-species autumn colour; plus 3× denser herbaceous foliage. (A ground-cover relief layer — thousands of anonymous grass tufts — shipped here and was **removed** after the first user look: at yard scale the tufts read as green specks indistinguishable from the real forbs, so the scene stopped saying clearly what the design actually contains. Texture is the honest place to say "there is lawn here"; geometry is not.) | `scripts/blender/assetlib` (`conventions.CROWN_ASPECT`/`LEAF_CM`, `mesh_ops.shape_to_aspect`/`squash_to_aspect`), `src/scene_dossier.py`, `html/scene3d/10-inspect.js`, `src/db/schema.sql` v47 + `scripts/seed_woody_morphology.py`, guards in `tests/test_model_assets.py` (authored-aspect + manifest↔geometry) and `tests/test_scene_dossier.py` | P5, P3, P10, P9, P4, P2 |
| — | **Species morphology drives the 3D archetypes + photos on the card (V2.29)** — the V2.29 aspect fix made the geometry honest; this makes it *specific*. All **365 non-woody species** get sourced leaf characters (`scripts/seed_non_woody_morphology.py`, schema **v48** adding `growth_form`) joining the 69 woody ones, so 434 of 434 rows now describe their own leaves — and `growth_form` replaces the 65-genus lookup that had been guessing the shape of 64 of the 211 wildflowers, two thirds of them onto one generic bush. Herb and shrub archetypes are no longer one mesh per growth form: each ships one baked unit per **(blade class × grain class)** its species actually use (52 herb + 31 shrub units), because instancing gives one scale per plant and a species' leaf size and outline therefore have to be *baked*. Shrubs are rebuilt as a branching **cane skeleton clothed in real leaves** placed opposite / whorled / spiralling per `leaf_arrangement` — the field mark that separates a dogwood from a saskatoon — replacing ellipsoids on straight stems, and peak shrub cost rose from 244–608 to 1408–1880 triangles against the same budget (leaf counts are now *budgeted*: a compound leaf costs 3–9× a simple blade, so a rose grows fewer, larger leaves, exactly as the plant does). The click-to-learn card is topped by the species' own **open-licensed iNaturalist photograph with its credit**, served through a route that resolves an opaque cache key inside the photo cache and nowhere else — the URL never reaches the browser — and a photo we cannot attribute is not shown at all. Where a species records nothing, the neutral variant and the tuned defaults apply: an honest empty, not an invented leaf (P9) | `scripts/seed_non_woody_morphology.py` + `src/db/schema.sql` v48, `scripts/blender/assetlib` (`conventions.blade_class`/`grain_class`/`FAMILY_FORMS`, `mesh_ops.thin_leaf_nodes`/`add_compound_leaf`, `flora_shrubs._canes`), `html/scene3d/02-plants.js` `variantKeyFor` + `09-models.js`, `src/photo_warm.py` + `src/web_assets.py` `/__image` + `src/image_cache.credit_line`, guards in `tests/test_model_assets.py` (classifier parity + every-species-resolves + per-unit budgets), `tests/test_web_assets.py`, `tests/test_photo_warm.py` | P5, P9, P2 |
| — | **Satellite tree detection (V2.26)** — OSM rarely maps individual trees outside city cores, so treed acreages got an empty shade map from the existing-features import and hand-marking dozens of crowns was the only way in. The **primary method reads the free Meta/WRI global 1 m canopy-height map** (`src/tree_detect_chm.py`) — the same download-once raster model the app uses for DEM/soil — and runs the industry-standard **variable-window local-maxima** on real height data: each tree's position and *measured* height (±≈3 m) come straight from the map, crown size is a stated allometric estimate, and it's location-independent with no per-photo tuning. This replaced a hard-won but fragile RGB-from-basemap heuristic (`src/tree_detect.py`, kept as an offline/no-`rasterio` fallback) that fought a losing battle against the basemap's missing infrared band and Esri's inconsistent captures — the lesson (recorded here rather than buried): RGB pixel colour can't reliably tell dark conifer from dark grass, so the field detects trees from *height*, not colour. Detected trees are then **editable like plants** (V2.26): drag to the real spot, scroll-wheel to resize the crown to the photo, toggle with the Plants layer, and coloured conifer 🌲 vs broadleaf 🌳 on the 2D map (foliage tagged from the photo's colour at each tree) and shaped accordingly in 3D — while staying *existing site inventory* (shade casters, not counted in the design's habitat/planting scores). Results ride the proven OSM-import tail: boundary + neighbour-margin clipping, satellite-alignment correction, dedupe against OSM/hand-marked trees, one undo step. Honesty contract (P9): positions/crown sizes measured from the photo, heights shipped as stated rough estimates, foliage left *unknown* (never invents a deciduous winter break), a failed tile fetch reported as failure — never "found 0" | `src/tree_detect.py` (Qt-free, pure stdlib) + `src/tree_detect_flow.py`, surfaced in `src/site_panel.py` (Features & Shade → existing-features import) | P8, P9 |

Net effect on the principles: **P1 partial → strong** (pattern language is now explicit), and
P3/P4/P5 are visibly stronger. **F40 is the first real ACT/OUTPUT win** — it turns a design into
a nursery-ready, plant-it-this-way artifact, advancing the under-served P8 (repair/conversion as a
*plan*) and P11 (a printable field plan that drives the user outside). The latest batch deepens the
*legibility* and *repair* spine: **F1** puts each plant's ecological role (keystone / hosts N
caterpillars / specialist / bird food) where the user already looks (P6, P10); **F10** makes the
Tallamy contrast explicit — this design vs. the ≈0 an equivalent lawn provides (P6, P8); and
**F17** turns the drawn conversion zones into a year-by-year remove-this / plant-that schedule
(P8, P4). The next batch finally invests in the long-neglected **P11 (the body & the site)**:
**F6** captures what the *site* knows as a walked checklist of field observations saved with the
project, and **F24** drops a real yard/drone photo onto the map as a georeferenced underlay you
can mark up — together moving P11 from "fetches site data" toward "captures the user's own
ground-truth". **F7 and F5 (V2.31) close the distinctive depth frontier**: the four unrelated
edge tables became one queryable layer, and the design is finally drawn as the network it always
was — taking **P3 and P10 from *partial* to *strong***, the last two headline principles that
were still hedging.

---

## Ranked summary

### High impact
| ID | Feature | Effort | Risk | Principle |
|----|---------|--------|------|-----------|
| ✅ F1 | "Why it matters" labels in the plant browser | M | Low | P6, P10 |
| ✅ F2 | Year 1 / 5 / 15 / 30 snapshot view | M | Low | P4 |
| ✅ F3 | Food-web completeness score | M | Low | P3, P6 |
| ✅ F4 | Pattern-language framing for communities | M (full L) | Med | P1, P7 |
| ✅ F5 | Relationship graph overlay (the distinctive frontier) | L | Med | P3, P5 |
| ✅ F6 | Site-walk field notes | L (slice M) | Med | P11 |
| ✅ F7 | Relationship-first data model (unified edges layer) | XL (built M) | High | P3, P10 |

### Medium impact
| ID | Feature | Effort | Risk | Principle |
|----|---------|--------|------|-----------|
| F8 | Uncertainty language pass | S | Low | P9 |
| ✅ F9 | Specialist-host spotlight | S | Low | P3, P6 |
| ✅ F10 | Lawn-equivalent counterfactual | S | Low | P6, P8 |
| ✅ F11 | Value-vs-price framing | S | Low | P6 |
| F12 | Inline "why this matters" provenance/citations | S | Low | P7, P6 |
| F13 | Reference-ecosystem fidelity score | S (was M) | Low | P2, P6 |
| F14 | Establishment-likelihood band | M | Med | P9 |
| F15 | Pollinator-pathway (bloom-in-space) overlay — *merge into F5* | M | Med | P5, P3 |
| ✅ F16 | Seasonal view toggle (spring/summer/fall/winter) | M | Med | P4, P5 |
| ✅ F17 | Phased conversion plan (year-by-year) | M | Low | P8 |
| F18 | Site-condition remediation advisor | M | Med | P8, P4 |
| F19 | "Why here?" composition reasoning toggle | M | Low | P2, P5 |
| F20 | Maintenance-over-time curve | S | Low | P4 |
| F21 | Ecosystem-services readout | M | Med | P6, P9 |
| ✅ F22 | Naturalistic drift placement | M | Med | P2 |
| F23 | Declarative, inspectable placement rules | M | Low | P1 |
| ✅ F24 | Site photo overlay + markup | M | Med | P11 |
| F25 | Mycorrhizal / symbiosis model | M (was L) | Med | P3 |
| F26 | Successional-sequence edges | M (was L) | Med | P3, P4 |
| F27 | Habitat-corridor analysis | L | Med | P3 |

### Lower impact / nice-to-have
| ID | Feature | Effort | Risk | Principle |
|----|---------|--------|------|-----------|
| F28 | Confidence marks on inferred fields | S | Low | P9 |
| F29 | Scenario *ranges* on the timeline | M | Low | P9, P4 |
| F30 | Invisible-relationship legend | S | Low | P5, P7 |
| F31 | Glossary / concept explainers | S | Low | P7, P5 |
| F32 | Field-mode checklist (printable) | S | Low | P11 |
| F33 | Seasonal observation journal | M | Low | P11, P4 |
| F34 | Shearing-layers data audit | S | Low | P4 |
| ✅ F35 | Self-seeding / spread simulation | M | Med | P1, P4 |
| F36 | Emergent community spacing | L | Med | P1, P4 |
| F37 | "What the bee sees" mode | M | Low | P5 |
| F38 | Mycoremediation / degraded-site notes | S | Low | P8 |
| F39 | Sensor integration hooks | L | High | P11 |

---

## High impact — detail

### ✅ F1 · "Why it matters" labels in the plant browser — *Shipped · was Impact High / Effort M / Risk Low (P6, P10)*
**Shipped** as the Qt-free `src/ecological_role.py` (`ecological_role_summary(plant) -> list[str]`),
surfaced as a leading **Role:** line in the expanded detail row of `src/plant_list_view.py`. Every
plant now carries its ecological role where the user already looks, not just in the Habitat tab.
**How (as built):** `ecological_role_summary` reuses the same use-tag membership the Habitat Value
Score keys off (keystone / host / bird-food / pollinator / nitrogen-fixer, from the synthesised
`permaculture_uses` blob) plus `fauna.fauna_for_plant(plant_id)` (its `relationship` + `specificity`
columns) to emit short badges — "Keystone", "Hosts 7 caterpillars", "Specialist host", "Bird food",
"Pollinator plant" — highest-value first. The delegate caches the line per `plant_id` (paint runs on
every scroll) and renders it text-only as the first detail row, avoiding the `plant_panel.py` guard
ceiling (the logic and tests live outside the widget). The collapsed-row badge remains the next slice.

### ✅ F2 · Year 1 / 5 / 15 / 30 snapshot view — *Shipped · was Impact High / Effort M / Risk Low (P4)*
**Shipped** in `src/snapshot_timeline.py` + `src/snapshot_window.py`. The philosophy's literal
"most important feature": see the trajectory, not the install-day moment. **How:** the engine already renders any year — `scene_contract.build_scene(project,
year=…)` → `scene3d.plant_3d_state(plant, lat, lng, year)` scales size via
`growth_scale_factor` and fades via `succession.presence_factor`. Build a four-up
comparison (2D thumbnails or 3D captures) calling `build_scene` at years {1,5,15,30}
clamped to `succession.timeline_max_years`. Reuse the 3D window's offscreen capture path
(the same one the "yard photo" bake uses). **First slice:** a 2×2 of 2D canopy renders.

### ✅ Forage calendar — whole-design bloom succession + gaps — *Shipped (P6, P9)*
**Shipped** as `src/forage_calendar.py` (Qt-free core) + a QPainter chart behind an
**Analysis → Forage** tab (V2.13). The dedicated tab (and chart widget) was retired in V2.25 —
Planning → Wildlife covers the same month-by-month bloom/gap question, the Habitat tab's
"fill nectar gaps" tips carry the gap-filling suggestions, and the Qt-free core still powers
the docent narration. The Habitat Value Score already rewarded *bloom
continuity* as a hidden sub-score; this makes it **legible**: a 12-month bar of how many plants flower
each month (growing season shaded), the pollinator **gap months** flagged red, and a per-plant
spring→fall **succession** band coloured by flower colour. Honest per P9 — wind-pollinated graminoids
don't count as forage, undated bloomers fall back to a summer relay, and the gaps are named, with
**gap-filling suggestions** (unplaced Alberta natives that flower in a gap, best-fit first). Parses
bloom windows with the same `parse_month_range` the score uses, so calendar and score never disagree.
Refreshes live from the placed plants (no button).

### ✅ F3 · Food-web completeness score — *Shipped · was Impact High / Effort M / Risk Low (P3, P6)*
**Shipped** as the `food_web` line in `src/habitat_score.py`, fed into `src/design_critic.py`.
Score whether the design closes the Tallamy chain (host plants → caterpillars → bird
nestlings), not just whether species are present. **How:** add an 8th, *informational*
line to `habitat_score.compute_habitat_score` that cross-references host-plant counts
(already computed) with `fauna.fauna_supported_by_plants(…, relationship='larval_host')`
and bird-food producers — reporting "supports caterpillars **and** the birds that eat
them" vs. a broken link. Keep it un-summed (like the existing fauna counts) so historical
scores don't drift. Feed a gap line into `design_critic.critique_lines`.

### ✅ F4 · Pattern-language framing for communities — *Shipped (presentation-first) · was Impact High / Effort M / Risk Med (P1, P7)*
**Shipped** in `src/pattern_language.py` + `src/polyculture_panel.py` (the schema-bump "full
version" remains optional). Present plant communities as Alexander patterns (problem → context
→ forces → solution → related) — the app's namesake made literal. **How (presentation-first, no schema bump):**
in `src/polyculture_panel.py`, render each community under the five headings, deriving
*problem/solution* from the existing `description`, *context* from members' `ab_ecoregion`
+ sun/moisture envelope, *forces* from member `functions` and the layer mix, and *related
patterns* from the existing `parent_id` hierarchy. **Full version (schema bump):** add
authored `problem` / `context` / `forces` columns to `polycultures` and seed them.

### ✅ F5 · Relationship graph overlay — *Shipped (V2.31) · was Impact High / Effort L / Risk Med (P3, P5, P10)*
**Shipped** as the Qt-free `src/relationship_graph.py` (`build_relationship_graph` +
`summary_lines`) drawn by a new `html/map/07-network.js`, driven from a **Relationship web**
block on Analysis → Habitat. The app's distinctive frontier: the design drawn as the living
network it is, over the real map, with the layer filter, the legend and the honest read-out of
what the picture leaves out.

**How (as built).** It reads the F7 edges layer, so the overlay never needs to know that
"companion" and "caterpillar host" come from different tables. Three decisions did most of the
work:

- **One node per species, not per placement.** Forty bergamots and one bee would draw forty
  identical lines to the same animal — a hairball hiding the structure it exists to reveal. The
  species node sits at the centroid of its placements, sized by count and by degree; the planting
  underneath stays the map.
- **Animals ring the design.** Fauna have no coordinates, and inventing a spot in the yard for a
  bumble bee would be false precision (P9). Each animal is placed on a ring just outside the
  planting, on the circular-mean bearing of the plants that support it, so its lines converge
  naturally on its own hosts — and the legend says plainly that the ring is a diagram. Crowded
  designs spill onto up to four concentric lanes, dealt round-robin by bearing so neighbours land
  on *different* rings (contiguous blocks just rebuild the pile-up one ring out).
- **Only the animals whose story the overlay exists to tell wear their name.** Sixty named chips
  is a wall of text, not a picture; specialists are labelled, everything else is a taxon mark that
  names itself on hover. Hovering any node fades every edge it does not touch, so one web can be
  read one species at a time.

Honesty (P9): derived plant↔plant links are drawn **dashed** and counted separately, so an
inference never looks like a record; a specialist is never dropped by the readability cap, and
whatever the cap *did* drop is reported (`"5 further wildlife species are supported but not
drawn"`). "Held up by a single plant in this design" falls straight out of the graph, matching
what F46's pull-a-plant simulator says in words.

All geometry — bearings, ring radius, lane assignment, colours, weights — is computed in Python
and shipped precomputed, so the renderer decides nothing about the ecology; `07-network.js` is
~215 lines against a 400 ceiling. It went into its own chunk rather than onto `06-overlays.js`,
which was already the largest of the six. Also exposed headless as
`permadesign_api.relationship_web(project, kinds)`.

**Cheap follow-ons:** a month scrubber over the same overlay (this subsumes most of F15), and
click-through from a node into the plant browser.

### ✅ F6 · Site-walk field notes — *Shipped (first slice) · was Impact High / Effort L (slice M) / Risk Med (P11)*
**Shipped** as the Qt-free `src/field_notes.py` (prompts catalogue + project-properties
read/write/format), surfaced as a **Field Notes** sub-tab in `src/site_panel.py`. Drives the user
outside and captures what the *site* knows. **How (as built):** a `field_notes` block lives on the
project FeatureCollection `properties` (no DB schema bump) holding a prompted walking checklist —
where water pools, where snow drifts, where soil compacts, where wind funnels, frost pockets, what's
already thriving, where people walk, sun morning vs. afternoon, and an embodied "stand here and
notice" — each a checkbox + one-line observation, plus a free-text catch-all. The panel debounces
edits into a `field_notes_changed` signal; `app.py` stores it on the project and marks it modified
(two thin lambdas — MainWindow is at its method ceiling). **Still to come:** pinning individual
observations to map points (reusing the annotation pipeline) and feeding them into generation as
soft constraints (zone/`exclusion` steering) — e.g. a "pools water" note biasing toward riparian
species.

### ✅ F7 · Relationship-first data model (unified edges layer) — *Shipped (V2.31) · was Impact High / Effort XL / Risk High (P3, P10)*
**Shipped** as `src/db/relationships.py` over a `relationship_edges` SQL **view** (schema v51).
The synthesis the philosophy has been pointing at: one queryable edges layer, so the app can ask
"show me everything connected to this plant" in a single call.

**How (as built) — and why it cost M, not XL.** The XL estimate assumed a new table, a seeder, a
reseed entry and a migration of four datasets into it. It is a **view** instead: `plant_fauna`,
`companion_friends`, `companion_enemies` and shared `polyculture_members` stay the single source
of truth and are unioned at read time. No seeder changes, no second copy to drift, nothing new for
the reseed to wipe, and the definition is dropped/recreated on every `init_db` so it can evolve
without a migration. The whole risk profile the "High / XL" rating was about came from the copy.

On top of the view sits the part that matters: a **shared vocabulary**. `EDGE_KINDS` gives every
relationship a label, a reading phrase, a group, a default weight and a colour, so the legend, the
tooltip, the filter row and the graph edge all say the same words — the drift that made four
tables feel like four subsystems was mostly vocabulary drift. `edges_among(plant_ids)` scopes to a
design (plant↔plant edges need *both* ends placed; plant→fauna edges need only their plant),
`edges_for_plant()` gives a species' full catalogue-wide neighbourhood, and `neighbourhood()`
returns it grouped and name-resolved for a panel or the API
(`permadesign_api.plant_relationships`).

Two honesty rules are structural (P9). Every edge carries `evidence`: `documented` means a seeded
record with a citable `source`, `derived` means this module computed it. And `strength` is a
coarse drawing/ranking weight, never a claimed interaction rate — a *specialist* edge outranks a
generalist one on the same kind because the specialist has nowhere else to go, which is a fact
about the record rather than a guess.

The layer also sees something **no individual table holds**: `shared_fauna` — two plants tied
together because they feed the same animal. That is the food web's actual topology, and it only
exists once the edges are in one place. It is derived, so it is labelled derived and drawn dashed.

**Still open, and now cheap:** F25 (mycorrhizal/symbiosis) and F26 (successional sequence) are no
longer "design a subsystem" — they are *seed a table, add a `UNION ALL` arm, register an
`EdgeKind`*. Their effort ratings drop **L → M** on the strength of this landing.

---

## Medium impact — detail

### F8 · Uncertainty language pass — *Impact Med · Effort S · Risk Low (P9)* — quick win
Soften deterministic phrasing toward honest ranges ("tends to establish well here").
**How:** audit the deterministic strings in `design_critic.critique_lines` and
`design_goals.caveats_for_goals` (both pure, no LLM) and reword toward probabilistic
framing; nudge the `llm_design` system prompt the same way. No new computation.

### ✅ F9 · Specialist-host spotlight — *Shipped · was Impact Med / Effort S / Risk Low (P3, P6)*
**Shipped** via `fauna` specificity surfaced in `src/habitat_score.py`. Flag the conservation
wins — designs that feed *specialist* species (monarch↔milkweed), not just generalists. **How:** `fauna.fauna_for_plant` already returns `specificity`;
surface a "supports N specialist species" badge/line in the habitat breakdown and on the
F1 plant labels. Pure read.

### ✅ F10 · Lawn-equivalent counterfactual — *Shipped · was Impact Med / Effort S / Risk Low (P6, P8)*
**Shipped** in `src/lawn_zones.py` (`lawn_counterfactual` + `format_lawn_counterfactual`), surfaced
as a "vs. lawn" callout directly under the score in the Habitat tab (`src/analysis_panel.py`). Makes
the Tallamy contrast explicit: "this design: 62/100 · the same area as lawn: ~0/100." **How (as
built):** a constant ≈0 lawn baseline (`LAWN_HABITAT_SCORE`) is set beside the design's Habitat Value
total; when conversion zones are drawn, the contrast is grounded in the lawn+restoration area from
`lawn_zones.conversion_summary` ("you're reclaiming ~120 m² from lawn"). `app.py` pushes the same
summary it already computes for the "On This Design" tab into the analysis panel, so the callout stays
live with edits. Qt-free and unit-tested.

### ✅ F11 · Value-vs-price framing — *Shipped · was Impact Med / Effort S / Risk Low (P6)*
Pair the cost estimate with the ecological value it buys (the Graeber/Raworth point).
**Shipped (V2.13):** the On This Design → Stats tab now reads top-to-bottom as habitat
value → **"Where to grow next"** (the biggest-headroom habitat-score gaps as ranged,
actionable nudges, `habitat_score.habitat_nudges`) → cost → **"What your spend creates"**
(wildlife species / native species / structures the spend buys), so the cost never stands
alone. Analysis-panel/PDF parity can follow later.

### F12 · Inline "why this matters" provenance — *Impact Med · Effort S · Risk Low (P7, P6)*
Cite the science at the point of use (Tallamy, Xerces, McHarg), not buried. **How:** add
short sourced one-liners next to the habitat components in `src/analysis_panel.py`
(the keystone framing already cites Tallamy — extend the pattern to host/bird/bloom).

### F13 · Reference-ecosystem fidelity score — *Impact Med · Effort S (was M, cheaper since F50) · Risk Low (P2, P6)*
Score how closely the design matches the *natural* community of its place. **How:**
`ecoregion.lookup_ecoregion(lat, lng)` already detects the site ecoregion, and **F50 already
resolves the reference community** — `reference_ecosystem.resolve_reference_community` returns
the characteristic genera and per-layer counts against the live catalogue. Comparing the design's
species and layer ratios against that resolved community is now the whole job. Report as a band,
not a point (P9), and pair it with F50's "walk your design, then walk the reference".

### F14 · Establishment-likelihood band — *Impact Med · Effort M · Risk Med (P9)*
Replace point-precision placement with "tends to establish well / variable / risky here."
**How:** `placement_score.score_cell_for_plant(plant, cell)` already returns a 0–1 site-fit
value; bucket it into a three-band confidence shown per plant in the generated-design
summary and (optionally) as a faint map heat cue. No new model calls.

### F15 · Pollinator-pathway (bloom-in-space) overlay — *Impact Med · Effort M · Risk Med — **merge into F5** (P5, P3)*
Show nectar availability across the *season and the map*, exposing gaps spatially (the
calendar already finds them in time). **How:** `habitat_score.parse_month_range` already
yields per-plant bloom months. **Since F5 shipped, build this as a month scrubber on the
relationship web** rather than a separate layer: `html/map/07-network.js` already has the
legend, the filter row and the plumbing, and gating edges by bloom month there says the same
thing with a fraction of the surface. Standalone it would be a third overlay repeating what
the web and "what the bee sees" already say.

### ✅ F16 · Seasonal view toggle — *Shipped · was Impact Med / Effort M / Risk Med (P4, P5)*
**Shipped** — season selector wired through `src/analysis_panel.py` → `src/map_js.py` →
`src/scene_contract.py`. Switch the scene between spring/summer/fall/winter (deciduous vs.
evergreen reads).
**How:** `build_scene` already takes a `when` datetime (the 3D window has month/hour
sliders driving `_when()`); extend the scene/material logic to vary leaf-on/leaf-off and
bloom colour from `deciduous_evergreen` + `bloom_period`, and expose a season switch.

### ✅ F17 · Phased conversion plan — *Shipped · was Impact Med / Effort M / Risk Low (P8)*
**Shipped** in the Qt-free `src/conversion_plan.py` (`build_conversion_schedule` +
`render_schedule_text`), surfaced in the planning **Timeline** tab (`src/planning_panel.py`), the
Planting Plan text export (`src/app.py`) and a dedicated PDF page (`src/pdf_export.py`). Turns drawn
conversion zones into a year-by-year "remove this / plant that, when" schedule. **How (as built):**
it crosses `lawn_zones.conversion_summary`'s `by_stage` breakdown (how much lawn is being converted)
with `succession.restoration_stage` (the five restoration bands: planting → pioneer forbs →
forb–grass matrix → shrubs establishing → climax/canopy) and the design's plants grouped by
successional role (woody structure / pioneers / matrix / self-spreaders / climax). The lawn-removal
step appears only when zones are drawn; the cadence is given as honest year *ranges*, never false
day-precision (P9). Dependency-injectable and unit-tested.

### F18 · Site-condition remediation advisor — *Impact Med · Effort M · Risk Med (P8, P4)*
From measured soil/disturbance, recommend a *repair sequence* (pioneer cover → soil
builders → target community). **How:** `property_data.fetch_soil` returns `ph_top` +
`texture_class`; combine with plant `soil_ph_min/max` (via `search_plants(soil_ph=…)`) and
`succession.successional_role` to stage a recommendation. Revives parked brainstorm L3
through a restoration lens.

### F19 · "Why here?" composition reasoning toggle — *Impact Med · Effort M → S · Risk Low — **half already built** (P2, P5)*
Explain why the generator placed a plant where it did — turn the black box into a teacher.
**How:** `placement_score` already produces the ecological + aesthetic sub-scores per cell;
surface them on plant click ("north edge: tall-to-the-back + full sun match"). **Scope this
down:** the V2.29 click-to-learn dossier (`src/scene_dossier.py` + `html/scene3d/10-inspect.js`)
already answers "what is this and what does it support" on click — the only piece still missing
is the *placement* rationale, which is a few sub-score lines added to a card that exists.

### F20 · Maintenance-over-time curve — *Impact Med · Effort S · Risk Low (P4)*
Show effort dropping as natives establish (brainstorm R4) across the timeline. **How:**
plot the existing year-1-vs-year-3 effort estimate against `succession` years in the
planning panel.

### F21 · Ecosystem-services readout — *Impact Med · Effort M · Risk Med (P6, P9)*
Carbon, stormwater retention, cooling, pollination — as honest *ranges* beside the habitat
score. **How:** add range-based estimators (keyed off canopy area, leaf area, species mix)
in the spirit of `sourcing.py`'s ranged costing; surface in the Analysis panel with
explicit uncertainty.

### ✅ F22 · Naturalistic drift placement — *Shipped · was Impact Med / Effort M / Risk Med (P2)*
**Shipped** — drift/matrix/scatter generators in `src/layout.py` with layer/spread-aware
spacing in `src/planting_spacing.py` (this also delivered F35). Rainer/West "designed plant
communities": matrix + scatter + drift, not rows.

### F23 · Declarative, inspectable placement rules — *Impact Med · Effort M · Risk Low (P1)*
Surface the implicit generative rules (density/m², native-first, anti-monoculture, layer
balance) as a small, tweakable rule set. **How:** lift the constants now embedded in
`placement_score` / `llm_design` into a named, documented rule object the UI can show and
adjust.

### ✅ F24 · Site photo overlay + markup — *Shipped · was Impact Med / Effort M / Risk Med (P11, P5)*
**Shipped** in the Qt-free `src/site_photo.py` (bbox maths + the `site_photo` GeoJSON feature) plus
`src/site_photo_flow.py` (image load/embed + map glue), surfaced as a "Site photo (map underlay)"
group on the Site → Field Notes tab and a new image layer in `html/map/06-overlays.js`. Drops a
yard/drone photo onto the map as a georeferenced underlay (complementing the Gaussian-splat "yard
photo"). **How (as built):** the chosen image is scaled, embedded as a data URL on a `site_photo`
feature, and placed centred on the property pin (or the current map centre) at a real-world **width
across** in metres, preserving aspect — so placement maths is Python-side and the map JS stays a
thin `L.imageOverlay`, mirroring the splat-ortho plumbing (`draw/set-visible/set-opacity/clear`).
Width + opacity are live; it persists with the project and restores through `render_project_to_map`
(so undo/redo and reload stay in sync). **Markup** reuses the existing map annotation pins — no
separate machinery. (The 06-overlays.js guard ceiling was deliberately bumped 1400 → 1480 for the
new overlay block.)

### F25 · Mycorrhizal / symbiosis model — *Impact Med · Effort M (was L, cheaper since F7) · Risk Med — schema bump (P3)*
Promote the facts now buried in plant `notes` (Frankia, ericoid, AMF, inoculation needs)
to first-class data. **How:** add a `plant_symbiosis` table + seed it, with inoculation
hints surfaced on the plant detail. **Since F7 shipped this is no longer a subsystem:** add a
`UNION ALL` arm to the `relationship_edges` view and register a `symbiosis` `EdgeKind`, and it
appears in the relationship web, `neighbourhood()` and the scripting API for free. The remaining
work is the data, which is the honest bottleneck (P9 — most of these facts are genus-level).
Schema bump + reseed.

### F26 · Successional-sequence edges — *Impact Med · Effort M (was L, cheaper since F7) · Risk Med — schema bump (P3, P4)*
Model "pioneer A prepares the ground for climax B" as a real relationship, driving planting
order and the timeline. **How:** a successional-edge table read by `succession.py` and the
timeline; feeds F2/F17. Same discount as F25 — one `UNION ALL` arm and one `EdgeKind` puts it in
the edges layer, the graph and the API. Note this is the one edge kind that is genuinely
*directed* between two plants, so it exercises the `directed` flag the view already carries.

### F27 · Habitat-corridor analysis — *Impact Med · Effort L · Risk Med (P3)*
Connect the design to adjacent natural features (parked brainstorm L2) — relationship
thinking at landscape scale. **How:** overlay nearby habitat (OSM/landcover) and score
connectivity to the design's planted areas; a new analysis layer.

---

## Lower impact / nice-to-have — detail

- **F28 · Confidence marks on inferred fields** — *S · Low (P9)*: visibly mark inferred vs.
  sourced values using the existing `design_goals.Goal.backed` flag pattern.
- **F29 · Scenario ranges on the timeline** — *M · Low (P9, P4)*: show a growth/maturity
  *band* rather than a single line, from a slow/expected/fast spread of `years_to_maturity`.
- **F30 · Invisible-relationship legend** — *S · Low (P5, P7)* — **merge into F5**: a short primer in the
  analysis panel naming what each overlay teaches the eye to see.
- **F31 · Glossary / concept explainers** — *S · Low (P7, P5)* — **fold into F45**: plain-language definitions
  for keystone, host, succession, mycorrhiza, linked from the UI and docs.
- **F32 · Field-mode checklist (printable)** — *S · Low (P11)*: a site-walk sheet via
  `pdf_export.py` so the user records outside, then enters findings (pairs with F6).
- **F33 · Seasonal observation journal** — *M · Low (P11, P4)*: timestamped notes
  ("first bloom", "snow lingered here") in the project `properties` that accrue site
  knowledge over years.
- **F34 · Shearing-layers data audit** — *S · Low (P4)* — **retire as a feature; belongs in `src/data_quality.py`**: confirm every layer (tree/shrub/
  perennial/annual/soil) carries the rate-of-change fields Brand's framing needs.
- **✅ F35 · Self-seeding / spread simulation** — *Shipped (P1, P4)*: `src/planting_spacing.py`
  reads the `spread_habit` field so self-spreaders are spaced wider and fill gaps over the
  timeline (delivered alongside F22).
- **F36 · Emergent community spacing** — *L · Med — schema (P1, P4)*: generate
  `polyculture_members` offsets from competition/canopy rules instead of fixed offsets.
- **F37 · "See what a bee sees" family** — *P8, P3, P10, P5, P9*: one Alberta native-bee data
  spine (nesting habit, tongue length, flight season, floral-host genera per species — schema
  v39 `bee_attributes`, seeded from the ANBC Apidae tables after Sheffield et al. 2014) feeding
  three lenses that share one *chosen bee → relevant flowers* selection (`src/bee_habitat.py`).
  - **✅ Increment 1 — "Design for a bee" habitat builder (shipped):** pick a genus or species and
    get floral hosts matched from your own plants (with a *Bombus* tongue↔flower-form fit), nesting
    guidance mapped to the real habitat structures (bee hotel, drilled log, brush pile, unmown lawn)
    or "support the host bee" for cuckoos, and a flight-season forage-coverage check that flags
    bloom gaps. Qt-free core + a Bees tab in `src/analysis_panel.py`. Honest about thin data (P9):
    tongue length is graded only for *Bombus*; undocumented flight seasons skip the coverage check.
  - **✅ Increment 2 — "Be a bumblebee" 3D fly-through (shipped):** a "Fly as a bee" toggle + target-bee
    selector in `src/scene3d_window.py` drops into a first-person fly camera in `html/scene3d.html`
    (WASD/arrows + Q/E + drag-look), with a CSS "bee-vision" tint/vignette overlay and glowing beacons
    floating over the chosen bee's floral-host plants (from `bee_habitat.target_plant_ids_for_bee`,
    driven through `map3d_js.set_bee_mode` / `set_bee_targets`). Purely additive to the viewer — when
    off, OrbitControls owns the camera exactly as before. (A true UV/compound-eye post-process pass is
    a later polish; the vendored three.js addons don't ship EffectComposer.)
    *V2.12 polish — the fly-through became a **nectar run**:* brushing a glowing flower collects its
    nectar (sparkle burst + a `Nectar n/N` HUD with a bearing arrow to the nearest unvisited flower,
    per-flower "collected!" callouts naming the plant, and a "this design feeds ⟨bee⟩" celebration when
    the run is complete — the bee's name rides along on `set_bee_targets`); **F** autopilots to the
    nearest unvisited flower for players who don't fly WASD; spawn faces the nearest target; flight is
    velocity-smoothed at 60 fps with banking; the bee avatar was rebuilt lit + properly scaled (its old
    wing discs used to whiteout half the screen). Alongside: a viewer-wide visual pass (ACES filmic
    tone mapping, a gradient sky dome + time-of-day atmosphere so low sun goes golden, a tiled
    procedural meadow ground texture, point-sprite size clamping, shadow-bias tuning) and the
    previously-unregistered `permaResetView` hook now works (Reset view button + sprite gallery).
  - **✅ Increment 3 — "What the bee sees" map recolour (shipped):** a "Show what this bee sees on the
    map" toggle in the Bees tab recolours the 2D Leaflet map as the selected bee's floral-resource map —
    its host plants glow like nectar (graded by tongue-fit for bumble bees via `setBeeForageView`), every
    other plant greys out, with a legend. The original F37 card; Yong's Umwelt made literal.
    (`src/map_js.py` + `html/map/06-overlays.js`, wired panel → map through the Bees tab's
    `bee_map_overlay_*` signals, reusing the same `floral_matches_for_bee` selection.)
  - **✅ Increment 4 — Lepidoptera + a seasonal nectar tour (shipped, V2.12):** the fly-through opened
    to **butterflies & moths** and became **bloom-accurate**. A new schema-v40 `lepidoptera_attributes`
    table (flight season, adult-nectar genera, overwintering stage, activity; seeded from
    `data/lepidoptera_attributes_master.json`, sourced after Acorn & Sheldon 2006 and Pohl et al. 2010,
    the ZooKeys annotated list) feeds `src/lep_habitat.py`, which yields a butterfly/moth's **nectar
    plants** (documented edges + genus fallback — empty for non-feeding giant silk moths, P9) and its
    **larval hosts** (the app's existing rich `larval_host` edges). The pollinator selector in
    `src/scene3d_window.py` now lists bees *and* butterflies/moths; the viewer picks a bee/butterfly/moth
    avatar, floats green "caterpillar nursery" markers over larval hosts, and **only lets nectar be
    collected from flowers actually in bloom that month** (the bloom-gating fix — nectar used to be
    collectable year-round). A **"Tour the year"** toggle drives a hands-free seasonal tour: the flyer
    auto-hops flower to flower while a host-side month timer walks the creature's flight season, so you
    watch the bloom succession come and go (`permaSetBeeTour` + `set_bee_tour`).
  - **✅ Increment 5 — Communities *for a creature* (shipped, V2.12):** the plant-community panel grew a
    **"For a creature…"** button. Pick a native bee, butterfly or moth and `src/creature_community.py`
    (Qt-free) assembles a ready-to-plant community from its nectar/pollen plants and — for
    butterflies/moths — its caterpillar host plants, bucketed by vegetation layer and laid out in
    concentric rings (canopy centre → nectar-rich edge), with an honest overwintering/nesting note.
    A Monarch yields a *Monarch Waystation* (milkweed hosts + late-nectar composites); a non-feeding
    Cecropia moth yields a host-only tree/shrub community.
  - **✅ Increment 7 — 3D readability pass + "Show its plants" (shipped, V2.12):** answering the "the
    bugs clump / you can't tell what is what / the bee's too fast" feedback. Ambient wildlife no longer
    piles onto one keystone plant — `scene_wildlife` spreads each species across the plants it uses and
    runs a spacing-relaxation pass so no two creatures sit within ~0.85 m; each critter gets a
    contact-shadow disc (tracking the fliers) so a low bee reads apart from a flower. Hovering a creature
    now identifies it and the edge — *"Bumble bee · sips nectar at Wild Bergamot"* (raycast wildlife
    first, plant names as the fallback). The flyer's cruise dropped 7→4 m/s with a gentler autopilot, and
    the flower's name is revealed on approach as a constant-screen-size floating label. New **"✨ Show its
    plants"** button (`permaSetPlantSpotlight`): in orbit/walk it raises a glowing, name-labelled light
    column over every plant in the design the selected creature benefits from and sends one of that
    creature touring them — the at-a-glance "which of my plants help this bee?" the 2D "what the bee sees"
    lens does on the map, now in 3D. (Also fixed a latent dispose bug that freed the shared critter-shadow
    geometry on every wildlife rebuild.)
  - **✅ Increment 6 — Ambient wildlife + a third-person walk (shipped, V2.12):** the 3D scene now shows
    **the animals the design's plants actually support**, not just the one you fly. `src/scene_wildlife.py`
    (Qt-free) reads the documented plant↔fauna edges for the scene's plants and places a capped,
    balanced, deterministic community — **bees drawn per genus** (a metallic-green *Agapostemon* sweat
    bee, a fuzzy *Bombus*, a stout leafcutter, a slender mining bee, a wasp-like cuckoo bee),
    butterflies/moths by species colourway, **birds, hover- & dragonflies, lady beetles and small
    mammals** — each standing on/near a plant it uses (a bird in a fruiting shrub, a bee at a nectar
    flower), pushed via `permaSetWildlife` and animated (fliers circle their flower, birds perch and
    look around, mammals hop). A new **"🚶 Walk the garden"** button drops you into a **third-person**
    stroll (a low-poly walker + follow camera, WASD + drag-look) to meet them; wildlife shows in the
    orbit + walk views and hides while flying as one creature. The flown avatar is now **species-styled**
    from the same appearance spec (`appearance_for_fauna`), so *which* bee you are is visible. Alongside,
    ~50 curated documented `nectar` plant↔lepidoptera edges were added (schema v41) so nectaring
    butterflies place from real records. `src/scene3d_window.py` computes wildlife on every scene push;
    the viewer factories + walk mode live in `html/scene3d.html`.
  - **✅ Increment 7 — "Show its plants" + readability/feel pass (shipped, V2.12):** a **"✨ Show its
    plants"** button lights + name-labels every plant in the design the selected creature benefits from
    and sends one of it touring them (`permaSetPlantSpotlight`) — the 3D cousin of the 2D "what the bee
    sees" lens. Alongside: wildlife **de-clumping** (spread each species across the plants it uses +
    a min-separation relaxation so a rich scene reads as individuals), **contact shadows** under critters,
    **hover-identification** ("Bumble bee · sips nectar at Wild Bergamot"), a **slower flyer** (7→4 m/s)
    that **reveals the flower's name on arrival**, and species-styled fly avatars.
  - **✅ Increment 8 — Seasonal + diurnal truth and a night mode (shipped, V2.12):** ambient wildlife is
    gated to when each animal is actually out — documented flight seasons for bees & leps, a coarse
    warm-season default for insects, year-round for birds; and a day/night split so day brings
    bees/butterflies while **night swaps in moths & bats** (owls too). The contract carries an
    `is_night` flag (sun below the horizon; the hour slider now spans a full 24 h), and the viewer
    renders a **moonlit night** — deep sky, a moon + star field, dim cool moonlight, additive-glowing
    blooms (moth-pollination made visible, P5), and an emissive lift so nocturnal critters read against
    the dark. This also thins the daytime clutter (P9: show only what's true). Data in
    `src/scene_wildlife.py` (+ `bee_flight_seasons` / `lep_activity_seasons` in `src/db/fauna.py`),
    render in `html/scene3d.html`.
  - **✅ Increment 9 — Liveliness pass + cinematic flyover (shipped, V2.13):** two tracks. *Liveliness:*
    flower sprites de-blob (per-point size + even areal/vertical spread → distinct blooms, not a disc);
    ambient wildlife now **travels** the plants its species uses (bees cruise-land-sip, butterflies/moths
    flutter, birds hop perch-to-perch, mammals scurry-and-freeze) instead of orbiting one; and a
    **"🔎 Identify"** toggle adds a "who lives here" roster + distance-gated name labels so you read the
    scene without hovering. *Cinematic:* a **"🎬 Flyover"** button plays a ~60 s three-act storyboard —
    grow the design year 0→25, turn the seasons at maturity, fall into a moonlit night — while the viewer
    slow-orbits with letterbox bars + a lower-third caption (`permaSetCinematic` / `set_cinematic_caption`;
    storyboard in `src/scene3d_window.py`). Time is the undervalued design variable made watchable (P4);
    "grown, not designed" made literal (P2).
  - **✅ Increment 10 — Polish + wildlife legible in the score (shipped, V2.13):** *Polish:* **walk-mode
    collision** (trunks + building footprints as bounding circles; you slide around them instead of
    clipping through, and can still stroll under a canopy) and a **two-row toolbar** (scene controls up
    top; a labelled Creature / View row below) so seven mode buttons stop reading as one strip. *Score
    made legible (P6):* the "who lives here" roster now headlines the design's **total ecological reach**
    — "your plants support N wildlife species" with the per-taxon breakdown — computed from the same
    documented edges as the Habitat Value Score (`scene_wildlife.support_by_taxon`, pushed on
    `set_wildlife`), so the number behind the score is visible right beside the animals it represents.
- **F38 · Mycoremediation / degraded-site notes** — *S · Low (P8)*: well-cited restoration
  techniques for contaminated/compacted ground (content, directional).
- **F39 · Sensor integration hooks** — *L · High — external (P11)*: optional soil-moisture/
  temp import (ROADMAP X5) to ground-truth fetched data.

---

## Activation & Action — the adoption frontier (F40–F45)

New entries that fill the ONBOARD and ACT/OUTPUT gaps the funnel lens exposed. These lead the
roadmap now — novices first, depth deferred (not dropped).

| ID | Feature | Stage | Effort | Risk | Principle |
|----|---------|-------|--------|------|-----------|
| ✅ F40 | Planting Plan (buy-it / plant-it sheet) | ACT | M | Low | P8, P4, P11, P6, P9 |
| ✅ F41 | Numbered plant-by-numbers map | ACT | M | Med | P5, P11 |
| ✅ F42 | Design-specific maintenance calendar | ACT / MAINTAIN | S–M | Low | P4, P9 |
| ✅ F43 | Site-prep & soil-amendment sheet | ACT | M | Med | P8, P11 |
| ✅ F44 | First-run activation pack | ONBOARD | M | Low | P1, P9 |
| ✅ F45 | In-context guidance | ONBOARD | S | Low | P5 |

### ✅ F40 · Planting Plan — buy-it / plant-it sheet — *Shipped · was Impact High / Effort M / Risk Low (P8, P4, P11, P6, P9)*
**Shipped** in `src/planting_plan.py`, surfaced in the text export (`app.py`) and the PDF
(`pdf_export.py`). Answers the three questions that otherwise strand a design on the screen:
*what to buy* (species, quantity, nursery form, per-species price range, grouped by Alberta
source), *when to plant* (per-species window from `db/calendar_data.py` + a phased
structure → matrix → fill schedule), and *how far apart* (spacing from `planting_spacing.py`).
Reuses `sourcing`, `planting_spacing`, `succession`, `calendar_data`; Qt-free and unit-tested;
consolidated the 165-line in-`MainWindow` order-list builder into the testable module.

### ✅ F41 · Numbered plant-by-numbers map — *Shipped (V2.31) · was Impact High / Effort M / Risk Med (P5, P11)*
**Shipped** as the Qt-free `src/planting_map.py`, drawn as a PDF page by `pdf_export._draw_planting_map`
and carried in the text export as a key plus per-plant offsets. F40 answered *what to buy*; this
answers **where each one goes**, which is the question standing between a nursery receipt and a
planted bed.

Three decisions went against the card, each deliberately:

- **A drawing, not a screenshot.** The card proposed numbering the captured map image. A satellite
  capture is the worst possible background for a document used outdoors with a tape measure: dark,
  busy, prints badly, and has *no scale*. A clean scale drawing of the boundary with numbered
  positions, a **scale bar** and a **north arrow** is what a planting plan has looked like for a
  century — and it costs no capture plumbing, no coordinate round-trip through the browser, and no
  map-JS, which also retires the card's "watch the map-capture plumbing" risk flag entirely.
- **Numbers are per SPECIES, not per hole.** "Dig holes 7, 8, 9" sounds right and is unusable at
  119 plants — a key of 119 entries is not a key. Every Saskatoon is a **7**, and the key reads
  *7 — Saskatoon Berry ×3 · 3.8 m apart*. A test pins the numbering to the F40 item order, so a
  number on the drawing and a number on the buy list can never disagree.
- **Positions come out in metres.** The core returns a local east/north frame, so the renderer only
  picks a scale — the geometry stays in Python where it can be tested, and the text export can list
  offsets for someone laying the bed out with a tape and no printer.

### ✅ F42 · Design-specific maintenance calendar — *Shipped (V2.31) · was Impact Med / Effort S–M / Risk Low (P4, P9)*
**Shipped** as the Qt-free `src/maintenance_calendar.py`, in the text export and as a PDF page.
Four bands aligned to `succession.restoration_stage` (so the calendar and the 3D year slider tell
the same story about the same years), each with tasks and an hours **range**, plus a month-by-month
first season.

The numbers carry the argument: on the example design the work falls **36–76 → 18–38 → 9–19 → 6–11
hours a year**. That curve *is* P4, and a test asserts it stays monotonic — if the ramp-down ever
flattens, the design's central promise has stopped being true on paper.

Two pieces of content a generic garden calendar gets wrong, and this one gets right because the app
has the data: **year one is about water** (deep weekly watering is what native plantings die
without, and "natives don't need water" is true of an established planting and false of a new one);
and **cut back in spring, not fall** — the October tidy-up removes exactly the overwintering habitat
the rest of the app spends its time modelling, so the note names the species *in your design* with
documented nesting or cover edges. `PLANT_MAINTENANCE_HOURS` moved here from `planning_panel.py`,
which now imports it, so the Effort tab and the calendar cannot quote different hours.

### ✅ F43 · Site-prep & soil-amendment sheet — *Shipped (V2.31) · was Impact Med / Effort M / Risk Med (P8, P11, P9)*
**Shipped** as the Qt-free `src/site_prep.py`, leading the document because it is the work that
happens first. Two things make it more than generic garden advice.

**It tells you not to amend.** The card's own example — "heavy clay → loosen and top with 5–8 cm
compost" — is half right and half the exact mistake: dig-in-compost is imported from vegetable
growing and works *against* a native planting, because a fertility spike favours the weeds that
outcompete young natives, which are adapted to the soil already there. The sheet's spine is
**decompact, don't enrich**, which is the supported restoration position and also the one that
saves the user money. Compost appears only as *surface* mulch, sized as a range from the bed area.

**It says how sure it is.** `fetch_soil` returns a real raster sample where the pack is installed
and a **regional approximation** otherwise, and flags which. Turning a regional guess into "buy 7 m³
of compost" would be inventing precision worth real dollars, so the sheet reads its own `fallback`
flag and, when the figure is regional, says so and points at the two things that settle it — the jar
test you can do this afternoon, and a lab test for about the price of one shrub (P9). It also flags
species whose recorded pH bracket doesn't suit the site, with the same 0.5-unit slack the plant
search uses, and says to **swap the species rather than treat the bed**.

Also included, because the app knows it matters and every mulch guide forgets it: leave a patch of
bare ground for the ~70% of native bees that nest in soil.

### ✅ F44 · First-run activation pack — *Shipped (V2.31) · was Impact High / Effort M / Risk Low (P1, P9)*
**Shipped** as the Qt-free `src/onboarding.py` plus `src/onboarding_flow.py`,
`src/welcome_dialog.py` and `src/first_step_bar.py`. The binding constraint the funnel review
named: everything else this app has built is worth nothing to somebody who never reaches a first
design.

**How (as built), against the five items the card asked for:**

- **A first-run welcome** (QSettings-flagged) offering *Generate a design / Start from my yard /
  Open the example*. Dismissing it counts as an answer — a user who closed it does not want it
  again next launch — and Help → Welcome brings it back, which is also where the example lives
  for anyone who wants it later.
- **The empty-state hint became a strip above the map, not JS inside it.** The map is a
  QWebEngineView; drawing the hint into it would have meant new JS on a chunk already near its
  guard ceiling, for a hint with nothing to do with Leaflet. A slim Qt strip between the toolbars
  and the map costs no JS and cannot be repainted away by a map redraw. It shows the three steps
  with the live one highlighted, and **its chips are controls, not a poster**: clicking one raises
  the Site tab and focuses the address box, or arms the boundary tool, or opens the Plants tab.
  It **retires itself** once you have a pin, a boundary and plants — guidance that outstays its
  welcome becomes furniture — and a View-menu toggle brings it back.
- **"✨ Generate Design" is now a visible button**, right-aligned on the Draw toolbar *and* in the
  strip, in step with the File-menu action while a run is in flight.
- **The example is a spec, not a shipped file.** A `.perma.geojson` would bake in plant ids, and
  ids are not stable across reseeds — a shipped example would silently rot into pointing at the
  wrong species on some future schema bump. The layout is authored as species *names* plus offsets
  in metres and resolved against the live catalogue at open time, the same trick `F50`'s reference
  communities use, so it can never name a plant the app doesn't have and improves as the seed data
  does. It is written to the user's data dir and opened through `MainWindow._load_from_path` — the
  same path File → Open uses, rather than a second near-identical path that would rot. What it
  opens is a real design, not a token: an 88 m² front-yard conversion, 19 plants, three fruiting
  shrubs for structure and a spring→fall nectar relay, scoring **54/100 "Solid habitat"**, with its
  project notes listing what to try on it (score it, pull the milkweed, run the year slider).
  Anything unresolvable is reported in the status bar rather than quietly producing a thinner
  design than the one described (P9). A test asserts every authored name resolves against the
  shipped catalogue, so a seed-data change that breaks the example fails the build instead of a
  user finding it.
- **Generate's defaults are pre-checked for a first-timer** — native, feeds something, stays in its
  bed, buyable at an actual Alberta nursery — but only when the project has no goals of its own,
  so a user who deliberately cleared every goal keeps that choice.

Written as a flow module, so **no new MainWindow methods** (still 125/140) and `app.py` carries
only lambdas. Verified end-to-end on a real Qt stack, not just statically: MainWindow builds, the
example loads through the real path with a consistent ProjectStore, the strip retires itself, and
the step chips actually navigate.

### ✅ F45 · In-context guidance — *Shipped (V2.31) · was Impact Med / Effort S / Risk Low (P5)*
**Shipped** alongside F44. Two of the three items were real gaps; the third was mostly already
done, and saying so is more useful than manufacturing work.

- **A bolded first-step line at the top of the Site panel**, drawn from the same
  `onboarding.first_step_line` the strip uses — one source, so the two surfaces cannot drift into
  giving different instructions about the same state.
- **Dead ends now name the way through.** A failed address search said "Search failed: …" and a
  fruitless one said "No Alberta results." — both true, both a place a beginner gives up. They now
  point at "Use Pin Drop…", which offline is not a workaround but *the* supported path: address
  search is the app's only networked entry point.
- **Tooltips: mostly already there.** An audit found the boundary tool, the five placement modes
  and every plant filter already carried one. What was genuinely missing were the first-contact
  buttons — Find, Refresh data, Clear pin, terrain Generate, Clear mix, Calculate Habitat Value —
  which now say what they do *and* what they don't touch ("Clear pin … your boundary and plants
  are not affected").

---

## Education & mastery — the learning layer (F46–F53)

The app already teaches by *showing* (role badges F1, the score rubric + food-web check F3,
communities as patterns F4, "become a bee/butterfly" embodiment, the lawn counterfactual F10).
What it never lets you do is **test recall**, **break something to understand it**, or **follow a
narrative**. These entries add the missing learning mechanisms — retrieval practice, learning by
breaking, and guided narrative — always on ecological-relationship ground (never Indigenous
plant-use knowledge; Principle 12).

| ID | Feature | Effort | Risk | Principle |
|----|---------|--------|------|-----------|
| ✅ F46 | Pull-a-plant impact simulator | M | Low | P3, P5, P10 |
| ✅ F48 | Field Study quiz layer | M | Low | P5, P7 |
| ✅ F47 | Feed-a-chickadee provisioning scenario | S–M | Low | P3, P6 |
| F49 | Ornamental → native swap card | S–M | Med — new seed data | P6, P8 |
| ✅ F50 | Walkable reference-ecosystem library | L | Med — 3D assets | P2, P6 |
| ✅ F51 | Phenology "what's happening now" dashboard | M | Low | P4, P11 |
| ✅ F52 | Docent / presentation mode | M | Med — capture plumbing | P5 |
| ✅ F53 | Guided lesson track | M | Low | P5, P7 |
| ✅ F54 | Species-shaped fruit in the 3D preview | S–M | Med — schema v49 + seed | P5, P9 |
| ✅ F55 | Groundcover archetype with real leaves | S | Low | P5, P2 |
| ✅ F56 | Oriented (non-billboard) flower heads | M | Low | P5, P2 |
| ✅ F57 | Species characters over genus tables (branching, formBias as fallback) | L | Med — authoring | P2, P9 |
| ✅ F58 | Species leaf silhouettes in tree crowns | M | Low | P2, P5 |
| ✅ F59 | Procedural bark/foliage surface detail | M | Low | P2, P5 |
| ◐ F60 | Blade-class variant axis on tree archetypes (per-SPECIES crown leaves) — poplar/aspen split done, rest open | L | Med — asset size | P2, P9 |
| ✅ F61 | Rebuild the fern, grass and pine archetypes (arc primitive) | M | Low | P2, P5 |
| F62 | Aspect variant axis on layer archetypes (a fescue is not a wild rye) | M | Med — asset size | P2, P9 |

### ✅ F46 · Pull-a-plant impact simulator — *Shipped · was Impact High · Effort M · Risk Low (P3, P5, P10)*
**Shipped** in `src/plant_impact.py` (`pull_plant_impact`), surfaced in the Analysis → Habitat tab
("Pull-a-plant") and exposed headless via `permadesign_api.run_analysis`-adjacent
`pull_plant_impact`. The flagship *learn-by-breaking-it* mechanic: pick a placed species and preview
what removing it costs — recomputes `habitat_score.compute_habitat_score` with and without it for the
score delta, diffs `fauna.fauna_supported_by_plants` per taxon to name the **species that lose all
their support** (the plant's true keystone weight *in this design*), and reports whether the Tallamy
**food-web chain snaps** (`HabitatScore.food_web` complete→broken). Honest about redundancy (P9): if
another copy remains, nothing is lost — and it says so, teaching resilience. Qt-free core + unit
tests; the map right-click gesture is a cheap follow-on (`map_events` plant context menu).

### ✅ F47 · Feed-a-chickadee provisioning scenario — *Shipped · was Impact High · Effort S–M · Risk Low (P3, P6)*
**Shipped** in `src/chickadee_scenario.py` (`chickadee_provision`), surfaced in the Habitat tab and
via the scripting API. Extends the embodiment family from "be a bee" to "provision a bird": tallies
the design's caterpillar-supporting capacity (distinct larval-host lepidoptera the design's plants
support, weighted by each host plant's keystone rank via `fauna.keystone_rank_lepidoptera`) against
the **6,000–9,000 caterpillars one chickadee brood needs** (Tallamy & Shropshire 2009), as an
honest *range* (P9), with a pass/partway/short verdict and the keystone plants doing the work. Makes
the invisible food web emotionally concrete without inventing precision.

### ✅ F48 · Field Study quiz layer — *Shipped · was Impact High · Effort M · Risk Low (P5, P7)*
**Shipped** in `src/field_study.py` (`generate_quiz`), surfaced as a Learn → Field Study tab
(moved from Analysis with the rest of the teaching tools when the top-level Learn tab landed, V2.25).
Procedurally-generated retrieval practice from data already present — no new content: *identify the
plant* (from an image + traits), *which plant feeds this specialist* (from the `plant_fauna`
specialist edges), and *spot the food-web gap* (from the design's own missing links). Deterministic
per seed so a question set is reproducible/testable; doubles as plant-ID training for a nursery or
trail visit (P7 cross-domain: turns the screen tool into field prep). New mechanism the app wholly
lacked — the first time it asks the user a question instead of only answering theirs.

### F49 · Ornamental → native swap card — *Impact Med · Effort S–M · Risk Med — new seed data (P6, P8)*
For a small **curated** ornamental→native swap table (the DB is native-only, so this needs a new
seed file + a schema bump), show the native that does the same aesthetic job *and* feeds the food
web — correcting the exact mistake a beginner makes at the garden centre. **How:** a
`data/native_swaps_master.json` (ornamental name, the aesthetic role it plays, the native
substitute keyed to a real `plants` row, the ecological gain) seeded into a new `native_swaps`
table (bump `_SCHEMA_VERSION`, add to the reseed wipe), a Qt-free `src/native_swaps.py` lookup, and
a search-box card in the plant browser. Data-cost worth discussing before building.

### ✅ F50 · Walkable reference-ecosystem library — *Shipped · was Impact Med · Effort L · Risk Med — 3D assets (P2, P6)*
*(The "Risk: 3D assets" flag is retired — V2.27 shipped a real asset pipeline:
Blender-generated GLB archetypes with the procedural set as permanent fallback;
see `docs/3D_ASSETS.md`.)*
**Shipped** in `src/reference_ecosystem.py` (curated communities + `build_reference_project` /
`build_reference_scene`), surfaced as a **View → Walk a Reference Ecosystem…** window
(`src/reference_ecosystem_window.py`, a `Map3DWidget` in walk mode with an ecoregion selector) and
headless via `permadesign_api.reference_community`. Lets the user *walk* the natural community their
ecoregion is reaching toward — "walk your design, then walk the reference." Rather than a canned
species list with an asset cost, each of the seven Alberta communities is authored as
**characteristic genera per canopy/shrub/forb/grass layer + layer counts** and resolved against the
*live* plant database (`fauna.plants_in_genera`), so it can never name a plant the app doesn't have
and improves as the seed grows; the resolved species are scattered into a `scene_contract` scene at
maturity (year 12) and opened straight into third-person walk mode. The initial community follows
the project's location via `ecoregion.lookup_ecoregion`. Qt-free core + unit tests (community
resolution and the full build-scene pipeline); the companion to the F13 fidelity score.

### ✅ F51 · Phenology "what's happening now" dashboard — *Shipped · was Impact Med · Effort M · Risk Low (P4, P11)*
**Shipped** in `src/phenology.py` (`build_phenology`), surfaced as an Analysis → **This Month** tab
(`src/phenology_widget.py`) and headless via `permadesign_api.phenology`. A month-by-month view of
the design — what's **blooming / fruiting / waking** (breaking dormancy) / **going dormant** / and
which hands-on **tasks** the planting calendar calls for — derived by joining `plants.bloom_period`
+ `fruit_period` (parsed with the score's `parse_month_range`) with the `planting_calendar` ring
(`db.plants.get_calendar`); dormancy transitions come from active→inactive edges in that ring. The
current month becomes a short **"go check outside"** prompt ("we predict X in bloom around now — is
it early, late, on time?"), turning a prediction into a thing to verify on the ground (P11). Qt-free
core + unit tests. Pinning individual observations back into the `field_notes` block stays a cheap
follow-on.

### ✅ F52 · Docent / presentation mode — *Shipped · was Impact Med · Effort M · Risk Med — capture plumbing (P5)*
**Shipped** in `src/docent.py` (`build_docent_script`), surfaced as a Learn → **Present** tab (V2.25; was Analysis → Present)
(`src/docent_widget.py`, an on-screen guided tour with Back/Next) and headless via
`permadesign_api.docent_script`. A narrated walk-through of a finished design to show a neighbour /
HOA / class: a sequence of *beats* — each a camera + season/year state plus a narration line
**generated from the design's own facts** (habitat score vs. the lawn's ≈0, food-web status,
species supported per taxon, seasonal bloom peak from `forage_calendar`, and the chickadee-brood
story from F47) — so the tour is always true to the project in front of you, never boilerplate.
The beats carry the camera/season state a 3D flyover could sync to (reusing the existing flyover
keyframe idea); the shipped surface walks them as an on-screen guided tour, and the same Qt-free
script can feed an offscreen-capture booklet as a cheap follow-on. Unit tests cover the beat
sequence and fact-driven narration.

### ✅ F53 · Guided lesson track — *Shipped · was Impact Med · Effort M · Risk Low (P5, P7)*
**Shipped** in `src/lesson_track.py` (`build_lesson_track`), surfaced as a Learn → **Lessons** tab (V2.25; was Analysis → Learn)
(`src/lesson_track_widget.py`, a Back/Next stepper with a status-dot row) and headless via
`permadesign_api.lesson_track`. A short **course narrated against the user's OWN project** in four
steps — keystone plants → closing the food web → succession over time → ranges-not-certainties —
each pairing a one-paragraph lesson with a live "your design" readout drawn from the surfaces the
app already computes (`fauna.keystone_rank_lepidoptera`, `habitat_score.food_web`,
`succession.successional_role`, and the app's own hedged ranges) plus a good/attention/empty status.
Qt-free core + unit tests. Turns scattered teaching moments into one legible path.

---

## Defer — depth & connoisseurship (after activation/action prove out)

Kept on the roadmap (the depth is the delight), but **parked** behind the adoption work: these
are high-effort and serve already-engaged power users, so they don't move "ecosystems created"
until the funnel above is healthier.

- ~~**F7 · Unified edges layer**~~ — **shipped V2.31** as a view rather than a table, which is
  what took it from XL to M. See the detail entry above.
- **F25 · Mycorrhizal / symbiosis model** — *M · schema (was L, cheaper since F7)*: connoisseur
  depth, not a planting blocker.
- **F26 · Successional-sequence edges** — *M · schema (was L, cheaper since F7)*: `succession.py`
  roles already cover the timeline on today's data.
- **F27 · Habitat-corridor analysis** — *L*: landscape-scale, speculative, needs external data.
- **F36 · Emergent community spacing** — *L · schema*: F22/F35 already give naturalistic spacing.
- **F37 · "What the bee sees" mode** — *M*: delightful, optional.
- **F39 · Sensor integration hooks** — *L · external*: speculative IoT; defer until asked.

---

## V2.31 review — everything still unbuilt, re-ranked for impact

A full pass over the ~25 remaining entries, done alongside F5/F7. Three things changed the
ranking, and one thing didn't change and should have.

**What changed.**

1. **The depth frontier is closed.** F5 and F7 were the last two High-impact entries. Nothing
   left on this roadmap is rated High on philosophical alignment alone — which means impact is
   now decided almost entirely by *funnel stage*, not by principle.
2. **F7 made several deferred items cheap.** F25 and F26 were `L · schema` because each needed a
   subsystem; over the edges layer each is "seed a table, add a `UNION ALL` arm, register an
   `EdgeKind`" — **L → M**. F13 likewise dropped **M → S** once F50 shipped
   `reference_ecosystem.resolve_reference_community` (the reference community it was going to
   have to define is already resolved against the live catalogue).
3. **F8's surface grew about fivefold.** When it was written, "audit the deterministic strings"
   meant two modules. The app now generates prose in `scene_dossier`, `docent`, `lesson_track`,
   `planting_plan`, `conversion_plan`, `habitat_nudges`, `phenology`, `plant_impact`,
   `chickadee_scenario` and the new `relationship_graph`. Still **S**, but the value of one
   afternoon's work went up a lot — and P9 is the principle the app most often *claims* in its
   own copy.

**What didn't change, and should have — now addressed.** The funnel lens above concluded, in
writing, *"lead with ACTION and ACTIVATION; keep but defer the DEPTH."* Since then the shipped work
had been: 3D succession, a 3D viewer split, a Blender asset pipeline, aspect/morphology realism,
click-to-learn, the teaching layer, and the relationship web. Every one of those is DESIGN or
LEGIBILITY. The ONBOARD column held **one** entry (F44), unbuilt: the app opened to a silent blank
map with "Generate Design" behind File → Ctrl+G. That was not a criticism of the depth work — the
depth is what makes this app worth opening — but the roadmap's own stated priority had lost seven
consecutive increments.

> **✅ Acted on in V2.31 — Tier 1 is done.** F44 and F45 shipped immediately after this review (a
> welcome with three doors, a three-step strip whose chips navigate, Generate promoted onto the
> toolbar, a worked 19-plant example scoring 54/100, and dead-end copy that names the way through),
> followed by **F41, F42 and F43** — which turned the Planting Plan from a buy list into the whole
> take-it-outside document: prep the ground → buy it → dig it in the right places → phase it → keep
> it alive. **ONBOARD and ACT/OUTPUT are both clear.** F32 (a printable field-walk sheet) is all
> that remains of ACT, and Tier 2's confidence block is the next coherent increment.

The rest of this review stands as written; the tiers below are unchanged apart from Tier 1 having
landed in full.

Updated funnel counts. Unshipped **F1–F49** only, by the stage each primarily serves — the
retire/merge candidates below are still counted here, and the 3D-asset cards (F60/F62) are not,
since they serve the viewer rather than a funnel stage:

| Funnel stage | Remaining | Which | Verdict |
|---|---|---|---|
| DESIGN | 7 | F18, F23, F25, F26, F27, F36, F38 | still the deepest column |
| LEGIBILITY / EDUCATE | 6 | F15, F19, F21, F29, F30, F31 | well served by what shipped |
| DECIDE / CONFIDENCE | 5 | F8, F12, F13, F14, F28 | all cheap, all unbuilt |
| MAINTAIN | 2 | F20, F33 · ✅ F42 | F42 shipped — the one that saves plantings |
| ~~ACT / OUTPUT~~ | 1 | F32 · ✅ F41, ✅ F43 | **cleared in V2.31** bar the printable field sheet |
| ~~ONBOARD / ACTIVATE~~ | ~~2~~ | ✅ F44, ✅ F45 | **cleared in V2.31** |

(F34 belongs in `data_quality.py` rather than any column, and F49 straddles LEGIBILITY and ACT —
both are discussed below.)

### Tier 1 — build these next, in this order

| # | ID | Why it's first |
|---|----|----|
| ✅ 1 | **F44 · First-run activation pack** *(M · Low)* | **Shipped V2.31.** Everything else on this roadmap is worth exactly zero to someone who never reaches a first design. |
| ✅ 2 | **F45 · In-context guidance** *(S · Low)* | **Shipped V2.31**, alongside F44 — same stage, and the two share their copy. |
| ✅ 3 | **F41 · Numbered plant-by-numbers map** *(M · Med)* | **Shipped V2.31.** F40 shipped "buy 3 Saskatoon" without ever saying *where hole #7 is* — the missing half of a shipped feature. |
| ✅ 4 | **F42 · Design-specific maintenance calendar** *(S–M · Low)* | **Shipped V2.31**, with **F43** alongside it. The commonest way a native planting dies is year-one drought while the user believes natives need no water. |

All of Tier 1 landed in V2.31, in two increments. **Tier 2 — the confidence block — is next.**

### Tier 2 — the confidence block (cheap, and all one theme)

F8, F12, F14, F28 and F13 are five separate cards that are really one job: **say how sure we are,
and say who says so.** Done together they share an audit pass and a visual vocabulary; done
separately they'll each be a lonely half-day.

- **F8 · Uncertainty language pass** *(S · Low)* — now spans ten prose generators; see above.
- **F12 · Inline provenance** *(S · Low)* — got much cheaper: every fauna edge already carries a
  `source`, and F7 surfaces it on every edge. This is now mostly *display*, not research.
- **F28 · Confidence marks on inferred fields** *(S · Low)* — the `evidence` field F7 introduced
  is exactly the distinction this card wanted; reuse the vocabulary rather than inventing one.
- **F14 · Establishment-likelihood band** *(M · Med)* — turns generation from "here is your
  design" into "here is where I'm confident", which is what makes a novice willing to act.
- **F13 · Reference-ecosystem fidelity score** *(S · Low — downgraded from M)* — compare the
  design against `reference_ecosystem.resolve_reference_community` for its ecoregion. The
  companion number to F50's walkable reference.

### Tier 3 — worth doing, but after the funnel

- **F43 · Site-prep & soil-amendment sheet** *(M · Med)* — completes the ACT trio with F40/F41/F42.
- **F20 · Maintenance-over-time curve** *(S · Low)* — fold into F42 rather than shipping alone.
- **F33 · Seasonal observation journal** *(M · Low)* — P11 is still the thinnest principle in
  practice, and the free-text Planning → Notes field is not a journal. Timestamped entries that
  accrue across years, hung off the existing `field_notes` block.
- **F23 · Declarative placement rules** *(M · Low)* — P1's honest gap: the generative rules exist
  but are constants buried in `placement_score` / `llm_design`. Lifting them into a named,
  inspectable rule object is the difference between *claiming* generative design and showing it.
- **F49 · Ornamental → native swap card** *(S–M · Med)* — the garden-centre moment, and the single
  most likely place to change a real purchase. Gated on curated seed data; a **25-row starter
  list** of the ornamentals actually sold in Alberta big-box garden centres is enough to prove it,
  and is a much smaller commitment than the card implies.

### Tier 4 — merge or retire (these are no longer distinct features)

Carrying dead cards costs review attention every time someone reads this file.

- **F15 · Pollinator-pathway overlay** → **merge into F5.** A month scrubber on the relationship
  web gives bloom-in-space with a legend and a filter row already built. Standalone, it would be a
  third overlay saying something the web and "what the bee sees" already say.
- **F30 · Invisible-relationship legend** → **merge into F5.** The overlay ships a legend; F30 is
  now a copy task inside it.
- **F19 · "Why here?" reasoning** → **scope down.** The V2.29 click-to-learn dossier answers "what
  is this and what does it support"; what's genuinely missing is only the *placement* rationale
  from `placement_score`'s sub-scores. Half the card is already built.
- **F34 · Shearing-layers data audit** → **retire as a feature.** It is a data-quality check;
  it belongs as an assertion in `src/data_quality.py`, not an entry here.
- **F31 · Glossary** → **fold into F45.** In-context definitions beat a separate glossary page,
  and the terms are already defined in `lesson_track` and `ecological_role`.
- **F39 · Sensor integration hooks** → **drop until a user asks.** Speculative IoT, external
  dependency, no evidence of demand. It has been on this list unchanged for a long time.

### Still deferred (unchanged, and correctly so)

**F25**, **F26** (now M, but connoisseur depth), **F27** (landscape-scale, external data),
**F36** (F22/F35 already give naturalistic spacing), **F21** (ranged ecosystem-services numbers
invite exactly the false precision P9 forbids — only worth building if the ranges stay wide and
loud), **F62** and the open half of **F60** (3D asset-size work, and the aspect fix already took
the deformation out).

---

## How to choose

Sequenced for **more ecosystems created** — the short version of the V2.31 review above:
- ✅ **Done — get people to a first design (ACTIVATION):** ✅ F44 → ✅ F45 (V2.31). The binding
  constraint, and the priority this roadmap had stated and skipped for seven increments.
- ✅ **Done — close the loop to the ground (ACTION):** ✅ F40 → ✅ F17 → ✅ F41 (the missing half of
  F40) → ✅ F42 (the calendar that keeps year-one plants alive) → ✅ F43. Only **F32** (a printable
  field-walk sheet) is left in this stage.
- **Now — build the trust to act (CONFIDENCE):** the Tier 2 block below.
  F8 / F12 / F28 / F14 / F13 as **one** block, not five cards.
- **Depth is now optional, not owed.** ✅ F1–F7/F9/F10/F16/F17/F22/F24/F35/F40–F45
  have shipped; P1–P11 all read *strong* or better than they did. Remaining depth (F23, F33, F49) is
  worth building when the funnel is healthy, not before.
- **Defer:** F21, F25, F26, F27, F36, F39. **Merge/retire:** F15 and F30 into F5, F31 into F45,
  F19 scoped down, F34 into `data_quality.py`.

---

## Method notes (keep these honest)

- **McHarg overlays (P5/P11):** the site-analysis tabs *are* McHarg's overlay method
  digitized; new layers should compose, not replace.
- **Alexander patterns (P1/P7):** prefer generative rules and reusable patterns over
  one-off layouts.
- **Tallamy "why" (P6/P8):** every recommendation should answer "why does this matter?"
  with data.
- **Uncertainty (P9):** ship ranges and confidence, never false precision.
- **Discipline:** respect the architecture guard — keep map-JS thin and domain logic
  Qt-free/Python-side; mind `plant_panel.py`'s line ceiling for any browser change.
- **Indigenous knowledge (P12):** anything touching Indigenous land knowledge is gated by
  **core principle #12** in [`DESIGN_PHILOSOPHY.md`](DESIGN_PHILOSOPHY.md) (*Indigenous
  knowledge is honoured through relationship, not extraction*) — directional only until
  consultation and free, prior, and informed consent. This is a hard guardrail, not a backlog
  item: there is no feature to "build" here without consent.

# Site & Pattern — Design Philosophy & Intellectual Foundation

> **About this document.** This is the source of truth for *why* Site & Pattern is
> built the way it is. The body below preserves the founding philosophy document in
> full; what's added — interleaved after each theme — is a **"Where this lives in the
> code"** note that ties the idea to the modules that implement it, with an honest
> **State** marker (*strong / partial / gap*).
>
> The connection runs both ways: the strongly-aligned modules carry a one-line
> `Design principle P# — see docs/DESIGN_PHILOSOPHY.md` anchor at the top of the file,
> and `tests/test_philosophy.py` keeps the anchors and this document from drifting
> apart.
>
> **Companion documents:**
> - [`REFERENCES.md`](REFERENCES.md) — the complete bibliography (every source text).
> - [`PHILOSOPHY_ROADMAP.md`](PHILOSOPHY_ROADMAP.md) — an in-depth, in-breadth map of
>   the features this framework makes possible, organized by principle.
>
> **A note on the name.** The application is **Site & Pattern** (formerly PermaDesign).
> What users see now reads "Site & Pattern"; a few internal identifiers keep the legacy
> `PermaDesign` name on purpose — the GitHub repo, the QSettings keys, the on-disk
> database *filenames*, and the frozen scripting/MCP API — so existing installs keep
> their data and the update path keeps working. The on-disk data *folder* is migrated
> from `PermaDesign` to `Site & Pattern` once, on first launch (see `src/user_paths.py`).

---

## Introduction

Site & Pattern is a native plant landscape design application for Alberta (hardiness zones 3b–4a) built on a simple conviction: the most effective landscape designs are the ones that work *with* ecological intelligence rather than against it. This philosophy is drawn from a synthesis of complexity science, ecological design, indigenous land stewardship, systems thinking, software architecture, and contemplative practice. The application treats landscapes not as static arrangements of individual plants but as dynamic, self-organizing communities operating across multiple timescales — from seasonal ground cover shifts to century-scale canopy succession. The design methodology encodes ecological archetypes (plant community patterns observed in natural systems) into repeatable, site-responsive planting formulas, supported by a relational data model that prioritizes connections between species (mycorrhizal associations, pollinator dependencies, competitive and complementary dynamics, successional sequences) over individual plant attributes. This document lays out the core themes and source material that inform the application's architecture, data modeling, user experience, and long-term development direction.

---

## Core Design Themes

### 1. Living systems self-organize from the bottom up

Complex ecological order emerges from simple rules applied locally, not from top-down blueprints. Kauffman's self-organization, Meadows' feedback loops, Capra's living systems theory, Johnson's emergence, and Alexander's pattern languages all converge on this finding. The application should not prescribe rigid layouts — it should encode the generative rules that produce good layouts. Plant guilds are emergent structures, not designed objects.

> **Where this lives in the code:** `src/placement_score.py` scores every candidate cell
> for a plant on continuous ecological fitness (shade, moisture, slope, edge) rather than
> stamping a fixed layout; `src/llm_design.py` turns an ecological brief into deterministic,
> scored placement; `src/pattern_language.py` now frames seeded communities
> (`src/db/polycultures.py`) as Alexander patterns (problem → context → forces → solution →
> related patterns). **State: strong** — generative scoring *plus* an explicit pattern-language
> framing (roadmap F4, shipped); and the design now *self-heals* over time — the V2.24 gap
> recruitment in `src/succession_engine.py` lets self-seeding natives colonise the openings the
> closing canopy leaves, an emergent bottom-up behaviour rather than a stamped layout. The
> remaining gap is that the placement rules themselves are still implicit in
> `placement_score`/`llm_design` rather than declared and tweakable (F23).

### 2. The best designs disappear into their context

Fukuoka's do-nothing farming, Alexander's "quality without a name," Weaner's managed succession, and ecological planting design all demonstrate that the most sophisticated design looks like it was never designed at all. The application succeeds when the landscapes it helps create appear to have grown there naturally — because, in a meaningful sense, they did.

> **Where this lives in the code:** the aesthetic-composition terms in
> `src/placement_score.py` — `_height_gradient` (tall to the north), `_cohesion` (legible
> bed grouping), `_rhythm` (natural repetition, not mega-clumps) — joined by naturalistic
> drift layouts in `src/layout.py` and layer/spread-aware spacing in
> `src/planting_spacing.py` (roadmap F22/F35, shipped) so plantings read as grown rather
> than gridded; and the **walkable reference-ecosystem library** (`src/reference_ecosystem.py`,
> roadmap F50) that lets the user walk the natural community their ecoregion is reaching toward —
> the "grown, not designed" endpoint made concrete as a target to design against. **State: strong.**

### 3. Relationships matter more than components

Simard's mycorrhizal networks, Lowenfels' soil food web, Sheldrake's fungal connections, Tallamy's insect-plant co-evolution, and Kimmerer's reciprocity all point to the same conclusion: the unit of ecological survival is the relationship, not the organism. The application's plant database contains hundreds of species, but the real value is in the edges between them — which species support each other, which compete, which succeed each other over time, which share mycorrhizal networks.

> **Where this lives in the code:** `src/db/fauna.py` + the `plant_fauna` junction (500+
> documented plant↔animal relationships with type and specificity), companion pairs in
> `src/db/seed_data.py`, `polyculture_members`, and the `plant_uses` junction; the food-web
> completeness check in `src/habitat_score.py` (`food_web`) now scores whether a design
> closes the host-plant → caterpillar → bird chain (roadmap F3, shipped), and specialist
> relationships are spotlighted through `fauna` specificity (F9, shipped); the **native-bee
> habitat builder** (`src/bee_habitat.py`, roadmap F37) now turns the plant↔bee edges into
> per-species advice — matched floral hosts, nesting needs, and a flight-season forage check
> backed by the schema-v39 `bee_attributes` spine; the **pull-a-plant impact simulator**
> (`src/plant_impact.py`, roadmap F46) makes those edges felt by *breaking* them — remove a
> plant and see which species lose all support and whether the food-web chain snaps; and the
> **feed-a-chickadee scenario** (`src/chickadee_scenario.py`, roadmap F47) walks one edge all
> the way up — host plant → caterpillar → nestling — weighing the design's caterpillar capacity
> against the 6,000–9,000 a brood needs. **State: partial (strengthening)** — the relationships
> are increasingly *scored*, now *testable by removal*, and now *followed up the chain to a
> fledged bird*, but not yet drawn as a network (F5) or unified into one edges layer (F7);
> mycorrhizal/symbiosis links still live only in plant `notes` text.

### 4. Time is the most undervalued design variable

Brand's shearing layers, Weaner's succession planting, Bridges' transition psychology, and ecological succession theory all demonstrate that systems operate on multiple timescales simultaneously. Most designs fail because they optimize for a single moment rather than a trajectory. A landscape is a process, not a product. The application's most important feature is temporal modeling — showing users what their landscape will look like in year 1, year 5, year 15, and year 30 as pioneer species give way to climax community.

> **Where this lives in the code:** `src/succession.py` (pioneer/mid/climax roles +
> presence-fade curves + restoration stages), the growth-year slider in
> `src/scene3d_window.py`, the year-aware `src/scene_contract.py`, the growth fields
> (`growth_rate`, `years_to_maturity`, `growth_curve`) in `src/db/schema.sql`, the
> Year 1 / 5 / 15 / 30 snapshot view (`src/snapshot_timeline.py` + `src/snapshot_window.py`,
> roadmap F2 — the philosophy's literal "most important feature", shipped), the
> spring/summer/fall/winter seasonal toggle (F16, shipped), and the **phenology "what's
> happening now" dashboard** (`src/phenology.py`, roadmap F51) that reads the design's trajectory
> at *this* month's resolution — what's blooming, fruiting, waking, and going dormant right now.
> The timeline is no longer merely *visual*: the **temporal succession engine**
> (`src/succession_engine.py`, V2.21) computes the shade the growing overstory casts over the
> understory year by year and lets sun-loving plants that get over-topped past their tolerance
> decline and die, so the year-N scene shows the emerging *climax community* — the survivors —
> rather than every plant frozen at full health (folded into `scene_contract` health/opacity and
> the 3D viewer's withered render). V2.24 makes that simulation more honest: a declared-deciduous
> crown shades the understory only for its leaf-on season (so a part-shade plant thrives under a
> birch where it would struggle under a spruce), canopy trees are *suppressed* by crowding rather
> than culled like a forb, and — crucially — a shaded-out gap does not stay bare: a self-seeding
> herbaceous native already in the design **recruits into it** and grows in, so the trajectory now
> shows *recovery*, not just loss. **State: strong.**

### 5. Perception is constructed, not received

Yong's Umwelt research, Deutscher's linguistic relativity, Berger's visual culture theory, Norman's affordances, and pain science all demonstrate that what an observer notices depends on what they have been trained to notice. The application is fundamentally a perception tool: it should help users *see* ecological relationships they currently cannot — pollinator pathways, mycorrhizal connections, successional trajectories, and habitat value that are invisible to the untrained eye.

> **Where this lives in the code:** the site-analysis overlays in `src/analysis_panel.py`
> and `html/map/06-overlays.js` (sun path, wind shelter zones, shade), plus sector analysis,
> the seasonal view toggle (roadmap F16, shipped) that lets the eye read leaf-on vs.
> leaf-off and bloom, the **site photo underlay** (`src/site_photo.py`, roadmap F24) that
> puts the user's real yard under the design, and the **snow-catch microsite overlay**
> (`src/snow_microsite.py`) that draws where winter snow drifts into the lee of windbreaks —
> an invisible microclimate made visible by reusing the wind-shelter geometry — and the
> **native-bee habitat builder** (`src/bee_habitat.py`, roadmap F37, "see what a bee sees"),
> which makes a chosen bee's hidden needs legible: which of your plants feed it, where it
> nests, and the gaps in its flight-season forage — and, in the 3D preview, lets you *fly as
> that bee* (`src/scene3d_window.py` → `html/scene3d.html`, a first-person bee camera with its
> host flowers marked) and recolours the 2D map as that bee's floral-resource map
> (`html/map/06-overlays.js` — its nectar/pollen plants glow, the rest greys out), a first taste
> of Umwelt as both overlay *and* embodiment. The **Field Study quiz layer**
> (`src/field_study.py`, roadmap F48) closes the loop the other way — the first time the app
> *asks* the user instead of only answering, building the perception through retrieval practice
> (identify a plant, trace a specialist to its host, spot the food-web gap in your own design);
> and the **guided lesson track** (`src/lesson_track.py`, roadmap F53) sequences the scattered
> teaching moments into one narrated path — keystone plants, closing the food web, succession,
> ranges-not-certainties — each step read back against the user's own design; and **docent /
> presentation mode** (`src/docent.py`, roadmap F52) turns the design into a narrated tour built
> from its own facts, so the user can teach *others* to see it (a neighbour, an HOA board, a class).
> **State: partial** — site forces, seasonality, the real site, winter snow microsites, a single
> bee's world, active recall, a guided course and a presentable tour are made visible, but
> ecological *relationships* (pollinator
> pathways, mycorrhizal networks, succession trajectories) are still not drawn as networks
> (roadmap F5, F15).

### 6. Conventional value metrics miss ecological value

Graeber, Saito, Raworth, Schumacher, and Tsing demonstrate that market price fails to capture ecological, social, or relational value. A native prairie is "worthless" by conventional metrics and priceless by ecological ones. The application implicitly argues for a different value system every time it recommends a native species over an ornamental — and the interface should make this ecological value legible, not hidden.

> **Where this lives in the code:** `src/habitat_score.py` and the Habitat Value tab in
> `src/analysis_panel.py` (a 0–100 score from native ratio, keystone species, host plants,
> bird food, vegetation layers, structures, and bloom continuity — explicitly grounded in
> Tallamy); honest cost framing in `src/sourcing.py`; the **lawn-equivalent counterfactual**
> (`src/lawn_zones.py:lawn_counterfactual`, roadmap F10) that scores this design against the ≈0
> an equivalent lawn provides; **"why it matters" ecological-role labels**
> (`src/ecological_role.py`, roadmap F1) that make each plant's value legible in the browser
> itself, not just in the Habitat tab; and the **feed-a-chickadee scenario**
> (`src/chickadee_scenario.py`, roadmap F47), which converts the abstract food-web score into
> the one number people feel — whether the design's host plants could raise a chickadee brood
> (the 6,000–9,000 caterpillars of Tallamy & Shropshire 2009), reported as an honest range.
> **State: strong.**

### 7. Generalist knowledge produces the most original design insights

The most important insights in ecological design come from people who cross disciplinary boundaries — Alexander (architect who influenced software), Bridle (artist who does philosophy of technology), Graeber (anthropologist who rewrote economics), Kauffman (biologist who does philosophy of complexity). The application is built at the intersection of complexity science, ecology, software architecture, and design theory. This cross-domain foundation is not incidental — it is the primary source of the application's distinctiveness.

> **Where this lives in the code:** app-wide rather than in a single module — the
> architecture itself sits at the intersection of complexity science, ecology, and
> software design (e.g. the deep-module / information-hiding discipline frozen by
> `tests/test_architecture_guard.py`); and the **guided lesson track**
> (`src/lesson_track.py`, roadmap F53) deliberately crosses ecology, design and time in one
> short course. **State: foundational.**

### 8. Repair is more sophisticated than creation

Kintsugi philosophy, Cradle to Cradle design, regenerative landscaping, and mycoremediation all demonstrate that restoring broken systems requires deeper understanding than building new ones. Most users will not be designing landscapes from bare ground — they will be converting existing lawns, ornamental beds, and degraded sites. The application must be as effective at guiding transformation and restoration as it is at new design.

> **Where this lives in the code:** the lawn-to-habitat conversion workflow
> (`src/lawn_zones.py` + drawn conversion zones), the evaluate→critique→revise→repair loop in
> `src/design_critic.py`, the **phased Planting Plan** (`src/planting_plan.py`, roadmap F40) that
> sequences the conversion into the ground — structure, then matrix, then fill — and now the
> **year-by-year conversion schedule** (`src/conversion_plan.py`, roadmap F17) that crosses the
> drawn zones with the restoration-stage timeline into a remove-this / plant-that, when task list,
> plus the **lawn-equivalent counterfactual** (roadmap F10) that frames the conversion as repair of
> a near-zero-value lawn; and the V2.24 **gap recruitment** in `src/succession_engine.py` models the
> system repairing *itself* — self-seeding natives recolonising the openings the maturing canopy
> leaves, so restoration is shown as an ongoing process rather than a one-time install. **State: strong.**

### 9. Uncertainty is a feature, not a bug

Ecological succession, Buddhist impermanence, Taleb's antifragility, Carse's infinite games, and complexity science all converge: rigid systems break, flexible systems adapt. The application should communicate probability and range rather than false precision. "This guild tends to establish well in these conditions" is more honest and more useful than deterministic prescriptions. Ecological modeling involves irreducible uncertainty, and the interface should make that uncertainty legible rather than hiding it behind confident-looking outputs.

> **Where this lives in the code:** price/spacing/height **ranges** in `src/sourcing.py`,
> the `backed` flag + caveats in `src/design_goals.py`, the informational (deliberately
> un-summed) fauna counts and month-range bloom parsing in `src/habitat_score.py`, and the
> **precipitation-timing split** in `src/precip_split.py` — which separates immediately-available
> growing-season rain from delayed snowmelt water (both as honest liquid-water equivalent, with
> *no* false snow-depth precision) rather than letting one "precipitation" number imply more
> growing-season water than a site gets. **State: strong** (language); **partial** (placement is
> still point-wise/deterministic once generated — see roadmap item C).

### 10. Design for relationships, not objects

This is the synthesis of all preceding themes. Every other landscape application treats plants as individual items to be placed on a map. Site & Pattern treats them as nodes in a network — connected by mycorrhizal associations, pollinator dependencies, succession sequences, competitive dynamics, and complementary resource use. The 35-field species schema is a strong foundation, but the application's true value will come from modeling the edges between plants, not just the nodes themselves.

> **Where this lives in the code:** the synthesis of #3 — `src/db/fauna.py`,
> `src/db/polycultures.py`, the companion tables, and the `plant_uses` junction (the
> shipped schema is now 41 fields); the food-web score (F3) and specialist-host spotlight
> (F9) have begun surfacing edges as scored, legible relationships, and the **ecological-role
> labels** (`src/ecological_role.py`, roadmap F1) now read those plant↔fauna edges back to the
> user per plant ("hosts 7 caterpillars", "specialist host"); the **native-bee habitat builder**
> (`src/bee_habitat.py`, F37) reads the same bee↔plant edges *forward* into "design for this
> species" guidance. **State: partial** — the edges are
> modeled in data, increasingly scored, summarised per node, and now actionable per target
> species, but not yet drawn as a first-class relationship network in the UI (roadmap F5, F7).

### 11. The body and the site know things the screen does not

Knowledge lives in hands, soil, wind, and direct observation — not only in abstractions and databases. The application should drive users outside, not keep them at a screen. The best landscape designs come from people who walk the site, feel the soil texture, notice where water pools and where wind dries. Digital tools augment direct observation; they do not replace it.

> **Where this lives in the code:** `src/analysis_panel.py`, `src/wind.py`,
> `src/soil_grid.py`, `src/terrain.py`, `src/property_data.py`, `src/scan_import.py`; the
> **printable Planting Plan** (`src/planting_plan.py`, roadmap F40) that sends the user *out to
> the yard* with what to buy, where to space it, and when to plant; the **site-walk field notes**
> (`src/field_notes.py`, roadmap F6) that capture what the user notices on the ground (where water
> pools, snow drifts, soil compacts); and the **site photo underlay** (`src/site_photo.py`, roadmap
> F24) that brings a real yard/drone photo onto the map; and **winter snow cover & survival
> metrics** (`src/snow.py`) that model snow's insulation (cover-days, freeze–thaw, chinook thaw,
> rain-on-snow) into honest, design-for-the-bad-year guidance; and the **phenology dashboard's
> "go check outside" prompt** (`src/phenology.py`, roadmap F51) that turns each month's prediction
> into a standing invitation to walk the ground and confirm it ("is it early, late, on time?").
> **State: strong (was a gap)** — the app now *fetches* site data, *hands the user a field plan*,
> *captures their own on-site observation*, *reads the winter the plants will actually face*, and
> *sends the user out to verify its predictions*. The remaining reach: pinning individual
> observations to map points and feeding them back into generation as soft constraints (the
> "pinned" slice of F6).

### 12. Indigenous knowledge is honoured through relationship, not extraction

Several of this document's sources — notably Kimmerer's *Braiding Sweetgrass*, Yunkaporta's *Sand Talk*, and elements of Ohlsen's *The Regenerative Landscaper* — draw on Indigenous knowledge systems, land stewardship, and ecological worldviews developed over millennia by Indigenous peoples. This knowledge is consistently among the most sophisticated and empirically validated ecological design wisdom available, often anticipating findings Western ecology has only recently arrived at. But Indigenous knowledge is **not an open resource to be extracted, encoded, or productized** without the explicit involvement and consent of the communities it originates from — to do so would replicate the very colonial pattern of extraction these knowledge systems critique. The same ecological thinking that drives the rest of this document insists that knowledge, like an ecosystem, functions through relationship and reciprocity, not extraction. So this is a design principle, not a footnote: Site & Pattern will not incorporate Indigenous ecological knowledge, land-management practices, plant-use traditions, or design frameworks into its data model, recommendations, or interface without:

- **Direct consultation** with Indigenous elders, knowledge keepers, and/or community leaders relevant to the specific knowledge in question and to the Treaty 6 territory (Alberta) context in which this application operates.
- **Free, prior, and informed consent** from appropriate Indigenous community representatives, consistent with UNDRIP (the United Nations Declaration on the Rights of Indigenous Peoples) and the Truth and Reconciliation Commission's Calls to Action.
- **Ongoing relationship**, not transactional consultation — sustained, reciprocal partnership rather than a one-time approval.
- **Attribution, benefit-sharing, and community control** over how Indigenous knowledge is represented, contextualized, and used within the application.

Until such consultation has taken place, references to Indigenous knowledge in this project serve as *directional indicators* — they point toward bodies of knowledge that are relevant and valuable, without presuming the right to encode or operationalize them. Proceeding otherwise would contradict the philosophical foundation of the project itself.

> **Where this lives in the code:** nowhere — *by design*. This principle is expressed as a
> constraint, not a feature: the app deliberately does **not** encode Indigenous knowledge
> into its data model, recommendations, or UI. The gate is consent. It surfaces as a guardrail
> wherever work could brush against it — the "Indigenous knowledge" method note in
> [`PHILOSOPHY_ROADMAP.md`](PHILOSOPHY_ROADMAP.md), the directional framing in
> [`REFERENCES.md`](REFERENCES.md), and the consent-gate rule injected at session start (see
> `CLAUDE.md` and the `.claude/` SessionStart hook). **State: directional guardrail** —
> references stay directional until free, prior, and informed consent is obtained.

---

## Top 10 Source Texts for Application Development

Ranked by direct relevance to the application's architecture, data modeling, UX, and design methodology. (The complete bibliography is in [`REFERENCES.md`](REFERENCES.md).)

1. **A Pattern Language** — Christopher Alexander (1977)
   The application's namesake and intellectual DNA. Alexander's pattern structure — problem → context → forces → solution → related patterns — is how plant guilds, site conditions, and design moves should be organized in the application. The concept of a generative language of design is the foundational architecture.

2. **Planting in a Post-Wild World** — Thomas Rainer & Claudia West (2015)
   The design methodology the application should encode. Ecological archetypes (stress-tolerant groundcover communities, structural plant layers, seasonal theme plants, dynamic fill species) translated into repeatable planting formulas. The bridge between ecological theory and actionable planting plans.

3. **Garden Revolution** — Larry Weaner & Thomas Christopher (2016)
   Succession as a primary design tool. Designing for what the landscape *becomes*, not just what it is at installation. The conceptual basis for the application's temporal modeling feature — managed succession as the engine of long-term landscape development.

4. **Thinking in Systems** — Donella Meadows (2008)
   The conceptual vocabulary for everything the application models: stocks, flows, feedback loops, reinforcing and balancing dynamics, leverage points. Without systems literacy, the application is a plant catalog. With it, the application is an ecological modeling tool.

5. **Design with Nature** — Ian McHarg (1969)
   The overlay method for site analysis — layering soil type, water flow, slope, solar exposure, wind patterns, and existing vegetation to determine what should go where. The application's site analysis module is McHarg's method digitized and made interactive.

6. **The Design of Everyday Things** — Don Norman (2013 revised edition)
   Affordances, signifiers, mapping, and feedback — the discipline of making complex tools intuitive. The most ecologically sophisticated application in the world is useless if users cannot figure out how to use it. UX integrity is non-negotiable.

7. **Finding the Mother Tree** — Suzanne Simard (2021)
   The empirical basis for plant relationship modeling. Mycorrhizal networks, resource sharing between species, kin recognition, hub trees. The science behind why guilds work and which species should be connected in the application's relational data model.

8. **How Buildings Learn** — Stewart Brand (1994)
   Shearing layers applied to landscape design: trees operate on a century timescale, shrubs on decades, perennials on years, annuals on seasons, soil biology continuously. The application's data schema must handle these different rates of change, and Brand provides the conceptual framework for temporal layering.

9. **A Philosophy of Software Design** — John Ousterhout (2018, 2nd ed. 2021)
   Managing complexity in code, which is managing complexity in ecological modeling. Deep modules (simple interfaces hiding complex implementations), information hiding, strategic versus tactical programming. 180 pages that directly improve codebase architecture for a project of this scope.

10. **Nature's Best Hope** — Doug Tallamy (2019)
    The application's *why*. The scientific case — grounded in insect-plant co-evolution data and food web research — that native plant landscapes in private yards constitute the most impactful conservation strategy available. When a user asks "why should I use this?" Tallamy's data is the answer.

> **On Indigenous knowledge:** the consent principles that once lived in an addendum here are
> now **core principle #12** above (*Indigenous knowledge is honoured through relationship,
> not extraction*) — promoted from footnote to foundation. The full bibliography is in
> [`REFERENCES.md`](REFERENCES.md).

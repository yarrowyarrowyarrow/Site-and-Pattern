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
> scored placement; seeded communities live in `src/db/polycultures.py`.
> **State: partial** — placement is generative-by-scoring, but communities are still
> templates and most generative rules are implicit rather than declared.

### 2. The best designs disappear into their context

Fukuoka's do-nothing farming, Alexander's "quality without a name," Weaner's managed succession, and ecological planting design all demonstrate that the most sophisticated design looks like it was never designed at all. The application succeeds when the landscapes it helps create appear to have grown there naturally — because, in a meaningful sense, they did.

> **Where this lives in the code:** the aesthetic-composition terms in
> `src/placement_score.py` — `_height_gradient` (tall to the north), `_cohesion` (legible
> bed grouping), `_rhythm` (natural repetition, not mega-clumps). **State: strong.**

### 3. Relationships matter more than components

Simard's mycorrhizal networks, Lowenfels' soil food web, Sheldrake's fungal connections, Tallamy's insect-plant co-evolution, and Kimmerer's reciprocity all point to the same conclusion: the unit of ecological survival is the relationship, not the organism. The application's plant database contains hundreds of species, but the real value is in the edges between them — which species support each other, which compete, which succeed each other over time, which share mycorrhizal networks.

> **Where this lives in the code:** `src/db/fauna.py` + the `plant_fauna` junction (500+
> documented plant↔animal relationships with type and specificity), companion pairs in
> `src/db/seed_data.py`, `polyculture_members`, and the `plant_uses` junction.
> **State: partial** — the relationship data is rich but not yet visualized as a network,
> and mycorrhizal/symbiosis links currently live only in plant `notes` text.

### 4. Time is the most undervalued design variable

Brand's shearing layers, Weaner's succession planting, Bridges' transition psychology, and ecological succession theory all demonstrate that systems operate on multiple timescales simultaneously. Most designs fail because they optimize for a single moment rather than a trajectory. A landscape is a process, not a product. The application's most important feature is temporal modeling — showing users what their landscape will look like in year 1, year 5, year 15, and year 30 as pioneer species give way to climax community.

> **Where this lives in the code:** `src/succession.py` (pioneer/mid/climax roles +
> presence-fade curves + restoration stages), the growth-year slider in
> `src/scene3d_window.py`, the year-aware `src/scene_contract.py`, and the growth fields
> (`growth_rate`, `years_to_maturity`, `growth_curve`) in `src/db/schema.sql`.
> **State: strong.**

### 5. Perception is constructed, not received

Yong's Umwelt research, Deutscher's linguistic relativity, Berger's visual culture theory, Norman's affordances, and pain science all demonstrate that what an observer notices depends on what they have been trained to notice. The application is fundamentally a perception tool: it should help users *see* ecological relationships they currently cannot — pollinator pathways, mycorrhizal connections, successional trajectories, and habitat value that are invisible to the untrained eye.

> **Where this lives in the code:** the site-analysis overlays in `src/analysis_panel.py`
> and `html/map/06-overlays.js` (sun path, wind shelter zones, shade), plus sector
> analysis. **State: partial** — site forces are made visible; ecological *relationships*
> (pollinator pathways, mycorrhizal networks, succession trajectories) are not yet drawn.

### 6. Conventional value metrics miss ecological value

Graeber, Saito, Raworth, Schumacher, and Tsing demonstrate that market price fails to capture ecological, social, or relational value. A native prairie is "worthless" by conventional metrics and priceless by ecological ones. The application implicitly argues for a different value system every time it recommends a native species over an ornamental — and the interface should make this ecological value legible, not hidden.

> **Where this lives in the code:** `src/habitat_score.py` and the Habitat Value tab in
> `src/analysis_panel.py` (a 0–100 score from native ratio, keystone species, host plants,
> bird food, vegetation layers, structures, and bloom continuity — explicitly grounded in
> Tallamy); honest cost framing in `src/sourcing.py`. **State: strong.**

### 7. Generalist knowledge produces the most original design insights

The most important insights in ecological design come from people who cross disciplinary boundaries — Alexander (architect who influenced software), Bridle (artist who does philosophy of technology), Graeber (anthropologist who rewrote economics), Kauffman (biologist who does philosophy of complexity). The application is built at the intersection of complexity science, ecology, software architecture, and design theory. This cross-domain foundation is not incidental — it is the primary source of the application's distinctiveness.

> **Where this lives in the code:** app-wide rather than in a single module — the
> architecture itself sits at the intersection of complexity science, ecology, and
> software design (e.g. the deep-module / information-hiding discipline frozen by
> `tests/test_architecture_guard.py`). **State: foundational.**

### 8. Repair is more sophisticated than creation

Kintsugi philosophy, Cradle to Cradle design, regenerative landscaping, and mycoremediation all demonstrate that restoring broken systems requires deeper understanding than building new ones. Most users will not be designing landscapes from bare ground — they will be converting existing lawns, ornamental beds, and degraded sites. The application must be as effective at guiding transformation and restoration as it is at new design.

> **Where this lives in the code:** the lawn-to-habitat conversion workflow
> (`src/lawn_zones.py` + drawn conversion zones) and the evaluate→critique→revise→repair
> loop in `src/design_critic.py`. **State: strong.**

### 9. Uncertainty is a feature, not a bug

Ecological succession, Buddhist impermanence, Taleb's antifragility, Carse's infinite games, and complexity science all converge: rigid systems break, flexible systems adapt. The application should communicate probability and range rather than false precision. "This guild tends to establish well in these conditions" is more honest and more useful than deterministic prescriptions. Ecological modeling involves irreducible uncertainty, and the interface should make that uncertainty legible rather than hiding it behind confident-looking outputs.

> **Where this lives in the code:** price/spacing/height **ranges** in `src/sourcing.py`,
> the `backed` flag + caveats in `src/design_goals.py`, the informational (deliberately
> un-summed) fauna counts and month-range bloom parsing in `src/habitat_score.py`.
> **State: strong** (language); **partial** (placement is still point-wise/deterministic
> once generated — see roadmap item C).

### 10. Design for relationships, not objects

This is the synthesis of all preceding themes. Every other landscape application treats plants as individual items to be placed on a map. Site & Pattern treats them as nodes in a network — connected by mycorrhizal associations, pollinator dependencies, succession sequences, competitive dynamics, and complementary resource use. The 35-field species schema is a strong foundation, but the application's true value will come from modeling the edges between plants, not just the nodes themselves.

> **Where this lives in the code:** the synthesis of #3 — `src/db/fauna.py`,
> `src/db/polycultures.py`, the companion tables, and the `plant_uses` junction (the
> shipped schema is now 41 fields). **State: partial** — the edges are modeled in data but
> not yet surfaced as first-class relationships in the UI.

### 11. The body and the site know things the screen does not

Knowledge lives in hands, soil, wind, and direct observation — not only in abstractions and databases. The application should drive users outside, not keep them at a screen. The best landscape designs come from people who walk the site, feel the soil texture, notice where water pools and where wind dries. Digital tools augment direct observation; they do not replace it.

> **Where this lives in the code:** `src/analysis_panel.py`, `src/wind.py`,
> `src/soil_grid.py`, `src/terrain.py`, `src/property_data.py`, `src/scan_import.py`.
> **State: partial** — strong at *fetching* site data, weak at *capturing the user's own
> on-site observation*. The structured "site-walk field notes" idea (roadmap item D) is
> the most direct expression of this principle still to be built.

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

---

## Addendum: Indigenous Knowledge, Consultation & Consent

Several source texts in this document — notably Kimmerer's *Braiding Sweetgrass*, Yunkaporta's *Sand Talk*, and elements of Ohlsen's *The Regenerative Landscaper* — draw on Indigenous knowledge systems, land stewardship practices, and ecological worldviews developed over millennia by Indigenous peoples. This knowledge is consistently among the most sophisticated and empirically validated ecological design wisdom available, often anticipating findings that Western ecology has only recently arrived at through institutional science.

**However, Indigenous knowledge is not an open resource to be extracted, encoded, or productized without the explicit involvement and consent of the communities from which it originates.** To do so would replicate the very colonial pattern of extraction that these knowledge systems critique.

Site & Pattern will not incorporate Indigenous ecological knowledge, land management practices, plant use traditions, or design frameworks into its data model, recommendations, or interface without:

- **Direct consultation** with Indigenous elders, knowledge keepers, and/or community leaders relevant to the specific knowledge in question and to the Treaty 6 territory (Alberta) context in which this application operates.
- **Free, prior, and informed consent** from appropriate Indigenous community representatives, consistent with the principles outlined in UNDRIP (United Nations Declaration on the Rights of Indigenous Peoples) and the Truth and Reconciliation Commission's Calls to Action.
- **Ongoing relationship**, not transactional consultation. Any incorporation of Indigenous knowledge must be grounded in sustained, reciprocal partnership — not a one-time approval process.
- **Attribution, benefit-sharing, and community control** over how Indigenous knowledge is represented, contextualized, and used within the application.

This is not a limitation on the application's development — it is a design principle. The same ecological thinking that informs the rest of this document insists that knowledge, like ecosystems, functions through relationship and reciprocity, not extraction. Proceeding without proper consultation would contradict the philosophical foundation of the project itself.

Until such consultation has taken place, references to Indigenous knowledge in this document serve as *directional indicators* — they point toward bodies of knowledge that are relevant and valuable, without presuming the right to encode or operationalize them.

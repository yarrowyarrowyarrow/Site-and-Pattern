# Site & Pattern — User Guide

A 5-minute tour of the controls. Read top-to-bottom, or jump to a section.

---

## 1. What you're looking at

When the app opens you'll see four areas:

- **Map** (centre) — Edmonton by default; pan with click-and-drag, zoom with the mouse wheel.
- **Toolbar** (top) — drawing tools, layer toggles, zoom-sensitivity combo.
- **Side panel** (right) — five tabs: **Plants** (with Plant Communities), **Site**, **Structures**, **Analysis**, **Planning**.
- **Status bar** (bottom) — coordinates, hardiness zone, current mode (e.g. "Placing: Yarrow — click map").

---

## 2. Draw your property first

Click **⬡ Boundary** in the toolbar, then click on the map to add corner points. **Double-click** (or click the first point again) to close the polygon. The hardiness zone is auto-detected from the boundary and shown in the status bar.

You can edit a boundary later by clicking it: drag white vertices to reshape, drag orange corner handles to resize, drag the interior to move. Right-click for colour, label toggles, or delete. **Esc** exits edit mode.

---

## 3. Find a plant

Open the **Plants** tab.

- Type a name in **Search plants…**.
- Narrow with the filter rows: **Type / Sun / Water / Use** combos, plus toggles for **Native AB**, **Edible**, **Medicinal**, **N-Fixer**, **Pollinator**, **Perennial**, and the habitat-focused trio **Keystone**, **Host Plant**, **Bird Food**.
- Pick a target Alberta ecoregion in **Restoring toward:** to filter the plant list to species documented from that region — Aspen Parkland, Mixedgrass Prairie, Fescue/Foothills, Boreal Mixedwood, Riparian, Wet Meadow, or Subalpine/Montane. The choice persists across sessions.
- Click the **▶ chevron** on any row to expand it inline. You'll see the full data block — sun, water, spacing, height, bloom, fruit, edible parts, uses — plus a **colour-coded 12-month planting calendar** and notes.

Long names automatically wrap to two lines so nothing is hidden.

---

## 4. Place a single plant

1. Click a plant row to select it.
2. In the **Placement Mode** strip choose **Single**.
3. (Optional) Click the **●** button to pick a marker colour, or set **Qty** to drop a hex burst at one click.
4. Click **Place on Map**, then click anywhere on the map.
5. Press **Esc** to finish.

Right-click a placed marker for **Remove this plant** or **Delete group** (when the marker belongs to a multi-plant placement).

---

## 5. Place a row, grid, or circle

Pick **Row**, **Grid**, or **Circle** in the Placement Mode strip, then click **Place on Map**. Each takes two clicks:

| Mode | First click | Second click |
|------|-------------|--------------|
| Row | Start of row | End of row |
| Grid | One corner | Opposite corner |
| Circle | Centre | A point on the radius |

Tweakable parameters:

- **Grid** — Rows / Columns spinners (`auto` derives from spacing) and a **Stagger** checkbox for hex-pack offset.
- **Circle** — **Total** spinner (caps the plant count — important for **Fill (hex)** mode so big circles don't make thousands of markers), **Fill (hex)** for honeycomb-fill, and an Overlap slider.
- **All multi-modes** — an **Overlap** slider. `0%` = canopies just touch; `50%` = canopies overlap by half.

---

## 6. Plant community mix (multiple species in one bed)

To plant multiple species mixed together in one Row / Grid / Circle:

1. Right-click any plant in the results list → **Add to Mix**. Add 2–8 species.
2. The **Mix** panel shows each species with three controls:
   - A **clickable colour dot** — gives that species a unique marker colour just for this mix.
   - A **ratio spinner** (1–9) — `1:1:1` is even split; `3:1:1` gives that species 60%, others 20% each.
   - A **✕** button to remove the species.
3. Click **Place Mix on Map**, then drop a Row / Grid / Circle as usual. The recipe stays armed — click again to drop another, **Esc** to finish.

Distribution is deterministic and spread-optimised: same-species plants are automatically pushed apart so the bed reads as mixed, not blocky.

**Save / load mixes** with the **Save** button (above the species list) and the dropdown. **✕** deletes the saved mix.

The **Plant Communities** library on the same tab ships with 18 pre-built communities. The original 8 are food-forest-flavoured (Apple, Saskatoon, Evans Cherry, Bur Oak, Prairie Pollinator Garden, Boreal Shade, Medicinal Herb Circle, Native Berry Hedge). The **10 newer communities** are tuned around Habitat Value Score and forage categories — drop them when the score / forage tabs flag a deficiency:

- **Keystone Pollinator Mound** — lifts the keystone-species score
- **Caterpillar Host Garden** — lifts the host-plant score
- **Songbird Berry Patch** — lifts the bird-food score, staggered berries Jun–Sep
- **Continuous Bloom Pollinator Strip** — closes nectar gaps across Apr–Oct in one drop
- **Native Edible Garden** — Human Forage powerhouse, staggered native edibles Jun–Oct
- **Aspen Parkland Edge** — hits all 5 vegetation layers at once
- **Mixedgrass Prairie Patch** — grasses (nesting material) + native forbs
- **Boreal Woodland Floor** — shade-tolerant bird food and edible berries
- **Late-Season Pollinator Refuge** — fills the common Aug–Oct nectar gap
- **Riparian Willow Thicket** — keystone + host + bird food in a single community (willows)

---

## 7. Selection & multi-delete

- **Shift+drag** on empty map → marquee-selects every plant, boundary, and sun-path inside the rectangle.
- **Shift+click** an item to toggle its membership in the selection.
- **Ctrl+Shift+drag** = additive marquee (extends instead of replaces).
- The top-right **selection badge** shows the count plus **Delete** and **Clear** links.

---

## 8. Other drawing tools

- **📏 Measure** — click two points to add a measurement; right-click any existing measurement to delete just that one. Use the View bar's Measurement toggle to hide them all without deleting.
- **📝 Note** — click to drop a draggable text note. Right-click the note to remove it. Every map note is also listed under **Planning → Notes** — click one there to jump to it on the map.
- **Structures tab** — search a structure library, drag hedgerows (4 styles: Hedge / Fence / Living Fence / Windbreak), or draw shapes (Garden Bed, Pathway, Patio, Lawn, Mulch, Water Feature, Custom).

The View bar (🛰 Satellite, ⬡ Boundary, 📏 Measurement, **#** Grid, ✿ Plants, 🌳 Canopy, 🏗 Structures) toggles each layer's visibility without deleting anything. The Grid action's ▾ menu picks the base size (1×1, 5×5, 10×10, 100×100 m) plus opacity and colour.

---

## 9. Site analysis (Analysis tab)

- **Sun Path** — pick a date (Summer Solstice, Equinox, Today, …), click *Place Sun Path…*, click the map. Shows the sun arc + sunrise/sunset/daylight-hours summary.
- **Wind** — three steps in one tab: **1** fetch this site's real wind history (Open-Meteo, cached for offline) and read the wind rose; **2** check the prevailing-direction dial (set automatically from the data — drag it to test other directions); **3** overlay the map: live wind shadow (sheltered zones behind trees/shrubs), snow catch, and the arrows + windbreak shelter-zone overlay via *Show Wind Overlay*.
- Manual **contour drawing** lives on the Site tab (next to the automatic slope analysis).

(The old Sectors and Season View tabs were retired in V2.25 — Sun Path and Wind cover the same questions with real data, and the season tile filter added no design value.)

The teaching tools live on their own top-level **Learn** tab (V2.25):

- **Field Study** — a five-question recall quiz built from your design and the plant catalogue: photo ID (only plants whose photo is actually downloaded), specialist relationships, and spot-the-gap questions about your own food web.
- **Lessons** — a short guided course narrated against your own project.
- **Present** — a docent-style walkthrough for showing the design to a neighbour or client.

---

## 10. Planning helpers (Planning tab)

- **Establishment Effort estimator** — splits maintenance hours into **Year 1** (heavy: watering-in, weeding bare zones, mulching, smother prep) and **Year 3+** (stewardship floor — established natives drop to ~30% of Y1 effort while cultivated plants stay closer to 100%). Enter your available hrs/week; the tool checks Year 1 against your capacity and reports the post-establishment drop-off.
- **Wildlife Forage** — month-by-month expandable tree of pollinator blooms and bird food (berries / seeds) from your placed plants. Expand a month to see the individual plants. Apr–Oct months with no bloom source are flagged red as **nectar gaps**.
- **Human Forage** — companion calendar for edible plants in your design. Shows what you can harvest each month with the edible part annotated (berries, leaves, roots, etc.).
- **Habitat Value Score** (Analysis panel) — composite 0–100 score derived from native ratio, keystone species, host plants, bird-food species, vegetation-layer diversity, habitat structures, and bloom continuity. The panel also generates **Tips for raising your score**: concrete Alberta-native plant and habitat-structure suggestions targeted at your lowest-scoring categories (e.g., "Add host plants: …", "Fill nectar gaps in June: …"). Based on Doug Tallamy's keystone-species framework.
- **Establishment Water Budget** — same garden / catchment inputs, but the demand splits into **Year 1** (1.5× baseline for establishment irrigation) and **Year 3+** (natives drop to ~0.2× baseline once rooted; cultivars stay at 1.0×). Shows both surpluses / deficits side-by-side, plus a suggested extra-barrel count for the Year-1 deficit.
- **Succession timeline** — drag the year slider 0–20 to see how the design matures.
- **Notes / journal** — free-form text editor with **Add Timestamp** and **+ Section** buttons, plus a **Notes pinned on the map** list of your 📝 Note pins — click one to frame it on the map.

---

## 11. Save & share

- **File → Save** (Ctrl+S) writes a `.perma.geojson` file — the whole design.
- **File → Open** (Ctrl+O) loads one.
- **File → Export PDF…** produces a printable booklet with the map screenshot, plant list, and notes.
- **File → Export Plant Order List…** produces a text list grouped by Alberta nursery source (ALCLA, Bow Valley Habitat, Wild About Flowers, Bedrock Seed Bank), with native woody / native herbaceous / cultivated sections.
- The app auto-saves every 5 minutes in the background.
- **Help → Check for Updates…** — one click to the newest version. On source installs (git checkout) the app switches itself to the newest published `V*.*` branch (any local source edits are set aside safely first) and offers to restart; on packaged `.dmg`/`.exe` installs it downloads and opens the newest installer from GitHub Releases. **Help → Switch to a specific version…** does the same for any published version, forward or back.

---

## 12. Keyboard shortcuts

| Shortcut | Action |
|----------|--------|
| Ctrl+N / Ctrl+O / Ctrl+S | New / Open / Save project |
| Ctrl+Shift+S | Save As |
| Ctrl+Z | Undo |
| Ctrl+Shift+Z or Ctrl+Y | Redo |
| Esc | Cancel current drawing / exit placement mode |
| Shift+drag | Marquee-select |
| Shift+click | Toggle an item in the selection |
| Right-click | Context menu (markers, boundaries, plant rows) |
| Mouse wheel | Zoom (sensitivity controlled by the toolbar combo) |

---

## 13. Tips that aren't obvious

- **Click a boundary's area label** to cycle units (m² → ha → acres → km²).
- The expanded plant calendar's colours map to life stages: **purple** = start indoors, **teal** = direct sow, **blue** = transplant, **green** = growing, **orange** = harvest, **brown** = pruning, **grey** = dormant. The current month gets a yellow ring.
- **Mix stays armed** across pattern clicks until **Esc** — you can drop ten mixed beds in a row with one click each.
- **Fill (hex) circles** need a **Total** cap or they'll generate thousands of markers on big radii.
- **Right-click a plant in the results list** for fast actions — *Place on Map*, *Place ×5*, *Add / Remove from Mix*.
- The **▶ chevron** doubles as a quick way to compare plants — multiple rows can stay expanded at once.

---

That's the whole interface. Have fun designing.

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

Open the **Plants** tab (**Browse**).

- Type in **Search plants by name or role…**.
- The line under the search box says which filters are on, for example *Restoring toward
  Aspen Parkland* once you have dropped a pin on your site. **Filters ▸** unfolds them and
  **Clear** unticks them all.
  - Nine dropdowns, each of which takes more than one value: **Type**, **Sun**, **Water**,
    **Role** (a plant must have every role you tick), **Where to buy**, **Restoring
    toward** (ecoregions; ticking a system includes everything inside it), **Blooms in**,
    **Fruits in** and **Flower colour**.
  - Nine on/off filters: **Native** (to Alberta, as the VASCAN flora records it),
    **Perennial**, **Feeds a specialist**, **Edible**, **Pet safe**, **Child safe**, **Well
    behaved**, **Easy to find** and **Has a photo**.
- **Order.** With a pin on your site the list starts with plants **recorded near this
  site**, then those hardy in your zone, with plants that need standing water last.
  Nothing is hidden, and a record nearby says nothing about your yard's sun or soil. You
  can also order by **Name**, **Type**, **Animals supported** or **Height**.
- Hover over a row to learn what its marks mean: the coloured dot is the plant's type,
  **Z3–7** its hardiness zones, **AB** that it is native to Alberta, and **[1×]** how many
  are already in this design.
- **Click a plant to read about it.** Its page opens beside the list, over the right edge
  of the map: photo, why it matters, roles, conditions, size, when it flowers and fruits,
  where it has been recorded, the animals it feeds, what grows well with it and where to
  buy it. The arrow keys step through the list and the page follows; **→** moves the
  keyboard into the page, and **Esc** or **✕** closes it.

The same search, filters and list are in **View → Plant Directory**, a bigger window for
reading that works before you have a design (with a design open, its **Place** button
hands the plant to the map), and in the community builder.

---

## 4. Place a single plant

1. Click a plant row to select it. Selecting only shows it: its page opens beside the
   list, the button under the list reads **Place ‹plant› on the map**, and the map is
   untouched.
2. Press **Place ‹plant› on the map** (under the list or on its page), or double-click the
   row, press **Enter** on it, or right-click → **Place ‹plant› on Map**. The page closes so
   the yard is clear, and a bar appears over the top of the map:
   *"Placing ‹plant›. Click the map to place it. Each click places another."* The pointer
   is a crosshair with the plant's footprint under it: a yellow ring at its planting
   spacing, a green one at its mature spread.
3. Click the map to place it. Each click places another.
4. While placing, click another plant in the list (or arrow to it) to switch to it; the
   bar says so. Dragging a plant into the mix doesn't switch, and no page opens while you
   are placing.
5. In the bar: **Qty** drops a cluster of that many at each click (the footprint shows the
   cluster and its count), and **Colour** sets the plant's marker colour.
6. Press **Esc** or **Done** to stop.

Right-click a placed marker for **Remove this plant** or **Delete group** (when the marker belongs to a multi-plant placement).

---

## 5. Place a row, grid, or circle

While placing, pick **Row**, **Grid**, **Circle** or **Fill area** in the bar over the map.
Only that pattern's settings show beside it, and changing one re-arms the map. Until the
first click the footprint shows one plant; after it, every plant the pattern will lay,
with a count.

| Mode | First click | Second click |
|------|-------------|--------------|
| Row | Start of row | End of row |
| Grid | One corner | Opposite corner |
| Circle | Centre | A point on the radius |
| Fill area | Click around the area | Double-click to finish |

Settings, in the bar:

- **Row**: **Count** (`auto` derives it from spacing) and **Drift**, a naturalistic sweep.
- **Grid**: **Rows** / **Columns** and **Stagger** for a hex-pack offset.
- **Circle**: **Total** (caps the count, which matters with **Fill (hex)**) and **Fill (hex)**.
- **Fill area**: **Spacing** (starts at the plants' own) and **Matrix planting**.
- **Row, Grid and Circle**: **Overlap** (`0 %` = canopies just touch; `50 %` = they overlap by
  half) and **Canopy width**, to space by mature spread instead of planting spacing.

---

## 6. Plant community mix (multiple species in one bed)

To plant multiple species mixed together in one Row / Grid / Circle:

1. Right-click any plant in the results list → **Add to Mix**. Add 2–8 species.
2. The **Mix** panel shows each species with three controls:
   - A **clickable colour dot** — gives that species a unique marker colour just for this mix.
   - A **ratio spinner** (1–9) — `1:1:1` is even split; `3:1:1` gives that species 60%, others 20% each.
   - A **✕** button to remove the species.
3. Press **Place mix** under the list. The bar switches to **Row** (a mix can't go down one
   plant per click); pick Grid, Circle or Fill area there if you prefer. Building a mix
   never arms the map by itself, and placing a single plant never places the mix. The
   mix stays armed: click again to drop another, **Esc** to finish.

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

- **Sun Path** — pick a date (Summer Solstice, Equinox, Today, …), click *Place Sun Path…*, then click the map once to anchor it. You get the sun's arc, the sunrise/sunset/daylight summary, and a **time-of-day slider**: drag it and the sun travels its arc with the shadow swinging behind it. The slider spans that date's real daylight, so it stops at sunrise and sunset. **Changing the date redraws in place** — no need to re-place the anchor to compare two solstices.
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

## 11. See it in 3D (View → 3D Preview)

The 3D preview is where the design stops being a plan and starts being a place.

- **Year slider** — drag it to watch the design grow. Year 0 is the mature
  reference; drag right and you see year 1, 5, 15, 25. Plants that the closing
  canopy shades past their tolerance decline and drop out, and self-seeding
  natives fill the gaps, so a late year shows the community that actually
  survives rather than everything you ever planted.
  Since V2.44 **each plant ages from the year you planted it**, not from the
  design's year — so something you add at year 12 shows up as a young plant
  among grown ones and catches up over the following seasons. Trees go in at
  nursery size (about five years old) and shrubs at about three, because nobody
  plants those from seed; herbs and grasses start from plugs as before.
  Designs made before V2.44 carry no planting dates and render exactly as they
  always did.
- **Split view (View → Split view, or Ctrl+Shift+3)** — the 3D scene under the
  map, both showing the same design and both editable. The map answers *where*;
  the 3D answers *what it will be like*. Close it and the map takes the whole
  column back.
- **Time of year** — foliage colour, bloom, berries and snow all follow the
  month. Each species turns its own autumn colour.
- **Time of day** — drives the sun and the shadows (the same engine as the 2D
  shade map, so the two always agree). Drag past dusk for a moonlit scene with
  moths and bats instead of the day's bees and butterflies.
- **Click any plant or creature** to open its card: what it is, when it blooms
  and fruits, how big it gets at years 1 / 5 / 15 / 25, every animal documented
  to use it and how — and, when it applies, *"pull this plant and N species lose
  their only support here"*. Clicking also draws threads from the plant to each
  creature in the scene that uses it, labelled with the relationship. Click a
  bee and you get the reverse: which of your plants it visits. Esc or the ×
  closes the card.
- **Creature + Fly as a bee / Tour the year / Show its plants** — pick a native
  bee, butterfly or moth, then either fly it yourself (WASD, F to snap to the
  nearest flower), let it tour the season hands-free, or light up the plants in
  your design that feed it.
- **Walk the garden** — third-person stroll among the wildlife. **Flyover** —
  a hands-free ~60 s cinematic: the design grows, the seasons turn, night falls.
- **Identify** — labels every creature and lists who lives here.
- **Detail** — lower it if the view is sluggish on your machine.

Nothing in 3D is invented: a creature only appears if there is a documented
relationship between it and a plant you actually placed.

---

## 12. Getting the design out

- **File → Export PDF (plan + planting map)…** — the whole document: site prep, the buy list,
  and a **numbered planting map drawn to scale** with a key, a scale bar and a north arrow.
  That map page is what you take outside with a tape measure. (It needs a property boundary to
  measure from; if you have plants but no boundary the PDF says so rather than dropping the page.)
- **File → Export Planting Plan…** — the same content as text.
- **Help → Send Feedback…** — tell the author what worked, what confused you, or what broke.
  It opens a prefilled report in your browser so you can read it before posting; setup details
  are optional and shown in full first.

## 13. Save & share

- **File → Save** (Ctrl+S) writes a `.perma.geojson` file — the whole design.
- **File → Open** (Ctrl+O) loads one.
- **File → Export PDF…** produces a printable booklet with the map screenshot, plant list, and notes.
- **File → Export Plant Order List…** produces a text list grouped by Alberta nursery source (ALCLA, Bow Valley Habitat, Wild About Flowers, Bedrock Seed Bank), with native woody / native herbaceous / cultivated sections.
- The app auto-saves every 5 minutes in the background.
- **Help → Check for Updates…** — one click to the newest version. On source installs (git checkout) the app switches itself to the newest published `V*.*` branch (any local source edits are set aside safely first) and offers to restart; on packaged `.dmg`/`.exe` installs it downloads and opens the newest installer from GitHub Releases. **Help → Switch to a specific version…** does the same for any published version, forward or back.

---

## 14. Keyboard shortcuts

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

## 15. Tips that aren't obvious

- **Click a boundary's area label** to cycle units (m² → ha → acres → km²).
- On a plant's page, the twelve-month bar has a **Flowers** row and a **Fruit** row; the line under it names any months to sow or prune.
- **Mix stays armed** across pattern clicks until **Esc** — you can drop ten mixed beds in a row with one click each.
- **Fill (hex) circles** need a **Total** cap or they'll generate thousands of markers on big radii.
- The **Plants** tab's sub-tabs are **Browse** (search the catalogue), **Plant Communities**, and **On This Design**.
- **Right-click a plant in the results list** for fast actions — *Place on Map*, *Place ×5*, *About ‹plant›* (its page), *Add / Remove from Mix*.
- **“Blooms in…” / “Fruits in…”** narrow the list to plants flowering or fruiting in chosen months — the direct way to fill the nectar gap the Analysis tab names.
- To compare plants, open one's page and step through the list with the arrow keys: the page follows.

---

That's the whole interface. Have fun designing.

# PermaDesign — User Guide

A 5-minute tour of the controls. Read top-to-bottom, or jump to a section.

---

## 1. What you're looking at

When the app opens you'll see four areas:

- **Map** (centre) — Edmonton by default; pan with click-and-drag, zoom with the mouse wheel.
- **Toolbar** (top) — drawing tools, layer toggles, zoom-sensitivity combo.
- **Side panel** (right) — five tabs: **Plants**, **Polycultures**, **Structures**, **Analysis**, **Planning**.
- **Status bar** (bottom) — coordinates, hardiness zone, current mode (e.g. "Placing: Yarrow — click map").

---

## 2. Draw your property first

Click **⬡ Boundary** in the toolbar, then click on the map to add corner points. **Double-click** (or click the first point again) to close the polygon. The hardiness zone is auto-detected from the boundary and shown in the status bar.

You can edit a boundary later by clicking it: drag white vertices to reshape, drag orange corner handles to resize, drag the interior to move. Right-click for colour, label toggles, or delete. **Esc** exits edit mode.

---

## 3. Find a plant

Open the **Plants** tab.

- Type a name in **Search plants…**.
- Narrow with the filter rows: **Type / Sun / Water / Use** combos, plus toggles for **Native AB**, **Edible**, **Medicinal**, **N-Fixer**, **Pollinator**, **Perennial**.
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

## 6. Polyculture mix (multiple species in one bed)

To plant multiple species mixed together in one Row / Grid / Circle:

1. Right-click any plant in the results list → **Add to Polyculture Mix**. Add 2–8 species.
2. The **Polyculture Mix** panel shows each species with three controls:
   - A **clickable colour dot** — gives that species a unique marker colour just for this mix.
   - A **ratio spinner** (1–9) — `1:1:1` is even split; `3:1:1` gives that species 60%, others 20% each.
   - A **✕** button to remove the species.
3. Click **Place Mix on Map**, then drop a Row / Grid / Circle as usual. The recipe stays armed — click again to drop another, **Esc** to finish.

Distribution is deterministic and spread-optimised: same-species plants are automatically pushed apart so the bed reads as mixed, not blocky.

**Save / load mixes** with the **Save** button (above the species list) and the dropdown. **✕** deletes the saved mix.

---

## 7. Selection & multi-delete

- **Shift+drag** on empty map → marquee-selects every plant, boundary, sector, and sun-path inside the rectangle.
- **Shift+click** an item to toggle its membership in the selection.
- **Ctrl+Shift+drag** = additive marquee (extends instead of replaces).
- The top-right **selection badge** shows the count plus **Delete** and **Clear** links.

---

## 8. Other drawing tools

- **📏 Measure** — click two points to add a measurement; right-click any existing measurement to delete just that one. Use the View bar's Measurement toggle to hide them all without deleting.
- **📝 Note** — click to drop a draggable text note. Right-click the note to remove it.
- **Structures tab** — search a structure library, drag hedgerows (4 styles: Hedge / Fence / Living Fence / Windbreak), or draw shapes (Garden Bed, Pathway, Patio, Lawn, Mulch, Water Feature, Custom).

The View bar (🛰 Satellite, ⬡ Boundary, 📏 Measurement, **#** Grid, ✿ Plants, 🌳 Canopy, 🏗 Structures) toggles each layer's visibility without deleting anything. The Grid action's ▾ menu picks the base size (1×1, 5×5, 10×10, 100×100 m) plus opacity and colour.

---

## 9. Site analysis (Analysis tab)

- **Sun Path** — pick a date (Summer Solstice, Equinox, Today, …), click *Place Sun Path…*, click the map. Shows the sun arc + sunrise/sunset/daylight-hours summary.
- **Sectors** — toggle presets (Summer Sun, Winter Sun, NW Wind, Cold North, Frost Pocket, Noise, View, Fire Risk), click *Place Sectors…*, click the map. Drag the handles to resize / rotate / move; right-click the centre to remove.
- **Contours** — set elevation + interval, click *Draw Contour Line*, click points on the map, double-click to finish.
- **Wind** — pick direction + speed, click *Show Wind Overlay*.
- **Season View** — Summer / Spring / Fall / Winter buttons fade plant markers by deciduous/evergreen behaviour to preview seasonal density.

---

## 10. Planning helpers (Planning tab)

- **Maintenance estimator** — enter your available hrs/week, click *Calculate Maintenance* to compare the design against your time budget.
- **Harvest calendar** — month-by-month table of what's ripening, derived from each plant's calendar.
- **Water budget** — enter garden area, rain barrels, roof catchment, swales, ponds → *Calculate Water Budget* shows demand vs. supply and any deficit.
- **Succession timeline** — drag the year slider 0–20 to see how the design matures.
- **Notes / journal** — free-form text editor with **Add Timestamp** and **+ Section** buttons.

---

## 11. Save & share

- **File → Save** (Ctrl+S) writes a `.perma.geojson` file — the whole design.
- **File → Open** (Ctrl+O) loads one.
- **File → Export PDF…** produces a printable booklet with the map screenshot, plant list, and notes.
- **File → Export Shopping List…** dumps a CSV / text plant-quantity list you can take to the nursery.
- The app auto-saves every 5 minutes in the background.

---

## 12. Keyboard shortcuts

| Shortcut | Action |
|----------|--------|
| Ctrl+N / Ctrl+O / Ctrl+S | New / Open / Save project |
| Ctrl+Shift+S | Save As |
| Ctrl+Z / Ctrl+Y | Undo / Redo |
| Esc | Cancel current drawing / exit placement mode |
| Shift+drag | Marquee-select |
| Shift+click | Toggle an item in the selection |
| Right-click | Context menu (markers, boundaries, plant rows) |
| Mouse wheel | Zoom (sensitivity controlled by the toolbar combo) |

---

## 13. Tips that aren't obvious

- **Click a boundary's area label** to cycle units (m² → ha → acres → km²).
- The expanded plant calendar's colours map to life stages: **purple** = start indoors, **teal** = direct sow, **blue** = transplant, **green** = growing, **orange** = harvest, **brown** = pruning, **grey** = dormant. The current month gets a yellow ring.
- **Polyculture stays armed** across pattern clicks until **Esc** — you can drop ten mixed beds in a row with one click each.
- **Fill (hex) circles** need a **Total** cap or they'll generate thousands of markers on big radii.
- **Right-click a plant in the results list** for fast actions — *Place on Map*, *Place ×5*, *Add / Remove from Polyculture Mix*.
- The **▶ chevron** doubles as a quick way to compare plants — multiple rows can stay expanded at once.

---

That's the whole interface. Have fun designing.

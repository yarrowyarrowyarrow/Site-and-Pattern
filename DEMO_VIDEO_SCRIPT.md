# PermaDesign — Demo Video Script & Storyboard

A scene-by-scene recording plan for a ~3:30 feature demo of PermaDesign V1.
Drives a screen recording on Windows with the real app running.

---

## Production notes

- **Target length:** 3:20–3:40 (full demo). A 60-second trailer cut is at the
  end.
- **Resolution:** 1920×1080, 30 fps. Record at 60 fps if your recorder
  supports it; YouTube will downscale cleanly.
- **Recorder:** OBS Studio (free) or ShareX. Record system audio + mic on
  separate tracks so you can re-do narration without re-recording video.
- **Cursor:** Enable cursor highlight (yellow ring) in OBS — small clicks on a
  big map are otherwise invisible.
- **Click sound FX:** Add a soft click on every map click in post — viewers
  need an audio cue that something happened.
- **Pace:** Move the cursor *slowly*. It feels glacial while recording but
  reads as confident on playback.
- **Voiceover:** Record narration after the screen capture, watching the
  silent video back. Easier than syncing live.

---

## Pre-recording setup checklist

Run through this once before each take so the recording is clean:

- [ ] Fresh project: **File → New** (Ctrl+N). Empty map, Edmonton centred.
- [ ] Window maximised, not full-screen — keeps the title bar visible so
      viewers know it's a desktop app.
- [ ] Side panel on **Plants** tab, search box empty, all filters off.
- [ ] Toolbar layer toggles: **Satellite ON**, Boundary/Plants/Structures ON,
      Grid OFF, Labels ON.
- [ ] Zoom level: Edmonton city block visible (~17–18). The boundary you'll
      draw should fit comfortably in frame.
- [ ] Close any open dialogs, plant detail expansions, or notes from prior
      sessions.
- [ ] Pre-stage one saved polyculture mix called **"Three Sisters"**
      (corn / beans / squash) so Scene 7's Save/Load dropdown isn't empty.
- [ ] Optional: pre-load `data/sample_design.perma.geojson` once to verify
      it opens cleanly, then start fresh.
- [ ] Mute Windows notifications (Focus Assist → Alarms only).
- [ ] Hide desktop icons or record only the app window.

---

## Scenes

Times are cumulative end-of-scene timestamps. "ACTION" is what happens
on-screen; "VO" is voiceover. "B-roll" notes overlay text or cuts.

---

### Scene 1 — Cold open / title (0:00 → 0:08)

**ACTION:** Hold on a still frame of a finished design — a polished example
project loaded from `.perma.geojson`. Boundary drawn, plants placed in
patterns, sun path visible, zone label showing in the status bar.

**VO:** *(none — let the visual breathe)*

**B-roll overlay:**
> **PermaDesign**
> Native plant landscape design for the Canadian prairies

**Cut to black for 0.3s before Scene 2.**

---

### Scene 2 — UI overview (0:08 → 0:25)

**ACTION:** Cut to a fresh empty project. Cursor circles each region of the
UI as it's named.

1. Circle the **map** (centre).
2. Circle the **toolbar** (top).
3. Circle the **side panel tabs** on the right: Plants, Guilds,
   Structures, Analysis, Planning.
4. Circle the **status bar** at the bottom — point to coordinates and the
   hardiness zone readout.

**VO:** "PermaDesign is a desktop tool for designing landscapes with native
plants. The map is your worksite. The toolbar has your drawing tools and
layer toggles. The side panel — five tabs — is where you find plants, build
guilds, place structures, run site analysis, and plan ahead. The status bar
keeps your coordinates and hardiness zone in view."

---

### Scene 3 — Draw the property boundary (0:25 → 0:48)

**ACTION:**
1. Click **⬡ Boundary** in the toolbar.
2. Click four corners on the map to outline a rectangular property.
3. Double-click the first point to close.
4. Pause on the closed polygon — the status bar updates to show
   **Hardiness Zone 4a** (or whatever Edmonton resolves to).
5. Click the area label once to cycle units: **m² → ha → acres**.

**VO:** "Start by drawing your property. Click the boundary tool, click the
corners, and double-click to close. PermaDesign automatically looks up your
hardiness zone from the boundary's location — no settings to configure.
Click the area label to flip between square metres, hectares, and acres."

**B-roll overlay (lower third):** *Hardiness zone auto-detected from
Natural Resources Canada polygons*

---

### Scene 4 — Find a plant (0:48 → 1:10)

**ACTION:**
1. Click the **Plants** tab.
2. Type "saskatoon" into the **Search plants…** box. Pause as the list
   filters live.
3. Clear the search. Toggle **Native AB** ON, then **Edible** ON,
   then **Pollinator** ON.
4. The list shrinks to native + edible + pollinator-friendly species.
5. Click the **▶ chevron** on **Saskatoon Berry**. The row expands inline
   to show sun, water, spacing, height, bloom and fruit windows, edible
   parts, and the **12-month colour-coded planting calendar**.
6. Hover the cursor over the calendar — point out one orange harvest
   block.

**VO:** "The plant database ships with 433 species suited to Alberta and
the prairies. Search by name, or stack filters — Native, Edible, N-fixer,
Pollinator, Perennial — to narrow the field. Open any row for the full
data block, including a colour-coded planting calendar that shows when to
sow, transplant, harvest, and prune, month by month."

---

### Scene 5 — Place a single plant (1:10 → 1:25)

**ACTION:**
1. With Saskatoon Berry's row still selected, scroll down to the
   **Placement Mode** strip and confirm **Single** is active.
2. Click the **●** colour swatch — pick a deep red.
3. Click **Place on Map**.
4. Click once on the map inside the boundary to drop a marker.
5. Press **Esc** to exit placement mode.

**VO:** "Click a plant to select it, choose a marker colour, click Place on
Map — and drop it. Escape exits placement mode."

---

### Scene 6 — Pattern placement: Row, Grid, Circle (1:25 → 1:55)

**ACTION:**
1. Select **Yarrow** in the plant list (search "yarrow").
2. Switch placement mode to **Row**, click **Place on Map**, click two
   points along one edge of the boundary. A row of evenly-spaced markers
   appears.
3. Switch to **Grid**, set **Stagger** ON, click two opposite corners of
   a small bed — a hex-staggered grid fills the rectangle.
4. Switch to **Circle**, toggle **Fill (hex)** ON, set **Total** to 30,
   click a centre point and a radius point — a honeycomb-filled circle
   appears.
5. Slow zoom-in on the staggered grid so viewers can see the pattern.

**VO:** "For repeating plantings, switch the placement mode. Row takes a
start and an end point. Grid takes two corners — toggle stagger for a
honeycomb pack. Circle takes a centre and a radius. Fill mode lets you cap
the total count, so a big circle doesn't spawn thousands of markers."

---

### Scene 7 — Polyculture mix (1:55 → 2:20)

**ACTION:**
1. Search "corn". **Right-click** the Corn row → **Add to Polyculture
   Mix**.
2. Search "bean", right-click → Add to mix. Same for "squash".
3. The **Polyculture Mix** panel now shows three species. Click each
   coloured dot in turn and pick a contrasting marker colour for each.
4. Set ratios to **3 : 2 : 1** using the spinners.
5. Click the **Save** button, name it **"Three Sisters"**.
6. Click **Place Mix on Map**, then drop a Grid into a free corner of the
   boundary. Notice the markers interleave by colour — same-species are
   pushed apart so the bed reads as mixed.
7. Press **Esc**.

**VO:** "For a real polyculture — multiple species in one bed — right-click
plants to add them to a mix. Each species gets a unique marker colour and a
ratio. Save the mix as a recipe you can drop again later. PermaDesign
spreads the species deterministically so the planting reads as mixed, not
blocky."

**B-roll overlay:** *Distribution is spread-optimised — same-species
markers are pushed apart automatically.*

---

### Scene 8 — Structures & hedgerows (2:20 → 2:35)

**ACTION:**
1. Click the **Structures** tab.
2. Drag a **Windbreak** hedgerow along the north edge of the boundary.
3. Draw a **Pathway** shape down the middle of the property.
4. Draw a small **Garden Bed** rectangle near the house position.

**VO:** "The Structures tab covers everything that isn't a plant —
windbreaks, fences, paths, garden beds, ponds. Drag the line, draw the
shape."

---

### Scene 9 — Site analysis (2:35 → 3:05)

**ACTION:**
1. Click the **Analysis** tab.
2. Under **Sun Path**, pick **Summer Solstice**, click *Place Sun Path…*,
   click the centre of the property. The sun arc appears with a
   sunrise / sunset / daylight-hours summary.
3. Under **Sectors**, toggle **NW Wind** and **Winter Sun** presets,
   click *Place Sectors…*, click the property centre. Two coloured pie
   slices appear; drag a handle to rotate one.
4. Under **Wind**, set direction **NW**, speed **30 km/h**, click *Show
   Wind Overlay*.
5. Click the **Season View → Winter** button. Watch deciduous markers fade
   while evergreens stay solid.

**VO:** "Site analysis is what makes a design site-aware. Drop a sun path
for any date and read the daylight hours. Add wind, sun, view, fire-risk,
or noise sectors and rotate them to your real conditions. The season
toggles fade plants by deciduous or evergreen behaviour, so you can
preview what the garden looks like in February."

---

### Scene 10 — Planning helpers (3:05 → 3:25)

**ACTION:**
1. Click the **Planning** tab.
2. **Maintenance estimator** — enter **5** hrs/week, click *Calculate
   Maintenance*. Result table shows demand vs. budget.
3. Scroll to **Harvest calendar** — month-by-month table of what's
   ripening this design.
4. **Water budget** — enter garden area, one rain barrel, a roof
   catchment area, click *Calculate Water Budget*. Result shows demand
   vs. supply.
5. **Succession timeline** — drag the year slider from **0** to **15**.
   Marker sizes grow as plants mature.

**VO:** "Planning tools turn a layout into a workable plan. Estimate
weekly maintenance hours. See a harvest calendar built from every plant in
the design. Run a water budget against your rain barrels and catchment.
And drag the succession slider to watch the design mature, year by year,
out to twenty."

---

### Scene 11 — Save & export (3:25 → 3:35)

**ACTION:**
1. **Ctrl+S** — save dialog appears. Type "north-yard.perma.geojson",
   save.
2. **File → Export PDF…** — quick cut to the resulting PDF opening in a
   reader: cover page with the map screenshot, plant list table, notes.
3. **File → Export Shopping List…** — quick cut to the CSV opening in a
   spreadsheet, with plant names and quantities.

**VO:** "Your work saves to a single GeoJSON file. Export a printable PDF
booklet with the map, plant list, and notes — or a CSV shopping list to
take to the nursery."

---

### Scene 12 — Outro (3:35 → 3:45)

**ACTION:** Cut back to the polished hero design from Scene 1. Hold.

**B-roll overlay:**
> **PermaDesign V1**
> Free for personal and non-profit use
> github.com/yarrowyarrowyarrow/PermaDesign
>
> *Successor project: Site & Pattern — coming soon*

**VO:** "PermaDesign V1 is free for personal and non-profit use, and the
final release in this line. The successor project, Site & Pattern, is in
the works — cross-platform, with deeper plant data and integrated
environmental layers. Link in the description."

**Fade to black.**

---

## 60-second trailer cut

If you want a short version for social media, keep these scenes only and
re-narrate over a single tighter VO:

| Time      | Source scene                              |
|-----------|-------------------------------------------|
| 0:00–0:05 | Scene 1 — title hold                      |
| 0:05–0:15 | Scene 3 — boundary draw + zone detect     |
| 0:15–0:25 | Scene 4 — search + filter + plant calendar|
| 0:25–0:38 | Scene 6 — pattern placement (Grid + Circle)|
| 0:38–0:48 | Scene 7 — polyculture mix drop            |
| 0:48–0:55 | Scene 9 — sun path + season toggle        |
| 0:55–1:00 | Scene 12 — outro card                     |

**Trailer VO (full):**
> "PermaDesign — a desktop tool for designing landscapes with native plants
> on the Canadian prairies. Draw your property; the hardiness zone is
> auto-detected. Search 433 native and naturalized species, with a
> month-by-month planting calendar for each. Drop plants in rows, grids,
> circles — or as a true polyculture mix. Run sun path, wind, and sector
> analysis on your real site. Free for personal use. Link below."

---

## Post-production checklist

- [ ] Background music: low-volume acoustic / ambient. Drop volume by
      another 6 dB under voiceover.
- [ ] Lower-third overlays at Scenes 3, 7, 12 (text suggested above).
- [ ] Add 0.3s cross-dissolves between scenes; hard cuts inside scenes.
- [ ] Captions/subtitles burned in or as a sidecar `.srt`.
- [ ] Export 1080p H.264, ~10 Mbps for YouTube; a separate vertical 1080×1920
      crop for the trailer if posting to Instagram / TikTok.
- [ ] Thumbnail: a still from Scene 1 with the title text overlaid.

---

## What's deliberately not in the demo

Skipped to keep the runtime tight; mention in the description if relevant:

- Permapeople API enrichment (requires credentials; not visible in default
  install).
- Undo/redo, marquee selection, keyboard shortcuts — covered in
  `USER_GUIDE.md §12`.
- Zone Circles, Measure tool, Notes — minor utilities; mention only if you
  need to fill time.
- Contour drawing — included in the Analysis tab but visually subtle;
  better suited to a follow-up "advanced features" video.

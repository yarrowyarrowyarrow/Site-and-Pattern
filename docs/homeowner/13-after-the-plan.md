# 13 · After the plan: where it stands, what to test, where next

*Written at the end of V3.32, when the fifteen increments of
[11-work-plan.md](11-work-plan.md) had all shipped their code. It draws on the
fifteen plan files (V3.18 to V3.32), a survey of every open item in
[`BACKLOG.md`](../BACKLOG.md) and [`ROADMAP_NEXT.md`](../ROADMAP_NEXT.md), and a
walk through the simple app's screens at 1366 × 768 with the worked example
(`scripts/surface_inventory.py --mode simple --click --dialogs`). Claims below
were checked against the code or GitHub; anything inferred says so.*

## 1. Where it stands

The code side of the plan is done. Against the definition of finished
([10 §1](10-finishing.md)):

| # | Item | State |
|---|---|---|
| 1 | Strangers complete the path | **Not yet**: the five sessions have not run (the notes page and a pre-flight test are ready) |
| 2 | No known High defect | Met, as far as anything is known before the sessions |
| 3 | Installing does not look like malware | Partly: unsigned by your choice (D2, D3), with the steps in the README and release notes |
| 4 | Licence and notices | Met |
| 5 | Services within their terms, credited | Partly: all credited; Esri's terms (D4) still unread |
| 6 | Users get only releases you chose | The mechanism works. **Nothing has been promoted since V3.17**, so every installed copy is 15 versions behind |
| 7 | Feedback without an account | Waits on the mailbox you are setting up |
| 8 | A one-page guide | Met |
| 9 | Runbook, and someone else can cut a release | Partly: `docs/MAINTENANCE.md` exists; no second maintainer yet |
| 10 | The freezes hold | Met |

**The single most useful thing to do next is item 6**: install the V3.32
prerelease, use it for an evening, and promote it if it holds. Until then
nobody's copy has any of this work, including V3.18's trust fixes and the
licence change.

## 2. What went well

- **The homeowner path is one path now.** Start screen → address → bed →
  *Plan my yard* → Overview → print, in plain words, with the advanced tools
  out of sight. The pre-flight test walks all seven session tasks through the
  real window, and every one has a way through.
- **One answer for each question.** The habitat score, the wildlife count, the
  hours, the planting area, the frost dates, the nursery list and what "native"
  means each come from one function, and tests hold the pages to it.
- **Edmonton is a pack, not a hard-coded city.** A test stops a place's name
  creeping back into code.
- **Honest about uncertainty.** "Typical for the Edmonton region" where a figure
  is not the yard's own; no line where the app does not know; nothing on
  spreading where the record is blank.

## 3. Weak spots

- **Everything visual was checked offscreen**, in fonts that are not Windows'.
  CI caught two layouts the sessions' font hid (V3.27, V3.30). No one has used
  the simple app on a real Windows laptop since the plan began.
- **Numbers resting on judgment.** The 70% and 40% cover targets, the cover
  estimate (0.7 m² a plant), and "Fill it now" on a 150 m² yard proposing about
  267 plants ($2,300–$4,900) are all judgment calls nobody outside has checked.
- **The data under the words is thin** (counted): `spread_habit` is recorded on
  16 of 424 plants, pet toxicity on 48, human toxicity on 33; 158 Edmonton natives
  are on no nursery list. The app says "not recorded" honestly, but the
  homeowner sees many blanks.
- **Docs behind the code** (small): F234 and F237 rows are still open though
  their items shipped; P13's State text predates F75/F76.

## 4. Your decisions not yet carried out

Checked in the code:

- **W4**: you chose *Feeds a specialist* advanced only. It ships in the simple
  app as "Food for a fussy eater", behind *More filters*.
- **E9**: rename the seven "Edmonton …" communities by habitat. Not done
  (`src/db/polycultures.py`).
- **S3**: fold the Lessons' "your design" lines into the Report card. Not found.
- **M2**: one door from the Overview to the 3D preview. Not found.
- **L3**: "too big" against the yard's measured front and back. Only the
  Overview uses those measures; the plant list does not.
- **O4** (the familiar animals list, F249) and **L5** (the spread review, F246):
  the mechanisms wait for their data.

## 5. Rough edges in the simple app (found in V3.32's screen walk)

Most important first. Each is small.

1. **"⬡ Boundary" is on the toolbar** in the simple app, and drawing says
   "Drawing boundary…". The glossary says *yard outline*. (Only the View row's
   layer switch is registered as advanced.)
2. **The plant list opens with three filters nobody chose**: "Restoring toward
   Aspen Parkland" (an ecoregion name), "Native around Edmonton", "Your soil:
   pH 6.5", cutting 424 plants to 247. A water plant (Creeping Spikerush) is
   fourth in a front-yard list; scientific names are cut mid-word; "[1×]" does
   not say it means "already in your design".
3. **Site › Notes points to a button the simple app hides** ("use Draw → 📝 Note").
4. **Words the glossary keeps out still show**: "Species" (a sub-tab and "14
   species" beside the Overview's "14 kinds"), "Mesic" on community rows,
   "property pin", "cached with the project", "ecoregion" in tooltips. The
   vocabulary test does not read the toolbar or tooltips.
5. **The printout has three names**: "Print the shopping list and care plan"
   (Overview), "Export PDF…" (Share), "Export PDF (plan + planting map)…" (File).
   The glossary says *Print the plan*.
6. **Communities is dense for a homeowner**: five dropdowns, a sort, grouping,
   and no line saying what a community is (09 §3.4).
7. **Plan My Yard**: "about 90 m²" where the map and Overview say 88; a
   where-question with one radio button; on a design with plants, it is only in
   the File menu (the strip is gone).
8. **Small things**: the scale bar sits over an edge label and the map credit;
   "Mode: Site data ready" in warning orange; Share has a strip with one tab;
   Notes is 2.4 screens of controls even in the simple app; *Where to buy*
   underlines two of five nurseries; "Find an October flower" is an odd ask for
   Edmonton.
9. **The surface probe photographs the Overview blank** (it renders fine when
   drawn on its own), so the audit's counts miss the simple app's main page.

## 6. Open beyond the plan

**Improves the homeowner's path** (code): the Overview's "Show the bare ground"
(V3.27), the sun-fit sentence (OV-14), F160 (swap Canada Goldenrod so six
withheld communities return), F49 (an ornamental → native swap card for
big-box plants), F73 (a dated photo of a plant in your own yard), F202 (a
placed community drawn as one thing), F169 (keep juniper away from saskatoon;
your call), F230 (per-user Windows install; your call).

**Data that makes the advice trustworthy**: F246 spread, F248 toxicity for the
top 60, F247 photos for the top 60, F249 familiar animals, F227 nursery stock,
F172 wrong flower colours, F190 animal ranges, F171 the real Green Milkweed.

**Principles still partial**: P13 (beauty) is the only State marked partial:
colour as an analysis ("your June is all yellow") and F247. Smaller gaps under
P1 (F23 inspectable rules), P8 (F18 remediation), P9 (F29 timeline ranges).

**Frozen or declined, not proposed**: the 3D preview and website (fixes only),
donations, signing, a bylaw block, a score on the Overview, other regions
(Calgary, Regina) for now, the AI in the app, anything P12 forbids.

## 7. Where next: suggestions

In order. Each is a V-branch.

1. **Promote a release** (yours, an evening). Install V3.32, try the five
   things in the runbook, promote it. Everything else reaches people only after.
2. **V3.33 · The screen walk's fixes** (code, no new decisions): §5 items 1–8,
   plus W4, E9 and the vocabulary test reading tooltips and the toolbar. This is
   what a stranger would trip on in the first ten minutes.
3. **Run two sessions before the other three** (yours and the friend's). Two
   people find most of what five would; fix what they hit, then run three more.
4. **V3.34 · Trustworthy plant facts** (data, your review): build the spread
   review tool (F246, about two hours of your answers), draft the familiar
   animals list (F249) for you to correct, and fill toxicity for the top 60
   (F248) from cited sources.
5. **V3.35 · Photos that sell the plants** (P13): photos for the 12 top picks
   without one, beauty-first hero photos for the top 40 (F247), and the
   bee-photo licence decision.
6. **V3.36 · The Overview's last two answers**: "Show the bare ground" and the
   sun-fit sentence (OV-14), plus the 3D door (M2) and the Lessons' lines (S3).
7. **The Esri question (D4)**: read the terms on a machine that can open
   arcgis.com, or make the street map the only default.
8. **Hand over** (FN-14): add the friend as a collaborator, have them cut one
   release by the runbook, then set the README's status to finished.

Questions only you can answer, which would change this order: is the Overview
or the plant list where you expect homeowners to spend most time; is the
feedback mailbox close; and would you rather the sessions come before or after
the screen walk's fixes?

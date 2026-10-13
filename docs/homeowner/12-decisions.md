# 12 · The owner's decisions, in one place

*Part of the [homeowner-path plan](README.md). Every choice the plan leaves to
the owner, with the recommended answer and the increment that needs it
([11-work-plan.md](11-work-plan.md)). 68 in all.*

## How to answer

**The answers are recorded on a page made from this file:**
<https://claude.ai/artifact/FE63BscPKbgrMHpciwVHSp> (private to the owner). Each
choice saves as it is made. A session reads them with the `ArtifactData` tool,
`list` on the collection `decisions`: one document per decision, its id the
decision's ID in lower case (`d1`, `s12`), holding `choice` (the option's letter,
or `other`), `label` (the option's words), `recommended`, `note` and `at`. **Read
them before starting an increment**, and copy the ones it needs into its plan
file. This table stays the reasoning; the page holds the answers.

- **Fill in the Answer column** in this file (a word is enough: *yes*, *rec*,
  *b*, *no*), or answer in batches in a session; whoever picks up the work
  copies the answer here and into the increment's plan file.
- **"Go with the recommendations"** is a valid answer for any group. Every
  recommendation was chosen so that taking it leaves the app coherent.
- Answer by **when it is needed** (the *By* column is the increment number).
  Increment 1 needs four answers; most others need two to six.
- Where a recommendation **reverses an earlier choice of the owner's**, it says
  so (§4); those are worth reading even when taking the recommendation.

The letters, so they cannot be confused with anything else: **S** start screen
(04), **L** plants that lead (05; renamed from P to keep clear of the design
principles P1–P13), **M** two ways (02), **G** what goes (03), **O** overview
(06), **Y** Plan My Yard (07), **E** Edmonton edition (08), **W** words (09),
**D** finishing (10), **K** work plan (11).

---

## 0. The answers (13 October 2026)

All 68 answered on the decisions page. **55 took the recommendation; 13 did
not**, and these change the plan as follows. The parts carry a note at the top
saying the same, and the work plan's increments already include it.

| ID | The answer | What changes |
|---|---|---|
| **S1** | Keep the Learn door and its menu, with the Lessons fix | ST-10 cancelled; ST-1 fixes the door; the "Your designs" screen keeps one *Learn* row (04). G1's "accept all" covers the other deletions only |
| **S2** | Field Study stays *within Learn* | It stays in the Learn tab (behind Advanced in the main window, G2) and in the Learn door's window |
| **S4** | Retire the Plant Directory window | New RM-10 (03), release 5. `plant_directory.py` stays: the plant page and the website read it |
| **L1** | Impact only, feasibility as words | PR-1 orders by Impact; feasibility becomes the reasons and cautions on the row, not points (05) |
| **L3** | "Boundary minus building outline. Automatic measurements for front and back" | No assumed yard size: new PY-12 measures the front and back yards from the outline less the house (07), release 10; the plant list's *fits* words use it |
| **L5** | Review the spreaders; show nothing for unchecked ones meanwhile | No "not yet checked" line; the filter and the Plan My Yard must-have read *leave out known spreaders* (05, 07, 09) |
| **E5** | Count "native" in the score by the Edmonton list | New ED-17 (08), release 8: a deliberate headline change to the habitat score in the Edmonton region |
| **E6** | Leave the rules block out | ED-14 cancelled; no `rules` in the region manifest |
| **O5** | Drop the bylaw sentence | The overview's street item names no rule; OV-13 keeps only the place name and price note |
| **G5** | "I do not want a website at this time. Donations are not necessary at this stage" | No website work (ED-12 deferred), the guide goes in the README and release notes (FN-11), no donate link (FN-10 cancelled), privacy note in About only |
| **D6** | No donation platform yet | As G5 |
| **D2** | Windows unsigned, with instructions | FN-3 becomes the SmartScreen steps in the README and release notes; SignPath stays possible later under GPL-3.0 |
| **K1** | "Automatic but able to change between the 2" | QF-18: View › Scale Units becomes *Automatic* (default), *Kilometres*, *Metres* |

**Two follow-ups this raised**, recorded in the parts rather than numbered as
new decisions:

1. *"I do not want a website at this time"* is read as **no website work in this
   plan**. Nothing is to be done to the published grownativeplants.ca site on
   this reading; whether to take it down is a separate question for the owner.
2. **Send Feedback** cannot point at the website's form (G5). 10 §7 now
   recommends a copyable address and the GitHub link; the address is the
   owner's to choose.

## 1. The ten that matter most

| # | ID | The question | Recommended | By |
|---|---|---|---|---|
| 1 | **D1** | The licence: PolyForm Noncommercial conflicts with PyQt6's GPL. Relicense as GPL-3.0, port to PySide6, or buy a PyQt licence? | **GPL-3.0** | 1 |
| 2 | **G1** | Delete the version picker, Import Yard Scan, the Learn door and the dead recipes module; take the AI out of the app? | **Yes** | 1, 5 |
| 3 | **M1** | Simple by default, with one remembered View → Advanced tools switch? | **Yes** | 4 |
| 4 | **S12** | Which start screen: A (tidy), B ("Your designs"), C (address box)? | **B** | 6 |
| 5 | **E1** | Is "Edmonton" the V3.12 50 km circle? | **Yes** | 7 |
| 6 | **L1** | Rank plants by Impact and Feasibility as 05 proposes? | **Yes** | 9 |
| 7 | **O1** | Should the overview show the 0–100 score? | **No number**; the score stays in Advanced | 10 |
| 8 | **Y2** | How a plan's look is chosen: front or back yard, named styles, or neither? | **Front or back yard** | 12 |
| 9 | **D2 / D3** | Sign the installers: SignPath (free with GPL) or Azure for Windows; notarize for Mac or not? | **SignPath; decide Mac by how many Mac users there are** | 14 |
| 10 | **D7** | Accept 10 §1 as the definition of finished? | **Yes** | 15 |

## 2. Everything, by part

### 2.1 Start screen (S, part 04)

| ID | Question | Options | Recommended | By | Answer |
|---|---|---|---|---|---|
| S1 | The Learn door on the start screen | Remove it (every window stays reachable from View or the Learn tab); keep one quiet link to Walk a Wild Landscape; keep the door with the Lessons fix | **Remove it** (ST-10) | 5 | **Keep the door and its menu, with the Lessons fix** |
| S2 | Field Study, the photo quiz: you said *Keep, and improve* in V3.05, and now say the app is not an ID reference | Retire it; behind Advanced; keep for everyone | **Behind Advanced** (consistent with V3.05 and G2); retire it if you read it as ID training | 5 | **Other:** Within learn |
| S3 | The four Lessons (keystones, food web, succession, ranges) | Keep in the Learn tab under Advanced and fold their "your design" lines into the Report card; keep as is; retire | **Advanced, and fold the "your design" lines into the Report card** | 5 | **Recommended** |
| S4 | The Plant Directory window | Advanced only (View menu); retire it (the same picker is Placement › Plants) | **Advanced only** | 5 | **Retire it; the same picker is Placement › Plants** |
| S5 | Walk a Wild Landscape | Advanced only; visible to everyone from the View menu | **Advanced only** (see G6) | 5 | **Recommended** |
| S6 | The tagline | "Native plant yards for Edmonton"; keep "Native Habitat Designer" | **"Native plant yards for Edmonton"** | 6 | **Recommended** |
| S7 | Closing the start screen at launch (X or Esc) | Quit the app; open a blank map as today | **Quit** (from Help → Start Screen it only closes the screen) | 6 | **Recommended** |
| S8 | "Skip this screen" | Keep it as *Next time, open my last design directly*; drop it | **Keep, reworded** | 6 | **Recommended** |
| S9 | Naming a design | From its address, asking once at first save if there is none; ask whenever a yard is started | **From the address** (ST-5) | 6 | **Recommended** |
| S10 | Where the donate link appears | Help and About only; also a quiet link on the start screen once a design is saved | **Help and About only** (and the website, D6) | 14 | **Recommended** |
| S11 | Checking for updates | Manual, in Help; quietly at launch (a GitHub call each launch, to be named in the privacy note) | **Manual** | 14 | **Recommended** |
| S12 | Which start screen | A: tidy the doors (a day); B: "Your designs" (3–4 days); C: an address box (a week or more) | **B** | 6 | **Recommended** |
| S13 | Work from a crash when the person picks another row | Keep it automatically as "<name> (unsaved changes from <date>)"; insist on restore or discard first | **Keep it automatically** (ST-8) | 6 | **Recommended** |

### 2.2 Plants that lead (L, part 05)

| ID | Question | Options | Recommended | By | Answer |
|---|---|---|---|---|---|
| L1 | The two-part ranking and its weights (caterpillars 0–4 with a keystone floor, bees 0–3, birds 0–2, specialist 1, season 1; feasibility as 05 §4.2) | Accept; something simpler (Impact only, Feasibility as words) | **Accept** | 9 | **Something simpler: Impact only, Feasibility as words** |
| L2 | The nine keystone genera | Keep as they are; add genera NWF lists for neighbouring ecoregions (*Amelanchier*, *Rosa*, *Vaccinium*, *Rubus*, *Cornus*, *Picea*), which also moves habitat scores | **Keep as they are** (adding moves a headline) | 9 | **Recommended** |
| L3 | The yard size assumed before an outline is drawn | A 100 m² bed and a 180 m² back yard; other numbers | **100 m² and 180 m²** | 9 | **Other:** Boundary minus building outline. Automatic measurements for front and back |
| L4 | Chokecherry leads the list (most wildlife on record; suckers, black knot, poisonous to pets) | Let it lead with its cautions shown; cap any known spreader at Good pick | **Let it lead, with "Spreads by suckers" and "Poisonous to pets if eaten" shown** | 9 | **Recommended** |
| L5 | The 26 candidate spreaders (R11) | Confirm, correct or reject each (F246); and show blank spread as "Not yet checked for spreading" until reviewed | **Review them; show "Not yet checked" meanwhile** | 9 | **Review them; show nothing for blanks meanwhile** |
| L6 | Moist-site plants (Joe-Pye Weed, Pussy Willow, Marsh Aster…) as Top picks for an unknown yard; specimen-label caterpillar records | Top picks with "Wants moist soil"; capped at Good pick until moisture is known. Specimen-label records in full or at half | **Top picks with the caution; records in full** | 9 | **Recommended** |
| L7 | The plant page's *What it looks like* and *Where these numbers came from* | Remove from the desktop page; keep in Advanced | **Keep in Advanced** | 9 | **Recommended** |
| L8 | Free-text Notes on the desktop plant page | Advanced only; not shown at all | **Not shown at all.** Some notes record plant-use traditions ("Traditional cold/flu remedy"), and the website already withholds notes under **P12**; the desktop should match | 9 | **Recommended** |
| L9 | A buying caution for big-box Highbush Cranberry (often the European variety); is "Green Milkweed" the right common name for *Asclepias ovalifolia*? | Yes / no to each | **Add the caution; check the name before QF-4 uses it** (`scripts/rename_common_name.py` if it changes) | 9 (L9's name before 1) | **Recommended** |
| L10 | The Edmonton list on by default (R30) | On; off, relying on the ranking's place term | **On** (ED-10) | 9 | **Recommended** |

### 2.3 Two ways to use it (M, part 02)

| ID | Question | Options | Recommended | By | Answer |
|---|---|---|---|---|---|
| M1 | How the two ways work | Simple by default with one remembered switch; ask on first run; offer it on the start screen | **One remembered switch, off by default** | 4 | **Recommended** |
| M2 | The 3D preview | Advanced, with one plain door from the overview; simple for everyone; advanced only | **Advanced, with one door from the overview** | 10 | **Recommended** |
| M3 | The switch's name | *Advanced tools*; *More tools*; *Expert mode* | **Advanced tools** | 4 | **Recommended** |
| M4 | Whether the Learn tab survives | See G2, S2, S3 | **Behind Advanced** | 5 | **Recommended** |

### 2.4 What goes (G, part 03)

| ID | Question | Options | Recommended | By | Answer |
|---|---|---|---|---|---|
| G1 | The four deletions (version picker, Import Yard Scan, the Learn door, `recipes.py`) and the AI leaving the app | Accept; accept some | **Accept all** | 1 (RM-1), 5 | **Recommended** |
| G2 | The Learn tab (Field Study, Lessons) | Behind Advanced; retire (about 1,200 lines, 7 test modules) | **Behind Advanced** | 5 | **Recommended** |
| G3 | Split view | Behind Advanced; delete (the 3D window follows the design since V3.08) | **Behind Advanced** | 5 | **Recommended** |
| G4 | Freeze the 3D preview: no new features; short of a crash or a wrong plant, *won't fix* | Yes; no | **Yes** | 4 | **Recommended** |
| G5 | Freeze the website at its current build, rebuilt only when the catalogue changes | Yes; no | **Yes** | 14 | **Other:** I do not want a website at this time. Donations are not neccesary at this stage |
| G6 | Anything in 03 §5 wanted in the simple app after all (most likely Measure, or Walk a Wild Landscape) | Name them | **None to start; revisit after the sessions (FN-9)** | 4 | **Recommended** |

### 2.5 How your yard is doing (O, part 06)

| ID | Question | Options | Recommended | By | Answer |
|---|---|---|---|---|---|
| O1 | The 0–100 score on the overview | No number; "Plant choice: N/100" beside the cover line; a coverage term in the score itself (a headline change: the example 63 → about 32) | **No number** | 10 | **Recommended** |
| O2 | Which score the Report card, PDF and critic show | The one rebased on the reference community (Habitat's, since V2.65); the universal one | **The rebased one** | 3 | **Recommended** |
| O3 | The cover target, and mulch as an equal choice to planting the gaps | 70% "well filled", mulch offered equally; other | **70%, mulch offered equally** | 10 | **Recommended** |
| O4 | Wildlife wording | Group counts "recorded as food for…" with the fixed caveat; named animals only. Plus a list of about 30 familiar Edmonton animals (F249) | **Counts with the caveat; make the list** | 10 | **Recommended** |
| O5 | The bylaw sentence on the overview | Read Bylaw 14600 and approve 06 §5.3's sentence; change it; drop it | **Read it, then approve or change**; never say a bed is exempt | 10 | **Drop the sentence** |
| O6 | The care calendar's four bands as the only hours anywhere, retiring "Year 3+" | Yes; no | **Yes** | 3 | **Recommended** |
| O7 | The order of the six items | Wildlife, flowers, right plants, how full, from the street, what it will take; or lead with cost and work | **The first order** | 10 | **Recommended** |

### 2.6 Plan My Yard (Y, part 07)

| ID | Question | Options | Recommended | By | Answer |
|---|---|---|---|---|---|
| Y1 | The local AI | Out of the app, kept in the command line and MCP; kept as an advanced option | **Out of the app** | 5 | **Recommended** |
| Y2 | How a plan's look is chosen | Front or back yard; named styles (*Tidy garden*, *Meadow*, *Woodland edge*); no choice | **Front or back yard** | 12 | **Recommended** |
| Y3 | *How full* | Two choices by cover (70% now; 40% over two or three summers); the three densities | **Two choices by cover** | 11 | **Recommended** |
| Y4 | A second plan | Replaces the first by default; ask every time; adds | **Replaces by default** (undo brings it back) | 1 | **Recommended** |
| Y5 | Structures in a back-yard plan | At most two (a brush pile, a bee hotel); never unless asked | **At most two** | 12 | **Recommended** |
| Y6 | The poison boxes | Offer as *leave out plants known to be poisonous*; hide until the top 60 have records (F248) | **Offer, worded as known-poisonous** | 11 | **Recommended** |

### 2.7 The Edmonton edition (E, part 08)

| ID | Question | Options | Recommended | By | Answer |
|---|---|---|---|---|---|
| E1 | The Edmonton area | The V3.12 50 km circle; a larger circle; a list of municipalities | **The 50 km circle** | 7 | **Recommended** |
| E2 | A pin in Alberta or Saskatchewan outside the area | Plan with province natives and a warning; refuse | **Plan, with the warning** | 8 | **Recommended** |
| E3 | A pin outside the two provinces | Disable Plan My Yard; allow it with a warning | **Disable it** | 8 | **Recommended** |
| E4 | Installers | One installer with every pack, the pin choosing; one per city | **One installer** | 7 | **Recommended** |
| E5 | Count "native" in the simple score and words by the Edmonton list rather than the province (moves the habitat score's native term) | Yes; not now | **Not now**; the overview's "Right plants for here" already speaks in Edmonton terms | 8 | **Yes** |
| E6 | The rules block (bylaw, weeds, call before you dig, neighbouring towns) | Include, re-checked every 24 months by a test; include without the towns; leave out | **Include, with the 24-month check** | 13 | **Leave it out** |
| E7 | Edmonton's frost dates and hardiness zone | Which station and which map edition to print (May 15 / Sep 16 from City Centre is reported; the zone is 3b or 4a by source) | **City Centre's dates; NRCan's current zone, after checking both** | 8 | **Recommended** |
| E8 | Calgary and Regina reviews | Who answers; the same "yes or no, no reasons" rule | **The same rule; a local reviewer** | after finishing | **Recommended** |
| E9 | "Edmonton" in seven community names | Keep; rename by habitat so a Calgary pack can share them | **Rename by habitat** | 7 | **Recommended** |

### 2.8 The words (W, part 09)

| ID | Question | Options | Recommended | By | Answer |
|---|---|---|---|---|---|
| W1 | The glossary (09 §2) as the contract for the simple app: *yard outline*, *bed*, *plant*, *community* (never *polyculture*) | Accept; amend | **Accept** | 4 | **Recommended** |
| W2 | *Plan* for what Plan My Yard makes and what is printed, *design* for the file | Yes; no | **Yes** | 11 | **Recommended** |
| W3 | The ID line ("These photos help you choose plants…") | The plant page's *More* section and About; every plant page; nowhere | **More and About** | 9 | **Recommended** |
| W4 | *Feeds a specialist* | Reword (*Food for a fussy eater*); Advanced only | **Advanced only** | 9 | **Recommended** |
| W5 | Site Info as four lines with Details below | Yes; keep today's page for everyone | **Yes** | 13 | **Recommended** |

### 2.9 Finishing (D, part 10)

| ID | Question | Options | Recommended | By | Answer |
|---|---|---|---|---|---|
| D1 | The licence | GPL-3.0; a PySide6 port keeping PolyForm Noncommercial; a PyQt commercial licence | **GPL-3.0** | 1 | **Recommended** |
| D2 | Windows signing | SignPath (free; needs GPL; SignPath named as publisher); Azure Artifact Signing (US$9.99 a month; the owner named); unsigned with instructions | **SignPath** | 14 | **Unsigned, with instructions** |
| D3 | macOS | Notarize (US$99 a year); unsigned with instructions; stop building for Mac | **Unsigned with instructions, unless Mac users turn up** | 14 | **Recommended** |
| D4 | Satellite imagery | Read Esri's terms and keep it if they allow; move to an Esri key; street map only by default | **Read the terms first** | 14 | **Recommended** |
| D5 | A stable channel | Prereleases by default with a promote step; release every push | **Prereleases and a promote step** | 1 | **Recommended** |
| D6 | The donation platform and words | Ko-fi, Buy Me a Coffee, GitHub Sponsors, Liberapay; the words in 10 §6 | **Owner's preference**; the words as drafted | 14 | **Other:** Nothing yet |
| D7 | The definition of finished (10 §1) | Accept; amend | **Accept** | 15 | **Recommended** |

### 2.10 The work plan (K, part 11)

| ID | Question | Options | Recommended | By | Answer |
|---|---|---|---|---|---|
| K1 | The scale bar's units (R18): V3.06 made kilometres the default on your choice | Automatic (metres below 1 km); keep kilometres | **Automatic** | 2 | **Other:** Automatic but able to change between the 2 |

## 3. Decisions that touch each other

- **The Learn side:** S1 (the door), S2 (Field Study), S3 (Lessons), G2 (the
  tab), M4 (whether it survives) are one question in five places. Answer G2 and
  the rest follow.
- **The 3D preview:** M2 (where its door is) and G4 (the freeze).
- **Donations:** S10 (where in the app) and D6 (platform and words, and the
  website).
- **Updates:** S11 (manual or automatic) and D5 (which releases users are
  offered).
- **Native, three ways:** L10 (the list on by default), E5 (the score's native
  term), ED-10 (the work item). L10 yes and E5 not now are consistent.
- **The bylaw:** O5 (the overview's sentence) and E6 (the rules block) rest on
  one reading of Bylaw 14600.
- **Licence and signing:** D2's free option exists only if D1 is GPL-3.0.
- **A plant's name:** L9's check of "Green Milkweed" should happen before
  QF-4 puts that name in the worked example.

## 4. Earlier choices the recommendations would reverse

Each reversal is recorded in the increment's plan file (RM-5), so it reads as a
decision, not a disappearance.

| Earlier choice | Where it was made | Reversed by |
|---|---|---|
| Kilometres as the scale bar's default | V3.06, the owner's choice | K1 |
| Learn as a front door at boot | V2.43 | S1, ST-10 |
| Field Study *Keep, and improve* (for everyone) | V3.05 surface audit | S2 (behind Advanced) |
| Phone-scan import and the splat backdrop | V1.63, V1.65 | G1, RM-2 |
| An AI choosing the plants | V1.62 onward | Y1, RM-3 |
| PolyForm Noncommercial | The repository's licence | D1 |
| Every push is a release users are offered | V1.73 and since | D5 |

## 5. Also for the owner, outside these lists

- **The data jobs** (11 §6): the spread review (F246), photographs (F247),
  toxicity (F248), the familiar animals (F249), the availability review (F227),
  and reading the bylaw.
- **Who the friend is in the repository** (FN-14): collaborator access, the
  signing account, the domain.

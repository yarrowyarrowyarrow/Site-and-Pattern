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
| S1 | The Learn door on the start screen | Remove it (every window stays reachable from View or the Learn tab); keep one quiet link to Walk a Wild Landscape; keep the door with the Lessons fix | **Remove it** (ST-10) | 5 | |
| S2 | Field Study, the photo quiz: you said *Keep, and improve* in V3.05, and now say the app is not an ID reference | Retire it; behind Advanced; keep for everyone | **Behind Advanced** (consistent with V3.05 and G2); retire it if you read it as ID training | 5 | |
| S3 | The four Lessons (keystones, food web, succession, ranges) | Keep in the Learn tab under Advanced and fold their "your design" lines into the Report card; keep as is; retire | **Advanced, and fold the "your design" lines into the Report card** | 5 | |
| S4 | The Plant Directory window | Advanced only (View menu); retire it (the same picker is Placement › Plants) | **Advanced only** | 5 | |
| S5 | Walk a Wild Landscape | Advanced only; visible to everyone from the View menu | **Advanced only** (see G6) | 5 | |
| S6 | The tagline | "Native plant yards for Edmonton"; keep "Native Habitat Designer" | **"Native plant yards for Edmonton"** | 6 | |
| S7 | Closing the start screen at launch (X or Esc) | Quit the app; open a blank map as today | **Quit** (from Help → Start Screen it only closes the screen) | 6 | |
| S8 | "Skip this screen" | Keep it as *Next time, open my last design directly*; drop it | **Keep, reworded** | 6 | |
| S9 | Naming a design | From its address, asking once at first save if there is none; ask whenever a yard is started | **From the address** (ST-5) | 6 | |
| S10 | Where the donate link appears | Help and About only; also a quiet link on the start screen once a design is saved | **Help and About only** (and the website, D6) | 14 | |
| S11 | Checking for updates | Manual, in Help; quietly at launch (a GitHub call each launch, to be named in the privacy note) | **Manual** | 14 | |
| S12 | Which start screen | A: tidy the doors (a day); B: "Your designs" (3–4 days); C: an address box (a week or more) | **B** | 6 | |
| S13 | Work from a crash when the person picks another row | Keep it automatically as "<name> (unsaved changes from <date>)"; insist on restore or discard first | **Keep it automatically** (ST-8) | 6 | |

### 2.2 Plants that lead (L, part 05)

| ID | Question | Options | Recommended | By | Answer |
|---|---|---|---|---|---|
| L1 | The two-part ranking and its weights (caterpillars 0–4 with a keystone floor, bees 0–3, birds 0–2, specialist 1, season 1; feasibility as 05 §4.2) | Accept; something simpler (Impact only, Feasibility as words) | **Accept** | 9 | |
| L2 | The nine keystone genera | Keep as they are; add genera NWF lists for neighbouring ecoregions (*Amelanchier*, *Rosa*, *Vaccinium*, *Rubus*, *Cornus*, *Picea*), which also moves habitat scores | **Keep as they are** (adding moves a headline) | 9 | |
| L3 | The yard size assumed before an outline is drawn | A 100 m² bed and a 180 m² back yard; other numbers | **100 m² and 180 m²** | 9 | |
| L4 | Chokecherry leads the list (most wildlife on record; suckers, black knot, poisonous to pets) | Let it lead with its cautions shown; cap any known spreader at Good pick | **Let it lead, with "Spreads by suckers" and "Poisonous to pets if eaten" shown** | 9 | |
| L5 | The 26 candidate spreaders (R11) | Confirm, correct or reject each (F246); and show blank spread as "Not yet checked for spreading" until reviewed | **Review them; show "Not yet checked" meanwhile** | 9 | |
| L6 | Moist-site plants (Joe-Pye Weed, Pussy Willow, Marsh Aster…) as Top picks for an unknown yard; specimen-label caterpillar records | Top picks with "Wants moist soil"; capped at Good pick until moisture is known. Specimen-label records in full or at half | **Top picks with the caution; records in full** | 9 | |
| L7 | The plant page's *What it looks like* and *Where these numbers came from* | Remove from the desktop page; keep in Advanced | **Keep in Advanced** | 9 | |
| L8 | Free-text Notes on the desktop plant page | Advanced only; not shown at all | **Not shown at all.** Some notes record plant-use traditions ("Traditional cold/flu remedy"), and the website already withholds notes under **P12**; the desktop should match | 9 | |
| L9 | A buying caution for big-box Highbush Cranberry (often the European variety); is "Green Milkweed" the right common name for *Asclepias ovalifolia*? | Yes / no to each | **Add the caution; check the name before QF-4 uses it** (`scripts/rename_common_name.py` if it changes) | 9 (L9's name before 1) | |
| L10 | The Edmonton list on by default (R30) | On; off, relying on the ranking's place term | **On** (ED-10) | 9 | |

### 2.3 Two ways to use it (M, part 02)

| ID | Question | Options | Recommended | By | Answer |
|---|---|---|---|---|---|
| M1 | How the two ways work | Simple by default with one remembered switch; ask on first run; offer it on the start screen | **One remembered switch, off by default** | 4 | |
| M2 | The 3D preview | Advanced, with one plain door from the overview; simple for everyone; advanced only | **Advanced, with one door from the overview** | 10 | |
| M3 | The switch's name | *Advanced tools*; *More tools*; *Expert mode* | **Advanced tools** | 4 | |
| M4 | Whether the Learn tab survives | See G2, S2, S3 | **Behind Advanced** | 5 | |

### 2.4 What goes (G, part 03)

| ID | Question | Options | Recommended | By | Answer |
|---|---|---|---|---|---|
| G1 | The four deletions (version picker, Import Yard Scan, the Learn door, `recipes.py`) and the AI leaving the app | Accept; accept some | **Accept all** | 1 (RM-1), 5 | |
| G2 | The Learn tab (Field Study, Lessons) | Behind Advanced; retire (about 1,200 lines, 7 test modules) | **Behind Advanced** | 5 | |
| G3 | Split view | Behind Advanced; delete (the 3D window follows the design since V3.08) | **Behind Advanced** | 5 | |
| G4 | Freeze the 3D preview: no new features; short of a crash or a wrong plant, *won't fix* | Yes; no | **Yes** | 4 | |
| G5 | Freeze the website at its current build, rebuilt only when the catalogue changes | Yes; no | **Yes** | 14 | |
| G6 | Anything in 03 §5 wanted in the simple app after all (most likely Measure, or Walk a Wild Landscape) | Name them | **None to start; revisit after the sessions (FN-9)** | 4 | |

### 2.5 How your yard is doing (O, part 06)

| ID | Question | Options | Recommended | By | Answer |
|---|---|---|---|---|---|
| O1 | The 0–100 score on the overview | No number; "Plant choice: N/100" beside the cover line; a coverage term in the score itself (a headline change: the example 63 → about 32) | **No number** | 10 | |
| O2 | Which score the Report card, PDF and critic show | The one rebased on the reference community (Habitat's, since V2.65); the universal one | **The rebased one** | 3 | |
| O3 | The cover target, and mulch as an equal choice to planting the gaps | 70% "well filled", mulch offered equally; other | **70%, mulch offered equally** | 10 | |
| O4 | Wildlife wording | Group counts "recorded as food for…" with the fixed caveat; named animals only. Plus a list of about 30 familiar Edmonton animals (F249) | **Counts with the caveat; make the list** | 10 | |
| O5 | The bylaw sentence on the overview | Read Bylaw 14600 and approve 06 §5.3's sentence; change it; drop it | **Read it, then approve or change**; never say a bed is exempt | 10 | |
| O6 | The care calendar's four bands as the only hours anywhere, retiring "Year 3+" | Yes; no | **Yes** | 3 | |
| O7 | The order of the six items | Wildlife, flowers, right plants, how full, from the street, what it will take; or lead with cost and work | **The first order** | 10 | |

### 2.6 Plan My Yard (Y, part 07)

| ID | Question | Options | Recommended | By | Answer |
|---|---|---|---|---|---|
| Y1 | The local AI | Out of the app, kept in the command line and MCP; kept as an advanced option | **Out of the app** | 5 | |
| Y2 | How a plan's look is chosen | Front or back yard; named styles (*Tidy garden*, *Meadow*, *Woodland edge*); no choice | **Front or back yard** | 12 | |
| Y3 | *How full* | Two choices by cover (70% now; 40% over two or three summers); the three densities | **Two choices by cover** | 11 | |
| Y4 | A second plan | Replaces the first by default; ask every time; adds | **Replaces by default** (undo brings it back) | 1 | |
| Y5 | Structures in a back-yard plan | At most two (a brush pile, a bee hotel); never unless asked | **At most two** | 12 | |
| Y6 | The poison boxes | Offer as *leave out plants known to be poisonous*; hide until the top 60 have records (F248) | **Offer, worded as known-poisonous** | 11 | |

### 2.7 The Edmonton edition (E, part 08)

| ID | Question | Options | Recommended | By | Answer |
|---|---|---|---|---|---|
| E1 | The Edmonton area | The V3.12 50 km circle; a larger circle; a list of municipalities | **The 50 km circle** | 7 | |
| E2 | A pin in Alberta or Saskatchewan outside the area | Plan with province natives and a warning; refuse | **Plan, with the warning** | 8 | |
| E3 | A pin outside the two provinces | Disable Plan My Yard; allow it with a warning | **Disable it** | 8 | |
| E4 | Installers | One installer with every pack, the pin choosing; one per city | **One installer** | 7 | |
| E5 | Count "native" in the simple score and words by the Edmonton list rather than the province (moves the habitat score's native term) | Yes; not now | **Not now**; the overview's "Right plants for here" already speaks in Edmonton terms | 8 | |
| E6 | The rules block (bylaw, weeds, call before you dig, neighbouring towns) | Include, re-checked every 24 months by a test; include without the towns; leave out | **Include, with the 24-month check** | 13 | |
| E7 | Edmonton's frost dates and hardiness zone | Which station and which map edition to print (May 15 / Sep 16 from City Centre is reported; the zone is 3b or 4a by source) | **City Centre's dates; NRCan's current zone, after checking both** | 8 | |
| E8 | Calgary and Regina reviews | Who answers; the same "yes or no, no reasons" rule | **The same rule; a local reviewer** | after finishing | |
| E9 | "Edmonton" in seven community names | Keep; rename by habitat so a Calgary pack can share them | **Rename by habitat** | 7 | |

### 2.8 The words (W, part 09)

| ID | Question | Options | Recommended | By | Answer |
|---|---|---|---|---|---|
| W1 | The glossary (09 §2) as the contract for the simple app: *yard outline*, *bed*, *plant*, *community* (never *polyculture*) | Accept; amend | **Accept** | 4 | |
| W2 | *Plan* for what Plan My Yard makes and what is printed, *design* for the file | Yes; no | **Yes** | 11 | |
| W3 | The ID line ("These photos help you choose plants…") | The plant page's *More* section and About; every plant page; nowhere | **More and About** | 9 | |
| W4 | *Feeds a specialist* | Reword (*Food for a fussy eater*); Advanced only | **Advanced only** | 9 | |
| W5 | Site Info as four lines with Details below | Yes; keep today's page for everyone | **Yes** | 13 | |

### 2.9 Finishing (D, part 10)

| ID | Question | Options | Recommended | By | Answer |
|---|---|---|---|---|---|
| D1 | The licence | GPL-3.0; a PySide6 port keeping PolyForm Noncommercial; a PyQt commercial licence | **GPL-3.0** | 1 | |
| D2 | Windows signing | SignPath (free; needs GPL; SignPath named as publisher); Azure Artifact Signing (US$9.99 a month; the owner named); unsigned with instructions | **SignPath** | 14 | |
| D3 | macOS | Notarize (US$99 a year); unsigned with instructions; stop building for Mac | **Unsigned with instructions, unless Mac users turn up** | 14 | |
| D4 | Satellite imagery | Read Esri's terms and keep it if they allow; move to an Esri key; street map only by default | **Read the terms first** | 14 | |
| D5 | A stable channel | Prereleases by default with a promote step; release every push | **Prereleases and a promote step** | 1 | |
| D6 | The donation platform and words | Ko-fi, Buy Me a Coffee, GitHub Sponsors, Liberapay; the words in 10 §6 | **Owner's preference**; the words as drafted | 14 | |
| D7 | The definition of finished (10 §1) | Accept; amend | **Accept** | 15 | |

### 2.10 The work plan (K, part 11)

| ID | Question | Options | Recommended | By | Answer |
|---|---|---|---|---|---|
| K1 | The scale bar's units (R18): V3.06 made kilometres the default on your choice | Automatic (metres below 1 km); keep kilometres | **Automatic** | 2 | |

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

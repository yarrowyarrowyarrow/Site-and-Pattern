# 1 · Who it is for: four people, and four it is not for

*Part of the [homeowner-path plan](README.md). No work items of its own; every
other part is checked against these people. The usability sessions in §6 are
work item **FN-9** in [10-finishing.md](10-finishing.md).*

The owner asked for the persona work to be *"expanded on"*. The first review had
one person: an Edmonton homeowner who knows little about native plants or
landscaping and wants to replace some lawn with them. That person is still the
one the simple app is for. This part adds the three people who will also open
the app, says which of them the simple app serves and which the Advanced switch
serves, and names four people it is **not** for, so a feature request from one
of them can be declined without a debate.

Pronouns: every persona is *they*. The names are placeholders.

---

## 1. The people

### A · Sam, converting a front lawn (the primary persona)

| | |
|---|---|
| **Home** | A 1960s bungalow in a mature neighbourhood (Bonnie Doon, Westmount, Lynnwood, Capilano). An older lot with a mown front lawn, a boulevard tree, a south- or north-facing front |
| **What they want** | Less lawn to mow, something that helps bees and birds, a front yard that looks *cared for*. "Native" is the word they heard; they could not name five native plants |
| **What worries them** | The neighbours and a bylaw complaint. Spending money on plants that die. Weeds. Doing it wrong and having to start again |
| **What they know** | How to search an address and drag a pin. Not a Latin name, not "forb", not "keystone", not a hardiness zone |
| **Time and money** | A few weekends, spring or fall; a few hundred to about $2,000 |
| **Computer** | A Windows laptop at 1366 × 768 or a little more; sometimes a Mac. Opens the app two or three times over a month, not daily |
| **Success, in their words** | *"I know what to buy, where it goes, and I have a printout to take outside."* And a year later: *"It looks like a garden, not like I stopped mowing."* |

**The five questions Sam brings, in the order they arise** (the first review's §2):
what can grow in my yard; what should go where so it looks intentional; what do
I buy, where, for how much; how do I prepare, plant and keep it alive; will the
neighbours or the bylaw object.

**Where Sam is served in this plan:** the start screen ([04](04-start-screen.md)),
the ranked plant list and the simple plant page ([05](05-plants-that-lead.md)),
Plan My Yard with *front yard* ([07](07-plan-my-yard.md)), the yard overview's
six items ([06](06-yard-overview.md)), the Edmonton defaults
([08](08-edmonton-edition.md)), the words ([09](09-words.md)) and the printed
plan.

### B · Jordan, a new house on a bare lot

| | |
|---|---|
| **Home** | A new build in an outer neighbourhood (the southwest or the north edge). Rough-graded clay, thin topsoil, a new fence, a back yard with nothing in it |
| **What they want** | A back yard that fills in quickly, that is safe for a child and a dog, and that is not a vegetable garden. Pollinators are a bonus |
| **What worries them** | Poisonous plants. Mud. The developer's landscaping deadline. Cost, after buying the house |
| **The constraint they may not know** | Edmonton-area developers' landscaping guidelines commonly require **full sod in the front yard** and set a deadline (one guideline: within a year of the rough-grade certificate; another: within a year of occupancy). A front-yard conversion may have to wait, or be agreed with the developer. *Not verified for every neighbourhood; the guidelines are the developer's, not the City's* |
| **Success** | *"The back yard is planted this summer, nothing in it will hurt the kid or the dog, and it is filling in by next year."* |

**What Jordan needs that Sam does not:** honest poison wording (R10;
[07](07-plan-my-yard.md) Y6), a fullness choice that says what filling costs
(06 O3, 07 Y3), the back-yard plan with a brush pile (07 Y5), and a line in the
rules block about developer guidelines (proposed for ED-14; decision E6).

### C · Robin, a gardener adding natives

| | |
|---|---|
| **Home** | Any; already has perennial beds and knows what deadheading is |
| **What they want** | To swap some beds to natives and to know *what feeds what*: which plant hosts which caterpillar, what flowers in late August, how a design scores |
| **What they know** | Common names, some Latin, how big a plant gets, how to divide and transplant |
| **Success** | *"Show me the gaps in my bloom season, and which plants carry the most caterpillars."* |

**Robin is the Advanced switch's first user.** The habitat breakdown, the Food
page, the relationship web, the community builder and the 3D preview are for
Robin ([03](03-what-goes.md) §5). They also read the website.

### D · Alex, helping someone else

| | |
|---|---|
| **Who** | A friend, a community league volunteer, a native-plant society member, a small landscaper doing one yard at a time |
| **What they want** | To sit beside Sam, plan the yard together, and leave a printout; sometimes to plan a community-league bed or a school garden |
| **What they need** | The printed plan and order file to be right; the presentation still and the narrated tour (Share, advanced) to win over a board or a neighbour; communities they can author once and place many times |
| **Success** | *"I can plan a yard with someone in an hour and hand them a plan they can follow without me."* |

**Alex is why the outputs must be trustworthy** (the single nursery list, EDF-1;
the place line, EDF-2; the PDF's legibility, R1) and why advanced tools stay
rather than go.

## 2. Who it is not for

Saying no is part of finishing. A request from one of these people is declined
politely and pointed elsewhere.

| Not for | Why not | Point them to |
|---|---|---|
| **Someone identifying a plant** | The app is not a flora and certainly not an identification guide: its plant information is there to choose and place plants. An ID mistake with a native look-alike (water parsnip and water hemlock) can be deadly | iNaturalist, the *Flora of Alberta*, a local naturalist club |
| **Acreage and restoration professionals** | Hectares, seed mixes by weight, reclamation standards and permits are a different job and a different scale; the generator caps a design at 300 plants on purpose | Professional reclamation tools and consultants |
| **People outside Alberta and Saskatchewan** | The plant list, the nurseries and the climate are the Edmonton region's (ED-8) | Their own province's native plant society |
| **A vegetable or fruit garden planner** | *Food for people* is a must-have in Plan My Yard, not the app's purpose | A vegetable garden planner |

## 3. What they all have in common

- **They use it in bursts**, weeks apart. The app must remember where they left
  off (ST-4's *Your designs*) and never lose work (ST-8, autosave).
- **They plan indoors and act outdoors.** The paper is the product as much as
  the screen (P11): the site-walk sheet, the planting map, the order file.
- **They trust the app's facts more than they should.** A blank field read as
  "safe" or "stays put" (R10, R11) is believed. The app must say *not known*
  when it does not know (P9).
- **They are at a laptop, not a big monitor.** Everything is checked at
  1366 × 768 (the V3.03 visual floors).
- **Some are older and some use a keyboard or a screen reader.** The V3.02 and
  V3.03 floors (text at 12 px or more, 4.5:1 contrast, 24 px targets, a focus
  ring, named controls) hold in the simple app too (MD-2).

## 4. Edmonton facts the personas rest on

Each with its source and whether it was checked. *Checked* means read from a
source in this pass or the repository's own data; *reported* means seen only in
a search summary, so a person should read the source before the app prints it.

| Fact | Value | Source | Status |
|---|---|---|---|
| Long grass rule | Grass and weeds on private property must not exceed 10 cm | City of Edmonton, *Tree and plant complaints*, citing the Community Standards Bylaw 14600 ([edmonton.ca](https://www.edmonton.ca/city_government/bylaws/tree-and-plant-complaints)) | **Reported.** Whether a planted bed counts as "weeds" is not stated; the app must never call a bed exempt (06 O5, 08 E6) |
| Precipitation | 455.7 mm a year at Edmonton City Centre, June and July wettest (87.1 and 91.7 mm) | `data/rainfall_fallback_prairie.json`: "Environment Canada 1981-2010 climate normal (Edmonton City Centre Airport)" | **Checked** (the shipped data; its own source not re-read) |
| Frost dates | Last spring frost about May 15, first fall frost about September 16, about 123 frost-free days, at about a 30% risk level | Old Farmer's Almanac's Edmonton page, which says it computes them from ECCC's 1981–2010 normals for Edmonton City Centre A ([almanac.com](https://cdn.almanac.com/gardening/frostdates/AB/Edmonton)) | **Reported.** The same source gives June 7 and September 1 at Edmonton Woodbend, outside the city: station matters (08 E7) |
| Hardiness zone | 3b or 4a by different sources | NRCan's map at planthardiness.gc.ca | **Not checked** (08 E7) |
| Lot sizes | Wide: listings zoned RS run from about 3,100 sq ft (a 25 × 120 ft lot) to about 9,600 sq ft; a 50 × 150 ft lot is 7,500 sq ft | City land sales and listings found by search | **Reported.** No "typical lot" figure was found; personas speak of a yard, not a size |
| New-build landscaping | Developers' guidelines in Edmonton neighbourhoods require sod in front yards and set deadlines (within a year of rough grade, or of occupancy); one requires at least 4 inches of topsoil | Sterling and Brookfield Residential guidelines found by search | **Reported**; varies by developer and neighbourhood |
| Basic landscaping permits | Not required for basic landscaping | A City of Edmonton guide, via a search summary | **Reported** |
| Native nurseries | Arnica Wildflowers, TreeTime.ca, the Edmonton Native Plant Group, ALCLA Native Plants, Wild About Flowers | `data/nurseries_master.json` | **Checked** (the shipped data); whether each still trades is not |
| The local plant list | 250 species native within 50 km of downtown, by the V3.12 rule and the owner's review | `data/local_flora.json` | **Checked** |

## 5. The persona's first season, and the moments that decide it

What Sam does, and where the plan meets each step.

| When | What Sam does | The moment that decides it | Plan item |
|---|---|---|---|
| Evening 1, 10 minutes | Installs, opens the app, sees the start screen | The first screen looks finished, and one button says what to do | ST-4 |
| | Types their address, sees their yard | The map zooms to the yard (R7) and names the design after the address | ST-5, QF-2 |
| | Outlines the front lawn, or a bed | Drawing a bed is enough, and is understood | PY-2, PY-10 |
| | *Plan my yard*: front yard, fill it now | A plan appears in the drawn bed, not on the lawn or the path | PY-2, PY-3, PY-7 |
| | Looks at the overview | Six plain answers, one of which says how full it will be | OV-1 |
| Evening 2, 30 minutes | Clicks plants, swaps two | The plant page says what it needs and why it matters, in their words | PR-3, PR-4 |
| | *Try another*; keeps the second | Trying again is free and undoable | PY-5, PY-6 |
| | Prints the plan | One nursery list, legible text, the right place name | EDF-1, EDF-2, R1 |
| A Saturday in May | Walks the yard with the site-walk sheet; buys plants | The order file matches the nursery's stock list closely enough | ED-4, availability (F226) |
| Planting day | Follows the planting map | Numbers on the map match the legend and the plants in the box | F218 (shipped) |
| July | Opens the app again: "is this a weed?" | The app says plainly it is not an ID guide and points to iNaturalist; the care calendar says what to pull this month | WD-8 (the ID line), OV-8 |
| Next spring | Sees gaps | The overview says gaps fill in years 2–4; mulch or plant more | 06 §5.1 |

## 6. Testing the plan on real people (FN-9)

The owner and their friend can run this with three to five homeowners who fit
Sam or Jordan, once the simple app is built. It is the only test that can tell
whether the plan worked. The method is the one in `docs/UI_PRINCIPLES.md`
(Krug): watch, do not help, write down where they stop.

**Setup.** A Windows laptop at 1366 × 768, a fresh install, an internet
connection, the person's own address (or a friend's). Screen recording if they
agree. 45 minutes. Say: *"We are testing the app, not you. Please think aloud."*

**Tasks**, read one at a time:

1. *"You'd like to replace some of your front lawn with native plants. Start a
   plan for your yard."* (Success: a pin on their yard and an outline or a bed,
   within 10 minutes, without help.)
2. *"Get the app to suggest a planting."* (Success: a plan in the drawn area.)
3. *"Is this planting going to look messy from the street? What would help?"*
   (Success: they find the overview's street item and name one cue.)
4. *"Find a plant in your plan that will feed caterpillars, and tell me how
   tall it gets."* (Success: they open a plant page and read both.)
5. *"Swap one plant you don't like for another that suits the same spot."*
6. *"You're going to the nursery on Saturday. Get what you'll need."* (Success:
   a printed or saved plan and order file.)
7. *"Close the app. Next week, come back to this yard."* (Success: one click
   from the start screen.)

**Record** for each task: completed or not, minutes, where they hesitated more
than ten seconds, every word they did not understand (feed these to
[09](09-words.md)'s glossary), and anything they expected that was not there.

**Done** (10's definition): four of five people complete tasks 1, 2, 6 and 7
unaided, and no task fails for the same reason twice.

## 7. What could not be checked

- **No real homeowner was observed.** The personas are built from the owner's
  brief, the first review's walkthrough and general knowledge of Edmonton
  yards, not interviews. §6 is how to fix that.
- The bylaw, frost dates, lot sizes and developer guidelines in §4 are from
  search summaries, as marked; edmonton.ca could not be opened from this
  environment.
- Which operating systems and screen sizes Edmonton homeowners actually use is
  assumed, not measured.

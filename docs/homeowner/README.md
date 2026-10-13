# The homeowner's path: the plan to finish Site & Pattern

*Start here. Written in V3.17 (13 October 2026) as the second pass of a review,
before any code changes. Nothing in this folder changes the app; it is the plan
for the work, to be carried out by the owner and a friend, increment by
increment. The first pass is [`../SALE_READINESS_REVIEW.md`](../SALE_READINESS_REVIEW.md)
(findings R1–R40).*

## What the owner asked for

> *"This pass will focus on what needs to be done to make the homeowner's path
> the strongest aspect of the app. It should also focus on how to make it
> simpler… as well as what it would mean for this app to be local to just
> Edmonton [which could be used as a template to build out the Calgary or Regina
> apps]."*

And, in the same message: the persona work expanded; the features that are "not
for a paying customer at all" slated for removal; two ways to use the app, so
advanced tools do not muddy what a novice sees; the ecosystem analysis kept as
an **overview**, because its depth hides its usefulness; the app is **not a
flora reference, certainly not an ID reference**, and should **lead with the
plants that do the most and are easiest to plant**; the start screen reworked
("feels unfinished… Continue, Open a design, and Design all are very
similar… when you click Learn it also opens the regular app"); and a plan
**fully accessible from the repository**, for a friend.

"Sell" was a metaphor. The goal is a free app, perhaps with a link to buy the
maker a coffee, finished well enough that the owner can **move on**.

## What this plan found, in eight lines

1. **The licence blocks a public release.** The repository is PolyForm
   Noncommercial; the app ships PyQt6, which is GPL v3. Relicensing as GPL-3.0
   fixes it and unlocks free code signing ([10](10-finishing.md) §2).
2. **The Learn door is broken by a one-character bug** that a safety net turned
   into "it opens the regular app" ([04](04-start-screen.md) §1.3).
3. **The generator ignores what a beginner draws**: a Garden Bed gets 1 of 42
   plants, a Lawn Area 32 of 42, and a 1 m path empties half the yard
   ([07](07-plan-my-yard.md) §2).
4. **One export prints two different nursery lists**, both partly Calgary's,
   and every PDF says "Edmonton, Alberta" wherever the yard is
   ([08](08-edmonton-edition.md) §3).
5. **The Design tab gives two scores, two wildlife counts and two sets of
   hours** for the same design, in 2,202 words ([06](06-yard-overview.md) §1).
6. **The plant list leads with the alphabet**, not with the plants that do the
   most; a ranking by impact and feasibility puts Chokecherry, Joe-Pye Weed and
   Smooth Aster first ([05](05-plants-that-lead.md) §5).
7. **Very little needs deleting**: four things, and the AI leaves the app. Most
   of what makes it busy moves behind one *Advanced tools* switch
   ([03](03-what-goes.md), [02](02-two-ways-to-use-it.md)).
8. **Edmonton-only is data, not a branch**: one region folder and one module,
   so Calgary is about a developer-week plus a local reviewer; Regina waits for
   herbarium data ([08](08-edmonton-edition.md) §5).

## The parts

| Part | What it is | Work items | Decisions |
|---|---|---|---|
| [01 · Who it is for](01-personas.md) | Four personas, four people it is not for, the Edmonton facts they rest on, and a usability test script | — (FN-9) | — |
| [02 · Two ways to use it](02-two-ways-to-use-it.md) | Simple by default, one remembered *Advanced tools* switch, and why that is not the toggle V2.42 rejected | MD-1 to MD-5 | M1–M4 |
| [03 · What goes](03-what-goes.md) | Every feature judged: delete, out of the product, advanced, simplify, keep; the ten removals that matter most | RM-1 to RM-9 | G1–G6 |
| [04 · The start screen](04-start-screen.md) | The dead Learn door diagnosed; three designs; "Your designs" recommended, with mockups | ST-1 to ST-10 | S1–S13 |
| [05 · Plants that lead](05-plants-that-lead.md) | A ranking by impact and feasibility; the top 40; the plant page in two modes | PR-1 to PR-9 | L1–L10 |
| [06 · How your yard is doing](06-yard-overview.md) | The analysis as one overview of six plain items; the defects that make the pages disagree | OV-1 to OV-14 | O1–O7 |
| [07 · Plan My Yard](07-plan-my-yard.md) | The generator for a beginner: four questions, plants where the beds are, replace and try again | PY-1 to PY-11 | Y1–Y6 |
| [08 · The Edmonton edition](08-edmonton-edition.md) | Every regional assumption audited; the region pack; how to build Calgary and Regina | ED-1 to ED-16 | E1–E9 |
| [09 · The words](09-words.md) | One name for each thing; a glossary a test can hold; the rewrite list | WD-1 to WD-8 | W1–W5 |
| [10 · Finishing](10-finishing.md) | Licence, signing, outside services, a stable release channel, donations, feedback, the runbook | FN-1 to FN-14 | D1–D7 |
| [11 · The work plan](11-work-plan.md) | Fifteen increments (V3.18 to V3.32), the quick fixes, R1–R40 mapped, feature IDs F233–F249 | QF-1 to QF-19 | K1 |
| [12 · The decisions](12-decisions.md) | All 68 owner decisions with a recommendation and when each is needed | — | all |

## How to read it

- **The owner:** this page, then [12](12-decisions.md) §1 (the ten that matter
  most), then [11](11-work-plan.md) §3 (the increments). The parts are there
  when a decision needs its reasoning.
- **The friend, before the first increment:** this page, [01](01-personas.md)
  (who it is for), [11](11-work-plan.md) §1 (how to work through it), and the
  repository's own [`CLAUDE.md`](../../CLAUDE.md) (the branch rules, the tests,
  and why `git pull` is never used on a release branch).
- **Before each increment:** the part its items come from, and that part's
  decisions in [12](12-decisions.md).

**IDs.** Work items are two letters and a number (ST-4, PY-2); defects found in
this pass are the part's letters plus F (EDF-1, OVF-3, PYF-1); the first review's
findings are R1–R40; owner decisions are one letter and a number (S12, L1, D1);
feature IDs in the project ledger are F233–F249. *P1–P13* always means a design
principle ([`../DESIGN_PHILOSOPHY.md`](../DESIGN_PHILOSOPHY.md)), never a
decision.

## Seeing the evidence yourself

**The start screen, today and proposed** (pictures, no commands): [today](img/start-screen-today.png),
[proposed, first run](img/start-screen-proposed-first-run.png),
[proposed, returning](img/start-screen-proposed-returning.png),
[proposed, after a crash](img/start-screen-proposed-recover.png).

**The broken Learn door**, in the app: open Site & Pattern, choose **Learn** on
the start screen, then **Lessons**. Expected: a Lessons window. What happens: the
main design window opens instead, with no message.

**What the generator does with drawn shapes** (07 §2):

```bash
S=$(mktemp -d)
HOME=$S XDG_DATA_HOME=$S/.local/share PYTHONPATH=. \
    python3 docs/homeowner/prototypes/plan_my_yard_probe.py
```

- *What it does:* makes a throwaway home folder (`mktemp -d`) and runs the
  probe with `HOME` pointed at it, so the app builds a fresh catalogue
  database there and never touches your own designs or database.
  `PYTHONPATH=.` lets the script import the app's code from the repository.
- *Why this way:* the probe calls the real generator, which seeds its database
  on first use; pointing `HOME` elsewhere is what keeps that seeding away from
  your real data folder.
- *Reading the output:* a table of plants placed, plants on the shape, and the
  share of the yard covered once grown. The rows to look at are *Garden Bed*
  (how many plants landed in the bed) and *Pathway* (how many plants survived a
  1 m path). It takes a minute or two.
- *Failure that looks like success:* if it prints nothing but warnings, it was
  probably run from outside the repository root; run it from the top folder.

**The plant ranking** (05 §5): the shipped-data ranking is
[`prototypes/ranking-shipped-data.csv`](prototypes/ranking-shipped-data.csv) and
the one after the proposed spread review
[`prototypes/ranking-after-spread-review.csv`](prototypes/ranking-after-spread-review.csv);
both open in a spreadsheet. To regenerate them, the prototype's docstring gives
the command (`plant_priority_prototype.py <outdir>`, with the same throwaway
`HOME` as above).

**The undefined-name guard** (04 §7):
[`prototypes/test_no_undefined_names_prototype.py`](prototypes/test_no_undefined_names_prototype.py)
is the proposed test. Run it where it is:

```bash
python3 -m unittest docs/homeowner/prototypes/test_no_undefined_names_prototype.py
```

- *What it does:* reads every module in `src/` with Python's own `symtable` and
  lists any name a function uses that nothing defines. It runs in about a
  second and needs nothing installed.
- *Reading the output:* today it fails with exactly one entry,
  `src/learn_flow.py: _go() (from line 59) uses '_sandbox_plants'`, the Lessons
  door's bug. After ST-1 it passes; that is ST-2's acceptance, once it is copied
  into `tests/`.

## What this plan does not do

- It changes no code, schema or data. Every claim about the code is a file and
  line at V3.17; the work items say how to check each one.
- It does not reopen the decisions in V2.79's *Handing this over* or the V3.12
  rules for the Edmonton list.
- It does not encode anything under P12. Where a decision touches it (the
  desktop plant page's free-text notes, L8), the recommendation is to show less,
  not more.

## What could not be checked from here

Each part ends with its own list. The common ones: no network to the City of
Edmonton's site (the bylaw and frost dates are from search summaries); no real
homeowner observed (01 §6 is the script for that); no lawyer read the licence
section; no Windows or Mac desktop (the GUI was driven in a virtual display on
Linux).
